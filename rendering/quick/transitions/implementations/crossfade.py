"""Quick Crossfade renderer using the canonical production fragment shader."""

from __future__ import annotations

from rendering.gl_programs.crossfade_program import crossfade_program
from ..fullscreen_pass import FullscreenPassRenderer
from ..render_contract import QuickTransitionRenderFrame


class QuickCrossfadeRenderer(FullscreenPassRenderer):
    transition_id = "crossfade"
    label = "Quick Crossfade"
    fragment_source = crossfade_program.fragment_source


def create_transition_renderer() -> QuickCrossfadeRenderer:
    return QuickCrossfadeRenderer()
