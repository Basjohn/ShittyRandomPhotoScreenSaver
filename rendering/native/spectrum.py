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

The product creates one through the Visualizer's native route on Vulkan (``rendering.quick.visualizer.native_route``);
the mode is offered there once the port's rules pass (D10: its ``renderer_backends`` gains ``vulkan``).
"""
from __future__ import annotations

import json
from types import ModuleType
from typing import Any, Mapping

from rendering.native.composite import CompositeGeometry, CompositeItem
from rendering.native.packet_reader import reader_config

#: The card's keys (``SpectrumPresentation::fromJson`` in ``spectrum.cpp``).
SPECTRUM_PRESENTATION_KEYS = ("quarters", "item_size", "oriented_size", "content_rect", "viewport_extent",
                              "visual_scale", "dpr", "content_fade", "expanded", "window_from_target",
                              "item_from_window", "target_size")


def _ortho_item_matrix(window_size: tuple[float, float], origin: tuple[float, float], *, single: bool) -> tuple:
    """The Python node's ``projectionMatrix() * matrix()`` for an item translated to ``origin`` in a window of
    ``window_size`` (logical) on OpenGL, column-major: Qt's own float32 product (``single``), or the same in double."""
    width, height = (float(v) for v in window_size)
    x, y = (float(v) for v in origin)
    if single:
        from PySide6.QtGui import QMatrix4x4

        projection = QMatrix4x4()
        projection.ortho(0.0, width, height, 0.0, 1.0, -1.0)     # QSGAbstractRenderer::setProjectionMatrixToRect
        item = QMatrix4x4()
        item.translate(x, y)
        return tuple(float(v) for v in (projection * item).data())
    m = [0.0] * 16
    m[0], m[5], m[10], m[15] = 2.0 / width, -2.0 / height, 1.0, 1.0
    m[12], m[13] = 2.0 * x / width - 1.0, 1.0 - 2.0 * y / height
    return tuple(m)


def compose_window_from_target(window_rows, target_origin: tuple[float, float],
                               ratio: float | tuple[float, float]) -> list[float]:
    """The target's pixel -> the window's, as rows x, y: the target's axes are the oriented item's (1 / ratio per
    pixel on each oriented axis, its origin at ``target_origin`` in the oriented item), composed with the exact (double)
    inverse of the window map ``window_rows`` (window pixel -> oriented item). ``ratio``: the window's
    logical-to-framebuffer ratio along the oriented item's x and y (the device pixel ratio only where the window's
    logical size times it is its framebuffer; audit 14 Nov, H1). A signed permutation with whole offsets; anything
    else raises."""
    sx, sy = (float(ratio), float(ratio)) if isinstance(ratio, (int, float)) else (float(ratio[0]), float(ratio[1]))
    (a, b, c), (d, e, f) = window_rows
    det = a * e - b * d
    inverse = ((e / det, -b / det), (-d / det, a / det))
    target_map = ((1.0 / sx, 0.0, float(target_origin[0])), (0.0, 1.0 / sy, float(target_origin[1])))
    composed: list[float] = []
    for row in inverse:
        coefficients = [row[0] * target_map[0][k] + row[1] * target_map[1][k] for k in range(3)]
        coefficients[2] -= row[0] * c + row[1] * f
        rounded = [float(round(value)) for value in coefficients]
        if max(abs(x - y) for x, y in zip(coefficients, rounded)) > 1e-3:
            raise ValueError(f"the target's pixel is not a whole-pixel image of the window's: {coefficients}")
        composed.extend(rounded)
    return composed


def spectrum_presentation(presentation: Any, geometry: CompositeGeometry, *, window_size: tuple[float, float],
                          window_pixels: tuple[int, int]) -> dict:
    """The card as the native Spectrum draws it: ``presentation`` (a ``ResolvedVisualizerPresentation``) through its
    composite ``geometry``, in a window of ``window_size`` (logical) and ``window_pixels`` (its framebuffer). The item
    is the card's outer rect (display-logical), as the Python renderer's item is.

    The pixel arithmetic is the Python renderer's own (N2.5 rule (a), lead 14 Nov): ``window_from_target`` rebuilds the
    window's pixel (x right, y up from the window's bottom: the Python renderer's ``gl_FragCoord``) from the target's
    (top-left origin, the content's orientation) by whole-pixel offsets and signs, exactly; ``item_from_window`` is
    the Python renderer's ``item_from_fragment`` of Qt's float32 item matrix, row for row."""
    from rendering.quick.visualizer.implementations.spectrum import item_from_fragment
    from widgets.spotify_visualizer.presentation_orientation import logical_rect_from_physical_rect

    quarters = int(presentation.content_rotation_quarters) % 4
    outer_x, outer_y, outer_width, outer_height = (float(v) for v in presentation.outer_rect)
    item_size = (outer_width, outer_height)
    oriented_size = (outer_height, outer_width) if quarters & 1 else (outer_width, outer_height)

    def oriented(rect) -> tuple[float, float, float, float]:
        if quarters == 0:
            return tuple(float(v) for v in rect)            # type: ignore[return-value]
        return tuple(float(v) for v in logical_rect_from_physical_rect(
            rect, physical_size=item_size, content_rotation_quarters=quarters))   # type: ignore[return-value]

    content_x, content_y, content_width, content_height = (float(v) for v in presentation.content_rect)
    content = oriented((content_x - outer_x, content_y - outer_y, content_width, content_height))
    target_x, target_y, target_width, target_height = geometry.rect
    target = oriented((target_x - outer_x, target_y - outer_y, target_width, target_height))
    # The rect's device pixels are counted with the window's own ratio per window axis; the oriented item's x is the
    # window's y under an odd quarter turn.
    ratio_x, ratio_y = geometry.ratio
    oriented_ratio = (ratio_y, ratio_x) if quarters & 1 else (ratio_x, ratio_y)
    texture_width, texture_height = geometry.texture_size
    viewport = (0, 0, int(window_pixels[0]), int(window_pixels[1]))
    rows = {}
    for single in (True, False):
        mapping = item_from_fragment(_ortho_item_matrix(window_size, (outer_x, outer_y), single=single), viewport,
                                     item_size, quarters, oriented_size)
        if mapping is None:
            raise ValueError("the card's window map is degenerate")
        rows[single] = mapping
    window_from_target = compose_window_from_target(rows[False], (target[0], target[1]), oriented_ratio)
    return {
        "quarters": quarters,
        "item_size": [outer_width, outer_height],
        "oriented_size": list(oriented_size),
        "content_rect": list(content),
        "viewport_extent": [float(v) for v in presentation.logical_viewport_extent],
        "visual_scale": float(presentation.uniform_visual_scale),
        "dpr": float(presentation.dpr),
        "content_fade": float(presentation.content_fade),
        "expanded": bool(presentation.expanded_display),
        # fragPixel (the target's pixel centre, top-left origin) -> the window's pixel (y up), exact.
        "window_from_target": window_from_target,
        # The window's pixel -> the item's oriented logical coordinate: the Python renderer's own float32 rows.
        "item_from_window": [*rows[True][0], *rows[True][1]],
        "target_size": [float(texture_width), float(texture_height)],
    }


def window_metrics(item: Any, composite: Any) -> tuple[tuple[float, float], tuple[int, int]]:
    """``item``'s window: its logical size and its framebuffer's pixels, the target Qt's projection maps
    ``QRectF(0, 0, window.size())`` onto, as Qt's own swapchain or redirect target reports it through the native item
    (``CompositeItem.window_pixels``; audit N29 L1: no platform call, no rounding of the logical size). Raises while the
    window has none yet (not exposed): the route then waits for its next update."""
    window = item.window()
    if window is None:
        raise WindowNotReady("the native item has no window")
    pixels = composite.window_pixels()
    if pixels is None:
        raise WindowNotReady("the native item's window has no framebuffer yet")
    return (float(window.width()), float(window.height())), pixels


class WindowNotReady(RuntimeError):
    """The native item's window is not there yet, or has no framebuffer yet (an ordinary startup state)."""


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

    def present(self, presentation: Any, geometry: CompositeGeometry, *, window_size: tuple[float, float],
                window_pixels: tuple[int, int]) -> dict:
        """The card as shown; returns what was handed over."""
        card = spectrum_presentation(presentation, geometry, window_size=window_size, window_pixels=window_pixels)
        self.present_raw(card)
        return card

    def present_raw(self, card: Mapping[str, Any]) -> None:
        missing = [key for key in SPECTRUM_PRESENTATION_KEYS if key not in card]
        if missing:
            raise ValueError(f"the Spectrum card misses {', '.join(missing)}")
        self._module.composite_spectrum_present(self._handle(), json.dumps(dict(card)))

    def program(self, pack: bytes | None) -> None:
        """The fragment pack the item draws (``rendering.native.program_values.mode_fragment_pack``; None: the
        module's compiled-in copy, a harness control only). A new pack rebuilds the pipeline at the next record."""
        self._module.composite_spectrum_program(self._handle(), None if pack is None else bytes(pack))

    def settings(self, values: Mapping[str, Any]) -> None:
        """The Settings- and card-derived members by name (``spectrum_settings_values``); refused (ValueError) on an
        unknown name, a wrong size or a per-frame member. Unchanged settings record nothing."""
        from rendering.native.program_values import settings_json

        self._module.composite_spectrum_settings(self._handle(), settings_json(values))

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


def spectrum_block(module: ModuleType, record: bytes, card: Mapping[str, Any], pack: bytes | None,
                   settings: Mapping[str, Any]) -> tuple[bytes | None, dict]:
    """The SpectrumDraw block the native Spectrum uploads for ``record`` (a version-1 Spectrum record) under ``card``,
    drawn by ``pack`` with ``settings`` by name (GPU-free), and its facts (``reason`` when nothing is drawn;
    ``unfilled``: the members neither side filled)."""
    from rendering.native.program_values import settings_json

    block, facts = module.spectrum_block(bytes(record), json.dumps(dict(card)),
                                         None if pack is None else bytes(pack), settings_json(settings))
    return block, json.loads(facts)


__all__ = ["NativeSpectrum", "SPECTRUM_PRESENTATION_KEYS", "WindowNotReady", "spectrum_block", "spectrum_presentation",
           "window_metrics"]
