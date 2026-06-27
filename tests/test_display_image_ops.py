from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap

from rendering import display_image_ops


def test_prewarm_spotify_visualizer_overlay_primes_shader_cache_before_overlay(monkeypatch):
    calls: list[object] = []

    class _FakeVisualizer:
        _vis_mode_str = "bubble"

        def geometry(self) -> QRect:
            return QRect(10, 20, 320, 160)

    class _FakeOverlay:
        def __init__(self) -> None:
            self._vis_mode = "spectrum"

        def prewarm_context(self, geom: QRect) -> None:
            calls.append(
                ("overlay", self._vis_mode, geom.x(), geom.y(), geom.width(), geom.height())
            )

    monkeypatch.setattr(
        "widgets.spotify_visualizer.shaders.preload_fragment_shaders",
        lambda: calls.append("shaders") or {"spectrum": "frag"},
    )
    monkeypatch.setattr(
        display_image_ops,
        "_ensure_spotify_bars_overlay",
        lambda widget: _FakeOverlay(),
    )

    widget = SimpleNamespace(spotify_visualizer_widget=_FakeVisualizer())

    assert display_image_ops.prewarm_spotify_visualizer_overlay(widget) is True
    assert calls == [
        "shaders",
        ("overlay", "bubble", 10, 20, 320, 160),
    ]


def test_ensure_spotify_bars_overlay_seeds_ctor_mode_from_visualizer(monkeypatch):
    calls: list[object] = []

    class _FakeVisualizer:
        _vis_mode_str = "devcurve"

    class _FakeWidget:
        spotify_visualizer_widget = _FakeVisualizer()
        _spotify_bars_overlay = None
        _resource_manager = None

    class _FakeOverlay:
        def __init__(self, parent, initial_mode=None) -> None:
            calls.append(("ctor", initial_mode))

        def setObjectName(self, name: str) -> None:
            calls.append(("name", name))

        def clear_overlay_buffer(self) -> None:
            return None

    monkeypatch.setattr(display_image_ops, "SpotifyBarsGLOverlay", _FakeOverlay)

    widget = _FakeWidget()
    overlay = display_image_ops._ensure_spotify_bars_overlay(widget)

    assert overlay is not None
    assert calls[0] == ("ctor", "devcurve")


def test_push_spotify_visualizer_frame_allows_hidden_startup_priming(monkeypatch):
    calls: list[dict] = []

    class _FakeVisualizer:
        _startup_reveal_pending = True
        _waiting_for_fresh_frame = True
        _waiting_for_fresh_engine_frame = True
        _border_width = 2

        def isVisible(self) -> bool:
            return False

        def geometry(self) -> QRect:
            return QRect(10, 20, 320, 160)

    class _FakeOverlay:
        def set_state(self, **kwargs) -> None:
            calls.append(kwargs)

        def set_painted_frame_shadow_enabled(self, enabled: bool) -> None:
            return None

    monkeypatch.setattr(
        display_image_ops,
        "_ensure_spotify_bars_overlay",
        lambda widget: _FakeOverlay(),
    )

    widget = SimpleNamespace(
        spotify_visualizer_widget=_FakeVisualizer(),
    )

    ok = display_image_ops.push_spotify_visualizer_frame(
        widget,
        bars=[0.1, 0.2],
        bar_count=2,
        segments=4,
        fill_color=None,
        border_color=None,
        fade=0.0,
        playing=True,
        vis_mode="bubble",
    )

    assert ok is True
    assert len(calls) == 1
    assert calls[0]["visible"] is True
    assert calls[0]["rect"] == QRect(10, 20, 320, 160)


def test_push_spotify_visualizer_frame_still_skips_hidden_nonstartup_widget(monkeypatch):
    class _FakeVisualizer:
        _startup_reveal_pending = False
        _waiting_for_fresh_frame = False
        _waiting_for_fresh_engine_frame = False

        def isVisible(self) -> bool:
            return False

        def geometry(self) -> QRect:
            return QRect(10, 20, 320, 160)

    monkeypatch.setattr(
        display_image_ops,
        "_ensure_spotify_bars_overlay",
        lambda widget: (_ for _ in ()).throw(AssertionError("overlay should not be created")),
    )

    widget = SimpleNamespace(
        spotify_visualizer_widget=_FakeVisualizer(),
    )

    ok = display_image_ops.push_spotify_visualizer_frame(
        widget,
        bars=[0.1, 0.2],
        bar_count=2,
        segments=4,
        fill_color=None,
        border_color=None,
        fade=0.0,
        playing=True,
        vis_mode="bubble",
    )

    assert ok is False


def test_prewarm_spotify_visualizer_overlay_prefers_committed_custom_rect_over_stale_live_geometry(monkeypatch):
    calls: list[object] = []

    class _FakeVisualizer:
        _vis_mode_str = "bubble"
        _custom_layout_local_rect = QRect(12, 220, 510, 340)

        def geometry(self) -> QRect:
            return QRect(12, 220, 340, 340)

        def _active_custom_layout_rect(self) -> QRect:
            return QRect(self._custom_layout_local_rect)

    class _FakeOverlay:
        def __init__(self) -> None:
            self._vis_mode = "spectrum"

        def prewarm_context(self, geom: QRect) -> None:
            calls.append(
                ("overlay", self._vis_mode, geom.x(), geom.y(), geom.width(), geom.height())
            )

    monkeypatch.setattr(
        "widgets.spotify_visualizer.shaders.preload_fragment_shaders",
        lambda: calls.append("shaders") or {"spectrum": "frag"},
    )
    monkeypatch.setattr(
        display_image_ops,
        "_ensure_spotify_bars_overlay",
        lambda widget: _FakeOverlay(),
    )

    widget = SimpleNamespace(spotify_visualizer_widget=_FakeVisualizer())

    assert display_image_ops.prewarm_spotify_visualizer_overlay(widget) is True
    assert calls == [
        "shaders",
        ("overlay", "bubble", 12, 220, 510, 340),
    ]


def test_push_spotify_visualizer_frame_prefers_committed_custom_rect_over_stale_live_geometry(monkeypatch):
    calls: list[dict] = []

    class _FakeVisualizer:
        _startup_reveal_pending = False
        _waiting_for_fresh_frame = False
        _waiting_for_fresh_engine_frame = False
        _border_width = 2
        _custom_layout_local_rect = QRect(24, 180, 402, 357)

        def isVisible(self) -> bool:
            return True

        def geometry(self) -> QRect:
            return QRect(24, 180, 357, 357)

        def _active_custom_layout_rect(self) -> QRect:
            return QRect(self._custom_layout_local_rect)

    class _FakeOverlay:
        def set_state(self, **kwargs) -> None:
            calls.append(kwargs)

        def set_painted_frame_shadow_enabled(self, enabled: bool) -> None:
            return None

    monkeypatch.setattr(
        display_image_ops,
        "_ensure_spotify_bars_overlay",
        lambda widget: _FakeOverlay(),
    )

    widget = SimpleNamespace(
        spotify_visualizer_widget=_FakeVisualizer(),
    )

    ok = display_image_ops.push_spotify_visualizer_frame(
        widget,
        bars=[0.1, 0.2],
        bar_count=2,
        segments=4,
        fill_color=None,
        border_color=None,
        fade=1.0,
        playing=True,
        vis_mode="bubble",
    )

    assert ok is True
    assert len(calls) == 1
    assert calls[0]["rect"] == QRect(24, 180, 402, 357)


def test_sync_spotify_visualizer_overlay_geometry_prefers_committed_custom_rect_over_stale_widget_and_overlay():
    class _FakeVisualizer:
        _custom_layout_local_rect = QRect(24, 180, 402, 357)

        def geometry(self) -> QRect:
            return QRect(24, 180, 357, 357)

        def _resolve_gpu_target_rect(self) -> QRect:
            return QRect(self._custom_layout_local_rect)

        def _active_custom_layout_rect(self) -> QRect:
            return QRect(self._custom_layout_local_rect)

    class _FakeOverlay:
        def __init__(self) -> None:
            self._geometry = QRect(0, 0, 100, 400)
            self.updated = False

        def geometry(self) -> QRect:
            return QRect(self._geometry)

        def setGeometry(self, rect: QRect) -> None:
            self._geometry = QRect(rect)

        def update(self) -> None:
            self.updated = True

    overlay = _FakeOverlay()
    widget = SimpleNamespace(
        spotify_visualizer_widget=_FakeVisualizer(),
        _spotify_bars_overlay=overlay,
    )

    assert display_image_ops.sync_spotify_visualizer_overlay_geometry(widget) is True
    assert overlay.geometry() == QRect(24, 180, 402, 357)
    assert overlay.updated is True


def test_schedule_startup_first_frame_ready_flushes_visible_compositor_before_emit(monkeypatch):
    scheduled = []

    monkeypatch.setattr(
        display_image_ops.QTimer,
        "singleShot",
        staticmethod(lambda delay_ms, callback: scheduled.append((delay_ms, callback))),
    )

    emitted = []
    pending = []

    class _FakeSignal:
        def emit(self, value):
            emitted.append(value)

    class _FakeCompositor:
        def __init__(self) -> None:
            self.update_calls = 0
            self.repaint_calls = 0

        def isVisible(self) -> bool:
            return True

        def update(self) -> None:
            self.update_calls += 1

        def repaint(self) -> None:
            self.repaint_calls += 1

    monkeypatch.setattr(display_image_ops, "GLCompositorWidget", _FakeCompositor)

    widget = SimpleNamespace(
        screen_index=1,
        _gl_compositor=_FakeCompositor(),
        _has_rendered_first_frame=False,
        image_displayed=_FakeSignal(),
        current_image_path=None,
        set_transition_work_pending=lambda value: pending.append(value),
    )

    display_image_ops._schedule_startup_first_frame_ready(widget, "first.png")

    assert len(scheduled) == 1
    scheduled.pop(0)[1]()

    assert widget._gl_compositor.update_calls == 1
    assert widget._gl_compositor.repaint_calls == 1
    assert len(scheduled) == 1

    scheduled.pop(0)[1]()

    assert widget._has_rendered_first_frame is True
    assert widget.current_image_path == "first.png"
    assert isinstance(widget._first_frame_committed_ts, float)
    assert widget._first_frame_committed_image_path == "first.png"
    assert emitted == ["first.png"]
    assert pending == [False]


def test_schedule_startup_first_frame_ready_latest_token_wins(monkeypatch):
    scheduled = []

    monkeypatch.setattr(
        display_image_ops.QTimer,
        "singleShot",
        staticmethod(lambda delay_ms, callback: scheduled.append(callback)),
    )

    emitted = []

    class _FakeSignal:
        def emit(self, value):
            emitted.append(value)

    widget = SimpleNamespace(
        screen_index=0,
        _gl_compositor=None,
        _has_rendered_first_frame=False,
        image_displayed=_FakeSignal(),
        current_image_path=None,
        update=lambda: None,
        repaint=lambda: None,
        set_transition_work_pending=lambda value: None,
    )

    display_image_ops._schedule_startup_first_frame_ready(widget, "first.png")
    first_flush = scheduled.pop(0)
    display_image_ops._schedule_startup_first_frame_ready(widget, "second.png")
    second_flush = scheduled.pop(0)

    first_flush()
    assert emitted == []

    second_flush()
    assert len(scheduled) == 1
    scheduled.pop(0)()

    assert emitted == ["second.png"]
    assert widget.current_image_path == "second.png"
    assert widget._first_frame_committed_image_path == "second.png"


def test_failed_transition_start_restores_widget_stack(qt_app, monkeypatch):
    calls: list[str] = []

    class _FakeSignal:
        def connect(self, _callback):
            calls.append("connect")

        def emit(self, *_args):
            calls.append("emit")

    class _FakeManager:
        def raise_all_widgets(self):
            calls.append("raise_widgets")

    class _FakeCompositor:
        def setGeometry(self, *_args):
            calls.append("comp_geom")

        def set_base_pixmap(self, *_args):
            calls.append("comp_base")

        def show(self):
            calls.append("comp_show")

        def raise_(self):
            calls.append("comp_raise")

        def warm_shader_textures(self, *_args):
            calls.append("comp_warm")

    class _FakeTransition:
        finished = _FakeSignal()

        def __init__(self):
            self.cleaned = False

        def start(self, *_args):
            calls.append("transition_start")
            return False

        def cleanup(self):
            calls.append("transition_cleanup")
            self.cleaned = True

    monkeypatch.setattr(display_image_ops, "GLCompositorWidget", _FakeCompositor)

    old_pixmap = QPixmap(8, 8)
    old_pixmap.fill()
    new_pixmap = QPixmap(8, 8)
    new_pixmap.fill()
    transition = _FakeTransition()

    class _FakeWidget:
        def __init__(self):
            self._transition_skip_count = 0
            self.settings_manager = object()
            self._has_rendered_first_frame = True
            self._transitions_enabled = True
            self._animation_manager = None
            self._overlay_timeouts = {}
            self._pre_raise_log_emitted = False
            self._base_fallback_paint_logged = False
            self._device_pixel_ratio = 1.0
            self._updates_blocked_until_seed = False
            self._image_presenter = None
            self._gl_compositor = _FakeCompositor()
            self._transition_controller = None
            self._current_transition = None
            self.current_pixmap = old_pixmap
            self.previous_pixmap = None
            self.current_image_path = None
            self.image_displayed = _FakeSignal()
            self._widget_manager = _FakeManager()
            self._spotify_bars_overlay = None
            self._ctrl_cursor_hint = None

        def has_running_transition(self):
            return False

        def set_transition_work_pending(self, value):
            calls.append(f"pending:{value}")

        def _ensure_gl_compositor(self):
            calls.append("ensure_comp")

        def width(self):
            return 8

        def height(self):
            return 8

        def _create_transition(self):
            return transition

        def _resolve_overlay_key_for_transition(self, _transition):
            return None

        def _warm_transition_if_needed(self, *_args):
            calls.append("warm_transition")

        def _cancel_transition_watchdog(self):
            calls.append("cancel_watchdog")

        def _ensure_overlay_stack(self, stage):
            calls.append(f"ensure_stack:{stage}")

        def update(self):
            calls.append("update")

    widget = _FakeWidget()

    display_image_ops.set_processed_image(widget, new_pixmap, new_pixmap, "next.png")

    assert "transition_start" in calls
    assert "transition_cleanup" in calls
    assert "raise_widgets" in calls
    raise_indices = [idx for idx, call in enumerate(calls) if call == "raise_widgets"]
    assert any(idx > calls.index("transition_cleanup") for idx in raise_indices)
    assert max(raise_indices) < calls.index("ensure_stack:display")
    assert widget.current_image_path == "next.png"
