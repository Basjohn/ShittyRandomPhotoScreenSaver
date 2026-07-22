from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSize

from rendering.gl_compositor_pkg import overlays
from rendering.gl_compositor_pkg import paint
from rendering.gl_compositor_pkg import shader_dispatch


def _idle_paint_widget():
    attrs = {
        "_gl_state": SimpleNamespace(is_ready=lambda: True),
        "_frame_state": None,
        "_paint_section_sample_counter": 1,
        "_last_paint_path": "",
        "_base_pixmap": object(),
        "_transition_renderer": SimpleNamespace(render_base_image=lambda *_args: None),
        "_paint_dimming": lambda _painter: None,
        "rect": lambda: object(),
    }
    for _name, attr, *_rest in paint._TRANSITION_SHADER_DESCRIPTORS:
        attrs[attr] = None
    return SimpleNamespace(**attrs)


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


def test_paint_qpainter_overlays_gl_skips_inactive_visualizer_layer(monkeypatch):
    comp = _OverlayWidget()
    comp._spotify_visualizer_layer = SimpleNamespace(
        should_paint_scene=lambda: False,
    )

    monkeypatch.setattr(shader_dispatch, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(
        shader_dispatch,
        "QPainter",
        lambda comp: (_ for _ in ()).throw(
            AssertionError("inactive visualizer must not open QPainter")
        ),
    )
    monkeypatch.setattr(
        shader_dispatch,
        "gl",
        SimpleNamespace(glUseProgram=lambda program: None),
    )

    shader_dispatch.paint_qpainter_overlays_gl(comp)


def test_healthy_native_visualizer_lane_skips_qpainter(monkeypatch):
    events: list[str] = []
    comp = _OverlayWidget()
    comp._spotify_visualizer_layer = SimpleNamespace(
        should_paint_scene=lambda: True,
        paint_native=lambda: events.append("native") or True,
    )

    monkeypatch.setattr(shader_dispatch, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(
        shader_dispatch,
        "QPainter",
        lambda _comp: (_ for _ in ()).throw(
            AssertionError("healthy native visualizer must not open QPainter")
        ),
    )
    monkeypatch.setattr(
        shader_dispatch,
        "gl",
        SimpleNamespace(
            glUseProgram=lambda _program: (_ for _ in ()).throw(
                AssertionError("native lane owns GL state directly")
            )
        ),
    )

    shader_dispatch.paint_qpainter_overlays_gl(comp)

    assert events == ["native"]


def test_native_visualizer_failure_retains_qpainter_fallback(monkeypatch, caplog):
    events: list[str] = []

    class _Painter:
        def __init__(self, _comp):
            events.append("painter:start")

        def end(self):
            events.append("painter:end")

    comp = _OverlayWidget()
    comp._spotify_visualizer_layer = SimpleNamespace(
        should_paint_scene=lambda: True,
        paint_native=lambda: events.append("native:failed") or False,
    )
    monkeypatch.setattr(shader_dispatch, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(shader_dispatch, "QPainter", _Painter)
    monkeypatch.setattr(
        shader_dispatch,
        "gl",
        SimpleNamespace(glUseProgram=lambda program: events.append(f"use:{program}")),
    )
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.overlays.paint_visualizer_scene",
        lambda _comp, _painter: events.append("painter:visualizer") or True,
    )

    with caplog.at_level("ERROR"):
        shader_dispatch.paint_qpainter_overlays_gl(comp)

    assert events == [
        "native:failed",
        "use:0",
        "painter:start",
        "painter:visualizer",
        "painter:end",
    ]
    assert "retaining QPainter path" in caplog.text


def test_partial_native_visualizer_frame_suppresses_double_blend_fallback(
    monkeypatch,
    caplog,
):
    events: list[str] = []
    comp = _OverlayWidget()
    comp._spotify_visualizer_layer = SimpleNamespace(
        should_paint_scene=lambda: True,
        paint_native=lambda: events.append("native:partial") or False,
        native_fallback_is_safe=lambda: False,
    )
    monkeypatch.setattr(shader_dispatch, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(
        shader_dispatch,
        "QPainter",
        lambda _comp: (_ for _ in ()).throw(
            AssertionError("partially presented native frame must not double blend")
        ),
    )
    monkeypatch.setattr(
        shader_dispatch,
        "gl",
        SimpleNamespace(glUseProgram=lambda _program: None),
    )

    with caplog.at_level("ERROR"):
        shader_dispatch.paint_qpainter_overlays_gl(comp)

    assert events == ["native:partial"]
    assert "suppressing double-blend" in caplog.text


def test_idle_base_shader_uses_only_resident_texture(monkeypatch):
    import rendering.gl_programs.program_cache as program_cache

    calls = []

    class FakePixmap:
        def isNull(self):
            return False

        def width(self):
            return 320

        def height(self):
            return 200

    class FakeManager:
        def get_committed_texture(self):
            calls.append(("committed", 41))
            return 41

    class FakeHelper:
        def render(self, **kwargs):
            calls.append(("render", kwargs))

    comp = SimpleNamespace(
        _gl_disabled_for_session=False,
        _gl_pipeline=SimpleNamespace(
            initialized=True,
            crossfade_program=7,
            crossfade_uniforms={"progress": 2},
            quad_vao=9,
        ),
        _texture_manager=FakeManager(),
        _base_pixmap=FakePixmap(),
        _cached_viewport=None,
        _cached_widget_size=None,
        width=lambda: 320,
        height=lambda: 200,
        devicePixelRatioF=lambda: 1.0,
    )

    monkeypatch.setattr(shader_dispatch, "gl", object())
    monkeypatch.setattr(shader_dispatch, "get_viewport_size", lambda _comp: (320, 200))
    monkeypatch.setattr(
        program_cache,
        "get_program_cache",
        lambda: SimpleNamespace(get_program_instance=lambda _name: FakeHelper()),
    )

    assert shader_dispatch.paint_idle_base_shader(comp) is True
    assert calls[0] == ("committed", 41)
    render_kwargs = calls[1][1]
    assert render_kwargs["old_tex"] == render_kwargs["new_tex"] == 41
    assert render_kwargs["program"] == 7
    assert render_kwargs["quad_vao"] == 9


def test_idle_base_shader_retains_fallback_on_cache_miss(monkeypatch):
    comp = SimpleNamespace(
        _gl_disabled_for_session=False,
        _gl_pipeline=SimpleNamespace(
            initialized=True,
            crossfade_program=7,
            quad_vao=9,
        ),
        _texture_manager=SimpleNamespace(get_committed_texture=lambda: 0),
        _base_pixmap=SimpleNamespace(isNull=lambda: False),
    )
    monkeypatch.setattr(shader_dispatch, "gl", object())

    assert shader_dispatch.paint_idle_base_shader(comp) is False


def test_idle_paint_uses_gl_base_without_full_qpainter(monkeypatch):
    comp = _idle_paint_widget()
    calls = []

    monkeypatch.setattr(paint, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(paint, "paint_idle_base_shader", lambda _comp: True)
    monkeypatch.setattr(
        paint,
        "paint_qpainter_overlays_gl",
        lambda _comp: calls.append("overlays"),
    )
    monkeypatch.setattr(
        paint,
        "QPainter",
        lambda _comp: (_ for _ in ()).throw(
            AssertionError("resident idle base must not open full-base QPainter")
        ),
    )

    paint.paintGL_impl(comp)

    assert calls == ["overlays"]
    assert comp._last_paint_path == "idle_gl"


def test_idle_paint_retains_qpainter_fallback_when_texture_is_not_resident(monkeypatch):
    comp = _idle_paint_widget()
    calls = []

    class FakePainter:
        class RenderHint:
            SmoothPixmapTransform = object()

        def __init__(self, _comp):
            calls.append("painter:start")

        def setRenderHint(self, *_args):
            calls.append("painter:hint")

        def end(self):
            calls.append("painter:end")

    comp._transition_renderer = SimpleNamespace(
        render_base_image=lambda *_args: calls.append("base")
    )
    comp._paint_dimming = lambda _painter: calls.append("dimming")
    monkeypatch.setattr(paint, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(paint, "paint_idle_base_shader", lambda _comp: False)
    monkeypatch.setattr(paint, "QPainter", FakePainter)
    monkeypatch.setattr(
        paint,
        "paint_visualizer_scene",
        lambda *_args: calls.append("visualizer"),
    )
    monkeypatch.setattr(
        paint,
        "paint_debug_overlay",
        lambda *_args: calls.append("debug"),
    )

    paint.paintGL_impl(comp)

    assert calls == [
        "painter:start",
        "painter:hint",
        "base",
        "dimming",
        "visualizer",
        "debug",
        "painter:end",
    ]
    assert comp._last_paint_path == "idle_qpainter_fallback"


def test_terminal_transition_outcome_requires_successful_shader_paint(monkeypatch):
    comp = _idle_paint_widget()
    comp._frame_state = SimpleNamespace(get_interpolated_progress=lambda: 1.0)
    comp._current_transition_name = "wipe"
    comp._wipe = SimpleNamespace(progress=0.0)
    comp._can_use_wipe_shader = lambda: True
    comp._paint_wipe_shader = lambda _target: None
    comp._try_shader_path = lambda *_args, **_kwargs: True

    monkeypatch.setattr(paint, "is_perf_metrics_enabled", lambda: False)

    outcome = paint.paintGL_impl(comp)

    assert outcome.path == "transition_gl"
    assert outcome.transition_rendered is True
    assert outcome.terminal_transition_rendered is True
    assert comp._wipe.progress == 1.0


def test_terminal_transition_fallback_never_authorizes_commit(monkeypatch):
    comp = _idle_paint_widget()
    comp._frame_state = SimpleNamespace(get_interpolated_progress=lambda: 1.0)
    comp._wipe = SimpleNamespace(progress=0.0)
    comp._can_use_wipe_shader = lambda: True
    comp._paint_wipe_shader = lambda _target: None
    comp._try_shader_path = lambda *_args, **_kwargs: False
    comp._gl_disabled_for_session = False
    comp._use_shaders = True
    comp._current_transition_name = "wipe"
    comp._last_shader_path_failure = "wipe:texture_prep_failed"

    class FakePainter:
        class RenderHint:
            SmoothPixmapTransform = object()

        def __init__(self, _comp):
            pass

        def setRenderHint(self, *_args):
            pass

        def end(self):
            pass

    monkeypatch.setattr(paint, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(paint, "QPainter", FakePainter)
    monkeypatch.setattr(paint, "paint_visualizer_scene", lambda *_args: False)
    monkeypatch.setattr(paint, "paint_debug_overlay", lambda *_args: None)

    outcome = paint.paintGL_impl(comp)

    assert outcome.path == "transition_qpainter_fallback"
    assert outcome.transition_rendered is False
    assert outcome.terminal_transition_rendered is False


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
