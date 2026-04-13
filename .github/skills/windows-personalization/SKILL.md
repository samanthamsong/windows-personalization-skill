---
name: windows-personalization
description: Personalize your Windows PC using natural language — RGB lighting, themes, wallpapers, sounds, and more.
---

# Windows Personalization Skill

Use this skill when a user wants to personalize or customize their Windows PC. This includes changing RGB lighting, themes, accent colors, wallpapers, sounds, or any visual/audio aspect of their desktop.

## Capabilities

### 🔆 Dynamic Lighting (Available)
Control Dynamic Lighting compatible RGB devices (keyboards, mice, light strips, etc.) via the MCP server.

**MCP Server Setup:**
```json
{
  "servers": {
    "dynamic-lighting": {
      "command": "dotnet",
      "args": ["run", "--project", "modules/dynamic-lighting/src/DynamicLightingMcp/DynamicLightingMcp.csproj"]
    }
  }
}
```

**Tools:**

| Tool | Description |
|------|-------------|
| `create_lighting_effect` | Create a dynamic effect from a description or structured params. Patterns: solid, wave, breathe, twinkle, gradient, rainbow. Supports layered effects. |
| `set_solid_color` | Set all lamps to a single color (by name or hex). |
| `set_per_lamp_colors` | Set individual lamp colors via JSON map of `{index: "#rrggbb"}`. |
| `get_lamp_layout` | Get physical positions and metadata for all lamps on a device. |
| `list_lighting_devices` | List connected Dynamic Lighting compatible devices. |
| `stop_lighting_effect` | Stop the current lighting effect. |
| `diagnose_lighting` | Run diagnostics on a device (capabilities, lamp count, connectivity). |

**Example Prompt Mappings:**

| User Says | Tool Call |
|-----------|-----------|
| "Make my keyboard breathe with purple" | `create_lighting_effect(description="breathe purple", pattern="breathe", base_color="#9C27B0")` |
| "Ocean waves on my keyboard" | `create_lighting_effect(pattern="wave", base_color="#0066FF", accent_color="#00BBDD", speed=0.7)` |
| "Cherry blossom falling" | `create_lighting_effect(pattern="twinkle", base_color="#FFB7C5", accent_color="#FFFFFF", speed=0.5, density=0.4)` |
| "Rainbow wave" | `create_lighting_effect(pattern="rainbow", speed=1.0)` |
| "Northern lights" | `create_lighting_effect(pattern="gradient", base_color="#00FF88", accent_color="#8800FF", speed=0.3)` |
| "Set my keyboard to red" | `set_solid_color(color="red")` |
| "Starry night with blue and yellow" | `create_lighting_effect(pattern="twinkle", base_color="#001133", accent_color="#FFD700", speed=0.6, density=0.3)` |
| "Stop the lights" | `stop_lighting_effect()` |
| "What devices do I have?" | `list_lighting_devices()` |
| "Enchanted forest" | `create_lighting_effect(layers=[{"pattern":"breathe","base_color":"#003300","accent_color":"#00AA44","speed":0.3,"z_index":0},{"pattern":"twinkle","base_color":"#003300","accent_color":"#FFFF88","speed":0.8,"density":0.2,"z_index":1}])` |

**Creating Custom Effects via Natural Language:**

When a user requests a complex or creative lighting effect that goes beyond the built-in patterns (solid, wave, breathe, twinkle, gradient, rainbow), the agent should **generate a per-lamp Python effect script** and run it.

**When to generate a script vs use built-in tools:**
- Simple/standard effects → use `create_lighting_effect` with built-in patterns
- Creative, artistic, or physics-based effects (e.g. "koi fish swimming", "the matrix", "fireworks", "rainstorm") → generate a Python script

**How to generate an effect script:**

1. Create a Python file in `modules/dynamic-lighting/effects/` based on the template below
2. Implement the `render_frame(t)` function that returns a color for each key based on time
3. Run the script with `python <script_path>`

**Script structure (follow this exactly):**

```python
import os, subprocess, json, time, threading, sys, math

# Launch MCP server
EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingMcp', 'bin', 'Debug', 'net9.0-windows10.0.26100.0', 'DynamicLightingMcp.exe')
proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int, 1)], daemon=True).start()

def send(obj):
    proc.stdin.write((json.dumps(obj) + '\n').encode())
    proc.stdin.flush()
def recv():
    return json.loads(proc.stdout.readline())

# MCP handshake
send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'effect','version':'1.0'}}})
recv()
send({'jsonrpc':'2.0','method':'notifications/initialized'})
time.sleep(3)

# Keyboard layout: 87-key TKL, 7 rows
rows = [15, 15, 15, 14, 13, 8, 7]
row_offsets = [0, 0, 0.075, 0.12, 0.15, 0, 0.85]
row_kw = [1, 1, 1, 1, 1, 1.5, 1]

lamps = []
idx = 0
for ri, count in enumerate(rows):
    for ci in range(count):
        x = (row_offsets[ri] + ci * row_kw[ri]) / 15.0  # 0.0 to 1.0, left to right
        y = ri / 6.0                                      # 0.0 to 1.0, top to bottom
        lamps.append({"idx": idx, "x": x, "y": y, "row": ri, "col": ci})
        idx += 1

def lerp(c1, c2, t):
    t = max(0, min(1, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def render_frame(t):
    """Return {lamp_index_str: '#rrggbb'} for each lamp at time t seconds."""
    colors = {}
    for lamp in lamps:
        # YOUR EFFECT LOGIC HERE using lamp['x'], lamp['y'], and t
        color = (0, 0, 0)
        colors[str(lamp['idx'])] = '#{:02x}{:02x}{:02x}'.format(*color)
    return colors

# Animation loop at ~8fps
frame = 0
start = time.time()
while True:
    t = time.time() - start
    colors = render_frame(t)
    send({'jsonrpc':'2.0','id':100+frame,'method':'tools/call','params':{'name':'set_per_lamp_colors','arguments':{'lamp_colors': json.dumps(colors)}}})
    recv()
    frame += 1
    target = frame / 8.0
    if target > (time.time() - start):
        time.sleep(target - (time.time() - start))
```

**Key design principles for render_frame(t):**
- Each lamp has `x` (0–1, left to right) and `y` (0–1, top to bottom) — use these for spatial effects
- `t` is elapsed seconds — use for animation (sin waves, movement, physics)
- Return hex color strings like `'#ff6600'`
- Use `lerp()` to blend between colors
- Use `math.sin()`, `math.cos()` for waves and oscillation
- For moving objects: compute distance from each lamp to the object's position
- For layered effects: compute a base layer, then overlay elements on top
- Keep FPS at ~8 for smooth performance

**Example reference effects in `modules/dynamic-lighting/effects/`:**
- `koi-fish.py` — animated fish with body segments, water ripples, lily pads, caustic shimmer
- `cherry-blossom.py` — falling petals with wind physics
- `shooting-stars.py` — streaking particles across a night sky
- `enchanted-forest.py` — layered forest floor with firefly overlay

### 🔔 Alert-Based Lighting Rules (Available)
Set up rules that trigger lighting effects when Windows notifications arrive.

**Tools:**

| Tool | Description |
|------|-------------|
| `add_lighting_rule` | Create a rule that maps a notification trigger to a lighting action. Params: `name`, `app_name`, `action_type` (flash/pulse/solid/effect), `color`, `duration_sec`, `title_contains`, `body_contains`, `pattern`. |
| `list_lighting_rules` | List all alert rules with their triggers, actions, and enabled status. |
| `remove_lighting_rule` | Remove an alert rule by its ID. |
| `start_alert_watcher` | Start the background daemon that monitors notifications and fires rules. |
| `stop_alert_watcher` | Stop the alert watcher daemon. |

**Example Prompt Mappings:**

| User Says | Tool Call |
|-----------|-----------|
| "Flash red when I get a Teams message" | `add_lighting_rule(name="Teams flash", app_name="Microsoft Teams", action_type="flash", color="#FF0000", duration_sec=3)` |
| "Pulse blue for Outlook emails" | `add_lighting_rule(name="Outlook pulse", app_name="Microsoft Outlook", action_type="pulse", color="#0066FF", duration_sec=5)` |
| "Flash green when I get a message about deployment" | `add_lighting_rule(name="Deploy alert", app_name="Microsoft Teams", action_type="flash", color="#00FF00", title_contains="deployment")` |
| "What alert rules do I have?" | `list_lighting_rules()` |
| "Remove the Teams flash rule" | `remove_lighting_rule(rule_id="teams-flash")` |
| "Start watching for alerts" | `start_alert_watcher()` |
| "Stop the alert watcher" | `stop_alert_watcher()` |

### 🎨 Themes (Planned)
Change Windows accent color, dark/light mode, titlebar colors.
- Future: PowerShell scripts in `modules/themes/`

### 🖼️ Wallpaper (Planned)
Set desktop wallpaper, lock screen, slideshow.
- Future: PowerShell scripts in `modules/wallpaper/`

### 🔊 Sounds (Planned)
Change system sound scheme.
- Future: PowerShell scripts in `modules/sounds/`

## Routing

When the user's request involves:
- **Lighting, RGB, keyboard colors, LED effects** → Use Dynamic Lighting tools
- **Alerts, notifications, "when I get", "flash when", "notify me"** → Use Alert Rule tools
- **Theme, accent color, dark mode, light mode, titlebar** → Themes module (planned)
- **Wallpaper, background, lock screen, desktop image** → Wallpaper module (planned)
- **Sounds, notification sound, system audio** → Sounds module (planned)
- **"Make everything [color]"** or **broad personalization** → Invoke all available modules for that color/theme
