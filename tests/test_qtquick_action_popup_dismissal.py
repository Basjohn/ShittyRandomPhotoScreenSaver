"""Regression: an admitted press outside a widget dismisses its action popup.

Gmail's three-dot menu used to only close on a press inside the Gmail card (its
own in-bounds scrim). A press anywhere outside the card left it open. The host
now closes any widget action popup (a QML item exposing ``activeActionIdentity``)
when an admitted scene press lands outside that widget's item -- event-driven, no
timer/poll. A press inside the widget is still left to the widget's own scrim.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QPointF

from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost


class _FakeItem:
    def __init__(self, identity: str, *, press_inside: bool) -> None:
        self._props = {
            "activeActionIdentity": identity,
            "activeActionMessageId": "msg-1" if identity else "",
        }
        self._press_inside = press_inside

    def property(self, name: str):
        return self._props.get(name)

    def setProperty(self, name: str, value) -> bool:
        self._props[name] = value
        return True

    def mapFromScene(self, point: QPointF) -> QPointF:
        return point

    def contains(self, _point: QPointF) -> bool:
        return self._press_inside


def _dismiss(widgets):
    stub = SimpleNamespace(_retired=False, _live=list(widgets))
    return OrdinaryWidgetPresentationHost.dismiss_outside_action_popups(
        stub, QPointF(500.0, 500.0)
    )


def test_press_outside_widget_dismisses_open_action_popup():
    widget = SimpleNamespace(item=_FakeItem("row_5", press_inside=False))
    changed = _dismiss([widget])
    assert changed is True
    assert widget.item.property("activeActionIdentity") == ""
    assert widget.item.property("activeActionMessageId") == ""


def test_press_inside_widget_leaves_popup_to_its_own_scrim():
    widget = SimpleNamespace(item=_FakeItem("row_5", press_inside=True))
    changed = _dismiss([widget])
    assert changed is False
    assert widget.item.property("activeActionIdentity") == "row_5"


def test_widget_without_action_popup_is_untouched():
    # No activeActionIdentity property -> property() returns None -> skipped.
    plain_item = _FakeItem("", press_inside=False)
    plain_item._props.pop("activeActionIdentity")
    widget = SimpleNamespace(item=plain_item)
    assert _dismiss([widget]) is False


def test_closed_popup_is_not_re_dismissed():
    widget = SimpleNamespace(item=_FakeItem("", press_inside=False))
    assert _dismiss([widget]) is False
