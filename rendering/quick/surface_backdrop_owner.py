"""Per-display owner of the card surface backdrop (Docs/Architecture/Card_Surface_Materials.md).

``QuickSceneController`` holds at most one, and only while some card or the Context
Menu uses a non-Normal material. The owner creates the backdrop item above the
wallpaper and dimming (z 2) and below every widget, binds it to the widget host and
the Context Menu, and forwards the controller's existing edges (image published,
transition started/cleared, geometry changed, dimming changed) as backdrop refreshes.
It has no timer, no frame request and no per-frame work of its own.

Its source (Current_Plan.md N5.7b, N5.2h): on every backend the core's pyramid built from
its background layer (``render.native_surface_backdrop``), whose item the same
``MaterialSurface`` samples. Without a core (the degraded display) there is no backdrop and
the cards keep their Normal fill (``backdrop_available``).
"""
from __future__ import annotations

from typing import Any

from PySide6.QtQuick import QQuickItem

from .widgets.surface_material import transition_refresh_interval_s

# Above backgroundDimming (z 1), below the CUSTOM guide underlay (z 4) and the
# pixel-shift layer that holds every card (z 5).
BACKDROP_Z = 2.0


def _make_source(root: QQuickItem, screen_index: int) -> tuple[Any, QQuickItem]:
    """The display's backdrop source and its item: the core's (no Python backdrop on any backend)."""
    from .render.native_surface_backdrop import NativeSurfaceBackdropSource, native_backdrop_core

    del screen_index
    core = native_backdrop_core()
    if core is None or not _window_hosted(root.window()):
        # N5.2h: one route per API, no Python backdrop; the degraded display (no core, or a window the core did not
        # host: nothing draws a layer there for the pyramid to read) has none (``backdrop_available``).
        raise RuntimeError("the surface backdrop needs the native core")
    source = NativeSurfaceBackdropSource(core, root)
    return source, source.item


def _window_hosted(window: Any) -> bool:
    """The core did not refuse ``window`` (None: not asked, the core's presence is the caller's check)."""
    from .bootstrap import window_hosted

    return window is None or window_hosted(window)


def backdrop_available(window: Any = None) -> bool:
    """Whether a display can have a backdrop (the native core loaded and, given ``window``, hosting it); on the
    degraded display (a process without the core, or one window the core refused) the cards keep their Normal fill
    (fail closed)."""
    from .render.native_surface_backdrop import native_backdrop_core

    return native_backdrop_core() is not None and _window_hosted(window)


class SurfaceBackdropOwner:
    """One display's backdrop item and its edge wiring; retire() removes all of it."""

    def __init__(self, root: QQuickItem, *, screen_index: int) -> None:
        self._root = root
        source, item = _make_source(root, int(screen_index))
        item.setZ(BACKDROP_Z)
        item.setEnabled(False)
        item.setWidth(root.width())
        item.setHeight(root.height())
        root.widthChanged.connect(self._on_geometry_changed)
        root.heightChanged.connect(self._on_geometry_changed)
        self._source: Any = source
        self._item: QQuickItem | None = item
        self._materials: frozenset[str] = frozenset()
        self._transition_active = False
        source.request_refresh()

    @property
    def item(self) -> QQuickItem:
        item = self._item
        if item is None:
            raise RuntimeError("surface backdrop owner has retired")
        return item

    @property
    def source(self) -> Any:
        """The native source (N5.7b): the core's backdrop and its item."""
        return self._source

    @property
    def native(self) -> bool:
        return self._source is not None and self._source is not self._item

    @property
    def retired(self) -> bool:
        return self._item is None

    @property
    def parked(self) -> bool:
        return self._item is None or self._source.parked

    def park(self) -> None:
        """Every surface went Normal: free the GL and stop traversal (consumers unbound first).

        The item stays in the scene, node-less in effect (opacity 0, no GL objects), and is
        woken if a surface needs it again in this generation; the next generation starts
        with nothing.
        """

        if self._item is None:
            return
        self._transition_active = False
        self._source.set_parked(True)

    def wake(self) -> None:
        if self._item is None:
            return
        self._source.set_parked(False)

    def set_materials(self, materials: frozenset[str]) -> None:
        """The non-Normal materials in use; they set the transition refresh spacing."""

        self._materials = frozenset(materials)
        if self._transition_active and self._item is not None:
            self._source.set_continuous(True, transition_refresh_interval_s(self._materials))

    def note_background_changed(self) -> None:
        """A new presentation image, dimming change or similar one-off edge."""

        if self._item is not None and not self._source.parked:
            self._source.request_refresh()

    def set_transition_active(self, active: bool) -> None:
        active = bool(active)
        if self._item is None or self._source.parked or active == self._transition_active:
            return
        self._transition_active = active
        self._source.set_continuous(active, transition_refresh_interval_s(self._materials))
        if not active:
            # The run's final frame and the adopted wallpaper that follows it.
            self._source.request_refresh()

    def _on_geometry_changed(self, *_args) -> None:
        item, root = self._item, self._root
        if item is None or root is None:
            return
        item.setWidth(root.width())
        item.setHeight(root.height())
        if not self._source.parked:
            self._source.request_refresh()

    def retire(self) -> None:
        """Scene retirement only: the Python item dies with the scene root (C++ owned); the native one is deleted
        now (its consumers were unbound first), its pyramid released on the render thread at the next sync."""
        item, root, source = self._item, self._root, self._source
        self._item = None
        self._root = None
        if root is not None:
            for signal in (root.widthChanged, root.heightChanged):
                try:
                    signal.disconnect(self._on_geometry_changed)
                except (RuntimeError, TypeError):
                    pass
        if item is None:
            return
        if source is not item:
            source.close()
        elif not source.parked:
            source.set_parked(True)


__all__ = ["BACKDROP_Z", "SurfaceBackdropOwner", "backdrop_available"]
