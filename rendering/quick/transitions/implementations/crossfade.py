"""Quick Crossfade renderer using the canonical production fragment shader."""

from __future__ import annotations

from rendering.gl_programs.crossfade_program import crossfade_program
from ..fullscreen_pass import FullscreenPassRenderer, fullscreen_pass_parts
from ..render_contract import QuickTransitionRenderFrame


class QuickCrossfadeRenderer(FullscreenPassRenderer):
    transition_id = "crossfade"
    label = "Quick Crossfade"
    fragment_source = crossfade_program.fragment_source
    vertex_source, block = fullscreen_pass_parts(fragment_source, "CrossfadePass")


def create_transition_renderer() -> QuickCrossfadeRenderer:
    return QuickCrossfadeRenderer()
