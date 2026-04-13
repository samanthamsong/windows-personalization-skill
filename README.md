# 🎨 Windows Personalization Skill

Personalize your Windows PC with natural language. Tell an AI assistant *"make everything pink!"* and watch it transform your RGB lighting, themes, wallpaper, and more.

This is a [Copilot Skill](https://docs.github.com/en/copilot/building-copilot-skills) — a set of instructions and tools that AI agents can invoke automatically.

## ✨ What's Inside

| Module | Status | Description |
|--------|--------|-------------|
| [🔆 Dynamic Lighting](modules/dynamic-lighting/) | ✅ Available | Control RGB devices via MCP server + per-lamp Python effects |
| [🎨 Themes](modules/themes/) | 🔜 Planned | Accent colors, dark/light mode, titlebars |
| [🖼️ Wallpaper](modules/wallpaper/) | 🔜 Planned | Desktop wallpaper, lock screen, slideshows |
| [🔊 Sounds](modules/sounds/) | 🔜 Planned | System sound schemes |

## 🚀 Quick Start

### Prerequisites
- Windows 11 22H2+
- .NET 9 SDK
- Python 3.10+ (for per-lamp effects)
- A [Dynamic Lighting](https://support.microsoft.com/en-us/windows/control-your-dynamic-lighting-devices-in-windows-8e9f9b1f-6844-4c5e-9873-d836e87fcb7f) compatible device

### 1. Build the MCP server

```powershell
cd modules/dynamic-lighting
dotnet build DynamicLightingMCP.sln
```

### 2. Configure your MCP client

**VS Code** — add to your `mcp.json`:
```json
{
  "servers": {
    "dynamic-lighting": {
      "command": "dotnet",
      "args": ["run", "--project", "<path-to-repo>/modules/dynamic-lighting/src/DynamicLightingMcp/DynamicLightingMcp.csproj"]
    }
  }
}
```

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
| [Cherry Blossom](modules/dynamic-lighting/effects/cherry-blossom.py) | Falling cherry blossom petals |
| [Shooting Stars](modules/dynamic-lighting/effects/shooting-stars.py) | Streaking stars across a night sky |
| [Enchanted Forest](modules/dynamic-lighting/effects/enchanted-forest.py) | Layered forest with firefly sparkles |
| [Monet Waterlilies](modules/dynamic-lighting/effects/monet-waterlilies.py) | Impressionist water and lilies |
| [Paris Twinkle](modules/dynamic-lighting/effects/paris-twinkle.py) | Parisian city lights at night |
| [Rainbow](modules/dynamic-lighting/effects/rainbow.py) | Per-lamp rainbow gradient |
| [Star Wars Lightsaber](modules/dynamic-lighting/effects/star-wars-lightsaber.py) | Lightsaber ignition effect |
| [Hello Kitty](modules/dynamic-lighting/effects/hello-kitty.py) | Hello Kitty themed colors |
| [Gemini](modules/dynamic-lighting/effects/gemini.py) | Gemini-inspired dual-tone effect |
| [Astrology](modules/dynamic-lighting/effects/astrology.py) | Zodiac constellation lighting |
| [Hearts](modules/dynamic-lighting/effects/hearts.py) | Floating hearts animation |
| [TSITP](modules/dynamic-lighting/effects/tsitp.py) | Summer-inspired palette |

## 🛠️ Create Your Own Effect

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

## 🗺️ Roadmap

This skill is the first step toward full Windows personalization via natural language:

- ✅ **V1:** Dynamic Lighting (RGB devices via MCP)
- 🔜 **V2:** Themes (accent color, dark/light mode)
- 🔜 **V3:** Wallpaper + Sounds
- 🔮 **Future:** Multi-surface orchestration ("make my whole PC feel like the ocean")

## 🤝 Contributing

We'd love your contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- **Add a lighting effect** — copy the template and submit a PR
- **Propose a new module** — open an issue with the 💡 label
- **Report a bug** — use the bug report template

## 📄 License

[MIT](LICENSE) — Copyright 2026 Samantha Song
