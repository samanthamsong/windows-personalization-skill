# Dynamic Lighting Module

An MCP server that lets AI assistants control Windows Dynamic Lighting compatible RGB devices using natural language.

## Prerequisites

- Windows 11 22H2 or newer
- .NET 9 SDK
- A Dynamic Lighting compatible device (keyboard, mouse, mousepad, light strip, etc.)
- Dynamic Lighting enabled: Settings > Personalization > Dynamic Lighting > "Use Dynamic Lighting on my devices"

## Build

```powershell
cd modules/dynamic-lighting
dotnet build DynamicLightingMCP.sln
```

## MCP Server Configuration

### VS Code (`mcp.json`)

```json
{
  "servers": {
    "dynamic-lighting": {
      "command": "dotnet",
      "args": [
        "run", "--project",
        "modules/dynamic-lighting/src/DynamicLightingMcp/DynamicLightingMcp.csproj"
      ]
    }
  }
}
```

### Claude Desktop

```json
{
  "mcpServers": {
    "dynamic-lighting": {
      "command": "dotnet",
      "args": [
        "run", "--project",
        "modules/dynamic-lighting/src/DynamicLightingMcp/DynamicLightingMcp.csproj"
      ]
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `create_lighting_effect` | Create effects from natural language or structured params (pattern, colors, speed, layers) |
| `set_solid_color` | Set all lamps to one color |
| `set_per_lamp_colors` | Control individual LEDs via `{index: "#rrggbb"}` JSON map |
| `get_lamp_layout` | Get physical lamp positions and metadata |
| `list_lighting_devices` | List connected DL devices |
| `stop_lighting_effect` | Stop the current effect |
| `diagnose_lighting` | Run device diagnostics |

## Supported Patterns

`solid` · `wave` · `breathe` · `twinkle` · `gradient` · `rainbow`

Layered effects are supported — combine a breathing base with a twinkle overlay for complex scenes.

## Per-Lamp Effect Scripts

The `effects/` folder contains Python scripts that create pixel-level animations by controlling individual LEDs at ~8fps. These go beyond the built-in patterns to create art, physics simulations, and complex animations.

**To create your own:** Copy `effects/_template.py` and implement the `render_frame(t)` function.

See the [effect gallery](../../README.md#-effect-gallery) for previews.

## How It Works

The server uses .NET with the ModelContextProtocol SDK over stdio transport. `LampArrayService` discovers devices via `DeviceWatcher` + `LampArray.GetDeviceSelector()`. `EffectEngine` converts parameters into `LampArrayCustomEffect` instances. `LightingTools` exposes MCP tools that translate natural language into effect parameters.
