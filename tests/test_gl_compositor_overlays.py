from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSize

from rendering.gl_compositor_pkg import overlays
from rendering.gl_compositor_pkg import shader_dispatch


class _Profiler:
    def __init__(self, metrics):
        self._metrics = metrics

    def get_metrics(self, name):
        return self._metrics.get(name)


class _OverlayWidget:
    def __init__(self):
        self._slide = None
        self._wipe = SimpleNamespace(progress=0.25)
        self._blockspin = None
        self._warp = None
        self._raindrops = None
        self._blockflip = None
        self._diffuse = None
        self._blinds = None
        self._crumble = None
        self._particle = None
        self._profiler = _Profiler({"wipe": (60.0, 14.0, 18.0, None)})
        self._debug_overlay_cache_key = None
        self._debug_overlay_cache_image = None
        self._debug_overlay_cache_built_at = 0.0
        self._size = QSize(320, 200)
        self._spotify_vis_enabled = False

    def size(self):
        return QSize(self._size)


@pytest.mark.qt_no_exception_capture
def test_render_debug_overlay_image_reuses_cached_image(monkeypatch, qt_app):
    widget = _OverlayWidget()
    monkeypatch.setattr(overlays, "is_perf_metrics_enabled", lambda: True)

    first = overlays.render_debug_overlay_image(widget)
    second = overlays.render_debug_overlay_image(widget)

    assert first is not None
    assert second is first


@pytest.mark.qt_no_exception_capture
def test_render_debug_overlay_image_invalidates_cache_when_payload_changes(monkeypatch, qt_app):
    widget = _OverlayWidget()
    monkeypatch.setattr(overlays, "is_perf_metrics_enabled", lambda: True)
    clock = {"now": 100.0}
    monkeypatch.setattr(overlays.time, "monotonic", lambda: clock["now"])
    first = overlays.render_debug_overlay_image(widget)
    widget._wipe.progress = 0.55
    clock["now"] += overlays._DEBUG_OVERLAY_REFRESH_INTERVAL_S + 0.01
    second = overlays.render_debug_overlay_image(widget)

    assert first is not None
    assert second is not None
    assert second is not first


@pytest.mark.qt_no_exception_capture
def test_render_debug_overlay_image_throttles_rebuilds_within_refresh_window(monkeypatch, qt_app):
    widget = _OverlayWidget()
    monkeypatch.setattr(overlays, "is_perf_metrics_enabled", lambda: True)
    clock = {"now": 100.0}
    monkeypatch.setattr(overlays.time, "monotonic", lambda: clock["now"])

    first = overlays.render_debug_overlay_image(widget)
    widget._wipe.progress = 0.55
    clock["now"] += overlays._DEBUG_OVERLAY_REFRESH_INTERVAL_S * 0.5
    second = overlays.render_debug_overlay_image(widget)

    assert first is not None
    assert second is first


def test_paint_qpainter_overlays_gl_batches_visualizer_and_debug_overlay(monkeypatch):
    events: list[str] = []

    class _Painter:
        def __init__(self, comp):
            events.append("painter:start")

        def drawImage(self, x, y, image):
            events.append("draw:image")

        def end(self):
            events.append("painter:end")

    comp = _OverlayWidget()
    comp._spotify_vis_enabled = True

    monkeypatch.setattr(shader_dispatch, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(shader_dispatch, "QPainter", _Painter)
    monkeypatch.setattr(shader_dispatch, "gl", SimpleNamespace(glUseProgram=lambda program: events.append(f"use:{program}")))
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.overlays.paint_spotify_visualizer",
        lambda comp, painter: events.append("draw:spotify"),
    )
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.overlays.render_debug_overlay_image",
        lambda comp: object(),
    )

    shader_dispatch.paint_qpainter_overlays_gl(comp)

    assert events == ["use:0", "painter:start", "draw:spotify", "draw:image", "painter:end"]


def test_paint_qpainter_overlays_gl_skips_painter_when_no_overlays(monkeypatch):
    comp = _OverlayWidget()
    comp._spotify_vis_enabled = False

    monkeypatch.setattr(shader_dispatch, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(shader_dispatch, "QPainter", lambda comp: (_ for _ in ()).throw(AssertionError("QPainter should not be created")))
    monkeypatch.setattr(shader_dispatch, "gl", SimpleNamespace(glUseProgram=lambda program: None))

    shader_dispatch.paint_qpainter_overlays_gl(comp)
