"""The logical side's framed cameras, built from the drawn card's exact framed view (native core N0.4, D5.5).

Pure: no Qt, no GL. ``core.settings.framed_camera`` stays the one implementation of camera math; this module only
feeds a framed mode's camera builder (the very function its renderer calls) with the frame's parameters and the
controller's ``framed_view`` (``core.framed_view``: the numbers the renderer reads from the card it draws), so the
camera built here equals the renderer's bit for bit for the same frame. Waveform Ribbon's capture sizes its
travelling pulse from it (``core.waveform_ribbon_view.card_span``); the packet does not carry a camera yet (the native
port's step). Neon Lake's camera moves at its port (N5.5).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.framed_view import FramedView


def waveform_ribbon_camera(parameters: Mapping[str, Any], view: FramedView, *, zoom: float = 1.0):
    """(view, projection, eye, lens): what ``QuickWaveformRibbonRenderer`` draws with (``physical_view`` at the card's
    pixel aspect and its content aperture, ``framed_aperture_scale(..., content=True)``)."""
    from core.waveform_ribbon_view import physical_view

    return physical_view(parameters, view.pixel_aspect, view.aperture_scale, zoom=zoom)


def extruded_bubble_camera(parameters: Mapping[str, Any], view: FramedView):
    """(view_to_world, world_to_view, eye, tan, projection): what the Extruded Bubble renderer draws with
    (``parameter_camera`` at the card's pixel aspect and its extent aperture, ``framed_aperture_scale(...)``)."""
    from rendering.gl_programs.extruded_bubble_scene import parameter_camera

    return parameter_camera(parameters, view.pixel_aspect, view.extent_aperture_scale)


__all__ = ["extruded_bubble_camera", "waveform_ribbon_camera"]
