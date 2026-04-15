# 🎵 Spotify Module

Sync your keyboard lighting to what you're listening to on Spotify. Extracts album art colors and maps audio features (energy, tempo, mood) to dynamic lighting effects.

## Prerequisites

- Spotify Premium account (required for currently-playing API)
- Python packages: `spotipy`, `Pillow`, `requests`
- A Spotify Developer App (free): https://developer.spotify.com/dashboard
  - Create an app with redirect URI: `http://localhost:8888/callback`
  - Copy the **Client ID**

## Setup

```powershell
# Install dependencies
pip install spotipy Pillow requests

# Authenticate (opens browser for Spotify login)
python modules/spotify/auth.py
```

On first run, you'll be prompted for your Spotify Client ID. It's saved locally so you only need to enter it once.

## Usage

```powershell
# Start music-reactive lighting (full takeover)
python modules/spotify/spotify-sync.py start

# Start in overlay mode (tints current effect with album colors)
python modules/spotify/spotify-sync.py start --overlay

# Check what's playing + mood analysis
python modules/spotify/spotify-sync.py status

# Stop sync
python modules/spotify/spotify-sync.py stop
```

## How It Works

1. **Polls Spotify** every 3 seconds for the currently playing track
2. **Extracts colors** from album art via k-means quantization
3. **Analyzes mood** using Spotify audio features (energy, valence, tempo, danceability)
4. **Drives lighting** with a wave/breathe effect using album colors at tempo-matched speed

### Mood → Effect Mapping

| Mood | Trigger | Effect |
|------|---------|--------|
| Energetic | High energy + happy | Fast wave, bright, twinkle overlay |
| Intense | High energy + low valence | Fast wave, cool-shifted colors |
| Melancholy | Low energy + sad | Slow breathe, dim, cool tones |
| Peaceful | Low energy + happy | Slow breathe, warm |
| Ambient | Instrumental | Very slow breathe, dim, twinkle |
| Groovy | High danceability | Medium wave, twinkle overlay |

### Modes

- **Replace mode** (default): Takes full control of the keyboard, renders frames at ~8fps
- **Overlay mode** (`--overlay`): Writes album palette to `rules/.spotify-palette` — running effects can read this file to shift their color palette without interrupting the animation

## Files

| File | Description |
|------|-------------|
| `spotify-sync.py` | Main sync script (CLI entry point) |
| `auth.py` | Spotify OAuth PKCE authentication |
| `color_extract.py` | Album art → dominant color extraction |
| `mood_mapper.py` | Audio features → effect parameter mapping |
| `.spotify-token` | Cached auth token (gitignored) |
| `.spotify-config` | Stored Client ID (gitignored) |
