from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSize

from rendering.gl_compositor_pkg import overlays
from rendering.gl_compositor_pkg import paint
from rendering.gl_compositor_pkg import shader_dispatch


class _Profiler:
    def __init__(self, metrics):
        self._metrics = metrics
        self.calls: list[str] = []

    def get_metrics(self, name):
        self.calls.append(name)
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
        self._spotify_visualizer_layer = None
        self._dimming_enabled = False
        self._dimming_opacity = 0.0

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
    first_calls = list(widget._profiler.calls)
    widget._wipe.progress = 0.55
    clock["now"] += overlays._DEBUG_OVERLAY_REFRESH_INTERVAL_S * 0.5
    second = overlays.render_debug_overlay_image(widget)

    assert first is not None
    assert second is first
    assert widget._profiler.calls == first_calls


def test_build_debug_overlay_payload_supports_burn_and_missing_attrs():
    widget = SimpleNamespace(
        _burn=SimpleNamespace(progress=0.33),
        _profiler=_Profiler({"burn": (144.0, 5.0, 11.0, None)}),
    )

    payload = overlays._build_debug_overlay_payload(widget)

    assert payload == ("Burn t=0.33", "144.0 fps  dt_min=5.0ms  dt_max=11.0ms")


def test_paint_qpainter_overlays_gl_batches_dimming_visualizer_and_debug_overlay(monkeypatch):
    events: list[str] = []

    class _Painter:
        def __init__(self, comp):
            events.append("painter:start")

        def drawImage(self, x, y, image):
            events.append("draw:image")

        def end(self):
            events.append("painter:end")

    comp = _OverlayWidget()
    comp._spotify_visualizer_layer = object()
    comp._dimming_enabled = True
    comp._dimming_opacity = 0.4
    comp._paint_dimming = lambda painter: events.append("draw:dimming")

    monkeypatch.setattr(shader_dispatch, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(shader_dispatch, "QPainter", _Painter)
    monkeypatch.setattr(shader_dispatch, "gl", SimpleNamespace(glUseProgram=lambda program: events.append(f"use:{program}")))
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.overlays.paint_visualizer_scene",
        lambda comp, painter: events.append("draw:spotify") or True,
    )
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.overlays.render_debug_overlay_image",
        lambda comp: object(),
    )

    shader_dispatch.paint_qpainter_overlays_gl(comp)

    assert events == [
        "use:0",
        "painter:start",
        "draw:dimming",
        "draw:spotify",
        "draw:image",
        "painter:end",
    ]


def test_paint_qpainter_overlays_gl_skips_painter_when_no_overlays(monkeypatch):
    comp = _OverlayWidget()

    monkeypatch.setattr(shader_dispatch, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(shader_dispatch, "QPainter", lambda comp: (_ for _ in ()).throw(AssertionError("QPainter should not be created")))
    monkeypatch.setattr(shader_dispatch, "gl", SimpleNamespace(glUseProgram=lambda program: None))

    shader_dispatch.paint_qpainter_overlays_gl(comp)


def test_visualizer_scene_routes_only_to_compositor_layer():
    events: list[str] = []
    comp = SimpleNamespace(
        _spotify_visualizer_layer=object(),
        paint_spotify_visualizer_layer=lambda painter: events.append("layer") or True,
    )
    assert overlays.paint_visualizer_scene(comp, object()) is True
    assert events == ["layer"]


def test_visualizer_scene_has_no_lower_fidelity_substitute():
    comp = SimpleNamespace(_spotify_visualizer_layer=None)

    assert overlays.paint_visualizer_scene(comp, object()) is False


@pytest.mark.parametrize(
    "transition_name",
    [descriptor[0] for descriptor in paint._TRANSITION_SHADER_DESCRIPTORS],
)
def test_every_compositor_transition_shader_path_paints_overlay_scene_once(
    transition_name,
    monkeypatch,
):
    events: list[str] = []
    comp = SimpleNamespace(
        _last_shader_path_failure="",
        _gl_disabled_for_session=False,
        _use_shaders=True,
    )
    monkeypatch.setattr(
        shader_dispatch,
        "paint_qpainter_overlays_gl",
        lambda _comp: events.append("scene_overlays"),
    )

    assert shader_dispatch.try_shader_path(
        comp,
        transition_name,
        object(),
        lambda: True,
        lambda _target: events.append("transition"),
        object(),
        lambda: True,
    ) is True
    assert events == ["transition", "scene_overlays"]
