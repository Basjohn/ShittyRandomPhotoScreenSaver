"""Extruded Bubble's GLSL programs: the underwater water and light, volumetric shafts, traced glass shells (and the
near-giant defocus layer), fused clusters and particulate.

Proven in the composition lab (``tools/labs/extruded_bubble_lab.py``, against the operator's mocks) and drawn by the
mode's renderer (``rendering/quick/visualizer/implementations/extruded_bubble.py``): one source for both, so every
lab comparison is a comparison of the product's shaders. Uniforms are documented where they are declared.
"""
from __future__ import annotations

from rendering.gl_programs.scene3d_optics import SCENE3D_OPTICS_GLSL
from rendering.gl_programs.scene3d_spheres import SCENE3D_SPHERES_GLSL
from rendering.gl_programs.scene3d_water import SCENE3D_WATER_GLSL
from rendering.quick.scene3d.defocus import SCENE_DEFOCUS_GLSL
from rendering.quick.scene3d.probe import SCENE3D_PROBE_GLSL
from rendering.quick.scene3d.target import SCENE_OIT_GLSL

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
uniform float uVeils;           // luminous caustic web through the water (deep scenes)
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
    if (uVeils > 0.0) {
        // Light focused by the surface far above hangs in the water as a glowing net (mocks: the deep scenes' web of
        // thin bright filaments, in patches, nearer sheets larger): the caustic cell edges on three sheets at depth.
        float web = 0.0;
        for (int i = 0; i < 3; ++i) {
            float d = 5.0 + 6.0 * float(i);
            vec3 at = ray * d;
            vec2 q = vec2(at.x + at.z * 0.35, at.y * 1.3 + at.z * 0.2) * (0.55 - 0.08 * float(i)) + vec2(float(i) * 4.1, 1.7);
            // Drawn out along the stream (the filaments trail with the water), fine across it.
            vec2 along = normalize(uStreak + vec2(1e-4));
            q = vec2(dot(q, along) * 0.45, dot(q, vec2(-along.y, along.x)) * 1.6);
            vec2 warp = vec2(skyFbm2(q * 0.4 + vec2(uTime * 0.02, 0.0), 3, 211u), skyFbm2(q * 0.4 + vec2(3.3, uTime * 0.015), 3, 223u));
            float c = waterCaustics(q + (warp - 0.5) * 1.6, uTime * 0.3);
            float patches = smoothstep(0.3, 0.7, skyFbm2(q * 0.18 + vec2(float(i) * 2.9), 3, 227u));
            // Thin bright threads in a soft glow of their own light.
            web += (pow(c, 6.0) + pow(c, 2.0) * 0.12) * patches * exp(-d * 0.07);
        }
        vec3 veil = mix(uShaftColour, vec3(0.6, 0.85, 1.0), 0.25) * web * 2.2 * uVeils;
        colour += veil;
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
uniform float uFanReach;        // angle (rad) over which the fan fades
uniform vec2 uFanMix;           // ray contrast 0..1, share of the depth march under the fan
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
    // Many fine and medium rays packed side by side (mocks), never a few solid wedges: soft contrast over a floor.
    float n = broad * 0.3 + mid * 0.4 + fine * 0.3;
    float rays = (1.0 - uFanMix.x) * n + uFanMix.x * smoothstep(0.42, 0.78, n);
    // Each ray reaches its own length; all fade with the angle from the sun, gone by about two thirds down.
    float reach = mix(uFanReach * 0.55, uFanReach * 1.25, skyNoise2(vec2(x * 1.3, 11.5), 101u));
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
    FragColor = vec4(mix(march, labShaftFan(ray, uSunBelow, uTime) * 0.9 + march * uFanMix.y, uShaftFan));
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
        // The light's own reflection is kept whole by the face's reflection share: a faint mirror of a very bright
        // source is still a bright highlight (only the mirrored water dims).
        vec3 lobe = vec3(0.0);
        if (i < count - 1) {
            lobe = sceneLightLobe(uViewToWorld * paths[i].xyz, lobeFootprint * (1.0 + float(i)))
                 * smoothstep(0.2, 0.5, facingHere) * smoothstep(2.5, 10.0, pixels) * filmHue;
            seen *= filmHue;
        }
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
            light += paths[i].w * (seen * reflectShare + lobe);
            own += paths[i].w * reflectShare;
            reflected += paths[i].w * (seen * reflectShare + lobe);
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
    // A bead under a few pixels: a slightly dark core (it bends the darker water below into view) and, on some, a
    // sparkle. Every one adding the same glow turned dense streams into a uniform haze (mocks: glitter, not fog).
    float sparkle = fract(vExtra.x * 17.31 + vSphere.w * 913.7) > 0.8 ? 2.5 : 0.2;
    vec3 speckLight = behind * (0.55 + 0.45 * centreness)
                    + mix(uSkyTint, uShaftColour, 0.4) * uSpeckGlow * sparkle * (0.7 + 0.6 * centreness);
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
uniform float uSpeckBloom;
void main() {
    float g = exp(-dot(vCorner, vCorner) * 8.0);
    FragColor = vec4(vColour * g * 2.6, 0.0);
    // The embers' own light also feeds the bloom: a smoky glow exactly where they gather (mock 6), never a separate
    // cloud that misses them.
    vec3 glow = max(vColour * g - 1.0, 0.0) * 0.3 + vColour * g * uSpeckBloom;
    Emission = vec4(glow, dot(glow, vec3(0.2126, 0.7152, 0.0722)));
}
"""


__all__ = [
    "BACKDROP_FRAGMENT",
    "BLUR_FRAGMENT",
    "BUBBLE_FRAGMENT",
    "BUBBLE_FRAGMENT_BODY",
    "BUBBLE_VERTEX",
    "CLUSTER_FRAGMENT",
    "CLUSTER_VERTEX",
    "COMMON",
    "FULL_VERTEX",
    "NEAR_FRAGMENT",
    "PARTICLE_FRAGMENT",
    "PARTICLE_VERTEX",
    "SHADE_GLSL",
    "SHAFT_FRAGMENT",
    "SPECKS_GLSL",
]
