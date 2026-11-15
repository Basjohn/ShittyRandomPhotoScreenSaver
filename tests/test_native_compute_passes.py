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
