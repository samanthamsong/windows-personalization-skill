import os
import subprocess, json, time, threading

proc = subprocess.Popen(
    ['dotnet', 'run', '--project', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingMcp', 'DynamicLightingMcp.csproj'), '--no-build'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=False
)

def send(msg):
    proc.stdin.write(json.dumps(msg).encode('utf-8') + b'\n')
    proc.stdin.flush()

def read_response(timeout=15):
    result = []
    def reader():
        line = proc.stdout.readline()
        if line:
            result.append(line.decode('utf-8').strip())
    t = threading.Thread(target=reader)
    t.start()
    t.join(timeout)
    return result[0] if result else None

# 1. Initialize MCP handshake
send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
    'protocolVersion': '2024-11-05',
    'capabilities': {},
    'clientInfo': {'name': 'cli', 'version': '1.0'}
}})
read_response(10)

# 2. Initialized notification
send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
time.sleep(2)

# 3. Apply "The Summer I Turned Pretty" effect
#    Layer 0: Deep ocean blue breathing slowly — Cousins Beach tides rolling in and out
#    Layer 1: Warm sunset wave of coral and golden amber drifting across — golden hour on the beach
#    Layer 2: Soft white-gold twinkle — sunlight sparkling on the water and summer stars
layers = json.dumps([
    {
        "pattern": "breathe",
        "base_color": "#1B4F72",
        "accent_color": "#5DADE2",
        "speed": 0.12,
        "density": 1.0,
        "direction": "center_out",
        "z_index": 0
    },
    {
        "pattern": "wave",
        "base_color": "#1B4F72",
        "accent_color": "#F0896C",
        "speed": 0.25,
        "density": 0.5,
        "direction": "left_to_right",
        "z_index": 1
    },
    {
        "pattern": "twinkle",
        "base_color": "#1B4F72",
        "accent_color": "#FDEBD0",
        "speed": 0.4,
        "density": 0.25,
        "z_index": 2
    }
])

send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
    'name': 'create_lighting_effect',
    'arguments': {
        'description': 'The Summer I Turned Pretty - deep ocean blue breathes like the Cousins Beach tide, warm coral-gold waves drift across like a sunset over the water, and soft golden twinkles shimmer like sunlight on the waves and summer stars above',
        'layers': layers
    }
}})

resp = read_response(15)
if resp:
    try:
        parsed = json.loads(resp)
        for item in parsed.get('result', {}).get('content', []):
            if item.get('type') == 'text':
                print(item['text'], flush=True)
    except json.JSONDecodeError:
        print('Response:', resp, flush=True)

print(f'\n🌊 The Summer I Turned Pretty... Server PID: {proc.pid} — Ctrl+C to stop', flush=True)

try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
