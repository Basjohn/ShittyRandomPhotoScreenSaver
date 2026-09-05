"""Detailed lifecycle matrix for retained Quick/CUSTOM ownership.

This suite protects the lifecycle invariants exposed by the 2026-09-05
multi-display torture run.  It intentionally spans the current owners instead
of recreating retired QWidget/widget-manager lifecycle seams.

The central rule is that healthy retained editing stays live/in-generation,
while already-proven Qt-object corruption may request one explicit rebuild only
after shared ownership has been terminalized.  Diagnostics never own whether
teardown may proceed.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QRect

from engine.display_manager import DisplayManager
from rendering.custom_layout_session import CustomLayoutSession
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner, _DisplayBinding
from rendering.quick.scene_controller import QuickSceneController
from rendering.quick.widgets import host as host_module
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, RetainedOverlayWidget


class _Settings:
    def __init__(self) -> None:
        self.widgets: dict[str, object] = {}
        self.saved = 0

    def get_widgets_map(self):
        return self.widgets

    def set_widgets_map(self, widgets, *, emit_change=True):
        del emit_change
        self.widgets = widgets

    def save(self):
        self.saved += 1


class _Scene:
    def __init__(self, *, result=(), error: Exception | None = None) -> None:
        self.result = tuple(result)
        self.error = error
        self.calls = 0

    def clear_custom_layout_session(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


class _Coordinator:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.retired = 0

    def retire(self) -> None:
        self.retired += 1
        if self.error is not None:
            raise self.error


class _Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback


class _DeadItem:
    def __init__(self) -> None:
        self.destroyed = _Signal()


def _owner(*, events: list[object] | None = None) -> QuickCustomLayoutOwner:
    sink = events if events is not None else []
    return QuickCustomLayoutOwner(
        settings_manager=_Settings(),
        participants_provider=lambda: (),
        visualizer_provider=lambda: (None, None),
        reload_request=lambda reason: sink.append(("reload", reason)),
    )


def _binding(identity: str, scene: _Scene) -> _DisplayBinding:
    return _DisplayBinding(
        identity=identity,
        monitor_route=identity,
        unit=SimpleNamespace(runtime=SimpleNamespace(scene_controller=scene)),
        screen=object(),
        geometry=QRect(0, 0, 800, 600),
    )


def _arm_owner(owner: QuickCustomLayoutOwner) -> None:
    owner._active = True
    owner._session = CustomLayoutSession()


def test_finish_terminalizes_shared_owner_even_if_coordinator_and_one_display_fail(monkeypatch) -> None:
    # Input suppression is orthogonal to lifecycle ownership; keep this test
    # deterministic and focused on terminalization order/guarantees.
    monkeypatch.setattr(
        "rendering.runtime_input.suppress_runtime_pointer_input",
        lambda *_args, **_kwargs: None,
    )
    owner = _owner()
    first = _Scene(error=RuntimeError("deleted QQuickItem"))
    second = _Scene(result=("ordinary:gmail", "scene_root"))
    coordinator = _Coordinator(error=RuntimeError("listener already dead"))
    _arm_owner(owner)
    owner._bindings = {
        "display:0": _binding("display:0", first),
        "display:1": _binding("display:1", second),
    }
    owner._descriptors = {object(): object()}
    owner._resize_origins = {object(): object()}
    owner._visualizer_pixels_per_world = {object(): 1.25}
    owner._visualizer_move_transfer_latch = {object()}
    owner._coordinator = coordinator

    corruption = owner._finish()

    assert coordinator.retired == 1
    assert first.calls == 1
    assert second.calls == 1
    assert "coordinator:RuntimeError" in corruption
    assert "display:0:scene_cleanup:RuntimeError" in corruption
    assert "display:1:ordinary:gmail" in corruption
    assert "display:1:scene_root" in corruption
    assert owner.is_active is False
    assert owner.session is None
    assert owner._coordinator is None
    assert owner._bindings == {}
    assert owner._descriptors == {}
    assert owner._resize_origins == {}
    assert owner._visualizer_pixels_per_world == {}
    assert owner._visualizer_move_transfer_latch == set()


def test_healthy_geometry_save_stays_live_and_never_requests_reconstruction() -> None:
    events: list[object] = []
    owner = _owner(events=events)
    _arm_owner(owner)
    owner._live_commit_topology_reason = lambda: None
    owner._promote_live_geometry_commit = lambda: events.append("promote")
    owner._finish = lambda: events.append("finish") or ()

    assert owner.save() is True
    assert events == ["promote", "finish"]


def test_coherent_cross_display_visualizer_save_stays_live_without_teardown_reload() -> None:
    events: list[object] = []
    owner = _owner(events=events)
    _arm_owner(owner)
    owner._live_commit_topology_reason = lambda: "display_transfer"
    owner._cross_display_transfer_is_coherent = lambda: True
    owner._promote_live_geometry_commit = lambda: events.append("promote")
    owner._finish = lambda: events.append("finish") or ()

    assert owner.save() is True
    assert events == ["promote", "finish"]
    assert owner.take_deferred_topology_reconciliation() is None


def test_layout_slot_deferred_save_does_not_consume_live_transfer_exception() -> None:
    events: list[object] = []
    owner = _owner(events=events)
    _arm_owner(owner)
    owner._live_commit_topology_reason = lambda: "display_transfer"
    owner._cross_display_transfer_is_coherent = lambda: True
    owner._promote_live_geometry_commit = lambda: events.append("unexpected_promote")
    owner._finish = lambda: events.append("finish") or ()

    assert owner.save(defer_topology_reconciliation=True) is True
    assert events == ["finish"]
    assert owner.take_deferred_topology_reconciliation() == "display_transfer"
    assert owner.take_deferred_topology_reconciliation() is None


def test_live_promotion_failure_finishes_shared_session_before_one_reconstruction() -> None:
    events: list[object] = []
    owner = _owner(events=events)
    _arm_owner(owner)
    owner._live_commit_topology_reason = lambda: None

    def _broken_promote() -> None:
        events.append("promote")
        raise RuntimeError("dead retained root")

    owner._promote_live_geometry_commit = _broken_promote
    owner._finish = lambda: events.append("finish") or ()

    assert owner.save() is True
    assert events == [
        "promote",
        "finish",
        ("reload", "save_corrupt_retained_runtime"),
    ]


def test_cancel_projection_failure_finishes_shared_session_before_one_reconstruction() -> None:
    events: list[object] = []
    owner = _owner(events=events)

    class _BrokenSession:
        def restore_baseline(self):
            events.append("restore")
            raise RuntimeError("dead retained root")

    owner._active = True
    owner._session = _BrokenSession()
    owner._finish = lambda: events.append("finish") or ()

    assert owner.cancel() is True
    assert events == [
        "restore",
        "finish",
        ("reload", "cancel_corrupt_retained_runtime"),
    ]


def test_unexpected_widget_root_death_is_one_shot_but_intentional_retirement_is_not_corruption(monkeypatch) -> None:
    # The fake item is not a real QObject. Treat it as already gone when explicit
    # retirement runs; the ownership semantics under test are the host maps/ledger.
    monkeypatch.setattr(host_module, "_qobject_is_alive", lambda _obj: False)
    host = OrdinaryWidgetPresentationHost(
        host_item=object(),
        context=object(),
        create_overlay_item=lambda _initial, _context: None,
    )

    unexpected = RetainedOverlayWidget(_DeadItem(), model_identity="gmail")
    unexpected._host = host
    host._live.append(unexpected)
    host._by_model_identity["gmail"] = unexpected

    unexpected._on_item_destroyed()
    unexpected._on_item_destroyed()
    assert host.live_count == 0
    assert host.presentation_for_model_identity("gmail") is None
    assert host.consume_unexpected_qt_deaths() == ("gmail",)
    assert host.consume_unexpected_qt_deaths() == ()

    intentional = RetainedOverlayWidget(_DeadItem(), model_identity="media")
    intentional._host = host
    host._live.append(intentional)
    host._by_model_identity["media"] = intentional
    assert host.retire_widget(intentional) is True
    # Qt may emit destroyed after deleteLater(); explicit retirement cleared the
    # host link first, so it must not be reclassified as unexpected corruption.
    intentional._on_item_destroyed()
    assert host.consume_unexpected_qt_deaths() == ()


def test_scene_root_loss_is_corruption_only_while_generation_admission_is_open() -> None:
    open_scene = SimpleNamespace(
        _readiness=SimpleNamespace(
            admission_open=True,
            qml_objects_retired=False,
            runtime_generation=17,
        ),
        _window=SimpleNamespace(screen_index=1),
        _scene_root=object(),
        _unexpected_scene_root_loss=False,
    )
    QuickSceneController._on_scene_root_destroyed(open_scene)
    assert open_scene._scene_root is None
    assert open_scene._unexpected_scene_root_loss is True

    retiring_scene = SimpleNamespace(
        _readiness=SimpleNamespace(
            admission_open=False,
            qml_objects_retired=False,
            runtime_generation=17,
        ),
        _window=SimpleNamespace(screen_index=1),
        _scene_root=object(),
        _unexpected_scene_root_loss=False,
    )
    QuickSceneController._on_scene_root_destroyed(retiring_scene)
    assert retiring_scene._scene_root is None
    assert retiring_scene._unexpected_scene_root_loss is False


def test_display_diagnostics_are_observational_and_one_broken_display_does_not_abort_snapshot() -> None:
    class _BrokenDisplay:
        screen_index = 1

        def describe_runtime_state(self):
            raise RuntimeError("deleted DisplayScene root")

    class _HealthyDisplay:
        screen_index = 0

        def describe_runtime_state(self):
            return {"screen_index": 0, "healthy": True}

    manager = SimpleNamespace(displays=(_BrokenDisplay(), _HealthyDisplay()))
    states = DisplayManager.describe_display_states(manager)

    assert len(states) == 2
    assert states[0]["screen_index"] == 1
    assert "RuntimeError" in states[0]["diagnostic_error"]
    assert states[1] == {"screen_index": 0, "healthy": True}
