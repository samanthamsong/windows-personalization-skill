---
name: windows-personalization
description: Personalize your Windows PC using natural language — RGB lighting, themes, wallpapers, sounds, and more.
---

# Windows Personalization Skill

Use this skill when a user wants to personalize or customize their Windows PC. This includes changing RGB lighting, themes, accent colors, wallpapers, sounds, or any visual/audio aspect of their desktop.

## Capabilities

### 🔆 Dynamic Lighting (Available)
Control Dynamic Lighting compatible RGB devices (keyboards, mice, light strips, etc.).

**Prerequisites:**
- Windows 11 22H2+ with a Dynamic Lighting compatible device
- .NET 8+ SDK, Python 3.10+, WinAppCLI
- Driver must be installed to `%LocalAppData%\DynamicLightingDriver\`

**First-time setup:** If the driver is not installed, run setup from the skill directory:
```
.\setup.ps1
```
If the skill is not yet installed, clone the repo and run setup:
```
git clone https://github.com/samanthamsong/windows-personalization-skill.git ~/.copilot/skills/windows-personalization
cd ~/.copilot/skills/windows-personalization
.\setup.ps1
```
This builds the driver, installs it, and registers for package identity. Only needed once.

**CLI Commands:**

| Command | Description |
|---------|-------------|
| `python modules/dynamic-lighting/lighting.py set-color <color>` | Set all lamps to a single color (hex or name) |
| `python modules/dynamic-lighting/lighting.py set-per-lamp '<json>'` | Set individual lamp colors |
| `python modules/dynamic-lighting/lighting.py list-devices` | List connected Dynamic Lighting devices |
| `python modules/dynamic-lighting/lighting.py list-effects` | List available effect scripts |
| `python modules/dynamic-lighting/lighting.py run-effect <name>` | Run a named effect (e.g. koi-fish) |
| `python modules/dynamic-lighting/lighting.py stop` | Stop running effects |
| `python modules/dynamic-lighting/lighting.py set-theme <light\|dark>` | Switch the driver window between light and dark mode |
| `python modules/dynamic-lighting/lighting.py diagnose` | Run device diagnostics |

**Example Prompt Mappings:**

| User Says | Action |
|-----------|--------|
| "Set my keyboard to red" | `python modules/dynamic-lighting/lighting.py set-color red` |
| "Make my keyboard breathe with purple" | Generate a breathe effect script and run it |
| "Koi fish swimming" | `python modules/dynamic-lighting/lighting.py run-effect koi-fish` OR generate a new script |
| "Ocean waves on my keyboard" | Generate an ocean wave effect script |
| "Rainbow wave" | `python modules/dynamic-lighting/lighting.py run-effect rainbow` |
| "Stop the lights" | `python modules/dynamic-lighting/lighting.py stop` |
| "Cinematic mode" | `python modules/dynamic-lighting/lighting.py run-effect cinematic` |
| "Match my lights to what's on screen" | `python modules/dynamic-lighting/lighting.py run-effect cinematic` |
| "Ambilight mode" | `python modules/dynamic-lighting/lighting.py run-effect cinematic` |
| "Switch to light mode" | `python modules/dynamic-lighting/lighting.py set-theme light` |
| "Use dark mode" | `python modules/dynamic-lighting/lighting.py set-theme dark` |
| "What devices do I have?" | `python modules/dynamic-lighting/lighting.py list-devices` |
| "What effects are available?" | `python modules/dynamic-lighting/lighting.py list-effects` |

**When to use CLI vs generate a script:**
- Simple solid color → `lighting.py set-color`
- Run existing effect → `lighting.py run-effect <name>`
- Creative/artistic/physics-based effects → Generate a Python script

**Creating Custom Effects via Natural Language:**

When a user requests a complex or creative lighting effect (e.g. "koi fish swimming", "the matrix", "fireworks", "rainstorm"), the agent should **generate a per-lamp Python effect script** and run it.

**How to generate an effect script:**

1. Create a Python file in `modules/dynamic-lighting/effects/` based on the template below
2. Implement the `render_frame(device, t)` function that returns a color for each lamp based on time
3. Run the script with `python <script_path>`

Effects automatically render to **all connected devices** (keyboards, lamps, mice, mousepads, light strips) via the shared `_runner.py` module. Alert flash coordination is handled automatically.

**Script structure (follow this exactly):**

```python
import math
from _runner import EffectRunner, lerp, hex_color

runner = EffectRunner("My Effect Name")

def render_frame(device, t):
    """Return {lamp_index_str: '#rrggbb'} for each lamp at time t seconds.

    Called once per device per frame. Works on keyboards, lamps, mice, etc.
    Each device has device.lamps with 'idx', 'x' (0-1), 'y' (0-1).
    """
    colors = {}
    for lamp in device.lamps:
        # YOUR EFFECT LOGIC HERE using lamp['x'], lamp['y'], and t
        color = (0, 0, 0)
        colors[str(lamp['idx'])] = hex_color(*color)
    return colors

runner.run(render_frame, fps=8)
```

**Key design principles for render_frame(device, t):**
- Each lamp has `x` (0–1, left to right) and `y` (0–1, top to bottom) — use these for spatial effects
- `t` is elapsed seconds — use for animation (sin waves, movement, physics)
- `device.kind` tells you the device type (Keyboard, Mouse, LampStrip, etc.)
- Return hex color strings like `'#ff6600'` — use `hex_color(r, g, b)` helper
- Use `lerp()` to blend between colors
- Use `math.sin()`, `math.cos()` for waves and oscillation
- For moving objects: compute distance from each lamp to the object's position
- For layered effects: compute a base layer, then overlay elements on top
- Keep FPS at ~8 for smooth performance

**Example reference effects in `modules/dynamic-lighting/effects/`:**
- `koi-fish.py` — animated fish with body segments, water ripples, lily pads, caustic shimmer
- `cherry-blossom.py` — falling petals with wind physics
- `shooting-stars.py` — streaking particles across a night sky
- `enchanted-forest.py` — layered forest floor with firefly overlay
- `water-droplets.py` — raindrops on a pond with expanding ripple rings and lily pads

### 🔔 Alert-Based Lighting Rules (Available)
Set up rules that trigger lighting effects when Windows notifications arrive.

**CLI Commands:**

| Command | Description |
|---------|-------------|
| `python modules/dynamic-lighting/alert-watcher.py add --name <name> --app <app> --color <hex> --duration <sec>` | Add a notification rule |
| `python modules/dynamic-lighting/alert-watcher.py list` | List all rules |
| `python modules/dynamic-lighting/alert-watcher.py remove <rule_id>` | Remove a rule |
| `python modules/dynamic-lighting/alert-watcher.py enable <rule_id>` | Enable a rule |
| `python modules/dynamic-lighting/alert-watcher.py disable <rule_id>` | Disable a rule |
| `python modules/dynamic-lighting/alert-watcher.py test <rule_id>` | Test a rule |
| `powershell -ExecutionPolicy Bypass -File modules/dynamic-lighting/notification-watcher.ps1` | Start watching for notifications |

**Example Prompt Mappings:**

| User Says | Action |
|-----------|--------|
| "Flash red when I get a Teams message" | `python modules/dynamic-lighting/alert-watcher.py add --name "Teams flash" --app "Microsoft Teams" --color "#FF0000" --duration 3` |
| "What alert rules do I have?" | `python modules/dynamic-lighting/alert-watcher.py list` |
| "Remove the Teams rule" | `python modules/dynamic-lighting/alert-watcher.py remove <id>` |
| "Start watching for notifications" | `powershell -ExecutionPolicy Bypass -File modules/dynamic-lighting/notification-watcher.ps1` |

### 🎵 Spotify Integration (Available)
Sync keyboard lighting to currently playing Spotify track — album art colors, mood-reactive effects.

**Prerequisites:**
- Spotify Premium account
- Python packages: `pip install spotipy Pillow requests pycaw comtypes numpy`
- Spotify Developer App with Client ID (https://developer.spotify.com/dashboard)
- Run `python modules/spotify/auth.py` once to authenticate

**CLI Commands:**

| Command | Description |
|---------|-------------|
| `python modules/spotify/spotify-sync.py start` | Start music-reactive lighting (full takeover) |
| `python modules/spotify/spotify-sync.py start --beat-sync` | Beat-reactive mode — keyboard pulses on every beat |
| `python modules/spotify/spotify-sync.py start --overlay` | Tint current effect with album colors |
| `python modules/spotify/spotify-sync.py stop` | Stop Spotify sync |
| `python modules/spotify/spotify-sync.py status` | Show current track, mood, and album colors |
| `python modules/spotify/auth.py` | Authenticate with Spotify |
| `python modules/spotify/auth.py status` | Check authentication status |

**Example Prompt Mappings:**

| User Says | Action |
|-----------|--------|
| "Sync my lights to Spotify" | `python modules/spotify/spotify-sync.py start` |
| "Match my keyboard to my music" | `python modules/spotify/spotify-sync.py start` |
| "Tint my effect with what I'm listening to" | `python modules/spotify/spotify-sync.py start --overlay` |
| "What song is playing?" | `python modules/spotify/spotify-sync.py status` |
| "Stop the music sync" | `python modules/spotify/spotify-sync.py stop` |

### 🎨 Themes (Available)
Apply full desktop + RGB themes from a single prompt. Changes wallpaper, accent color, taskbar, dark/light mode, transparency, and Dynamic Lighting simultaneously.

**📦 MSIX Theme Library:** The skill includes a library of packaged Windows themes (MSIX) with professional wallpapers, accent colors, sounds, and cursors. When applying a theme, the tool automatically checks the library first. If a packaged theme closely matches the request, it is applied instead of generating a custom theme — giving richer results. The agent does NOT need to change behavior; just generate a spec as usual.

When a packaged theme is applied, the agent should still **generate a matching per-lamp keyboard animation** based on the theme's vibe (the packaged theme doesn't include RGB data).

If no library match is found (or `--skip-library` is used), the tool falls back to custom theme generation via registry + wallpaper download + DL lighting.

**Prerequisites:**
- Python 3.10+ with `requests` package (`pip install requests`)
- Registry write access (for desktop styling — gracefully skipped if unavailable)
- Dynamic Lighting driver built (for RGB — gracefully skipped if unavailable)

**CLI Commands:**

| Command | Description |
|---------|-------------|
| `python modules/themes/apply-theme.py --spec '<json>'` | Apply a theme (checks library first, then custom) |
| `python modules/themes/apply-theme.py --spec-file <path>` | Apply a theme from a JSON file |
| `python modules/themes/apply-theme.py --skip-library` | Force custom generation, skip library match |
| `python modules/themes/apply-theme.py --list-library` | List available packaged themes |
| `python modules/themes/apply-theme.py --check` | Check which theming capabilities are available |
| `python modules/themes/apply-theme.py --stop-lighting` | Stop the running theme lighting effect |
| `python modules/themes/msix_handler.py list` | List all themes in the library |
| `python modules/themes/msix_handler.py apply <theme_id>` | Apply a specific packaged theme by ID |
| `python modules/themes/msix_handler.py rebuild-catalog` | Rebuild catalog from MSIX packages |
| `python modules/themes/lighting_handler.py --palette "<colors>" --style <style>` | Run just the RGB lighting effect |
| `python modules/themes/lighting_handler.py --stop` | Stop the RGB lighting effect |

**Theme Spec Format:**

The agent generates this JSON from the user's natural language request:

```json
{
    "name": "enchanted-forest",
    "wallpaper_url": "https://example.com/enchanted-forest.jpg",
    "wallpaper_search": "enchanted forest green mossy",
    "art_search": "",
    "accent_color": "#4A7C2E",
    "mode": "dark",
    "taskbar_accent": true,
    "transparency": true,
    "dl_palette": ["#4A7C2E", "#8B6914", "#2D5016", "#6B8F3C"],
    "dl_style": "wave"
}
```

All fields are optional — the tool applies what it can and gracefully skips the rest.

**Field reference:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Theme name (for display) |
| `wallpaper_url` | string | Direct URL to wallpaper image (preferred) |
| `wallpaper_search` | string | Unsplash photo search query (fallback for nature, landscapes, photos) |
| `art_search` | string | Museum art search query (fallback for paintings, fine art, artists). Searches Art Institute of Chicago. |
| `accent_color` | string | Hex color for Windows accent (`#RRGGBB`) |
| `mode` | string | `"dark"` or `"light"` — sets both app and system theme |
| `taskbar_accent` | bool | Show accent color on taskbar and Start menu |
| `transparency` | bool | Enable transparency effects |
| `dl_palette` | string[] | 2-6 hex colors for RGB lighting effect |
| `dl_style` | string | `"wave"`, `"breathe"`, `"shimmer"`, `"static"`, or `"pulse"` |

**Wallpaper source priority:** direct URL → museum art search → Unsplash photo search.
Wallpapers are cached per theme name in `~/Pictures/themes/` so re-applying a theme reuses the same image.

**Example Prompt Mappings:**

| User Says | Action |
|-----------|--------|
| "Make everything forest themed" | Generate spec with green accent, forest wallpaper, dark mode, green DL palette → `apply-theme.py --spec '...'` |
| "Anime sky theme" | Generate spec with sky blue accent, anime sky wallpaper, light mode, pastel DL palette |
| "Make my PC look like the ocean" | Deep blue accent, ocean wallpaper, dark mode, blue DL wave effect |
| "Impressionist art theme" | Use `art_search: "impressionist landscape"` to find paintings. Warm palette, dark mode, breathe effect |
| "Water lilies theme" | Use `art_search: "water lilies"` to find paintings. Green/blue palette, dark mode, wave effect |
| "Pink aesthetic" | Pink accent, pink flower wallpaper (`wallpaper_search`), light mode, pink DL shimmer |
| "Dark hacker theme" | Black/green accent, dark matrix wallpaper, dark mode, green DL pulse |
| "Stop the theme lighting" | `python modules/themes/apply-theme.py --stop-lighting` |

**How to generate a theme spec from a prompt:**

1. **Name**: Use the user's theme description
2. **Colors**: Pick 1 accent color + 2-6 DL palette colors that match the theme. The accent color should be the dominant/primary color.
3. **Wallpaper**: Choose the right source based on the theme:
   - **Art/painting themes** (e.g., "impressionist", "watercolor", "abstract art"): Use `art_search` with the style or subject. This searches museum collections for actual artwork.
   - **Photo themes** (e.g., "ocean", "forest", "sunset"): Use `wallpaper_search` for Unsplash photos.
   - **Specific image**: Use `wallpaper_url` with a direct link. Always provide a fallback (`art_search` or `wallpaper_search`).
4. **Mode**: Choose dark or light based on the theme mood (dark for moody/gaming/night themes, light for bright/cute/nature themes)
5. **Taskbar**: Usually `true` for bold themes (forest green, ocean blue), `false` for subtle/light themes
6. **DL style**: Match the theme mood — `wave` (flowing/natural), `breathe` (calm/ambient), `shimmer` (sparkly/magical), `static` (clean/minimal), `pulse` (energetic/gaming), `droplet` (water/rain/pond)

**IMPORTANT — Library themes vs custom themes vs standalone effects:**
- **Library themes** (MSIX packages in `modules/themes/library/`) are full Windows themes with wallpapers, accent colors, sounds, and cursors. The tool checks the library automatically when `apply-theme.py --spec` is called. When a library theme matches, the agent should still **generate a creative per-lamp keyboard animation** for the theme.
- **Custom themes** (generated via registry + wallpaper download) are the fallback when no library match exists. These use `dl_style` for generic palette-based RGB effects.
- **Standalone effects** (`modules/dynamic-lighting/effects/`) are custom per-lamp animations with unique visuals (koi fish swimming, cherry blossoms falling, shooting stars). They have their own hardcoded colors and physics.
- When a user asks to **"create a new effect"**, **"make an animation"**, or describes a **specific visual scene** (e.g., "water droplets on a pond", "fireflies in a forest") → **generate a standalone effect script** in `modules/dynamic-lighting/effects/`.
- When a user asks to **"change my theme"** or **"make everything X"** → use the theme engine (`apply-theme.py --spec`). It will check the library first, then fall back to custom.

**Capability-aware**: The tool auto-detects what's available. If registry writes aren't possible, desktop styling is skipped. If no DL device is found, lighting is skipped. The tool always reports what it applied and what it skipped.

## Routing

When the user's request involves:
- **"Create/generate/make a new effect/animation"** → Generate a standalone effect script in `modules/dynamic-lighting/effects/` (see template above)
- **"Run [effect name]", "Play koi fish"** → `python modules/dynamic-lighting/lighting.py run-effect <name>`
- **Lighting, RGB, keyboard colors, solid color** → Use Dynamic Lighting CLI commands
- **"Cinematic mode", "match lights to screen", "ambilight", "bias light", "movie mode"** → `python modules/dynamic-lighting/lighting.py run-effect cinematic`
- **Alerts, notifications, "when I get", "flash when", "notify me"** → Use alert-watcher.py CLI commands
- **Spotify, music, "sync to music", "what's playing", album colors** → Use Spotify module commands
- **Theme, accent color, dark mode, light mode, wallpaper, "make everything X"** → Use Themes module (`apply-theme.py --spec`). Library themes are checked first automatically. When a library theme is applied, generate a matching keyboard animation.
- **Just wallpaper** → Use Themes module with only `wallpaper_url`/`wallpaper_search`/`art_search` fields
- **Just accent color or dark/light mode** → Use Themes module with only `accent_color`/`mode` fields
- **"Make everything [theme]"** or **broad personalization** → Use Themes module with full spec. If a library theme matches, it's applied for richer results (sounds, cursors, wallpaper sets).
- **"List available themes"** or **"what themes do you have"** → `python modules/themes/apply-theme.py --list-library`
