"""N3.4's harness scenes (Current_Plan.md item 8b, N3.4; decision D17): the shared stages as data, harness-only and never
registered (like ``scene_targets``). Stills (no stream): a program, its settings and the card are the frame.

- ``eb``: Extruded Bubble's shape. A surface-sized ``scene`` target (RGBA16F colour, the HDR intermediate; RGBA16F
  emission; depth) at 1 or 4 samples; the ``backdrop`` pass (opaque, colour past white, a translucent band, a glowing
  spot into the emission, a tilted window depth through ``gl_FragDepth``); the capture; three overlapping transparent
  discs on the transparency target ``glass`` (its own accumulation and coverage; the scene's emission borrowed at
  location 2; ``SCENE_OIT_GLSL``'s product text) at known window depths (the backdrop hides part of them), view depths
  and alphas; the resolve; the near layer ``near`` (a mipped target: a hard-edged disc and a highlight, drawn with
  ``SCENE_DEFOCUS_GLSL``'s product text) spread onto the scene by the defocus step; bloom from the emission; the
  overlay composite with glow and the HDR tone map.
- ``osc``: the Oscilloscope's shape: a one-sample overlay (RGBA8 colour, RGBA16F emission), two traces blended MAX on
  both attachments, bloom from the emission, the overlay composite with glow (no tone map).
- ``tiles``: an opaque scene (Exploding Tiles' shape): an RGBA8 colour whose alpha is the emitted brightness, bloom from
  it, the opaque composite with glow.
- ``solo``: a one-attachment owner (RGBA8 colour, depth) with three transparent discs on ``solo_glass`` and the plain
  overlay composite: the scene the sorted fallback rescues (D17's lead answers).

Each pass's fragment is product-shaped (``vUv`` y up over the content, one block at binding 18) so the Python reference
(``SceneTarget``, ``BloomChain``, ``DefocusLayer`` in an offscreen GL context) draws the same text. A transparent pass
ships its sorted pack (D17 choice D): the same text writing premultiplied colour at location 0 (and the emission at 1).
"""
from __future__ import annotations

import functools
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASPECT = 640.0 / 384.0                 # the aligned card's (the discs' shape; any card draws them)
LAYERS = (1, 2, 3)
TRACES = (1, 2)

# ------------------------------------------------------------------------------------------------------- the fragments

_HEADER = "#version 440\nlayout(location = 0) in vec2 vUv;\n"
_LUMA = "vec3(0.2126, 0.7152, 0.0722)"

BACKDROP = _HEADER + """// N3.4's harness, the EB scene's opaque pass: the scene's colour (premultiplied, alpha the overlay's coverage) and its
// emission, at a tilted window depth.
layout(location = 0) out vec4 colour;
layout(location = 1) out vec4 emission;
layout(std140, binding = 18) uniform PostBackdrop {
    vec4 u_back_colour;    // the base colour (straight)
    float u_back_gain;     // light past white (the HDR intermediate)
    float u_back_near;     // the window depth at the content's left edge
    float u_back_far;      // and at its right edge
    float u_back_emission; // the glowing spot's light
    float u_back_edge;     // vUv.x past which nothing is drawn (the overlay's transparent part)
};
void main()
{
    if (vUv.x > u_back_edge)
        discard;
    float cover = vUv.y > 0.88 ? 0.5 : 1.0;
    vec3 rgb = u_back_colour.rgb * (0.35 + 0.65 * vUv.x);
    rgb.r += u_back_gain * smoothstep(0.55, 0.75, vUv.y) * vUv.x;
    colour = vec4(rgb * cover, cover);
    vec2 d = (vUv - vec2(0.25, 0.3)) * vec2(%(aspect).6f, 1.0);
    float spot = 1.0 - smoothstep(0.05, 0.09, length(d));
    vec3 light = vec3(1.0, 0.55, 0.2) * (u_back_emission * spot);
    emission = vec4(light, dot(light, %(luma)s));
    gl_FragDepth = mix(u_back_near, u_back_far, vUv.x);
}
""" % {"aspect": ASPECT, "luma": _LUMA}

SOLO_BACK = _HEADER + """// N3.4's harness, the one-attachment owner's opaque pass (the sorted fallback's scene).
layout(location = 0) out vec4 colour;
layout(std140, binding = 18) uniform PostSolo {
    vec4 u_solo_colour;
    float u_solo_edge;
};
void main()
{
    if (vUv.x > u_solo_edge)
        discard;
    colour = vec4(u_solo_colour.rgb * (0.4 + 0.6 * vUv.y), 1.0);
    gl_FragDepth = 0.9;
}
"""

_LAYER_BLOCK = """layout(std140, binding = 18) uniform PostLayer%(n)d {
    vec4 u_l%(n)d_colour;   // straight colour and alpha
    vec4 u_l%(n)d_disc;     // centre (vUv), radius (vUv.y units), window depth
    vec4 u_l%(n)d_light;    // emitted light, view depth (scene units: the OIT weight's)
    float u_l%(n)d_band;    // > 0: two partial-coverage bands under the centre (gl_SampleMask, N3.1's)
};
"""

_LAYER_BODY = """void main()
{
    vec2 d = (vUv - u_l%(n)d_disc.xy) * vec2(%(aspect).6f, 1.0);
    if (length(d) > u_l%(n)d_disc.z)
        discard;
    // The first band (every sample but 0) and the second (sample 0 alone), below the centre.
    float below = u_l%(n)d_disc.y - vUv.y;
    int mask = -1;
    if (u_l%(n)d_band > 0.0 && below > 0.0 && below <= u_l%(n)d_band)
        mask = ~1;
    else if (u_l%(n)d_band > 0.0 && below > u_l%(n)d_band && below <= 2.0 * u_l%(n)d_band)
        mask = 1;
    gl_SampleMask[0] = mask;
    float alpha = u_l%(n)d_colour.a;
    sceneTransparent(u_l%(n)d_colour.rgb * alpha, alpha, u_l%(n)d_light.w);
%(emission)s%(depth)s}
"""

_SORTED_GLSL = """
layout(location = 0) out vec4 SceneColour;
void sceneTransparent(vec3 premultiplied, float alpha, float viewDepth) {
    SceneColour = vec4(premultiplied, alpha);
}
"""

NEAR = None    # filled below (needs the product's SCENE_DEFOCUS_GLSL)

_TRACE = _HEADER + """// N3.4's harness, an Oscilloscope trace: blended MAX into colour and emission.
layout(location = 0) out vec4 colour;
layout(location = 1) out vec4 emission;
layout(std140, binding = 18) uniform PostTrace%(n)d {
    vec4 u_t%(n)d_colour;   // rgb, the line's half width (pixels of a 384-pixel card)
    vec4 u_t%(n)d_wave;     // amplitude, cycles, phase, emission gain
};
void main()
{
    // vUv at the aligned card's pixel centres, exactly: on the trace's steep edge each renderer's last-bit
    // interpolation of vUv became up to 5 float16 ulps of emission between the backends (3 with this).
    vec2 uv = (floor(vUv * vec2(640.0, 384.0)) + 0.5) / vec2(640.0, 384.0);
    float y = 0.5 + u_t%(n)d_wave.x * sin(6.2831853 * u_t%(n)d_wave.y * uv.x + u_t%(n)d_wave.z);
    float d = abs(uv.y - y) * 384.0;
    float i = 1.0 - smoothstep(0.0, u_t%(n)d_colour.w, d);
    if (i <= 0.0)
        discard;
    colour = vec4(u_t%(n)d_colour.rgb * i, i);
    vec3 light = u_t%(n)d_colour.rgb * (i * u_t%(n)d_wave.w);
    emission = vec4(light, dot(light, %(luma)s));
}
"""

TILES = _HEADER + """// N3.4's harness, an opaque scene: tiles, some emitting (their brightness in alpha, the bloom's bright pass).
layout(location = 0) out vec4 colour;
layout(std140, binding = 18) uniform PostTiles {
    vec4 u_tile_colour;
    float u_tile_cells;
    float u_tile_glow;
};
void main()
{
    vec2 cell = floor(vUv * vec2(u_tile_cells * %(aspect).6f, u_tile_cells));
    float checker = mod(cell.x + cell.y, 2.0);
    vec3 rgb = u_tile_colour.rgb * mix(1.0, 0.35, checker) * (0.5 + 0.5 * vUv.x);
    bool glowing = mod(cell.x + 3.0 * cell.y, 5.0) < 0.5;
    colour = glowing ? vec4(min(rgb * 1.6, vec3(1.0)), u_tile_glow) : vec4(rgb, 0.0);
}
""" % {"aspect": ASPECT}


def _product():
    from rendering.quick.scene3d.defocus import SCENE_DEFOCUS_GLSL
    from rendering.quick.scene3d.target import SCENE_EMISSION_GLSL, SCENE_OIT_GLSL

    return SCENE_OIT_GLSL, SCENE_EMISSION_GLSL, SCENE_DEFOCUS_GLSL


def layer_text(n: int, *, emission: bool, sorted_pack: bool, frag_depth: bool) -> str:
    """Transparent disc ``n``: ``emission`` writes the borrowed emission (location 2; 1 in the sorted pack);
    ``sorted_pack`` the fallback's text; ``frag_depth`` its window depth through ``gl_FragDepth`` (the OIT pack only:
    a sorted pack never writes depth)."""
    oit, scene_emission, _defocus = _product()
    text = _HEADER + f"// N3.4's harness, transparent disc {n} ({'sorted pack' if sorted_pack else 'OIT pack'}).\n"
    text += _SORTED_GLSL if sorted_pack else oit
    if emission:
        text += f"layout(location = {1 if sorted_pack else 2}) out vec4 SceneEmission;\n" + scene_emission
    text += _LAYER_BLOCK % {"n": n}
    body_emission = (f"    SceneEmission = sceneEmission(u_l{n}_light.rgb * alpha);\n" if emission else "")
    body_depth = (f"    gl_FragDepth = u_l{n}_disc.w;\n" if frag_depth and not sorted_pack else "")
    return text + _LAYER_BODY % {"n": n, "aspect": ASPECT, "emission": body_emission, "depth": body_depth}


def near_text() -> str:
    _oit, _emission, defocus = _product()
    return _HEADER + "// N3.4's harness, the near layer: a hard-edged disc and a highlight with their circle.\n" + defocus + \
        """layout(std140, binding = 18) uniform PostNear {
    vec4 u_near_colour;   // straight colour and alpha
    vec4 u_near_disc;     // centre, radius (vUv.y units), circle of confusion (pixels)
    vec4 u_near_spot;     // centre, radius, its light (a highlight)
};
void main()
{
    float disc = length((vUv - u_near_disc.xy) * vec2(%(aspect).6f, 1.0)) <= u_near_disc.z ? 1.0 : 0.0;
    float spot = length((vUv - u_near_spot.xy) * vec2(%(aspect).6f, 1.0)) <= u_near_spot.z ? 1.0 : 0.0;
    if (disc + spot <= 0.0)
        discard;
    float alpha = max(u_near_colour.a * disc, spot);
    vec3 rgb = u_near_colour.rgb + vec3(u_near_spot.w * spot);
    sceneDefocusWrite(rgb * alpha, alpha, u_near_disc.w);
}
""" % {"aspect": ASPECT}


def trace_text(n: int) -> str:
    return _TRACE % {"n": n, "luma": _LUMA}


@functools.lru_cache(maxsize=1)
def texts() -> dict[str, str]:
    """Every fragment's text by its pack name (read only: cached)."""
    out = {"backdrop": BACKDROP, "solo_back": SOLO_BACK, "near": near_text(), "tiles": TILES}
    for n in LAYERS:
        out[f"eb_layer{n}"] = layer_text(n, emission=True, sorted_pack=False, frag_depth=True)
        out[f"eb_layer{n}_sorted"] = layer_text(n, emission=True, sorted_pack=True, frag_depth=True)
        out[f"solo_layer{n}"] = layer_text(n, emission=False, sorted_pack=False, frag_depth=False)
        out[f"solo_layer{n}_sorted"] = layer_text(n, emission=False, sorted_pack=True, frag_depth=False)
    for n in TRACES:
        out[f"trace{n}"] = trace_text(n)
    return out


#: Each pack's block (the Python reference packs it through the module).
BLOCKS = {"backdrop": "PostBackdrop", "solo_back": "PostSolo", "near": "PostNear", "tiles": "PostTiles",
          **{f"{kind}_layer{n}{s}": f"PostLayer{n}" for kind in ("eb", "solo") for n in LAYERS for s in ("", "_sorted")},
          **{f"trace{n}": f"PostTrace{n}" for n in TRACES}}


def bake_all(folder: Path) -> dict[str, bytes]:
    """Every fragment baked by ``tools/regen_qrc.py``'s own baker (no module build): pack name -> pack."""
    import probe_rings

    return {name: probe_rings.bake(text, f"post_{name}.frag", folder) for name, text in texts().items()}


def members(name: str, values: dict) -> dict:
    """The settings ``name``'s block reads (by its members' names in the text)."""
    text = texts()[name]
    return {k: v for k, v in values.items() if k in text}


# ------------------------------------------------------------------------------------------------------- the settings

DEFOCUS_TAPS = 64


def read_level(radius: float) -> int:
    """``defocus.py`` ``_read_size``'s level for ``radius`` (the step's ``u_defocus_level``, Python's to resolve)."""
    tap_area = math.pi * radius * radius / DEFOCUS_TAPS
    return max(int(math.floor(math.log2(max(math.sqrt(tap_area), 1.0)))), 0)


def read_level_cap(allocation: tuple[int, int]) -> int:
    """``post_stages.cpp`` ``defocusReadLevelCap``: two levels above the last level made only from even-sized levels."""
    width, height = allocation
    exact = 0
    while width > 1 or height > 1:
        if (width > 1 and width % 2) or (height > 1 and height % 2):
            break
        width, height = max(1, width // 2), max(1, height // 2)
        exact += 1
    return max(0, exact - 2)


SETTINGS = {
    "u_back_colour": [0.35, 0.55, 0.8, 1.0], "u_back_gain": 2.4, "u_back_near": 0.3, "u_back_far": 0.8,
    "u_back_emission": 3.0, "u_back_edge": 0.82,
    "u_l1_colour": [0.2, 0.6, 1.0, 0.45], "u_l1_disc": [0.45, 0.5, 0.28, 0.5], "u_l1_light": [0.0, 0.3, 0.6, 3.0],
    "u_l1_band": 0.0,
    "u_l2_colour": [1.0, 0.3, 0.2, 0.6], "u_l2_disc": [0.66, 0.42, 0.25, 0.45], "u_l2_light": [0.9, 0.25, 0.1, 5.0],
    "u_l2_band": 0.0,
    "u_l3_colour": [0.9, 0.9, 0.3, 0.3], "u_l3_disc": [0.55, 0.64, 0.2, 0.4], "u_l3_light": [0.0, 0.0, 0.0, 8.0],
    "u_l3_band": 0.0,
    "u_near_colour": [0.95, 0.85, 0.7, 0.8], "u_near_disc": [0.18, 0.78, 0.12, 9.0],
    "u_near_spot": [0.32, 0.86, 0.018, 6.0],
    "u_defocus_radius": 12.0, "u_defocus_highlight": 0.25, "u_defocus_level": read_level(12.0),
    "u_bloom_strength": 0.55, "u_hdr_exposure": 1.0,
    "u_t1_colour": [0.2, 1.0, 0.5, 3.0], "u_t1_wave": [0.22, 2.0, 0.0, 1.6],
    "u_t2_colour": [1.0, 0.4, 0.9, 2.0], "u_t2_wave": [0.15, 3.5, 1.3, 1.2],
    "u_tile_colour": [0.9, 0.6, 0.3, 1.0], "u_tile_cells": 6.0, "u_tile_glow": 0.9,
    "u_solo_colour": [0.3, 0.5, 0.75, 1.0], "u_solo_edge": 0.8,
}


#: The members each stage step's core shader reads (filled by the one rule from the settings).
STAGE_MEMBERS = {"overlay_glow": ("u_bloom_strength", "u_hdr_exposure"), "opaque_glow": ("u_bloom_strength",),
                 "overlay": (), "defocus": ("u_defocus_radius", "u_defocus_highlight", "u_defocus_level")}


def pack_of(pass_name: str) -> str:
    """The pack a harness pass draws (the EB discs' passes are ``layer<n>``)."""
    return pass_name if pass_name in texts() else f"eb_{pass_name}"


def values_for(passes, values: dict | None = None, **changes) -> dict:
    """The settings ``passes`` read (the core refuses a name no pass reads): ``values`` (default ``SETTINGS``) with
    ``changes``, kept to the members of the passes' blocks and their steps' core shaders."""
    import re

    from rendering.native.mode import CompositeStep, DefocusStep, ModePass

    source = dict(SETTINGS if values is None else values, **changes)
    names: set[str] = set()
    for p in passes:
        if isinstance(p, ModePass):
            names.update(re.findall(r"\bu_\w+", texts()[pack_of(p.name)]))
        elif isinstance(p, CompositeStep):
            names.update(STAGE_MEMBERS[p.form])
        elif isinstance(p, DefocusStep):
            names.update(STAGE_MEMBERS["defocus"])
    return {k: v for k, v in source.items() if k in names}


# ------------------------------------------------------------------------------------------------------- the programs

#: The EB program's stage variants (the cost round's "with the stage less without it").
EB_VARIANTS = ("full", "no_transparency", "no_bloom", "no_defocus", "none")


def eb_program(packs: dict, *, samples: int = 1, variant: str = "full", order=LAYERS, capture: bool = True):
    """(passes, targets) of the EB scene; ``variant`` leaves stages out (``EB_VARIANTS``), ``order`` the discs' draw
    order."""
    from rendering.native.mode import (BlendState, BloomStep, CapturePass, CompositeStep, DefocusStep, ModePass,
                                       ModeTarget, PassOutput, TargetAttachment, TransparencyResolve,
                                       TransparencyTarget)

    transparency = variant in ("full", "no_bloom", "no_defocus")
    bloom = variant in ("full", "no_transparency", "no_defocus")
    defocus = variant in ("full", "no_transparency", "no_bloom")
    scene = ModeTarget("scene", (TargetAttachment("colour", "rgba16f"), TargetAttachment("emission", "rgba16f")),
                       depth=True, samples=int(samples))
    targets = [scene]
    if transparency:
        targets.append(TransparencyTarget("glass", "scene", ("emission",)))
    if defocus:
        targets.append(ModeTarget("near", (TargetAttachment("colour", "rgba16f"), TargetAttachment("circle", "rgba16f")),
                                  mips=True))
    passes = [ModePass("backdrop", packs["backdrop"], "replace", target="scene",
                       outputs=(PassOutput(True, "replace"), PassOutput(True, "additive")), depth_test="always",
                       depth_write=True)]
    if capture:
        passes.append(CapturePass("capture", "scene"))
    if transparency:
        for n in order:
            passes.append(ModePass(f"layer{n}", packs[f"eb_layer{n}"], "additive", target="glass",
                                   sorted_pack=packs[f"eb_layer{n}_sorted"]))
        passes.append(TransparencyResolve("resolve", "glass"))
    if defocus:
        maximum = BlendState(("max", "one", "one"), ("max", "one", "one"))
        passes.append(ModePass("near", packs["near"], "premultiplied", target="near",
                               outputs=(PassOutput(True, "premultiplied"), PassOutput(True, maximum))))
        passes.append(DefocusStep("defocus", "near", "scene"))
    if bloom:
        passes.append(BloomStep("bloom", "scene.emission"))
        passes.append(CompositeStep("show", "overlay_glow", "scene.colour", "bloom.glow"))
    else:
        passes.append(CompositeStep("show", "overlay", "scene.colour"))
    return tuple(passes), tuple(targets)


def osc_program(packs: dict):
    from rendering.native.mode import (BlendState, BloomStep, CompositeStep, ModePass, ModeTarget, PassOutput,
                                       TargetAttachment)

    maximum = BlendState(("max", "one", "one"), ("max", "one", "one"))
    scene = ModeTarget("scene", (TargetAttachment("colour", "rgba8"), TargetAttachment("emission", "rgba16f")))
    passes = tuple(ModePass(f"trace{n}", packs[f"trace{n}"], "replace", target="scene",
                            outputs=(PassOutput(True, maximum), PassOutput(True, maximum))) for n in TRACES)
    passes += (BloomStep("bloom", "scene.emission"),
               CompositeStep("show", "overlay_glow", "scene.colour", "bloom.glow"))
    return passes, (scene,)


def tiles_program(packs: dict, *, samples: int = 1):
    from rendering.native.mode import BloomStep, CompositeStep, ModePass, ModeTarget, TargetAttachment

    scene = ModeTarget("scene", (TargetAttachment("colour", "rgba8", (0.0, 0.0, 0.0, 1.0)),), samples=int(samples))
    passes = (ModePass("tiles", packs["tiles"], "replace", target="scene"),
              BloomStep("bloom", "scene.colour"),
              CompositeStep("show", "opaque_glow", "scene.colour", "bloom.glow"))
    return passes, (scene,)


def solo_program(packs: dict, *, samples: int = 1, with_layers: bool = True):
    from rendering.native.mode import (CompositeStep, ModePass, ModeTarget, TargetAttachment, TransparencyResolve,
                                       TransparencyTarget)

    owner = ModeTarget("solo", (TargetAttachment("colour", "rgba8"),), depth=True, samples=int(samples))
    targets = (owner, TransparencyTarget("solo_glass", "solo")) if with_layers else (owner,)
    passes = [ModePass("solo_back", packs["solo_back"], "replace", target="solo", depth_test="always",
                       depth_write=True)]
    if with_layers:
        passes += [ModePass(f"solo_layer{n}", packs[f"solo_layer{n}"], "replace", target="solo_glass",
                            sorted_pack=packs[f"solo_layer{n}_sorted"]) for n in LAYERS]
        passes.append(TransparencyResolve("resolve", "solo_glass"))
    passes.append(CompositeStep("show", "overlay", "solo.colour"))
    return tuple(passes), targets


def program(scene: str, packs: dict, **options):
    return {"eb": eb_program, "osc": osc_program, "tiles": tiles_program, "solo": solo_program}[scene](packs, **options)
