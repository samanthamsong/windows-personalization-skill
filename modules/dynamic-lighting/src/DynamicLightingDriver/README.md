# DynamicLightingDriver

DynamicLightingDriver is a Windows stdin/stdout driver that lets scripts and AI assistants control Dynamic Lighting compatible RGB devices (keyboard, mouse, etc.). It uses a simple line-based protocol over stdio — send a command, receive a response.

## Prerequisites

- Windows 11 22H2 or newer
- .NET 9 SDK
- A Dynamic Lighting compatible device (keyboard, mouse, mousepad, light strip, chassis, etc.)
- Dynamic Lighting enabled in Windows Settings:
  - Settings > Personalization > Dynamic Lighting
  - Turn on "Use Dynamic Lighting on my devices"

## Build And Run

From the workspace root:

```powershell
dotnet build DynamicLightingDriver.sln
```

## Protocol

The driver uses a line-based stdin/stdout protocol. Each command is one line in, one line out.

### Commands

```
SET_ALL <color>              — Set all lamps to a single color
SET_LAMPS <json>             — Set individual lamp colors via JSON map
LIST_DEVICES                 — List connected devices
GET_LAYOUT                   — Get lamp positions and metadata
CREATE_EFFECT <pattern> ...  — Create a lighting effect
STOP_EFFECT                  — Stop the current effect
DIAGNOSE                     — Run device diagnostics
QUIT                         — Exit the driver
```

Responses start with `OK ` or `ERROR `.

## Supported Patterns

- solid
- wave
- breathe
- twinkle
- gradient
- rainbow

## How It Works

The driver is built with .NET and a simple line protocol. `LampArrayService` uses `DeviceWatcher` with `LampArray.GetDeviceSelector()` to discover and open compatible devices. `EffectEngine` turns parsed effect parameters into `LampArrayCustomEffect` instances managed by `LampArrayEffectPlaylist`. `CommandHandler` parses line commands and dispatches to the service classes.
