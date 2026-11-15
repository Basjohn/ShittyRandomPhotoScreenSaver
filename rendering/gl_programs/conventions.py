"""The conventions include (``srpss_conventions.glsl``, Docs/Future_Work/Native_Core_P3_Decisions.md N0.3 rule 3): the
one place a shader learns a backend convention, and the front-face rule (N0.3 rule 4).

A shader never writes ``gl_FragCoord`` arithmetic or ``ndc * 0.5 + 0.5`` by hand; it includes this and calls:

- ``vec2 ndcToUv(vec2 ndc)`` / ``vec2 uvToNdc(vec2 uv)``: the clip NDC of the pass's own (uploaded) matrices to its
  target's uv and back. Under the native core (``NATIVE_CORE_DEFINE``) they negate Y where the block's ``y`` says the
  clip NDC's +Y lands on the target's first row (decided F2: D3D11, D3D12 and Metal); in this renderer they are
  today's ``ndc * 0.5 + 0.5`` and ``uv * 2.0 - 1.0`` as written (its ``y`` is 0 for good; see ``NATIVE_CORE_DEFINE``).
- ``float viewDepthFromDepthTexture(float depth)``: a depth texture's sample as the window depth the depth test
  compared, in [0, 1] on every backend after rule 1; the one place a reverse-Z or depth-range change would go.
- ``vec3 srgbToLinear(vec3 encoded)``: the exact IEC 61966-2-1 decode, for an sRGB asset uploaded as plain RGBA8
  (decided F4: the shader decodes on every backend; the GPU filters the encoded values first).
- fragment shaders only (``SRPSS_CONVENTIONS_FRAGMENT_GLSL``): ``vec2 fragPixel(vec2 targetSize)`` (the fragment's
  pixel centre in the target's row convention), ``ivec2 fragTexel(ivec2 targetSize)`` (its texel) and
  ``vec2 fragUv(vec2 targetSize)`` (its uv), from the block's ``x``.

Every stage that includes the text declares the ``SrpssConventions`` std140 block at
``SCENE3D_CONVENTIONS_BLOCK_BINDING`` (SPIR-V is shared by Vulkan, D3D and Metal, so a backend is a value, not a
compile-time branch). Its values belong to the target a pass draws into and are set by the host that owns the target
(decided F1, 12 Nov):

- ``x``, the fragment Y flip: 1 flips ``gl_FragCoord.y`` against the target height. This OpenGL renderer keeps 0 for
  every target: its targets keep OpenGL's bottom-up rows the shaders were authored in, so ``gl_FragCoord`` is already
  the convention they were written for. The native core also writes 0 for every target it owns, on every backend: its
  upload correction flips Y on OpenGL (``clipSpaceCorrMatrix()`` times a Y flip where ``isYUpInFramebuffer()``), so
  texel (0,0) is the top-left in memory everywhere and ``gl_FragCoord`` is the memory texel. 1 would only be right for
  a core shader drawing into a bottom-up target it does not own.
- ``y``, the clip-NDC Y flip: ``isYUpInNDC() && !isYUpInFramebuffer()`` under the native core (1 on D3D11, D3D12,
  Metal); 0 here and on Vulkan and OpenGL.

In this renderer ``rendering.quick.render.gl_resources`` writes ``OPENGL_CONVENTIONS`` once per context (the buffer is
created and bound when the first program declaring the block links, deleted with the last one), never per frame, and
every function is then an identity of the arithmetic it replaced (bit for bit: N1.4's identity runs, and again for F1
and F2 on 12 Nov). The values never change for this renderer until it retires.

The text below is the include as the native core bakes it with ``qsb`` (it is kept here, in Python source, so the
OpenGL renderer composes it without a data file).
"""
from __future__ import annotations

import struct

from rendering.gl_programs.scene3d import SCENE3D_CONVENTIONS_BLOCK_BINDING

CONVENTIONS_BLOCK_NAME = "SrpssConventions"
# Defined by the native core before the include (its qsb bake; native/spike_p1's scene shaders): the mapping functions
# then read the clip-NDC flip from the block (decided F2). This OpenGL renderer never defines it. Its y is 0 for every
# target and never changes, and a value read at run time is not bit-identical here: on NVIDIA 617.42 OpenGL a select on
# the block between ``uv * 2.0 - 1.0`` and ``* 0.5 + 0.5`` changed the last bits of the composed result, because the
# driver no longer folds the arithmetic around it (``tests/test_conventions_include.py``, 12 Nov).
NATIVE_CORE_DEFINE = "SRPSS_NATIVE_CORE"

# srpss_conventions.glsl. The block and the mapping part serve any stage; the gl_FragCoord functions only a stage that
# defines SRPSS_CONVENTIONS_FRAGMENT first. Each part is guarded, so a source composed from several pieces that each
# include it declares everything once.
SRPSS_CONVENTIONS_GLSL = f"""
#ifndef SRPSS_CONVENTIONS_MAPPING
#define SRPSS_CONVENTIONS_MAPPING
layout(std140, binding = {SCENE3D_CONVENTIONS_BLOCK_BINDING}) uniform {CONVENTIONS_BLOCK_NAME} {{
    vec4 srpssConventions;   // the target's: x 1 flips the fragment row; y 1 negates the clip NDC's Y; z, w reserved
}};
#ifdef {NATIVE_CORE_DEFINE}
vec2 ndcToUv(vec2 ndc) {{ return vec2(ndc.x, srpssConventions.y > 0.5 ? -ndc.y : ndc.y) * 0.5 + 0.5; }}
vec2 uvToNdc(vec2 uv) {{
    vec2 ndc = uv * 2.0 - 1.0;
    return vec2(ndc.x, srpssConventions.y > 0.5 ? -ndc.y : ndc.y);
}}
#else
// This renderer: y is 0 for every target and never changes, so these are the authored arithmetic, bit for bit.
vec2 ndcToUv(vec2 ndc) {{ return ndc * 0.5 + 0.5; }}
vec2 uvToNdc(vec2 uv) {{ return uv * 2.0 - 1.0; }}
#endif
float viewDepthFromDepthTexture(float depth) {{ return depth; }}
// IEC 61966-2-1, exactly, for an sRGB asset uploaded as plain RGBA8 (decided F4: no backend's sRGB flag is relied on;
// the GPU filters the encoded values before this decode).
vec3 srgbToLinear(vec3 encoded) {{
    return mix(pow((encoded + 0.055) / 1.055, vec3(2.4)), encoded / 12.92, lessThanEqual(encoded, vec3(0.04045)));
}}
#endif
#if defined(SRPSS_CONVENTIONS_FRAGMENT) && !defined(SRPSS_CONVENTIONS_FRAGMENT_DECLARED)
#define SRPSS_CONVENTIONS_FRAGMENT_DECLARED
vec2 fragPixel(vec2 targetSize) {{
    return vec2(gl_FragCoord.x, srpssConventions.x > 0.5 ? targetSize.y - gl_FragCoord.y : gl_FragCoord.y);
}}
ivec2 fragTexel(ivec2 targetSize) {{ return ivec2(fragPixel(vec2(targetSize))); }}
vec2 fragUv(vec2 targetSize) {{ return fragPixel(targetSize) / targetSize; }}
#endif
"""
SRPSS_CONVENTIONS_FRAGMENT_GLSL = "\n#define SRPSS_CONVENTIONS_FRAGMENT" + SRPSS_CONVENTIONS_GLSL

# The vertex and instance index with OpenGL's meaning on every backend (N1.6): ``srpssVertexIndex`` and
# ``srpssInstanceIndex``. Vulkan GLSL (``qsb`` compiles with ``VULKAN`` defined) has only ``gl_VertexIndex`` and
# ``gl_InstanceIndex``, which add the draw's first vertex and first instance; OpenGL's ``gl_VertexID`` adds the first
# vertex too and ``gl_InstanceID`` never adds a base instance. The renderer draws with no base instance, so both read
# the same numbers; SPIRV-Cross writes the OpenGL target's base-instance term itself.
SRPSS_VERTEX_INDEX_GLSL = """
#ifndef SRPSS_VERTEX_INDEX
#define SRPSS_VERTEX_INDEX
#ifdef VULKAN
#define srpssVertexIndex gl_VertexIndex
#define srpssInstanceIndex gl_InstanceIndex
#else
#define srpssVertexIndex gl_VertexID
#define srpssInstanceIndex gl_InstanceID
#endif
#endif
"""

#: The line a shader file writes where the geometry include goes (D15; after the conventions marker).
GEOMETRY_MARKER = "//@srpss_geometry"
#: The geometry include (D15 points 5 and 6): sprite corners and placement for instanced quads in place of point
#: sprites, and a batched draw's batch index. It reads the conventions block's ``z`` (the native core: 1 where the
#: target's top row lies at clip NDC -Y; this renderer: 0). ``native/core/shaders/srpss_geometry.glsl`` is the same
#: text (a test holds them equal).
SRPSS_GEOMETRY_GLSL = """
#ifndef SRPSS_GEOMETRY
#define SRPSS_GEOMETRY
// The geometry include (D15 points 5 and 6; rendering/gl_programs/conventions.py SRPSS_GEOMETRY_GLSL, the core's
// native/core/shaders/srpss_geometry.glsl holds the same text). It follows the conventions include (its block's z: 1
// where the drawn target's top row lies at clip NDC -Y, the native core's OpenGL and Vulkan targets; 0 in the OpenGL
// renderer's window and targets).
// Instanced quads in place of point sprites: a strip of 4 vertices a sprite (draw(4, n), the sprite as the instance), or a
// list of 6 where the instance is taken. The unit corner has gl_PointCoord's orientation: x right, y down, (0, 0) the
// sprite's top-left.
vec2 srpssSpriteCorner(int vertexIndex) { return vec2(float(vertexIndex & 1), float((vertexIndex >> 1) & 1)); }
vec2 srpssSpriteCornerList(int vertexIndex) {
    int c = vertexIndex % 6;
    return srpssSpriteCorner(c < 3 ? c : (c == 3 ? 2 : (c == 4 ? 1 : 3)));
}
// The clip position of `corner` of a sprite `sizePx` target pixels across, centred on `clipCentre`: the same square of
// pixel centres on every backend.
vec4 srpssSpriteClip(vec4 clipCentre, vec2 corner, float sizePx, vec2 targetPx) {
    vec2 d = vec2(corner.x - 0.5, 0.5 - corner.y) * (2.0 * sizePx) / targetPx;
    if (srpssConventions.z > 0.5) d.y = -d.y;
    return vec4(clipCentre.xy + d * clipCentre.w, clipCentre.zw);
}
// The clip position of a point given top-down over the drawn target (x right, y down, 0 to 1): the target's top row
// where the conventions put it, so a pass that places its geometry by hand (a sprite's centre in an explicit-size
// target, which the item matrix does not map) draws the same image on every backend; in the OpenGL renderer it is
// the authored `(x * 2 - 1, 1 - y * 2)`.
vec2 srpssTopDownClip(vec2 topDown) {
    vec2 ndc = vec2(topDown.x * 2.0 - 1.0, 1.0 - topDown.y * 2.0);
    if (srpssConventions.z > 0.5) ndc.y = -ndc.y;
    return ndc;
}
// A culled sprite: every corner outside the clip volume, a degenerate quad.
vec4 srpssSpriteCulled() { return vec4(2.0, 2.0, 2.0, 1.0); }
// A batched draw's batch (D15 point 6): gl_DrawID in the pass's draw-parameters pack (one multi-draw indirect call;
// #version 460), else the core's per-batch block member u_srpss_batch (one draw a batch at its dynamic offset).
#ifdef SRPSS_DRAW_PARAMETERS
#define srpssBatchIndex gl_DrawID
#else
#define srpssBatchIndex u_srpss_batch
#endif
#endif
"""

# The block's values for every target of this OpenGL renderer (the host's, decided F1): no fragment flip (its targets
# keep the bottom-up rows the shaders were authored in), no clip-NDC flip (OpenGL's clip Y and rows agree), the reserved
# fields zero. Kept until this renderer retires; the native core sets its own per target.
OPENGL_CONVENTIONS = (0.0, 0.0, 0.0, 0.0)
# Clip-space Y in this renderer (QRhi's ``isYUpInNDC()``: false on Vulkan only).
RENDERER_NDC_Y_UP = True


def conventions_block(values: tuple[float, float, float, float] = OPENGL_CONVENTIONS) -> bytes:
    """The block's std140 bytes (one ``vec4``)."""
    return struct.pack("<4f", *values)


def front_face_clockwise(matrix_values, *, ndc_y_up: bool = RENDERER_NDC_Y_UP) -> bool:
    """N0.3 rule 4: whether the counter-clockwise-authored front faces of a culled draw are clockwise on screen, from
    the item matrix's handedness and the backend's clip-space Y. Quick's item matrix is Y-down (``m[0] * m[5] < 0``);
    a mirrored one (same signs) turns the winding, and so does a clip space whose Y points down. Evaluated where a
    pipeline is chosen (the native core prebuilds the clockwise and counter-clockwise variants of each culling pass);
    this OpenGL renderer gives the answer to ``glFrontFace``. ``matrix_values`` is the matrix as uploaded, after the
    upload correction (decided F3, 12 Nov; N0.3 run 1: the uncorrected matrix culls the wrong faces on Vulkan and on
    the core's OpenGL); this renderer uploads uncorrected matrices, so for it the two are the same."""
    mirrored = float(matrix_values[0]) * float(matrix_values[5]) > 0.0
    return mirrored == bool(ndc_y_up)


__all__ = [
    "CONVENTIONS_BLOCK_NAME",
    "GEOMETRY_MARKER",
    "NATIVE_CORE_DEFINE",
    "OPENGL_CONVENTIONS",
    "RENDERER_NDC_Y_UP",
    "SCENE3D_CONVENTIONS_BLOCK_BINDING",
    "SRPSS_CONVENTIONS_FRAGMENT_GLSL",
    "SRPSS_CONVENTIONS_GLSL",
    "SRPSS_GEOMETRY_GLSL",
    "SRPSS_VERTEX_INDEX_GLSL",
    "conventions_block",
    "front_face_clockwise",
]
