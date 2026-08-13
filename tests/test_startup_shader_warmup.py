"""Regression tests for startup shader/program warmup policy."""

import inspect
from types import SimpleNamespace

import rendering.gl_compositor_pkg.gl_lifecycle as gl_lifecycle
from rendering.gl_compositor_pkg.gl_lifecycle import (
    _disable_current_context_swap_interval,
    _warm_next_transition_program,
    _schedule_deferred_transition_resource_warmup,
    deferred_transition_program_specs,
    ensure_transition_program_ready,
    resume_deferred_transition_warmup,
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
            self._program_cache = _StubCache()
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
            self._program_cache = _StubCache()

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

    widget = _StubWidget()
    assert ensure_transition_program_ready(widget, "GLCompositorBurnTransition") is True
    assert widget._gl_pipeline.burn_program == 987
    assert widget._gl_pipeline.burn_uniforms == {"uProgress": 5}


def test_transition_program_ensure_skips_make_current_when_already_bound(monkeypatch) -> None:
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

    monkeypatch.setattr("rendering.gl_compositor_pkg.gl_lifecycle.gl", object())

    widget = _StubWidget()
    assert ensure_transition_program_ready(widget, "slide") is True
    assert widget.make_current_calls == 0
    assert widget.done_current_calls == 0


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


def test_noncritical_shader_warmup_waits_during_startup_fade(monkeypatch) -> None:
    class _Pipeline:
        burn_program = 0

    widget = type(
        "_Widget",
        (),
        {
            "_gl_disabled_for_session": False,
            "_startup_transition_warm_queue": [
                ("burn", "burn_program", "burn_uniforms"),
            ],
            "_gl_pipeline": _Pipeline(),
        },
    )()
    scheduled = []
    compiled = []
    monkeypatch.setattr(
        gl_lifecycle,
        "_deferred_warmup_block_reason",
        lambda _widget: "startup_fade",
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "_schedule_deferred_gl_warmup",
        lambda _widget, callback, **_kwargs: scheduled.append(callback),
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "_compile_transition_program",
        lambda *_args: compiled.append("compiled") or True,
    )

    _warm_next_transition_program(widget)

    assert compiled == []
    assert len(widget._startup_transition_warm_queue) == 1
    assert scheduled == [_warm_next_transition_program]


def test_ready_overlay_without_data_does_not_strand_optional_warmup(
    monkeypatch,
) -> None:
    class _Coordinator:
        @staticmethod
        def describe():
            return {
                "state": "READY",
                "participants": ["media"],
                "pending": [],
                "active": [],
                "startup_holds": [],
            }

    class _Display:
        _widget_manager = SimpleNamespace(_fade_coordinator=_Coordinator())

        @staticmethod
        def has_transition_work_pending():
            return False

    monkeypatch.setattr(
        gl_lifecycle,
        "_live_displays_for_compositor",
        lambda _widget: [_Display()],
    )

    assert gl_lifecycle._deferred_warmup_block_reason(object()) is None


def test_noncritical_warmup_resumes_after_coordinated_fade(monkeypatch) -> None:
    class _Pipeline:
        burn_program = 0

    widget = type(
        "_Widget",
        (),
        {
            "_gl_disabled_for_session": False,
            "_startup_transition_warm_queue": [
                ("burn", "burn_program", "burn_uniforms"),
            ],
            "_startup_transition_resource_warm_queue": [],
            "_gl_pipeline": _Pipeline(),
        },
    )()
    blocked = [True]
    compiled = []
    scheduled = []
    monkeypatch.setattr(
        gl_lifecycle,
        "_deferred_warmup_block_reason",
        lambda _widget: "startup_fade" if blocked[0] else None,
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "_schedule_deferred_gl_warmup",
        lambda _widget, callback, **kwargs: scheduled.append(
            (callback, int(kwargs.get("delay_ms", 140)))
        ),
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "acquire_safe_warmup_context",
        lambda *_args, **_kwargs: (lambda: None),
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "_compile_transition_program",
        lambda *_args: compiled.append("burn") or True,
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "_schedule_deferred_transition_resource_warmup",
        lambda _widget: None,
    )

    _warm_next_transition_program(widget)
    assert compiled == []

    blocked[0] = False
    resume_deferred_transition_warmup(widget)
    assert scheduled[-1] == (_warm_next_transition_program, 0)
    scheduled[-1][0](widget)

    assert compiled == ["burn"]
    assert widget._startup_transition_warm_queue == []


def test_transition_beginning_postpones_next_warmup_slice(monkeypatch) -> None:
    class _Pipeline:
        burn_program = 0
        warp_program = 0

    widget = type(
        "_Widget",
        (),
        {
            "_gl_disabled_for_session": False,
            "_startup_transition_warm_queue": [
                ("burn", "burn_program", "burn_uniforms"),
                ("warp", "warp_program", "warp_uniforms"),
            ],
            "_gl_pipeline": _Pipeline(),
        },
    )()
    block_reason = [None]
    compiled = []
    scheduled = []
    monkeypatch.setattr(
        gl_lifecycle,
        "_deferred_warmup_block_reason",
        lambda _widget: block_reason[0],
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "_schedule_deferred_gl_warmup",
        lambda _widget, callback, **_kwargs: scheduled.append(callback),
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "acquire_safe_warmup_context",
        lambda *_args, **_kwargs: (lambda: None),
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "_compile_transition_program",
        lambda _widget, name, *_args: compiled.append(name) or True,
    )

    _warm_next_transition_program(widget)
    assert compiled == ["burn"]
    assert len(widget._startup_transition_warm_queue) == 1

    block_reason[0] = "transition_work"
    _warm_next_transition_program(widget)

    assert compiled == ["burn"]
    assert widget._startup_transition_warm_queue[0][0] == "warp"
    assert scheduled[-1] is _warm_next_transition_program


def test_failed_shader_compile_still_consumes_only_one_warmup_slice(
    monkeypatch,
) -> None:
    class _Pipeline:
        burn_program = 0
        warp_program = 0

    widget = type(
        "_Widget",
        (),
        {
            "_gl_disabled_for_session": False,
            "_startup_transition_warm_queue": [
                ("burn", "burn_program", "burn_uniforms"),
                ("warp", "warp_program", "warp_uniforms"),
            ],
            "_gl_pipeline": _Pipeline(),
        },
    )()
    attempted = []
    scheduled = []
    monkeypatch.setattr(
        gl_lifecycle,
        "_deferred_warmup_block_reason",
        lambda _widget: None,
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "acquire_safe_warmup_context",
        lambda *_args, **_kwargs: (lambda: None),
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "_compile_transition_program",
        lambda _widget, name, *_args: attempted.append(name) or False,
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "_schedule_deferred_gl_warmup",
        lambda _widget, callback, **_kwargs: scheduled.append(callback),
    )

    _warm_next_transition_program(widget)

    assert attempted == ["burn"]
    assert widget._startup_transition_warm_queue == [
        ("warp", "warp_program", "warp_uniforms"),
    ]
    assert scheduled == [_warm_next_transition_program]


def test_safe_warmup_context_trace_reports_hidden_and_deferred_routes(
    monkeypatch,
) -> None:
    released: list[str] = []

    class _Context:
        def makeCurrent(self, _surface):
            return True

        def doneCurrent(self):
            released.append("hidden")

    widget = type(
        "_Widget",
        (),
        {
            "_deferred_warmup_context": None,
            "_deferred_warmup_surface": None,
            "makeCurrent": lambda self: released.append("compositor_make"),
            "doneCurrent": lambda self: released.append("compositor_done"),
        },
    )()
    context = _Context()
    surface = object()
    monkeypatch.setattr(
        gl_lifecycle,
        "_ensure_hidden_shared_warmup_context",
        lambda _widget: (context, surface),
    )

    trace: dict[str, object] = {}
    release = gl_lifecycle.acquire_safe_warmup_context(
        widget,
        fallback_label="test",
        perf_trace=trace,
    )

    assert callable(release)
    assert trace["context_route"] == "hidden_shared"
    assert trace["hidden_context_created"] is True
    assert trace["context_prepare_ms"] >= 0.0
    assert trace["context_make_current_ms"] >= 0.0
    release()
    assert released == ["hidden"]

    monkeypatch.setattr(
        gl_lifecycle,
        "_ensure_hidden_shared_warmup_context",
        lambda _widget: None,
    )
    monkeypatch.setattr(
        gl_lifecycle,
        "_has_live_visible_base_surface",
        lambda _widget: True,
    )
    deferred_trace: dict[str, object] = {}
    assert gl_lifecycle.acquire_safe_warmup_context(
        widget,
        fallback_label="test",
        perf_trace=deferred_trace,
    ) is None
    assert deferred_trace["context_route"] == "deferred"
    assert "compositor_make" not in released
