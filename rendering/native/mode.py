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


@dataclass(frozen=True)
class PassOutput:
    """N3.1: one attachment's write mask and blend in a pass on a scene target (None: the pass's blend)."""

    write: bool = True
    blend: str | None = None

    def __post_init__(self) -> None:
        if self.blend is not None and self.blend not in PASS_BLENDS:
            raise ValueError(f"unknown blend {self.blend!r} (the blends are {', '.join(PASS_BLENDS)})")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"write": bool(self.write)}
        if self.blend is not None:
            entry["blend"] = self.blend
        return entry


@dataclass(frozen=True)
class ModePass:
    """One full-card pass: its name, its fragment pack (bytes of a ``.qsb``), its blend and its samplers. N3.1: the
    scene target it draws into (None: the card's surface), its attachments' masks and blends (empty: every attachment
    with ``blend``), and its depth test and write (on a target with depth)."""

    name: str
    pack: bytes
    blend: str = "alpha"
    samplers: tuple[PassSampler, ...] = ()
    target: str | None = None
    outputs: tuple[PassOutput, ...] = ()
    depth_test: str | None = None
    depth_write: bool = False

    def __post_init__(self) -> None:
        if self.blend not in PASS_BLENDS:
            raise ValueError(f"unknown blend {self.blend!r} (the blends are {', '.join(PASS_BLENDS)})")
        if self.depth_test is not None and self.depth_test not in DEPTH_TESTS:
            raise ValueError(f"unknown depth test {self.depth_test!r} (the tests are {', '.join(DEPTH_TESTS)})")

    def declaration(self) -> dict:
        entry: dict[str, Any] = {"name": self.name, "blend": self.blend}
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


def program_json(passes: Sequence[ModePass | CapturePass],
                 targets: Sequence[ModeTarget] = ()) -> tuple[str, list[bytes]]:
    """The program's declaration and its packs, in pass order (a pass with samplers declares them; one without has no
    ``samplers`` key, N2.9's declaration as it was; N3.1: ``targets`` when there are any, a capture's pack empty)."""
    declared = [p.declaration() for p in passes]
    program: dict[str, Any] = {"passes": declared}
    if targets:
        program["targets"] = [t.declaration() for t in targets]
    packs = [b"" if isinstance(p, CapturePass) else bytes(p.pack) for p in passes]
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
                targets: Sequence[ModeTarget] = ()) -> None:
        """The passes (N3.1: and the scene targets they draw into); ``settings`` with them (a shader that adds a member
        comes with its value), else the ones given before. Refused (ValueError), the drawn program kept, when they do
        not fit."""
        declared, packs = program_json(passes, targets)
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


__all__ = ["CapturePass", "DEPTH_TESTS", "MAX_TARGETS", "MAX_TARGET_COLOUR", "MAX_TARGET_SAMPLES", "MODE_CARD_KEYS",
           "MODE_CORE_MEMBERS", "ModePass", "ModeTarget", "NativeMode", "PASS_BLENDS", "PassOutput", "PassSampler",
           "SAMPLER_FILTERS", "SAMPLER_MIPS", "SAMPLER_WRAPS", "TARGET_FORMATS", "TARGET_RESOLVES", "TargetAttachment", "mode_blocks",
           "mode_card", "program_json", "schema_table_entry"]
