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
# Lighting driver connection (line protocol over stdio)
# ---------------------------------------------------------------------------

class LightingClient:
    """Communicates with the Dynamic Lighting Driver via line protocol."""

    def __init__(self):
        exe = os.path.join(os.environ.get('LOCALAPPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Local')), 'DynamicLightingDriver', 'DynamicLightingDriver.exe')
        self.proc = subprocess.Popen(
            [exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0
        )
        threading.Thread(
            target=lambda: [self.proc.stderr.readline() for _ in iter(int, 1)],
            daemon=True
        ).start()
        self._wait_ready()

    def _send(self, cmd):
        self.proc.stdin.write((cmd + '\n').encode())
        self.proc.stdin.flush()

    def _recv(self):
        return self.proc.stdout.readline().decode().strip()

    def _wait_ready(self):
        ready = self._recv()
        assert ready == 'READY', f'Driver not ready: {ready}'

    def set_solid_color(self, color):
        self._send(f'SET_ALL {color}')
        return self._recv()

    def create_effect(self, **kwargs):
        pattern = kwargs.pop('pattern', kwargs.pop('description', 'solid'))
        parts = [f'CREATE_EFFECT {pattern}']
        for k, v in kwargs.items():
            parts.append(f'{k}={v}')
        self._send(' '.join(parts))
        return self._recv()

    def stop_effect(self):
        self._send('STOP_EFFECT')
        return self._recv()

    def shutdown(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Alert actions — what happens when a rule fires
# ---------------------------------------------------------------------------

PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules', '.pause')


def _pause_effects(color, duration):
    """Signal running effects to flash the given color, then resume."""
    try:
        with open(PAUSE_FILE, 'w') as f:
            f.write(f'{color}|{duration}')
    except Exception:
        pass


def _wait_for_resume(duration):
    """Wait for the effect to finish the flash (pause file gets deleted)."""
    deadline = time.time() + duration + 2  # extra buffer
    while os.path.exists(PAUSE_FILE) and time.time() < deadline:
        time.sleep(0.2)


def execute_action(client, action, dry_run=False):
    """Execute a lighting action from a matched rule."""
    action_type = action.get('type', 'flash')
    color = action.get('color', '#FF0000')
    duration = action.get('duration_sec', 3)
    pattern = action.get('pattern')

    if dry_run:
        print(f"  [DRY RUN] Would execute: {action_type} {color} for {duration}s")
        return

    # Signal the running effect to handle the flash
    _pause_effects(color, duration)
    _wait_for_resume(duration)


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
        print("Connecting to Dynamic Lighting driver...")
        client = LightingClient()
        print("Connected!\n")

    async def _run():
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
# Polling fallback using Python winsdk (async polling loop)
# ---------------------------------------------------------------------------

def start_polling_listener(rules_path, dry_run=False):
    """Polling listener that uses Python winsdk to check for new notifications."""
    try:
        from winsdk.windows.ui.notifications.management import UserNotificationListener
        from winsdk.windows.ui.notifications import NotificationKinds
    except ImportError:
        print("ERROR: 'winsdk' package not installed. Run: pip install winsdk")
        sys.exit(1)

    print("=== Alert Watcher (Polling Mode) ===")
    print(f"Rules: {rules_path or RULES_PATH}")
    print(f"Dry run: {dry_run}")
    print()

    rules_data = load_rules(rules_path)
    enabled_count = sum(1 for r in rules_data['rules'] if r.get('enabled', True))
    print(f"Loaded {len(rules_data['rules'])} rules ({enabled_count} enabled)")
    for r in rules_data['rules']:
        status = "✅" if r.get('enabled', True) else "⏸️"
        print(f"  {status} {r['id']}: {r['name']}")
    print()

    client = None
    if not dry_run:
        print("Connecting to Dynamic Lighting driver...")
        client = LightingClient()
        print("Connected!\n")

    async def _poll():
        listener = UserNotificationListener.current
        access = await listener.request_access_async()
        if access != 0:
            print(f"ERROR: Notification access denied (status={access})")
            print("Notification listener requires package identity or notification access.")
            print("Falling back to file-based trigger mode.")
            print(f"To test manually, run: python alert-watcher.py test <rule_id>")
            print()
            await _file_trigger_loop(rules_path, client, dry_run)
            return

        print("Notification access granted! Polling for new notifications...\n")
        sys.stdout.flush()

        seen_ids = set()
        cooldown_until = 0
        cooldown_sec = rules_data.get('settings', {}).get('cooldown_sec', 5)

        # Seed seen_ids with existing notifications so we only fire on NEW ones
        try:
            existing = await listener.get_notifications_async(NotificationKinds.TOAST)
            for notif in existing:
                seen_ids.add(notif.id)
            print(f"Indexed {len(seen_ids)} existing notifications (will only fire on new ones)\n")
        except Exception:
            pass

        while True:
            try:
                current_rules = load_rules(rules_path)
            except Exception:
                current_rules = rules_data

            try:
                notifications = await listener.get_notifications_async(NotificationKinds.TOAST)
                for notif in notifications:
                    nid = notif.id
                    if nid in seen_ids:
                        continue
                    seen_ids.add(nid)

                    try:
                        app_info = notif.app_info
                        app_name = app_info.display_info.display_name if app_info else "Unknown"
                    except Exception:
                        app_name = "Unknown"

                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] 🔔 New notification from: {app_name}")

                    now = time.time()
                    if now < cooldown_until:
                        print(f"  ⏳ Cooldown active, skipping")
                        continue

                    matches = find_matching_rules(current_rules, app_name, "", "")
                    if matches:
                        for rule in matches:
                            print(f"  💡 Rule matched: {rule['name']}")
                            execute_action(client, rule['action'], dry_run)
                        cooldown_until = now + cooldown_sec
                    else:
                        print(f"  (no matching rules)")
                    print()
                    sys.stdout.flush()
            except Exception as e:
                print(f"  Poll error: {e}")

            if len(seen_ids) > 10000:
                seen_ids = set(list(seen_ids)[-5000:])

            await asyncio.sleep(2)

    try:
        asyncio.run(_poll())
    except KeyboardInterrupt:
        print("\nStopping alert watcher...")
        if client:
            client.stop_effect()
            client.shutdown()
        print("Stopped.")


async def _file_trigger_loop(rules_path, client, dry_run):
    """Fallback: watch a trigger file for manual/external triggers."""
    trigger_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules')
    trigger_file = os.path.join(trigger_dir, '.trigger')
    print(f"File trigger mode: write app name to {trigger_file} to simulate a notification")
    print("Example: echo Microsoft Teams > rules\\.trigger\n")
    sys.stdout.flush()

    cooldown_until = 0

    while True:
        try:
            rules_data = load_rules(rules_path)
        except Exception:
            pass

        if os.path.exists(trigger_file):
            try:
                app_name = open(trigger_file).read().strip()
                os.remove(trigger_file)
                if app_name:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] 🔔 File trigger: {app_name}")

                    now = time.time()
                    cooldown_sec = rules_data.get('settings', {}).get('cooldown_sec', 5)
                    if now < cooldown_until:
                        print(f"  ⏳ Cooldown active, skipping")
                    else:
                        matches = find_matching_rules(rules_data, app_name, "", "")
                        if matches:
                            for rule in matches:
                                print(f"  💡 Rule matched: {rule['name']}")
                                execute_action(client, rule['action'], dry_run)
                            cooldown_until = now + cooldown_sec
                        else:
                            print(f"  (no matching rules)")
                    print()
                    sys.stdout.flush()
            except Exception as e:
                print(f"  Trigger error: {e}")

        await asyncio.sleep(1)


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
        print(f"   Connecting to Dynamic Lighting driver...")
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
