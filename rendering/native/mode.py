"""A generic mode's Python face (Current_Plan.md item 8b, N2.9; ``native/core/src/mode_content.h``).

A Visualizer mode drawn by the native core from data alone, so a new mode, or a port of a 2D mode, needs no per-mode
C++ and no module build; the Python renderer and the core draw the same shader file:

- its **simulation** runs in Python (the engine worker in the product), publishing one fixed-layout frame record per
  frame through the frame mapping (``core.visualizer_engine.packet_abi``);
- its **schema** is the record's table (``core.visualizer_engine.native_schema.NativeSchema``), handed to the core when
  the stream is bound (:func:`schema_table_entry`): the core's reader admits the mode's slots by it, and the record's
  fields are packed by name;
- its **program** is one or more passes (:class:`ModePass`): a fragment pack each (the product's ``.qsb``, baked by
  ``tools/regen_qrc.py``'s baker, handed over as bytes) and a blend (``PASS_BLENDS``), drawn in order over the card;
- its **settings** are every Settings- and mode-derived value, resolved here from the spec, by name; its **card**
  (:func:`mode_card`) is the item as shown.

The product fullscreen shaders' shape: a pass declares one std140 block of its own (any name, any binding but 17),
optionally the conventions block, a vec2 at location 0 named ``v_uv`` (the Visualizer quad's uv, y down) or ``vUv``
(the item quad's, y up; the fullscreen transitions), and ``sampler2D`` s, each bound by name to one of the item's
textures (:class:`PassSampler`, N4.a). One rule fills the block by member name from exactly one of three sources:
the core's conventions (``MODE_CORE_MEMBERS``: what the Python renderers compute per frame from the card and the
target), the settings, and the record's fields. The core refuses an unknown name (a setting or a field no pass
declares), a name with two owners (a setting or field naming a core member, a setting naming a field), an unfilled
member, and an unbound, unknown or doubly bound sampler, each with its reason. A shader, spec or simulation change is a
new pack, new settings or a new record: never C++.

The textures (N4.a, :meth:`NativeMode.texture`): pixels Python holds (RGBA8, rows top first, tight) are copied once
into the core and uploaded once (mips generated on the GPU when asked), never again at rest; a removed texture is
released on the render thread. N3.8 (D9): on a Vulkan device with a job service the upload is a job on the job queue,
and the item's changed textures are drawn together once their jobs are published; elsewhere it is recorded in the
frame. A texture whose node was made again is lost: the owner's :meth:`NativeMode.on_textures_lost` is called with its
name (the edge; ``state()["textures_lost"]`` keeps the list), and it sends the image again.

Scene targets (N3.1, decision D14; ``native/core/src/scene_targets.h``): a program may declare up to four targets
(:class:`ModeTarget`) its passes draw into before what reaches the card: colour attachments (``TARGET_FORMATS``; the HDR
intermediate is ``rgba16f``), an optional D32F depth, a requested sample count (``rendering.gl_programs.scene3d``'s
``scene_samples`` is its one owner; the core clamps it to the device). A pass names its ``target``, writes one output per
attachment (:class:`PassOutput`: its write mask and blend) and may test and write the depth (``depth_test``,
``depth_write``); a :class:`CapturePass` copies what a target's passes drew so far (Python's ``SceneTarget.background()``);
a sampler reads ``"<target>.<attachment>"``, ``"<target>.depth"``, ``"<target>.capture_colour"`` or
``"<target>.capture_depth"``. Allocation is the core's: 64 px buckets, grown at once, shrunk two buckets below.
Meshes and buffers (N3.2, decision D15; ``native/core/src/mesh_buffers.h``): a pass may bring its own vertex stage
(:class:`PassGeometry`: its vertex pack, topology, counts, its mesh and instance source, storage, cull and front face, an
indirect or batched draw); an item holds meshes (:meth:`NativeMode.mesh`: interleaved f32 records with their
:class:`RecordLayout`, uploaded once; the built-in ``quad`` is the item quad's four vertices, ``aPosition``); a program
declares streams (:class:`ModeStream`: a record field each, read as per-instance attributes, storage or indirect
commands); a blend may be a full declaration (:class:`BlendState`). Every block lives in one arena at aligned offsets
(``rendering.native.streams.arena_layout`` mirrors the core's plan); ``firstInstance`` is always 0.
Compute passes (N3.3, decision D16; ``native/core/src/compute_passes.h``): a program may declare storage buffers
(:class:`StorageBuffer`) and images (:class:`StorageImage`, 2D or 3D) and compute entries in its pass list
(:class:`ComputePass`: one compute pack, its trigger, groups and bindings, each with its access); each entry is its own
QRhi compute pass and dispatches only when its trigger has new work (``u_srpss_compute`` tells the shader the trigger,
its last value, whether the storage is fresh, and the dispatches since). Draws read a storage buffer as storage, per
instance or as indirect commands, and an image through a sampler. Nothing is read back in the product; a content made
again finds its storage gone and the owner's :meth:`NativeMode.on_state_lost` is told once.
Stages (N3.4, decision D17; ``native/core/src/post_stages.h``), each data in the program and absent unless declared:
depth-aware order-independent transparency (:class:`TransparencyTarget`, its passes with their sorted packs, and a
:class:`TransparencyResolve`), bloom (:class:`BloomStep`), the composite onto the card with the HDR tone map
(:class:`CompositeStep`) and the defocus layer (a ``mips`` :class:`ModeTarget` and a :class:`DefocusStep`). The core's
shaders draw them (the Python oracles: ``rendering/quick/scene3d/target.py``, ``post.py``, ``defocus.py``); their
strengths, exposure, radius and level are block members the settings or the record fill.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable, Mapping, Sequence

from rendering.native.composite import CompositeItem
from rendering.native.packet_reader import reader_config

#: How a pass's colour meets the target (``PassBlend`` in ``mode_content.h``).
PASS_BLENDS = ("replace", "alpha", "premultiplied", "add", "additive")  # N3.1: "additive" is ONE, ONE
#: N3.1: a scene target's attachment formats (``TargetFormat`` in ``scene_targets.h``) and a pass's depth tests.
TARGET_FORMATS = ("rgba8", "rgba16f", "r16f", "r32f")
#: D14 points 8 and 10: a multisampled attachment's single-sampled copy (QRhi's average, or the core's nearest).
TARGET_RESOLVES = ("average", "nearest")
DEPTH_TESTS = ("none", "never", "less", "equal", "less_equal", "greater", "not_equal", "greater_equal", "always")
#: N3.1: the most targets a program declares, attachments a target holds, samples a target requests.
MAX_TARGETS = 4
MAX_TARGET_COLOUR = 4
MAX_TARGET_SAMPLES = 8
#: The core's conventions (``kModeCoreMembers`` in ``mode_content.cpp``; a test holds the two equal): name ->
#: (components, read from the card). Every other member of a pass's block is a setting or a record field.
MODE_CORE_MEMBERS = {
    "uMatrix": (16, False),
    "uItemSize": (2, True),
    "uContentRotationQuarters": (1, True),
    "u_resolution": (2, True),
    "u_dpr": (1, True),
    "u_viewport_origin_px": (2, False),
    "u_quick_item_coords": (1, False),
    "u_fade": (1, True),
    "u_border_width": (1, True),
    "u_item_from_frag": (1, False),
    "u_item_from_frag_x": (3, True),
    "u_item_from_frag_y": (3, True),
    "u_window_from_target_x": (3, True),
    "u_window_from_target_y": (3, True),
    "u_target_px": (2, False),
    "u_scene_item": (4, True),     # ABI 27: the item's cover in the target's pixels (left, top, width, height)
    "u_scene_from_target_x": (3, True),  # ABI 29: the target's pixel to the scene's texel (the composite's), rows x
    "u_scene_from_target_y": (3, True),  # and y: the surface's own unturned, the window's frame under a turned card
    "uOriented": (2, True),
    "uQuarters": (1, True),
    "u_srpss_batch": (1, False),   # N3.2 (D15 point 6): a batched pass's batch
    "u_srpss_compute": (4, False), # N3.3 (D16 point 7): a compute entry's (trigger, last trigger, fresh, dispatches)
}
#: The card's keys (``ModeCard::fromJson``).
MODE_CARD_KEYS = ("quarters", "item_size", "oriented_size", "dpr", "content_fade", "border_width", "window_from_target",
                  "item_from_window", "scene_item")
#: The card's optional keys (ABI 28: ``scene_item``, Python's SceneTarget rect; without it the item covers its target).
MODE_CARD_OPTIONAL_KEYS = ("scene_item",)


def schema_table_entry(schema: Any) -> dict:
    """``schema`` (a ``NativeSchema``) as the core reads a table: the compiled header's and a runtime schema's one
    shape (rows ``[name, kind, count, offset, check, limit]`` in the reference decoder's order, the check order as
    indexes, the layout's fingerprint)."""
    checks = {name: (kind, limit) for name, kind, limit in schema.checks}
    rows = []
    for name in schema.fields:
        entry = schema.layout.field(name)
        kind, limit = checks.get(name, ("", 0))
        rows.append([name, entry.kind, entry.count, entry.offset, kind, limit])
    return {
        "schema_id": schema.schema_id, "mode_id": schema.mode_id, "mode_code": schema.mode_code,
        "version": schema.version, "record_bytes": schema.layout.size,
        "fingerprint": schema.layout.fingerprint(), "fields": rows,
        "check_order": [schema.fields.index(name) for name, _kind, _limit in schema.checks],
    }


def mode_card(presentation: Any, geometry: Any, *, window_size: tuple[float, float],
              window_pixels: tuple[int, int]) -> dict:
    """The card a generic mode's core members read: ``presentation`` (a ``ResolvedVisualizerPresentation``) through
    its composite ``geometry`` in a window of ``window_size`` (logical) and ``window_pixels`` (its framebuffer, Qt's
    own: ``CompositeItem.window_pixels``). The maps are the native Spectrum's (``spectrum_presentation``): the Python
    renderers' own arithmetic."""
    from rendering.native.spectrum import spectrum_presentation

    card = spectrum_presentation(presentation, geometry, window_size=window_size, window_pixels=window_pixels,
                                 scene_item=True)
    values = {key: card[key] for key in MODE_CARD_KEYS if key in card}
    values["border_width"] = float(getattr(presentation, "border_width", 0.0) or 0.0)
    return values


#: A sampler's state (``PassSampler`` in ``mode_content.h``): its filter, its wrap and its mip filter.
SAMPLER_FILTERS = ("nearest", "linear")
SAMPLER_WRAPS = ("clamp", "repeat", "mirror")
SAMPLER_MIPS = ("none", "nearest", "linear")


@dataclass(frozen=True)
class PassSampler:
    """One ``sampler2D`` of a pass (by its name in the shader) bound to one of the item's textures (by its name), with
    its sampler state declared beside it (N4.a)."""

    name: str
    texture: str
    filter: str = "linear"
    wrap: str = "clamp"
    mips: str = "none"

    def __post_init__(self) -> None:
        for value, allowed, what in ((self.filter, SAMPLER_FILTERS, "filter"), (self.wrap, SAMPLER_WRAPS, "wrap"),
                                     (self.mips, SAMPLER_MIPS, "mips")):
            if value not in allowed:
                raise ValueError(f"unknown {what} {value!r} (the {what} values are {', '.join(allowed)})")

    def declaration(self) -> dict:
        return {"name": self.name, "texture": self.texture, "filter": self.filter, "wrap": self.wrap,
                "mips": self.mips}


@dataclass(frozen=True)
class TargetAttachment:
    """N3.1: one colour attachment of a scene target: its name, its format, the value its clearing draw writes and,
    when the target is multisampled, how a sampler's single-sampled copy is made (D14 points 8 and 10): ``average``
    (QRhi's resolve) or ``nearest`` (the core's minimum over the samples; an ``r32f`` attachment past the first, e.g. a
    linear depth written beside the colour)."""

    name: str
    format: str = "rgba8"
    clear: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    resolve: str = "average"

    def __post_init__(self) -> None:
        if self.format not in TARGET_FORMATS:
            raise ValueError(f"unknown format {self.format!r} (the formats are {', '.join(TARGET_FORMATS)})")
        if len(self.clear) != 4:
            raise ValueError("a clear value is four numbers")
        if self.resolve not in TARGET_RESOLVES:
            raise ValueError(f"unknown resolve {self.resolve!r} (the resolves are {', '.join(TARGET_RESOLVES)})")
        if self.resolve == "nearest" and self.format != "r32f":
            raise ValueError("a nearest resolve takes an r32f attachment")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"name": self.name, "format": self.format}
        if tuple(self.clear) != (0.0, 0.0, 0.0, 0.0):
            entry["clear"] = [float(v) for v in self.clear]
        if self.resolve != "average":
            entry["resolve"] = self.resolve
        return entry


@dataclass(frozen=True)
class ModeTarget:
    """N3.1 (D14): a scene target a program's passes draw into: its name, its size (None: the surface's device pixels;
    else explicit pixels, changed later with :meth:`NativeMode.target_size`), its colour attachments, whether it has a
    depth (one D32F texture) and its requested samples (``rendering.gl_programs.scene3d.scene_samples``).
    ``previous_frame``: a pass may sample it before any pass of the frame drew it, reading the frame before
    (single-sampled only; the core refuses such a read otherwise, audit 2 M4)."""

    name: str
    colour: tuple[TargetAttachment, ...]
    size: tuple[int, int] | None = None
    depth: bool = False
    samples: int = 1
    previous_frame: bool = False
    #: N3.4 (D17 point 6): a mipped target (the defocus layer): single-sampled, surface-sized, without depth; its mips
    #: are QRhi's generateMips when a :class:`DefocusStep` reads it (D17 choice G: this layer only).
    mips: bool = False

    def __post_init__(self) -> None:
        if not 1 <= len(self.colour) <= MAX_TARGET_COLOUR:
            raise ValueError(f"a target has 1 to {MAX_TARGET_COLOUR} colour attachments")
        if not 1 <= int(self.samples) <= MAX_TARGET_SAMPLES:
            raise ValueError(f"a target requests 1 to {MAX_TARGET_SAMPLES} samples")
        if self.mips and (int(self.samples) != 1 or self.size is not None or self.depth or self.previous_frame):
            raise ValueError("a mipped target is single-sampled, surface-sized, without depth or previous_frame")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"name": self.name,
                                 "size": "surface" if self.size is None else [int(self.size[0]), int(self.size[1])],
                                 "colour": [a.declaration() for a in self.colour]}
        if self.depth:
            entry["depth"] = True
        if int(self.samples) != 1:
            entry["samples"] = int(self.samples)
        if self.previous_frame:
            entry["previous_frame"] = True
        if self.mips:
            entry["mips"] = True
        return entry


@dataclass(frozen=True)
class TransparencyTarget:
    """N3.4 (D17 point 2): a transparency target of the scene target ``of`` (declared before it, surface-sized, with
    depth): its own accumulation (``accum``, RGBA16F) and coverage (``coverage``, R16F: the revealage stored inverted,
    choice B), both cleared to 0, then the owner's attachments it ``borrow`` s (never the owner's colour 0), at the
    owner's size and samples, over the owner's depth (loaded, tested, never written). Its passes write
    ``SCENE_OIT_GLSL``'s outputs at locations 0 and 1 and a borrowed attachment at 2 on; the core fixes the first two
    blends. A :class:`TransparencyResolve` composites it onto the owner."""

    name: str
    of: str
    borrow: tuple[str, ...] = ()

    def declaration(self) -> dict:
        transparency: dict[str, Any] = {"of": self.of}
        if self.borrow:
            transparency["borrow"] = list(self.borrow)
        return {"name": self.name, "transparency": transparency}


#: N3.2 (D15): a pass's topology (points are refused: instanced quads, D5.6 row 11), cull, stream kinds, blend operations
#: and factors; the most batches a batched pass draws.
TOPOLOGIES = ("triangles", "triangle_strip")
CULL_MODES = ("none", "back", "front")
STREAM_KINDS = ("instance", "storage", "indirect")
BLEND_OPS = ("add", "subtract", "reverse_subtract", "min", "max")
BLEND_FACTORS = ("zero", "one", "src_color", "one_minus_src_color", "dst_color", "one_minus_dst_color", "src_alpha",
                 "one_minus_src_alpha", "dst_alpha", "one_minus_dst_alpha")
MAX_BATCHES = 64
#: The built-in mesh (the item quad's vertices as the Python host's VAO holds them; attribute ``aPosition``).
BUILTIN_QUAD_MESH = "quad"


@dataclass(frozen=True)
class BlendState:
    """N3.2: a full blend declaration, ``(op, src, dst)`` for the colour and the alpha (``BLEND_OPS``, ``BLEND_FACTORS``)."""

    color: tuple[str, str, str]
    alpha: tuple[str, str, str]

    def __post_init__(self) -> None:
        for op, src, dst in (self.color, self.alpha):
            if op not in BLEND_OPS or src not in BLEND_FACTORS or dst not in BLEND_FACTORS:
                raise ValueError(f"unknown blend ({op}, {src}, {dst})")

    def declaration(self) -> dict:
        return {"color": list(self.color), "alpha": list(self.alpha)}


def _blend_declaration(blend: "str | BlendState") -> Any:
    if isinstance(blend, BlendState):
        return blend.declaration()
    if blend not in PASS_BLENDS:
        raise ValueError(f"unknown blend {blend!r} (the blends are {', '.join(PASS_BLENDS)}, or a BlendState)")
    return blend


@dataclass(frozen=True)
class MeshAttribute:
    """N3.2: one attribute of interleaved f32 records: its name (the vertex input it fills), floats and byte offset."""

    name: str
    components: int
    offset: int

    def declaration(self) -> dict:
        return {"name": self.name, "components": int(self.components), "offset": int(self.offset)}


@dataclass(frozen=True)
class RecordLayout:
    """N3.2: the interleaved f32 records of a mesh's vertices, its instance stream, or an instance stream."""

    stride: int
    attributes: tuple[MeshAttribute, ...]

    def __post_init__(self) -> None:
        if int(self.stride) <= 0 or int(self.stride) % 4 or not self.attributes:
            raise ValueError("a layout has a positive stride (a multiple of 4) and attributes")
        for a in self.attributes:
            if not 1 <= int(a.components) <= 4 or int(a.offset) % 4 or int(a.offset) + 4 * int(a.components) > self.stride:
                raise ValueError(f"attribute {a.name!r} does not fit its {self.stride}-byte record")

    def declaration(self) -> dict:
        return {"stride": int(self.stride), "attributes": [a.declaration() for a in self.attributes]}


@dataclass(frozen=True)
class ModeStream:
    """N3.2 (D15 point 4): a record's array field bound by name as a stream: ``instance`` (f32 records of ``layout`` read
    per instance), ``storage`` (read in a buffer block) or ``indirect`` (u32 commands of four: vertices, instances,
    first vertex, 0). An f32 field names its ``used`` length: a u32 field counting the elements in use, under an
    ``at_most`` rule no larger than the field's count; only those bytes are written each record (the core refuses an
    f32 stream without one, and a u32 stream with one). Only a storage stream keeps the bytes past its used length
    from an earlier record; an instance stream is drawn exactly its used records (its pass's instance count is the
    used records, and any other count refuses the draw: checkpoint audit 4, H2)."""

    name: str
    field: str
    kind: str = "storage"
    layout: RecordLayout | None = None
    used: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in STREAM_KINDS:
            raise ValueError(f"unknown stream kind {self.kind!r} (the kinds are {', '.join(STREAM_KINDS)})")
        if (self.kind == "instance") != (self.layout is not None):
            raise ValueError("an instance stream has a layout; the others have none")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"name": self.name, "field": self.field, "kind": self.kind}
        if self.layout is not None:
            entry["layout"] = self.layout.declaration()
        if self.used is not None:
            entry["used"] = self.used
        return entry


@dataclass(frozen=True)
class PassGeometry:
    """N3.2 (D15 point 1): a pass's own vertex stage and geometry. Counts are a number or a name the record (a u32
    field) or the settings fill; ``vertices`` may be ``"mesh"`` (the mesh's), ``instances`` ``"mesh"`` (the instance
    source's; the default with one: an instance stream's used records this record). ``front_face`` is ``ccw``, ``cw`` or a name choosing per record (0 ccw, 1 cw). An
    indirect draw names an indirect stream and its ``draw_count``; a batched draw (D15 point 6) names the record's u32
    {first, count} pairs and its ``batch_count``, and may give a ``draw_parameters_pack`` (one multi-draw where the
    device reports the features; the plain ``vertex_pack`` draws one draw a batch with ``u_srpss_batch`` set)."""

    vertex_pack: bytes
    topology: str = "triangles"
    vertices: int | str | None = None
    instances: int | str | None = None
    first_vertex: int = 0
    mesh: str | None = None
    instance_from: str | None = None
    storage: tuple[tuple[str, str], ...] = ()          # (buffer block, storage stream)
    cull: str = "none"
    front_face: str = "ccw"
    indirect: str | None = None
    draw_count: int | str | None = None
    batches: str | None = None
    batch_count: str | None = None
    draw_parameters_pack: bytes = b""

    def __post_init__(self) -> None:
        if self.topology not in TOPOLOGIES:
            raise ValueError(f"unknown topology {self.topology!r} (the topologies are {', '.join(TOPOLOGIES)})")
        if self.cull not in CULL_MODES:
            raise ValueError(f"unknown cull {self.cull!r} (the modes are {', '.join(CULL_MODES)})")
        if (self.indirect is None) != (self.draw_count is None) or (self.batches is None) != (self.batch_count is None):
            raise ValueError("an indirect draw names its draw_count, a batched draw its batch_count")
        if self.draw_parameters_pack and self.batches is None:
            raise ValueError("a draw-parameters pack belongs to a batched draw")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"vertex": True, "topology": self.topology}
        for key, value in (("vertices", self.vertices), ("instances", self.instances), ("mesh", self.mesh),
                           ("instance_from", self.instance_from), ("indirect", self.indirect),
                           ("draw_count", self.draw_count), ("batches", self.batches),
                           ("batch_count", self.batch_count)):
            if value is not None:
                entry[key] = value
        if int(self.first_vertex):
            entry["first_vertex"] = int(self.first_vertex)
        if self.storage:
            entry["storage"] = [{"name": block, "stream": stream} for block, stream in self.storage]
        if self.cull != "none":
            entry["cull"] = self.cull
        if self.front_face != "ccw":
            entry["front_face"] = self.front_face
        return entry

    def packs(self) -> list[bytes]:
        """The packs after the fragment's: the vertex pack, and a batched draw's draw-parameters pack (empty: none)."""
        packs = [bytes(self.vertex_pack)]
        if self.batches is not None:
            packs.append(bytes(self.draw_parameters_pack))
        return packs


@dataclass(frozen=True)
class PassOutput:
    """N3.1: one attachment's write mask and blend in a pass on a scene target (None: the pass's blend)."""

    write: bool = True
    blend: "str | BlendState | None" = None

    def __post_init__(self) -> None:
        if self.blend is not None:
            _blend_declaration(self.blend)

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"write": bool(self.write)}
        if self.blend is not None:
            entry["blend"] = _blend_declaration(self.blend)
        return entry


@dataclass(frozen=True)
class ModePass:
    """One full-card pass: its name, its fragment pack (bytes of a ``.qsb``), its blend and its samplers. N3.1: the
    scene target it draws into (None: the card's surface), its attachments' masks and blends (empty: every attachment
    with ``blend``), and its depth test and write (on a target with depth)."""

    name: str
    pack: bytes
    blend: "str | BlendState" = "alpha"
    samplers: tuple[PassSampler, ...] = ()
    target: str | None = None
    outputs: tuple[PassOutput, ...] = ()
    depth_test: str | None = None
    depth_write: bool = False
    geometry: PassGeometry | None = None   # N3.2: its own vertex stage (None: the core's triangle)
    #: N3.4 (D17 choice D): a pass on a :class:`TransparencyTarget` ships its sorted pack, what a device the gate does not
    #: admit draws into the owner (premultiplied over); it binds what ``pack`` binds and writes the owner's attachments.
    sorted_pack: bytes | None = None

    def __post_init__(self) -> None:
        _blend_declaration(self.blend)
        if self.depth_test is not None and self.depth_test not in DEPTH_TESTS:
            raise ValueError(f"unknown depth test {self.depth_test!r} (the tests are {', '.join(DEPTH_TESTS)})")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"name": self.name, "blend": _blend_declaration(self.blend)}
        if self.geometry is not None:
            entry.update(self.geometry.declaration())
        if self.sorted_pack is not None:
            entry["sorted"] = True
        if self.samplers:
            entry["samplers"] = [s.declaration() for s in self.samplers]
        if self.target is not None:
            entry["target"] = self.target
        if self.outputs:
            entry["attachments"] = [o.declaration() for o in self.outputs]
            if self.sorted_pack is not None:
                # A transparent pass: the accumulation's and the coverage's blends are the core's (D17 point 2), so
                # their entries are {}; a borrowed attachment (location 2 on) keeps its declaration.
                entry["attachments"][:2] = [{} for _ in entry["attachments"][:2]]
        if self.depth_test is not None:
            entry["depth"] = {"test": self.depth_test, "write": bool(self.depth_write)}
        return entry


#: N3.3 (D16): a compute binding's access and resource kinds, a storage image's formats and dimensions.
STORAGE_ACCESS = ("read", "write", "read_write")
COMPUTE_RESOURCES = ("buffer", "image", "stream", "mesh")
STORAGE_IMAGE_FORMATS = ("rgba8", "rgba16f", "rgba32f", "r16f", "r32f")
MAX_STORAGE_BUFFERS = 8
MAX_STORAGE_IMAGES = 8
MAX_COMPUTE_BINDINGS = 8
#: The lost edge's prefix for storage a content made again found gone (``mode_content.h``).
_STATE_LOST = "state:"


@dataclass(frozen=True)
class StorageBuffer:
    """N3.3 (D16 point 2): a storage buffer the program's compute entries write and its draws read: its name, its bytes
    (a multiple of 4, or a setting's name: a record field never sizes it), and whether a draw also reads it per instance
    (``layout``: its records) or as indirect commands. Created zeroed; a size change keeps its prefix."""

    name: str
    bytes: int | str
    layout: RecordLayout | None = None
    indirect: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.bytes, int) and (self.bytes <= 0 or self.bytes % 4):
            raise ValueError("a storage buffer's bytes are a positive multiple of 4 (or a setting's name)")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"name": self.name, "bytes": self.bytes}
        usage = (["vertex"] if self.layout is not None else []) + (["indirect"] if self.indirect else [])
        if usage:
            entry["usage"] = usage
        if self.layout is not None:
            entry["layout"] = self.layout.declaration()
        return entry


@dataclass(frozen=True)
class StorageImage:
    """N3.3 (D16 point 2, choice L): a storage image: its name, its size ``(w, h)`` or ``(w, h, d)`` (a 3D image; changed
    later with :meth:`NativeMode.image_size`) and its format (``STORAGE_IMAGE_FORMATS``). Created zeroed."""

    name: str
    size: tuple[int, ...]
    format: str = "rgba16f"

    def __post_init__(self) -> None:
        if len(self.size) not in (2, 3) or min(int(v) for v in self.size) < 1:
            raise ValueError("a storage image's size is (w, h) or (w, h, d), each at least 1")
        if self.format not in STORAGE_IMAGE_FORMATS:
            raise ValueError(f"unknown format {self.format!r} (the formats are {', '.join(STORAGE_IMAGE_FORMATS)})")

    def declaration(self) -> dict:
        return {"name": self.name, "dimensions": len(self.size), "format": self.format,
                "size": [int(v) for v in self.size]}


@dataclass(frozen=True)
class ComputeBinding:
    """N3.3: one binding of a compute entry: the shader's buffer block or image (``name``) bound to a resource of
    ``kind`` (``COMPUTE_RESOURCES``: a storage buffer, a storage image, a storage stream or a mesh held with
    ``storage=True``, the last two read only), with its ``access`` (``STORAGE_ACCESS``), from which QRhi derives the
    barriers. The core refuses an access the shader's qualifiers contradict (a block it can write declared ``read``)."""

    name: str
    resource: str
    kind: str = "buffer"
    access: str = "read"

    def __post_init__(self) -> None:
        if self.kind not in COMPUTE_RESOURCES:
            raise ValueError(f"unknown resource kind {self.kind!r} (the kinds are {', '.join(COMPUTE_RESOURCES)})")
        if self.access not in STORAGE_ACCESS:
            raise ValueError(f"unknown access {self.access!r} (the accesses are {', '.join(STORAGE_ACCESS)})")
        if self.kind in ("stream", "mesh") and self.access != "read":
            raise ValueError("a stream or a mesh is read only")

    def declaration(self) -> dict:
        return {"name": self.name, self.kind: self.resource, "access": self.access}


@dataclass(frozen=True)
class ComputePass:
    """N3.3 (D16 point 1): a compute entry: its name, its compute pack (bytes of a ``.qsb``), its trigger (``"frame"``: a
    newly accepted record; or the name of a record u32 field: dispatched when it changes), its groups (three counts,
    each a number or a name the record (a u32 under an at_most rule) or the settings fill; or ``over``: a resource's
    extent over the pack's local size), its bindings and its samplers."""

    name: str
    pack: bytes
    bindings: tuple[ComputeBinding, ...] = ()
    groups: tuple[int | str, int | str, int | str] | None = None
    over: str | None = None
    trigger: str = "frame"
    samplers: tuple[PassSampler, ...] = ()

    def __post_init__(self) -> None:
        if (self.groups is None) == (self.over is None):
            raise ValueError("a compute entry's groups are three counts or `over` a resource, one of the two")
        if self.groups is not None and len(self.groups) != 3:
            raise ValueError("a compute entry's groups are three counts")
        if len(self.bindings) > MAX_COMPUTE_BINDINGS:
            raise ValueError(f"a compute entry binds at most {MAX_COMPUTE_BINDINGS} resources")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"name": self.name, "compute": True,
                                 "trigger": "frame" if self.trigger == "frame" else {"field": self.trigger},
                                 "groups": {"over": self.over} if self.over is not None else list(self.groups),
                                 "bindings": [b.declaration() for b in self.bindings]}
        if self.samplers:
            entry["samplers"] = [s.declaration() for s in self.samplers]
        return entry


@dataclass(frozen=True)
class CapturePass:
    """N3.1 (D14 point 5): a capture step of ``target``: what its passes drew so far, copied (colour, nearest window
    depth) into ``"<target>.capture_colour"`` and ``"<target>.capture_depth"``; the next pass on the target goes on
    drawing where it was. No fragment of its own."""

    name: str
    target: str

    def declaration(self) -> dict:
        return {"name": self.name, "capture": self.target}


#: N3.4 (D17 point 5): the composite step's forms (N5.2c: ``opaque``, the 3D transitions' scenes without bloom), and the
#: alpha a transparency resolve writes.
COMPOSITE_FORMS = ("overlay", "overlay_glow", "opaque_glow", "opaque")
#: The forms that add a bloom step's glow.
GLOW_FORMS = ("overlay_glow", "opaque_glow")
RESOLVE_ALPHAS = ("coverage", "keep")
#: N3.4: the bloom chain's levels (``post.py`` ``BLOOM_LEVELS``), and the most bloom and defocus steps a program takes.
BLOOM_LEVELS = 4
MAX_BLOOM_STEPS = 2
MAX_DEFOCUS_STEPS = 2


@dataclass(frozen=True)
class TransparencyResolve:
    """N3.4 (D17 point 2): the step compositing the :class:`TransparencyTarget` ``target`` onto its owner's colour 0,
    premultiplied, per sample when multisampled (choice C); ``alpha`` ``coverage`` adds the layer's coverage to the
    owner's alpha (an overlay's, Python's ONE), ``keep`` keeps it (ZERO). It follows every pass on the target."""

    name: str
    target: str
    alpha: str = "coverage"

    def __post_init__(self) -> None:
        if self.alpha not in RESOLVE_ALPHAS:
            raise ValueError(f"unknown resolve alpha {self.alpha!r} (they are {', '.join(RESOLVE_ALPHAS)})")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"name": self.name, "transparency_resolve": self.target}
        if self.alpha != "coverage":
            entry["alpha"] = self.alpha
        return entry


@dataclass(frozen=True)
class BloomStep:
    """N3.4 (D17 point 4): the bloom chain of ``source`` (``"<target>.<attachment>"``, its resolve when multisampled):
    ``BLOOM_LEVELS`` RGBA16F textures, one a level, the first downsample with the bright pass; its glow is read by a
    later sampler as ``"<name>.glow"`` (half the source's allocation, linear)."""

    name: str
    source: str

    def declaration(self) -> dict:
        return {"name": self.name, "bloom": self.source}


@dataclass(frozen=True)
class CompositeStep:
    """N3.4 (D17 point 5): the scene ``scene`` (``"<target>.<attachment>"``) onto the card's surface with the core's
    composite (``COMPOSITE_FORMS``): ``overlay`` (straight colour times the fade), ``overlay_glow`` (premultiplied, the
    glow at ``u_bloom_strength``, tone mapped at ``u_hdr_exposure`` when above 0, dithered where glow is added) or
    ``opaque_glow``. ``glow`` is a :class:`BloomStep`'s ``"<name>.glow"`` (the glow forms only). Its block's
    ``u_bloom_strength`` and ``u_hdr_exposure`` are settings or record fields, by the one rule. ABI 27: every form
    reads the core's ``u_scene_item`` (the item's cover in the surface) as Python's ``SceneTarget`` reads its own rect:
    its texel, glow and dither from the item's own pixel, nothing drawn outside the item; a :class:`BloomStep` from a
    surface-sized target pairs its first downsample's pixels from there too. ABI 29: ``scene_frame="window"`` says the
    mode's Python scene is drawn through Quick's window, unturned (its ``SceneTarget`` given the physical frame, the
    content turned at the vertex: the Oscilloscope); under a turned card the core then keeps the scene in the window's
    frame and the composite reads it at Python's texel (``u_scene_from_target``). Without it a turned card's bloom or
    composite is refused (Python's turned Scene3D frame, ``orient_visualizer_scene_frame``, is not built)."""

    name: str
    form: str
    scene: str
    glow: str | None = None
    scene_frame: str | None = None

    def __post_init__(self) -> None:
        if self.form not in COMPOSITE_FORMS:
            raise ValueError(f"unknown composite {self.form!r} (the forms are {', '.join(COMPOSITE_FORMS)})")
        if (self.glow is None) == (self.form in GLOW_FORMS):
            raise ValueError("the glow forms read a bloom step's glow; the overlay and the opaque form read none")
        if self.scene_frame not in (None, "window"):
            raise ValueError(f"unknown scene frame {self.scene_frame!r} (the window's, \"window\", or none)")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"name": self.name, "composite": self.form, "scene": self.scene}
        if self.glow is not None:
            entry["glow"] = self.glow
        if self.scene_frame is not None:
            entry["scene_frame"] = self.scene_frame
        return entry


@dataclass(frozen=True)
class DefocusStep:
    """N3.4 (D17 point 6): the defocus layer ``layer`` (a mipped target: premultiplied light, then the circle of
    confusion, both RGBA16F) spread onto the scene target ``onto``: its mips (QRhi's generateMips), the clip at the read
    level, the gather and the highlight sprites. Its block's ``u_defocus_radius``, ``u_defocus_highlight`` and
    ``u_defocus_level`` (``defocus.py`` ``_read_size``: the read level for the radius) are settings or record fields;
    the read level's texture and the sprite count are the core's."""

    name: str
    layer: str
    onto: str

    def declaration(self) -> dict:
        return {"name": self.name, "defocus": self.layer, "onto": self.onto}


#: N5.2c (N4.j): the most environment steps a program takes, and the most texels a side.
MAX_ENVIRONMENT_STEPS = 2
MAX_ENVIRONMENT_SIDE = 4096


@dataclass(frozen=True)
class EnvironmentStep:
    """N5.2c (N4.j's ``PhotoEnvironment``, ``rendering/quick/scene3d/environment.py``): the item texture ``source``
    box-filtered into an RGBA8 copy of ``size`` with a full mip chain (the core's ``shaders/environment.frag``, Python's
    16-tap ``_COPY_FRAGMENT``; mips by ``generateMips``, Python's ``glGenerateTextureMipmap``), drawn once per photo; a
    later sampler reads ``"<name>.environment"`` with mips. ``size`` is ``environment_size``'s (its one owner)."""

    name: str
    source: str
    size: tuple[int, int]

    def __post_init__(self) -> None:
        if len(self.size) != 2 or not all(1 <= int(v) <= MAX_ENVIRONMENT_SIDE for v in self.size):
            raise ValueError(f"an environment's size is (w, h), each 1 to {MAX_ENVIRONMENT_SIDE}")

    def declaration(self) -> dict:
        return {"name": self.name, "environment": self.source, "size": [int(self.size[0]), int(self.size[1])]}


_STEPS = (CapturePass, TransparencyResolve, BloomStep, CompositeStep, DefocusStep, EnvironmentStep)


def program_json(passes: Sequence[Any], targets: Sequence[ModeTarget | TransparencyTarget] = (),
                 streams: Sequence[ModeStream] = (), buffers: Sequence[StorageBuffer] = (),
                 images: Sequence[StorageImage] = (), *, unread: Sequence[str] = ()) -> tuple[str, list[bytes]]:
    """The program's declaration and its packs, in pass order (a pass with samplers declares them; one without has no
    ``samplers`` key, N2.9's declaration as it was; N3.1: ``targets`` when there are any, a capture's pack empty; N3.2:
    ``streams`` when there are any, and after a geometry pass's fragment pack its vertex pack, then a batched one's
    draw-parameters pack; N3.3: ``buffers`` and ``images`` when there are any, a compute entry's pack its compute
    shader; N3.4: a stage step's pack empty (its shaders are the core's), and a transparent pass's sorted pack last;
    ABI 26: ``unread`` when there are any, the record's fields the program reads nowhere: a stage it leaves out reads
    them, as the Oscilloscope's Glow 0 program leaves the bloom strength)."""
    declared = [p.declaration() for p in passes]
    program: dict[str, Any] = {"passes": declared}
    if unread:
        program["unread"] = [str(name) for name in unread]
    if targets:
        program["targets"] = [t.declaration() for t in targets]
    if streams:
        program["streams"] = [s.declaration() for s in streams]
    if buffers:
        program["buffers"] = [b.declaration() for b in buffers]
    if images:
        program["images"] = [i.declaration() for i in images]
    packs: list[bytes] = []
    for p in passes:
        packs.append(b"" if isinstance(p, _STEPS) else bytes(p.pack))
        if isinstance(p, ModePass) and p.geometry is not None:
            packs.extend(p.geometry.packs())
        if isinstance(p, ModePass) and p.sorted_pack is not None:
            packs.append(bytes(p.sorted_pack))
    return json.dumps(program), packs


def _settings(values: Mapping[str, Any]) -> str:
    from rendering.native.program_values import settings_json

    return settings_json(values)


def _card(card: Mapping[str, Any]) -> str:
    missing = [key for key in MODE_CARD_KEYS if key not in card and key not in MODE_CARD_OPTIONAL_KEYS]
    if missing:
        raise ValueError(f"the mode's card misses {', '.join(missing)}")
    return json.dumps({key: card[key] for key in MODE_CARD_KEYS if key in card})


class NativeMode:
    """A generic mode on one composite item (``NativeCore.mode``): bound to a stream with its schema, given its
    program, settings and card, destroyed with its composite. Every call is the GUI thread's and returns at once."""

    def __init__(self, module: ModuleType, composite: CompositeItem) -> None:
        self._module = module
        self.composite = composite
        # The core's one lost edge carries textures' names and (N3.3) "state:<resource>" names: split here.
        self._textures_lost: Callable[[list[str]], None] | None = None
        self._state_lost: Callable[[list[str]], None] | None = None

    def _lost(self, names: list[str]) -> None:
        state = [name[len(_STATE_LOST):] for name in names if name.startswith(_STATE_LOST)]
        textures = [name for name in names if not name.startswith(_STATE_LOST)]
        if textures and self._textures_lost is not None:
            self._textures_lost(textures)
        if state and self._state_lost is not None:
            self._state_lost(state)

    def _listen(self) -> None:
        listening = self._textures_lost is not None or self._state_lost is not None
        self._module.composite_mode_on_lost(self._handle(), self._lost if listening else None)

    def _handle(self) -> int:
        return self.composite._live()

    def bind(self, mapping_name: str, schema: Any, *, expect: Mapping[str, int] | None = None,
             controls: tuple[str, ...] = ()) -> None:
        """Draw from this frame stream, read by ``schema`` (a ``NativeSchema``, or its table entry); refused
        (ValueError) for a schema the core does not admit or one the program cannot draw."""
        table = schema if isinstance(schema, Mapping) else schema_table_entry(schema)
        self._module.composite_mode_bind(self._handle(), str(mapping_name), json.dumps(dict(table)),
                                         reader_config(expect, tuple(controls)))

    def unbind(self) -> None:
        self._module.composite_mode_unbind(self._handle())

    def still(self, still: bool = True) -> None:
        """N5.7a: the item draws as a still, with no stream (``mode_content.h``, "Stills"): its textures, settings and
        card are its frame, and it records only when what it draws changed (a new image handed to its upload job keeps
        the frame until the commit). Refused (ValueError) while a stream is bound, or when the program cannot be drawn
        without a record (a member the core and the settings do not fill)."""
        self._module.composite_mode_still(self._handle(), bool(still))

    def retire(self) -> None:
        """The stream retires (D1); the owner's lost-texture listener goes with it (audit N38 L4)."""
        self._module.composite_mode_retire(self._handle())

    def program(self, passes: Sequence[ModePass | CapturePass | ComputePass], settings: Mapping[str, Any] | None = None,
                *, targets: Sequence[ModeTarget] = (), streams: Sequence[ModeStream] = (),
                buffers: Sequence[StorageBuffer] = (), images: Sequence[StorageImage] = (),
                unread: Sequence[str] = ()) -> None:
        """The passes (N3.1: and the scene targets they draw into; N3.2: and the streams they read; N3.3: and the
        storage buffers and images its compute entries write; ABI 26: and the record's fields it reads nowhere,
        ``unread``); ``settings`` with them (a shader that adds a member comes with its value), else the ones given
        before. Refused (ValueError), the drawn program kept, when they do not fit."""
        declared, packs = program_json(passes, targets, streams, buffers, images, unread=unread)
        if settings is None:
            self._module.composite_mode_program(self._handle(), declared, packs)
        else:
            self._module.composite_mode_program(self._handle(), declared, packs, _settings(settings))

    def settings(self, values: Mapping[str, Any]) -> None:
        """The settings by name; unchanged settings record nothing."""
        self._module.composite_mode_settings(self._handle(), _settings(values))

    def card(self, card: Mapping[str, Any]) -> None:
        """The item as shown (``MODE_CARD_KEYS``; :func:`mode_card`); an unchanged card records nothing."""
        self._module.composite_mode_card(self._handle(), _card(card))

    def texture(self, name: str, pixels: bytes, size: tuple[int, int], *, mips: bool = False,
                in_frame: bool = False) -> None:
        """The item's texture ``name`` (N4.a): ``pixels`` RGBA8, rows top first, tight, of ``size`` (width, height);
        copied once into the core and uploaded from the next record; ``mips``: generated on the GPU. On a Vulkan device
        with a job service the upload is a job (N3.8, D9): the item draws the textures it held until the job is
        published, then every changed texture of the item at once. ``in_frame`` is the harness control of D9's in-frame
        form (the measurement both ways). Refused (ValueError) for a bad name, size or byte count, too many textures, or
        mips a sampler reads that it lacks."""
        if in_frame:
            self._module.composite_mode_texture(self._handle(), str(name), (int(size[0]), int(size[1])),
                                                bytes(pixels), bool(mips), True)
        else:
            self._module.composite_mode_texture(self._handle(), str(name), (int(size[0]), int(size[1])),
                                                bytes(pixels), bool(mips))

    def on_textures_lost(self, callback: Callable[[list[str]], None] | None) -> None:
        """The owner's lost-texture edge (N3.8, N4.a's leftover): ``callback`` is called on the GUI thread with the
        names of textures found lost (a node made again, a texture that could not be created), once per loss; the
        owner sends them again. None removes it."""
        self._textures_lost = callback
        self._listen()

    def on_state_lost(self, callback: Callable[[list[str]], None] | None) -> None:
        """N3.3 (D16 choice I): the owner's lost-state edge: ``callback`` is called on the GUI thread, once, with the
        storage buffers and images a content made again found gone (they are made zeroed and the compute entries
        dispatch fresh: a history restarts as at its first frame). None removes it."""
        self._state_lost = callback
        self._listen()

    def image_size(self, name: str, size: tuple[int, ...]) -> None:
        """N3.3: a storage image's size ``(w, h)`` or ``(w, h, d)`` with no new program (Waveform's fog grid follows its
        surface); the image is made again, zeroed, at the next record. ValueError for an image the program does not
        declare or a size outside its bounds."""
        self._module.composite_mode_image_size(self._handle(), str(name), tuple(int(v) for v in size))

    def read_storage(self) -> None:
        """N3.3, harness only: every storage buffer and image read back at the next record (which dispatches nothing)."""
        self._module.composite_mode_storage_read(self._handle())

    def storage_data(self) -> list[dict] | None:
        """N3.3, harness only: the last storage readback once complete (None before), each ``{"name", "kind", "format",
        "size", "data"}``: a buffer's bytes, or an image's texels as stored (rows top first, slices in order)."""
        return self._module.composite_mode_storage_data(self._handle())

    def remove_texture(self, name: str) -> None:
        """The texture goes; the render thread releases it at the next record (KeyError: no such texture)."""
        self._module.composite_mode_texture_remove(self._handle(), str(name))

    def mesh(self, name: str, vertices: bytes, layout: RecordLayout, *, instances: bytes | None = None,
             instance_layout: RecordLayout | None = None, storage: bool = False) -> None:
        """N3.2 (D15 point 2): the item's mesh ``name``: interleaved f32 ``vertices`` of ``layout`` and optionally an
        instance stream; copied once into the core and uploaded once at the next record, never again at rest. Refused
        (ValueError) for a bad name (or ``quad``, the built-in), layout or byte count, or too many meshes. N3.3:
        ``storage`` also lets a compute entry read the vertices (D3's geometry, once per revision)."""
        declaration: dict[str, Any] = {"vertices": layout.declaration()}
        if (instances is None) != (instance_layout is None):
            raise ValueError("a mesh's instance stream comes with its layout")
        if instance_layout is not None:
            declaration["instances"] = instance_layout.declaration()
        if storage:
            declaration["storage"] = True
        self._module.composite_mode_mesh(self._handle(), str(name), json.dumps(declaration), bytes(vertices),
                                         None if instances is None else bytes(instances))

    def remove_mesh(self, name: str) -> None:
        """N3.2: the mesh goes; the render thread releases it at the next record (KeyError: no such mesh)."""
        self._module.composite_mode_mesh_remove(self._handle(), str(name))

    def target_size(self, name: str, size: tuple[int, int]) -> None:
        """N3.1: an explicit-size scene target's size (Bubble's ambient target follows its card) with no new program;
        the core's allocation follows at the next record, until the next :meth:`program`, whose declarations size its
        targets again (``state()["target_sizes"]`` holds the sizes set since the program). ValueError for a target the
        program does not declare with an explicit size."""
        self._module.composite_mode_target_size(self._handle(), str(name), (int(size[0]), int(size[1])))

    def read_targets(self) -> None:
        """N3.1, harness: a readback of every scene target's readable texture at the next record."""
        self._module.composite_mode_target_read(self._handle())

    def target_pixels(self) -> list[dict] | None:
        """N3.1, harness: the last readback once complete (None before), each ``{"name", "size", "content", "format",
        "samples", "level", "data"}``, rows top first on every backend; the content sits at rows ``[H-h, H)``, columns
        ``[0, w)``. At nonzero mip levels, ``content`` is the base normalized rectangle projected into that level,
        rounded outward to texels. It describes nominal coverage; filtering may blend beyond that rectangle."""
        return self._module.composite_mode_target_pixels(self._handle())

    def update(self) -> None:
        self._module.composite_update(self._handle())

    def drop_retained_frame(self) -> None:
        self._module.composite_mode_drop(self._handle())

    def head(self) -> dict | None:
        return self._module.composite_mode_head(self._handle())

    def state(self) -> dict:
        return json.loads(self._module.composite_mode_state(self._handle()))


def mode_blocks(module: ModuleType, schema: Any, passes: Sequence[ModePass], settings: Mapping[str, Any],
                record: bytes, card: Mapping[str, Any] | None, target: tuple[int, int], *,
                streams: Sequence[ModeStream] = (),
                correction: Sequence[float] | None = None) -> tuple[list[bytes], dict]:
    """Each pass's block bytes the core uploads for ``record`` under ``card`` into a ``target`` of these pixels
    (GPU-free), and the facts (each pass's members by source, the program's reflected blocks, the schema as the core
    holds it). ValueError with the reason when refused. N3.2: the program's ``streams``, and ``correction`` (16 floats,
    column-major): a target's clip correction of a vertex stage's ``uMatrix`` (None: none)."""
    table = schema if isinstance(schema, Mapping) else schema_table_entry(schema)
    declared, packs = program_json(passes, (), streams)
    arguments = [json.dumps(dict(table)), declared, packs, _settings(settings), bytes(record),
                 None if card is None else _card(card), (int(target[0]), int(target[1]))]
    if correction is not None:
        arguments.append([float(v) for v in correction])
    blocks, facts = module.mode_blocks(*arguments)
    return [bytes(block) for block in blocks], json.loads(facts)


__all__ = ["BLEND_FACTORS", "BLEND_OPS", "BUILTIN_QUAD_MESH", "BlendState", "COMPUTE_RESOURCES", "CULL_MODES",
           "CapturePass", "ComputeBinding", "ComputePass", "DEPTH_TESTS", "EnvironmentStep", "GLOW_FORMS",
           "MAX_ENVIRONMENT_SIDE", "MAX_ENVIRONMENT_STEPS", "MAX_COMPUTE_BINDINGS", "MAX_STORAGE_BUFFERS",
           "MAX_STORAGE_IMAGES", "STORAGE_ACCESS", "STORAGE_IMAGE_FORMATS", "StorageBuffer", "StorageImage",
           "MAX_BATCHES", "MAX_TARGETS", "MAX_TARGET_COLOUR", "MAX_TARGET_SAMPLES", "MODE_CARD_KEYS", "MODE_CORE_MEMBERS",
           "MeshAttribute", "ModePass", "ModeStream", "ModeTarget", "NativeMode", "PASS_BLENDS", "PassGeometry",
           "PassOutput", "PassSampler", "RecordLayout", "STREAM_KINDS", "TOPOLOGIES",
           "SAMPLER_FILTERS", "SAMPLER_MIPS", "SAMPLER_WRAPS", "TARGET_FORMATS", "TARGET_RESOLVES", "TargetAttachment", "mode_blocks",
           "mode_card", "program_json", "schema_table_entry"]
