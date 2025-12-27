"""Tests for MediaWidget and centralized media controller integration.

These tests focus on:
- Widget visibility when no media is available (hidden when no track)
- Rendering of track metadata
- Artwork byte decoding into a QPixmap and margin adjustments
- Transport control delegation from MediaWidget to the controller
- DisplayWidget mouse interaction routing for Ctrl/ hard-exit modes
"""
from __future__ import annotations

import logging
import sys
import time

import pytest
from PySide6 import QtCore
from PySide6.QtCore import Qt, QEvent, QBuffer, QIODevice
from PySide6.QtGui import QMouseEvent, QPixmap, QImage
from PySide6.QtWidgets import QWidget

from core.media import media_controller as mc
from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode
from widgets.media_widget import MediaWidget
from widgets import media_widget as media_mod


class _DummyController(mc.BaseMediaController):
    def __init__(self, info: mc.MediaTrackInfo | None = None) -> None:
        self._info = info
        self.get_calls = 0
        self.play_pause_calls = 0
        self.next_calls = 0
        self.prev_calls = 0

    def get_current_track(self) -> mc.MediaTrackInfo | None:
        self.get_calls += 1
        return self._info

    def play_pause(self) -> None:
        self.play_pause_calls += 1

    def next(self) -> None:
        self.next_calls += 1

    def previous(self) -> None:
        self.prev_calls += 1


def test_noop_media_controller_safe_calls():
    """NoOpMediaController should be safe to call and always return None."""

    ctrl = mc.NoOpMediaController()
    assert ctrl.get_current_track() is None
    # These should not raise or have any side-effects beyond internal logging.
    ctrl.play_pause()
    ctrl.next()
    ctrl.previous()


def test_create_media_controller_falls_back_to_noop(monkeypatch):
    """Factory should fall back to NoOp when Windows controller is unavailable."""

    class _FakeWinController(mc.BaseMediaController):
        def __init__(self) -> None:  # pragma: no cover - trivial shim
            # Simulate an environment where the Windows controller reports
            # itself as unavailable even though construction succeeded.
            self._available = False

        def get_current_track(self):  # pragma: no cover - unused in test
            return None

        def play_pause(self) -> None:  # pragma: no cover - unused in test
            pass

        def next(self) -> None:  # pragma: no cover - unused in test
            pass

        def previous(self) -> None:  # pragma: no cover - unused in test
            pass

    monkeypatch.setattr(mc, "WindowsGlobalMediaController", _FakeWinController)

    ctrl = mc.create_media_controller()
    assert isinstance(ctrl, mc.NoOpMediaController)


def test_windows_media_controller_selects_spotify_session():
    """WindowsGlobalMediaController should prefer Spotify sessions by app id."""

    class _FakeSession:
        def __init__(self, app_id: str) -> None:
            self.source_app_user_model_id = app_id

    class _FakeMgr:
        def __init__(self, sessions):
            self._sessions = sessions

        def get_sessions(self):
            return list(self._sessions)

    class _Ctrl(mc.WindowsGlobalMediaController):
        def __init__(self) -> None:  # pragma: no cover - trivial shim
            # Skip base __init__ to avoid winrt import during tests.
            pass

    spotify = _FakeSession("Spotify.exe")
    other = _FakeSession("vlc.exe")
    mgr = _FakeMgr([other, spotify])

    ctrl = _Ctrl()
    session = ctrl._select_spotify_session(mgr)
    assert session is spotify


def test_windows_media_controller_returns_none_when_no_spotify():
    """If no Spotify session exists, selector should return None."""

    class _FakeSession:
        def __init__(self, app_id: str) -> None:
            self.source_app_user_model_id = app_id

    class _FakeMgr:
        def __init__(self, sessions):
            self._sessions = sessions

        def get_sessions(self):
            return list(self._sessions)

    class _Ctrl(mc.WindowsGlobalMediaController):
        def __init__(self) -> None:  # pragma: no cover - trivial shim
            pass

    mgr = _FakeMgr([_FakeSession("vlc.exe"), _FakeSession("chrome.exe")])
    ctrl = _Ctrl()
    session = ctrl._select_spotify_session(mgr)
    assert session is None


def test_windows_media_controller_live_spotify_track():
    """Integration check: live Windows GSMTC should yield a Spotify track.

    This test is intentionally environment-dependent and assumes:
    - Running on Windows with the WinRT projections installed, and
    - The Spotify desktop app is running on the same session.

    When those conditions are not met, the test is skipped so CI does not
    fail spuriously, but on the user's machine it will fail if the widget
    would also fail to see Spotify.
    """

    if sys.platform != "win32":
        pytest.skip("Windows-only GSMTC integration test")

    ctrl = mc.create_media_controller()
    if not isinstance(ctrl, mc.WindowsGlobalMediaController):
        pytest.skip("Windows GSMTC controller not available (NoOp or unsupported)")

    info = None
    for _ in range(5):
        info = ctrl.get_current_track()
        if info is not None:
            break
        time.sleep(0.5)

    assert info is not None, "Expected a Spotify track via GSMTC; ensure Spotify is running and playing"


def _wait_for_media_refresh(qtbot, widget: MediaWidget, timeout: int = 2000) -> None:
    """Wait until MediaWidget finishes its async refresh."""
    qtbot.waitUntil(lambda: not getattr(widget, "_refresh_in_flight", False), timeout=timeout)


def _run_refresh_cycles(qtbot, widget: MediaWidget, cycles: int = 1) -> None:
    """Trigger MediaWidget._refresh multiple times and wait for completion."""

    for _ in range(max(1, cycles)):
        widget._refresh()  # type: ignore[attr-defined]
        _wait_for_media_refresh(qtbot, widget)


def _wait_for_display_media_widget(qt_app, qtbot, display: DisplayWidget, timeout: int = 3000) -> None:
    """Wait until DisplayWidget.media_widget is created and registered."""

    def _ready() -> bool:
        qt_app.processEvents()
        return isinstance(getattr(display, "media_widget", None), MediaWidget)

    qtbot.waitUntil(_ready, timeout=timeout)


def _bootstrap_display_widget_for_tests(qt_app, qtbot, display: DisplayWidget, timeout: int = 5000) -> None:
    """Ensure DisplayWidget widget setup completes deterministically in tests."""

    qt_app.processEvents()
    try:
        display._setup_widgets()
    except Exception:
        pass

    def _widgets_ready() -> bool:
        qt_app.processEvents()
        media = getattr(display, "media_widget", None)
        wm = getattr(display, "_widget_manager", None)
        return media is not None and wm is not None

    qtbot.waitUntil(_widgets_ready, timeout=timeout)
    _wait_for_display_media_widget(qt_app, qtbot, display, timeout=timeout)


@pytest.mark.qt
def test_media_widget_placeholder_when_no_media(qt_app, qtbot, thread_manager):
    """When controller returns None, widget should remain hidden (no media)."""

    ctrl = _DummyController(info=None)
    w = MediaWidget(parent=None, controller=ctrl)
    w.set_thread_manager(thread_manager)
    qtbot.addWidget(w)
    w.resize(400, 80)

    w.start()
    qt_app.processEvents()

    # Force a single refresh and verify widget is not shown when no media is available.
    _run_refresh_cycles(qtbot, w, cycles=1)
    qt_app.processEvents()

    assert not w.isVisible()


@pytest.mark.qt
def test_media_widget_displays_metadata(qt_app, qtbot, thread_manager):
    """MediaWidget should render title/artist text block once visible."""

    info = mc.MediaTrackInfo(
        title="Song Title",
        artist="Artist Name",
        album="Album Name",
        state=mc.MediaPlaybackState.PLAYING,
    )
    ctrl = _DummyController(info=info)
    w = MediaWidget(parent=None, controller=ctrl)
    w.set_thread_manager(thread_manager)
    qtbot.addWidget(w)
    w.resize(500, 100)

    w.start()
    qt_app.processEvents()

    # First refresh primes layout (widget stays hidden)
    _run_refresh_cycles(qtbot, w, cycles=2)
    qt_app.processEvents()

    qtbot.waitUntil(lambda: w.isVisible(), timeout=2000)
    html = w.text()
    assert "Song Title" in html
    assert "Artist Name" in html


@pytest.mark.qt
def test_media_widget_hides_again_when_media_disappears(qt_app, qtbot, thread_manager):
    """Widget should hide after being visible when media goes away."""

    info = mc.MediaTrackInfo(
        title="Song Title",
        artist="Artist Name",
        album="Album Name",
        state=mc.MediaPlaybackState.PLAYING,
    )
    ctrl = _DummyController(info=info)
    w = MediaWidget(parent=None, controller=ctrl)
    w.set_thread_manager(thread_manager)
    qtbot.addWidget(w)
    w.resize(500, 100)

    # Start with media present
    w.start()
    qt_app.processEvents()
    _run_refresh_cycles(qtbot, w, cycles=2)
    qt_app.processEvents()
    qtbot.waitUntil(lambda: w.isVisible(), timeout=2000)

    # Now simulate media disappearing
    ctrl._info = None
    w._refresh()  # type: ignore[attr-defined]
    _wait_for_media_refresh(qtbot, w)
    qt_app.processEvents()
    assert not w.isVisible()


@pytest.mark.qt
def test_media_widget_decodes_artwork_and_adjusts_margins(qt_app, qtbot, thread_manager):
    """Artwork bytes should be decoded into a pixmap and margins updated."""

    # Create a tiny in-memory PNG for artwork
    img = QImage(8, 8, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.red)
    pm = QPixmap.fromImage(img)

    # Encode to PNG bytes using an in-memory buffer so loadFromData can decode it.
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.ReadWrite)
    assert pm.save(buf, "PNG")
    png_bytes = bytes(buf.data())

    info = mc.MediaTrackInfo(
        title="Artwork Test",
        artist="Artist",
        album="Album",
        state=mc.MediaPlaybackState.PLAYING,
        artwork=png_bytes,
    )

    ctrl = _DummyController(info=info)
    w = MediaWidget(parent=None, controller=ctrl)
    w.set_thread_manager(thread_manager)
    qtbot.addWidget(w)
    w.resize(400, 120)

    w.start()
    qt_app.processEvents()

    # Capture initial margins, then refresh twice and ensure the right
    # margin grows to the configured footprint (artwork size + padding).
    initial_margins = w.contentsMargins()

    _run_refresh_cycles(qtbot, w, cycles=2)
    qt_app.processEvents()

    expected_right_margin = max(w._artwork_size + 40, 60)
    updated_margins = w.contentsMargins()
    assert expected_right_margin > initial_margins.right()
    assert updated_margins.right() == expected_right_margin


@pytest.mark.qt
def test_media_widget_warns_when_thread_manager_missing(qt_app, qtbot, caplog):
    """MediaWidget should log an error and stay disabled without a ThreadManager."""

    ctrl = _DummyController(info=None)
    w = MediaWidget(parent=None, controller=ctrl)
    qtbot.addWidget(w)
    w.resize(400, 80)

    with caplog.at_level(logging.ERROR):
        w.start()
        qt_app.processEvents()

    assert not getattr(w, "_enabled", False)
    assert any("Missing ThreadManager" in record.getMessage() for record in caplog.records)


@pytest.mark.qt
def test_media_widget_starts_fade_in_when_artwork_appears(qt_app, qtbot, thread_manager):
    """Artwork appearing should trigger a fade-in animation."""

    img = QImage(8, 8, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.blue)
    pm = QPixmap.fromImage(img)

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.ReadWrite)
    assert pm.save(buf, "PNG")
    png_bytes = bytes(buf.data())

    info = mc.MediaTrackInfo(
        title="Artwork Fade Test",
        artist="Artist",
        album="Album",
        state=mc.MediaPlaybackState.PLAYING,
        artwork=png_bytes,
    )

    ctrl = _DummyController(info=None)
    w = MediaWidget(parent=None, controller=ctrl)
    w.set_thread_manager(thread_manager)
    qtbot.addWidget(w)
    w.resize(400, 120)

    # First refresh with no media keeps widget hidden and no artwork.
    w.start()
    qt_app.processEvents()
    ctrl._info = None
    _run_refresh_cycles(qtbot, w, cycles=1)
    qt_app.processEvents()
    assert not w.isVisible()

    # Now provide artwork-bearing media and refresh once; this should
    # create an artwork pixmap and start a fade-in (opacity starts at 0).
    ctrl._info = info
    _run_refresh_cycles(qtbot, w, cycles=2)
    qt_app.processEvents()

    qtbot.waitUntil(lambda: getattr(w, "_artwork_anim", None) is not None, timeout=2000)
    assert getattr(w, "_artwork_anim", None) is not None
    assert 0.0 <= getattr(w, "_artwork_opacity", 1.0) <= 0.4


def test_media_widget_transport_delegates_to_controller():
    """Transport methods should delegate to the underlying controller."""

    info = mc.MediaTrackInfo(title="Song", state=mc.MediaPlaybackState.PLAYING)
    ctrl = _DummyController(info=info)
    w = MediaWidget(parent=QWidget(), controller=ctrl)

    w.play_pause()
    w.next_track()
    w.previous_track()

    assert ctrl.play_pause_calls == 1
    assert ctrl.next_calls == 1
    assert ctrl.prev_calls == 1


@pytest.mark.qt
def test_display_widget_ctrl_click_routes_to_media_widget(
    qt_app, settings_manager, qtbot, monkeypatch, thread_manager
):
    """Ctrl-held click over media widget should trigger play/pause, not exit."""

    fake_info = mc.MediaTrackInfo(title="Track", state=mc.MediaPlaybackState.PLAYING)
    fake_ctrl = _DummyController(info=fake_info)

    monkeypatch.setattr(media_mod, "create_media_controller", lambda: fake_ctrl)

    settings_manager.set(
        "widgets",
        {
            "media": {
                "enabled": True,
                "position": "Bottom Left",
                "monitor": "ALL",
            }
        },
    )

    w = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
        thread_manager=thread_manager,
    )
    qtbot.addWidget(w)
    w.resize(800, 600)
    w.show()
    _bootstrap_display_widget_for_tests(qt_app, qtbot, w)
    qt_app.processEvents()

    # Ensure media widget is visible before clicking
    qtbot.waitUntil(lambda: w.media_widget is not None and w.media_widget.isVisible(), timeout=2000)

    # Simulate global Ctrl-held interaction mode
    from rendering import display_widget as display_mod

    display_mod.DisplayWidget._global_ctrl_held = True  # type: ignore[attr-defined]
    w._ctrl_held = True  # type: ignore[attr-defined]
    try:
        w._coordinator.set_ctrl_held(True)
    except Exception:
        pass

    handler = getattr(w, "_input_handler", None)
    assert handler is not None

    media = w.media_widget
    local_controls_pos = QtCore.QPoint(media.width() // 2, media.height() - 10)
    pos = media.mapToParent(local_controls_pos)
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QtCore.QPointF(pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
    )

    handled, _, _ = handler.route_widget_click(
        event,
        getattr(w, "spotify_volume_widget", None),
        w.media_widget,
        getattr(w, "reddit_widget", None),
        getattr(w, "reddit2_widget", None),
    )
    assert handled
    assert fake_ctrl.play_pause_calls == 1
    # Ensure screensaver exit was not requested
    assert not getattr(w, "_exiting", False)

    display_mod.DisplayWidget._global_ctrl_held = False  # type: ignore[attr-defined]
    try:
        w._coordinator.set_ctrl_held(False)
    except Exception:
        pass
    w._ctrl_held = False  # type: ignore[attr-defined]


@pytest.mark.qt
def test_display_widget_hard_exit_click_routes_to_media_widget(
    qt_app, settings_manager, qtbot, monkeypatch, thread_manager
):
    """Hard-exit mode should also allow media widget interaction without exit."""

    fake_info = mc.MediaTrackInfo(title="Track", state=mc.MediaPlaybackState.PLAYING)
    fake_ctrl = _DummyController(info=fake_info)

    monkeypatch.setattr(media_mod, "create_media_controller", lambda: fake_ctrl)

    settings_manager.set(
        "widgets",
        {
            "media": {
                "enabled": True,
                "position": "Bottom Left",
                "monitor": "ALL",
            }
        },
    )
    settings_manager.set("input.hard_exit", True)

    w = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
        thread_manager=thread_manager,
    )
    qtbot.addWidget(w)
    w.resize(800, 600)
    w.show()
    _bootstrap_display_widget_for_tests(qt_app, qtbot, w)
    qt_app.processEvents()

    qtbot.waitUntil(lambda: w.media_widget is not None and w.media_widget.isVisible(), timeout=2000)

    handler = getattr(w, "_input_handler", None)
    assert handler is not None

    geom = w.media_widget.geometry()
    pos = QtCore.QPoint(geom.center().x(), geom.bottom() - 10)
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QtCore.QPointF(pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    handled, _, _ = handler.route_widget_click(
        event,
        getattr(w, "spotify_volume_widget", None),
        w.media_widget,
        getattr(w, "reddit_widget", None),
        getattr(w, "reddit2_widget", None),
    )
    assert handled
    assert fake_ctrl.play_pause_calls == 1
    assert not getattr(w, "_exiting", False)
