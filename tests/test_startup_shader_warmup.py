"""Regression tests for startup shader/program warmup policy."""

import inspect

import rendering.gl_compositor_pkg.gl_lifecycle as gl_lifecycle
from rendering.gl_compositor_pkg.gl_lifecycle import (
    _disable_current_context_swap_interval,
    _schedule_deferred_base_texture_warmup,
    _schedule_deferred_transition_resource_warmup,
    deferred_transition_program_specs,
    ensure_transition_program_ready,
    init_gl_pipeline,
    startup_transition_program_specs,
    _has_live_visible_base_surface,
)
from widgets.spotify_bars_gl_overlay import prioritized_visualizer_compile_order


def test_gl_lifecycle_deferred_warmup_uses_managed_scheduler() -> None:
    source = inspect.getsource(gl_lifecycle)

    assert "QTimer.singleShot" not in source
    assert "ThreadManager.single_shot" in source


def test_swap_interval_disable_noops_outside_windows(monkeypatch) -> None:
    monkeypatch.setattr(gl_lifecycle.sys, "platform", "linux")

    ok, current, source = _disable_current_context_swap_interval()

    assert ok is None
    assert current is None
    assert source == "non_windows"


def test_swap_interval_disable_reports_missing_wgl_extension(monkeypatch) -> None:
    monkeypatch.setattr(gl_lifecycle.sys, "platform", "win32")
    monkeypatch.setattr(gl_lifecycle, "_wgl_proc_address", lambda name: None)

    ok, current, source = _disable_current_context_swap_interval()

    assert ok is None
    assert current is None
    assert source == "wglSwapIntervalEXT_unavailable"


def test_startup_transition_programs_only_compile_minimal_subset() -> None:
    startup_names = [name for name, _, _ in startup_transition_program_specs()]
    deferred_names = [name for name, _, _ in deferred_transition_program_specs()]

    assert startup_names == ["crossfade"]
    assert "crossfade" not in deferred_names
    assert "burn" in deferred_names
    assert "warp" in deferred_names


def test_visualizer_compile_order_prioritizes_active_mode() -> None:
    order = prioritized_visualizer_compile_order(
        "spectrum",
        ["bubble", "devcurve", "oscilloscope", "sine_wave", "spectrum"],
    )

    assert order[0] == "spectrum"
    assert sorted(order) == ["bubble", "devcurve", "oscilloscope", "sine_wave", "spectrum"]


def test_visualizer_compile_order_falls_back_to_available_modes() -> None:
    order = prioritized_visualizer_compile_order(
        "nonexistent",
        ["bubble", "devcurve", "spectrum"],
    )

    assert order == ["bubble", "devcurve", "spectrum"]


def test_hidden_deferred_warmup_guard_detects_live_visible_surface() -> None:
    class _Pixmap:
        def isNull(self):
            return False

    class _StubFrameState:
        started = False
        completed = True

    class _StubWidget:
        def __init__(self):
            self._base_pixmap = _Pixmap()
            self._frame_state = _StubFrameState()

        def isVisible(self):
            return True

    assert _has_live_visible_base_surface(_StubWidget()) is True


def test_hidden_deferred_warmup_guard_ignores_hidden_surface_without_base() -> None:
    class _StubFrameState:
        started = False
        completed = True

    class _StubWidget:
        def __init__(self):
            self._base_pixmap = None
            self._frame_state = _StubFrameState()

        def isVisible(self):
            return False

    assert _has_live_visible_base_surface(_StubWidget()) is False


def test_transition_program_ensure_binds_runtime_alias(monkeypatch) -> None:
    class _StubPipeline:
        initialized = True
        wipe_program = 0
        wipe_uniforms = None

    class _StubWidget:
        def __init__(self):
            self._gl_disabled_for_session = False
            self._gl_pipeline = _StubPipeline()
            self.make_current_calls = 0
            self.done_current_calls = 0

        def makeCurrent(self):
            self.make_current_calls += 1

        def doneCurrent(self):
            self.done_current_calls += 1

    class _StubCache:
        def get_program(self, name):
            assert name == "wipe"
            return 321

        def get_uniforms(self, name):
            assert name == "wipe"
            return {"uMix": 7}

    monkeypatch.setattr("rendering.gl_compositor_pkg.gl_lifecycle.gl", object())
    monkeypatch.setattr("rendering.gl_compositor_pkg.gl_lifecycle.get_program_cache", lambda: _StubCache())

    widget = _StubWidget()
    assert ensure_transition_program_ready(widget, "wipe") is True
    assert widget._gl_pipeline.wipe_program == 321
    assert widget._gl_pipeline.wipe_uniforms == {"uMix": 7}
    assert widget.make_current_calls == 1
    assert widget.done_current_calls == 1


def test_transition_program_ensure_binds_compositor_class(monkeypatch) -> None:
    class _StubPipeline:
        initialized = True
        burn_program = 0
        burn_uniforms = None

    class _StubWidget:
        def __init__(self):
            self._gl_disabled_for_session = False
            self._gl_pipeline = _StubPipeline()

        def makeCurrent(self):
            return None

        def doneCurrent(self):
            return None

    class _StubCache:
        def get_program(self, name):
            assert name == "burn"
            return 987

        def get_uniforms(self, name):
            assert name == "burn"
            return {"uProgress": 5}

    monkeypatch.setattr("rendering.gl_compositor_pkg.gl_lifecycle.gl", object())
    monkeypatch.setattr("rendering.gl_compositor_pkg.gl_lifecycle.get_program_cache", lambda: _StubCache())

    widget = _StubWidget()
    assert ensure_transition_program_ready(widget, "GLCompositorBurnTransition") is True
    assert widget._gl_pipeline.burn_program == 987
    assert widget._gl_pipeline.burn_uniforms == {"uProgress": 5}


def test_transition_program_ensure_revalidates_already_bound_program(monkeypatch) -> None:
    class _StubPipeline:
        initialized = True
        slide_program = 456
        slide_uniforms = {"uProgress": 1}

    class _StubWidget:
        def __init__(self):
            self._gl_disabled_for_session = False
            self._gl_pipeline = _StubPipeline()
            self.make_current_calls = 0
            self.done_current_calls = 0

        def makeCurrent(self):
            self.make_current_calls += 1

        def doneCurrent(self):
            self.done_current_calls += 1

    class _StubCache:
        def get_program(self, name):
            assert name == "slide"
            return 789

        def get_uniforms(self, name):
            assert name == "slide"
            return {"uProgress": 9}

    monkeypatch.setattr("rendering.gl_compositor_pkg.gl_lifecycle.gl", object())
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle.get_program_cache",
        lambda: _StubCache(),
    )

    widget = _StubWidget()
    assert ensure_transition_program_ready(widget, "slide") is True
    assert widget._gl_pipeline.slide_program == 789
    assert widget._gl_pipeline.slide_uniforms == {"uProgress": 9}
    assert widget.make_current_calls == 1
    assert widget.done_current_calls == 1


def test_transition_program_ensure_skips_make_current_for_unknown_identity(monkeypatch) -> None:
    class _StubPipeline:
        initialized = True

    class _StubWidget:
        def __init__(self):
            self._gl_disabled_for_session = False
            self._gl_pipeline = _StubPipeline()
            self.make_current_calls = 0
            self.done_current_calls = 0

        def makeCurrent(self):
            self.make_current_calls += 1

        def doneCurrent(self):
            self.done_current_calls += 1

    monkeypatch.setattr("rendering.gl_compositor_pkg.gl_lifecycle.gl", object())

    widget = _StubWidget()
    assert ensure_transition_program_ready(widget, "unknown_transition_identity") is True
    assert widget.make_current_calls == 0
    assert widget.done_current_calls == 0


def test_deferred_transition_resource_warmup_schedules_when_base_ready(monkeypatch) -> None:
    class _Pixmap:
        def isNull(self):
            return False

    class _StubWidget:
        def __init__(self):
            self._gl_disabled_for_session = False
            self._base_pixmap = _Pixmap()
            self._startup_transition_warm_queue = []
            self._startup_transition_resource_warm_queue = []
            self._startup_transition_resource_warm_types = set()

    scheduled: list[int] = []
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle.ThreadManager.single_shot",
        lambda delay, callback: scheduled.append(delay),
    )

    widget = _StubWidget()
    _schedule_deferred_transition_resource_warmup(widget)

    assert widget._startup_transition_resource_warm_queue
    assert "GLCompositorSlideTransition" in widget._startup_transition_resource_warm_queue
    assert scheduled == [140]


def test_deferred_base_texture_warmup_coalesces_and_presents_after_commit(monkeypatch) -> None:
    class _Pixmap:
        def isNull(self):
            return False

    class _Manager:
        def __init__(self):
            self.committed = 0

        def get_committed_texture(self):
            return self.committed

    class _StubWidget:
        def __init__(self):
            self._gl_disabled_for_session = False
            self._base_pixmap = _Pixmap()
            self._texture_manager = _Manager()
            self._base_texture_warmup_pending = False
            self.warm_calls = 0
            self.update_sources = []

        def _warm_pixmap_textures_in_current_context(
            self,
            old,
            new,
            *,
            old_payload=None,
            new_payload=None,
        ):
            assert old is self._base_pixmap
            assert new is self._base_pixmap
            assert old_payload is None
            assert new_payload is None
            self.warm_calls += 1
            self._texture_manager.committed = 77
            return True

        def request_scene_update(self, *, source):
            self.update_sources.append(source)

    callbacks = []
    releases = []
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle.ThreadManager.single_shot",
        lambda delay, callback: callbacks.append((delay, callback)),
    )
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle.acquire_safe_warmup_context",
        lambda *_args, **_kwargs: lambda: releases.append(True),
    )

    widget = _StubWidget()
    _schedule_deferred_base_texture_warmup(widget)
    _schedule_deferred_base_texture_warmup(widget)

    assert len(callbacks) == 1
    assert callbacks[0][0] == 0
    callbacks[0][1]()

    assert widget.warm_calls == 1
    assert releases == [True]
    assert widget.update_sources == ["base_residency_ready"]
    assert widget._base_texture_warmup_pending is False


def test_deferred_base_texture_warmup_does_not_outlive_render_shutdown(monkeypatch) -> None:
    class _Pixmap:
        def isNull(self):
            return False

    class _StubWidget:
        def __init__(self):
            self._gl_disabled_for_session = False
            self._render_shutdown_requested = False
            self._base_pixmap = _Pixmap()
            self._texture_manager = None
            self._base_texture_warmup_pending = False
            self.warm_calls = 0

        def _warm_pixmap_textures_in_current_context(
            self,
            _old,
            _new,
            **_kwargs,
        ):
            self.warm_calls += 1
            return True

    callbacks = []
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle.ThreadManager.single_shot",
        lambda _delay, callback: callbacks.append(callback),
    )
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle.acquire_safe_warmup_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("shutdown callback must not acquire a GL context")
        ),
    )

    widget = _StubWidget()
    _schedule_deferred_base_texture_warmup(widget)
    assert len(callbacks) == 1

    widget._render_shutdown_requested = True
    callbacks[0]()

    assert widget.warm_calls == 0
    assert widget._base_texture_warmup_pending is False


def test_pipeline_ready_rearms_base_residency_after_pre_show_miss(monkeypatch) -> None:
    class _FakeGL:
        @staticmethod
        def glGetUniformLocation(_program, _name):
            return 1

    class _Geometry:
        quad_vao = 1
        quad_vbo = 2
        box_vao = 3
        box_vbo = 4
        box_vertex_count = 36

        def initialize(self):
            return True

    widget = type(
        "_Widget",
        (),
        {
            "_gl_disabled_for_session": False,
            "_use_shaders": False,
            "_gl_pipeline": gl_lifecycle._GLPipelineState(),
            "_geometry_manager": _Geometry(),
            "_texture_manager": object(),
        },
    )()
    scheduled = []
    monkeypatch.setattr(gl_lifecycle, "gl", _FakeGL())
    monkeypatch.setattr(gl_lifecycle, "create_card_flip_program", lambda _widget: 7)
    monkeypatch.setattr(gl_lifecycle, "startup_transition_program_specs", lambda: [])
    monkeypatch.setattr(
        gl_lifecycle,
        "schedule_deferred_transition_program_warmup",
        lambda _widget: scheduled.append("programs"),
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "_schedule_deferred_base_texture_warmup",
        lambda _widget: scheduled.append("base"),
    )

    init_gl_pipeline(widget)

    assert widget._gl_pipeline.initialized is True
    assert scheduled == ["programs", "base"]
