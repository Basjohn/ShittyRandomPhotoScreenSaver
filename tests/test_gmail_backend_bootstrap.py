"""Thread-affinity and lifecycle coverage for Gmail backend bootstrap."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import json
import pickle
import threading

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from core.gmail.gmail_backend import GmailBackend
import core.gmail.gmail_bootstrap as gmail_bootstrap_module
from core.gmail.gmail_bootstrap import (
    PreparedGmailBootstrap,
    PreparedOAuthClientConfig,
    PreparedOAuthCredentials,
    prepare_gmail_backend_bootstrap,
)
from core.gmail.gmail_oauth import GmailOAuthManager
from core.threading.manager import ThreadManager


class _QueuedIoManager:
    def __init__(self) -> None:
        self.tasks: list[SimpleNamespace] = []

    def submit_io_task(
        self,
        func,
        *args,
        callback=None,
        category="uncategorized",
        **kwargs,
    ):
        self.tasks.append(
            SimpleNamespace(
                func=func,
                args=args,
                kwargs=kwargs,
                callback=callback,
                category=category,
            )
        )
        return f"task-{len(self.tasks)}"


def _snapshot(tmp_path: Path, *, mode: str = "oauth") -> PreparedGmailBootstrap:
    app_data = tmp_path / "appdata"
    return PreparedGmailBootstrap(
        app_data_path=app_data,
        backend_config_path=app_data / "gmail_backend.json",
        imap_credentials_path=app_data / "gmail_imap_creds.enc",
        backend_mode=mode,
        imap_email="fake@example.com" if mode == "imap" else None,
        imap_password="fake_app_password" if mode == "imap" else None,
        oauth_credentials_path=app_data / "client_secrets.json",
        oauth_token_path=app_data / "gmail_token.enc",
        oauth_legacy_token_path=app_data / "gmail_credentials.json",
        oauth_client_config=PreparedOAuthClientConfig(
            "fake_client_id.apps.googleusercontent.com",
            "fake_client_secret",
        ),
        oauth_credentials=PreparedOAuthCredentials(
            access_token="fake_access_token",
            refresh_token="fake_refresh_token",
            token_type="Bearer",
            expires_at=datetime.now() + timedelta(hours=1),
            scope="fake_scope",
        ),
    )


def test_gmail_facade_construction_is_filesystem_inert(
    qt_app,
    tmp_path,
    monkeypatch,
) -> None:
    calls: list[str] = []

    def _unexpected(name):
        def _call(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError(f"unexpected constructor filesystem call: {name}")

        return _call

    monkeypatch.setattr(Path, "exists", _unexpected("exists"))
    monkeypatch.setattr(Path, "read_text", _unexpected("read_text"))
    monkeypatch.setattr(Path, "read_bytes", _unexpected("read_bytes"))
    monkeypatch.setattr(Path, "mkdir", _unexpected("mkdir"))

    oauth = GmailOAuthManager(
        credentials_path=tmp_path / "client_secrets.json",
        token_path=tmp_path / "gmail_token.enc",
    )
    backend = GmailBackend(oauth_manager=oauth)

    assert calls == []
    assert backend.is_initialized is False
    assert oauth.is_initialized is False
    assert backend.thread() == qt_app.thread()
    assert oauth.thread() == qt_app.thread()


def test_gmail_bootstrap_reads_and_decrypts_only_on_worker(
    tmp_path,
    monkeypatch,
) -> None:
    app_data = tmp_path / "appdata"
    app_data.mkdir()
    config_path = app_data / "gmail_backend.json"
    client_path = app_data / "client_secrets.json"
    token_path = app_data / "gmail_token.enc"
    config_path.write_text(json.dumps({"mode": "imap"}), encoding="utf-8")
    client_path.write_text(
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

    oauth_payload = pickle.dumps(
        {
            "access_token": "fake_access_token",
            "refresh_token": "fake_refresh_token",
            "token_type": "Bearer",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
            "scope": "fake_scope",
        }
    )
    imap_payload = json.dumps(
        {"email": "fake@example.com", "app_password": "fake_app_password"}
    ).encode("utf-8")
    observed_threads: list[int] = []

    def _load_encrypted(path: Path):
        observed_threads.append(threading.get_ident())
        if Path(path) == token_path:
            return oauth_payload
        if Path(path) == app_data / "gmail_imap_creds.enc":
            return imap_payload
        return None

    real_read_text = Path.read_text

    def _read_text(path: Path, *args, **kwargs):
        observed_threads.append(threading.get_ident())
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr("core.gmail.gmail_bootstrap.load_encrypted", _load_encrypted)
    monkeypatch.setattr(Path, "read_text", _read_text)
    main_thread_id = threading.get_ident()
    result: list[PreparedGmailBootstrap] = []

    worker = threading.Thread(
        target=lambda: result.append(
            prepare_gmail_backend_bootstrap(
                app_data_path=app_data,
                oauth_credentials_path=client_path,
                oauth_token_path=token_path,
            )
        )
    )
    worker.start()
    worker.join(timeout=5)

    assert worker.is_alive() is False
    assert observed_threads
    assert all(thread_id != main_thread_id for thread_id in observed_threads)
    assert result[0].backend_mode == "imap"
    assert result[0].imap_email == "fake@example.com"
    assert result[0].oauth_credentials is not None
    assert result[0].oauth_credentials.access_token == "fake_access_token"


def test_legacy_migration_keeps_authenticated_snapshot_when_cleanup_is_blocked(
    tmp_path,
    monkeypatch,
) -> None:
    legacy_path = tmp_path / "gmail_credentials.json"
    token_path = tmp_path / "gmail_token.enc"
    legacy_path.write_text(
        json.dumps(
            {
                "access_token": "fake_access_token",
                "refresh_token": "fake_refresh_token",
                "token_type": "Bearer",
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
                "scope": "fake_scope",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        gmail_bootstrap_module,
        "_write_encrypted_atomic",
        lambda path, _payload: path.write_bytes(b"fake_encrypted_token"),
    )
    real_unlink = Path.unlink

    def _unlink(path: Path, *args, **kwargs):
        if path == legacy_path:
            raise PermissionError("fake file lock")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _unlink)

    credentials = gmail_bootstrap_module._migrate_legacy_oauth_credentials(
        legacy_path,
        token_path,
    )

    assert credentials is not None
    assert credentials.access_token == "fake_access_token"
    assert token_path.read_bytes() == b"fake_encrypted_token"
    assert legacy_path.exists()


def test_bootstrap_retries_legacy_cleanup_after_encrypted_load(
    tmp_path,
    monkeypatch,
) -> None:
    app_data = tmp_path / "appdata"
    app_data.mkdir()
    legacy_path = app_data / "gmail_credentials.json"
    token_path = app_data / "gmail_token.enc"
    client_path = app_data / "client_secrets.json"
    legacy_path.write_text("{}", encoding="utf-8")
    client_path.write_text(
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
    oauth_payload = pickle.dumps(
        {
            "access_token": "fake_access_token",
            "refresh_token": "fake_refresh_token",
            "token_type": "Bearer",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
            "scope": "fake_scope",
        }
    )
    monkeypatch.setattr(
        gmail_bootstrap_module,
        "load_encrypted",
        lambda path: oauth_payload if Path(path) == token_path else None,
    )

    snapshot = prepare_gmail_backend_bootstrap(
        app_data_path=app_data,
        oauth_credentials_path=client_path,
        oauth_token_path=token_path,
    )

    assert snapshot.oauth_credentials is not None
    assert legacy_path.exists() is False


def test_gmail_bootstrap_coalesces_waiters_and_commits_on_gui(
    qt_app,
    tmp_path,
    monkeypatch,
) -> None:
    manager = _QueuedIoManager()
    snapshot = _snapshot(tmp_path)
    prepare_threads: list[QThread] = []
    ui_deliveries: list[tuple[object, tuple[object, ...]]] = []
    callbacks: list[tuple[str, bool]] = []

    def _prepare():
        prepare_threads.append(QThread.currentThread())
        return snapshot

    monkeypatch.setattr("core.gmail.gmail_backend.prepare_gmail_backend_bootstrap", _prepare)
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda func, *args: ui_deliveries.append((func, args))),
    )

    oauth = GmailOAuthManager()
    backend = GmailBackend(oauth_manager=oauth)
    assert backend.ensure_initialized(
        manager,
        lambda success: callbacks.append(("first", success)),
    )
    assert backend.ensure_initialized(
        manager,
        lambda success: callbacks.append(("second", success)),
    )
    assert len(manager.tasks) == 1
    assert manager.tasks[0].category == "gmail_backend_bootstrap"

    task = manager.tasks[0]

    def _run_worker() -> None:
        value = task.func(*task.args, **task.kwargs)
        task.callback(SimpleNamespace(success=True, result=value, error=None))

    worker = threading.Thread(target=_run_worker)
    worker.start()
    worker.join(timeout=5)

    assert worker.is_alive() is False
    assert backend.is_initialized is False
    assert callbacks == []
    assert prepare_threads and prepare_threads[0] != qt_app.thread()
    assert len(ui_deliveries) == 1

    delivery, args = ui_deliveries.pop()
    delivery(*args)

    assert backend.is_initialized is True
    assert oauth.is_initialized is True
    assert backend.thread() == qt_app.thread()
    assert oauth.thread() == qt_app.thread()
    assert callbacks == [("first", True), ("second", True)]
    assert backend.is_authenticated is True
    assert backend.client is not None


def test_secret_bearing_bootstrap_repr_does_not_expose_values(tmp_path) -> None:
    snapshot = _snapshot(tmp_path)

    assert "fake_access_token" not in repr(snapshot)
    assert "fake_app_password" not in repr(snapshot)
    assert snapshot.oauth_credentials is not None
    assert "fake_access_token" not in repr(snapshot.oauth_credentials)








def test_settings_first_bootstrap_disables_actions_until_ready(
    qt_app,
    monkeypatch,
) -> None:
    from ui.tabs import widgets_tab_gmail

    class _Backend:
        is_initialized = False

        def ensure_initialized(self, _manager, callback):
            self.callback = callback
            return True

    backend = _Backend()
    tab = QWidget()
    tab._gmail_backend_body = QWidget(tab)
    tab.gmail_auth_status = QLabel(tab)
    tab.gmail_authorize_btn = QPushButton("Authorize", tab)
    tab.gmail_sign_out_btn = QPushButton("Sign Out", tab)
    refreshes: list[QWidget] = []
    monkeypatch.setattr(widgets_tab_gmail, "_get_gmail_backend", lambda: backend)
    monkeypatch.setattr(
        widgets_tab_gmail,
        "_get_gmail_thread_manager",
        lambda _tab: _QueuedIoManager(),
    )
    monkeypatch.setattr(
        widgets_tab_gmail,
        "_refresh_gmail_auth_state",
        lambda owner: refreshes.append(owner),
    )

    widgets_tab_gmail._begin_gmail_backend_bootstrap(tab)  # type: ignore[arg-type]
    assert tab._gmail_backend_body.isEnabled() is False
    assert tab.gmail_auth_status.text() == "Gmail status loading..."

    backend.is_initialized = True
    backend.callback(True)

    assert tab._gmail_backend_body.isEnabled() is True
    assert refreshes == [tab]


def test_settings_shutdown_cannot_cancel_process_owned_bootstrap(
    qt_app,
    tmp_path,
    monkeypatch,
) -> None:
    from ui.tabs import widgets_tab_gmail

    class _TabManager:
        def __init__(self) -> None:
            self.shutdown_called = False

        def shutdown(self, **_kwargs) -> None:
            self.shutdown_called = True

    process_manager = _QueuedIoManager()
    tab_manager = _TabManager()
    ui_deliveries: list[tuple[object, tuple[object, ...]]] = []
    refreshes: list[QWidget] = []
    oauth = GmailOAuthManager()
    backend = GmailBackend(oauth_manager=oauth)
    monkeypatch.setattr(
        backend,
        "get_bootstrap_thread_manager",
        lambda: process_manager,
    )
    monkeypatch.setattr(
        "core.gmail.gmail_backend.prepare_gmail_backend_bootstrap",
        lambda: _snapshot(tmp_path),
    )
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda func, *args: ui_deliveries.append((func, args))),
    )
    monkeypatch.setattr(widgets_tab_gmail, "_get_gmail_backend", lambda: backend)
    monkeypatch.setattr(
        widgets_tab_gmail,
        "_refresh_gmail_auth_state",
        lambda owner: refreshes.append(owner),
    )

    tab = QWidget()
    tab._gmail_thread_manager = tab_manager
    tab._gmail_backend_body = QWidget(tab)
    tab.gmail_auth_status = QLabel(tab)
    tab.gmail_authorize_btn = QPushButton("Authorize", tab)
    tab.gmail_sign_out_btn = QPushButton("Sign Out", tab)

    widgets_tab_gmail._begin_gmail_backend_bootstrap(tab)  # type: ignore[arg-type]
    assert len(process_manager.tasks) == 1
    assert tab_manager.shutdown_called is False

    tab_manager.shutdown(wait=False)
    task = process_manager.tasks[0]
    value = task.func(*task.args, **task.kwargs)
    task.callback(SimpleNamespace(success=True, result=value, error=None))
    delivery, args = ui_deliveries.pop()
    delivery(*args)

    assert backend.is_initialized is True
    assert refreshes == [tab]
    later_callbacks: list[bool] = []
    assert backend.ensure_initialized(
        process_manager,
        later_callbacks.append,
    )
    assert later_callbacks == [True]
