---
name: windows-personalization
description: Personalize your Windows PC using natural language — RGB lighting, themes, wallpapers, sounds, and more.
---

# Windows Personalization Skill

Use this skill when a user wants to personalize or customize their Windows PC. This includes changing RGB lighting, themes, accent colors, wallpapers, sounds, or any visual/audio aspect of their desktop.

## Capabilities

### 🔆 Dynamic Lighting (Available)
Control Dynamic Lighting compatible RGB devices (keyboards, mice, light strips, etc.).

**Prerequisites:**
- Windows 11 22H2+ with a Dynamic Lighting compatible device
- .NET 9 SDK (build once: `dotnet build modules/dynamic-lighting/DynamicLightingDriver.sln`)
- Python 3.10+
- Run `modules/dynamic-lighting/src/DynamicLightingDriver/Package/Register-AmbientLighting.ps1` once for device access

**CLI Commands:**

| Command | Description |
|---------|-------------|
| `python modules/dynamic-lighting/lighting.py set-color <color>` | Set all lamps to a single color (hex or name) |
| `python modules/dynamic-lighting/lighting.py set-per-lamp '<json>'` | Set individual lamp colors |
| `python modules/dynamic-lighting/lighting.py list-devices` | List connected Dynamic Lighting devices |
| `python modules/dynamic-lighting/lighting.py list-effects` | List available effect scripts |
| `python modules/dynamic-lighting/lighting.py run-effect <name>` | Run a named effect (e.g. koi-fish) |
| `python modules/dynamic-lighting/lighting.py stop` | Stop running effects |
| `python modules/dynamic-lighting/lighting.py set-theme <light\|dark>` | Switch the driver window between light and dark mode |
| `python modules/dynamic-lighting/lighting.py diagnose` | Run device diagnostics |

**Example Prompt Mappings:**

| User Says | Action |
|-----------|--------|
| "Set my keyboard to red" | `python modules/dynamic-lighting/lighting.py set-color red` |
| "Make my keyboard breathe with purple" | Generate a breathe effect script and run it |
| "Koi fish swimming" | `python modules/dynamic-lighting/lighting.py run-effect koi-fish` OR generate a new script |
| "Ocean waves on my keyboard" | Generate an ocean wave effect script |
| "Rainbow wave" | `python modules/dynamic-lighting/lighting.py run-effect rainbow` |
| "Stop the lights" | `python modules/dynamic-lighting/lighting.py stop` |
| "Switch to light mode" | `python modules/dynamic-lighting/lighting.py set-theme light` |
| "Use dark mode" | `python modules/dynamic-lighting/lighting.py set-theme dark` |
| "What devices do I have?" | `python modules/dynamic-lighting/lighting.py list-devices` |
| "What effects are available?" | `python modules/dynamic-lighting/lighting.py list-effects` |

**When to use CLI vs generate a script:**
- Simple solid color → `lighting.py set-color`
- Run existing effect → `lighting.py run-effect <name>`
- Creative/artistic/physics-based effects → Generate a Python script

**Creating Custom Effects via Natural Language:**

When a user requests a complex or creative lighting effect (e.g. "koi fish swimming", "the matrix", "fireworks", "rainstorm"), the agent should **generate a per-lamp Python effect script** and run it.

**How to generate an effect script:**

1. Create a Python file in `modules/dynamic-lighting/effects/` based on the template below
2. Implement the `render_frame(t)` function that returns a color for each key based on time
3. Run the script with `python <script_path>`

**IMPORTANT:** Every effect MUST include the pause-file alert coordination block (shown below). This allows notification flashes to overlay on any running effect.

**Script structure (follow this exactly):**

```python
import os, subprocess, json, time, threading, sys, math

# Launch lighting driver
EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingDriver', 'bin', 'Debug', 'net9.0-windows10.0.26100.0', 'DynamicLightingDriver.exe')
proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int, 1)], daemon=True).start()

def send(cmd):
    proc.stdin.write((cmd + '\n').encode())
    proc.stdin.flush()
def recv():
    return proc.stdout.readline().decode().strip()

# Wait for driver ready
ready = recv()
assert ready == 'READY', f'Driver not ready: {ready}'

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

# Alert flash coordination — DO NOT REMOVE
PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rules', '.pause')

# Animation loop at ~8fps
frame = 0
start = time.time()
while True:
    # Check for notification flash override
    if os.path.exists(PAUSE_FILE):
        try:
            with open(PAUSE_FILE, 'r') as f:
                alert_data = f.read().strip()
            parts = alert_data.split('|')
            flash_color = parts[0] if parts[0].startswith('#') else '#FF69B4'
            flash_duration = float(parts[1]) if len(parts) > 1 else 3.0
            all_flash = {str(lamp['idx']): flash_color for lamp in lamps}
            flash_start = time.time()
            while time.time() - flash_start < flash_duration:
                send(f"SET_LAMPS {json.dumps(all_flash)}")
                recv()
                frame += 1
                time.sleep(0.125)
        except Exception as e:
            print(f"Alert flash error: {e}")
        finally:
            try:
                os.remove(PAUSE_FILE)
            except Exception:
                pass
        continue

    t = time.time() - start
    colors = render_frame(t)
    send(f"SET_LAMPS {json.dumps(colors)}")
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

**CLI Commands:**

| Command | Description |
|---------|-------------|
| `python modules/dynamic-lighting/alert-watcher.py add --name <name> --app <app> --color <hex> --duration <sec>` | Add a notification rule |
| `python modules/dynamic-lighting/alert-watcher.py list` | List all rules |
| `python modules/dynamic-lighting/alert-watcher.py remove <rule_id>` | Remove a rule |
| `python modules/dynamic-lighting/alert-watcher.py enable <rule_id>` | Enable a rule |
| `python modules/dynamic-lighting/alert-watcher.py disable <rule_id>` | Disable a rule |
| `python modules/dynamic-lighting/alert-watcher.py test <rule_id>` | Test a rule |
| `powershell -ExecutionPolicy Bypass -File modules/dynamic-lighting/notification-watcher.ps1` | Start watching for notifications |

**Example Prompt Mappings:**

| User Says | Action |
|-----------|--------|
| "Flash red when I get a Teams message" | `python modules/dynamic-lighting/alert-watcher.py add --name "Teams flash" --app "Microsoft Teams" --color "#FF0000" --duration 3` |
| "What alert rules do I have?" | `python modules/dynamic-lighting/alert-watcher.py list` |
| "Remove the Teams rule" | `python modules/dynamic-lighting/alert-watcher.py remove <id>` |
| "Start watching for notifications" | `powershell -ExecutionPolicy Bypass -File modules/dynamic-lighting/notification-watcher.ps1` |

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
- **Lighting, RGB, keyboard colors, LED effects** → Use Dynamic Lighting CLI commands or generate effect scripts
- **Alerts, notifications, "when I get", "flash when", "notify me"** → Use alert-watcher.py CLI commands
- **Theme, accent color, dark mode, light mode, titlebar** → Themes module (planned)
- **Wallpaper, background, lock screen, desktop image** → Wallpaper module (planned)
- **Sounds, notification sound, system audio** → Sounds module (planned)
- **"Make everything [color]"** or **broad personalization** → Invoke all available modules for that color/theme
