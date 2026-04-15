# Contributing

Thanks for your interest in contributing to the Windows Personalization Skill! Here's how to get involved.

## Adding a New Lighting Effect

1. **Copy the template:**
   ```powershell
   cp modules/dynamic-lighting/effects/_template.py modules/dynamic-lighting/effects/my-effect.py
   ```

2. **Implement `render_frame(t)`** — return a dict of `{lamp_index: "#rrggbb"}` for each frame.

3. **Generate a visualization** — include a PNG preview showing 4 snapshots of your effect. Save it to `modules/dynamic-lighting/gallery/my-effect.png`. See existing effects for the visualization pattern.

4. **Test it** — run your script and confirm it looks good on a real device (or review the visualization).

5. **Submit a PR** with:
   - [ ] Your effect script in `modules/dynamic-lighting/effects/`
   - [ ] A gallery PNG in `modules/dynamic-lighting/gallery/`
   - [ ] No hardcoded local paths (use `os.path` relative to `__file__`)
   - [ ] A description of the effect in your PR body

## Proposing a New Personalization Module

Want to add support for themes, wallpaper, sounds, or something else?

1. Open an issue using the "💡 New Personalization Module" template
2. Describe the Windows APIs or settings it would control
3. Sketch out what tools/scripts it would expose

If approved, create a folder under `modules/<name>/` with:
- `README.md` describing the module
- Scripts or source code
- Update the SKILL.md routing section

## Development Setup

### Dynamic Lighting Driver
```powershell
cd modules/dynamic-lighting
dotnet build DynamicLightingDriver.sln
```

### Running Effects
```powershell
python modules/dynamic-lighting/effects/koi-fish.py
```

Requires: Windows 11 22H2+, .NET 9 SDK, Python 3.10+, WinAppCLI (`winget install Microsoft.WinAppCli`), Dynamic Lighting device.

## Code of Conduct

This project follows the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
