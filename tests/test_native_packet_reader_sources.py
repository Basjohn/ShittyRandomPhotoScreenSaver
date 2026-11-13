"""N2.3's packet reader: everything that runs without the built module (the module is compiled only on GitHub).

- The C++ reader reads the layout, the mode codes and every record's fields and range rules from a header generated from
  the Python modules (``tools/native_frame_abi_header.py``); the committed header is what they say today.
- The reader's source keeps the module's rules (no STL container, lock or function wrapper; built by CMake), and every
  entry the Python face calls is registered by the module, with the same negative controls and results.
- The adversarial table (``tools/packet_reader_adversary.py``) holds on the Python reference reader, and its naive
  negative control fails every case that has a control; the in-place writer's race never gets a mixed record past the
  reference's seqlock and does get one past the naive reader. The same table runs on the C++ reader in
  ``tests/test_native_core_packet_reader.py`` once the module is built.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from rendering.native import packet_reader as face
from tools import native_frame_abi_header as header_tool
from tools import packet_reader_adversary as adversary

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "native" / "core" / "src"


# ------------------------------------------------------------------------------------------ the generated header

def test_the_generated_header_is_what_the_python_modules_say():
    committed = (ROOT / header_tool.HEADER_RELATIVE).read_text(encoding="utf-8")
    assert committed == header_tool.render()
    assert header_tool.main(["--check", "--repo", str(ROOT)]) == 0


def test_the_header_check_sees_a_changed_layout_or_mode_table(monkeypatch):
    # Negative control: one more mode code, or a schema whose range rule moved, renders another header.
    from core.visualizer_engine import packet_abi
    from core.visualizer_engine import spectrum_native_schema as spectrum
    from core.visualizer_engine import native_schema

    committed = (ROOT / header_tool.HEADER_RELATIVE).read_text(encoding="utf-8")
    monkeypatch.setitem(packet_abi.MODE_CODES, "a_mode_that_does_not_exist", 250)
    assert header_tool.render() != committed
    monkeypatch.delitem(packet_abi.MODE_CODES, "a_mode_that_does_not_exist")
    import dataclasses

    moved = dataclasses.replace(spectrum.SCHEMA, checks=spectrum.SCHEMA.checks[1:])
    monkeypatch.setattr(native_schema, "_schemas", {moved.schema_id: moved})
    assert header_tool.render() != committed


def test_the_header_carries_every_schema_and_the_reference_decoder_uses_its_table():
    from core.visualizer_engine import native_schema

    text = header_tool.render()
    for schema in native_schema.native_schemas().values():
        assert f'0x{schema.schema_id:X}u, {schema.layout.size}, "{schema.layout.fingerprint()}"' in text
        assert schema.fields and set(name for name, _kind, _limit in schema.checks) <= set(schema.fields)
        for name, kind, _limit in schema.checks:
            assert kind in native_schema.FIELD_CHECK_KINDS and schema.layout.field(name).kind == "u32"


def test_the_python_face_refuses_a_module_whose_schemas_differ():
    table = face.python_schema_table()
    assert face.schema_table_differences(table, table) == []
    assert face.schema_table_differences(face.json.loads(face.json.dumps(table)), table) == []
    # Negative controls: another fingerprint, a missing schema, another mode table.
    changed = face.json.loads(face.json.dumps(table))
    changed["schemas"][0]["fingerprint"] = "0" * 16
    assert face.schema_table_differences(changed, table)
    missing = dict(table, schemas=[])
    assert face.schema_table_differences(missing, table)
    modes = dict(table, mode_codes=dict(table["mode_codes"], extra=99))
    assert face.schema_table_differences(modes, table)


def test_the_reader_config_names_only_known_controls_and_a_whole_identity():
    assert face.json.loads(face.reader_config())["controls"] == []
    expect = dict(adversary.EXPECTED_IDENTITY, engine_generation=-1)
    assert face.json.loads(face.reader_config(expect))["expect"]["engine_generation"] == 0xFFFFFFFF
    with pytest.raises(ValueError):
        face.reader_config(controls=("not_a_control",))
    with pytest.raises(ValueError):
        face.reader_config({"runtime_generation": 1})


# ---------------------------------------------------------------------------------------- the reader's source

_FORBIDDEN_INCLUDE = re.compile(r"^#include <(vector|string|map|unordered_map|set|unordered_set|list|deque|mutex|thread|"
                                r"functional|memory|condition_variable|shared_mutex|sstream|iostream|future)>", re.M)


def stl_problems(text: str) -> list[str]:
    return [match.group(0) for match in _FORBIDDEN_INCLUDE.finditer(text)]


def test_the_reader_keeps_the_modules_runtime_rule_and_is_built():
    for name in ("packet_reader.h", "packet_reader.cpp", "frame_abi_generated.h"):
        assert stl_problems((SRC / name).read_text(encoding="utf-8")) == [], name
    assert stl_problems("#include <QtCore/QString>\n#include <mutex>\n") == ["#include <mutex>"]   # negative control
    cmake = (ROOT / "native" / "core" / "CMakeLists.txt").read_text(encoding="utf-8")
    sources = re.search(r"set\(_sources\n(.*?)\)", cmake, re.S).group(1)
    assert "src/packet_reader.cpp" in sources.split()


def _module_entries(text: str) -> set[str]:
    return set(re.findall(r'\{ "(\w+)", \1, METH_', text))


def _called_entries() -> set[str]:
    called = set()
    for path in (ROOT / "rendering" / "native" / "packet_reader.py", ROOT / "rendering" / "native" / "loader.py"):
        called |= set(re.findall(r"self\.(?:_)?module\.((?:packet_reader|frame_schemas)\w*)\(",
                                 path.read_text(encoding="utf-8")))
    return called


def test_every_entry_the_python_face_calls_is_registered_by_the_module():
    module = (SRC / "module.cpp").read_text(encoding="utf-8")
    called = _called_entries()
    assert {"packet_reader_open", "packet_reader_read", "packet_reader_head", "packet_reader_frame",
            "packet_reader_close", "frame_schemas"} <= called
    assert called <= _module_entries(module)
    # Negative control: the same reading of a module without one entry reports it missing.
    trimmed = module.replace('{ "packet_reader_head", packet_reader_head, METH_', "")
    assert not called <= _module_entries(trimmed)


def test_the_faces_controls_and_results_are_the_readers():
    cpp = (SRC / "packet_reader.cpp").read_text(encoding="utf-8")
    controls = set(re.findall(r'name == QLatin1String\("(\w+)"\)', cpp))
    assert controls == set(face.READER_CONTROLS)
    results = re.findall(r'case ReadResult::\w+: return "(\w+)";', cpp)
    assert results == list(face.READ_RESULTS)
    # Negative control: a control the reader does not parse is seen.
    assert set(re.findall(r'name == QLatin1String\("(\w+)"\)', cpp.replace('"skip_identity"', '"x"'))) != controls


# ------------------------------------------------------------------------------- the table on the reference

def test_the_adversarial_table_holds_on_the_python_reference_and_its_naive_control_fails():
    table = adversary.run_reference_table()
    failures = {row["case"]: row["failures"] for row in table["cases"] if not row["held"]}
    assert not failures, failures
    unseen = [row["case"] for row in table["cases"] if row["naive_fails"] and not row["naive_failed"]]
    assert not unseen, unseen
    assert table["pass"]
    names = {row["case"] for row in table["cases"]}
    for kind in ("torn", "stale", "duplicate", "oversize", "refused at the head", "refused record"):
        assert any(name.startswith(kind) for name in names), kind
    # Every refusal cause of the transport rule appears.
    assert set(adversary.HEAD_REFUSALS.values()) == {"schema", "mode", "version", "size"}


def test_every_native_case_names_a_control_or_says_why_not():
    # Each case of the C++ table carries the negative controls that must fail it (run with the built module); the two
    # without one are the baseline and the replacement writer, whose naive control is the reference's.
    without = [case.name for case in adversary.cases() if not case.controls]
    assert without == ["a whole slot is accepted and acknowledged",
                       "torn: the writer died mid-publish, then a replacement"]
    assert all(set(case.controls) <= set(face.READER_CONTROLS) for case in adversary.cases())


def test_the_in_place_writer_never_gets_a_mixed_record_past_the_reference_seqlock():
    held = adversary.stress(lambda name: adversary.ReferenceReader(name), reads=40_000)
    naive = adversary.stress(lambda name: adversary.ReferenceReader(name, naive=True), reads=40_000)
    assert held["writer_exit"] == naive["writer_exit"] == 0
    assert held["mixed"] == 0 and held["torn_reads"] > 0 and held["accepted"] > 0, held
    assert naive["mixed"] > 0, naive                          # negative control: no seqlock, mixed records accepted
