"""The conventions include (``srpss_conventions.glsl``, Docs/Future_Work/Native_Core_P3_Decisions.md N0.3 rule 3): the
one place a shader learns a backend convention, and the front-face rule (N0.3 rule 4).

A shader never writes ``gl_FragCoord`` arithmetic or ``ndc * 0.5 + 0.5`` by hand; it includes this and calls:

- ``vec2 ndcToUv(vec2 ndc)`` / ``vec2 uvToNdc(vec2 uv)``: normalised device coordinates to a target's uv and back.
  After the projection correction at upload (rule 1) this is one expression on every backend.
- ``float viewDepthFromDepthTexture(float depth)``: a depth texture's sample as the window depth the depth test
  compared, in [0, 1] on every backend after rule 1; the one place a reverse-Z or depth-range change would go.
- fragment shaders only (``SRPSS_CONVENTIONS_FRAGMENT_GLSL``): ``vec2 fragPixel(vec2 targetSize)`` (the fragment's
  pixel centre in the renderer's target convention), ``ivec2 fragTexel(ivec2 targetSize)`` (its texel) and
  ``vec2 fragUv(vec2 targetSize)`` (its uv). They read the backend's value from the ``SrpssConventions`` std140
  block at ``SCENE3D_CONVENTIONS_BLOCK_BINDING``: SPIR-V is shared by Vulkan, D3D and Metal, so a backend is a value,
  not a compile-time branch.

The block's values are written once per context (``rendering.quick.render.gl_resources`` creates and binds the buffer
when the first program declaring it links, and deletes it with the last one), never per frame. In this OpenGL renderer
every target keeps OpenGL's bottom-up rows the shaders were authored in, so ``OPENGL_CONVENTIONS`` makes every
function an identity of the arithmetic it replaced (bit for bit: N1.4's identity runs). The native core (lead's
decision on N0.3: core-owned targets are top-left, Y down on every backend; OpenGL is the backend that flips) sets the
flip on its OpenGL backend and leaves it off on Vulkan, D3D and Metal.

The text below is the include as the native core bakes it with ``qsb`` (it is kept here, in Python source, so the
OpenGL renderer composes it without a data file).
"""
from __future__ import annotations

import struct

from rendering.gl_programs.scene3d import SCENE3D_CONVENTIONS_BLOCK_BINDING

CONVENTIONS_BLOCK_NAME = "SrpssConventions"

# srpss_conventions.glsl. The mapping part serves any stage; the fragment part (the block and the gl_FragCoord
# functions) only a stage that defines SRPSS_CONVENTIONS_FRAGMENT first. Each part is guarded, so a source composed
# from several pieces that each include it declares everything once.
SRPSS_CONVENTIONS_GLSL = f"""
#ifndef SRPSS_CONVENTIONS_MAPPING
#define SRPSS_CONVENTIONS_MAPPING
vec2 ndcToUv(vec2 ndc) {{ return ndc * 0.5 + 0.5; }}
vec2 uvToNdc(vec2 uv) {{ return uv * 2.0 - 1.0; }}
float viewDepthFromDepthTexture(float depth) {{ return depth; }}
#endif
#if defined(SRPSS_CONVENTIONS_FRAGMENT) && !defined(SRPSS_CONVENTIONS_FRAGMENT_DECLARED)
#define SRPSS_CONVENTIONS_FRAGMENT_DECLARED
layout(std140, binding = {SCENE3D_CONVENTIONS_BLOCK_BINDING}) uniform {CONVENTIONS_BLOCK_NAME} {{
    vec4 srpssConventions;   // x: 1 flips gl_FragCoord.y against the target height, 0 keeps it; y, z, w: reserved
}};
vec2 fragPixel(vec2 targetSize) {{
    return vec2(gl_FragCoord.x, srpssConventions.x > 0.5 ? targetSize.y - gl_FragCoord.y : gl_FragCoord.y);
}}
ivec2 fragTexel(ivec2 targetSize) {{ return ivec2(fragPixel(vec2(targetSize))); }}
vec2 fragUv(vec2 targetSize) {{ return fragPixel(targetSize) / targetSize; }}
#endif
"""
SRPSS_CONVENTIONS_FRAGMENT_GLSL = "\n#define SRPSS_CONVENTIONS_FRAGMENT" + SRPSS_CONVENTIONS_GLSL

# The block's values in this OpenGL renderer: no flip (its targets keep the bottom-up rows the shaders were authored
# in), the reserved fields zero.
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
    this OpenGL renderer gives the answer to ``glFrontFace``."""
    mirrored = float(matrix_values[0]) * float(matrix_values[5]) > 0.0
    return mirrored == bool(ndc_y_up)


__all__ = [
    "CONVENTIONS_BLOCK_NAME",
    "OPENGL_CONVENTIONS",
    "RENDERER_NDC_Y_UP",
    "SCENE3D_CONVENTIONS_BLOCK_BINDING",
    "SRPSS_CONVENTIONS_FRAGMENT_GLSL",
    "SRPSS_CONVENTIONS_GLSL",
    "conventions_block",
    "front_face_clockwise",
]
