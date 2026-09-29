"""Gradual warm-up (S11): while the displays hold an image, spaced single-program steps on
frames they render anyway prepare the next run, so its first frame compiles nothing.

Offscreen GL through the transition capture harness; no window is shown.
"""
from __future__ import annotations

import pytest

import rendering.quick.render.gl_resources as gl_resources
import rendering.quick.scene3d.resources as scene_resources
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

_CASES = (
    ("exploding_tiles", "center_out", "exploding_tiles"),
    ("glass_shatter", "left", "glass_shatter"),
    ("crumble", None, "crumble"),
    ("pixel_accretion", "left", "pixel_accretion"),
    ("block_spins", "left", "blockspin"),
)
_SETUPS = (
    {},                                                                    # canonical defaults
    {"antialiasing": "4x", "motion_blur": "On", "motion_trails": "On", "bloom": "On", "edge_glass": "Both"},
    {"antialiasing": "Off", "motion_blur": "On"},
    {"antialiasing": "Off", "motion_trails": "On"},
)


class _Compiles:
    """Counts every program compile."""

    def __init__(self, monkeypatch) -> None:
        self.total = 0
        original = gl_resources.compile_program

        def compile_program(*args, **kwargs):
            self.total += 1
            return original(*args, **kwargs)

        for module in (gl_resources, scene_resources):
            monkeypatch.setattr(module, "compile_program", compile_program)


class _Work(_Compiles):
    """Counts program compiles and per-run texture allocations (S10), the units a warm-up
    step may do one of."""

    def __init__(self, monkeypatch) -> None:
        super().__init__(monkeypatch)
        from rendering.quick.scene3d.motion import MotionBlur
        from rendering.quick.scene3d.post import BloomChain
        from rendering.quick.scene3d.target import SceneTarget
        from rendering.quick.scene3d.trails import MotionTrails

        self.allocations = []
        for owner, name in ((SceneTarget, "_allocate"), (SceneTarget, "_allocate_resolve"),
                            (MotionBlur, "_allocate"), (BloomChain, "_allocate"), (MotionTrails, "_allocate")):
            original = getattr(owner, name)

            def counted(*args, _original=original, _label=f"{owner.__name__}.{name}", **kwargs):
                self.allocations.append(_label)
                self.total += 1
                return _original(*args, **kwargs)

            monkeypatch.setattr(owner, name, counted)


@pytest.mark.parametrize("effect,direction,section", _CASES)
@pytest.mark.parametrize("setup", range(len(_SETUPS)))
def test_after_warming_a_runs_first_frames_compile_and_allocate_nothing(qt_app, monkeypatch, effect, direction,
                                                                         section, setup):
    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run(effect, direction=direction, duration_ms=3000,
                          settings={"detail_3d": "High", section: dict(_SETUPS[setup])})
        parameters = run.request.parameter_dict()
        size = (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step(run.request.transition_id, parameters, size):
            steps += 1
            assert work.total <= steps, "a warm-up step did more than one compile or allocation"
            assert steps < 100, "warm-up never finished"
        assert work.total > 1
        warmed, allocated = work.total, list(work.allocations)
        for progress in (0.0, 0.3):              # an endpoint frame and a mid-run frame
            capture.render(run, progress)
        assert work.allocations == allocated, "the warmed run's first frames allocated textures"
        assert work.total == warmed, "the warmed run's first frames compiled a program"
        assert capture.host.warm_step(run.request.transition_id, parameters, size)   # nothing left
        capture.host.park()
        renderer = capture.host._implementations[run.request.transition_id]
        assert not renderer._target.has_resources and not renderer._trails.has_resources   # none held
    finally:
        capture.close()


def test_without_a_render_size_the_warm_up_compiles_only(qt_app, monkeypatch):
    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("block_spins", direction="left", settings={"detail_3d": "High"})
        while not capture.host.warm_step(run.request.transition_id, run.request.parameter_dict()):
            pass
        assert work.allocations == []
    finally:
        capture.close()


def test_the_warm_up_render_size_is_never_smaller_than_the_window():
    """Before any render, the node estimates the size from its logical size; the native
    size may round either way, so the estimate must cover all of them."""
    from rendering.quick.render.background_node import BackgroundRenderNode
    from rendering.quick.render.telemetry import RenderNodeTelemetry
    from rendering.quick.scene3d.target import _bucket

    node = BackgroundRenderNode(RenderNodeTelemetry(gui_thread_id=1), screen_index=0)
    for ratio in (1.0, 1.25, 1.5, 1.75, 2.0, 2.5):
        for native in range(1000, 4400, 7):
            logical = round(native / ratio)
            node._logical_size, node._device_pixel_ratio = (float(logical), float(logical)), ratio
            estimate = node._warm_size()[0]
            assert estimate >= native and _bucket(estimate) - _bucket(native) <= 64
    node._render_target_size = (2560, 1442)                      # once a render has seen it
    assert node._warm_size() == (2560, 1442)


def test_a_warm_step_is_one_plain_compile_and_leaves_nothing_running(qt_app, monkeypatch):
    """No driver compile threads, no status polling: a step compiles one program and returns."""
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, warm_programs

    capture = TransitionCapture(64, 64)
    resources = MeshResources("warm test")
    try:
        compiles = _Compiles(monkeypatch)
        entries = [(resources, *UNDERLAY_PROGRAM), (resources, "second", *UNDERLAY_PROGRAM[1:])]
        assert warm_programs(entries) is False and compiles.total == 1 and resources.has_program("underlay")
        assert warm_programs(entries) is False and compiles.total == 2
        assert warm_programs(entries) is True and compiles.total == 2
        # The driver's parallel compile threads are never asked for.
        import rendering.quick.render.gl_resources as source
        assert "parallel_shader_compile" not in open(source.__file__, encoding="utf-8").read()
        assert "COMPLETION_STATUS" not in open(scene_resources.__file__, encoding="utf-8").read()
        assert gl.glGetError() == gl.GL_NO_ERROR
    finally:
        resources.release_resources()
        capture.close()


def test_the_background_nodes_own_program_is_a_warm_up_step_too(qt_app, monkeypatch):
    """The node's quad program would otherwise compile on its first run frame."""
    from rendering.quick.render import background_node
    from rendering.quick.render.telemetry import RenderNodeTelemetry

    capture = TransitionCapture(64, 64)
    node = background_node.BackgroundRenderNode(RenderNodeTelemetry(gui_thread_id=1), screen_index=0)
    try:
        compiles = _Compiles(monkeypatch)
        monkeypatch.setattr(background_node, "compile_program", gl_resources.compile_program)
        run = capture.run("crumble")
        parameters = run.request.parameter_dict()
        assert node.warm_step("crumble", parameters) is False
        assert compiles.total == 1 and node._program                 # the node's program, alone
        steps = 1
        while not node.warm_step("crumble", parameters):
            steps += 1
            assert compiles.total <= steps and steps < 100
        assert compiles.total > 1                                    # then the transition's programs
    finally:
        node.releaseResources()
        capture.close()


def test_the_warm_up_steps_on_spaced_rendered_frames_and_stops_when_done_or_cancelled(qt_app, monkeypatch):
    from PySide6.QtCore import QObject, Signal

    import rendering.quick.render.background_item as background_item
    from rendering.quick.render.background_item import _TransitionWarmUp

    clock = [100.0]
    monkeypatch.setattr(background_item.time, "monotonic", lambda: clock[0])
    spacing = _TransitionWarmUp.SPACING_S

    def frames(window, count, frame_s):
        for _ in range(count):              # frames the window renders anyway
            clock[0] += frame_s
            window.beforeRendering.emit()

    class _Window(QObject):
        beforeRendering = Signal()

        def __init__(self):
            super().__init__()
            self.external = []

        def beginExternalCommands(self):
            self.external.append("begin")

        def endExternalCommands(self):
            self.external.append("end")

    class _Retirement:
        def __init__(self, steps_needed):
            self.steps, self.needed = [], steps_needed

        def warm_step(self, transition_id, parameters):
            self.steps.append((transition_id, dict(parameters)))
            return len(self.steps) >= self.needed

    window, retirement = _Window(), _Retirement(3)
    warm_up = _TransitionWarmUp(window, retirement, "glass_shatter", {"sheen": 0.5})
    frame_s = 1.0 / 144.0
    per_step = int(spacing / frame_s) + 1
    frames(window, per_step - 1, frame_s)
    assert retirement.steps == []                                       # not on the frames right away
    frames(window, per_step * 6, frame_s)
    assert retirement.steps == [("glass_shatter", {"sheen": 0.5})] * 3   # spaced steps, then done
    assert not warm_up.active
    assert window.external == ["begin", "end"] * 3                     # GL work bracketed for Quick
    retirement = _Retirement(100)
    warm_up = _TransitionWarmUp(window, retirement, "crumble", {})
    frames(window, 1, spacing)
    warm_up.cancel()
    frames(window, 3, spacing)
    assert len(retirement.steps) == 1 and not warm_up.active
    retirement = _Retirement(100)
    _TransitionWarmUp(window, retirement, "crumble", {})
    clock[0] += 60.0                                                   # a window that renders nothing
    assert retirement.steps == []                                      # does no warm-up at all


def test_a_starting_run_cancels_the_warm_up(qt_app):
    from rendering.quick.render.background_item import BackgroundRenderItem

    item = BackgroundRenderItem()
    item.request_warm_up("glass_shatter", {})
    assert item._warm_up is None                     # no window: nothing renders, nothing to warm

    class _Pending:
        cancelled = False

        def cancel(self):
            self.cancelled = True

    pending = _Pending()
    item._warm_up = pending
    capture = TransitionCapture(64, 64)
    try:
        item.set_transition_run(capture.run("glass_shatter", direction="left"))
    finally:
        capture.close()
    assert pending.cancelled and item._warm_up is None


def test_the_display_manager_warms_the_next_transition_on_every_display_while_idle(qt_app, monkeypatch):
    import sys
    from types import SimpleNamespace

    from engine.display_manager import DisplayManager
    from rendering.quick.transitions.request_resolution import RandomTransitionSelection

    module = "rendering.quick.transitions.implementations.crumble"
    monkeypatch.delitem(sys.modules, module, raising=False)
    requests = []

    class _Settings:
        def get(self, key, default=None):
            if key == "transitions":
                return {"type": "Crossfade", "random_always": True, "pool": {"Crumble": True, "Slide": True}}
            if key == "display.hw_accel":
                return True
            return default

        def get_bool(self, key, default=False):
            return bool(self.get(key, default))

    def _unit(name):
        return SimpleNamespace(
            display_bounds=lambda: SimpleNamespace(x=0.0, y=0.0, width=1920.0, height=1080.0),
            transition_logical_size=lambda: (1920.0, 1081.0),
            request_transition_warm_up=lambda transition_id, parameters: requests.append((name, transition_id,
                                                                                           parameters)),
        )

    manager = DisplayManager(settings_manager=_Settings(), thread_manager=None, runtime_generation=706)
    try:
        manager.displays = [_unit("left"), _unit("right")]
        manager.set_random_transition_selection(RandomTransitionSelection("Crumble"))
        spec = manager._resolve_quick_transition_batch_spec()
        # The batch about to run starts within milliseconds: nothing to warm there.
        assert requests == [] and module not in sys.modules
        manager._reset_quick_transition_batch()
        manager._transition_work_pending = True
        manager.prepare_next_transition(RandomTransitionSelection("Crumble"))
        assert requests == []                                # not while image work is pending
        manager._transition_work_pending = False
        manager.prepare_next_transition(RandomTransitionSelection("Crumble"))
        assert module in sys.modules                         # imported here, not on a render thread
        assert [(name, transition_id) for name, transition_id, _ in requests] == [("left", "crumble"),
                                                                                  ("right", "crumble")]
        assert requests[0][2] is requests[1][2]              # one shared parameter set, as a batch has
        unseeded = {key: value for key, value in spec.parameters if key != "seed"}
        assert {key: value for key, value in requests[0][2].items() if key != "seed"} == unseeded
    finally:
        manager.displays = []


def test_the_next_batch_meets_the_spec_and_geometry_prepared_while_idle(qt_app):
    from types import SimpleNamespace

    from engine.display_manager import DisplayManager
    from rendering.quick.transitions.request_resolution import RandomTransitionSelection
    from rendering.quick.transitions.run_geometry import prepare_run_geometry

    submitted, warmed = [], []

    class _Threads:
        def submit_compute_task(self, func, *args, **kwargs):
            submitted.append((func, args))
            return "task"

    class _Settings:
        def __init__(self):
            self.transitions = {"type": "Crossfade", "random_always": True,
                                "pool": {"Glass Shatter": True, "Slide": True}}

        def get(self, key, default=None):
            if key == "transitions":
                return self.transitions
            return True if key == "display.hw_accel" else default

        def get_bool(self, key, default=False):
            return bool(self.get(key, default))

    unit = SimpleNamespace(
        display_bounds=lambda: SimpleNamespace(x=0.0, y=0.0, width=1920.0, height=1080.0),
        transition_logical_size=lambda: (1920.0, 1081.0),
        request_transition_warm_up=lambda transition_id, parameters: warmed.append(parameters),
    )
    settings = _Settings()
    manager = DisplayManager(settings_manager=settings, thread_manager=_Threads(), runtime_generation=707)
    try:
        manager.displays = [unit]
        selection = RandomTransitionSelection("Glass Shatter")
        for _ in range(3):
            submitted.clear(), warmed.clear()
            manager.prepare_next_transition(selection)
            manager.prepare_next_transition(selection)          # a second idle edge: same spec
            assert warmed[0] == warmed[1]
            assert [func for func, _ in submitted] == [prepare_run_geometry] * 2
            prepared = submitted[0][1]
            manager.set_random_transition_selection(selection)
            spec = manager._resolve_quick_transition_batch_spec()
            assert dict(spec.parameters) == warmed[0]          # seed and all: nothing re-drawn
            assert submitted[-1][1] == prepared                 # the geometry COMPUTE already built
            manager._reset_quick_transition_batch()
        # Settings changed after the warm-up: the batch follows Settings, not the warm-up.
        manager.prepare_next_transition(selection)
        from core.settings.default_contract import require_canonical_default

        shards = int(require_canonical_default("transitions.glass_shatter")["shards"])
        shards = shards + 12 if shards < 150 else shards - 12
        settings.transitions = {**settings.transitions, "glass_shatter": {"shards": shards}}
        manager.set_random_transition_selection(selection)
        spec = manager._resolve_quick_transition_batch_spec()
        assert spec.parameters and dict(spec.parameters) != warmed[-1]
        manager._reset_quick_transition_batch()
        # Without an idle warm-up the batch draws fresh values, as before.
        spec_a = manager._resolve_quick_transition_batch_spec()
        manager._reset_quick_transition_batch()
        spec_b = manager._resolve_quick_transition_batch_spec()
        assert dict(spec_a.parameters)["seed"] != dict(spec_b.parameters)["seed"]
    finally:
        manager.displays = []


class _PoolSettings:
    def __init__(self, pool):
        from rendering.transition_registry import get_transition_setting_names

        names = get_transition_setting_names()
        self.transitions = {
            "type": "Crossfade",
            "random_always": True,
            "pool": {name: name in pool for name in names},
            "activation": {name: True for name in names},
        }

    def get(self, key, default=None):
        return self.transitions if key == "transitions" else default

    def get_bool(self, key, default=False):
        return True

    def set(self, key, value):
        pass

    def save(self):
        pass


def _engine(settings, idle=True):
    from types import SimpleNamespace

    from engine.screensaver_engine import RandomTransitionHistory, ScreensaverEngine

    prepared = []
    manager = SimpleNamespace(
        has_transition_work_pending=lambda: not idle,
        prepare_next_transition=prepared.append,
        set_random_transition_selection=lambda selection: None,
    )
    engine = SimpleNamespace(settings_manager=settings, display_manager=manager,
                             _random_transition_history=RandomTransitionHistory())
    for name in ("_prepare_next_transition", "_prepare_random_transition_if_needed",
                 "_publish_random_transition_selection"):
        setattr(engine, name, getattr(ScreensaverEngine, name).__get__(engine))
    return engine, prepared


def test_the_next_random_pick_is_made_when_the_displays_go_idle_and_taken_by_the_next_rotation():
    settings = _PoolSettings({"Crumble", "Glass Shatter", "Exploding Tiles", "Slide"})
    engine, prepared = _engine(settings)
    for _ in range(40):
        engine._prepare_next_transition()
        engine._prepare_next_transition()                    # a second idle edge keeps the pick
        assert len(prepared) == 2 and prepared[0] == prepared[1]
        assert engine._prepare_random_transition_if_needed() == prepared[0].transition_name
        assert engine._random_transition_history.current == prepared[0]
        assert engine._random_transition_history.upcoming is None
        previous = prepared[0].transition_name
        prepared.clear()
        engine._prepare_next_transition()
        assert prepared[0].transition_name != previous       # no immediate repeat, as before
        prepared.clear()


def test_a_reserved_pick_that_left_the_pool_is_replaced_and_busy_displays_get_nothing():
    settings = _PoolSettings({"Crumble", "Glass Shatter"})
    engine, prepared = _engine(settings)
    engine._prepare_next_transition()
    reserved = prepared[0].transition_name
    remaining = ({"Crumble", "Glass Shatter"} - {reserved}).pop()
    settings.transitions["pool"][reserved] = False
    assert engine._prepare_random_transition_if_needed() == remaining
    busy, prepared = _engine(settings, idle=False)
    busy._prepare_next_transition()
    assert prepared == [] and busy._random_transition_history.upcoming is None


def test_fixed_transitions_are_warmed_without_a_random_pick():
    settings = _PoolSettings({"Crumble"})
    settings.transitions["random_always"] = False
    engine, prepared = _engine(settings)
    engine._prepare_next_transition()
    assert prepared == [None]


def test_the_engine_prepares_the_next_transition_when_a_transition_completes(monkeypatch):
    from types import SimpleNamespace

    import engine.image_pipeline as image_pipeline
    from engine.screensaver_engine import ScreensaverEngine

    calls = []
    monkeypatch.setattr(image_pipeline, "notify_transition_complete", lambda engine, screen: calls.append("prefetch"))
    engine = SimpleNamespace(_prepare_next_transition=lambda: calls.append("next"))
    ScreensaverEngine._on_display_transition_completed(engine, 0)
    assert calls == ["prefetch", "next"]


def test_the_engine_prepares_the_first_transition_once_the_startup_reveal_completes(monkeypatch):
    from types import SimpleNamespace

    import core.logging.logger as logger_module
    import core.performance.resource_metrics as resource_metrics
    from engine.screensaver_engine import ScreensaverEngine

    calls = []
    monkeypatch.setattr(resource_metrics, "log_lifecycle_resource_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(logger_module, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(logger_module, "is_lifecycle_logging_enabled", lambda: False)
    current = [True]
    engine = SimpleNamespace(
        _is_runtime_identity_current=lambda generation, manager: current[0],
        _record_stale_runtime_callback=lambda *args: calls.append("stale"),
        _end_replacement_watchdog=lambda reason: calls.append("watchdog"),
        _runtime_lifecycle_event="cold_start",
        _prepare_next_transition=lambda: calls.append("next"),
    )
    ScreensaverEngine._on_startup_reveal_completed(engine, 3, object(), 3)
    assert calls == ["watchdog", "next"]
    calls.clear()
    current[0] = False                                   # a retired runtime prepares nothing
    ScreensaverEngine._on_startup_reveal_completed(engine, 3, object(), 3)
    assert calls == ["stale"]

