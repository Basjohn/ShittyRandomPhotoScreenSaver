"""The one-program transitions' shared renderer: one fragment shader drawn over the item quad.

Ripple, Wipe, Slide, Crossfade, Warp Dissolve, Particle and Burn each draw a single fragment
program between the old picture (unit 0) and the new one (unit 1). They used to repeat the same
lifecycle by hand, and one shared gap (no warm-up: their programs compiled on the first visible
frame, 3-18 ms at 1440p) followed. This base owns that lifecycle once:

* ``warm()`` compiles the program in one warm-up step and, given the render size, allocates its
  pass block's ring in the next, so the run's first frame compiles and allocates nothing
  (``tests/test_transition_lifecycle_contract.py``);
* every instance owns its own program and pass blocks: never a shared or class-level GL handle
  (``Docs/Historical_Bugs/R-51_Shared_Shader_Cache_Deletion_Ownership.md``);
* every value the program reads is one std140 pass block (N1.6), which the fragment declares
  (at ``SCENE3D_PASS_BLOCK_BINDING``) and the item quad's vertex stage declares
  identically (``item_quad_vertex_source``); the block's members are checked at compile and a
  missing one fails loudly, and the samplers carry their units in the source (0 old, 1 new);
* ``render()`` validates the run's parameters (``resolve``) before any GL state changes, then
  packs the common values (matrix, item size, progress) and the transition's own (``values``),
  binds both pictures and draws inside the bound block, in that order.

A transition gives its ``transition_id``, ``label``, ``fragment_source`` and the parts
``fullscreen_pass_parts`` makes from it, and overrides ``resolve`` / ``values`` when it has
parameters.
"""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl, pack_block
from rendering.gl_programs.scene3d import Scene3DBlockLayout
from rendering.quick.render.gl_resources import compile_program, delete_program
from rendering.quick.scene3d.frame import item_quad_vertex_source
from rendering.quick.scene3d.uniforms import PassBlocks
from .render_contract import QuickTransitionRenderFrame

COMMON_VALUES = ("uMatrix", "uItemSize", "u_progress")


def fullscreen_pass_parts(fragment_source: str, block_name: str):
    """(the item quad's vertex stage, the block layout) from the fragment's own ``block_name`` declaration: one
    declaration for both stages and for the packing."""
    declaration = block_declaration(fragment_source, block_name)
    return item_quad_vertex_source(declaration), block_layout_from_glsl(declaration)


class FullscreenPassRenderer:
    transition_id: str = ""
    label: str = ""
    fragment_source: str = ""
    # ``fullscreen_pass_parts(fragment_source, <its block's name>)``, in the class body (so the readiness check reads
    # the vertex stage the transition draws with).
    vertex_source: str = ""
    block: Scene3DBlockLayout | None = None
    value_names: tuple[str, ...] = ()        # beyond COMMON_VALUES

    def __init__(self) -> None:
        self._program = 0
        self._layout = self.block
        self._blocks = PassBlocks(self.label, block_bytes=self._layout.size)

    @property
    def has_resources(self) -> bool:
        return bool(self._program) or self._blocks.has_resources

    def resolve(self, frame: QuickTransitionRenderFrame) -> object:
        """The run's validated values for ``values`` (no GL); raise on an unresolved parameter."""
        return None

    def values(self, resolved: object, frame: QuickTransitionRenderFrame) -> Mapping[str, object]:
        """The transition's own block values (beyond the common ones) for this frame."""
        return {}

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        resolved = self.resolve(frame)
        values = {"uMatrix": frame.matrix_values, "uItemSize": frame.logical_size,
                  "u_progress": float(frame.sample.eased_progress)}
        values.update(self.values(resolved, frame))
        data = pack_block(self._layout, values)
        gl.glUseProgram(self._program)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        with self._blocks.bound(data):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """The gradual warm-up's steps (render thread, between runs): compile the program, then, given the render
        ``size``, allocate the pass block's ring, so the run's first frame compiles and allocates nothing."""
        if not self._program:
            self._initialize()
            return size is None
        return size is None or self._blocks.warm()

    def release_resources(self) -> None:
        if self._program:
            delete_program(self._program)
            self._program = 0
        self._blocks.release()

    def _initialize(self) -> None:
        held = {name for name, _kind in self._layout.fields}
        missing = [name for name in COMMON_VALUES + self.value_names if name not in held]
        if missing:
            raise RuntimeError(f"{self.label} pass block is incomplete: " + ", ".join(missing))
        self._program = compile_program(self.vertex_source, self.fragment_source, label=self.label)
