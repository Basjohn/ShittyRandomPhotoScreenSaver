"""N3.3's harness scenes (Current_Plan.md item 8b, N3.3; decision D16; ``native/core/src/compute_passes.h``): compute
entries, storage buffers and images, and the draws that read them, as data, harness-only and never registered (like
``mesh_buffers`` and ``scene_targets``). Each scene is a program on one item bound to a frame stream of its own schema (a
mode code outside ``packet_abi.MODE_CODES``); most draw into a surface-sized RGBA8 scene target ``scene`` the harness
reads back, and every storage resource is read back by the harness only (``NativeMode.read_storage``). The Python
reference runs the same compute text in the production GL host (``compute.py``'s calls: ``glDispatchCompute``,
``glBindImageTexture``, ``glMemoryBarrier``).

Every input value is a dyadic rational a few bits wide, so each sum and product the shaders make is exact in float32
(and in half floats for the volume): rule (a) and rule (b) are exact by construction, and any difference is a defect,
reported with its ULP distance.

- ``field``: Waveform's body field: a storage stream (the knots) in, a 2D RGBA32F image out (``groups`` over the image),
  a fullscreen pass sampling it (a draw reading what the next record's compute writes: research Q7).
- ``chain``: the floor give field: sections (store) then a blur that reads them by ``imageLoad`` (a group count from a
  setting), a pass sampling the blur.
- ``volume``: the fog: inject writes a 3D RGBA16F and a 3D R16F image, integrate reads the first by ``imageLoad`` and
  writes a 3D RGBA16F image along z, a pass samples it through ``sampler3D``.
- ``state``: the drift's shape: one persistent read-write state buffer advanced only when the record's ``step`` changes,
  two entries writing disjoint halves of one shared output (write-after-write), sized by a setting (a resize keeps the
  prefix), the output drawn as per-instance input; the shader records ``u_srpss_compute`` so the trigger is read back.
- ``population``: the compacted population's own product shaders (``rendering/quick/scene3d/population.py``): count,
  scan and scatter, the command drawn by ``drawIndirect``, the vertex stage reading ids and states; ``population_direct``
  draws the same members directly (the indirect draw's equal).
- ``war``: write-after-read: entry 1 reads X and writes Y, entry 2 writes X (two QRhi passes: clean; the single-pass
  control: the hazard QRhi does not barrier).
- ``war_pingpong``: write-after-read's other form (checkpoint audit 5 M4): two buffers, a ping-pong; entry 1 reads A
  and writes B, entry 2 reads B and writes A (A's write after entry 1's read), each a counter one past what it read.
- ``pair_check``: D4's pair-check kernel (``extruded_bubble_drift_solver.PROGRAMS[2]``, verbatim, ``precise``) baked
  through the core's own path, its cases from a storage stream, its results in a storage buffer, judged against exact
  arithmetic as ``DriftSolver.check`` judges them (audit 5 M4, rule (b)); ``pair_check_broken`` is the same kernel with
  the error terms a compiler that ignores ``precise`` may drop zeroed (its negative control).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

CARD = (480, 270)
MODE_CODES = {"field": 230, "chain": 231, "volume": 232, "state": 233, "population": 234, "population_direct": 235,
              "war": 236, "refusal": 237,
              # Checkpoint audit 5's scenes, below 230 (mesh_buffers holds 240 to 249).
              "war_pingpong": 227, "pair_check": 228, "pair_check_broken": 229}
KNOTS = 64                 # field and chain: 64 knots of vec4
FIELD_SIZE = (64, 8)
VOLUME_SIZE = (16, 8, 4)
STATE_ROWS = 256           # vec4 rows; the resize doubles it
POPULATION = 4096
POPULATION_GROUP = 256
WAR_ROWS = 64

HEADER = """#version 440
#ifdef VULKAN
#define srpssVertexIndex gl_VertexIndex
#define srpssInstanceIndex gl_InstanceIndex
#else
#define srpssVertexIndex gl_VertexID
#define srpssInstanceIndex gl_InstanceID
#endif
"""

# ----------------------------------------------------------------------------------------------------- field
FIELD_COMP = """#version 440
layout(local_size_x = 64) in;
layout(std140, binding = 0) uniform FieldDispatch {
    vec4 u_field;              // gain (a power of two), offset per row, 0, 0
    uvec4 u_srpss_compute;     // the core's: trigger, last trigger, fresh, dispatches
};
layout(std430, binding = 1) readonly buffer Knots { vec4 knots[]; };
layout(binding = 2, rgba32f) writeonly uniform image2D uField;
void main()
{
    uint x = gl_GlobalInvocationID.x;
    uint row = gl_GlobalInvocationID.y;
    if (x >= 64u || row >= 8u)
        return;
    vec4 k = knots[(x + row * 7u) % 64u];
    imageStore(uField, ivec2(int(x), int(row)),
               vec4(k.xy * u_field.x + float(row) * u_field.y, k.z + k.w, u_srpss_compute.z != 0u ? 1.0 : 0.5));
}
"""
# A fullscreen pass sampling an image (nearest): its texel over the scene target.
SAMPLE_FRAG = """#version 440
layout(location = 0) in vec2 v_uv;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 18) uniform SampleDraw {
    vec4 u_scale;              // the sampled value's scale into [0, 1]
    float u_frame;             // the record's tick (a record field fills a member)
};
layout(binding = 1) uniform sampler2D uImage;
void main()
{
    vec4 v = texture(uImage, v_uv);
    fragColor = vec4(clamp(abs(v.xyz) * u_scale.xyz, 0.0, 1.0), 1.0);
}
"""

# ----------------------------------------------------------------------------------------------------- chain
SECTIONS_COMP = """#version 440
layout(local_size_x = 64) in;
layout(std140, binding = 0) uniform SectionsDispatch { vec4 u_sections; };   // gain, 0, 0, 0
layout(std430, binding = 1) readonly buffer Knots { vec4 knots[]; };
layout(binding = 2, rgba32f) writeonly uniform image2D uSections;
void main()
{
    uint x = gl_GlobalInvocationID.x;
    if (x >= 64u)
        return;
    for (uint row = 0u; row < 8u; ++row) {
        vec4 k = knots[(x * 3u + row) % 64u];
        imageStore(uSections, ivec2(int(x), int(row)), k * u_sections.x + vec4(float(row)));
    }
}
"""
BLUR_COMP = """#version 440
layout(local_size_x = 64) in;
layout(std140, binding = 0) uniform BlurDispatch { vec4 u_blur; };          // weight (1/8), 0, 0, 0
layout(binding = 1, rgba32f) readonly uniform image2D uSections;
layout(binding = 2, rgba32f) writeonly uniform image2D uGive;
void main()
{
    uint x = gl_GlobalInvocationID.x;
    if (x >= 64u)
        return;
    vec4 sum = vec4(0.0);
    for (int row = 0; row < 8; ++row)
        sum += imageLoad(uSections, ivec2(int(x), row));
    imageStore(uGive, ivec2(int(x), 0), sum * u_blur.x);
}
"""

# ----------------------------------------------------------------------------------------------------- volume
INJECT_COMP = """#version 440
layout(local_size_x = 4, local_size_y = 4, local_size_z = 4) in;
layout(std140, binding = 0) uniform InjectDispatch {
    vec4 u_inject;             // density step, 0, 0, 0
    float u_phase;             // the record's (an f64 field into a float member)
};
layout(binding = 1, rgba16f) writeonly uniform image3D uInject;
layout(binding = 2, r16f) writeonly uniform image3D uSteady;
void main()
{
    ivec3 p = ivec3(gl_GlobalInvocationID);
    ivec3 size = imageSize(uInject);
    if (p.x >= size.x || p.y >= size.y || p.z >= size.z)
        return;
    float d = float((p.x + 3 * p.y + 5 * p.z) % 8) * u_inject.x + u_phase;
    imageStore(uInject, p, vec4(d, float(p.z) * 0.25, float(p.x) * 0.125, 1.0));
    imageStore(uSteady, p, vec4(float(p.y) * 0.5));
}
"""
INTEGRATE_COMP = """#version 440
layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;
layout(binding = 1, rgba16f) readonly uniform image3D uInject;
layout(binding = 2, rgba16f) writeonly uniform image3D uIntegrated;
void main()
{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec3 size = imageSize(uInject);
    if (p.x >= size.x || p.y >= size.y)
        return;
    vec4 sum = vec4(0.0);
    for (int z = 0; z < size.z; ++z) {
        sum += imageLoad(uInject, ivec3(p, z));
        imageStore(uIntegrated, ivec3(p, z), sum);
    }
}
"""
VOLUME_FRAG = """#version 440
layout(location = 0) in vec2 v_uv;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 18) uniform VolumeDraw {
    vec4 u_slice;              // the slice's texel centre in z, scale
    float u_frame;
};
layout(binding = 1) uniform sampler3D uVolume;
void main()
{
    vec4 v = texture(uVolume, vec3(v_uv, u_slice.x));
    fragColor = vec4(clamp(v.xyz * u_slice.y, 0.0, 1.0), 1.0);
}
"""

# ----------------------------------------------------------------------------------------------------- state
STATE_COMP = """#version 440
layout(local_size_x = 64) in;
layout(std140, binding = 0) uniform StateDispatch {
    vec4 HALF;                 // first row, rows (this entry's half)
    uvec4 u_srpss_compute;
};
layout(std430, binding = 1) buffer State { vec4 state[]; };
layout(std430, binding = 2) writeonly buffer Out { vec4 outRows[]; };
void main()
{
    uint i = gl_GlobalInvocationID.x;
    uint first = uint(HALF.x);
    if (i >= uint(HALF.y))
        return;
    uint k = first + i;
    vec4 s = u_srpss_compute.z != 0u ? vec4(0.0) : state[k];
    s.x += 1.0;                              // the dispatches this row has seen since the storage was made
    s.y = float(u_srpss_compute.x);          // the trigger
    s.z = float(u_srpss_compute.y);          // its value at the last dispatch
    s.w = float(u_srpss_compute.z) * 1000.0 + float(u_srpss_compute.w);  // fresh, the dispatches before this one
    state[k] = s;
    outRows[k] = vec4(s.x * 2.0, s.y, float(k), 1.0);
}
"""
STATE_DRAW_BLOCK = """layout(std140, binding = 18) uniform StateDraw {
    mat4 uMatrix;
    vec4 u_grid;               // columns, cell px
    float u_frame;
};
"""
STATE_VERT = HEADER + STATE_DRAW_BLOCK + """layout(location = 0) in vec4 aOut;    // the compute entries' output, per instance
layout(location = 0) out vec4 vColour;
void main()
{
    int i = srpssInstanceIndex;
    int v = srpssVertexIndex;
    vec2 corner = vec2(float(v & 1), float((v >> 1) & 1));
    vec2 cell = vec2(float(i % int(u_grid.x)), float(i / int(u_grid.x)));
    vec2 item = (cell + 0.125 + corner * 0.75) * u_grid.y;
    gl_Position = uMatrix * vec4(item, 0.0, 1.0);
    vColour = vec4(fract(aOut.x / 16.0), fract(aOut.y / 32.0), fract(aOut.z / 64.0), 1.0);
}
"""
PLAIN_FRAG = """#version 440
layout(location = 0) in vec2 v_uv;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 18) uniform PlainDraw { float u_frame; };
void main()
{
    fragColor = vec4(v_uv, 0.25 + 0.001 * fract(u_frame), 1.0);
}
"""
COLOUR_FRAG = """#version 440
layout(location = 0) in vec4 vColour;
layout(location = 0) out vec4 fragColor;
void main()
{
    fragColor = vColour;
}
"""

# ----------------------------------------------------------------------------------------------------- population
POPULATION_HOOKS = """
bool populationActive(uint id) { return ((id * 2654435761u) >> 7u) % 3u != 0u; }
vec4 populationState(uint id) { return vec4(float(id % 64u), float(id / 64u), float(id % 7u) * 0.125, 1.0); }
"""
POPULATION_DRAW_BLOCK = """layout(std140, binding = 18) uniform PopulationDraw {
    mat4 uMatrix;
    vec4 u_cell;               // cell px
    float u_frame;
};
"""
POPULATION_VERT = HEADER + POPULATION_DRAW_BLOCK + """layout(std430, binding = 6) readonly buffer PopulationIds { uint populationIds[]; };
layout(std430, binding = 7) readonly buffer PopulationStates { vec4 populationStates[]; };
layout(location = 0) out vec4 vColour;
void main()
{
    vec4 s = populationStates[srpssInstanceIndex];
    uint id = populationIds[srpssInstanceIndex];
    int v = srpssVertexIndex;
    vec2 corner = vec2(float(v & 1), float((v >> 1) & 1));
    vec2 item = (s.xy + 0.25 + corner * 0.5) * u_cell.x;
    gl_Position = uMatrix * vec4(item, 0.0, 1.0);
    vColour = vec4(s.z + 0.125, float(id % 5u) * 0.25, 0.5, 1.0);
}
"""

# ----------------------------------------------------------------------------------------------------- war
WAR_READ_COMP = """#version 440
layout(local_size_x = 64) in;
layout(std140, binding = 0) uniform WarRead { vec4 u_war; float u_frame; };
layout(std430, binding = 1) readonly buffer X { vec4 x[]; };
layout(std430, binding = 2) writeonly buffer Y { vec4 y[]; };
void main()
{
    uint i = gl_GlobalInvocationID.x;
    if (i < 64u)
        y[i] = x[i] * 2.0 + vec4(u_war.x);
}
"""
WAR_WRITE_COMP = """#version 440
layout(local_size_x = 64) in;
layout(std140, binding = 0) uniform WarWrite { vec4 u_war_next; uvec4 u_srpss_compute; };
layout(std430, binding = 1) writeonly buffer X { vec4 x[]; };
void main()
{
    uint i = gl_GlobalInvocationID.x;
    if (i < 64u)
        x[i] = vec4(float(u_srpss_compute.x), float(i), u_war_next.x, 1.0);
}
"""

# The ping-pong form (two buffers): each entry writes one past what it read, so A's write must follow entry 1's read.
PINGPONG_COMP = """#version 440
layout(local_size_x = 64) in;
layout(std140, binding = 0) uniform PingPong { float u_frame; };   // the record's (w only: the counter ignores it)
layout(std430, binding = 1) readonly buffer X { vec4 x[]; };
layout(std430, binding = 2) writeonly buffer Y { vec4 y[]; };
void main()
{
    uint i = gl_GlobalInvocationID.x;
    if (i < 64u)
        y[i] = vec4(x[i].x + 1.0, float(i), x[i].x, u_frame);
}
"""


def pair_check_sources() -> tuple[str, str]:
    """D4's pair-check kernel verbatim (the product's ``PROGRAMS[2]``) and its broken twin: the error terms a compiler
    that ignores ``precise`` may reassociate away, zeroed (``tests/test_extruded_bubble_drift_solver.py``'s model)."""
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import PROGRAMS

    source = PROGRAMS[2][1]
    broken = (source.replace("precise float e = (a - (s - v)) + (b - v);", "precise float e = 0.0;")
              .replace("precise float e = ((x.x * y.x - p) + x.x * y.y + x.y * y.x) + x.y * y.y;",
                       "precise float e = 0.0;"))
    if broken == source:
        raise RuntimeError("the pair-check kernel changed: its broken twin no longer differs")
    return source, broken


def pair_check_report(results: bytes) -> dict:
    """The kernel's results judged as ``DriftSolver.check`` judges them (exact arithmetic on the same cases)."""
    import numpy as np

    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import pair_check_cases

    cases, expected = pair_check_cases()
    got = np.frombuffer(results, "<f4").reshape(-1, 4)[:len(cases)]
    fraction = np.abs(got[:, 0].astype(np.float64) - expected["fraction"])
    fraction = np.minimum(fraction, 1. - fraction)
    report = {"fraction_error": float(fraction.max()),
              "product_mismatches": int((got[:, 1] != expected["product"]).sum()),
              "sum_mismatches": int((got[:, 2] != expected["sum"]).sum())}
    report["exact"] = (report["fraction_error"] < 1e-6 and not report["product_mismatches"]
                       and not report["sum_mismatches"])
    return report


def pair_check_record() -> dict:
    """The pair check's record: its cases as the storage stream's floats."""
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import pair_check_cases

    cases, _expected = pair_check_cases()
    return {"case_rows": cases.astype("<f4").tobytes(), "case_floats": int(cases.size)}


# ----------------------------------------------------------------------------------------------------- refusals
# D16 choice D's admission, settled on the module: each is refused with its reason.
REFUSAL_COMP = """#version 440
layout(local_size_x = 64) in;
layout(std140, binding = 0) uniform RefusalDispatch { vec4 u_a; };
layout(std430, binding = 1) readonly buffer In { vec4 rows[]; };
layout(std430, binding = 2) writeonly buffer Out { vec4 outRows[]; };
layout(std430, binding = 3) buffer Both { vec4 both[]; };
layout(binding = 4, rgba16f) writeonly uniform image3D uVol;
void main()
{
    uint i = gl_GlobalInvocationID.x;
    outRows[i] = rows[i] * u_a.x + both[i];
    both[i] = rows[i];
    imageStore(uVol, ivec3(int(i), 0, 0), rows[i]);
}
"""


def population_shaders() -> dict[str, str]:
    """The product's three population programs for the harness hooks (``population.py``), verbatim."""
    from rendering.quick.scene3d.population import population_programs

    (_count_key, count), (_scan_key, scan), (_scatter_key, scatter) = population_programs("n33", POPULATION_HOOKS)
    return {"population_count.comp": count, "population_scan.comp": scan, "population_scatter.comp": scatter}


def shaders() -> dict[str, str]:
    out = {
        "field.comp": FIELD_COMP, "sample.frag": SAMPLE_FRAG, "sections.comp": SECTIONS_COMP, "blur.comp": BLUR_COMP,
        "inject.comp": INJECT_COMP, "integrate.comp": INTEGRATE_COMP, "volume.frag": VOLUME_FRAG,
        "state_a.comp": STATE_COMP.replace("HALF", "u_half_a"), "state_b.comp": STATE_COMP.replace("HALF", "u_half_b"),
        "state.vert": STATE_VERT, "colour.frag": COLOUR_FRAG, "plain.frag": PLAIN_FRAG, "population.vert": POPULATION_VERT,
        "war_read.comp": WAR_READ_COMP, "war_write.comp": WAR_WRITE_COMP, "refusal.comp": REFUSAL_COMP,
        "pingpong.comp": PINGPONG_COMP,
    }
    out.update(population_shaders())
    out["pair_check.comp"], out["pair_check_broken.comp"] = pair_check_sources()
    return out


def bake_all(folder: Path) -> dict[str, bytes]:
    """Every shader baked by ``tools/regen_qrc.py``'s own baker (``.comp`` included since N3.3)."""
    import probe_rings

    return {name: probe_rings.bake(text, name, folder) for name, text in shaders().items()}


def reflection(pack_path: Path) -> dict:
    """``qsb -d``'s reflection of a pack (the qualifiers D16 choice D reads): its JSON."""
    import json
    import subprocess

    import PySide6

    qsb = Path(PySide6.__file__).parent / "qsb.exe"
    text = subprocess.run([str(qsb), "-d", str(pack_path)], capture_output=True, text=True, timeout=120).stdout
    start = text.index("Reflection info: ") + len("Reflection info: ")
    depth, end = 0, start
    for end in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[end], 0)
        if depth == 0 and end > start:
            break
    return json.loads(text[start:end + 1])


# ----------------------------------------------------------------------------------------------------- the data

def _f32(values) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def knots(frame: int = 0) -> list[float]:
    """64 knots (vec4), every value a multiple of 1/64 below 8: exact through the shaders' sums and products."""
    out = []
    for i in range(KNOTS):
        out += [((i * 5 + frame * 3) % 128) / 16.0, ((i * 11 + frame) % 64) / 8.0, (i % 8) / 4.0, (frame % 4) / 64.0]
    return out


def schema(name: str, entries: tuple, checks: tuple = ()):
    """A ``NativeSchema`` of the scene's own (its mode code outside the product's table)."""
    import mesh_buffers

    made = mesh_buffers.schema(name, entries, checks, code=MODE_CODES[name])
    return made


@dataclass
class SceneSpec:
    name: str
    passes: tuple
    targets: tuple
    streams: tuple
    settings: dict
    schema: Any
    record: dict
    buffers: tuple = ()
    images: tuple = ()
    meshes: tuple = ()
    # The reference's dispatches: (shader file, groups (x, y, z), {binding: resource}, block values in the block's
    # order as (name, std140 kind, value)); the u_srpss_compute member is filled by the reference's own trigger rule.
    reference: tuple = ()


def _target():
    from rendering.native.mode import ModeTarget, TargetAttachment

    return ModeTarget("scene", (TargetAttachment("colour", "rgba8"),))


def state_grid(rows: int) -> list[float]:
    return [32.0, 7.5 if rows <= 256 else 3.75, 0.0, 0.0]


def scene(name: str, packs: dict, *, state_rows: int = STATE_ROWS, population: int = POPULATION,
          volume: tuple = VOLUME_SIZE, knots_count: int = KNOTS) -> SceneSpec:
    """The scene ``name`` (module notes) with its program, storage, settings, schema, first record and the reference's
    dispatches."""
    from rendering.native.mode import (ComputeBinding, ComputePass, MeshAttribute, ModePass, ModeStream, PassGeometry,
                                       PassSampler, RecordLayout, StorageBuffer, StorageImage)

    target = (_target(),)
    if name == "field":
        passes = (
            ComputePass("field", packs["field.comp"], bindings=(ComputeBinding("Knots", "knots", "stream"),
                                                                ComputeBinding("uField", "field", "image", "write")),
                        over="field"),
            ModePass("sample", packs["sample.frag"], "replace", target="scene",
                     samplers=(PassSampler("uImage", "field", filter="nearest"),)))
        return SceneSpec(name, passes, target, (ModeStream("knots", "knot_rows", used="knot_floats"),),
                         {"u_field": [0.5, 0.25, 0.0, 0.0], "u_scale": [0.125, 0.125, 0.125, 0.0]},
                         schema(name, (("knot_rows", "f32", 4 * KNOTS), ("knot_floats", "u32", 1), ("u_frame", "f64", 1)),
                                (("knot_floats", "at_most", 4 * KNOTS),)),
                         {"knot_rows": _f32(knots()), "knot_floats": 4 * KNOTS, "u_frame": 0.0},
                         images=(StorageImage("field", FIELD_SIZE, "rgba32f"),),
                         reference=(("field.comp", (1, 8, 1), {1: "knots", 2: "field"},
                                     (("u_field", "vec4", [0.5, 0.25, 0.0, 0.0]),
                                      ("u_srpss_compute", "uvec4", "compute"))),))
    if name == "chain":
        passes = (
            ComputePass("sections", packs["sections.comp"],
                        bindings=(ComputeBinding("Knots", "knots", "stream"),
                                  ComputeBinding("uSections", "sections", "image", "write")), groups=(1, 1, 1)),
            ComputePass("blur", packs["blur.comp"],
                        bindings=(ComputeBinding("uSections", "sections", "image", "read"),
                                  ComputeBinding("uGive", "give", "image", "write")), groups=("blur_groups", 1, 1)),
            ModePass("sample", packs["sample.frag"], "replace", target="scene",
                     samplers=(PassSampler("uImage", "give", filter="nearest"),)))
        return SceneSpec(name, passes, target, (ModeStream("knots", "knot_rows", used="knot_floats"),),
                         {"u_sections": [0.25, 0.0, 0.0, 0.0], "u_blur": [0.125, 0.0, 0.0, 0.0], "blur_groups": 1,
                          "u_scale": [0.25, 0.25, 0.25, 0.0]},
                         schema(name, (("knot_rows", "f32", 4 * KNOTS), ("knot_floats", "u32", 1), ("u_frame", "f64", 1)),
                                (("knot_floats", "at_most", 4 * KNOTS),)),
                         {"knot_rows": _f32(knots()), "knot_floats": 4 * KNOTS, "u_frame": 0.0},
                         images=(StorageImage("sections", FIELD_SIZE, "rgba32f"), StorageImage("give", (64, 1), "rgba32f")),
                         reference=(("sections.comp", (1, 1, 1), {1: "knots", 2: "sections"},
                                     (("u_sections", "vec4", [0.25, 0.0, 0.0, 0.0]),)),
                                    ("blur.comp", (1, 1, 1), {1: "sections", 2: "give"},
                                     (("u_blur", "vec4", [0.125, 0.0, 0.0, 0.0]),))))
    if name == "volume":
        w, h, d = volume
        passes = (
            ComputePass("inject", packs["inject.comp"],
                        bindings=(ComputeBinding("uInject", "inject", "image", "write"),
                                  ComputeBinding("uSteady", "steady", "image", "write")), over="inject"),
            ComputePass("integrate", packs["integrate.comp"],
                        bindings=(ComputeBinding("uInject", "inject", "image", "read"),
                                  ComputeBinding("uIntegrated", "integrated", "image", "write")),
                        groups=(-(-w // 8), -(-h // 8), 1)),
            ModePass("sample", packs["volume.frag"], "replace", target="scene",
                     samplers=(PassSampler("uVolume", "integrated", filter="nearest"),)))
        return SceneSpec(name, passes, target, (),
                         {"u_inject": [0.125, 0.0, 0.0, 0.0], "u_slice": [(2 + 0.5) / d, 0.25, 0.0, 0.0]},
                         schema(name, (("u_phase", "f64", 1), ("u_frame", "f64", 1))), {"u_phase": 0.0, "u_frame": 0.0},
                         images=(StorageImage("inject", (w, h, d), "rgba16f"), StorageImage("steady", (w, h, d), "r16f"),
                                 StorageImage("integrated", (w, h, d), "rgba16f")),
                         reference=(("inject.comp", (-(-w // 4), -(-h // 4), -(-d // 4)), {1: "inject", 2: "steady"},
                                     (("u_inject", "vec4", [0.125, 0.0, 0.0, 0.0]), ("u_phase", "float", None))),
                                    ("integrate.comp", (-(-w // 8), -(-h // 8), 1), {1: "inject", 2: "integrated"}, ())))
    if name == "state":
        half = state_rows // 2
        groups = -(-half // 64)
        out_layout = RecordLayout(16, (MeshAttribute("aOut", 4, 0),))
        passes = (
            ComputePass("advance_a", packs["state_a.comp"], trigger="step", groups=("state_groups", 1, 1),
                        bindings=(ComputeBinding("State", "state", "buffer", "read_write"),
                                  ComputeBinding("Out", "out", "buffer", "write"))),
            ComputePass("advance_b", packs["state_b.comp"], trigger="step", groups=("state_groups", 1, 1),
                        bindings=(ComputeBinding("State", "state", "buffer", "read_write"),
                                  ComputeBinding("Out", "out", "buffer", "write"))),
            ModePass("draw", packs["colour.frag"], "replace", target="scene",
                     geometry=PassGeometry(packs["state.vert"], topology="triangle_strip", vertices=4,
                                           instance_from="out")))
        return SceneSpec(name, passes, target, (),
                         {"u_half_a": [0.0, float(half), 0.0, 0.0], "u_half_b": [float(half), float(half), 0.0, 0.0],
                          "state_groups": groups, "state_bytes": 16 * state_rows, "u_grid": state_grid(state_rows)},
                         schema(name, (("step", "u32", 1), ("u_frame", "f64", 1))), {"step": 1, "u_frame": 0.0},
                         buffers=(StorageBuffer("state", "state_bytes"),
                                  StorageBuffer("out", "state_bytes", layout=out_layout)))
    if name in ("population", "population_direct"):
        groups = -(-population // POPULATION_GROUP)
        every = ("PopulationCounts", "PopulationOffsets", "PopulationCommand", "PopulationIds", "PopulationStates")
        resource = dict(zip(every, ("counts", "offsets", "command", "ids", "states")))
        bindings = tuple(ComputeBinding(block, resource[block], "buffer", "read_write") for block in every)
        geometry = (PassGeometry(packs["population.vert"], topology="triangle_strip", vertices=4, indirect="command",
                                 draw_count=1, storage=(("PopulationIds", "ids"), ("PopulationStates", "states")))
                    if name == "population" else
                    PassGeometry(packs["population.vert"], topology="triangle_strip", vertices=4,
                                 instances="live_members", storage=(("PopulationIds", "ids"),
                                                                    ("PopulationStates", "states"))))
        passes = (
            ComputePass("count", packs["population_count.comp"], bindings=bindings, groups=("pop_groups", 1, 1)),
            ComputePass("scan", packs["population_scan.comp"], bindings=bindings, groups=(1, 1, 1)),
            ComputePass("scatter", packs["population_scatter.comp"], bindings=bindings, groups=("pop_groups", 1, 1)),
            ModePass("draw", packs["colour.frag"], "replace", target="scene", geometry=geometry))
        settings = {"uPopulation": population, "uGroups": groups, "uVertices": 4, "pop_groups": groups,
                    "u_cell": [7.0, 0.0, 0.0, 0.0], "u_counts_bytes": 4 * groups}
        settings.pop("u_counts_bytes")
        if name == "population_direct":
            settings["live_members"] = live_members(population)
        buffers = (StorageBuffer("counts", 4 * groups), StorageBuffer("offsets", 4 * groups),
                   StorageBuffer("command", 16, indirect=True), StorageBuffer("ids", 4 * population),
                   StorageBuffer("states", 16 * population))
        block = (("uPopulation", "uint", population), ("uGroups", "uint", groups), ("uVertices", "uint", 4))
        everything = {3: "counts", 4: "offsets", 5: "command", 6: "ids", 7: "states"}
        return SceneSpec(name, passes, target, (), settings, schema(name, (("u_frame", "f64", 1),)), {"u_frame": 0.0},
                         buffers=buffers,
                         reference=(("population_count.comp", (groups, 1, 1), everything, block),
                                    ("population_scan.comp", (1, 1, 1), everything, block),
                                    ("population_scatter.comp", (groups, 1, 1), everything, block)))
    if name == "war":
        passes = (
            ComputePass("read_x", packs["war_read.comp"], groups=(1, 1, 1),
                        bindings=(ComputeBinding("X", "x", "buffer", "read"), ComputeBinding("Y", "y", "buffer", "write"))),
            ComputePass("write_x", packs["war_write.comp"], groups=(1, 1, 1),
                        bindings=(ComputeBinding("X", "x", "buffer", "write"),)))
        return SceneSpec(name, passes, (), (), {"u_war": [0.5, 0.0, 0.0, 0.0], "u_war_next": [0.25, 0.0, 0.0, 0.0]},
                         schema(name, (("u_frame", "f64", 1),)), {"u_frame": 0.0},
                         buffers=(StorageBuffer("x", 16 * WAR_ROWS), StorageBuffer("y", 16 * WAR_ROWS)))
    if name == "war_pingpong":
        passes = (
            ComputePass("ping", packs["pingpong.comp"], groups=(1, 1, 1),
                        bindings=(ComputeBinding("X", "a", "buffer", "read"), ComputeBinding("Y", "b", "buffer", "write"))),
            ComputePass("pong", packs["pingpong.comp"], groups=(1, 1, 1),
                        bindings=(ComputeBinding("X", "b", "buffer", "read"), ComputeBinding("Y", "a", "buffer", "write"))))
        return SceneSpec(name, passes, (), (), {}, schema(name, (("u_frame", "f64", 1),)), {"u_frame": 0.0},
                         buffers=(StorageBuffer("a", 16 * WAR_ROWS), StorageBuffer("b", 16 * WAR_ROWS)))
    if name in ("pair_check", "pair_check_broken"):
        record = pair_check_record()
        floats = record["case_floats"]
        passes = (
            ComputePass("pair_check", packs[f"{name}.comp"], groups=(1, 1, 1),
                        bindings=(ComputeBinding("CheckCases", "cases", "stream"),
                                  ComputeBinding("CheckResults", "results", "buffer", "write"))),)
        return SceneSpec(name, passes, (), (ModeStream("cases", "case_rows", used="case_floats"),), {},
                         schema(name, (("case_rows", "f32", floats), ("case_floats", "u32", 1)),
                                (("case_floats", "at_most", floats),)),
                         record, buffers=(StorageBuffer("results", 4 * floats),))
    raise KeyError(name)


def live_members(population: int) -> int:
    """The population's live members by its hook (the CPU's count: the direct draw's instances)."""
    return sum(1 for i in range(population) if ((i * 2654435761) % (1 << 32) >> 7) % 3 != 0)


def refusal_programs(packs: dict) -> dict:
    """D16 choice D: each program the core must refuse (by the reflection's qualifiers and image formats), and the one
    it must take."""
    from rendering.native.mode import ComputeBinding, ComputePass, StorageBuffer, StorageImage

    def entry(**changes):
        bindings = {"In": ("in_rows", "buffer", "read"), "Out": ("out_rows", "buffer", "write"),
                    "Both": ("both", "buffer", "read_write"), "uVol": ("vol", "image", "write")}
        bindings.update(changes)
        return ComputePass("refusal", packs["refusal.comp"], groups=(1, 1, 1),
                           bindings=tuple(ComputeBinding(k, r, kind, access) for k, (r, kind, access) in bindings.items()))

    buffers = tuple(StorageBuffer(n, 1024) for n in ("in_rows", "out_rows", "both"))
    images = (StorageImage("vol", (64, 1, 1), "rgba16f"),)
    wrong_format = (StorageImage("vol", (64, 1, 1), "rgba32f"),)
    flat = (StorageImage("vol", (64, 1), "rgba16f"),)
    return {
        "accepted": (entry(), buffers, images),
        "readonly_block_declared_write": (entry(In=("in_rows", "buffer", "write")), buffers, images),
        "writeonly_block_declared_read": (entry(Out=("out_rows", "buffer", "read")), buffers, images),
        "written_block_declared_read": (entry(Both=("both", "buffer", "read")), buffers, images),
        "writeonly_image_declared_read": (entry(uVol=("vol", "image", "read")), buffers, images),
        "image_of_another_format": (entry(), buffers, wrong_format),
        "2d_image_bound_to_image3d": (entry(), buffers, flat),
        # Checkpoint audit 5 M3: one buffer bound twice with two accesses (each block's qualifier fits its own access).
        "one_buffer_bound_read_and_write": (entry(Out=("in_rows", "buffer", "write")), buffers, images),
        "unbound_block": (ComputePass("refusal", packs["refusal.comp"], groups=(1, 1, 1),
                                      bindings=tuple(ComputeBinding(k, r, kind, a) for k, (r, kind, a) in
                                                     {"In": ("in_rows", "buffer", "read"),
                                                      "Out": ("out_rows", "buffer", "write"),
                                                      "uVol": ("vol", "image", "write")}.items())), buffers, images),
    }


__all__ = ["CARD", "SceneSpec", "bake_all", "knots", "live_members", "pair_check_record", "pair_check_report",
           "pair_check_sources", "reflection", "refusal_programs", "scene", "shaders"]
