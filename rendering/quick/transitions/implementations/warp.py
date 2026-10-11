"""Lazy Quick renderer for the canonical Warp Dissolve shader."""

from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.warp_program import warp_program
from ..fullscreen_pass import FullscreenPassRenderer
from ..render_contract import QuickTransitionRenderFrame


class QuickWarpRenderer(FullscreenPassRenderer):
    transition_id = "warp_dissolve"
    label = "Quick Warp Dissolve"
    fragment_source = warp_program.fragment_source
    uniform_names = ("u_resolution",)

    def apply(self, values, uniforms, frame: QuickTransitionRenderFrame) -> None:
        gl.glUniform2f(uniforms["u_resolution"], float(frame.viewport[2]), float(frame.viewport[3]))


def create_transition_renderer() -> QuickWarpRenderer:
    return QuickWarpRenderer()
