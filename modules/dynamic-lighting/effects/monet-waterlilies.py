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
try: proc.wait()
except KeyboardInterrupt: proc.terminate()
