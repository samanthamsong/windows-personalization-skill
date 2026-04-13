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

**Per-Lamp Scripting:**
For advanced pixel-level effects (animations, physics simulations, art), see `modules/dynamic-lighting/effects/`. Each script uses the `set_per_lamp_colors` tool to control individual LEDs at ~8fps.

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
- **Theme, accent color, dark mode, light mode, titlebar** → Themes module (planned)
- **Wallpaper, background, lock screen, desktop image** → Wallpaper module (planned)
- **Sounds, notification sound, system audio** → Sounds module (planned)
- **"Make everything [color]"** or **broad personalization** → Invoke all available modules for that color/theme
