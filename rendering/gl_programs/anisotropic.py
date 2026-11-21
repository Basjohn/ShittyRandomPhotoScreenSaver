"""Anisotropic filtering written in the shader, one text for both renderers (Current_Plan.md N5.4, the sampler
anisotropy box).

Why it exists: QRhi's sampler carries no anisotropy on any backend (Qt 6.12's ``QRhiSampler`` holds the filters, the
mip filter, the three address modes and the compare op only, and offers no ``QRhi::Feature`` for it; its Vulkan sampler
is made at ``maxAnisotropy`` 1), while the Python renderer sets it on its textures with ``GL_TEXTURE_MAX_ANISOTROPY``
(16x on Waveform's reflection, ``rendering/quick/scene3d/reflection.py``; 8x on its floor maps,
``rendering/quick/scene3d/waveform.py``). A raw sampler setting would be a native route beside QRhi on each backend (a
Vulkan sampler QRhi does not make, a GL texture parameter QRhi does not track): the lead's line, not taken here. This is
the means both renderers can share: the footprint's major axis split into taps, each filtered at the minor axis's level
(the model of ``EXT_texture_filter_anisotropic``: N = min(ceil(Pmax / Pmin), max), the level log2(Pmax / N)).

``ANISOTROPIC_GLSL`` declares ``srpssAnisotropic(sampler2D, uv, dPdx, dPdy, maxAnisotropy)``; a shader passes its own
gradients (``dFdx``/``dFdy`` of its coordinate, or the footprint it already gives ``textureGrad``). The taps are
symmetric about ``uv``, so the gradients' signs (``dFdy`` runs the other way on Vulkan) change nothing. Sampled with the
texture's sampler at 1x (the hardware's own anisotropy off), a pass reads at most ``ANISOTROPIC_MAX_TAPS`` texels' worth
of filtered taps per call.
"""
from __future__ import annotations

#: The most taps one call takes (the loop's constant bound; ``maxAnisotropy`` is clamped to it).
ANISOTROPIC_MAX_TAPS = 16

ANISOTROPIC_GLSL = """
// Anisotropic filtering in the shader (rendering/gl_programs/anisotropic.py): taps along the footprint's major axis,
// each filtered at the minor axis's level, averaged (EXT_texture_filter_anisotropic's model).
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
    float n = clamp(ceil(pMax / max(pMin, 1e-8)), 1.0, min(maxAnisotropy, %(taps)d.0));
    int count = int(n);
    vec2 stepUv = major / n;
    vec4 sum = vec4(0.0);
    for (int i = 0; i < %(taps)d; ++i) {
        if (i >= count)
            break;
        float t = (float(i) + 0.5) / n - 0.5;
        sum += textureGrad(tex, uv + major * t, stepUv, minor);
    }
    return sum / n;
}
""" % {"taps": ANISOTROPIC_MAX_TAPS}

__all__ = ["ANISOTROPIC_GLSL", "ANISOTROPIC_MAX_TAPS"]
