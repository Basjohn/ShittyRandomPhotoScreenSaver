"""N2.9's generic mode content (native/core/src: mode_schema, mode_content, program_blocks' packRecordField;
rendering/native/mode.py; the harness-only mode native/core/python/probe_rings and its harness generic_mode_check.py):
everything that runs without the built module. The built module's half is tests/test_native_core_mode.py and the
harness's draw round.

- A runtime schema is the Python table in the compiled table's own row shape; the core recomputes its fingerprint the
  way NativeLayout does (the algorithm is mirrored here and fed both schemas).
- A mode code appended after a module was built is tolerated (append-only); a renumbered one is not.
- Every module entry the Python face calls is registered; the new sources are built.
- Probe Rings is never registered; its passes declare exactly its record's fields and its spec's settings, by name;
  its shaders bake for every shipped target with regen_qrc's baker (no module build); its simulation is deterministic
  and its record round-trips with its range rule.
- The harness's own measures (the ring radii on the centre row, the independent block packer) hold on an analytic
  image and fail on a shifted one.
- Audit 14 Nov L3: the Spectrum block copies the settings packed when they changed and reads no JSON per record.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core"
SRC = CORE / "src"
HARNESS = CORE / "python"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

import probe_rings as pr  # noqa: E402  (native/core/python)


# ------------------------------------------------------------------------------------------------ the schema


def fingerprint_by_offsets(entry: dict) -> str:
    """mode_schema.cpp's fingerprintOf, in Python: the header words, then every field in offset order."""
    rows = sorted(entry["fields"], key=lambda row: row[3])
    text = "payload_schema:u32:1:0;record_bytes:u32:1:4" + "".join(
        f";{name}:{kind}:{count}:{offset}" for name, kind, count, offset, _check, _limit in rows)
    text += f";size={entry['record_bytes']}"
    return hashlib.sha256(text.encode("ascii")).hexdigest()[:16]


def test_a_runtime_schema_is_the_compiled_tables_row_shape_and_its_fingerprint_is_recomputed():
    from core.visualizer_engine import native_schema
    from rendering.native.mode import schema_table_entry
    from rendering.native.packet_reader import python_schema_table

    compiled = python_schema_table()["schemas"]
    assert compiled == [schema_table_entry(s) for s in sorted(native_schema.compiled_schemas().values(),
                                                                 key=lambda s: s.schema_id)]
    for entry in [*compiled, schema_table_entry(pr.SCHEMA)]:
        assert fingerprint_by_offsets(entry) == entry["fingerprint"], entry["mode_id"]
    # The C++ reads every key the face writes, and the text it hashes starts with the header words.
    cpp = (SRC / "mode_schema.cpp").read_text(encoding="utf-8")
    keys = set(re.findall(r'QStringLiteral\("(\w+)"\)', cpp.split("const QStringList keys", 1)[1].split(";", 1)[0]))
    assert keys == set(schema_table_entry(pr.SCHEMA))
    assert '"payload_schema:u32:1:0;record_bytes:u32:1:4"' in cpp and '";size="' in cpp
    # Negative control: a field moved without its fingerprint is seen.
    moved = schema_table_entry(pr.SCHEMA)
    moved["fields"] = [[*row[:3], row[3] + 8 if row[0] == "time" else row[3], *row[4:]] for row in moved["fields"]]
    assert fingerprint_by_offsets(moved) != moved["fingerprint"]


def test_a_mode_code_appended_after_the_module_was_built_is_tolerated():
    from rendering.native import packet_reader as face

    table = face.python_schema_table()
    module = json.loads(json.dumps(table))
    module["mode_codes"].pop(max(module["mode_codes"], key=module["mode_codes"].get))
    assert face.schema_table_differences(module, table) == []
    # Negative controls: a renumbered code, and a code only the module has.
    renumbered = json.loads(json.dumps(table))
    first = next(iter(renumbered["mode_codes"]))
    renumbered["mode_codes"][first] += 100
    assert face.schema_table_differences(renumbered, table)
    extra = dict(table, mode_codes=dict(table["mode_codes"], a_later_mode=99))
    assert face.schema_table_differences(extra, table)


def test_a_runtime_schema_never_makes_the_module_table_differ_and_a_compiled_one_does(monkeypatch):
    # Audit N29 M5.1: the schemas the module compiles (compared with a built module's table) and the runtime schemas
    # (known to the Python transport, handed to the core at bind) are two registries.
    import types

    from core.visualizer_engine import native_schema
    from core.visualizer_engine.native_schema import NativeLayout, NativeSchema
    from rendering.native import packet_reader as face

    module_table = face.python_schema_table()          # a module built before the new mode's schema existed
    layout = NativeLayout.build((("level", "f64", 1),))
    schema = NativeSchema(mode_id="oscilloscope", version=1, layout=layout, encode=lambda values: b"",
                          decode=lambda payload: {}, fields=("level",))
    fake = types.ModuleType("srpss_test_runtime_schema")
    fake.SCHEMAS = (schema,)
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    monkeypatch.setattr(native_schema, "_runtime_ids", native_schema._runtime_ids)
    compiled = dict(native_schema._SCHEMA_MODULES)

    def registered(compiled_modules, runtime_modules):
        monkeypatch.setattr(native_schema, "_SCHEMA_MODULES", compiled_modules)
        monkeypatch.setattr(native_schema, "_RUNTIME_SCHEMA_MODULES", runtime_modules)
        monkeypatch.setattr(native_schema, "_schemas", None)
        return face.schema_table_differences(module_table, face.python_schema_table())

    assert registered(compiled, {"oscilloscope": fake.__name__}) == []
    assert schema.schema_id in native_schema.runtime_schemas() and schema.schema_id in native_schema.native_schemas()
    assert schema.schema_id not in native_schema.compiled_schemas()
    # Control: the same schema in the compiled registry is a difference (the module would raise SchemaTableMismatch).
    differences = registered({**compiled, "oscilloscope": fake.__name__}, {})
    assert differences and any("not in the module" in line for line in differences)
    # A mode in both registries is refused.
    with pytest.raises(RuntimeError, match="both schema registries"):
        registered({**compiled, "oscilloscope": fake.__name__}, {"oscilloscope": fake.__name__})
    monkeypatch.setattr(native_schema, "_schemas", None)


# --------------------------------------------------------------------------------------------- the sources


_CALL = re.compile(r"(?:self\._module|self\.module|\bmodule)\.(\w+)\(")


def _module_entries(text: str) -> set[str]:
    return set(re.findall(r'\{ "(\w+)", \1, METH_', text))


def test_every_entry_the_mode_face_calls_is_registered_and_the_sources_are_built():
    called = set()
    for path in (ROOT / "rendering" / "native" / "mode.py", ROOT / "rendering" / "native" / "loader.py"):
        called |= set(_CALL.findall(path.read_text(encoding="utf-8")))
    mode_calls = {name for name in called if name.startswith(("composite_mode", "mode_", "program_block"))}
    assert {"composite_mode_bind", "composite_mode_program", "composite_mode_settings", "mode_blocks",
            "mode_program_layout", "program_block_pack"} <= mode_calls
    module = (SRC / "module.cpp").read_text(encoding="utf-8")
    assert mode_calls <= _module_entries(module)
    trimmed = module.replace('{ "mode_blocks", mode_blocks, METH_', "")
    assert not mode_calls <= _module_entries(trimmed)                      # negative control
    cmake = (CORE / "CMakeLists.txt").read_text(encoding="utf-8")
    sources = re.search(r"set\(_sources\n(.*?)\)", cmake, re.S).group(1).split()
    assert {"src/mode_schema.cpp", "src/mode_content.cpp"} <= set(sources)


def _function_body(text: str, signature: str) -> str:
    start = text.index(signature)
    depth, index = 0, text.index("{", start)
    for position in range(index, len(text)):
        depth += {"{": 1, "}": -1}.get(text[position], 0)
        if depth == 0:
            return text[index:position + 1]
    raise AssertionError(f"{signature} has no body")


def per_record_json(body: str) -> list[str]:
    """What a block function reads from JSON per record (audit 14 Nov, L3: nothing)."""
    return re.findall(r"\bsetJson\s*\(|\.settings\b(?!\s*\))", re.sub(r"//[^\n]*", "", body))


def test_the_spectrum_block_copies_the_packed_settings_and_reads_no_json_per_record():
    text = (SRC / "spectrum.cpp").read_text(encoding="utf-8")
    body = _function_body(text, "bool spectrumBlock(")
    assert per_record_json(body) == [] and "program.packed" in body
    # Negative control: the old body's lines are caught.
    old = body.replace("BlockValues packed = program.packed;",
                       "BlockValues packed(program.layout);\n    if (!packed.setJson(program.settings, reason))")
    assert per_record_json(old)


# ------------------------------------------------------------------------------------------- Probe Rings


def registered_places(mode_id: str, code: int, schema_id: int) -> list[str]:
    """Where the product knows a mode: its code, its schema, its Settings spec, its registry descriptor, its shaders."""
    from core.settings import visualizer_mode_registry
    from core.settings.visualizer_mode_settings import iter_mode_settings
    from core.visualizer_engine import native_schema, packet_abi
    from tools import regen_qrc

    places = []
    if mode_id in packet_abi.MODE_CODES or code in packet_abi.MODE_CODES.values():
        places.append("MODE_CODES")
    if schema_id in native_schema.native_schemas():
        places.append("native_schemas")
    if any(spec.mode_id == mode_id for spec in iter_mode_settings()):
        places.append("mode settings")
    try:
        visualizer_mode_registry.get_visualizer_mode_descriptor(mode_id)
        places.append("mode registry")
    except Exception:
        pass
    if [p for p in regen_qrc.quick_shader_sources() if p.parent == pr.HERE]:
        places.append("product shaders")
    return places


def test_probe_rings_is_never_registered(monkeypatch):
    from core.visualizer_engine import packet_abi

    assert registered_places(pr.MODE_ID, pr.MODE_CODE, pr.SCHEMA.schema_id) == []
    # Negative control (audit N29 L11): a stand-in registration of its code is seen.
    monkeypatch.setattr(packet_abi, "MODE_CODES", {**packet_abi.MODE_CODES, pr.MODE_ID: pr.MODE_CODE})
    assert registered_places(pr.MODE_ID, pr.MODE_CODE, pr.SCHEMA.schema_id) == ["MODE_CODES"]


def _block_members(text: str, block: str) -> list[str]:
    from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl

    return [name for name, _kind in block_layout_from_glsl(block_declaration(text, block)).fields]


_UNIFORM_BLOCK = re.compile(r"layout\s*\(\s*std140\s*,\s*binding\s*=\s*(\d+)\s*\)\s*uniform\s+(\w+)\s*\{")


def own_blocks(text: str) -> list[tuple[str, int]]:
    """A shader's uniform blocks other than the conventions block, (name, binding), as the core's checkPass reads its
    reflection: the product 2D shape has exactly one, at any binding but 17."""
    return [(name, int(binding)) for binding, name in _UNIFORM_BLOCK.findall(re.sub(r"//[^\n]*", "", text))
            if name != "SrpssConventions"]


def _sources(texts) -> dict[str, set[str]]:
    """Each pass's own block's members by the source that fills them (mode_content.h's one rule)."""
    from rendering.native.mode import MODE_CORE_MEMBERS

    by_source: dict[str, set[str]] = {"core": set(), "record": set(), "settings": set()}
    for text in texts:
        (block, _binding), = own_blocks(text)
        for name in _block_members(text, block):
            source = ("core" if name in MODE_CORE_MEMBERS else "record" if name in pr.SCHEMA.fields else "settings")
            by_source[source].add(name)
    return by_source


def test_probe_rings_is_in_the_product_2d_shape_and_fills_each_member_from_one_source():
    base = [pr.shader_text(filename) for _name, filename, _blend in pr.PASSES]
    assert all(own_blocks(text) == [("ProbeRingsDraw", 18)] for text in base)
    assert "in vec2 v_uv;" in pr.shader_text("glow.frag")      # the core's triangle gives v_uv (M5)
    sources = _sources(base)
    assert sources["record"] == set(pr.SCHEMA.fields)          # every record field a member, every member a field
    assert sources["core"] == {"u_target_px", "u_fade"}
    assert sources["settings"] == set(pr.resolve_settings({}, dpr=1.0))
    assert set(pr.SETTING_UNIFORMS) >= {control.key for control in pr.TINT_SPEC.controls}
    # The proof's change: the tinted shader declares a member the base spec does not fill (the core's unfilled
    # refusal), which the tinted spec fills.
    tinted = _sources([pr.shader_variant(tint=True), base[1]])
    assert tinted["record"] == sources["record"] and tinted["settings"] - sources["settings"] == {"u_tint"}
    assert tinted["settings"] == set(pr.resolve_settings({}, dpr=1.0, spec=pr.TINT_SPEC, defaults=pr.TINT_DEFAULTS))
    assert pr.shader_variant(green=True) != base[0] and "u_tint" not in _sources([pr.shader_variant(green=True)])[
        "settings"]
    # The thickness is a setting in device pixels: the dpr scales it, never the shader.
    assert pr.resolve_settings({}, dpr=1.5)["u_thickness_px"] == 1.5 * pr.resolve_settings({}, dpr=1.0)["u_thickness_px"]


def test_the_product_2d_shaders_have_one_block_of_their_own_and_bubble_two_samplers():
    # Audit N29 M5: the generic pass takes the product 2D shaders' shape. Oscilloscope and Spline Curve declare v_uv and
    # one block of their own; Bubble also two samplers (the sampling primitive's, plan N4.a). Proved over the real
    # .qsb packs by checkPass in tests/test_native_core_mode.py and the harness's blocks round.
    from tools import regen_qrc

    folder = regen_qrc.mode_shader_dir()
    for name in ("oscilloscope.frag", "devcurve.frag", "bubble.frag"):
        text = (folder / name).read_text(encoding="utf-8")
        blocks = own_blocks(text)
        assert len(blocks) == 1 and blocks[0][1] != 17, (name, blocks)
        assert "layout(location = 0) in vec2 v_uv;" in text
    bubble = (folder / "bubble.frag").read_text(encoding="utf-8")
    samplers = re.findall(r"uniform\s+sampler2D\s+(\w+)", bubble)      # whatever Bubble names them (L7)
    assert len(samplers) == len(set(samplers)) == 2
    # Negative control: a second block of its own is seen.
    assert len(own_blocks(text + "\nlayout(std140, binding = 19) uniform Second { float x; };\n")) == 2


#: What a renderer reads from its presentation that is the card's (the rest of the presentation is its settings).
_CARD_PRESENTATION = frozenset({"dpr", "border_width", "content_fade"})


def card_members(source: str) -> set[str]:
    """The block members a Python 2D renderer fills from its frame (the card) rather than from its settings or its
    mode state: what the core's conventions must cover (audit N29 M5). Read from the source's syntax tree (round 2,
    L7: any spelling of the assignment): each ``values["name"] = expression`` whose expression reads ``frame.<attr>``
    (directly, or through a local that is ``frame.<attr>`` itself), the card's ``presentation.<dpr | border_width |
    content_fade>``, or is a literal (the core's own constants)."""
    import ast

    tree = ast.parse(source)
    aliases = {node.targets[0].id for node in ast.walk(tree)
               if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
               and isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name)
               and node.value.value.id == "frame"}

    def from_card(expression) -> bool:
        if isinstance(expression, ast.Constant) or (isinstance(expression, ast.Tuple) and all(
                isinstance(element, ast.Constant) for element in expression.elts)):
            return True
        for node in ast.walk(expression):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "frame" or (node.value.id == "presentation" and node.attr in _CARD_PRESENTATION):
                    return True
            if isinstance(node, ast.Name) and node.id in aliases:
                return True
        return False

    taken = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target = node.targets[0]
        if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "values"
                and isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str)
                and from_card(node.value)):
            taken.add(target.slice.value)
    return taken


def test_the_cores_conventions_cover_what_the_python_2d_renderers_take_from_the_card():
    from rendering.native.mode import MODE_CORE_MEMBERS

    folder = ROOT / "rendering" / "quick" / "visualizer" / "implementations"
    for name in ("devcurve.py", "bubble.py", "oscilloscope.py"):
        source = (folder / name).read_text(encoding="utf-8")
        taken = card_members(source)
        assert {"uMatrix"} < taken, name                                    # the scan sees each renderer's card
        assert taken <= set(MODE_CORE_MEMBERS), (name, taken - set(MODE_CORE_MEMBERS))
    # Negative controls: a new member taken from the frame is seen outside the table, in another spelling too (an
    # alias of a frame attribute, a call around it).
    assert card_members('values["u_frame_new"] = frame.logical_size\n') - set(MODE_CORE_MEMBERS) == {"u_frame_new"}
    assert card_members('size = frame.logical_size\nvalues["u_frame_new"] = tuple(size)\n') == {"u_frame_new"}
    assert card_members('values["u_frame_new"] = float(frame.logical_size[0])\n') == {"u_frame_new"}
    assert card_members('values["u_setting"] = layout.scale\n') == set()                  # a setting is not


def test_the_cores_conventions_table_is_the_faces():
    from rendering.native.mode import MODE_CORE_MEMBERS

    text = (SRC / "mode_content.cpp").read_text(encoding="utf-8")
    table = text.split("const ModeCoreMember kModeCoreMembers[] = {", 1)[1].split("};", 1)[0]
    rows = re.findall(r'\{\s*"(\w+)",\s*(\d+),\s*(true|false)\s*,\s*\w+\s*\}', table)   # each with its values (L6)
    assert {name: (int(n), flag == "true") for name, n, flag in rows} == MODE_CORE_MEMBERS
    assert [name for name, _n, _f in rows] == list(MODE_CORE_MEMBERS)      # one order
    # Negative control: a row changed in C++ only is seen.
    changed = re.sub(r'\{ "u_fade", 1, true,', '{ "u_fade", 2, true,', table)
    assert changed != table
    assert {n: (int(c), f == "true") for n, c, f in re.findall(
        r'\{\s*"(\w+)",\s*(\d+),\s*(true|false)\s*,\s*\w+\s*\}', changed)} != MODE_CORE_MEMBERS


def test_probe_rings_shaders_bake_for_every_shipped_target_with_no_module_build(tmp_path):
    from tools import regen_qrc

    try:
        regen_qrc.quick_shader_baker(sys.executable)
    except regen_qrc.QrcRegenerationError as exc:
        pytest.skip(f"no qsb: {exc}")
    passes = pr.passes(tmp_path / "base")
    assert [p.name for p in passes] == [name for name, _f, _b in pr.PASSES]
    assert all(p.pack and p.blend in ("alpha", "add") for p in passes)
    for label, text in (("tint", pr.shader_variant(tint=True)), ("green", pr.shader_variant(green=True))):
        folder = tmp_path / label
        folder.mkdir()
        assert pr.bake(text, "rings.frag", folder)


def test_the_harness_refusal_shaders_declare_what_a_pass_may_not_and_bake(tmp_path):
    import generic_mode_check as check
    from tools import regen_qrc

    assert own_blocks(check.variant_text("binding17")) == [("ProbeRingsDraw", 17)]
    assert sorted(own_blocks(check.variant_text("two_blocks"))) == [("ProbeRingsDraw", 18), ("ProbeSecond", 19)]
    assert "uniform sampler2D u_probe_texture" in check.variant_text("sampler")
    bubble = (regen_qrc.mode_shader_dir() / "bubble.frag").read_text(encoding="utf-8")
    stripped = check.bubble_without_samplers_text(bubble)
    code = re.sub(r"//[^\n]*", "", stripped)
    assert "sampler2D" not in code and not any(f"texture({name}," in code for name, _b in check.bubble_samplers(bubble))
    assert own_blocks(stripped) == own_blocks(bubble)                      # its own block untouched
    # Negative control: a shader that does not read its samplers as expected is refused, not silently passed.
    last = check.bubble_samplers(bubble)[-1][0]
    with pytest.raises(ValueError):
        check.bubble_without_samplers_text(bubble.replace(f"texture({last},", f"texture( {last},"))
    try:
        regen_qrc.quick_shader_baker(sys.executable)
    except regen_qrc.QrcRegenerationError as exc:
        pytest.skip(f"no qsb: {exc}")
    for kind in check.VARIANTS:                                            # every one compiles: refused by checkPass
        assert pr.bake(check.variant_text(kind), "glow.frag", tmp_path / kind)
    assert pr.bake(stripped, "bubble.frag", tmp_path / "bubble")


def test_probe_rings_simulation_is_deterministic_and_its_record_round_trips():
    from core.visualizer_engine.native_schema import PayloadRefused

    def run(speed):
        simulation = pr.RingsSimulation(speed=speed)
        return [simulation.step(1.0 / 60.0) for _ in range(240)]

    first, again, fast = run(0.35), run(0.35), run(0.7)
    assert first == again and first != fast
    assert max(v["ring_count"] for v in first) >= 2 and all(v["ring_count"] <= pr.MAX_RINGS for v in first)
    for values in first[::20]:
        decoded = pr.SCHEMA.decode(pr.record(values))
        assert decoded == {k: (tuple(v) if isinstance(v, (list, tuple)) else v) for k, v in values.items()}
    broken = bytearray(pr.record(first[-1]))
    struct.pack_into("<I", broken, pr.SCHEMA.layout.field("ring_count").offset, pr.MAX_RINGS + 1)
    with pytest.raises(PayloadRefused):
        pr.SCHEMA.decode(bytes(broken))


# --------------------------------------------------------------------------------------------- the harness


def _analytic_rings(values: dict, thickness: float, shift: float = 0.0):
    """rings.frag's alpha, in numpy, over the harness card (premultiplied white over black)."""
    import numpy as np

    import generic_mode_check as check

    width, height = check.CARD
    ys, xs = np.mgrid[0:height, 0:width]
    d = np.hypot(xs + 0.5 - width / 2.0, ys + 0.5 - height / 2.0)
    unit = 0.5 * min(width, height)
    alpha = np.zeros_like(d)
    for r, a in zip(values["rings"][:values["ring_count"]], values["ring_alpha"][:values["ring_count"]]):
        t = np.clip((np.abs(d - (r * unit + shift)) - 0.5 * thickness) / 1.0, 0.0, 1.0)
        alpha = np.maximum(alpha, (1.0 - t * t * (3.0 - 2.0 * t)) * a)
    value = np.round(alpha * 255.0).astype(np.uint8)
    return np.stack([value, value, value, np.full_like(value, 255)], axis=2)


def test_the_harness_finds_rings_where_the_record_puts_them_and_not_where_it_does_not():
    import generic_mode_check as check

    thickness = 3.0
    sample = next(_frames_with_rings(thickness))
    assert check._radii_match(_analytic_rings(sample, thickness), sample, thickness) is True
    # Negative control: the same rings drawn 4 pixels out are not where the record puts them.
    assert check._radii_match(_analytic_rings(sample, thickness, shift=4.0), sample, thickness) is False
    thin = check.ring_runs(_analytic_rings(sample, 2.0))
    thick = check.ring_runs(_analytic_rings(sample, 8.0))
    assert min(w for _c, w in thick) >= max(w for _c, w in thin) + 4


def _frames_with_rings(thickness: float):
    import generic_mode_check as check

    simulation = pr.RingsSimulation()
    for _ in range(240):
        values = simulation.step(1.0 / 60.0)
        rings = check.visible_rings(values, thickness)
        if rings and len(rings) >= 2:
            yield values


def test_the_harness_packer_places_values_at_reflected_offsets_and_strides():
    import generic_mode_check as check

    rows = [["u_target_px", 0, 0, 1, 0, False], ["rings", 0, 16, 3, 16, True], ["ring_count", 0, 64, 1, 0, False],
            ["pulse_color", 0, 80, 1, 0, False]]
    values = {"u_target_px": [480.0, 270.0], "rings": (0.25, 0.5, 0.75), "ring_count": 3,
              "pulse_color": (0.1, 0.2, 0.3, 1.0)}
    data = check.expected_block(rows, values, 96)
    assert struct.unpack_from("<2f", data, 0) == (480.0, 270.0)
    assert [struct.unpack_from("<f", data, 16 + 16 * i)[0] for i in range(3)] == [0.25, 0.5, 0.75]
    assert struct.unpack_from("<i", data, 64)[0] == 3
    assert struct.unpack_from("<4f", data, 80) == tuple(struct.unpack("<4f", struct.pack("<4f", 0.1, 0.2, 0.3, 1.0)))
    assert data[20:32] == bytes(12)                        # the stride's padding stays zero
    # Negative control: a ring_count packed as a float is not the int the shader reads.
    assert struct.unpack_from("<i", check.expected_block([["count", 0, 0, 1, 0, False]], {"count": 3}, 16), 0)[0] != 3
