"""Gmail OAuth 2.0 authentication module.

Provides OAuth 2.0 PKCE flow for desktop applications.
Security: PKCE, DPAPI-encrypted tokens, external client_secrets.json.
"""
from __future__ import annotations

import pickle
import secrets
import hashlib
import base64
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, parse_qs, urlparse

from PySide6.QtCore import QObject, Signal, QCoreApplication

from core.logging.logger import get_logger
from core.resources.manager import ResourceManager
from core.threading.manager import ThreadManager
from core.windows.dpapi import save_encrypted

logger = get_logger(__name__)

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.metadata",
]
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
REDIRECT_HOST = "127.0.0.1"
SERVER_TIMEOUT_SECONDS = 300
SERVER_POLL_SECONDS = 1.0


class GmailConfigError(Exception):
    pass


@dataclass
class GmailCredentials:
    access_token: str
    refresh_token: Optional[str]
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


@dataclass
class _CallbackServerContext:
    server: HTTPServer
    generation: int
    task_id: str
    redirect_uri: str
    expected_state: str
    pkce_verifier: str
    stop_event: threading.Event = field(default_factory=threading.Event)
    finished_event: threading.Event = field(default_factory=threading.Event)
    _close_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _closed: bool = field(default=False, repr=False)

    def close_once(self) -> bool:
        """Close the listening socket exactly once across cancel/task races."""
        with self._close_lock:
            if self._closed:
                return False
            self._closed = True
        self.server.server_close()
        return True


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
        thread_manager: Optional[ThreadManager] = None,
    ):
        super().__init__()
        self._credentials: Optional[GmailCredentials] = None
        self._client_id: Optional[str] = None
        self._client_secret: Optional[str] = None
        self._auth_server: Optional[HTTPServer] = None
        self._auth_context: Optional[_CallbackServerContext] = None
        self._auth_server_task_id: Optional[str] = None
        self._auth_server_generation = 0
        self._auth_server_lock = threading.RLock()
        self._pkce_verifier: Optional[str] = None
        self._state: Optional[str] = None
        self._redirect_uri: Optional[str] = None
        self._thread_manager = thread_manager
        self._owns_thread_manager = False
        self._shutdown_hook_connected = False
        # Construction is deliberately filesystem-inert.  The GUI-owned
        # QObject receives one detached worker snapshot through GmailBackend.
        self._credentials_path = Path(credentials_path) if credentials_path is not None else None
        self._token_path = Path(token_path) if token_path is not None else None
        self._legacy_token_path: Optional[Path] = None
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def client_id(self) -> Optional[str]:
        return self._client_id

    def install_prepared_bootstrap(self, snapshot) -> None:
        """Commit a Qt-free bootstrap snapshot on the QObject's GUI thread."""

        from core.gmail.gmail_bootstrap import PreparedGmailBootstrap

        if not isinstance(snapshot, PreparedGmailBootstrap):
            raise TypeError("Expected PreparedGmailBootstrap")
        self._credentials_path = snapshot.oauth_credentials_path
        self._token_path = snapshot.oauth_token_path
        self._legacy_token_path = snapshot.oauth_legacy_token_path
        self.install_prepared_client_config(snapshot.oauth_client_config)
        prepared = snapshot.oauth_credentials
        self._credentials = (
            GmailCredentials(
                access_token=prepared.access_token,
                refresh_token=prepared.refresh_token,
                token_type=prepared.token_type,
                expires_at=prepared.expires_at,
                scope=prepared.scope,
            )
            if prepared is not None
            else None
        )
        self._initialized = True

    def install_prepared_client_config(self, config) -> None:
        """Commit worker-prepared OAuth client configuration."""

        from core.gmail.gmail_bootstrap import PreparedOAuthClientConfig

        if not isinstance(config, PreparedOAuthClientConfig):
            raise TypeError("Expected PreparedOAuthClientConfig")
        self._client_id = config.client_id
        self._client_secret = config.client_secret

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
        self.cancel_auth_flow()
        try:
            if self._token_path is not None and self._token_path.exists():
                self._token_path.unlink()
        except Exception as exc:
            logger.warning("[GMAIL_OAUTH] Failed to delete token file: %s", exc)
        self._credentials = None
        self.auth_revoked.emit()
        logger.info("[GMAIL_OAUTH] Local credentials cleared")

    def _save_credentials(self, creds: Optional[GmailCredentials] = None) -> None:
        target = creds or self._credentials
        if target is None or self._token_path is None:
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
            self._stop_callback_server()
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
        self._stop_callback_server()
        context: _CallbackServerContext

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
                        if state == context.expected_state:
                            self.wfile.write(
                                b"<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                                b"<h1>Authorization Successful!</h1>"
                                b"<p>You can close this window and return to the application.</p>"
                                b"</body></html>"
                            )
                            try:
                                manager._get_thread_manager().submit_io_task(
                                    manager._exchange_code,
                                    code,
                                    context.redirect_uri,
                                    context.pkce_verifier,
                                    task_id=f"gmail_oauth_exchange_{id(manager)}_{context.generation}",
                                )
                            except Exception as exc:
                                logger.error("[GMAIL_OAUTH] Token exchange submission failed: %s", exc)
                                ThreadManager.run_on_ui_thread(
                                    manager._emit_auth_failed_safe,
                                    "Could not start Gmail token exchange",
                                )
                        else:
                            self.wfile.write(
                                b"<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                                b"<h1>Authorization Failed</h1>"
                                b"<p>Invalid state parameter. Please try again.</p>"
                                b"</body></html>"
                            )
                            ThreadManager.run_on_ui_thread(manager._emit_auth_failed_safe, "Invalid state parameter")
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
                            ThreadManager.run_on_ui_thread(manager._emit_auth_failed_safe, full_error)
                        else:
                            ThreadManager.run_on_ui_thread(
                                manager._emit_auth_failed_safe,
                                "Missing authorization code or state",
                            )
                    context.stop_event.set()
                else:
                    self.send_response(404)
                    self.end_headers()

        callback_server: Optional[HTTPServer] = None
        redirect_uri: Optional[str] = None
        for port in range(8080, 8100):
            try:
                redirect_uri = f"http://{REDIRECT_HOST}:{port}"
                callback_server = HTTPServer((REDIRECT_HOST, port), CallbackHandler)
                break
            except OSError:
                continue
        if callback_server is None or redirect_uri is None:
            raise GmailConfigError("Could not find an available port for OAuth callback server")

        with self._auth_server_lock:
            self._auth_server_generation += 1
            generation = self._auth_server_generation
            task_id = f"gmail_oauth_callback_{id(self)}_{generation}"
            context = _CallbackServerContext(
                server=callback_server,
                generation=generation,
                task_id=task_id,
                redirect_uri=redirect_uri,
                expected_state=self._state or "",
                pkce_verifier=self._pkce_verifier or "",
            )
            self._auth_context = context
            self._auth_server = callback_server
            self._auth_server_task_id = task_id
            self._redirect_uri = redirect_uri

        try:
            thread_manager = self._get_thread_manager()
            self._ensure_shutdown_hook()
            thread_manager.submit_io_task(
                self._run_callback_server,
                context,
                task_id=task_id,
            )
        except Exception:
            self._finalize_callback_server(context)
            raise
        logger.info(
            "[GMAIL_OAUTH] Callback server started on %s task_id=%s",
            redirect_uri,
            task_id,
        )

    def _run_callback_server(self, context: _CallbackServerContext) -> None:
        """Serve one bounded OAuth flow from a ThreadManager IO worker."""
        deadline = time.monotonic() + max(0.0, float(SERVER_TIMEOUT_SECONDS))
        timed_out = False
        try:
            while not context.stop_event.is_set():
                thread_manager = self._thread_manager
                if thread_manager is not None and getattr(thread_manager, "_shutdown", False):
                    context.stop_event.set()
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    timed_out = True
                    context.stop_event.set()
                    break
                context.server.timeout = min(SERVER_POLL_SECONDS, remaining)
                try:
                    context.server.handle_request()
                except OSError:
                    if not context.stop_event.is_set():
                        raise
            if timed_out and self._is_active_callback_context(context):
                ThreadManager.run_on_ui_thread(
                    self._emit_auth_failed_safe,
                    "Gmail authorization timed out. Please try again.",
                )
                logger.info("[GMAIL_OAUTH] Callback server timed out")
        finally:
            self._finalize_callback_server(context)

    def _get_thread_manager(self) -> ThreadManager:
        """Return the owned ThreadManager used for OAuth network work."""
        manager = self._thread_manager
        if manager is None:
            manager = ThreadManager.get_app_shared()
            if manager is None:
                manager = ThreadManager.create_helper_manager(
                    resource_manager=ResourceManager.get_app_shared(),
                )
                self._owns_thread_manager = True
            self._thread_manager = manager
        return manager

    def _ensure_shutdown_hook(self) -> None:
        if self._shutdown_hook_connected:
            return
        app = QCoreApplication.instance()
        if app is None:
            return
        try:
            app.aboutToQuit.connect(self.shutdown)
            self._shutdown_hook_connected = True
        except Exception as exc:
            logger.debug("[GMAIL_OAUTH] Failed to attach OAuth shutdown hook: %s", exc)

    def _is_active_callback_context(self, context: _CallbackServerContext) -> bool:
        with self._auth_server_lock:
            return self._auth_context is context

    def _finalize_callback_server(self, context: _CallbackServerContext) -> None:
        try:
            context.close_once()
        except Exception as exc:
            logger.debug("[GMAIL_OAUTH] Server close suppressed: %s", exc)
        finally:
            with self._auth_server_lock:
                if self._auth_context is context:
                    self._auth_context = None
                    self._auth_server = None
                    self._auth_server_task_id = None
                    self._redirect_uri = None
            context.finished_event.set()

    def _stop_callback_server(self) -> None:
        with self._auth_server_lock:
            context = self._auth_context
        if context is None:
            return
        context.stop_event.set()
        manager = self._thread_manager
        cancelled = False
        if manager is not None and not getattr(manager, "_shutdown", False):
            try:
                cancelled = manager.cancel_task(context.task_id)
            except Exception as exc:
                logger.debug("[GMAIL_OAUTH] Callback task cancellation suppressed: %s", exc)
        if cancelled or manager is None or getattr(manager, "_shutdown", False):
            self._finalize_callback_server(context)

    def cancel_auth_flow(self) -> None:
        """Cancel any pending browser callback without blocking the UI thread."""
        self._stop_callback_server()

    def shutdown(self) -> None:
        """Release callback state before application-owned thread pools stop."""
        with self._auth_server_lock:
            context = self._auth_context
        self._stop_callback_server()
        if context is not None:
            context.finished_event.wait(timeout=SERVER_POLL_SECONDS + 0.25)
        manager = self._thread_manager
        if self._owns_thread_manager and manager is not None:
            manager.shutdown(wait=True, timeout=SERVER_POLL_SECONDS + 0.25)
            self._thread_manager = None
            self._owns_thread_manager = False

    def _emit_auth_failed_safe(self, msg: str) -> None:
        """Emit auth_failed on the UI thread with R-10 RuntimeError guard."""
        try:
            self.objectName()
        except RuntimeError:
            return
        self.auth_failed.emit(msg)

    def _emit_auth_completed_safe(self, creds: "GmailCredentials") -> None:
        """Emit auth_completed on the UI thread with R-10 RuntimeError guard."""
        try:
            self.objectName()
        except RuntimeError:
            return
        self.auth_completed.emit(creds)

    def _exchange_code(
        self,
        code: str,
        redirect_uri: Optional[str] = None,
        pkce_verifier: Optional[str] = None,
    ) -> None:
        """Exchange authorization code for tokens.

        Runs on a ThreadManager IO thread (not the UI thread).
        Qt signals are emitted back on the UI thread via run_on_ui_thread.
        """
        try:
            import requests
            data = {
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "client_secret": self._client_secret or "",
                "code": code,
                "redirect_uri": redirect_uri or self._redirect_uri,
                "code_verifier": pkce_verifier or self._pkce_verifier,
            }
            resp = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=30)
            resp.raise_for_status()
            token_data = resp.json()
            self._process_token_response(token_data)
        except Exception as exc:
            logger.error("[GMAIL_OAUTH] Token exchange failed: %s", exc)
            ThreadManager.run_on_ui_thread(self._emit_auth_failed_safe, str(exc))

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
            ThreadManager.run_on_ui_thread(self._emit_auth_completed_safe, self._credentials)
            logger.info("[GMAIL_OAUTH] Authentication completed successfully")
        except KeyError as exc:
            logger.error("[GMAIL_OAUTH] Malformed token response: %s", exc)
            ThreadManager.run_on_ui_thread(self._emit_auth_failed_safe, f"Malformed token response: {exc}")

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
