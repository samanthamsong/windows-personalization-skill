# Dynamic Lighting Module

A stdin/stdout driver that lets scripts and AI assistants control Windows Dynamic Lighting compatible RGB devices.

## Prerequisites

- Windows 11 22H2 or newer
- .NET 9 SDK
- A Dynamic Lighting compatible device (keyboard, mouse, mousepad, light strip, etc.)
- Dynamic Lighting enabled: Settings > Personalization > Dynamic Lighting > "Use Dynamic Lighting on my devices"

## Build

```powershell
cd modules/dynamic-lighting
dotnet build DynamicLightingDriver.sln
```

## Registration

To enable background (ambient) lighting access, run the registration script once from an elevated prompt:

```powershell
cd modules/dynamic-lighting/src/DynamicLightingDriver/Package
.\Register-AmbientLighting.ps1
```

## Driver Protocol

The driver uses a line-based stdin/stdout protocol. Commands are sent as single lines; responses start with `OK ` or `ERROR `.

| Command | Description |
|---------|-------------|
| `SET_ALL <color>` | Set all lamps to one color |
| `SET_LAMPS <json>` | Control individual LEDs via `{index: "#rrggbb"}` JSON map |
| `GET_LAYOUT` | Get physical lamp positions and metadata |
| `LIST_DEVICES` | List connected DL devices |
| `CREATE_EFFECT <pattern> [key=value ...]` | Create effects with pattern, colors, speed, layers |
| `STOP_EFFECT` | Stop the current effect |
| `DIAGNOSE` | Run device diagnostics |

## Supported Patterns

`solid` · `wave` · `breathe` · `twinkle` · `gradient` · `rainbow`

Layered effects are supported — combine a breathing base with a twinkle overlay for complex scenes.

## Per-Lamp Effect Scripts

The `effects/` folder contains Python scripts that create pixel-level animations by controlling individual LEDs at ~8fps. These go beyond the built-in patterns to create art, physics simulations, and complex animations.

**To create your own:** Copy `effects/_template.py` and implement the `render_frame(t)` function.

See the [effect gallery](../../README.md#-effect-gallery) for previews.

## How It Works

The driver uses .NET with a simple line protocol over stdin/stdout. `LampArrayService` discovers devices via `DeviceWatcher` + `LampArray.GetDeviceSelector()`. `EffectEngine` converts parameters into `LampArrayCustomEffect` instances. `CommandHandler` parses line commands and dispatches to the service classes.
