"""
Spotify → Dynamic Lighting sync.

Polls Spotify for the currently playing track and drives keyboard lighting
based on album art colors and audio features (energy, mood, tempo).

Usage:
    python spotify-sync.py start              # Full takeover mode
    python spotify-sync.py start --overlay    # Tint current effect with album colors
    python spotify-sync.py stop               # Stop sync
    python spotify-sync.py status             # Show current track + mood

Requires:
    - Spotify Premium account
    - SPOTIPY_CLIENT_ID env var or run `python auth.py` first
    - Dynamic Lighting driver built and registered
"""

import os
import sys
import json
import time
import math
import signal
import subprocess
import threading

# Add module path
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MODULE_DIR)

from auth import get_spotify, check_status
from color_extract import colors_from_url, rgb_to_hex
from mood_mapper import classify_mood, mood_to_effect_params, apply_brightness, blend_colors, shift_color_temperature

# Driver exe path
DRIVER_EXE = os.path.join(MODULE_DIR, '..', 'dynamic-lighting', 'src',
                          'DynamicLightingDriver', 'bin', 'Debug',
                          'net9.0-windows10.0.26100.0', 'DynamicLightingDriver.exe')

# Overlay palette file — effects read this to shift their color palette
PALETTE_FILE = os.path.join(MODULE_DIR, '..', 'dynamic-lighting', 'rules', '.spotify-palette')

# PID file for stop command
PID_FILE = os.path.join(MODULE_DIR, '.spotify-sync.pid')

# Keyboard layout (same as effect scripts)
ROWS = [15, 15, 15, 14, 13, 8, 7]
ROW_OFFSETS = [0, 0, 0.075, 0.12, 0.15, 0, 0.85]
ROW_KW = [1, 1, 1, 1, 1, 1.5, 1]

LAMPS = []
idx = 0
for ri, count in enumerate(ROWS):
    for ci in range(count):
        x = (ROW_OFFSETS[ri] + ci * ROW_KW[ri]) / 15.0
        y = ri / 6.0
        LAMPS.append({"idx": idx, "x": x, "y": y, "row": ri, "col": ci})
        idx += 1


class SpotifySync:
    def __init__(self, overlay=False):
        self.overlay = overlay
        self.running = False
        self.sp = None
        self.proc = None
        self.current_track_id = None
        self.current_colors = [(80, 80, 120)]
        self.current_params = None

    def start_driver(self):
        """Launch the Dynamic Lighting driver subprocess."""
        if not os.path.exists(DRIVER_EXE):
            print(f"ERROR: Driver not found at {DRIVER_EXE}")
            print("Run: dotnet build modules/dynamic-lighting/DynamicLightingDriver.sln")
            sys.exit(1)

        self.proc = subprocess.Popen(
            [DRIVER_EXE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        # Drain stderr in background
        threading.Thread(target=lambda: [self.proc.stderr.readline() for _ in iter(int, 1)], daemon=True).start()

        ready = self.proc.stdout.readline().decode().strip()
        if ready != 'READY':
            print(f"ERROR: Driver not ready: {ready}")
            sys.exit(1)

    def send(self, cmd):
        self.proc.stdin.write((cmd + '\n').encode())
        self.proc.stdin.flush()

    def recv(self):
        return self.proc.stdout.readline().decode().strip()

    def get_current_track(self):
        """Poll Spotify for currently playing track."""
        try:
            result = self.sp.current_playback()
            if not result or not result.get('is_playing') or result.get('currently_playing_type') != 'track':
                return None
            track = result['item']
            return {
                'id': track['id'],
                'name': track['name'],
                'artist': ', '.join(a['name'] for a in track['artists']),
                'album': track['album']['name'],
                'album_art': track['album']['images'][0]['url'] if track['album']['images'] else None,
                'duration_ms': track['duration_ms'],
                'progress_ms': result.get('progress_ms', 0),
            }
        except Exception as e:
            print(f"  ⚠ Spotify API error: {e}")
            return None

    def get_audio_features(self, track_id):
        """Get audio features for a track."""
        try:
            features = self.sp.audio_features([track_id])
            if features and features[0]:
                return features[0]
        except Exception as e:
            print(f"  ⚠ Audio features error: {e}")
        return {'energy': 0.5, 'valence': 0.5, 'tempo': 120, 'danceability': 0.5, 'instrumentalness': 0.0}

    def render_frame(self, t, params):
        """Render a single frame of the music-reactive effect."""
        colors = params['colors']
        if not colors:
            colors = [(80, 80, 120)]

        speed = params.get('speed', 1.0)
        brightness = params.get('brightness', 1.0)
        pattern = params.get('pattern', 'wave')
        color_shift = params.get('color_shift')

        # Apply color temperature shift if specified
        shifted_colors = colors[:]
        if color_shift:
            shifted_colors = [shift_color_temperature(c, color_shift) for c in colors]

        frame = {}
        for lamp in LAMPS:
            x, y = lamp['x'], lamp['y']

            if pattern == 'wave':
                # Horizontal wave using album colors
                wave = math.sin(x * math.pi * 2 - t * speed * 2.0) * 0.5 + 0.5
                # Pick two colors to blend between
                c1 = shifted_colors[0]
                c2 = shifted_colors[min(1, len(shifted_colors) - 1)]
                color = blend_colors(c1, c2, wave)

                # Add vertical variation with third color
                if len(shifted_colors) > 2:
                    vert = math.sin(y * math.pi - t * speed * 0.5) * 0.3 + 0.5
                    color = blend_colors(color, shifted_colors[2], vert * 0.3)

            elif pattern == 'breathe':
                # Breathing pulse with album colors
                pulse = math.sin(t * speed * 1.5) * 0.5 + 0.5
                c1 = shifted_colors[0]
                c2 = shifted_colors[min(1, len(shifted_colors) - 1)]
                base = blend_colors(c1, c2, x)
                # Dim the base by the pulse
                color = apply_brightness(base, 0.3 + pulse * 0.7)

            else:
                color = shifted_colors[0]

            # Apply overall brightness
            color = apply_brightness(color, brightness)

            # Twinkle overlay
            if params.get('overlay') == 'twinkle':
                sparkle = math.sin(t * 8 + lamp['idx'] * 1.7) * 0.5 + 0.5
                if sparkle > 0.92:
                    color = (255, 255, 255)

            frame[str(lamp['idx'])] = rgb_to_hex(*color)

        return frame

    def write_overlay_palette(self, colors, mood, track_name):
        """Write album palette to file for overlay mode."""
        data = {
            'colors': [rgb_to_hex(*c) for c in colors],
            'mood': mood,
            'track': track_name,
        }
        try:
            os.makedirs(os.path.dirname(PALETTE_FILE), exist_ok=True)
            with open(PALETTE_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"  ⚠ Failed to write palette: {e}")

    def clear_overlay_palette(self):
        """Remove the overlay palette file."""
        try:
            if os.path.exists(PALETTE_FILE):
                os.remove(PALETTE_FILE)
        except Exception:
            pass

    def run(self):
        """Main sync loop."""
        self.sp = get_spotify()
        user = self.sp.current_user()
        print(f"🔗 Connected to Spotify (user: {user['display_name']})")

        if not self.overlay:
            self.start_driver()
            # Set effect name
            self.send('SET_EFFECT_NAME Spotify Sync')
            self.recv()

        # Write PID file
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))

        self.running = True
        mode_str = "overlay" if self.overlay else "replace"
        print(f"🎵 Syncing in {mode_str} mode (updates every 3s, Ctrl+C to stop)")
        print()

        frame_count = 0
        start_time = time.time()

        try:
            while self.running:
                track = self.get_current_track()

                if not track:
                    if self.current_track_id:
                        print("⏸  Playback paused or stopped")
                        self.current_track_id = None
                        if self.overlay:
                            self.clear_overlay_palette()
                    time.sleep(3)
                    continue

                # Track changed — update colors and mood
                if track['id'] != self.current_track_id:
                    self.current_track_id = track['id']
                    print(f"🎵 Now playing: \"{track['name']}\" by {track['artist']}")

                    # Extract album colors
                    if track['album_art']:
                        try:
                            self.current_colors = colors_from_url(track['album_art'], num_colors=5)
                            hex_colors = ', '.join(rgb_to_hex(*c) for c in self.current_colors[:3])
                            print(f"🎨 Album colors: {hex_colors}")
                        except Exception as e:
                            print(f"  ⚠ Color extraction failed: {e}")
                            self.current_colors = [(80, 80, 120), (60, 60, 100)]

                    # Get audio features and classify mood
                    features = self.get_audio_features(track['id'])
                    mood = classify_mood(features)
                    self.current_params = mood_to_effect_params(
                        mood, features.get('tempo', 120), self.current_colors
                    )
                    tempo = features.get('tempo', 120)
                    energy = features.get('energy', 0.5)
                    print(f"🔆 Mood: {mood} (tempo: {tempo:.0f}bpm, energy: {energy:.2f})")
                    print()

                    if self.overlay:
                        self.write_overlay_palette(self.current_colors, mood,
                                                   f"{track['name']} - {track['artist']}")

                # Render frames in replace mode
                if not self.overlay and self.current_params:
                    # Run ~8fps for 3 seconds, then re-poll Spotify
                    for _ in range(24):  # 3 seconds at 8fps
                        if not self.running:
                            break
                        t = time.time() - start_time
                        frame = self.render_frame(t, self.current_params)
                        self.send(f"SET_LAMPS {json.dumps(frame)}")
                        self.recv()
                        frame_count += 1
                        target = frame_count / 8.0
                        elapsed = time.time() - start_time
                        if target > elapsed:
                            time.sleep(target - elapsed)
                else:
                    # Overlay mode — just poll every 3s
                    time.sleep(3)

        except KeyboardInterrupt:
            print("\n⏹  Stopping Spotify sync...")
        finally:
            self.running = False
            if self.overlay:
                self.clear_overlay_palette()
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
            if self.proc:
                try:
                    self.send('QUIT')
                except Exception:
                    pass
                self.proc.terminate()


def cmd_start(args):
    overlay = '--overlay' in args
    sync = SpotifySync(overlay=overlay)

    # Handle Ctrl+C gracefully
    def sigint_handler(sig, frame):
        sync.running = False
    signal.signal(signal.SIGINT, sigint_handler)

    sync.run()


def cmd_stop():
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, signal.SIGINT)
            print(f"⏹  Sent stop signal to Spotify sync (PID {pid})")
        except OSError:
            print(f"⚠  Process {pid} not found, cleaning up PID file")
            os.remove(PID_FILE)
    else:
        print("ℹ  No Spotify sync running")


def cmd_status():
    if not check_status():
        return

    sp = get_spotify()
    result = sp.current_playback()

    if not result or not result.get('is_playing'):
        print("⏸  Nothing playing on Spotify")
        return

    track = result['item']
    name = track['name']
    artist = ', '.join(a['name'] for a in track['artists'])
    print(f"🎵 Now playing: \"{name}\" by {artist}")

    # Show audio features
    try:
        features = sp.audio_features([track['id']])
        if features and features[0]:
            f = features[0]
            mood = classify_mood(f)
            print(f"🔆 Mood: {mood}")
            print(f"   Energy: {f['energy']:.2f}  Valence: {f['valence']:.2f}  "
                  f"Tempo: {f['tempo']:.0f}bpm  Dance: {f['danceability']:.2f}")
    except Exception:
        pass

    # Show album colors
    if track['album']['images']:
        try:
            colors = colors_from_url(track['album']['images'][0]['url'], num_colors=3)
            hex_colors = ', '.join(rgb_to_hex(*c) for c in colors)
            print(f"🎨 Album colors: {hex_colors}")
        except Exception:
            pass

    # Check if sync is running
    if os.path.exists(PID_FILE):
        print("🔄 Spotify sync is active")
    else:
        print("ℹ  Spotify sync is not running")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python spotify-sync.py start [--overlay]  Start music-reactive lighting")
        print("  python spotify-sync.py stop               Stop sync")
        print("  python spotify-sync.py status             Show current track + mood")
        print("  python spotify-sync.py auth               Authenticate with Spotify")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == 'start':
        cmd_start(sys.argv[2:])
    elif cmd == 'stop':
        cmd_stop()
    elif cmd == 'status':
        cmd_status()
    elif cmd == 'auth':
        from auth import get_spotify
        sp = get_spotify()
        user = sp.current_user()
        print(f"✅ Authenticated as: {user['display_name']}")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
