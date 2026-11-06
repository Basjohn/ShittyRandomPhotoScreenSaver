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
    """Counts every program compile, graphics or compute."""

    def __init__(self, monkeypatch) -> None:
        self.total = 0
        for name in ("compile_program", "compile_compute_program"):
            original = getattr(gl_resources, name)

            def counted(*args, _original=original, **kwargs):
                self.total += 1
                return _original(*args, **kwargs)

            for module in (gl_resources, scene_resources):
                monkeypatch.setattr(module, name, counted)


class _Work(_Compiles):
    """Counts program compiles, per-run texture allocations (S10) and stream-ring allocations
    (S14), the units a warm-up step may do one of."""

    def __init__(self, monkeypatch) -> None:
        super().__init__(monkeypatch)
        from rendering.quick.scene3d.motion import MotionBlur
        from rendering.quick.scene3d.post import BloomChain
        from rendering.quick.scene3d.stream import StreamRing
        from rendering.quick.scene3d.target import SceneTarget
        from rendering.quick.scene3d.trails import MotionTrails

        self.allocations = []
        for owner, name in ((SceneTarget, "_allocate"), (SceneTarget, "_allocate_resolve"),
                            (MotionBlur, "_allocate"), (BloomChain, "_allocate"), (MotionTrails, "_allocate"),
                            (StreamRing, "_allocate")):
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
                          settings={"scene3d_detail": "High", section: dict(_SETUPS[setup])})
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
        assert work.allocations == allocated, "the warmed run's first frames allocated textures or buffers"
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
        run = capture.run("block_spins", direction="left", settings={"scene3d_detail": "High"})
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


def test_idle_no_stage_job_does_one_step_without_repainting(qt_app, monkeypatch):
    import threading
    from types import SimpleNamespace
    from rendering.quick.render import background_item
    from rendering.quick.render.background_item import _TransitionWarmStepJob

    monkeypatch.setattr(background_item, "QOpenGLContext", SimpleNamespace(currentContext=lambda: object()))
    operations = []

    class _Window:
        def beginExternalCommands(self): operations.append("begin")
        def endExternalCommands(self): operations.append("end")
        def update(self): raise AssertionError("idle preparation must never repaint")

    class _Node:
        def warm_step(self, name, parameters):
            operations.append((name, parameters))
            return False

    class _Reporter:
        class _Signal:
            def emit(self, *args): operations.append(("done", args))
        finished = _Signal()

    # Retain the GUI-affine owners for the full synthetic render-job lifetime.
    # They are retained by the real display manager and BackgroundRenderItem;
    # an anonymous temporary is gone before a weak-ref-only job can run.
    window, reporter, retirement = _Window(), _Reporter(), _Node()
    job = _TransitionWarmStepJob(window, retirement, ("crumble", {"x": 1}),
                                 threading.Event(), reporter, 17)
    assert job._window_ref() is window and job._reporter_ref() is reporter
    job.run()
    assert operations == ["begin", ("crumble", {"x": 1}), "end", ("done", (17, False))]
    operations.clear()
    cancelled = threading.Event()
    cancelled.set()
    _TransitionWarmStepJob(window, _Node(), ("crumble", {}), cancelled, reporter, 19).run()
    assert not operations


def test_idle_render_job_with_retired_gui_owners_fails_closed_without_repainting(qt_app, monkeypatch):
    """The real manager owns these wrappers, but a retired window must be a no-op.

    This is deliberately the inverse of the preceding live-owner fixture:
    the job must never keep a GUI QObject alive merely to make its test pass.
    """
    import gc
    import threading
    import weakref
    from types import SimpleNamespace
    from rendering.quick.render import background_item
    from rendering.quick.render.background_item import _TransitionWarmStepJob

    operations = []
    monkeypatch.setattr(
        background_item, "QOpenGLContext",
        SimpleNamespace(currentContext=lambda: operations.append("context")),
    )

    class _Window:
        def beginExternalCommands(self): operations.append("begin")
        def endExternalCommands(self): operations.append("end")
        def update(self): raise AssertionError("retired job must never repaint")

    class _Retirement:
        def warm_step(self, *_args):
            operations.append("compile")
            return True

    class _Reporter:
        finished = SimpleNamespace(emit=lambda *_args: operations.append("done"))

    window, reporter = _Window(), _Reporter()
    job = _TransitionWarmStepJob(
        window, _Retirement(), ("crumble", {}), threading.Event(), reporter, 18,
    )
    window_ref, reporter_ref = weakref.ref(window), weakref.ref(reporter)
    del window, reporter
    gc.collect()
    assert window_ref() is None and reporter_ref() is None
    job.run()
    assert operations == []


def test_a_starting_run_cancels_the_idle_job(qt_app):
    import threading
    from rendering.quick.render.background_item import BackgroundRenderItem

    item = BackgroundRenderItem()
    token = threading.Event()
    item._warm_up_cancel = token
    capture = TransitionCapture(64, 64)
    try:
        item.set_transition_run(capture.run("glass_shatter", direction="left"))
    finally:
        capture.close()
    assert token.is_set() and item._warm_up_cancel is None


def test_display_manager_warms_only_after_both_displays_idle_and_serially(qt_app, monkeypatch):
    import sys
    from types import SimpleNamespace
    from engine.display_manager import DisplayManager, IDLE_TRANSITION_WARM_STEP_SPACING_MS
    from rendering.quick.transitions.request_resolution import RandomTransitionSelection

    module = "rendering.quick.transitions.implementations.crumble"
    monkeypatch.delitem(sys.modules, module, raising=False)
    requests, deferred = [], []

    class _Settings:
        def get(self, key, default=None):
            if key == "transitions":
                return {"type": "Crossfade", "random_always": True,
                        "pool": {"Crumble": True, "Slide": True}}
            return True if key == "display.hw_accel" else default
        def get_bool(self, key, default=False): return bool(self.get(key, default))

    class _Threads:
        def single_shot(self, delay, callback, *args):
            deferred.append((delay, lambda: callback(*args)))
            return SimpleNamespace(active=True)

    def _unit(name):
        return SimpleNamespace(
            display_bounds=lambda: SimpleNamespace(x=0, y=0, width=1920, height=1080),
            transition_logical_size=lambda: (1920.0, 1081.0),
            schedule_transition_warm_step=lambda transition, params, reporter, ticket:
                (requests.append((name, transition, params, ticket)) or True),
            cancel_transition_warm_up=lambda: None,
        )

    manager = DisplayManager(settings_manager=_Settings(), thread_manager=_Threads(), runtime_generation=706)
    try:
        manager.displays = [_unit("D0"), _unit("D1")]
        manager._authoritative_first_frame_emitted = True
        manager._transition_work_pending = True
        manager.prepare_next_transition(RandomTransitionSelection("Crumble"))
        assert not deferred and not requests
        manager._transition_work_pending = False
        manager.prepare_next_transition(RandomTransitionSelection("Crumble"))
        assert module in sys.modules and len(deferred) == 1 and not requests
        assert deferred[0][0] == IDLE_TRANSITION_WARM_STEP_SPACING_MS
        deferred.pop(0)[1]()
        assert [item[0] for item in requests] == ["D0"]
        ticket = requests[-1][3]
        manager._on_idle_warm_step_finished(ticket, False)
        deferred.pop(0)[1]()
        assert [item[0] for item in requests] == ["D0", "D0"]
        manager._on_idle_warm_step_finished(requests[-1][3], True)
        deferred.pop(0)[1]()
        assert [item[0] for item in requests] == ["D0", "D0", "D1"]
        manager._on_idle_warm_step_finished(requests[-1][3], True)
        assert not deferred and manager._idle_warm_seed is None
    finally:
        manager._cancel_idle_transition_warmup()
        manager.displays = []


def test_the_next_batch_meets_the_spec_and_geometry_prepared_while_idle(qt_app):
    from types import SimpleNamespace

    from engine.display_manager import DisplayManager
    from rendering.quick.transitions.request_resolution import RandomTransitionSelection
    from rendering.quick.transitions.run_geometry import prepare_run_geometry

    submitted, warmed, deferred = [], [], []

    class _Threads:
        def submit_compute_task(self, func, *args, **kwargs):
            submitted.append((func, args))
            return "task"
        def single_shot(self, delay, callback, *args):
            deferred.append((delay, lambda: callback(*args)))
            return SimpleNamespace(active=True)

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
        schedule_transition_warm_step=lambda transition_id, parameters, reporter, ticket: (warmed.append(parameters) or True),
        cancel_transition_warm_up=lambda: None,
    )
    settings = _Settings()
    manager = DisplayManager(settings_manager=settings, thread_manager=_Threads(), runtime_generation=707)
    try:
        manager.displays = [unit]
        manager._authoritative_first_frame_emitted = True
        selection = RandomTransitionSelection("Glass Shatter")
        for _ in range(3):
            submitted.clear(), warmed.clear()
            manager.prepare_next_transition(selection)
            manager.prepare_next_transition(selection)          # a second idle edge: same spec
            assert len(deferred) == 1 and len(warmed) == 0
            deferred.pop(0)[1]()
            assert len(warmed) == 1
            assert [func for func, _ in submitted] == [prepare_run_geometry]
            prepared = submitted[0][1]
            manager.set_random_transition_selection(selection)
            spec = manager._resolve_quick_transition_batch_spec()
            assert dict(spec.parameters) == warmed[0]          # seed and all: nothing re-drawn
            assert submitted[-1][1] == prepared                 # same preparation supplied to admission
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
    engine = SimpleNamespace(
        _prepare_next_transition=lambda: calls.append("next"),
        _ban_advance_pending=False,  # no user-initiated Ban Image transaction
    )
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



def test_stale_reservation_and_recreation_cancel_idle_gl_jobs(qt_app, monkeypatch):
    """No stale callbacks after new batch, session teardown or new reservation."""
    from types import SimpleNamespace
    import engine.display_manager as source
    from engine.display_manager import DisplayManager

    warmed, deferred, cancelled = [], [], []
    class _Threads:
        def single_shot(self, delay, callback, *args):
            deferred.append((delay, lambda: callback(*args)))
            return SimpleNamespace(active=True)

    monkeypatch.setattr(source, "resolve_quick_transition_spec",
                        lambda *a, **k: SimpleNamespace(transition_id="crossfade", parameters={}))
    monkeypatch.setattr(source, "preload_quick_transition_implementation", lambda *a: None)
    manager = DisplayManager(settings_manager=object(), thread_manager=_Threads(), runtime_generation=710)
    manager._prepare_transition_run_geometry = lambda spec: None
    manager._authoritative_first_frame_emitted = True
    manager.displays = [SimpleNamespace(
        schedule_transition_warm_step=lambda *args: (warmed.append(args) or True),
        cancel_transition_warm_up=lambda: cancelled.append(True),
    )]
    try:
        manager.prepare_next_transition(None)
        assert len(deferred) == 1
        _, stale = deferred.pop(0)
        manager._begin_quick_transition_batch({0})
        stale()
        assert warmed == [] and cancelled
        manager._transition_work_pending = False
        manager._reset_quick_transition_batch()
        manager.prepare_next_transition(None)
        deferred.pop(0)[1]()
        assert len(warmed) == 1
        old_ticket = warmed[-1][-1]
        manager._cancel_idle_transition_warmup()
        manager._on_idle_warm_step_finished(old_ticket, False)
        assert not deferred
    finally:
        manager._cancel_idle_transition_warmup()
        manager.displays = []
