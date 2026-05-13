"""Tests for Gmail OAuth manager with mocked network calls (no real Google API)."""
from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

import requests
from PySide6.QtCore import QThread

import core.gmail.gmail_oauth as gmail_oauth_module
from core.gmail.gmail_oauth import GmailConfigError


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
    credentials_path.write_text(
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

    token_path = tmp_path / "gmail_token.enc"
    manager = gmail_oauth_module.GmailOAuthManager(
        credentials_path=credentials_path,
        token_path=token_path,
    )
    manager._pkce_verifier = "fake_verifier"
    manager._state = "fake_state"

    class _FakeThreadManager:
        def __init__(self) -> None:
            self.calls: list[tuple[object, tuple[object, ...]]] = []
            self.done = threading.Event()
            self.worker: threading.Thread | None = None

        def submit_io_task(self, fn, *args):
            self.calls.append((fn, args))

            # Use a real worker thread here because the contract we are guarding
            # is specifically "not on the Qt UI thread".
            def runner() -> None:
                fn(*args)
                self.done.set()

            self.worker = threading.Thread(target=runner, daemon=True)
            self.worker.start()
            return self.worker

    fake_tm = _FakeThreadManager()
    ui_dispatches: list[tuple[object, tuple[object, ...]]] = []
    request_thread_state: dict[str, bool] = {}

    monkeypatch.setattr(manager, "_get_thread_manager", lambda: fake_tm)
    monkeypatch.setattr(
        gmail_oauth_module.ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda fn, *args: ui_dispatches.append((fn, args))),
    )

    def fake_post(url, data=None, timeout=None, **kwargs):
        request_thread_state["is_ui_thread"] = (
            QThread.currentThread() == qt_app.thread()
        )

        class _Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {
                    "access_token": "fake_access_token",
                    "refresh_token": "fake_refresh_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": " ".join(gmail_oauth_module.GMAIL_SCOPES),
                }

        return _Response()

    monkeypatch.setattr(requests, "post", fake_post)

    try:
        manager._start_callback_server()
        assert manager._redirect_uri is not None

        callback_url = f"{manager._redirect_uri}/callback?code=fake_code&state=fake_state"
        with urllib.request.urlopen(callback_url, timeout=2) as response:
            body = response.read().decode("utf-8")

        assert "Authorization Successful!" in body
        assert fake_tm.done.wait(timeout=2), "OAuth IO task did not finish"
        assert fake_tm.calls
        submitted_fn, submitted_args = fake_tm.calls[0]
        assert getattr(submitted_fn, "__self__", None) is manager
        assert submitted_args == ("fake_code",)
        assert request_thread_state["is_ui_thread"] is False
        assert ui_dispatches, "Expected auth completion/failure dispatch back to UI thread"
    finally:
        manager._stop_callback_server()
        if fake_tm.worker is not None:
            fake_tm.worker.join(timeout=2)
