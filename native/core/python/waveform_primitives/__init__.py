"""N5.4's harness scenes for Waveform's five C++ boxes (Current_Plan.md item N5.4; ABI 33): harness-only and never
registered (like ``scene_targets``). Stills (no stream): a program, its settings, its textures and the card are the
frame. Run by ``native/core/python/scene_target_check.py --rounds waveform`` (the rounds are in that file).

The floor scene (boxes 1 to 3), Waveform's shape at odd sizes:
- ``reflection``: an explicit-size, exact, mipped RGBA16F target with a depth (the planar reflection): ``refl_sky``
  (replace, depth always, ``gl_FragDepth``) and ``refl_light`` (ONE, ONE, depth less). Their text writes colour AND
  emission (Waveform's light shaders); the core draws its one-output variant (``ONE_OUTPUT``: the same text with
  ``WAVE_ONE_OUTPUT`` defined, as the port's wrapper file will), Python the text itself into its one attachment. Its
  chain is the shared box kernel's after the run (``rendering.gl_programs.mip_chain``) in both renderers;
  ``reference_frames("driver_chain")`` is Python's shipping ``glGenerateTextureMipmap`` (a fact, never the oracle).
- ``prepass``: an explicit-size, exact RGBA16F target (the floor's reduced pre-pass), one pass.
- ``slope_levels``: every level of the item texture ``slope`` (RGBA16F with mips made on the GPU, Waveform's slope map
  baked from a height map) laid side by side by ``texelFetch``: the levels as the GPU made them.
- ``floor``: an explicit-size target with four RGBA16F attachments read back apart: ``checker`` (the RGBA8 item
  texture ``checker`` on a grazing plane, anisotropic taps or one plain read), ``reflection`` (the reflection read
  with ``textureGrad`` footprints, taps or one read), ``relief`` (the slope map at Waveform's mip bias, shaded; the
  pre-pass read in alpha), ``mean`` (the reflection's 1x1 level: Waveform's scene mean).
- ``show``: the surface's look (not judged).

The shape program (box 4): Waveform's counts as stand-ins: 7 compute entries over 9 storage images (the world field 1,
floor give 2, two fog volumes 3 each), 4 targets (the scene with colour, emission and depth; its transparency target;
the exact mipped reflection; the pre-pass), 28 passes in all with the transparency resolve, the bloom and the
composite; ``shape_program(extra_pass=True)`` and ``extra_image=True`` are the refusals one past each limit.

The float-filter program (box 5): an RGBA32F storage image (the world field's format) read by a linear sampler.

Every fragment is product-shaped (``vUv`` y up over its target's content, one block at binding 18) so the Python
reference (an offscreen GL context, ``reference_frames``) draws the same text.
"""
from __future__ import annotations

import math
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent

REFLECTION = (333, 187)        # odd on both axes: every level past 0 is made from an odd size on one axis or both
PREPASS = (251, 141)
FLOOR = (480, 270)
CHECKER = 512                  # the RGBA8 floor map (power of two: its levels are exact halves on every backend)
SLOPE = 128                    # the RGBA16F slope map (a power of two: its levels are exact halves on both backends)
WAVEFORM_ANISOTROPY = {"maps": 8.0, "reflection": 16.0}   # Python's: waveform.py's 8x, reflection.py's 16x


def slope_levels_size() -> tuple[int, int]:
    """The probe target: every level of the slope map side by side (level 0 at the left)."""
    width, side = 0, SLOPE
    while True:
        width += side
        if side == 1:
            break
        side = max(1, side // 2)
    return width, SLOPE


_HEADER = "#version 440\nlayout(location = 0) in vec2 vUv;\n"

REFL_SKY = _HEADER + """// N5.4's harness: the reflected sky into the one-attachment reflection, with the emission Waveform's light
// shaders write at location 1 (Python's one-attachment framebuffer drops it; the core draws the one-output variant).
layout(location = 0) out vec4 colour;
#ifndef WAVE_ONE_OUTPUT
layout(location = 1) out vec4 emission;
#endif
layout(std140, binding = 18) uniform WaveReflSky {
    vec4 u_sky_low;
    vec4 u_sky_high;
    float u_sky_depth;
};
void main()
{
    vec3 sky = mix(u_sky_low.rgb, u_sky_high.rgb, vUv.y);
    float band = 0.5 + 0.5 * sin(vUv.x * 91.0) * sin(vUv.y * 57.0);
    colour = vec4(sky * (0.6 + 0.8 * band), 0.25 + 0.5 * vUv.x);
#ifndef WAVE_ONE_OUTPUT
    emission = vec4(1.0, 0.0, 1.0, 1.0);
#endif
    gl_FragDepth = u_sky_depth;
}
"""

REFL_LIGHT = _HEADER + """// N5.4's harness: the ribbon light added into the reflection (ONE, ONE, depth less), light past white.
layout(location = 0) out vec4 colour;
#ifndef WAVE_ONE_OUTPUT
layout(location = 1) out vec4 emission;
#endif
layout(std140, binding = 18) uniform WaveReflLight {
    vec4 u_light_colour;
    float u_light_depth;
};
void main()
{
    vec2 d = (vUv - vec2(0.62, 0.41)) * vec2(1.7, 1.0);
    float glow = exp(-dot(d, d) * 60.0);
    colour = vec4(u_light_colour.rgb * (3.0 * glow), 0.5 * glow);
#ifndef WAVE_ONE_OUTPUT
    emission = vec4(glow);
#endif
    gl_FragDepth = u_light_depth;
}
"""

PREPASS_FRAG = _HEADER + """// N5.4's harness: the floor's reduced pre-pass (its own exact RGBA16F target).
layout(location = 0) out vec4 colour;
layout(std140, binding = 18) uniform WavePrepass {
    vec4 u_pre_tint;
};
void main()
{
    colour = vec4(u_pre_tint.rgb * (0.5 + 0.5 * cos(vUv.x * 37.0 + vUv.y * 23.0)), 1.0);
}
"""

SLOPE_PROBE = _HEADER + """// N5.4's harness: every level of the slope map side by side, by texelFetch (the levels as the GPU made them).
layout(location = 0) out vec4 colour;
layout(std140, binding = 18) uniform WaveSlopeProbe {
    vec2 u_target_px;
};
layout(binding = 1) uniform sampler2D u_slope;
void main()
{
    ivec2 p = ivec2(floor(vec2(vUv.x, 1.0 - vUv.y) * u_target_px)); // x right, y down from the top row
    int levels = textureQueryLevels(u_slope);
    int offset = 0;
    colour = vec4(0.0);
    for (int level = 0; level < 16; ++level) {
        if (level >= levels)
            break;
        ivec2 size = textureSize(u_slope, level);
        if (p.x < offset + size.x) {
            if (p.y < size.y)
                colour = texelFetch(u_slope, ivec2(p.x - offset, p.y), level);
            break;
        }
        offset += size.x;
    }
}
"""


def one_output(text: str) -> str:
    """The one-output variant of a light shader (the port's wrapper file: ``#define WAVE_ONE_OUTPUT`` then the same
    text), what the core draws into a one-attachment target."""
    head, rest = text.split("\n", 1)
    return head + "\n#define WAVE_ONE_OUTPUT\n" + rest


#: The passes the core draws as their one-output variant.
ONE_OUTPUT = ("refl_sky", "refl_light")


def floor_text() -> str:
    from rendering.gl_programs.anisotropic import ANISOTROPIC_GLSL
    from rendering.gl_programs.conventions import SRPSS_CONVENTIONS_GLSL

    return _HEADER + """// N5.4's harness: Waveform's floor reads on a grazing plane, one attachment each (read back apart).
layout(location = 0) out vec4 checker_out;
layout(location = 1) out vec4 reflection_out;
layout(location = 2) out vec4 relief_out;
layout(location = 3) out vec4 mean_out;
layout(std140, binding = 18) uniform WaveFloor {
    float u_taps;               // 1: the anisotropic taps; 0: one read (the hardware's 1x, or its own anisotropy)
    float u_aniso_maps;         // Waveform's floor maps' 8x
    float u_aniso_reflection;   // Waveform's reflection's 16x
    float u_slope_bias;         // Waveform's slope mip bias
    float u_slope_encoded;      // 1: the slope stored as RGBA8 (x * 0.25 + 0.5), the half-float box's control
    float u_horizon;
    float u_tiling;
    float u_footprint;          // the reflection footprint's scale (Waveform's roughness)
};
layout(binding = 1) uniform sampler2D u_checker;
layout(binding = 2) uniform sampler2D u_reflection;
layout(binding = 3) uniform sampler2D u_slope;
layout(binding = 4) uniform sampler2D u_prepass;
""" + SRPSS_CONVENTIONS_GLSL + ANISOTROPIC_GLSL + """
// A scene target's image uv as each renderer stores it: the core's targets are top first (F1; their conventions' z is
// 1), Python's bottom first (0). Item textures are rows top first in both (no flip).
vec2 targetUv(vec2 uv) { return srpssConventions.z > 0.5 ? vec2(uv.x, 1.0 - uv.y) : uv; }
void main()
{
    vec2 p = vUv * 2.0 - 1.0;
    float h = max(u_horizon - p.y, 0.02);
    float below = step(0.02, u_horizon - p.y);
    vec2 floorUv = vec2(p.x / h, 1.0 / h) * (0.25 * u_tiling);
    vec2 dx = dFdx(floorUv);
    vec2 dy = dFdy(floorUv);
    vec4 checker = u_taps > 0.5 ? srpssAnisotropic(u_checker, floorUv, dx, dy, u_aniso_maps)
                                : texture(u_checker, floorUv);
    checker_out = vec4(checker.rgb * below, below);
    vec2 reflUv = targetUv(clamp(vec2(vUv.x + 0.03 * sin(floorUv.y * 5.0), 1.0 - vUv.y), 0.0, 1.0));
    vec2 rdx = dFdx(reflUv) * u_footprint;
    vec2 rdy = dFdy(reflUv) * u_footprint;
    vec4 reflection = u_taps > 0.5 ? srpssAnisotropic(u_reflection, reflUv, rdx, rdy, u_aniso_reflection)
                                   : textureGrad(u_reflection, reflUv, rdx, rdy);
    reflection_out = vec4(reflection.rgb * below, reflection.a);
    // The slope map at Waveform's mip bias: the taps over the biased footprint (2^bias), or one biased read.
    vec2 slopeUv = floorUv * 0.5;
    float biasScale = exp2(u_slope_bias);
    vec4 slope = u_taps > 0.5 ? srpssAnisotropic(u_slope, slopeUv, dx * (0.5 * biasScale), dy * (0.5 * biasScale),
                                                 u_aniso_maps)
                              : texture(u_slope, slopeUv, u_slope_bias);
    if (u_slope_encoded > 0.5)
        slope = (slope - 0.5) * 4.0;
    vec3 n = normalize(vec3(-slope.x, 1.0, -slope.y));
    vec3 l = normalize(vec3(0.35, 0.8, -0.45));
    vec3 v = normalize(vec3(-p.x, h, 1.0));
    float diffuse = max(dot(n, l), 0.0);
    float specular = pow(max(dot(reflect(-l, n), v), 0.0), 48.0);
    vec4 prepass = texture(u_prepass, targetUv(vUv));
    relief_out = vec4(vec3(diffuse, specular, slope.z) * below, prepass.g);
    ivec2 size = textureSize(u_reflection, 0);
    float top = floor(log2(float(max(size.x, size.y))));
    mean_out = textureLod(u_reflection, vec2(0.5), top);
}
"""


SHOW = _HEADER + """// N5.4's harness: the surface's look (not judged).
layout(location = 0) out vec4 colour;
layout(binding = 1) uniform sampler2D u_floor;
void main()
{
    colour = vec4(texture(u_floor, vUv).rgb, 1.0);
}
"""

FILTERED_FIELD = _HEADER + """// N5.4's harness: a storage image read through a linear sampler (Waveform's world field: RGBA32F).
layout(location = 0) out vec4 colour;
layout(binding = 1) uniform sampler2D u_field;
void main()
{
    colour = vec4(texture(u_field, vUv).rgb, 1.0);
}
"""


def texts() -> dict[str, str]:
    return {"refl_sky": REFL_SKY, "refl_light": REFL_LIGHT, "refl_sky_two_outputs": REFL_SKY,
            "prepass": PREPASS_FRAG, "slope_probe": SLOPE_PROBE,
            "floor": floor_text(), "show": SHOW, "filtered_field": FILTERED_FIELD, **shape_texts()}


BLOCKS = {"refl_sky": "WaveReflSky", "refl_light": "WaveReflLight", "prepass": "WavePrepass",
          "slope_probe": "WaveSlopeProbe", "floor": "WaveFloor"}

#: std140 members of each harness block, in order (the reference packs them; the core reflects the pack).
LAYOUTS = {
    "WaveReflSky": (("u_sky_low", 4), ("u_sky_high", 4), ("u_sky_depth", 1)),
    "WaveReflLight": (("u_light_colour", 4), ("u_light_depth", 1)),
    "WavePrepass": (("u_pre_tint", 4),),
    "WaveSlopeProbe": (("u_target_px", 2),),
    "WaveFloor": (("u_taps", 1), ("u_aniso_maps", 1), ("u_aniso_reflection", 1), ("u_slope_bias", 1),
                  ("u_slope_encoded", 1), ("u_horizon", 1), ("u_tiling", 1), ("u_footprint", 1)),
}

SETTINGS = {
    "u_sky_low": [0.05, 0.12, 0.3, 1.0], "u_sky_high": [0.6, 0.75, 1.2, 1.0], "u_sky_depth": 0.9,
    "u_light_colour": [1.0, 0.55, 0.25, 1.0], "u_light_depth": 0.5,
    "u_pre_tint": [0.3, 0.8, 0.6, 1.0],
    "u_taps": 1.0, "u_aniso_maps": WAVEFORM_ANISOTROPY["maps"], "u_aniso_reflection": WAVEFORM_ANISOTROPY["reflection"],
    "u_slope_bias": 0.75, "u_slope_encoded": 0.0, "u_horizon": 0.45, "u_tiling": 6.0, "u_footprint": 4.0,
}


def std140(layout, values: dict) -> bytes:
    """One block of ``LAYOUTS`` packed by std140 (scalars at 4, vec2 at 8, vec4 at 16), float32."""
    out = bytearray()
    for name, components in layout:
        align = {1: 4, 2: 8, 4: 16}[components]
        while len(out) % align:
            out.append(0)
        value = values[name]
        numbers = [float(value)] if components == 1 else [float(v) for v in value][:components]
        out += struct.pack(f"<{components}f", *numbers)
    while len(out) % 16:
        out.append(0)
    return bytes(out)


def bake_all(folder: Path) -> dict[str, bytes]:
    import probe_rings

    return {name: probe_rings.bake(one_output(text) if name in ONE_OUTPUT else text,
                                   f"wave_{name}.frag" if not name.startswith("shape_comp") else f"wave_{name}.comp",
                                   folder)
            for name, text in texts().items()}


# ------------------------------------------------------------------------------------------------------- the textures

def checker_pixels():
    """The RGBA8 floor map: a fine checker with a diagonal stripe (detail every level must filter), rows top first."""
    import numpy as np

    y, x = np.mgrid[0:CHECKER, 0:CHECKER]
    check = ((x // 8 + y // 8) % 2).astype(np.float64)
    stripe = 0.5 + 0.5 * np.sin((x + 2 * y) * (2 * math.pi / 23.0))
    rgba = np.stack([0.15 + 0.7 * check, 0.2 + 0.6 * stripe, 0.35 + 0.5 * check * stripe, np.ones_like(check)], -1)
    return np.clip(np.rint(rgba * 255.0), 0, 255).astype(np.uint8)


def slope_values():
    """The slope map baked from a height map (Waveform's: slope x, slope z, height, 1), float32, rows top first."""
    import numpy as np

    y, x = np.mgrid[0:SLOPE, 0:SLOPE].astype(np.float64)
    u, v = x * (2 * math.pi / SLOPE), y * (2 * math.pi / SLOPE)
    height = 0.6 * np.sin(3 * u) * np.cos(2 * v) + 0.25 * np.sin(7 * u + 5 * v)
    dx = 0.6 * 3 * np.cos(3 * u) * np.cos(2 * v) + 0.25 * 7 * np.cos(7 * u + 5 * v)
    dz = -0.6 * 2 * np.sin(3 * u) * np.sin(2 * v) + 0.25 * 5 * np.cos(7 * u + 5 * v)
    scale = 2 * math.pi / SLOPE * 6.0
    return np.stack([dx * scale, dz * scale, height, np.ones_like(height)], -1).astype(np.float32)


def slope_texture(encoded: bool):
    """(bytes, format): the slope map as RGBA16F half floats, or (the control) encoded into RGBA8 (x * 0.25 + 0.5)."""
    import numpy as np

    values = slope_values()
    if encoded:
        return np.clip(np.rint((values * 0.25 + 0.5) * 255.0), 0, 255).astype(np.uint8).tobytes(), "rgba8"
    return values.astype(np.float16).tobytes(), "rgba16f"


# ------------------------------------------------------------------------------------------------------- the programs

def floor_program(packs: dict, *, reflection_allocation: str = "exact"):
    """(passes, targets) of the floor scene; ``reflection_allocation`` "bucket" is the exact box's negative control."""
    from rendering.native.mode import ModePass, ModeTarget, PassOutput, PassSampler, TargetAttachment

    reflection = ModeTarget("reflection", (TargetAttachment("colour", "rgba16f"),), size=REFLECTION, depth=True,
                            mips=True, allocation=reflection_allocation)
    prepass = ModeTarget("prepass", (TargetAttachment("colour", "rgba16f"),), size=PREPASS, allocation="exact")
    levels = ModeTarget("slope_levels", (TargetAttachment("colour", "rgba16f"),), size=slope_levels_size(),
                        allocation="exact")
    floor = ModeTarget("floor", tuple(TargetAttachment(name, "rgba16f")
                                      for name in ("checker", "reflection", "relief", "mean")),
                       size=FLOOR, allocation="exact")
    passes = (
        ModePass("refl_sky", packs["refl_sky"], "replace", target="reflection", depth_test="always", depth_write=True),
        ModePass("refl_light", packs["refl_light"], "additive", target="reflection", depth_test="less"),
        ModePass("prepass", packs["prepass"], "replace", target="prepass"),
        ModePass("slope_probe", packs["slope_probe"], "replace", target="slope_levels",
                 samplers=(PassSampler("u_slope", "slope", "nearest", "clamp", "nearest"),)),
        ModePass("floor", packs["floor"], "replace", target="floor",
                 outputs=tuple(PassOutput(True, "replace") for _ in range(4)),
                 samplers=(PassSampler("u_checker", "checker", "linear", "repeat", "linear"),
                           PassSampler("u_reflection", "reflection.colour", "linear", "clamp", "linear"),
                           PassSampler("u_slope", "slope", "linear", "repeat", "linear"),
                           PassSampler("u_prepass", "prepass.colour", "linear", "clamp", "none"))),
        ModePass("show", packs["show"], "replace", samplers=(PassSampler("u_floor", "floor.checker"),)),
    )
    return passes, (reflection, prepass, levels, floor)


def floor_settings(**changes) -> dict:
    values = dict(SETTINGS, **changes)
    names = {name for layout in LAYOUTS.values() for name, _ in layout} - {"u_target_px"}
    return {k: v for k, v in values.items() if k in names}


# ------------------------------------------------------------------------------------------------------- box 4: the shape

#: Waveform's counts (Current_Plan.md N5.4's reading): 7 compute entries, 9 storage images with Floor Give on, 4 targets,
#: 28 passes with the continuation draws as passes of their own.
SHAPE_IMAGES = (("field", (64, 8), "rgba32f", 2), ("give_sections", (64, 4), "rgba32f", 2),
                ("give_blur", (64, 3), "rgba32f", 2),
                ("fog_inject", (16, 9, 8), "rgba16f", 3), ("fog_integrated", (16, 9, 8), "rgba16f", 3),
                ("fog_steady", (16, 9, 8), "r16f", 3),
                ("mirror_inject", (8, 5, 8), "rgba16f", 3), ("mirror_integrated", (8, 5, 8), "rgba16f", 3),
                ("mirror_steady", (8, 5, 8), "r16f", 3))
SHAPE_COMPUTE = (("give_sections", ("give_sections",)), ("give_blur", ("give_blur",)), ("field", ("field",)),
                 ("fog_inject", ("fog_inject",)), ("fog_integrate", ("fog_integrated", "fog_steady")),
                 ("mirror_inject", ("mirror_inject",)), ("mirror_integrate", ("mirror_integrated", "mirror_steady")))
SHAPE_REFLECTION_DRAWS = ("refl_sky", "refl_body", "refl_body_a", "refl_body_b", "refl_strays", "refl_sparks")
SHAPE_SCENE_DRAWS = ("sky", "floor", "light", "light_a", "light_b", "strays", "sparks", "pulse", "rim")
SHAPE_PASSES = 28                  # 7 compute + 6 reflection + 1 pre-pass + 9 scene + 2 body + resolve, bloom, composite
SHAPE_IMAGE_COUNT = 9


def _image_glsl(binding: int, name: str, fmt: str, dims: int) -> str:
    qualifier = {"rgba32f": "rgba32f", "rgba16f": "rgba16f", "r16f": "r16f"}[fmt]
    kind = "image3D" if dims == 3 else "image2D"
    return f"layout(binding = {binding}, {qualifier}) writeonly uniform {kind} u_{name};\n"


def shape_texts() -> dict[str, str]:
    """The shape program's stand-ins: one compute shader per entry (storing into its images), and one fragment per
    output count."""
    images = {name: (fmt, dims) for name, _size, fmt, dims in SHAPE_IMAGES}
    out: dict[str, str] = {}
    for entry, written in SHAPE_COMPUTE:
        dims = images[written[0]][1]
        body = "#version 440\nlayout(local_size_x = 4, local_size_y = 4, local_size_z = 1) in;\n"
        for index, name in enumerate(written):
            body += _image_glsl(index + 1, name, *images[name])
        body += "void main()\n{\n"
        for name in written:
            if images[name][1] == 3:
                body += f"    imageStore(u_{name}, ivec3(gl_GlobalInvocationID), vec4(0.25));\n"
            else:
                body += f"    imageStore(u_{name}, ivec2(gl_GlobalInvocationID.xy), vec4(0.25));\n"
        body += "}\n"
        out[f"shape_comp_{entry}"] = body
    for count in (1, 2, 3):
        outputs = "".join(f"layout(location = {i}) out vec4 o{i};\n" for i in range(count))
        writes = "".join(f"    o{i} = vec4(vUv, 0.25 * float({i}), 1.0);\n" for i in range(count))
        out[f"shape_out{count}"] = _HEADER + "// N5.4's harness: a stand-in draw (the shape's count only).\n" + outputs \
            + "void main()\n{\n" + writes + "}\n"
    out["shape_reads"] = _HEADER + """// N5.4's harness: the floor's stand-in, reading the field and the reflection's levels.
layout(location = 0) out vec4 colour;
layout(location = 1) out vec4 emission;
layout(binding = 1) uniform sampler2D u_field;
layout(binding = 2) uniform sampler2D u_reflection;
layout(binding = 3) uniform sampler3D u_fog;
void main()
{
    colour = vec4(texture(u_field, vUv).rgb + textureLod(u_reflection, vUv, 2.0).rgb + texture(u_fog, vec3(vUv, 0.5)).rgb,
                  1.0);
    emission = vec4(0.0);
}
"""
    return out


def shape_program(packs: dict, layer_packs: dict, *, extra_pass: bool = False, extra_image: bool = False):
    """(passes, targets, images) of Waveform's shape: 28 passes (29 with ``extra_pass``), 9 storage images (10 with
    ``extra_image``), 4 targets. ``layer_packs`` are N3.4's transparent layer packs (``post_stages``: ``eb_layer1`` and
    its sorted pack), drawn on the transparency target as Waveform's ribbon body."""
    from rendering.native.mode import (BloomStep, ComputeBinding, ComputePass, CompositeStep, ModePass, ModeTarget,
                                       PassOutput, PassSampler, StorageImage, TargetAttachment, TransparencyResolve,
                                       TransparencyTarget)

    images = [StorageImage(name, size, fmt) for name, size, fmt, _dims in SHAPE_IMAGES]
    if extra_image:
        images.append(StorageImage("one_past", (4, 4), "rgba16f"))
    scene = ModeTarget("scene", (TargetAttachment("colour", "rgba16f"), TargetAttachment("emission", "rgba16f")),
                       depth=True)
    reflection = ModeTarget("reflection", (TargetAttachment("colour", "rgba16f"),), size=REFLECTION, depth=True,
                            mips=True, allocation="exact")
    prepass = ModeTarget("prepass", (TargetAttachment("colour", "rgba16f"),), size=PREPASS, allocation="exact")
    targets = (scene, TransparencyTarget("glass", "scene", ("emission",)), reflection, prepass)
    passes: list = []
    for entry, written in SHAPE_COMPUTE:
        passes.append(ComputePass(entry, packs[f"shape_comp_{entry}"],
                                  bindings=tuple(ComputeBinding(f"u_{name}", name, "image", "write") for name in written),
                                  over=written[0]))
    for name in SHAPE_REFLECTION_DRAWS:
        passes.append(ModePass(name, packs["shape_out1"], "additive", target="reflection"))
    passes.append(ModePass("prepass", packs["shape_out1"], "replace", target="prepass"))
    two = (PassOutput(True, "replace"), PassOutput(True, "additive"))
    for name in SHAPE_SCENE_DRAWS:
        if name == "floor":
            passes.append(ModePass(name, packs["shape_reads"], "replace", target="scene", outputs=two,
                                   samplers=(PassSampler("u_field", "field", "linear", "clamp", "none"),
                                             PassSampler("u_reflection", "reflection.colour", "linear", "clamp",
                                                         "linear"),
                                             PassSampler("u_fog", "fog_integrated", "linear", "clamp", "none"))))
        else:
            passes.append(ModePass(name, packs["shape_out2"], "replace", target="scene", outputs=two))
    for n in (1, 2, 3) if extra_pass else (1, 2):
        passes.append(ModePass(f"body{n}", layer_packs["eb_layer1"], "additive", target="glass",
                               sorted_pack=layer_packs["eb_layer1_sorted"]))
    passes.append(TransparencyResolve("resolve", "glass"))
    passes.append(BloomStep("bloom", "scene.emission"))
    passes.append(CompositeStep("show", "overlay_glow", "scene.colour", "bloom.glow"))
    return tuple(passes), targets, tuple(images)


# ------------------------------------------------------------------------------------------------------- the reference

REFERENCE_VERTEX = """#version 440
layout(location = 0) out vec2 vUv;
void main()
{
    vec2 p = vec2(gl_VertexID == 1 ? 3.0 : -1.0, gl_VertexID == 2 ? 3.0 : -1.0);
    vUv = p * 0.5 + 0.5;
    gl_Position = vec4(p, 0.0, 1.0);
}
"""

#: The reference's variants: the anisotropic taps with the hardware's anisotropy off (the means chosen, both renderers);
#: one read with Python's hardware anisotropy (what the Python renderer ships today: 8x maps, 16x reflection); one
#: plain read at 1x; the taps over the slope stored as RGBA8 (the half-float box's control, Python's side of it).
REFERENCE_VARIANTS = ("taps", "hardware", "plain", "taps_slope_rgba8", "driver_chain")
_GL_TEXTURE_MAX_ANISOTROPY = 0x84FE


def reference_frames(variant: str = "taps") -> dict:
    """The Python renderer's GL calls drawing the floor scene's same fragments (an offscreen context; the textures made
    with ``glTextureStorage2D``, their chains by ``glGenerateTextureMipmap``, Python's own call), read back as the core
    reads its own (rows flipped to the image's top first; every level of the mipped reflection)."""
    import ctypes

    import numpy as np
    from OpenGL import GL as gl

    from rendering.gl_programs.conventions import conventions_block
    from rendering.gl_programs.mip_chain import MIP_BOX_COMP, dispatch_mip_chain
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.render.gl_resources import compile_compute_program, compile_program, delete_program

    if variant not in REFERENCE_VARIANTS:
        raise ValueError(f"unknown reference variant {variant!r}")
    taps = variant.startswith("taps") or variant == "driver_chain"
    encoded = variant == "taps_slope_rgba8"
    settings = dict(SETTINGS, u_taps=1.0 if taps else 0.0, u_slope_encoded=1.0 if encoded else 0.0)
    probe_size = slope_levels_size()
    host = OffscreenRenderTarget(64, 64, label="n54-reference")
    frames: dict = {}
    with host.current():
        programs = {name: compile_program(REFERENCE_VERTEX, text, label=f"n54 {name}")
                    for name, text in texts().items() if name in ("refl_sky", "refl_light", "prepass", "slope_probe",
                                                                   "floor")}
        box = compile_compute_program(MIP_BOX_COMP, label="n54 mip box")
        buffers = {}
        conventions = (ctypes.c_uint * 1)()                    # this renderer's conventions (zeros: rows bottom first)
        gl.glCreateBuffers(1, conventions)
        zeros = conventions_block()
        gl.glNamedBufferData(int(conventions[0]), len(zeros), zeros, gl.GL_STATIC_DRAW)
        buffers["_conventions"] = int(conventions[0])
        for name, block in BLOCKS.items():
            values = dict(settings, u_target_px=[float(probe_size[0]), float(probe_size[1])])
            data = std140(LAYOUTS[block], values)
            name_buffer = (ctypes.c_uint * 1)()
            gl.glCreateBuffers(1, name_buffer)
            gl.glNamedBufferData(int(name_buffer[0]), len(data), data, gl.GL_STATIC_DRAW)
            buffers[name] = int(name_buffer[0])
        made: list[int] = []

        def texture(fmt: int, size: tuple[int, int], levels: int) -> int:
            handle = (ctypes.c_uint * 1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, handle)
            name = int(handle[0])
            gl.glTextureStorage2D(name, levels, fmt, size[0], size[1])
            made.append(name)
            return name

        def levels_of(size: tuple[int, int]) -> int:
            return int(math.floor(math.log2(max(size)))) + 1

        def sampler_state(name: int, *, linear: bool, wrap: int, mips: str, anisotropy: float = 1.0) -> None:
            mag = gl.GL_LINEAR if linear else gl.GL_NEAREST
            minimum = {("none", True): gl.GL_LINEAR, ("none", False): gl.GL_NEAREST,
                       ("linear", True): gl.GL_LINEAR_MIPMAP_LINEAR, ("nearest", False): gl.GL_NEAREST_MIPMAP_NEAREST,
                       ("nearest", True): gl.GL_LINEAR_MIPMAP_NEAREST}[(mips, linear)]
            gl.glTextureParameteri(name, gl.GL_TEXTURE_MIN_FILTER, minimum)
            gl.glTextureParameteri(name, gl.GL_TEXTURE_MAG_FILTER, mag)
            gl.glTextureParameteri(name, gl.GL_TEXTURE_WRAP_S, wrap)
            gl.glTextureParameteri(name, gl.GL_TEXTURE_WRAP_T, wrap)
            gl.glTextureParameterf(name, _GL_TEXTURE_MAX_ANISOTROPY, float(anisotropy))

        def framebuffer(colours: list[int], depth: int = 0) -> int:
            handle = (ctypes.c_uint * 1)()
            gl.glCreateFramebuffers(1, handle)
            fbo = int(handle[0])
            for index, colour in enumerate(colours):
                gl.glNamedFramebufferTexture(fbo, gl.GL_COLOR_ATTACHMENT0 + index, colour, 0)
            if depth:
                gl.glNamedFramebufferTexture(fbo, gl.GL_DEPTH_ATTACHMENT, depth, 0)
            gl.glNamedFramebufferDrawBuffers(fbo, len(colours), [gl.GL_COLOR_ATTACHMENT0 + i for i in range(len(colours))])
            return fbo

        def draw(name: str, size: tuple[int, int]) -> None:
            gl.glViewport(0, 0, size[0], size[1])
            gl.glUseProgram(programs[name])
            if name in buffers:
                gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 18, buffers[name])
            gl.glBindVertexArray(host.vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)

        def read(name: int, size: tuple[int, int], level: int = 0) -> dict:
            w, h = max(1, size[0] >> level), max(1, size[1] >> level)
            array = np.empty((h, w, 4), np.float16)
            gl.glGetTextureImage(name, level, gl.GL_RGBA, gl.GL_HALF_FLOAT, array.nbytes, array)
            return {"array": array[::-1].copy(), "content": (w, h), "size": (w, h), "format": "rgba16f", "samples": 1}

        # The item textures: the checker (RGBA8) and the slope map (RGBA16F, or RGBA8 encoded), their chains made.
        checker = texture(gl.GL_RGBA8, (CHECKER, CHECKER), levels_of((CHECKER, CHECKER)))
        gl.glTextureSubImage2D(checker, 0, 0, 0, CHECKER, CHECKER, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
                               checker_pixels().tobytes())
        gl.glGenerateTextureMipmap(checker)
        data, fmt = slope_texture(encoded)
        slope = texture(gl.GL_RGBA8 if fmt == "rgba8" else gl.GL_RGBA16F, (SLOPE, SLOPE), levels_of((SLOPE, SLOPE)))
        gl.glTextureSubImage2D(slope, 0, 0, 0, SLOPE, SLOPE, gl.GL_RGBA,
                               gl.GL_UNSIGNED_BYTE if fmt == "rgba8" else gl.GL_HALF_FLOAT, data)
        gl.glGenerateTextureMipmap(slope)
        hardware = variant == "hardware"
        # The reflection: exact, mipped RGBA16F with a depth; cleared as the core's clearing draw clears it.
        reflection = texture(gl.GL_RGBA16F, REFLECTION, levels_of(REFLECTION))
        reflection_depth = texture(gl.GL_DEPTH_COMPONENT32F, REFLECTION, 1)
        fbo = framebuffer([reflection], reflection_depth)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glViewport(0, 0, *REFLECTION)
        gl.glClearBufferfv(gl.GL_COLOR, 0, (0.0, 0.0, 0.0, 0.0))
        gl.glClearBufferfv(gl.GL_DEPTH, 0, (1.0,))
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDepthFunc(gl.GL_ALWAYS)
        gl.glDisable(gl.GL_BLEND)
        draw("refl_sky", REFLECTION)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendEquationSeparate(gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
        gl.glBlendFuncSeparate(gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
        draw("refl_light", REFLECTION)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_TRUE)
        if variant == "driver_chain":
            gl.glGenerateTextureMipmap(reflection)        # Python's shipping reflection.py (the fact)
        else:
            dispatch_mip_chain(box, reflection, REFLECTION, levels_of(REFLECTION))   # the shared box kernel
        # The pre-pass and the slope probe.
        prepass = texture(gl.GL_RGBA16F, PREPASS, 1)
        pre_fbo = framebuffer([prepass])
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, pre_fbo)
        draw("prepass", PREPASS)
        probe = texture(gl.GL_RGBA16F, probe_size, 1)
        probe_fbo = framebuffer([probe])
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, probe_fbo)
        sampler_state(slope, linear=False, wrap=gl.GL_CLAMP_TO_EDGE, mips="nearest")
        gl.glBindTextureUnit(1, slope)
        draw("slope_probe", probe_size)
        # The floor: its four reads, with the samplers the program declares (and Python's anisotropy when "hardware").
        attachments = [texture(gl.GL_RGBA16F, FLOOR, 1) for _ in range(4)]
        floor_fbo = framebuffer(attachments)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, floor_fbo)
        sampler_state(checker, linear=True, wrap=gl.GL_REPEAT, mips="linear",
                      anisotropy=WAVEFORM_ANISOTROPY["maps"] if hardware else 1.0)
        sampler_state(reflection, linear=True, wrap=gl.GL_CLAMP_TO_EDGE, mips="linear",
                      anisotropy=WAVEFORM_ANISOTROPY["reflection"] if hardware else 1.0)
        sampler_state(slope, linear=True, wrap=gl.GL_REPEAT, mips="linear",
                      anisotropy=WAVEFORM_ANISOTROPY["maps"] if hardware else 1.0)
        sampler_state(prepass, linear=True, wrap=gl.GL_CLAMP_TO_EDGE, mips="none")
        for unit, name in ((1, checker), (2, reflection), (3, slope), (4, prepass)):
            gl.glBindTextureUnit(unit, name)
        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 17, buffers["_conventions"])
        draw("floor", FLOOR)
        gl.glFinish()
        for level in range(levels_of(REFLECTION)):
            frames["reflection.colour" + (f"@{level}" if level else "")] = read(reflection, REFLECTION, level)
        frames["prepass.colour"] = read(prepass, PREPASS)
        frames["slope_levels.colour"] = read(probe, probe_size)
        for index, name in enumerate(("checker", "reflection", "relief", "mean")):
            frames[f"floor.{name}"] = read(attachments[index], FLOOR)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, host.fbo)
        for fbo_name in (fbo, pre_fbo, probe_fbo, floor_fbo):
            gl.glDeleteFramebuffers(1, [fbo_name])
        gl.glDeleteTextures(made)
        for buffer in buffers.values():
            gl.glDeleteBuffers(1, [buffer])
        for program in programs.values():
            delete_program(program)
        delete_program(box)
    host.close()
    return frames


SHEET_TEXTURES = ("floor.checker", "floor.reflection", "floor.relief")


def sheet(rows: dict, path: Path, *, reference: str | None = None) -> None:
    """A review sheet: one row per labelled frame set (``rows``: label -> frames), the floor's reads side by side, and
    under ``reference`` (a label of ``rows``) each other row's absolute difference x8."""
    import numpy as np
    from PIL import Image, ImageDraw

    def image(array) -> "Image.Image":
        rgb = np.clip(array[..., :3].astype(np.float32), 0.0, 1.0)
        return Image.fromarray((rgb * 255.0 + 0.5).astype(np.uint8), "RGB")

    width, height = FLOOR
    labels = list(rows)
    lines = labels + ([f"|{label} - {reference}| x8" for label in labels if label != reference] if reference else [])
    canvas = Image.new("RGB", (width * len(SHEET_TEXTURES), (height + 18) * len(lines)), (16, 16, 16))
    draw = ImageDraw.Draw(canvas)
    for row, line in enumerate(lines):
        y = row * (height + 18)
        draw.text((4, y + 2), line, fill=(230, 230, 230))
        for column, name in enumerate(SHEET_TEXTURES):
            if row < len(labels):
                array = rows[labels[row]][name]["array"]
            else:
                label = [l for l in labels if l != reference][row - len(labels)]
                array = np.abs(rows[label][name]["array"].astype(np.float32)
                               - rows[reference][name]["array"].astype(np.float32)) * 8.0
            canvas.paste(image(array), (column * width, y + 18))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def float_filter_program(packs: dict, *, fmt: str = "rgba32f"):
    """(passes, images) of box 5: a storage image of ``fmt`` read through a linear sampler."""
    from rendering.native.mode import ModePass, PassSampler, StorageImage

    images = (StorageImage("field", (64, 8), fmt),)
    passes = (ModePass("filtered", packs["filtered_field"], "replace",
                       samplers=(PassSampler("u_field", "field", "linear", "clamp", "none"),)),)
    return passes, images
