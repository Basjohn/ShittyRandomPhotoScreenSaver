"""A generic mode's Python face (Current_Plan.md item 8b, N2.9; ``native/core/src/mode_content.h``).

A Visualizer mode drawn by the native core from data alone, so a new mode iterates with no module build:

- its **simulation** runs in Python (the engine worker in the product), publishing one fixed-layout frame record per
  frame through the frame mapping (``core.visualizer_engine.packet_abi``);
- its **schema** is the record's table (``core.visualizer_engine.native_schema.NativeSchema``), handed to the core when
  the stream is bound (:func:`schema_table_entry`): the core's reader admits the mode's slots by it, and the frame block
  is packed from it by name;
- its **program** is one or more passes (:class:`ModePass`): a fragment pack each (baked by ``tools/regen_qrc.py``'s
  baker, handed over as bytes) and a blend (``PASS_BLENDS``), drawn in order over the whole card;
- its **settings** are every Settings- and card-derived value, resolved here from the spec and handed over by name.

Each pass declares two std140 blocks: ``ModeSettings`` (the settings) and ``ModeFrame`` (members named exactly as the
record's fields). The core refuses an unknown name (a setting no pass declares, a record field no pass's ModeFrame
declares) and an unfilled member (a ModeSettings member no setting fills, a ModeFrame member no field names), each with
its reason. A shader, spec or simulation change is a new pack, new settings or a new record: never C++.
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
#: The two blocks a pass may declare beside the conventions block.
MODE_SETTINGS_BLOCK = "ModeSettings"
MODE_FRAME_BLOCK = "ModeFrame"


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


class NativeMode:
    """A generic mode on one composite item (``NativeCore.mode``): bound to a stream with its schema, given its program
    and settings, destroyed with its composite. Every call is the GUI thread's and returns at once."""

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
        """The passes; ``settings`` with them (a shader that adds a ModeSettings member comes with its value), else the
        ones given before. Refused (ValueError), the drawn program kept, when they do not fit."""
        declared, packs = program_json(passes)
        if settings is None:
            self._module.composite_mode_program(self._handle(), declared, packs)
        else:
            self._module.composite_mode_program(self._handle(), declared, packs, _settings(settings))

    def settings(self, values: Mapping[str, Any]) -> None:
        """The ModeSettings members by name; unchanged settings record nothing."""
        self._module.composite_mode_settings(self._handle(), _settings(values))

    def update(self) -> None:
        self._module.composite_update(self._handle())

    def drop_retained_frame(self) -> None:
        self._module.composite_mode_drop(self._handle())

    def head(self) -> dict | None:
        return self._module.composite_mode_head(self._handle())

    def state(self) -> dict:
        return json.loads(self._module.composite_mode_state(self._handle()))


def mode_blocks(module: ModuleType, schema: Any, passes: Sequence[ModePass], settings: Mapping[str, Any],
                record: bytes) -> tuple[list[tuple[bytes, bytes]], dict]:
    """Each pass's (ModeSettings, ModeFrame) bytes the core uploads for ``record`` (GPU-free), and the facts (the
    program's reflected blocks, the schema as the core holds it). ValueError with the reason when refused."""
    table = schema if isinstance(schema, Mapping) else schema_table_entry(schema)
    declared, packs = program_json(passes)
    blocks, facts = module.mode_blocks(json.dumps(dict(table)), declared, packs, _settings(settings), bytes(record))
    return [(bytes(s), bytes(f)) for s, f in blocks], json.loads(facts)


__all__ = ["MODE_FRAME_BLOCK", "MODE_SETTINGS_BLOCK", "ModePass", "NativeMode", "PASS_BLENDS", "mode_blocks",
           "program_json", "schema_table_entry"]
