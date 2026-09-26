"""Focused parity bars for presentation-neutral Guided Setup account operations."""
from __future__ import annotations

from types import SimpleNamespace

from core.account_setup import controllers


def test_steam_saved_connection_status_is_non_decrypting_and_reports_callback(monkeypatch) -> None:
    seen = []
    status = controllers.SteamConnectionController(
        seen.append,
        storage_status_reader=lambda: SimpleNamespace(
            storage_available=True, has_credentials=True, message="unused"
        ),
    ).inspect_saved_connection(None, explicit=True)

    assert status.state == "connected"
    assert status.feedback == "Connected Successfully"
    assert seen == [status]


def test_steam_controller_validates_before_dpapi_save(monkeypatch) -> None:
    saved = []
    emitted = []
    monkeypatch.setattr(
        controllers,
        "validate_connection",
        lambda **_kwargs: SimpleNamespace(status=controllers.SteamResultStatus.SUCCESS),
    )
    monkeypatch.setattr(controllers, "save_credentials", saved.append)

    status = controllers.SteamConnectionController(emitted.append).test_and_save_credentials(
        "abcdef0123456789abcdef0123456789", "76561197960265728"
    )

    assert status.state == "connected"
    assert len(saved) == 1
    assert saved[0].profile_identifier == "76561197960265728"
    assert emitted == [status]



def test_steam_controller_drops_verified_save_after_lifetime_closes(monkeypatch) -> None:
    saved = []
    emitted = []
    monkeypatch.setattr(
        controllers,
        "validate_connection",
        lambda **_kwargs: SimpleNamespace(status=controllers.SteamResultStatus.SUCCESS),
    )
    monkeypatch.setattr(controllers, "save_credentials", saved.append)
    lifetime = iter((True, False))

    status = controllers.SteamConnectionController(emitted.append).test_and_save_credentials(
        "abcdef0123456789abcdef0123456789",
        "76561197960265728",
        is_current=lambda: next(lifetime),
    )

    assert status.state == "cancelled"
    assert saved == []
    assert emitted == []

def test_gmail_imap_controller_only_saves_after_a_successful_test() -> None:
    events = []

    class Backend:
        status_text = "Enter email & app password"

        def test_imap_credentials(self, _email, _password):
            return False

        def save_imap_credentials(self, *_args):
            events.append("save")

    result = controllers.GmailConnectionController().test_imap(
        Backend(), "user@example.test", "application password"
    )

    assert result.success is False
    assert events == []


def test_gmail_verification_and_gui_commit_are_separate():
    import pytest
    calls = []
    backend = SimpleNamespace(test_imap_credentials=lambda *args: True,
                              save_imap_credentials=lambda *args: calls.append(args))
    controller = controllers.GmailConnectionController()
    verification = controller.test_imap(backend, "user@example.test", "fake app password")
    assert calls == []
    controller.save_verified_imap(backend, "user@example.test", "fake app password", verification)
    assert calls == [("user@example.test", "fake app password")]
    with pytest.raises(ValueError):
        controller.save_verified_imap(backend, "other@example.test", "wrong", controllers.GmailOperationResult(False,"failed"))
    assert len(calls) == 1


def test_gmail_storage_failure_keeps_prior_backend_credentials(qapp, monkeypatch, tmp_path):
    import pytest
    import core.gmail.gmail_backend as module
    backend = module.GmailBackend()
    backend._imap_email, backend._imap_password = "prior@example.test", "prior password"
    backend._imap_creds_path = tmp_path / "test.enc"
    def fail(*args): raise OSError("test storage unavailable")
    monkeypatch.setattr(module, "save_encrypted", fail)
    with pytest.raises(RuntimeError, match="Encrypted Gmail storage failed"):
        backend.save_imap_credentials("replacement@example.test", "replacement password")
    assert backend._imap_email == "prior@example.test"
    assert backend._imap_password == "prior password"
    backend.deleteLater()
