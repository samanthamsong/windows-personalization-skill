import os
import subprocess, json, time, threading

EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingDriver', 'bin', 'Debug', 'net9.0-windows10.0.26100.0', 'DynamicLightingDriver.exe')
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

# 3. Apply falling cherry blossom effect
#    Layer 0: Soft pink glow breathing gently — the blush of spring air
#    Layer 1: Gentle wave of deeper sakura pink drifting across — wind through the branches
#    Layer 2: Sparse white-pink twinkle — individual petals catching the light as they fall
layers = json.dumps([
    {
        "pattern": "breathe",
        "base_color": "#FFB7C5",
        "accent_color": "#FFDDE1",
        "speed": 0.15,
        "density": 1.0,
        "direction": "center_out",
        "z_index": 0
    },
    {
        "pattern": "wave",
        "base_color": "#FFB7C5",
        "accent_color": "#E8909C",
        "speed": 0.3,
        "density": 0.6,
        "direction": "left_to_right",
        "z_index": 1
    },
    {
        "pattern": "twinkle",
        "base_color": "#FFB7C5",
        "accent_color": "#FFFFFF",
        "speed": 0.5,
        "density": 0.3,
        "z_index": 2
    }
], separators=(',', ':'))

send(f'CREATE_EFFECT layered layers={layers}')
resp = recv()
print(resp, flush=True)

print(f'\n🌸 Cherry blossoms falling... Server PID: {proc.pid} — Ctrl+C to stop', flush=True)

# === LAMP LAYOUT (for alert coordination) ===
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

PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rules', '.pause')

frame = 0
try:
    while True:
        # Alert flash coordination — check for notification override
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
            # Resume the effect after flash
            send(f'CREATE_EFFECT layered layers={layers}')
            recv()
            continue
        if proc.poll() is not None:
            break
        time.sleep(0.25)
except KeyboardInterrupt:
    proc.terminate()
