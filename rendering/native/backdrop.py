"""The native backdrop pyramid's Python face (Current_Plan.md N5.7b; D7 points 2 to 6; ``native/core/src/backdrop.h``).

The card materials sample one blurred backdrop per display (``Docs/Architecture/Card_Surface_Materials.md`` section
3). The pyramid is the core's on both APIs: built from the core's background layer (N5.7a) in the frame the layer drew a
new frame, only while the item is not parked (the owner's demand above zero), level for level the Python pyramid's that
it replaced (deleted at N5.2h's switch; its frames live on as the reference cache). Its item is a texture provider: ``item`` is a
``QQuickItem`` that ``MaterialSurface`` takes as its ``backdrop``, unchanged; until its first build (or while the
window has no layer frame) it hands out a transparent texture or none, so the cards show their Normal fill.

GUI thread only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from types import ModuleType
from typing import Any

#: The backdrop's options (``backdrop_set``): demand went to zero (every QRhi object goes), and the dimming over the
#: wallpaper (DisplayScene's ``backgroundDimming`` opacity, 0 to 1; applied in the pyramid's seed).
BACKDROP_OPTIONS = ("parked", "dimming")


@dataclass(frozen=True)
class BackdropLevel:
    """One level as read back (``backdrop_levels``): its name (``backdrop_pyramid_sizes``'s ``levels``), size and RGBA8
    rows in the texture's memory order (the window framebuffer's row order: bottom-up on OpenGL)."""

    name: str
    width: int
    height: int
    rgba: bytes


class NativeBackdrop:
    """One display's backdrop pyramid item (``NativeCore.backdrop``)."""

    def __init__(self, module: ModuleType, handle: int, address: int) -> None:
        import shiboken6
        from PySide6.QtQuick import QQuickItem

        self._module = module
        self._handle: int | None = int(handle)
        # A wrapper of the C++ item (not owned by Python: its QObject parent owns it).
        self.item = shiboken6.wrapInstance(int(address), QQuickItem)

    @property
    def handle(self) -> int:
        if self._handle is None:
            raise RuntimeError("the backdrop was destroyed")
        return self._handle

    @property
    def destroyed(self) -> bool:
        return self._handle is None

    def set(self, **options: Any) -> None:
        unknown = sorted(set(options) - set(BACKDROP_OPTIONS))
        if unknown:
            raise ValueError(f"unknown backdrop option(s) {', '.join(unknown)} (the options are "
                             f"{', '.join(BACKDROP_OPTIONS)})")
        self._module.backdrop_set(self.handle, json.dumps(options))

    def set_parked(self, parked: bool) -> None:
        self.set(parked=bool(parked))

    def set_dimming(self, opacity: float) -> None:
        self.set(dimming=min(1.0, max(0.0, float(opacity))))

    def request_build(self, *, readback: bool = False) -> None:
        """A harness's build at the next frame (``readback``: every level read back with it, see :meth:`levels`)."""
        self._module.backdrop_build(self.handle, bool(readback))

    def levels(self) -> list[BackdropLevel] | None:
        """The last readback's levels once the QRhi completed it (taken once), else None."""
        rows = self._module.backdrop_levels(self.handle)
        if rows is None:
            return None
        return [BackdropLevel(str(name), int(w), int(h), bytes(data)) for name, w, h, data in rows]

    def state(self) -> dict:
        return json.loads(self._module.backdrop_state(self.handle))

    def destroy(self) -> bool:
        """Deletes the item (its node and pyramid go on the render thread at the next sync). Idempotent."""
        if self._handle is None:
            return False
        handle, self._handle = self._handle, None
        return bool(self._module.backdrop_destroy(handle))


def pyramid_sizes(module: ModuleType, width: int, height: int) -> dict:
    """The level sizes of a ``width`` x ``height`` window as the core computes them, and the level names."""
    return json.loads(module.backdrop_pyramid_sizes(int(width), int(height)))


__all__ = ["BACKDROP_OPTIONS", "BackdropLevel", "NativeBackdrop", "pyramid_sizes"]
