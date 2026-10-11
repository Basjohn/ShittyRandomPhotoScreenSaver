"""Quick Wipe renderer using the canonical production fragment shader."""

from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.wipe_program import wipe_program
from ..fullscreen_pass import FullscreenPassRenderer
from ..render_contract import QuickTransitionRenderFrame


_DIRECTION_MODES = {
    "left_to_right": 0,
    "right_to_left": 1,
    "top_to_bottom": 2,
    "bottom_to_top": 3,
    "diag_tl_br": 4,
    "diag_tr_bl": 5,
}


def _wipe_mode(direction: object) -> int:
    """Map one resolved canonical Wipe direction to its shader mode."""

    value = "left_to_right" if direction is None else str(direction).strip().lower()
    mode = _DIRECTION_MODES.get(value)
    if mode is None:
        raise ValueError(f"unknown canonical Wipe direction: {direction!r}")
    return mode


class QuickWipeRenderer(FullscreenPassRenderer):
    transition_id = "wipe"
    label = "Quick Wipe"
    fragment_source = wipe_program.fragment_source
    uniform_names = ("u_mode",)

    def resolve(self, frame: QuickTransitionRenderFrame) -> int:
        return _wipe_mode(frame.run.request.direction)

    def apply(self, mode, uniforms, frame: QuickTransitionRenderFrame) -> None:
        gl.glUniform1i(uniforms["u_mode"], mode)


def create_transition_renderer() -> QuickWipeRenderer:
    return QuickWipeRenderer()
