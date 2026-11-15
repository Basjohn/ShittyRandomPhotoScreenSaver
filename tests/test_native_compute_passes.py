"""N3.3 (D16, compute passes; ``native/core/src/compute_passes.h``): GPU-free checks of the Python face, the sources and
the core's kernels. The GPU proof is ``native/core/python/compute_pass_check.py`` (hidden host, both backends)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core" / "src"
SHADERS = ROOT / "native" / "core" / "shaders"


# --------------------------------------------------------------------------------------------- the Python face

def test_a_compute_program_declares_its_storage_and_entries_in_pass_order():
    from rendering.native.mode import (ComputeBinding, ComputePass, ModePass, PassGeometry, PassSampler,
                                       RecordLayout, MeshAttribute, StorageBuffer, StorageImage, program_json)

    layout = RecordLayout(16, (MeshAttribute("aState", 4, 0),))
    buffers = (StorageBuffer("state", 4096, layout=layout), StorageBuffer("commands", "command_bytes", indirect=True))
    images = (StorageImage("field", (64, 8), "rgba32f"), StorageImage("fog", (16, 9, 4), "r16f"))
    entry = ComputePass("advance", b"C", bindings=(ComputeBinding("State", "state", "buffer", "read_write"),
                                                    ComputeBinding("uField", "field", "image", "write")),
                        groups=(4, "rows", 1), trigger="step_serial")
    over = ComputePass("fog", b"F", bindings=(ComputeBinding("uFog", "fog", "image", "write"),), over="fog")
    draw = ModePass("draw", b"P", samplers=(PassSampler("uFog", "fog"),),
                    geometry=PassGeometry(b"V", instance_from="state", vertices=4, topology="triangle_strip"))
    declared, packs = program_json((entry, over, draw), buffers=buffers, images=images)
    program = json.loads(declared)
    assert [p["name"] for p in program["passes"]] == ["advance", "fog", "draw"]
    assert packs == [b"C", b"F", b"P", b"V"]          # a compute entry's one pack, then the draw's fragment and vertex
    first = program["passes"][0]
    assert first["compute"] is True and first["trigger"] == {"field": "step_serial"}
    assert first["groups"] == [4, "rows", 1]
    assert first["bindings"][0] == {"name": "State", "buffer": "state", "access": "read_write"}
    assert program["passes"][1]["groups"] == {"over": "fog"} and program["passes"][1]["trigger"] == "frame"
    assert program["buffers"][0]["usage"] == ["vertex"] and program["buffers"][0]["layout"]["stride"] == 16
    assert program["buffers"][1] == {"name": "commands", "bytes": "command_bytes", "usage": ["indirect"]}
    assert program["images"][1] == {"name": "fog", "dimensions": 3, "format": "r16f", "size": [16, 9, 4]}
    # A program without storage declares none (N3.2's declaration as it was).
    assert "buffers" not in json.loads(program_json((draw,))[0])


def test_the_python_face_refuses_what_the_core_would():
    from rendering.native.mode import ComputeBinding, ComputePass, StorageBuffer, StorageImage

    with pytest.raises(ValueError):
        StorageBuffer("b", 6)                                    # not a multiple of 4
    with pytest.raises(ValueError):
        StorageImage("i", (4,))                                  # one side
    with pytest.raises(ValueError):
        StorageImage("i", (4, 4), "rgb10a2")                     # no such format
    with pytest.raises(ValueError):
        ComputeBinding("s", "stream", "stream", "write")         # a stream is read only
    with pytest.raises(ValueError):
        ComputeBinding("s", "x", "buffer", "readwrite")          # no such access
    with pytest.raises(ValueError):
        ComputePass("c", b"", groups=(1, 1, 1), over="b")        # groups or over, not both
    with pytest.raises(ValueError):
        ComputePass("c", b"")                                    # neither


def test_the_lost_edge_splits_textures_from_state():
    from rendering.native.mode import NativeMode

    class Module:
        listener = None

        def composite_mode_on_lost(self, handle, callback):
            Module.listener = callback

    class Composite:
        def _live(self):
            return 1

    mode = NativeMode(Module(), Composite())
    textures: list = []
    state: list = []
    mode.on_textures_lost(textures.extend)
    mode.on_state_lost(state.extend)
    Module.listener(["photo", "state:drift", "state:fog"])
    assert textures == ["photo"] and state == ["drift", "fog"]
    mode.on_textures_lost(None)
    mode.on_state_lost(None)
    assert Module.listener is None                               # no owner: no listener left in the core


# --------------------------------------------------------------------------------------------- the sources

def test_the_core_member_and_the_abi():
    from rendering.native.loader import EXPECTED_ABI
    from rendering.native.mode import MODE_CORE_MEMBERS

    source = (CORE / "mode_content.cpp").read_text(encoding="utf-8")
    rows = dict(re.findall(r'\{ "(\w+)", (\d+), (?:true|false), \w+ \},', source))
    assert MODE_CORE_MEMBERS["u_srpss_compute"][0] == int(rows["u_srpss_compute"]) == 4
    assert (CORE / "compute_passes.cpp").read_text(encoding="utf-8").count('kComputeMember[] = "u_srpss_compute"') == 1
    # N3.3's entries came with ABI 19; a later ABI (N3.4's 20) keeps them (the history line stays in abi.h).
    abi = (CORE / "abi.h").read_text(encoding="utf-8")
    assert "// 19 (N3.3, compute passes;" in abi
    assert EXPECTED_ABI >= 19
    assert f"#define SRPSS_NATIVE_CORE_ABI {EXPECTED_ABI}" in abi
    module = (CORE / "module.cpp").read_text(encoding="utf-8")
    for entry in ("composite_mode_image_size", "composite_mode_storage_read", "composite_mode_storage_data",
                  "compute_control"):
        assert f'{{ "{entry}", {entry}, METH_VARARGS,' in module, entry


def test_the_core_records_one_qrhi_compute_pass_per_entry_and_never_a_barrier_of_its_own():
    """D16 choice A and point 3: every compute pass the core begins is ended in the same function before another
    entry (the single-pass control aside), and no raw barrier call exists anywhere in the core."""
    for name in ("compute_passes.cpp", "mode_content.cpp"):
        text = (CORE / name).read_text(encoding="utf-8")
        assert "glMemoryBarrier" not in text and "vkCmdPipelineBarrier" not in text, name
        assert text.count("beginComputePass(") >= 1, name
    content = (CORE / "mode_content.cpp").read_text(encoding="utf-8")
    body = content[content.index("void ModeContent::recordCompute("):content.index("bool ModeContent::build(")]
    assert "if (!computeSinglePass()) {\n        cb->endComputePass();" in body


def _body(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end, text.index(start))]


def test_a_program_without_storage_releases_the_last_programs_buffers():
    """Checkpoint audit 5 M1: the content's early return ("nothing declared, nothing held") counts the buffers a program
    without storage replaced and the kernels, so the next record's sync releases them (a resize's delayed release)."""
    header = (CORE / "compute_passes.h").read_text(encoding="utf-8")
    empty = re.search(r"bool empty\(\) const \{([^}]*)\}", header).group(1)
    assert "m_retiring" in empty and "m_clear" in empty and "holds()" in empty
    content = (CORE / "mode_content.cpp").read_text(encoding="utf-8")
    sync = _body(content, "bool ModeContent::syncStorage(", "void ModeContent::decideDispatches(")
    assert "m_storage.empty())\n        return true;" in sync
    assert "!m_storage.empty()" not in sync                      # "held" is declared resources: holds()


def test_fresh_is_per_entry_and_a_new_program_keeps_each_entrys_history():
    """Checkpoint audit 5 M2: an entry is fresh from its own storage bindings' serials (a prefix copy keeps its
    source's), never from a content-wide generation, and a new program keeps the track of each entry it names again."""
    content = (CORE / "mode_content.cpp").read_text(encoding="utf-8")
    decide = _body(content, "void ModeContent::decideDispatches(", "quint64 ModeContent::entryFreshKey(")
    assert "m_freshGeneration" not in decide and "entryFreshKey(pass)" in decide
    sync = _body(content, "bool ModeContent::syncStorage(", "void ModeContent::decideDispatches(")
    assert "retrackCompute(program)" in sync and "t = ComputeTrack()" not in sync
    retrack = _body(content, "void ModeContent::retrackCompute(", "void ModeContent::recordCompute(")
    assert "old.name != pass.name" in retrack and "t = old;" in retrack
    storage = (CORE / "compute_passes.cpp").read_text(encoding="utf-8")
    sync = _body(storage, "bool ModeStorage::sync(", "bool ModeStorage::ensureKernels(")
    assert "b->fresh = m->existing->fresh;" in sync and sync.count("++m_freshSerial") == 2


def test_one_resource_bound_twice_with_two_accesses_is_refused_with_its_reason():
    """Checkpoint audit 5 M3, and its harness case (the facts round expects it refused)."""
    content = (CORE / "mode_content.cpp").read_text(encoding="utf-8")
    assert "earlier.resource == binding.resource && earlier.access != binding.access" in content
    import sys

    sys.path.insert(0, str(ROOT / "native" / "core" / "python"))
    import compute_passes

    packs = {name: b"" for name in compute_passes.shaders()}
    programs = compute_passes.refusal_programs(packs)
    twice = [label for label, (entry, _b, _i) in programs.items()
             if len({(b.kind, b.resource) for b in entry.bindings}) < len(entry.bindings)]
    assert len(twice) == 1 and twice[0] != "accepted"
    entry = programs[twice[0]][0]
    accesses = {}
    for b in entry.bindings:
        accesses.setdefault((b.kind, b.resource), set()).add(b.access)
    assert any(len(a) == 2 for a in accesses.values())


def test_the_storage_sync_allocates_nothing_when_everything_is_kept():
    """Checkpoint audit 5 L1: the record's sync returns before any list is built when every declaration is kept, and
    the left-behind control's mutex is taken only while it left anything."""
    storage = (CORE / "compute_passes.cpp").read_text(encoding="utf-8")
    sync = _body(storage, "bool ModeStorage::sync(", "bool ModeStorage::ensureKernels(")
    assert sync.index("if (unchanged(buffers, images, settings))") < sync.index("QList<quint32> sizes;")
    unchanged = _body(storage, "bool ModeStorage::unchanged(", "void ModeStorage::releaseBuffer(")
    assert "QList" not in unchanged.split("{", 1)[1] and "QString" not in unchanged
    left = _body(storage, "void releaseLeftBehind(", "} // namespace")
    assert left.index("g_leftBehindCount.loadAcquire() == 0") < left.index("QMutexLocker")


def test_storage_images_have_a_byte_bound_and_their_format_is_checked_when_made():
    """Checkpoint audit 5 L3 and L4: an image's bytes are bounded as a buffer's; its format is asked only of an image
    to be made, from the Vulkan facts the core read at device creation; the local size meets the device's limits."""
    header = (CORE / "compute_passes.h").read_text(encoding="utf-8")
    assert re.search(r"kMaxStorageImageBytes = qint64\(\d+\) << 20;", header)
    storage = (CORE / "compute_passes.cpp").read_text(encoding="utf-8")
    fits = _body(storage, "bool storageImageSizeFits(", "bool parseStorageImage(")
    assert "kMaxStorageImageBytes" in fits
    sync = _body(storage, "bool ModeStorage::sync(", "bool ModeStorage::ensureKernels(")
    assert "isTextureFormatSupported" not in sync and "storageImageUsable(rhi, decl)" in sync
    usable = _body(storage, "bool storageImageUsable(", "} // namespace")
    assert "vulkanDeviceFacts(" in usable and '"storage_image_formats"' in usable
    content = (CORE / "mode_content.cpp").read_text(encoding="utf-8")
    build = _body(content, "bool ModeContent::build(", "const QShader vs = ")
    for limit in ("MaxThreadGroupX", "MaxThreadGroupY", "MaxThreadGroupZ", "MaxThreadsPerThreadGroup"):
        assert limit in build, limit


def test_the_pair_check_scene_judges_as_the_product_and_its_control_differs():
    """Checkpoint audit 5 M4: the harness's pair-check kernel is the product's verbatim, its broken twin differs, and
    the report the harness judges it by tells exact arithmetic from lost error terms."""
    import sys

    import numpy as np

    sys.path.insert(0, str(ROOT / "native" / "core" / "python"))
    import compute_passes
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import PROGRAMS, pair_check_cases

    source, broken = compute_passes.pair_check_sources()
    assert source == PROGRAMS[2][1] and broken != source and "precise" in source
    cases, expected = pair_check_cases()
    record = compute_passes.pair_check_record()
    assert record["case_floats"] == cases.size and len(record["case_rows"]) == 4 * cases.size
    exact = np.zeros((len(cases), 4), np.float32)
    exact[:, 0], exact[:, 1], exact[:, 2] = expected["fraction"], expected["product"], expected["sum"]
    assert compute_passes.pair_check_report(exact.tobytes())["exact"]
    lost = exact.copy()
    lost[:, 1:3] = 0.0                                          # what zeroed error terms leave
    report = compute_passes.pair_check_report(lost.tobytes())
    assert not report["exact"] and report["product_mismatches"] and report["sum_mismatches"]


def test_the_kernels_are_shaders_the_cmake_bake_finds():
    cmake = (ROOT / "native" / "core" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert '"${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.comp"' in cmake
    assert "src/compute_passes.cpp" in cmake
    for name in ("storage_clear.comp", "storage_copy.comp"):
        text = (SHADERS / name).read_text(encoding="utf-8")
        assert text.startswith("#version 440") and "local_size_x = 256" in text, name
    assert "kStorageKernelGroup = 256" in (CORE / "compute_passes.h").read_text(encoding="utf-8")


def test_the_kernels_bake_with_qsb_for_every_shipped_target(tmp_path):
    """The two kernels bake as CMake bakes them (SPIR-V, GLSL 430, HLSL 5.0, MSL 1.2), so the module's build cannot
    fail on them; their reflected qualifiers are read by the harness on the built module."""
    import subprocess

    import PySide6

    qsb = Path(PySide6.__file__).parent / "qsb.exe"
    if not qsb.exists():
        pytest.skip("PySide6's qsb is not installed here")
    for name in ("storage_clear.comp", "storage_copy.comp"):
        out = tmp_path / (name + ".qsb")
        result = subprocess.run([str(qsb), "--glsl", "430", "--hlsl", "50", "--msl", "12", "-o", str(out),
                                 str(SHADERS / name)], capture_output=True, text=True, timeout=120)
        text = result.stdout + result.stderr
        assert result.returncode == 0 and out.exists() and "failed" not in text.lower(), text
