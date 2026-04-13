"""
Alert Watcher — Background daemon that monitors Windows notifications
and triggers lighting effects based on user-defined rules.

Usage:
    python alert-watcher.py                    # Run with rules/rules.json
    python alert-watcher.py --rules my.json    # Custom rules file
    python alert-watcher.py --dry-run          # Print matches without lighting

Requires:
    pip install winsdk
    Windows 11 22H2+ with package identity (run Register-AmbientLighting.ps1 first)
"""

import os
import sys
import json
import time
import math
import asyncio
import argparse
import subprocess
import threading
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Rules engine
# ---------------------------------------------------------------------------

RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules', 'rules.json')


def load_rules(path=None):
    """Load rules from JSON file."""
    path = path or RULES_PATH
    with open(path, 'r') as f:
        data = json.load(f)
    return data


def save_rules(data, path=None):
    """Save rules to JSON file."""
    path = path or RULES_PATH
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def match_rule(rule, app_name, title, body):
    """Check if a notification matches a rule's trigger."""
    if not rule.get('enabled', True):
        return False

    trigger = rule.get('trigger', {})

    if trigger.get('type') != 'notification':
        return False

    # App name filter (case-insensitive substring)
    rule_app = trigger.get('app_name')
    if rule_app and rule_app.lower() not in (app_name or '').lower():
        return False

    # Title keyword filter
    title_kw = trigger.get('title_contains')
    if title_kw and title_kw.lower() not in (title or '').lower():
        return False

    # Body keyword filter
    body_kw = trigger.get('body_contains')
    if body_kw and body_kw.lower() not in (body or '').lower():
        return False

    return True


def find_matching_rules(rules_data, app_name, title, body):
    """Return all enabled rules that match a notification."""
    return [r for r in rules_data.get('rules', []) if match_rule(r, app_name, title, body)]


# ---------------------------------------------------------------------------
# MCP server connection (reuses the same pattern as effect scripts)
# ---------------------------------------------------------------------------

class LightingClient:
    """Communicates with the Dynamic Lighting MCP server via JSON-RPC."""

    def __init__(self):
        exe = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'src', 'DynamicLightingMcp', 'bin', 'Debug',
            'net9.0-windows10.0.26100.0', 'DynamicLightingMcp.exe'
        )
        self.proc = subprocess.Popen(
            [exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0
        )
        threading.Thread(
            target=lambda: [self.proc.stderr.readline() for _ in iter(int, 1)],
            daemon=True
        ).start()
        self._id = 0
        self._handshake()

    def _send(self, obj):
        self.proc.stdin.write((json.dumps(obj) + '\n').encode())
        self.proc.stdin.flush()

    def _recv(self):
        return json.loads(self.proc.stdout.readline())

    def _handshake(self):
        self._send({
            'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
            'params': {
                'protocolVersion': '2024-11-05', 'capabilities': {},
                'clientInfo': {'name': 'alert-watcher', 'version': '1.0'}
            }
        })
        self._recv()
        self._send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        time.sleep(3)

    def call_tool(self, name, arguments):
        self._id += 1
        self._send({
            'jsonrpc': '2.0', 'id': self._id,
            'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments}
        })
        return self._recv()

    def set_solid_color(self, color):
        return self.call_tool('set_solid_color', {'color': color})

    def create_effect(self, **kwargs):
        return self.call_tool('create_lighting_effect', kwargs)

    def stop_effect(self):
        return self.call_tool('stop_lighting_effect', {})

    def shutdown(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Alert actions — what happens when a rule fires
# ---------------------------------------------------------------------------

def execute_action(client, action, dry_run=False):
    """Execute a lighting action from a matched rule."""
    action_type = action.get('type', 'flash')
    color = action.get('color', '#FF0000')
    duration = action.get('duration_sec', 3)
    pattern = action.get('pattern')

    if dry_run:
        print(f"  [DRY RUN] Would execute: {action_type} {color} for {duration}s")
        return

    if action_type == 'flash':
        # Quick flash: set color → wait → stop
        client.set_solid_color(color)
        time.sleep(duration)
        client.stop_effect()

    elif action_type == 'pulse':
        # Gentle pulse: breathe effect for duration then stop
        client.create_effect(
            description=f"pulse {color}",
            pattern='breathe',
            base_color=color,
            speed=0.8
        )
        time.sleep(duration)
        client.stop_effect()

    elif action_type == 'solid':
        # Set and hold (no auto-revert)
        client.set_solid_color(color)
        if duration > 0:
            time.sleep(duration)
            client.stop_effect()

    elif action_type == 'effect':
        # Run a named pattern
        if pattern:
            client.create_effect(pattern=pattern, base_color=color)
            time.sleep(duration)
            client.stop_effect()
        else:
            client.set_solid_color(color)
            time.sleep(duration)
            client.stop_effect()


# ---------------------------------------------------------------------------
# Windows notification listener (WinRT)
# ---------------------------------------------------------------------------

def start_notification_listener(rules_path, dry_run=False):
    """Start monitoring Windows notifications using UserNotificationListener."""
    try:
        from winsdk.windows.ui.notifications.management import UserNotificationListener
        from winsdk.windows.ui.notifications import NotificationKinds
    except ImportError:
        print("ERROR: 'winsdk' package not installed. Run: pip install winsdk")
        sys.exit(1)

    print("=== Alert Watcher ===")
    print(f"Rules: {rules_path or RULES_PATH}")
    print(f"Dry run: {dry_run}")
    print()

    # Load rules
    rules_data = load_rules(rules_path)
    enabled_count = sum(1 for r in rules_data['rules'] if r.get('enabled', True))
    print(f"Loaded {len(rules_data['rules'])} rules ({enabled_count} enabled)")
    for r in rules_data['rules']:
        status = "✅" if r.get('enabled', True) else "⏸️"
        print(f"  {status} {r['id']}: {r['name']}")
    print()

    # Connect to lighting server (unless dry run)
    client = None
    if not dry_run:
        print("Connecting to Dynamic Lighting MCP server...")
        client = LightingClient()
        print("Connected!\n")

    async def _run():
        listener = UserNotificationListener.current
        access = await listener.request_access_async()
        # UserNotificationListenerAccessStatus: 0=Allowed, 1=Denied, 2=Unspecified
        if access != 0:
            print(f"ERROR: Notification access denied (status={access})")
            print("Go to Settings → Privacy & security → Notifications and grant notification access.")
            sys.exit(1)

        print("Listening for notifications... (Ctrl+C to stop)\n")
        sys.stdout.flush()

        seen_ids = set()
        cooldown_until = 0
        cooldown_sec = rules_data.get('settings', {}).get('cooldown_sec', 5)

        while True:
            # Re-read rules each cycle so edits take effect live
            try:
                current_rules = load_rules(rules_path)
            except Exception:
                current_rules = rules_data

            notifications = await listener.get_notifications_async(NotificationKinds.TOAST)

            for notif in notifications:
                nid = notif.id
                if nid in seen_ids:
                    continue
                seen_ids.add(nid)

                # Extract notification details
                try:
                    app_info = notif.app_info
                    app_name = app_info.display_info.display_name if app_info else "Unknown"
                except Exception:
                    app_name = "Unknown"

                try:
                    toast_notif = notif.notification
                    visual = toast_notif.visual
                    bindings = visual.bindings
                    title = ""
                    body = ""
                    if bindings and bindings.size > 0:
                        binding = bindings.get_at(0)
                        texts = binding.get_text_elements()
                        text_list = []
                        for i in range(texts.size):
                            t = texts.get_at(i)
                            text_list.append(t.text if hasattr(t, 'text') else str(t))
                        title = text_list[0] if len(text_list) > 0 else ""
                        body = text_list[1] if len(text_list) > 1 else ""
                except Exception:
                    title = ""
                    body = ""

                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] Notification from: {app_name}")
                if title:
                    print(f"  Title: {title}")
                if body:
                    print(f"  Body: {body[:80]}{'...' if len(body) > 80 else ''}")

                # Check cooldown
                now = time.time()
                if now < cooldown_until:
                    print(f"  ⏳ Cooldown active, skipping")
                    continue

                # Find matching rules
                matches = find_matching_rules(current_rules, app_name, title, body)
                if matches:
                    for rule in matches:
                        print(f"  🔔 Rule matched: {rule['name']}")
                        execute_action(client, rule['action'], dry_run)
                    cooldown_until = now + cooldown_sec
                else:
                    print(f"  (no matching rules)")
                print()
                sys.stdout.flush()

            # Trim seen_ids to prevent unbounded growth
            if len(seen_ids) > 10000:
                seen_ids = set(list(seen_ids)[-5000:])

            await asyncio.sleep(1)

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\nStopping alert watcher...")
        if client:
            client.stop_effect()
            client.shutdown()
        print("Stopped.")


# ---------------------------------------------------------------------------
# Polling fallback (no WinRT required — uses PowerShell to read Action Center)
# ---------------------------------------------------------------------------

def start_polling_listener(rules_path, dry_run=False):
    """Fallback listener that polls for notifications via PowerShell.
    Less efficient but works without winsdk package."""

    print("=== Alert Watcher (Polling Mode) ===")
    print("Using PowerShell polling fallback (install 'winsdk' for native mode)")
    print(f"Rules: {rules_path or RULES_PATH}")
    print()

    rules_data = load_rules(rules_path)
    enabled_count = sum(1 for r in rules_data['rules'] if r.get('enabled', True))
    print(f"Loaded {len(rules_data['rules'])} rules ({enabled_count} enabled)")
    print()

    client = None
    if not dry_run:
        print("Connecting to Dynamic Lighting MCP server...")
        client = LightingClient()
        print("Connected!\n")

    print("Listening for notifications via polling... (Ctrl+C to stop)\n")

    # PowerShell command to get recent notifications
    ps_cmd = '''
    [Windows.UI.Notifications.Management.UserNotificationListener,Windows.UI.Notifications.Management,ContentType=WindowsRuntime] | Out-Null
    $listener = [Windows.UI.Notifications.Management.UserNotificationListener]::Current
    $notifications = $listener.GetNotificationsAsync([Windows.UI.Notifications.NotificationKinds]::Toast).GetAwaiter().GetResult()
    foreach ($n in $notifications) {
        $app = try { $n.AppInfo.DisplayInfo.DisplayName } catch { "Unknown" }
        Write-Output "$($n.Id)|$app"
    }
    '''

    seen_ids = set()
    cooldown_until = 0
    cooldown_sec = rules_data.get('settings', {}).get('cooldown_sec', 5)

    try:
        while True:
            try:
                rules_data = load_rules(rules_path)
            except Exception:
                pass

            try:
                result = subprocess.run(
                    ['powershell', '-NoProfile', '-Command', ps_cmd],
                    capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.strip().split('\n'):
                    if '|' not in line:
                        continue
                    nid, app_name = line.split('|', 1)
                    if nid in seen_ids:
                        continue
                    seen_ids.add(nid)

                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] Notification from: {app_name}")

                    now = time.time()
                    if now < cooldown_until:
                        print(f"  ⏳ Cooldown active, skipping")
                        continue

                    matches = find_matching_rules(rules_data, app_name, "", "")
                    if matches:
                        for rule in matches:
                            print(f"  🔔 Rule matched: {rule['name']}")
                            execute_action(client, rule['action'], dry_run)
                        cooldown_until = now + cooldown_sec
                    else:
                        print(f"  (no matching rules)")
                    print()
            except Exception as e:
                print(f"  Poll error: {e}")

            if len(seen_ids) > 10000:
                seen_ids = set(list(seen_ids)[-5000:])

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nStopping alert watcher...")
        if client:
            client.stop_effect()
            client.shutdown()
        print("Stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Alert Watcher — Lighting rules triggered by Windows notifications')
    parser.add_argument('--rules', type=str, help='Path to rules JSON file')
    parser.add_argument('--dry-run', action='store_true', help='Print matches without activating lighting')
    parser.add_argument('--polling', action='store_true', help='Use PowerShell polling instead of WinRT')

    # Rule management subcommands
    sub = parser.add_subparsers(dest='command')

    add_cmd = sub.add_parser('add', help='Add a new rule')
    add_cmd.add_argument('name', help='Rule name')
    add_cmd.add_argument('--app', required=True, help='App name to match (e.g., "Microsoft Teams")')
    add_cmd.add_argument('--title', help='Title keyword to match')
    add_cmd.add_argument('--body', help='Body keyword to match')
    add_cmd.add_argument('--action', default='flash', choices=['flash', 'pulse', 'solid', 'effect'], help='Lighting action')
    add_cmd.add_argument('--color', default='#FF0000', help='Color hex code')
    add_cmd.add_argument('--duration', type=int, default=3, help='Duration in seconds')
    add_cmd.add_argument('--pattern', help='Effect pattern (for action=effect)')

    list_cmd = sub.add_parser('list', help='List all rules')

    rm_cmd = sub.add_parser('remove', help='Remove a rule')
    rm_cmd.add_argument('rule_id', help='Rule ID to remove')

    enable_cmd = sub.add_parser('enable', help='Enable a rule')
    enable_cmd.add_argument('rule_id', help='Rule ID')

    disable_cmd = sub.add_parser('disable', help='Disable a rule')
    disable_cmd.add_argument('rule_id', help='Rule ID')

    test_cmd = sub.add_parser('test', help='Simulate a notification to test a rule')
    test_cmd.add_argument('rule_id', help='Rule ID to test')

    args = parser.parse_args()

    rules_path = args.rules or RULES_PATH

    if args.command == 'add':
        data = load_rules(rules_path)
        rule_id = args.name.lower().replace(' ', '-')
        new_rule = {
            'id': rule_id,
            'name': args.name,
            'enabled': True,
            'trigger': {
                'type': 'notification',
                'app_name': args.app,
                'title_contains': args.title,
                'body_contains': args.body
            },
            'action': {
                'type': args.action,
                'color': args.color,
                'duration_sec': args.duration,
                'pattern': args.pattern
            }
        }
        data['rules'].append(new_rule)
        save_rules(data, rules_path)
        print(f"✅ Added rule: {args.name} (id: {rule_id})")

    elif args.command == 'list':
        data = load_rules(rules_path)
        if not data['rules']:
            print("No rules defined. Use 'add' to create one.")
            return
        print(f"{'ID':<30} {'Name':<30} {'App':<20} {'Action':<10} {'Enabled'}")
        print('-' * 120)
        for r in data['rules']:
            app = r['trigger'].get('app_name', '*')
            action = r['action']['type']
            enabled = '✅' if r.get('enabled', True) else '⏸️'
            print(f"{r['id']:<30} {r['name']:<30} {app:<20} {action:<10} {enabled}")

    elif args.command == 'remove':
        data = load_rules(rules_path)
        before = len(data['rules'])
        data['rules'] = [r for r in data['rules'] if r['id'] != args.rule_id]
        if len(data['rules']) < before:
            save_rules(data, rules_path)
            print(f"✅ Removed rule: {args.rule_id}")
        else:
            print(f"❌ Rule not found: {args.rule_id}")

    elif args.command == 'enable':
        data = load_rules(rules_path)
        for r in data['rules']:
            if r['id'] == args.rule_id:
                r['enabled'] = True
                save_rules(data, rules_path)
                print(f"✅ Enabled: {r['name']}")
                return
        print(f"❌ Rule not found: {args.rule_id}")

    elif args.command == 'disable':
        data = load_rules(rules_path)
        for r in data['rules']:
            if r['id'] == args.rule_id:
                r['enabled'] = False
                save_rules(data, rules_path)
                print(f"⏸️ Disabled: {r['name']}")
                return
        print(f"❌ Rule not found: {args.rule_id}")

    elif args.command == 'test':
        data = load_rules(rules_path)
        rule = next((r for r in data['rules'] if r['id'] == args.rule_id), None)
        if not rule:
            print(f"❌ Rule not found: {args.rule_id}")
            return
        print(f"🧪 Testing rule: {rule['name']}")
        print(f"   Action: {rule['action']['type']} {rule['action'].get('color', '')} for {rule['action'].get('duration_sec', 3)}s")
        print(f"   Connecting to Dynamic Lighting MCP server...")
        client = LightingClient()
        print(f"   Connected! Firing action now...")
        execute_action(client, rule['action'], dry_run=False)
        print(f"   ✅ Action complete!")
        client.shutdown()

    else:
        # Default: start the watcher
        if args.polling:
            start_polling_listener(rules_path, args.dry_run)
        else:
            try:
                import winsdk
                start_notification_listener(rules_path, args.dry_run)
            except ImportError:
                print("'winsdk' not found, falling back to polling mode...")
                start_polling_listener(rules_path, args.dry_run)


if __name__ == '__main__':
    main()
