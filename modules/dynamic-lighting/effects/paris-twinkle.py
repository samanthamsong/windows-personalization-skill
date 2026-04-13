import os
import subprocess, json, time, threading, sys

proc = subprocess.Popen(
    ['dotnet', 'run', '--project', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingMcp', 'DynamicLightingMcp.csproj'), '--no-build'],
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

# 1. Initialize
send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
    'protocolVersion': '2024-11-05',
    'capabilities': {},
    'clientInfo': {'name': 'cli', 'version': '1.0'}
}})
read_response(10)

# 2. Initialized notification
send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
time.sleep(2)

# 3. Apply Paris night twinkle effect
send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
    'name': 'create_lighting_effect',
    'arguments': {
        'description': 'Paris night twinkle - elegant golden lights sparkling against a deep midnight blue Parisian sky',
        'pattern': 'twinkle',
        'base_color': '#0D1B3E',
        'accent_color': '#FFD180',
        'speed': 0.5,
        'density': 0.35
    }
}})
resp = read_response(15)
print('Effect applied:', resp, flush=True)
print(f'MCP server PID: {proc.pid} — keeping alive...', flush=True)

# Keep process alive indefinitely so the effect keeps running
try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
