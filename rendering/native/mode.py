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

The product 2D shader's shape: a pass declares one std140 block of its own (any name, any binding but 17), optionally
the conventions block and ``in vec2 v_uv``. One rule fills the block by member name from exactly one of three sources:
the core's conventions (``MODE_CORE_MEMBERS``: what the Python renderers compute per frame from the card and the
target), the settings, and the record's fields. The core refuses an unknown name (a setting or a field no pass
declares), a name with two owners (a setting or field naming a core member, a setting naming a field) and an unfilled
member, each with its reason. A shader, spec or simulation change is a new pack, new settings or a new record: never C++.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Mapping, Sequence

from rendering.native.composite import CompositeItem
from rendering.native.packet_reader import reader_config

#: How a pass's colour meets the target (``PassBlend`` in ``mode_content.h``).
PASS_BLENDS = ("replace", "alpha", "premultiplied", "add")
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


@dataclass(frozen=True)
class ModePass:
    """One full-card pass: its name, its fragment pack (bytes of a ``.qsb``) and its blend."""

    name: str
    pack: bytes
    blend: str = "alpha"

    def __post_init__(self) -> None:
        if self.blend not in PASS_BLENDS:
            raise ValueError(f"unknown blend {self.blend!r} (the blends are {', '.join(PASS_BLENDS)})")


def program_json(passes: Sequence[ModePass]) -> tuple[str, list[bytes]]:
    """The program's declaration and its packs, in pass order."""
    declared = {"passes": [{"name": p.name, "blend": p.blend} for p in passes]}
    return json.dumps(declared), [bytes(p.pack) for p in passes]


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

    def retire(self) -> None:
        self._module.composite_mode_retire(self._handle())

    def program(self, passes: Sequence[ModePass], settings: Mapping[str, Any] | None = None) -> None:
        """The passes; ``settings`` with them (a shader that adds a member comes with its value), else the ones given
        before. Refused (ValueError), the drawn program kept, when they do not fit."""
        declared, packs = program_json(passes)
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


__all__ = ["MODE_CARD_KEYS", "MODE_CORE_MEMBERS", "ModePass", "NativeMode", "PASS_BLENDS", "mode_blocks", "mode_card",
           "program_json", "schema_table_entry"]
