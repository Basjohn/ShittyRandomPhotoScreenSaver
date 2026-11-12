"""Port-readiness rule 5 (Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md): compute shaders compile with
``qsb`` for every shipped backend's target (SPIR-V, GLSL 430, HLSL 5.0, MSL 1.2; GLSL 310 es is loaded by no backend
we ship and is not baked, lead's decision 12 Nov 2026).

PySide6 ships ``qsb`` (glslang -> SPIR-V -> SPIRV-Cross), so the rule is enforced by test, over every compute source
the tool discovers in the product (never a fixed module list). There are no exceptions: the 18 loose-uniform sources
that predated the rule (8 Nov 2026) were converted by D4 and N1.2 (12 Nov 2026), each bit-identical in OpenGL
(``tools/compute_pass_identity.py``), and the exception list was removed with the last of them, so a compute source
that does not bake for every target fails here, with no list to add it to."""
import subprocess

import pytest

from tools.vulkan_shader_readiness import (
    QSB_TARGETS,
    _compute_sources,
    _qsb,
    compile_source,
    compute_modules,
    qsb_targets,
)

# The modules whose compute sources this rule was written for (they must stay discovered, so a scan that silently
# stopped finding them cannot pass vacuously).
_CONVERTED_MODULES = frozenset({
    "rendering.gl_programs.fog_volume",
    "rendering.gl_programs.waveform_atmosphere",
    "rendering.gl_programs.waveform_floor_give",
    "rendering.quick.scene3d.edge_field",
    "rendering.quick.scene3d.motion",
    "rendering.quick.scene3d.population",
    "rendering.quick.scene3d.propagation_field",
    "rendering.quick.visualizer.implementations.extruded_bubble_drift_solver",
})


def _require_qsb():
    qsb = _qsb()
    if not qsb.exists():
        pytest.skip("this PySide6 has no qsb")
    return qsb


def test_every_compute_shader_compiles_for_every_target(tmp_path):
    qsb = _require_qsb()
    seen, failures = set(), []
    for module_name in compute_modules():
        for name, source in _compute_sources(module_name).items():
            key = f"{module_name}.{name}"
            seen.add(key)
            ok, error = compile_source(qsb, source, tmp_path / f"{key.replace('.', '_')}.comp")
            if not ok:
                failures.append((key, error))
    assert len(seen) >= len(_CONVERTED_MODULES)
    assert not failures, f"compute shaders must be Vulkan GLSL for every qsb target (no exceptions): {failures}"


def test_compute_sources_are_discovered_not_listed():
    modules = compute_modules()
    # Every module the scan finds holds a compute source, and the ones this rule was written for are among them.
    assert all(_compute_sources(module) for module in modules)
    assert _CONVERTED_MODULES <= set(modules)


def test_the_required_targets_are_the_shipped_backends():
    # SPIR-V is qsb's default; the rest are GLSL 430, HLSL 5.0 and MSL 1.2. GLSL ES is baked by no target we ship.
    assert QSB_TARGETS == ("--glsl", "430", "--hlsl", "50", "--msl", "12")
    assert not any("es" in arg.split() for arg in QSB_TARGETS)


def test_a_format_a_target_rejects_fails_and_r16f_compiles_for_the_shipped_targets(tmp_path):
    # A storage-image format one target rejects fails the bake (here GLSL ES 3.1, which has no r16f image: the reason
    # N1.2 widened the scalar half-float images), so a target that rejects a format cannot pass silently. The shipped
    # targets accept r16f, which is why those images went back to R16F.
    qsb = _require_qsb()
    source = ("#version 460 core\nlayout(local_size_x=8) in;\nlayout(FORMAT, binding=0) writeonly uniform image2D i;\n"
              "void main(){ imageStore(i, ivec2(gl_GlobalInvocationID.xy), vec4(1.0)); }\n")
    r16f = source.replace("FORMAT", "r16f")
    assert not compile_source(qsb, r16f, tmp_path / "r16f_es.comp", qsb_targets(glsl="430,310 es"))[0]
    assert compile_source(qsb, r16f, tmp_path / "r16f.comp")[0]
    assert compile_source(qsb, source.replace("FORMAT", "rgba16f"), tmp_path / "rgba16f.comp")[0]


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
    # A 64-bit float compiles to SPIR-V alone (qsb with no target), yet HLSL 5.0 and MSL refuse it.
    qsb = _require_qsb()
    source = ("#version 460 core\nlayout(local_size_x=8) in;\nlayout(std430, binding=0) buffer B { double v[]; };\n"
              "layout(std140, binding=1) uniform U { double uGain; };\n"
              "void main(){ v[gl_GlobalInvocationID.x] *= uGain; }\n")
    path = tmp_path / "fp64.comp"
    path.write_text(source, encoding="utf-8")
    spirv = subprocess.run([str(qsb), str(path), "-o", str(tmp_path / "spirv.qsb")], capture_output=True, text=True)
    assert spirv.returncode == 0 and (tmp_path / "spirv.qsb").exists()
    assert not compile_source(qsb, source, tmp_path / "fp64_all.comp")[0]
