from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from widgets.service_widget_runtime import (
    defer_refresh_if_transition,
    defer_value_if_transition,
    ensure_single_shot_timer,
    stop_qtimer_attr,
    sync_refresh_spinner_for_transition,
)


class _ResourceWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.resources: list[tuple[object, str]] = []

    def _register_resource(self, resource: object, name: str) -> None:
        self.resources.append((resource, name))


class _TransitionParent(QWidget):
    def __init__(self, running: bool = False, pending: bool = False) -> None:
        super().__init__()
        self.running = running
        self.pending = pending

    def has_running_transition(self) -> bool:
        return self.running

    def has_transition_work_pending(self) -> bool:
        return self.pending


def test_ensure_single_shot_timer_reuses_existing_timer(qt_app):
    widget = _ResourceWidget()
    calls: list[str] = []
    try:
        timer1 = ensure_single_shot_timer(
            widget,
            attr_name="_timer",
            delay_ms=250,
            timeout_callback=lambda: calls.append("tick"),
            resource_name="service timer",
        )
        timer2 = ensure_single_shot_timer(
            widget,
            attr_name="_timer",
            delay_ms=250,
            timeout_callback=lambda: calls.append("tick"),
            resource_name="service timer",
        )

        assert timer1 is timer2
        assert timer1.isSingleShot() is True
        assert timer1.isActive() is True
        assert widget.resources == [(timer1, "service timer")]
    finally:
        stop_qtimer_attr(widget, "_timer", delete_qtimers=True)
        widget.deleteLater()


def test_defer_refresh_if_transition_sets_pending_and_schedules(qt_app):
    parent = _TransitionParent(running=True)
    widget = _ResourceWidget(parent)
    calls: list[str] = []
    try:
        widget._pending_refresh = False  # type: ignore[attr-defined]

        deferred = defer_refresh_if_transition(
            widget,
            pending_attr="_pending_refresh",
            schedule_callback=lambda: calls.append("scheduled"),
        )

        assert deferred is True
        assert widget._pending_refresh is True  # type: ignore[attr-defined]
        assert calls == ["scheduled"]
    finally:
        widget.deleteLater()
        parent.deleteLater()


def test_defer_value_if_transition_stages_value_and_clears_peer_attrs(qt_app):
    parent = _TransitionParent(pending=True)
    widget = _ResourceWidget(parent)
    calls: list[str] = []
    try:
        widget._staged_value = None  # type: ignore[attr-defined]
        widget._peer_one = "keep?"  # type: ignore[attr-defined]
        widget._peer_two = "keep?"  # type: ignore[attr-defined]

        deferred = defer_value_if_transition(
            widget,
            attr_name="_staged_value",
            value={"payload": 1},
            clear_attrs=("_peer_one", "_peer_two"),
            schedule_callback=lambda: calls.append("scheduled"),
        )

        assert deferred is True
        assert widget._staged_value == {"payload": 1}  # type: ignore[attr-defined]
        assert widget._peer_one is None  # type: ignore[attr-defined]
        assert widget._peer_two is None  # type: ignore[attr-defined]
        assert calls == ["scheduled"]
    finally:
        widget.deleteLater()
        parent.deleteLater()


def test_sync_refresh_spinner_for_transition_suspends_and_resumes(qt_app):
    parent = _TransitionParent(running=False, pending=False)
    widget = _ResourceWidget(parent)
    updates: list[str] = []
    restarts: list[str] = []
    try:
        timer = QTimer(widget)
        timer.setInterval(25)
        timer.start()
        widget._refreshing = True  # type: ignore[attr-defined]
        widget._refresh_spin_timer = timer  # type: ignore[attr-defined]
        widget._refresh_spinner_suspended_for_transition = False  # type: ignore[attr-defined]

        sync_refresh_spinner_for_transition(
            widget,
            True,
            restart_callback=lambda active_timer: restarts.append("restart") or active_timer.start(),
            update_callback=lambda: updates.append("update"),
        )

        assert widget._refresh_spinner_suspended_for_transition is True  # type: ignore[attr-defined]
        assert timer.isActive() is False

        sync_refresh_spinner_for_transition(
            widget,
            False,
            restart_callback=lambda active_timer: restarts.append("restart") or active_timer.start(),
            update_callback=lambda: updates.append("update"),
        )

        assert widget._refresh_spinner_suspended_for_transition is False  # type: ignore[attr-defined]
        assert timer.isActive() is True
        assert restarts == ["restart"]
        assert updates == ["update", "update"]
    finally:
        stop_qtimer_attr(widget, "_refresh_spin_timer", delete_qtimers=True)
        widget.deleteLater()
        parent.deleteLater()
