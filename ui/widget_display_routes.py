"""Leaving a widget's Settings page: warn about widgets only a disabled display would show.

A widget routed only to a display that is not enabled in Display settings never appears in
the saver. When the operator leaves the page that owns such a widget (another page, another
tab, Guided Setup or closing Settings), a themed popup offers **Switch For Me** (move it to an
enabled display, then leave) or **Trust Me Bro** (keep it, leave, and stop asking about that
exact arrangement for the rest of this Settings session). Closing the popup is not a decision,
so the operator stays, as Arrange does.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from core.settings.display_selection import describe_monitors, enabled_monitor_numbers
from core.settings.widget_family_catalog import get_widget_member_label
from rendering.widget_descriptors import (
    get_effective_monitor_value_for_widget,
    route_widgets_to_single_monitor,
    widgets_routed_off_monitors,
)
from ui.styled_popup import StyledPopup

SWITCH = "switch"
TRUST = "trust"


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


class DisplayRouteLeaveGuard:
    """One page owner's guard (Widgets, Visualizers): asks, moves or remembers the trust."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self._trusted: set[tuple[str, str, frozenset[int]]] = set()

    def resolve(
        self,
        parent: QWidget | None,
        widget_ids: Iterable[str],
        *,
        flush: Callable[[], None] | None = None,
        on_switched: Callable[[], None] | None = None,
    ) -> bool:
        """Before leaving the page owning ``widget_ids``: False means stay on it."""

        widget_ids = tuple(widget_ids)
        if not widget_ids:
            return True
        if flush is not None:
            flush()          # the page's coalesced edits first: the check reads saved settings
        widgets = self._settings.get("widgets", {})
        if not isinstance(widgets, Mapping):
            return True
        enabled = enabled_monitor_numbers(self._settings.get("display.show_on_monitors"),
                                          len(QGuiApplication.screens()))
        if not enabled:
            return True      # no display at all: nothing to switch to, and not this page's concern
        routes = {}
        for widget_id in widgets_routed_off_monitors(widgets, widget_ids, enabled):
            route = get_effective_monitor_value_for_widget(widget_id, widgets)
            if (widget_id, route, enabled) not in self._trusted:
                routes[widget_id] = route
        if not routes:
            return True
        target = min(enabled)
        names = [get_widget_member_label(widget_id) for widget_id in routes]
        off_numbers = {int(route) for route in routes.values()}
        verb, them = ("is", "it") if len(names) == 1 else ("are", "them")
        isnt = "isn't" if len(off_numbers) == 1 else "aren't"
        popup = StyledPopup(
            parent.window() if parent is not None else None,
            "Widget On A Disabled Display",
            f"{_join(names)} {verb} set to show only on {describe_monitors(off_numbers)}, which {isnt} enabled "
            f"in Display settings, so the saver won't show {them}. Switch For Me moves {them} to Display {target}.",
            icon_type="warning",
            buttons=[("Switch For Me", SWITCH), ("Trust Me Bro", TRUST)],
            default_button_index=0,
        )
        popup.exec()
        choice = popup.result_value
        if choice == SWITCH:
            routed = deepcopy(dict(widgets))
            route_widgets_to_single_monitor(routed, target, routes)
            self._settings.set("widgets", routed)
            if on_switched is not None:
                on_switched()
            return True
        if choice == TRUST:
            self._trusted.update((widget_id, route, enabled) for widget_id, route in routes.items())
            return True
        return False
