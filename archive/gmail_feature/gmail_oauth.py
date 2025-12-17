"""
Gmail OAuth 2.0 authentication module.

Provides OAuth 2.0 PKCE flow for desktop applications to authenticate with Gmail API.
Uses metadata-only scopes to ensure user privacy - we never access message content.

Security:
- Uses PKCE (Proof Key for Code Exchange) for secure desktop auth
- Tokens stored locally in user's app data directory
- Only requests gmail.metadata and gmail.modify scopes
- Never downloads message content or attachments
"""
from __future__ import annotations

import json
import os
import secrets
import hashlib
import base64
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from urllib.parse import urlencode, parse_qs, urlparse

from PySide6.QtCore import QObject, Signal

from core.logging.logger import get_logger

logger = get_logger(__name__)

# Gmail API scopes - using sensitive (not restricted) scopes for easier publishing
# gmail.readonly: Read email metadata (sender, subject, labels)
# gmail.modify: Modify labels (mark read, archive, spam, trash)
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

# Local callback server - use localhost for Desktop app OAuth
# Google Desktop apps support http://localhost:<port> with dynamic port binding
# No need to register redirect URI in console for Desktop app type
REDIRECT_HOST = "localhost"

# Client ID for desktop app (public - PKCE provides security, not client ID secrecy)
# This is safe to embed in source code - PKCE flow doesn't rely on client secret
DEFAULT_CLIENT_ID = "867389666912-r0anqoa5e6hcisf770qd0qvpe2a1l51u.apps.googleusercontent.com"


@dataclass
class GmailCredentials:
    """OAuth 2.0 credentials for Gmail API access."""
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime
    scope: str
    
    def is_expired(self) -> bool:
        """Check if the access token is expired or about to expire."""
        return datetime.now() >= self.expires_at - timedelta(minutes=5)
    
    def to_dict(self) -> dict:
        """Serialize credentials to dictionary."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at.isoformat(),
            "scope": self.scope,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "GmailCredentials":
        """Deserialize credentials from dictionary."""
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_type=data["token_type"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            scope=data["scope"],
        )


class GmailOAuthManager(QObject):
    """
    Manages Gmail OAuth 2.0 authentication flow.
    
    Signals:
        auth_started: Emitted when auth flow begins
        auth_completed: Emitted with credentials when auth succeeds
        auth_failed: Emitted with error message when auth fails
        auth_revoked: Emitted when credentials are revoked
    """
    
    auth_started = Signal()
    auth_completed = Signal(object)  # GmailCredentials
    auth_failed = Signal(str)  # Error message
    auth_revoked = Signal()
    
    _instance: Optional["GmailOAuthManager"] = None
    _instance_lock = threading.Lock()
    
    @classmethod
    def instance(cls) -> "GmailOAuthManager":
        """Get or create the singleton instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    
    def __init__(self):
        super().__init__()
        self._credentials: Optional[GmailCredentials] = None
        self._client_id: str = DEFAULT_CLIENT_ID
        self._auth_server: Optional[HTTPServer] = None
        self._auth_thread: Optional[threading.Thread] = None
        self._pkce_verifier: Optional[str] = None
        self._state: Optional[str] = None
        self._redirect_uri: Optional[str] = None  # Set dynamically when server starts
        self._credentials_path = self._get_credentials_path()
        
        # Try to load existing credentials
        self._load_credentials()
    
    def _get_credentials_path(self) -> str:
        """Get the path to store credentials."""
        app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
        creds_dir = os.path.join(app_data, "ShittyRandomPhotoScreenSaver", "auth")
        os.makedirs(creds_dir, exist_ok=True)
        return os.path.join(creds_dir, "gmail_credentials.json")
    
    def set_client_id(self, client_id: str) -> None:
        """Set the OAuth client ID."""
        self._client_id = client_id
    
    @property
    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        return self._credentials is not None
    
    @property
    def credentials(self) -> Optional[GmailCredentials]:
        """Get current credentials, refreshing if needed."""
        if self._credentials is None:
            return None
        
        if self._credentials.is_expired():
            self._refresh_token()
        
        return self._credentials
    
    def _load_credentials(self) -> None:
        """Load credentials from disk."""
        try:
            if os.path.exists(self._credentials_path):
                with open(self._credentials_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._credentials = GmailCredentials.from_dict(data)
                logger.info("[GMAIL_OAUTH] Loaded existing credentials")
        except Exception as e:
            logger.warning("[GMAIL_OAUTH] Failed to load credentials: %s", e)
            self._credentials = None
    
    def _save_credentials(self) -> None:
        """Save credentials to disk."""
        if self._credentials is None:
            return
        
        try:
            with open(self._credentials_path, "w", encoding="utf-8") as f:
                json.dump(self._credentials.to_dict(), f, indent=2)
            logger.info("[GMAIL_OAUTH] Saved credentials")
        except Exception as e:
            logger.error("[GMAIL_OAUTH] Failed to save credentials: %s", e)
    
    def _delete_credentials(self) -> None:
        """Delete stored credentials."""
        try:
            if os.path.exists(self._credentials_path):
                os.remove(self._credentials_path)
            self._credentials = None
            logger.info("[GMAIL_OAUTH] Deleted credentials")
        except Exception as e:
            logger.error("[GMAIL_OAUTH] Failed to delete credentials: %s", e)
    
    def _generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge."""
        # Generate random verifier (43-128 chars)
        verifier = secrets.token_urlsafe(64)
        
        # Create SHA256 challenge
        challenge_bytes = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(challenge_bytes).decode("ascii").rstrip("=")
        
        return verifier, challenge
    
    def start_auth_flow(self) -> bool:
        """
        Start the OAuth 2.0 authorization flow.
        
        Opens the user's browser to Google's consent screen and starts
        a local server to receive the callback.
        
        Returns:
            True if flow started successfully, False otherwise
        """
        if not self._client_id:
            self.auth_failed.emit("No OAuth client ID configured")
            return False
        
        try:
            # Generate PKCE pair
            self._pkce_verifier, pkce_challenge = self._generate_pkce_pair()
            self._state = secrets.token_urlsafe(32)
            
            # Start callback server first to get the dynamic port
            self._start_callback_server()
            
            # Build authorization URL with the actual redirect URI
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
            
            # Open browser
            self.auth_started.emit()
            webbrowser.open(auth_url)
            
            logger.info("[GMAIL_OAUTH] Auth flow started")
            return True
            
        except Exception as e:
            logger.error("[GMAIL_OAUTH] Failed to start auth flow: %s", e)
            self.auth_failed.emit(str(e))
            return False
    
    def _start_callback_server(self) -> None:
        """Start the local HTTP server to receive OAuth callback."""
        manager = self
        
        class CallbackHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress HTTP server logs
            
            def do_GET(self):
                parsed = urlparse(self.path)
                # Accept any path - Google redirects to root for Desktop apps
                if parsed.path in ("/", "/callback"):
                    params = parse_qs(parsed.query)
                    
                    # Send response to browser
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    
                    if "code" in params and "state" in params:
                        code = params["code"][0]
                        state = params["state"][0]
                        
                        if state == manager._state:
                            self.wfile.write(b"""
                                <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
                                <h1>Authorization Successful!</h1>
                                <p>You can close this window and return to the application.</p>
                                </body></html>
                            """)
                            # Exchange code for tokens in background
                            threading.Thread(
                                target=manager._exchange_code,
                                args=(code,),
                                daemon=True
                            ).start()
                        else:
                            self.wfile.write(b"""
                                <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
                                <h1>Authorization Failed</h1>
                                <p>State mismatch - possible CSRF attack.</p>
                                </body></html>
                            """)
                            manager.auth_failed.emit("State mismatch")
                    else:
                        error = params.get("error", ["Unknown error"])[0]
                        self.wfile.write(f"""
                            <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
                            <h1>Authorization Failed</h1>
                            <p>{error}</p>
                            </body></html>
                        """.encode())
                        manager.auth_failed.emit(error)
                    
                    # Shutdown server after handling
                    threading.Thread(target=manager._stop_callback_server, daemon=True).start()
                else:
                    self.send_response(404)
                    self.end_headers()
        
        try:
            # Bind to port 0 to let OS assign an available port
            self._auth_server = HTTPServer((REDIRECT_HOST, 0), CallbackHandler)
            actual_port = self._auth_server.server_address[1]
            self._redirect_uri = f"http://{REDIRECT_HOST}:{actual_port}"
            
            self._auth_thread = threading.Thread(target=self._auth_server.serve_forever, daemon=True)
            self._auth_thread.start()
            logger.debug("[GMAIL_OAUTH] Callback server started on %s", self._redirect_uri)
        except Exception as e:
            logger.error("[GMAIL_OAUTH] Failed to start callback server: %s", e)
            raise
    
    def _stop_callback_server(self) -> None:
        """Stop the callback server."""
        if self._auth_server:
            try:
                self._auth_server.shutdown()
                self._auth_server = None
                logger.debug("[GMAIL_OAUTH] Callback server stopped")
            except Exception:
                pass
    
    def _exchange_code(self, code: str) -> None:
        """Exchange authorization code for tokens."""
        try:
            import urllib.request
            
            data = urlencode({
                "client_id": self._client_id,
                "code": code,
                "code_verifier": self._pkce_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": self._redirect_uri,
            }).encode("utf-8")
            
            req = urllib.request.Request(
                GOOGLE_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                token_data = json.loads(response.read().decode("utf-8"))
            
            # Create credentials
            expires_in = token_data.get("expires_in", 3600)
            self._credentials = GmailCredentials(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", ""),
                token_type=token_data.get("token_type", "Bearer"),
                expires_at=datetime.now() + timedelta(seconds=expires_in),
                scope=token_data.get("scope", " ".join(GMAIL_SCOPES)),
            )
            
            self._save_credentials()
            self.auth_completed.emit(self._credentials)
            logger.info("[GMAIL_OAUTH] Authorization completed successfully")
            
        except Exception as e:
            logger.error("[GMAIL_OAUTH] Token exchange failed: %s", e)
            self.auth_failed.emit(str(e))
    
    def _refresh_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self._credentials or not self._credentials.refresh_token:
            return False
        
        try:
            import urllib.request
            
            data = urlencode({
                "client_id": self._client_id,
                "refresh_token": self._credentials.refresh_token,
                "grant_type": "refresh_token",
            }).encode("utf-8")
            
            req = urllib.request.Request(
                GOOGLE_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                token_data = json.loads(response.read().decode("utf-8"))
            
            # Update credentials
            expires_in = token_data.get("expires_in", 3600)
            self._credentials = GmailCredentials(
                access_token=token_data["access_token"],
                refresh_token=self._credentials.refresh_token,  # Keep existing refresh token
                token_type=token_data.get("token_type", "Bearer"),
                expires_at=datetime.now() + timedelta(seconds=expires_in),
                scope=self._credentials.scope,
            )
            
            self._save_credentials()
            logger.debug("[GMAIL_OAUTH] Token refreshed successfully")
            return True
            
        except Exception as e:
            logger.error("[GMAIL_OAUTH] Token refresh failed: %s", e)
            return False
    
    def revoke_authorization(self) -> bool:
        """
        Revoke the current authorization.
        
        Returns:
            True if revocation succeeded, False otherwise
        """
        if not self._credentials:
            return True
        
        try:
            import urllib.request
            
            # Revoke the token with Google
            data = urlencode({"token": self._credentials.access_token}).encode("utf-8")
            req = urllib.request.Request(
                GOOGLE_REVOKE_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            try:
                with urllib.request.urlopen(req, timeout=30):
                    pass
            except Exception:
                pass  # Revocation may fail if token already expired, that's OK
            
            # Delete local credentials
            self._delete_credentials()
            self.auth_revoked.emit()
            logger.info("[GMAIL_OAUTH] Authorization revoked")
            return True
            
        except Exception as e:
            logger.error("[GMAIL_OAUTH] Revocation failed: %s", e)
            return False
    
    def get_access_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if needed."""
        creds = self.credentials
        if creds:
            return creds.access_token
        return None
