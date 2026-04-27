"""Gmail OAuth 2.0 authentication module.

Provides OAuth 2.0 PKCE flow for desktop applications.
Security: PKCE, DPAPI-encrypted tokens, external client_secrets.json.
"""
from __future__ import annotations

import json
import pickle
import secrets
import hashlib
import base64
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, parse_qs, urlparse

from PySide6.QtCore import QObject, Signal, QTimer

from core.logging.logger import get_logger
from core.settings.storage_paths import get_app_data_dir
from core.windows.dpapi import save_encrypted, load_encrypted

logger = get_logger(__name__)

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.metadata",
]
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
REDIRECT_HOST = "127.0.0.1"
SERVER_TIMEOUT_SECONDS = 300


class GmailConfigError(Exception):
    pass


@dataclass
class GmailCredentials:
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime
    scope: str

    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at - timedelta(minutes=5)

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at.isoformat(),
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GmailCredentials":
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_type=data["token_type"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            scope=data["scope"],
        )


class GmailOAuthManager(QObject):
    auth_started = Signal()
    auth_completed = Signal(object)
    auth_failed = Signal(str)
    auth_revoked = Signal()

    _instance: Optional["GmailOAuthManager"] = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "GmailOAuthManager":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        token_path: Optional[Path] = None,
    ):
        super().__init__()
        self._credentials: Optional[GmailCredentials] = None
        self._client_id: Optional[str] = None
        self._client_secret: Optional[str] = None
        self._auth_server: Optional[HTTPServer] = None
        self._auth_thread: Optional[threading.Thread] = None
        self._pkce_verifier: Optional[str] = None
        self._state: Optional[str] = None
        self._redirect_uri: Optional[str] = None

        app_data = get_app_data_dir()

        # Resolve credentials path: bundled resource first, then app data override
        if credentials_path is not None:
            self._credentials_path = credentials_path
        else:
            bundled = Path(__file__).resolve().parents[2] / "resources" / "client_secrets.json"
            if bundled.exists():
                self._credentials_path = bundled
            else:
                self._credentials_path = app_data / "client_secrets.json"

        self._token_path = token_path or (app_data / "gmail_token.enc")
        self._legacy_token_path = app_data / "gmail_credentials.json"

        self._load_client_config()
        self._load_credentials()
        if self._credentials is None:
            self._migrate_legacy_token()

    def _load_client_config(self) -> None:
        path = Path(self._credentials_path)
        if not path.exists():
            logger.error("[GMAIL_OAUTH] client_secrets.json not found at %s", path)
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "installed" in data:
                data = data["installed"]
            elif "web" in data:
                data = data["web"]
            self._client_id = data.get("client_id")
            self._client_secret = data.get("client_secret")
            if not self._client_id:
                raise GmailConfigError("client_secrets.json missing 'client_id'")
            if not self._client_secret:
                logger.warning("[GMAIL_OAUTH] client_secret missing from JSON")
            logger.info("[GMAIL_OAUTH] Loaded client configuration (client_id=%s...)", self._client_id[:20] if self._client_id else "None")
        except Exception as exc:
            logger.error("[GMAIL_OAUTH] Failed to parse client_secrets.json: %s", exc)
            self._client_id = None

    def _migrate_legacy_token(self) -> None:
        if not self._legacy_token_path.exists():
            return
        try:
            with open(self._legacy_token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            creds = GmailCredentials.from_dict(data)
            self._save_credentials(creds)
            self._legacy_token_path.unlink()
            logger.info("[GMAIL_OAUTH] Migrated legacy token to encrypted storage")
        except Exception as exc:
            logger.warning("[GMAIL_OAUTH] Legacy token migration failed: %s", exc)

    def set_client_id(self, client_id: str) -> None:
        self._client_id = client_id

    @property
    def is_authenticated(self) -> bool:
        return self._credentials is not None

    @property
    def credentials(self) -> Optional[GmailCredentials]:
        if self._credentials is None:
            return None
        if self._credentials.is_expired():
            self._refresh_token()
        return self._credentials

    def clear_local_credentials(self) -> None:
        try:
            if self._token_path.exists():
                self._token_path.unlink()
        except Exception as exc:
            logger.warning("[GMAIL_OAUTH] Failed to delete token file: %s", exc)
        self._credentials = None
        self.auth_revoked.emit()
        logger.info("[GMAIL_OAUTH] Local credentials cleared")

    def _load_credentials(self) -> None:
        try:
            plaintext = load_encrypted(self._token_path)
            if plaintext is None:
                return
            data = pickle.loads(plaintext)
            self._credentials = GmailCredentials.from_dict(data)
            logger.info("[GMAIL_OAUTH] Loaded existing credentials")
        except Exception as exc:
            logger.warning("[GMAIL_OAUTH] Failed to load credentials: %s", exc)
            self._credentials = None

    def _save_credentials(self, creds: Optional[GmailCredentials] = None) -> None:
        target = creds or self._credentials
        if target is None:
            return
        try:
            plaintext = pickle.dumps(target.to_dict())
            save_encrypted(self._token_path, plaintext)
            logger.info("[GMAIL_OAUTH] Saved credentials")
        except Exception as exc:
            logger.error("[GMAIL_OAUTH] Failed to save credentials: %s", exc)

    def _generate_pkce_pair(self) -> tuple[str, str]:
        verifier = secrets.token_urlsafe(64)
        challenge_bytes = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(challenge_bytes).decode("ascii").rstrip("=")
        return verifier, challenge

    def start_auth_flow(self) -> bool:
        if not self._client_id:
            msg = "Gmail OAuth client ID not configured. Place client_secrets.json in app data directory."
            self.auth_failed.emit(msg)
            logger.error("[GMAIL_OAUTH] %s", msg)
            return False
        try:
            self._pkce_verifier, pkce_challenge = self._generate_pkce_pair()
            self._state = secrets.token_urlsafe(32)
            self._start_callback_server()
            params = {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "response_type": "code",
                "scope": " ".join(GMAIL_SCOPES),
                "state": self._state,
                "code_challenge": pkce_challenge,
                "code_challenge_method": "S256",
                "access_type": "offline",
                "prompt": "consent",
            }
            auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
            self.auth_started.emit()
            self._open_browser(auth_url)
            logger.info("[GMAIL_OAUTH] Auth flow started")
            return True
        except Exception as exc:
            logger.error("[GMAIL_OAUTH] Failed to start auth flow: %s", exc)
            self.auth_failed.emit(str(exc))
            return False

    def _open_browser(self, url: str) -> None:
        import webbrowser
        # new=1 opens a new browser window (not just a tab), which is
        # critical for OAuth flows where the user must interact with
        # the authorization page while the app stays visible.
        webbrowser.open(url, new=1)
        logger.debug("[GMAIL_OAUTH] Browser opened: %s", url)

    def _start_callback_server(self) -> None:
        """Start local HTTP server to receive OAuth callback."""
        manager = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path in ("/", "/callback"):
                    params = parse_qs(parsed.query)
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    if "code" in params and "state" in params:
                        code = params["code"][0]
                        state = params["state"][0]
                        if state == manager._state:
                            self.wfile.write(
                                b"<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                                b"<h1>Authorization Successful!</h1>"
                                b"<p>You can close this window and return to the application.</p>"
                                b"</body></html>"
                            )
                            # Schedule token exchange on UI thread
                            QTimer.singleShot(0, lambda: manager._exchange_code(code))
                        else:
                            self.wfile.write(
                                b"<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                                b"<h1>Authorization Failed</h1>"
                                b"<p>Invalid state parameter. Please try again.</p>"
                                b"</body></html>"
                            )
                            QTimer.singleShot(0, lambda: manager.auth_failed.emit("Invalid state parameter"))
                    else:
                        self.wfile.write(
                            b"<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                            b"<h1>Authorization Failed</h1>"
                            b"<p>Missing authorization code or state.</p>"
                            b"</body></html>"
                        )
                        if "error" in params:
                            error = params["error"][0]
                            error_desc = params.get("error_description", [""])[0]
                            full_error = f"OAuth error: {error}"
                            if error_desc:
                                full_error += f" — {error_desc}"
                            logger.error("[GMAIL_OAUTH] Callback received error: %s", full_error)
                            QTimer.singleShot(0, lambda err=full_error: manager.auth_failed.emit(err))
                else:
                    self.send_response(404)
                    self.end_headers()

        for port in range(8080, 8100):
            try:
                self._redirect_uri = f"http://{REDIRECT_HOST}:{port}"
                self._auth_server = HTTPServer((REDIRECT_HOST, port), CallbackHandler)
                self._auth_server.timeout = SERVER_TIMEOUT_SECONDS
                break
            except OSError:
                continue
        if self._auth_server is None:
            raise GmailConfigError("Could not find an available port for OAuth callback server")
        self._auth_thread = threading.Thread(target=self._auth_server.serve_forever, daemon=True)
        self._auth_thread.start()
        logger.info("[GMAIL_OAUTH] Callback server started on %s", self._redirect_uri)

    def _stop_callback_server(self) -> None:
        if self._auth_server:
            try:
                self._auth_server.shutdown()
            except Exception as exc:
                logger.debug("[GMAIL_OAUTH] Server shutdown suppressed: %s", exc)
            self._auth_server = None
        self._auth_thread = None
        self._redirect_uri = None

    def _exchange_code(self, code: str) -> None:
        """Exchange authorization code for tokens.

        TODO(P2): When widget has access to app ThreadManager, submit this
        as an IO task to avoid blocking the UI thread during the POST.
        """
        try:
            import requests
            data = {
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "client_secret": self._client_secret or "",
                "code": code,
                "redirect_uri": self._redirect_uri,
                "code_verifier": self._pkce_verifier,
            }
            resp = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=30)
            resp.raise_for_status()
            token_data = resp.json()
            self._process_token_response(token_data)
        except Exception as exc:
            logger.error("[GMAIL_OAUTH] Token exchange failed: %s", exc)
            self.auth_failed.emit(str(exc))
        finally:
            self._stop_callback_server()

    def _process_token_response(self, token_data: dict) -> None:
        """Convert raw token response to GmailCredentials and save."""
        try:
            access_token = token_data["access_token"]
            refresh_token = token_data.get("refresh_token")
            if not refresh_token:
                logger.warning("[GMAIL_OAUTH] No refresh_token received; session will not persist")
            token_type = token_data.get("token_type", "Bearer")
            expires_in = token_data.get("expires_in", 3600)
            scope = token_data.get("scope", " ".join(GMAIL_SCOPES))
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            self._credentials = GmailCredentials(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=token_type,
                expires_at=expires_at,
                scope=scope,
            )
            self._save_credentials()
            self.auth_completed.emit(self._credentials)
            logger.info("[GMAIL_OAUTH] Authentication completed successfully")
        except KeyError as exc:
            logger.error("[GMAIL_OAUTH] Malformed token response: %s", exc)
            self.auth_failed.emit(f"Malformed token response: {exc}")

    def _refresh_token(self) -> None:
        """Refresh the access token using the refresh token."""
        if not self._credentials or not self._credentials.refresh_token:
            logger.warning("[GMAIL_OAUTH] Cannot refresh: no refresh token available")
            return
        try:
            import requests
            data = {
                "grant_type": "refresh_token",
                "client_id": self._client_id,
                "client_secret": self._client_secret or "",
                "refresh_token": self._credentials.refresh_token,
            }
            resp = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=30)
            resp.raise_for_status()
            token_data = resp.json()
            self._credentials.access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self._credentials.expires_at = datetime.now() + timedelta(seconds=expires_in)
            self._credentials.scope = token_data.get("scope", self._credentials.scope)
            self._save_credentials()
            logger.info("[GMAIL_OAUTH] Token refreshed successfully")
        except Exception as exc:
            logger.error("[GMAIL_OAUTH] Token refresh failed: %s", exc)
            # Clear credentials if refresh fails permanently
            self.clear_local_credentials()
            self.auth_failed.emit(str(exc))

    def revoke_credentials(self) -> bool:
        """Revoke credentials with Google and clear local storage."""
        if not self._credentials:
            return False
        try:
            import requests
            data = {"token": self._credentials.access_token}
            resp = requests.post(GOOGLE_REVOKE_URL, data=data, timeout=30)
            if resp.status_code != 200:
                logger.warning("[GMAIL_OAUTH] Revoke request returned %s", resp.status_code)
            else:
                logger.info("[GMAIL_OAUTH] Credentials revoked with Google")
        except Exception as exc:
            logger.warning("[GMAIL_OAUTH] Revoke request failed: %s", exc)
        self.clear_local_credentials()
        return True
