"""The mip chain's box, one text for both renderers (Current_Plan.md N5.4: the exact-size mipped target box, ABI 33;
every level chain a sampler reads, the lead's decision of 21 Nov, ABI 35: the item textures' too).

Why it exists: a mip chain made by ``glGenerateTextureMipmap`` (Python) or QRhi's ``generateMips`` (the core) is the
driver's: on this machine's OpenGL its levels made from odd sizes are anchored at memory row 0, and the core stores its
targets top first (F1) where Python stores them bottom first, so the same picture's chain differs from level 3 on at
Waveform's odd reflection sizes (measured: the core's OpenGL chain is exactly Python's own call over the rows stored top
first); on Vulkan ``generateMips`` is a linear blit, another filter again. This kernel is the exact area average of
each destination texel (an even side two taps of 1/2, an odd side 2d + 1 three taps of (d - i), d and (i + 1) over
2d + 1), summed outer taps first with no fused multiply-add, so it gives the same bits whichever way the rows are
stored and on every backend.

``MIP_BOX_COMP`` is ``native/core/shaders/mip_box.comp`` (RGBA16F) and ``MIP_BOX_RGBA8_COMP``
``native/core/shaders/mip_box_rgba8.comp`` (RGBA8; a test holds each equal to its file): one dispatch a level, level
L - 1 bound as ``u_source`` (read) and level L as ``u_dest`` (write), 8 x 8 invocations a group. The core runs them
for a self-mipped scene target's attachments a sampler reads with mips (``native/core/src/scene_targets.cpp``
``generateSelfMips``) and for an item texture uploaded with mips (``mode_content.cpp``, ABI 35), through
``native/core/src/mip_chain.h``; the Python renderer runs the same texts with ``glBindImageTexture`` per level
(``dispatch_mip_chain``).
"""
from __future__ import annotations

_MIP_BOX = """#version 440
// The mip chain's box (N5.4: ABI 33, the self-mipped targets; ABI 35, the item textures; rendering/gl_programs/
// mip_chain.py holds the same texts, a test holds them equal): one level from the one above it, each destination texel
// the exact area average of the source texels it covers (an even side: two taps of 1/2; an odd side 2d + 1: three taps
// of (d - i), d and (i + 1) over 2d + 1; a side of 1: one tap), separable, summed outer taps first so the result is the
// same bit for bit whichever way the rows are stored (the core's targets top first, F1; Python's bottom first). Never
// generateMips: its odd levels are the driver's (anchored at memory row 0 on OpenGL, a linear blit on Vulkan) and
// differ between the two renderers. This text's images are %(format)s.
layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;
layout(binding = 0, %(format)s) readonly uniform image2D u_source;
layout(binding = 1, %(format)s) writeonly uniform image2D u_dest;

void taps(int i, int s, out ivec3 at, out vec3 w)
{
    if (s == 1) {
        at = ivec3(0, 0, 0);
        w = vec3(0.0, 1.0, 0.0);
    } else if ((s & 1) == 0) {
        at = ivec3(2 * i, 2 * i, 2 * i + 1);
        w = vec3(0.5, 0.0, 0.5);
    } else {
        int d = s / 2;
        at = ivec3(2 * i, 2 * i + 1, 2 * i + 2);
        w = vec3(float(d - i), float(d), float(i + 1)) / float(s);
    }
}

vec4 row(int y, ivec3 ax, vec3 wx)
{
    // precise: no fused multiply-add, so the outer pair's sum is the same whichever tap comes first.
    precise vec4 outer = wx.x * imageLoad(u_source, ivec2(ax.x, y)) + wx.z * imageLoad(u_source, ivec2(ax.z, y));
    precise vec4 sum = outer + wx.y * imageLoad(u_source, ivec2(ax.y, y));
    return sum;
}

void main()
{
    ivec2 dst = ivec2(gl_GlobalInvocationID.xy);
    ivec2 size = imageSize(u_dest);
    if (dst.x >= size.x || dst.y >= size.y)
        return;
    ivec2 source = imageSize(u_source);
    ivec3 ax;
    ivec3 ay;
    vec3 wx;
    vec3 wy;
    taps(dst.x, source.x, ax, wx);
    taps(dst.y, source.y, ay, wy);
    precise vec4 outer = wy.x * row(ay.x, ax, wx) + wy.z * row(ay.z, ax, wx);
    precise vec4 sum = outer + wy.y * row(ay.y, ax, wx);
%(store)s}
"""
_STORE = "    imageStore(u_dest, dst, sum);\n"
#: An 8-bit level is rounded in the kernel, once, to the nearest of its 256 values (precise: no fused multiply-add, so
#: both backends compute the same k), and the store then converts an exact value: the backends' own float-to-unorm
#: conversions differ near the halves (measured 21 Nov on the ABI 35 build: 509 of the 14,508 level-1 texels of the
#: chain scene one level apart between OpenGL and Vulkan, every one at a fraction between 0.486 and 0.585).
_STORE_RGBA8 = ("    // Rounded here to the nearest 8-bit value (the backends' own conversions differ at the halves).\n"
                "    precise vec4 level = floor(sum * 255.0 + 0.5) / 255.0;\n"
                "    imageStore(u_dest, dst, level);\n")
MIP_BOX_COMP = _MIP_BOX % {"format": "rgba16f", "store": _STORE}
MIP_BOX_RGBA8_COMP = _MIP_BOX % {"format": "rgba8", "store": _STORE_RGBA8}
#: The kernel's text by its images' format (the core's two shader files).
MIP_BOX_TEXTS = {"rgba16f": MIP_BOX_COMP, "rgba8": MIP_BOX_RGBA8_COMP}
MIP_BOX_GROUP = 8


def mip_levels(size: tuple[int, int]) -> int:
    """A full chain's levels for ``size`` (level 0 included): ``native/core/src/mip_chain.cpp`` mipChainLevels, and
    ``glTextureStorage2D``'s ``max(size).bit_length()``."""
    return max(1, max(int(size[0]), int(size[1])).bit_length())


def dispatch_mip_chain(program: int, texture: int, size: tuple[int, int], levels: int, fmt: str = "rgba16f") -> None:
    """Every level of ``texture`` (``fmt``: RGBA16F or RGBA8, ``levels`` levels, level 0 of ``size``) from the one above
    it, with the compiled ``MIP_BOX_TEXTS[fmt]`` ``program`` (the caller's current GL context; an image barrier after
    each level)."""
    from OpenGL import GL as gl

    internal = {"rgba16f": gl.GL_RGBA16F, "rgba8": gl.GL_RGBA8}[fmt]
    gl.glUseProgram(program)
    for level in range(1, levels):
        width, height = max(1, size[0] >> level), max(1, size[1] >> level)
        gl.glBindImageTexture(0, texture, level - 1, gl.GL_FALSE, 0, gl.GL_READ_ONLY, internal)
        gl.glBindImageTexture(1, texture, level, gl.GL_FALSE, 0, gl.GL_WRITE_ONLY, internal)
        gl.glDispatchCompute((width + MIP_BOX_GROUP - 1) // MIP_BOX_GROUP, (height + MIP_BOX_GROUP - 1) // MIP_BOX_GROUP,
                             1)
        gl.glMemoryBarrier(gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | gl.GL_TEXTURE_FETCH_BARRIER_BIT)
    gl.glUseProgram(0)


__all__ = ["MIP_BOX_COMP", "MIP_BOX_GROUP", "MIP_BOX_RGBA8_COMP", "MIP_BOX_TEXTS", "dispatch_mip_chain", "mip_levels"]
