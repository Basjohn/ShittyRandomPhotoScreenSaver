"""Lazy Quick renderer for Edge Bloom Reveal: the new picture grows out of its own glowing contours."""

from __future__ import annotations

from collections.abc import Mapping


from rendering.gl_programs.edge_bloom_program import (
    EDGE_BLOOM_FRAGMENT_SOURCE,
    EDGE_BLOOM_LINE_TEXELS,
    EDGE_BLOOM_SETTLED,
    edge_bloom_thresholds,
)
from rendering.gl_programs.photo_colour import photo_accent_colour, photo_glow_colour
from rendering.quick.scene3d.edge_field import edge_field_size
from ..fullscreen_pass import SHOW_EFFECT, SHOW_NEW, SHOW_OLD, NativeFragmentPass, NativeFieldRequest
from ..render_contract import QuickTransitionRenderFrame

#: N5.2g: the item textures the native core makes the run's two edge fields into (field recipes, ABI 43).
NATIVE_NEW_FIELD = "edge_field_new"
NATIVE_OLD_FIELD = "edge_field_old"

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


def _shown(progress: float) -> int:
    if progress <= 0.0:
        return SHOW_OLD
    if progress >= EDGE_BLOOM_SETTLED:
        return SHOW_NEW
    return SHOW_EFFECT


class QuickEdgeBloomRenderer(NativeFragmentPass):
    transition_id = "edge_bloom"
    fragment_source = EDGE_BLOOM_FRAGMENT_SOURCE
    #: N5.2g: the fields' samplers on the native core (linear and clamped, as the fields' own textures).
    native_samplers = (("uNewField", NATIVE_NEW_FIELD, "linear"), ("uOldField", NATIVE_OLD_FIELD, "linear"))
    native_settled = EDGE_BLOOM_SETTLED       # the eased progress from which the frame is the new picture

    _SAMPLERS = ("uOldTex", "uNewTex")      # the fields' samplers are bound in the source; values in EDGE_BLOOM_BLOCK

    def __init__(self) -> None:
        self._colours: dict[tuple, tuple[float, float, float]] = {}

    @classmethod
    def native_field_sources(cls) -> dict[str, str]:
        from rendering.quick.scene3d.native_fields import edge_field_sources

        return edge_field_sources()

    def native_fields(self, run, pixels: tuple[int, int]) -> tuple[NativeFieldRequest, ...]:
        """N5.2g: the run's two edge fields as field recipes: the new picture's and the old picture's, each over its own
        photograph (``EdgeField._build``'s dispatches at the render's device ``pixels``)."""
        from rendering.quick.scene3d.native_fields import edge_field_recipe

        _color, _source, _glow, detail, _seed = edge_bloom_parameters(run.request.parameter_dict())
        low, high = edge_bloom_thresholds(detail)
        return (NativeFieldRequest("new", edge_field_recipe(pixels, low, high, input_texture="", output=NATIVE_NEW_FIELD)),
                NativeFieldRequest("old", edge_field_recipe(pixels, low, high, input_texture="", output=NATIVE_OLD_FIELD)))

    def block_values(self, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        """Every value of the pass block for this frame (no GL): the one owner, packed by ``_draw`` and filled by the
        native core (N5.2g)."""
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        color, source, glow, _detail, seed = edge_bloom_parameters(frame.run.request.parameter_dict())
        new, old = self._glow_colours(frame, color, source)
        size = tuple(frame.viewport[2:])
        return {"uMatrix": frame.matrix_values, "uItemSize": frame.logical_size, "uProgress": progress,
                "uTime": progress * frame.run.request.duration_ms / 1000.0,
                "uLineWidth": EDGE_BLOOM_LINE_TEXELS / edge_field_size(size)[1], "uGlow": glow,
                "uSeed": float(seed), "uColor": new, "uOldColor": old, "uShow": _shown(progress)}

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


def create_transition_renderer() -> QuickEdgeBloomRenderer:
    return QuickEdgeBloomRenderer()
