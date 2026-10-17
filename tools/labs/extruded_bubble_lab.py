"""Extruded Bubble composition lab (§4A): every shared primitive composed into one underwater scene per operator mock
(tmp/Bubbleexamples: bright, mid, dark water, teal), rendered offscreen at the mocks' resolution and laid side by
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

W, H = 1672, 941
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

# Per mock: water palette, sun, camera pitch.
VARIANTS = {
    "ExBubble1": dict(shaft_fan=1.0, fan_rays=22.0, shaft_scale=0.55, shaft_soft=0.35, ray_focus=0.3, film=0.3, surface_sky=0.35, glint_power=120.0, glint_sharp=300.0, probe_fill=3.0, proxy_power=10.0, shell=0.03, iors=(1.15, 2.0, 1.0), lens=1.0, surface_gain=1.6, rough=0.05,
                      chains=3.0, chain_size=1.0,
                      deep=(0.1, 0.16, 0.24), water=(0.19, 0.26, 0.36), sky=(0.82, 0.9, 0.98), shaft=(0.62, 0.67, 0.74),
                      sun=(0.05, 0.75, -1.0), pitch=16.0, exposure=1.0, absorb=(0.06, 0.042, 0.032), ray_cut=0.08, rays=0.7),
    "ExBubble2": dict(ray_cut=0.1, shaft_fan=1.0, fan_rays=22.0, shaft_scale=0.55, shaft_soft=0.35, ray_focus=0.3, film=0.35, surface_sky=0.35, glint_power=120.0, glint_sharp=300.0, probe_fill=3.0, proxy_power=10.0, shell=0.03, iors=(1.15, 2.0, 1.0), lens=1.0, surface_gain=3.0, rough=0.05,
                      chains=3.0, chain_size=1.0,
                      deep=(0.022, 0.055, 0.12), water=(0.03, 0.08, 0.16), sky=(0.6, 0.76, 0.95), shaft=(0.36, 0.55, 0.85),
                      sun=(0.0, 0.7, -1.0), pitch=16.0, exposure=0.9, absorb=(0.08, 0.05, 0.035), rays=0.7),
    "ExBubble3": dict(ray_cut=0.1, shaft_fan=1.0, fan_rays=22.0, shaft_scale=0.55, shaft_soft=0.35, ray_focus=0.3, film=0.3, surface_sky=0.35, glint_power=120.0, glint_sharp=300.0, probe_fill=3.0, proxy_power=10.0, shell=0.03, iors=(1.15, 2.0, 1.0), lens=1.0, surface_gain=2.0, rough=0.05,
                      chains=3.0, chain_size=1.0,
                      deep=(0.016, 0.03, 0.046), water=(0.024, 0.046, 0.07), sky=(0.52, 0.68, 0.85), shaft=(0.45, 0.5, 0.58),
                      sun=(0.0, 0.8, -1.0), pitch=18.0, exposure=0.82, absorb=(0.09, 0.06, 0.045), rays=0.55),
    "ExBubble4": dict(ray_cut=0.1, shaft_fan=1.0, fan_rays=22.0, shaft_scale=0.55, shaft_soft=0.35, ray_focus=0.3, film=0.8, film_range=(255.0, 345.0), surface_sky=0.35, glint_power=120.0, glint_sharp=300.0, probe_fill=3.0, proxy_power=10.0, shell=0.03, iors=(1.15, 2.0, 1.0), lens=1.0, surface_gain=2.5, rough=0.05,
                      chains=3.0, chain_size=1.0,
                      deep=(0.05, 0.11, 0.2), water=(0.04, 0.1, 0.17), sky=(0.48, 0.66, 0.84), shaft=(0.4, 0.58, 0.8),
                      sun=(0.15, 0.65, -1.0), pitch=14.0, exposure=0.82, absorb=(0.1, 0.05, 0.03), drift=0.12,
                      wakes=0.0, mist=0.3, aperture=1.2),
    "ExBubble5CameraAbyss": dict(spec_view=(0.6, 0.6, 0.5),inner_blur=0.12, speck_glow=0.25, chains=2.0, near_coc=3.0, near_lens=1.0, near_reflect=0.1, film=0.9, film_range=(255.0, 345.0), glint_power=1500.0, glint_sharp=300.0, probe_fill=2.5, mid_count=0.45, travel=(0.4, 1.0, 0.0),
                                 columns=(0.371, 0.928, 120.0), shell=0.03, iors=(1.15, 2.0, 1.0), lens=1.0, surface_gain=0.6,
                                 rough=0.05, light_power=1.2, light_view=(0.75, 0.75, -1.0), light=(0.75, 0.88, 1.0),
                                 specks=0.35, warm_share=0.85, streak=(0.35, 1.0), chain_size=1.0,
                                 deep=(0.004, 0.02, 0.05), water=(0.01, 0.06, 0.14), sky=(0.3, 0.6, 1.0),
                                 shaft=(0.25, 0.5, 0.95), sun=(0.6, 0.6, -1.0), pitch=6.0, exposure=1.0, wisps=0.0,
                                 mist=0.6, wakes=0.0, focus=3.2, sparkle=1.0, crisp=1.0, surface=60.0,
                                 absorb=(0.1, 0.05, 0.03), drift=0.6, shaft_y=16.0, glow=0.6, rays=0.2, aperture=0.6),
    "ExBubble5Cameradown": dict(
        # Looking down into a dark abyss lit from above and behind: deep blue-black, a lighter haze far off.
        deep=(0.01, 0.04, 0.08), water=(0.03, 0.11, 0.2), sky=(0.45, 0.65, 1.0), shaft=(0.3, 0.55, 0.95),
        sun=(0.3, 0.8, -1.0), pitch=-32.0, exposure=1.0, surface=30.0, shaft_y=12.0, absorb=(0.1, 0.05, 0.03),
        surface_gain=0.6, light_power=0.0, mist=0.4, rays=0.4, glow=0.6, drift=0.15, wisps=0.0, wakes=0.0,
        # Particulate and streams.
        specks=0.6, warm_share=0.85, streak=(0.15, 1.0), chains=5.0, chain_size=1.0, mid_count=0.6, sparkle=0.7,
        # Luminous violet-rimmed glass bubbles with sharp glints.
        crisp=1.0, rough=0.03, film=1.0, film_range=(255.0, 345.0), shell=0.03, iors=(1.15, 2.0, 1.0), lens=1.0,
        probe_fill=5.0, glint_power=400.0, glint_sharp=600.0, inner_blur=0.15),
}
VARIANTS["ExBubble6Diagonal"] = dict(spec_view=(0.75, 0.55, 0.38),
    # Water and light: near-black teal, orange light from the top-right corner, faint beams.
    deep=(0.012, 0.05, 0.06), water=(0.03, 0.13, 0.17), sky=(1.0, 0.55, 0.22), shaft=(0.95, 0.45, 0.14),
    light=(1.0, 0.52, 0.2), sun=(0.9, 0.35, -0.5), light_view=(1.0, 0.68, -1.0), pitch=4.0, exposure=1.0,
    hdr_exposure=0.75, surface=60.0, shaft_y=16.0, glow=0.2, rays=0.25, ray_focus=1.0, mist=0.6, dust=1.2,
    light_power=0.15, absorb=(0.06, 0.05, 0.05),
    # Ember particulate in diagonal bands; bubbles streaming with it.
    specks=1.8, speck_warm=(0.9, 0.26, 0.05), speck_size=1.6, warm_share=0.9, streak=(1.0, -0.3), banded=True,
    band_freq=9.0, cloud_contrast=3.0, cloud_floor=0.03, cloud_glow=0.6, travel=(1.0, -0.3, 0.15), sway=0.25,
    fizz=2.5, fizz_size=2.0, small_count=5.0, sparkle=1.5, wakes=0.0, mid_count=1.5,
    # Crisp clear glass bubbles: dark interiors, orange-lit rims and glints.
    crisp=1.0, rough=0.1, inner_blur=0.6, shell=0.03, iors=(1.15, 2.0, 1.0), probe_fill=0.4, glint_power=300.0,
    glint_sharp=300.0, lens=1.0, focus=3.4, aperture=1.5)

COMMON = """
uniform mat3 uViewToWorld;
uniform vec2 uTan;
uniform float uTime;
uniform vec3 uSun;
uniform vec3 uSunBelow;
uniform vec3 uDeep;
uniform vec3 uWater;
uniform vec3 uSkyTint;
uniform vec3 uShaftColour;
uniform float uWisps;
uniform float uSurfaceY;
uniform vec3 uAbsorb;
uniform float uShaftY;
uniform float uGlow;
uniform float uRays;
uniform float uMist;
uniform float uSurfaceGain;
uniform float uSurfaceSky;      // the window's light away from the sun   // the light through the surface (HDR: what bubbles mirror)
uniform float uDust;
uniform float uRayFocus;
uniform float uRayCut;          // beam density below which water stays clear
uniform float uSpecks;          // particulate density in the water
uniform float uProbeMode;       // 1 while drawn into the scene probe
uniform float uLightPower;      // the light itself, seen directly (deep scenes)
uniform float uGlintPower;      // the sun as only reflections see it
uniform float uProbeFill;
uniform float uGlintSharp;      // how small the sun is to a bubble (cosine exponent)       // scattered light round a bubble (what its wall mirrors)
uniform vec2 uStreak;           // on-screen direction the particulate clouds stretch along
uniform float uSparkle;
uniform vec3 uLightColour;      // the scene light's colour (sunlight through this water)
uniform float uFilm;            // soap-film tint strength
uniform vec2 uFilmRange;        // film thickness range, nm
uniform float uCrisp;           // 0 softly focused (mocks 1-4) .. 1 crisp (abyss, sixth mock)
#define SURFACE_Y uSurfaceY
vec2 equirectUv(vec3 d) { return vec2(atan(d.x, -d.z) / 6.28318530718 + 0.5, asin(clamp(d.y, -1.0, 1.0)) / 3.14159265359 + 0.5); }
vec3 equirectDirection(vec2 uv) {
    float lon = (uv.x - 0.5) * 6.28318530718, lat = (uv.y - 0.5) * 3.14159265359;
    return vec3(sin(lon) * cos(lat), sin(lat), -cos(lon) * cos(lat));
}
// Wind ripples: drifting lattice-noise octaves, stretched across the wind, each faded out as it shrinks toward
// the pixel's footprint; the normal from central differences.
float rippleHeight(vec2 p, float t, float footprint) {
    float h = 0.0, amplitude = 0.5, wavelength = 3.0;
    vec2 q = p;
    for (int i = 0; i < 6; ++i) {
        float fade = 1.0 - smoothstep(0.35, 0.8, footprint / wavelength);
        vec2 drift = vec2(0.9, 0.35) * t * (0.6 + 0.25 * float(i));
        h += amplitude * fade * (skyNoise2((q + drift) / wavelength * vec2(1.0, 1.7), 90u + uint(i)) - 0.5);
        amplitude *= 0.55;
        wavelength *= 0.52;
        q = mat2(0.8, 0.6, -0.6, 0.8) * q;
    }
    return h;
}
vec3 rippleNormal(vec2 p, float t, float footprint) {
    float e = max(footprint * 0.5, 0.02);
    float dx = rippleHeight(p + vec2(e, 0.0), t, footprint) - rippleHeight(p - vec2(e, 0.0), t, footprint);
    float dz = rippleHeight(p + vec2(0.0, e), t, footprint) - rippleHeight(p - vec2(0.0, e), t, footprint);
    return normalize(vec3(-dx / (2.0 * e) * 1.6, 1.0, -dz / (2.0 * e) * 1.6));
}
vec3 basinSky(vec3 dir) {
    float sun = max(dot(dir, uSun), 0.0);
    vec3 sky = uSkyTint * (0.45 + 0.6 * pow(sun, 3.0)) * smoothstep(-0.05, 0.3, dir.y);
    return sky + vec3(pow(sun, 350.0) * 30.0 + pow(sun, 40.0) * 1.8 + pow(sun, 10.0) * 0.45);
}
// The water along a ray from the eye (world y up). detail 1: everything; lower in blurred lookups.
vec3 basinWater(vec3 ray, float detail, float shafts) {
    float glow = max(dot(ray, uSunBelow), 0.0);
    vec3 medium = mix(uDeep * smoothstep(-1.0, -0.2, ray.y) * 0.8 + uDeep * 0.2, uWater,
                      pow(smoothstep(-0.5, 0.9, ray.y), 1.5))
                + uShaftColour * (pow(glow, 4.0) * 0.08 * (uGlow - 1.0) + pow(glow, 10.0) * 0.22 * uGlow
                                  + pow(glow, 60.0) * 0.6);
    if (shafts > 0.0)
        medium += mix(uShaftColour, vec3(0.9), 0.35) * shafts * (0.4 + 1.9 * pow(glow, 2.5));
    // Below: the abyss, darkening with depth (operator: no ocean floor).
    if (ray.y <= 0.015) return medium;
    float distance_ = SURFACE_Y / ray.y;
    vec2 hit = (ray * distance_).xz;
    float footprint = length(fwidth(hit)) * detail + (1.0 - detail) * 1.5;
    vec3 n = rippleNormal(hit, uTime, footprint);
    // Light from above leaves through the surface where the slope lets it; the sun's broad lobe through tilted
    // wavelets makes the bright patches, the sky between them the dimmer light, total reflection the deep.
    vec3 out_ = refract(ray, -n, 1.33);
    vec3 surface = medium;
    if (dot(out_, out_) > 1e-8) {
        out_ = normalize(out_);
        float transmission = 1.0 - sceneFresnelDielectric(clamp(dot(ray, n), 0.0, 1.0), 1.33);
        float s = max(dot(out_, uSun), 0.0);
        // The sky's own colour between the patches; the sun's light white, as sunlight is.
        vec3 white = mix(uSkyTint, vec3(1.0), 0.85);
        // Away from the sun the window shows dim sky: the bright patches gather round the sun (mocks).
        vec3 light = uSkyTint * (0.28 + 0.3 * out_.y) * uSurfaceSky + white * (pow(s, 6.0) * 0.45 * uSurfaceSky + pow(s, 40.0) * 1.4)
                   + vec3(pow(s, 900.0) * 40.0);
        float window = smoothstep(0.56, 0.7, ray.y);
        surface = mix(medium * 0.75, light * uSurfaceGain, transmission * smoothstep(0.0, 0.25, out_.y) * window);
    } else {
        surface = medium * 0.75;
    }
    vec3 result = waterMedium(surface, distance_ * 1.0, uAbsorb, medium);
    return result;
}
"""

FULL_VERTEX = """#version 460 core
out vec2 vNdc;
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    vNdc = p * 2.0 - 1.0;
    gl_Position = vec4(vNdc, 0.9999, 1.0);
}
"""
ENV_FRAGMENT = "#version 460 core\nout vec4 FragColor;\nin vec2 vNdc;\n" + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + COMMON + """
void main() {
    vec3 dir = equirectDirection(vNdc * 0.5 + 0.5);
    float shafts = waterShafts(vec3(0.0), dir, 40.0, uSunBelow, uShaftY, uTime, 12, 0.5) * 0.08;
    FragColor = vec4(basinWater(dir, 0.6, shafts), 1.0);
}
"""
SPECKS_GLSL = """
float speckLayer(vec2 px, float cell, float size, float density, uint salt, out float hue) {
    vec2 id = floor(px / cell);
    float h = sceneRandom(uint(int(id.x) + 65536) * 0x8da6b343u ^ uint(int(id.y) + 65536) * 0xd8163841u, salt, 5u);
    vec2 centre = (id + 0.2 + 0.6 * vec2(fract(h * 57.31), fract(h * 91.17))) * cell;
    float d = distance(px, centre);
    hue = fract(h * 23.7);
    float lit = step(1.0 - density, fract(h * 7.91));
    return lit * exp(-d * d / (size * size)) * (0.35 + 0.65 * fract(h * 13.3));
}
// The particulate seen along a view ray: (light-coloured, neutral) amounts.
vec2 waterSpecks(vec3 ray, vec2 framePx) {
    float pxPerRadian = framePx.y / (2.0 * uTan.y);
    vec2 angular = vec2(atan(ray.x, -ray.z), asin(clamp(ray.y, -1.0, 1.0))) * pxPerRadian;
    vec2 along = normalize(uStreak + vec2(1e-4));
    vec2 rotated = vec2(dot(angular, along), dot(angular, vec2(-along.y, along.x)));
    float cloud = skyFbm2(rotated * vec2(0.0018, 0.008) + vec2(uTime * 0.01, 0.0), 4, 131u);
    float clouds = smoothstep(0.35, 0.75, cloud);
    float density = uSpecks * (0.12 + 0.88 * clouds);
    float hueA, hueB, hueC;
    float a = speckLayer(angular, 7.0, 0.55, density * 0.55, 141u, hueA);
    float b = speckLayer(angular + 3.1, 13.0, 0.9, density * 0.45, 149u, hueB);
    float c = speckLayer(angular + 7.7, 31.0, 2.6, density * 0.35, 151u, hueC) * 0.35;
    float warm = a * step(0.3, hueA) + b * step(0.25, hueB) + c * step(0.3, hueC);
    float cool = a * (1.0 - step(0.3, hueA)) + b * (1.0 - step(0.25, hueB)) + c * (1.0 - step(0.3, hueC));
    return vec2(warm, cool) * (0.6 + 0.6 * clouds);
}
"""
BACKDROP_FRAGMENT = ("#version 460 core\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\n"
                     "in vec2 vNdc;\nuniform sampler2D uShafts;\nuniform vec2 uFrameSize;\n" + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + COMMON
                     + """
void main() {
    vec3 ray = uViewToWorld * normalize(vec3(vNdc * uTan, -1.0));
    float shafts = uProbeMode > 0.5
                 ? 0.6 * pow(max(dot(ray, uSunBelow), 0.0), 3.0) * uRays
                 : texture(uShafts, gl_FragCoord.xy / uFrameSize).r * uRays;
    if (uProbeMode < 0.5) {
        float s = texture(uShafts, gl_FragCoord.xy / uFrameSize).r;
        shafts = uRays * (uRayCut > 0.0 ? s * smoothstep(uRayCut * 0.6, uRayCut * 1.6, s) * 1.2 + s * 0.3 : s * 1.4);
    }
    // Beams gathered around the light (the sixth mock's corner) rather than filling the water.
    shafts *= mix(1.0, pow(max(dot(ray, uSunBelow), 0.0), 6.0) * 3.0, uRayFocus);
    vec3 colour = basinWater(ray, 1.0, shafts);
    if (uMist > 0.0) {
        float haze = pow(1.0 - abs(ray.y), 3.0);
        float drift = skyFbm2(vec2(atan(ray.x, -ray.z) * 2.5, ray.y * 3.0) + vec2(uTime * 0.01, 0.0), 3, 61u);
        colour += uWater * 0.8 * uMist * haze * (0.35 + 0.9 * drift);
    }
    if (uDust > 0.0) {
        // Glowing clouds of fine dust (the 3D particulate gives their grain), stretched along the streaming.
        vec2 angular = vec2(atan(ray.x, -ray.z), asin(clamp(ray.y, -1.0, 1.0)));
        vec2 along = normalize(uStreak + vec2(1e-4));
        vec2 rotated = vec2(dot(angular, along), dot(angular, vec2(-along.y, along.x)));
        float cloud = skyFbm2(rotated * vec2(1.6, 6.5) + vec2(uTime * 0.02, 0.0), 5, 67u);
        float dust = smoothstep(0.42, 0.85, cloud);
        float toward = 0.5 + 1.2 * pow(max(dot(ray, uSunBelow), 0.0), 2.0);
        vec3 ember = uShaftColour * vec3(1.0, 0.62, 0.4);
        colour += ember * uDust * dust * dust * 0.45 * toward;
    }
    if (uWisps > 0.0) {
        float strands = 0.0;
        for (int i = 0; i < 3; ++i) {
            float d = 6.0 + 7.0 * float(i);
            vec3 at = ray * d;
            strands += waterWisps(vec2(at.x + at.z * 0.3, at.y) * (0.9 - 0.15 * float(i)) + vec2(float(i) * 7.3), uTime)
                     * exp(-d * 0.06);
        }
        colour += mix(uShaftColour, vec3(0.5, 0.8, 1.0), 0.3) * strands * 0.22 * uWisps;
    }
    if (uLightPower > 0.0) {
        float g = max(dot(ray, uSunBelow), 0.0);
        // An area light: a hot core, a broad bright body and the glow of the water round it.
        colour += uLightColour * uLightPower * (pow(g, 2500.0) * 8.0 + pow(g, 180.0) * 1.6 + pow(g, 25.0) * 0.25
                                               + pow(g, 5.0) * 0.06);
    }
    if (uProbeMode > 0.5 && uProbeFill > 0.0) {
        // The water all round a bubble is lit by light scattered from above: what its wall mirrors sideways and below
        // is the bright scattering water, not the dark deep the camera sees far off (mocks: bubbles lighter than the
        // water everywhere).
        vec3 lit = mix(uWater, uSkyTint * 0.5, 0.35) * uProbeFill * (0.55 + 0.45 * ray.y);
        colour = max(colour, lit);
    }
    if (uProbeMode > 0.5 && uGlintPower > 0.0) {
        // The sun as the bubbles see it: a tiny, very bright source (in the probe only; the frame shows it through
        // the surface). A small bubble mirrors it into a pixel-sized point bright enough to sparkle.
        float g = max(dot(ray, uSunBelow), 0.0);
        colour += uLightColour * uGlintPower * (pow(g, uGlintSharp) + pow(g, uGlintSharp * 0.1) * 0.02);
    }
    FragColor = vec4(colour, 1.0);
    vec3 glow = max(colour - 1.1, 0.0) * 0.4;
    Emission = vec4(glow, dot(glow, vec3(0.2126, 0.7152, 0.0722)));
}
""")

# Volumetric shafts at half resolution, jittered, then blurred: smooth beams without per-pixel grain.
SHAFT_FRAGMENT = "#version 460 core\nout vec4 FragColor;\nin vec2 vNdc;\n" + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + COMMON + """
uniform float uShaftScale;      // source pattern frequency (1: the shared pattern's)
uniform float uShaftSoft;       // threshold softness 0..1
uniform float uShaftFan;        // share of the sun fan (0: depth march only)
uniform float uFanRays;         // broad rays round a full turn of the fan
float labShaftFan(vec3 ray, vec3 sunBelow, float t) {
    // Azimuth round the sun axis, zero pointing down (the seam faces up, behind the sun).
    vec3 down = normalize(vec3(0.0, -1.0, 0.0) - sunBelow * -sunBelow.y + vec3(1e-4, 0.0, 0.0));
    vec3 side = cross(sunBelow, down);
    float phi = atan(dot(ray, side), dot(ray, down)) / 6.2831853;
    float theta = acos(clamp(dot(ray, sunBelow), -1.0, 1.0));
    float x = phi * uFanRays;
    float broad = skyNoise2(vec2(x + t * 0.04, 0.5), 83u);
    float mid = skyNoise2(vec2(x * 2.7 - t * 0.07, 3.5), 89u);
    float fine = skyNoise2(vec2(x * 7.3 + t * 0.1, 7.5), 97u);
    float n = broad * 0.55 + mid * 0.3 + fine * 0.15;
    float lo = mix(0.5, 0.25, uShaftSoft), hi = mix(0.78, 0.9, uShaftSoft);
    float rays = smoothstep(lo, hi, n);
    // Each ray reaches its own length; all fade with the angle from the sun.
    float reach = mix(0.7, 1.6, skyNoise2(vec2(x * 1.3, 11.5), 101u));
    // The fan hangs below the sun: rays leaving sideways (toward the top corners) are faint (mocks).
    float spread = smoothstep(0.24, 0.1, abs(phi));
    return rays * spread * exp(-theta / reach) * smoothstep(0.02, 0.12, theta);
}
float labShaftPattern(vec2 q, float t) {
    q *= uShaftScale;
    float a = skyNoise2(q * 2.1 + vec2(t * 0.12, -t * 0.07), 71u);
    float b = skyNoise2(q * 5.3 + vec2(-t * 0.2, t * 0.15), 73u);
    float slow = skyNoise2(q * 0.55 + vec2(t * 0.03, 0.0), 79u);
    float n = a * 0.7 + b * 0.3;
    float lo = mix(0.58, 0.3, uShaftSoft), hi = mix(0.82, 0.95, uShaftSoft);
    return smoothstep(lo, hi, n) * (0.45 + 0.9 * slow);
}
float labShafts(vec3 ray, float maxDistance, vec3 sunBelow, float surfaceY, float t, int samples, float jitter) {
    float stepLength = maxDistance / float(samples);
    vec2 slope = sunBelow.xz / max(sunBelow.y, 0.2);
    float sum = 0.0;
    for (int i = 0; i < samples; ++i) {
        float s = (float(i) + jitter) * stepLength;
        vec3 p = ray * s;
        float below = surfaceY - p.y;
        if (below <= 0.0) break;
        sum += labShaftPattern(p.xz + slope * below, t) * exp(-below * 0.07) * exp(-s * 0.035);
    }
    return sum * stepLength;
}
void main() {
    vec3 ray = uViewToWorld * normalize(vec3(vNdc * uTan, -1.0));
    float jitter = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
    float toward = pow(max(dot(ray, uSunBelow), 0.0), 2.0);
    float march = labShafts(ray, 45.0, uSunBelow, uShaftY, uTime, 40, jitter) * 0.13 * (0.25 + toward);
    FragColor = vec4(mix(march, labShaftFan(ray, uSunBelow, uTime) * 0.9 + march * 0.2, uShaftFan));
}
"""
BLUR_FRAGMENT = """#version 460 core
out vec4 FragColor;
uniform sampler2D uSource;
uniform vec2 uStep;
void main() {
    vec2 uv = gl_FragCoord.xy * abs(uStep) / max(abs(uStep.x) + abs(uStep.y), 1e-9) * 0.0 + gl_FragCoord.xy;
    vec2 size = vec2(textureSize(uSource, 0));
    const float w[5] = float[5](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
    float sum = texture(uSource, gl_FragCoord.xy / size).r * w[0];
    for (int i = 1; i < 5; ++i) {
        sum += texture(uSource, (gl_FragCoord.xy + uStep * float(i) * 1.5) / size).r * w[i];
        sum += texture(uSource, (gl_FragCoord.xy - uStep * float(i) * 1.5) / size).r * w[i];
    }
    FragColor = vec4(sum);
}
"""

BUBBLE_VERTEX = """#version 460 core
layout(location=0) in vec4 aSphere;   // world centre, radius
layout(location=1) in vec2 aExtra;    // seed, kind (0 bubble, 1 snow)
uniform mat3 uWorldToView;
uniform mat4 uProjection;
uniform float uFocus;
uniform float uAperture;
uniform float uPixel;
uniform float uCrisp;
uniform float uNearLayer;      // 1: drawing the near layer (kind 3 only, sharp)
out vec2 vCorner;
flat out vec4 vSphere;
flat out float vBlur;
flat out vec3 vExtra;    // seed, kind, true radius / drawn radius
""" + SCENE3D_SPHERES_GLSL + """
void main() {
    vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1)) * 2.0 - 1.0;
    vec3 centre = uWorldToView * aSphere.xyz;
    float depth = -centre.z;
    // Blur in proportion to the bubble: a tiny near bubble softens without swelling into a grey disc.
    float blur = min(sceneDefocusRadius(depth, uFocus, uAperture, 0.12, 0.0), aSphere.w * 0.1);
    if (aExtra.y > 1.5 && aExtra.y < 2.5) blur = aSphere.w * 0.3;
    blur = max(blur, uPixel * depth * mix(0.7, 0.2, uCrisp));
    bool near_ = aExtra.y > 2.5;
    if (near_) blur = uPixel * depth * 0.5;                  // sharp in its layer; the lens blurs it
    if (near_ != (uNearLayer > 0.5)) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
    // At least half a pixel across so specks resolve; their light is scaled back to their true size.
    float radius = max(aSphere.w, uPixel * depth * 0.5);
    vSphere = vec4(centre, radius);
    vBlur = blur;
    vExtra = vec3(aExtra, (aSphere.w * aSphere.w) / (radius * radius));
    // Round on screen wherever it sits (a wide view draws an off-axis sphere as an oval).
    vCorner = corner;
    gl_Position = sceneSphereScreenCorner(centre, radius, blur, corner, uProjection);
}
"""
SHADE_GLSL = """
uniform sampler2D uEnvironment;
uniform sampler2D uBackground;   // what was drawn before the bubbles, covering the target allocation
uniform vec3 uSunScreen;
uniform vec2 uTargetSize;
uniform samplerCube uProbe;      // the scene all round the eye (water, light, beams, particulate)
uniform float uProbeLevels;
uniform float uEta;              // outside / inside index along the ray (an air bubble in water: 1.33)
uniform float uBehind;           // how far behind a bubble what it bends lies (view units)
uniform float uLens;             // share of the light through a bubble taken from its own bent view
uniform float uPixelSize;        // view units per pixel at unit distance
uniform mat4 uProjection;
uniform vec2 uFrameSize;
vec3 environment(vec3 dir, float blur) { return textureLod(uEnvironment, equirectUv(dir), blur).rgb; }
// What the captured frame shows at a view-space point (negative where it is off screen).
vec4 behindAt(vec3 viewPoint, float blurPx) {
    vec4 clip = uProjection * vec4(viewPoint, 1.0);
    if (clip.w <= 0.0) return vec4(0.0);
    vec2 px = (clip.xy / clip.w * 0.5 + 0.5) * uFrameSize;
    vec2 inside = min(px, uFrameSize - px);
    float trust = smoothstep(0.0, 60.0, min(inside.x, inside.y));
    if (trust <= 0.0) return vec4(0.0);
    px = clamp(px, vec2(0.5), uFrameSize - 0.5);
    if (blurPx < 0.75) return vec4(texture(uBackground, px / uTargetSize).rgb, trust);
    // A filled disc (golden spiral), each tap itself a small box (2x2 bilinear quad offset), so sparse bright specks
    // spread to a smooth haze; the same pattern at every pixel (a per-pixel spin read as speckle).
    vec3 sum = vec3(0.0);
    float tap = max(blurPx / 4.0, 0.5);
    for (int i = 0; i < 16; ++i) {
        float r = sqrt((float(i) + 0.5) / 16.0) * blurPx;
        float a = float(i) * 2.39996323;
        vec2 at = px + vec2(cos(a), sin(a)) * r;
        sum += texture(uBackground, (at + vec2(-0.5, -0.5) * tap) / uTargetSize).rgb
             + texture(uBackground, (at + vec2(0.5, 0.5) * tap) / uTargetSize).rgb;
    }
    return vec4(sum / 32.0, trust);
}
uniform float uShell;            // the glass wall's thickness, a share of the radius (0: a solid sphere)
uniform vec3 uIors;              // outside, wall, core
uniform float uRough;            // the surface's own blur (softly focused scenes)
uniform float uInnerBlur;
uniform float uShellMin;         // radius px below which a bubble is one interface
uniform int uDiag;               // 0 composed; diagnostic views otherwise
uniform vec3 uLightDir;          // world direction toward the scene's light (as seen under water)
uniform vec3 uSpecColour;        // the light's colour x strength
uniform vec3 uSpecShape;
uniform float uSpecThrough;      // share of the light seen through the lens         // core radius (rad), shoulder radius (rad), shoulder share
vec3 sceneLightLobe(vec3 dirWorld, float footprint) {
    float angle = acos(clamp(dot(normalize(dirWorld), uLightDir), -1.0, 1.0));
    float f2 = footprint * footprint;
    float core2 = uSpecShape.x * uSpecShape.x, shoulder2 = uSpecShape.y * uSpecShape.y;
    float core = core2 / (core2 + f2) * exp(-angle * angle / (core2 + f2));
    float shoulder = shoulder2 / (shoulder2 + f2) * exp(-angle * angle / (shoulder2 + f2));
    return uSpecColour * (core + uSpecShape.z * shoulder);
}
uniform float uSpeckGlow;        // light a pixel-sized bubble mirrors
uniform float uReflect;          // reflections' share (near giants: their glass dims what they mirror)
uniform float uFrameShare;       // what is seen through: the frame (1) or the probe (0)        // blur of the scene seen through a bubble, a share of its radius in pixels
// A bubble seen along one view ray (view space: the ray, the sphere's centre and radius): the ray traced exactly
// through the hollow sphere (front reflection, the glass wall with its total internal reflections, the core, the
// back), every path looked up in the scene itself (the probe; what finally comes out behind, from the captured
// frame where it lands on screen). Highlights, rims, the guided light in the wall and colour all come from what the
// scene holds.
// One shading ray through the bubble (premultiplied light, owned alpha).
vec4 shadeBubbleRay(vec3 rayView, vec4 sphere, float pixels, float soft, float blur) {
    vec3 axis = normalize(sphere.xyz);
    float along = dot(rayView, axis);
    vec3 offAxis = rayView - axis * along;
    float maxSin = (sphere.w / length(sphere.xyz)) * (1.0 - 0.6 / max(pixels, 2.0));
    float sinNow = length(offAxis);
    if (sinNow > maxSin)
        rayView = normalize(axis * sqrt(max(1.0 - maxSin * maxSin, 0.0)) + offAxis / max(sinNow, 1e-6) * maxSin);
    float tN, tF;
    sceneSphereRay(rayView, sphere.xyz, sphere.w, tN, tF);
    vec3 frontView = rayView * tN;
    // A mirror on a sphere turns the view by twice the normal's turn: one pixel spans ~2 / (radius px x facing) rad.
    float facingHere = max(dot(-rayView, normalize(frontView - sphere.xyz)), 0.15);
    float lobeFootprint = 2.0 / (max(pixels, 1.0) * facingHere) + soft * 0.6;
    vec4 paths[8];
    vec3 origin = (frontView - sphere.xyz) / sphere.w - rayView * 1e-3;
    // Under ~40 px the wall's inner surface is a sub-pixel ring that aliases into dots: draw small bubbles as a
    // single interface (the film still colours what they mirror).
    // Below ~uShellMin px the two walls fall within a couple of pixels of each other: one interface (a single thick
    // bright band, as the mocks draw small bubbles) instead of two concentric hoops.
    float shell = pixels < uShellMin ? 0.0 : max(uShell, 1.5 / max(pixels, 1.0));
    int count = sceneHollowSphereTrace(origin, rayView, 1.0, max(1.0 - shell, 0.0), uIors, paths);
    vec3 light = vec3(0.0);
    float own = 0.0;
    vec3 reflected = vec3(0.0), transmitted = vec3(0.0);
    // Soap-film interference on what the surface mirrors: thickness drifts over the bubble (gravity thins the top),
    // the hue is kept relative (it recolours reflected scene light, never adds light of its own). Per scene.
    vec3 filmHue = vec3(1.0);
    // Reflections' share: uReflect at the face, full toward the rim (a near giant's face mirrors little).
    float faceOn = clamp(dot(-rayView, normalize(frontView - sphere.xyz)), 0.0, 1.0);
    float reflectShare = mix(1.0, uReflect, pow(faceOn, 0.6));
    if (uFilm > 0.0) {
        vec3 local = (frontView - sphere.xyz) / sphere.w;
        float c = clamp(dot(-rayView, normalize(local)), 0.0, 1.0);
        float drift = skyNoise2(local.xy * 2.3 + vec2(sphere.w * 37.0, sphere.x * 11.0), 191u);
        float thickness = mix(uFilmRange.x, uFilmRange.y, clamp(0.5 - 0.4 * local.y + 0.6 * (drift - 0.5), 0.0, 1.0));
        // Hue at the true incidence; where the angle swings faster than the pixel can hold (the rim of small
        // bubbles: dc per pixel ~ 1 / (radius px * c)), toward the mean angle so the ring never speckles.
        float swing = clamp(1.5 / (max(pixels, 1.0) * max(c, 0.05)), 0.0, 1.0);
        vec3 film = sceneThinFilm(mix(c, 0.7, swing), thickness, 1.33, 1.0);
        vec3 hue = film / max(dot(film, vec3(0.3333)), 1e-3);
        hue.g = min(hue.g, 0.5 * (hue.r + hue.b) + 0.1);
        hue /= max(dot(hue, vec3(0.3333)), 1e-3);
        filmHue = mix(vec3(1.0), hue, uFilm * (1.0 - smoothstep(0.2, 0.85, c)));
    }
    for (int i = 0; i < 8; ++i) {
        if (i >= count) break;
        // Light bounced inside the wall leaves in directions that swing from pixel to pixel: read it wider.
        vec3 seen = sceneProbe(uProbe, uViewToWorld * paths[i].xyz, min(blur + 0.06 * float(i), 1.0), uProbeLevels);
        // Mirrored paths also see the light itself (later bounces inside the wall spread wider).
        // Highlights stay inset from the silhouette (operator): the mirror lobe fades toward grazing, where the rim's
        // own Fresnel band already carries the light.
        if (i < count - 1) seen = (seen + sceneLightLobe(uViewToWorld * paths[i].xyz, lobeFootprint * (1.0 + float(i)))
                                         * smoothstep(0.2, 0.5, facingHere) * smoothstep(2.5, 10.0, pixels)) * filmHue;
        if (i == count - 1) {
            // What is seen through is out of focus inside the bubble (the lens's depth): softened with its size.
            // The frame is read along the smooth lens of the bubble as a whole (refraction through a plain sphere of the
            // outer index): the traced exit through the glass wall swings chaotically near the rim (speckle). The trace
            // still sets how much light comes through.
            vec3 lensDir = sceneSphereRefraction(rayView, normalize(frontView - sphere.xyz), 1.0 / uIors.x);
            vec4 behind = behindAt(frontView + lensDir * uBehind, max(soft * pixels * 0.35, pixels * uInnerBlur));
            // Off the frame's edge the bent view falls back to the scene behind this pixel, never to the probe (its
            // scattered fill lit every bubble at the frame's edge).
            vec3 here = texture(uBackground, gl_FragCoord.xy / uTargetSize).rgb;
            // Light that went through the glass wall leaves in directions that swing from pixel to pixel: its frame
            // lookups scatter over the screen (speckle). Only the core's gently bent view reads the frame; the rest
            // reads the scene's blurred light round this pixel.
            seen = mix(mix(here, seen, 1.0 - uFrameShare), behind.rgb, behind.a * uFrameShare);
            // The light itself seen through the bubble's lens: an inset glow where the bending carries the view to it.
            // Only bubbles big enough to show a lens: on a bead the lens view spans every direction (a uniform glow).
            // The light through an air bubble (a diverging lens, water to air): it shows inset on the light's own side.
            vec3 airLens = sceneSphereRefraction(rayView, normalize(frontView - sphere.xyz), uIors.x / uIors.z);
            seen += sceneLightLobe(uViewToWorld * airLens, lobeFootprint * 1.5) * uSpecThrough
                  * smoothstep(8.0, 24.0, pixels);
            light += paths[i].w * seen * uLens;
            own += paths[i].w * uLens;
            transmitted += paths[i].w * seen * uLens;
        } else {
            light += paths[i].w * seen * reflectShare;
            own += paths[i].w * reflectShare;
            reflected += paths[i].w * seen * reflectShare;
        }
    }
    if (uDiag == 1) return vec4(reflected, 1.0);
    if (uDiag == 2) return vec4(transmitted, 1.0);
    if (uDiag == 3) return vec4(filmHue * 0.5, 1.0);
    if (uDiag == 4) return vec4(normalize(frontView - sphere.xyz) * 0.5 + 0.5, 1.0);
    return vec4(light, own);
}
// A bubble seen along one view ray (view space: the ray, the sphere's centre and radius): the ray traced exactly
// through the hollow sphere, every path looked up in the scene itself. Toward the rim, where the paths change from
// one pixel to the next (light guided round inside the wall), four rays spread over the pixel are averaged.
vec4 shadeBubble(vec3 rayView, vec4 sphere, float pixels, float soft, vec3 frontView) {
    // Each pixel sees a cone of directions as wide as the curvature it covers: read the probe at that level.
    float texelAngle = 1.5707963 / float(textureSize(uProbe, 0).x);
    float facing = max(dot(-rayView, normalize(frontView - sphere.xyz)), 0.2);
    // The footprint is anisotropic: radially it grows as 1 / facing (handled by the rim's sub-pixel rays),
    // tangentially it stays ~2 / radius px. Filtering by the radial width averaged the whole hemisphere into every
    // rim pixel (uniform hoops); the tangential width keeps the mirrored light and dark round the rim.
    float cone = 2.0 / max(pixels, 1.0) / mix(1.0, facing, 0.25);
    float footprint = log2(max(cone / texelAngle, 1.0)) / max(uProbeLevels - 1.0, 1.0);
    float blur = clamp(footprint + uRough + soft * 0.55, 0.0, 1.0);
    vec4 sum;
    // One pixel's step in view directions, analytic (derivatives after the caller's discard are undefined: they
    // came back zero and every sub-ray was the same ray).
    vec3 dx = vec3(uPixelSize, 0.0, 0.0) * -rayView.z, dy = vec3(0.0, uPixelSize, 0.0) * -rayView.z;
    if (facing > 0.8 || pixels < 3.0) {
        sum = shadeBubbleRay(rayView, sphere, pixels, soft, blur);
    } else {
        sum = vec4(0.0);
        for (int i = 0; i < 8; ++i) {
            // Eight points spread over the pixel (a rotated-grid pattern), never beyond it.
            vec2 o = vec2(fract(float(i) * 0.618034 + 0.0625), (float(i) + 0.5) / 8.0) - 0.5;
            sum += shadeBubbleRay(normalize(rayView + dx * o.x + dy * o.y), sphere, pixels, soft, blur) * 0.125;
        }
    }
    if (uDiag > 0) return vec4(sum.rgb / max(sum.a, 1e-4), 1.0);
    float alpha = clamp(sum.a, 0.0, 1.0);
    return vec4(sum.rgb / max(alpha, 1e-4), alpha);
}
"""
BUBBLE_FRAGMENT_BODY = (""
                   + SCENE3D_SPHERES_GLSL + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + SCENE3D_PROBE_GLSL + COMMON
                   + SHADE_GLSL + """
in vec2 vCorner;
flat in vec4 vSphere;
flat in float vBlur;
flat in vec3 vExtra;
void main() {
    vec3 ray = sceneSphereFacingRay(vSphere.xyz, vSphere.w + vBlur, vCorner);
    float coverage = sceneSphereCoverage(ray, vSphere.xyz, vSphere.w, vBlur);
    if (coverage <= 0.0) discard;
    float tNear, tFar;
    bool hit = sceneSphereRay(ray, vSphere.xyz, vSphere.w, tNear, tFar);
    vec3 front = hit ? ray * tNear : ray * dot(vSphere.xyz, ray);
    vec3 rayW = uViewToWorld * ray;
    float soft = clamp(vBlur / max(vSphere.w, 1e-3), 0.0, 1.0);
    float pixels = vSphere.w / (uPixelSize * max(-front.z, 0.1));
    if (vExtra.y > 1.5 && vExtra.y < 2.5) {
        // A defocused speck close to the lens: a flat disc of its light, a little brighter at its edge.
        float edge = smoothstep(0.55, 1.0, length(ray - normalize(vSphere.xyz)) / (vSphere.w / length(vSphere.xyz)));
        float h = fract(vExtra.x * 7.13);
        vec3 sceneHue = uSkyTint / max(dot(uSkyTint, vec3(0.3333)), 1e-3);
        vec3 tint = mix(sceneHue, h < 0.15 ? vec3(0.85, 0.78, 1.15) : vec3(1.0), 0.35);
        float a = coverage * (0.08 + 0.06 * edge) * (0.5 + fract(vExtra.x * 3.7));
#ifndef NEAR_LAYER
        sceneTransparent(tint * 1.3 * a, a, -front.z);
        Emission = vec4(0.0);
#endif
        return;
    }
    if (vExtra.y > 0.5 && vExtra.y < 1.5) {
        float a = coverage * 0.45 * vExtra.z * (1.0 - soft * 0.7);
        float glitter = 1.0 + uSparkle * 7.0 * step(0.86, fract(vExtra.x * 31.7));
#ifndef NEAR_LAYER
        sceneTransparent(mix(uShaftColour, vec3(0.9, 0.95, 1.0), 0.4) * 1.2 * glitter * a, a, -front.z);
        Emission = vec4(0.0);
#endif
        return;
    }
    vec4 clipC = uProjection * vec4(vSphere.xyz, 1.0);
    vec2 centrePx = (clipC.xy / clipC.w * 0.5 + 0.5) * uFrameSize;
    gl_FragDepth = sceneSphereDepth(front, uProjection);
    vec4 shaded = shadeBubble(ray, vSphere, pixels, soft, front);
    if (uDiag == 5) shaded = vec4(vec3(coverage), 1.0);
    float speck = 1.0 - smoothstep(1.0, 2.5, pixels);
    float centreness = clamp(dot(-ray, normalize(front - vSphere.xyz)), 0.0, 1.0);
    vec3 behind = texture(uBackground, gl_FragCoord.xy / uTargetSize).rgb;
    vec3 speckLight = (behind + mix(uSkyTint, uShaftColour, 0.4) * uSpeckGlow) * (0.7 + 0.6 * centreness);
    shaded = mix(shaded, vec4(speckLight, 0.3 + 0.5 * centreness), speck);
    float alpha = shaded.a * coverage * mix(mix(vExtra.z, 1.0, 0.3), max(vExtra.z, 0.55), speck);
#ifdef NEAR_LAYER
    // The circle this bubble's light spreads over at the lens, in pixels: grows as it nears the camera.
    float coc = uNearCoc * max(uFocus - (-vSphere.z), 0.0) / max(uFocus - 2.5, 0.1);
    sceneDefocusWrite(shaded.rgb * alpha * uNearGain, alpha * uNearGain, coc);
#else
    sceneTransparent(shaded.rgb * alpha, alpha, -front.z);
    vec3 emitted = max(shaded.rgb - 1.2, 0.0) * alpha * 0.6 * smoothstep(3.0, 10.0, pixels) * (1.0 - soft * 0.8);
    Emission = vec4(emitted, dot(emitted, vec3(0.2126, 0.7152, 0.0722)));
#endif
}
""")
BUBBLE_FRAGMENT = ("#version 460 core\n" + SCENE_OIT_GLSL + "layout(location=2) out vec4 Emission;\n"
                   + BUBBLE_FRAGMENT_BODY)
NEAR_FRAGMENT = ("#version 460 core\n#define NEAR_LAYER\n" + SCENE_DEFOCUS_GLSL
                 + "uniform float uNearCoc;\nuniform float uFocus;\nuniform float uNearGain;\n" + BUBBLE_FRAGMENT_BODY)

CLUSTER_VERTEX = """#version 460 core
layout(location=0) in vec4 aS0;
layout(location=1) in vec4 aS1;
layout(location=2) in vec4 aS2;
layout(location=3) in vec4 aInfo;     // count, blend, seed, unused
uniform mat3 uWorldToView;
uniform mat4 uProjection;
out vec3 vView;
flat out vec4 vSpheres[3];
flat out vec4 vBound;
flat out vec4 vInfo;
""" + SCENE3D_SPHERES_GLSL + """
void main() {
    vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1)) * 2.0 - 1.0;
    vec4 world[3] = vec4[3](aS0, aS1, aS2);
    int count = int(aInfo.x);
    vec3 centre = vec3(0.0);
    for (int i = 0; i < 3; ++i) if (i < count) centre += world[i].xyz;
    centre /= float(count);
    float bound = 0.0;
    for (int i = 0; i < 3; ++i) {
        vSpheres[i] = vec4(uWorldToView * world[i].xyz, world[i].w);
        if (i < count) bound = max(bound, distance(centre, world[i].xyz) + world[i].w);
    }
    vBound = vec4(uWorldToView * centre, bound + aInfo.y);
    vInfo = aInfo;
    vView = sceneSphereCorner(vBound.xyz, vBound.w, 0.0, corner);
    gl_Position = uProjection * vec4(vView, 1.0);
}
"""
CLUSTER_FRAGMENT = ("#version 460 core\n" + SCENE_OIT_GLSL + "layout(location=2) out vec4 Emission;\n"
                    + SCENE3D_SPHERES_GLSL + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + SCENE3D_PROBE_GLSL + COMMON
                    + SHADE_GLSL + """
in vec3 vView;
flat in vec4 vSpheres[3];
flat in vec4 vBound;
flat in vec4 vInfo;
void main() {
    vec3 ray = normalize(vView);
    float tNear, tFar, t, closest;
    vec3 normal;
    if (!sceneSphereRay(ray, vBound.xyz, vBound.w, tNear, tFar)) discard;
    vec4 s[4] = vec4[4](vSpheres[0], vSpheres[1], vSpheres[2], vec4(0.0));
    bool hit = sceneClusterRay(ray, s, int(vInfo.x), vInfo.y, tNear, tFar, t, normal, closest);
    // Antialias the joined silhouette from how closely the ray passed.
    float pixelAngle = uPixelSize;
    float coverage = hit ? 1.0 : clamp(0.5 - closest / pixelAngle, 0.0, 1.0);
    if (coverage <= 0.0) discard;
    if (!hit) {
        t = dot(vBound.xyz, ray);
        float d = sceneClusterDistance(ray * t, s, int(vInfo.x), vInfo.y);
        normal = normalize(ray * t - vBound.xyz);
    }
    vec3 point = ray * t;
    float pixels = vBound.w / (uPixelSize * max(-point.z, 0.1));
    vec4 clipC = uProjection * vec4(vBound.xyz, 1.0);
    vec2 centrePx = (clipC.xy / clipC.w * 0.5 + 0.5) * uFrameSize;
    // The union surface carries the trace: a sphere tangent at this point along the union's own normal, its radius
    // that of the nearest member (curvature continues smoothly through the neck).
    float r = s[0].w;
    float nearest = 1e9;
    for (int i = 0; i < 3; ++i) {
        if (i >= int(vInfo.x)) break;
        float gap = abs(distance(point, s[i].xyz) - s[i].w);
        if (gap < nearest) { nearest = gap; r = s[i].w; }
    }
    vec4 tangent = vec4(point - normal * r, r);
    float localPixels = r / (uPixelSize * max(-point.z, 0.1));
    vec4 shaded = shadeBubble(ray, tangent, localPixels, 0.0, point);
    if (uDiag == 5) shaded = vec4(vec3(coverage), 1.0);
    gl_FragDepth = sceneSphereDepth(point, uProjection);
    float alpha = shaded.a * coverage;
    sceneTransparent(shaded.rgb * alpha, alpha, -point.z);
    vec3 emitted = max(shaded.rgb - 1.2, 0.0) * alpha * 0.6;
    Emission = vec4(emitted, dot(emitted, vec3(0.2126, 0.7152, 0.0722)));
}
""")
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
PARTICLE_VERTEX = """#version 460 core
layout(location=0) in vec4 aPoint;   // world position (eye at the origin), world radius
layout(location=1) in vec4 aLook;    // brightness, warm (lit in the light's colour) or neutral, seed, unused
uniform mat3 uWorldToView;
uniform bool uRowMajor;
uniform mat4 uProjection;
uniform float uPixel;                // view units per pixel at unit distance
uniform vec3 uSunBelow;
uniform vec3 uLightColour;
uniform vec3 uSpeckWarm;
uniform vec3 uWater;
uniform float uSpecks;
out vec2 vCorner;
flat out vec3 vColour;
void main() {
    vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1)) * 2.0 - 1.0;
    mat3 toView = uRowMajor ? transpose(uWorldToView) : uWorldToView;
    vec3 c = toView * aPoint.xyz;
    float depth = -c.z;
    float drawn = max(aPoint.w, uPixel * depth * 0.75);
    float energy = min((aPoint.w * aPoint.w) / (drawn * drawn), 1.0);
    float phase = 0.3 + 2.2 * pow(max(dot(normalize(aPoint.xyz), uSunBelow), 0.0), 4.0);
    vec3 tint = aLook.y > 0.5 ? uSpeckWarm : mix(uWater * 6.0, vec3(0.75, 0.82, 0.86), 0.5);
    vColour = tint * aLook.x * phase * energy * uSpecks;
    vCorner = corner;
    gl_Position = depth > 0.05 ? uProjection * vec4(c + vec3(corner * drawn * 2.0, 0.0), 1.0) : vec4(2.0, 2.0, 2.0, 1.0);
}
"""
PARTICLE_FRAGMENT = """#version 460 core
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
in vec2 vCorner;
flat in vec3 vColour;
void main() {
    float g = exp(-dot(vCorner, vCorner) * 8.0);
    FragColor = vec4(vColour * g * 2.6, 0.0);
    vec3 glow = max(vColour * g - 1.0, 0.0) * 0.3;
    Emission = vec4(glow, dot(glow, vec3(0.2126, 0.7152, 0.0722)));
}
"""


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
     near_program, shaft_tex, shaft_fbo) = programs
    settings = {**settings, **OVERRIDES}
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
        gl.glUseProgram(program)
        u = lambda name: gl.glGetUniformLocation(program, name)
        gl.glUniformMatrix3fv(u("uViewToWorld"), 1, gl.GL_FALSE, view_to_world)
        gl.glUniform2f(u("uTan"), *tan)
        gl.glUniform1f(u("uTime"), 4.0)
        gl.glUniform3f(u("uSun"), *sun)
        gl.glUniform3f(u("uSunBelow"), *sun_below)
        exposure = settings["exposure"]
        gl.glUniform1f(u("uWisps"), settings.get("wisps", 0.0))
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
        gl.glUniform1f(u("uLens"), settings.get("near_lens", 0.5) if program == near_program else settings.get("lens", 0.85))
        gl.glUniform1f(u("uShell"), settings.get("shell", 0.1))
        gl.glUniform3f(u("uIors"), *settings.get("iors", (1.33, 1.5, 1.0)))
        gl.glUniform1f(u("uNearCoc"), settings.get("near_coc", 22.0))
        gl.glUniform1f(u("uReflect"), settings.get("near_reflect", 0.15) if program == near_program else 1.0)
        gl.glUniform1f(u("uNearGain"), settings.get("near_gain", 0.5))
        gl.glUniform1f(u("uRough"), settings.get("rough", 0.0))
        gl.glUniform1f(u("uShellMin"), settings.get("shell_min", 0.0))
        gl.glUniform1i(u("uDiag"), DIAG)
        spec_uniforms(u)
        gl.glUniform1f(u("uSpeckGlow"), settings.get("speck_glow", 0.6))
        gl.glUniform1f(u("uInnerBlur"), settings.get("inner_blur", 0.25))
        gl.glUniform1f(u("uFrameShare"), settings.get("frame_share", 1.0))
        gl.glUniform1f(u("uNearLayer"), 1.0 if program == near_program else 0.0)
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
                    common(shell)
                    u = lambda name: gl.glGetUniformLocation(shell, name)
                    gl.glUniformMatrix3fv(u("uWorldToView"), 1, gl.GL_FALSE, world_to_view)
                    gl.glUniformMatrix4fv(u("uProjection"), 1, gl.GL_FALSE, projection)
                    gl.glUniform1f(u("uFocus"), settings.get("focus", 4.2))
                    gl.glUniform1f(u("uAperture"), settings.get("aperture", 3.0))
                    gl.glUniform1f(u("uPixel"), 2.0 * tan_y / H)
                    gl.glUniform1f(u("uPixelSize"), 2.0 * tan_y / H)
                    gl.glActiveTexture(gl.GL_TEXTURE3)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, env)
                    gl.glUniform1i(u("uEnvironment"), 3)
                    gl.glActiveTexture(gl.GL_TEXTURE5)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, background_tex)
                    gl.glActiveTexture(gl.GL_TEXTURE0)
                    for name in ("uBackground",):
                        gl.glUniform1i(u(name), 5)
                    gl.glUniform2f(u("uTargetSize"), *target.allocation[:2])
                    gl.glUniform2f(u("uFrameSize"), W, H)
                    gl.glUniform3f(u("uSunScreen"), *sun_screen)
                    gl.glActiveTexture(gl.GL_TEXTURE6)
                    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, PROBE.texture)
                    gl.glActiveTexture(gl.GL_TEXTURE0)
                    for program in (shell, merged):
                        gl.glUseProgram(program)
                        v = lambda name: gl.glGetUniformLocation(program, name)
                        gl.glUniform1i(v("uProbe"), 6)
                        gl.glUniform1f(v("uProbeLevels"), PROBE.levels)
                        gl.glUniform1f(v("uEta"), settings.get("eta", 1.33))
                        gl.glUniform1f(v("uBehind"), settings.get("behind", 8.0))
                        gl.glUniform1f(v("uLens"), settings.get("lens", 0.85))
                        gl.glUniform1f(v("uShell"), settings.get("shell", 0.1))
                        gl.glUniform3f(v("uIors"), *settings.get("iors", (1.33, 1.5, 1.0)))
                        gl.glUniform1f(v("uRough"), settings.get("rough", 0.0))
                        gl.glUniform1f(v("uShellMin"), settings.get("shell_min", 0.0))
                        gl.glUniform1i(v("uDiag"), DIAG)
                        spec_uniforms(v)
                        gl.glUniform1f(v("uInnerBlur"), settings.get("inner_blur", 0.25))
                        gl.glUniform1f(v("uReflect"), 1.0)
                        gl.glUniform1f(v("uSpeckGlow"), settings.get("speck_glow", 0.6))
                        gl.glUniform1f(v("uFrameShare"), settings.get("frame_share", 1.0))
                    gl.glUseProgram(shell)
                    gl.glBindVertexArray(vao)
                    if not BACKDROP_ONLY:
                        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, len(items))
                    mark("shells")
                    common(merged)
                    m = lambda name: gl.glGetUniformLocation(merged, name)
                    gl.glUniform1i(m("uProbe"), 6)
                    gl.glUniform1f(m("uProbeLevels"), PROBE.levels)
                    gl.glUniform1f(m("uEta"), settings.get("eta", 1.33))
                    gl.glUniform1f(m("uBehind"), settings.get("behind", 8.0))
                    gl.glUniform1f(m("uLens"), settings.get("lens", 0.85))
                    gl.glUniform1f(m("uShell"), settings.get("shell", 0.1))
                    gl.glUniform3f(m("uIors"), *settings.get("iors", (1.33, 1.5, 1.0)))
                    gl.glUniform1f(m("uRough"), settings.get("rough", 0.0))
                    gl.glUniform1f(m("uShellMin"), settings.get("shell_min", 0.0))
                    gl.glUniform1i(m("uDiag"), DIAG)
                    spec_uniforms(m)
                    gl.glUniform1f(m("uInnerBlur"), settings.get("inner_blur", 0.25))
                    gl.glUniform1f(m("uReflect"), 1.0)
                    gl.glUniform1f(m("uSpeckGlow"), settings.get("speck_glow", 0.6))
                    gl.glUniform1f(m("uFrameShare"), settings.get("frame_share", 1.0))
                    gl.glUniformMatrix3fv(m("uWorldToView"), 1, gl.GL_FALSE, world_to_view)
                    gl.glUniformMatrix4fv(m("uProjection"), 1, gl.GL_FALSE, projection)
                    gl.glUniform1f(m("uPixelSize"), 2.0 * tan_y / H)
                    gl.glUniform1i(m("uEnvironment"), 3)
                    gl.glUniform1i(m("uBackground"), 5)
                    gl.glUniform2f(m("uTargetSize"), *target.allocation[:2])
                    gl.glUniform2f(m("uFrameSize"), W, H)
                    gl.glUniform3f(m("uSunScreen"), *sun_screen)
                    gl.glBindVertexArray(cvao)
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, len(clusters))
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
                    NEAR.end()
                    NEAR.composite(settings.get("near_coc", 22.0) * 1.6)
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
                compile_program(BUBBLE_VERTEX, NEAR_FRAGMENT, label="lab near layer"))
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
            mock_full = Image.open(ROOT / "tmp/Bubbleexamples" / f"{name}.png").convert("RGB").resize((W, H), Image.LANCZOS)
            for label, box in CARD_SETS[CARD]["crops"].items():
                a, b = mock_full.crop(box), image.crop(box)
                pair = Image.new("RGB", (a.width * 2 + 6, a.height))
                pair.paste(a, (0, 0))
                pair.paste(b, (a.width + 6, 0))
                pair.save(sys.argv[1].replace(".png", f"_card_{label}.png"))
        mock = Image.open(ROOT / "tmp/Bubbleexamples" / f"{name}.png").convert("RGB").resize(half, Image.LANCZOS)
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
