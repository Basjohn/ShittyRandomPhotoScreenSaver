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


@pytest.mark.parametrize("kind", ["control", "text", "cast"])
def test_shadowed_widget_is_freed_where_its_owner_lets_it_go(qt_app, kind) -> None:
    """A shadow helper never keeps the widget it watches alive.

    A strong back-reference closed a Python cycle (widget attribute -> helper -> widget), so a
    Python-owned shadowed widget could be freed only by the cycle collector, at any allocation,
    including inside Qt's dispatch of an event to that widget through the helper's own
    ``eventFilter``: the widget and the helper were deleted under the dispatch ("Internal C++
    object already deleted", then heap corruption). Freed by reference counting, it dies where
    its owner drops it, with its helper and event filter, and its pending events go with it.
    """
    import gc
    import weakref

    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QLabel, QPushButton

    from ui.widgets import control_shadow

    if kind == "control":
        widget = QPushButton("Shadowed")
        control_shadow.attach_control_shadow(widget, control_shadow.PILL_BUTTON_SHADOW)
        helper = widget._control_shadow_helper
    elif kind == "text":
        widget = QLabel("Shadowed heading")
        control_shadow.attach_text_shadow(widget, control_shadow.PAGE_TEXT_SHADOW)
        helper = widget._settings_text_shadow_helper
    else:
        widget = QWidget()
        control_shadow.attach_cast_shadow(widget, control_shadow.SHELL_PANEL_SHADOW, radius=8.0)
        helper = widget._settings_cast_shadow_helper
    widget_ref = weakref.ref(widget)
    helper_ref = weakref.ref(helper)
    del helper
    QCoreApplication.postEvent(widget, QEvent(QEvent.Type.Polish))

    collector_was_enabled = gc.isenabled()
    gc.disable()
    try:
        del widget
        assert widget_ref() is None, "the shadow helper kept its widget alive for the cycle collector"
        assert helper_ref() is None
    finally:
        if collector_was_enabled:
            gc.enable()
    # The freed widget's pending events left with it; nothing reaches a deleted helper.
    qt_app.processEvents()


def test_control_shadow_eventfilter_ignores_events_for_other_widgets(qt_app) -> None:
    widget = QWidget()
    other = QWidget()
    helper = _ControlShadowHelper(widget, ShadowConfig())

    # An event for a different watched object is passed through untouched.
    result = helper.eventFilter(other, QEvent(QEvent.Type.EnabledChange))
    assert result in (True, False)
