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
from rendering.gl_programs.scene3d_spheres import SCENE3D_SPHERES_GLSL
from rendering.gl_programs.scene3d_water import SCENE3D_WATER_GLSL, water_sun_below
from rendering.quick.render.gl_resources import compile_program
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.target import SCENE_OIT_GLSL, SceneTarget
from tools.transition_contact_sheet import TransitionCapture

W, H = 1672, 941
BACKDROP_ONLY = "--backdrop" in sys.argv
# --card: mock 2's own bubbles at its measured positions and pixel sizes (x, y from the top-left, radius, depth), so
# crops compare one to one; the doublet is joined as the mock shows it.
CARD = "--card" in sys.argv
CARD_BUBBLES = ((705, 617, 42, 9.0), (395, 713, 38, 9.0), (627, 812, 37, 9.0), (230, 407, 35, 9.0),
                (167, 330, 17, 12.0), (477, 593, 17, 12.0), (547, 707, 15, 12.0), (513, 527, 13, 12.0),
                (170, 790, 190, 3.2), (40, 347, 95, 3.6))
CARD_DOUBLET = ((541, 363, 88, 9.0), (632, 432, 37, 9.0))
CARD_CROPS = {"doublet": (400, 250, 720, 500), "giant": (0, 560, 450, 941), "mids": (330, 540, 780, 860)}
ENV_W, ENV_H = 1024, 512
SURFACE_Y = 9.0

# Per mock: water palette, sun, camera pitch.
VARIANTS = {
    "ExBubble1": dict(deep=(0.05, 0.08, 0.12), water=(0.2, 0.25, 0.32), sky=(0.85, 0.9, 0.95), shaft=(0.62, 0.67, 0.74),
                      sun=(0.05, 0.75, -1.0), pitch=24.0, exposure=1.15, absorb=(0.06, 0.042, 0.032)),
    "ExBubble2": dict(deep=(0.008, 0.03, 0.075), water=(0.03, 0.085, 0.18), sky=(0.6, 0.76, 0.95), shaft=(0.36, 0.55, 0.85),
                      sun=(0.0, 0.7, -1.0), pitch=24.0, exposure=0.9, absorb=(0.08, 0.05, 0.035), rays=0.7),
    "ExBubble3": dict(deep=(0.006, 0.012, 0.022), water=(0.025, 0.037, 0.055), sky=(0.6, 0.68, 0.78), shaft=(0.45, 0.5, 0.58),
                      sun=(0.0, 0.8, -1.0), pitch=26.0, exposure=0.82, absorb=(0.09, 0.06, 0.045)),
    "ExBubble4": dict(deep=(0.02, 0.06, 0.12), water=(0.05, 0.12, 0.2), sky=(0.48, 0.66, 0.84), shaft=(0.4, 0.58, 0.8),
                      sun=(0.15, 0.65, -1.0), pitch=20.0, exposure=1.05, absorb=(0.1, 0.05, 0.03), drift=0.12,
                      wakes=1.0, mist=0.3, aperture=1.2),
    "ExBubble5CameraAbyss": dict(deep=(0.004, 0.02, 0.05), water=(0.01, 0.06, 0.14), sky=(0.3, 0.6, 1.0),
                                 shaft=(0.25, 0.5, 0.95), sun=(0.6, 0.6, -1.0), pitch=6.0, exposure=1.0, wisps=0.0, mist=1.0, wakes=0.6, focus=3.2, sparkle=1.0,
                                 surface=60.0, absorb=(0.1, 0.05, 0.03), drift=0.6,
                                 shaft_y=16.0, glow=1.8, rays=0.6, aperture=0.6),
    "ExBubble5Cameradown": dict(deep=(0.01, 0.05, 0.13), water=(0.03, 0.09, 0.17), sky=(0.5, 0.7, 0.9),
                                shaft=(0.3, 0.55, 0.85), sun=(0.3, 0.8, -1.0), pitch=-32.0, exposure=1.0, wisps=0.0, mist=0.6, wakes=0.8, sparkle=0.7,
                                surface=30.0, absorb=(0.1, 0.05, 0.03), drift=0.15,
                                shaft_y=12.0),
}

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
uniform float uSparkle;
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
        vec3 light = uSkyTint * (0.28 + 0.3 * out_.y) + white * (pow(s, 6.0) * 0.45 + pow(s, 40.0) * 1.4)
                   + vec3(pow(s, 900.0) * 40.0);
        surface = mix(medium, light, transmission * smoothstep(0.0, 0.25, out_.y));
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
BACKDROP_FRAGMENT = ("#version 460 core\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\n"
                     "in vec2 vNdc;\nuniform sampler2D uShafts;\nuniform vec2 uFrameSize;\n" + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + COMMON + """
void main() {
    vec3 ray = uViewToWorld * normalize(vec3(vNdc * uTan, -1.0));
    float shafts = texture(uShafts, gl_FragCoord.xy / uFrameSize).r * uRays;
    vec3 colour = basinWater(ray, 1.0, shafts);
    if (uMist > 0.0) {
        float haze = pow(1.0 - abs(ray.y), 3.0);
        float drift = skyFbm2(vec2(atan(ray.x, -ray.z) * 2.5, ray.y * 3.0) + vec2(uTime * 0.01, 0.0), 3, 61u);
        vec3 mistColour = mix(uWater, uShaftColour * 0.35, 0.4);
        colour += mistColour * uMist * haze * (0.35 + 0.9 * drift);
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
    FragColor = vec4(colour, 1.0);
    vec3 glow = max(colour - 1.1, 0.0) * 0.4;
    Emission = vec4(glow, dot(glow, vec3(0.2126, 0.7152, 0.0722)));
}
""")

# Volumetric shafts at half resolution, jittered, then blurred: smooth beams without per-pixel grain.
SHAFT_FRAGMENT = "#version 460 core\nout vec4 FragColor;\nin vec2 vNdc;\n" + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + COMMON + """
void main() {
    vec3 ray = uViewToWorld * normalize(vec3(vNdc * uTan, -1.0));
    float jitter = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
    float toward = pow(max(dot(ray, uSunBelow), 0.0), 2.0);
    FragColor = vec4(waterShafts(vec3(0.0), ray, 45.0, uSunBelow, uShaftY, uTime, 56, jitter) * 0.13 * (0.25 + toward));
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
out vec3 vView;
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
    if (aExtra.y > 1.5) blur = aSphere.w * 0.3;
    blur = max(blur, uPixel * depth * 0.7);
    // At least half a pixel across so specks resolve; their light is scaled back to their true size.
    float radius = max(aSphere.w, uPixel * depth * 0.5);
    vSphere = vec4(centre, radius);
    vBlur = blur;
    vExtra = vec3(aExtra, (aSphere.w * aSphere.w) / (radius * radius));
    vView = sceneSphereCorner(centre, radius, blur, corner);
    gl_Position = uProjection * vec4(vView, 1.0);
}
"""
SHADE_GLSL = """
uniform sampler2D uEnvironment;
uniform sampler2D uBackground;   // what was drawn before the bubbles, covering the target allocation
uniform vec3 uSunScreen;         // the light's pixel position, z 1 when it is in front of the eye
uniform vec2 uTargetSize;
// The scene behind seen through an air lens centred at centrePx: turned over and shrunk toward the centre.
vec3 behindLens(vec2 centrePx, float strength) {
    vec2 offset = gl_FragCoord.xy - centrePx;
    return texture(uBackground, (centrePx - offset * strength) / uTargetSize).rgb;
}
uniform float uPixelSize;    // view units per pixel at unit distance
vec3 environment(vec3 dir, float blur) { return textureLod(uEnvironment, equirectUv(dir), blur).rgb; }
// A bubble at one point of its silhouette (world view ray rayW, world front normal n, radius in pixels, defocus soft,
// seed, centre in pixels), as the mocks draw one: layers composited front to back over what is seen through it.
//  1 interior: the scene behind, through the air lens (blurred when the bubble itself is out of focus);
//  2 the glass wall: a band inside the silhouette, lighter than the water, carrying the reflected scene;
//  3 the rim: a crisp line at the silhouette, brightest toward the light;
//  4 highlights: a soft oblong with a hot core inset toward the light (front wall) and a fainter one opposite (back
//    wall), never touching the edge;
// coloured by the scene (its water, sky and beam colours and the reflected world), the soap film only in patches.
vec4 shadeBubble(vec3 rayW, vec3 n, float pixels, float soft, float seed, vec2 centrePx) {
    float c = clamp(dot(-rayW, n), 0.0, 1.0);
    float rel = sqrt(max(1.0 - c * c, 0.0));                       // 0 at the centre, 1 at the silhouette
    float fromEdge = (1.0 - rel) * pixels;
    float big = smoothstep(4.0, 30.0, pixels);
    float blurPx = soft * pixels;
    float defocused = smoothstep(0.02, 0.08, soft) * smoothstep(60.0, 200.0, pixels);
    vec2 toward = uSunScreen.z > 0.5 ? uSunScreen.xy - centrePx : (transpose(uViewToWorld) * uSunBelow).xy;
    toward = normalize(toward + vec2(0.0, 1e-3));
    vec2 q = (gl_FragCoord.xy - centrePx) / max(pixels, 1.0);
    float side = dot(normalize(q + vec2(1e-4, 0.0)), toward);      // 1 toward the light, -1 away
    float lit = side * 0.5 + 0.5;
    vec3 sceneLight = mix(uSkyTint, uShaftColour, 0.4);
    vec3 sceneHue = sceneLight / max(dot(sceneLight, vec3(0.3333)), 1e-3);
    vec3 sunColour = mix(uSkyTint, vec3(1.0), 0.85);

    vec3 through = behindLens(centrePx, 0.55);
    // The light a bubble adds is relative to the water behind it: bright water keeps bubbles clear, dark water lets
    // them glow (an absolute amount blew bubbles out to white in bright scenes).
    float adapt = 1.25 / (1.0 + 3.0 * dot(through, vec3(0.3333)));
    sceneLight *= adapt;
    sunColour *= mix(1.0, adapt, 0.5);
    if (defocused > 0.0) {
        vec3 blurred = vec3(0.0);
        for (int i = 0; i < 8; ++i) {
            float a = float(i) * 0.785398 + 0.3;
            blurred += texture(uBackground, (gl_FragCoord.xy + vec2(cos(a), sin(a)) * pixels * 0.12) / uTargetSize).rgb;
        }
        through = mix(through, blurred * 0.125 * 0.8 + environment(rayW, 4.0) * 0.2, defocused);
    }
    vec3 mirrored = environment(reflect(rayW, n), soft * 4.5 + (1.0 - big) * 1.5 + 2.0) * adapt;
    float swirl = skyFbm3(n * 2.1 + vec3(seed * 17.0, seed * 5.0, uTime * 0.06), 3, 7u);
    vec3 film = sceneThinFilm(c, mix(200.0, 520.0, swirl), 1.33, 1.0);
    vec3 hue = film / max(dot(film, vec3(0.3333)), 1e-3);
    hue.g = min(hue.g, 0.5 * (hue.r + hue.b) + 0.05);
    hue /= max(dot(hue, vec3(0.3333)), 1e-3);
    float filmAmount = smoothstep(0.35, 0.7, swirl) * (1.0 - abs(side) * 0.6) * 0.95 * (1.0 - defocused);
    vec3 filmTint = mix(vec3(1.0), hue, filmAmount);

    // 1 interior
    // Seen through, the mocks' bubbles act as lenses that turn the scene over: the bright water overhead focused into
    // the lower half, the deep above; glass-like, stronger than a physical air bubble.
    vec3 lensEnv = environment(sceneSphereRefraction(rayW, n, 1.0 / 1.45), soft * 4.5 + (1.0 - big) * 1.0 + 3.5);
    vec3 lensed = through * clamp(pow(lensEnv / max(environment(rayW, 6.0), vec3(1e-3)), vec3(1.2)), 0.85, 2.5);
    through = mix(through, lensed, 0.25 * big * (1.0 - defocused));
    vec3 interior = through + sceneLight * (0.1 * big + 0.08 * defocused) + mirrored * 0.05 * big;
    vec3 premultiplied = interior * mix(0.06, 0.28, big);
    float alpha = mix(0.06, 0.28, big);
    float opaque = 0.7 * defocused * clamp(adapt, 0.35, 1.0);
    premultiplied = interior * opaque + premultiplied * (1.0 - opaque);
    alpha = opaque + alpha * (1.0 - opaque);
    // 2 the glass wall
    float band = smoothstep(0.7, 0.92, rel) * big * (1.0 - 0.6 * defocused);
    vec3 wall = (through * 1.2 + mirrored * 0.35 + sceneLight * 0.3) * (0.75 + 0.55 * lit) * filmTint;
    float wallA = band * 0.6;
    wall += max(hue - 0.75, 0.0) * dot(sceneLight, vec3(0.3333)) * 0.5 * filmAmount;
    premultiplied = wall * wallA + premultiplied * (1.0 - wallA);
    alpha = wallA + alpha * (1.0 - wallA);
    // 3 the rim
    float rim = exp(-fromEdge / (1.6 + blurPx)) * (1.6 + 0.3 * blurPx) / (1.6 + blurPx);
    vec3 rimLight = mix(wall, vec3(dot(wall, vec3(0.3333))), 0.35) * 1.15 + sunColour * 0.7 * lit * lit
                  + sceneLight * 0.45 * smoothstep(1.0, 1.25, adapt);
    float rimA = rim * 0.85;
    premultiplied = rimLight * rimA + premultiplied * (1.0 - rimA);
    alpha = rimA + alpha * (1.0 - rimA);
    // 3b fragments
    float lensSide = smoothstep(0.2, -0.7, side);
    for (int layer = 0; layer < 2; ++layer) {
        float cells = layer == 0 ? 2.2 : 3.6;
        vec2 local = q * cells + vec2(seed * 41.0 + float(layer) * 7.7, seed * 23.0);
        vec2 cell = floor(local);
        float h = sceneRandom(uint(int(cell.x) + 4096) * 0x8da6b343u ^ uint(int(cell.y) + 4096) * 0xd8163841u,
                              11u + uint(layer), uint(seed * 977.0));
        vec2 centre = vec2(fract(h * 57.3), fract(h * 91.1)) * 0.3 + 0.35;
        float size = mix(0.2, 0.36, fract(h * 113.7));
        float chance = clamp(0.05 + 0.45 * band + 0.3 * lensSide * (1.0 - band), 0.0, 0.7);
        float piece = smoothstep(size, size * 0.05, distance(fract(local), centre)) * step(1.0 - chance, h)
                    * mix(0.25, 1.0, fract(h * 37.7)) * smoothstep(0.98, 0.9, rel);
        vec3 pieceColour = mix(mix(sceneLight, sunColour, 0.55) * 1.4, hue * sceneLight * 1.6, step(0.75, fract(h * 19.3)) * 0.8);
        premultiplied += pieceColour * piece * big * (1.0 - defocused) * (layer == 0 ? 0.8 : 0.55);
        alpha = clamp(alpha + piece * 0.3 * big * (1.0 - defocused), 0.0, 1.0);
    }
    // 4 highlights
    vec2 atFront = q - toward * 0.62;
    vec2 atBack = q + toward * 0.68;
    float hiFront = exp(-dot(atFront, atFront) / pow(0.2 + 0.1 * defocused, 2.0));
    float coreFront = exp(-dot(atFront, atFront) / 0.012) * (1.0 - 0.6 * defocused);
    float hiBack = exp(-dot(atBack, atBack) / 0.02);
    float coreBack = exp(-dot(atBack, atBack) / 0.005) * (1.0 - 0.6 * defocused);
    float highlight = (hiFront * 0.9 * min(adapt, 1.0) + coreFront * 0.8 + hiBack * 0.45 * min(adapt, 1.0) + coreBack * 0.4)
                    * smoothstep(3.0, 10.0, pixels);
    // The wall mirrors the busy water around it: soft bright spots of reflected light and bubbles, some film-coloured.
    for (int i = 0; i < 10; ++i) {
        float h = fract(seed * (17.31 + float(i) * 3.17) + float(i) * 0.137);
        float h2 = fract(h * 91.7 + 0.31);
        vec2 dir = vec2(cos(h * 6.2832), sin(h * 6.2832));
        vec2 at = q - dir * mix(0.7, 0.9, h2);
        float along = dot(at, vec2(-dir.y, dir.x)), across = dot(at, dir);
        float spread = mix(0.08, 0.3, fract(h2 * 7.3));
        float spot = exp(-along * along / (spread * spread) - across * across / mix(0.004, 0.012, fract(h * 5.9)))
                   * mix(0.35, 1.2, fract(h * 13.1));
        vec3 silver = mix(sceneLight, sunColour, 0.6) * 1.5;
        vec3 spotColour = mix(silver, hue * silver, step(0.55, h2) * 0.75);
        premultiplied += spotColour * spot * big * (1.0 - defocused) * (0.6 + 0.7 * lit);
        alpha = clamp(alpha + spot * 0.25 * big * (1.0 - defocused), 0.0, 1.0);
    }
    premultiplied += sunColour * highlight * 1.2;
    alpha = clamp(alpha + highlight * 0.3, 0.0, 1.0);
    // Out of focus near the lens: a few large soft bokeh blobs, gathered on the side away from the light.
    if (defocused > 0.0) {
        vec2 local = q * 1.6 + vec2(seed * 31.0, seed * 17.0);
        vec2 cell = floor(local);
        float h = sceneRandom(uint(int(cell.x) + 4096) * 0x8da6b343u ^ uint(int(cell.y) + 4096) * 0xd8163841u, 3u,
                              uint(seed * 977.0));
        vec2 centre = vec2(fract(h * 57.3), fract(h * 91.1)) * 0.36 + 0.32;
        float size = mix(0.18, 0.3, fract(h * 113.7));
        float chance = 0.35 + 0.4 * smoothstep(0.3, -0.6, side);
        float blob = smoothstep(size, size * 0.25, distance(fract(local), centre)) * step(1.0 - chance, h)
                   * mix(0.4, 1.0, fract(h * 37.7));
        premultiplied += mix(sceneLight, sunColour, 0.5) * blob * 0.8 * defocused;
        alpha = clamp(alpha + blob * 0.25 * defocused, 0.0, 1.0);
    }
    return vec4(premultiplied / max(alpha, 1e-3), alpha);
}
"""
BUBBLE_FRAGMENT = ("#version 460 core\n" + SCENE_OIT_GLSL + "layout(location=2) out vec4 Emission;\n"
                   + SCENE3D_SPHERES_GLSL + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + COMMON + SHADE_GLSL + """
in vec3 vView;
flat in vec4 vSphere;
flat in float vBlur;
flat in vec3 vExtra;
uniform mat4 uProjection;
uniform vec2 uFrameSize;
void main() {
    vec3 ray = normalize(vView);
    float coverage = sceneSphereCoverage(ray, vSphere.xyz, vSphere.w, vBlur);
    if (coverage <= 0.0) discard;
    float tNear, tFar;
    bool hit = sceneSphereRay(ray, vSphere.xyz, vSphere.w, tNear, tFar);
    vec3 front = hit ? ray * tNear : ray * dot(vSphere.xyz, ray);
    vec3 rayW = uViewToWorld * ray;
    float soft = clamp(vBlur / max(vSphere.w, 1e-3), 0.0, 1.0);
    float pixels = vSphere.w / (uPixelSize * max(-front.z, 0.1));
    if (vExtra.y > 1.5) {
        // A defocused speck close to the lens: a flat disc of its light, a little brighter at its edge.
        float edge = smoothstep(0.55, 1.0, length(ray - normalize(vSphere.xyz)) / (vSphere.w / length(vSphere.xyz)));
        float h = fract(vExtra.x * 7.13);
        vec3 sceneHue = uSkyTint / max(dot(uSkyTint, vec3(0.3333)), 1e-3);
        vec3 tint = mix(sceneHue, h < 0.15 ? vec3(0.85, 0.78, 1.15) : vec3(1.0), 0.35);
        float a = coverage * (0.08 + 0.06 * edge) * (0.5 + fract(vExtra.x * 3.7));
        sceneTransparent(tint * 1.3 * a, a, -front.z);
        Emission = vec4(0.0);
        return;
    }
    if (vExtra.y > 0.5) {
        float a = coverage * 0.45 * vExtra.z * (1.0 - soft * 0.7);
        float glitter = 1.0 + uSparkle * 7.0 * step(0.86, fract(vExtra.x * 31.7));
        sceneTransparent(mix(uShaftColour, vec3(0.9, 0.95, 1.0), 0.4) * 1.2 * glitter * a, a, -front.z);
        Emission = vec4(0.0);
        return;
    }
    vec4 clipC = uProjection * vec4(vSphere.xyz, 1.0);
    vec2 centrePx = (clipC.xy / clipC.w * 0.5 + 0.5) * uFrameSize;
    vec4 shaded = shadeBubble(rayW, uViewToWorld * normalize(front - vSphere.xyz), pixels, soft, vExtra.x, centrePx);
    float speck = 1.0 - smoothstep(1.5, 4.5, pixels);
    float centreness = clamp(dot(-ray, normalize(front - vSphere.xyz)), 0.0, 1.0);
    vec3 behind = texture(uBackground, gl_FragCoord.xy / uTargetSize).rgb;
    vec3 speckLight = (behind * 1.4 + mix(uSkyTint, uShaftColour, 0.4) * 0.35 / (1.0 + 3.0 * dot(behind, vec3(0.3333))))
                    * (0.7 + 0.6 * centreness);
    shaded = mix(shaded, vec4(speckLight, 0.22 + 0.4 * centreness), speck);
    float alpha = shaded.a * coverage * mix(mix(vExtra.z, 1.0, 0.3), max(vExtra.z, 0.55), speck);
    sceneTransparent(shaded.rgb * alpha, alpha, -front.z);
    vec3 emitted = max(shaded.rgb - 1.2, 0.0) * alpha * 0.6 * smoothstep(3.0, 10.0, pixels) * (1.0 - soft * 0.8);
    Emission = vec4(emitted, dot(emitted, vec3(0.2126, 0.7152, 0.0722)));
}
""")

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
                    + SCENE3D_SPHERES_GLSL + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + COMMON + SHADE_GLSL + """
uniform mat4 uProjection;
uniform vec2 uFrameSize;
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
    vec4 shaded = shadeBubble(uViewToWorld * ray, uViewToWorld * normal, pixels, 0.0, vInfo.z, centrePx);
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
const int SEGMENTS = 40;
out vec2 vAcross;                     // across the sheet (-1..1), along it (0 at the bubble .. 1)
out float vFold;
out float vDepth;
flat out float vStrength;
flat out float vShapeSeed;
vec3 ribbonPath(float s) {
    float length_ = aShape.y, r = aStart.w, seed = aShape.x;
    vec3 p = aStart.xyz + vec3(0.0, -length_ * s, 0.0);
    p.x += aShape.z * length_ * s * s + sin(s * 2.2 + seed * 6.28) * r * 2.5 * s;
    p.z += cos(s * 1.9 + seed * 4.1) * r * 1.5 * s;
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
    float turn = 0.35 + 0.65 * cos(s * 3.5 + aShape.x * 6.28);
    float width = aStart.w * mix(0.6, 0.9, s) * mix(1.0, 0.5, s * s);
    vAcross = vec2(sideSign, s);
    vFold = turn;
    vDepth = -here.z;
    vStrength = aShape.w;
    vShapeSeed = aShape.x;
    gl_Position = uProjection * vec4(here + across * sideSign * width * turn, 1.0);
}
"""
RIBBON_FRAGMENT = ("#version 460 core\n" + SCENE_OIT_GLSL + "layout(location=2) out vec4 Emission;\n" + """
uniform vec3 uShaftColour;
uniform vec3 uSkyTint;
in vec2 vAcross;
in float vFold;
in float vDepth;
flat in float vStrength;
flat in float vShapeSeed;
void main() {
    float s = vAcross.y;
    float edge = pow(abs(vAcross.x), 3.0);
    float fold = 0.45 / (abs(vFold) + 0.45);
    float fade = smoothstep(0.0, 0.06, s) * pow(1.0 - s, 1.4);
    float u = vAcross.x * 0.5 + 0.5;
    float strands = 0.0;
    for (int k = 0; k < 7; ++k) {
        float centre = fract(float(k) * 0.618 + vShapeSeed * 3.1) * 0.8 + 0.1 + 0.08 * sin(s * (3.0 + float(k)) + float(k));
        float thin = fwidth(u) * 1.2 + 0.004;
        strands += exp(-pow((u - centre) / thin, 2.0)) * (0.5 + 0.5 * fract(float(k) * 0.37 + vShapeSeed));
    }
    float a = clamp((0.05 + 0.35 * edge + 0.75 * strands) * fold * fade * vStrength, 0.0, 0.9);
    vec3 light = mix(uShaftColour, uSkyTint, 0.4) * 2.2;
    sceneTransparent(light * a, a, vDepth);
    Emission = vec4(0.0);
}
""")
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


def population(rng, view_to_world, tan, drift=0.0, wakes=None, wake_strength=0.0):
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
        for x, y, rpx, depth in CARD_BUBBLES:
            bubble(*at(x, y, rpx, depth))
        cluster([tuple(at(*b)[0]) + (at(*b)[1],) for b in CARD_DOUBLET], at(*CARD_DOUBLET[1])[1] * 0.15)
        for x, low, high in ((585, 480, 941), (655, 470, 941), (300, 430, 941)):
            for k in range(60):
                y = high - (high - low) * k / 60.0 + rng.uniform(-3.0, 3.0)
                bubble(*at(x + rng.gauss(0.0, 4.0), y, rng.uniform(1.5, 4.0), 10.0))
        return items, clusters
    # Bubbles by on-screen radius, as the mocks show them: hundreds small, a good number mid, a few large.
    pixel = 2.0 * tan[1] / H
    bands = ((10, 40.0, 85.0), (24, 18.0, 40.0), (55, 8.0, 18.0), (140, 2.0, 7.0))
    placed = []     # (x px, y px, radius px) of the bubbles 8 px and up
    for count, low, high in bands:
        for _ in range(count):
            for _try in range(30):
                u, v = rng.uniform(-1.12, 1.12), rng.uniform(-1.1, 1.08)
                pixels = rng.uniform(low, high)
                x, y = u * W / 2, v * H / 2
                if low < 8.0 or all((x - a) ** 2 + (y - b) ** 2 > ((pixels + c) * 1.05) ** 2 for a, b, c in placed):
                    break
            if low >= 8.0:
                placed.append((x, y, pixels * 1.6))
            depth = 6.0 + 26.0 * rng.random()
            r = pixels * pixel * depth
            p = place(u, v, depth)
            if high > 18.0 and rng.random() < 0.3:
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
                wakes.append((p[0], p[1] - r * 0.95, p[2], r, rng.random(), r * rng.uniform(6.0, 14.0),
                              drift + rng.uniform(-0.3, 0.3), wake_strength * rng.uniform(0.5, 1.0)))
            if high > 8.0:     # a dense wake of tiny bubbles trailing below, widening as it falls behind
                count_trail = rng.randint(40, 110) if high > 18.0 else rng.randint(15, 40)
                for k in range(count_trail):
                    along = rng.random() ** 0.7 * r * 9.0
                    spread = r * (0.25 + along / (r * 9.0) * 1.2)
                    bubble((p[0] + rng.gauss(0, spread) + math.sin(along / r) * r * 0.3 - drift * along, p[1] - r * 0.6 - along,
                            p[2] + rng.gauss(0, spread * 0.6)), r * rng.uniform(0.02, 0.08) * (1.0 - 0.5 * along / (r * 9.0)))
    # Near, out-of-focus giants at the edges.
    for side, v_low, v_high in ((-1, -0.9, -0.2), (1, -0.9, 0.0), (rng.choice((-1, 1)), 0.3, 0.8)):
        if v_low > 0.0 and rng.random() < 0.5:
            continue
        bubble(place(side * rng.uniform(0.8, 1.0), rng.uniform(v_low, v_high), rng.uniform(2.6, 3.6)),
               rng.uniform(0.5, 0.8))
    # Rising chains: beads a few pixels across, spaced a few pixels apart on screen at any distance, wobbling a little
    # and leaning with the current; now and then a larger bead.
    for _ in range(42):
        u, depth = rng.uniform(-1.3, 1.3), 5.0 + 28.0 * rng.random()
        base = place(u, -1.25, depth)
        size = rng.uniform(1.4, 4.0)
        scale = depth / 15.0
        rise, phase = 0.0, rng.uniform(0.0, 6.3)
        while rise < 1.7 * depth:
            rise += rng.uniform(0.08, 0.34) * scale * (rng.uniform(3.0, 8.0) if rng.random() < 0.07 else 1.0)
            px = size * rng.uniform(0.35, 1.3) * (1.9 if rng.random() < 0.06 else 1.0)
            bubble((base[0] + drift * rise + math.sin(rise / scale * 1.3 + phase) * 0.16 * scale + rng.gauss(0, 0.07 * scale),
                    base[1] + rise, base[2] + rng.gauss(0, 0.05 * scale)), px * pixel * depth)
    # Specks just in front of the lens, far out of focus: bokeh discs, most toward the lower corners.
    for _ in range(70):
        u = rng.choice((-1, 1)) * (1.15 - rng.random() ** 1.6 * 1.0)
        v = -1.1 + rng.random() ** 1.5 * 1.9
        depth = rng.uniform(1.1, 2.4)
        bubble(place(u, v, depth), rng.uniform(5.0, 34.0) * pixel * depth, 2.0)
    # Marine snow.
    for _ in range(2500):
        bubble(place(rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2), 2.5 + 35.0 * rng.random()), 0.005, 1.0)
    return items, clusters


def render_variant(capture, resources, target, programs, env, env_fbo, settings, seed):
    env_program, backdrop, shell, merged, shaft_program, blur_program, glint_program, ribbon_program, shaft_tex, shaft_fbo = programs
    pitch = math.radians(settings["pitch"])
    c, s = math.cos(pitch), math.sin(pitch)
    view_to_world = (1, 0, 0, 0, c, s, 0, -s, c)
    world_to_view = (1, 0, 0, 0, c, -s, 0, s, c)
    fov = math.radians(62.0)
    tan_y = math.tan(fov / 2)
    tan = (tan_y * W / H, tan_y)
    f = 1.0 / tan_y
    near, far = 0.05, 200.0
    projection = (f * H / W, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) / (near - far), -1, 0, 0, 2 * far * near / (near - far), 0)
    sun = np.array(settings["sun"]) / np.linalg.norm(settings["sun"])
    sun_below = np.array(water_sun_below(tuple(sun)))
    wakes = []
    items, clusters = population(random.Random(seed), view_to_world, tan, settings.get("drift", 0.0), wakes,
                                 settings.get("wakes", 0.0))
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
        gl.glUniform1f(u("uSparkle"), settings.get("sparkle", 0.0))
        gl.glUniform3f(u("uAbsorb"), *settings.get("absorb", (0.16, 0.065, 0.04)))
        for name, key in (("uDeep", "deep"), ("uWater", "water"), ("uSkyTint", "sky"), ("uShaftColour", "shaft")):
            gl.glUniform3f(u(name), *(v * exposure for v in settings[key]))

    def render():
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, env_fbo)
        gl.glViewport(0, 0, ENV_W, ENV_H)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        common(env_program)
        gl.glBindVertexArray(capture.vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glGenerateTextureMipmap(env)
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
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glViewport(0, 0, W, H)
        gl.glClearColor(0.11, 0.11, 0.12, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        with target.scope(frame, 4, resources, overlay=1.0, bloom=0.55, depth_texture=True, oit=True):
            with target.emission_writes():
                common(backdrop)
                gl.glActiveTexture(gl.GL_TEXTURE4)
                gl.glBindTexture(gl.GL_TEXTURE_2D, shaft_tex[0])
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glUniform1i(gl.glGetUniformLocation(backdrop, "uShafts"), 4)
                gl.glUniform2f(gl.glGetUniformLocation(backdrop, "uFrameSize"), W, H)
                gl.glBindVertexArray(capture.vao)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
                background_tex, _depth = target.background(frame, resources)
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
                    gl.glBindVertexArray(vao)
                    if not BACKDROP_ONLY:
                        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, len(items))
                    common(merged)
                    m = lambda name: gl.glGetUniformLocation(merged, name)
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
                    if wakes and not BACKDROP_ONLY:
                        common(ribbon_program)
                        w = lambda name: gl.glGetUniformLocation(ribbon_program, name)
                        gl.glUniformMatrix3fv(w("uWorldToView"), 1, gl.GL_FALSE, world_to_view)
                        gl.glUniformMatrix4fv(w("uProjection"), 1, gl.GL_FALSE, projection)
                        gl.glDisable(gl.GL_CULL_FACE)
                        gl.glBindVertexArray(wvao)
                        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 82, len(wakes))
                    gl.glActiveTexture(gl.GL_TEXTURE3)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
                    gl.glActiveTexture(gl.GL_TEXTURE0)
                if not BACKDROP_ONLY:
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
                    gl.glUniform3f(g("uLightColour"), *(sky / max(sky.mean(), 1e-3) * 0.15 + 0.85))
                    gl.glBindVertexArray(gvao)
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, 2 * len(items))
                    (gl.glEnablei if blend_on else gl.glDisablei)(gl.GL_BLEND, 0)
                    (gl.glEnable if depth_on else gl.glDisable)(gl.GL_DEPTH_TEST)

    query = int(np.asarray(gl.glGenQueries(1)).ravel()[0])
    times = []
    for index in range(16):
        gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
        render()
        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        gl.glFlush()
        if index:
            times.append(int(np.asarray(gl.glGetQueryObjectuiv(query, gl.GL_QUERY_RESULT)).ravel()[0]) / 1e6)
    raw = gl.glReadPixels(0, 0, W, H, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    gl.glDeleteVertexArrays(1, [vao])
    gl.glDeleteVertexArrays(1, [gvao])
    gl.glDeleteBuffers(1, [vbo])
    image = Image.frombytes("RGBA", (W, H), bytes(raw)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert("RGB")
    gl.glDeleteVertexArrays(1, [cvao])
    gl.glDeleteVertexArrays(1, [wvao])
    gl.glDeleteBuffers(1, [wvbo])
    gl.glDeleteBuffers(1, [cvbo])
    return image, float(np.median(times)), len(items) + len(clusters)


def main():
    capture = TransitionCapture(W, H)
    resources, target = MeshResources("bubble lab"), SceneTarget("bubble lab")
    programs = (compile_program(FULL_VERTEX, ENV_FRAGMENT, label="lab env"),
                compile_program(FULL_VERTEX, BACKDROP_FRAGMENT, label="lab backdrop"),
                compile_program(BUBBLE_VERTEX, BUBBLE_FRAGMENT, label="lab bubbles"),
                compile_program(CLUSTER_VERTEX, CLUSTER_FRAGMENT, label="lab clusters"),
                compile_program(FULL_VERTEX, SHAFT_FRAGMENT, label="lab shafts"),
                compile_program(FULL_VERTEX, BLUR_FRAGMENT, label="lab blur"),
                compile_program(GLINT_VERTEX, GLINT_FRAGMENT, label="lab glints"),
                compile_program(RIBBON_VERTEX, RIBBON_FRAGMENT, label="lab ribbons"))
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
    names = ["ExBubble2"] if CARD else [name for name in VARIANTS if only is None or name in only]
    sheet = Image.new("RGB", (W, half[1] * len(names)))
    for row, name in enumerate(names):
        image, gpu, count = render_variant(capture, resources, target, programs, env, env_fbo, VARIANTS[name], 11 + row)
        image.save(sys.argv[1].replace(".png", f"_{name}.png"))
        if CARD:
            mock_full = Image.open(ROOT / "tmp/Bubbleexamples" / f"{name}.png").convert("RGB").resize((W, H), Image.LANCZOS)
            for label, box in CARD_CROPS.items():
                a, b = mock_full.crop(box), image.crop(box)
                pair = Image.new("RGB", (a.width * 2 + 6, a.height))
                pair.paste(a, (0, 0))
                pair.paste(b, (a.width + 6, 0))
                pair.save(sys.argv[1].replace(".png", f"_card_{label}.png"))
        mock = Image.open(ROOT / "tmp/Bubbleexamples" / f"{name}.png").convert("RGB").resize(half, Image.LANCZOS)
        sheet.paste(mock, (0, row * half[1]))
        sheet.paste(image.resize(half, Image.LANCZOS), (half[0], row * half[1]))
        print(f"{name}: GPU median {gpu:.3f} ms, {count} instances ({W}x{H}, 4x MSAA)")
    sheet.save(sys.argv[1])
    target.release()
    resources.release_resources()
    capture.close()


main()
