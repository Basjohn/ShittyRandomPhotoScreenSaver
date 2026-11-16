"""N3.2's harness scenes (Current_Plan.md item 8b, N3.2; decision D15; ``native/core/src/mesh_buffers.h``): passes with
their own vertex stage, meshes, streams, sprites and batched draws, as data, harness-only and never registered (like
``probe_rings`` and ``scene_targets``). Each scene is a program on one item bound to a frame stream of its own schema (a
mode code outside ``packet_abi.MODE_CODES``), drawing into a surface-sized RGBA8 scene target ``scene`` the harness reads
back; the Python reference draws the same shader text in the production GL host.

- ``box``: Extruded Spectrum's shape: the product's unit box (``SCENE3D_BOX_VERTICES``) as the mesh ``box``, instanced
  over per-frame bar records in a storage stream, depth tested, back faces culled with the front face chosen per record
  (``u_front_cw``: N0.3 rule 4 on the matrix as uploaded).
- ``voxels``: Sphere's shape: a cube mesh with a static per-instance stream (centre, size, seed), alpha blended.
- ``sprites``: Bubble's shape: point records in an instance stream drawn as instanced quads (``srpss_geometry.glsl``);
  the reference also draws them as ``gl_PointSize`` points (``SPRITE_POINTS``) for the conversion's figures.
- ``beam``: the Oscilloscope's shape: a strip of 4 a segment, its endpoints from a storage stream, blend MAX.
- ``streaks``: Beam's shape: 900 instances over the built-in ``quad``, a third culled outside the clip volume, additive;
  ``streaks_indirect`` draws the same from a record-written indirect command.
- ``cells``: the batched draw (D15 point 6): 16 batches of 4 quads from storage, one draw a batch (form 2) or one
  multi-draw with ``gl_DrawID`` (form 3, its draw-parameters pack); ``cells_direct`` is the same in one draw (its batch
  from the instance), ``cells_flat`` the negative control (every batch's tint the first's).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

HEADER = """#version 440
#ifdef VULKAN
#define srpssVertexIndex gl_VertexIndex
#define srpssInstanceIndex gl_InstanceIndex
#else
#define srpssVertexIndex gl_VertexID
#define srpssInstanceIndex gl_InstanceID
#endif
"""
HEADER_460 = HEADER.replace("#version 440", "#version 460")

HUE = """
vec3 hue(float h) { return clamp(abs(fract(h + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0, 0.0, 1.0); }
"""

# ----------------------------------------------------------------------------------------------------- box
BOX_BLOCK = """layout(std140, binding = 18) uniform BoxDraw {
    mat4 uMatrix;
    vec4 u_box;       // bar width px, base y px, depth scale, turn (radians)
    vec4 u_light;     // light direction
};
"""
BOX_VERT = HEADER + BOX_BLOCK + """layout(location = 0) in vec3 aPosition;
layout(location = 1) in vec3 aNormal;
layout(std430, binding = 3) readonly buffer Bars { vec4 bars[]; };   // x px, height px, hue, 0
layout(location = 0) out vec3 vNormal;
layout(location = 1) out float vHue;
void main()
{
    vec4 bar = bars[srpssInstanceIndex];
    float c = cos(u_box.w), s = sin(u_box.w);
    vec3 q = vec3(c * aPosition.x + s * aPosition.z, aPosition.y, -s * aPosition.x + c * aPosition.z);
    vNormal = vec3(c * aNormal.x + s * aNormal.z, aNormal.y, -s * aNormal.x + c * aNormal.z);
    vHue = bar.z;
    vec2 item = vec2(bar.x + q.x * u_box.x, u_box.y - (q.y + 0.5) * bar.y);
    gl_Position = uMatrix * vec4(item, 0.5 - q.z * u_box.z, 1.0);
}
"""
BOX_FRAG = "#version 440\n" + BOX_BLOCK + HUE + """layout(location = 0) in vec3 vNormal;
layout(location = 1) in float vHue;
layout(location = 0) out vec4 fragColor;
void main()
{
    float d = 0.35 + 0.65 * max(dot(normalize(vNormal), normalize(u_light.xyz)), 0.0);
    fragColor = vec4(hue(vHue) * d, 1.0);
}
"""

# ----------------------------------------------------------------------------------------------------- voxels
VOXEL_BLOCK = """layout(std140, binding = 18) uniform VoxelDraw {
    mat4 uMatrix;
    vec4 u_tint;
    float u_frame;    // the record's tick (no math reads it: a record field fills a member)
};
"""
VOXEL_VERT = HEADER + VOXEL_BLOCK + HUE + """layout(location = 0) in vec3 aPosition;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec4 aCell;   // centre x, y px, size px, seed
layout(location = 0) out vec4 vColour;
void main()
{
    vec2 item = aCell.xy + vec2(aPosition.x + 0.35 * aPosition.z, aPosition.y - 0.25 * aPosition.z) * aCell.z;
    gl_Position = uMatrix * vec4(item, 0.0, 1.0);
    float shade = 0.55 + 0.45 * aNormal.z + 0.2 * aNormal.x;
    vColour = vec4(hue(aCell.w) * u_tint.rgb * shade, u_tint.a);
}
"""
VOXEL_FRAG = "#version 440\n" + """layout(location = 0) in vec4 vColour;
layout(location = 0) out vec4 fragColor;
void main()
{
    fragColor = vColour;
}
"""

# ----------------------------------------------------------------------------------------------------- sprites
SPRITE_BLOCK = """layout(std140, binding = 18) uniform SpriteDraw {
    mat4 uMatrix;
    vec2 u_target_px;
    float u_dpr;
    float u_sprite_scale;
    vec4 u_colour;
};
"""
SPRITE_VERT = HEADER + "//@srpss_conventions\n//@srpss_geometry\n" + SPRITE_BLOCK + """layout(location = 0) in vec4 aPoint;   // x, y item px, diameter px, opacity
layout(location = 1) in vec2 aOther;   // glow, kind (0 a microbubble, 1 a particle)
layout(location = 0) out vec2 vCoord;
layout(location = 1) out float vAlpha;
layout(location = 2) out float vKind;
void main()
{
    vec4 centre = uMatrix * vec4(aPoint.xy, 0.0, 1.0);
    float size = clamp(aPoint.z * u_dpr * u_sprite_scale, 1.0, 128.0);
    vec2 corner = srpssSpriteCorner(srpssVertexIndex);
    gl_Position = srpssSpriteClip(centre, corner, size, u_target_px);
#ifndef SPRITE_NO_CULL
    if (aOther.y > 1.5)
        gl_Position = srpssSpriteCulled();     // a culled sprite (kind 2): every corner outside the clip volume
#endif
    vCoord = corner;
    vAlpha = aPoint.w;
    vKind = aOther.y;
}
"""
# The Python reference only: the same record drawn as a gl_PointSize point (the conversion's figures).
SPRITE_POINT_VERT = HEADER + SPRITE_BLOCK + """layout(location = 0) in vec4 aPoint;
layout(location = 1) in vec2 aOther;
layout(location = 0) out vec2 vCoord;
layout(location = 1) out float vAlpha;
layout(location = 2) out float vKind;
void main()
{
    gl_Position = uMatrix * vec4(aPoint.xy, 0.0, 1.0);
    gl_PointSize = clamp(aPoint.z * u_dpr * u_sprite_scale, 1.0, 128.0);
    vCoord = vec2(0.0);
    vAlpha = aPoint.w;
    vKind = aOther.y;
}
"""
SPRITE_FRAG_BODY = """layout(location = 0) in vec2 vCoord;
layout(location = 1) in float vAlpha;
layout(location = 2) in float vKind;
layout(location = 0) out vec4 fragColor;
void main()
{
#ifdef SPRITE_POINTS
    vec2 c = gl_PointCoord;
#elif defined(SPRITE_Y_UP)
    vec2 c = vec2(vCoord.x, 1.0 - vCoord.y);     // the negative control: the sprite coordinate with y up
#else
    vec2 c = vCoord;
#endif
    vec2 p = 2.0 * (c - vec2(0.5));
    float d = length(p);
    if (d > 1.0)
        discard;
    float ring = smoothstep(0.43, 0.68, d) * (1.0 - smoothstep(0.68, 0.96, d));
    float glint = (1.0 - smoothstep(0.0, 0.30, length(p - vec2(-0.38, 0.32)))) * 0.60;
    float a = clamp(vKind > 0.5 ? 1.0 - smoothstep(0.6, 1.0, d) : ring + glint, 0.0, 1.0) * vAlpha * u_colour.a;
    fragColor = vec4(u_colour.rgb * a, a);
}
"""
SPRITE_FRAG = "#version 440\n" + SPRITE_BLOCK + SPRITE_FRAG_BODY

# ----------------------------------------------------------------------------------------------------- beam
BEAM_BLOCK = """layout(std140, binding = 18) uniform BeamDraw {
    mat4 uMatrix;
    vec4 u_beam;      // half width px, reach px
    vec4 u_colour;
};
"""
BEAM_VERT = HEADER + BEAM_BLOCK + """layout(std430, binding = 3) readonly buffer Trace { vec2 points[]; };
layout(location = 0) out float vAcross;
void main()
{
    int i = srpssInstanceIndex;
    vec2 a = points[i];
    vec2 b = points[i + 1];
    vec2 dir = normalize(b - a + vec2(1e-6, 0.0));
    vec2 n = vec2(-dir.y, dir.x);
    int v = srpssVertexIndex;
    float side = (v & 1) == 1 ? 1.0 : -1.0;
    vec2 end = v < 2 ? a - dir * u_beam.y : b + dir * u_beam.y;
    gl_Position = uMatrix * vec4(end + n * side * u_beam.x, 0.0, 1.0);
    vAcross = side;
}
"""
BEAM_FRAG = "#version 440\n" + BEAM_BLOCK + """layout(location = 0) in float vAcross;
layout(location = 0) out vec4 fragColor;
void main()
{
    float f = 1.0 - abs(vAcross);
    fragColor = vec4(u_colour.rgb * f * f, f);
}
"""

# ----------------------------------------------------------------------------------------------------- streaks
STREAK_BLOCK = """layout(std140, binding = 18) uniform StreakDraw {
    mat4 uMatrix;
    vec2 uItemSize;
    vec2 u_spread;    // length range px
    vec4 u_colour;
    float u_frame;    // the record's tick
};
"""
STREAK_VERT = HEADER + STREAK_BLOCK + """layout(location = 0) in vec2 aPosition;   // the item quad's (the built-in mesh "quad")
layout(location = 0) out vec3 vColour;
layout(location = 1) out float vAcross;
uint mixBits(uint x)
{
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
    return x;
}
float rnd(uint id, uint k) { return float(mixBits(id * 0x9e3779b9u + k * 0x85ebca6bu) >> 8) * (1.0 / 16777216.0); }
void main()
{
    uint id = uint(srpssInstanceIndex);
    if (rnd(id, 1u) < 0.35) {
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);    // not alive: outside the clip volume (Beam's cull)
        vColour = vec3(0.0);
        vAcross = 0.0;
        return;
    }
    vec2 origin = vec2(rnd(id, 2u), rnd(id, 3u)) * uItemSize;
    float angle = rnd(id, 4u) * 6.2831853;
    vec2 dir = vec2(cos(angle), sin(angle));
    float len = mix(u_spread.x, u_spread.y, rnd(id, 5u));
    vec2 item = origin + dir * len * aPosition.x + vec2(-dir.y, dir.x) * 1.5 * (aPosition.y - 0.5);
    gl_Position = uMatrix * vec4(item, 0.0, 1.0);
    vColour = u_colour.rgb * (0.4 + 0.6 * rnd(id, 6u));
    vAcross = aPosition.y - 0.5;
}
"""
STREAK_FRAG = "#version 440\n" + """layout(location = 0) in vec3 vColour;
layout(location = 1) in float vAcross;
layout(location = 0) out vec4 fragColor;
void main()
{
    fragColor = vec4(vColour * (1.0 - 4.0 * vAcross * vAcross), 1.0);
}
"""

# ----------------------------------------------------------------------------------------------------- cells
CELL_BLOCK = """layout(std140, binding = 18) uniform CellDraw {
    mat4 uMatrix;
    vec4 u_tint;
    int u_srpss_batch;
};
"""
CELL_BODY = CELL_BLOCK + HUE + "//@srpss_geometry\n" + """layout(std430, binding = 3) readonly buffer Cells { vec4 cells[]; };     // x, y px, size px, hue
layout(std430, binding = 4) readonly buffer Batches { uvec2 batches[]; };  // first, count
layout(location = 0) out vec4 vColour;
void main()
{
#if defined(CELLS_DIRECT)
    int batch = srpssInstanceIndex / 4;
    uint index = uint(srpssInstanceIndex);
#elif defined(CELLS_FLAT)
    int batch = 0;
    uint index = uint(srpssInstanceIndex);
#elif defined(CELLS_PASS)
    int batch = CELLS_PASS;
    uint index = uint(4 * CELLS_PASS + srpssInstanceIndex);
#else
    int batch = int(srpssBatchIndex);
    uint index = batches[batch].x + uint(srpssInstanceIndex);
#endif
    vec4 c = cells[index];
    if (batches[0].y > 1000000u)
        c.z = 0.0;                     // every variant reads the table (never true: four a batch)
    vec2 corner = vec2(float(srpssVertexIndex & 1), float((srpssVertexIndex >> 1) & 1));
    gl_Position = uMatrix * vec4(c.xy + (corner - 0.5) * c.z, 0.0, 1.0);
    vColour = vec4(hue(c.w + 0.06 * float(batch)) * u_tint.rgb, u_tint.a);
#ifdef CELLS_IDS
    vColour = vec4(float(gl_DrawID), float(gl_BaseInstance), float(gl_BaseVertex), 255.0) / 255.0;
#endif
}
"""
CELL_VERT = HEADER + "//@srpss_conventions\n" + CELL_BODY
CELL_VERT_DP = HEADER_460 + "#define SRPSS_DRAW_PARAMETERS\n//@srpss_conventions\n" + CELL_BODY
CELL_VERT_DIRECT = HEADER + "#define CELLS_DIRECT\n//@srpss_conventions\n" + CELL_BODY
CELL_VERT_FLAT = HEADER + "#define CELLS_FLAT\n//@srpss_conventions\n" + CELL_BODY


def cell_pass_vert(batch: int) -> str:
    """One batch drawn as a pass of its own (N3.1's form: sixteen passes, each its own block)."""
    return HEADER + f"#define CELLS_PASS {int(batch)}\n//@srpss_conventions\n" + CELL_BODY


SPRITE_FRAG_Y_UP = "#version 440\n#define SPRITE_Y_UP\n" + SPRITE_BLOCK + SPRITE_FRAG_BODY
# The culled sprite's control: the same vertex stage without the cull (a kind-2 sprite then draws as a particle).
SPRITE_VERT_NO_CULL = SPRITE_VERT.replace("//@srpss_conventions\n", "#define SPRITE_NO_CULL\n//@srpss_conventions\n", 1)
SPRITE_FRAG_POINTS = "#version 440\n#define SPRITE_POINTS\n" + SPRITE_BLOCK + SPRITE_FRAG_BODY
# Research Q5: qsb compiles the draw parameters (gl_DrawID, gl_BaseInstance, gl_BaseVertex) for which targets.
DRAW_PARAMETERS_PROBE = """#version 460
layout(location = 0) out vec4 vIds;
void main()
{
    vIds = vec4(float(gl_DrawID), float(gl_BaseInstance), float(gl_BaseVertex), 0.0);
    gl_Position = vec4(0.0, 0.0, 0.0, 1.0);
}
"""
CELL_FRAG = "#version 440\n" + """layout(location = 0) in vec4 vColour;
layout(location = 0) out vec4 fragColor;
void main()
{
    fragColor = vColour;
}
"""

# ----------------------------------------------------------------------------------------------------- the stream ring
RING_BLOCK = """layout(std140, binding = 18) uniform RingDraw {
    mat4 uMatrix;
    vec4 u_colour;
    float u_frame;    // the record's tick
};
"""
RING_VERT = HEADER + RING_BLOCK + """layout(std430, binding = 3) readonly buffer Small { vec4 small[]; };
layout(location = 0) out vec4 vColour;
void main()
{
    vec4 c = small[srpssInstanceIndex];
    vec2 corner = vec2(float(srpssVertexIndex & 1), float((srpssVertexIndex >> 1) & 1));
    gl_Position = uMatrix * vec4(c.xy + (corner - 0.5) * c.z, 0.0, 1.0);
    vColour = u_colour;
}
"""
# The payload read per instance (Extruded Spectrum's bars, Bubble's points): a quad a row.
RING_INSTANCE_VERT = HEADER + RING_BLOCK + """layout(location = 0) in vec2 aCorner;
layout(location = 1) in vec4 aRow;      // x, y px, size px, 0
layout(location = 0) out vec4 vColour;
void main()
{
    gl_Position = uMatrix * vec4(aRow.xy + (aCorner - 0.5) * aRow.z, 0.0, 1.0);
    vColour = u_colour;
}
"""
# The payload read with neighbours (the Oscilloscope's points, Waveform's knots): a segment a row.
RING_STORAGE_VERT = HEADER + RING_BLOCK + """layout(std430, binding = 3) readonly buffer Rows { vec4 rows[]; };
layout(location = 0) out vec4 vColour;
void main()
{
    int i = srpssInstanceIndex;
    vec2 a = rows[i].xy;
    vec2 b = rows[i + 1].xy;
    vec2 dir = normalize(b - a + vec2(1e-6, 0.0));
    vec2 n = vec2(-dir.y, dir.x);
    int v = srpssVertexIndex;
    vec2 end = v < 2 ? a : b;
    gl_Position = uMatrix * vec4(end + n * ((v & 1) == 1 ? 1.0 : -1.0), 0.0, 1.0);
    vColour = u_colour;
}
"""
RING_FRAG = CELL_FRAG

# L2 retarget controls: a cached compute SRB reads the current immutable mesh buffer, with a sampled texture in the
# second form so one record must retarget both resource classes. Baked by this fixture owner's normal pack baker.
MESH_READ_COMP = """#version 440
layout(local_size_x = 64) in;
layout(std140, binding = 0) uniform MeshRead { float u_frame; };
layout(std430, binding = 1) readonly buffer Source { vec4 source[]; };
layout(std430, binding = 2) writeonly buffer Result { vec4 result[]; };
void main() {
    uint i = gl_GlobalInvocationID.x;
    result[i] = vec4(source[i].xyz, u_frame);
}
"""
MESH_TEXTURE_COMP = """#version 440
layout(local_size_x = 64) in;
layout(std140, binding = 0) uniform MeshRead { float u_frame; };
layout(std430, binding = 1) readonly buffer Source { vec4 source[]; };
layout(std430, binding = 2) writeonly buffer Result { vec4 result[]; };
layout(binding = 3) uniform sampler2D uTexture;
void main() {
    uint i = gl_GlobalInvocationID.x;
    float texel = texelFetch(uTexture, ivec2(0), 0).r;
    result[i] = vec4(source[i].xyz + vec3(texel), u_frame);
}
"""

SHADERS = {
    "box.vert": BOX_VERT, "box.frag": BOX_FRAG, "voxel.vert": VOXEL_VERT, "voxel.frag": VOXEL_FRAG,
    "sprite.vert": SPRITE_VERT, "sprite.frag": SPRITE_FRAG, "beam.vert": BEAM_VERT, "beam.frag": BEAM_FRAG,
    "streak.vert": STREAK_VERT, "streak.frag": STREAK_FRAG, "cell.vert": CELL_VERT,
    "cell_direct.vert": CELL_VERT_DIRECT, "cell_flat.vert": CELL_VERT_FLAT, "cell.frag": CELL_FRAG,
    "ring.vert": RING_VERT, "ring.frag": RING_FRAG, "ring_instance.vert": RING_INSTANCE_VERT,
    "ring_storage.vert": RING_STORAGE_VERT, "sprite_nocull.vert": SPRITE_VERT_NO_CULL, "sprite_yup.frag": SPRITE_FRAG_Y_UP,
    "mesh_read.comp": MESH_READ_COMP, "mesh_texture.comp": MESH_TEXTURE_COMP,
    **{f"cell_pass{b}.vert": cell_pass_vert(b) for b in range(16)},
}
#: Baked apart: a failure is a fact (research Q5), not the harness's end.
CELL_VERT_IDS = HEADER_460 + "#define SRPSS_DRAW_PARAMETERS\n#define CELLS_IDS\n//@srpss_conventions\n" + CELL_BODY
OPTIONAL_SHADERS = {"cell_dp.vert": CELL_VERT_DP, "draw_parameters.vert": DRAW_PARAMETERS_PROBE,
                    "cell_ids.vert": CELL_VERT_IDS}


def compose(text: str) -> str:
    """The text as both renderers compile it: the conventions and geometry markers expanded (as
    ``compose_shader_source`` and the core's bake do)."""
    from rendering.gl_programs.conventions import SRPSS_CONVENTIONS_GLSL, SRPSS_GEOMETRY_GLSL

    return text.replace("//@srpss_conventions\n", SRPSS_CONVENTIONS_GLSL + "\n").replace(
        "//@srpss_geometry\n", SRPSS_GEOMETRY_GLSL + "\n")


def bake_all(folder: Path) -> dict[str, bytes]:
    """Every shader of ``SHADERS`` baked by ``tools/regen_qrc.py``'s own baker (its markers composed): file name
    -> pack (the optional ones are :func:`bake_optional`'s)."""
    import probe_rings

    packs = {name: probe_rings.bake(compose(text), name, folder) for name, text in SHADERS.items()}
    return packs


def bake_optional(folder: Path) -> tuple[dict[str, bytes], dict[str, dict]]:
    """The optional shaders (``OPTIONAL_SHADERS``), tried for every shipped target, then for SPIR-V and GLSL alone:
    name -> pack, and name -> the targets each was baked for (or the errors; a failure leaves the pack out)."""
    import subprocess
    import sys

    import probe_rings
    from tools import regen_qrc

    packs, facts = {}, {}
    for name, text in OPTIONAL_SHADERS.items():
        try:
            packs[name] = probe_rings.bake(compose(text), name, folder)
            facts[name] = {"targets": list(regen_qrc.quick_shader_targets())}
            continue
        except Exception as exc:            # noqa: BLE001 (the fact is the failure)
            facts[name] = {"every_target_error": str(exc)[-600:]}
        source = Path(folder) / name
        source.write_text(compose(text), encoding="utf-8")
        pack = source.with_name(name + ".qsb")
        glsl = regen_qrc.quick_shader_targets()[1]
        try:
            regen_qrc._bake_quick_shader(regen_qrc.quick_shader_baker(sys.executable), source, pack, ("--glsl", glsl),
                                         subprocess.run)
            packs[name] = pack.read_bytes()
            facts[name]["targets"] = ["--glsl", glsl]
        except Exception as exc:            # noqa: BLE001
            facts[name]["spirv_glsl_error"] = str(exc)[-600:]
    return packs, facts


# ----------------------------------------------------------------------------------------------------- the data

CARD = (480, 270)
MODE_CODES = {"box": 240, "voxels": 241, "sprites": 242, "beam": 243, "streaks": 244, "streaks_indirect": 245,
              "cells": 246, "cells_direct": 247, "cells_flat": 248, "ring": 249}
BARS = 24
POINTS = 120
TRACE_POINTS = 160
STREAKS = 900
CELLS = 64
BATCHES = 16
VOXELS = 40
RETARGET_ROWS = 64


def _f32(values) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def schema(name: str, entries: tuple, checks: tuple = (), *, code: int | None = None):
    """A ``NativeSchema`` of the scene's own (its mode code outside the product's table)."""
    from dataclasses import dataclass as dc

    from core.visualizer_engine.native_schema import NativeLayout, NativeSchema

    @dc(frozen=True, slots=True)
    class SceneSchema(NativeSchema):
        code: int = 0

        @property
        def mode_code(self) -> int:
            return self.code

    layout = NativeLayout.build(entries)
    names = tuple(n for n, _k, _c in entries)
    holder: dict[str, Any] = {}

    def encode(values) -> bytes:
        return layout.pack(holder["schema"].schema_id, values)

    def decode(payload: bytes) -> dict:
        return {k: v for k, v in layout.unpack(payload).items() if k in names}

    made = SceneSchema(mode_id=f"n32_{name}", version=1, layout=layout, encode=encode, decode=decode, fields=names,
                       checks=checks, code=MODE_CODES[name] if code is None else int(code))
    holder["schema"] = made
    return made


def box_mesh() -> bytes:
    from rendering.gl_programs.scene3d import SCENE3D_BOX_VERTICES

    return _f32(SCENE3D_BOX_VERTICES)


def bars(frame: int = 0) -> list[float]:
    out = []
    for i in range(BARS):
        out += [40.13 + i * 17.5, 30.0 + 160.0 * (0.5 + 0.5 * math.sin(0.7 * i + 0.3 * frame)), i / BARS, 0.0]
    return out


def voxel_instances() -> bytes:
    out = []
    for i in range(VOXELS):
        # Edges off pixel centres: an edge through a centre is a tie the core's Y flip turns the other way (the fill
        # rule's top edge is its bottom edge), so it is no proof of the stream (the tie round shows it apart).
        out += [60.137 + (i % 10) * 38.0, 60.291 + (i // 10) * 48.0, 20.31 + 6.0 * (i % 3), (i * 0.137) % 1.0]
    return _f32(out)


def points(frame: int = 0) -> list[float]:
    """Sprite records (x, y, diameter, opacity, glow, kind) at sub-pixel centres and the proof's sizes."""
    sizes = (1.0, 1.7, 2.1, 12.5, 40.0, 128.0)
    out = []
    for i in range(POINTS):
        out += [23.37 + (i % 15) * 29.13 + 0.11 * frame, 21.81 + (i // 15) * 30.77, sizes[i % len(sizes)],
                0.55 + 0.45 * ((i * 7) % 5) / 4.0, 1.0, float(i % 2)]
    return out


def trace(frame: int = 0) -> list[float]:
    out = []
    for i in range(TRACE_POINTS):
        x = 12.0 + i * (CARD[0] - 24.0) / (TRACE_POINTS - 1)
        out += [x, CARD[1] * 0.5 + 80.0 * math.sin(i * 0.11 + 0.2 * frame) * math.cos(i * 0.023)]
    return out


def cells() -> list[float]:
    out = []
    for i in range(CELLS):
        out += [30.0 + (i % 16) * 27.0, 40.0 + (i // 16) * 50.0, 22.0, (i * 0.031) % 1.0]
    return out


def batch_table() -> list[int]:
    out = []
    for b in range(BATCHES):
        out += [4 * b, 4]
    return out


@dataclass
class SceneSpec:
    name: str
    passes: tuple
    targets: tuple
    streams: tuple
    settings: dict
    schema: Any
    record: dict
    meshes: tuple = ()      # (name, vertices, layout, instances, instance_layout)
    buffers: tuple = ()     # retarget's compute fixture (compute_pass_check.Scene owns its lifecycle/readback)
    images: tuple = ()


def retarget_compute_scene(packs: dict, *, texture: bool = False) -> SceneSpec:
    """A compute entry reading a storage mesh, optionally alongside a texture whose object changes at retarget."""
    from rendering.native.mode import ComputeBinding, ComputePass, PassSampler, StorageBuffer

    shader = "mesh_texture.comp" if texture else "mesh_read.comp"
    entry = ComputePass("mesh_texture" if texture else "mesh_read", packs[shader], groups=(1, 1, 1),
                        bindings=(ComputeBinding("Source", "source_mesh", "mesh"),
                                  ComputeBinding("Result", "result", "buffer", "write")),
                        samplers=(PassSampler("uTexture", "probe_texture", filter="nearest"),) if texture else ())
    return SceneSpec("retarget_compute", (entry,), (), (), {},
                     schema("retarget_compute", (("u_frame", "f64", 1),), code=238), {"u_frame": 0.0},
                     buffers=(StorageBuffer("result", RETARGET_ROWS * 16),))


def _target(depth: bool = False):
    from rendering.native.mode import ModeTarget, TargetAttachment

    return ModeTarget("scene", (TargetAttachment("colour", "rgba8"),), depth=depth)


def box_layout():
    from rendering.native.mode import MeshAttribute, RecordLayout

    return RecordLayout(24, (MeshAttribute("aPosition", 3, 0), MeshAttribute("aNormal", 3, 12)))


def scene(name: str, packs: dict, *, front_cw: int = 0, form: str = "") -> SceneSpec:
    """The scene ``name`` (module notes) with its program, streams, settings, schema, first record and meshes.
    ``front_cw``: the box's front face this backend draws (N0.3 rule 4)."""
    from rendering.native.mode import (BlendState, MeshAttribute, ModePass, ModeStream, PassGeometry, PassOutput,
                                       RecordLayout)

    if name == "box":
        geometry = PassGeometry(packs["box.vert"], mesh="box", instances="bar_count", storage=(("Bars", "bars"),),
                                cull="back", front_face="u_front_cw")
        passes = (ModePass("box", packs["box.frag"], "replace", target="scene", depth_test="less", depth_write=True,
                           geometry=geometry),)
        return SceneSpec(name, passes, (_target(depth=True),), (ModeStream("bars", "bar_rows", used="bar_floats"),),
                         {"u_box": [11.3, 249.71, 0.6, 0.55], "u_light": [0.4, -0.6, 0.7, 0.0],
                          "u_front_cw": int(front_cw)},
                         schema(name, (("bar_rows", "f32", 4 * 64), ("bar_count", "u32", 1), ("bar_floats", "u32", 1)),
                                (("bar_count", "at_most", 64), ("bar_floats", "at_most", 4 * 64))),
                         {"bar_rows": _f32(bars()), "bar_count": BARS, "bar_floats": 4 * BARS},
                         (("box", box_mesh(), box_layout(), None, None),))
    if name == "voxels":
        cell_layout = RecordLayout(16, (MeshAttribute("aCell", 4, 0),))
        geometry = PassGeometry(packs["voxel.vert"], mesh="voxels", instance_from="voxels")
        passes = (ModePass("voxels", packs["voxel.frag"], "alpha", target="scene", geometry=geometry),)
        return SceneSpec(name, passes, (_target(),), (), {"u_tint": [1.0, 0.85, 0.7, 0.6]},
                         schema(name, (("u_frame", "f64", 1),)), {"u_frame": 0.0},
                         (("voxels", box_mesh(), box_layout(), voxel_instances(), cell_layout),))
    if name == "sprites":
        layout = RecordLayout(24, (MeshAttribute("aPoint", 4, 0), MeshAttribute("aOther", 2, 16)))
        geometry = PassGeometry(packs["sprite.vert"], topology="triangle_strip", vertices=4, instances="point_count",
                                instance_from="points")
        passes = (ModePass("sprites", packs["sprite.frag"], "premultiplied", target="scene", geometry=geometry),)
        return SceneSpec(name, passes, (_target(),),
                         (ModeStream("points", "point_rows", "instance", layout, used="point_floats"),),
                         {"u_sprite_scale": 1.0, "u_colour": [0.9, 0.95, 1.0, 1.0]},
                         schema(name, (("point_rows", "f32", 6 * 192), ("point_count", "u32", 1),
                                       ("point_floats", "u32", 1)),
                                (("point_count", "at_most", 192), ("point_floats", "at_most", 6 * 192))),
                         {"point_rows": _f32(points()), "point_count": POINTS, "point_floats": 6 * POINTS})
    if name == "beam":
        geometry = PassGeometry(packs["beam.vert"], topology="triangle_strip", vertices=4, instances="segments",
                                storage=(("Trace", "trace"),))
        max_blend = BlendState(("max", "one", "one"), ("max", "one", "one"))
        passes = (ModePass("beam", packs["beam.frag"], max_blend, target="scene", geometry=geometry),)
        return SceneSpec(name, passes, (_target(),), (ModeStream("trace", "trace_rows", used="trace_floats"),),
                         {"u_beam": [2.5, 1.5, 0.0, 0.0], "u_colour": [0.35, 1.0, 0.55, 1.0]},
                         schema(name, (("trace_rows", "f32", 2 * 256), ("segments", "u32", 1),
                                       ("trace_floats", "u32", 1)),
                                (("segments", "at_most", 255), ("trace_floats", "at_most", 2 * 256))),
                         {"trace_rows": _f32(trace()), "segments": TRACE_POINTS - 1,
                          "trace_floats": 2 * TRACE_POINTS})
    if name in ("streaks", "streaks_indirect"):
        indirect = name == "streaks_indirect"
        geometry = (PassGeometry(packs["streak.vert"], topology="triangle_strip", mesh="quad", vertices="mesh",
                                 indirect="commands", draw_count="command_count") if indirect else
                    PassGeometry(packs["streak.vert"], topology="triangle_strip", mesh="quad", vertices="mesh",
                                 instances=STREAKS))
        passes = (ModePass("streaks", packs["streak.frag"], "additive", target="scene", geometry=geometry),)
        entries = (("u_frame", "f64", 1),) + ((("commands", "u32", 4), ("command_count", "u32", 1)) if indirect else ())
        record = dict({"u_frame": 0.0}, **({"commands": (4, STREAKS, 0, 0), "command_count": 1} if indirect else {}))
        return SceneSpec(name, passes, (_target(),),
                         (ModeStream("commands", "commands", "indirect"),) if indirect else (),
                         {"u_spread": [6.0, 36.0], "u_colour": [1.0, 0.7, 0.35, 1.0]},
                         schema(name, entries, (("command_count", "at_most", 1),) if indirect else ()), record)
    if name in ("cells", "cells_direct", "cells_flat"):
        streams = (ModeStream("cells", "cell_rows", used="cell_floats"), ModeStream("batches", "batch_table"))
        storage = (("Cells", "cells"), ("Batches", "batches"))
        if name == "cells":
            geometry = PassGeometry(packs["cell.vert"], topology="triangle_strip", vertices=4, storage=storage,
                                    batches="batch_table", batch_count="batch_len",
                                    draw_parameters_pack=packs["cell_dp.vert"] if form != "loop_only" else b"")
        else:
            geometry = PassGeometry(packs["cell_direct.vert" if name == "cells_direct" else "cell_flat.vert"],
                                    topology="triangle_strip", vertices=4, instances=CELLS, storage=storage)
        passes = (ModePass("cells", packs["cell.frag"], "alpha", target="scene", geometry=geometry),)
        entries = (("cell_rows", "f32", 4 * CELLS), ("batch_table", "u32", 2 * BATCHES), ("cell_floats", "u32", 1),
                   ("batch_len", "u32", 1))
        record = {"cell_rows": _f32(cells()), "batch_table": tuple(batch_table()), "cell_floats": 4 * CELLS,
                  "batch_len": BATCHES}
        checks = (("cell_floats", "at_most", 4 * CELLS), ("batch_len", "at_most", BATCHES))
        if name != "cells":
            entries = entries[:3]
            record.pop("batch_len")
            checks = checks[:1]
        return SceneSpec(name, passes, (_target(),), streams, {"u_tint": [1.0, 0.9, 0.8, 0.85]},
                         schema(name, entries, checks), record)
    raise KeyError(name)


def ring_rows(count: int) -> bytes:
    """``count`` payload rows (x, y px, size px, 0) spread over the card."""
    out = []
    for i in range(count):
        out += [20.0 + (i * 7.31) % 440.0, 20.0 + (i * 3.17) % 230.0, 3.0, 0.0]
    return _f32(out)


RING_CORNERS = _f32([0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0])


def ring_scene(packs: dict, payload_floats: int, kind: str, used_floats: int | None = None):
    """The stream ring's measurement (D15 point 7), a payload of ``payload_floats`` floats (rows of four) read as its
    consumer reads it: ``instance`` (an instance stream: QRhi's Dynamic fast path, the pair's CPU floor), ``storage``
    (a storage stream read with neighbours: QRhi's Static route, ``uploadStaticBuffer``), ``floor`` (the instance pass
    over the same rows resident in a mesh's instance stream: no copy, the pair's GPU floor); ``none``: eight quads from a
    small storage stream (the base)."""
    from rendering.native.mode import MeshAttribute, ModePass, ModeStream, PassGeometry, RecordLayout

    rows = max(2, int(payload_floats) // 4)
    corner = RecordLayout(8, (MeshAttribute("aCorner", 2, 0),))
    row = RecordLayout(16, (MeshAttribute("aRow", 4, 0),))
    entries = [("u_frame", "f64", 1)]
    checks: list = []
    record: dict = {"u_frame": 0.0}
    streams: tuple = ()
    meshes: tuple = ()
    if kind == "none":
        geometry = PassGeometry(packs["ring.vert"], topology="triangle_strip", vertices=4, instances=8,
                                storage=(("Small", "small"),))
        streams = (ModeStream("small", "small_rows", used="small_floats"),)
        entries += [("small_rows", "f32", 32), ("small_floats", "u32", 1)]
        checks.append(("small_floats", "at_most", 32))
        record["small_floats"] = 32
        record["small_rows"] = _f32([40.0 + 50.0 * i if j == 0 else (60.0 if j == 1 else (30.0 if j == 2 else 0.0))
                                     for i in range(8) for j in range(4)])
    elif kind == "instance":
        geometry = PassGeometry(packs["ring_instance.vert"], topology="triangle_strip", mesh="ring_quad",
                                vertices="mesh", instance_from="payload")
        streams = (ModeStream("payload", "payload", "instance", row, used="payload_floats"),)
        meshes = (("ring_quad", RING_CORNERS, corner, None, None),)
        entries += [("payload", "f32", 4 * rows), ("payload_floats", "u32", 1)]
        checks.append(("payload_floats", "at_most", 4 * rows))
        record["payload"] = ring_rows(rows)
        record["payload_floats"] = 4 * rows if used_floats is None else int(used_floats)
    elif kind == "storage":
        geometry = PassGeometry(packs["ring_storage.vert"], topology="triangle_strip", vertices=4, instances=rows - 1,
                                storage=(("Rows", "payload"),))
        streams = (ModeStream("payload", "payload", used="payload_floats"),)
        entries += [("payload", "f32", 4 * rows), ("payload_floats", "u32", 1)]
        checks.append(("payload_floats", "at_most", 4 * rows))
        record["payload"] = ring_rows(rows)
        record["payload_floats"] = 4 * rows if used_floats is None else int(used_floats)
    elif kind == "floor":
        geometry = PassGeometry(packs["ring_instance.vert"], topology="triangle_strip", mesh="ring_floor",
                                vertices="mesh", instance_from="ring_floor")
        meshes = (("ring_floor", RING_CORNERS, corner, ring_rows(rows), row),)
    else:
        raise KeyError(kind)
    passes = (ModePass("ring", packs["ring.frag"], "alpha", target="scene", geometry=geometry),)
    return SceneSpec(f"ring_{kind}_{payload_floats}", passes, (_target(),), streams,
                     {"u_colour": [0.6, 0.8, 1.0, 0.9]}, schema("ring", tuple(entries), tuple(checks)), record,
                     meshes)


__all__ = ["CARD", "SHADERS", "SceneSpec", "bake_all", "compose", "ring_scene", "scene", "schema"]
