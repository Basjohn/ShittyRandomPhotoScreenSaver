"""Lazy Quick renderer for Jigsaw Piece Flip: jigsaw pieces flip over one by one to the next picture."""

from __future__ import annotations

from collections.abc import Mapping
import math


from rendering.gl_programs.jigsaw_options import JIGSAW_ORDERS, JIGSAW_PIECES_RANGE
from rendering.gl_programs.jigsaw_program import (
    JIGSAW_FLAT_FRAGMENT_SOURCE,
    JIGSAW_FLAT_VERTEX_SOURCE,
    JIGSAW_FLIGHT_FRAGMENT_SOURCE,
    JIGSAW_FLIGHT_VERTEX_SOURCE,
    JIGSAW_HOP,
    JIGSAW_MAX_PIECES,
    JIGSAW_SHADOW_FRAGMENT_SOURCE,
    JIGSAW_SHADOW_VERTEX_SOURCE,
    JIGSAW_THICKNESS,
)
from rendering.gl_programs.scene3d import scene3d_detail, scene3d_request_samples
from ..native_scene import native_clip_depth, NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses, eased_show
from ..piece_layout import PIECE_VERTEX_ATTRIBUTES
from ..run_geometry import PREPARED_GEOMETRY, build_jigsaw_geometry, jigsaw_geometry_key

_ORDER_CODES = frozenset(JIGSAW_ORDERS.values())
_PIECE_BYTES = 16                                  # one vec4 (centre uv, rank, axis angle), std140's array stride
_NO_PIECES = bytes(JIGSAW_MAX_PIECES * _PIECE_BYTES)
#: N5.2c: the pieces' attributes by name (``PIECE_VERTEX_ATTRIBUTES``' order).
_PIECE_INPUTS = tuple(zip(("aUv", "aSide", "aNormal", "aBevel", "aPiece"), PIECE_VERTEX_ATTRIBUTES))
#: The shadow's multiply (``blend_scope(GL_FUNC_ADD, GL_DST_COLOR, GL_ZERO)``: alpha ZERO, ONE).
_SHADOW_BLEND = (("add", "dst_color", "zero"), ("add", "zero", "one"))
_SCENE_PASSES = (
    NativeScenePass("flat", native_clip_depth(JIGSAW_FLAT_VERTEX_SOURCE), JIGSAW_FLAT_FRAGMENT_SOURCE, mesh="pieces",
                    samplers=(("uOldTex", "old"), ("uNewTex", "new"))),
    NativeScenePass("shadow", JIGSAW_SHADOW_VERTEX_SOURCE, JIGSAW_SHADOW_FRAGMENT_SOURCE, topology="triangle_strip",
                    vertices=4, blend=_SHADOW_BLEND),
    NativeScenePass("flight", native_clip_depth(JIGSAW_FLIGHT_VERTEX_SOURCE), JIGSAW_FLIGHT_FRAGMENT_SOURCE, mesh="pieces",
                    samplers=(("uOldTex", "old"), ("uNewTex", "new"), ("uEnvironment", "environment")), depth=True),
)


def _progress(sample) -> float:
    return max(0.0, min(1.0, float(sample.eased_progress)))


def jigsaw_values(geometry, progress: float, aspect: float) -> dict[str, object]:
    """Every pass's values for a frame of ``geometry`` (N5.2c's one owner): the schedule (``uPieces`` packed whole),
    the cell (the shadow's) and the card's size and hop (the flight's and the shadow's); a block takes the names it
    declares."""
    cell_w, cell_h = aspect / geometry.cols, 1.0 / geometry.rows
    knob = min(cell_w, cell_h)
    return {"uProgress": progress, "uCount": geometry.count, "uPieces": _pieces_block(geometry.pieces),
            "uCell": (cell_w, cell_h), "uThick": JIGSAW_THICKNESS * knob,
            "uRadius": 0.5 * math.hypot(cell_w, cell_h) + 0.3 * knob, "uHop": JIGSAW_HOP * knob}


def _pieces_block(pieces: bytes) -> bytes:
    """``uPieces`` as its pass block holds it: the run's pieces (float32 vec4s) and zero after them (never read: a
    piece index is below the count)."""
    if len(pieces) % _PIECE_BYTES or len(pieces) > len(_NO_PIECES):
        raise ValueError(f"Jigsaw Piece Flip holds at most {JIGSAW_MAX_PIECES} pieces of {_PIECE_BYTES} bytes")
    return bytes(pieces) + _NO_PIECES[len(pieces):]


def jigsaw_parameters(parameters: Mapping[str, object]) -> tuple[int, int, str]:
    """The resolved seed, piece count and order, validated before any GL state changes."""
    seed, pieces, order = parameters.get("seed"), parameters.get("pieces"), parameters.get("order")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Jigsaw Piece Flip seed must be an integer between 1 and 65535")
    low, high = JIGSAW_PIECES_RANGE
    if isinstance(pieces, bool) or not isinstance(pieces, int) or not low <= pieces <= high:
        raise ValueError(f"Jigsaw Piece Flip pieces must be an integer between {low} and {high}")
    if order not in _ORDER_CODES:
        raise ValueError(f"unknown resolved Jigsaw Piece Flip order: {order!r}")
    return seed, pieces, str(order)


def _shadows(parameters: Mapping[str, object]) -> bool:
    return scene3d_detail(parameters.get("detail", "High")).shadows


def _run_geometry(run, logical_size: tuple[float, float]):
    """The run's prepared pieces (COMPUTE's, ``prepare_run_geometry``; built here when it has not prepared them)."""
    aspect = logical_size[0] / logical_size[1]
    return PREPARED_GEOMETRY.get_or_build(jigsaw_geometry_key(run.request.parameter_dict(), aspect),
                                          build_jigsaw_geometry), aspect


class QuickJigsawRenderer(NativeScenePasses):
    transition_id = "jigsaw"

    # ------------------------------------------------------------------------------- N5.2c: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        jigsaw_parameters(parameters)
        geometry, _aspect = _run_geometry(run, logical_size)
        flat, shadow, flight = _SCENE_PASSES
        flat = NativeScenePass(flat.name, flat.vertex_source, flat.fragment_source, mesh=flat.mesh,
                               vertices=int(geometry.flat_vertices), samplers=flat.samplers)
        shadow = NativeScenePass(shadow.name, shadow.vertex_source, shadow.fragment_source, topology=shadow.topology,
                                 vertices=4, instances=int(geometry.count), blend=shadow.blend)
        pieces = NativeSceneMesh("pieces", bytes(geometry.vertices), _PIECE_INPUTS)
        passes = (flat, shadow, flight) if _shadows(parameters) else (flat, flight)
        return NativeScene(passes, (pieces,), scene3d_request_samples(parameters), True)

    def scene_show(self, run, sample) -> int:
        return eased_show(_progress(sample))

    def scene_values(self, run, sample, logical_size: tuple[float, float]) -> dict[str, object]:
        geometry, aspect = _run_geometry(run, logical_size)
        return jigsaw_values(geometry, _progress(sample), aspect)

    # The photographs bind_frame binds (units 0 and 1); every other value is in the programs' pass blocks.
    _SAMPLERS = ("uOldTex", "uNewTex")


def create_transition_renderer() -> QuickJigsawRenderer:
    return QuickJigsawRenderer()
