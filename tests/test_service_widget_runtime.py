from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from widgets.service_widget_runtime import (
    begin_fetch_guard,
    defer_refresh_if_transition,
    defer_value_if_transition,
    end_fetch_guard,
    ensure_single_shot_timer,
    has_visible_fallback_content,
    preserve_visible_fallback,
    reset_deferred_runtime_state,
    stop_overlay_timer_pair,
    stop_qtimer_attr,
    sync_refresh_spinner_for_transition,
    trigger_manual_refresh,
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


def test_begin_fetch_guard_blocks_duplicate_fetches(qt_app):
    widget = _ResourceWidget()
    try:
        widget._fetch_in_progress = False  # type: ignore[attr-defined]

        first = begin_fetch_guard(widget)
        second = begin_fetch_guard(widget)

        assert first is True
        assert second is False
        assert widget._fetch_in_progress is True  # type: ignore[attr-defined]
    finally:
        end_fetch_guard(widget)
        widget.deleteLater()


def test_begin_fetch_guard_respects_widget_lock(qt_app):
    import threading

    widget = _ResourceWidget()
    try:
        widget._fetch_in_progress = False  # type: ignore[attr-defined]
        widget._fetch_lock = threading.Lock()  # type: ignore[attr-defined]

        first = begin_fetch_guard(widget, lock_attr="_fetch_lock")
        end_fetch_guard(widget, lock_attr="_fetch_lock")
        second = begin_fetch_guard(widget, lock_attr="_fetch_lock")

        assert first is True
        assert second is True
        assert widget._fetch_in_progress is True  # type: ignore[attr-defined]
    finally:
        end_fetch_guard(widget, lock_attr="_fetch_lock")
        widget.deleteLater()


def test_trigger_manual_refresh_short_circuits_when_fetch_already_running(qt_app):
    widget = _ResourceWidget()
    calls: list[str] = []
    try:
        widget._enabled = True  # type: ignore[attr-defined]
        widget._fetch_in_progress = True  # type: ignore[attr-defined]

        started = trigger_manual_refresh(
            widget,
            defer_refresh=lambda: calls.append("defer") or False,
            fetch_callback=lambda: calls.append("fetch") or True,
        )

        assert started is True
        assert calls == []
    finally:
        widget.deleteLater()


def test_trigger_manual_refresh_runs_feedback_and_stops_on_failed_queue(qt_app):
    widget = _ResourceWidget()
    calls: list[str] = []
    try:
        widget._enabled = True  # type: ignore[attr-defined]
        widget._fetch_in_progress = False  # type: ignore[attr-defined]

        started = trigger_manual_refresh(
            widget,
            defer_refresh=lambda: calls.append("defer") or False,
            fetch_callback=lambda: calls.append("fetch") or False,
            start_feedback=lambda: calls.append("start"),
            stop_feedback=lambda: calls.append("stop"),
        )

        assert started is False
        assert calls == ["defer", "start", "fetch", "stop"]
    finally:
        widget.deleteLater()


def test_has_visible_fallback_content_requires_truthy_content_and_valid_flag(qt_app):
    widget = _ResourceWidget()
    try:
        widget._has_displayed_valid_data = False  # type: ignore[attr-defined]
        widget._items = ["visible"]  # type: ignore[attr-defined]
        assert has_visible_fallback_content(widget, content_attr="_items") is False

        widget._has_displayed_valid_data = True  # type: ignore[attr-defined]
        assert has_visible_fallback_content(widget, content_attr="_items") is True

        widget._items = []  # type: ignore[attr-defined]
        assert has_visible_fallback_content(widget, content_attr="_items") is False
    finally:
        widget.deleteLater()


def test_preserve_visible_fallback_returns_true_only_for_trustworthy_visible_content(qt_app):
    widget = _ResourceWidget()
    try:
        widget._has_displayed_valid_data = True  # type: ignore[attr-defined]
        widget._items = ["visible"]  # type: ignore[attr-defined]
        assert preserve_visible_fallback(widget, content_attr="_items") is True

        widget._items = []  # type: ignore[attr-defined]
        assert preserve_visible_fallback(widget, content_attr="_items") is False
    finally:
        widget.deleteLater()


def test_reset_deferred_runtime_state_stops_timers_and_clears_attrs(qt_app):
    widget = _ResourceWidget()
    try:
        widget._timer_one = QTimer(widget)  # type: ignore[attr-defined]
        widget._timer_two = QTimer(widget)  # type: ignore[attr-defined]
        widget._timer_one.start(1000)  # type: ignore[attr-defined]
        widget._timer_two.start(1000)  # type: ignore[attr-defined]
        widget._pending = True  # type: ignore[attr-defined]
        widget._payload = {"x": 1}  # type: ignore[attr-defined]

        reset_deferred_runtime_state(
            widget,
            timer_attrs=("_timer_one", "_timer_two"),
            state_attrs=(("_pending", False), ("_payload", None)),
            delete_qtimers=True,
        )

        assert widget._timer_one is None  # type: ignore[attr-defined]
        assert widget._timer_two is None  # type: ignore[attr-defined]
        assert widget._pending is False  # type: ignore[attr-defined]
        assert widget._payload is None  # type: ignore[attr-defined]
    finally:
        widget.deleteLater()


def test_stop_overlay_timer_pair_stops_handle_and_qtimer(qt_app):
    class _Handle:
        def __init__(self) -> None:
            self.stopped = False

        def stop(self) -> None:
            self.stopped = True

    widget = _ResourceWidget()
    try:
        handle = _Handle()
        widget._handle = handle  # type: ignore[attr-defined]
        widget._timer = QTimer(widget)  # type: ignore[attr-defined]
        widget._timer.start(1000)  # type: ignore[attr-defined]

        stop_overlay_timer_pair(
            widget,
            handle_attr="_handle",
            qtimer_attr="_timer",
            delete_qtimers=True,
        )

        assert handle.stopped is True
        assert widget._handle is None  # type: ignore[attr-defined]
        assert widget._timer is None  # type: ignore[attr-defined]
    finally:
        widget.deleteLater()
