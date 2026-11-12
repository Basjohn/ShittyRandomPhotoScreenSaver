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


def _prefixed(previous, items: list, width: int) -> tuple:
    """A ``TENSION_MAX_POOLS`` array: ``items`` first, then ``previous``'s later elements (zero when none)."""
    rest = tuple(previous[len(items):]) if previous else ((0.0,) * width,) * (TENSION_MAX_POOLS - len(items))
    return tuple(items) + rest


class QuickSurfaceTensionRenderer:
    transition_id = "surface_tension"

    _SAMPLERS = ("uOldTex", "uNewTex")      # every other value is in SURFACE_TENSION_BLOCK

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Surface Tension Merge", block_bytes=SURFACE_TENSION_BLOCK.size)

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        count, gloss, seed = surface_tension_parameters(frame.run.request.parameter_dict())
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            # The flood has covered everything and the meniscus has settled: the new picture.
            if progress >= TENSION_SETTLE[1]:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            self._draw(frame, progress, count, gloss, seed)
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

    def _draw(self, frame, progress: float, count: int, gloss: float, seed: int) -> None:
        r = self._resources
        program = r.program("surface_tension", SURFACE_TENSION_VERTEX_SOURCE, SURFACE_TENSION_FRAGMENT_SOURCE)
        uniforms = r.uniforms("surface_tension", self._SAMPLERS)
        values = r.values("surface_tension")
        width, height = frame.logical_size
        pools = tension_pools(seed, count, width / max(1e-6, height))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame, values)
        # The first ``count`` elements, the rest as the array held them (glUniform*fv with a count wrote only those).
        values["uPools"] = _prefixed(values.get("uPools"), [(x, y, radius, birth)
                                                            for x, y, radius, birth, _dx, _dy in pools], 4)
        values["uDrift"] = _prefixed(values.get("uDrift"), [(dx, dy) for *_rest, dx, dy in pools], 2)
        values["uPoolCount"] = count
        values["uProgress"] = progress
        values["uGloss"] = gloss
        with r.pass_blocks.bound(pack_block(SURFACE_TENSION_BLOCK, values)):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        self._resources.release_resources()


def create_transition_renderer() -> QuickSurfaceTensionRenderer:
    return QuickSurfaceTensionRenderer()
