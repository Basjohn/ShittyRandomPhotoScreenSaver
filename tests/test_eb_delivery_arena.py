"""The delivery stream's format 2 (N5.6 D3, Extruded Bubble's drift geometry): each arena write recorded with the input
whose frame made it, a window's first line holding every bank live then, and the native-only player's arena replaying
them under the recorded writer namespace so the record's keys are held."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from tools.visualizer_replay import native_record_identity as nri

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "native" / "core" / "python"
FAMILIES = ["shells", "clusters"]
BANK_BYTES = 256


def _lines(folder: Path) -> tuple[dict, list[dict]]:
    rows = [json.loads(line) for line in (folder / "deliveries.jsonl").read_text(encoding="utf-8").splitlines()]
    return rows[0], rows[1:]


def _layout() -> dict:
    return {"families": FAMILIES, "bank_bytes": BANK_BYTES, "namespace": 77}


def _record(folder: Path, keep=None, stream_class=nri.DeliveryStream):
    """Inputs 0..3: input 0 writes family 0 bank 0, input 2 family 1 bank 0, input 3 family 0 bank 1."""
    stream = stream_class(folder, "extruded_bubble", keep=keep, arena=_layout())
    writes = {0: [(0, 0, (77, 1, 1, 0, 5, 64), b"\x01" * 64)], 2: [(1, 0, (77, 1, 1, 1, 6, 32), b"\x02" * 32)],
              3: [(0, 1, (77, 1, 1, 0, 7, 64), b"\x03" * 64)]}
    for index in range(4):
        for write in writes.get(index, ()):
            stream.write(*write)
        stream.add(index, {"drawn": False})
    stream.close()
    return writes


def test_each_write_is_recorded_with_its_input(tmp_path):
    _record(tmp_path)
    header, lines = _lines(tmp_path)
    assert header["format"] == 2 and header["arena"] == _layout()
    assert [sorted(line) for line in lines] == [["drawn", "geometry", "input"], ["drawn", "input"],
                                                ["drawn", "geometry", "input"], ["drawn", "geometry", "input"]]
    data = (tmp_path / "geometry.bin").read_bytes()
    family, bank, key, offset, size = lines[2]["geometry"][0]
    assert (family, bank, key) == (1, 0, [77, 1, 1, 1, 6, 32]) and data[offset:offset + size] == b"\x02" * 32


def test_a_windows_first_line_holds_every_live_bank(tmp_path):
    _record(tmp_path, keep=(3, 4))
    _header, lines = _lines(tmp_path)
    assert [line["input"] for line in lines] == [3]
    assert sorted((g[0], g[1]) for g in lines[0]["geometry"]) == [(0, 0), (0, 1), (1, 0)]


def test_control_a_window_without_the_earlier_banks_is_seen(tmp_path):
    source = Path(nri.__file__).read_text(encoding="utf-8")
    old = "            writes = [(family, bank, key, payload) for (family, bank), (key, payload) in sorted(self._banks.items())]\n"
    assert source.count(old) == 1
    namespace: dict = {}
    start = source.index("class DeliveryStream:")
    end = source.index("\n# ----", start)
    exec(compile("from __future__ import annotations\nimport json\nfrom pathlib import Path\nfrom typing import Any\n"
                 "_jsonable = None\n" + source[start:end].replace(old, "            pass\n"), "control", "exec"),
         namespace)
    _record(tmp_path, keep=(3, 4), stream_class=namespace["DeliveryStream"])
    _header, lines = _lines(tmp_path)
    assert sorted((g[0], g[1]) for g in lines[0]["geometry"]) != [(0, 0), (0, 1), (1, 0)]


def _eb_stream_check():
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import eb_stream_check

    return eb_stream_check


def _replayed(tmp_path, arena_class):
    _record(tmp_path)
    _header, lines = _lines(tmp_path)
    arena = arena_class(_layout(), tmp_path / "geometry.bin")
    try:
        for line in lines:
            arena.apply(line.get("geometry", []))
        return arena.owner.writer_namespace(), [arena.owner.holds(k) for k in
                                                ((77, 1, 1, 0, 5, 64), (77, 1, 1, 1, 6, 32), (77, 1, 1, 0, 7, 64))]
    finally:
        arena.close()


def test_the_players_arena_holds_every_recorded_key_under_the_recorded_namespace(tmp_path):
    from core.visualizer_engine import extruded_bubble_native_schema as schema

    module = _eb_stream_check()
    if len(schema.FAMILIES) < len(FAMILIES):
        pytest.skip("the schema has fewer families than the test's layout")
    namespace, held = _replayed(tmp_path, module.Arena)
    assert namespace == 77 and held == [True, True, True]


def test_control_an_arena_left_at_its_own_namespace_is_seen(tmp_path):
    module = _eb_stream_check()
    source = Path(module.__file__).read_text(encoding="utf-8")
    old = "        ga._WRITER_NAMESPACE.pack_into(self.writer._memory.buf, ga._WRITER_NAMESPACE_AT, self.writer.namespace)\n"
    assert source.count(old) == 1
    copy = types.ModuleType("eb_stream_check_control")
    copy.__file__ = module.__file__
    exec(compile(source.replace(old, ""), module.__file__, "exec"), copy.__dict__)
    namespace, _held = _replayed(tmp_path, copy.Arena)
    assert namespace != 77
