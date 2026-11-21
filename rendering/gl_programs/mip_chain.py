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

# The template starts after its version line, so the shader-source scan (``tools/vulkan_shader_readiness.py``) bakes the
# two texts and never the template itself.
_MIP_BOX_VERSION = "#version 440\n"
_MIP_BOX = """// The mip chain's box (N5.4: ABI 33, the self-mipped targets; ABI 35, the item textures; rendering/gl_programs/
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
MIP_BOX_COMP = _MIP_BOX_VERSION + _MIP_BOX % {"format": "rgba16f", "store": _STORE}

#: The RGBA8 text sums integers: each loaded texel is taken back to its 8-bit value 0..255 (``unorm8``) and the level
#: rounded once to the nearest of them before its store. Why (measured 21 Nov on the ABI 35 builds, the chain scene):
#: NVIDIA's OpenGL returns an RGBA8 image's texel at half-float precision (k / 255 off by up to 2.4e-4) where its Vulkan
#: returns it at single precision, so float sums of the loads differed by up to 0.06 of a level and rounded apart at
#: the halves (530 of the 14,508 level-1 texels one level apart, at fractions 0.46 to 0.53; Vulkan matched the exact
#: average, OpenGL did not); and even sides' ties (a sum ending in exactly .5) fell either way on the loads' last bits.
#: Integers are exact in any precision, so both backends sum the same values, ties included, and the store converts an
#: exact 8-bit value.
_UNORM8 = """// An 8-bit texel as its integer value 0..255, recovered exactly whatever precision the load returns (NVIDIA's OpenGL
// loads an RGBA8 image at half-float precision, its Vulkan at single), so the sums below are of integers and every
// backend computes the same bits, ties included.
vec4 unorm8(ivec2 p)
{
    return floor(imageLoad(u_source, p) * 255.0 + 0.5);
}

vec4 row("""
_STORE_RGBA8 = ("    // The level in 8-bit units, rounded once to the nearest value and stored exactly.\n"
                "    precise vec4 level = floor(sum + 0.5) / 255.0;\n"
                "    imageStore(u_dest, dst, level);\n")


def _rgba8_text() -> str:
    text = _MIP_BOX_VERSION + _MIP_BOX % {"format": "rgba8", "store": _STORE_RGBA8}
    for tap in ("ax.x", "ax.z", "ax.y"):
        old = f"imageLoad(u_source, ivec2({tap}, y))"
        assert text.count(old) == 1, old
        text = text.replace(old, f"unorm8(ivec2({tap}, y))")
    assert text.count("\nvec4 row(") == 1
    return text.replace("\nvec4 row(", "\n" + _UNORM8, 1)


MIP_BOX_RGBA8_COMP = _rgba8_text()
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
