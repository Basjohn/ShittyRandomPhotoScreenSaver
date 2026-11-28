"""Gradual warm-up (S11): while the displays hold an image, spaced single-program steps on
frames they render anyway prepare the next run, so its first frame compiles nothing.

The display manager and the engine drive it; no window is shown.
"""
from __future__ import annotations

import pytest


pytestmark = pytest.mark.qt



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
        # The idle edge imports nothing (the hitch rows, 22 Nov): the module's import is the display's first unit.
        assert module not in sys.modules and len(deferred) == 1 and not requests
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
    from rendering.quick.transitions.run_geometry import prepare_display_run_geometry

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

    from tests._display_manager_doubles import display_runtime_double, display_unit_double, quick_display_identity

    unit = display_unit_double(
        display_runtime_double(display_identity=quick_display_identity(0, "hidden-key-0", (0, 0, 1920, 1080))),
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
            assert [func for func, _ in submitted] == [prepare_display_run_geometry]
            prepared = submitted[0][1]
            manager.set_random_transition_selection(selection)
            spec = manager._resolve_quick_transition_batch_spec()
            own = manager._display_transition_spec(unit, spec, manager._quick_transition_batch_seed)
            assert dict(own.parameters) == warmed[0]           # the display's own seed and all: nothing re-drawn
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
        _freeze_revealed_generation=lambda: None,   # the reveal's GC freeze (tests/test_gc_freeze_per_generation.py)
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

    from rendering.quick.transitions.request_resolution import ResolvedQuickTransitionSpec

    spec = ResolvedQuickTransitionSpec(transition_id="crossfade", requested_name="Crossfade",
                                       selected_from_random=False, duration_ms=1000, direction=None, parameters=())
    monkeypatch.setattr(source, "resolve_quick_transition_spec", lambda *a, **k: spec)
    manager = DisplayManager(settings_manager=object(), thread_manager=_Threads(), runtime_generation=710)
    manager._prepare_transition_run_geometry = lambda spec, seed, displays: None
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
