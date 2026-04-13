# DynamicLightingMcp

DynamicLightingMcp is a Windows MCP (Model Context Protocol) server that lets AI assistants control Dynamic Lighting compatible RGB devices (keyboard, mouse, etc.) using natural-language requests. An MCP client like VS Code, Claude Desktop, or another MCP-capable tool can call this server over stdio, list connected LampArray devices, and apply single or layered effects such as wave, breathe, twinkle, gradient, and rainbow.

## Prerequisites

- Windows 11 22H2 or newer
- .NET 8 SDK
- A Dynamic Lighting compatible device (keyboard, mouse, mousepad, light strip, chassis, etc.)
- Dynamic Lighting enabled in Windows Settings:
  - Settings > Personalization > Dynamic Lighting
  - Turn on "Use Dynamic Lighting on my devices"

## Build And Run

From the workspace root:

```powershell
dotnet build
dotnet run --project .\DynamicLightingMcp\DynamicLightingMcp.csproj
```

## MCP Server Configuration (stdio)

### VS Code MCP configuration (example `mcp.json`)

Use your local path to this repository in the `args` value.

```json
{
  "servers": {
    "dynamic-lighting": {
      "command": "dotnet",
      "args": [
        "run",
        "--project",
        "C:/Users/samanthasong/DynamicLightingMCP/DynamicLightingMcp/DynamicLightingMcp.csproj"
      ]
    }
  }
}
```

### Claude Desktop style MCP config (example)

Some clients use a slightly different top-level key. The server command is the same.

```json
{
  "mcpServers": {
    "dynamic-lighting": {
      "command": "dotnet",
      "args": [
        "run",
        "--project",
        "C:/Users/samanthasong/DynamicLightingMCP/DynamicLightingMcp/DynamicLightingMcp.csproj"
      ]
    }
  }
}
```

## Example Prompts

- "Create a starry night effect with blue and yellow"
- "Make my keyboard breathe with a soft purple glow"
- "Set a rainbow wave across my keyboard"
- "Ocean waves with teal and white"
- "Stop the lighting effect"

## Supported Patterns

- solid
- wave
- breathe
- twinkle
- gradient
- rainbow

## How It Works

The server is built with .NET hosting and the ModelContextProtocol SDK over stdio transport. `LampArrayService` uses `DeviceWatcher` with `LampArray.GetDeviceSelector()` to discover and open compatible devices and expose capability metadata. `EffectEngine` turns parsed effect parameters into `LampArrayCustomEffect` instances managed by `LampArrayEffectPlaylist`, with per-lamp updates driven by physical lamp positions and elapsed time. `LightingTools` exposes MCP tools that parse natural language into colors/pattern/speed and execute those effects on a target device.
