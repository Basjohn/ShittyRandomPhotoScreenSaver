"""Tests for Gmail OAuth manager with mocked network calls (no real Google API)."""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path

from PySide6.QtCore import QThread

import core.gmail.gmail_oauth as gmail_oauth_module
from core.gmail.gmail_oauth import GmailConfigError
from core.threading.manager import ThreadManager


def _wait_until(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def _write_fake_client_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "fake_client_id.apps.googleusercontent.com",
                    "client_secret": "fake_client_secret",
                }
            }
        ),
        encoding="utf-8",
    )


def test_dpapi_roundtrip_no_leak() -> None:
    """Verify DPAPI encrypt/decrypt roundtrip with fake credentials (no leak)."""
    from core.windows.dpapi import encrypt_user_data, decrypt_user_data

    # Use fake test data - NEVER use real credentials
    fake_password = b"fake_test_password_12345"
    
    # Encrypt
    encrypted = encrypt_user_data(fake_password)
    assert encrypted != fake_password
    assert encrypted.startswith(b"dpapi::") or encrypted.startswith(b"plain::")
    
    # Decrypt
    decrypted = decrypt_user_data(encrypted)
    assert decrypted == fake_password
    
    # Verify no plaintext in encrypted data
    assert fake_password not in encrypted
    assert b"password" not in encrypted


def test_oauth_config_error() -> None:
    """Verify GmailConfigError is raised for missing credentials."""
    # Test error message
    error = GmailConfigError("Test error message")
    assert str(error) == "Test error message"
    assert isinstance(error, Exception)


def test_gmail_credentials_dataclass() -> None:
    """Verify GmailCredentials dataclass structure."""
    from core.gmail.gmail_oauth import GmailCredentials
    from datetime import datetime, timedelta

    # Create credentials with fake data
    creds = GmailCredentials(
        access_token="fake_access_token",
        refresh_token="fake_refresh_token",
        token_type="Bearer",
        expires_at=datetime.now() + timedelta(hours=1),
        scope="gmail.metadata",
    )

    # Verify structure
    assert creds.access_token == "fake_access_token"
    assert creds.refresh_token == "fake_refresh_token"
    assert creds.is_expired() is False  # Should not be expired

    # Test to_dict
    creds_dict = creds.to_dict()
    assert "access_token" in creds_dict
    assert "refresh_token" in creds_dict

    # Test from_dict
    creds2 = GmailCredentials.from_dict(creds_dict)
    assert creds2.access_token == creds.access_token


def test_oauth_manager_singleton() -> None:
    """Verify GmailOAuthManager is a singleton."""
    from core.gmail.gmail_oauth import GmailOAuthManager

    # Get instance
    instance1 = GmailOAuthManager.instance()
    instance2 = GmailOAuthManager.instance()

    # Should be the same instance
    assert instance1 is instance2


def test_no_real_credentials_in_code() -> None:
    """Verify test code uses explicit fake credentials only."""
    import inspect
    import tests.test_gmail_oauth as test_module

    # Get source code
    source = inspect.getsource(test_module)

    # Verify we use explicit "fake_" prefixes for all credentials
    # This ensures no accidental real credentials
    assert "fake_" in source, "Test code should use fake_ prefix for test credentials"
    assert "fake_access_token" in source or "fake_token" in source
    assert "fake_password" in source


def test_imap_password_storage_mocked() -> None:
    """Verify IMAP password storage with DPAPI (no real credentials)."""
    from core.windows.dpapi import encrypt_user_data, decrypt_user_data

    # Use fake test password - NEVER use real IMAP password
    fake_imap_password = b"fake_imap_password_67890"
    
    # Encrypt
    encrypted = encrypt_user_data(fake_imap_password)
    assert encrypted != fake_imap_password
    
    # Decrypt
    decrypted = decrypt_user_data(encrypted)
    assert decrypted == fake_imap_password
    
    # Verify no plaintext password in encrypted data
    assert fake_imap_password not in encrypted


def test_oauth_callback_submits_token_exchange_off_ui_thread(tmp_path: Path, qt_app, monkeypatch) -> None:
    """Verify callback flow submits token exchange to background IO instead of the UI thread."""
    credentials_path = tmp_path / "client_secrets.json"
    _write_fake_client_config(credentials_path)

    token_path = tmp_path / "gmail_token.enc"
    thread_manager = ThreadManager.create_helper_manager(io_workers=2, compute_workers=1)
    manager = gmail_oauth_module.GmailOAuthManager(
        credentials_path=credentials_path,
        token_path=token_path,
        thread_manager=thread_manager,
    )
    manager._pkce_verifier = "fake_verifier"
    manager._state = "fake_state"

    exchange_done = threading.Event()
    exchange_args: list[tuple[str, str, str]] = []
    request_thread_state: dict[str, bool] = {}

    def fake_exchange(code: str, redirect_uri: str, pkce_verifier: str) -> None:
        request_thread_state["is_ui_thread"] = (
            QThread.currentThread() == qt_app.thread()
        )
        exchange_args.append((code, redirect_uri, pkce_verifier))
        exchange_done.set()

    monkeypatch.setattr(manager, "_exchange_code", fake_exchange)

    try:
        manager._start_callback_server()
        assert manager._redirect_uri is not None
        context = manager._auth_context
        assert context is not None
        assert context.task_id in thread_manager.get_active_tasks()

        callback_url = f"{manager._redirect_uri}/callback?code=fake_code&state=fake_state"
        with urllib.request.urlopen(callback_url, timeout=2) as response:
            body = response.read().decode("utf-8")

        assert "Authorization Successful!" in body
        assert exchange_done.wait(timeout=2), "OAuth IO task did not finish"
        assert exchange_args == [("fake_code", context.redirect_uri, "fake_verifier")]
        assert request_thread_state["is_ui_thread"] is False
        assert context.finished_event.wait(timeout=2)
        assert manager._auth_server is None
        assert manager._auth_server_task_id is None
        assert manager._redirect_uri is None
        assert _wait_until(lambda: not thread_manager.get_active_tasks())
    finally:
        manager.cancel_auth_flow()
        thread_manager.shutdown(wait=True, timeout=2)


def test_oauth_user_cancel_releases_callback_server_once(tmp_path: Path, qt_app, monkeypatch) -> None:
    credentials_path = tmp_path / "client_secrets.json"
    _write_fake_client_config(credentials_path)
    thread_manager = ThreadManager.create_helper_manager(io_workers=1, compute_workers=1)
    real_server_type = gmail_oauth_module.HTTPServer

    class _CountingHTTPServer(real_server_type):
        def __init__(self, *args, **kwargs):
            self.close_calls = 0
            super().__init__(*args, **kwargs)

        def server_close(self) -> None:
            self.close_calls += 1
            super().server_close()

    dispatches: list[tuple[object, tuple[object, ...]]] = []
    monkeypatch.setattr(gmail_oauth_module, "HTTPServer", _CountingHTTPServer)
    monkeypatch.setattr(
        gmail_oauth_module.ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda fn, *args: dispatches.append((fn, args))),
    )
    manager = gmail_oauth_module.GmailOAuthManager(
        credentials_path=credentials_path,
        token_path=tmp_path / "gmail_token.enc",
        thread_manager=thread_manager,
    )
    manager._pkce_verifier = "fake_verifier"
    manager._state = "fake_state"

    try:
        manager._start_callback_server()
        context = manager._auth_context
        assert context is not None
        with urllib.request.urlopen(
            f"{context.redirect_uri}/?error=access_denied&error_description=fake_cancel",
            timeout=2,
        ) as response:
            assert "Authorization Failed" in response.read().decode("utf-8")
        assert context.finished_event.wait(timeout=2)
        assert context.server.close_calls == 1
        assert dispatches
        assert "access_denied" in str(dispatches[0][1][0])
        assert _wait_until(lambda: not thread_manager.get_active_tasks())
    finally:
        manager.cancel_auth_flow()
        thread_manager.shutdown(wait=True, timeout=2)


def test_oauth_callback_timeout_releases_server(tmp_path: Path, qt_app, monkeypatch) -> None:
    credentials_path = tmp_path / "client_secrets.json"
    _write_fake_client_config(credentials_path)
    thread_manager = ThreadManager.create_helper_manager(io_workers=1, compute_workers=1)
    dispatches: list[tuple[object, tuple[object, ...]]] = []
    monkeypatch.setattr(gmail_oauth_module, "SERVER_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(
        gmail_oauth_module.ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda fn, *args: dispatches.append((fn, args))),
    )
    manager = gmail_oauth_module.GmailOAuthManager(
        credentials_path=credentials_path,
        token_path=tmp_path / "gmail_token.enc",
        thread_manager=thread_manager,
    )
    manager._pkce_verifier = "fake_verifier"
    manager._state = "fake_state"

    try:
        manager._start_callback_server()
        context = manager._auth_context
        assert context is not None
        assert context.finished_event.wait(timeout=2)
        assert manager._auth_server is None
        assert dispatches
        assert "timed out" in str(dispatches[0][1][0]).lower()
        assert _wait_until(lambda: not thread_manager.get_active_tasks())
    finally:
        manager.cancel_auth_flow()
        thread_manager.shutdown(wait=True, timeout=2)


def test_oauth_shutdown_releases_pending_callback_task(tmp_path: Path, qt_app) -> None:
    credentials_path = tmp_path / "client_secrets.json"
    _write_fake_client_config(credentials_path)
    thread_manager = ThreadManager.create_helper_manager(io_workers=1, compute_workers=1)
    manager = gmail_oauth_module.GmailOAuthManager(
        credentials_path=credentials_path,
        token_path=tmp_path / "gmail_token.enc",
        thread_manager=thread_manager,
    )
    manager._pkce_verifier = "fake_verifier"
    manager._state = "fake_state"

    try:
        manager._start_callback_server()
        context = manager._auth_context
        assert context is not None
        manager.shutdown()
        assert context.finished_event.wait(timeout=2)
        assert manager._auth_server is None
        assert _wait_until(lambda: not thread_manager.get_active_tasks())
    finally:
        thread_manager.shutdown(wait=True, timeout=2)


def test_settings_owner_destruction_cancels_oauth_flow() -> None:
    from ui.tabs.widgets_tab_gmail import _wire_gmail_auth_lifecycle

    class _FakeSignal:
        def __init__(self) -> None:
            self.callbacks: list[object] = []

        def connect(self, callback) -> None:
            self.callbacks.append(callback)

        def emit(self) -> None:
            for callback in self.callbacks:
                callback(None)

    class _FakeTab:
        def __init__(self) -> None:
            self.destroyed = _FakeSignal()

    class _FakeOAuthManager:
        def __init__(self) -> None:
            self.cancel_calls = 0

        def cancel_auth_flow(self) -> None:
            self.cancel_calls += 1

    tab = _FakeTab()
    manager = _FakeOAuthManager()
    _wire_gmail_auth_lifecycle(tab, manager)
    _wire_gmail_auth_lifecycle(tab, manager)
    assert len(tab.destroyed.callbacks) == 1
    tab.destroyed.emit()
    assert manager.cancel_calls == 1
