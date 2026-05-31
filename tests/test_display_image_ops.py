from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QRect

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
