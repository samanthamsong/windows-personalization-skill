"""
Spotify OAuth 2.0 PKCE authentication.

Usage:
    python auth.py          # Run interactive auth flow
    python auth.py status   # Check if authenticated

Stores refresh token in .spotify-token (gitignored).
Requires SPOTIPY_CLIENT_ID env var or --client-id flag.
"""

import os
import sys
import json
import spotipy
from spotipy.oauth2 import SpotifyPKCE

TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.spotify-token')
REDIRECT_URI = 'http://127.0.0.1:8888/callback'
SCOPES = 'user-read-currently-playing user-read-playback-state'
DEFAULT_CLIENT_ID = '231a510c2e5b49d3913b12f461578064'


def get_client_id():
    """Get Spotify Client ID from env, config file, or built-in default."""
    client_id = os.environ.get('SPOTIPY_CLIENT_ID')
    if client_id:
        return client_id

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.spotify-config')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
            client_id = config.get('client_id')
        if client_id:
            return client_id

    return DEFAULT_CLIENT_ID


def get_auth_manager(client_id=None):
    """Create a SpotifyPKCE auth manager."""
    if not client_id:
        client_id = get_client_id()
    if not client_id:
        print("ERROR: No Client ID provided.")
        sys.exit(1)
    return SpotifyPKCE(
        client_id=client_id,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        cache_path=TOKEN_PATH,
    )


def get_spotify(client_id=None):
    """Get an authenticated Spotify client. Triggers auth flow if needed."""
    auth_manager = get_auth_manager(client_id)
    return spotipy.Spotify(auth_manager=auth_manager)


def check_status():
    """Check if we have a valid cached token."""
    if not os.path.exists(TOKEN_PATH):
        print("❌ Not authenticated. Run: python auth.py")
        return False
    try:
        sp = get_spotify()
        user = sp.current_user()
        print(f"✅ Authenticated as: {user['display_name']} ({user['id']})")
        return True
    except Exception as e:
        print(f"❌ Token expired or invalid: {e}")
        print("Run: python auth.py")
        return False


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        check_status()
    else:
        print("🔗 Starting Spotify authentication...")
        sp = get_spotify()
        user = sp.current_user()
        print(f"✅ Authenticated as: {user['display_name']} ({user['id']})")
        print(f"Token cached at: {TOKEN_PATH}")
