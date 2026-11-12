"""Lazy Quick renderer for the canonical Warp Dissolve shader."""

from __future__ import annotations

from rendering.gl_programs.warp_program import warp_program
from ..fullscreen_pass import FullscreenPassRenderer, fullscreen_pass_parts
from ..render_contract import QuickTransitionRenderFrame


class QuickWarpRenderer(FullscreenPassRenderer):
    transition_id = "warp_dissolve"
    label = "Quick Warp Dissolve"
    fragment_source = warp_program.fragment_source
    vertex_source, block = fullscreen_pass_parts(fragment_source, "WarpPass")
    value_names = ("u_resolution",)

    def values(self, resolved, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        return {"u_resolution": (float(frame.viewport[2]), float(frame.viewport[3]))}


def create_transition_renderer() -> QuickWarpRenderer:
    return QuickWarpRenderer()
