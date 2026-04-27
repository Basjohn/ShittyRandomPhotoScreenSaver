"""Unified Gmail backend — routes to OAuth/REST or IMAP depending on config.

The widget layer interacts only with GmailBackend. It decides which underlying
client to construct based on stored settings (backend mode, credentials).

Credential storage for IMAP uses DPAPI-encrypted files identical to OAuth tokens.
"""
from __future__ import annotations

import json
import threading
from enum import Enum
from typing import Optional

from PySide6.QtCore import QObject, Signal

from core.gmail.gmail_client import GmailClient
from core.gmail.gmail_imap import GmailImapClient
from core.gmail.gmail_oauth import GmailOAuthManager
from core.logging.logger import get_logger
from core.settings.storage_paths import get_app_data_dir
from core.windows.dpapi import save_encrypted, load_encrypted

logger = get_logger(__name__)


class GmailBackendMode(Enum):
    OAUTH = "oauth"
    IMAP = "imap"


class GmailBackend(QObject):
    """Unified facade over OAuth+REST and IMAP+AppPassword Gmail access."""

    auth_state_changed = Signal()

    _instance: Optional["GmailBackend"] = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "GmailBackend":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._app_data = get_app_data_dir()
        self._imap_creds_path = self._app_data / "gmail_imap_creds.enc"
        self._config_path = self._app_data / "gmail_backend.json"

        self._mode: GmailBackendMode = GmailBackendMode.OAUTH
        self._imap_email: Optional[str] = None
        self._imap_password: Optional[str] = None
        self._imap_client: Optional[GmailImapClient] = None

        self._load_config()
        self._load_imap_credentials()

        self._oauth_manager = GmailOAuthManager.instance()
        self._oauth_client: Optional[GmailClient] = None
        if self._oauth_manager.is_authenticated:
            self._oauth_client = GmailClient(self._oauth_manager)

        self._oauth_manager.auth_completed.connect(self._on_oauth_completed)
        self._oauth_manager.auth_revoked.connect(self._on_oauth_revoked)

    @property
    def mode(self) -> GmailBackendMode:
        return self._mode

    @mode.setter
    def mode(self, value: GmailBackendMode) -> None:
        if self._mode != value:
            self._mode = value
            self._save_config()
            self.auth_state_changed.emit()

    @property
    def is_authenticated(self) -> bool:
        if self._mode == GmailBackendMode.OAUTH:
            return self._oauth_manager.is_authenticated
        return self._imap_email is not None and self._imap_password is not None

    @property
    def client(self) -> Optional[GmailClient | GmailImapClient]:
        """Return the active client or None if not authenticated."""
        if self._mode == GmailBackendMode.OAUTH:
            if self._oauth_manager.is_authenticated:
                if self._oauth_client is None:
                    self._oauth_client = GmailClient(self._oauth_manager)
                return self._oauth_client
            return None
        if self._imap_email and self._imap_password:
            if self._imap_client is None:
                self._imap_client = GmailImapClient(self._imap_email, self._imap_password)
            return self._imap_client
        return None

    @property
    def status_text(self) -> str:
        """Human-readable status for the settings UI."""
        if self._mode == GmailBackendMode.OAUTH:
            if self._oauth_manager.is_authenticated:
                return "Signed in (OAuth)"
            if not getattr(self._oauth_manager, '_client_id', None):
                return "Missing client_secrets.json"
            return "Ready — click Authorize"
        if self._imap_email and self._imap_password:
            return f"Signed in (IMAP: {self._imap_email})"
        return "Enter email & app password"

    def save_imap_credentials(self, email_address: str, app_password: str) -> None:
        """Store IMAP credentials (DPAPI-encrypted)."""
        self._imap_email = email_address
        self._imap_password = app_password
        self._imap_client = None
        try:
            data = json.dumps({"email": email_address, "app_password": app_password}).encode("utf-8")
            save_encrypted(self._imap_creds_path, data)
            logger.info("[GMAIL_BACKEND] IMAP credentials saved for %s", email_address)
        except Exception as exc:
            logger.error("[GMAIL_BACKEND] Failed to save IMAP creds: %s", exc)
        self.auth_state_changed.emit()

    def clear_imap_credentials(self) -> None:
        """Remove stored IMAP credentials."""
        self._imap_email = None
        self._imap_password = None
        self._imap_client = None
        try:
            if self._imap_creds_path.exists():
                self._imap_creds_path.unlink()
        except Exception as exc:
            logger.warning("[GMAIL_BACKEND] Failed to delete IMAP creds file: %s", exc)
        logger.info("[GMAIL_BACKEND] IMAP credentials cleared")
        self.auth_state_changed.emit()

    def test_imap_connection(self) -> bool:
        """Test IMAP login with current credentials."""
        if not self._imap_email or not self._imap_password:
            return False
        client = GmailImapClient(self._imap_email, self._imap_password)
        return client.test_connection()

    def start_oauth_flow(self) -> bool:
        """Delegate to OAuth manager."""
        return self._oauth_manager.start_auth_flow()

    def sign_out(self) -> None:
        """Sign out of whatever backend is active."""
        if self._mode == GmailBackendMode.OAUTH:
            if self._oauth_manager.is_authenticated:
                self._oauth_manager.revoke_credentials()
            else:
                self._oauth_manager.clear_local_credentials()
            self._oauth_client = None
        else:
            self.clear_imap_credentials()
        self.auth_state_changed.emit()

    def _on_oauth_completed(self, _creds) -> None:
        self._oauth_client = GmailClient(self._oauth_manager)
        self.auth_state_changed.emit()

    def _on_oauth_revoked(self) -> None:
        self._oauth_client = None
        self.auth_state_changed.emit()

    def _load_config(self) -> None:
        try:
            if self._config_path.exists():
                data = json.loads(self._config_path.read_text(encoding="utf-8"))
                mode_str = data.get("mode", "oauth")
                self._mode = GmailBackendMode(mode_str)
        except Exception as exc:
            logger.warning("[GMAIL_BACKEND] Failed to load config: %s", exc)

    def _save_config(self) -> None:
        try:
            self._config_path.write_text(
                json.dumps({"mode": self._mode.value}), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("[GMAIL_BACKEND] Failed to save config: %s", exc)

    def _load_imap_credentials(self) -> None:
        try:
            plaintext = load_encrypted(self._imap_creds_path)
            if plaintext is None:
                return
            data = json.loads(plaintext.decode("utf-8"))
            self._imap_email = data.get("email")
            self._imap_password = data.get("app_password")
            if self._imap_email and self._imap_password:
                logger.info("[GMAIL_BACKEND] Loaded IMAP credentials for %s", self._imap_email)
        except Exception as exc:
            logger.warning("[GMAIL_BACKEND] Failed to load IMAP creds: %s", exc)
