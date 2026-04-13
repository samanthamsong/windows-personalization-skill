using System.Diagnostics;
using System.Text.Json;
using ModelContextProtocol.Server;

namespace DynamicLightingMcp;

[McpServerToolType]
public sealed class AlertTools
{
    private static readonly string RulesDir = Path.Combine(
        AppContext.BaseDirectory, "..", "..", "..", "..", "..", "rules");
    private static readonly string RulesPath = Path.Combine(RulesDir, "rules.json");
    private static readonly string WatcherScript = Path.Combine(
        AppContext.BaseDirectory, "..", "..", "..", "..", "..", "alert-watcher.py");

    private static Process? _watcherProcess;

    private static RulesFile LoadRules()
    {
        if (!File.Exists(RulesPath))
        {
            var empty = new RulesFile();
            SaveRules(empty);
            return empty;
        }
        var json = File.ReadAllText(RulesPath);
        return JsonSerializer.Deserialize<RulesFile>(json, JsonOpts) ?? new RulesFile();
    }

    private static void SaveRules(RulesFile data)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(RulesPath)!);
        var json = JsonSerializer.Serialize(data, JsonOpts);
        File.WriteAllText(RulesPath, json);
    }

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull
    };

    /// <summary>
    /// Add a lighting alert rule. When a matching Windows notification arrives, the keyboard
    /// will react with the specified lighting action.
    /// Example: add_lighting_rule(name="Teams flash", app_name="Microsoft Teams", action_type="flash", color="#FF0000")
    /// </summary>
    [McpServerTool]
    public string add_lighting_rule(
        string name,
        string app_name,
        string action_type = "flash",
        string color = "#FF0000",
        int duration_sec = 3,
        string? title_contains = null,
        string? body_contains = null,
        string? pattern = null)
    {
        var data = LoadRules();
        var ruleId = name.ToLowerInvariant().Replace(' ', '-');

        // Check for duplicate ID
        if (data.Rules.Any(r => r.Id == ruleId))
        {
            return $"A rule with ID '{ruleId}' already exists. Use remove_lighting_rule first, or choose a different name.";
        }

        var validActions = new[] { "flash", "pulse", "solid", "effect" };
        if (!validActions.Contains(action_type.ToLowerInvariant()))
        {
            return $"Invalid action_type '{action_type}'. Must be one of: {string.Join(", ", validActions)}";
        }

        var rule = new AlertRule
        {
            Id = ruleId,
            Name = name,
            Enabled = true,
            Trigger = new AlertTrigger
            {
                Type = "notification",
                AppName = app_name,
                TitleContains = title_contains,
                BodyContains = body_contains
            },
            Action = new AlertAction
            {
                Type = action_type.ToLowerInvariant(),
                Color = color,
                DurationSec = duration_sec,
                Pattern = pattern
            }
        };

        data.Rules.Add(rule);
        SaveRules(data);

        return $"✅ Created rule '{name}' (id: {ruleId})\n" +
               $"  Trigger: notifications from '{app_name}'" +
               (title_contains != null ? $" with title containing '{title_contains}'" : "") +
               (body_contains != null ? $" with body containing '{body_contains}'" : "") +
               $"\n  Action: {action_type} {color} for {duration_sec}s" +
               $"\n\nUse start_alert_watcher to begin monitoring notifications.";
    }

    /// <summary>
    /// List all lighting alert rules. Shows rule ID, name, trigger app, action type, and enabled status.
    /// </summary>
    [McpServerTool]
    public string list_lighting_rules()
    {
        var data = LoadRules();

        if (data.Rules.Count == 0)
        {
            return "No alert rules defined. Use add_lighting_rule to create one.";
        }

        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Found {data.Rules.Count} alert rule(s):\n");

        foreach (var r in data.Rules)
        {
            var status = r.Enabled ? "✅ enabled" : "⏸️ disabled";
            sb.AppendLine($"  [{r.Id}] {r.Name} ({status})");
            sb.AppendLine($"    Trigger: {r.Trigger.AppName ?? "any app"}" +
                (r.Trigger.TitleContains != null ? $", title contains '{r.Trigger.TitleContains}'" : "") +
                (r.Trigger.BodyContains != null ? $", body contains '{r.Trigger.BodyContains}'" : ""));
            sb.AppendLine($"    Action: {r.Action.Type} {r.Action.Color} for {r.Action.DurationSec}s");
            sb.AppendLine();
        }

        sb.AppendLine($"Settings: cooldown={data.Settings.CooldownSec}s");
        return sb.ToString();
    }

    /// <summary>
    /// Remove a lighting alert rule by its ID.
    /// </summary>
    [McpServerTool]
    public string remove_lighting_rule(string rule_id)
    {
        var data = LoadRules();
        var before = data.Rules.Count;
        data.Rules.RemoveAll(r => r.Id == rule_id);

        if (data.Rules.Count < before)
        {
            SaveRules(data);
            return $"✅ Removed rule '{rule_id}'.";
        }

        var available = string.Join(", ", data.Rules.Select(r => r.Id));
        return $"❌ Rule '{rule_id}' not found. Available rules: {available}";
    }

    /// <summary>
    /// Start the alert watcher background daemon. It monitors Windows notifications
    /// and triggers lighting effects when rules match. Uses polling mode by default.
    /// </summary>
    [McpServerTool]
    public string start_alert_watcher(bool polling = true)
    {
        if (_watcherProcess != null && !_watcherProcess.HasExited)
        {
            return "⚠️ Alert watcher is already running (PID: " + _watcherProcess.Id + "). Use stop_alert_watcher first.";
        }

        if (!File.Exists(WatcherScript))
        {
            return $"❌ Alert watcher script not found at: {WatcherScript}";
        }

        var args = polling ? "--polling" : "";
        try
        {
            _watcherProcess = Process.Start(new ProcessStartInfo
            {
                FileName = "python",
                Arguments = $"\"{WatcherScript}\" {args}".Trim(),
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            });

            if (_watcherProcess == null)
            {
                return "❌ Failed to start alert watcher process.";
            }

            return $"✅ Alert watcher started (PID: {_watcherProcess.Id}, mode: {(polling ? "polling" : "native")})\n" +
                   "Monitoring Windows notifications and triggering lighting rules.";
        }
        catch (Exception ex)
        {
            return $"❌ Failed to start alert watcher: {ex.Message}";
        }
    }

    /// <summary>
    /// Stop the alert watcher background daemon.
    /// </summary>
    [McpServerTool]
    public string stop_alert_watcher()
    {
        if (_watcherProcess == null || _watcherProcess.HasExited)
        {
            _watcherProcess = null;
            return "Alert watcher is not running.";
        }

        try
        {
            _watcherProcess.Kill(entireProcessTree: true);
            _watcherProcess.WaitForExit(5000);
            var pid = _watcherProcess.Id;
            _watcherProcess = null;
            return $"✅ Alert watcher stopped (was PID: {pid}).";
        }
        catch (Exception ex)
        {
            _watcherProcess = null;
            return $"⚠️ Error stopping watcher: {ex.Message}";
        }
    }

    // --- JSON model classes ---

    private class RulesFile
    {
        public List<AlertRule> Rules { get; set; } = new();
        public string? DefaultEffect { get; set; }
        public RulesSettings Settings { get; set; } = new();
    }

    private class AlertRule
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public bool Enabled { get; set; } = true;
        public AlertTrigger Trigger { get; set; } = new();
        public AlertAction Action { get; set; } = new();
    }

    private class AlertTrigger
    {
        public string Type { get; set; } = "notification";
        public string? AppName { get; set; }
        public string? TitleContains { get; set; }
        public string? BodyContains { get; set; }
    }

    private class AlertAction
    {
        public string Type { get; set; } = "flash";
        public string Color { get; set; } = "#FF0000";
        public int DurationSec { get; set; } = 3;
        public string? Pattern { get; set; }
    }

    private class RulesSettings
    {
        public int CooldownSec { get; set; } = 5;
        public int MaxConcurrentAlerts { get; set; } = 1;
    }
}
