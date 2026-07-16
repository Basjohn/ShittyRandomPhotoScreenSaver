from __future__ import annotations

from types import SimpleNamespace

import pytest

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from rendering import display_image_ops
from rendering.gl_compositor import GLCompositorWidget
from rendering.gl_compositor_pkg.spotify_visualizer_layer import (
    CompositorSpotifyVisualizerLayer,
    single_surface_visualizer_enabled,
)
from rendering.gl_compositor_pkg import spotify_visualizer_layer as layer_module
from widgets.spotify_visualizer import startup_staging
from widgets.spotify_visualizer.card_paint import (
    ensure_painted_frame_shadow_pixmap,
    paint_compositor_card,
)
from widgets.spotify_bars_gl_overlay import (
    SpotifyVisualizerGLRenderer,
    _visualizer_startup_compile_targets,
)
from widgets import spotify_bars_gl_overlay as renderer_module


def _bare_layer(**values):
    layer = object.__new__(CompositorSpotifyVisualizerLayer)
    defaults = {
        "_compositor": SimpleNamespace(
            _gl_disabled_for_session=False,
            get_gl_state=lambda: SimpleNamespace(name="READY"),
        ),
        "_renderer": SimpleNamespace(),
        "_geometry": QRect(),
        "_front": None,
        "_back": None,
        "_retained_front": None,
        "_buffer_logical_size": QSize(),
        "_has_last_good_frame": False,
        "_retired": False,
        "_prepare_failure_domain": "",
        "_prepare_failure_reason": "",
        "_prepare_attempted_this_paint": False,
        "_prepare_retry_not_before_ts": 0.0,
        "_prepare_retry_delay_s": 0.0,
        "_perf_fbo_resize_window": 0,
        "_perf_render_failure_window": 0,
        "_perf_retained_last_good_window": 0,
        "_perf_fbo_render_window": 0,
        "_perf_texture_reuse_window": 0,
    }
    defaults.update(values)
    for name, value in defaults.items():
        object.__setattr__(layer, name, value)
    return layer


def test_single_surface_visualizer_is_default_and_has_explicit_rollback(monkeypatch):
    monkeypatch.delenv("SRPSS_SINGLE_SURFACE_VISUALIZER", raising=False)
    assert single_surface_visualizer_enabled() is True

    for value in ("0", "false", "legacy", "disabled"):
        monkeypatch.setenv("SRPSS_SINGLE_SURFACE_VISUALIZER", value)
        assert single_surface_visualizer_enabled() is False


def test_compositor_prewarms_all_modes_while_legacy_keeps_incremental_warmup():
    order = ["bubble", "spectrum", "sine_wave", "oscilloscope"]

    assert _visualizer_startup_compile_targets("compositor", order) == order
    assert _visualizer_startup_compile_targets("legacy_child", order) == ["bubble"]


def test_layer_geometry_reuses_buffers_for_position_only_changes():
    requests: list[str] = []
    compositor = SimpleNamespace(
        request_scene_update=lambda: requests.append("update") or True,
    )
    layer = _bare_layer(
        _compositor=compositor,
        _geometry=QRect(10, 20, 320, 180),
        _buffer_logical_size=QSize(320, 180),
    )

    layer.setGeometry(QRect(40, 50, 320, 180))

    assert layer._buffer_logical_size == QSize(320, 180)
    assert requests == ["update"]

    layer.setGeometry(QRect(40, 50, 420, 220))

    assert layer._buffer_logical_size.isEmpty()
    assert requests == ["update", "update"]


def test_layer_surface_invalidation_keeps_old_buffers_until_replacement():
    requests: list[str] = []
    front = object()
    back = object()
    layer = _bare_layer(
        _compositor=SimpleNamespace(
            request_scene_update=lambda: requests.append("update") or True,
        ),
        _front=front,
        _back=back,
        _buffer_logical_size=QSize(320, 180),
        _last_render_attempt_generation=8,
    )

    layer.invalidate_surface_metrics(reason="dpr_change")

    assert layer._front is front
    assert layer._back is back
    assert layer._buffer_logical_size.isEmpty()
    assert layer._last_render_attempt_generation == -1
    assert requests == ["update"]


def test_resize_keeps_previous_front_until_new_generation_publishes(monkeypatch):
    class _FakeGL:
        GL_FRAMEBUFFER = 1
        GL_BLEND = 2
        GL_DEPTH_TEST = 3
        GL_CULL_FACE = 4
        GL_SCISSOR_TEST = 5

        @staticmethod
        def glBindFramebuffer(*_args):
            return None

        @staticmethod
        def glViewport(*_args):
            return None

        @staticmethod
        def glDisable(*_args):
            return None

        @staticmethod
        def glColorMask(*_args):
            return None

        @staticmethod
        def glStencilMask(*_args):
            return None

    class _Renderer:
        _state_generation = 10

        def __init__(self) -> None:
            self.transparent = False

        def render_current_framebuffer(self, _rect: QRect) -> bool:
            return False

        def is_intentionally_transparent_frame(self) -> bool:
            return self.transparent

    old_front = SimpleNamespace(name="old_front", framebuffer=11)
    old_back = SimpleNamespace(name="old_back", framebuffer=12)
    new_front = SimpleNamespace(name="new_front", framebuffer=21)
    new_back = SimpleNamespace(name="new_back", framebuffer=22)
    new_slots = iter((new_front, new_back))
    releases: list[object] = []
    renderer = _Renderer()
    layer = _bare_layer(
        _compositor=SimpleNamespace(defaultFramebufferObject=lambda: 7),
        _renderer=renderer,
        _geometry=QRect(0, 0, 640, 360),
        _front=old_front,
        _back=old_back,
        _retained_front=None,
        _buffer_size_px=QSize(320, 180),
        _buffer_logical_size=QSize(320, 180),
        _buffer_dpr=1.0,
        _has_last_good_frame=True,
        _last_render_attempt_generation=-1,
        _last_rendered_state_generation=9,
        _fbo_resize_count=0,
        _fbo_render_count=0,
        _texture_reuse_count=0,
        _last_good_frame_ts=0.0,
    )
    object.__setattr__(layer, "devicePixelRatioF", lambda: 1.0)
    object.__setattr__(layer, "rect", lambda: QRect(0, 0, 640, 360))
    object.__setattr__(
        layer,
        "_create_framebuffer_slot",
        lambda *_args, **_kwargs: next(new_slots),
    )
    object.__setattr__(
        layer,
        "_release_framebuffer_slot",
        lambda slot, **_kwargs: releases.append(slot) if slot is not None else None,
    )
    monkeypatch.setattr(layer_module, "gl", _FakeGL)

    assert layer._ensure_framebuffers() is True
    assert layer._retained_front is old_front
    assert releases == [old_back]

    assert layer._render_to_back_buffer() == (True, True)
    assert layer._retained_front is old_front
    assert releases == [old_back]

    renderer._state_generation = 11
    renderer.transparent = True

    assert layer._render_to_back_buffer() == (True, False)
    assert layer._retained_front is None
    assert releases == [old_back, old_front]


def test_explicit_clear_releases_retained_resize_frame(monkeypatch):
    class _FakeGL:
        GL_FRAMEBUFFER = 1
        GL_SCISSOR_TEST = 2
        GL_COLOR_BUFFER_BIT = 4
        GL_STENCIL_BUFFER_BIT = 8

        @staticmethod
        def glBindFramebuffer(*_args):
            return None

        @staticmethod
        def glViewport(*_args):
            return None

        @staticmethod
        def glDisable(*_args):
            return None

        @staticmethod
        def glClearColor(*_args):
            return None

        @staticmethod
        def glClear(*_args):
            return None

    retained = SimpleNamespace(framebuffer=30)
    releases: list[object] = []
    layer = _bare_layer(
        _compositor=SimpleNamespace(defaultFramebufferObject=lambda: 7),
        _front=SimpleNamespace(framebuffer=10),
        _back=SimpleNamespace(framebuffer=20),
        _retained_front=retained,
        _buffer_size_px=QSize(320, 180),
        _has_last_good_frame=True,
        _last_render_attempt_generation=12,
        _last_rendered_state_generation=11,
    )
    object.__setattr__(layer, "_acquire_context", lambda: False)
    object.__setattr__(layer, "_release_context", lambda _acquired: None)
    object.__setattr__(layer, "update", lambda: None)
    object.__setattr__(
        layer,
        "_release_framebuffer_slot",
        lambda slot, **_kwargs: releases.append(slot) if slot is not None else None,
    )
    monkeypatch.setattr(layer_module, "gl", _FakeGL)

    layer.clear_renderer_backbuffer()

    assert layer._retained_front is None
    assert releases == [retained]
    assert layer._has_presentable_frame() is False
    assert layer._last_render_attempt_generation == -1
    assert layer._last_rendered_state_generation == -1


def test_compositor_physical_cache_invalidation_reaches_visualizer_layer():
    reasons: list[str] = []
    compositor = SimpleNamespace(
        _cached_viewport=(3840, 2160),
        _cached_widget_size=(1920, 1080),
        _spotify_visualizer_layer=SimpleNamespace(
            invalidate_surface_metrics=lambda *, reason: reasons.append(reason),
        ),
        request_scene_update=lambda: True,
    )

    GLCompositorWidget.invalidate_physical_surface_cache(
        compositor,
        reason="screen_change",
    )

    assert compositor._cached_viewport is None
    assert compositor._cached_widget_size is None
    assert reasons == ["screen_change"]


def test_layer_only_authorizes_legacy_for_compositor_owned_hard_failures():
    layer = _bare_layer(
        _prepare_failure_domain="shared_renderer",
        _prepare_failure_reason="renderer_error",
    )
    assert layer.hard_legacy_fallback_reason() is None

    layer._prepare_failure_domain = "framebuffer"
    layer._prepare_failure_reason = "framebuffer_allocation_failed"
    assert layer.hard_legacy_fallback_reason() == "framebuffer_allocation_failed"

    layer._prepare_failure_domain = ""
    layer._prepare_failure_reason = ""
    layer._compositor = SimpleNamespace(
        get_gl_state=lambda: SimpleNamespace(name="CONTEXT_LOST"),
    )
    assert layer.hard_legacy_fallback_reason() == "compositor_state_context_lost"

    layer._compositor = SimpleNamespace(
        get_gl_state=lambda: SimpleNamespace(name="DESTROYED"),
    )
    assert layer.hard_legacy_fallback_reason() is None


def test_layer_terminal_renderer_state_disables_short_startup_retry():
    layer = _bare_layer(
        _renderer=SimpleNamespace(
            get_gl_state=lambda: SimpleNamespace(name="ERROR"),
        ),
    )

    assert layer.startup_retry_allowed() is False


def test_layer_perf_window_counters_are_consumed_once():
    layer = _bare_layer(
        _perf_fbo_resize_window=2,
        _perf_render_failure_window=3,
        _perf_retained_last_good_window=1,
        _perf_fbo_render_window=40,
        _perf_texture_reuse_window=80,
    )

    assert layer.take_perf_window_counters() == (2, 3, 1, 40, 80)
    assert layer.take_perf_window_counters() == (0, 0, 0, 0, 0)


def test_layer_publishes_transparent_generation_and_reuses_unchanged_texture(monkeypatch):
    class _FakeGL:
        GL_FRAMEBUFFER = 1
        GL_BLEND = 2
        GL_DEPTH_TEST = 3
        GL_CULL_FACE = 4
        GL_SCISSOR_TEST = 5
        GL_STENCIL_BUFFER_BIT = 6

        @staticmethod
        def glBindFramebuffer(*_args):
            return None

        @staticmethod
        def glViewport(*_args):
            return None

        @staticmethod
        def glDisable(*_args):
            return None

        @staticmethod
        def glColorMask(*_args):
            return None

        @staticmethod
        def glStencilMask(*_args):
            return None

        @staticmethod
        def glClear(*_args):
            return None

    monkeypatch.setattr(layer_module, "gl", _FakeGL)

    class _Renderer:
        _state_generation = 4

        def __init__(self) -> None:
            self.calls = 0
            self.transparent = True
            self.raise_render = False

        def render_current_framebuffer(self, _rect: QRect) -> bool:
            self.calls += 1
            if self.raise_render:
                raise RuntimeError("render failed")
            return False

        def is_intentionally_transparent_frame(self) -> bool:
            return self.transparent

    renderer = _Renderer()
    front = SimpleNamespace(framebuffer=11)
    back = SimpleNamespace(framebuffer=12)
    layer = _bare_layer(
        _renderer=renderer,
        _front=front,
        _back=back,
        _buffer_size_px=QSize(640, 360),
        _has_last_good_frame=False,
        _last_render_attempt_generation=-1,
        _last_rendered_state_generation=-1,
        _fbo_render_count=0,
        _texture_reuse_count=0,
        _perf_fbo_render_window=0,
        _perf_texture_reuse_window=0,
        _last_good_frame_ts=0.0,
    )
    layer.rect = lambda: QRect(0, 0, 320, 180)

    assert layer._render_to_back_buffer() == (True, False)
    assert renderer.calls == 1
    assert layer._front is back
    assert layer._last_rendered_state_generation == 4

    assert layer._render_to_back_buffer() == (True, False)
    assert renderer.calls == 1
    assert layer._texture_reuse_count == 1

    renderer._state_generation = 5
    renderer.transparent = False
    assert layer._render_to_back_buffer() == (True, True)
    assert renderer.calls == 2
    assert layer._front is back

    renderer._state_generation = 6
    renderer.raise_render = True
    assert layer._render_to_back_buffer() == (True, True)
    assert renderer.calls == 3
    assert layer._front is back


def test_framebuffer_slot_uses_stencil_only_and_cleans_partial_allocation(monkeypatch):
    class _FakeGL:
        GL_TEXTURE_2D = 1
        GL_TEXTURE_MIN_FILTER = 2
        GL_TEXTURE_MAG_FILTER = 3
        GL_LINEAR = 4
        GL_TEXTURE_WRAP_S = 5
        GL_TEXTURE_WRAP_T = 6
        GL_CLAMP_TO_EDGE = 7
        GL_RGBA8 = 8
        GL_RGBA = 9
        GL_UNSIGNED_BYTE = 10
        GL_RENDERBUFFER = 11
        GL_STENCIL_INDEX8 = 12
        GL_FRAMEBUFFER = 13
        GL_COLOR_ATTACHMENT0 = 14
        GL_STENCIL_ATTACHMENT = 15
        GL_FRAMEBUFFER_COMPLETE = 16

        deleted_framebuffers: list[int] = []
        deleted_textures: list[int] = []
        deleted_renderbuffers: list[int] = []
        storage_formats: list[int] = []
        attachment_points: list[int] = []
        fail_texture_upload = False

        @classmethod
        def glGenFramebuffers(cls, _count):
            return 101

        @classmethod
        def glGenTextures(cls, _count):
            return 102

        @classmethod
        def glGenRenderbuffers(cls, _count):
            return 103

        @staticmethod
        def glBindTexture(*_args):
            return None

        @staticmethod
        def glTexParameteri(*_args):
            return None

        @classmethod
        def glTexImage2D(cls, *_args):
            if cls.fail_texture_upload:
                raise RuntimeError("upload failed")

        @staticmethod
        def glBindRenderbuffer(*_args):
            return None

        @classmethod
        def glRenderbufferStorage(cls, _target, storage_format, _width, _height):
            cls.storage_formats.append(storage_format)

        @staticmethod
        def glBindFramebuffer(*_args):
            return None

        @staticmethod
        def glFramebufferTexture2D(*_args):
            return None

        @classmethod
        def glFramebufferRenderbuffer(
            cls,
            _target,
            attachment,
            _renderbuffer_target,
            _renderbuffer,
        ):
            cls.attachment_points.append(attachment)

        @classmethod
        def glCheckFramebufferStatus(cls, _target):
            return cls.GL_FRAMEBUFFER_COMPLETE

        @classmethod
        def glDeleteFramebuffers(cls, _count, handles):
            cls.deleted_framebuffers.extend(handles)

        @classmethod
        def glDeleteTextures(cls, _count, handles):
            cls.deleted_textures.extend(handles)

        @classmethod
        def glDeleteRenderbuffers(cls, _count, handles):
            cls.deleted_renderbuffers.extend(handles)

    monkeypatch.setattr(layer_module, "gl", _FakeGL)
    layer = _bare_layer(
        _resource_manager=SimpleNamespace(
            register_gl_handle=lambda *_args, **_kwargs: None,
        ),
    )

    slot = layer._create_framebuffer_slot(640, 360)

    assert slot.stencil == 103
    assert _FakeGL.storage_formats == [_FakeGL.GL_STENCIL_INDEX8]
    assert _FakeGL.attachment_points == [_FakeGL.GL_STENCIL_ATTACHMENT]

    _FakeGL.fail_texture_upload = True
    with pytest.raises(RuntimeError, match="upload failed"):
        layer._create_framebuffer_slot(640, 360)

    assert _FakeGL.deleted_framebuffers == [101]
    assert _FakeGL.deleted_textures == [102]
    assert _FakeGL.deleted_renderbuffers == [103]


def test_composite_program_cleans_partial_handle_when_uniform_contract_fails(
    monkeypatch,
):
    class _FakeGL:
        GL_VERTEX_SHADER = 1
        GL_FRAGMENT_SHADER = 2
        GL_LINK_STATUS = 3
        deleted_programs: list[int] = []
        deleted_shaders: list[int] = []

        @staticmethod
        def glCreateProgram():
            return 31

        @staticmethod
        def glAttachShader(*_args):
            return None

        @staticmethod
        def glLinkProgram(*_args):
            return None

        @staticmethod
        def glGetProgramiv(*_args):
            return True

        @staticmethod
        def glGetUniformLocation(_program, name):
            return -1 if name == "u_target_rect" else 5

        @classmethod
        def glDeleteProgram(cls, program):
            cls.deleted_programs.append(program)

        @classmethod
        def glDeleteShader(cls, shader):
            cls.deleted_shaders.append(shader)

    monkeypatch.setattr(layer_module, "gl", _FakeGL)
    shader_ids = iter((11, 12))
    monkeypatch.setattr(
        layer_module,
        "_compile_shader",
        lambda *_args: next(shader_ids),
    )
    layer = _bare_layer(
        _composite_program=0,
        _composite_program_rid=None,
        _composite_target_loc=-1,
        _composite_sampler_loc=-1,
    )

    assert layer._ensure_composite_program() is False
    assert _FakeGL.deleted_programs == [31]
    assert _FakeGL.deleted_shaders == [11, 12]
    assert layer._composite_program == 0
    assert layer._composite_target_loc == -1
    assert layer._composite_sampler_loc == -1


def test_renderer_reuses_cached_mask_uniform_locations(monkeypatch):
    class _FakeGL:
        GL_TRIANGLE_STRIP = 1

        uniform4_locations: list[int] = []
        uniform1_locations: list[int] = []

        @staticmethod
        def glUseProgram(_program):
            return None

        @staticmethod
        def glGetUniformLocation(*_args):
            raise AssertionError("mask locations must be cached at initialization")

        @classmethod
        def glUniform4f(cls, location, *_values):
            cls.uniform4_locations.append(location)

        @classmethod
        def glUniform1f(cls, location, _value):
            cls.uniform1_locations.append(location)

        @staticmethod
        def glBindVertexArray(_vao):
            return None

        @staticmethod
        def glDrawArrays(*_args):
            return None

    monkeypatch.setattr("widgets.spotify_bars_gl_overlay.gl", _FakeGL)
    renderer = SimpleNamespace(
        _gl_mask_program=7,
        _gl_mask_uniforms={"u_card_rect": 21, "u_radius": 22},
        _gl_vao=9,
        _border_width_px=2.0,
        _get_dpr=lambda: 1.5,
    )

    SpotifyVisualizerGLRenderer._draw_painted_card_stencil_mask(
        renderer,
        QRect(0, 0, 320, 180),
    )

    assert _FakeGL.uniform4_locations == [21]
    assert _FakeGL.uniform1_locations == [22]


def test_renderer_refuses_unmasked_frame_when_required_stencil_setup_fails(
    monkeypatch,
):
    render_calls: list[str] = []
    renderer = SimpleNamespace(
        _perf_paint_count=0,
        _perf_metrics_enabled=False,
        _gl_state=SimpleNamespace(is_ready=lambda: True),
        _surface_rect=lambda: QRect(0, 0, 320, 180),
        _painted_frame_shadow_enabled=True,
        _begin_painted_card_stencil_clip=lambda _rect: False,
        _render_with_shader=lambda *_args: render_calls.append("render") or True,
    )
    monkeypatch.setattr(
        renderer_module,
        "clear_overlay_backbuffer",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        renderer_module,
        "resolve_frame_fade",
        lambda *_args, **_kwargs: 1.0,
    )

    assert SpotifyVisualizerGLRenderer.render_current_framebuffer(
        renderer,
        QRect(0, 0, 320, 180),
    ) is False
    assert render_calls == []


@pytest.mark.parametrize("use_retained_resize_frame", [False, True])
def test_layer_scales_presentable_frame_when_buffer_rebuild_fails(
    monkeypatch,
    use_retained_resize_frame,
):
    events: list[str] = []

    class _Painter:
        def beginNativePainting(self):
            events.append("native_begin")

        def endNativePainting(self):
            events.append("native_end")

    class _FakeGL:
        GL_FRAMEBUFFER = 1
        GL_SCISSOR_TEST = 2
        GL_STENCIL_TEST = 3
        GL_DEPTH_TEST = 4
        GL_CULL_FACE = 5
        GL_BLEND = 6

        @staticmethod
        def glBindFramebuffer(*_args):
            return None

        @staticmethod
        def glViewport(*_args):
            return None

        @staticmethod
        def glDisable(*_args):
            return None

        @staticmethod
        def glColorMask(*_args):
            return None

        @staticmethod
        def glStencilMask(*_args):
            return None

        @staticmethod
        def glBindVertexArray(*_args):
            return None

        @staticmethod
        def glUseProgram(*_args):
            return None

    visualizer = SimpleNamespace(
        _compositor_visualizer_active=True,
        isVisible=lambda: True,
    )
    compositor = SimpleNamespace(
        parent=lambda: SimpleNamespace(spotify_visualizer_widget=visualizer),
        defaultFramebufferObject=lambda: 7,
        width=lambda: 1920,
        height=lambda: 1080,
    )
    layer = _bare_layer(
        _compositor=compositor,
        _renderer=SimpleNamespace(_enabled=True),
        _geometry=QRect(20, 30, 400, 220),
        _visible=True,
        _retired=False,
        _front=None if use_retained_resize_frame else SimpleNamespace(texture=5),
        _retained_front=(
            SimpleNamespace(texture=5) if use_retained_resize_frame else None
        ),
        _has_last_good_frame=not use_retained_resize_frame,
        _composite_program=9,
        _paint_count=0,
    )
    def _fail_prepare(_painter):
        layer._prepare_attempted_this_paint = True
        return False

    object.__setattr__(layer, "_prepare_inside_painter", _fail_prepare)
    object.__setattr__(
        layer,
        "_record_render_failure",
        lambda reason: events.append(f"failure:{reason}"),
    )
    object.__setattr__(
        layer,
        "_composite_front_buffer",
        lambda: events.append("composite") or True,
    )
    object.__setattr__(layer, "devicePixelRatioF", lambda: 1.0)
    monkeypatch.setattr(layer_module, "gl", _FakeGL)
    monkeypatch.setattr(
        layer_module,
        "paint_compositor_card",
        lambda *_args, **_kwargs: events.append("card"),
    )

    assert layer.paint(_Painter()) is True
    assert events == [
        "failure:prepare",
        "card",
        "native_begin",
        "composite",
        "native_end",
    ]


def test_layer_prepare_failure_backoff_does_not_retry_each_compositor_paint(
    monkeypatch,
):
    class _Painter:
        def beginNativePainting(self):
            raise AssertionError("backoff must not reopen native painting")

        def endNativePainting(self):
            raise AssertionError("backoff must not reopen native painting")

    layer = _bare_layer(
        _renderer=SimpleNamespace(_state_generation=12),
        _geometry=QRect(0, 0, 320, 180),
        _prepare_failure_domain="framebuffer",
        _prepare_retry_not_before_ts=101.0,
    )
    object.__setattr__(layer, "_needs_prepare", lambda: True)
    object.__setattr__(layer, "devicePixelRatioF", lambda: 1.0)
    monkeypatch.setattr(layer_module.time, "monotonic", lambda: 100.5)

    assert layer._prepare_inside_painter(_Painter()) is False
    assert layer._prepare_attempted_this_paint is False


def test_compositor_scene_update_coalesces_with_pending_display_paint(monkeypatch):
    calls: list[object] = []
    monkeypatch.setattr(
        "rendering.gl_compositor._queue_safe_widget_update",
        lambda widget: calls.append(widget) or True,
    )
    compositor = SimpleNamespace(
        _render_shutdown_requested=False,
        _srpss_timer_update_pending=False,
    )

    assert GLCompositorWidget.request_scene_update(compositor) is True
    assert calls == [compositor]

    compositor._srpss_timer_update_pending = True
    assert GLCompositorWidget.request_scene_update(compositor) is False
    assert calls == [compositor]


def test_ensure_visualizer_renderer_prefers_display_compositor(monkeypatch):
    class _FakeVisualizer:
        _vis_mode_str = "deep_sea"

        def __init__(self) -> None:
            self.compositor_active = None

        def set_compositor_visualizer_active(self, active: bool) -> None:
            self.compositor_active = bool(active)

    class _FakeLayer:
        def clear_overlay_buffer(self) -> None:
            return None

    layer = _FakeLayer()

    class _FakeCompositor:
        def get_or_create_spotify_visualizer_layer(self, *, initial_mode=None):
            assert initial_mode == "deep_sea"
            return layer

    monkeypatch.setattr(display_image_ops, "GLCompositorWidget", _FakeCompositor)
    monkeypatch.setattr(display_image_ops, "CompositorSpotifyVisualizerLayer", _FakeLayer)
    monkeypatch.setattr(display_image_ops, "single_surface_visualizer_enabled", lambda: True)
    monkeypatch.setattr(
        display_image_ops,
        "_create_legacy_spotify_bars_overlay",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy surface must not be created")
        ),
    )

    visualizer = _FakeVisualizer()
    widget = SimpleNamespace(
        spotify_visualizer_widget=visualizer,
        _spotify_bars_overlay=None,
        _gl_compositor=_FakeCompositor(),
        _spotify_visualizer_surface_terminal_reason="prior_failure",
    )

    assert display_image_ops._ensure_spotify_bars_overlay(widget) is layer
    assert widget._spotify_bars_overlay is layer
    assert widget._spotify_visualizer_surface_terminal_reason == ""
    assert visualizer.compositor_active is True


def test_unexpected_compositor_layer_creation_failure_does_not_start_legacy(monkeypatch):
    class _FakeVisualizer:
        _vis_mode_str = "spectrum"

        def set_compositor_visualizer_active(self, _active: bool) -> None:
            return None

    class _FakeCompositor:
        def get_or_create_spotify_visualizer_layer(self, *, initial_mode=None):
            raise RuntimeError(f"broken layer for {initial_mode}")

    monkeypatch.setattr(display_image_ops, "GLCompositorWidget", _FakeCompositor)
    monkeypatch.setattr(display_image_ops, "single_surface_visualizer_enabled", lambda: True)
    monkeypatch.setattr(
        display_image_ops,
        "_create_legacy_spotify_bars_overlay",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected compositor defects must not be masked")
        ),
    )

    widget = SimpleNamespace(
        spotify_visualizer_widget=_FakeVisualizer(),
        _spotify_bars_overlay=None,
        _gl_compositor=_FakeCompositor(),
    )

    assert display_image_ops._ensure_spotify_bars_overlay(widget) is None
    assert (
        widget._spotify_visualizer_surface_terminal_reason
        == "compositor_layer_creation_failed"
    )


def test_missing_opengl_compositor_does_not_start_legacy_without_rollback(monkeypatch):
    monkeypatch.setattr(display_image_ops, "single_surface_visualizer_enabled", lambda: True)
    monkeypatch.setattr(
        display_image_ops,
        "_create_legacy_spotify_bars_overlay",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("missing compositor is not an authorized legacy condition")
        ),
    )
    widget = SimpleNamespace(
        spotify_visualizer_widget=SimpleNamespace(_vis_mode_str="spectrum"),
        _spotify_bars_overlay=None,
        _gl_compositor=None,
        _backend_selection=SimpleNamespace(resolved_mode="opengl"),
        screen_index=0,
    )

    assert display_image_ops._ensure_spotify_bars_overlay(widget) is None
    assert (
        widget._spotify_visualizer_surface_terminal_reason
        == "compositor_unavailable"
    )


def test_transient_compositor_prewarm_does_not_fall_back(monkeypatch):
    class _FakeVisualizer:
        _vis_mode_str = "bubble"

        def geometry(self) -> QRect:
            return QRect(10, 20, 320, 180)

    class _FakeLayer:
        def __init__(self) -> None:
            self._vis_mode = "spectrum"

        def prewarm_context(self, _geom: QRect) -> None:
            return None

        def is_render_ready(self) -> bool:
            return False

        def hard_legacy_fallback_reason(self):
            return None

        def describe_state(self):
            return {"kind": "compositor", "gl_ready": False}

    layer = _FakeLayer()
    monkeypatch.setattr(display_image_ops, "CompositorSpotifyVisualizerLayer", _FakeLayer)
    monkeypatch.setattr(
        display_image_ops,
        "_ensure_spotify_bars_overlay",
        lambda _widget: layer,
    )
    monkeypatch.setattr(
        display_image_ops,
        "_fallback_compositor_visualizer_to_legacy",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("transient readiness must not use legacy")
        ),
    )
    monkeypatch.setattr(
        "widgets.spotify_visualizer.shaders.preload_fragment_shaders",
        lambda: {"bubble": "frag"},
    )
    widget = SimpleNamespace(
        spotify_visualizer_widget=_FakeVisualizer(),
        screen_index=0,
    )

    assert display_image_ops.prewarm_spotify_visualizer_overlay(widget) is False
    assert layer._vis_mode == "bubble"


def test_startup_reveal_retries_compositor_readiness_without_surface_switch(monkeypatch):
    class _Layer:
        render_surface_kind = "compositor"

        def __init__(self) -> None:
            self.ready = False

        def is_render_ready(self) -> bool:
            return self.ready

    layer = _Layer()
    parent = SimpleNamespace(
        _gl_compositor=object(),
        _spotify_bars_overlay=layer,
    )
    widget = SimpleNamespace(parent=lambda: parent)

    def _prewarm(_widget) -> bool:
        layer.ready = True
        return True

    monkeypatch.setattr(startup_staging, "prewarm_parent_overlay", _prewarm)

    assert startup_staging.is_parent_renderer_ready(widget) is True
    assert parent._spotify_bars_overlay is layer


def test_terminal_startup_renderer_does_not_create_rapid_retry_loop(monkeypatch):
    scheduled: list[int] = []
    widget = SimpleNamespace(
        _enabled=True,
        _startup_reveal_pending=True,
        _startup_require_playing_before_reveal=False,
        _spotify_playing=False,
        _startup_idle_reveal_requires_authoritative_media=False,
        _startup_has_authoritative_media_update=False,
        _waiting_for_fresh_frame=False,
        _startup_renderer_terminal_logged=False,
    )
    monkeypatch.setattr(startup_staging, "_qt_object_is_valid", lambda _widget: True)
    monkeypatch.setattr(startup_staging, "is_anchor_visible", lambda _widget: True)
    monkeypatch.setattr(
        startup_staging,
        "is_parent_renderer_ready",
        lambda _widget: False,
    )
    monkeypatch.setattr(
        startup_staging,
        "parent_renderer_startup_retry_allowed",
        lambda _widget: False,
    )
    monkeypatch.setattr(
        startup_staging,
        "schedule_ready_driven_startup_reveal",
        lambda _widget, *, delay_ms: scheduled.append(delay_ms),
    )

    startup_staging.finish_staged_startup_reveal(widget, reason="test")

    assert scheduled == []
    assert widget._startup_renderer_terminal_logged is True


def test_display_surface_terminal_reason_disables_short_startup_retry():
    parent = SimpleNamespace(
        _gl_compositor=SimpleNamespace(
            get_gl_state=lambda: SimpleNamespace(name="READY"),
        ),
        _spotify_bars_overlay=None,
        _spotify_visualizer_surface_terminal_reason=(
            "compositor_layer_creation_failed"
        ),
    )
    widget = SimpleNamespace(parent=lambda: parent)

    assert startup_staging.parent_renderer_startup_retry_allowed(widget) is False


def test_terminal_surface_reason_is_logged_without_scheduling_retry(
    monkeypatch,
    caplog,
):
    scheduled: list[int] = []
    parent = SimpleNamespace(
        _spotify_bars_overlay=None,
        _gl_compositor=SimpleNamespace(
            get_gl_state=lambda: SimpleNamespace(name="READY"),
        ),
        _spotify_visualizer_surface_terminal_reason="compositor_unavailable",
    )
    widget = SimpleNamespace(
        parent=lambda: parent,
        _enabled=True,
        _startup_reveal_pending=True,
        _startup_require_playing_before_reveal=False,
        _spotify_playing=False,
        _startup_idle_reveal_requires_authoritative_media=False,
        _startup_has_authoritative_media_update=False,
        _waiting_for_fresh_frame=False,
        _startup_renderer_terminal_logged=False,
    )
    monkeypatch.setattr(startup_staging, "_qt_object_is_valid", lambda _widget: True)
    monkeypatch.setattr(startup_staging, "is_anchor_visible", lambda _widget: True)
    monkeypatch.setattr(
        startup_staging,
        "schedule_ready_driven_startup_reveal",
        lambda _widget, *, delay_ms: scheduled.append(delay_ms),
    )

    with caplog.at_level("ERROR"):
        startup_staging.finish_staged_startup_reveal(widget, reason="test")

    assert scheduled == []
    assert widget._startup_renderer_terminal_logged is True
    assert "reason=compositor_unavailable" in caplog.text


def test_non_display_visualizer_host_does_not_require_renderer_target():
    from widgets.spotify_visualizer import startup_staging

    parent = SimpleNamespace()
    widget = SimpleNamespace(parent=lambda: parent)

    assert startup_staging.is_parent_renderer_ready(widget) is True
    assert startup_staging.parent_renderer_startup_retry_allowed(widget) is False


@pytest.mark.qt
def test_compositor_card_reuses_exact_painted_shadow_asset(qt_app, qtbot):
    card = QWidget()
    qtbot.addWidget(card)
    card.resize(260, 120)
    card._bg_color = QColor(18, 24, 30)
    card._bg_opacity = 0.72
    card._card_border_color = QColor(220, 230, 240, 210)
    card._border_width = 2
    card._painted_frame_shadow_pixmap = None
    card._painted_frame_shadow_cache_key = None
    card._shadowfade_progress = 1.0
    card.uses_painted_frame_shadow = lambda: True

    source = ensure_painted_frame_shadow_pixmap(card)
    assert source is not None and not source.isNull()

    target = QPixmap(source.size())
    target.setDevicePixelRatio(source.devicePixelRatio())
    target.fill(QColor(0, 0, 0, 0))
    painter = QPainter(target)
    try:
        paint_compositor_card(card, painter, QRect(0, 0, card.width(), card.height()))
    finally:
        painter.end()

    assert target.toImage() == source.toImage()
