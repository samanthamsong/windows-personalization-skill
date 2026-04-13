import os
import subprocess, json, time, threading, sys

proc = subprocess.Popen(
    ['dotnet', 'run', '--project', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingMcp', 'DynamicLightingMcp.csproj')],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=False
)

def send(msg):
    data = json.dumps(msg).encode('utf-8')
    proc.stdin.write(data + b'\n')
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

# 3. Apply Hello Kitty effect
#    Soft pink base with white twinkle accents — cute and dreamy
send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
    'name': 'create_lighting_effect',
    'arguments': {
        'description': 'Hello Kitty - soft candy pink glow with gentle sparkling white twinkles like Hello Kittys iconic bow ribbon',
        'pattern': 'twinkle',
        'base_color': '#FF69B4',
        'accent_color': '#FFFFFF',
        'speed': 0.3,
        'density': 0.25
    }
}})
resp = read_response(15)
print('🎀 Hello Kitty effect activated!', flush=True)
print('Effect response:', resp, flush=True)
print(f'MCP server PID: {proc.pid} — keeping alive (Ctrl+C to stop)...', flush=True)

# Keep process alive so the effect keeps running
try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
