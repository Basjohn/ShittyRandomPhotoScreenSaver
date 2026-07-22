from __future__ import annotations

import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from rendering.transition_controller import TransitionController
from transitions.base_transition import BaseTransition, TransitionState


class _Transition(BaseTransition):
    def __init__(self, compositor=None):
        super().__init__(duration_ms=100)
        self._compositor = compositor
        self._animation_id = "animation"
        self.stop_calls = 0
        self.cleanup_calls = 0

    def start(self, old_pixmap, new_pixmap, widget):
        del old_pixmap, new_pixmap, widget
        self._set_state(TransitionState.RUNNING)
        return True

    def stop(self):
        self.stop_calls += 1
        self._set_state(TransitionState.CANCELLED)
        self.finished.emit()

    def cleanup(self):
        self.cleanup_calls += 1

    def complete(self):
        self._set_state(TransitionState.FINISHED)
        self.finished.emit()


class _Compositor:
    def __init__(self):
        self.cancel_calls: list[bool] = []

    def cancel_current_transition(self, *, snap_to_new=True):
        self.cancel_calls.append(bool(snap_to_new))


@pytest.mark.qt_no_exception_capture
def test_natural_completion_clears_owner_before_notifications(qt_app, monkeypatch):
    parent = QWidget()
    compositor = _Compositor()
    parent._gl_compositor = compositor
    controller = TransitionController(parent)
    monkeypatch.setattr(controller, "_start_watchdog", lambda *_args: None)
    transition = _Transition(compositor)
    notification_state: list[tuple[object, str]] = []

    assert controller.start_transition(
        transition,
        QPixmap(),
        QPixmap(),
        on_finished=lambda: notification_state.append(
            (controller.current_transition, controller.describe_state()["terminal_phase"])
        ),
    )

    transition.complete()

    assert notification_state == [(None, "completion_applied")]
    assert controller.current_transition is None
    assert controller.describe_state()["terminal_phase"] == "idle"
    assert transition.cleanup_calls == 1
    assert compositor.cancel_calls == []


@pytest.mark.qt_no_exception_capture
def test_quiesce_disconnects_success_path_and_cancels_once(qt_app, monkeypatch):
    parent = QWidget()
    compositor = _Compositor()
    parent._gl_compositor = compositor
    controller = TransitionController(parent)
    monkeypatch.setattr(controller, "_start_watchdog", lambda *_args: None)
    transition = _Transition(compositor)
    finished: list[str] = []

    assert controller.start_transition(
        transition,
        QPixmap(),
        QPixmap(),
        on_finished=lambda: finished.append("finished"),
    )

    controller.begin_quiesce(reason="test", snap_to_new=True)

    assert finished == []
    assert controller.current_transition is None
    assert controller.admission_open is False
    assert controller.describe_state()["terminal_phase"] == "idle"
    assert compositor.cancel_calls == [True]
    assert transition.stop_calls == 1
    assert transition.cleanup_calls == 1


@pytest.mark.qt_no_exception_capture
def test_runtime_resume_opens_a_fresh_controller_generation(qt_app):
    parent = QWidget()
    controller = TransitionController(parent)
    original_generation = controller.describe_state()["generation"]

    controller.begin_quiesce(reason="settings", snap_to_new=True)
    assert controller.admission_open is False

    controller.resume_after_quiesce()

    assert controller.admission_open is True
    assert controller.current_transition is None
    assert controller.describe_state()["terminal_phase"] == "idle"
    assert controller._generation > original_generation


@pytest.mark.qt_no_exception_capture
def test_notification_failure_cannot_strand_terminal_phase(qt_app, monkeypatch):
    parent = QWidget()
    controller = TransitionController(parent)
    monkeypatch.setattr(controller, "_start_watchdog", lambda *_args: None)
    transition = _Transition()

    assert controller.start_transition(transition, QPixmap(), QPixmap())
    generation = controller.active_generation

    with pytest.raises(RuntimeError, match="observer failed"):
        controller._finish_transition(
            transition,
            generation=generation,
            on_finished=lambda: (_ for _ in ()).throw(RuntimeError("observer failed")),
        )

    assert controller.current_transition is None
    assert controller.describe_state()["terminal_phase"] == "idle"
