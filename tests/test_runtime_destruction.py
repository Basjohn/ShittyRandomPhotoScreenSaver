"""Focused Qt destruction-barrier and delayed-callback lifecycle regressions."""

from __future__ import annotations

import gc
from types import SimpleNamespace
import threading
import weakref
import warnings

import pytest
from PySide6.QtCore import QObject, QTimer
from shiboken6 import isValid as is_valid_qobject

from core.resources import ResourceManager, ResourceType
from core.threading.manager import ThreadManager
from engine.display_manager import DisplayManager
from engine.runtime_destruction import (
    RuntimeDestructionBarrier,
    continue_after_runtime_destruction,
    create_runtime_destruction_barrier,
)
from widgets.clock_ticker import GlobalClockTicker


class _EmptyResourceManager:
    @staticmethod
    def get_resources_by_runtime_generation(_generation):
        return ()


class _EmptyThreadManager:
    @staticmethod
    def get_lifecycle_ownership_snapshot():
        return {
            "active_tasks": (),
            "ui": {
                "queued_by_generation": {},
                "scheduled_single_shots_by_generation": {},
            },
        }


def _engine() -> SimpleNamespace:
    return SimpleNamespace(
        resource_manager=_EmptyResourceManager(),
        thread_manager=_EmptyThreadManager(),
        _pending_runtime_destruction_barrier=None,
        _terminal_shutdown_requested=False,
    )


def test_qobject_destruction_precedes_replacement_continuation(qt_app, qtbot):
    engine = _engine()
    root = QObject()
    child = QObject(root)
    events = []
    root.destroyed.connect(lambda *_args: events.append("root_destroyed"))
    child.destroyed.connect(lambda *_args: events.append("child_destroyed"))

    barrier = RuntimeDestructionBarrier(
        engine,
        reason="custom_edit",
        retiring_generation=7,
    )
    engine._pending_runtime_destruction_barrier = barrier
    barrier.watch_qobject(root, label="root")
    barrier.watch_qobject(child, label="child")
    barrier.seal()
    barrier.then(lambda: events.append("replacement"))

    root.deleteLater()
    qtbot.waitUntil(lambda: "replacement" in events, timeout=1000)

    assert events.index("root_destroyed") < events.index("replacement")
    assert events.index("child_destroyed") < events.index("replacement")
    assert engine._pending_runtime_destruction_barrier is None


def test_python_cycle_blocks_replacement_until_explicitly_released(qt_app, qtbot):
    class _CyclicOwner:
        pass

    engine = _engine()
    root = QObject()
    cyclic_owner = _CyclicOwner()
    cyclic_owner.self = cyclic_owner
    completed = []

    barrier = RuntimeDestructionBarrier(
        engine,
        reason="settings",
        retiring_generation=8,
    )
    engine._pending_runtime_destruction_barrier = barrier
    barrier.watch_qobject(root, label="root")
    barrier.watch_python_owner(cyclic_owner, label="cyclic-owner")
    barrier.seal()
    barrier.then(lambda: completed.append(True))

    root.deleteLater()
    qtbot.waitUntil(
        lambda: barrier.describe()["qobjects_pending"] == 0,
        timeout=1000,
    )

    assert completed == []
    assert barrier.describe()["python_owners_by_class"] == {"cyclic-owner": 1}
    assert cyclic_owner.self is cyclic_owner

    cyclic_owner.self = None
    del cyclic_owner
    qtbot.waitUntil(lambda: completed == [True], timeout=1000)


@pytest.mark.parametrize("display_count", [1, 2])
def test_teardown_barrier_releases_display_roots_without_gc(
    qt_app,
    qtbot,
    display_count,
    monkeypatch,
    request,
):
    """The replacement barrier observes the current per-display retirement roots
    and drains them without gc.collect().

    A retiring display publishes its roots through the current
    ``runtime_retirement_roots()`` contract: the runtime/window QObjects plus the
    plain-Python generation owners (the unit itself, its presenter and its
    visualizer owner). ``create_runtime_destruction_barrier`` collects them from
    ``DisplayManager.collect_runtime_retirement_roots()`` and holds only weakrefs.
    The retiring owner graph must be acyclic enough to release by refcount alone,
    and the QObject roots must invalidate on deleteLater even while their Python
    wrappers are deliberately kept alive — no gc.collect() is permitted.
    """

    gc_was_enabled = gc.isenabled()
    gc.disable()
    if gc_was_enabled:
        request.addfinalizer(gc.enable)

    def _unexpected_collection(*_args, **_kwargs):
        raise AssertionError("runtime teardown must not call gc.collect()")

    monkeypatch.setattr(gc, "collect", _unexpected_collection)

    class _Runtime(QObject):
        """Stand-in Quick runtime QObject root; its window is a QObject child."""

        def __init__(self):
            super().__init__()
            self.window = QObject(self)

    class _PlainOwner:
        """A plain-Python per-generation owner (presenter / visualizer style)."""

    class _DisplayUnit:
        """Minimal current-contract display unit.

        The real QuickDisplayUnit is itself a plain-Python generation owner whose
        ``runtime_retirement_roots()`` publishes its runtime/window QObjects and
        its plain-Python owners (self, presenter, visualizer owner).
        """

        def __init__(self, screen_index):
            self.screen_index = int(screen_index)
            self._runtime = _Runtime()
            self._presenter = _PlainOwner()
            self._visualizer_owner = _PlainOwner()

        def runtime_retirement_roots(self):
            return (
                (self._runtime, self._runtime.window),
                (self, self._presenter, self._visualizer_owner),
            )

    manager = DisplayManager(
        resource_manager=object(),
        thread_manager=None,
        runtime_generation=301,
    )
    units = [_DisplayUnit(screen_index) for screen_index in range(display_count)]
    manager.displays = list(units)

    unit_refs = [weakref.ref(unit) for unit in units]
    presenter_refs = [weakref.ref(unit._presenter) for unit in units]
    visualizer_refs = [weakref.ref(unit._visualizer_owner) for unit in units]
    # Keep the runtime Python wrappers alive after their C++ QObjects are
    # destroyed: the barrier must observe C++ invalidation, not wrapper refcount.
    runtime_wrappers = [unit._runtime for unit in units]

    engine = _engine()

    barrier = create_runtime_destruction_barrier(
        engine,
        manager,
        reason="settings",
        retiring_generation=301,
        purpose="replacement",
    )
    engine._pending_runtime_destruction_barrier = barrier
    barrier.seal()

    # The barrier watched the exact plain-Python owners each display published
    # (unit + presenter + visualizer owner per display).
    assert barrier.describe()["python_owners_pending"] >= 3 * display_count
    assert barrier.is_complete is False

    completed = []
    continue_after_runtime_destruction(engine, lambda: completed.append(True))

    # Drop every strong reference to the retiring generation's owners and queue
    # the QObject roots for destruction. The manager QObject tree is also watched,
    # so it is retired here too.
    for runtime in runtime_wrappers:
        runtime.deleteLater()
    manager.displays = []
    units.clear()
    manager.deleteLater()
    del manager

    qtbot.waitUntil(lambda: completed == [True], timeout=1000)

    assert all(unit_ref() is None for unit_ref in unit_refs)
    assert all(owner_ref() is None for owner_ref in presenter_refs)
    assert all(owner_ref() is None for owner_ref in visualizer_refs)
    # C++ roots invalidated even though the Python wrappers are still held.
    assert all(not is_valid_qobject(runtime) for runtime in runtime_wrappers)
    assert barrier.describe()["python_owners_pending"] == 0
    assert barrier.describe()["qobjects_pending"] == 0


def test_display_manager_retires_only_owned_signal_connections_without_warnings(
    qt_app,
):
    manager = DisplayManager(
        resource_manager=object(),
        thread_manager=None,
        runtime_generation=303,
    )
    calls = []

    def _on_exit():
        calls.append("exit")

    manager.exit_requested.connect(_on_exit)
    manager.track_runtime_signal_connection("exit_requested", _on_exit)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        manager.retire_runtime()

    manager.exit_requested.emit()
    assert calls == []
    assert manager._runtime_signal_connections == []
    assert not [
        warning
        for warning in caught
        if issubclass(warning.category, RuntimeWarning)
        and "disconnect" in str(warning.message).lower()
    ]


def test_terminal_shutdown_discards_pending_replacement(qt_app, qtbot):
    engine = _engine()
    root = QObject()
    completed = []
    barrier = RuntimeDestructionBarrier(
        engine,
        reason="monitor_topology",
        retiring_generation=9,
    )
    engine._pending_runtime_destruction_barrier = barrier
    barrier.watch_qobject(root)
    barrier.seal()
    barrier.then(lambda: completed.append(True))

    engine._terminal_shutdown_requested = True
    root.deleteLater()
    qtbot.waitUntil(lambda: barrier.is_complete, timeout=1000)

    assert completed == []
    assert engine._pending_runtime_destruction_barrier is None


def test_timeout_releases_barrier_ownership_without_continuing(
    qt_app,
    qtbot,
    monkeypatch,
):
    from engine import runtime_destruction

    engine = _engine()
    root = QObject()
    exits = []
    completed = []
    monkeypatch.setattr(
        runtime_destruction.QApplication,
        "exit",
        staticmethod(lambda code: exits.append(int(code))),
    )
    barrier = RuntimeDestructionBarrier(
        engine,
        reason="settings",
        retiring_generation=10,
        timeout_ms=50,
    )
    engine._pending_runtime_destruction_barrier = barrier
    barrier.watch_qobject(root)
    barrier.seal()
    barrier.then(lambda: completed.append(True))

    qtbot.waitUntil(lambda: exits == [1], timeout=1000)

    assert completed == []
    assert barrier.is_complete
    assert engine._pending_runtime_destruction_barrier is None
    root.deleteLater()


def test_runtime_single_shot_is_cancelled_by_generation(qt_app, qtbot):
    class _Owner(QObject):
        def __init__(self):
            super().__init__()
            self._runtime_generation = 41
            self.calls = 0

        def publish(self):
            self.calls += 1

    owner = _Owner()
    ThreadManager.single_shot(5000, owner.publish)

    assert ThreadManager.cancel_scheduled_single_shots(41) == 1
    qtbot.wait(20)

    assert owner.calls == 0
    owner.deleteLater()


def test_cancelled_runtime_closure_releases_plain_owner_without_gc(qt_app, qtbot):
    """Cancellation must drop closure payloads before the destruction barrier."""

    import gc

    class _PlainOwner:
        _runtime_generation = 411

    def _schedule_owner_closure():
        owner = _PlainOwner()

        def _publish():
            return owner

        _publish._srpss_timer_owner = owner
        _publish._srpss_runtime_generation = owner._runtime_generation
        ThreadManager.single_shot(60_000, _publish)
        return weakref.ref(owner)

    was_enabled = gc.isenabled()
    gc.disable()
    try:
        owner_ref = _schedule_owner_closure()
        assert owner_ref() is not None
        assert ThreadManager.cancel_scheduled_single_shots(411) == 1
        qtbot.waitUntil(lambda: owner_ref() is None, timeout=1000)
    finally:
        if was_enabled:
            gc.enable()


def test_queued_ui_callback_is_rejected_for_retired_generation(qt_app, qtbot):
    class _Owner(QObject):
        def __init__(self):
            super().__init__()
            self._runtime_generation = 42
            self.calls = 0

        def publish(self):
            self.calls += 1

    owner = _Owner()
    worker = threading.Thread(
        target=lambda: ThreadManager.run_on_ui_thread(owner.publish)
    )
    worker.start()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert ThreadManager.cancel_queued_ui_callbacks(42) == 1
    qtbot.wait(20)

    assert owner.calls == 0
    owner.deleteLater()


def test_display_manager_publishes_generation_milestones_once(qt_app):
    manager = DisplayManager(
        resource_manager=object(),
        thread_manager=None,
        runtime_generation=52,
    )
    manager.displays = [
        SimpleNamespace(screen_index=0),
        SimpleNamespace(screen_index=1),
    ]
    first_frames = []
    reveals = []
    manager.authoritative_first_frames_ready.connect(first_frames.append)
    manager.startup_reveal_completed.connect(reveals.append)

    manager._on_image_displayed(0, "first.jpg")
    manager._on_image_displayed(1, "second.jpg")
    manager._on_image_displayed(1, "later.jpg")
    # Repeated reveal-finished callbacks for the live generation still publish
    # the startup-reveal milestone exactly once (dedupe via _startup_reveal_emitted).
    manager._on_quick_startup_reveal_finished(52)
    manager._on_quick_startup_reveal_finished(52)

    assert first_frames == [52]
    assert reveals == [52]
    manager.disconnect_monitor_detection()
    manager.displays = []
    manager.deleteLater()


def test_clock_ticker_does_not_strongly_retain_bound_widget_owner(qt_app):
    class _Owner:
        _runtime_generation = 61

        def tick(self):
            return None

    GlobalClockTicker.reset()
    ticker = GlobalClockTicker()
    owner = _Owner()
    owner_ref = weakref.ref(owner)
    ticker.subscribe(owner.tick)

    assert ticker.get_lifecycle_ownership_snapshot()["total"] == 1
    del owner

    assert owner_ref() is None
    assert ticker.get_lifecycle_ownership_snapshot()["total"] == 0
    GlobalClockTicker.reset()


def test_barrier_waits_for_retired_global_subscription(qt_app, qtbot):
    class _Owner:
        _runtime_generation = 62

        def tick(self):
            return None

    GlobalClockTicker.reset()
    ticker = GlobalClockTicker()
    owner = _Owner()
    ticker.subscribe(owner.tick)
    engine = _engine()
    completed = []
    barrier = RuntimeDestructionBarrier(
        engine,
        reason="settings",
        retiring_generation=62,
    )
    engine._pending_runtime_destruction_barrier = barrier
    barrier.seal()
    barrier.then(lambda: completed.append(True))

    qtbot.wait(50)
    assert completed == []

    ticker.unsubscribe(owner.tick)
    qtbot.waitUntil(lambda: completed == [True], timeout=1000)
    GlobalClockTicker.reset()


def test_barrier_uses_unbounded_clock_generation_counts(qt_app, qtbot):
    GlobalClockTicker.reset()
    ticker = GlobalClockTicker()
    filler_callbacks = []
    for generation in range(100, 164):
        callback = lambda: None
        callback._srpss_runtime_generation = generation
        filler_callbacks.append(callback)
        ticker.subscribe(callback)

    retired_callback = lambda: None
    retired_callback._srpss_runtime_generation = 164
    ticker.subscribe(retired_callback)
    snapshot = ticker.get_lifecycle_ownership_snapshot()
    assert snapshot["omitted"] == 1
    assert snapshot["subscribers_by_generation"]["164"] == 1

    engine = _engine()
    completed = []
    barrier = RuntimeDestructionBarrier(
        engine,
        reason="settings",
        retiring_generation=164,
    )
    engine._pending_runtime_destruction_barrier = barrier
    barrier.seal()
    barrier.then(lambda: completed.append(True))

    qtbot.wait(50)
    assert completed == []

    ticker.unsubscribe(retired_callback)
    qtbot.waitUntil(lambda: completed == [True], timeout=1000)
    GlobalClockTicker.reset()


def test_five_alternating_recreation_cycles_reach_zero_retired_ownership(
    qt_app,
    qtbot,
):
    class _RuntimeOwner(QObject):
        def __init__(self, generation, parent=None):
            super().__init__(parent)
            self._runtime_generation = generation
            self.calls = 0

        def publish(self):
            self.calls += 1

        def compute(self, value):
            return value

        def computed(self, _result, *, payload):
            self.calls += int(payload == 1)

    resource_manager = ResourceManager()
    thread_manager = ThreadManager.create_helper_manager(
        resource_manager=resource_manager,
        io_workers=1,
        compute_workers=1,
    )
    engine = SimpleNamespace(
        resource_manager=resource_manager,
        thread_manager=thread_manager,
        _pending_runtime_destruction_barrier=None,
        _terminal_shutdown_requested=False,
    )
    completed = []
    destroyed = []
    GlobalClockTicker.reset()
    ticker = GlobalClockTicker()
    ticker.set_thread_manager(thread_manager)
    try:
        for generation, reason in enumerate(
            ("settings", "custom_edit", "settings", "custom_edit", "settings"),
            start=201,
        ):
            root = QObject()
            root._runtime_generation = generation
            owner = _RuntimeOwner(generation, root)
            timer = QTimer(root)
            timer._runtime_generation = generation
            timer.start(60_000)
            for label, obj, resource_type in (
                ("root", root, ResourceType.GUI_COMPONENT),
                ("owner", owner, ResourceType.GUI_COMPONENT),
                ("timer", timer, ResourceType.TIMER),
            ):
                resource_manager.register(
                    obj,
                    resource_type,
                    f"cycle {generation} {label}",
                    runtime_generation=generation,
                    lifetime_scope="runtime",
                )
                obj.destroyed.connect(
                    lambda *_args, g=generation, name=label: destroyed.append(
                        (g, name)
                    )
                )

            ticker.subscribe(owner.publish)
            ThreadManager.single_shot(60_000, owner.publish)
            lane = thread_manager.create_compute_lane(
                owner.compute,
                owner.computed,
                lane_id=f"lifecycle-cycle-{generation}",
                category="test.lifecycle_lane",
                runtime_generation=generation,
            )

            barrier = RuntimeDestructionBarrier(
                engine,
                reason=reason,
                retiring_generation=generation,
            )
            engine._pending_runtime_destruction_barrier = barrier
            barrier.watch_qobject(root, label="DisplayManager")
            barrier.watch_qobject(owner, label="RuntimeOwner")
            barrier.watch_qobject(timer, label="RuntimeTimer")

            barrier.seal()
            pending = barrier.describe()
            assert pending["resources_pending"] >= 3
            assert pending["thread_work_pending"] >= 1
            assert pending["global_subscriptions_pending"] == 1
            assert barrier.is_complete is False

            assert ThreadManager.cancel_scheduled_single_shots(generation) == 1
            ThreadManager.cancel_queued_ui_callbacks(generation)
            lane.stop()
            ticker.unsubscribe(owner.publish)
            timer.stop()
            barrier.then(lambda g=generation: completed.append(g))
            root.deleteLater()

            qtbot.waitUntil(
                lambda g=generation: bool(completed and completed[-1] == g),
                timeout=1000,
            )

            assert not resource_manager.get_resources_by_runtime_generation(
                generation
            )
            thread_snapshot = thread_manager.get_lifecycle_ownership_snapshot()
            generation_key = str(generation)
            assert generation_key not in thread_snapshot["ui"][
                "scheduled_single_shots_by_generation"
            ]
            assert generation_key not in thread_snapshot["ui"][
                "queued_by_generation"
            ]
            assert generation_key not in ticker.get_lifecycle_ownership_snapshot()[
                "subscribers_by_generation"
            ]
            assert not any(
                item.get("runtime_generation") == generation
                for item in thread_snapshot["active_tasks"]
            )

        assert completed == [201, 202, 203, 204, 205]
        assert len(destroyed) == 15
        assert {generation for generation, _name in destroyed} == set(completed)
    finally:
        GlobalClockTicker.reset()
        thread_manager.shutdown(wait=True, timeout=1.0)
        resource_manager.shutdown()
