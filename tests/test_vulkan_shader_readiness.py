"""Port-readiness rule 5 (Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md): compute shaders compile with
``qsb`` for every backend it targets (SPIR-V, GLSL 430 and 310 es, HLSL 5.0, MSL 1.2).

PySide6 ships ``qsb`` (glslang -> SPIR-V -> SPIRV-Cross), so the rule is enforced by test, over every compute source
the tool discovers in the product (never a fixed module list). The compute shaders written before this test exist use
loose uniforms outside a block (OpenGL-only GLSL); they are listed below and convert per mode as the native render
core (P3) ports them. A ratchet: every compute shader not listed must compile, and a listed one that now compiles
must leave the list (so it can never regress)."""
import subprocess

import pytest

from tools.vulkan_shader_readiness import _compute_sources, _qsb, compile_source, compute_modules

#: Compute shader sources that predate the rule (8 Nov 2026) and still use loose uniforms. Only ever shrinks.
LEGACY_GL_ONLY = frozenset({
    "rendering.gl_programs.fog_volume.FOG_INTEGRATE_COMPUTE",
    "rendering.gl_programs.fog_volume._INJECT_HEAD",
    "rendering.gl_programs.waveform_atmosphere.FIELD_COMPUTE",
    "rendering.gl_programs.waveform_floor_give.FLOOR_GIVE_BLUR_COMPUTE",
    "rendering.gl_programs.waveform_floor_give.FLOOR_GIVE_SECTION_COMPUTE",
    "rendering.quick.scene3d.edge_field._BLUR_COMPUTE",
    "rendering.quick.scene3d.edge_field._EDGES_COMPUTE",
    "rendering.quick.scene3d.edge_field._FLOOD_COMPUTE",
    "rendering.quick.scene3d.edge_field._HEADER",
    "rendering.quick.scene3d.edge_field._LUMA_COMPUTE",
    "rendering.quick.scene3d.edge_field._RESOLVE_COMPUTE",
    "rendering.quick.scene3d.population.POPULATION_SCAN_SOURCE",
    "rendering.quick.scene3d.propagation_field._EXTENT_COMPUTE",
    "rendering.quick.scene3d.propagation_field._HEADER",
    "rendering.quick.scene3d.propagation_field._RELAX_COMPUTE",
})


def _require_qsb():
    qsb = _qsb()
    if not qsb.exists():
        pytest.skip("this PySide6 has no qsb")
    return qsb


def test_compute_shaders_compile_for_every_target_or_are_listed_legacy(tmp_path):
    qsb = _require_qsb()
    seen, new_failures, now_compiling = set(), [], []
    for module_name in compute_modules():
        for name, source in _compute_sources(module_name).items():
            key = f"{module_name}.{name}"
            seen.add(key)
            ok, error = compile_source(qsb, source, tmp_path / f"{key.replace('.', '_')}.comp")
            if not ok and key not in LEGACY_GL_ONLY:
                new_failures.append((key, error))
            if ok and key in LEGACY_GL_ONLY:
                now_compiling.append(key)
    assert len(seen) > len(LEGACY_GL_ONLY)
    assert not new_failures, f"new compute shaders must be Vulkan GLSL for every qsb target: {new_failures}"
    assert not now_compiling, f"these compile now: remove them from LEGACY_GL_ONLY: {now_compiling}"
    assert LEGACY_GL_ONLY <= seen, f"listed shaders no longer exist: {sorted(LEGACY_GL_ONLY - seen)}"


def test_compute_sources_are_discovered_not_listed():
    modules = compute_modules()
    # Every module the scan finds holds a compute source, and the ones this rule was written for are among them.
    assert all(_compute_sources(module) for module in modules)
    assert {key.rsplit(".", 1)[0] for key in LEGACY_GL_ONLY} <= set(modules)
    assert "rendering.quick.visualizer.implementations.extruded_bubble_drift_solver" in modules


def test_a_loose_uniform_fails_and_a_block_compiles(tmp_path):
    # The rule's two sides on one tiny program: what the legacy shaders do fails; the Vulkan form compiles.
    qsb = _require_qsb()
    head = "#version 460 core\nlayout(local_size_x=8) in;\nlayout(std430, binding=0) buffer B { float v[]; };\n"
    loose = head + "uniform float uGain;\nvoid main(){ v[gl_GlobalInvocationID.x] *= uGain; }\n"
    block = head + ("layout(std140, binding=1) uniform U { float uGain; };\n"
                    "void main(){ v[gl_GlobalInvocationID.x] *= uGain; }\n")
    assert not compile_source(qsb, loose, tmp_path / "loose.comp")[0]
    assert compile_source(qsb, block, tmp_path / "block.comp")[0]


def test_every_target_is_checked_not_only_spirv(tmp_path):
    # A 64-bit float compiles to SPIR-V alone (qsb with no target), yet GLSL ES, HLSL 5.0 and MSL refuse it.
    qsb = _require_qsb()
    source = ("#version 460 core\nlayout(local_size_x=8) in;\nlayout(std430, binding=0) buffer B { double v[]; };\n"
              "layout(std140, binding=1) uniform U { double uGain; };\n"
              "void main(){ v[gl_GlobalInvocationID.x] *= uGain; }\n")
    path = tmp_path / "fp64.comp"
    path.write_text(source, encoding="utf-8")
    spirv = subprocess.run([str(qsb), str(path), "-o", str(tmp_path / "spirv.qsb")], capture_output=True, text=True)
    assert spirv.returncode == 0 and (tmp_path / "spirv.qsb").exists()
    assert not compile_source(qsb, source, tmp_path / "fp64_all.comp")[0]
