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

# Gemini: cosmic blue-to-purple gradient base + cyan starlight twinkle + bright white sparkle highlights
layers = json.dumps([
    {"pattern": "gradient", "base_color": "#1A44CC", "accent_color": "#8E24AA", "speed": 0.4, "density": 1.0, "direction": "left_to_right", "z_index": 0},
    {"pattern": "wave", "base_color": "#1A44CC", "accent_color": "#00BCD4", "speed": 0.6, "density": 0.5, "direction": "right_to_left", "z_index": 1},
    {"pattern": "twinkle", "base_color": "#1A44CC", "accent_color": "#E0E0FF", "speed": 1.2, "density": 0.12, "z_index": 2}
])

send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
    'name': 'create_lighting_effect',
    'arguments': {
        'description': 'Google Gemini aesthetic - cosmic flowing blue-to-purple gradient with cyan waves and bright starlight twinkles',
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
