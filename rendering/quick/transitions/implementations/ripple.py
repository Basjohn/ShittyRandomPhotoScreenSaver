"""Lazy Quick renderer for the canonical authored Ripple/Raindrops shader."""

from __future__ import annotations

from collections.abc import Mapping
import math

from OpenGL import GL as gl

from rendering.gl_programs.raindrops_program import raindrops_program
from ..fullscreen_pass import FullscreenPassRenderer
from ..render_contract import QuickTransitionRenderFrame


def _ripple_count(parameters: Mapping[str, object]) -> int:
    raw = parameters.get("ripple_count")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError("Ripple requires resolved integer parameter 'ripple_count'")
    if not 1 <= raw <= 8:
        raise ValueError("Ripple ripple_count must be between 1 and 8")
    return raw


def _ripple_seed(parameters: Mapping[str, object]) -> float:
    raw = parameters.get("ripple_seed")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("Ripple requires resolved numeric parameter 'ripple_seed'")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("Ripple ripple_seed must be finite")
    return value


class QuickRippleRenderer(FullscreenPassRenderer):
    transition_id = "ripple"
    label = "Quick Ripple"
    fragment_source = raindrops_program.fragment_source
    uniform_names = ("u_resolution", "u_ripple_count", "u_ripple_seed")

    def resolve(self, frame: QuickTransitionRenderFrame) -> tuple[int, float]:
        parameters = frame.run.request.parameter_dict()
        return _ripple_count(parameters), _ripple_seed(parameters)

    def apply(self, values, uniforms, frame: QuickTransitionRenderFrame) -> None:
        count, seed = values
        gl.glUniform2f(uniforms["u_resolution"], float(frame.viewport[2]), float(frame.viewport[3]))
        gl.glUniform1i(uniforms["u_ripple_count"], count)
        gl.glUniform1f(uniforms["u_ripple_seed"], seed)


def create_transition_renderer() -> QuickRippleRenderer:
    return QuickRippleRenderer()
