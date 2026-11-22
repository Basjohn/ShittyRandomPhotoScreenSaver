"""The native core's field recipes (ABI 43, ``Current_Plan.md`` N5.2g with N4.g): the edge field (``edge_field.py``) and
the propagation field (``propagation_field.py``) as data the core records (``native/core/src/field_recipe.h``), from the
same compute texts and the same values the Python owners dispatch, so one owner holds each.

- ``edge_field_sources()`` / ``propagation_sources(name, cost_glsl)``: every compute pack a recipe names, by its file
  name (``tools/regen_qrc.py --shaders`` bakes ``<stem>.comp.qsb`` beside the transitions' packs). A propagation
  consumer's seed has its cost block and the dispatch block merged into one (``native_one_block``: the core admits one
  block a dispatch); the edge field's stages and the relax and extent stages declare one already.
- ``edge_field_recipe(...)`` / ``propagation_recipe(...)``: one ``NativeFieldRecipe`` (the JSON the core admits, its
  packs' stems in order, and its blocks: std140 bytes packed by the owners' own ``Scene3DBlockLayout``), the dispatches
  in the Python owner's order exactly (the flood's jumps, the relax ping-pong, the extent last).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rendering.gl_programs.scene3d import Scene3DBlockLayout

from . import edge_field as ef
from . import propagation_field as pf

#: The edge field's stages' pack stems, in the owner's order (``EDGE_FIELD_PROGRAMS``).
EDGE_FIELD_PACKS = tuple(key for key, _source in ef.EDGE_FIELD_PROGRAMS)
PROPAGATION_RELAX_FORWARD = "propagation_relax_forward"
PROPAGATION_RELAX_BACK = "propagation_relax_back"
PROPAGATION_EXTENT = "propagation_extent"


def propagation_seed_stem(name: str) -> str:
    return f"propagation_seed_{name}"


@dataclass(frozen=True)
class NativeFieldRecipe:
    """A recipe as the core takes it (``NativeMode.field``): its declaration, its packs' stems in index order and its
    blocks' bytes in index order."""

    recipe: dict
    packs: tuple[str, ...]
    blocks: tuple[bytes, ...]
    outputs: tuple[str, ...] = field(default=())

    def pack_bytes(self, folder: Path) -> list[bytes]:
        return [(Path(folder) / f"{stem}.comp.qsb").read_bytes() for stem in self.packs]

    def with_input(self, texture: str | None) -> "NativeFieldRecipe":
        """The same recipe sampling the item texture ``texture`` (a consumer names its photograph's slot late)."""
        return NativeFieldRecipe({**self.recipe, "input": texture or None}, self.packs, self.blocks, self.outputs)


class _Builder:
    def __init__(self) -> None:
        self.packs: list[str] = []
        self.blocks: list[bytes] = []
        self.images: list[dict] = []
        self.dispatches: list[dict] = []

    def pack(self, stem: str) -> int:
        if stem not in self.packs:
            self.packs.append(stem)
        return self.packs.index(stem)

    def block(self, data: bytes) -> int:
        if data not in self.blocks:
            self.blocks.append(bytes(data))
        return self.blocks.index(bytes(data))

    def image(self, name: str, fmt: str, size: tuple[int, int]) -> None:
        self.images.append({"name": name, "format": fmt, "size": [int(size[0]), int(size[1])]})

    def dispatch(self, stem: str, block: bytes | None, groups: tuple[int, int, int], bindings: dict) -> None:
        self.dispatches.append({"pack": self.pack(stem), "block": -1 if block is None else self.block(block),
                                "groups": [int(g) for g in groups], "bindings": dict(bindings)})

    def recipe(self, input_texture: str | None, outputs: list[tuple[str, str]]) -> NativeFieldRecipe:
        declaration = {"input": input_texture, "images": self.images, "dispatches": self.dispatches,
                       "outputs": [{"image": image, "texture": texture} for image, texture in outputs]}
        return NativeFieldRecipe(declaration, tuple(self.packs), tuple(self.blocks),
                                 tuple(texture for _image, texture in outputs))


def _image(name: str, access: str) -> dict:
    return {"image": name, "access": access}


# ------------------------------------------------------------------------------------------------- the edge field

def edge_field_sources() -> dict[str, str]:
    """The edge field's compute packs by file name (the owner's texts verbatim: one block each)."""
    return {f"{key}.comp": source for key, source in ef.EDGE_FIELD_PROGRAMS}


def edge_field_recipe(pixel_size: tuple[int, int], low: float, high: float, *, input_texture: str,
                      output: str) -> NativeFieldRecipe:
    """The edge field of the item texture ``input_texture`` (the photograph) for a render of ``pixel_size`` device
    pixels and the thresholds ``low`` / ``high``, into the item texture ``output`` (rgba16f): ``EdgeField._build``'s
    dispatches as data."""
    size = ef.edge_field_size(pixel_size)
    width, height = size
    groups = (-(-width // ef._GROUP), -(-height // ef._GROUP), 1)
    values = {"uSize": (width, height), "uStep": (0.25 / width, 0.25 / height), "uLow": float(low),
              "uHigh": float(high), "uJump": 0}
    base = ef._DISPATCH_BLOCK.pack(values)
    b = _Builder()
    for name, fmt in (("luma", "r16f"), ("blur", "r16f"), ("edge", "r16f"), ("ping", "rgba32f"), ("pong", "rgba32f"),
                      ("field", "rgba16f")):
        b.image(name, fmt, size)
    b.dispatch("edge_field_luma", base, groups, {"uPhoto": "input", "uLuma": _image("luma", "write")})
    for read, write in (("luma", "blur"), ("blur", "luma")):
        b.dispatch("edge_field_blur", base, groups, {"uLuma": _image(read, "read"), "uBlur": _image(write, "write")})
    b.dispatch("edge_field_edges", base, groups, {"uLuma": _image("luma", "read"), "uEdge": _image("edge", "write"),
                                                  "uSeed": _image("ping", "write")})
    source, target = "ping", "pong"
    for jump in ef.edge_field_jumps(size):
        b.dispatch("edge_field_flood", ef._DISPATCH_BLOCK.pack({**values, "uJump": int(jump)}), groups,
                   {"uSeedIn": _image(source, "read"), "uSeedOut": _image(target, "write")})
        source, target = target, source
    b.dispatch("edge_field_resolve", base, groups, {"uSeed": _image(source, "read"), "uEdge": _image("edge", "read"),
                                                    "uField": _image("field", "write")})
    return b.recipe(input_texture, [("field", output)])


# ------------------------------------------------------------------------------------------------- the propagation

def _seed_layout(cost_glsl: str) -> Scene3DBlockLayout:
    _source, cost = pf._portable_seed(cost_glsl)
    return Scene3DBlockLayout.of(cost.name, tuple(cost.fields) + tuple(pf._DISPATCH_BLOCK.fields))


def propagation_seed_source(cost_glsl: str) -> str:
    from rendering.quick.transitions.native_scene import native_one_block

    source, _cost = pf._portable_seed(cost_glsl)
    return native_one_block((source,), "PropagationDispatch")[0]


def propagation_sources(name: str, cost_glsl: str) -> dict[str, str]:
    """A propagation consumer's packs by file name: its seed (one merged block) and the shared relax and extent."""
    return {f"{propagation_seed_stem(name)}.comp": propagation_seed_source(cost_glsl),
            f"{PROPAGATION_RELAX_FORWARD}.comp": pf._RELAX_FORWARD_COMPUTE,
            f"{PROPAGATION_RELAX_BACK}.comp": pf._RELAX_BACK_COMPUTE,
            f"{PROPAGATION_EXTENT}.comp": pf._EXTENT_COMPUTE}


def propagation_recipe(name: str, cost_glsl: str, pixel_size: tuple[int, int], sources, bound: float,
                       cost_values: dict, *, arrival: str, extent: str,
                       passes: int = pf.PROPAGATION_PASSES) -> NativeFieldRecipe:
    """The arrival field and its extent for a render of ``pixel_size`` (``PropagationField.build_step``'s dispatches:
    the seed, ``passes`` relax passes forward and back over the same two images, the extent), into the item textures
    ``arrival`` and ``extent`` (r32f). No input: the field is the consumer's cost alone."""
    size = pf.propagation_size(pixel_size)
    width, height = size
    groups = (-(-width // pf._GROUP), -(-height // pf._GROUP), 1)
    count = min(len(sources), pf.PROPAGATION_MAX_SOURCES)
    packed = [(*source[:3], 0.0) for source in list(sources)[:count]]
    dispatch = {"uSize": (width, height), "uAspect": width / height, "uSourceCount": count, "uBound": float(bound),
                "uSources": packed + [(0.0, 0.0, 0.0, 0.0)] * (pf.PROPAGATION_MAX_SOURCES - count)}
    layout = _seed_layout(cost_glsl)
    seed_values = {member: 0.0 for member, _kind in layout.fields}
    seed_values.update({k: v for k, v in cost_values.items()})
    seed_values.update(dispatch)
    for member, kind in layout.fields:
        value = seed_values[member]
        if kind in ("ivec2", "vec2") and not isinstance(value, (tuple, list)):
            seed_values[member] = (value, value)
    plain = pf._DISPATCH_BLOCK.pack(dispatch)
    b = _Builder()
    for image in ("cost", "arrival", "relaxed"):
        b.image(image, "r32f", size)
    b.image("extent", "r32f", (1, 1))
    b.dispatch(propagation_seed_stem(name), layout.pack(seed_values), groups,
               {"uCost": _image("cost", "write"), "uArrival": _image("arrival", "write")})
    newest, other = "arrival", "relaxed"
    for index in range(int(passes)):
        stem = PROPAGATION_RELAX_FORWARD if index % 2 == 0 else PROPAGATION_RELAX_BACK
        b.dispatch(stem, plain, groups, {"uCost": _image("cost", "read"), "uArrival": _image(newest, "read"),
                                         "uRelaxed": _image(other, "write")})
        newest, other = other, newest
    b.dispatch(PROPAGATION_EXTENT, plain, (1, 1, 1),
               {"uArrival": _image(newest, "read"), "uExtent": _image("extent", "write")})
    return b.recipe(None, [(newest, arrival), ("extent", extent)])


__all__ = ["EDGE_FIELD_PACKS", "NativeFieldRecipe", "PROPAGATION_EXTENT", "PROPAGATION_RELAX_BACK",
           "PROPAGATION_RELAX_FORWARD", "edge_field_recipe", "edge_field_sources", "propagation_recipe",
           "propagation_seed_source", "propagation_seed_stem", "propagation_sources"]
