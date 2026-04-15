using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Windows.Devices.Lights;
using Windows.UI;

namespace DynamicLightingDriver;

public sealed class CommandHandler
{
    private static readonly Regex HexColorRegex = new("#?[0-9a-fA-F]{6}", RegexOptions.Compiled);

    private static readonly Dictionary<string, Color> NamedColors = new(StringComparer.OrdinalIgnoreCase)
    {
        ["red"] = Color.FromArgb(255, 255, 0, 0),
        ["blue"] = Color.FromArgb(255, 0, 102, 255),
        ["green"] = Color.FromArgb(255, 0, 200, 83),
        ["teal"] = Color.FromArgb(255, 0, 150, 136),
        ["purple"] = Color.FromArgb(255, 156, 39, 176),
        ["orange"] = Color.FromArgb(255, 255, 152, 0),
        ["yellow"] = Color.FromArgb(255, 255, 235, 59),
        ["white"] = Color.FromArgb(255, 255, 255, 255),
        ["pink"] = Color.FromArgb(255, 233, 30, 99),
        ["cyan"] = Color.FromArgb(255, 0, 188, 212),
        ["gold"] = Color.FromArgb(255, 255, 193, 7),
        ["navy"] = Color.FromArgb(255, 0, 26, 87),
        ["coral"] = Color.FromArgb(255, 255, 127, 80),
        ["lavender"] = Color.FromArgb(255, 181, 126, 220),
    };

    private readonly LampArrayService _lampArrayService;
    private readonly EffectEngine _effectEngine;
    private readonly LightingWindow _window;
    private string? _currentEffectName;

    public CommandHandler(LampArrayService lampArrayService, EffectEngine effectEngine, LightingWindow window)
    {
        _lampArrayService = lampArrayService;
        _effectEngine = effectEngine;
        _window = window;
    }

    public async Task<string> HandleAsync(string line)
    {
        try
        {
            var spaceIdx = line.IndexOf(' ');
            var command = spaceIdx < 0 ? line.Trim().ToUpperInvariant() : line[..spaceIdx].Trim().ToUpperInvariant();
            var args = spaceIdx < 0 ? "" : line[(spaceIdx + 1)..].Trim();

            return command switch
            {
                "SET_ALL" => await HandleSetAll(args),
                "SET_LAMPS" => await HandleSetLamps(args),
                "SET_LAMPS_MULTI" => await HandleSetLampsMulti(args),
                "SET_EFFECT_NAME" => HandleSetEffectName(args),
                "SET_THEME" => HandleSetTheme(args),
                "SET_SPOTIFY" => HandleSetSpotify(args),
                "CLEAR_SPOTIFY" => HandleClearSpotify(),
                "LIST_DEVICES" => await HandleListDevices(),
                "GET_LAYOUT" => await HandleGetLayout(),
                "GET_ALL_LAYOUTS" => await HandleGetAllLayouts(),
                "DIAGNOSE" => await HandleDiagnose(),
                "CREATE_EFFECT" => await HandleCreateEffect(args),
                "STOP_EFFECT" => HandleStopEffect(),
                "QUIT" => "QUIT",
                _ => $"ERROR Unknown command: {command}",
            };
        }
        catch (Exception ex)
        {
            return $"ERROR {ex.Message}";
        }
    }

    // -----------------------------------------------------------------------
    // SET_ALL <color>
    // -----------------------------------------------------------------------
    private async Task<string> HandleSetAll(string colorArg)
    {
        if (string.IsNullOrWhiteSpace(colorArg))
            return "ERROR Color is required.";

        var targetDevice = await ResolveTargetDeviceAsync(null);
        if (targetDevice is null)
            return "ERROR No compatible Dynamic Lighting devices were found.";

        var parsed = ParseSingleColor(colorArg, Color.FromArgb(255, 255, 255, 255));
        var device = targetDevice.Value.Device;

        await EnsureDeviceAvailable(device);

        _effectEngine.StopAllEffects();
        device.SetColor(parsed);
        _effectEngine.HoldDevice(device);

        var summary = _lampArrayService.GetDeviceCapabilitySummary(device);
        _window.UpdateStatus($"🔴 Solid {FormatColor(parsed)} on {summary}");
        return $"OK Set all {device.LampCount} lamps to {FormatColor(parsed)}";
    }

    // -----------------------------------------------------------------------
    // SET_LAMPS <json>
    // -----------------------------------------------------------------------
    private async Task<string> HandleSetLamps(string jsonArg)
    {
        if (string.IsNullOrWhiteSpace(jsonArg))
            return "ERROR lamp_colors JSON is required.";

        var targetDevice = await ResolveTargetDeviceAsync(null);
        if (targetDevice is null)
            return "ERROR No compatible Dynamic Lighting devices were found.";

        var device = targetDevice.Value.Device;
        var defaultParsed = Color.FromArgb(255, 0, 0, 0);
        var lampColorMap = new Dictionary<int, Color>();

        try
        {
            using var doc = JsonDocument.Parse(jsonArg);

            if (doc.RootElement.ValueKind == JsonValueKind.Object)
            {
                foreach (var property in doc.RootElement.EnumerateObject())
                {
                    if (int.TryParse(property.Name, out var index) && index >= 0 && index < device.LampCount)
                    {
                        var colorStr = property.Value.GetString() ?? "";
                        lampColorMap[index] = ParseSingleColor(colorStr, defaultParsed);
                    }
                }
            }
            else if (doc.RootElement.ValueKind == JsonValueKind.Array)
            {
                var i = 0;
                foreach (var element in doc.RootElement.EnumerateArray())
                {
                    if (i < device.LampCount)
                    {
                        var colorStr = element.GetString() ?? "";
                        lampColorMap[i] = ParseSingleColor(colorStr, defaultParsed);
                    }
                    i++;
                }
            }
            else
            {
                return "ERROR lamp_colors must be a JSON object or array.";
            }
        }
        catch (JsonException ex)
        {
            return $"ERROR Invalid lamp_colors JSON: {ex.Message}";
        }

        if (lampColorMap.Count == 0)
            return "ERROR No valid lamp colors were parsed from the input.";

        // Fast path: update in-place if a per-lamp effect is already running
        if (_effectEngine.TryUpdatePerLampColors(device, lampColorMap, defaultParsed))
            return $"OK {lampColorMap.Count}";

        await EnsureDeviceAvailable(device);
        _effectEngine.ApplyPerLampColors(device, lampColorMap, defaultParsed);

        _window.UpdateStatus(_currentEffectName != null
            ? $"✨ {_currentEffectName}"
            : $"🎨 Custom {lampColorMap.Count}/{device.LampCount} lamps");
        return $"OK {lampColorMap.Count}";
    }

    // -----------------------------------------------------------------------
    // LIST_DEVICES
    // -----------------------------------------------------------------------
    private async Task<string> HandleListDevices()
    {
        var devices = await _lampArrayService.GetDevicesAsync();
        if (devices.Count == 0)
            return "OK No Dynamic Lighting LampArray devices are currently connected.";

        var sb = new StringBuilder("OK ");
        foreach (var device in devices)
        {
            var lampArray = await _lampArrayService.GetDeviceAsync(device.Id);
            var summary = _lampArrayService.GetDeviceCapabilitySummary(lampArray);
            sb.Append(summary);
            if (device != devices[^1])
                sb.Append(" | ");
        }
        return sb.ToString();
    }

    // -----------------------------------------------------------------------
    // GET_LAYOUT
    // -----------------------------------------------------------------------
    private async Task<string> HandleGetLayout()
    {
        var targetDevice = await ResolveTargetDeviceAsync(null);
        if (targetDevice is null)
            return "ERROR No compatible Dynamic Lighting devices were found.";

        var device = targetDevice.Value.Device;
        var lampCount = device.LampCount;
        var positions = _lampArrayService.GetAllLampPositions(device);

        var metersX = positions.Select(p => LampMeters(p.X)).ToArray();
        var metersY = positions.Select(p => LampMeters(p.Y)).ToArray();
        var boxWidth = LampMeters(device.BoundingBox.X);
        var boxHeight = LampMeters(device.BoundingBox.Y);

        var hasPositions = metersX.Any(v => v != 0d) || metersY.Any(v => v != 0d);
        var syntheticLayout = !hasPositions;

        var lamps = new List<object>(lampCount);

        if (syntheticLayout && device.LampArrayKind == LampArrayKind.Keyboard)
        {
            var grid = BuildSyntheticKeyboardGrid(lampCount);
            for (var i = 0; i < lampCount; i++)
            {
                var lampInfo = device.GetLampInfo(i);
                lamps.Add(new
                {
                    index = i,
                    x = Math.Round(grid[i].X, 3),
                    y = Math.Round(grid[i].Y, 3),
                    purpose = LampPurpose(lampInfo),
                    color_settable = LampColorSettable(lampInfo),
                });
            }
        }
        else
        {
            var minX = metersX.Length > 0 ? metersX.Min() : 0d;
            var maxX = metersX.Length > 0 ? metersX.Max() : 0d;
            var minY = metersY.Length > 0 ? metersY.Min() : 0d;
            var maxY = metersY.Length > 0 ? metersY.Max() : 0d;
            var width = boxWidth > 0 ? boxWidth : Math.Max(maxX - minX, 0.001);
            var height = boxHeight > 0 ? boxHeight : Math.Max(maxY - minY, 0.001);

            for (var i = 0; i < lampCount; i++)
            {
                var nx = Math.Round(Math.Clamp((metersX[i] - minX) / width, 0d, 1d), 3);
                var ny = Math.Round(Math.Clamp((metersY[i] - minY) / height, 0d, 1d), 3);
                var lampInfo = device.GetLampInfo(i);
                lamps.Add(new
                {
                    index = i,
                    x = nx,
                    y = ny,
                    purpose = LampPurpose(lampInfo),
                    color_settable = LampColorSettable(lampInfo),
                });
            }
        }

        var result = new
        {
            device = _lampArrayService.GetDeviceCapabilitySummary(device),
            kind = device.LampArrayKind.ToString(),
            lamp_count = lampCount,
            width_cm = Math.Round(boxWidth * 100.0),
            height_cm = Math.Round(boxHeight * 100.0),
            synthetic_layout = syntheticLayout,
            lamps,
        };

        return "OK " + JsonSerializer.Serialize(result);
    }

    // -----------------------------------------------------------------------
    // GET_ALL_LAYOUTS — returns layouts for every connected device in one call
    // -----------------------------------------------------------------------
    private async Task<string> HandleGetAllLayouts()
    {
        var devices = await _lampArrayService.GetDevicesAsync();
        if (devices.Count == 0)
            return "OK {\"devices\":[]}";

        var deviceLayouts = new List<object>();

        foreach (var info in devices)
        {
            LampArray lampArray;
            try
            {
                lampArray = await _lampArrayService.GetDeviceAsync(info.Id);
            }
            catch
            {
                continue;
            }

            var positions = _lampArrayService.GetAllLampPositions(lampArray);
            var metersX = positions.Select(p => LampMeters(p.X)).ToArray();
            var metersY = positions.Select(p => LampMeters(p.Y)).ToArray();
            var boxWidth = LampMeters(lampArray.BoundingBox.X);
            var boxHeight = LampMeters(lampArray.BoundingBox.Y);

            var hasPositions = metersX.Any(v => v != 0d) || metersY.Any(v => v != 0d);
            var syntheticLayout = !hasPositions;

            var lamps = new List<object>(lampArray.LampCount);

            if (syntheticLayout && lampArray.LampArrayKind == LampArrayKind.Keyboard)
            {
                var grid = BuildSyntheticKeyboardGrid(lampArray.LampCount);
                for (var i = 0; i < lampArray.LampCount; i++)
                {
                    var lampInfo = lampArray.GetLampInfo(i);
                    lamps.Add(new
                    {
                        index = i,
                        x = Math.Round(grid[i].X, 3),
                        y = Math.Round(grid[i].Y, 3),
                        purpose = LampPurpose(lampInfo),
                        color_settable = LampColorSettable(lampInfo),
                    });
                }
            }
            else
            {
                var minX = metersX.Length > 0 ? metersX.Min() : 0d;
                var maxX = metersX.Length > 0 ? metersX.Max() : 0d;
                var minY = metersY.Length > 0 ? metersY.Min() : 0d;
                var maxY = metersY.Length > 0 ? metersY.Max() : 0d;
                var width = boxWidth > 0 ? boxWidth : Math.Max(maxX - minX, 0.001);
                var height = boxHeight > 0 ? boxHeight : Math.Max(maxY - minY, 0.001);

                for (var i = 0; i < lampArray.LampCount; i++)
                {
                    var nx = Math.Round(Math.Clamp((metersX[i] - minX) / width, 0d, 1d), 3);
                    var ny = Math.Round(Math.Clamp((metersY[i] - minY) / height, 0d, 1d), 3);
                    var lampInfo = lampArray.GetLampInfo(i);
                    lamps.Add(new
                    {
                        index = i,
                        x = nx,
                        y = ny,
                        purpose = LampPurpose(lampInfo),
                        color_settable = LampColorSettable(lampInfo),
                    });
                }
            }

            deviceLayouts.Add(new
            {
                id = info.Id,
                name = info.Name,
                kind = lampArray.LampArrayKind.ToString(),
                lamp_count = lampArray.LampCount,
                width_cm = Math.Round(boxWidth * 100.0),
                height_cm = Math.Round(boxHeight * 100.0),
                synthetic_layout = syntheticLayout,
                lamps,
            });
        }

        var result = new { devices = deviceLayouts };
        return "OK " + JsonSerializer.Serialize(result);
    }

    // -----------------------------------------------------------------------
    // SET_LAMPS_MULTI {"<device_id>": {"0":"#ff0000",...}, ...}
    // Sets lamps on multiple devices in a single call for tight sync.
    // -----------------------------------------------------------------------
    private async Task<string> HandleSetLampsMulti(string jsonArg)
    {
        if (string.IsNullOrWhiteSpace(jsonArg))
            return "ERROR JSON mapping of device_id → lamp_colors is required.";

        try
        {
            using var doc = JsonDocument.Parse(jsonArg);
            if (doc.RootElement.ValueKind != JsonValueKind.Object)
                return "ERROR Expected a JSON object mapping device IDs to lamp color maps.";

            var totalLamps = 0;
            var deviceCount = 0;

            foreach (var deviceEntry in doc.RootElement.EnumerateObject())
            {
                var deviceId = deviceEntry.Name;
                LampArray device;
                try
                {
                    device = await _lampArrayService.GetDeviceAsync(deviceId);
                }
                catch
                {
                    continue; // skip disconnected devices
                }

                var lampColorMap = new Dictionary<int, Color>();
                var defaultParsed = Color.FromArgb(255, 0, 0, 0);

                if (deviceEntry.Value.ValueKind == JsonValueKind.Object)
                {
                    foreach (var property in deviceEntry.Value.EnumerateObject())
                    {
                        if (int.TryParse(property.Name, out var index) && index >= 0 && index < device.LampCount)
                        {
                            var colorStr = property.Value.GetString() ?? "";
                            lampColorMap[index] = ParseSingleColor(colorStr, defaultParsed);
                        }
                    }
                }

                if (lampColorMap.Count == 0)
                    continue;

                if (!_effectEngine.TryUpdatePerLampColors(device, lampColorMap, defaultParsed))
                {
                    await EnsureDeviceAvailable(device);
                    _effectEngine.ApplyPerLampColors(device, lampColorMap, defaultParsed);
                }

                totalLamps += lampColorMap.Count;
                deviceCount++;
            }

            return $"OK {totalLamps} lamps on {deviceCount} devices";
        }
        catch (JsonException ex)
        {
            return $"ERROR Invalid JSON: {ex.Message}";
        }
    }

    // -----------------------------------------------------------------------
    // DIAGNOSE
    // -----------------------------------------------------------------------
    private async Task<string> HandleDiagnose()
    {
        var sb = new StringBuilder();
        sb.AppendLine("=== Dynamic Lighting Diagnostics v5 (Ambient) ===");

        sb.AppendLine("\\nStep 1: Checking package identity...");
        try
        {
            var package = Windows.ApplicationModel.Package.Current;
            sb.AppendLine($"  Package: {package.Id.FullName}");
            sb.AppendLine($"  Publisher: {package.Id.Publisher}");
            sb.AppendLine($"  Has identity: YES");
        }
        catch (Exception ex)
        {
            sb.AppendLine($"  Has identity: NO ({ex.Message})");
        }

        sb.AppendLine("\\nStep 1b: Checking ambient lighting registry...");
        try
        {
            using var key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Lighting");
            if (key != null)
            {
                var ambientEnabled = key.GetValue("AmbientLightingEnabled");
                sb.AppendLine($"  AmbientLightingEnabled = {ambientEnabled}");
            }
        }
        catch (Exception ex)
        {
            sb.AppendLine($"  Registry read failed: {ex.Message}");
        }

        sb.AppendLine("\\nStep 2: Opening device...");
        var devices = await _lampArrayService.GetDevicesAsync();
        if (devices.Count == 0)
        {
            sb.AppendLine("  No devices found.");
            return "OK " + sb.ToString().Replace("\r\n", "\\n").Replace("\n", "\\n");
        }

        var targetId = devices[0].Id;
        LampArray lampArray;
        try
        {
            lampArray = await LampArray.FromIdAsync(targetId);
            sb.AppendLine($"  OK: {lampArray.LampCount} lamps, IsEnabled={lampArray.IsEnabled}");
            sb.AppendLine($"  IsAvailable (ambient): {lampArray.IsAvailable}");
        }
        catch (Exception ex)
        {
            sb.AppendLine($"  FAILED: {ex.Message}");
            return "OK " + sb.ToString().Replace("\r\n", "\\n").Replace("\n", "\\n");
        }

        if (!lampArray.IsAvailable)
        {
            sb.AppendLine("\\n  Device not available. Trying to bring window to foreground...");
            var brought = _window.BringToForeground();
            sb.AppendLine($"  BringToForeground result: {brought}");
            sb.AppendLine("  Waiting up to 5 seconds for availability...");
            await WaitForAvailability(lampArray, timeoutMs: 5000);
            sb.AppendLine($"  IsAvailable after wait: {lampArray.IsAvailable}");
        }

        var testColor = Color.FromArgb(255, 255, 0, 0);
        sb.AppendLine("\\nStep 3: Applying test color (RED)...");
        try
        {
            _effectEngine.StopAllEffects();
            lampArray.SetColor(testColor);
            _effectEngine.HoldDevice(lampArray);
            sb.AppendLine("  SetColor: OK");
        }
        catch (Exception ex)
        {
            sb.AppendLine($"  SetColor FAILED: {ex.Message}");
        }

        sb.AppendLine("\\n>>> Check keyboard — should be RED <<<");
        return "OK " + sb.ToString().Replace("\r\n", "\\n").Replace("\n", "\\n");
    }

    // -----------------------------------------------------------------------
    // CREATE_EFFECT <pattern> [key=value ...]
    // -----------------------------------------------------------------------
    private async Task<string> HandleCreateEffect(string args)
    {
        if (string.IsNullOrWhiteSpace(args))
            return "ERROR Provide a pattern name (solid, wave, breathe, twinkle, gradient, rainbow).";

        var parts = args.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        var pattern = parts[0];
        var kvPairs = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        for (var i = 1; i < parts.Length; i++)
        {
            var eqIdx = parts[i].IndexOf('=');
            if (eqIdx > 0)
            {
                kvPairs[parts[i][..eqIdx]] = parts[i][(eqIdx + 1)..];
            }
        }

        var targetDevice = await ResolveTargetDeviceAsync(null);
        if (targetDevice is null)
            return "ERROR No compatible Dynamic Lighting devices were found.";

        var device = targetDevice.Value.Device;
        await EnsureDeviceAvailable(device);

        // Check for layers JSON
        if (kvPairs.TryGetValue("layers", out var layersJson))
        {
            return ApplyLayeredEffectFromJson(device, layersJson, pattern);
        }

        var parsedPattern = ParsePatternParam(pattern);
        var baseColor = kvPairs.TryGetValue("base_color", out var bc)
            ? ParseSingleColor(bc, Color.FromArgb(255, 0, 80, 180))
            : Color.FromArgb(255, 0, 80, 180);
        var accentColor = kvPairs.TryGetValue("accent_color", out var ac)
            ? ParseSingleColor(ac, Lighten(baseColor, 0.25))
            : Lighten(baseColor, 0.25);
        var speed = kvPairs.TryGetValue("speed", out var sp) && float.TryParse(sp, CultureInfo.InvariantCulture, out var spVal)
            ? Math.Clamp(spVal, 0.1f, 3.0f)
            : 1.0f;
        var density = kvPairs.TryGetValue("density", out var dn) && float.TryParse(dn, CultureInfo.InvariantCulture, out var dnVal)
            ? Math.Clamp(dnVal, 0.0f, 1.0f)
            : 0.3f;
        var direction = kvPairs.TryGetValue("direction", out var dir) ? ParseDirectionParam(dir) : Direction.LeftToRight;

        var parameters = new EffectParameters(
            BaseColor: baseColor,
            AccentColor: accentColor,
            PatternType: parsedPattern,
            Speed: speed,
            Density: density,
            Direction: direction);

        _effectEngine.ApplyEffect(device, parameters);

        _window.UpdateStatus($"🌈 {parsedPattern} — {FormatColor(baseColor)} / {FormatColor(accentColor)}");
        return $"OK Started {parsedPattern} effect";
    }

    private string ApplyLayeredEffectFromJson(LampArray device, string layersJson, string description)
    {
        List<LayerInput>? layerInputs;
        try
        {
            layerInputs = JsonSerializer.Deserialize<List<LayerInput>>(layersJson, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
            });
        }
        catch (Exception ex)
        {
            return $"ERROR Invalid layers JSON: {ex.Message}";
        }

        if (layerInputs is null || layerInputs.Count == 0)
            return "ERROR Layers array is empty.";

        var effectLayers = new List<EffectLayer>();

        foreach (var input in layerInputs)
        {
            var layerPattern = !string.IsNullOrWhiteSpace(input.Pattern)
                ? ParsePatternParam(input.Pattern)
                : PatternType.Solid;
            var layerBase = ParseSingleColor(input.Base_color ?? "", Color.FromArgb(255, 0, 80, 180));
            var layerAccent = ParseSingleColor(input.Accent_color ?? "", Lighten(layerBase, 0.25));
            var layerDirection = ParseDirectionParam(input.Direction ?? "left_to_right");

            effectLayers.Add(new EffectLayer(
                PatternType: layerPattern,
                BaseColor: layerBase,
                AccentColor: layerAccent,
                Speed: Math.Clamp(input.Speed ?? 1.0f, 0.1f, 3.0f),
                Density: Math.Clamp(input.Density ?? 0.3f, 0.0f, 1.0f),
                Direction: layerDirection,
                ZIndex: input.Z_index ?? 0));
        }

        _effectEngine.ApplyLayeredEffect(device, effectLayers);

        _window.UpdateStatus($"🌈 Layered: {effectLayers.Count} layers");
        return $"OK Started {effectLayers.Count}-layer effect";
    }

    private sealed class LayerInput
    {
        public string? Pattern { get; set; }
        public string? Base_color { get; set; }
        public string? Accent_color { get; set; }
        public float? Speed { get; set; }
        public float? Density { get; set; }
        public string? Direction { get; set; }
        public int? Z_index { get; set; }
    }

    // -----------------------------------------------------------------------
    // STOP_EFFECT
    // -----------------------------------------------------------------------
    private string HandleStopEffect()
    {
        _effectEngine.StopAllEffects();
        _currentEffectName = null;
        return "OK Stopped";
    }

    private string HandleSetEffectName(string name)
    {
        _currentEffectName = string.IsNullOrWhiteSpace(name) ? null : name.Trim();
        if (_currentEffectName != null)
            _window.UpdateStatus($"✨ {_currentEffectName}");
        return "OK";
    }

    private string HandleSetTheme(string args)
    {
        var theme = args.Trim().ToLowerInvariant();
        if (theme is not ("light" or "dark"))
            return "ERROR Expected 'light' or 'dark'";
        _window.SetTheme(theme == "light");
        return $"OK {theme}";
    }

    // -----------------------------------------------------------------------
    // SET_SPOTIFY <json>
    // Expects: {"track":"...", "artist":"...", "mood":"...", "colors":["#hex",...]}
    // -----------------------------------------------------------------------
    private string HandleSetSpotify(string args)
    {
        if (string.IsNullOrWhiteSpace(args))
            return "ERROR JSON payload required";

        try
        {
            using var doc = JsonDocument.Parse(args);
            var root = doc.RootElement;

            var track = root.TryGetProperty("track", out var t) ? t.GetString() ?? "" : "";
            var artist = root.TryGetProperty("artist", out var a) ? a.GetString() ?? "" : "";
            var mood = root.TryGetProperty("mood", out var m) ? m.GetString() ?? "" : "";

            var colors = Array.Empty<string>();
            if (root.TryGetProperty("colors", out var c) && c.ValueKind == JsonValueKind.Array)
            {
                colors = c.EnumerateArray()
                    .Select(v => v.GetString() ?? "")
                    .Where(s => s.Length > 0)
                    .ToArray();
            }

            _window.SetSpotifyData(track, artist, mood, colors);
            return $"OK spotify: {track}";
        }
        catch (JsonException ex)
        {
            return $"ERROR Invalid JSON: {ex.Message}";
        }
    }

    // -----------------------------------------------------------------------
    // CLEAR_SPOTIFY
    // -----------------------------------------------------------------------
    private string HandleClearSpotify()
    {
        _window.ClearSpotifyData();
        return "OK spotify cleared";
    }

    // -----------------------------------------------------------------------
    // Shared helpers (ported from LightingTools.cs)
    // -----------------------------------------------------------------------

    private async Task<(string DeviceId, LampArray Device)?> ResolveTargetDeviceAsync(string? deviceId)
    {
        if (!string.IsNullOrWhiteSpace(deviceId))
        {
            var device = await _lampArrayService.GetDeviceAsync(deviceId);
            return (deviceId, device);
        }

        var devices = await _lampArrayService.GetDevicesAsync();
        if (devices.Count == 0)
            return null;

        var first = devices[0];
        var lampArray = await _lampArrayService.GetDeviceAsync(first.Id);
        return (first.Id, lampArray);
    }

    private async Task EnsureDeviceAvailable(LampArray device)
    {
        if (device.IsAvailable) return;

        await WaitForAvailability(device, timeoutMs: 2000);
        if (device.IsAvailable) return;

        for (int i = 0; i < 3; i++)
        {
            _window.BringToForeground();
            await WaitForAvailability(device, timeoutMs: 2000);
            if (device.IsAvailable) return;
        }
    }

    private static async Task WaitForAvailability(LampArray device, int timeoutMs = 3000)
    {
        if (device.IsAvailable) return;

        var tcs = new TaskCompletionSource<bool>();
        device.AvailabilityChanged += OnChanged;

        await Task.WhenAny(tcs.Task, Task.Delay(timeoutMs));
        device.AvailabilityChanged -= OnChanged;

        await Task.Delay(100);

        void OnChanged(LampArray sender, object args)
        {
            if (sender.IsAvailable)
                tcs.TrySetResult(true);
        }
    }

    private static Color ParseSingleColor(string input, Color fallback)
    {
        if (string.IsNullOrWhiteSpace(input))
            return fallback;

        if (NamedColors.TryGetValue(input.Trim(), out var named))
            return named;

        var hex = input.Trim();
        if (hex.StartsWith("#", StringComparison.Ordinal))
            hex = hex[1..];

        if (hex.Length == 6 && int.TryParse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var value))
        {
            var r = (byte)((value >> 16) & 0xFF);
            var g = (byte)((value >> 8) & 0xFF);
            var b = (byte)(value & 0xFF);
            return Color.FromArgb(255, r, g, b);
        }

        return fallback;
    }

    private static string FormatColor(Color color) => $"#{color.R:X2}{color.G:X2}{color.B:X2}";

    private static Color Lighten(Color color, double amount)
    {
        var clamped = Math.Clamp(amount, 0d, 1d);
        return Color.FromArgb(
            255,
            (byte)Math.Clamp((int)Math.Round(color.R + ((255 - color.R) * clamped)), 0, 255),
            (byte)Math.Clamp((int)Math.Round(color.G + ((255 - color.G) * clamped)), 0, 255),
            (byte)Math.Clamp((int)Math.Round(color.B + ((255 - color.B) * clamped)), 0, 255));
    }

    private static double LampMeters(double value)
    {
        if (value <= 0) return 0;
        return value > 10.0 ? value / 1_000_000.0 : value;
    }

    private static string LampPurpose(LampInfo lampInfo)
    {
        var value = lampInfo.GetType().GetProperty("Purposes")?.GetValue(lampInfo);
        return value?.ToString() ?? "Unknown";
    }

    private static bool LampColorSettable(LampInfo lampInfo)
    {
        var value = lampInfo.GetType().GetProperty("IsColorSettable")?.GetValue(lampInfo);
        return value is bool b ? b : true;
    }

    private static List<(double X, double Y)> BuildSyntheticKeyboardGrid(int lampCount)
    {
        int[] rowSizes = lampCount switch
        {
            <= 61 => [14, 14, 14, 13, 6],
            <= 75 => [15, 15, 15, 14, 13, 3],
            <= 87 => [15, 15, 15, 14, 13, 8, 7],
            _ =>     [16, 16, 15, 15, 14, 13, 8],
        };

        var totalAssigned = 0;
        var rows = new List<int>();
        for (var r = 0; r < rowSizes.Length; r++)
        {
            var remaining = lampCount - totalAssigned;
            if (r == rowSizes.Length - 1)
                rows.Add(remaining);
            else
                rows.Add(Math.Min(rowSizes[r], remaining));
            totalAssigned += rows[^1];
            if (totalAssigned >= lampCount) break;
        }

        var grid = new List<(double X, double Y)>(lampCount);
        var rowCount = rows.Count;
        var lampIndex = 0;

        for (var r = 0; r < rowCount && lampIndex < lampCount; r++)
        {
            var keysInRow = rows[r];
            var y = rowCount > 1 ? (double)r / (rowCount - 1) : 0.5;

            for (var c = 0; c < keysInRow && lampIndex < lampCount; c++)
            {
                var x = keysInRow > 1 ? (double)c / (keysInRow - 1) : 0.5;
                grid.Add((x, y));
                lampIndex++;
            }
        }

        return grid;
    }

    private static PatternType ParsePatternParam(string pattern)
    {
        return pattern.Trim().ToLowerInvariant() switch
        {
            "solid" => PatternType.Solid,
            "wave" => PatternType.Wave,
            "breathe" or "pulse" => PatternType.Breathe,
            "twinkle" or "sparkle" => PatternType.Twinkle,
            "gradient" or "fade" => PatternType.Gradient,
            "rainbow" or "spectrum" => PatternType.Rainbow,
            "shootingstar" or "shooting_star" or "meteor" or "comet" or "shooting" => PatternType.ShootingStar,
            _ => PatternType.Solid,
        };
    }

    private static Direction ParseDirectionParam(string direction)
    {
        return direction.Trim().ToLowerInvariant() switch
        {
            "right_to_left" or "rtl" => Direction.RightToLeft,
            "center_out" or "center" => Direction.CenterOut,
            _ => Direction.LeftToRight,
        };
    }
}
