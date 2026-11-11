"""Linux branches of shared runtime owners (links, helper, desktop, folders, credentials, orbit).

Linux-only (never collected off Linux); each owner's Windows contract stays in its own test file.
"""
from __future__ import annotations

from unittest.mock import patch

from PySide6.QtCore import QRectF

import main
from core.sources.folder_paths import display_folder_path, same_folder, without_folder
from core.steam.links import store_target
from core.windows.desktop_context import is_interactive_user_desktop


class _FakeWin32:
    def __init__(self, name):
        self.name = name

    def current_thread_desktop_name(self):
        return self.name


@patch("core.windows.secure_url_launcher.reddit_helper_runtime.ensure_helper_runtime")
@patch("core.windows.secure_url_launcher.reddit_helper_bridge")
@patch("core.windows.secure_url_launcher.QDesktopServices.openUrl", return_value=True)
def test_linux_saver_opens_links_directly_and_never_touches_the_windows_helper(
    mock_open,
    mock_bridge,
    mock_ensure_helper,
    monkeypatch,
) -> None:
    from core.windows import secure_url_launcher

    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", False)
    monkeypatch.setenv("SESSIONNAME", "Winlogon")  # meaningless on Linux

    assert secure_url_launcher.open_url("https://example.com", source="reddit") is True
    assert secure_url_launcher.open_steam_target(store_target(570), source="steam") is True
    assert mock_open.call_count == 2
    assert mock_open.call_args_list[1].args[0].toString().startswith("steam://")
    mock_bridge.is_bridge_available.assert_not_called()
    mock_bridge.enqueue_url.assert_not_called()
    mock_ensure_helper.assert_not_called()


def test_linux_defaults_to_the_engine_worker_and_in_process_stays_a_choice(monkeypatch):
    # Native core P2, H3 (11 Nov 2026): the engine worker is the default on Linux too (the operator's 8 Nov decision:
    # no Linux machine, no proving step). --viz-in-process chooses the in-process path and wins over
    # --viz-engine-worker. This asserts the SELECTION. Whether the worker path runs on Linux (the named wake pipe,
    # forkserver, the mapping's tracker, Pulse capture in the worker) is shown by the worker tests when this suite
    # runs on Linux, not by this test; until such a run is recorded in Linux_Plan.md it is unverified.
    from core.diagnostics import experiment_flags as ef

    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", False)
    saved = ef.active_experiment_flags()
    try:
        ef.override_active_flags_for_testing(None)
        assert ef.visualizer_engine_worker_platform_default() is True
        assert ef.visualizer_engine_worker_admitted() is True
        ef.activate_experiment_flags(ef.parse_experiment_flags(["main.py", "--viz-in-process", "/s"]))
        assert ef.visualizer_engine_worker_admitted() is False
        ef.activate_experiment_flags(ef.parse_experiment_flags(["main.py", "--viz-engine-worker", "--viz-in-process"]))
        assert ef.visualizer_engine_worker_admitted() is False
    finally:
        ef.override_active_flags_for_testing(saved)


def test_linux_never_schedules_the_windows_helper_or_writes_its_breadcrumb(monkeypatch):
    import core.windows.reddit_helper_installer as installer

    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", False)
    events: list[str] = []
    monkeypatch.setattr(installer, "_log_helper_event", events.append)

    class _Engine:
        thread_manager = object()

    assert main._schedule_runtime_reddit_helper_session(_Engine()) is False
    assert events == []
    assert getattr(_Engine, "_reddit_helper_session_timer", None) is None


def test_linux_session_is_the_users_interactive_desktop(monkeypatch):
    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", False)
    assert is_interactive_user_desktop() is True
    # An explicit adapter is still authoritative (fake-Win32 tests on any OS).
    assert is_interactive_user_desktop(_FakeWin32("Winlogon")) is False


def test_posix_folder_spelling_ignores_trailing_separators_but_keeps_case() -> None:
    assert same_folder("/home/me/Wallpapers/", "/home/me/Wallpapers")
    assert display_folder_path("/home/me/Wallpapers/") == "/home/me/Wallpapers"
    assert not same_folder("/home/me/wallpapers", "/home/me/Wallpapers")
    assert without_folder(["/home/me/Wallpapers/", "/srv/Other"], "/home/me/Wallpapers") == ["/srv/Other"]


def test_plain_credential_file_is_owner_only(tmp_path):
    import stat

    from core.windows.dpapi import load_encrypted, save_encrypted

    target = tmp_path / "imap.bin"
    target.write_bytes(b"old")
    target.chmod(0o644)  # a pre-existing world-readable file is tightened too
    save_encrypted(target, b"secret")
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert load_encrypted(target) == b"secret"


def test_orbit_capture_is_a_qt_grab_without_confinement(monkeypatch):
    from rendering.quick import pointer_capture

    class _Window:
        def __init__(self):
            self.grab_calls = []

        def setMouseGrabEnabled(self, enabled):
            self.grab_calls.append(enabled)
            return True

    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", False)
    window = _Window()
    capture = pointer_capture.new_orbit_capture(window)
    assert isinstance(capture, pointer_capture.QtOrbitCapture)
    assert not capture.cleanup_pending
    capture.acquire(QRectF(0., 0., 10., 10.))
    assert capture.cleanup_pending and window.grab_calls == [True]
    capture.release()
    assert not capture.cleanup_pending and window.grab_calls == [True, False]


def test_studio_conceals_settings_without_ending_its_modal_loop(qt_app):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog

    from ui.studio.presence import WindowPresence

    dialog = QDialog()
    dialog.setGeometry(100, 100, 300, 200)
    presence = WindowPresence(dialog)
    seen = []

    def conceal():
        presence.conceal()
        seen.append((dialog.isVisible(), dialog.windowOpacity(), dialog.geometry().x() < -10000))
        QTimer.singleShot(50, reveal)

    def reveal():
        presence.reveal()
        seen.append((dialog.isVisible(), dialog.windowOpacity(), dialog.geometry().topLeft().toTuple()))
        dialog.accept()

    QTimer.singleShot(50, conceal)
    assert dialog.exec() == QDialog.DialogCode.Accepted  # the modal loop survived concealment
    assert seen == [(True, 0.0, True), (True, 1.0, (100, 100))]
    assert presence.reveal_count == 1
