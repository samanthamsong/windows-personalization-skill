import os
import subprocess, json, time, threading

proc = subprocess.Popen(
    ['dotnet', 'run', '--project', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingMcp', 'DynamicLightingMcp.csproj'), '--no-build'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False
)

def send(msg):
    proc.stdin.write(json.dumps(msg).encode('utf-8') + b'\n')
    proc.stdin.flush()

def read_response(timeout=15):
    result = []
    def reader():
        line = proc.stdout.readline()
        if line: result.append(line.decode('utf-8').strip())
    t = threading.Thread(target=reader)
    t.start(); t.join(timeout)
    return result[0] if result else None

send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
    'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'cli', 'version': '1.0'}
}})
read_response(15)
send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
time.sleep(2)

# Monet's Water Lilies:
#   - Soft dreamy pond water: slow wave of deep teal-green to soft sage
#   - Lily pad reflections: gentle breathe of muted lavender-pink to moss green
#   - Dappled sunlight on water: sparse warm golden twinkle
layers = json.dumps([
    {"pattern": "wave", "base_color": "#2E5B52", "accent_color": "#7BA899", "speed": 0.2, "density": 1.0, "direction": "left_to_right", "z_index": 0},
    {"pattern": "breathe", "base_color": "#5B7065", "accent_color": "#C9A0C4", "speed": 0.15, "density": 0.5, "direction": "center_out", "z_index": 1},
    {"pattern": "twinkle", "base_color": "#5B7065", "accent_color": "#F5DEB3", "speed": 0.4, "density": 0.08, "z_index": 2}
])

send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
    'name': 'create_lighting_effect',
    'arguments': {
        'description': "Monet's Water Lilies - dreamy impressionist pond with soft teal-green waves, muted lavender-pink lily reflections breathing gently, and sparse golden sunlight dappling the surface",
        'layers': layers
    }
}})
resp = read_response(15)
if resp:
    parsed = json.loads(resp)
    for item in parsed.get('result', {}).get('content', []):
        if item.get('type') == 'text':
            print(item['text'], flush=True)

print(f'\nServer PID: {proc.pid} — Ctrl+C to stop', flush=True)
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

def recv():
    return json.loads(proc.stdout.readline())

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
                    send({'jsonrpc':'2.0','id':100+frame,'method':'tools/call','params':{
                        'name':'set_per_lamp_colors',
                        'arguments':{'lamp_colors': json.dumps(all_flash)}
                    }})
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
        if proc.poll() is not None:
            break
        time.sleep(0.25)
except KeyboardInterrupt:
    proc.terminate()
