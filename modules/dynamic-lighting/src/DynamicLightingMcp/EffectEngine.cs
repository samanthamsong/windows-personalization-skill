using Windows.Devices.Lights;
using Windows.Devices.Lights.Effects;
using Windows.Foundation;
using Windows.UI;

namespace DynamicLightingMcp;

public enum PatternType
{
    Solid,
    Wave,
    Breathe,
    Twinkle,
    Gradient,
    Rainbow,
    ShootingStar,
}

public enum Direction
{
    LeftToRight,
    RightToLeft,
    CenterOut,
}

public sealed record EffectParameters(
    Color BaseColor,
    Color AccentColor,
    PatternType PatternType,
    float Speed = 1.0f,
    float Density = 0.3f,
    Direction Direction = Direction.LeftToRight);

public sealed record EffectLayer(
    PatternType PatternType,
    Color BaseColor,
    Color AccentColor,
    float Speed = 1.0f,
    float Density = 0.3f,
    Direction Direction = Direction.LeftToRight,
    int ZIndex = 0);

public sealed class LayeredEffect
{
    public IReadOnlyList<EffectLayer> Layers { get; }

    public LayeredEffect(IEnumerable<EffectLayer> layers)
    {
        ArgumentNullException.ThrowIfNull(layers);
        Layers = layers.OrderBy(l => l.ZIndex).ToList();
    }
}

public sealed class EffectEngine : IDisposable
{
    private static readonly TimeSpan DefaultUpdateInterval = TimeSpan.FromMilliseconds(50);
    private static readonly TimeSpan InfiniteDuration = TimeSpan.MaxValue;

    private readonly object _sync = new();
    private readonly Random _random = new();

    private LampArrayEffectPlaylist? _activePlaylist;
    private LampArray? _activeDevice;
    private readonly List<(LampArrayCustomEffect Effect, TypedEventHandler<LampArrayCustomEffect, LampArrayUpdateRequestedEventArgs> Handler)> _activeBindings = new();

    // Tracks the last-applied effect so we can re-apply on AvailabilityChanged
    private Action<LampArray>? _pendingReapply;
    private TypedEventHandler<LampArray, object>? _availabilityHandler;
    private volatile bool _isReapplying;
    private LightingWindow? _window;

    // Per-lamp color streaming: reuse the running playlist and update colors in-place
    private Color[]? _perLampColors;
    private string? _perLampDeviceId;

    /// <summary>
    /// Set the companion window so the engine can bring it to foreground when availability is lost.
    /// </summary>
    public void SetWindow(LightingWindow window) => _window = window;

    private enum EffectivePatternType
    {
        Solid,
        Wave,
        Breathe,
        Twinkle,
        Gradient,
        Rainbow,
        Blink,
        ShootingStar,
    }

    private void TrackDeviceAvailability(LampArray device, Action<LampArray> reapply)
    {
        lock (_sync)
        {
            // Unsubscribe from previous device
            if (_activeDevice != null && _availabilityHandler != null)
            {
                _activeDevice.AvailabilityChanged -= _availabilityHandler;
            }

            _pendingReapply = reapply;

            _availabilityHandler = (sender, _) =>
            {
                // Prevent recursive re-application
                if (_isReapplying) return;

                if (!sender.IsAvailable)
                {
                    // Try to recover by bringing window to foreground with retries
                    Console.Error.WriteLine("[EffectEngine] AvailabilityChanged: lost. Recovering foreground...");
                    _window?.BringToForeground();
                    _window?.StartForegroundRetryLoop();
                    return;
                }

                // Device became available again — stop retrying and re-apply the effect
                _window?.StopRetryLoop();

                Action<LampArray>? action;
                lock (_sync)
                {
                    action = _pendingReapply;
                }

                if (action != null)
                {
                    _isReapplying = true;
                    try
                    {
                        Console.Error.WriteLine("[EffectEngine] AvailabilityChanged: available. Re-applying effect.");
                        action(sender);
                    }
                    finally
                    {
                        _isReapplying = false;
                    }
                }
            };

            device.AvailabilityChanged += _availabilityHandler;
        }
    }

    public void HoldDevice(LampArray device)
    {
        lock (_sync)
        {
            _activeDevice = device;
        }
    }

    public void HoldPlaylist(LampArrayEffectPlaylist playlist)
    {
        lock (_sync)
        {
            _activePlaylist = playlist;
        }
    }

    public void ApplyEffect(LampArray device, EffectParameters parameters)
    {
        ArgumentNullException.ThrowIfNull(device);
        ArgumentNullException.ThrowIfNull(parameters);

        var normalized = Normalize(parameters);
        var adaptedPattern = AdaptPattern(device, normalized.PatternType);
        var layout = BuildLayout(device);
        var lampIndices = layout.Select(p => p.Index).ToArray();

        if (lampIndices.Length == 0)
        {
            throw new InvalidOperationException("No color-settable lamps were found on this device.");
        }

        var effect = new LampArrayCustomEffect(device, lampIndices)
        {
            Duration = InfiniteDuration,
            UpdateInterval = DefaultUpdateInterval,
            ZIndex = 100,
        };

        TypedEventHandler<LampArrayCustomEffect, LampArrayUpdateRequestedEventArgs> handler = (_, args) =>
        {
            var elapsedSeconds = args.SinceStarted.TotalSeconds * normalized.Speed;

            foreach (var lamp in layout)
            {
                var color = ComputeLampColor(lamp, elapsedSeconds, normalized, adaptedPattern);
                args.SetColorForIndex(lamp.Index, color);
            }
        };

        effect.UpdateRequested += handler;

        var playlist = new LampArrayEffectPlaylist();
        playlist.Append(effect);

        StopEffect();

        lock (_sync)
        {
            _activePlaylist = playlist;
            _activeDevice = device;
            _activeBindings.Add((effect, handler));
        }

        _window?.SetHoldForeground(true);
        playlist.Start();

        // Track for re-apply when device becomes available again (ambient mode)
        TrackDeviceAvailability(device, d => ApplyEffect(d, parameters));
    }

    public void ApplyLayeredEffect(LampArray device, List<EffectLayer> layers)
    {
        ArgumentNullException.ThrowIfNull(device);
        ArgumentNullException.ThrowIfNull(layers);

        var layered = new LayeredEffect(layers);
        if (layered.Layers.Count == 0)
        {
            throw new ArgumentException("At least one layer is required.", nameof(layers));
        }

        var layout = BuildLayout(device);
        if (layout.Count == 0)
        {
            throw new InvalidOperationException("No color-settable lamps were found on this device.");
        }

        // Build resolved layer data for the composite callback
        var ordered = layered.Layers.OrderBy(l => l.ZIndex).ToList();
        var lowestZ = ordered[0].ZIndex;

        var resolvedLayers = new List<ResolvedLayer>();
        foreach (var layer in ordered)
        {
            var parameters = Normalize(new EffectParameters(
                layer.BaseColor,
                layer.AccentColor,
                layer.PatternType,
                layer.Speed,
                layer.Density,
                layer.Direction));

            var adaptedPattern = AdaptPattern(device, parameters.PatternType);
            var activeLampSet = new HashSet<int>(
                SelectLayerLamps(layout, layer, lowestZ).Select(l => l.Index));

            if (activeLampSet.Count == 0)
            {
                continue;
            }

            resolvedLayers.Add(new ResolvedLayer(parameters, adaptedPattern, activeLampSet));
        }

        if (resolvedLayers.Count == 0)
        {
            throw new InvalidOperationException("No active layers could be applied with the provided settings.");
        }

        // Single custom effect that composites all layers per-lamp each frame
        var lampIndices = layout.Select(p => p.Index).ToArray();
        var effect = new LampArrayCustomEffect(device, lampIndices)
        {
            Duration = InfiniteDuration,
            UpdateInterval = DefaultUpdateInterval,
            ZIndex = 100,
        };

        TypedEventHandler<LampArrayCustomEffect, LampArrayUpdateRequestedEventArgs> handler = (_, args) =>
        {
            foreach (var lamp in layout)
            {
                Color? composited = null;

                foreach (var resolved in resolvedLayers)
                {
                    if (!resolved.ActiveLamps.Contains(lamp.Index))
                    {
                        continue;
                    }

                    var elapsedSeconds = args.SinceStarted.TotalSeconds * resolved.Parameters.Speed;
                    var layerColor = ComputeLampColor(lamp, elapsedSeconds, resolved.Parameters, resolved.Pattern);

                    composited = layerColor;
                }

                if (composited.HasValue)
                {
                    args.SetColorForIndex(lamp.Index, composited.Value);
                }
            }
        };

        effect.UpdateRequested += handler;

        var playlist = new LampArrayEffectPlaylist();
        playlist.Append(effect);

        StopAllEffects();

        lock (_sync)
        {
            _activePlaylist = playlist;
            _activeDevice = device;
            _activeBindings.Add((effect, handler));
        }

        _window?.SetHoldForeground(true);
        playlist.Start();

        // Track for re-apply when device becomes available again (ambient mode)
        TrackDeviceAvailability(device, d => ApplyLayeredEffect(d, layers));
    }

    private sealed record ResolvedLayer(
        EffectParameters Parameters,
        EffectivePatternType Pattern,
        HashSet<int> ActiveLamps);

    /// <summary>
    /// Fast path for streaming per-lamp color updates. If a per-lamp effect is already
    /// running on the same device, updates the shared color array in-place without
    /// tearing down and rebuilding the playlist. Returns true if the fast path was used.
    /// </summary>
    public bool TryUpdatePerLampColors(LampArray device, IReadOnlyDictionary<int, Color> lampColors, Color defaultColor)
    {
        lock (_sync)
        {
            if (_perLampColors is null
                || _perLampDeviceId is null
                || _activePlaylist is null
                || _perLampDeviceId != device.DeviceId
                || _perLampColors.Length != device.LampCount)
            {
                return false;
            }

            // Update the shared color array in-place; the running effect callback
            // will pick up the new values on the next UpdateRequested tick.
            for (var i = 0; i < _perLampColors.Length; i++)
            {
                _perLampColors[i] = lampColors.TryGetValue(i, out var c) ? c : defaultColor;
            }

            return true;
        }
    }

    public void ApplyPerLampColors(LampArray device, IReadOnlyDictionary<int, Color> lampColors, Color defaultColor)
    {
        ArgumentNullException.ThrowIfNull(device);
        ArgumentNullException.ThrowIfNull(lampColors);

        var lampCount = device.LampCount;
        if (lampCount == 0)
        {
            throw new InvalidOperationException("No lamps found on this device.");
        }

        var lampIndices = Enumerable.Range(0, lampCount).ToArray();

        // Build the shared color array that the effect callback reads from.
        // Subsequent calls via TryUpdatePerLampColors can update this in-place.
        var colors = new Color[lampCount];
        for (var i = 0; i < lampCount; i++)
        {
            colors[i] = lampColors.TryGetValue(i, out var c) ? c : defaultColor;
        }

        var effect = new LampArrayCustomEffect(device, lampIndices)
        {
            Duration = InfiniteDuration,
            UpdateInterval = DefaultUpdateInterval,
            ZIndex = 100,
        };

        TypedEventHandler<LampArrayCustomEffect, LampArrayUpdateRequestedEventArgs> handler = (_, args) =>
        {
            // Read from the shared color array; may be updated concurrently by
            // TryUpdatePerLampColors, which is safe (Color is a small value type).
            for (var i = 0; i < colors.Length; i++)
            {
                args.SetColorForIndex(i, colors[i]);
            }
        };

        effect.UpdateRequested += handler;

        var playlist = new LampArrayEffectPlaylist();
        playlist.Append(effect);

        StopAllEffects();

        lock (_sync)
        {
            _activePlaylist = playlist;
            _activeDevice = device;
            _activeBindings.Add((effect, handler));
            _perLampColors = colors;
            _perLampDeviceId = device.DeviceId;
        }

        _window?.SetHoldForeground(true);
        playlist.Start();

        // Track for re-apply when device becomes available again (ambient mode).
        // The re-apply callback creates a fresh playlist with the latest colors.
        TrackDeviceAvailability(device, d =>
        {
            Color[] snapshot;
            lock (_sync)
            {
                snapshot = _perLampColors != null ? (Color[])_perLampColors.Clone() : colors;
            }
            var map = new Dictionary<int, Color>();
            for (var i = 0; i < snapshot.Length; i++)
            {
                map[i] = snapshot[i];
            }
            ApplyPerLampColors(d, map, defaultColor);
        });
    }

    public void StopEffect()
    {
        StopAllEffects();
    }

    public void StopAllEffects()
    {
        _window?.SetHoldForeground(false);
        _window?.StopRetryLoop();

        LampArrayEffectPlaylist? playlist;
        List<(LampArrayCustomEffect Effect, TypedEventHandler<LampArrayCustomEffect, LampArrayUpdateRequestedEventArgs> Handler)> bindings;

        lock (_sync)
        {
            playlist = _activePlaylist;
            bindings = _activeBindings.ToList();

            _activePlaylist = null;
            _activeBindings.Clear();

            // Clear per-lamp streaming state
            _perLampColors = null;
            _perLampDeviceId = null;

            // Clear re-apply tracking
            _pendingReapply = null;
            if (_activeDevice != null && _availabilityHandler != null)
            {
                _activeDevice.AvailabilityChanged -= _availabilityHandler;
                _availabilityHandler = null;
            }
            _activeDevice = null;
        }

        foreach (var binding in bindings)
        {
            binding.Effect.UpdateRequested -= binding.Handler;
        }

        playlist?.Stop();
    }

    public void Dispose()
    {
        StopAllEffects();
    }

    private static IEnumerable<LampPoint> SelectLayerLamps(IReadOnlyList<LampPoint> layout, EffectLayer layer, int baseZIndex)
    {
        if (layer.ZIndex <= baseZIndex)
        {
            return layout;
        }

        var density = Math.Clamp(layer.Density, 0.0f, 1.0f);
        if (density <= 0f)
        {
            return Array.Empty<LampPoint>();
        }

        if (density >= 1f)
        {
            return layout;
        }

        return layout.Where(lamp => IsLampInOverlaySubset(lamp.Index, layer.ZIndex, density));
    }

    private static bool IsLampInOverlaySubset(int lampIndex, int zIndex, float density)
    {
        var hash = (lampIndex * 73856093) ^ (zIndex * 19349663);
        var normalized = (Math.Abs(hash) % 1000) / 1000.0;
        return normalized < density;
    }

    private Color ComputeLampColor(LampPoint lamp, double elapsedSeconds, EffectParameters parameters, EffectivePatternType pattern)
    {
        return pattern switch
        {
            EffectivePatternType.Solid => parameters.BaseColor,
            EffectivePatternType.Wave => Blend(parameters.BaseColor, parameters.AccentColor, WaveAmount(lamp, elapsedSeconds, parameters)),
            EffectivePatternType.Breathe => Blend(parameters.BaseColor, parameters.AccentColor, BreatheAmount(elapsedSeconds)),
            EffectivePatternType.Twinkle => TwinkleColor(parameters),
            EffectivePatternType.Gradient => Blend(parameters.BaseColor, parameters.AccentColor, SpatialCoordinate(lamp, parameters.Direction)),
            EffectivePatternType.Rainbow => RainbowColor(lamp, elapsedSeconds, parameters.Direction),
            EffectivePatternType.Blink => BlinkColor(elapsedSeconds, parameters),
            EffectivePatternType.ShootingStar => ShootingStarColor(lamp, elapsedSeconds, parameters),
            _ => parameters.BaseColor,
        };
    }

    private static double WaveAmount(LampPoint lamp, double elapsedSeconds, EffectParameters parameters)
    {
        var spatial = SpatialCoordinate(lamp, parameters.Direction);
        var normalizedScrollCyclesPerSecond = 0.30 / Math.Max(lamp.DeviceWidthMeters, 0.1);
        var phase = (spatial * Math.PI * 2.0) - (elapsedSeconds * Math.PI * 2.0 * normalizedScrollCyclesPerSecond);
        return (Math.Sin(phase) + 1.0) * 0.5;
    }

    private static double BreatheAmount(double elapsedSeconds)
    {
        var phase = elapsedSeconds * Math.PI * 2.0 * 0.2;
        return (Math.Sin(phase) + 1.0) * 0.5;
    }

    private Color TwinkleColor(EffectParameters parameters)
    {
        var sparkle = _random.NextDouble() < parameters.Density;
        return sparkle ? parameters.AccentColor : parameters.BaseColor;
    }

    private static Color BlinkColor(double elapsedSeconds, EffectParameters parameters)
    {
        var phase = ((int)Math.Floor(elapsedSeconds * 2.0)) % 2;
        return phase == 0 ? parameters.BaseColor : parameters.AccentColor;
    }

    /// <summary>
    /// Shooting star effect: multiple meteors streak across the keyboard with glowing tails.
    /// Uses deterministic pseudo-random star generation so it's stateless (no per-frame tracking).
    /// Each star has a unique Y-row, speed offset, and spawn period derived from its slot index.
    /// </summary>
    private static Color ShootingStarColor(LampPoint lamp, double elapsedSeconds, EffectParameters parameters)
    {
        const int starSlots = 6;
        const double tailLength = 0.25;
        const double headGlow = 0.04;

        var bestBrightness = 0.0;

        for (var i = 0; i < starSlots; i++)
        {
            // Deterministic properties for each star slot
            var hash1 = ((i * 73856093) ^ 19349663) & 0x7FFFFFFF;
            var hash2 = ((i * 19349663) ^ 83492791) & 0x7FFFFFFF;
            var hash3 = ((i * 83492791) ^ 73856093) & 0x7FFFFFFF;

            var starY = (hash1 % 1000) / 1000.0;        // Y position (0-1)
            var period = 2.0 + (hash2 % 1000) / 250.0;  // cycle period: 2-6 seconds
            var speedVar = 0.8 + (hash3 % 1000) / 1000.0 * 0.6; // speed variance: 0.8-1.4

            // Star travels from X=1+tail to X=0-head (right to left)
            var cycleTime = elapsedSeconds * speedVar / period;
            var phase = cycleTime - Math.Floor(cycleTime); // 0..1 within cycle
            var starX = 1.0 + tailLength - phase * (1.0 + tailLength + headGlow);

            // Distance from lamp to star's path
            var dx = lamp.X - starX;
            var dy = lamp.Y - starY;
            var yProximity = Math.Exp(-dy * dy / 0.01); // narrow vertical band

            if (yProximity < 0.05) continue;

            // Head: bright glow just ahead and at the star position
            if (dx >= -headGlow && dx <= headGlow)
            {
                var headIntensity = 1.0 - Math.Abs(dx) / headGlow;
                bestBrightness = Math.Max(bestBrightness, headIntensity * yProximity);
            }
            // Tail: fading trail behind the star (dx > 0 means lamp is behind)
            else if (dx > 0 && dx < tailLength)
            {
                var tailIntensity = 1.0 - dx / tailLength;
                tailIntensity *= tailIntensity; // quadratic falloff for comet-like tail
                bestBrightness = Math.Max(bestBrightness, tailIntensity * yProximity * 0.7);
            }
        }

        if (bestBrightness < 0.01) return parameters.BaseColor;

        // Head is white/bright accent, tail transitions to accent color
        var starColor = Blend(parameters.AccentColor, Color.FromArgb(255, 255, 255, 255), bestBrightness);
        return Blend(parameters.BaseColor, starColor, Math.Min(bestBrightness * 1.5, 1.0));
    }

    private static Color RainbowColor(LampPoint lamp, double elapsedSeconds, Direction direction)
    {
        var coordinate = SpatialCoordinate(lamp, direction);
        var normalizedScrollCyclesPerSecond = 0.25 / Math.Max(lamp.DeviceWidthMeters, 0.1);
        var hue = ((coordinate + (elapsedSeconds * normalizedScrollCyclesPerSecond)) % 1.0) * 360.0;
        return FromHsv(hue, 1.0, 1.0);
    }

    private static EffectivePatternType AdaptPattern(LampArray device, PatternType requested)
    {
        var lampCount = device.LampCount;
        var kindName = device.LampArrayKind.ToString();
        var isMouseLike = kindName.Equals("Mouse", StringComparison.OrdinalIgnoreCase)
            || kindName.Equals("MousePad", StringComparison.OrdinalIgnoreCase)
            || kindName.Equals("Mousepad", StringComparison.OrdinalIgnoreCase);
        var isStripOrChassis = kindName.Equals("LampStrip", StringComparison.OrdinalIgnoreCase)
            || kindName.Equals("Chassis", StringComparison.OrdinalIgnoreCase);

        if ((requested is PatternType.Wave or PatternType.Gradient) && lampCount < 10)
        {
            return requested == PatternType.Wave ? EffectivePatternType.Breathe : EffectivePatternType.Blink;
        }

        if ((requested is PatternType.Wave or PatternType.Gradient) && isMouseLike)
        {
            return EffectivePatternType.Breathe;
        }

        if ((requested is PatternType.Wave or PatternType.Gradient) && isStripOrChassis)
        {
            return requested == PatternType.Wave ? EffectivePatternType.Wave : EffectivePatternType.Gradient;
        }

        return requested switch
        {
            PatternType.Solid => EffectivePatternType.Solid,
            PatternType.Wave => EffectivePatternType.Wave,
            PatternType.Breathe => EffectivePatternType.Breathe,
            PatternType.Twinkle => EffectivePatternType.Twinkle,
            PatternType.Gradient => EffectivePatternType.Gradient,
            PatternType.Rainbow => EffectivePatternType.Rainbow,
            PatternType.ShootingStar => EffectivePatternType.ShootingStar,
            _ => EffectivePatternType.Solid,
        };
    }

    private static double SpatialCoordinate(LampPoint lamp, Direction direction)
    {
        return direction switch
        {
            Direction.LeftToRight => lamp.X,
            Direction.RightToLeft => 1.0 - lamp.X,
            Direction.CenterOut => lamp.DistanceFromCenter,
            _ => lamp.X,
        };
    }

    private static EffectParameters Normalize(EffectParameters parameters)
    {
        var speed = Math.Clamp(parameters.Speed, 0.1f, 3.0f);
        var density = Math.Clamp(parameters.Density, 0.0f, 1.0f);

        return parameters with
        {
            Speed = speed,
            Density = density,
        };
    }

    private static List<LampPoint> BuildLayout(LampArray device)
    {
        var boundingBox = device.BoundingBox;
        var boxWidth = ToMeters(boundingBox.X);
        var boxHeight = ToMeters(boundingBox.Y);

        var rawPoints = new List<(int Index, double X, double Y)>(device.LampCount);

        for (var i = 0; i < device.LampCount; i++)
        {
            var lampInfo = device.GetLampInfo(i);
            if (!IsLampColorSettable(lampInfo))
            {
                continue;
            }

            rawPoints.Add((i, ToMeters(ReadX(lampInfo)), ToMeters(ReadY(lampInfo))));
        }

        if (rawPoints.Count == 0)
        {
            return new List<LampPoint>();
        }

        // Detect all-zero positions and fall back to synthetic grid
        var hasPositions = rawPoints.Any(p => p.X != 0d || p.Y != 0d);
        if (!hasPositions)
        {
            return BuildSyntheticLayout(rawPoints, boxWidth);
        }

        var minX = rawPoints.Min(p => p.X);
        var maxX = rawPoints.Max(p => p.X);
        var minY = rawPoints.Min(p => p.Y);
        var maxY = rawPoints.Max(p => p.Y);

        var hasBoundingBox = boxWidth > 0 && boxHeight > 0;
        var width = hasBoundingBox ? boxWidth : Math.Max(maxX - minX, 0.001d);
        var height = hasBoundingBox ? boxHeight : Math.Max(maxY - minY, 0.001d);
        var originX = minX;
        var originY = minY;

        return rawPoints
            .Select(p =>
            {
                var normalizedX = Math.Clamp((p.X - originX) / width, 0d, 1d);
                var normalizedY = Math.Clamp((p.Y - originY) / height, 0d, 1d);
                var dx = normalizedX - 0.5;
                var dy = normalizedY - 0.5;
                var distance = Math.Clamp(Math.Sqrt((dx * dx) + (dy * dy)) / 0.7071067811865476, 0d, 1d);
                return new LampPoint(p.Index, normalizedX, normalizedY, distance, width);
            })
            .ToList();
    }

    private static List<LampPoint> BuildSyntheticLayout(List<(int Index, double X, double Y)> rawPoints, double deviceWidth)
    {
        var count = rawPoints.Count;

        // Approximate keyboard rows
        int[] rowSizes = count switch
        {
            <= 61 => [14, 14, 14, 13, 6],
            <= 75 => [15, 15, 15, 14, 13, 3],
            <= 87 => [15, 15, 15, 14, 13, 8, 7],
            _ =>     [16, 16, 15, 15, 14, 13, 8],
        };

        var rows = new List<int>();
        var totalAssigned = 0;
        for (var r = 0; r < rowSizes.Length; r++)
        {
            var remaining = count - totalAssigned;
            if (r == rowSizes.Length - 1)
            {
                rows.Add(remaining);
            }
            else
            {
                rows.Add(Math.Min(rowSizes[r], remaining));
            }
            totalAssigned += rows[^1];
            if (totalAssigned >= count) break;
        }

        var result = new List<LampPoint>(count);
        var rowCount = rows.Count;
        var lampIdx = 0;

        for (var r = 0; r < rowCount && lampIdx < count; r++)
        {
            var keysInRow = rows[r];
            var ny = rowCount > 1 ? (double)r / (rowCount - 1) : 0.5;

            for (var c = 0; c < keysInRow && lampIdx < count; c++)
            {
                var nx = keysInRow > 1 ? (double)c / (keysInRow - 1) : 0.5;
                var dx = nx - 0.5;
                var dy = ny - 0.5;
                var distance = Math.Clamp(Math.Sqrt((dx * dx) + (dy * dy)) / 0.7071067811865476, 0d, 1d);
                var idx = rawPoints[lampIdx].Index;
                result.Add(new LampPoint(idx, nx, ny, distance, deviceWidth > 0 ? deviceWidth : 0.35));
                lampIdx++;
            }
        }

        return result;
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

    private static double ToMeters(double value)
    {
        if (value <= 0)
        {
            return 0;
        }

        return value > 10.0 ? value / 1_000_000.0 : value;
    }

    private static double ReadX(LampInfo lampInfo)
    {
        return ReadNumericProperty(lampInfo, "PositionXInMicrometers")
            ?? ReadNumericProperty(lampInfo, "PositionX")
            ?? ReadVectorProperty(lampInfo, "X")
            ?? 0d;
    }

    private static double ReadY(LampInfo lampInfo)
    {
        return ReadNumericProperty(lampInfo, "PositionYInMicrometers")
            ?? ReadNumericProperty(lampInfo, "PositionY")
            ?? ReadVectorProperty(lampInfo, "Y")
            ?? 0d;
    }

    private static double? ReadNumericProperty(LampInfo lampInfo, string propertyName)
    {
        var value = lampInfo.GetType().GetProperty(propertyName)?.GetValue(lampInfo);
        return value is null ? null : Convert.ToDouble(value);
    }

    private static double? ReadVectorProperty(LampInfo lampInfo, string axis)
    {
        var position = lampInfo.GetType().GetProperty("Position")?.GetValue(lampInfo);
        if (position is null)
        {
            return null;
        }

        var value = position.GetType().GetProperty(axis)?.GetValue(position);
        return value is null ? null : Convert.ToDouble(value);
    }

    private static Color Blend(Color from, Color to, double amount)
    {
        var clamped = Math.Clamp(amount, 0d, 1d);

        return Color.FromArgb(
            255,
            BlendChannel(from.R, to.R, clamped),
            BlendChannel(from.G, to.G, clamped),
            BlendChannel(from.B, to.B, clamped));
    }

    private static byte BlendChannel(byte from, byte to, double amount)
    {
        var value = from + ((to - from) * amount);
        return (byte)Math.Clamp((int)Math.Round(value), 0, 255);
    }

    private static Color FromHsv(double hue, double saturation, double value)
    {
        hue = ((hue % 360.0) + 360.0) % 360.0;
        saturation = Math.Clamp(saturation, 0.0, 1.0);
        value = Math.Clamp(value, 0.0, 1.0);

        var c = value * saturation;
        var x = c * (1 - Math.Abs(((hue / 60.0) % 2) - 1));
        var m = value - c;

        var (r1, g1, b1) = hue switch
        {
            < 60 => (c, x, 0d),
            < 120 => (x, c, 0d),
            < 180 => (0d, c, x),
            < 240 => (0d, x, c),
            < 300 => (x, 0d, c),
            _ => (c, 0d, x),
        };

        var r = (byte)Math.Clamp((int)Math.Round((r1 + m) * 255), 0, 255);
        var g = (byte)Math.Clamp((int)Math.Round((g1 + m) * 255), 0, 255);
        var b = (byte)Math.Clamp((int)Math.Round((b1 + m) * 255), 0, 255);

        return Color.FromArgb(255, r, g, b);
    }

    private sealed record LampPoint(int Index, double X, double Y, double DistanceFromCenter, double DeviceWidthMeters);
}
