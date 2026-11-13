"""A class attribute that refers to a widget without keeping it alive (the one owner; the control-shadow helpers and
the combo knob controllers use it)."""
from __future__ import annotations

import weakref


class WeakWidgetSlot:
    """A helper attribute that refers to the widget it watches without keeping it alive.

    Each helper using it is a Qt child of the widget it watches, and the widget keeps the helper as a Python
    attribute (``_control_shadow_helper`` and friends). A strong reference back would close a Python reference cycle,
    so a parentless widget could be freed only by the cycle collector, which runs at any allocation, including inside
    Qt's dispatch of an event to that very widget (through the helper's own ``eventFilter``): the widget and the
    helper were then deleted under the dispatch ("Internal C++ object already deleted", heap corruption). Held
    weakly, the widget is freed by reference counting where its owner lets it go, and the helper dies with it as its
    Qt child.
    """

    def __set_name__(self, owner: type, name: str) -> None:
        self._slot = f"_{name.lstrip('_')}_weak_ref"

    def __get__(self, instance, owner=None):  # noqa: ANN001
        if instance is None:
            return self
        ref = instance.__dict__.get(self._slot)
        return None if ref is None else ref()

    def __set__(self, instance, value) -> None:  # noqa: ANN001
        instance.__dict__[self._slot] = None if value is None else weakref.ref(value)
