"""Port-readiness rule 5 (Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md): every shader the product renders
with compiles with ``qsb`` for every shipped backend's target (SPIR-V, GLSL 430, HLSL 5.0, MSL 1.2; GLSL ES is loaded
by no backend we ship and is not baked, lead's decision 12 Nov 2026).

PySide6 ships ``qsb`` (glslang -> SPIR-V -> SPIRV-Cross), so the rule is enforced by test over every source the tool
discovers (N1.3): shader files, module-level sources, program classes' sources, and the sources composers build at
runtime with the product's own arguments (the population count/scatter programs, the composed fog medium, the
propagation seed). Nothing is listed by hand except today's failures.

The ratchet: the sources that did not bake when the check was widened to every stage (12 Nov 2026) are listed below,
grouped in N5's porting order. The list only shrinks: a listed source that bakes fails the test until it is removed,
and a source that is not listed and does not bake fails the test (convert it, never list it). The module-level compute
sources that D4 and N1.2 converted stay outside the list (no exceptions there), and since N1.6 converted the last
composed one (the Capillary propagation seed) no compute source is on it."""
import ast
import subprocess

import pytest

from tools.vulkan_shader_readiness import (
    GROUPS,
    QSB_TARGETS,
    ROOT,
    _compute_sources,
    _qsb,
    check,
    compile_source,
    compute_modules,
    discover,
    group_of,
    qsb_targets,
    stage_of,
    static_causes,
)

# The modules whose compute sources the compute rule was written for (they must stay discovered, so a scan that
# silently stopped finding them cannot pass vacuously).
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

# The composers whose runtime sources N1.3 brought under the check (they must keep producing discovered sources).
_RUNTIME_COMPOSERS = (
    "rendering.quick.scene3d.population.population_programs(",
    "rendering.quick.scene3d.propagation_field.PropagationField(",
)


def _require_qsb():
    qsb = _qsb()
    if not qsb.exists():
        pytest.skip("this PySide6 has no qsb")
    return qsb


@pytest.fixture(scope="module")
def rows():
    _require_qsb()
    return check(discover()[0])


def test_every_shader_source_bakes_or_is_on_the_ratchet(rows):
    failing = {row["key"]: row["error"] for row in rows if not row["compiles"]}
    listed = {key for keys in _RATCHET.values() for key in keys}
    new = {key: error for key, error in failing.items() if key not in listed}
    fixed = sorted(listed - set(failing))
    assert not new, f"these sources do not bake for every qsb target (make them Vulkan GLSL; never list them): {new}"
    assert not fixed, f"these listed sources bake now (or are gone): remove them from the ratchet: {fixed}"


def test_the_ratchet_is_grouped_by_mode_in_n5_order():
    order = [name for name, _ in GROUPS]
    assert list(_RATCHET) == [name for name in order if name in _RATCHET]
    owners = {source.key: source.module for source in discover()[0]}
    keys = [key for values in _RATCHET.values() for key in values]
    assert len(keys) == len(set(keys))
    for group, values in _RATCHET.items():
        for key in values:
            assert key in owners, f"{key} is not a discovered source"
            assert group_of(owners[key]) == group, f"{key} belongs to {group_of(owners[key])}, not {group}"


def test_no_compute_source_is_on_the_ratchet():
    # D4 and N1.2 converted every module-level compute source, and N1.6 the last composed one N1.3 found (the
    # Capillary propagation seed): every compute source the scan discovers bakes, and none is listed.
    stages = {source.key: source.stage for source in discover()[0]}
    assert any(stage == "comp" and "(" in key for key, stage in stages.items())   # composed ones are discovered
    listed_compute = [key for values in _RATCHET.values() for key in values if stages.get(key) == "comp"]
    assert not listed_compute


def test_every_stage_and_every_kind_of_source_is_discovered():
    sources, _ = discover()
    stages = {source.stage for source in sources}
    assert {"vert", "frag", "comp", "geom"} <= stages
    keys = [source.key for source in sources]
    shader_files = sorted(path.relative_to(ROOT).as_posix() for package in ("rendering", "widgets")
                          for suffix in ("*.vert", "*.frag") for path in (ROOT / package).rglob(suffix))
    assert shader_files and set(shader_files) <= set(keys)
    assert any(".fragment_source" in key for key in keys), "program classes' properties are read"
    for composer in _RUNTIME_COMPOSERS:
        assert any(key.startswith(composer) for key in keys), f"{composer} is not evaluated"
    # The composed fog medium Waveform injects is composed once at module level since N1.6 (its portable form), and
    # checked there as a compute source.
    stage = {source.key: source.stage for source in sources}
    assert stage.get("rendering.gl_programs.waveform_atmosphere.MEDIUM_INJECT_SOURCE") == "comp"
    # One identity per text: an imported or re-exported source is its owner's.
    assert len({source.text for source in sources}) == len(sources)


def test_every_composer_call_site_is_resolved_swept_or_forwarded():
    _, sites = discover()
    assert sites
    unresolved = [site for site in sites if site.status.startswith("unresolved")]
    assert not unresolved, f"a composed shader whose arguments cannot be resolved is never checked: {unresolved}"
    # A composition forwarded from a method's parameters must also be called with the product's own text somewhere.
    resolved = {site.composer for site in sites if site.status in ("resolved", "swept")}
    for site in sites:
        if site.status == "forwarded":
            assert site.composer in resolved, f"{site.composer} is only ever forwarded ({site.caller})"


def test_no_shader_is_built_where_discovery_cannot_see_it():
    # A '#version' literal lives at module level, in a class body or property, or in a module-level function
    # (a composer, evaluated at its call sites). One in a plain method would be compiled unseen.
    hidden = []
    for path in sorted((ROOT / "rendering").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for top in tree.body:
            if not isinstance(top, ast.ClassDef):
                continue
            for member in ast.walk(top):
                if not isinstance(member, ast.FunctionDef):
                    continue
                if any(isinstance(d, ast.Name) and d.id == "property" for d in member.decorator_list):
                    continue
                if any(isinstance(leaf, ast.Constant) and isinstance(leaf.value, str) and "#version" in leaf.value
                       and leaf.value.lstrip().startswith("#version") for leaf in ast.walk(member)):
                    hidden.append(f"{path.relative_to(ROOT)}:{member.lineno} {top.name}.{member.name}")
    assert not hidden, hidden


def test_stage_comes_from_the_text():
    assert stage_of("#version 460\nlayout(local_size_x=8) in;\nvoid main(){}") == "comp"
    assert stage_of("#version 460\nvoid main(){ gl_Position = vec4(0.0); }") == "vert"
    assert stage_of("#version 460\nvoid main(){ gl_Position = vec4(0.0); EmitVertex(); }") == "geom"
    assert stage_of("#version 460\nout vec4 c;\nvoid main(){ c = gl_FragCoord; }") == "frag"


def test_the_census_reads_every_cause_a_source_holds():
    source = ("#version 460 core\nin vec2 vUv;\nlayout(location = 0) out vec4 FragColor;\nuniform float uGain;\n"
              "layout(binding = 0) uniform sampler2D uA;\nlayout(std140, binding = 0) uniform B { float b; };\n"
              "uniform sampler2D uB;\nvoid main(){ FragColor = texture(uA, gl_FragCoord.xy * uGain) * b; }\n")
    assert static_causes(source, "frag") == {"loose uniforms": 1, "binding missing": 1, "in/out location missing": 1,
                                             "binding collisions": 1, "gl_FragCoord conventions": 1}
    clean = ("#version 460 core\nlayout(location = 0) in vec2 vUv;\nlayout(location = 0) out vec4 FragColor;\n"
             "layout(binding = 1) uniform sampler2D uA;\nlayout(std140, binding = 0) uniform B { float b; };\n"
             "void main(){ FragColor = texture(uA, vUv) * b; }\n")
    assert static_causes(clean, "frag") == {}
    assert static_causes("#version 460\nvoid main(){ gl_Position = vec4(float(gl_VertexID)); }", "vert") == {
        "OpenGL-only built-ins": 1}


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


def test_a_fragment_stage_is_baked_as_one(tmp_path):
    # The stage is the file suffix: an unlocated varying fails as a fragment shader, a located one bakes.
    qsb = _require_qsb()
    body = "layout(location = 0) out vec4 FragColor;\nvoid main(){ FragColor = vec4(vUv, 0.0, 1.0); }\n"
    assert not compile_source(qsb, "#version 460 core\nin vec2 vUv;\n" + body, tmp_path / "loose.frag")[0]
    assert compile_source(qsb, "#version 460 core\nlayout(location = 0) in vec2 vUv;\n" + body,
                          tmp_path / "located.frag")[0]


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


# The sources that did not bake on 12 Nov 2026 (N1.3), in N5's order. Only ever shrinks.
_RATCHET = {
    "Extruded Bubble": (
        "rendering.gl_programs.extruded_bubble_program.BEAD_VERTEX",
        "rendering.gl_programs.extruded_bubble_program.BUBBLE_FRAGMENT",
        "rendering.gl_programs.extruded_bubble_program.BUBBLE_VERTEX",
        "rendering.gl_programs.extruded_bubble_program.CLUSTER_FRAGMENT",
        "rendering.gl_programs.extruded_bubble_program.CLUSTER_VERTEX",
        "rendering.gl_programs.extruded_bubble_program.NEAR_CLUSTER_FRAGMENT",
        "rendering.gl_programs.extruded_bubble_program.NEAR_FRAGMENT",
        "rendering.gl_programs.extruded_bubble_program.PARTICLE_FRAGMENT",
        "rendering.gl_programs.extruded_bubble_program.PARTICLE_VERTEX",
        "rendering.gl_programs.extruded_bubble_program.SPECK_VERTEX",
        "rendering.gl_programs.extruded_bubble_program.TRAIL_FRAGMENT",
        "rendering.gl_programs.extruded_bubble_program.TRAIL_VERTEX",
        # Not a loose uniform: SPIRV-Cross has no HLSL for the layered write (gl_Layer); converts at its port.
        "rendering.quick.scene3d.probe._PREFILTER_GEOMETRY",
    ),
    "Neon Lake": (
        "rendering.gl_programs.neon_lake_basin_program.NEON_FRAGMENT_SOURCE",
        "rendering.gl_programs.neon_lake_basin_program.NEON_SKYLINE_FRAGMENT_SOURCE",
        "rendering.gl_programs.neon_lake_basin_program.NEON_SKYLINE_VERTEX_SOURCE",
        "rendering.gl_programs.neon_lake_basin_program.NEON_SKY_FRAGMENT_SOURCE",
        "rendering.gl_programs.neon_lake_basin_program.NEON_SKY_VERTEX_SOURCE",
        "rendering.gl_programs.neon_lake_basin_program.NEON_VERTEX_SOURCE",
        "rendering.quick.scene3d.shafts._DOWNSAMPLE_FRAGMENT",
        "rendering.quick.scene3d.shafts._DOWNSAMPLE_SAMPLES_FRAGMENT",
        "rendering.quick.scene3d.shafts._GATHER_FRAGMENT",
    ),
    "Extruded Spectrum": (
        "rendering.gl_programs.extruded_spectrum_program.EXTRUDED_FRAGMENT_SOURCE",
        "rendering.gl_programs.extruded_spectrum_program.EXTRUDED_VERTEX_SOURCE",
    ),
    "Sphere": (
        "rendering.quick.visualizer.implementations.sphere_voxel._FRAGMENT_SOURCE",
        "rendering.quick.visualizer.implementations.sphere_voxel._SHADOW_FRAGMENT_SOURCE",
        "rendering.quick.visualizer.implementations.sphere_voxel._VERTEX_SOURCE",
    ),
    "Quick hosts and materials": (
        "rendering.quick.visualizer.clip_host._FRAGMENT_SOURCE",
        "rendering.quick.visualizer.clip_host._VERTEX_SOURCE",
    ),
}
