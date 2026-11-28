"""Lazy Quick renderer for Depth Card Cascade: the picture's cards lift and slide past the viewer."""

from __future__ import annotations

from collections.abc import Mapping


from rendering.gl_programs.depth_cascade_program import (
    CASCADE_CARDS_RANGE,
    CASCADE_DONE,
    CASCADE_FRAGMENT_SOURCE,
    CASCADE_SHADOW_FRAGMENT_SOURCE,
    CASCADE_SHADOW_VERTEX_SOURCE,
    CASCADE_VERTEX_SOURCE,
    cascade_cards,
)
from rendering.gl_programs.depth_cascade_options import CASCADE_SWEEP_VECTORS
from rendering.gl_programs.scene3d import scene3d_request_samples
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, pack_floats
from ..native_scene import (native_clip_depth, NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses, eased_show,
                            item_quad_pass)

_QUAD = (0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0)
#: N5.2c: the card quad's and its instances' attributes by name (``_QUAD``'s corner; per card its rect and its flight).
_CARD_INPUTS = (("aLocal", 2),)
_CARD_INSTANCE_INPUTS = (("aRect", 4), ("aCard", 4))
#: The shadows' blend (``_draw``: colour SRC_ALPHA, ONE_MINUS_SRC_ALPHA; alpha ZERO, ONE).
_SHADOW_BLEND = (("add", "src_alpha", "one_minus_src_alpha"), ("add", "zero", "one"))
_SCENE_PASSES = (
    item_quad_pass("underlay", UNDERLAY_PROGRAM[1], UNDERLAY_PROGRAM[2], (("uImage", "new"),)),
    NativeScenePass("shadows", native_clip_depth(CASCADE_SHADOW_VERTEX_SOURCE), CASCADE_SHADOW_FRAGMENT_SOURCE, mesh="cards",
                    instances="mesh", blend=_SHADOW_BLEND),
    NativeScenePass("cards", native_clip_depth(CASCADE_VERTEX_SOURCE), CASCADE_FRAGMENT_SOURCE, mesh="cards", instances="mesh",
                    samplers=(("uOldTex", "old"), ("uEnvironment", "environment")), depth=True),
)


def _progress(sample) -> float:
    return max(0.0, min(1.0, float(sample.eased_progress)))


def _sweep(direction) -> tuple[float, float]:
    sweep = CASCADE_SWEEP_VECTORS.get(str(direction))
    if sweep is None:
        raise ValueError(f"unknown resolved Depth Card Cascade sweep: {direction!r}")
    return sweep


def depth_cascade_parameters(parameters: Mapping[str, object]) -> tuple[int, float, bool, int]:
    """The resolved card count, gloss, shadows and seed, validated before any GL state changes."""
    cards, gloss = parameters.get("cards"), parameters.get("gloss")
    shadows, seed = parameters.get("shadows"), parameters.get("seed")
    low, high = CASCADE_CARDS_RANGE
    if isinstance(cards, bool) or not isinstance(cards, int) or not low <= cards <= high:
        raise ValueError(f"Depth Card Cascade needs a resolved card count between {low} and {high}")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Depth Card Cascade needs a resolved gloss between 0 and 1")
    if not isinstance(shadows, bool):
        raise ValueError("Depth Card Cascade needs a resolved shadows choice")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Depth Card Cascade needs a resolved seed")
    return cards, float(gloss), shadows, seed


class QuickDepthCascadeRenderer(NativeScenePasses):
    transition_id = "depth_cascade"

    # ------------------------------------------------------------------------------- N5.2c: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        count, _gloss, shadows, seed = depth_cascade_parameters(parameters)
        width, height = logical_size
        cards = cascade_cards(seed, count, width / max(1e-6, height), _sweep(run.request.direction))
        mesh = NativeSceneMesh("cards", pack_floats(_QUAD), _CARD_INPUTS,
                               pack_floats(tuple(value for card in cards for value in card)), _CARD_INSTANCE_INPUTS)
        passes = _SCENE_PASSES if shadows else (_SCENE_PASSES[0], _SCENE_PASSES[2])
        return NativeScene(passes, (mesh,), scene3d_request_samples(parameters), True)

    def scene_show(self, run, sample) -> int:
        return eased_show(_progress(sample), CASCADE_DONE)

    def scene_values(self, run, sample, logical_size: tuple[float, float]) -> dict[str, object]:
        """The frame's values of the shadows and the cards (the underlay's are the core's)."""
        _count, gloss, _shadows, _seed = depth_cascade_parameters(run.request.parameter_dict())
        return {"uProgress": _progress(sample), "uGloss": gloss}

    # The photographs bind_frame binds (units 0 and 1; the cards read only the old); every other value is in the
    # programs' pass blocks.
    _CARD_SAMPLERS = ("uOldTex", "uNewTex")


def create_transition_renderer() -> QuickDepthCascadeRenderer:
    return QuickDepthCascadeRenderer()
