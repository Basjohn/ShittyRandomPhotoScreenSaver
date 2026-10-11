"""The one-program transitions' shared renderer: one fragment shader drawn over the item quad.

Ripple, Wipe, Slide, Crossfade, Warp Dissolve, Particle and Burn each draw a single fragment
program between the old picture (unit 0) and the new one (unit 1). They used to repeat the same
lifecycle by hand, and one shared gap (no warm-up: their programs compiled on the first visible
frame, 3-18 ms at 1440p) followed. This base owns that lifecycle once:

* ``warm()`` compiles the program in the warm-up's one step, so the run's first frame compiles
  nothing (``tests/test_transition_lifecycle_contract.py``);
* every instance owns its own program and uniform locations: never a shared or class-level GL
  handle (``Docs/Historical_Bugs/R-51_Shared_Shader_Cache_Deletion_Ownership.md``);
* the required uniforms are looked up at compile and any missing one fails loudly;
* ``render()`` validates the run's parameters (``resolve``) before any GL state changes, then sets
  the common uniforms (matrix, item size, progress), the transition's own (``apply``), binds both
  pictures and draws, in that order.

A transition gives its ``transition_id``, ``label``, ``fragment_source`` and extra
``uniform_names``, and overrides ``resolve`` / ``apply`` when it has parameters.
"""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from .render_contract import QUICK_TRANSITION_VERTEX_SOURCE, QuickTransitionRenderFrame

COMMON_UNIFORMS = ("uMatrix", "uItemSize", "u_progress", "uOldTex", "uNewTex")


class FullscreenPassRenderer:
    transition_id: str = ""
    label: str = ""
    fragment_source: str = ""
    uniform_names: tuple[str, ...] = ()      # beyond COMMON_UNIFORMS

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def resolve(self, frame: QuickTransitionRenderFrame) -> object:
        """The run's validated values for ``apply`` (no GL); raise on an unresolved parameter."""
        return None

    def apply(self, values: object, uniforms: Mapping[str, int], frame: QuickTransitionRenderFrame) -> None:
        """Set the transition's own uniforms (its program is in use)."""

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        values = self.resolve(frame)
        uniforms = self._uniforms
        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(uniforms["u_progress"], float(frame.sample.eased_progress))
        self.apply(values, uniforms, frame)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glUniform1i(uniforms["uOldTex"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        gl.glUniform1i(uniforms["uNewTex"], 1)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """The gradual warm-up's one step (render thread, between runs): compile the program so
        the run's first frame compiles nothing."""
        if not self._program:
            self._initialize()
        return True

    def release_resources(self) -> None:
        if not self._program:
            return
        gl.glDeleteProgram(self._program)
        self._program = 0
        self._uniforms.clear()

    def _initialize(self) -> None:
        program = compile_program(QUICK_TRANSITION_VERTEX_SOURCE, self.fragment_source, label=self.label)
        self._program = program
        try:
            names = COMMON_UNIFORMS + tuple(name for name in self.uniform_names if name not in COMMON_UNIFORMS)
            uniforms = {name: int(gl.glGetUniformLocation(program, name)) for name in names}
            missing = [name for name in names if uniforms[name] < 0]
            if missing:
                raise RuntimeError(f"{self.label} uniforms are incomplete: " + ", ".join(missing))
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise
