"""
Etsy API v3 OAuth 2.0 + PKCE authentication.

Adapted from devonjhills/etsy-digital-mockup-tools (MIT license),
src/services/etsy/auth.py. Etsy's current v3 API requires the app keystring
and shared secret, separated by a colon, in the x-api-key header.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import ssl
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PKCE:
    @staticmethod
    def generate_code_verifier(length: int = 128) -> str:
        return secrets.token_urlsafe(length)

    @staticmethod
    def get_code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")


class CallbackHandler(BaseHTTPRequestHandler):
    """Local HTTP handler that captures Etsy's OAuth redirect."""

    code: Optional[str] = None
    expected_state: Optional[str] = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        returned_state = params.get("state", [None])[0]
        if returned_state != CallbackHandler.expected_state:
            logger.error("OAuth callback state did not match the request state.")
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Authentication failed</h1><p>OAuth state mismatch.</p></body></html>")
        elif "code" in params:
            CallbackHandler.code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authentication successful!</h1>"
                b"<p>You can close this window and return to the terminal.</p></body></html>"
            )
        elif parsed.path == "/oauth/redirect":
            logger.error("Redirect received but no code in parameters: %s", params)
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authentication failed!</h1>"
                b"<p>No authorization code received.</p></body></html>"
            )
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Waiting for Etsy authentication...</h1></body></html>"
            )

    def log_message(self, format_str, *args):
        logger.debug("HTTP callback server: %s", format_str % args)


class EtsyAuth:
    """Handles the OAuth 2.0 + PKCE flow and token lifecycle for Etsy API v3."""

    TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
    AUTHORIZE_URL = "https://www.etsy.com/oauth/connect"
    SCOPES = ("listings_w", "listings_r", "listings_d", "shops_r")

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        redirect_uri: str = "http://localhost:3003/oauth/redirect",
        token_file: str = "etsy_token.json",
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.redirect_uri = redirect_uri
        self.token_file = token_file

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiry: float = 0

        self.code_verifier = PKCE.generate_code_verifier()
        self.code_challenge = PKCE.get_code_challenge(self.code_verifier)
        self.state = secrets.token_hex(8)
        self.scope = " ".join(self.SCOPES)

        self._load_token()

    # -- token persistence -------------------------------------------------

    def _load_token(self) -> bool:
        if not os.path.exists(self.token_file):
            return False
        try:
            with open(self.token_file, "r") as f:
                data = json.load(f)
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.token_expiry = data.get("expiry", 0)
            if self.token_expiry < time.time():
                logger.info("Stored token expired, refreshing...")
                return self.refresh_access_token()
            return True
        except Exception as e:
            logger.error("Error loading token: %s", e)
            return False

    def _save_token(self) -> None:
        token_path = os.path.abspath(self.token_file)
        token_dir = os.path.dirname(token_path)
        if token_dir and not os.path.exists(token_dir):
            os.makedirs(token_dir)
        with open(token_path, "w") as f:
            json.dump(
                {
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "expiry": self.token_expiry,
                },
                f,
            )
        logger.info("Token saved to %s", token_path)

    # -- OAuth flow ----------------------------------------------------------

    def get_oauth_url(self) -> str:
        params = {
            "response_type": "code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "scope": self.scope,
            "state": self.state,
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def start_oauth_flow(self, timeout: int = 180) -> bool:
        """Open the browser, run a local server to catch the redirect, and
        exchange the resulting code for tokens. Returns True on success."""
        CallbackHandler.code = None
        CallbackHandler.expected_state = self.state
        oauth_url = self.get_oauth_url()

        try:
            port = int(urllib.parse.urlparse(self.redirect_uri).port or 3003)
        except Exception:
            port = 3003

        try:
            httpd = HTTPServer(("", port), CallbackHandler)
        except OSError as e:
            logger.error(
                "Could not bind localhost:%s -- close whatever is using that "
                "port (e.g. a previous stuck run) and retry. (%s)",
                port,
                e,
            )
            return False

        if urllib.parse.urlparse(self.redirect_uri).scheme == "https":
            cert_path, key_path = self._ensure_localhost_certificate()
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

        print(f"\nOpening your browser to authorize EverframeDigital with Etsy...")
        print(f"If it doesn't open automatically, visit:\n  {oauth_url}\n")
        webbrowser.open(oauth_url)

        result = {"got_code": False}

        def serve():
            start = time.time()
            while time.time() - start < timeout:
                httpd.timeout = 1
                httpd.handle_request()
                if CallbackHandler.code:
                    result["got_code"] = True
                    return

        t = threading.Thread(target=serve, daemon=True)
        t.start()
        t.join(timeout=timeout + 2)

        if not CallbackHandler.code:
            logger.error("No authorization code received within %ss timeout.", timeout)
            return False

        return self.exchange_code(CallbackHandler.code)

    @staticmethod
    def _ensure_localhost_certificate() -> tuple[str, str]:
        """Create a short-lived self-signed localhost certificate for OAuth."""
        from datetime import datetime, timedelta, timezone
        from ipaddress import ip_address

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        cert_dir = os.path.join(tempfile.gettempdir(), "everframe-etsy-oauth")
        os.makedirs(cert_dir, exist_ok=True)
        cert_path = os.path.join(cert_dir, "localhost-cert.pem")
        key_path = os.path.join(cert_dir, "localhost-key.pem")
        if os.path.exists(cert_path) and os.path.exists(key_path):
            return cert_path, key_path

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.now(timezone.utc)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=7))
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.DNSName("localhost"), x509.IPAddress(ip_address("127.0.0.1"))]
                ),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        with open(key_path, "wb") as file:
            file.write(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption(),
                )
            )
        with open(cert_path, "wb") as file:
            file.write(cert.public_bytes(serialization.Encoding.PEM))
        return cert_path, key_path

    def exchange_code(self, code: str) -> bool:
        import requests

        data = {
            "grant_type": "authorization_code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "code": code,
            "code_verifier": self.code_verifier,
        }
        resp = requests.post(self.TOKEN_URL, data=data)
        if resp.status_code != 200:
            logger.error("Error exchanging code: %s %s", resp.status_code, resp.text)
            return False

        token_data = resp.json()
        self.access_token = token_data.get("access_token")
        self.refresh_token = token_data.get("refresh_token")
        self.token_expiry = time.time() + token_data.get("expires_in", 3600)
        self._save_token()
        logger.info("Successfully authenticated with Etsy.")
        return True

    def refresh_access_token(self) -> bool:
        import requests

        if not self.refresh_token:
            logger.error("No refresh token available -- run the OAuth flow again.")
            return False

        data = {
            "grant_type": "refresh_token",
            "client_id": self.api_key,
            "refresh_token": self.refresh_token,
        }
        resp = requests.post(self.TOKEN_URL, data=data)
        if resp.status_code != 200:
            logger.error("Error refreshing token: %s %s", resp.status_code, resp.text)
            return False

        token_data = resp.json()
        self.access_token = token_data.get("access_token")
        self.refresh_token = token_data.get("refresh_token")
        self.token_expiry = time.time() + token_data.get("expires_in", 3600)
        self._save_token()
        return True

    def get_headers(self) -> Dict[str, str]:
        if not self.access_token:
            logger.error("No access token available.")
            return {}
        if self.token_expiry < time.time():
            logger.info("Access token expired, refreshing...")
            if not self.refresh_access_token():
                return {}
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "x-api-key": f"{self.api_key}:{self.api_secret}",
        }

    def is_authenticated(self) -> bool:
        return self.access_token is not None and self.token_expiry > time.time()
