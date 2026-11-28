"""Extruded Bubble's item placement for the native-only player (``tools/visualizer_replay/native_stream_player.py``,
rule (b), N5.6 "P, T and C"): the generic modes' harness (``devcurve_check.py``) with Extruded Bubble's record schema,
slot, program and geometry arena.

The route programs Extruded Bubble by its variant (``extruded_bubble_program.program``: the scene's samples), then sends
each explicit target size (``native_route._program``'s variant path); the player hands the item the same, from the
delivery stream (``native_record_identity.DeliveryStream`` format 2: the variant, the settings, the target sizes).

The drift geometry lives in the stream's arena (D3), not the record: ``Arena`` is the player's arena, opened with the
recorded layout under the in-process label namespace (0, as ``owner_render_parity.in_process_drift_arena`` opens it),
its writer stamped with the recorded key namespace, and each input's recorded writes made before its record is
published, as the worker writes them before the slot names them. The item is told the arena's name after its bind
(the route's ``DriftStream._tell``; the player projects nothing).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import pixel_tolerance as pt  # noqa: E402


def _generic_rounds():
    """The generic modes' harness as a module of this harness's own (``bubble_check``'s reason)."""
    spec = importlib.util.spec_from_file_location("_eb_stream_check_rounds", HERE / "devcurve_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _generic_rounds()

MODE_ID = "extruded_bubble"
#: Rule (b) before its measurement: one level outside the translucent mask, nothing else admitted. The bound is
#: measured on the acceptance takes (the guide's rule) and set here with its figures.
VULKAN_RULE_B = pt.Tolerance("extruded bubble, Vulkan against OpenGL (rule b)", masked_level=1)


def _schema():
    from core.visualizer_engine import extruded_bubble_native_schema

    return extruded_bubble_native_schema.SCHEMA


def _slot_bytes() -> int:
    from rendering.quick.visualizer.native_route import _slot_bytes

    return _slot_bytes(MODE_ID)


def program_item(mode, entry: dict, dpr: float, first: bool) -> None:
    """The route's order: the variant's program with the first settings, then each target's size; afterwards the
    settings and the sizes."""
    from rendering.native import extruded_bubble_program as ebp

    settings = base.settings_at(entry, dpr)
    if first:
        built = ebp.program(tuple(entry["variant"]))
        extra = {key: built[key] for key in ("unread", "images", "buffers") if built.get(key)}
        mode.program(built["passes"], settings, targets=built["targets"], streams=built["streams"], **extra)
    else:
        mode.settings(settings)
    for name, size in (entry.get("sizes") or {}).items():
        mode.target_size(name, tuple(int(v) for v in size))


class Arena:
    """The player's geometry arena: the recorded layout, the recorded writer namespace, the recorded writes."""

    def __init__(self, layout: dict, geometry: Path) -> None:
        from core.visualizer_engine import extruded_bubble_native_schema as schema
        from core.visualizer_engine import geometry_arena as ga

        self._schema = schema
        self.owner = schema.open_stream_arena(0, int(layout["bank_bytes"]))
        if self.owner.bank_bytes != int(layout["bank_bytes"]) or self.owner.families < len(layout["families"]):
            self.close()
            raise ValueError(f"the player's arena ({self.owner.families} families, {self.owner.bank_bytes} bytes a "
                             f"bank) is not the recorded layout {layout}")
        self.writer = ga.GeometryArenaWriter(self.owner.name, families=list(layout["families"]))
        self.writer.namespace = int(layout["namespace"])
        ga._WRITER_NAMESPACE.pack_into(self.writer._memory.buf, ga._WRITER_NAMESPACE_AT, self.writer.namespace)
        self._geometry = Path(geometry).open("rb")
        self.writes = 0

    @property
    def name(self) -> str:
        return self.owner.name

    def apply(self, writes: list) -> None:
        """One input's recorded writes (``[family, bank, key words, offset, size]``), in their order."""
        for family, bank, key, offset, size in writes:
            self._geometry.seek(int(offset))
            payload = self._geometry.read(int(size))
            if len(payload) != int(size) or not self.writer._write(int(family), int(bank), tuple(key), payload):
                raise ValueError(f"the recorded write of family {family} bank {bank} could not be made")
            self.writes += 1

    def close(self) -> None:
        geometry = getattr(self, "_geometry", None)
        if geometry is not None:
            geometry.close()
        writer = getattr(self, "writer", None)
        if writer is not None:
            writer.close()
        self._schema.close_stream_arena(self.owner)


base.use_mode(MODE_ID=MODE_ID, _schema=_schema, program_item=program_item, VULKAN_RULE_B=VULKAN_RULE_B)
