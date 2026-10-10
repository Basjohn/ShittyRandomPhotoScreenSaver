"""Lazy Quick renderer for Edge Bloom Reveal: the new picture grows out of its own glowing contours."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.edge_bloom_program import (
    EDGE_BLOOM_FRAGMENT_SOURCE,
    EDGE_BLOOM_LINE_TEXELS,
    EDGE_BLOOM_SETTLED,
    edge_bloom_thresholds,
)
from rendering.gl_programs.photo_colour import photo_accent_colour, photo_glow_colour
from rendering.quick.scene3d.edge_field import EdgeField, edge_field_size, edge_field_warm_entries
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from ..render_contract import QuickTransitionRenderFrame

# Texture units 0-1 hold the photographs (bind_frame); the host fence restores units 0-2, so the
# new picture's field takes unit 2 and the old picture's field unit 3, handed back after the draw.
_NEW_FIELD_UNIT = 2
_OLD_FIELD_UNIT = 3


_COLOUR_SOURCES = frozenset(("custom", "next", "each"))


def edge_bloom_parameters(parameters: Mapping[str, object]) -> tuple[tuple[float, float, float], str, float, float, int]:
    """The resolved glow colour, its source, glow, detail and seed, validated before any GL state changes."""
    color, glow, detail, seed = (parameters.get(name) for name in ("color", "glow", "detail", "seed"))
    source = parameters.get("color_source")
    if source not in _COLOUR_SOURCES:
        raise ValueError(f"Edge Bloom Reveal needs a resolved colour source, not {source!r}")
    if (not isinstance(color, (tuple, list)) or len(color) < 3
            or not all(isinstance(c, (int, float)) and 0.0 <= float(c) <= 1.0 for c in color[:3])):
        raise ValueError("Edge Bloom Reveal needs a resolved colour with channels between 0 and 1")
    for name, value in (("glow", glow), ("detail", detail)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Edge Bloom Reveal needs a resolved {name} between 0 and 1")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Edge Bloom Reveal needs a resolved seed")
    return (float(color[0]), float(color[1]), float(color[2])), source, float(glow), float(detail), seed


class QuickEdgeBloomRenderer:
    transition_id = "edge_bloom"

    _UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uNewTex", "uOldField", "uNewField", "uProgress", "uTime",
                 "uLineWidth", "uGlow", "uSeed", "uColor", "uOldColor")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Edge Bloom Reveal")
        self._old_field = EdgeField("Quick Edge Bloom Reveal old picture")
        self._new_field = EdgeField("Quick Edge Bloom Reveal new picture")
        self._colours: dict[tuple, tuple[float, float, float]] = {}   # (run, image) -> glow colour

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._old_field.has_resources or self._new_field.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        color, source, glow, detail, seed = edge_bloom_parameters(frame.run.request.parameter_dict())
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= EDGE_BLOOM_SETTLED:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            self._draw(frame, progress, *self._glow_colours(frame, color, source), glow, detail, seed)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the render
        ``size`` in device pixels, allocate nothing (the fields are built, not allocated, then)."""
        edge_bloom_parameters(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, "edge_bloom", ITEM_QUAD_VERTEX_SOURCE, EDGE_BLOOM_FRAGMENT_SOURCE),
                   *edge_field_warm_entries(r)]
        if not warm_programs(entries):
            return False
        if size and size[0] > 0 and size[1] > 0:
            if not self._new_field.warm(size):
                return False
            return self._old_field.warm(size)
        return True

    def _picture_glow(self, frame, image) -> tuple[float, float, float]:
        """A picture's accent colour made luminous, found once per run."""
        key = (frame.run.run_id, image.identity)
        colour = self._colours.get(key)
        if colour is None:
            colour = photo_glow_colour(photo_accent_colour(image.rgba8, image.pixel_size, image.row_stride))
            self._colours = {k: v for k, v in self._colours.items() if k[0] == frame.run.run_id}
            self._colours[key] = colour
        return colour

    def _glow_colours(self, frame, color, source: str) -> tuple[tuple, tuple]:
        """The new picture's and the old picture's line colours for the chosen source."""
        if source == "custom":
            return color, color
        request = frame.run.request
        new = self._picture_glow(frame, request.destination_image)
        return new, (new if source == "next" else self._picture_glow(frame, request.source_image))

    def park(self) -> None:
        """Drop the run's edge fields and picture colours; the programs stay warm."""
        self._colours = {}
        try:
            self._new_field.release()
        finally:
            self._old_field.release()

    def _draw(self, frame, progress: float, color, old_color, glow: float, detail: float, seed: int) -> None:
        r = self._resources
        low, high = edge_bloom_thresholds(detail)
        request = frame.run.request
        size = tuple(frame.viewport[2:])
        new_field = self._new_field.texture(r, frame.destination_texture_id, size,
                                            (frame.run.run_id, request.destination_image.identity), low, high)
        old_field = self._old_field.texture(r, frame.source_texture_id, size,
                                            (frame.run.run_id, request.source_image.identity), low, high)
        program = r.program("edge_bloom", ITEM_QUAD_VERTEX_SOURCE, EDGE_BLOOM_FRAGMENT_SOURCE)
        uniforms = r.uniforms("edge_bloom", self._UNIFORMS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glActiveTexture(gl.GL_TEXTURE0 + _OLD_FIELD_UNIT)
        inherited = int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D))
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTextureUnit(_NEW_FIELD_UNIT, new_field)
        gl.glBindTextureUnit(_OLD_FIELD_UNIT, old_field)
        gl.glUniform1i(uniforms["uNewField"], _NEW_FIELD_UNIT)
        gl.glUniform1i(uniforms["uOldField"], _OLD_FIELD_UNIT)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uTime"], progress * request.duration_ms / 1000.0)
        gl.glUniform1f(uniforms["uLineWidth"], EDGE_BLOOM_LINE_TEXELS / edge_field_size(size)[1])
        gl.glUniform1f(uniforms["uGlow"], glow)
        gl.glUniform1f(uniforms["uSeed"], float(seed))
        gl.glUniform3f(uniforms["uColor"], *color)
        gl.glUniform3f(uniforms["uOldColor"], *old_color)
        gl.glBindVertexArray(frame.quad_vao)
        try:
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        finally:
            gl.glBindTextureUnit(_OLD_FIELD_UNIT, inherited)

    def release_resources(self) -> None:
        try:
            self.park()
        finally:
            self._resources.release_resources()


def create_transition_renderer() -> QuickEdgeBloomRenderer:
    return QuickEdgeBloomRenderer()
