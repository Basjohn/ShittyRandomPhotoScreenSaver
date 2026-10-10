"""Lazy Quick renderer for Capillary Bloom: the next picture spreads through the old like dye."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.capillary_bloom_program import (
    CAPILLARY_BLOOM_FRAGMENT_SOURCE,
    CAPILLARY_COST_GLSL,
    CAPILLARY_SETTLE,
    CAPILLARY_SOURCES_RANGE,
    capillary_sources,
)
from rendering.gl_programs.capillary_field import CAPILLARY_COST
from rendering.quick import gl_query
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.propagation_field import PropagationField
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from ..render_contract import QuickTransitionRenderFrame


def capillary_bloom_parameters(parameters: Mapping[str, object]) -> tuple[int, float, int]:
    """The resolved source count, fibres and seed, validated before any GL state changes."""
    sources, fibres, seed = parameters.get("sources"), parameters.get("fibres"), parameters.get("seed")
    low, high = CAPILLARY_SOURCES_RANGE
    if isinstance(sources, bool) or not isinstance(sources, int) or not low <= sources <= high:
        raise ValueError(f"Capillary Bloom needs a resolved source count between {low} and {high}")
    if isinstance(fibres, bool) or not isinstance(fibres, (int, float)) or not 0.0 <= float(fibres) <= 1.0:
        raise ValueError("Capillary Bloom needs a resolved fibres value between 0 and 1")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Capillary Bloom needs a resolved seed")
    return sources, float(fibres), seed


class QuickCapillaryBloomRenderer:
    transition_id = "capillary_bloom"

    _UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uNewTex", "uArrival", "uExtent", "uProgress", "uSeed")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Capillary Bloom")
        self._field = PropagationField("Quick Capillary Bloom", "capillary", CAPILLARY_COST_GLSL)

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._field.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        count, fibres, seed = capillary_bloom_parameters(frame.run.request.parameter_dict())
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            # Every point is dyed and the dye has cleared: the new picture.
            if progress >= CAPILLARY_SETTLE[1]:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            size = (int(frame.viewport[2]), int(frame.viewport[3]))
            arrival, extent = self._field.textures(self._resources, size, *self._field_inputs(count, fibres, seed, size))
            self._draw(frame, progress, seed, arrival, extent)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): compile, then (given the render ``size``) build the run's arrival field a few
        relaxation passes per step, so the first frame compiles, allocates and builds nothing."""
        count, fibres, seed = capillary_bloom_parameters(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, "capillary_bloom", ITEM_QUAD_VERTEX_SOURCE, CAPILLARY_BLOOM_FRAGMENT_SOURCE)]
        entries += [(r, key, source) for key, source in self._field.programs]
        if not warm_programs(entries):
            return False
        if not size or size[0] <= 0 or size[1] <= 0:
            return True
        return self._field.build_step(r, size, *self._field_inputs(count, fibres, seed, size))

    def park(self) -> None:
        """Drop the run's arrival field; the programs stay warm."""
        self._field.release()

    @staticmethod
    def _field_inputs(count: int, fibres: float, seed: int, size: tuple[int, int]):
        aspect = size[0] / max(1, size[1])
        sources, grain = capillary_sources(seed, count, aspect)

        def set_cost_uniforms(locate) -> None:
            gl.glUniform2f(locate("uGrain"), *grain)
            gl.glUniform1f(locate("uFibres"), fibres)
            gl.glUniform1f(locate("uSeed"), float(seed % 65536))

        key = (seed, count, round(fibres, 6), round(aspect, 4))
        return key, sources, CAPILLARY_COST, set_cost_uniforms

    def _draw(self, frame, progress: float, seed: int, arrival: int, extent: int) -> None:
        r = self._resources
        program = r.program("capillary_bloom", ITEM_QUAD_VERTEX_SOURCE, CAPILLARY_BLOOM_FRAGMENT_SOURCE)
        uniforms = r.uniforms("capillary_bloom", self._UNIFORMS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uSeed"], float(seed % 65536))
        # Units 0 and 1 hold the photographs (bind_frame); the field goes on 2 and 3. The host
        # fence restores units 0-2; unit 3 is handed back here.
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, arrival)
        gl.glUniform1i(uniforms["uArrival"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE3)
        inherited = gl_query.get_int(gl.GL_TEXTURE_BINDING_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, extent)
        gl.glUniform1i(uniforms["uExtent"], 3)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        try:
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        finally:
            gl.glActiveTexture(gl.GL_TEXTURE3)
            gl.glBindTexture(gl.GL_TEXTURE_2D, inherited)
            gl.glActiveTexture(gl.GL_TEXTURE0)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._field.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickCapillaryBloomRenderer:
    return QuickCapillaryBloomRenderer()
