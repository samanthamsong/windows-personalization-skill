"""
Dynamic Lighting CLI
====================
Command-line interface for controlling Dynamic Lighting devices.
Communicates with the C# DynamicLightingMcp.exe via JSON-RPC over stdio.

Usage:
    python lighting.py set-color <color>
    python lighting.py set-per-lamp '<json>'
    python lighting.py list-devices
    python lighting.py list-effects
    python lighting.py run-effect <name>
    python lighting.py stop
    python lighting.py diagnose
"""

import os
import sys
import json
import time
import subprocess
import threading
import argparse
import signal

EXE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'src', 'DynamicLightingMcp', 'bin', 'Debug',
    'net9.0-windows10.0.26100.0', 'DynamicLightingMcp.exe'
)

EFFECTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'effects')


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def launch_server():
    """Launch the C# DynamicLightingMcp.exe and return the subprocess."""
    if not os.path.isfile(EXE):
        print(f"Error: MCP server exe not found at {EXE}", file=sys.stderr)
        print("Build it first: dotnet build modules/dynamic-lighting/DynamicLightingMCP.sln", file=sys.stderr)
        sys.exit(1)
    proc = subprocess.Popen(
        [EXE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    # Drain stderr in background to prevent blocking
    threading.Thread(
        target=lambda: [proc.stderr.readline() for _ in iter(int, 1)],
        daemon=True,
    ).start()
    return proc


def send(proc, obj):
    """Send a JSON-RPC message to the server."""
    proc.stdin.write((json.dumps(obj) + '\n').encode())
    proc.stdin.flush()


def recv(proc):
    """Read a JSON-RPC response from the server."""
    line = proc.stdout.readline()
    if not line:
        return None
    return json.loads(line)


def handshake(proc):
    """Perform the MCP initialization handshake."""
    send(proc, {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'initialize',
        'params': {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {'name': 'lighting-cli', 'version': '1.0'},
        },
    })
    recv(proc)
    send(proc, {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    time.sleep(3)


def call_tool(proc, tool_name, arguments, req_id=2):
    """Call an MCP tool and return the response."""
    send(proc, {
        'jsonrpc': '2.0',
        'id': req_id,
        'method': 'tools/call',
        'params': {
            'name': tool_name,
            'arguments': arguments,
        },
    })
    return recv(proc)


def print_response(resp):
    """Print the text content from an MCP tool response."""
    if resp is None:
        print("No response from server.")
        return
    result = resp.get('result', resp)
    if isinstance(result, dict) and 'content' in result:
        for item in result['content']:
            if item.get('type') == 'text':
                print(item['text'])
    else:
        print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_set_color(args):
    proc = launch_server()
    try:
        handshake(proc)
        resp = call_tool(proc, 'set_solid_color', {'color': args.color})
        print_response(resp)
    finally:
        proc.terminate()


def cmd_set_per_lamp(args):
    proc = launch_server()
    try:
        handshake(proc)
        resp = call_tool(proc, 'set_per_lamp_colors', {'lamp_colors': args.json_str})
        print_response(resp)
    finally:
        proc.terminate()


def cmd_list_devices(args):
    proc = launch_server()
    try:
        handshake(proc)
        resp = call_tool(proc, 'list_lighting_devices', {})
        print_response(resp)
    finally:
        proc.terminate()


def cmd_diagnose(args):
    proc = launch_server()
    try:
        handshake(proc)
        resp = call_tool(proc, 'diagnose_lighting', {})
        print_response(resp)
    finally:
        proc.terminate()


def cmd_list_effects(args):
    if not os.path.isdir(EFFECTS_DIR):
        print(f"Effects directory not found: {EFFECTS_DIR}", file=sys.stderr)
        sys.exit(1)
    effects = []
    for f in sorted(os.listdir(EFFECTS_DIR)):
        if f.endswith('.py') and f != '_template.py' and not f.startswith('_'):
            name = f[:-3]  # strip .py
            effects.append(name)
    if effects:
        print("Available effects:")
        for name in effects:
            print(f"  - {name}")
    else:
        print("No effects found.")


def cmd_run_effect(args):
    name = args.name
    if not name.endswith('.py'):
        name = name + '.py'
    script = os.path.join(EFFECTS_DIR, name)
    if not os.path.isfile(script):
        print(f"Effect not found: {script}", file=sys.stderr)
        print("Run 'python lighting.py list-effects' to see available effects.", file=sys.stderr)
        sys.exit(1)
    # Use CREATE_NEW_PROCESS_GROUP so the effect survives if this CLI exits
    flags = subprocess.CREATE_NEW_PROCESS_GROUP
    p = subprocess.Popen([sys.executable, script], creationflags=flags)
    print(f"Started effect '{args.name}' (PID {p.pid})")
    print("Press Ctrl+C to detach (effect keeps running).")
    try:
        p.wait()
    except KeyboardInterrupt:
        print(f"\nDetached. Effect still running (PID {p.pid}). Use 'lighting.py stop' to end it.")


def cmd_stop(args):
    """Find and kill Python processes running effect scripts."""
    import ctypes

    killed = []
    try:
        # Use WMIC to find python processes with their command lines
        result = subprocess.run(
            ['wmic', 'process', 'where', "name like '%python%'", 'get',
             'ProcessId,CommandLine', '/format:list'],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stdout.strip().split('\n')
        current_pid = os.getpid()
        pid = None
        cmdline = None
        for line in lines:
            line = line.strip()
            if line.startswith('CommandLine='):
                cmdline = line[len('CommandLine='):]
            elif line.startswith('ProcessId='):
                pid = int(line[len('ProcessId='):])
            if pid is not None and cmdline is not None:
                effects_norm = os.path.normpath(EFFECTS_DIR).lower()
                if (pid != current_pid
                        and effects_norm in os.path.normpath(cmdline).lower()
                        and cmdline.endswith('.py')):
                    try:
                        os.kill(pid, signal.SIGTERM)
                        killed.append(pid)
                    except OSError:
                        pass
                pid = None
                cmdline = None
    except Exception as e:
        print(f"Error scanning processes: {e}", file=sys.stderr)

    if killed:
        print(f"Stopped {len(killed)} effect process(es): {killed}")
    else:
        print("No running effect processes found.")


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog='lighting.py',
        description='CLI for controlling Dynamic Lighting devices.',
    )
    sub = parser.add_subparsers(dest='command', required=True)

    # set-color
    p_color = sub.add_parser('set-color', help='Set all lamps to a single color (hex or name)')
    p_color.add_argument('color', help='Color value, e.g. "#FF0000" or "red"')
    p_color.set_defaults(func=cmd_set_color)

    # set-per-lamp
    p_per = sub.add_parser('set-per-lamp', help='Set individual lamp colors via JSON')
    p_per.add_argument('json_str', help='JSON map of lamp index to hex color, e.g. \'{"0":"#FF0000"}\'')
    p_per.set_defaults(func=cmd_set_per_lamp)

    # list-devices
    p_dev = sub.add_parser('list-devices', help='List connected Dynamic Lighting devices')
    p_dev.set_defaults(func=cmd_list_devices)

    # list-effects
    p_eff = sub.add_parser('list-effects', help='List available effect scripts')
    p_eff.set_defaults(func=cmd_list_effects)

    # run-effect
    p_run = sub.add_parser('run-effect', help='Run a named effect (e.g. koi-fish)')
    p_run.add_argument('name', help='Effect name (auto-adds .py)')
    p_run.set_defaults(func=cmd_run_effect)

    # stop
    p_stop = sub.add_parser('stop', help='Stop running effect processes')
    p_stop.set_defaults(func=cmd_stop)

    # diagnose
    p_diag = sub.add_parser('diagnose', help='Run device diagnostics')
    p_diag.set_defaults(func=cmd_diagnose)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
