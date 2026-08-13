"""Unified Gmail backend — routes to OAuth/REST or IMAP depending on config.

The widget layer interacts only with GmailBackend. It decides which underlying
client to construct based on stored settings (backend mode, credentials).

Credential storage for IMAP uses DPAPI-encrypted files identical to OAuth tokens.
"""
from __future__ import annotations

import json
import threading
from enum import Enum
from pathlib import Path
from typing import Callable, Optional
import weakref

from PySide6.QtCore import QCoreApplication, QObject, Signal
from shiboken6 import Shiboken

from core.gmail.gmail_bootstrap import (
    PreparedGmailBootstrap,
    PreparedOAuthClientConfig,
    prepare_gmail_backend_bootstrap,
    prepare_oauth_client_config,
)
from core.gmail.gmail_client import GmailClient
from core.gmail.gmail_imap import GmailImapClient
from core.gmail.gmail_oauth import GmailOAuthManager
from core.logging.logger import get_logger
from core.threading.manager import ThreadManager
from core.windows.dpapi import save_encrypted

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

    def __init__(self, *, oauth_manager: GmailOAuthManager | None = None) -> None:
        super().__init__()
        # The QObject facade is cheap and GUI-owned.  All cold filesystem and
        # DPAPI work is installed later from one shared-worker snapshot.
        self._app_data: Optional[Path] = None
        self._imap_creds_path: Optional[Path] = None
        self._config_path: Optional[Path] = None

        self._mode: GmailBackendMode = GmailBackendMode.OAUTH
        self._imap_email: Optional[str] = None
        self._imap_password: Optional[str] = None
        self._imap_client: Optional[GmailImapClient] = None

        self._oauth_manager = oauth_manager or GmailOAuthManager.instance()
        self._oauth_client: Optional[GmailClient] = None
        self._initialized = False
        self._initializing = False
        self._initialization_callbacks: list[Callable[[bool], None]] = []
        self._client_config_refreshing = False
        self._client_config_callbacks: list[Callable[[bool], None]] = []
        self._bootstrap_thread_manager: Optional[ThreadManager] = None
        self._owns_bootstrap_thread_manager = False
        self._bootstrap_shutdown_hook_connected = False

        self._oauth_manager.auth_completed.connect(self._on_oauth_completed)
        self._oauth_manager.auth_revoked.connect(self._on_oauth_revoked)

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def oauth_manager(self) -> GmailOAuthManager:
        return self._oauth_manager

    @property
    def app_data_path(self) -> Optional[Path]:
        return self._app_data

    def get_bootstrap_thread_manager(self) -> ThreadManager:
        """Return a process-lifetime manager for singleton bootstrap work."""

        manager = self._bootstrap_thread_manager
        if manager is not None and not getattr(manager, "_shutdown", False):
            return manager

        manager = ThreadManager.get_app_shared()
        if manager is None:
            manager = ThreadManager.create_helper_manager()
            self._owns_bootstrap_thread_manager = True
        else:
            self._owns_bootstrap_thread_manager = False
        self._bootstrap_thread_manager = manager

        if not self._bootstrap_shutdown_hook_connected:
            app = QCoreApplication.instance()
            if app is not None:
                try:
                    app.aboutToQuit.connect(self.shutdown)
                    self._bootstrap_shutdown_hook_connected = True
                except Exception as exc:
                    logger.debug(
                        "[GMAIL_BACKEND] Failed to attach bootstrap shutdown hook: %s",
                        exc,
                    )
        return manager

    def shutdown(self) -> None:
        """Release a backend-owned fallback manager at process shutdown."""

        manager = self._bootstrap_thread_manager
        self._bootstrap_thread_manager = None
        if self._owns_bootstrap_thread_manager and manager is not None:
            try:
                manager.shutdown(wait=True, timeout=2.0)
            except Exception as exc:
                logger.debug(
                    "[GMAIL_BACKEND] Bootstrap manager shutdown suppressed: %s",
                    exc,
                )
        self._owns_bootstrap_thread_manager = False

    def ensure_initialized(
        self,
        thread_manager: ThreadManager | None,
        callback: Callable[[bool], None] | None = None,
    ) -> bool:
        """Coalesce cold preparation and commit it back on the GUI thread."""

        if self._initialized:
            if callback is not None:
                callback(True)
            return True
        if callback is not None:
            self._initialization_callbacks.append(callback)
        if self._initializing:
            return True
        if thread_manager is None:
            self._finish_initialization(None, "ThreadManager is not configured")
            return False

        self._initializing = True
        owner_ref = weakref.ref(self)

        def _on_result(result) -> None:
            snapshot = None
            error = None
            if getattr(result, "success", False):
                candidate = getattr(result, "result", None)
                if isinstance(candidate, PreparedGmailBootstrap):
                    snapshot = candidate
                else:
                    error = "No Gmail backend bootstrap returned"
            else:
                error = str(getattr(result, "error", None) or "Gmail backend bootstrap failed")

            def _deliver() -> None:
                owner = owner_ref()
                if owner is None or not Shiboken.isValid(owner):
                    return
                owner._finish_initialization(snapshot, error)

            ThreadManager.run_on_ui_thread(_deliver)

        try:
            thread_manager.submit_io_task(
                prepare_gmail_backend_bootstrap,
                callback=_on_result,
                category="gmail_backend_bootstrap",
            )
            return True
        except Exception as exc:
            self._finish_initialization(None, str(exc))
            return False

    def _finish_initialization(
        self,
        snapshot: PreparedGmailBootstrap | None,
        error: str | None,
    ) -> None:
        callbacks = self._initialization_callbacks
        self._initialization_callbacks = []
        self._initializing = False
        success = snapshot is not None
        if snapshot is not None:
            self._app_data = snapshot.app_data_path
            self._config_path = snapshot.backend_config_path
            self._imap_creds_path = snapshot.imap_credentials_path
            self._mode = GmailBackendMode(snapshot.backend_mode)
            self._imap_email = snapshot.imap_email
            self._imap_password = snapshot.imap_password
            self._imap_client = None
            self._oauth_manager.install_prepared_bootstrap(snapshot)
            self._oauth_client = (
                GmailClient(self._oauth_manager)
                if self._oauth_manager.is_authenticated
                else None
            )
            self._initialized = True
            self.auth_state_changed.emit()
        elif error:
            logger.error("[GMAIL_BACKEND] Bootstrap failed: %s", error)
        for pending in callbacks:
            try:
                pending(success)
            except Exception as exc:
                logger.warning("[GMAIL_BACKEND] Bootstrap callback failed: %s", exc)

    def reload_oauth_client_config(
        self,
        thread_manager: ThreadManager | None,
        callback: Callable[[bool], None] | None = None,
    ) -> bool:
        """Refresh client_secrets.json on shared I/O, coalescing callers."""

        path = self._oauth_manager._credentials_path
        if not self._initialized or path is None or thread_manager is None:
            if callback is not None:
                callback(False)
            return False
        if callback is not None:
            self._client_config_callbacks.append(callback)
        if self._client_config_refreshing:
            return True
        self._client_config_refreshing = True
        owner_ref = weakref.ref(self)
        credentials_path = Path(path)

        def _prepare() -> PreparedOAuthClientConfig:
            return prepare_oauth_client_config(credentials_path)

        def _on_result(result) -> None:
            config = None
            if getattr(result, "success", False):
                candidate = getattr(result, "result", None)
                if isinstance(candidate, PreparedOAuthClientConfig):
                    config = candidate

            def _deliver() -> None:
                owner = owner_ref()
                if owner is None or not Shiboken.isValid(owner):
                    return
                owner._finish_client_config_refresh(config)

            ThreadManager.run_on_ui_thread(_deliver)

        try:
            thread_manager.submit_io_task(
                _prepare,
                callback=_on_result,
                category="gmail_oauth_config_refresh",
            )
            return True
        except Exception as exc:
            logger.warning("[GMAIL_BACKEND] Client config refresh dispatch failed: %s", exc)
            self._finish_client_config_refresh(None)
            return False

    def _finish_client_config_refresh(
        self,
        config: PreparedOAuthClientConfig | None,
    ) -> None:
        callbacks = self._client_config_callbacks
        self._client_config_callbacks = []
        self._client_config_refreshing = False
        success = config is not None
        if config is not None:
            self._oauth_manager.install_prepared_client_config(config)
            self.auth_state_changed.emit()
        for pending in callbacks:
            try:
                pending(success)
            except Exception as exc:
                logger.warning("[GMAIL_BACKEND] Client config callback failed: %s", exc)

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
        if not self._initialized:
            return False
        if self._mode == GmailBackendMode.OAUTH:
            return self._oauth_manager.is_authenticated
        return self._imap_email is not None and self._imap_password is not None

    @property
    def client(self) -> Optional[GmailClient | GmailImapClient]:
        """Return the active client or None if not authenticated."""
        if not self._initialized:
            return None
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
        if not self._initialized:
            return "Gmail status loading..."
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
            if self._imap_creds_path is None:
                raise RuntimeError("Gmail backend is not initialized")
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
            if self._imap_creds_path is not None and self._imap_creds_path.exists():
                self._imap_creds_path.unlink()
        except Exception as exc:
            logger.warning("[GMAIL_BACKEND] Failed to delete IMAP creds file: %s", exc)
        logger.info("[GMAIL_BACKEND] IMAP credentials cleared")
        self.auth_state_changed.emit()

    def test_imap_connection(self) -> bool:
        """Test IMAP login with current credentials."""
        if not self._imap_email or not self._imap_password:
            return False
        return self.test_imap_credentials(self._imap_email, self._imap_password)

    def test_imap_credentials(self, email_address: str, app_password: str) -> bool:
        """Test supplied IMAP credentials without storing them."""
        if not email_address or not app_password:
            return False
        client = GmailImapClient(email_address, app_password)
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

    def _save_config(self) -> None:
        try:
            if self._config_path is None:
                raise RuntimeError("Gmail backend is not initialized")
            self._config_path.write_text(
                json.dumps({"mode": self._mode.value}), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("[GMAIL_BACKEND] Failed to save config: %s", exc)
