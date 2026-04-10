"""Automatic OAuth and token management.

Handles the full auth flow:
  1. Opens browser to consent page
  2. Runs a temporary local server to receive the callback
  3. Exchanges auth code for tokens
  4. Stores tokens securely in config/tokens/
  5. Refreshes tokens automatically when expired
"""

from __future__ import annotations

import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from src.core.config import CONFIG_DIR, ROOT_DIR
from src.core.logger import get_logger

log = get_logger(__name__)

TOKENS_DIR = CONFIG_DIR / "tokens"
CALLBACK_PORT = 8765
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/auth/callback"


def ensure_tokens_dir() -> Path:
    """Create tokens directory if it doesn't exist."""
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    # Add to .gitignore if not there
    gitignore = ROOT_DIR / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if "config/tokens/" not in content:
            with open(gitignore, "a") as f:
                f.write("\n# Auth tokens (sensitive)\nconfig/tokens/\n")
    return TOKENS_DIR


def run_oauth_flow(
    integration_name: str,
    client_id: str,
    client_secret: str,
    auth_uri: str,
    token_uri: str,
    scopes: list[str],
) -> dict | None:
    """Run the full OAuth 2.0 flow automatically.

    Opens browser → user consents → callback received → tokens stored.

    Returns the token dict or None if failed.
    """
    ensure_tokens_dir()

    state = secrets.token_urlsafe(32)

    # Build authorization URL
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{auth_uri}?{urlencode(params)}"

    print(f"\n  Opening browser for {integration_name} authorization...")
    print(f"  If the browser doesn't open, visit this URL:\n  {auth_url}\n")

    # Start callback server in a thread
    auth_code = {}
    server = _start_callback_server(auth_code, state)

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback (timeout 120 seconds)
    print("  Waiting for authorization (you have 2 minutes)...")
    start = time.time()
    while "code" not in auth_code and time.time() - start < 120:
        time.sleep(0.5)

    server.shutdown()

    if "code" not in auth_code:
        print("  [X] Authorization timed out.")
        return None

    if "error" in auth_code:
        print(f"  [X] Authorization failed: {auth_code['error']}")
        return None

    # Exchange code for tokens
    print("  Exchanging authorization code for tokens...")
    try:
        response = httpx.post(
            token_uri,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": auth_code["code"],
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        response.raise_for_status()
        tokens = response.json()
    except Exception as e:
        print(f"  [X] Token exchange failed: {e}")
        return None

    # Store tokens
    token_path = TOKENS_DIR / f"{integration_name}.json"
    tokens["_integration"] = integration_name
    tokens["_created_at"] = int(time.time())
    token_path.write_text(json.dumps(tokens, indent=2))

    print(f"  [OK] {integration_name} authorized successfully!")
    log.info("auth.oauth.success", integration=integration_name)
    return tokens


def run_bot_token_flow(integration_name: str, url: str, instructions: str) -> str | None:
    """For bot-token integrations (Telegram, Discord): open the setup page
    and prompt for the token.

    Returns the token or None.
    """
    print(f"\n  {instructions}")
    print(f"  Opening: {url}")
    webbrowser.open(url)

    token = input(f"\n  Paste your {integration_name} bot token here: ").strip()
    if not token:
        print("  Skipped.")
        return None

    # Store in tokens dir too
    ensure_tokens_dir()
    token_path = TOKENS_DIR / f"{integration_name}.json"
    token_path.write_text(json.dumps({
        "bot_token": token,
        "_integration": integration_name,
        "_created_at": int(time.time()),
    }, indent=2))

    print(f"  [OK] {integration_name} token saved!")
    return token


def get_stored_token(integration_name: str) -> dict | None:
    """Get stored tokens for an integration."""
    token_path = TOKENS_DIR / f"{integration_name}.json"
    if not token_path.exists():
        return None
    try:
        return json.loads(token_path.read_text())
    except Exception:
        return None


def has_valid_token(integration_name: str) -> bool:
    """Check if we have a stored token for this integration."""
    return get_stored_token(integration_name) is not None


def refresh_token(
    integration_name: str,
    client_id: str,
    client_secret: str,
    token_uri: str,
) -> dict | None:
    """Refresh an expired OAuth token."""
    tokens = get_stored_token(integration_name)
    if not tokens or "refresh_token" not in tokens:
        return None

    try:
        response = httpx.post(
            token_uri,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": tokens["refresh_token"],
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        response.raise_for_status()
        new_tokens = response.json()

        # Preserve refresh token if not returned
        if "refresh_token" not in new_tokens:
            new_tokens["refresh_token"] = tokens["refresh_token"]

        new_tokens["_integration"] = integration_name
        new_tokens["_created_at"] = int(time.time())

        token_path = TOKENS_DIR / f"{integration_name}.json"
        token_path.write_text(json.dumps(new_tokens, indent=2))

        log.info("auth.token.refreshed", integration=integration_name)
        return new_tokens
    except Exception as e:
        log.warning("auth.token.refresh_failed", integration=integration_name, error=str(e))
        return None


def revoke_token(integration_name: str) -> bool:
    """Remove stored tokens for an integration."""
    token_path = TOKENS_DIR / f"{integration_name}.json"
    if token_path.exists():
        token_path.unlink()
        log.info("auth.token.revoked", integration=integration_name)
        return True
    return False


# ─── Callback server ──────────────────────────────────────────────

def _start_callback_server(auth_code: dict, expected_state: str) -> HTTPServer:
    """Start a temporary HTTP server to receive the OAuth callback."""

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != "/auth/callback":
                self.send_response(404)
                self.end_headers()
                return

            params = parse_qs(parsed.query)

            # Verify state
            state = params.get("state", [None])[0]
            if state != expected_state:
                auth_code["error"] = "State mismatch - possible CSRF attack"
                self._respond("Authorization failed: state mismatch.")
                return

            if "error" in params:
                auth_code["error"] = params["error"][0]
                self._respond(f"Authorization failed: {params['error'][0]}")
                return

            code = params.get("code", [None])[0]
            if code:
                auth_code["code"] = code
                self._respond(
                    "Authorization successful! You can close this tab and "
                    "return to the terminal."
                )
            else:
                auth_code["error"] = "No authorization code received"
                self._respond("Authorization failed: no code received.")

        def _respond(self, message: str):
            self.send_response(200)
            self.send_headers = {"Content-Type": "text/html"}
            self.end_headers()
            html = f"""<!DOCTYPE html>
<html><head><title>AI Assistant Auth</title>
<style>
body {{ font-family: -apple-system, sans-serif; display: flex;
  justify-content: center; align-items: center; height: 100vh;
  margin: 0; background: #1a1a2e; color: #eee; }}
.card {{ text-align: center; padding: 2rem; background: #16213e;
  border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }}
</style></head>
<body><div class="card"><h2>{message}</h2></div></body></html>"""
            self.wfile.write(html.encode())

        def log_message(self, format, *args):
            pass  # Suppress server logs

    server = HTTPServer(("localhost", CALLBACK_PORT), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
