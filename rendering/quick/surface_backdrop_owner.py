"""Per-display owner of the card surface backdrop (Docs/Architecture/Card_Surface_Materials.md).

``QuickSceneController`` holds at most one, and only while some card or the Context
Menu uses a non-Normal material. The owner creates the backdrop item above the
wallpaper and dimming (z 2) and below every widget, binds it to the widget host and
the Context Menu, and forwards the controller's existing edges (image published,
transition started/cleared, geometry changed, dimming changed) as backdrop refreshes.
It has no timer, no frame request and no per-frame work of its own.
"""
from __future__ import annotations

from PySide6.QtQuick import QQuickItem

from .render.surface_backdrop import SurfaceBackdropSource
from .widgets.surface_material import transition_refresh_interval_s

# Above backgroundDimming (z 1), below the CUSTOM guide underlay (z 4) and the
# pixel-shift layer that holds every card (z 5).
BACKDROP_Z = 2.0


class SurfaceBackdropOwner:
    """One display's backdrop item and its edge wiring; retire() removes all of it."""

    def __init__(self, root: QQuickItem, *, screen_index: int) -> None:
        self._root = root
        item = SurfaceBackdropSource(root, screen_index=screen_index)
        item.setZ(BACKDROP_Z)
        item.setEnabled(False)
        item.setWidth(root.width())
        item.setHeight(root.height())
        root.widthChanged.connect(self._on_geometry_changed)
        root.heightChanged.connect(self._on_geometry_changed)
        self._item: SurfaceBackdropSource | None = item
        self._materials: frozenset[str] = frozenset()
        self._transition_active = False
        item.request_refresh()

    @property
    def item(self) -> SurfaceBackdropSource:
        item = self._item
        if item is None:
            raise RuntimeError("surface backdrop owner has retired")
        return item

    @property
    def retired(self) -> bool:
        return self._item is None

    @property
    def parked(self) -> bool:
        return self._item is None or self._item.parked

    def park(self) -> None:
        """Every surface went Normal: free the GL and stop traversal (consumers unbound first).

        The item stays in the scene, node-less in effect (opacity 0, no GL objects), and is
        woken if a surface needs it again in this generation; the next generation starts
        with nothing.
        """

        item = self._item
        if item is None:
            return
        self._transition_active = False
        item.set_parked(True)

    def wake(self) -> None:
        item = self._item
        if item is None:
            return
        item.set_parked(False)

    def set_materials(self, materials: frozenset[str]) -> None:
        """The non-Normal materials in use; they set the transition refresh spacing."""

        self._materials = frozenset(materials)
        if self._transition_active and self._item is not None:
            self._item.set_continuous(True, transition_refresh_interval_s(self._materials))

    def note_background_changed(self) -> None:
        """A new presentation image, dimming change or similar one-off edge."""

        if self._item is not None and not self._item.parked:
            self._item.request_refresh()

    def set_transition_active(self, active: bool) -> None:
        active = bool(active)
        item = self._item
        if item is None or item.parked or active == self._transition_active:
            return
        self._transition_active = active
        item.set_continuous(active, transition_refresh_interval_s(self._materials))
        if not active:
            # The run's final frame and the adopted wallpaper that follows it.
            item.request_refresh()

    def _on_geometry_changed(self, *_args) -> None:
        item, root = self._item, self._root
        if item is None or root is None:
            return
        item.setWidth(root.width())
        item.setHeight(root.height())
        if not item.parked:
            item.request_refresh()

    def retire(self) -> None:
        """Scene retirement only: the item dies with the scene root (C++ owned)."""
        item, root = self._item, self._root
        self._item = None
        self._root = None
        if root is not None:
            for signal in (root.widthChanged, root.heightChanged):
                try:
                    signal.disconnect(self._on_geometry_changed)
                except (RuntimeError, TypeError):
                    pass
        if item is not None and not item.parked:
            item.set_parked(True)


__all__ = ["BACKDROP_Z", "SurfaceBackdropOwner"]
