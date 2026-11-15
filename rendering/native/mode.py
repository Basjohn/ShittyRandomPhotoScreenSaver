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
    "uOriented": (2, True),
    "uQuarters": (1, True),
    "u_srpss_batch": (1, False),   # N3.2 (D15 point 6): a batched pass's batch
}
#: The card's keys (``ModeCard::fromJson``).
MODE_CARD_KEYS = ("quarters", "item_size", "oriented_size", "dpr", "content_fade", "border_width", "window_from_target",
                  "item_from_window")


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

    card = spectrum_presentation(presentation, geometry, window_size=window_size, window_pixels=window_pixels)
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

    def __post_init__(self) -> None:
        if not 1 <= len(self.colour) <= MAX_TARGET_COLOUR:
            raise ValueError(f"a target has 1 to {MAX_TARGET_COLOUR} colour attachments")
        if not 1 <= int(self.samples) <= MAX_TARGET_SAMPLES:
            raise ValueError(f"a target requests 1 to {MAX_TARGET_SAMPLES} samples")

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
        return entry


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
    first vertex, 0)."""

    name: str
    field: str
    kind: str = "storage"
    layout: RecordLayout | None = None

    def __post_init__(self) -> None:
        if self.kind not in STREAM_KINDS:
            raise ValueError(f"unknown stream kind {self.kind!r} (the kinds are {', '.join(STREAM_KINDS)})")
        if (self.kind == "instance") != (self.layout is not None):
            raise ValueError("an instance stream has a layout; the others have none")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"name": self.name, "field": self.field, "kind": self.kind}
        if self.layout is not None:
            entry["layout"] = self.layout.declaration()
        return entry


@dataclass(frozen=True)
class PassGeometry:
    """N3.2 (D15 point 1): a pass's own vertex stage and geometry. Counts are a number or a name the record (a u32
    field) or the settings fill; ``vertices`` may be ``"mesh"`` (the mesh's), ``instances`` ``"mesh"`` (the instance
    source's; the default with one). ``front_face`` is ``ccw``, ``cw`` or a name choosing per record (0 ccw, 1 cw). An
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

    def __post_init__(self) -> None:
        _blend_declaration(self.blend)
        if self.depth_test is not None and self.depth_test not in DEPTH_TESTS:
            raise ValueError(f"unknown depth test {self.depth_test!r} (the tests are {', '.join(DEPTH_TESTS)})")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"name": self.name, "blend": _blend_declaration(self.blend)}
        if self.geometry is not None:
            entry.update(self.geometry.declaration())
        if self.samplers:
            entry["samplers"] = [s.declaration() for s in self.samplers]
        if self.target is not None:
            entry["target"] = self.target
        if self.outputs:
            entry["attachments"] = [o.declaration() for o in self.outputs]
        if self.depth_test is not None:
            entry["depth"] = {"test": self.depth_test, "write": bool(self.depth_write)}
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


def program_json(passes: Sequence[ModePass | CapturePass], targets: Sequence[ModeTarget] = (),
                 streams: Sequence[ModeStream] = ()) -> tuple[str, list[bytes]]:
    """The program's declaration and its packs, in pass order (a pass with samplers declares them; one without has no
    ``samplers`` key, N2.9's declaration as it was; N3.1: ``targets`` when there are any, a capture's pack empty; N3.2:
    ``streams`` when there are any, and after a geometry pass's fragment pack its vertex pack, then a batched one's
    draw-parameters pack)."""
    declared = [p.declaration() for p in passes]
    program: dict[str, Any] = {"passes": declared}
    if targets:
        program["targets"] = [t.declaration() for t in targets]
    if streams:
        program["streams"] = [s.declaration() for s in streams]
    packs: list[bytes] = []
    for p in passes:
        packs.append(b"" if isinstance(p, CapturePass) else bytes(p.pack))
        if isinstance(p, ModePass) and p.geometry is not None:
            packs.extend(p.geometry.packs())
    return json.dumps(program), packs


def _settings(values: Mapping[str, Any]) -> str:
    from rendering.native.program_values import settings_json

    return settings_json(values)


def _card(card: Mapping[str, Any]) -> str:
    missing = [key for key in MODE_CARD_KEYS if key not in card]
    if missing:
        raise ValueError(f"the mode's card misses {', '.join(missing)}")
    return json.dumps({key: card[key] for key in MODE_CARD_KEYS})


class NativeMode:
    """A generic mode on one composite item (``NativeCore.mode``): bound to a stream with its schema, given its
    program, settings and card, destroyed with its composite. Every call is the GUI thread's and returns at once."""

    def __init__(self, module: ModuleType, composite: CompositeItem) -> None:
        self._module = module
        self.composite = composite

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

    def program(self, passes: Sequence[ModePass | CapturePass], settings: Mapping[str, Any] | None = None, *,
                targets: Sequence[ModeTarget] = (), streams: Sequence[ModeStream] = ()) -> None:
        """The passes (N3.1: and the scene targets they draw into; N3.2: and the streams they read); ``settings`` with
        them (a shader that adds a member comes with its value), else the ones given before. Refused (ValueError), the
        drawn program kept, when they do not fit."""
        declared, packs = program_json(passes, targets, streams)
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
        self._module.composite_mode_on_lost(self._handle(), callback)

    def remove_texture(self, name: str) -> None:
        """The texture goes; the render thread releases it at the next record (KeyError: no such texture)."""
        self._module.composite_mode_texture_remove(self._handle(), str(name))

    def mesh(self, name: str, vertices: bytes, layout: RecordLayout, *, instances: bytes | None = None,
             instance_layout: RecordLayout | None = None) -> None:
        """N3.2 (D15 point 2): the item's mesh ``name``: interleaved f32 ``vertices`` of ``layout`` and optionally an
        instance stream; copied once into the core and uploaded once at the next record, never again at rest. Refused
        (ValueError) for a bad name (or ``quad``, the built-in), layout or byte count, or too many meshes."""
        declaration: dict[str, Any] = {"vertices": layout.declaration()}
        if (instances is None) != (instance_layout is None):
            raise ValueError("a mesh's instance stream comes with its layout")
        if instance_layout is not None:
            declaration["instances"] = instance_layout.declaration()
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
        "samples", "data"}``, rows top first on every backend; the content sits at rows ``[H-h, H)``, columns
        ``[0, w)``."""
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
                record: bytes, card: Mapping[str, Any] | None, target: tuple[int, int]) -> tuple[list[bytes], dict]:
    """Each pass's block bytes the core uploads for ``record`` under ``card`` into a ``target`` of these pixels
    (GPU-free), and the facts (each pass's members by source, the program's reflected blocks, the schema as the core
    holds it). ValueError with the reason when refused."""
    table = schema if isinstance(schema, Mapping) else schema_table_entry(schema)
    declared, packs = program_json(passes)
    blocks, facts = module.mode_blocks(json.dumps(dict(table)), declared, packs, _settings(settings), bytes(record),
                                       None if card is None else _card(card), (int(target[0]), int(target[1])))
    return [bytes(block) for block in blocks], json.loads(facts)


__all__ = ["BLEND_FACTORS", "BLEND_OPS", "BUILTIN_QUAD_MESH", "BlendState", "CULL_MODES", "CapturePass", "DEPTH_TESTS",
           "MAX_BATCHES", "MAX_TARGETS", "MAX_TARGET_COLOUR", "MAX_TARGET_SAMPLES", "MODE_CARD_KEYS", "MODE_CORE_MEMBERS",
           "MeshAttribute", "ModePass", "ModeStream", "ModeTarget", "NativeMode", "PASS_BLENDS", "PassGeometry",
           "PassOutput", "PassSampler", "RecordLayout", "STREAM_KINDS", "TOPOLOGIES",
           "SAMPLER_FILTERS", "SAMPLER_MIPS", "SAMPLER_WRAPS", "TARGET_FORMATS", "TARGET_RESOLVES", "TargetAttachment", "mode_blocks",
           "mode_card", "program_json", "schema_table_entry"]
