"""Regression tests for startup shader/program warmup policy."""

from rendering.gl_compositor_pkg.gl_lifecycle import (
    _schedule_deferred_transition_resource_warmup,
    deferred_transition_program_specs,
    ensure_transition_program_ready,
    startup_transition_program_specs,
    _has_live_visible_base_surface,
)
from widgets.spotify_bars_gl_overlay import prioritized_visualizer_compile_order


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
        "rendering.gl_compositor_pkg.gl_lifecycle.QTimer.singleShot",
        lambda delay, callback: scheduled.append(delay),
    )

    widget = _StubWidget()
    _schedule_deferred_transition_resource_warmup(widget)

    assert widget._startup_transition_resource_warm_queue
    assert "GLCompositorSlideTransition" in widget._startup_transition_resource_warm_queue
    assert scheduled == [140]
