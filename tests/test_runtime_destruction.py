"""Focused Qt destruction-barrier and delayed-callback lifecycle regressions."""

from __future__ import annotations

from types import SimpleNamespace
import threading
import weakref
import warnings

from PySide6.QtCore import QObject, QTimer, Signal

from core.resources import ResourceManager, ResourceType
from core.threading.manager import ThreadManager
from engine.display_manager import DisplayManager
from engine.engine_lifecycle import teardown_display_runtime
from engine.runtime_destruction import (
    RuntimeDestructionBarrier,
    continue_after_runtime_destruction,
)
from rendering.custom_layout_manager import CustomLayoutManager
from rendering.widget_manager import WidgetManager
from widgets.clock_ticker import GlobalClockTicker
from widgets.clock_widget import ClockWidget


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


def test_display_teardown_releases_widget_manager_and_fade_owner_before_replacement(
    qt_app,
    qtbot,
):
    class _Display(QObject):
        image_displayed = Signal(str)

        def __init__(self, parent, screen_index):
            super().__init__(parent)
            self.screen_index = int(screen_index)
            self._has_rendered_first_frame = False
            self._runtime_cleanup_complete = False
            self._widget_manager = WidgetManager(self, resource_manager=object())
            self._custom_layout_manager = CustomLayoutManager(self)

        def describe_runtime_state(self):
            return {"screen": self.screen_index}

        def quiesce_for_runtime_pause(self):
            self._widget_manager.prepare_for_runtime_pause()

        def clear(self):
            return None

        def cleanup_runtime(self, _reason):
            self._widget_manager.cleanup()
            self._widget_manager = None
            self._custom_layout_manager.cleanup()
            self._custom_layout_manager = None
            self._runtime_cleanup_complete = True

        def close(self):
            assert self._runtime_cleanup_complete

    manager = DisplayManager(
        resource_manager=object(),
        thread_manager=None,
        runtime_generation=301,
    )
    displays = [_Display(manager, 0), _Display(manager, 1)]
    manager.displays = displays
    widget_manager_refs = [weakref.ref(display._widget_manager) for display in displays]
    fade_coordinator_refs = [
        weakref.ref(display._widget_manager._fade_coordinator)
        for display in displays
    ]
    custom_layout_manager_refs = [
        weakref.ref(display._custom_layout_manager)
        for display in displays
    ]
    engine = SimpleNamespace(
        display_manager=manager,
        resource_manager=_EmptyResourceManager(),
        thread_manager=_EmptyThreadManager(),
        _pending_runtime_destruction_barrier=None,
        _terminal_shutdown_requested=False,
        _display_initialized=True,
        _display_initializing=False,
        _pending_displays_ready_generation=None,
        _loading_in_progress=False,
        _runtime_generation=302,
    )
    del displays
    del manager

    barrier = teardown_display_runtime(engine, reason="settings")
    completed = []
    continue_after_runtime_destruction(
        engine,
        lambda: completed.append(
            all(owner_ref() is None for owner_ref in custom_layout_manager_refs)
        ),
    )

    assert barrier is not None
    qtbot.waitUntil(lambda: completed == [True], timeout=1000)
    assert all(owner_ref() is None for owner_ref in widget_manager_refs)
    assert all(owner_ref() is None for owner_ref in fade_coordinator_refs)
    assert all(owner_ref() is None for owner_ref in custom_layout_manager_refs)
    assert barrier.describe()["python_owners_pending"] == 0


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
    manager._on_startup_reveal_completed(1)
    manager._on_startup_reveal_completed(0)
    manager._on_startup_reveal_completed(0)

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


def test_clock_cleanup_does_not_construct_global_ticker(qt_app):
    GlobalClockTicker.reset()
    owner = SimpleNamespace(_update_time=lambda: None)

    ClockWidget._deactivate_impl(owner)

    assert GlobalClockTicker._instance is None


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
