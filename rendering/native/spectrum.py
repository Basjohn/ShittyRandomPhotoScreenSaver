"""The native Spectrum's Python face (Current_Plan.md item 8b, N2.5; ``native/core/src/spectrum.h``).

Spectrum drawn by the core into a composite's surface (D5.2), from a frame stream the core's packet reader reads at the
item's sync on the render thread (N2.3: D1, D2; the reader's first user). Python never touches a frame here: it binds
the stream by its mapping name, hands over the card as shown, asks for frames, raises the drop edge and reads the
stream's head (D2's non-consuming read). The fragment shader is the product's own ``spectrum.frag``; the values it
gets are the Python renderer's arithmetic ported to C++ (``spectrum_block`` returns them, GPU-free, for the test that
compares the two byte for byte).

``spectrum_presentation`` resolves the card on the GUI thread from the ``ResolvedVisualizerPresentation`` and the
composite's geometry (``rendering.native.composite.composite_geometry``): the Python renderer's presentation inputs
(the item's oriented size, ``logical_content_rect``, the viewport extent, the visual scale, the content fade, the
expanded record, the device pixel ratio) and the map from the target's pixel to the item's oriented logical coordinate
(``u_item_from_frag``: the target is the card's drawn rect on whole device pixels, already in the content's
orientation, its texel (0, 0) at the top-left on every backend, N0.3 F1).

Nothing in the product creates one yet (D10: the mode offers ``vulkan`` once the port's rules pass).
"""
from __future__ import annotations

import json
from types import ModuleType
from typing import Any, Mapping

from rendering.native.composite import CompositeGeometry, CompositeItem
from rendering.native.packet_reader import reader_config

#: The card's keys (``SpectrumPresentation::fromJson`` in ``spectrum.cpp``).
SPECTRUM_PRESENTATION_KEYS = ("quarters", "item_size", "oriented_size", "content_rect", "viewport_extent",
                              "visual_scale", "dpr", "content_fade", "expanded", "item_from_target", "target_size")


def spectrum_presentation(presentation: Any, geometry: CompositeGeometry) -> dict:
    """The card as the native Spectrum draws it: ``presentation`` (a ``ResolvedVisualizerPresentation``) through its
    composite ``geometry``. The item is the card's outer rect (display-logical), as the Python renderer's item is."""
    from widgets.spotify_visualizer.presentation_orientation import logical_rect_from_physical_rect

    quarters = int(presentation.content_rotation_quarters) % 4
    outer_x, outer_y, outer_width, outer_height = (float(v) for v in presentation.outer_rect)
    item_size = (outer_width, outer_height)

    def oriented(rect) -> tuple[float, float, float, float]:
        if quarters == 0:
            return tuple(float(v) for v in rect)            # type: ignore[return-value]
        return tuple(float(v) for v in logical_rect_from_physical_rect(
            rect, physical_size=item_size, content_rotation_quarters=quarters))   # type: ignore[return-value]

    content_x, content_y, content_width, content_height = (float(v) for v in presentation.content_rect)
    content = oriented((content_x - outer_x, content_y - outer_y, content_width, content_height))
    target_x, target_y, target_width, target_height = geometry.rect
    target = oriented((target_x - outer_x, target_y - outer_y, target_width, target_height))
    dpr = float(geometry.dpr)
    texture_width, texture_height = geometry.texture_size
    return {
        "quarters": quarters,
        "item_size": [outer_width, outer_height],
        "oriented_size": [outer_height, outer_width] if quarters & 1 else [outer_width, outer_height],
        "content_rect": list(content),
        "viewport_extent": [float(v) for v in presentation.logical_viewport_extent],
        "visual_scale": float(presentation.uniform_visual_scale),
        "dpr": float(presentation.dpr),
        "content_fade": float(presentation.content_fade),
        "expanded": bool(presentation.expanded_display),
        # fragPixel (the target's pixel centre, top-left origin) -> the item's oriented logical coordinate.
        "item_from_target": [1.0 / dpr, 0.0, target[0], 0.0, 1.0 / dpr, target[1]],
        "target_size": [float(texture_width), float(texture_height)],
    }


class NativeSpectrum:
    """Spectrum on one composite item (``NativeCore.spectrum``): bound to a stream, given the card, destroyed with its
    composite. Every call is the GUI thread's and returns at once (a retire never waits, D1)."""

    def __init__(self, module: ModuleType, composite: CompositeItem) -> None:
        self._module = module
        self.composite = composite

    def _handle(self) -> int:
        return self.composite._live()

    def bind(self, mapping_name: str, *, expect: Mapping[str, int] | None = None, controls: tuple[str, ...] = ()) -> None:
        """Draw from this frame stream (the previous one retires); ``expect``: its identity; ``controls``: a harness's
        reader controls (``READER_CONTROLS``)."""
        self._module.composite_spectrum_bind(self._handle(), str(mapping_name), reader_config(expect, tuple(controls)))

    def unbind(self) -> None:
        self._module.composite_spectrum_unbind(self._handle())

    def retire(self) -> None:
        """Any thread: the bound stream stores Retiring at once (D1); :meth:`unbind` then releases it."""
        self._module.composite_spectrum_retire(self._handle())

    def present(self, presentation: Any, geometry: CompositeGeometry) -> dict:
        """The card as shown (and the composite placed for it); returns what was handed over."""
        card = spectrum_presentation(presentation, geometry)
        self.present_raw(card)
        return card

    def present_raw(self, card: Mapping[str, Any]) -> None:
        missing = [key for key in SPECTRUM_PRESENTATION_KEYS if key not in card]
        if missing:
            raise ValueError(f"the Spectrum card misses {', '.join(missing)}")
        self._module.composite_spectrum_present(self._handle(), json.dumps(dict(card)))

    def update(self) -> None:
        """A frame of the item (the wake's present request)."""
        self._module.composite_update(self._handle())

    def drop_retained_frame(self) -> None:
        self._module.composite_spectrum_drop(self._handle())

    def head(self) -> dict | None:
        """The bound stream's newest whole slot head; consumes nothing (D2)."""
        return self._module.composite_spectrum_head(self._handle())

    def state(self) -> dict:
        return json.loads(self._module.composite_spectrum_state(self._handle()))

    def wait_paused(self, timeout_ms: int) -> bool:
        """The ``pause_in_copy`` hook: the bound reader is paused inside a copy."""
        return bool(self._module.composite_spectrum_wait_paused(self._handle(), int(timeout_ms)))

    def resume(self) -> None:
        self._module.composite_spectrum_resume(self._handle())


def spectrum_block(module: ModuleType, record: bytes, card: Mapping[str, Any]) -> tuple[bytes | None, dict]:
    """The SpectrumDraw block the native Spectrum uploads for ``record`` (a version-1 Spectrum record) under ``card``
    (GPU-free), and its facts (``reason`` when nothing is drawn)."""
    block, facts = module.spectrum_block(bytes(record), json.dumps(dict(card)))
    return block, json.loads(facts)


__all__ = ["NativeSpectrum", "SPECTRUM_PRESENTATION_KEYS", "spectrum_block", "spectrum_presentation"]
