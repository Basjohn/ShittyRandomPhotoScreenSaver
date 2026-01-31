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
from types import SimpleNamespace
import weakref

import pytest
from PySide6 import QtCore
from PySide6.QtCore import Qt, QEvent, QBuffer, QIODevice
from PySide6.QtGui import QMouseEvent, QPixmap, QImage
from PySide6.QtWidgets import QWidget

from core.media import media_controller as mc
from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode
from widgets.media_widget import MediaWidget, MediaPosition
from widgets import media_widget as media_mod


logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def _reset_media_widget_class_state():
    """Ensure shared MediaWidget caches don't leak between tests."""
    MediaWidget._shared_last_valid_info = None
    MediaWidget._shared_last_valid_info_ts = 0.0
    timer = getattr(MediaWidget, "_shared_feedback_timer", None)
    try:
        if timer is not None and timer.isActive():
            timer.stop()
    except Exception:
        pass
    MediaWidget._shared_feedback_timer = None
    MediaWidget._shared_feedback_events = {}
    MediaWidget._instances = weakref.WeakSet()

    original_invalidate = getattr(MediaWidget, "_invalidate_controls_layout", None)

    def _invalidate_controls_layout(self):
        setattr(self, "_controls_layout_cache", None)

    MediaWidget._invalidate_controls_layout = _invalidate_controls_layout  # type: ignore[attr-defined]

    def _log_feedback_metric(self, *, phase: str, key: str, source: str, event_id: str) -> None:
        message = (
            "[MEDIA_WIDGET][FEEDBACK] phase=%s key=%s source=%s event=%s"
            % (phase, key, source, event_id)
        )
        logger.debug(message)

    MediaWidget._log_feedback_metric = _log_feedback_metric  # type: ignore[attr-defined]

    yield

    if original_invalidate is not None:
        MediaWidget._invalidate_controls_layout = original_invalidate  # type: ignore[attr-defined]
    else:
        try:
            delattr(MediaWidget, "_invalidate_controls_layout")
        except AttributeError:
            pass


@pytest.fixture
def mock_parent(qtbot):
    """Create a parent widget for MediaWidget unit-style tests."""
    parent = QWidget()
    parent.resize(1920, 1080)
    qtbot.addWidget(parent)
    return parent


@pytest.fixture
def fade_ready_parent(qtbot):
    """Parent that immediately runs overlay fade starters."""

    class _FadeParent(QWidget):
        def request_overlay_fade_sync(self, _overlay_name, starter):
            starter()

    parent = _FadeParent()
    parent.resize(1920, 1080)
    qtbot.addWidget(parent)
    return parent


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

    for attr_name in ("media_widget", "reddit_widget", "reddit2_widget"):
        widget = getattr(display, attr_name, None)
        if widget is None:
            continue
        try:
            widget.cleanup()
        except Exception:
            pass

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


def _create_test_artwork_bytes(size: int = 100) -> bytes:
    """Create a small ARGB PNG blob for in-memory artwork tests."""
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.red)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


@pytest.mark.qt
def test_media_widget_placeholder_when_no_media(qt_app, qtbot, thread_manager, fade_ready_parent):
    """When controller returns None, widget should remain hidden (no media)."""

    ctrl = _DummyController(info=None)
    w = MediaWidget(parent=fade_ready_parent, controller=ctrl)
    w.set_thread_manager(thread_manager)
    w.resize(400, 80)

    w.start()
    qt_app.processEvents()

    # Force a single refresh and verify widget never recorded a valid track.
    _run_refresh_cycles(qtbot, w, cycles=1)
    qt_app.processEvents()

    assert not getattr(w, "_has_seen_first_track", False)
    assert not getattr(w, "_fade_in_completed", False)


@pytest.mark.qt
def test_media_widget_displays_metadata(qt_app, qtbot, thread_manager, fade_ready_parent):
    """MediaWidget should render title/artist text block once visible."""

    info = mc.MediaTrackInfo(
        title="Song Title",
        artist="Artist Name",
        album="Album Name",
        state=mc.MediaPlaybackState.PLAYING,
    )
    ctrl = _DummyController(info=info)
    w = MediaWidget(parent=fade_ready_parent, controller=ctrl)
    w.set_thread_manager(thread_manager)
    w.resize(500, 100)

    w.start()
    qt_app.processEvents()

    # First refresh primes layout (widget stays hidden)
    _run_refresh_cycles(qtbot, w, cycles=2)
    qt_app.processEvents()

    qtbot.waitUntil(lambda: getattr(w, "_has_seen_first_track", False), timeout=2500)
    html = w.text()
    assert "Song Title" in html
    assert "Artist Name" in html


@pytest.mark.qt
def test_media_widget_hides_again_when_media_disappears(qt_app, qtbot, thread_manager, fade_ready_parent):
    """Widget should hide after being visible when media goes away."""

    info = mc.MediaTrackInfo(
        title="Song Title",
        artist="Artist Name",
        album="Album Name",
        state=mc.MediaPlaybackState.PLAYING,
    )
    ctrl = _DummyController(info=info)
    w = MediaWidget(parent=fade_ready_parent, controller=ctrl)
    w.set_thread_manager(thread_manager)
    w.resize(500, 100)

    # Start with media present
    w.start()
    qt_app.processEvents()
    _run_refresh_cycles(qtbot, w, cycles=2)
    qt_app.processEvents()
    qtbot.waitUntil(lambda: getattr(w, "_fade_in_completed", False), timeout=2500)

    # Now simulate media disappearing
    ctrl._info = None
    w._refresh()  # type: ignore[attr-defined]
    _wait_for_media_refresh(qtbot, w)
    qt_app.processEvents()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=2500)


@pytest.mark.qt
def test_media_widget_decodes_artwork_and_adjusts_margins(qt_app, qtbot, thread_manager, fade_ready_parent):
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

    ctrl = _DummyController(info=None)
    w = MediaWidget(parent=fade_ready_parent, controller=ctrl)
    w.set_thread_manager(thread_manager)
    w.resize(400, 120)

    w.start()
    qt_app.processEvents()

    # Capture initial margins, then refresh twice and ensure the right
    # margin grows to the configured footprint (artwork size + padding).
    initial_margins = w.contentsMargins()

    # First refresh with no media keeps widget hidden and no artwork.
    _run_refresh_cycles(qtbot, w, cycles=1)
    qt_app.processEvents()
    assert not w.isVisible()

    # Now provide artwork-bearing media and refresh once.
    ctrl._info = info
    _run_refresh_cycles(qtbot, w, cycles=2)
    qt_app.processEvents()

    # Artwork pixmap should be decoded synchronously.
    assert getattr(w, "_artwork_pixmap", None) is not None

    expected_right_margin = max(w._artwork_size + 40, 60)
    updated_margins = w.contentsMargins()
    assert expected_right_margin >= initial_margins.right()
    assert updated_margins.right() == expected_right_margin
    assert updated_margins.right() > initial_margins.right()


@pytest.mark.qt
def test_media_widget_emits_signal_on_first_track(qt_app, qtbot, thread_manager):
    """First snapshot should emit media_updated even before fade-in occurs."""

    info = mc.MediaTrackInfo(
        title="Signal Test",
        artist="Artist",
        album="Album",
        state=mc.MediaPlaybackState.PLAYING,
    )
    ctrl = _DummyController(info=info)
    widget = MediaWidget(parent=None, controller=ctrl)
    qtbot.addWidget(widget)
    widget.set_thread_manager(thread_manager)

    widget.start()
    qt_app.processEvents()

    # First refresh should emit the signal even though the widget remains hidden.
    with qtbot.waitSignal(widget.media_updated, timeout=2000) as blocker:
        _run_refresh_cycles(qtbot, widget, cycles=1)
        qt_app.processEvents()

    payload = blocker.args[0]
    assert payload["title"] == "Signal Test"
    assert payload["state"] == mc.MediaPlaybackState.PLAYING.value


def test_media_widget_warns_when_thread_manager_missing(qt_app, qtbot, caplog, fade_ready_parent):
    """MediaWidget should log an error and stay disabled without a ThreadManager."""

    ctrl = _DummyController(info=None)
    w = MediaWidget(parent=fade_ready_parent, controller=ctrl)
    w.resize(400, 80)

    with caplog.at_level(logging.ERROR):
        w.start()
        qt_app.processEvents()

    assert not getattr(w, "_enabled", False)
    assert any("Missing ThreadManager" in record.getMessage() for record in caplog.records)


@pytest.mark.qt
def test_media_widget_logs_when_timer_cannot_start(qtbot, caplog):
    """_ensure_timer should log a timer warning when no ThreadManager is present."""

    parent = QWidget()
    w = MediaWidget(parent=parent)

    with caplog.at_level(logging.WARNING):
        w._ensure_timer()

    assert any("[MEDIA_WIDGET][TIMER]" in record.getMessage() for record in caplog.records)


@pytest.mark.qt
def test_media_widget_ensure_timer_uses_thread_manager(monkeypatch, qtbot):
    """Once a ThreadManager is injected, _ensure_timer should create a polling handle."""

    parent = QWidget()
    w = MediaWidget(parent=parent)
    w._thread_manager = object()

    calls = {}

    class _FakeHandle:
        def __init__(self):
            self._timer = SimpleNamespace(isActive=lambda: True)

        def stop(self):
            calls["stopped"] = True

    def fake_create(widget, interval, callback, description=""):
        calls["args"] = (widget, interval, description)
        return _FakeHandle()

    monkeypatch.setattr(media_mod, "create_overlay_timer", fake_create)

    w._ensure_timer()

    assert calls["args"][0] is w
    assert calls["args"][1] == w._poll_intervals[0]
    assert w._update_timer_handle is not None


@pytest.mark.qt
def test_media_widget_set_thread_manager_restarts_timer(monkeypatch, qtbot):
    """set_thread_manager should force a fresh timer when the widget is enabled."""

    parent = QWidget()
    w = MediaWidget(parent=parent)
    qtbot.addWidget(parent)

    w._enabled = True
    w._thread_manager = object()  # Simulate previous manager already present

    stop_called = {}

    class _FakeHandle:
        def __init__(self):
            self._timer = SimpleNamespace(isActive=lambda: True)

        def stop(self):
            stop_called["stop"] = True

    w._update_timer_handle = _FakeHandle()

    create_calls = {}

    def fake_create(widget, interval, callback, description=""):
        create_calls["called"] = True
        return _FakeHandle()

    monkeypatch.setattr(media_mod, "create_overlay_timer", fake_create)

    new_tm = object()
    w.set_thread_manager(new_tm)

    assert stop_called.get("stop") is True
    assert create_calls.get("called") is True
    assert w._thread_manager is new_tm


@pytest.mark.qt
def test_media_widget_starts_fade_in_when_artwork_appears(qt_app, qtbot, thread_manager, fade_ready_parent):
    """Artwork appearing after an initial track should trigger a fade-in animation."""

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
    w = MediaWidget(parent=fade_ready_parent, controller=ctrl)
    w.set_thread_manager(thread_manager)
    w.resize(400, 120)

    w.start()
    qt_app.processEvents()

    # First track without artwork completes the baseline fade.
    ctrl._info = mc.MediaTrackInfo(
        title="Baseline",
        artist="Artist",
        album="Album",
        state=mc.MediaPlaybackState.PLAYING,
    )
    _run_refresh_cycles(qtbot, w, cycles=2)
    qt_app.processEvents()
    qtbot.waitUntil(lambda: getattr(w, "_fade_in_completed", False), timeout=2500)

    # Now provide artwork-bearing media and refresh; this should trigger an artwork fade.
    ctrl._info = info
    _run_refresh_cycles(qtbot, w, cycles=2)
    qt_app.processEvents()

    def _fade_started() -> bool:
        anim = getattr(w, "_artwork_anim", None)
        opacity = getattr(w, "_artwork_opacity", 1.0)
        return anim is not None or opacity < 0.99

    qtbot.waitUntil(_fade_started, timeout=2500)
    assert getattr(w, "_artwork_pixmap", None) is not None


@pytest.mark.qt
class TestMediaWidgetArtworkLoading:
    """Focused tests for MediaWidget artwork/diff gating internals."""

    def test_artwork_decoded_on_first_track(self, mock_parent, qtbot):
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)

        info = mc.MediaTrackInfo(
            title="Test Song",
            artist="Test Artist",
            album="Album",
            state=mc.MediaPlaybackState.PLAYING,
            artwork=_create_test_artwork_bytes(),
        )

        widget._update_display(info)
        assert widget._artwork_pixmap is not None
        assert not widget._artwork_pixmap.isNull()
        assert widget._has_seen_first_track is True

    def test_artwork_decoded_when_paused(self, mock_parent, qtbot):
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)

        info = mc.MediaTrackInfo(
            title="Paused Song",
            artist="Artist",
            album="Album",
            state=mc.MediaPlaybackState.PAUSED,
            artwork=_create_test_artwork_bytes(),
        )

        widget._update_display(info)
        assert widget._artwork_pixmap is not None
        assert not widget._artwork_pixmap.isNull()

    def test_first_track_sets_has_seen_flag(self, mock_parent, qtbot):
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        assert widget._has_seen_first_track is False

        info = mc.MediaTrackInfo(title="Test", artist="Artist", state=mc.MediaPlaybackState.PLAYING)
        widget._update_display(info)
        assert widget._has_seen_first_track is True

    def test_content_margins_set_on_first_track(self, mock_parent, qtbot):
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        info = mc.MediaTrackInfo(
            title="Long Song Title",
            artist="Artist",
            state=mc.MediaPlaybackState.PLAYING,
            artwork=_create_test_artwork_bytes(),
        )

        expected_bottom = widget._controls_row_margin()
        widget._update_display(info)
        margins = widget.contentsMargins()
        expected_right_margin = max(widget._artwork_size + 40, 60)
        assert margins.right() == expected_right_margin
        assert margins.bottom() == expected_bottom


@pytest.mark.qt
class TestMediaWidgetDiffGating:
    def test_diff_gating_allows_updates_before_fade_complete(self, mock_parent, qtbot):
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)

        info = mc.MediaTrackInfo(title="Test Song", artist="Artist", state=mc.MediaPlaybackState.PLAYING)
        widget._fade_in_completed = False
        widget._has_seen_first_track = True
        widget._last_track_identity = widget._compute_track_identity(info)

        widget._update_display(info)
        assert widget._last_info is not None

    def test_diff_gating_skips_after_fade_complete(self, mock_parent, qtbot):
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)

        info = mc.MediaTrackInfo(title="Test Song", artist="Artist", state=mc.MediaPlaybackState.PLAYING)
        widget._update_display(info)
        widget._fade_in_completed = True
        widget._last_track_identity = widget._compute_track_identity(info)

        widget._update_display(info)
        assert widget._fade_in_completed is True

    def test_diff_gating_allows_track_change(self, mock_parent, qtbot):
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)

        info1 = mc.MediaTrackInfo(title="Song 1", artist="Artist 1", state=mc.MediaPlaybackState.PLAYING)
        widget._update_display(info1)
        widget._fade_in_completed = True

        info2 = mc.MediaTrackInfo(title="Song 2", artist="Artist 2", state=mc.MediaPlaybackState.PLAYING)
        widget._update_display(info2)
        assert widget._last_track_identity == widget._compute_track_identity(info2)

    def test_track_identity_includes_state(self, mock_parent, qtbot):
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)

        info_playing = mc.MediaTrackInfo(title="Test", artist="Artist", state=mc.MediaPlaybackState.PLAYING)
        info_paused = mc.MediaTrackInfo(title="Test", artist="Artist", state=mc.MediaPlaybackState.PAUSED)

        assert widget._compute_track_identity(info_playing) != widget._compute_track_identity(info_paused)


@pytest.mark.qt
class TestMediaWidgetIdleDetection:
    def test_idle_detection_tracks_none_results(self, mock_parent, qtbot):
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        assert widget._consecutive_none_count == 0
        assert widget._is_idle is False

        for _ in range(5):
            widget._update_display(None)

        assert widget._consecutive_none_count >= 5
        assert widget._is_idle is False

    def test_idle_mode_entered_after_threshold(self, mock_parent, qtbot):
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)

        for _ in range(widget._idle_threshold + 2):
            widget._update_display(None)

        assert widget._is_idle is True

    def test_idle_mode_exits_on_track(self, mock_parent, qtbot):
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)

        for _ in range(widget._idle_threshold + 2):
            widget._update_display(None)

        assert widget._is_idle is True

        info = mc.MediaTrackInfo(title="Song", artist="Artist", state=mc.MediaPlaybackState.PLAYING)
        widget._update_display(info)

        assert widget._is_idle is False
        assert widget._consecutive_none_count == 0


@pytest.mark.qt
def test_media_widget_transport_delegates_to_controller(qtbot, fade_ready_parent):
    """Transport methods should delegate to the underlying controller."""

    info = mc.MediaTrackInfo(title="Song", state=mc.MediaPlaybackState.PLAYING)
    ctrl = _DummyController(info=info)
    w = MediaWidget(parent=fade_ready_parent, controller=ctrl)

    w.play_pause()
    w.next_track()
    w.previous_track()

    assert ctrl.play_pause_calls == 1
    assert ctrl.next_calls == 1
    assert ctrl.prev_calls == 1


@pytest.mark.qt
def test_media_widget_media_key_triggers_optimistic_state(mock_parent, qtbot, monkeypatch):
    """Media key events (execute=False) should still flip the glyph immediately."""

    widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)

    widget._enabled = True
    widget._has_seen_first_track = True
    widget._fade_in_completed = True
    widget._last_info = mc.MediaTrackInfo(
        title="Song",
        artist="Artist",
        state=mc.MediaPlaybackState.PLAYING,
        can_play_pause=True,
    )

    observed_states: list[mc.MediaPlaybackState | None] = []

    def fake_update_display(info):
        observed_states.append(getattr(info, "state", None))
        widget._last_info = info

    monkeypatch.setattr(widget, "_update_display", fake_update_display)

    pending_states: list[mc.MediaPlaybackState] = []

    def fake_apply_pending(state):
        pending_states.append(state)
        widget._pending_state_override = state

    monkeypatch.setattr(widget, "_apply_pending_state_override", fake_apply_pending)

    widget.handle_transport_command("play", source="media_key", execute=False)

    assert observed_states, "Expected optimistic update to run"
    assert observed_states[-1] == mc.MediaPlaybackState.PAUSED
    assert pending_states == [mc.MediaPlaybackState.PAUSED]


@pytest.mark.qt
def test_display_widget_ctrl_click_routes_to_media_widget(
    qt_app, settings_manager, qtbot, monkeypatch, thread_manager
):
    """Ctrl-held click over media widget should trigger play/pause, not exit."""

    fake_info = mc.MediaTrackInfo(title="Track", state=mc.MediaPlaybackState.PLAYING)
    fake_ctrl = _DummyController(info=fake_info)

    monkeypatch.setattr(media_mod, "create_media_controller", lambda: fake_ctrl)
    from rendering import widget_manager as widget_manager_mod

    def _immediate_fade(self, overlay_name, starter):
        starter()

    monkeypatch.setattr(
        widget_manager_mod.WidgetManager,
        "request_overlay_fade_sync",
        _immediate_fade,
    )

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
    # Detach auxiliary overlays so InputHandler routes clicks directly to the media widget.
    w.spotify_volume_widget = None
    w.spotify_visualizer_widget = None
    w.reddit_widget = None
    w.reddit2_widget = None

    # Ensure media widget finished its fade before clicking
    qtbot.waitUntil(
        lambda: w.media_widget is not None and getattr(w.media_widget, "_fade_in_completed", False),
        timeout=2000,
    )
    media = w.media_widget
    assert media is not None
    media._controller = fake_ctrl  # type: ignore[attr-defined]
    media.resolve_control_hit = lambda _pos: "play"  # type: ignore[assignment]

    # Simulate global Ctrl-held interaction mode
    from rendering import display_widget as display_mod

    display_mod.DisplayWidget._global_ctrl_held = True  # type: ignore[attr-defined]
    w._ctrl_held = True  # type: ignore[attr-defined]
    w._exiting = False
    handler = getattr(w, "_input_handler", None)
    assert handler is not None
    handler.set_exiting(False)
    try:
        w._coordinator.set_ctrl_held(True)
    except Exception:
        pass

    handler = getattr(w, "_input_handler", None)
    assert handler is not None
    handler.set_exiting(False)

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
    from rendering import widget_manager as widget_manager_mod

    def _immediate_fade(self, overlay_name, starter):
        starter()

    monkeypatch.setattr(
        widget_manager_mod.WidgetManager,
        "request_overlay_fade_sync",
        _immediate_fade,
    )

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
    w.spotify_volume_widget = None
    w.spotify_visualizer_widget = None
    w.reddit_widget = None
    w.reddit2_widget = None

    qtbot.waitUntil(
        lambda: w.media_widget is not None and getattr(w.media_widget, "_fade_in_completed", False),
        timeout=2000,
    )
    media = w.media_widget
    assert media is not None
    media._controller = fake_ctrl  # type: ignore[attr-defined]
    media.resolve_control_hit = lambda _pos: "play"  # type: ignore[assignment]

    handler = getattr(w, "_input_handler", None)
    assert handler is not None

    geom = media.geometry()
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
