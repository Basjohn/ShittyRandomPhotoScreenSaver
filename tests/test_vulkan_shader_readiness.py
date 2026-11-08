"""Port-readiness rule 5 (Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md): compute shaders compile to SPIR-V.

PySide6 ships ``qsb`` (glslang -> SPIR-V), so the rule is enforced by test. The compute shaders written before this
test exist use loose uniforms outside a block (OpenGL-only GLSL); they are listed below and convert per mode as the
Vulkan render core (P3) ports them. A ratchet: every compute shader not listed must compile to SPIR-V, and a listed
one that now compiles must leave the list (so it can never regress)."""
import pytest

from tools.vulkan_shader_readiness import MODULES, _compute_sources, _qsb

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
    "rendering.quick.scene3d.motion._TILE_MAX_COMPUTE",
    "rendering.quick.scene3d.population.POPULATION_SCAN_SOURCE",
    "rendering.quick.scene3d.propagation_field._EXTENT_COMPUTE",
    "rendering.quick.scene3d.propagation_field._HEADER",
    "rendering.quick.scene3d.propagation_field._RELAX_COMPUTE",
    "rendering.quick.visualizer.implementations.extruded_bubble_drift_solver.CHAIN_COMPUTE",
    "rendering.quick.visualizer.implementations.extruded_bubble_drift_solver.CLOUD_COMPUTE",
})


def _compiles(qsb, source, tmp_path, name) -> tuple[bool, str]:
    import subprocess

    path = tmp_path / f"{name}.comp"
    path.write_text(source, encoding="utf-8")
    out = path.with_suffix(".comp.qsb")
    result = subprocess.run([str(qsb), str(path), "-o", str(out)], capture_output=True, text=True, timeout=120)
    text = (result.stdout + result.stderr).strip()
    return out.exists() and "failed" not in text.lower(), text


def test_compute_shaders_compile_to_spirv_or_are_listed_legacy(tmp_path):
    qsb = _qsb()
    if not qsb.exists():
        pytest.skip("this PySide6 has no qsb")
    seen, new_failures, now_compiling = set(), [], []
    for module_name in MODULES:
        for name, source in _compute_sources(module_name).items():
            key = f"{module_name}.{name}"
            seen.add(key)
            ok, text = _compiles(qsb, source, tmp_path, key.replace(".", "_"))
            if not ok and key not in LEGACY_GL_ONLY:
                new_failures.append((key, next((l for l in text.splitlines() if "ERROR" in l), text[:200])))
            if ok and key in LEGACY_GL_ONLY:
                now_compiling.append(key)
    assert len(seen) >= len(LEGACY_GL_ONLY)
    assert not new_failures, f"new compute shaders must be Vulkan GLSL (uniforms in a block): {new_failures}"
    assert not now_compiling, f"these compile now: remove them from LEGACY_GL_ONLY: {now_compiling}"
    assert LEGACY_GL_ONLY <= seen, f"listed shaders no longer exist: {sorted(LEGACY_GL_ONLY - seen)}"


def test_a_loose_uniform_fails_and_a_block_compiles(tmp_path):
    # The rule's two sides on one tiny program: what the legacy shaders do fails; the Vulkan form compiles.
    qsb = _qsb()
    if not qsb.exists():
        pytest.skip("this PySide6 has no qsb")
    head = "#version 460 core\nlayout(local_size_x=8) in;\nlayout(std430, binding=0) buffer B { float v[]; };\n"
    loose = head + "uniform float uGain;\nvoid main(){ v[gl_GlobalInvocationID.x] *= uGain; }\n"
    block = head + ("layout(std140, binding=1) uniform U { float uGain; };\n"
                    "void main(){ v[gl_GlobalInvocationID.x] *= uGain; }\n")
    assert not _compiles(qsb, loose, tmp_path, "loose")[0]
    assert _compiles(qsb, block, tmp_path, "block")[0]
