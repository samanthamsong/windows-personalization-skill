using System.Collections.Generic;
using Windows.Devices.Enumeration;
using Windows.Devices.Lights;

namespace DynamicLightingDriver;

public sealed record LampArrayInfo(
    string Id,
    string Name,
    int LampCount,
    bool IsKeyboard,
    string LampArrayKind,
    double WidthMeters,
    double HeightMeters,
    bool AllLampsSupportRgb,
    IReadOnlyList<string> LampPurposes);

public sealed record LampPosition(int Index, double X, double Y);

public sealed class LampArrayService : IDisposable
{
    private readonly object _sync = new();
    private readonly Dictionary<string, DeviceInformation> _devicesById = new();
    private readonly DeviceWatcher _watcher;

    public LampArrayService()
    {
        var selector = LampArray.GetDeviceSelector();
        _watcher = DeviceInformation.CreateWatcher(selector);

        _watcher.Added += OnDeviceAdded;
        _watcher.Updated += OnDeviceUpdated;
        _watcher.Removed += OnDeviceRemoved;

        _watcher.Start();
    }

    public async Task<List<LampArrayInfo>> GetDevicesAsync()
    {
        List<(string Id, string Name)> deviceSnapshot;

        lock (_sync)
        {
            deviceSnapshot = _devicesById.Values
                .Select(d => (d.Id, string.IsNullOrWhiteSpace(d.Name) ? d.Id : d.Name))
                .ToList();
        }

        var results = new List<LampArrayInfo>(deviceSnapshot.Count);

        foreach (var device in deviceSnapshot)
        {
            LampArray? lampArray;

            try
            {
                lampArray = await LampArray.FromIdAsync(device.Id);
            }
            catch
            {
                continue;
            }

            if (lampArray is null)
            {
                continue;
            }

            results.Add(BuildLampArrayInfo(device.Id, device.Name, lampArray));
        }

        return results;
    }

    public async Task<LampArray> GetDeviceAsync(string deviceId)
    {
        if (string.IsNullOrWhiteSpace(deviceId))
        {
            throw new ArgumentException("Device ID is required.", nameof(deviceId));
        }

        lock (_sync)
        {
            if (!_devicesById.ContainsKey(deviceId))
            {
                throw new KeyNotFoundException($"LampArray device '{deviceId}' is not currently connected.");
            }
        }

        var lampArray = await LampArray.FromIdAsync(deviceId);

        return lampArray ?? throw new InvalidOperationException($"Unable to open LampArray device '{deviceId}'.");
    }

    public List<LampPosition> GetAllLampPositions(LampArray lampArray)
    {
        ArgumentNullException.ThrowIfNull(lampArray);

        var positions = new List<LampPosition>(lampArray.LampCount);

        for (var index = 0; index < lampArray.LampCount; index++)
        {
            var lampInfo = lampArray.GetLampInfo(index);
            positions.Add(ReadLampPosition(index, lampInfo));
        }

        return positions;
    }

    public string GetDeviceCapabilitySummary(LampArray lampArray)
    {
        ArgumentNullException.ThrowIfNull(lampArray);

        var name = ResolveDeviceName(lampArray.DeviceId);
        var kind = lampArray.LampArrayKind.ToString();
        var lampCount = lampArray.LampCount;
        var widthMeters = ToMeters(lampArray.BoundingBox.X);
        var heightMeters = ToMeters(lampArray.BoundingBox.Y);
        var allRgb = AreAllLampsColorSettable(lampArray);
        var rgbLabel = allRgb ? "RGB" : "mixed";

        var widthCm = Math.Round(widthMeters * 100.0);
        var heightCm = Math.Round(heightMeters * 100.0);

        return $"{name} ({kind}, {lampCount} {rgbLabel} lamps, {widthCm}cm x {heightCm}cm)";
    }

    private LampArrayInfo BuildLampArrayInfo(string id, string name, LampArray lampArray)
    {
        var kind = lampArray.LampArrayKind;
        var isKeyboard = kind == LampArrayKind.Keyboard;
        var widthMeters = ToMeters(lampArray.BoundingBox.X);
        var heightMeters = ToMeters(lampArray.BoundingBox.Y);
        var allRgb = AreAllLampsColorSettable(lampArray);
        var purposes = GetLampPurposes(lampArray);

        return new LampArrayInfo(
            id,
            name,
            lampArray.LampCount,
            isKeyboard,
            kind.ToString(),
            widthMeters,
            heightMeters,
            allRgb,
            purposes);
    }

    private bool AreAllLampsColorSettable(LampArray lampArray)
    {
        for (var i = 0; i < lampArray.LampCount; i++)
        {
            var lampInfo = lampArray.GetLampInfo(i);
            if (!IsLampColorSettable(lampInfo))
            {
                return false;
            }
        }

        return true;
    }

    private static bool IsLampColorSettable(LampInfo lampInfo)
    {
        var value = lampInfo.GetType().GetProperty("IsColorSettable")?.GetValue(lampInfo);
        return value switch
        {
            bool b => b,
            null => true,
            _ => true,
        };
    }

    private static IReadOnlyList<string> GetLampPurposes(LampArray lampArray)
    {
        var purposes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        for (var i = 0; i < lampArray.LampCount; i++)
        {
            var lampInfo = lampArray.GetLampInfo(i);
            var purposeValue = lampInfo.GetType().GetProperty("Purposes")?.GetValue(lampInfo);
            if (purposeValue is null)
            {
                continue;
            }

            var purposeName = purposeValue.ToString();
            if (!string.IsNullOrWhiteSpace(purposeName))
            {
                foreach (var part in purposeName.Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries))
                {
                    purposes.Add(part);
                }
            }
        }

        if (purposes.Count == 0)
        {
            return Array.Empty<string>();
        }

        return purposes.OrderBy(p => p).ToList();
    }

    private string ResolveDeviceName(string deviceId)
    {
        lock (_sync)
        {
            if (_devicesById.TryGetValue(deviceId, out var device))
            {
                return string.IsNullOrWhiteSpace(device.Name) ? deviceId : device.Name;
            }
        }

        return deviceId;
    }

    private static double ToMeters(double value)
    {
        if (value <= 0)
        {
            return 0;
        }

        return value > 10.0 ? value / 1_000_000.0 : value;
    }

    private static LampPosition ReadLampPosition(int index, LampInfo lampInfo)
    {
        var x = ReadNumericProperty(lampInfo, "PositionXInMicrometers")
            ?? ReadNumericProperty(lampInfo, "PositionX")
            ?? 0d;

        var y = ReadNumericProperty(lampInfo, "PositionYInMicrometers")
            ?? ReadNumericProperty(lampInfo, "PositionY")
            ?? 0d;

        if ((x == 0d && y == 0d) && TryReadVectorPosition(lampInfo, out var vectorX, out var vectorY))
        {
            x = vectorX;
            y = vectorY;
        }

        return new LampPosition(index, x, y);
    }

    private static bool TryReadVectorPosition(LampInfo lampInfo, out double x, out double y)
    {
        x = 0d;
        y = 0d;

        var position = lampInfo.GetType().GetProperty("Position")?.GetValue(lampInfo);
        if (position is null)
        {
            return false;
        }

        var xValue = position.GetType().GetProperty("X")?.GetValue(position);
        var yValue = position.GetType().GetProperty("Y")?.GetValue(position);

        if (xValue is null || yValue is null)
        {
            return false;
        }

        x = Convert.ToDouble(xValue);
        y = Convert.ToDouble(yValue);
        return true;
    }

    private static double? ReadNumericProperty(LampInfo lampInfo, string propertyName)
    {
        var value = lampInfo.GetType().GetProperty(propertyName)?.GetValue(lampInfo);
        return value is null ? null : Convert.ToDouble(value);
    }

    public void Dispose()
    {
        _watcher.Added -= OnDeviceAdded;
        _watcher.Updated -= OnDeviceUpdated;
        _watcher.Removed -= OnDeviceRemoved;

        if (_watcher.Status is DeviceWatcherStatus.Started or DeviceWatcherStatus.EnumerationCompleted)
        {
            _watcher.Stop();
        }
    }

    private void OnDeviceAdded(DeviceWatcher sender, DeviceInformation args)
    {
        lock (_sync)
        {
            _devicesById[args.Id] = args;
        }
    }

    private void OnDeviceUpdated(DeviceWatcher sender, DeviceInformationUpdate args)
    {
        lock (_sync)
        {
            if (_devicesById.TryGetValue(args.Id, out var current))
            {
                current.Update(args);
            }
        }
    }

    private void OnDeviceRemoved(DeviceWatcher sender, DeviceInformationUpdate args)
    {
        lock (_sync)
        {
            _devicesById.Remove(args.Id);
        }
    }
}
