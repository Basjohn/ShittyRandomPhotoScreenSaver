"""Extruded Bubble composition lab (§4A): every shared primitive composed into one underwater scene per operator mock
(Docs/Reference/Extruded_Bubble/Targets/Originals: bright, mid, dark water, teal), rendered offscreen at the mocks' resolution and laid side by
side with them. A development harness for judging primitives against the target; not the Extruded Bubble renderer.
usage: python tools/labs/extruded_bubble_lab.py out_sheet.png [--backdrop]"""
import ctypes
import math
import random
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
from rendering.gl_error_policy import disable_per_call_gl_error_checking
if not disable_per_call_gl_error_checking():
    raise RuntimeError("GL imported before production policy")
from OpenGL import GL as gl
from PIL import Image

from rendering.gl_programs.scene3d_optics import SCENE3D_OPTICS_GLSL
from rendering.quick.scene3d.defocus import SCENE_DEFOCUS_GLSL, DefocusLayer
from rendering.quick.scene3d.probe import SCENE3D_PROBE_GLSL, SceneProbe
from rendering.gl_programs.scene3d_spheres import SCENE3D_SPHERES_GLSL
from rendering.gl_programs.scene3d_water import SCENE3D_WATER_GLSL, water_sun_below
from rendering.quick.render.gl_resources import compile_program
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.target import SCENE_OIT_GLSL, SceneTarget
from tools.transition_contact_sheet import TransitionCapture
from rendering.gl_programs.extruded_bubble_scene import ENGINE, MODES
from rendering.gl_programs.extruded_bubble_program import (  # the product's shaders, proven here
    COMMON,
    FULL_VERTEX,
    SPECKS_GLSL,
    BACKDROP_FRAGMENT,
    SHAFT_FRAGMENT,
    BLUR_FRAGMENT,
    BUBBLE_VERTEX,
    SHADE_GLSL,
    BUBBLE_FRAGMENT_BODY,
    BUBBLE_FRAGMENT,
    NEAR_FRAGMENT,
    NEAR_CLUSTER_FRAGMENT,
    CLUSTER_VERTEX,
    CLUSTER_FRAGMENT,
    PARTICLE_VERTEX,
    PARTICLE_FRAGMENT,
)

W, H = 1672, 941
# --size=WxH: render (and time) at another size, e.g. a 1440p display (mock sheets and card crops assume the default).
W, H = next((tuple(int(v) for v in a.split("=", 1)[1].split("x")) for a in sys.argv if a.startswith("--size=")), (W, H))
BACKDROP_ONLY = "--backdrop" in sys.argv
# --card[=MockName]: a mock's own bubbles at their measured positions and pixel sizes (x, y from the top-left,
# radius, depth; doublets joined as the mock shows them; bead chains as x, y from, y to), so crops compare one to one.
CARD_SETS = {
    "ExBubble2": dict(
        bubbles=((705, 617, 42, 9.0), (395, 713, 38, 9.0), (627, 812, 37, 9.0), (230, 407, 35, 9.0),
                 (167, 330, 17, 12.0), (477, 593, 17, 12.0), (547, 707, 15, 12.0), (513, 527, 13, 12.0),
                 (170, 790, 190, 3.2), (40, 347, 95, 3.6)),
        doublets=(((541, 363, 88, 9.0), (632, 432, 37, 9.0)),),
        chains=((585, 941, 480), (655, 941, 470), (300, 941, 430)),
        crops={"doublet": (400, 250, 720, 500), "giant": (0, 560, 450, 941), "mids": (330, 540, 780, 860)}),
    "ExBubble6Diagonal": dict(
        bubbles=((472, 152, 44, 9.0), (272, 288, 62, 9.0), (808, 343, 49, 9.0), (565, 512, 80, 9.0),
                 (955, 510, 37, 9.0), (680, 567, 27, 10.0), (807, 540, 25, 10.0), (607, 377, 22, 10.0),
                 (850, 642, 23, 10.0), (493, 308, 18, 11.0), (195, 740, 125, 2.4), (530, 783, 35, 4.0)),
        doublets=(),
        chains=(),
        crops={"mids": (200, 90, 1000, 600), "giant": (0, 560, 450, 941)}),
}
CARD_ARG = next((a for a in sys.argv if a == "--card" or a.startswith("--card=")), None)
CARD = None if CARD_ARG is None else (CARD_ARG.split("=", 1)[1] if "=" in CARD_ARG else "ExBubble2")
ENV_W, ENV_H = 1024, 512
SURFACE_Y = 9.0

# Settings in three layers (the shape of the eventual product presets):
# * ENGINE: the same for every scene (the glass's optics, its lens share).
# * MODES: what a light setting implies. "surface": the sun above the water seen through it (Snell's window, a fan of
#   rays from it, lit scattering water round the bubbles); "deep": a light inside the water with no surface in view.
# * Each scene: its mode plus what a preset would store (colours, light direction, amounts, camera pitch).
# ENGINE and MODES are the product's (rendering/gl_programs/extruded_bubble_scene.py); VARIANTS are the lab's scenes.
VARIANTS = {
    "ExBubble1": dict(mode="surface", film=0.3, surface_gain=1.6, ray_cut=0.08, rays=0.7,
                      deep=(0.1, 0.16, 0.24), water=(0.19, 0.26, 0.36), sky=(0.82, 0.9, 0.98), shaft=(0.62, 0.67, 0.74),
                      sun=(0.05, 0.75, -1.0), pitch=16.0, exposure=1.0, absorb=(0.06, 0.042, 0.032)),
    "ExBubble2": dict(mode="surface", film=0.35, surface_gain=3.0, rays=0.7,
                      deep=(0.022, 0.055, 0.12), water=(0.03, 0.08, 0.16), sky=(0.6, 0.76, 0.95), shaft=(0.36, 0.55, 0.85),
                      sun=(0.0, 0.7, -1.0), pitch=16.0, exposure=0.9, absorb=(0.08, 0.05, 0.035)),
    "ExBubble3": dict(mode="surface", film=0.3, surface_gain=2.0, rays=0.55,
                      deep=(0.016, 0.03, 0.046), water=(0.024, 0.046, 0.07), sky=(0.52, 0.68, 0.85), shaft=(0.45, 0.5, 0.58),
                      sun=(0.0, 0.8, -1.0), pitch=18.0, exposure=0.82, absorb=(0.09, 0.06, 0.045)),
    # Broad soft rays (operator preferred them to the fine fan here), lighter film, haze, a wider aperture.
    "ExBubble4": dict(mode="surface", fan_rays=35.0, fan_contrast=0.35, fan_march=0.45, rays=0.45,
                      film=0.5, film_range=(255.0, 345.0), surface_gain=2.5,
                      deep=(0.05, 0.11, 0.2), water=(0.04, 0.1, 0.17), sky=(0.48, 0.66, 0.84), shaft=(0.4, 0.58, 0.8),
                      sun=(0.15, 0.65, -1.0), pitch=14.0, exposure=0.82, absorb=(0.1, 0.05, 0.03), drift=0.12,
                      mist=0.3, aperture=1.2),
    # A dark teal abyss lit from the upper right inside the water: luminous veils, bead columns, clear glass.
    "ExBubble5CameraAbyss": dict(mode="deep", spec_view=(0.6, 0.6, 0.5), veils=0.4, proxy_power=6.0, inner_blur=0.12,
                                 speck_glow=0.25, chains=2.0, near_coc=3.0, near_lens=1.0, near_reflect=0.1, film=0.9,
                                 film_range=(255.0, 345.0), glint_power=600.0, glint_sharp=300.0, probe_fill=3.0,
                                 face_reflect=0.2, mid_count=0.45, travel=(0.4, 1.0, 0.0), columns=(0.371, 0.928, 120.0),
                                 surface_gain=0.6, rough=0.05, light_power=1.2, light_view=(0.75, 0.75, -1.0),
                                 light=(0.75, 0.88, 1.0), specks=0.35, warm_share=0.85, streak=(0.35, 1.0),
                                 deep=(0.016, 0.05, 0.08), water=(0.02, 0.08, 0.13), sky=(0.3, 0.6, 1.0),
                                 shaft=(0.25, 0.5, 0.95), sun=(0.6, 0.6, -1.0), pitch=6.0, exposure=1.0, mist=0.6,
                                 focus=3.2, sparkle=1.0, surface=60.0, absorb=(0.1, 0.05, 0.03), drift=0.6, shaft_y=16.0,
                                 glow=0.6, rays=0.2, aperture=0.6),
    # Looking down into a dark abyss lit from above and behind: deep blue, a lighter haze far off, violet-rimmed glass.
    "ExBubble5Cameradown": dict(mode="deep", deep=(0.05, 0.12, 0.2), water=(0.03, 0.11, 0.2), sky=(0.45, 0.65, 1.0),
                                shaft=(0.3, 0.55, 0.95), face_reflect=0.25, sun=(0.3, 0.8, -1.0), pitch=-32.0,
                                exposure=1.0, surface=30.0, shaft_y=12.0, absorb=(0.1, 0.05, 0.03), surface_gain=0.6,
                                light_power=0.0, mist=0.4, rays=0.4, glow=0.6, drift=0.15, specks=0.6, warm_share=0.85,
                                streak=(0.15, 1.0), chains=5.0, mid_count=0.6, sparkle=0.7, rough=0.03, film=1.0,
                                film_range=(255.0, 345.0), probe_fill=5.0, glint_power=400.0, glint_sharp=600.0,
                                inner_blur=0.15),
    # Near-black teal, orange light from the top-right corner, ember particulate in diagonal bands, dark clear glass.
    "ExBubble6Diagonal": dict(mode="deep", spec_view=(0.75, 0.55, 0.38), deep=(0.012, 0.05, 0.06),
                              water=(0.03, 0.13, 0.17), sky=(1.0, 0.55, 0.22), shaft=(0.95, 0.45, 0.14),
                              light=(1.0, 0.52, 0.2), sun=(0.9, 0.35, -0.5), light_view=(1.0, 0.68, -1.0), pitch=4.0,
                              exposure=1.0, hdr_exposure=0.75, surface=60.0, shaft_y=16.0, glow=0.2, rays=0.25,
                              ray_focus=1.0, mist=0.6, dust=0.4, light_power=0.15, absorb=(0.06, 0.05, 0.05),
                              specks=2.4, speck_warm=(1.0, 0.25, 0.02), speck_size=1.6, speck_bloom=0.6,
                              warm_share=0.9, streak=(1.0, -0.3), banded=True, band_freq=9.0, cloud_contrast=4.0,
                              cloud_floor=0.03, cloud_glow=1.8, travel=(1.0, -0.3, 0.15), sway=0.25, fizz=2.5,
                              fizz_size=2.0, small_count=5.0, sparkle=1.5, mid_count=1.5, rough=0.1, inner_blur=0.6,
                              probe_fill=1.5, face_reflect=0.3, veils=0.35, glint_power=60.0, glint_sharp=300.0,
                              focus=3.4, aperture=1.5),
}


def effective(variant):
    """A scene's full settings: engine, then its mode, then its own values."""
    return {**ENGINE, **MODES[variant["mode"]], **variant}

ENV_FRAGMENT = "#version 460 core\nout vec4 FragColor;\nin vec2 vNdc;\n" + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + COMMON + """
void main() {
    vec3 dir = equirectDirection(vNdc * 0.5 + 0.5);
    float shafts = waterShafts(vec3(0.0), dir, 40.0, uSunBelow, uShaftY, uTime, 12, 0.5) * 0.08;
    FragColor = vec4(basinWater(dir, 0.6, shafts), 1.0);
}
"""
RIBBON_VERTEX = """#version 460 core
layout(location=0) in vec4 aStart;    // world point under the bubble, bubble radius
layout(location=1) in vec4 aShape;    // seed, length, current lean, strength
uniform mat3 uWorldToView;
uniform mat4 uProjection;
uniform vec3 uTrail;                  // world direction the wake trails in (opposite the travel)
uniform float uSway;
const int SEGMENTS = 40;
out vec2 vAcross;                     // across the sheet (-1..1), along it (0 at the bubble .. 1)
out float vFold;
out float vDepth;
flat out float vStrength;
flat out float vShapeSeed;
vec3 ribbonPath(float s) {
    float length_ = aShape.y, r = aStart.w, seed = aShape.x;
    vec3 lateral = -cross(uTrail, vec3(0.0, 0.0, 1.0));
    lateral = dot(lateral, lateral) > 1e-6 ? normalize(lateral) : vec3(1.0, 0.0, 0.0);
    vec3 p = aStart.xyz + uTrail * length_ * s;
    p += lateral * (aShape.z * length_ * s * s + sin(s * 2.2 + seed * 6.28) * r * 4.0 * s * s * uSway);
    p.z += cos(s * 1.9 + seed * 4.1) * r * 1.5 * s * uSway;
    return p;
}
void main() {
    int i = gl_VertexID >> 1;
    float sideSign = (gl_VertexID & 1) == 0 ? -1.0 : 1.0;
    float s = float(i) / float(SEGMENTS);
    vec3 here = uWorldToView * ribbonPath(s);
    vec3 next = uWorldToView * ribbonPath(min(s + 0.02, 1.0));
    vec3 previous = uWorldToView * ribbonPath(max(s - 0.02, 0.0));
    vec3 tangent = normalize(next - previous);
    vec3 across = normalize(cross(tangent, normalize(-here)));
    float turn = 0.6 + 0.4 * cos(s * 3.5 + aShape.x * 6.28);
    float width = aStart.w * mix(0.8, 1.6, s) * mix(1.0, 0.6, s * s);
    vAcross = vec2(sideSign, s);
    vFold = turn;
    vDepth = -here.z;
    vStrength = aShape.w;
    vShapeSeed = aShape.x;
    gl_Position = uProjection * vec4(here + across * sideSign * width * turn, 1.0);
}
"""
RIBBON_FRAGMENT = ("#version 460 core\n" + SCENE_OIT_GLSL + "layout(location=2) out vec4 Emission;\n"
                   + SCENE3D_SPHERES_GLSL + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + COMMON + """
uniform sampler2D uBackground;
uniform vec2 uTargetSize;
in vec2 vAcross;
in float vFold;
in float vDepth;
flat in float vStrength;
flat in float vShapeSeed;
// A wake is disturbed water: it bends the scene behind it (a soft wobble across the sheet) and here and there a
// thin fold of it catches the light as a faint broken strand; it fades as it falls behind.
void main() {
    float s = vAcross.y;
    float u = vAcross.x * 0.5 + 0.5;
    float fade = smoothstep(0.0, 0.08, s) * pow(1.0 - s, 1.8);
    float sheet = smoothstep(0.0, 0.25, u) * smoothstep(1.0, 0.75, u);
    // Refraction: the scene behind displaced across the sheet by a slow wave along it.
    float wave = sin(u * 9.0 + s * 14.0 + vShapeSeed * 20.0) * 0.6 + sin(u * 23.0 - s * 9.0 + vShapeSeed * 7.0) * 0.4;
    vec2 shift = vec2(dFdx(u), dFdy(u));
    shift = shift / max(length(shift), 1e-6) * wave * 3.0 * sheet * fade;
    if (!(abs(shift.x) + abs(shift.y) < 1e4)) shift = vec2(0.0);
    vec3 bent = texture(uBackground, (gl_FragCoord.xy + shift) / uTargetSize).rgb;
    // Strands: a bundle of fine filaments leaving the bubble together and fanning apart as they trail, each lightly
    // broken along its length, brightest where the sheet turns edge-on.
    float strands = 0.0;
    float pixelU = max(fwidth(u), 1e-4);
    for (int k = 0; k < 10; ++k) {
        float h = fract(float(k) * 0.618034 + vShapeSeed * 3.1);
        float centre = 0.5 + (h - 0.5) * (0.25 + 0.85 * s) + 0.04 * sin(s * (5.0 + float(k)) + float(k) * 1.7);
        float d = abs(u - centre) / (pixelU * mix(0.8, 1.6, fract(h * 7.3)));
        float broken = mix(0.35, 1.0, smoothstep(0.3, 0.7, skyNoise2(vec2(s * (10.0 + 3.0 * float(k)), float(k) * 3.7 + vShapeSeed * 11.0), 171u)));
        strands += exp(-d * d) * broken * mix(0.5, 1.0, fract(h * 13.1));
    }
    float edgeOn = 0.5 / (abs(vFold) + 0.5);
    float glow = min(strands, 1.5) * edgeOn * fade * vStrength;
    vec3 strandLight = mix(uSkyTint, uShaftColour, 0.5) * 1.6 + uLightColour * 0.25;
    float sheetA = sheet * fade * vStrength * 0.3;
    float a = clamp(sheetA + glow * 0.6, 0.0, 0.9);
    vec3 premultiplied = bent * sheetA + strandLight * glow * 0.6;
    sceneTransparent(premultiplied, a, vDepth);
    Emission = vec4(0.0);
}
""")
def stream_bands(directions, settings):
    """0..1 density of the streaming bands along world directions (rows of unit vectors)."""
    along = np.array(settings.get("travel", (0.0, 1.0, 0.0)), dtype=float)
    along /= np.linalg.norm(along)
    across = np.cross(along, (0.0, 0.0, 1.0))
    across = across / np.linalg.norm(across) if np.linalg.norm(across) > 1e-6 else np.array((1.0, 0.0, 0.0))
    a, b = directions @ across, directions @ along
    freq = settings.get("band_freq", 9.0)
    phase = a * freq + 1.4 * np.sin(b * 2.3 + a * 3.0) + 0.8 * np.sin(b * 5.1 - a * 7.0)
    return np.clip(0.5 + 0.5 * np.sin(phase), 0.0, 1.0)


def particulate(rng, settings):
    """Specks in the water all round the eye, gathered in drifting clouds stretched along the streaming direction."""
    count = int(settings.get("specks", 0.0) * 90000)
    if count <= 0:
        return np.zeros((1, 8), dtype=np.float32)
    nrng = np.random.default_rng(rng.randrange(1 << 30))
    directions = nrng.normal(size=(count * 2, 3))
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    distance = 1.2 + 38.0 * nrng.random(count * 2) ** 1.6
    points = directions * distance[:, None]
    along = np.array(settings.get("travel", (0.0, 1.0, 0.0)), dtype=float)
    along /= np.linalg.norm(along)
    across = np.cross(along, (0.0, 0.0, 1.0))
    across = across / np.linalg.norm(across) if np.linalg.norm(across) > 1e-6 else np.array((1.0, 0.0, 0.0))
    clouds = stream_bands(directions, settings) ** settings.get("cloud_contrast", 1.5)
    keep = nrng.random(count * 2) < (settings.get("cloud_floor", 0.12) + 0.88 * clouds)
    points, distance, clouds = points[keep][:count], distance[keep][:count], clouds[keep][:count]
    n = len(points)
    pixel = 2.0 * math.tan(math.radians(31.0)) / H
    radius = nrng.uniform(0.25, 1.1, n) ** 1.3 * pixel * distance * settings.get("speck_size", 1.0)
    bright = np.exp(nrng.normal(0.0, 0.7, n)) * (0.35 + settings.get("cloud_glow", 1.3) * clouds)
    warm = (nrng.random(n) < settings.get("warm_share", 0.7)).astype(float)
    return np.column_stack([points, radius, bright, warm, nrng.random(n), np.zeros(n)]).astype(np.float32)


GLINT_VERTEX = """#version 460 core
layout(location=0) in vec4 aSphere;
layout(location=1) in vec2 aExtra;
uniform mat3 uWorldToView;
uniform mat4 uProjection;
uniform vec2 uFrameSize;
uniform float uPixel;
uniform vec3 uLightView;
uniform vec3 uLightColour;
uniform vec3 uSunScreen;
flat out vec3 vColour;
out vec2 vDelta;
flat out float vReach;
flat out float vStrength;
""" + SCENE3D_SPHERES_GLSL + """
void main() {
    vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1)) * 2.0 - 1.0;
    int which = gl_InstanceID & 1;
    vec3 centre = uWorldToView * aSphere.xyz;
    float pixels = aSphere.w / (uPixel * max(-centre.z, 0.05));
    float h = fract(aExtra.x * 13.17 + float(which) * 0.37);
    vColour = uLightColour;
    vec4 clipCentre = uProjection * vec4(centre, 1.0);
    vec2 centrePx = (clipCentre.xy / clipCentre.w * 0.5 + 0.5) * uFrameSize;
    vec2 toward = uSunScreen.z > 0.5 ? uSunScreen.xy - centrePx : uLightView.xy;
    toward = normalize(toward + vec2(0.0, 1e-3));
    vec2 at = centrePx + toward * pixels * (which == 0 ? 0.62 : -0.68);
    // Only a few bubbles sparkle; the rest keep their soft highlight alone.
    float flare = h > 0.88 ? 1.0 : 0.0;
    vStrength = (which == 0 ? 0.7 : 0.25) * flare * (0.6 + 0.6 * h) * smoothstep(6.0, 16.0, pixels);
    vReach = clamp(pixels * 0.32, 3.0, 14.0);
    vDelta = corner * vReach;
    gl_Position = (aExtra.y < 0.5 && vStrength > 0.01 && centre.z < 0.0)
                ? vec4((at + corner * vReach) / uFrameSize * 2.0 - 1.0, 0.0, 1.0) : vec4(2.0, 2.0, 2.0, 1.0);
}
"""
GLINT_FRAGMENT = """#version 460 core
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
in vec2 vDelta;
flat in float vReach;
flat in float vStrength;
flat in vec3 vColour;
""" + SCENE3D_SPHERES_GLSL + """
void main() {
    float halo = exp(-dot(vDelta, vDelta) / (vReach * vReach * 0.12));
    vec3 light = vColour * (sceneStarburst(vDelta, vReach, 0.0) * 0.45 + halo * 0.9) * vStrength
               * (1.0 - smoothstep(0.7, 1.0, length(vDelta) / vReach));
    FragColor = vec4(light, 0.0);
    vec3 glow = light * 0.3;
    Emission = vec4(glow, dot(glow, vec3(0.2126, 0.7152, 0.0722)));
}
"""


def population(rng, view_to_world, tan, drift=0.0, wakes=None, wake_strength=0.0, travel=None, fizz=1.0,
               particulate_scene=False, chain_scale=1.0, chain_size=1.0, fizz_size=1.0, banded=None, small_count=1.0,
               columns=None, mid_count=1.0):
    if travel is not None:
        travel = np.array(travel, dtype=float) / np.linalg.norm(travel)
        across = np.cross(travel, (0.0, 0.0, 1.0))
        across = across / max(np.linalg.norm(across), 1e-6)
    items, clusters = [], []
    rot = np.array(view_to_world).reshape(3, 3).T

    def place(u, v, depth):
        d = np.array([u * tan[0], v * tan[1], -1.0])
        return tuple(rot @ (d * depth))

    def bubble(p, r, kind=0.0):
        items.append((p[0], p[1], p[2], r, rng.random(), kind))

    def cluster(members, blend):
        padded = list(members) + [(0.0, 0.0, 0.0, 0.0)] * (3 - len(members))
        clusters.append(tuple(v for m in padded for v in m) + (len(members), blend, rng.random(), 0.0))

    pixel = 2.0 * tan[1] / H
    if CARD:
        def at(x, y, rpx, depth):
            return place(x / W * 2.0 - 1.0, 1.0 - y / H * 2.0, depth), rpx * pixel * depth
        card = CARD_SETS[CARD]
        for x, y, rpx, depth in card["bubbles"]:
            bubble(*at(x, y, rpx, depth))
        for pair in card["doublets"]:
            cluster([tuple(at(*b)[0]) + (at(*b)[1],) for b in pair], at(*pair[1])[1] * 0.15)
        for x, high, low in card["chains"]:
            for k in range(60):
                y = high - (high - low) * k / 60.0 + rng.uniform(-3.0, 3.0)
                bubble(*at(x + rng.gauss(0.0, 4.0), y, rng.uniform(1.5, 4.0), 10.0))
        return items, clusters
    # Bubbles by on-screen radius, as the mocks show them: hundreds small, a good number mid, a few large.
    pixel = 2.0 * tan[1] / H
    bands = ((10, 40.0, 85.0), (int(26 * mid_count), 18.0, 40.0), (int(60 * mid_count), 8.0, 18.0),
             (int(150 * small_count), 2.0, 7.0))
    placed = []     # (x px, y px, radius px) of the bubbles 8 px and up
    for count, low, high in bands:
        for _ in range(count):
            for _try in range(30):
                u, v = rng.uniform(-1.12, 1.12), rng.uniform(-1.1, 1.08)
                pixels = rng.uniform(low, high)
                x, y = u * W / 2, v * H / 2
                if columns and rng.random() < 0.75:
                    # Streams: bubbles line up in columns along the travel (on screen), as the mocks show them.
                    tx, ty = columns[0], columns[1]
                    s = x * -ty + y * tx
                    snapped = round(s / columns[2]) * columns[2] + rng.gauss(0.0, columns[2] * 0.06)
                    x, y = x + -ty * (snapped - s), y + tx * (snapped - s)
                    u, v = x / (W / 2), y / (H / 2)
                if banded is not None:
                    d = np.array(place(u, v, 1.0))
                    if rng.random() > 0.1 + 0.9 * float(stream_bands(d[None, :] / np.linalg.norm(d), banded)[0]) ** 2:
                        continue
                if low < 8.0 or all((x - a) ** 2 + (y - b) ** 2 > ((pixels + c) * 1.05) ** 2 for a, b, c in placed):
                    break
            if low >= 8.0:
                placed.append((x, y, pixels * 1.6))
            depth = 6.0 + 26.0 * rng.random()
            r = pixels * pixel * depth
            p = place(u, v, depth)
            if high > 18.0 and rng.random() < 0.4:
                # Touching bubbles merge with a neck, as in the mocks.
                members = [(p[0], p[1], p[2], r)]
                for _m in range(1 if rng.random() < 0.8 else 2):
                    small = r * rng.uniform(0.25, 0.85)
                    gap = (r + small) * rng.uniform(0.7, 0.97)
                    angle = rng.uniform(0.0, 2.0 * math.pi)
                    tilt = rng.uniform(-0.5, 0.5)
                    members.append((p[0] + gap * math.cos(angle) * math.cos(tilt), p[1] + gap * math.sin(angle),
                                    p[2] + gap * math.sin(tilt), small))
                cluster(members, r * rng.uniform(0.08, 0.35))
            else:
                bubble(p, r)
            if wakes is not None and wake_strength > 0.0 and high > 8.0 and rng.random() < wake_strength * 0.6:
                start = (p[0], p[1] - r * 0.95, p[2]) if travel is None else tuple(np.array(p) - travel * r * 0.95)
                wakes.append((*start, r, rng.random(), r * rng.uniform(6.0, 14.0),
                              (drift + rng.uniform(-0.3, 0.3)) * (1.0 if travel is None else 0.2), wake_strength * rng.uniform(0.5, 1.0)))
            if high > 8.0:     # a dense wake of tiny bubbles trailing below, widening as it falls behind
                count_trail = int((rng.randint(40, 110) if high > 18.0 else rng.randint(15, 40)) * fizz)
                for k in range(count_trail):
                    along = rng.random() ** 0.7 * r * 9.0
                    spread = r * (0.25 + along / (r * 9.0) * 1.2)
                    if travel is not None:
                        at = (np.array(p) - travel * (r * 0.6 + along) + across * (rng.gauss(0, spread) + math.sin(along / r) * r * 0.3)
                              + np.array((0.0, 0.0, 1.0)) * rng.gauss(0, spread * 0.6))
                        bubble(tuple(at), r * rng.uniform(0.02, 0.08) * fizz_size * (1.0 - 0.5 * along / (r * 9.0)))
                        continue
                    bubble((p[0] + rng.gauss(0, spread) + math.sin(along / r) * r * 0.3 - drift * along, p[1] - r * 0.6 - along,
                            p[2] + rng.gauss(0, spread * 0.6)), r * rng.uniform(0.02, 0.08) * fizz_size * (1.0 - 0.5 * along / (r * 9.0)))
    # Near, out-of-focus giants at the edges.
    for side, v_low, v_high in ((-1, -0.9, -0.2), (1, -0.9, 0.0), (rng.choice((-1, 1)), 0.3, 0.8)):
        if v_low > 0.0 and rng.random() < 0.5:
            continue
        bubble(place(side * rng.uniform(0.8, 1.0), rng.uniform(v_low, v_high), rng.uniform(2.6, 3.6)),
               rng.uniform(0.5, 0.8), 3.0)
    # Rising chains: beads a few pixels across, spaced a few pixels apart on screen at any distance, wobbling a little
    # and leaning with the current; now and then a larger bead.
    for _ in range(int(42 * chain_scale)):
        u, depth = rng.uniform(-1.3, 1.3), 7.0 + 26.0 * rng.random()
        base = place(u, -1.25, depth)
        # The chain starts below the frame; beads come nearer the camera there, so they are sized where they are.
        base_depth = depth
        if travel is not None:
            base = tuple(np.array(place(rng.uniform(-1.2, 1.2), rng.uniform(-1.1, 1.1), depth)) - travel * 0.85 * depth)
        size = rng.uniform(1.4, 4.0) * chain_size
        scale = depth / 15.0
        rise, phase = 0.0, rng.uniform(0.0, 6.3)
        while rise < 1.7 * depth:
            rise += rng.uniform(0.05, 0.16) * scale * chain_size * (rng.uniform(3.0, 8.0) if rng.random() < 0.05 else 1.0)
            px = size * rng.uniform(0.3, 1.4) ** 1.5 * (2.4 if rng.random() < 0.06 else 1.0)
            if travel is not None:
                at = (np.array(base) + travel * rise
                      + across * (math.sin(rise / scale * 1.3 + phase) * 0.16 * scale + rng.gauss(0, 0.07 * scale))
                      + np.array((0.0, 0.0, 1.0)) * rng.gauss(0, 0.05 * scale))
                bubble(tuple(at), px * pixel * depth)
                continue
            at = (base[0] + drift * rise + math.sin(rise / scale * 0.6 + phase) * 0.1 * scale + rng.gauss(0, 0.045 * scale * (1.0 + rise / depth)),
                  base[1] + rise, base[2] + rng.gauss(0, 0.05 * scale))
            view_depth = -float(np.dot(rot.T @ np.array(at), (0.0, 0.0, 1.0)))
            bubble(at, px * pixel * max(view_depth, 1.0))
    if particulate_scene:
        return items, clusters
    # Marine snow.
    for _ in range(2500):
        bubble(place(rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2), 2.5 + 35.0 * rng.random()), 0.005, 1.0)
    return items, clusters


def render_variant(capture, resources, target, programs, env, env_fbo, settings, seed):
    (env_program, backdrop, shell, merged, shaft_program, blur_program, glint_program, ribbon_program, particle_program,
     near_program, near_cluster_program, shaft_tex, shaft_fbo) = programs
    settings = {**effective(settings), **OVERRIDES}
    pitch = math.radians(settings["pitch"])
    c, s = math.cos(pitch), math.sin(pitch)
    view_to_world = (1, 0, 0, 0, c, s, 0, -s, c)
    # The specular key: the light as the bubbles' faces meet it. World-fixed (orbits correctly). Default: the
    # surface's bright window straight overhead; scenes lit from one side give it in view space at the authored
    # camera ("spec_view"), converted to world once here.
    if "spec_view" in settings:
        base = np.array(view_to_world).reshape(3, 3).T
        spec_dir = base @ (np.array(settings["spec_view"]) / np.linalg.norm(settings["spec_view"]))
    else:
        spec_dir = np.array((0.0, 1.0, 0.0))
    if YAW:
        yaw = math.radians(YAW)
        ry = np.array(((math.cos(yaw), 0.0, math.sin(yaw)), (0.0, 1.0, 0.0), (-math.sin(yaw), 0.0, math.cos(yaw))))
        # Columns of view_to_world (row-major tuple read as columns by GL) are the view axes in world space.
        axes = np.array(view_to_world).reshape(3, 3).T
        view_to_world = tuple((ry @ axes).T.ravel())
    world_to_view = tuple(np.array(view_to_world).reshape(3, 3).T.ravel())
    fov = math.radians(62.0)
    tan_y = math.tan(fov / 2)
    tan = (tan_y * W / H, tan_y)
    f = 1.0 / tan_y
    near, far = 0.05, 200.0
    projection = (f * H / W, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) / (near - far), -1, 0, 0, 2 * far * near / (near - far), 0)
    sun = np.array(settings["sun"]) / np.linalg.norm(settings["sun"])
    sun_below = np.array(water_sun_below(tuple(sun)))
    if "light_view" in settings:   # deep scenes: the light's own direction in view space (no surface to refract it)
        rot = np.array(view_to_world).reshape(3, 3).T
        sun_below = rot @ (np.array(settings["light_view"]) / np.linalg.norm(settings["light_view"]))
    wakes = []
    items, clusters = population(random.Random(seed), view_to_world, tan, settings.get("drift", 0.0), wakes,
                                 settings.get("wakes", 0.0), settings.get("travel"), settings.get("fizz", 1.0),
                                 settings.get("specks", 0.0) > 0.0, settings.get("chains", 1.0),
                                 settings.get("chain_size", 1.0), settings.get("fizz_size", 1.0),
                                 settings if settings.get("banded") else None, settings.get("small_count", 1.0),
                                 settings.get("columns"), settings.get("mid_count", 1.0))
    pdata = particulate(random.Random(seed * 7 + 1), settings)
    # Proxies: each bubble as the probe sees it, its glint toward the light (a small bright point near its surface).
    bubble_rows = np.array([row for row in items if row[5] == 0.0 and row[3] > 0.01], dtype=np.float64)
    if len(bubble_rows):
        glint_points = bubble_rows[:, :3] + sun_below[None, :] * bubble_rows[:, 3:4] * 0.7
        distance = np.linalg.norm(glint_points, axis=1)
        # A glint is a point: never wider than about a degree as the probe sees it, however near.
        proxy_radius = np.maximum(bubble_rows[:, 3] * settings.get("proxy_size", 0.6), 0.004)
        proxy_bright = settings.get("proxy_power", 2.5) * np.ones(len(bubble_rows))
        proxies = np.column_stack([glint_points, proxy_radius, proxy_bright, np.ones(len(bubble_rows)),
                                   np.zeros(len(bubble_rows)), np.zeros(len(bubble_rows))]).astype(np.float32)
        pdata = np.concatenate([pdata, proxies]) if len(pdata) > 1 else proxies
    pvao, pvbo = int(gl.glGenVertexArrays(1)), int(gl.glGenBuffers(1))
    gl.glBindVertexArray(pvao)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, pvbo)
    gl.glBufferData(gl.GL_ARRAY_BUFFER, pdata.nbytes, pdata, gl.GL_STATIC_DRAW)
    for location in range(2):
        gl.glEnableVertexAttribArray(location)
        gl.glVertexAttribPointer(location, 4, gl.GL_FLOAT, gl.GL_FALSE, 32, ctypes.c_void_p(16 * location))
        gl.glVertexAttribDivisor(location, 1)
    gl.glBindVertexArray(0)
    trail = np.array(settings.get("travel", (0.0, 1.0, 0.0)), dtype=float)
    trail = -trail / np.linalg.norm(trail)
    wdata = np.array(wakes if wakes else [(0.0,) * 8], dtype=np.float32)
    wvao, wvbo = int(gl.glGenVertexArrays(1)), int(gl.glGenBuffers(1))
    gl.glBindVertexArray(wvao)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, wvbo)
    gl.glBufferData(gl.GL_ARRAY_BUFFER, wdata.nbytes, wdata, gl.GL_STATIC_DRAW)
    for location in range(2):
        gl.glEnableVertexAttribArray(location)
        gl.glVertexAttribPointer(location, 4, gl.GL_FLOAT, gl.GL_FALSE, 32, ctypes.c_void_p(16 * location))
        gl.glVertexAttribDivisor(location, 1)
    gl.glBindVertexArray(0)
    cdata = np.array(clusters, dtype=np.float32)
    cvao, cvbo = int(gl.glGenVertexArrays(1)), int(gl.glGenBuffers(1))
    gl.glBindVertexArray(cvao)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, cvbo)
    gl.glBufferData(gl.GL_ARRAY_BUFFER, cdata.nbytes, cdata, gl.GL_STATIC_DRAW)
    for location in range(4):
        gl.glEnableVertexAttribArray(location)
        gl.glVertexAttribPointer(location, 4, gl.GL_FLOAT, gl.GL_FALSE, 64, ctypes.c_void_p(16 * location))
        gl.glVertexAttribDivisor(location, 1)
    gl.glBindVertexArray(0)
    data = np.array(items, dtype=np.float32)
    vao, vbo = int(gl.glGenVertexArrays(1)), int(gl.glGenBuffers(1))
    gl.glBindVertexArray(vao)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
    gl.glBufferData(gl.GL_ARRAY_BUFFER, data.nbytes, data, gl.GL_STATIC_DRAW)
    for location, size, offset in ((0, 4, 0), (1, 2, 16)):
        gl.glEnableVertexAttribArray(location)
        gl.glVertexAttribPointer(location, size, gl.GL_FLOAT, gl.GL_FALSE, 24, ctypes.c_void_p(offset))
        gl.glVertexAttribDivisor(location, 1)
    gl.glBindVertexArray(0)
    gvao = int(gl.glGenVertexArrays(1))
    gl.glBindVertexArray(gvao)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
    for location, size, offset in ((0, 4, 0), (1, 2, 16)):
        gl.glEnableVertexAttribArray(location)
        gl.glVertexAttribPointer(location, size, gl.GL_FLOAT, gl.GL_FALSE, 24, ctypes.c_void_p(offset))
        gl.glVertexAttribDivisor(location, 2)
    gl.glBindVertexArray(0)
    rotation = np.array(view_to_world).reshape(3, 3).T
    light_view = rotation.T @ sun_below
    if light_view[2] < -1e-3:
        sun_screen = ((f * H / W * light_view[0] / -light_view[2] * 0.5 + 0.5) * W,
                      (f * light_view[1] / -light_view[2] * 0.5 + 0.5) * H, 1.0)
    else:
        sun_screen = (0.0, 0.0, 0.0)
    matrix = (2 / W, 0, 0, 0, 0, -2 / H, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
    frame = SimpleNamespace(viewport=(0, 0, W, H), logical_size=(float(W), float(H)), matrix_values=matrix,
                            quad_vao=capture.vao)

    def common(program):
        # Lab-authored six/16-float records are fully opaque; production carries explicit lifetime attributes.
        gl.glVertexAttrib1f(2, 1.0)
        gl.glVertexAttrib3f(4, 1.0, 1.0, 1.0)
        gl.glUseProgram(program)
        u = lambda name: gl.glGetUniformLocation(program, name)
        gl.glUniformMatrix3fv(u("uViewToWorld"), 1, gl.GL_FALSE, view_to_world)
        gl.glUniform2f(u("uTan"), *tan)
        gl.glUniform1f(u("uTime"), 4.0)
        gl.glUniform3f(u("uSun"), *sun)
        gl.glUniform3f(u("uSunBelow"), *sun_below)
        exposure = settings["exposure"]
        gl.glUniform1f(u("uWisps"), settings.get("wisps", 0.0))
        gl.glUniform1f(u("uVeils"), settings.get("veils", 0.0))
        gl.glUniform1f(u("uSurfaceY"), settings.get("surface", SURFACE_Y))
        gl.glUniform1f(u("uShaftY"), settings.get("shaft_y", SURFACE_Y))
        gl.glUniform1f(u("uGlow"), settings.get("glow", 1.0))
        gl.glUniform1f(u("uRays"), settings.get("rays", 1.0))
        gl.glUniform1f(u("uMist"), settings.get("mist", 0.0))
        gl.glUniform1f(u("uSurfaceGain"), settings.get("surface_gain", 1.0))
        gl.glUniform1f(u("uSurfaceSky"), settings.get("surface_sky", 1.0))
        gl.glUniform1f(u("uDust"), settings.get("dust", 0.0))
        gl.glUniform1f(u("uRayFocus"), settings.get("ray_focus", 0.0))
        gl.glUniform1f(u("uRayCut"), settings.get("ray_cut", 0.25))
        gl.glUniform1f(u("uShaftScale"), settings.get("shaft_scale", 1.0))
        gl.glUniform1f(u("uShaftSoft"), settings.get("shaft_soft", 0.0))
        gl.glUniform1f(u("uShaftFan"), settings.get("shaft_fan", 0.0))
        gl.glUniform1f(u("uFanRays"), settings.get("fan_rays", 30.0))
        gl.glUniform1f(u("uFanReach"), settings.get("fan_reach", 0.6))
        gl.glUniform2f(u("uFanMix"), settings.get("fan_contrast", 0.7), settings.get("fan_march", 0.2))
        gl.glUniform1f(u("uSpecks"), settings.get("specks", 0.0))
        gl.glUniform1f(u("uLightPower"), settings.get("light_power", 0.0))
        gl.glUniform1f(u("uGlintPower"), settings.get("glint_power", 0.0))
        gl.glUniform1f(u("uProbeFill"), settings.get("probe_fill", 0.0))
        gl.glUniform1f(u("uGlintSharp"), settings.get("glint_sharp", 6000.0))
        gl.glUniform1f(u("uProbeMode"), 0.0)
        gl.glUniform2f(u("uStreak"), *settings.get("streak", (0.0, 1.0)))
        gl.glUniform1f(u("uSparkle"), settings.get("sparkle", 0.0))
        sky = np.array(settings["sky"])
        gl.glUniform3f(u("uLightColour"), *settings.get("light", tuple(sky / max(sky.mean(), 1e-3) * 0.15 + 0.85)))
        gl.glUniform1f(u("uFilm"), settings.get("film", 0.0))
        gl.glUniform2f(u("uFilmRange"), *settings.get("film_range", (250.0, 600.0)))
        gl.glUniform1f(u("uCrisp"), settings.get("crisp", 0.0))
        gl.glUniform3f(u("uAbsorb"), *settings.get("absorb", (0.16, 0.065, 0.04)))
        for name, key in (("uDeep", "deep"), ("uWater", "water"), ("uSkyTint", "sky"), ("uShaftColour", "shaft")):
            gl.glUniform3f(u(name), *(v * exposure for v in settings[key]))

    def spec_uniforms(loc):
        # Lab reference art authors an angular emitter; production Deep uses
        # physical Source and per-interface points via the renderer's mapping.
        gl.glUniform1f(loc("uPositionalLight"), 0.0)
        gl.glUniform3f(loc("uLightDir"), *spec_dir)
        colour = np.array(settings.get("light", (1.0, 1.0, 1.0))) * settings.get("spec_power", 300.0)
        gl.glUniform3f(loc("uSpecColour"), *colour)
        gl.glUniform1f(loc("uSpecThrough"), settings.get("spec_through", 0.4))
        gl.glUniform3f(loc("uSpecShape"), settings.get("sun_size", 0.05), settings.get("spec_shoulder", 0.25),
                       settings.get("spec_broad", 0.012))

    def bubble_uniforms(program, background_tex):
        common(program)
        u = lambda name: gl.glGetUniformLocation(program, name)
        gl.glUniformMatrix3fv(u("uWorldToView"), 1, gl.GL_FALSE, world_to_view)
        gl.glUniformMatrix4fv(u("uProjection"), 1, gl.GL_FALSE, projection)
        gl.glUniform1f(u("uFocus"), settings.get("focus", 4.2))
        gl.glUniform1f(u("uAperture"), settings.get("aperture", 3.0))
        gl.glUniform1f(u("uPixel"), 2.0 * tan_y / H)
        gl.glUniform1f(u("uPixelSize"), 2.0 * tan_y / H)
        gl.glUniform1i(u("uEnvironment"), 3)
        gl.glUniform1i(u("uBackground"), 5)
        gl.glUniform2f(u("uTargetSize"), *target.allocation[:2])
        gl.glUniform2f(u("uFrameSize"), W, H)
        gl.glUniform3f(u("uSunScreen"), *sun_screen)
        gl.glUniform1i(u("uProbe"), 6)
        gl.glUniform1f(u("uProbeLevels"), PROBE.levels)
        gl.glUniform1f(u("uEta"), settings.get("eta", 1.33))
        gl.glUniform1f(u("uBehind"), settings.get("behind", 8.0))
        gl.glUniform1f(u("uLens"), settings.get("near_lens", 0.5) if program in (near_program,near_cluster_program) else settings.get("lens", 0.85))
        gl.glUniform1f(u("uShell"), settings.get("shell", 0.1))
        gl.glUniform3f(u("uIors"), *settings.get("iors", (1.33, 1.5, 1.0)))
        gl.glUniform1f(u("uNearCoc"), settings.get("near_coc", 22.0) * H / 941.0)
        gl.glUniform1f(u("uNearMax"), settings.get("near_coc", 22.0) * 1.6 * H / 941.0)
        # Face reflection share (an air bubble's face mirrors ~2%; the rim carries the reflections): per scene.
        gl.glUniform1f(u("uReflect"), settings.get("near_reflect", 0.15) if program in (near_program,near_cluster_program)
                       else settings.get("face_reflect", 1.0))
        gl.glUniform1f(u("uNearGain"), settings.get("near_gain", 0.5))
        gl.glUniform1f(u("uRough"), settings.get("rough", 0.0))
        gl.glUniform1f(u("uShellMin"), settings.get("shell_min", 0.0))
        gl.glUniform1i(u("uDiag"), DIAG)
        spec_uniforms(u)
        gl.glUniform1f(u("uSpeckGlow"), settings.get("speck_glow", 0.6))
        gl.glUniform1f(u("uInnerBlur"), settings.get("inner_blur", 0.25))
        gl.glUniform1f(u("uFrameShare"), settings.get("frame_share", 1.0))
        gl.glUniform1f(u("uNearLayer"), 1.0 if program in (near_program,near_cluster_program) else 0.0)
        gl.glActiveTexture(gl.GL_TEXTURE3)
        gl.glBindTexture(gl.GL_TEXTURE_2D, env)
        gl.glActiveTexture(gl.GL_TEXTURE5)
        gl.glBindTexture(gl.GL_TEXTURE_2D, background_tex)
        gl.glActiveTexture(gl.GL_TEXTURE6)
        gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, PROBE.texture)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    particulate_count = len(pdata) - (len(bubble_rows) if len(bubble_rows) else 0)

    def draw_particulate(rotation, row_major, proj, pixel, with_proxies=False):
        count = len(pdata) if with_proxies else particulate_count
        if count <= 1 or BACKDROP_ONLY:
            return
        common(particle_program)
        q = lambda name: gl.glGetUniformLocation(particle_program, name)
        gl.glUniformMatrix3fv(q("uWorldToView"), 1, gl.GL_FALSE, rotation)
        gl.glUniform1i(q("uRowMajor"), 1 if row_major else 0)
        gl.glUniformMatrix4fv(q("uProjection"), 1, gl.GL_FALSE, proj)
        gl.glUniform1f(q("uPixel"), pixel)
        gl.glUniform1f(q("uSpecks"), 1.0)
        gl.glUniform1f(q("uSpeckBloom"), 0.0 if row_major else settings.get("speck_bloom", 0.0))
        gl.glUniform1f(q("uParticleActivity"), 1.0)  # frozen art lab, not the logical idle driver
        gl.glUniform1f(q("uParticleRadiusShare"), 1.0)
        sky_ = np.array(settings["sky"])
        gl.glUniform3f(q("uSpeckWarm"), *settings.get("speck_warm", settings.get("light", tuple(sky_ / max(sky_.mean(), 1e-3) * 0.15 + 0.85))))
        blend0 = bool(gl.glIsEnabledi(gl.GL_BLEND, 0))
        depth_mask = bool(gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK))
        gl.glEnablei(gl.GL_BLEND, 0)
        gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
        gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glBindVertexArray(pvao)
        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, count)
        gl.glDepthMask(gl.GL_TRUE if depth_mask else gl.GL_FALSE)
        (gl.glEnablei if blend0 else gl.glDisablei)(gl.GL_BLEND, 0)

    def draw_probe_face(face, world_to_face, proj):
        common(backdrop)
        gl.glUniformMatrix3fv(gl.glGetUniformLocation(backdrop, "uViewToWorld"), 1, gl.GL_FALSE, world_to_face)
        gl.glUniform2f(gl.glGetUniformLocation(backdrop, "uTan"), 1.0, 1.0)
        gl.glUniform1f(gl.glGetUniformLocation(backdrop, "uProbeMode"), 1.0)
        gl.glUniform2f(gl.glGetUniformLocation(backdrop, "uFrameSize"), PROBE.size, PROBE.size)
        gl.glDisable(gl.GL_BLEND)
        gl.glBindVertexArray(capture.vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        draw_particulate(world_to_face, True, proj, 2.0 / PROBE.size, with_proxies=True)

    marks = []

    def mark(name):
        if marks is not None:
            q = int(np.asarray(gl.glGenQueries(1)).ravel()[0])
            gl.glQueryCounter(q, gl.GL_TIMESTAMP)
            marks.append((name, q))

    def render():
        mark("start")
        PROBE.capture(draw_probe_face)
        mark("probe")
        # (The equirect environment map is no longer sampled: the scene probe replaced it.)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        # Shafts: half-resolution march, then a separable blur (two textures ping-pong).
        hw, hh = W // 2, H // 2
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, shaft_fbo[0])
        gl.glViewport(0, 0, hw, hh)
        common(shaft_program)
        gl.glBindVertexArray(capture.vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glUseProgram(blur_program)
        gl.glUniform1i(gl.glGetUniformLocation(blur_program, "uSource"), 0)
        for source, target_fbo, step in ((shaft_tex[0], shaft_fbo[1], (1.0, 0.0)), (shaft_tex[1], shaft_fbo[0], (0.0, 1.0))):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target_fbo)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, source)
            gl.glUniform2f(gl.glGetUniformLocation(blur_program, "uStep"), *step)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        mark("shafts")
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glViewport(0, 0, W, H)
        gl.glClearColor(0.11, 0.11, 0.12, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        with target.scope(frame, 4, resources, overlay=1.0, bloom=0.55, depth_texture=True, oit=True,
                          hdr=settings.get("hdr_exposure", 1.0)):
            with target.emission_writes():
                common(backdrop)
                gl.glActiveTexture(gl.GL_TEXTURE4)
                gl.glBindTexture(gl.GL_TEXTURE_2D, shaft_tex[0])
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glUniform1i(gl.glGetUniformLocation(backdrop, "uShafts"), 4)
                gl.glUniform2f(gl.glGetUniformLocation(backdrop, "uFrameSize"), W, H)
                gl.glBindVertexArray(capture.vao)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
                draw_particulate(world_to_view, False, projection, 2.0 * tan_y / H)
                background_tex, _depth = target.background(frame, resources)
                mark("backdrop+particulate+capture")
                with target.transparent_writes(frame, resources):
                    bubble_uniforms(shell,background_tex)
                    gl.glBindVertexArray(vao)
                    if not BACKDROP_ONLY:
                        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP,0,4,len(items))
                    mark("shells")
                    bubble_uniforms(merged,background_tex)
                    gl.glBindVertexArray(cvao)
                    if not BACKDROP_ONLY:
                        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP,0,4,len(clusters))
                    mark("clusters")
                    if wakes and not BACKDROP_ONLY:
                        common(ribbon_program)
                        w = lambda name: gl.glGetUniformLocation(ribbon_program, name)
                        gl.glUniformMatrix3fv(w("uWorldToView"), 1, gl.GL_FALSE, world_to_view)
                        gl.glUniformMatrix4fv(w("uProjection"), 1, gl.GL_FALSE, projection)
                        gl.glUniform3f(w("uTrail"), *trail)
                        gl.glUniform1f(w("uSway"), settings.get("sway", 1.0))
                        gl.glUniform1i(w("uBackground"), 5)
                        gl.glUniform2f(w("uTargetSize"), *target.allocation[:2])
                        gl.glDisable(gl.GL_CULL_FACE)
                        gl.glBindVertexArray(wvao)
                        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 82, len(wakes))
                    gl.glActiveTexture(gl.GL_TEXTURE3)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
                    gl.glActiveTexture(gl.GL_TEXTURE0)
                mark("oit resolve")
                if not BACKDROP_ONLY:
                    NEAR.begin(*target.allocation[:2])
                    bubble_uniforms(near_program, background_tex)
                    gl.glViewport(0, 0, W, H)
                    gl.glBindVertexArray(vao)
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, len(items))
                    bubble_uniforms(near_cluster_program,background_tex)
                    gl.glBindVertexArray(cvao)
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP,0,4,len(clusters))
                    NEAR.end()
                    NEAR.composite(settings.get("near_coc", 22.0) * 1.6 * H / 941.0)
                    mark("near defocus")
                if not BACKDROP_ONLY and settings.get("glints", 0.0) > 0.0:
                    blend_on = bool(gl.glIsEnabledi(gl.GL_BLEND, 0))
                    depth_on = bool(gl.glIsEnabled(gl.GL_DEPTH_TEST))
                    gl.glEnablei(gl.GL_BLEND, 0)
                    gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
                    gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
                    gl.glDisable(gl.GL_DEPTH_TEST)
                    gl.glUseProgram(glint_program)
                    g = lambda name: gl.glGetUniformLocation(glint_program, name)
                    gl.glUniformMatrix3fv(g("uWorldToView"), 1, gl.GL_FALSE, world_to_view)
                    gl.glUniformMatrix4fv(g("uProjection"), 1, gl.GL_FALSE, projection)
                    gl.glUniform2f(g("uFrameSize"), W, H)
                    gl.glUniform1f(g("uPixel"), 2.0 * tan_y / H)
                    gl.glUniform3f(g("uLightView"), *light_view)
                    gl.glUniform3f(g("uSunScreen"), *sun_screen)
                    sky = np.array(settings["sky"])
                    gl.glUniform3f(g("uLightColour"), *settings.get("light", tuple(sky / max(sky.mean(), 1e-3) * 0.15 + 0.85)))
                    gl.glBindVertexArray(gvao)
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, 2 * len(items))
                    (gl.glEnablei if blend_on else gl.glDisablei)(gl.GL_BLEND, 0)
                    (gl.glEnable if depth_on else gl.glDisable)(gl.GL_DEPTH_TEST)
        mark("bloom+composite")

    query = int(np.asarray(gl.glGenQueries(1)).ravel()[0])
    times = []
    passes = {}
    for index in range(16):
        marks.clear()
        gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
        render()
        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        gl.glFlush()
        if index:
            times.append(int(np.asarray(gl.glGetQueryObjectuiv(query, gl.GL_QUERY_RESULT)).ravel()[0]) / 1e6)
            stamps = []
            for name, q in marks:
                value = ctypes.c_uint64(0)
                gl.glGetQueryObjectui64v(q, gl.GL_QUERY_RESULT, ctypes.byref(value))
                stamps.append((name, int(value.value)))
            for (_, before), (name, after) in zip(stamps, stamps[1:]):
                passes.setdefault(name, []).append((after - before) / 1e6)
        gl.glDeleteQueries(len(marks), [q for _, q in marks])
    TIMINGS.clear()
    TIMINGS.update({name: (float(np.median(v)), float(np.percentile(v, 95))) for name, v in passes.items()})
    TIMINGS["total"] = (float(np.median(times)), float(np.percentile(times, 95)))
    if "--probe-dump" in sys.argv:   # the probe's six faces at full detail, tone-clipped, in a cross
        faces = []
        for face in range(6):
            buffer = np.zeros((PROBE.size, PROBE.size, 4), dtype=np.float32)
            gl.glGetTextureSubImage(PROBE.texture, 0, 0, 0, face, PROBE.size, PROBE.size, 1, gl.GL_RGBA, gl.GL_FLOAT,
                                    buffer.nbytes, buffer)
            faces.append(np.clip(buffer[..., :3], 0.0, 1.0))
        s = PROBE.size
        cross = np.zeros((3 * s, 4 * s, 3), dtype=np.float32)
        for face, (row, col) in zip(range(6), ((1, 2), (1, 0), (0, 1), (2, 1), (1, 1), (1, 3))):
            cross[row * s:(row + 1) * s, col * s:(col + 1) * s] = faces[face][::-1]
        Image.fromarray((cross * 255).astype(np.uint8)).save(sys.argv[1].replace(".png", "_probe.png"))
    raw = gl.glReadPixels(0, 0, W, H, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    gl.glDeleteVertexArrays(1, [vao])
    gl.glDeleteVertexArrays(1, [gvao])
    gl.glDeleteBuffers(1, [vbo])
    image = Image.frombytes("RGBA", (W, H), bytes(raw)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert("RGB")
    gl.glDeleteVertexArrays(1, [cvao])
    gl.glDeleteVertexArrays(1, [wvao])
    gl.glDeleteVertexArrays(1, [pvao])
    gl.glDeleteBuffers(1, [pvbo])
    gl.glDeleteBuffers(1, [wvbo])
    gl.glDeleteBuffers(1, [cvbo])
    return image, float(np.median(times)), len(items) + len(clusters)


PROBE = None
PROBE_SIZE = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--probe=")), 256)
NEAR = None
TIMINGS = {}
TIMING_LOG = {}
# --set key=value[,key=value]: override every rendered variant (same-scene A/B without editing the variants).
OVERRIDES = {}
for _arg in sys.argv:
    if _arg.startswith("--set="):
        for _pair in _arg[6:].split(";"):
            _key, _value = _pair.split("=", 1)
            OVERRIDES[_key] = eval(_value, {}, {})
# --yaw=degrees: orbit the camera about the vertical axis (off-axis checks).
DIAG = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--diag=")), 0)
YAW = next((float(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--yaw=")), 0.0)


def main():
    global PROBE, NEAR
    capture = TransitionCapture(W, H)
    PROBE = SceneProbe("bubble lab probe", PROBE_SIZE)
    NEAR = DefocusLayer("bubble lab near layer")
    resources, target = MeshResources("bubble lab"), SceneTarget("bubble lab")
    programs = (compile_program(FULL_VERTEX, ENV_FRAGMENT, label="lab env"),
                compile_program(FULL_VERTEX, BACKDROP_FRAGMENT, label="lab backdrop"),
                compile_program(BUBBLE_VERTEX, BUBBLE_FRAGMENT, label="lab bubbles"),
                compile_program(CLUSTER_VERTEX, CLUSTER_FRAGMENT, label="lab clusters"),
                compile_program(FULL_VERTEX, SHAFT_FRAGMENT, label="lab shafts"),
                compile_program(FULL_VERTEX, BLUR_FRAGMENT, label="lab blur"),
                compile_program(GLINT_VERTEX, GLINT_FRAGMENT, label="lab glints"),
                compile_program(RIBBON_VERTEX, RIBBON_FRAGMENT, label="lab ribbons"),
                compile_program(PARTICLE_VERTEX, PARTICLE_FRAGMENT, label="lab particulate"),
                compile_program(BUBBLE_VERTEX, NEAR_FRAGMENT, label="lab near layer"),
                compile_program(CLUSTER_VERTEX, NEAR_CLUSTER_FRAGMENT, label="lab near clusters"))
    shaft_tex, shaft_fbo = [], []
    for _ in range(2):
        texture = int(np.asarray(gl.glGenTextures(1)).ravel()[0])
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexStorage2D(gl.GL_TEXTURE_2D, 1, gl.GL_R16F, W // 2, H // 2)
        for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, parameter, gl.GL_LINEAR)
        for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, wrap, gl.GL_CLAMP_TO_EDGE)
        fbo = int(np.asarray(gl.glGenFramebuffers(1)).ravel()[0])
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        shaft_tex.append(texture)
        shaft_fbo.append(fbo)
    programs = programs + (shaft_tex, shaft_fbo)
    levels = int(math.log2(ENV_W)) + 1
    env = int(np.asarray(gl.glGenTextures(1)).ravel()[0])
    gl.glBindTexture(gl.GL_TEXTURE_2D, env)
    gl.glTexStorage2D(gl.GL_TEXTURE_2D, levels, gl.GL_RGBA16F, ENV_W, ENV_H)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
    env_fbo = int(np.asarray(gl.glGenFramebuffers(1)).ravel()[0])
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, env_fbo)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, env, 0)
    half = (W // 2, H // 2)
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    names = [CARD] if CARD else [name for name in VARIANTS if only is None or name in only]
    sheet = Image.new("RGB", (W, half[1] * len(names)))
    for row, name in enumerate(names):
        image, gpu, count = render_variant(capture, resources, target, programs, env, env_fbo, VARIANTS[name], 11 + list(VARIANTS).index(name))
        image.save(sys.argv[1].replace(".png", f"_{name}.png"))
        if CARD:
            mock_full = Image.open(ROOT / "Docs/Reference/Extruded_Bubble/Targets/Originals" / f"{name}.png").convert("RGB").resize((W, H), Image.LANCZOS)
            for label, box in CARD_SETS[CARD]["crops"].items():
                a, b = mock_full.crop(box), image.crop(box)
                pair = Image.new("RGB", (a.width * 2 + 6, a.height))
                pair.paste(a, (0, 0))
                pair.paste(b, (a.width + 6, 0))
                pair.save(sys.argv[1].replace(".png", f"_card_{label}.png"))
        mock = Image.open(ROOT / "Docs/Reference/Extruded_Bubble/Targets/Originals" / f"{name}.png").convert("RGB").resize(half, Image.LANCZOS)
        sheet.paste(mock, (0, row * half[1]))
        sheet.paste(image.resize(half, Image.LANCZOS), (half[0], row * half[1]))
        print(f"{name}: GPU median {gpu:.3f} ms (p95 {TIMINGS['total'][1]:.3f}), {count} instances ({W}x{H}, 4x MSAA)")
        print("   " + "  ".join(f"{k} {v[0]:.2f}/{v[1]:.2f}" for k, v in TIMINGS.items() if k != "total"))
        TIMING_LOG[name] = dict(TIMINGS)
    sheet.save(sys.argv[1])
    import json
    Path(sys.argv[1].replace(".png", "_timings.json")).write_text(json.dumps(
        {"overrides": {k: repr(v) for k, v in OVERRIDES.items()}, "yaw": YAW, "size": [W, H], "msaa": 4,
         "passes_ms_median_p95": TIMING_LOG}, indent=1), encoding="utf-8")
    PROBE.release()
    NEAR.release()
    target.release()
    resources.release_resources()
    capture.close()


main()
