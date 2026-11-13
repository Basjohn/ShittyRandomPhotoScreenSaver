"""``WeakWidgetSlot``: one public owner of the weak back-reference the Settings helpers keep to their widget.

A helper is a Qt child of the widget it watches and the widget keeps the helper as an attribute; a strong reference
back closes a cycle only the cycle collector can free (inside an event dispatch, R-204's second round). With the slot,
reference counting frees a parentless widget where its owner lets it go.
"""
from __future__ import annotations

import gc
import weakref

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from ui.widgets import combo_knob_overlay, control_shadow
from ui.widgets.weak_widget_slot import WeakWidgetSlot


class _WeakHelper(QObject):
    widget = WeakWidgetSlot()


class _StrongHelper(QObject):
    pass


def _released_without_the_collector(helper_type) -> bool:
    widget = QWidget()
    helper = helper_type(widget)                 # a Qt child of the widget it watches
    helper.widget = widget
    widget._helper = helper                      # the widget keeps its helper
    assert helper.widget is widget
    released = weakref.ref(widget)
    del widget, helper
    return released() is None


def test_the_slot_lets_reference_counting_free_a_watched_widget(qapp):
    gc.disable()
    try:
        assert _released_without_the_collector(_WeakHelper)
        # Negative control: a strong back-reference keeps the pair for the cycle collector.
        assert not _released_without_the_collector(_StrongHelper)
    finally:
        gc.enable()
        gc.collect()


def test_a_cleared_or_dead_slot_reads_none(qapp):
    helper = _WeakHelper()
    assert helper.widget is None
    widget = QWidget()
    helper.widget = widget
    del widget
    assert helper.widget is None
    helper.widget = None
    assert helper.widget is None


def test_every_user_takes_the_one_public_slot():
    for module in (control_shadow, combo_knob_overlay):
        assert module.WeakWidgetSlot is WeakWidgetSlot, module.__name__
        assert not hasattr(module, "_WeakWidgetSlot"), module.__name__
