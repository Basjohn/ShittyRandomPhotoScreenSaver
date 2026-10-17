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
ENV_W, ENV_H = 1024, 512
SURFACE_Y = 9.0

# Per mock: water palette, sun, camera pitch.
VARIANTS = {
    "ExBubble1": dict(deep=(0.01, 0.035, 0.08), water=(0.16, 0.24, 0.34), sky=(0.8, 0.88, 0.95), shaft=(0.6, 0.66, 0.72),
                      sun=(0.05, 0.75, -1.0), pitch=24.0, exposure=1.15),
    "ExBubble2": dict(deep=(0.003, 0.012, 0.04), water=(0.04, 0.1, 0.2), sky=(0.65, 0.78, 0.92), shaft=(0.5, 0.6, 0.72),
                      sun=(0.0, 0.7, -1.0), pitch=24.0, exposure=1.0),
    "ExBubble3": dict(deep=(0.001, 0.004, 0.012), water=(0.02, 0.04, 0.07), sky=(0.6, 0.68, 0.78), shaft=(0.45, 0.5, 0.58),
                      sun=(0.0, 0.8, -1.0), pitch=26.0, exposure=0.95),
    "ExBubble4": dict(deep=(0.003, 0.02, 0.06), water=(0.04, 0.14, 0.28), sky=(0.6, 0.8, 1.0), shaft=(0.4, 0.62, 0.9),
                      sun=(0.15, 0.65, -1.0), pitch=20.0, exposure=1.05),
    "ExBubble5CameraAbyss": dict(deep=(0.0, 0.006, 0.03), water=(0.0, 0.06, 0.2), sky=(0.3, 0.6, 1.0),
                                 shaft=(0.2, 0.5, 1.0), sun=(0.6, 0.6, -1.0), pitch=4.0, exposure=1.0, wisps=1.4),
    "ExBubble5Cameradown": dict(deep=(0.002, 0.012, 0.03), water=(0.02, 0.08, 0.16), sky=(0.5, 0.7, 0.9),
                                shaft=(0.3, 0.55, 0.85), sun=(0.3, 0.8, -1.0), pitch=-32.0, exposure=1.0, wisps=0.4),
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
const float SURFACE_Y = %.3f;
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
    vec3 medium = mix(uDeep * smoothstep(-1.0, -0.2, ray.y) * 0.8 + uDeep * 0.2, uWater, smoothstep(-0.8, 0.85, ray.y))
                + uShaftColour * (pow(glow, 10.0) * 0.22 + pow(glow, 60.0) * 0.6);
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
        vec3 light = uSkyTint * (0.28 + 0.3 * out_.y) + white * (pow(s, 6.0) * 1.4 + pow(s, 40.0) * 2.8)
                   + vec3(pow(s, 900.0) * 40.0);
        surface = mix(medium, light, transmission * smoothstep(0.0, 0.25, out_.y));
    }
    vec3 result = waterMedium(surface, distance_ * 1.0, vec3(0.16, 0.065, 0.04), medium);
    return result;
}
""" % SURFACE_Y

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
    float shafts = waterShafts(vec3(0.0), dir, 40.0, uSunBelow, SURFACE_Y, uTime, 12, 0.5) * 0.08;
    FragColor = vec4(basinWater(dir, 0.6, shafts), 1.0);
}
"""
BACKDROP_FRAGMENT = ("#version 460 core\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\n"
                     "in vec2 vNdc;\nuniform sampler2D uShafts;\nuniform vec2 uFrameSize;\n" + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + COMMON + """
void main() {
    vec3 ray = uViewToWorld * normalize(vec3(vNdc * uTan, -1.0));
    float shafts = texture(uShafts, gl_FragCoord.xy / uFrameSize).r;
    vec3 colour = basinWater(ray, 1.0, shafts);
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
    FragColor = vec4(waterShafts(vec3(0.0), ray, 45.0, uSunBelow, SURFACE_Y, uTime, 56, jitter) * 0.13 * (0.25 + toward));
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
    float blur = min(sceneDefocusRadius(depth, uFocus, uAperture, 0.12, 0.0), aSphere.w * 0.3);
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
uniform vec2 uTargetSize;
// The scene behind seen through an air lens centred at centrePx: turned over and shrunk toward the centre.
vec3 behindLens(vec2 centrePx, float strength) {
    vec2 offset = gl_FragCoord.xy - centrePx;
    return texture(uBackground, (centrePx - offset * strength) / uTargetSize).rgb;
}
uniform float uPixelSize;    // view units per pixel at unit distance
vec3 environment(vec3 dir, float blur) { return textureLod(uEnvironment, equirectUv(dir), blur).rgb; }
// A bubble's light and coverage at one point of its silhouette (world view ray rayW, world front normal n).
// A thin shell: the front wall reflects the world upright, the back wall reflects it inverted and smaller; both
// reflect through a soap film whose interference colours the reflection (blue, violet, magenta, gold) and both
// reflect almost everything toward grazing, which makes the rim. Light that passed through focuses into a bright
// crescent inside the far side. The interior is nearly clear.
vec4 shadeBubble(vec3 rayW, vec3 n, float pixels, float soft, float seed, vec2 centrePx) {
    float c = clamp(dot(-rayW, n), 0.0, 1.0);
    vec3 nBack = n - 2.0 * dot(n, rayW) * rayW;                 // the far wall along the same chord, outward
    float big = smoothstep(4.0, 30.0, pixels);                   // detail grows with on-screen size
    float sharp = soft * 4.5 + (1.0 - big) * 1.5;
    vec3 rFront = reflect(rayW, n);
    vec3 rBack = reflect(rayW, -nBack);
    vec3 front = environment(rFront, sharp);
    vec3 back = environment(rBack, sharp + 0.6);
    // Bright reflected features (the lit surface's patches) stand out of the darker water.
    front *= 1.0 + 1.8 * smoothstep(0.35, 1.4, dot(front, vec3(0.3333)));
    back *= 1.0 + 1.2 * smoothstep(0.35, 1.4, dot(back, vec3(0.3333)));
    float swirl = skyFbm3(n * 2.1 + vec3(seed * 17.0, seed * 5.0, uTime * 0.06), 3, 7u);
    float thickness = mix(160.0, 560.0, clamp(0.55 - 0.35 * n.y + 0.6 * (swirl - 0.5), 0.0, 1.0));
    vec3 filmFront = sceneThinFilm(c, thickness, 1.33, 1.0);
    vec3 filmBack = sceneThinFilm(c, thickness * 0.9 + 40.0, 1.33, 1.0);
    // Normalise the film to a hue and let the shell reflect more toward grazing (a broad rim, not a hairline).
    vec3 hueFront = filmFront / max(dot(filmFront, vec3(0.3333)), 1e-3);
    vec3 hueBack = filmBack / max(dot(filmBack, vec3(0.3333)), 1e-3);
    float shell = 0.035 + 0.965 * pow(1.0 - c, 3.2);
    float colourful = 0.55 * (1.0 - soft * 0.6);
    vec3 tintFront = mix(vec3(1.0), hueFront, colourful);
    vec3 tintBack = mix(vec3(1.0), hueBack, colourful);
    vec3 reflectedLight = front * tintFront * shell + back * tintBack * shell * 0.55 * (1.0 - shell);
    // Through the bubble: the scene behind, slightly turned over by the air lens, mostly clear.
    vec3 through = mix(behindLens(centrePx, 0.55), environment(sceneSphereRefraction(rayW, n, 1.0 / 1.33), sharp + 0.3),
                       0.25);
    // Highlights: the sun (sharp core and a soft sheen), the bright water overhead as a broad upper arc.
    float sunR = max(dot(rFront, uSunBelow), 0.0);
    vec3 key = normalize(vec3(-0.45, 0.8, 0.4));
    float keyR = max(dot(rFront, key), 0.0);
    float glint = pow(sunR, 2500.0) * 60.0 + pow(sunR, 220.0) * 3.0 + pow(keyR, 900.0) * 18.0 + pow(keyR, 80.0) * 1.2;
    float sunBack = max(dot(rBack, uSunBelow), 0.0);
    glint += pow(sunBack, 1200.0) * 14.0 * big;
    // The crescent of focused light inside the far side, opposite the light, brightest just inside the rim.
    vec3 away = normalize(-uSunBelow + vec3(0.0, -0.2, 0.0));
    float ring = smoothstep(0.35, 0.8, 1.0 - c * c) * (1.0 - smoothstep(0.9, 0.99, 1.0 - c * c));
    float crescent = ring * pow(max(dot(n, away), 0.0), 2.0) * 1.4 * big;
    // The rim's own glow: light scattered into the film all round reads as a luminous ring in every mock, brightest
    // on the side toward the light, coloured by the film (blue, violet, magenta).
    float lightSide = clamp(dot(n, normalize(uSunBelow + vec3(0.0, 0.2, 0.0))) * 0.5 + 0.5, 0.0, 1.0);
    float rimBand = pow(1.0 - c, 2.6) * (1.0 - 0.35 * smoothstep(0.97, 1.0, 1.0 - c));
    vec3 rimColour = mix(vec3(0.55, 0.72, 1.05), hueFront * vec3(0.8, 0.75, 1.25), 0.6 * (1.0 - soft * 0.3));
    vec3 rimGlow = rimColour * rimBand * (0.55 + 1.3 * lightSide * lightSide) * mix(0.5, 1.0, big);
    vec3 light = through * (1.0 - shell) + reflectedLight + rimGlow + vec3(glint) + vec3(0.8, 0.9, 1.0) * crescent;
    // Specks: points of reflected light, not dark dots.
    light += vec3(0.65, 0.82, 1.1) * 1.3 * (1.0 - smoothstep(1.0, 4.0, pixels));
    float alpha = clamp(0.12 + 0.9 * shell + rimBand * 0.6 + glint * 0.4 + crescent * 0.5, 0.0, 1.0);
    // Out of focus: a luminous disc whose rim stays (bokeh keeps the bubble's ring).
    vec3 disc = environment(rayW, 5.0) * 0.6 + vec3(0.35, 0.42, 0.52) * (0.3 + 1.2 * pow(1.0 - c, 2.5))
              + reflectedLight * 0.6 + rimGlow + vec3(glint);
    // A defocused bubble near the lens catches the specks of light behind it as bokeh dots, over a faint blue fill.
    vec2 local = (gl_FragCoord.xy - centrePx) / max(pixels, 1.0) * 5.0;
    vec2 cellId = floor(local);
    float dotHash = sceneRandom(uint(int(cellId.x) + 4096) * 0x8da6b343u ^ uint(int(cellId.y) + 4096) * 0xd8163841u, 3u,
                                uint(seed * 977.0));
    float dots = smoothstep(0.32, 0.22, distance(fract(local), vec2(0.5))) * step(0.72, dotHash) * (0.4 + dotHash);
    // Near giants stay glass spheres (rim, film, lens, highlights), only softened, with the bokeh dots added.
    light = mix(light, disc, soft * 0.3) + mix(uShaftColour, vec3(0.8, 0.9, 1.0), 0.5) * (dots * 0.9 + 0.1) * big * soft;
    // Small defocused bubbles stay faint; only big near ones become luminous discs.
    alpha = mix(alpha, (0.25 + 0.7 * pow(1.0 - c, 2.2)) * mix(0.25, 1.0, big), soft * 0.4);
    return vec4(light, alpha);
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
    if (vExtra.y > 0.5) {
        float a = coverage * 0.45 * vExtra.z * (1.0 - soft * 0.7);
        sceneTransparent(uShaftColour * 1.2 * a, a, -front.z);
        Emission = vec4(0.0);
        return;
    }
    vec4 clipC = uProjection * vec4(vSphere.xyz, 1.0);
    vec2 centrePx = (clipC.xy / clipC.w * 0.5 + 0.5) * uFrameSize;
    vec4 shaded = shadeBubble(rayW, uViewToWorld * normalize(front - vSphere.xyz), pixels, soft, vExtra.x, centrePx);
    float speck = 1.0 - smoothstep(1.0, 3.0, pixels);
    float alpha = shaded.a * coverage * mix(mix(vExtra.z, 1.0, 0.3), max(vExtra.z, 0.55), speck);
    shaded.rgb = mix(shaded.rgb, vec3(0.75, 0.85, 0.95) * 1.4, speck * 0.6);
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


def population(rng, view_to_world, tan):
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

    # Bubbles by on-screen radius, as the mocks show them: hundreds small, a good number mid, a few large.
    pixel = 2.0 * tan[1] / H
    bands = ((260, 3.0, 8.0), (130, 8.0, 18.0), (55, 18.0, 40.0), (12, 40.0, 85.0))
    for count, low, high in bands:
        for _ in range(count):
            u, v = rng.uniform(-1.12, 1.12), rng.uniform(-1.1, 1.08)
            depth = 6.0 + 26.0 * rng.random()
            r = rng.uniform(low, high) * pixel * depth
            p = place(u, v, depth)
            if high > 18.0 and rng.random() < 0.5:
                # Touching bubbles merge with a neck, as in the mocks.
                members = [(p[0], p[1], p[2], r)]
                for _m in range(1 if rng.random() < 0.6 else 2):
                    small = r * rng.uniform(0.25, 0.85)
                    gap = (r + small) * rng.uniform(0.7, 0.97)
                    angle = rng.uniform(0.0, 2.0 * math.pi)
                    tilt = rng.uniform(-0.5, 0.5)
                    members.append((p[0] + gap * math.cos(angle) * math.cos(tilt), p[1] + gap * math.sin(angle),
                                    p[2] + gap * math.sin(tilt), small))
                cluster(members, r * rng.uniform(0.08, 0.35))
            else:
                bubble(p, r)
            if high > 8.0:     # a dense wake of tiny bubbles trailing below, widening as it falls behind
                count_trail = rng.randint(40, 110) if high > 18.0 else rng.randint(15, 40)
                for k in range(count_trail):
                    along = rng.random() ** 0.7 * r * 9.0
                    spread = r * (0.25 + along / (r * 9.0) * 1.2)
                    bubble((p[0] + rng.gauss(0, spread) + math.sin(along / r) * r * 0.3, p[1] - r * 0.6 - along,
                            p[2] + rng.gauss(0, spread * 0.6)), r * rng.uniform(0.02, 0.08) * (1.0 - 0.5 * along / (r * 9.0)))
    # Near, out-of-focus giants at the edges.
    for _ in range(3):
        bubble(place(rng.choice((-1, 1)) * rng.uniform(0.75, 1.0), rng.uniform(-0.8, 0.4), rng.uniform(2.6, 3.6)),
               rng.uniform(0.5, 0.8))
    # Dense rising columns of micro-bubbles.
    for _ in range(110):
        u, depth = rng.uniform(-1.2, 1.2), 5.0 + 30.0 * rng.random()
        base = place(u, -1.2, depth)
        for k in range(rng.randint(80, 200)):
            rise = k * 0.11
            bubble((base[0] + math.sin(k * 0.3 + depth) * 0.25 + rng.gauss(0, 0.07), base[1] + rise,
                    base[2] + rng.gauss(0, 0.15)), 0.008 + 0.04 * rng.random() ** 2.5)
    # Marine snow.
    for _ in range(2500):
        bubble(place(rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2), 2.5 + 35.0 * rng.random()), 0.005, 1.0)
    return items, clusters


def render_variant(capture, resources, target, programs, env, env_fbo, settings, seed):
    env_program, backdrop, shell, merged, shaft_program, blur_program, shaft_tex, shaft_fbo = programs
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
    items, clusters = population(random.Random(seed), view_to_world, tan)
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
                    gl.glUniform1f(u("uFocus"), 4.2)
                    gl.glUniform1f(u("uAperture"), 3.0)
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
                    gl.glBindVertexArray(cvao)
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, len(clusters))
                    gl.glActiveTexture(gl.GL_TEXTURE3)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
                    gl.glActiveTexture(gl.GL_TEXTURE0)

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
    gl.glDeleteBuffers(1, [vbo])
    image = Image.frombytes("RGBA", (W, H), bytes(raw)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert("RGB")
    gl.glDeleteVertexArrays(1, [cvao])
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
                compile_program(FULL_VERTEX, BLUR_FRAGMENT, label="lab blur"))
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
    names = [name for name in VARIANTS if only is None or name in only]
    sheet = Image.new("RGB", (W, half[1] * len(names)))
    for row, name in enumerate(names):
        image, gpu, count = render_variant(capture, resources, target, programs, env, env_fbo, VARIANTS[name], 11 + row)
        image.save(sys.argv[1].replace(".png", f"_{name}.png"))
        mock = Image.open(ROOT / "tmp/Bubbleexamples" / f"{name}.png").convert("RGB").resize(half, Image.LANCZOS)
        sheet.paste(mock, (0, row * half[1]))
        sheet.paste(image.resize(half, Image.LANCZOS), (half[0], row * half[1]))
        print(f"{name}: GPU median {gpu:.3f} ms, {count} instances ({W}x{H}, 4x MSAA)")
    sheet.save(sys.argv[1])
    target.release()
    resources.release_resources()
    capture.close()


main()
