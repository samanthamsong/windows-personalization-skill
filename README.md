# 🎨 Windows Personalization Skill

Personalize your Windows PC with natural language. Tell an AI assistant *"make everything pink!"* and watch it transform your RGB lighting, window layouts, desktop vibes, and more.

This is a [Copilot Skill](https://docs.github.com/en/copilot/building-copilot-skills) — a set of instructions and tools that AI agents can invoke automatically.

## ✨ What's Inside

| Module | Status | Description |
|--------|--------|-------------|
| [🔆 Dynamic Lighting](modules/dynamic-lighting/) | ✅ Available | Control RGB devices via CLI + per-lamp Python effects |
| [🎵 Spotify](modules/spotify/) | ✅ Available | Sync keyboard lighting to Spotify — album colors + mood |
| [🎨 Themes](modules/themes/) | ✅ Available | Full desktop + RGB theming from a single prompt |
| [🪟 Windowing](modules/windowing/) | 🔜 Planned | Save, restore, and create aesthetic window layouts |

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Install |
|-------------|---------|---------|
| Windows 11 | 22H2+ | — |
| .NET SDK | 9.0+ | [dotnet.microsoft.com](https://dotnet.microsoft.com/download/dotnet/9.0) |
| Python | 3.10+ | [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12` |
| WinAppCLI | 0.2+ | `winget install Microsoft.WinAppCli` |
| Dynamic Lighting device | — | Any [compatible](https://support.microsoft.com/en-us/windows/control-your-dynamic-lighting-devices-in-windows-8e9f9b1f-6844-4c5e-9873-d836e87fcb7f) RGB keyboard, mouse, light strip, etc. |
| Spotify account | — | Free or Premium (for Spotify integration) |

> **Windows Settings:** Go to **Settings → Personalization → Dynamic Lighting** and ensure **"Use Dynamic Lighting on my devices"** is turned on.

### 1. Clone the repo

Clone directly into the Copilot skills directory so it's automatically discovered:

```powershell
git clone https://github.com/samanthamsong/windows-personalization-skill.git "$HOME\.copilot\skills\windows-personalization"
cd "$HOME\.copilot\skills\windows-personalization"
```

> **Already cloned somewhere else?** Run `.\setup.ps1` — it creates a junction from `~/.copilot/skills/windows-personalization/` to the repo automatically.

### 2. Run setup

```powershell
.\setup.ps1
```

This will:
1. Check prerequisites (.NET 9, Python 3, WinAppCLI)
2. Install Python dependencies
3. Build the .NET driver
4. Install the driver to `%LocalAppData%\DynamicLightingDriver\`
5. Register for AppX package identity (needed for LampArray API access)
6. Verify everything works

> ⚠️ **First run:** You may need to run as admin once so the dev certificate can be added to the machine trust store:
> ```powershell
> Start-Process powershell -Verb RunAs -ArgumentList "-File $PWD\setup.ps1"
> ```

> ⚠️ **Important:** After setup, go to **Settings → Personalization → Dynamic Lighting → Background light control** and move **Dynamic Lighting Driver** so it is **below** "Dynamic Lighting Background Controller" in the priority list.

### 3. Try it!

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
| [Cinematic](modules/dynamic-lighting/effects/cinematic.py) | Screen-reactive ambient lighting — keyboard mirrors your display |

## 🤖 Installing as a Copilot Skill

This repo is structured as a [Copilot personal skill](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills). The `SKILL.md` at the repo root tells AI agents how to use the lighting, themes, and Spotify modules.

### Automatic (recommended)

Running `.\setup.ps1` installs everything — including registering the skill with Copilot:

```powershell
git clone https://github.com/samanthamsong/windows-personalization-skill.git "$HOME\.copilot\skills\windows-personalization"
cd "$HOME\.copilot\skills\windows-personalization"
.\setup.ps1
```

### Manual

If you've already cloned the repo elsewhere:

```powershell
# Create a junction so Copilot can find the skill
cmd /c mklink /J "%USERPROFILE%\.copilot\skills\windows-personalization" "C:\path\to\windows-personalization-skill"
```

### Verify

In the Copilot CLI, run:

```
/skills info windows-personalization
```

> **Note:** If you move or rename the repo directory, re-run `.\setup.ps1` to update the link.

## 📁 Repo Structure

```
windows-personalization-skill/
├── SKILL.md                    # Copilot skill definition (agent instructions)
├── README.md                   # This file
├── setup.ps1                   # One-command setup (build + install + register skill)
├── modules/
│   ├── dynamic-lighting/       # RGB device control + per-lamp effects
│   │   ├── lighting.py         # CLI entry point
│   │   ├── effects/            # Per-lamp animation scripts
│   │   └── src/                # .NET driver source
│   ├── spotify/                # Spotify album color sync
│   ├── themes/                 # Full desktop theming
│   ├── sounds/                 # (planned) Sound customization
│   └── wallpaper/              # (planned) Wallpaper management
├── .github/
│   ├── workflows/              # CI/CD
│   └── ISSUE_TEMPLATE/         # Bug reports & feature requests
└── .gitignore
```

> **Important:** `SKILL.md` must stay at the repo root alongside `modules/`. This is what makes the repo a valid Copilot skill directory — the skill system looks for `SKILL.md` and makes sibling files available to the agent.

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

All effects support notification flash alerts. Every per-lamp effect (koi-fish, flower-garden, shooting-stars, etc.) will flash and automatically resume.

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
| **🎵 Spotify panel** | Now-playing info: track, artist, mood, album color swatches (auto-shows when Spotify sync is running) |
| **☀️/🌙 Theme toggle** | Switch between light and dark mode |
| **👁 Hide button** | Make the window invisible (stays running); restore from system tray |
| **System tray icon** | Always visible — right-click to restore or exit |

The window stays in the foreground to maintain LampArray access. When hidden, it becomes fully transparent but retains foreground status.

## 🎵 Spotify Integration

Sync your keyboard lighting to the currently playing Spotify track. Album art colors drive the palette, and audio features shape the animation.

### Setup (one-time)

```powershell
# Install Python dependencies
pip install spotipy Pillow requests pycaw comtypes numpy

# Authenticate with your Spotify account (opens browser)
python modules/spotify/auth.py
```

That's it — the Client ID is built in. Each developer logs in with their own Spotify account.

### Usage

```powershell
# Color wave synced to album art
python modules/spotify/spotify-sync.py start

# Beat-reactive mode — keyboard pulses on every beat
python modules/spotify/spotify-sync.py start --beat-sync

# Overlay mode — tints the current running effect with album colors
python modules/spotify/spotify-sync.py start --overlay

# Check what's playing
python modules/spotify/spotify-sync.py status

# Stop sync
python modules/spotify/spotify-sync.py stop
```

Or tell your AI agent:

> "Sync my keyboard to Spotify"
>
> "Pulse my keyboard to the beat"
>
> "Stop the music sync"

### How it works

1. **Album art → colors**: Downloads the album cover and extracts dominant colors via k-means quantization
2. **Audio features → mood**: Maps Spotify's energy, valence, and tempo to a mood (energetic, peaceful, melancholy, etc.)
3. **Mood → effect**: Each mood drives a different animation pattern and speed
4. **Beat sync** (optional): Reads the Windows audio meter in real-time to detect beats and trigger radial burst pulses

The driver window shows a Spotify "now playing" panel (🎵 toggle) with track name, artist, mood, and album color swatches.

## 🎨 Themes

Transform your entire desktop with a single prompt — wallpaper, accent color, taskbar, dark/light mode, and RGB lighting all change together.

### Usage

```powershell
# Apply a theme from a JSON spec
python modules/themes/apply-theme.py --spec '{"name":"ocean","accent_color":"#0077B6","mode":"dark",...}'

# Check what theming capabilities are available on your machine
python modules/themes/apply-theme.py --check

# Stop the theme RGB lighting effect
python modules/themes/apply-theme.py --stop-lighting
```

Or tell your AI agent in natural language:

> "Make everything shrek themed"
>
> "Give me a cozy autumn aesthetic"
>
> "Ocean theme — dark mode, blue everything"

### How it works

1. The AI agent interprets your prompt and generates a **theme spec** — picking colors, wallpaper, dark/light mode, and an RGB lighting style
2. `apply-theme.py` orchestrates three handlers:
   - **Wallpaper** — downloads a themed image and sets it (Full screen / Fill mode)
   - **Desktop styling** — sets accent color, taskbar, dark/light mode, transparency via registry
   - **RGB lighting** — starts a palette-driven effect on all Dynamic Lighting devices
3. Each handler is **capability-aware** — if registry writes or DL devices aren't available, that component is gracefully skipped

### Theme spec

```json
{
    "name": "ocean",
    "wallpaper_url": "https://example.com/ocean.jpg",
    "wallpaper_search": "deep ocean underwater",
    "accent_color": "#0077B6",
    "mode": "dark",
    "taskbar_accent": true,
    "transparency": true,
    "dl_palette": ["#0077B6", "#00B4D8", "#90E0EF", "#CAF0F8"],
    "dl_style": "wave"
}
```

All fields are optional. Available DL styles: `wave`, `breathe`, `shimmer`, `static`, `pulse`.

## 🗺️ Roadmap

This skill is the first step toward full Windows personalization via natural language:

- ✅ **V1:** Dynamic Lighting (RGB devices via CLI)
- ✅ **V2:** Alert-based lighting (flash keyboard on Windows notifications)
- ✅ **V2.1:** Driver UI (theme toggle, hide button, system tray, effect display)
- ✅ **V2.2:** Spotify integration (album colors, mood mapping, beat-sync)
- ✅ **V3:** Themes (wallpaper + accent + taskbar + dark/light mode + RGB lighting from one prompt)
- 🔜 **V3.1:** Multi-peripheral sync (mouse, headset, mousepad match keyboard effects)
- 🔜 **V4:** Windowing (save/restore/create aesthetic window layouts)

### 🔆 Multi-Peripheral Sync (planned)

The Dynamic Lighting driver already discovers all DL-compatible devices (keyboards, mice, headsets, mousepads). Planned enhancements:

- **Device-aware rendering** — adapt effects to each device's geometry (a mouse has ~2-5 zones vs. 87 keys)
- **Sync all mode** — push matching frames to every connected device simultaneously
- **Unified vibe** — koi fish swim across your keyboard while your mouse glows the pond color and your headset pulses with the ripples

### 🪟 Windowing (planned)

A layout library + context layer for managing window arrangements:

- **Pre-baked layouts** — "Dev Setup" (editor + terminal + browser), "Meeting Mode" (Teams + notes), "Content Creation" (timeline + preview + assets)
- **Aesthetic arrangements** — "cascade my windows like cards," "golden ratio tiling," "messy desk" (slightly rotated, overlapping)
- **Save custom layouts** — "save this as my coding layout" with friendly names
- **Context-aware restore** — adapts to monitor count and resolution automatically

## 🛠️ Developer Setup

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

# Python dependencies (for effects and Spotify integration)
pip install spotipy Pillow requests pycaw comtypes numpy
```

### Clone and build

```powershell
# Clone directly into the skills directory (recommended)
git clone https://github.com/samanthamsong/windows-personalization-skill.git "$HOME\.copilot\skills\windows-personalization"
cd "$HOME\.copilot\skills\windows-personalization"

# One-command setup (builds, installs, registers skill)
.\setup.ps1
```

If you clone elsewhere, `setup.ps1` will create a junction to `~/.copilot/skills/windows-personalization/` automatically.

Or manually:

```powershell
# Build the driver
dotnet build modules/dynamic-lighting/DynamicLightingDriver.sln

# Install to canonical path and register
cd modules/dynamic-lighting/src/DynamicLightingDriver/Package
.\Register-AmbientLighting.ps1
```

The driver is installed to `%LocalAppData%\DynamicLightingDriver\`. All effect scripts and CLI tools reference this path.

### Verify setup

```powershell
# Check your device is detected
python modules/dynamic-lighting/lighting.py diagnose

# Quick test — set all LEDs to green
python modules/dynamic-lighting/lighting.py set-color "#00FF00"
```

### Set up Spotify integration (optional)

```powershell
# Authenticate with your Spotify account (opens browser — log in and click Agree)
python modules/spotify/auth.py

# Test it — play a song on Spotify, then:
python modules/spotify/spotify-sync.py start --beat-sync
```

### Troubleshooting

| Issue | Fix |
|-------|-----|
| "No devices found" | Ensure Dynamic Lighting is on in Settings → Personalization → Dynamic Lighting |
| "Access denied" during registration | Run PowerShell as admin for the first registration |
| Driver not taking effect | Move "Dynamic Lighting Driver" to top of priority list in Dynamic Lighting settings |
| Certificate trust error on `Add-AppxPackage` | Run `Register-AmbientLighting.ps1` once from an admin prompt |
| Effects not showing on keyboard | Check that no other lighting app (iCUE, SignalRGB, etc.) is overriding |
| Spotify auth fails | Ensure you clicked "Agree" in the browser; check that `http://127.0.0.1:8888/callback` is in your app's redirect URIs |
| Spotify "403 Forbidden" on audio features | Spotify recently restricted this API for new apps — mood defaults to "neutral" but album colors still work |

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
