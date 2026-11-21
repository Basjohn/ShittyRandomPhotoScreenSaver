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
from dataclasses import dataclass

from OpenGL import GL as gl

from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl, pack_block
from rendering.gl_programs.scene3d import Scene3DBlockLayout
from rendering.quick.render.gl_resources import compile_program, delete_program
from rendering.quick.scene3d.frame import item_quad_vertex_source
from rendering.quick.scene3d.uniforms import PassBlocks
from .render_contract import QuickTransitionRenderFrame

COMMON_VALUES = ("uMatrix", "uItemSize", "u_progress")
#: The native core's frame (``run_values``): ``uMatrix`` is a core member there (its triangle reads none).
_IDENTITY_MATRIX = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


def fullscreen_pass_parts(fragment_source: str, block_name: str):
    """(the item quad's vertex stage, the block layout) from the fragment's own ``block_name`` declaration: one
    declaration for both stages and for the packing."""
    declaration = block_declaration(fragment_source, block_name)
    return item_quad_vertex_source(declaration), block_layout_from_glsl(declaration)


@dataclass(frozen=True)
class NativeQuadInstances:
    """A pass the native core draws after a transition's fragment (N5.2b's leftover, Beam's sparks): the built-in item
    quad (``aPosition``, the corners 0..1) drawn ``instances`` times from its own vertex stage, blended ``blend``
    (``rendering.native.mode.PASS_BLENDS``) over the fragment's picture. ``vertex_source`` and ``fragment_source`` are
    the texts the Python renderer compiles (baked into ``<name>.vert.qsb`` and ``<name>.frag.qsb`` beside the
    transition's fragment pack by ``tools/regen_qrc.py --shaders``); its block's values are among the transition's
    ``block_values`` by name (``uMatrix``, item to clip, is the core's)."""

    name: str
    vertex_source: str
    fragment_source: str
    instances: int
    blend: str = "additive"


class NativeFragmentPass:
    """A transition the native core can draw as one fragment between its two pictures (N5.2a, N5.2b): its
    ``fragment_source`` (baked into its pack by ``tools/regen_qrc.py --shaders``) and ``block_values``, every value of
    that fragment's pass block for a frame, by name, reading no GL object (the one owner of the values: the Python
    renderer packs them, the core fills its block from them). Beam (N5.2b's leftover) adds ``instanced_passes``, drawn
    after the fragment as instanced quads of their own vertex stage (``NativeQuadInstances``), each only where
    ``native_instanced_passes`` gives it for the run; ``block_values`` then holds their values too. A transition with
    state across frames, or a pass of another kind, is not one."""

    transition_id: str = ""
    fragment_source: str = ""
    #: Every instanced pass the transition may draw after its fragment (their packs are baked from these, discovered).
    instanced_passes: tuple[NativeQuadInstances, ...] = ()

    def block_values(self, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        raise NotImplementedError

    def native_instanced_passes(self, parameters: Mapping[str, object]) -> tuple[NativeQuadInstances, ...]:
        """The instanced passes a run with ``parameters`` draws (the program the core is given at the run's start;
        ``block_values`` gives exactly their values with the fragment's)."""
        return self.instanced_passes

    def run_values(self, run, sample, logical_size: tuple[float, float],
                   device_pixel_ratio: float) -> dict[str, object]:
        """``block_values`` for a frame the native core draws (N5.2a: the item's own target, no GL object here): the
        render frame's GL names are the contract's stand-ins, since ``block_values`` reads none of them."""
        width, height = (max(1, round(float(v) * float(device_pixel_ratio))) for v in logical_size)
        frame = QuickTransitionRenderFrame(run, sample, (0, 0, width, height),
                                           (float(logical_size[0]), float(logical_size[1])), _IDENTITY_MATRIX,
                                           1, 1, 2, device_pixel_ratio=float(device_pixel_ratio))
        return self.block_values(frame)


#: ``uShow`` (N5.2b): what an item-quad transition's fragment draws this frame: its effect, or one of its pictures
#: exactly (the frames its Python renderer draws as the plain picture).
SHOW_EFFECT, SHOW_OLD, SHOW_NEW = 0, 1, 2


class FullscreenPassRenderer(NativeFragmentPass):
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

    def block_values(self, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        """Every value of the pass block for this frame, by name: the common ones and the transition's own (validated
        by ``resolve`` first). The one owner of the values: ``render`` packs them, and the native core's fullscreen pass
        (N4.a, ``native/core/python/fullscreen_pass_check.py``) fills its block from the same dict."""
        resolved = self.resolve(frame)
        values = {"uMatrix": frame.matrix_values, "uItemSize": frame.logical_size,
                  "u_progress": float(frame.sample.eased_progress)}
        values.update(self.values(resolved, frame))
        return values

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        data = pack_block(self._layout, self.block_values(frame))
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
