"""The card surface backdrop on the native core (Current_Plan.md N5.7b; D7 points 2 to 6).

On the native background's backend (Vulkan: ``native_background.native_background_wanted``) the display's wallpaper is
the core's background layer (N5.7a) and the Python backdrop (``surface_backdrop.SurfaceBackdropSource``, an OpenGL
render node reading Qt Quick's window target) cannot run, so ``SurfaceBackdropOwner`` takes this source instead: the
core's pyramid (``rendering.native.backdrop``), built from the layer in the frame the layer drew a new frame and only
while the owner's demand is above zero. Its ``item`` is the texture provider every ``MaterialSurface`` samples,
unchanged; before its first build, or while the window has no layer frame, the cards show their Normal fill (fail
closed). On OpenGL nothing here is made: the Python pyramid stays.

It speaks the owner's side of ``SurfaceBackdropSource`` (``request_refresh``, ``set_continuous``, ``set_parked``,
``parked``, ``armed``):
- ``request_refresh`` (the owner's one-shot edges: an image published, the dimming, the geometry, the owner made) only
  hands the core the dimming over the wallpaper (DisplayScene's ``backgroundDimming``; the core builds once when it
  changed). A new photo, a resize and a transition frame reach the pyramid through the layer itself, in the frame the
  layer draws them, never earlier from the GUI's edge (the photo's upload job may still be running then).
- ``set_continuous`` keeps no rate: the pyramid follows every frame the layer draws (D7 point 3, measured against its
  budget by ``native/core/python/backdrop_pyramid_check.py``).

GUI thread only. No timer, no frame request of its own.
"""
from __future__ import annotations

from typing import Any

from core.logging.logger import get_logger

logger = get_logger(__name__)


def native_backdrop_core() -> Any:
    """The process's native core when the display's backdrop comes from it (the native background's backend with the
    core loaded), else None (the Python backdrop)."""
    from .native_background import native_background_wanted

    if not native_background_wanted():
        return None
    from rendering.quick.bootstrap import native_core

    return native_core()


def dimming_opacity(root: Any) -> float:
    """DisplayScene's ``backgroundDimming`` opacity, as its QML computes it (0 when dimming is off or the root has no
    such properties)."""
    try:
        enabled = root.property("dimmingEnabled")
        opacity = root.property("dimmingOpacity")
    except RuntimeError:
        return 0.0
    if not enabled or opacity is None:
        return 0.0
    return max(0.0, min(1.0, float(opacity)))


class NativeSurfaceBackdropSource:
    """One display's native backdrop, made in ``root`` (the display's scene root)."""

    def __init__(self, core: Any, root: Any) -> None:
        self._root = root
        self._backdrop = core.backdrop(root)
        self.item = self._backdrop.item
        self.item.setObjectName("surfaceBackdropSource")   # the Python source's name: one backdrop item per display
        self._parked = False
        self._continuous = False
        self._dimming: float | None = None
        self.request_refresh()

    @property
    def backdrop(self) -> Any:
        return self._backdrop

    @property
    def parked(self) -> bool:
        return self._parked

    @property
    def armed(self) -> bool:
        """Nothing is armed from the GUI: the core builds from the layer's own frames."""
        return False

    @property
    def continuous(self) -> bool:
        return self._continuous

    def request_refresh(self) -> None:
        if self._parked or self._backdrop.destroyed:
            return
        dimming = dimming_opacity(self._root)
        if dimming != self._dimming:
            self._dimming = dimming
            self._backdrop.set_dimming(dimming)

    def set_continuous(self, active: bool, min_interval_s: float) -> None:
        del min_interval_s   # D7 point 3: every layer frame, no rate on the native core
        self._continuous = bool(active)

    def set_parked(self, parked: bool) -> None:
        parked = bool(parked)
        if parked == self._parked or self._backdrop.destroyed:
            return
        self._parked = parked
        self._backdrop.set_parked(parked)
        if not parked:
            self._dimming = None
            self.request_refresh()

    def state(self) -> dict:
        if self._backdrop.destroyed:
            return {"destroyed": True}
        return self._backdrop.state()

    def close(self) -> None:
        """The scene retires (its consumers unbound first): the item goes now, its node and pyramid on the render
        thread at the next sync. Idempotent."""
        self._parked = True
        try:
            self._backdrop.destroy()
        except Exception:
            logger.debug("[QUICK] native backdrop destroy failed", exc_info=True)


__all__ = ["NativeSurfaceBackdropSource", "dimming_opacity", "native_backdrop_core"]
