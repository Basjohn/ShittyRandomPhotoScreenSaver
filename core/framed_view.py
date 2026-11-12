"""The framed view a framed 3D camera is built from: the drawn card's exact numbers (native core N0.4, D5.5 point 3).

Pure and Qt-free. A framed renderer builds its camera (``core.settings.framed_camera``) from the frame's parameters
and three numbers only the GUI side knows exactly: the card's pixel aspect as the render thread sees it
(``item_pixel_rect`` of the drawn card: whole device pixels since R-191) and the presentation's
``framed_aperture_scale``, with the content inset (``content=True``: Waveform Ribbon, Neon Lake) and without it
(Extruded Bubble). ``rendering.quick.visualizer.framed_view.resolve_framed_view`` resolves them from the record the
scene draws, with the renderer's own functions; the scene publishes them at its geometry edges (resize, CUSTOM edge
resize, DPR, Expanded enter and exit, a display move) to the Visualizer's runtime controller, and on the engine worker
they travel in ``VIS_SET_VIEW`` (latest wins, never per frame), so the logical side builds the camera the renderer
builds, from the same numbers (``card_span``; the worker-side camera, ``widgets.spotify_visualizer.framed_view_camera``).
"""
from __future__ import annotations

import math
from typing import Any, NamedTuple

#: ``VIS_SET_VIEW``'s message version: 2 since the view carries the framed view (an internal message, never
#: persisted: no bridge, N0.4 lead decision 2). The worker refuses any other version.
VIEW_MESSAGE_VERSION = 2


class FramedView(NamedTuple):
    """The drawn card's camera inputs (plain floats; a tuple, so it compares by value and pickles plainly)."""

    #: Width over height of the card's device-pixel rect as the renderer sees it (``item_pixel_rect``).
    pixel_aspect: float
    #: ``framed_aperture_scale(presentation, content=True)``.
    aperture_scale: float
    #: ``framed_aperture_scale(presentation)`` (``content=False``).
    extent_aperture_scale: float


def admit_framed_view(value: Any) -> FramedView | None:
    """``value`` (a ``FramedView`` or any three numbers) as a ``FramedView``, or None for None; anything else (a wrong
    length, a non-finite or non-positive number) raises ``ValueError``."""
    if value is None:
        return None
    try:
        numbers = tuple(float(v) for v in value)
    except TypeError as exc:
        raise ValueError(f"a framed view is three numbers, not {value!r}") from exc
    if len(numbers) != 3 or not all(math.isfinite(v) and v > 0.0 for v in numbers):
        raise ValueError(f"a framed view is three finite positive numbers, not {value!r}")
    return FramedView(*numbers)


__all__ = ["FramedView", "VIEW_MESSAGE_VERSION", "admit_framed_view"]
