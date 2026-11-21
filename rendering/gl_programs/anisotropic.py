"""Anisotropic filtering written in the shader, one text for both renderers (Current_Plan.md N5.4, the sampler
anisotropy box).

Why it exists: QRhi's sampler carries no anisotropy on any backend (Qt 6.12's ``QRhiSampler`` holds the filters, the
mip filter, the three address modes and the compare op only, and offers no ``QRhi::Feature`` for it; its Vulkan sampler
is made at ``maxAnisotropy`` 1), while the Python renderer sets it on its textures with ``GL_TEXTURE_MAX_ANISOTROPY``
(16x on Waveform's reflection, ``rendering/quick/scene3d/reflection.py``; 8x on its floor maps,
``rendering/quick/scene3d/waveform.py``). A raw sampler setting would be a native route beside QRhi on each backend (a
Vulkan sampler QRhi does not make, a GL texture parameter QRhi does not track): the lead's line, not taken here. This is
the means both renderers can share: the footprint's major axis covered by taps, each filtered at the minor axis's
level (the model of ``EXT_texture_filter_anisotropic``: the footprint's ratio r = Pmax / Pmin, up to the maximum, the
level log2(Pmax / r)).

The taps sit on a fixed lattice along the major axis, one minor width apart and centred on ``uv``, each weighted by its
overlap with the footprint [-r/2, r/2]: a tap enters at the footprint's ends with weight 0, so the result is
continuous in the gradients (a tap count jumping at an integer ratio would move a pixel by several levels between the
two renderers, whose interpolated coordinates differ in their last bits: the core rasterises its targets top first).
The lattice is symmetric about ``uv``, so the gradients' signs (``dFdy`` runs the other way on Vulkan) change nothing.

``ANISOTROPIC_GLSL`` declares ``srpssAnisotropic(sampler2D, uv, dPdx, dPdy, maxAnisotropy)``; a shader passes its own
gradients (``dFdx``/``dFdy`` of its coordinate, or the footprint it already gives ``textureGrad``), sampling with the
texture's sampler at 1x (the hardware's own anisotropy off). A call reads at most ``ANISOTROPIC_MAX_TAPS`` filtered taps
(the ratio is clamped below it).
"""
from __future__ import annotations

#: The most taps one call takes (the lattice's reach either side of ``uv`` is half of one less; the ratio stays below).
ANISOTROPIC_MAX_TAPS = 15
_REACH = (ANISOTROPIC_MAX_TAPS - 1) // 2

ANISOTROPIC_GLSL = """
// Anisotropic filtering in the shader (rendering/gl_programs/anisotropic.py): taps on a lattice along the footprint's
// major axis, each weighted by its overlap with the footprint and filtered at the minor axis's level.
vec4 srpssAnisotropic(sampler2D tex, vec2 uv, vec2 dPdx, vec2 dPdy, float maxAnisotropy)
{
    vec2 size = vec2(textureSize(tex, 0));
    vec2 px = dPdx * size;
    vec2 py = dPdy * size;
    float lx = dot(px, px);
    float ly = dot(py, py);
    bool xMajor = lx >= ly;
    vec2 major = xMajor ? dPdx : dPdy;
    vec2 minor = xMajor ? dPdy : dPdx;
    float pMax = sqrt(max(lx, ly));
    float pMin = sqrt(min(lx, ly));
    float r = clamp(pMax / max(pMin, 1e-8), 1.0, min(maxAnisotropy, %(taps)d.0));
    int reach = int(ceil((r - 1.0) * 0.5));
    vec2 stepUv = major / r;
    vec4 sum = vec4(0.0);
    for (int j = -%(reach)d; j <= %(reach)d; ++j) {
        if (j < -reach || j > reach)
            continue;
        float t = float(j);
        float w = max(0.0, min(t + 0.5, 0.5 * r) - max(t - 0.5, -0.5 * r));
        sum += w * textureGrad(tex, uv + stepUv * t, stepUv, minor);
    }
    return sum / r;
}
""" % {"taps": ANISOTROPIC_MAX_TAPS, "reach": _REACH}

__all__ = ["ANISOTROPIC_GLSL", "ANISOTROPIC_MAX_TAPS"]
