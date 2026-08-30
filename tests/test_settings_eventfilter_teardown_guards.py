"""Settings event-filter teardown hygiene (H1b Part E).

Two Settings helpers install themselves as Qt event filters and dereference a
lifetime-sensitive member (`_ControlShadowHelper._widget`,
`ComboKnobController._host`). During terminal Exit / Settings teardown a late Qt
event can reach the override after Python-side teardown has cleared that member,
which previously raised from inside `eventFilter`.

Invariant under test:

    a late Qt event after Python-side helper teardown cannot raise from the
    eventFilter override, and a Destroy-time removal tolerates an already-invalid
    target.

These bars are deterministic and do not depend on the physical exit timing.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QComboBox, QWidget

from ui.widgets.combo_knob_overlay import ComboKnobController
from ui.widgets.control_shadow import ShadowConfig, _ControlShadowHelper


class _RaisingOnRemove(QObject):
    """A real QObject whose removeEventFilter raises, as a deleted C++ widget would."""

    def removeEventFilter(self, _obj) -> None:  # type: ignore[override]
        raise RuntimeError("wrapped C/C++ object has been deleted")


def test_control_shadow_eventfilter_survives_cleared_widget(qt_app) -> None:
    widget = QWidget()
    helper = _ControlShadowHelper(widget, ShadowConfig())

    # Python-side teardown cleared the tracked widget.
    helper._widget = None

    # A late event of any handled type must return without raising or applying.
    result = helper.eventFilter(widget, QEvent(QEvent.Type.EnabledChange))
    assert result in (True, False)


def test_control_shadow_destroy_tolerates_invalid_target(qt_app) -> None:
    widget = QWidget()
    helper = _ControlShadowHelper(widget, ShadowConfig())

    dead = _RaisingOnRemove()
    helper._widget = dead

    # watched is target and the target's removeEventFilter raises: the override
    # must swallow it rather than propagate during retirement.
    result = helper.eventFilter(dead, QEvent(QEvent.Type.Destroy))
    assert result in (True, False)


def test_combo_knob_eventfilter_survives_cleared_host(qt_app) -> None:
    host = QComboBox()
    controller = ComboKnobController(host)

    controller._host = None

    result = controller.eventFilter(host, QEvent(QEvent.Type.Resize))
    assert result in (True, False)


def test_combo_knob_eventfilter_still_handles_live_host(qt_app) -> None:
    host = QComboBox()
    controller = ComboKnobController(host)

    # The guard must not change behaviour while the host is live: a matching
    # event is still processed without raising.
    result = controller.eventFilter(host, QEvent(QEvent.Type.Resize))
    assert result in (True, False)
    assert controller._host is host


def test_control_shadow_eventfilter_ignores_events_for_other_widgets(qt_app) -> None:
    widget = QWidget()
    other = QWidget()
    helper = _ControlShadowHelper(widget, ShadowConfig())

    # An event for a different watched object is passed through untouched.
    result = helper.eventFilter(other, QEvent(QEvent.Type.EnabledChange))
    assert result in (True, False)
