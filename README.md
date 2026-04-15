# 🎨 Windows Personalization Skill

Personalize your Windows PC with natural language. Tell an AI assistant *"make everything pink!"* and watch it transform your RGB lighting, themes, wallpaper, and more.

This is a [Copilot Skill](https://docs.github.com/en/copilot/building-copilot-skills) — a set of instructions and tools that AI agents can invoke automatically.

## ✨ What's Inside

| Module | Status | Description |
|--------|--------|-------------|
| [🔆 Dynamic Lighting](modules/dynamic-lighting/) | ✅ Available | Control RGB devices via CLI + per-lamp Python effects |
| [🎵 Spotify](modules/spotify/) | ✅ Available | Sync keyboard lighting to Spotify — album colors + mood |
| [🎨 Themes](modules/themes/) | 🔜 Planned | Accent colors, dark/light mode, titlebars |
| [🖼️ Wallpaper](modules/wallpaper/) | 🔜 Planned | Desktop wallpaper, lock screen, slideshows |
| [🔊 Sounds](modules/sounds/) | 🔜 Planned | System sound schemes |

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Install |
|-------------|---------|---------|
| Windows 11 | 22H2+ | — |
| .NET SDK | 9.0+ | [dotnet.microsoft.com](https://dotnet.microsoft.com/download/dotnet/9.0) |
| Python | 3.10+ | [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12` |
| WinAppCLI | 0.2+ | `winget install Microsoft.WinAppCli` |
| Dynamic Lighting device | — | Any [compatible](https://support.microsoft.com/en-us/windows/control-your-dynamic-lighting-devices-in-windows-8e9f9b1f-6844-4c5e-9873-d836e87fcb7f) RGB keyboard, mouse, light strip, etc. |

> **Windows Settings:** Go to **Settings → Personalization → Dynamic Lighting** and ensure **"Use Dynamic Lighting on my devices"** is turned on.

### 1. Clone the repo

```powershell
git clone https://github.com/samanthamsong/windows-personalization-skill.git
cd windows-personalization-skill
```

### 2. Build the driver

```powershell
cd modules/dynamic-lighting
dotnet build DynamicLightingDriver.sln
```

### 3. Register for package identity

The driver needs package identity to access the LampArray API. The registration script uses WinAppCLI to create a signed MSIX package and install it.

```powershell
cd src/DynamicLightingDriver/Package
.\Register-AmbientLighting.ps1
```

This script will:
1. Build the .NET project
2. Auto-detect your CPU architecture (x64/arm64) and patch the manifest
3. Generate a dev certificate with `winapp cert generate` (first run only)
4. Create and sign the MSIX with `winapp package`
5. Install the package with `Add-AppxPackage`

> ⚠️ **First run:** You may need to run as admin once so the dev certificate can be added to the machine trust store. Subsequent runs work without admin.

> ⚠️ **Important:** After registration, go to **Settings → Personalization → Dynamic Lighting → Background light control** and move **Dynamic Lighting Driver** to the **top of the priority list**. This ensures the driver takes precedence over other lighting apps.

### 4. Try it!

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

Or tell your AI agent (Copilot, etc.) what you want in natural language:

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
| [Ocean Sunset](modules/dynamic-lighting/effects/ocean-sunset.py) | Warm sunset gradient with rolling ocean waves |
| [Sunset](modules/dynamic-lighting/effects/sunset.py) | Golden hour sky with shifting warm tones |
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

1. Copy the template:
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

## 🔔 Notification Alerts

Flash your keyboard whenever you get a Windows notification — Teams messages, Outlook emails, any app.

### How it works

1. `notification-watcher.ps1` monitors the Windows Event Log for toast notifications
2. When a toast arrives, it writes a color + duration to `rules/.pause`
3. The running effect reads the pause file, flashes the color, then resumes the animation

All effects support notification flash alerts — both per-frame effects (koi-fish, flower-garden, etc.) and CREATE_EFFECT effects (cherry-blossom, rainbow, etc.) will flash and automatically resume.

### Quick start

```powershell
# Terminal 1: Run any effect
python modules/dynamic-lighting/effects/flower-garden.py

# Terminal 2: Start the notification watcher (hot pink flash for 3s)
powershell -ExecutionPolicy Bypass -File modules/dynamic-lighting/notification-watcher.ps1

# Custom color/duration
powershell -ExecutionPolicy Bypass -File modules/dynamic-lighting/notification-watcher.ps1 -Color "#00FF00" -Duration 2
```

## 🖥️ Driver Window

The driver runs a companion window that provides foreground status for the LampArray API. It includes several features:

| Feature | Description |
|---------|-------------|
| **Effect name display** | Shows the currently running effect name |
| **☀️/🌙 Theme toggle** | Switch between light and dark mode |
| **👁 Hide button** | Make the window invisible (stays running); restore from system tray |
| **System tray icon** | Always visible — right-click to restore or exit |

The window stays in the foreground to maintain LampArray access. When hidden, it becomes fully transparent but retains foreground status.

## 🗺️ Roadmap

This skill is the first step toward full Windows personalization via natural language:

- ✅ **V1:** Dynamic Lighting (RGB devices via CLI)
- ✅ **V2:** Alert-based lighting (flash keyboard on Windows notifications)
- ✅ **V2.1:** Driver UI (theme toggle, hide button, system tray, effect display)
- 🔜 **V3:** Themes (accent color, dark/light mode)
- 🔜 **V4:** Wallpaper + Sounds
- 🔮 **Future:** Multi-surface orchestration ("make my whole PC feel like the ocean")

## 🤝 Contributing

Want to run this on your own machine from scratch? Here's the full setup:

### System requirements

- **OS:** Windows 11 22H2 or newer (Build 22621+)
- **Hardware:** Any Dynamic Lighting compatible RGB device
- **Developer mode:** Enable in **Settings → System → For developers → Developer Mode**

### Install dependencies

```powershell
# .NET 9 SDK
winget install Microsoft.DotNet.SDK.9

# Python 3.12
winget install Python.Python.3.12

# WinAppCLI (for MSIX packaging and signing)
winget install Microsoft.WinAppCli

# Windows SDK (optional — WinAppCLI replaces MakeAppx/SignTool for packaging)
# Only needed if you want to use the Windows SDK tools directly
# winget install Microsoft.WindowsSDK
```

### Clone and build

```powershell
git clone https://github.com/samanthamsong/windows-personalization-skill.git
cd windows-personalization-skill
dotnet build modules/dynamic-lighting/DynamicLightingDriver.sln
```

### Register for package identity

```powershell
cd modules/dynamic-lighting/src/DynamicLightingDriver/Package
.\Register-AmbientLighting.ps1
```

On the **first run**, run from an elevated (admin) PowerShell so the dev certificate can be trusted system-wide. Subsequent runs don't need admin — the certificate is cached as `devcert.pfx`.

### Verify setup

```powershell
# Check your device is detected
python modules/dynamic-lighting/lighting.py diagnose

# Quick test — set all LEDs to green
python modules/dynamic-lighting/lighting.py set-color "#00FF00"
```

### Troubleshooting

| Issue | Fix |
|-------|-----|
| "No devices found" | Ensure Dynamic Lighting is on in Settings → Personalization → Dynamic Lighting |
| "Access denied" during registration | Run PowerShell as admin for the first registration |
| Driver not taking effect | Move "Dynamic Lighting Driver" to top of priority list in Dynamic Lighting settings |
| Certificate trust error on `Add-AppxPackage` | Run `Register-AmbientLighting.ps1` once from an admin prompt |
| Effects not showing on keyboard | Check that no other lighting app (iCUE, SignalRGB, etc.) is overriding |

### Uninstall

```powershell
# Remove the registered package
Get-AppxPackage *DynamicLightingDriver* | Remove-AppxPackage

# Remove trusted certificate (optional)
Get-ChildItem "Cert:\CurrentUser\TrustedPeople" | Where-Object { $_.Subject -eq "CN=DynamicLightingDriver" } | Remove-Item
```

## 🤝 Contributing

We'd love your contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- **Add a lighting effect** — copy the template and submit a PR
- **Propose a new module** — open an issue with the 💡 label
- **Report a bug** — use the bug report template

## 📄 License

[MIT](LICENSE) — Copyright 2026 Samantha Song
