using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;
using DynamicLightingMcp;
using ModelContextProtocol.Server;
using Windows.UI;

namespace DynamicLightingMcp;

[McpServerToolType]
public sealed class LightingTools
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

    public LightingTools(LampArrayService lampArrayService, EffectEngine effectEngine, LightingWindow window)
    {
        _lampArrayService = lampArrayService;
        _effectEngine = effectEngine;
        _window = window;
    }

    /// <summary>
    /// Creates a dynamic lighting effect on the keyboard. Accepts a natural language description
    /// which is used as a fallback, OR explicit structured parameters for precise control.
    /// When calling from an AI agent, ALWAYS translate the user's creative intent into the structured
    /// parameters. Examples: "japanese cherry blossom falling" → pattern=twinkle, base_color=#FFB7C5,
    /// accent_color=#FFFFFF, speed=0.5, density=0.4. "Ocean waves" → pattern=wave, base_color=#0066FF,
    /// accent_color=#00BBDD, speed=0.7. "Northern lights" → pattern=gradient, base_color=#00FF88,
    /// accent_color=#8800FF, speed=0.3. Available patterns: solid, wave, breathe, twinkle, gradient, rainbow.
    /// Available directions: left_to_right, right_to_left, center_out. Speed range: 0.1 (slow) to 3.0 (fast).
    /// Density range: 0.0 (sparse) to 1.0 (dense), mainly affects twinkle pattern.
    /// For complex scenes, provide a JSON array of layers in the "layers" parameter. Each layer object
    /// has: pattern, base_color, accent_color, speed, density, direction, z_index. Lower z_index layers
    /// render first (background); higher z_index layers overlay on top with density controlling coverage.
    /// Example for "enchanted forest": layers=[{"pattern":"breathe","base_color":"#003300","accent_color":"#00AA44","speed":0.3,"density":1.0,"z_index":0},{"pattern":"twinkle","base_color":"#003300","accent_color":"#FFFF88","speed":0.8,"density":0.2,"z_index":1}]
    /// Use layers when a single pattern cannot capture the full mood (e.g., a breathing base with sparkle overlay).
    /// </summary>
    [McpServerTool]
    public async Task<string> create_lighting_effect(
        string description,
        string? pattern = null,
        string? base_color = null,
        string? accent_color = null,
        float speed = 1.0f,
        float density = 0.3f,
        string direction = "left_to_right",
        string? layers = null,
        string? deviceId = null)
    {
        if (string.IsNullOrWhiteSpace(description) && string.IsNullOrWhiteSpace(pattern) && string.IsNullOrWhiteSpace(layers))
        {
            return "Provide a description, pattern, or layers.";
        }

        var targetDevice = await ResolveTargetDeviceAsync(deviceId);
        if (targetDevice is null)
        {
            return "No compatible Dynamic Lighting devices were found.";
        }

        var device = targetDevice.Value.Device;

        await EnsureDeviceAvailable(device);

        // If layers JSON is provided, use the layered effect path
        if (!string.IsNullOrWhiteSpace(layers))
        {
            return ApplyLayeredEffectFromJson(device, layers, description);
        }

        // Use structured params if provided, otherwise fall back to keyword parsing from description
        var text = description ?? "";
        var parsedPattern = pattern != null ? ParsePatternParam(pattern) : ParsePatternFromText(text);
        var (fallbackBase, fallbackAccent) = ParseColorsFromText(text);
        var parsedBase = base_color != null
            ? ParseSingleColor(base_color, fallbackBase)
            : fallbackBase;
        var parsedAccent = accent_color != null
            ? ParseSingleColor(accent_color, Lighten(parsedBase, 0.25))
            : fallbackAccent;
        if (pattern == null && speed == 1.0f)
            speed = ParseSpeedFromText(text);
        var parsedDirection = ParseDirectionParam(direction);

        var parameters = new EffectParameters(
            BaseColor: parsedBase,
            AccentColor: parsedAccent,
            PatternType: parsedPattern,
            Speed: Math.Clamp(speed, 0.1f, 3.0f),
            Density: Math.Clamp(density, 0.0f, 1.0f),
            Direction: parsedDirection);

        _effectEngine.ApplyEffect(device, parameters);

        var summary = _lampArrayService.GetDeviceCapabilitySummary(device);
        _window.UpdateStatus($"🌈 {parsedPattern} — {FormatColor(parsedBase)} / {FormatColor(parsedAccent)}");
        return $"Applied {parsedPattern} effect on {summary} with base={FormatColor(parsedBase)}, accent={FormatColor(parsedAccent)}, speed={speed:0.0}, density={density:0.0}.";
    }

    private string ApplyLayeredEffectFromJson(Windows.Devices.Lights.LampArray device, string layersJson, string description)
    {
        List<LayerInput>? layerInputs;
        try
        {
            layerInputs = System.Text.Json.JsonSerializer.Deserialize<List<LayerInput>>(layersJson, new System.Text.Json.JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
            });
        }
        catch (Exception ex)
        {
            return $"Invalid layers JSON: {ex.Message}";
        }

        if (layerInputs is null || layerInputs.Count == 0)
        {
            return "Layers array is empty.";
        }

        var effectLayers = new List<EffectLayer>();
        var layerDescriptions = new List<string>();

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

            layerDescriptions.Add($"{layerPattern}(z={input.Z_index ?? 0}, {FormatColor(layerBase)}/{FormatColor(layerAccent)})");
        }

        _effectEngine.ApplyLayeredEffect(device, effectLayers);

        var summary = _lampArrayService.GetDeviceCapabilitySummary(device);
        var layersSummary = string.Join(" + ", layerDescriptions);
        _window.UpdateStatus($"🌈 Layered: {layersSummary}");
        return $"Applied {effectLayers.Count}-layer effect on {summary}: {layersSummary}.";
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

    [McpServerTool]
    public async Task<string> list_lighting_devices()
    {
        var devices = await _lampArrayService.GetDevicesAsync();
        if (devices.Count == 0)
        {
            return "No Dynamic Lighting LampArray devices are currently connected.";
        }

        var builder = new StringBuilder();
        builder.AppendLine("Connected Dynamic Lighting devices:");

        foreach (var device in devices)
        {
            builder.Append("- ")
                .Append(device.Name)
                .Append(" | id=")
                .Append(device.Id)
                .Append(" | lamps=")
                .Append(device.LampCount)
                .AppendLine();
        }

        return builder.ToString().TrimEnd();
    }

    [McpServerTool]
    public string stop_lighting_effect()
    {
        _effectEngine.StopAllEffects();
        return "Stopped active lighting effects.";
    }

    [McpServerTool]
    public async Task<string> diagnose_lighting(string? deviceId = null)
    {
        var sb = new StringBuilder();
        sb.AppendLine("=== Dynamic Lighting Diagnostics v5 (Ambient) ===");

        // Step 1: Check package identity and ambient registration
        sb.AppendLine("\nStep 1: Checking package identity...");
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

        sb.AppendLine("\nStep 1b: Checking ambient lighting registry...");
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

        // Step 2: Open device and check availability
        sb.AppendLine("\nStep 2: Opening device...");
        var devices = await _lampArrayService.GetDevicesAsync();
        if (devices.Count == 0)
        {
            sb.AppendLine("  No devices found.");
            return sb.ToString();
        }

        var targetId = deviceId ?? devices[0].Id;
        Windows.Devices.Lights.LampArray lampArray;
        try
        {
            lampArray = await Windows.Devices.Lights.LampArray.FromIdAsync(targetId);
            sb.AppendLine($"  OK: {lampArray.LampCount} lamps, IsEnabled={lampArray.IsEnabled}");
            sb.AppendLine($"  IsAvailable (ambient): {lampArray.IsAvailable}");
        }
        catch (Exception ex)
        {
            sb.AppendLine($"  FAILED: {ex.Message}");
            return sb.ToString();
        }

        if (!lampArray.IsAvailable)
        {
            sb.AppendLine("\n  Device not available. Trying to bring window to foreground...");
            var brought = _window.BringToForeground();
            sb.AppendLine($"  BringToForeground result: {brought}");
            sb.AppendLine("  Waiting up to 5 seconds for availability...");
            await WaitForAvailability(lampArray, timeoutMs: 5000);
            sb.AppendLine($"  IsAvailable after wait: {lampArray.IsAvailable}");
        }

        // Step 3: Apply test color
        var testColor = Color.FromArgb(255, 255, 0, 0);
        sb.AppendLine("\nStep 3: Applying test color (RED)...");
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

        sb.AppendLine("\n>>> Check keyboard — should be RED <<<");
        return sb.ToString();
    }

    [McpServerTool]
    public async Task<string> set_solid_color(string color, string? deviceId = null)
    {
        if (string.IsNullOrWhiteSpace(color))
        {
            return "Color is required.";
        }

        var targetDevice = await ResolveTargetDeviceAsync(deviceId);
        if (targetDevice is null)
        {
            return "No compatible Dynamic Lighting devices were found.";
        }

        var parsed = ParseSingleColor(color, Color.FromArgb(255, 255, 255, 255));
        var device = targetDevice.Value.Device;

        await EnsureDeviceAvailable(device);

        _effectEngine.StopAllEffects();
        device.SetColor(parsed);
        _effectEngine.HoldDevice(device);

        var summary = _lampArrayService.GetDeviceCapabilitySummary(device);
        _window.UpdateStatus($"🔴 Solid {FormatColor(parsed)} on {summary}");
        return $"Set solid color {FormatColor(parsed)} on {summary}.";
    }

    /// <summary>
    /// Returns the full spatial layout of all lamps on a connected lighting device.
    /// Use this to discover lamp indices, their physical positions, and capabilities before calling set_per_lamp_colors.
    /// Returns JSON with device info and a lamps array. Each lamp has: index (integer — use as key in set_per_lamp_colors),
    /// x (0.0=left to 1.0=right), y (0.0=top to 1.0=bottom), purpose (e.g. "Control", "Accent"),
    /// and color_settable (boolean). Call this first when you want full per-lamp creative control.
    /// When the device firmware does not report per-lamp positions, a synthetic keyboard grid is generated.
    /// </summary>
    [McpServerTool]
    public async Task<string> get_lamp_layout(string? deviceId = null)
    {
        var targetDevice = await ResolveTargetDeviceAsync(deviceId);
        if (targetDevice is null)
        {
            return "No compatible Dynamic Lighting devices were found.";
        }

        var device = targetDevice.Value.Device;
        var lampCount = device.LampCount;
        var positions = _lampArrayService.GetAllLampPositions(device);

        var metersX = positions.Select(p => LampMeters(p.X)).ToArray();
        var metersY = positions.Select(p => LampMeters(p.Y)).ToArray();
        var boxWidth = LampMeters(device.BoundingBox.X);
        var boxHeight = LampMeters(device.BoundingBox.Y);

        // Detect if the device reports no meaningful positions (all zeros)
        var hasPositions = metersX.Any(v => v != 0d) || metersY.Any(v => v != 0d);
        var syntheticLayout = !hasPositions;

        var lamps = new List<object>(lampCount);

        if (syntheticLayout && device.LampArrayKind == Windows.Devices.Lights.LampArrayKind.Keyboard)
        {
            // Generate a synthetic keyboard grid layout
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

        return System.Text.Json.JsonSerializer.Serialize(result);
    }

    private static List<(double X, double Y)> BuildSyntheticKeyboardGrid(int lampCount)
    {
        // Standard keyboard row sizes (approximate key counts per row)
        int[] rowSizes = lampCount switch
        {
            <= 61 => [14, 14, 14, 13, 6],          // 60% keyboard
            <= 75 => [15, 15, 15, 14, 13, 3],      // 75% keyboard
            <= 87 => [15, 15, 15, 14, 13, 8, 7],   // TKL keyboard
            _ =>     [16, 16, 15, 15, 14, 13, 8],   // full-size
        };

        // Distribute lamps across rows, adjusting last row to absorb remainder
        var totalAssigned = 0;
        var rows = new List<int>();
        for (var r = 0; r < rowSizes.Length; r++)
        {
            var remaining = lampCount - totalAssigned;
            var rowsLeft = rowSizes.Length - r;
            if (r == rowSizes.Length - 1)
            {
                rows.Add(remaining);
            }
            else
            {
                var size = Math.Min(rowSizes[r], remaining);
                rows.Add(size);
            }
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

    /// <summary>
    /// Sets individual lamps to specific colors for fully custom lighting effects beyond presets.
    /// Call get_lamp_layout first to discover lamp indices and their positions.
    /// lamp_colors accepts either:
    /// (1) A JSON object mapping lamp index to color: {"0": "#FF0000", "1": "blue", "42": "#00FF00"}
    /// (2) A JSON array of colors where array position = lamp index: ["#FF0000", "blue", "#00FF00", ...]
    /// Colors can be hex (#RRGGBB) or named (red, blue, green, purple, cyan, orange, pink, gold, etc.).
    /// Unspecified lamps use default_color (defaults to black/off).
    /// This enables creating arbitrary artistic effects, game-specific layouts, per-key highlighting,
    /// custom gradients, random color patterns, or any effect not possible with the preset patterns.
    /// </summary>
    [McpServerTool]
    public async Task<string> set_per_lamp_colors(
        string lamp_colors,
        string? default_color = null,
        string? deviceId = null)
    {
        if (string.IsNullOrWhiteSpace(lamp_colors))
        {
            return "lamp_colors JSON is required. Use get_lamp_layout to discover lamp indices.";
        }

        var targetDevice = await ResolveTargetDeviceAsync(deviceId);
        if (targetDevice is null)
        {
            return "No compatible Dynamic Lighting devices were found.";
        }

        var device = targetDevice.Value.Device;

        var defaultParsed = ParseSingleColor(default_color ?? "", Color.FromArgb(255, 0, 0, 0));
        var lampColorMap = new Dictionary<int, Color>();

        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(lamp_colors);

            if (doc.RootElement.ValueKind == System.Text.Json.JsonValueKind.Object)
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
            else if (doc.RootElement.ValueKind == System.Text.Json.JsonValueKind.Array)
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
                return "lamp_colors must be a JSON object or array.";
            }
        }
        catch (System.Text.Json.JsonException ex)
        {
            return $"Invalid lamp_colors JSON: {ex.Message}";
        }

        if (lampColorMap.Count == 0)
        {
            return "No valid lamp colors were parsed from the input.";
        }

        // Fast path: if a per-lamp effect is already running on this device,
        // just update the color array in-place without rebuilding the playlist.
        // This avoids the expensive teardown/rebuild cycle during rapid animation
        // loops and keeps the playlist alive across foreground switches.
        if (_effectEngine.TryUpdatePerLampColors(device, lampColorMap, defaultParsed))
        {
            return $"Updated colors for {lampColorMap.Count} lamps (streaming).";
        }

        await EnsureDeviceAvailable(device);
        _effectEngine.ApplyPerLampColors(device, lampColorMap, defaultParsed);

        var summary = _lampArrayService.GetDeviceCapabilitySummary(device);
        _window.UpdateStatus($"🎨 Custom {lampColorMap.Count}/{device.LampCount} lamps");
        return $"Applied custom colors to {lampColorMap.Count} of {device.LampCount} lamps on {summary}.";
    }

    private async Task<(string DeviceId, Windows.Devices.Lights.LampArray Device)?> ResolveTargetDeviceAsync(string? deviceId)
    {
        if (!string.IsNullOrWhiteSpace(deviceId))
        {
            var device = await _lampArrayService.GetDeviceAsync(deviceId);
            return (deviceId, device);
        }

        var devices = await _lampArrayService.GetDevicesAsync();
        if (devices.Count == 0)
        {
            return null;
        }

        var first = devices[0];
        var lampArray = await _lampArrayService.GetDeviceAsync(first.Id);
        return (first.Id, lampArray);
    }

    private async Task EnsureDeviceAvailable(Windows.Devices.Lights.LampArray device)
    {
        if (device.IsAvailable) return;

        // Ambient mode: wait briefly for the system to grant access
        await WaitForAvailability(device, timeoutMs: 2000);
        if (device.IsAvailable) return;

        // Fallback: bring companion window to foreground to gain device access
        // Retry a few times since SetForegroundWindow may not succeed immediately
        for (int i = 0; i < 3; i++)
        {
            _window.BringToForeground();
            await WaitForAvailability(device, timeoutMs: 2000);
            if (device.IsAvailable) return;
        }
    }

    private static async Task WaitForAvailability(Windows.Devices.Lights.LampArray device, int timeoutMs = 3000)
    {
        if (device.IsAvailable) return;

        var tcs = new TaskCompletionSource<bool>();
        device.AvailabilityChanged += OnChanged;

        var completed = await Task.WhenAny(tcs.Task, Task.Delay(timeoutMs));
        device.AvailabilityChanged -= OnChanged;

        // Small extra delay for the compositor to settle
        await Task.Delay(100);

        void OnChanged(Windows.Devices.Lights.LampArray sender, object args)
        {
            if (sender.IsAvailable)
                tcs.TrySetResult(true);
        }
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

    private static PatternType ParsePatternFromText(string text)
    {
        var lower = text.ToLowerInvariant();
        if (ContainsAny(lower, "wave", "ocean", "flowing", "ripple", "water")) return PatternType.Wave;
        if (ContainsAny(lower, "breathe", "pulse", "glow", "heartbeat")) return PatternType.Breathe;
        if (ContainsAny(lower, "twinkle", "sparkle", "stars", "starry", "falling", "rain", "snow", "petal", "blossom", "firefly")) return PatternType.Twinkle;
        if (ContainsAny(lower, "gradient", "fade", "blend", "aurora", "northern", "sunset", "sunrise")) return PatternType.Gradient;
        if (ContainsAny(lower, "rainbow", "spectrum", "pride", "prism")) return PatternType.Rainbow;
        if (ContainsAny(lower, "shooting", "meteor", "comet", "streak")) return PatternType.ShootingStar;
        return PatternType.Breathe; // more interesting default than solid
    }

    private static float ParseSpeedFromText(string text)
    {
        var lower = text.ToLowerInvariant();
        if (ContainsAny(lower, "slow", "gentle", "calm", "lazy", "soft")) return 0.5f;
        if (ContainsAny(lower, "fast", "rapid", "energetic", "intense", "rave")) return 2.0f;
        return 0.8f;
    }

    private static (Color Base, Color Accent) ParseColorsFromText(string text)
    {
        var found = new List<Color>(2);
        var lower = text.ToLowerInvariant();

        foreach (var match in HexColorRegex.Matches(text).Cast<Match>())
        {
            found.Add(ParseSingleColor(match.Value, Color.FromArgb(255, 255, 255, 255)));
            if (found.Count == 2) return (found[0], found[1]);
        }

        foreach (var kvp in NamedColors)
        {
            if (ContainsWord(lower, kvp.Key))
            {
                found.Add(kvp.Value);
                if (found.Count == 2) return (found[0], found[1]);
            }
        }

        // Theme-based color inference
        if (ContainsAny(lower, "cherry", "blossom", "sakura")) { found.Add(Color.FromArgb(255, 255, 183, 197)); found.Add(Color.FromArgb(255, 255, 255, 255)); }
        else if (ContainsAny(lower, "ocean", "sea", "water")) { found.Add(Color.FromArgb(255, 0, 102, 255)); found.Add(Color.FromArgb(255, 0, 204, 220)); }
        else if (ContainsAny(lower, "fire", "flame", "lava")) { found.Add(Color.FromArgb(255, 255, 80, 0)); found.Add(Color.FromArgb(255, 255, 200, 0)); }
        else if (ContainsAny(lower, "aurora", "northern")) { found.Add(Color.FromArgb(255, 0, 255, 136)); found.Add(Color.FromArgb(255, 136, 0, 255)); }
        else if (ContainsAny(lower, "sunset", "dusk")) { found.Add(Color.FromArgb(255, 255, 100, 50)); found.Add(Color.FromArgb(255, 150, 0, 200)); }
        else if (ContainsAny(lower, "forest", "nature", "leaf")) { found.Add(Color.FromArgb(255, 0, 180, 60)); found.Add(Color.FromArgb(255, 100, 220, 0)); }
        else if (ContainsAny(lower, "snow", "ice", "frost", "winter")) { found.Add(Color.FromArgb(255, 200, 230, 255)); found.Add(Color.FromArgb(255, 255, 255, 255)); }
        else if (ContainsAny(lower, "night", "midnight", "dark")) { found.Add(Color.FromArgb(255, 20, 0, 80)); found.Add(Color.FromArgb(255, 80, 0, 160)); }
        else if (ContainsAny(lower, "star", "galaxy", "cosmos", "space")) { found.Add(Color.FromArgb(255, 10, 10, 60)); found.Add(Color.FromArgb(255, 255, 255, 200)); }

        if (found.Count >= 2) return (found[0], found[1]);
        if (found.Count == 1) return (found[0], Lighten(found[0], 0.25));
        return (Color.FromArgb(255, 0, 80, 180), Color.FromArgb(255, 255, 213, 79));
    }

    private static Color ParseSingleColor(string input, Color fallback)
    {
        if (string.IsNullOrWhiteSpace(input))
        {
            return fallback;
        }

        if (NamedColors.TryGetValue(input.Trim(), out var named))
        {
            return named;
        }

        var hex = input.Trim();
        if (hex.StartsWith("#", StringComparison.Ordinal))
        {
            hex = hex[1..];
        }

        if (hex.Length == 6 && int.TryParse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var value))
        {
            var r = (byte)((value >> 16) & 0xFF);
            var g = (byte)((value >> 8) & 0xFF);
            var b = (byte)(value & 0xFF);
            return Color.FromArgb(255, r, g, b);
        }

        return fallback;
    }

    private static Color Lighten(Color color, double amount)
    {
        var clamped = Math.Clamp(amount, 0d, 1d);
        return Color.FromArgb(
            255,
            (byte)Math.Clamp((int)Math.Round(color.R + ((255 - color.R) * clamped)), 0, 255),
            (byte)Math.Clamp((int)Math.Round(color.G + ((255 - color.G) * clamped)), 0, 255),
            (byte)Math.Clamp((int)Math.Round(color.B + ((255 - color.B) * clamped)), 0, 255));
    }

    private static bool ContainsAny(string text, params string[] keywords)
    {
        return keywords.Any(k => text.Contains(k, StringComparison.Ordinal));
    }

    private static bool ContainsWord(string text, string word)
    {
        return Regex.IsMatch(text, $"\\b{Regex.Escape(word)}\\b", RegexOptions.IgnoreCase);
    }

    private static string FormatColor(Color color)
    {
        return $"#{color.R:X2}{color.G:X2}{color.B:X2}";
    }

    private static double LampMeters(double value)
    {
        if (value <= 0) return 0;
        return value > 10.0 ? value / 1_000_000.0 : value;
    }

    private static string LampPurpose(Windows.Devices.Lights.LampInfo lampInfo)
    {
        var value = lampInfo.GetType().GetProperty("Purposes")?.GetValue(lampInfo);
        return value?.ToString() ?? "Unknown";
    }

    private static bool LampColorSettable(Windows.Devices.Lights.LampInfo lampInfo)
    {
        var value = lampInfo.GetType().GetProperty("IsColorSettable")?.GetValue(lampInfo);
        return value is bool b ? b : true;
    }
}
