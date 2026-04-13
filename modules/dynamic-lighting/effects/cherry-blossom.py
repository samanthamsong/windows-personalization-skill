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
])

send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
    'name': 'create_lighting_effect',
    'arguments': {
        'description': 'Falling cherry blossoms - a gentle sakura pink glow breathes softly like spring air, while waves of deeper pink drift across like wind through branches, and sparse white-pink petals twinkle as they catch the light falling to the ground',
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

print(f'\n🌸 Cherry blossoms falling... Server PID: {proc.pid} — Ctrl+C to stop', flush=True)

try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
