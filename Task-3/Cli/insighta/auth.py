import hashlib
import http.server
import os
import secrets
import threading
import webbrowser
from urllib.parse import parse_qs, urlparse

import httpx

from insighta.store import save_tokens, clear_tokens

BASE_URL = os.environ.get("INSIGHTA_API_URL", "http://localhost:8000")
CALLBACK_PORT = 8788


def _generate_code_verifier() -> str:
    return secrets.token_urlsafe(32)


def _generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    import base64
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _generate_state() -> str:
    return secrets.token_hex(16)


def login() -> dict:
    code_verifier = _generate_code_verifier()
    code_challenge = _generate_code_challenge(code_verifier)
    state = _generate_state()

    auth_url = (
        f"{BASE_URL}/auth/github"
        f"?state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    result = {"user": None, "error": None}
    server_done = threading.Event()

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # suppress default logs

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return

            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            returned_state = params.get("state", [None])[0]

            if not code or returned_state != state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid callback. Please try again.")
                result["error"] = "Invalid state or missing code"
                server_done.set()
                return

            # Exchange code for tokens
            token_res = httpx.get(
                f"{BASE_URL}/auth/github/callback",
                params={
                    "code": code,
                    "state": state,
                    "code_verifier": code_verifier,
                },
            )

            data = token_res.json()

            if token_res.status_code != 200 or not data.get("access_token"):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Login failed. Please try again.")
                result["error"] = data.get("message", "Login failed")
                server_done.set()
                return

            save_tokens(data["access_token"], data["refresh_token"])
            result["user"] = data["user"]

            html = f"""
            <html>
            <body style="font-family:sans-serif;text-align:center;padding:60px">
                <h2>&#10003; Login successful!</h2>
                <p>Welcome, <strong>{data['user']['username']}</strong>
                ({data['user']['role']})</p>
                <p>You can close this tab and return to the terminal.</p>
            </body>
            </html>
            """.encode()

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html)
            server_done.set()

    server = http.server.HTTPServer(("localhost", CALLBACK_PORT), CallbackHandler)

    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    print(f"\nOpening GitHub login in your browser...")
    print(f"If it doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Wait up to 3 minutes
    server_done.wait(timeout=180)
    server.shutdown()

    if result["error"]:
        raise Exception(result["error"])
    if not result["user"]:
        raise Exception("Login timed out. Please try again.")

    return result["user"]


def logout():
    clear_tokens()