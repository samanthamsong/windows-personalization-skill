# Themes Module

Apply full desktop + RGB themes from a single JSON spec.

## Files

| File | Description |
|------|-------------|
| `apply-theme.py` | Orchestrator CLI — parses spec, calls all handlers |
| `desktop_handler.py` | Sets accent color, taskbar, dark/light mode, transparency via registry |
| `wallpaper_handler.py` | Downloads themed image and sets as wallpaper (Fill mode) |
| `lighting_handler.py` | Palette-driven DL effect on all peripherals via DeviceManager |

## Usage

```powershell
python apply-theme.py --spec '{"name":"ocean","accent_color":"#0077B6","mode":"dark","dl_palette":["#0077B6","#00B4D8"],"dl_style":"wave"}'
python apply-theme.py --check
python apply-theme.py --stop-lighting
```

See the [main README](../../README.md#-themes) for full documentation.
