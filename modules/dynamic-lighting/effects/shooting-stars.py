import os, subprocess, json, time, threading, sys, math

# Launch lighting driver
EXE = os.path.join(os.environ.get('LOCALAPPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Local')), 'DynamicLightingDriver', 'DynamicLightingDriver.exe')
proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int, 1)], daemon=True).start()

def send(cmd):
    proc.stdin.write((cmd + '\n').encode())
    proc.stdin.flush()
def recv():
    return proc.stdout.readline().decode().strip()

# Wait for driver ready
ready = recv()
assert ready == 'READY', f'Driver not ready: {ready}'

send("SET_EFFECT_NAME Shooting Stars")
recv()

# Keyboard layout: 87-key TKL, 7 rows
rows = [15, 15, 15, 14, 13, 8, 7]
row_offsets = [0, 0, 0.075, 0.12, 0.15, 0, 0.85]
row_kw = [1, 1, 1, 1, 1, 1.5, 1]

lamps = []
idx = 0
for ri, count in enumerate(rows):
    for ci in range(count):
        x = (row_offsets[ri] + ci * row_kw[ri]) / 15.0
        y = ri / 6.0
        lamps.append({"idx": idx, "x": x, "y": y, "row": ri, "col": ci})
        idx += 1

# Night sky colors
BASE = (5, 5, 16)
ACCENT = (136, 204, 255)

def lerp(c1, c2, t):
    t = max(0, min(1, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def render_frame(t):
    """Return {lamp_index_str: '#rrggbb'} for each lamp at time t seconds."""
    star_slots = 6
    tail_length = 0.25
    head_glow = 0.04
    colors = {}

    for lamp in lamps:
        lx, ly = lamp['x'], lamp['y']
        best_brightness = 0.0

        for i in range(star_slots):
            h1 = ((i * 73856093) ^ 19349663) & 0x7FFFFFFF
            h2 = ((i * 19349663) ^ 83492791) & 0x7FFFFFFF
            h3 = ((i * 83492791) ^ 73856093) & 0x7FFFFFFF

            star_y = (h1 % 1000) / 1000.0
            period = 2.0 + (h2 % 1000) / 250.0
            speed_var = 0.8 + (h3 % 1000) / 1000.0 * 0.6

            cycle_time = t * speed_var / period
            phase = cycle_time - math.floor(cycle_time)
            star_x = 1.0 + tail_length - phase * (1.0 + tail_length + head_glow)

            dx = lx - star_x
            dy = ly - star_y
            y_proximity = math.exp(-dy * dy / 0.01)

            if y_proximity < 0.05:
                continue

            if -head_glow <= dx <= head_glow:
                head_intensity = 1.0 - abs(dx) / head_glow
                best_brightness = max(best_brightness, head_intensity * y_proximity)
            elif 0 < dx < tail_length:
                tail_intensity = 1.0 - dx / tail_length
                tail_intensity *= tail_intensity
                best_brightness = max(best_brightness, tail_intensity * y_proximity * 0.7)

        if best_brightness < 0.01:
            color = BASE
        else:
            star_r = int(ACCENT[0] + (255 - ACCENT[0]) * best_brightness)
            star_g = int(ACCENT[1] + (255 - ACCENT[1]) * best_brightness)
            star_b = int(ACCENT[2] + (255 - ACCENT[2]) * best_brightness)
            blend = min(best_brightness * 1.5, 1.0)
            r = int(BASE[0] + (star_r - BASE[0]) * blend)
            g = int(BASE[1] + (star_g - BASE[1]) * blend)
            b = int(BASE[2] + (star_b - BASE[2]) * blend)
            color = (min(r, 255), min(g, 255), min(b, 255))

        colors[str(lamp['idx'])] = '#{:02x}{:02x}{:02x}'.format(*color)
    return colors

# Alert flash coordination
PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rules', '.pause')

print("Effect is running on keyboard!")
sys.stdout.flush()

# Animation loop at ~8fps
frame = 0
start = time.time()
try:
    while True:
        if os.path.exists(PAUSE_FILE):
            try:
                with open(PAUSE_FILE, 'r') as f:
                    alert_data = f.read().strip()
                parts = alert_data.split('|')
                flash_color = parts[0] if parts[0].startswith('#') else '#FF69B4'
                flash_duration = float(parts[1]) if len(parts) > 1 else 3.0
                all_flash = {str(lamp['idx']): flash_color for lamp in lamps}
                flash_start = time.time()
                while time.time() - flash_start < flash_duration:
                    send(f"SET_LAMPS {json.dumps(all_flash)}")
                    recv()
                    frame += 1
                    time.sleep(0.125)
            except Exception as e:
                print(f"Alert flash error: {e}")
            finally:
                try:
                    os.remove(PAUSE_FILE)
                except Exception:
                    pass
            continue

        t = time.time() - start
        colors = render_frame(t)
        send(f"SET_LAMPS {json.dumps(colors)}")
        recv()
        frame += 1
        target = frame / 8.0
        if target > (time.time() - start):
            time.sleep(target - (time.time() - start))

        if proc.poll() is not None:
            break
except KeyboardInterrupt:
    proc.terminate()
