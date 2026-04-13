# 🎨 Windows Personalization Skill

Personalize your Windows PC with natural language. Tell an AI assistant *"make everything pink!"* and watch it transform your RGB lighting, themes, wallpaper, and more.

This is a [Copilot Skill](https://docs.github.com/en/copilot/building-copilot-skills) — a set of instructions and tools that AI agents can invoke automatically.

## ✨ What's Inside

| Module | Status | Description |
|--------|--------|-------------|
| [🔆 Dynamic Lighting](modules/dynamic-lighting/) | ✅ Available | Control RGB devices via CLI + per-lamp Python effects |
| [🎨 Themes](modules/themes/) | 🔜 Planned | Accent colors, dark/light mode, titlebars |
| [🖼️ Wallpaper](modules/wallpaper/) | 🔜 Planned | Desktop wallpaper, lock screen, slideshows |
| [🔊 Sounds](modules/sounds/) | 🔜 Planned | System sound schemes |

## 🚀 Quick Start

### Prerequisites
- Windows 11 22H2+
- .NET 9 SDK
- Python 3.10+ (for per-lamp effects)
- A [Dynamic Lighting](https://support.microsoft.com/en-us/windows/control-your-dynamic-lighting-devices-in-windows-8e9f9b1f-6844-4c5e-9873-d836e87fcb7f) compatible device

### 1. Build & register the device driver

```powershell
cd modules/dynamic-lighting
dotnet build DynamicLightingDriver.sln
```

Then register the app for package identity (required for LampArray API access):

```powershell
cd src/DynamicLightingDriver/Package
.\Register-AmbientLighting.ps1
```

> ⚠️ **Important:** After registration, go to **Settings → Personalization → Dynamic Lighting → Background light control** and move **Dynamic Lighting Driver** to the **top of the priority list**. This ensures the driver takes precedence over other lighting apps.

### 2. Try it!

```powershell
# Set your keyboard to a color
python modules/dynamic-lighting/lighting.py set-color "#FF6600"

# Run a per-lamp effect
python modules/dynamic-lighting/lighting.py run-effect koi-fish

# List available effects
python modules/dynamic-lighting/lighting.py list-effects

# Stop running effects
python modules/dynamic-lighting/lighting.py stop
```

Or tell your AI agent (Copilot, etc.) what you want in natural language — it will use the CLI commands and generate effects automatically.

### 3. Try it!

> "Make my keyboard breathe with purple"
>
> "Ocean waves on my keyboard"
>
> "Set everything to red"

## 🐟 Effect Gallery

Per-lamp Python scripts that create pixel-level animations on your keyboard.

| Effect | Description |
|--------|-------------|
| [Koi Fish](modules/dynamic-lighting/effects/koi-fish.py) | Animated koi swimming across a pond with lily pads and water ripples |
| [Flower Garden](modules/dynamic-lighting/effects/flower-garden.py) | Blooming flowers with butterflies drifting across the keyboard |
| [Cherry Blossom](modules/dynamic-lighting/effects/cherry-blossom.py) | Falling cherry blossom petals |
| [Shooting Stars](modules/dynamic-lighting/effects/shooting-stars.py) | Streaking stars across a night sky |
| [Enchanted Forest](modules/dynamic-lighting/effects/enchanted-forest.py) | Layered forest with firefly sparkles |
| [Monet Waterlilies](modules/dynamic-lighting/effects/monet-waterlilies.py) | Impressionist water and lilies |
| [Paris Twinkle](modules/dynamic-lighting/effects/paris-twinkle.py) | Parisian city lights at night |
| [Rainbow](modules/dynamic-lighting/effects/rainbow.py) | Per-lamp rainbow gradient |
| [Star Wars Lightsaber](modules/dynamic-lighting/effects/star-wars-lightsaber.py) | Lightsaber ignition effect |
| [Hello Kitty](modules/dynamic-lighting/effects/hello-kitty.py) | Hello Kitty themed colors |


## 🛠️ Create Your Own Effect

Just describe what you want in natural language — the agent generates the Python script and runs it on your keyboard.

> **You:** "Create a rainstorm effect with blue drops falling down the keyboard"
>
> **Agent:** *generates `rainstorm.py` using the per-lamp scripting framework, runs it*

### How it works

The agent uses the `render_frame(t)` pattern — a function that computes a color for every key on your keyboard based on time and position. Each key has an `(x, y)` coordinate (0–1), and the function runs at ~8fps.

For simple effects (solid color, wave, breathe), the agent calls CLI commands directly. For creative or artistic effects, it generates a Python script.

### Manual creation

If you prefer to code by hand:
   ```powershell
   cp modules/dynamic-lighting/effects/_template.py modules/dynamic-lighting/effects/my-effect.py
   ```

2. Edit `render_frame(t)` — this function receives the current time and returns a color for each key:
   ```python
   def render_frame(t):
       colors = {}
       for lamp in lamps:
           # Use lamp['x'], lamp['y'] for position, t for animation
           wave = math.sin(lamp['x'] * math.pi * 2 - t * 2.0) * 0.5 + 0.5
           color = lerp(COLOR_A, COLOR_B, wave)
           colors[str(lamp['idx'])] = '#{:02x}{:02x}{:02x}'.format(*color)
       return colors
   ```

3. Run it:
   ```powershell
   python modules/dynamic-lighting/effects/my-effect.py
   ```

## 🗺️ Roadmap

This skill is the first step toward full Windows personalization via natural language:

- ✅ **V1:** Dynamic Lighting (RGB devices via CLI)
- ✅ **V2:** Alert-based lighting (flash keyboard on Windows notifications)
- 🔜 **V3:** Themes (accent color, dark/light mode)
- 🔜 **V4:** Wallpaper + Sounds
- 🔮 **Future:** Multi-surface orchestration ("make my whole PC feel like the ocean")

## 🔔 Notification Alerts

Flash your keyboard whenever you get a Windows notification — Teams messages, Outlook emails, any app.

### How it works

1. `notification-watcher.ps1` monitors the Windows Event Log for toast notifications
2. When a toast arrives, it writes a color + duration to `rules/.pause`
3. The running effect reads the pause file, flashes the color, then resumes the animation

### Quick start

```powershell
# Terminal 1: Run any effect
python modules/dynamic-lighting/effects/flower-garden.py

# Terminal 2: Start the notification watcher (hot pink flash for 3s)
powershell -ExecutionPolicy Bypass -File modules/dynamic-lighting/notification-watcher.ps1

# Custom color/duration
powershell -ExecutionPolicy Bypass -File modules/dynamic-lighting/notification-watcher.ps1 -Color "#00FF00" -Duration 2
```

> **Note:** Effects must include the pause-file coordination code to support alert flashes. Currently supported: `koi-fish.py`, `flower-garden.py`. Use the [template](modules/dynamic-lighting/effects/_template.py) as a starting point for new effects — copy the pause-file block from any supported effect.

## 🤝 Contributing

We'd love your contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- **Add a lighting effect** — copy the template and submit a PR
- **Propose a new module** — open an issue with the 💡 label
- **Report a bug** — use the bug report template

## 📄 License

[MIT](LICENSE) — Copyright 2026 Samantha Song
