"""Lazy Quick renderer for Surface Tension Merge: pools of the next picture swell and merge."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.portable import pack_block
from rendering.gl_programs.surface_tension_program import (
    SURFACE_TENSION_BLOCK,
    SURFACE_TENSION_FRAGMENT_SOURCE,
    SURFACE_TENSION_VERTEX_SOURCE,
    TENSION_MAX_POOLS,
    TENSION_POOLS_RANGE,
    TENSION_SETTLE,
    tension_pools,
)
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs, warm_pass_blocks
from ..fullscreen_pass import SHOW_EFFECT, SHOW_NEW, SHOW_OLD, NativeFragmentPass
from ..render_contract import QuickTransitionRenderFrame


def surface_tension_parameters(parameters: Mapping[str, object]) -> tuple[int, float, int]:
    """The resolved pool count, gloss and seed, validated before any GL state changes."""
    pools, gloss, seed = parameters.get("pools"), parameters.get("gloss"), parameters.get("seed")
    low, high = TENSION_POOLS_RANGE
    if isinstance(pools, bool) or not isinstance(pools, int) or not low <= pools <= high:
        raise ValueError(f"Surface Tension Merge needs a resolved pool count between {low} and {high}")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Surface Tension Merge needs a resolved gloss between 0 and 1")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Surface Tension Merge needs a resolved seed")
    return pools, float(gloss), seed


def _padded(items: list, width: int) -> tuple:
    """A ``TENSION_MAX_POOLS`` array: ``items`` first, then zeros (the fragment reads only ``uPoolCount`` of them)."""
    return tuple(items) + ((0.0,) * width,) * (TENSION_MAX_POOLS - len(items))


def _shown(progress: float) -> int:
    """What the frame shows: the old picture before the run; the new one once the flood has covered everything and the
    meniscus has settled; else the effect."""
    if progress <= 0.0:
        return SHOW_OLD
    if progress >= TENSION_SETTLE[1]:
        return SHOW_NEW
    return SHOW_EFFECT


class QuickSurfaceTensionRenderer(NativeFragmentPass):
    transition_id = "surface_tension"
    fragment_source = SURFACE_TENSION_FRAGMENT_SOURCE

    _SAMPLERS = ("uOldTex", "uNewTex")      # every other value is in SURFACE_TENSION_BLOCK

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Surface Tension Merge", block_bytes=SURFACE_TENSION_BLOCK.size)

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def block_values(self, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        """Every value of the pass block for this frame (validated first; no GL): the one owner, packed by ``render``
        and filled by the native core (N5.2b). The pools are arrays (the core packs them flat at their stride)."""
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        count, gloss, seed = surface_tension_parameters(frame.run.request.parameter_dict())
        width, height = frame.logical_size
        pools = tension_pools(seed, count, width / max(1e-6, height))
        return {"uMatrix": frame.matrix_values, "uItemSize": frame.logical_size, "u_target_px": frame.item_pixels,
                "uShow": _shown(progress),
                "uPools": _padded([(x, y, radius, birth) for x, y, radius, birth, _dx, _dy in pools], 4),
                "uDrift": _padded([(dx, dy) for *_rest, dx, dy in pools], 2),
                "uPoolCount": count, "uProgress": progress, "uGloss": gloss}

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        values = self.block_values(frame)
        try:
            if values["uShow"] == SHOW_OLD:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if values["uShow"] == SHOW_NEW:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            self._draw(frame, values)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing. Surface Tension
        Merge allocates nothing per run (its pools are a few uniforms)."""
        surface_tension_parameters(parameters)
        r = self._resources
        return warm_programs([(r, *UNDERLAY_PROGRAM),
                              (r, "surface_tension", SURFACE_TENSION_VERTEX_SOURCE, SURFACE_TENSION_FRAGMENT_SOURCE)]
                             ) and warm_pass_blocks(r, size)

    def park(self) -> None:
        """Nothing per run to drop; the programs stay warm."""

    def _draw(self, frame, block: dict) -> None:
        r = self._resources
        program = r.program("surface_tension", SURFACE_TENSION_VERTEX_SOURCE, SURFACE_TENSION_FRAGMENT_SOURCE)
        uniforms = r.uniforms("surface_tension", self._SAMPLERS)
        values = r.values("surface_tension")
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame, values)
        values.update(block)
        with r.pass_blocks.bound(pack_block(SURFACE_TENSION_BLOCK, values)):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        self._resources.release_resources()


def create_transition_renderer() -> QuickSurfaceTensionRenderer:
    return QuickSurfaceTensionRenderer()
