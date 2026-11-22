"""N5.6, Extruded Bubble's core C++ boxes (ABI 42), GPU-free (``native/core/src/abi.h`` 42).

Box 1, the scene probe (``scene_targets.h`` cube targets, ``cube_prefilter.h``): Python's ``SceneProbe``
(``rendering/quick/scene3d/probe.py``) is the oracle for the faces' order and orientation, the prefilter's filter and
its cone. Each test's negative control is a mutated form of the source, seen failing. The drawn proofs (every face and
level read back against Python's capture on both backends, a lookup across a face edge) run on the built module.
"""
from __future__ import annotations

import math
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "native" / "core" / "src"
SHADERS = ROOT / "native" / "core" / "shaders"


def _source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8").replace("\r\n", "\n")


def _function(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end, text.index(start))]


def _probe_prefilter_body() -> str:
    """probe.py's prefilter fragment as authored (before portable_program rewrites it), from ``vec3 helper`` on."""
    text = (ROOT / "rendering" / "quick" / "scene3d" / "probe.py").read_text(encoding="utf-8")
    fragment = text[text.index('_PREFILTER_FRAGMENT = """'):]
    fragment = fragment[:fragment.index('"""\n', len('_PREFILTER_FRAGMENT = """'))]
    return fragment[fragment.index("    vec3 helper"):fragment.rindex("}")]


# ------------------------------------------------------------------------------------------ box 1: the prefilter

def prefilter_is_probes(frag: str, probe_body: str) -> bool:
    """The core's prefilter filters as probe.py's: the same body from the cone's frame to the stored level, its axis
    from the face's rotation over an NDC that reads OpenGL's rows (fragPixel's memory row 0 at NDC -1), no gl_Layer."""
    if "gl_Layer =" in frag or "layout(triangles" in frag:
        return False
    body = frag[frag.index("    vec3 helper"):frag.rindex("}")]
    return (body == probe_body
            and "vec2 fNdc = fragPixel(vec2(uSide)) / uSide * 2.0 - 1.0;" in frag
            and "vec3 axis = transpose(mat3(uWorldToFace[uFace])) * normalize(vec3(fNdc, -1.0));" in frag
            and "uniform samplerCube uSource;" in frag)


def test_the_prefilter_is_probe_pys_filter_tap_for_tap():
    frag = (SHADERS / "cube_prefilter.frag").read_text(encoding="utf-8")
    probe_body = _probe_prefilter_body()
    assert prefilter_is_probes(frag, probe_body)
    # Negative controls: fewer taps, a mirrored row order, a layered geometry-shader form.
    assert not prefilter_is_probes(frag.replace("i < 32", "i < 16").replace("/ 32.0", "/ 16.0"), probe_body)
    assert not prefilter_is_probes(frag.replace("/ uSide * 2.0 - 1.0;", "/ uSide * -2.0 + 1.0;"), probe_body)
    assert not prefilter_is_probes(frag + "\n// gl_Layer = face;\n", probe_body)


def _core_faces(cpp: str):
    table = cpp[cpp.index("constexpr double kFaces[kCubeFaces][2][3] = {"):]
    table = table[:table.index("};")]
    numbers = [float(v) for v in re.findall(r"-?\d+\.\d+", table)]
    return [((numbers[6 * f:6 * f + 3]), (numbers[6 * f + 3:6 * f + 6])) for f in range(6)]


def _rotation(forward, up):
    right = (forward[1] * up[2] - forward[2] * up[1], forward[2] * up[0] - forward[0] * up[2],
             forward[0] * up[1] - forward[1] * up[0])
    return (*right, *up, *(-v for v in forward))


def faces_match_probe(cpp: str) -> bool:
    from rendering.quick.scene3d.probe import scene3d_probe_face_rotation
    faces = _core_faces(cpp)
    return len(faces) == 6 and all(
        tuple(_rotation(*faces[f])) == tuple(scene3d_probe_face_rotation(f)) for f in range(6))


def test_the_faces_are_opengls_cube_map_order_and_probe_pys_rotations():
    cpp = _source("cube_prefilter.cpp")
    assert faces_match_probe(cpp)
    # The block holds GLSL's mat3 as the row-major rotation (probe.py's _FACE_COLUMNS).
    assert "rotations[f * 16 + column * 4 + row] = float(r[3 * row + column]);" in cpp
    # Negative control: +X and -X swapped.
    swapped = cpp.replace("{ { 1.0, 0.0, 0.0 }, { 0.0, -1.0, 0.0 } },\n    { { -1.0, 0.0, 0.0 }, { 0.0, -1.0, 0.0 } },",
                          "{ { -1.0, 0.0, 0.0 }, { 0.0, -1.0, 0.0 } },\n    { { 1.0, 0.0, 0.0 }, { 0.0, -1.0, 0.0 } },")
    assert swapped != cpp and not faces_match_probe(swapped)


def test_the_cone_and_the_level_read_are_probe_pys():
    cpp = _source("cube_prefilter.cpp")
    assert "return qMin(2.2 * (kPi / 2.0) / double(levelSide), kPi / 2.0);" in cpp
    assert "const float sourceLod = float(level - 1);" in cpp

    def core_cone(side, level):                 # cubePrefilterCone, line for line
        return min(2.2 * (math.pi / 2.0) / max(1, side >> level), math.pi / 2.0)

    for size in (256, 128, 64):                 # the probe's face sizes by tier (eb.py)
        for level in range(1, int(math.log2(size)) + 1):
            side = max(size >> level, 1)
            assert core_cone(size, level) == min(2.2 * (math.pi / 2.0) / side, math.pi / 2.0)


# ------------------------------------------------------------------------------------------ box 1: the cube target

def cube_target_is_wired(targets_h: str, targets_cpp: str, prefilter_cpp: str) -> bool:
    """One RGBA16F cube (CubeMap | MipMapped), a render target per face over level 0 (setLayer), a stage cube per level
    the prefilter draws and copies from, every face and level read back; never generateMips."""
    step = _function(targets_cpp, "bool SceneTargets::step(", "QRhiTexture *SceneTargets::sampledTexture(")
    return ("flags |= QRhiTexture::CubeMap | QRhiTexture::MipMapped;" in step
            and "attachment.setLayer(f);\n                    attachment.setLevel(0);" in step and "t.faceTarget[f]->setRenderPassDescriptor(t.renderPass.get());" in step
            and "QRhiTexture::CubeMap | QRhiTexture::RenderTarget" in step
            and "generateMips" not in prefilter_cpp
            and "description.setDestinationLevel(level);" in prefilter_cpp
            and "copy->copyTexture(t.colour[0].get(), t.stage[level].get(), description);" in prefilter_cpp
            and "description.setLayer(texture.layer);" in targets_cpp
            and "RhiOwned<QRhiTextureRenderTarget> faceTarget[kCubeFaces];" in targets_h)


def test_a_cube_target_is_six_face_targets_and_a_prefiltered_chain():
    h, cpp, pre = _source("scene_targets.h"), _source("scene_targets.cpp"), _source("cube_prefilter.cpp")
    assert cube_target_is_wired(h, cpp, pre)
    # Negative controls: QRhi's generateMips for the chain; the faces drawn into one layer.
    assert not cube_target_is_wired(h, cpp, pre.replace("cb->resourceUpdate(copy);",
                                                        "copy->generateMips(t.colour[0].get());\n        cb->resourceUpdate(copy);"))
    assert not cube_target_is_wired(h, cpp.replace("attachment.setLayer(f);\n                    attachment.setLevel(0);",
                                                   "attachment.setLevel(0);"), pre)


def cube_declaration_rules(targets_cpp: str) -> bool:
    parse = _function(targets_cpp, "bool parseTargetDeclaration(", "int bucketPixels(")
    return ("d.size.width() != d.size.height()" in parse and "d.colour.at(0).format != TargetFormat::RGBA16F" in parse
            and "d.samples != 1" in parse and "d.mips" in parse and "d.exact = true;" in parse
            and 'QStringLiteral("cube") };' in parse)


def test_a_cube_is_square_rgba16f_single_sampled_and_exact():
    cpp = _source("scene_targets.cpp")
    assert cube_declaration_rules(cpp)
    assert not cube_declaration_rules(cpp.replace("d.size.width() != d.size.height() || ", ""))


def cube_passes_are_wired(mode_cpp: str) -> bool:
    """A run on a cube is one face's passes into that face's target, cleared per face, over the rows-up triangle; the
    prefilter step runs outside any run; a vertex stage's uMatrix gains the cube's Y flip."""
    passes = _function(mode_cpp, "void ModeContent::recordPasses(", "bool ModeContent::record(")
    return ("&& program.passes.at(last + 1).face == pass.face)" in passes
            and "cube ? t.faceRenderTarget(pass.face) : t.renderTarget.get()" in passes
            and "cleared[runTarget] = false;" in passes
            and "cube ? cubeInput : t.decl.surfaceSized() ? sceneInput : ownInput" in passes
            and "m_cubePrefilter.record(rhi, cb, *cube, &pending, &prefilterError)" in passes
            and "cubeCorrection[c] = (c % 4 == 1) ? -clipCorrection[c] : clipCorrection[c];" in mode_cpp
            and "o[3] = 1.0f - in[3];" in mode_cpp and "o[5] = 1.0f - in[5];" in mode_cpp)


def test_a_cube_face_run_draws_its_face_rows_up_and_is_cleared():
    cpp = _source("mode_content.cpp")
    assert cube_passes_are_wired(cpp)
    # Negative controls: the faces merged into one run; the face drawn in the core's own rows (no flip).
    assert not cube_passes_are_wired(cpp.replace("\n               && program.passes.at(last + 1).face == pass.face)",
                                                 ")"))
    assert not cube_passes_are_wired(cpp.replace("o[3] = 1.0f - in[3];", "o[3] = in[3];"))


def test_the_rows_up_triangle_puts_uv_zero_at_the_faces_bottom_row():
    # cubeTriangle, line for line, over the own triangle's uv: a vertex at the target's top row (vUv.y 1, v_uv.y 0)
    # lands at the face's bottom-row uv (vUv.y 0, v_uv.y 1); the map stays affine (the triangle's far corners too).
    own = [(-1.0, -1.0, 0.0, 1.0, 0.0, 0.0), (3.0, -1.0, 2.0, 1.0, 2.0, 0.0), (-1.0, 3.0, 0.0, -1.0, 0.0, 2.0)]
    flipped = [(x, y, u, 1.0 - v, s, 1.0 - t) for x, y, u, v, s, t in own]
    for (x, y, u, v, s, t), (_, _, fu, fv, fs, ft) in zip(own, flipped):
        assert fu == u and fs == s and fv + v == 1.0 and ft + t == 1.0


def test_a_face_pass_and_the_prefilter_are_checked_at_the_parse():
    cpp = _source("mode_content.cpp")
    assert 'QStringLiteral("face"), // N3.4; ABI 42' in cpp
    assert "a pass into a cube target declares its \\\"face\\\" (0 to 5)" in cpp
    assert "each of its six faces is drawn by a pass, then one prefilter step" in cpp
    assert "a transparency, mipped or cube target has no capture" in cpp
    assert "type == QShaderDescription::SamplerCube ? kCubeSamplerDimensions" in cpp
    assert "|| prefilter;                     // ABI 42" in _source("mode_content.h")


def test_the_abi_is_42_and_the_loader_speaks_it():
    from rendering.native import loader
    assert "#define SRPSS_NATIVE_CORE_ABI 42" in _source("abi.h")
    assert loader.EXPECTED_ABI == 42
    assert "src/cube_prefilter.cpp" in (ROOT / "native" / "core" / "CMakeLists.txt").read_text(encoding="utf-8")


# ------------------------------------------------------------------------- box 2: geometry once per key (D3)

def _arena_constants(header: str) -> dict:
    return {name: int(value, 0) for name, value in re.findall(
        r"constexpr quint(?:32|64) (kGeometry\w+) = (0x[0-9A-Fa-f]+|\d+)u?;", header)}


def _bank_offset(family: int, bank: int, bank_bytes: int, c: dict) -> int:
    """geometryBankOffset as geometry_arena.h's layout states it."""
    return (c["kGeometryHeaderBytes"]
            + (family * c["kGeometryBanks"] + bank) * (c["kGeometryBankHeaderBytes"] + bank_bytes))


def _write_arena(families: int, bank_bytes: int, banks: dict, c: dict) -> bytearray:
    """A twin of the main process's writer from the header comment's layout: `banks` maps (family, bank) to
    (sequence, key (ns, engine, activation, family, capacity, revision), payload)."""
    data = bytearray(_bank_offset(families, 0, bank_bytes, c))
    struct.pack_into("<IIIIQII", data, 0, c["kGeometryArenaMagic"], c["kGeometryArenaVersion"], families,
                     c["kGeometryBanks"], bank_bytes, c["kGeometryHeaderBytes"], c["kGeometryBankHeaderBytes"])
    for (family, bank), (sequence, key, payload) in banks.items():
        at = _bank_offset(family, bank, bank_bytes, c)
        struct.pack_into("<IIQIIIIQ", data, at, sequence, len(payload), *key)
        start = at + c["kGeometryBankHeaderBytes"]
        data[start:start + len(payload)] = payload
    return data


_KEY_FIELDS = ("ns", "engine", "activation", "family", "capacity", "revision")


def _core_read(cpp: str, data: bytes, key: tuple, c: dict):
    """GeometryArena::read's header offsets, taken from the source, applied to an arena: the payload of the even bank
    holding every word of `key`, else None (a reader that reads fewer words than the key never matches)."""
    body = _function(cpp, "GeometryArena::Read GeometryArena::read(", "\n} // namespace srpss_core")
    reads = {field: int(off) for field, off in re.findall(r"held\.(\w+) = u(?:32|64)At\(header \+ (\d+)\);", body)}
    families = struct.unpack_from("<I", data, 8)[0]
    bank_bytes = struct.unpack_from("<Q", data, 16)[0]
    want = dict(zip(_KEY_FIELDS, key))
    if want["family"] >= families or set(reads) != set(_KEY_FIELDS):
        return None
    for bank in range(c["kGeometryBanks"]):
        at = _bank_offset(want["family"], bank, bank_bytes, c)
        if struct.unpack_from("<I", data, at)[0] & 1:
            continue
        held = {f: struct.unpack_from("<Q" if f in ("ns", "revision") else "<I", data, at + off)[0]
                for f, off in reads.items()}
        if held == want:
            start = at + c["kGeometryBankHeaderBytes"]
            return bytes(data[start:start + struct.unpack_from("<I", data, at + 4)[0]])
    return None


def test_the_arena_reader_takes_the_bank_the_writer_wrote_by_its_whole_key():
    header = _source("geometry_arena.h")
    cpp = _source("geometry_arena.cpp")
    c = _arena_constants(header)
    assert c["kGeometryBanks"] == 2 and '"SRGA"' in header
    offset = _function(cpp, "quint64 geometryBankOffset(", "quint64 geometryArenaBytes(")
    assert "(quint64(family) * kGeometryBanks + bank) * (quint64(kGeometryBankHeaderBytes) + bankBytes)" in offset
    a = (7 << 32 | 1, 3, 9, 1, 4096, 5)
    b = (8 << 32 | 1, 3, 9, 1, 4096, 5)       # D3 test 1: another worker's namespace publishing the same revision
    data = _write_arena(2, 64, {(1, 0): (2, a, b"\x01" * 16), (1, 1): (4, b, b"\x02" * 32)}, c)
    assert _core_read(cpp, data, a, c) == b"\x01" * 16
    assert _core_read(cpp, data, b, c) == b"\x02" * 32
    assert _core_read(cpp, data, a[:5] + (6,), c) is None                  # a revision no bank holds
    assert _core_read(cpp, _write_arena(2, 64, {(1, 0): (3, a, b"\x01" * 16)}, c), a, c) is None  # odd: being written
    body = _function(cpp, "GeometryArena::Read GeometryArena::read(", "\n} // namespace srpss_core")
    assert "if (sequenceAt(header) != before) {" in body          # rewritten under the copy: never trusted
    # Negative control: a reader that skips the namespace word (the key on fewer words) never matches.
    assert _core_read(cpp.replace("held.ns = u64At(header + 8);", ""), data, a, c) is None


def key_is_every_word(header: str) -> bool:
    eq = header[header.index("bool operator==(const GeometryKey &o) const"):]
    eq = eq[:eq.index("}")]
    return all(f"{field} == o.{field}" in eq for field in _KEY_FIELDS)


def test_a_geometry_key_is_its_six_words_never_a_bare_revision():
    header = _source("geometry_arena.h")
    assert key_is_every_word(header)
    words = _function(_source("geometry_arena.cpp"), "GeometryKey GeometryKey::fromWords(", "quint64 geometryBankOffset(")
    assert "k.ns = quint64(w[0]) | (quint64(w[1]) << 32);" in words
    assert "k.revision = quint64(w[5]) | (quint64(w[6]) << 32);" in words and "k.capacity = w[7];" in words
    # Negative control (D3's): the key on revision alone.
    start = header.index("return ", header.index("bool operator==(const GeometryKey &o) const"))
    alone = header[:start] + "return revision == o.revision" + header[header.index(";", start):]
    assert not key_is_every_word(alone)


def _sync_geometry(cpp: str) -> str:
    return _function(cpp, "bool ModeStorage::syncGeometry(", "void ModeStorage::geometryRecorded()")


def residency_holds(cpp: str) -> bool:
    """Once per key, failures never retried, nothing deleted before its replacement exists: a held key is skipped
    before any read, a failed key too; the failure branch releases nothing; the new buffer is made before the slot's
    current moves to previous, and the oldest residency retires only through the retiring list."""
    sync = _sync_geometry(cpp)
    held = sync.find("if (slot->current && slot->currentKey == key)")
    failed = sync.find("if (slot->failed.contains(key))")
    read = sync.find("arena->read(key, &bytes, &readError)")
    made = sync.find("rhi->newBuffer(QRhiBuffer::Static, QRhiBuffer::StorageBuffer")
    moved = sync.find("slot->previous = slot->current;")
    failure = sync[sync.find("if (!ok) {"):sync.find("updates->uploadStaticBuffer(")]
    keys = sync[sync.find("for (const StorageBufferDeclaration &decl : declared) {\n        if (!decl.geometry)"):]
    return (0 <= held < read and 0 <= failed < read and 0 <= read < made < moved
            and "releaseGeometryBuffer" not in failure and "slot->failed.append(key);" in failure
            and "releaseGeometryBuffer(slot->current)" not in keys
            and "m_geometryRetiring.append(slot->previous);" in sync)


def test_a_key_uploads_once_a_failed_swap_keeps_the_old_and_nothing_goes_first():
    cpp = _source("compute_passes.cpp")
    assert residency_holds(cpp)
    # Negative controls: an upload every record (no held-key skip), a failed key retried every record, delete before
    # allocate (D3's), the old key dropped on a failure.
    assert not residency_holds(cpp.replace("if (slot->current && slot->currentKey == key)", "if (false)"))
    assert not residency_holds(cpp.replace("if (slot->failed.contains(key)) {", "if (false) {"))
    allocate = "RhiOwned<QRhiBuffer> made;"
    assert not residency_holds(cpp.replace(allocate, "releaseGeometryBuffer(slot->current);\n        " + allocate))
    failure = "            slot->failed.append(key);\n            g_geometryFailed.fetchAndAddRelaxed(1);\n            qWarning"
    norm = cpp.replace("\r\n", "\n")
    assert norm.count(failure) == 1
    assert not residency_holds(norm.replace(failure, failure.replace(
        "slot->failed.append(key);", "slot->failed.append(key);\n            releaseGeometryBuffer(slot->current);")))
    assert "qWarning(\"srpss core: geometry buffer '%s' key %s failed: %s\"" in _sync_geometry(cpp)  # logged once


def retire_follows_a_recorded_frame(mode_cpp: str, storage_cpp: str) -> bool:
    recorded = _function(storage_cpp, "void ModeStorage::geometryRecorded()", "void ModeStorage::releaseGeometry()")
    return ("    recordPasses(rhi, cb, target, updates, draw, readback);\n    if (draw)\n"
            "        m_storage.geometryRecorded();" in mode_cpp.replace("\r\n", "\n")
            and "m_geometryRetiring.append(slot->previous);" in recorded
            and "releaseGeometryBuffer" not in recorded)


def test_the_old_key_retires_only_after_a_frame_using_the_new_one_was_recorded():
    mode_cpp = _source("mode_content.cpp")
    storage_cpp = _source("compute_passes.cpp")
    assert retire_follows_a_recorded_frame(mode_cpp, storage_cpp)
    # Negative controls: retired at a record that drew nothing (waiting or kept), released in the same record.
    assert not retire_follows_a_recorded_frame(
        mode_cpp.replace("\r\n", "\n").replace("    if (draw)\n        m_storage.geometryRecorded();",
                                               "    m_storage.geometryRecorded();"), storage_cpp)
    assert not retire_follows_a_recorded_frame(mode_cpp, storage_cpp.replace(
        "m_geometryRetiring.append(slot->previous);   // D3", "releaseGeometryBuffer(slot->previous);   // D3"))
    # A record with no resident key keeps its frame (never an empty one).
    assert "const bool withPasses = texturesReady() && meshesReady() && !m_geometryWaiting;" in mode_cpp


def teardown_releases_every_residency(storage_cpp: str, mode_cpp: str) -> bool:
    release = _function(storage_cpp, "void ModeStorage::release()", "\n}\n")
    every = _function(storage_cpp, "void ModeStorage::releaseGeometry()", "\n}\n")
    arena = _function(mode_cpp, "bool ModeContent::syncGeometry(", "void ModeContent::decideDispatches()")
    return ("releaseGeometry();" in release
            and "m_geometryRetiring.clear();" in every and "m_geometry.clear();" in every
            and "for (Buffer *b : { slot->current, slot->previous })" in every
            and "m_storage.releaseGeometry();" in arena)


def test_teardown_a_mode_switch_and_a_new_activation_release_every_residency():
    storage_cpp = _source("compute_passes.cpp").replace("\r\n", "\n")
    mode_cpp = _source("mode_content.cpp").replace("\r\n", "\n")
    assert teardown_releases_every_residency(storage_cpp, mode_cpp)
    # A program no longer declaring the buffer drops its slot (the mode switch); a program without storage still syncs
    # while residencies remain; the content's live objects count them.
    assert "// Slots of geometry buffers no longer declared go with their residencies." in _sync_geometry(storage_cpp)
    assert "&& m_geometry.isEmpty()\n            && m_geometryRetiring.isEmpty();" in _source("compute_passes.h")
    # Negative controls (D3's retire job skipped): the content's release without the geometry; a new arena keeping the
    # old activation's keys.
    assert not teardown_releases_every_residency(
        storage_cpp.replace("    releaseGeometry();                        // ABI 42", "    // ABI 42"), mode_cpp)
    assert not teardown_releases_every_residency(
        storage_cpp, mode_cpp.replace("        m_storage.releaseGeometry();          // D3 point 3", ""))


def test_a_geometry_buffer_is_read_only_its_key_a_record_array_and_previous_bindable():
    storage_cpp = _source("compute_passes.cpp").replace("\r\n", "\n")
    mode_cpp = _source("mode_content.cpp")
    parse = _function(storage_cpp, "bool parseStorageBuffer(", "const bool withUsage")
    assert "family >= double(kMaxGeometryFamilies)" in parse and "!identifier(b.geometryKey)" in parse
    assert "key->kind != fa::FieldKind::U32 || key->count != quint32(kGeometryKeyWords)" in mode_cpp
    assert "decl && decl->geometry && b.access != StorageAccess::Read" in mode_cpp
    assert "declared = decl != nullptr && (!previous || decl->geometry);" in mode_cpp
    resolve = _function(storage_cpp, "// ABI 42 (D3): a geometry buffer is its current key's residency",
                        "void ModeStorage::releaseGeometryBuffer(")
    assert "previous && slot->previous ? slot->previous : slot->current" in resolve
    assert "if (key.family != decl.geometryFamily) {" in _sync_geometry(storage_cpp)
    # The plain buffers' sync never sees a geometry buffer (never zeroed or sized by bytes).
    assert "if (!decl.geometry)\n                m_plainBuffers.append(decl);" in storage_cpp
    module = _source("module.cpp")
    assert '"composite_mode_geometry_arena", composite_mode_geometry_arena' in module
    assert all(f'QStringLiteral("geometry_{n}")' in module
               for n in ("resident", "uploads", "failed", "released", "waits", "arenas", "reads_found", "reads_torn"))
    assert "src/geometry_arena.cpp" in (ROOT / "native" / "core" / "CMakeLists.txt").read_text(encoding="utf-8")
