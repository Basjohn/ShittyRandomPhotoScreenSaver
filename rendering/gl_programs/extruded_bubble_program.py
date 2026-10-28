"""Extruded Bubble's GLSL programs: the underwater water and light, volumetric shafts, traced glass shells (and the
near-field defocus layer), fused clusters and particulate.

Proven in the composition lab (``tools/labs/extruded_bubble_lab.py``, against the operator's mocks) and drawn by the
mode's renderer (``rendering/quick/visualizer/implementations/extruded_bubble.py``): one source for both, so every
lab comparison is a comparison of the product's shaders. Uniforms are documented where they are declared.
"""
from __future__ import annotations

from core.constants.extruded_bubble_world import (WAKE_COUNT, WAKE_LEAD, WAKE_PATH, WAKE_POINTS, WAKE_RADIUS,
                                                  WAKE_SPACING, WAKE_STRIDE, WAKE_WATER)
from rendering.gl_programs.scene3d_optics import SCENE3D_OPTICS_GLSL
from rendering.gl_programs.scene3d_spheres import SCENE3D_SPHERES_GLSL
from rendering.gl_programs.scene3d_water import SCENE3D_WATER_GLSL
from rendering.quick.scene3d.defocus import SCENE_DEFOCUS_GLSL
from rendering.quick.scene3d.probe import SCENE3D_PROBE_GLSL
from rendering.quick.scene3d.target import SCENE_OIT_GLSL

COMMON = """
uniform mat3 uViewToWorld;
uniform vec3 uEye;         // translated camera origin in the fixed world
uniform vec2 uTan;
uniform vec2 uLensShift;
uniform float uTime;
uniform float uSurfaceTravel;
uniform vec3 uSun;
uniform vec3 uSunBelow;
uniform vec3 uLightSource;  // real physical deep-light position
uniform float uLightStrength; // direct illumination; ambient water/particle floor remain
uniform float uPositionalLight; // Light Type only; never inferred from strength
uniform float uLightingScene;  // independent of physical stream emission geometry
uniform float uBeamWidth;      // 1 retains the authored BEAM width
uniform vec3 uWorldCenter;
uniform vec3 uWorldHalf;
uniform vec3 uLightEnd;     // authored far end; directional shape derived by the CPU
uniform vec3 uDeep;
uniform vec3 uWater;
uniform vec3 uSkyTint;
uniform vec3 uShaftColour;
uniform float uShaftWhite;     // how far the shafts pale toward white (sunlight); less as Light Tint colours them
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
uniform vec2 uFloor;            // Floor amount, world height of the floor below the tank
uniform vec3 uDustAlong;        // the stream (world), along which the particle bands run
uniform vec3 uDustAcross;
uniform vec3 uDustBands;        // band frequency, world unit, how far the dust gathers into the particle bands (0..1)
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
                                  + pow(glow, 60.0) * 0.6) * uLightStrength;
    if (shafts > 0.0)
        medium += mix(uShaftColour, vec3(0.9), uShaftWhite) * shafts * (0.4 + 1.9 * pow(glow, 2.5));
    // Below: the abyss, darkening with depth (operator: no ocean floor).
    if (ray.y <= 0.015) return medium;
    float distance_ = (SURFACE_Y - uEye.y) / ray.y;
    vec2 hit = uEye.xz + (ray * distance_).xz;
    float footprint = length(fwidth(hit)) * detail + (1.0 - detail) * 1.5;
    vec3 n = rippleNormal(hit, uSurfaceTravel, footprint);
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
        // Preserve a low, continuous sky/surface across the entire upward hemisphere.
        // The high-angle sun/refraction lobe remains brighter, but the rest
        // of the ceiling must not vanish into the water medium.
        float window = 0.30 + 0.70 * smoothstep(0.12, 0.68, ray.y);
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
uniform vec2 uLensShift;        // Scene Pan: where the view's centre sits on screen (NDC; zero in the probe)
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.9999, 1.0);
    vNdc = p * 2.0 - 1.0 - uLensShift;
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
    float beamFocus = 6.0 / max(uBeamWidth*uBeamWidth,0.01);
    shafts *= mix(1.0, pow(max(dot(ray, uSunBelow), 0.0), beamFocus) * 3.0, uRayFocus * (1.0-uLightingScene));
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
        float dust = smoothstep(0.38, 0.85, cloud);
        if (uDustBands.z > 0.0) {
            // Gathered with the specks: the same world-space bands, sampled at three depths along the ray, so the
            // smoke glows where the embers stream (sixth goal) instead of wherever the sky noise falls.
            float banded = 0.0;
            for (int i = 0; i < 3; ++i) {
                vec3 p = uEye + ray * (6.0 + 8.0 * float(i)) - uWorldCenter;
                float a = dot(p, uDustAcross) / uDustBands.y, b = dot(p, uDustAlong) / uDustBands.y;
                float phase = a * uDustBands.x + 1.4 * sin(b * 2.3 + a * 3.0) + 0.8 * sin(b * 5.1 - a * 7.0);
                banded += pow(clamp(0.5 + 0.5 * sin(phase), 0.0, 1.0), 3.0) / 3.0;
            }
            dust = mix(dust, smoothstep(0.25, 0.8, cloud) * 2.4 * banded, uDustBands.z);
        }
        // Fine smouldering streaks drawn out along the stream inside the clouds (smoke, not a smooth glow).
        float streaks = skyFbm2(rotated * vec2(3.5, 24.0) + vec2(uTime * 0.03, 0.0), 4, 71u);
        dust *= 0.35 + 1.3 * smoothstep(0.35, 0.75, streaks);
        float toward = 0.5 + 1.2 * pow(max(dot(ray, uSunBelow), 0.0), 2.0);
        // Smouldering: the light's own colour deepened toward red, as embers glow (the shafts' colour washed it pale).
        vec3 ember = mix(uShaftColour, uLightColour, 0.6) * vec3(1.0, 0.55, 0.3);
        // Glowing smoke, not a faint tint (sixth goal: molten clouds along the bands); a dim light still shows it.
        colour += ember * uDust * dust * dust * 1.2 * toward * (0.5 + 0.5 * uLightStrength);
    }
    if (uWisps > 0.0) {
        float strands = 0.0;
        for (int i = 0; i < 3; ++i) {
            float d = 6.0 + 7.0 * float(i);
            vec3 at = ray * d;
            strands += waterWisps(vec2(at.x + at.z * 0.3, at.y) * (0.9 - 0.15 * float(i)) + vec2(float(i) * 7.3), uTime)
                     * exp(-d * 0.06);
        }
        colour += mix(uShaftColour, vec3(0.5, 0.8, 1.0), 0.3) * strands * 0.22 * uWisps * uLightStrength;
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
            float c = waterCaustics(q + (warp - 0.5) * 1.6, uSurfaceTravel * 0.3);
            float patches = smoothstep(0.3, 0.7, skyFbm2(q * 0.18 + vec2(float(i) * 2.9), 3, 227u));
            // Thin bright threads in a soft glow of their own light.
            web += (pow(c, 6.0) + pow(c, 2.0) * 0.12) * patches * exp(-d * 0.07);
        }
        vec3 veil = mix(uShaftColour, vec3(0.6, 0.85, 1.0), 0.25) * web * 2.2 * uVeils;
        colour += veil * uLightStrength;
    }
    if (uFloor.x > 0.0 && ray.y < -0.02) {
        // A floor far below (goals 5 and 6): the light the surface focuses lies on it as a moving caustic net over
        // darker, rocky patches, sinking into the water's haze with distance. Light in the water, not a scene object.
        float t = (uFloor.y - uEye.y) / ray.y;
        if (t > 0.0) {
            vec2 q = (uEye + ray * t).xz;
            float rocks = skyFbm2(q * 0.09, 4, 301u);
            float stones = smoothstep(0.42, 0.7, skyFbm2(q * 0.3 + vec2(7.1, 2.3), 4, 307u));
            // Warped, as light focused through a moving surface falls: organic threads, never a cell grid.
            vec2 warp = vec2(skyFbm2(q * 0.12 + vec2(uTime * 0.01, 0.0), 3, 311u),
                             skyFbm2(q * 0.12 + vec2(5.2, uTime * 0.008), 3, 313u));
            float c = waterCaustics(q * 0.32 + (warp - 0.5) * 2.4, uSurfaceTravel * 0.3);
            // Murky, not a lit tiling: the net shows only where broad patches of light fall (slowly drifting), soft
            // pools glow where it gathers, and the dark bed between threads stays dark.
            float patches = smoothstep(0.3, 0.75, skyFbm2(q * 0.05 + vec2(uTime * 0.006, -uTime * 0.004), 3, 317u));
            float pools = pow(smoothstep(0.5, 0.9, skyFbm2(q * 0.1 + vec2(-uTime * 0.01, 1.9), 3, 331u)), 1.6);
            float web = (pow(c, 6.0) + pow(c, 3.0) * 0.12) * (0.12 + 1.3 * patches) * (1.0 - 0.8 * stones);
            float glow = pools * (0.35 + 0.65 * patches) * (1.0 - 0.5 * stones);
            vec3 bed = uDeep * (0.22 + 0.45 * rocks) * (1.0 - 0.75 * stones);
            vec3 light = mix(uShaftColour, vec3(0.6, 0.85, 1.0), 0.3) * uLightStrength;
            vec3 caustic = light * (web * 4.5 + glow * 3.0);
            // The water veils the floor with distance; a little of its glow still bleeds through the haze.
            float veil = exp(-t * 0.04) * smoothstep(0.02, 0.25, -ray.y);
            colour = mix(colour, bed + caustic, uFloor.x * veil) + caustic * uFloor.x * (1.0 - veil) * 0.18;
        }
    }
    if (uLightPower > 0.0) {
        // Deep lights are physical emitters. Translating both endpoints now
        // changes their apparent screen position (not merely their angle).
        float g = max(dot(ray, normalize(uLightSource - uEye)), 0.0);
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
uniform float uShaftFan;
uniform float uFanRays;
uniform vec2 uFanMix;
uniform float uSurfaceShaft;    // Light Type only: directional Surface1, positional Deep0
uniform float uFanReach;        // angle (rad) over which the fan fades
uniform float uFlicker;         // cosmetic shimmer depth (brightness modulation is independent)
uniform float uShimmer;         // the shimmer's phase (the simulation's; faster on the hits)
uniform vec3 uRaySource;        // physical world-space beam segment start
uniform vec3 uRayEnd;           // physical world-space beam segment end
uniform vec4 uBlock0;           // up to four scene bubbles (xyz, physical radius; radius 0 = vacant)
uniform vec4 uBlock1;
uniform vec4 uBlock2;
uniform vec4 uBlock3;
uniform float uParticleAtten;   // bounded aggregate dust opacity; not per-particle shadowing
// SCENE light extent (extruded_bubble_scene.scene_light_support): entry-face weights and travel (Surface), aim
// (Deep); reach per entry face's axis (Surface) or range in x (Deep); 0 leaves that part unshaped.
// A program that never sets them sees the unshaped light: the surface admits, nothing fades.
uniform vec3 uLightFaces = vec3(0.0, 1.0, 0.0);
uniform vec3 uLightTravel = vec3(0.0, -1.0, 0.0);
uniform vec3 uLightAxis = vec3(0.0, -1.0, 0.0);
uniform vec3 uLightReach = vec3(0.0);

float blockAttenuation(vec3 samplePoint, vec4 bubble, vec3 lightTravel) {
    if (bubble.w <= 0.0) return 1.0;
    if (uLightingScene > 0.5 && uPositionalLight > 0.5
            && dot(bubble.xyz-uLightSource, lightTravel) < 0.0) return 1.0;
    vec3 fromObject = samplePoint - bubble.xyz;
    float afterObject = dot(fromObject, lightTravel);
    float lateral = length(fromObject - afterObject * lightTravel);
    float shadow = (1.0 - smoothstep(bubble.w * 0.8, bubble.w * 3.2, lateral))
                 * smoothstep(-bubble.w * 0.3, bubble.w * 1.2, afterObject);
    // Glass does not black out the shafts. Four strongest bubbles at most; diffuse shadow.
    return 1.0 - 0.16 * shadow;
}
float sceneTransmittance(vec3 p) {
    vec3 line = uRayEnd - uRaySource;
    float lengthLine = length(line);
    if (uLightingScene < 0.5 && lengthLine < 0.001) return 1.0;
    vec3 lightTravel;
    if (uLightingScene > 0.5) {
        vec3 travel = uPositionalLight > 0.5 ? p-uLightSource : -uSunBelow;
        lightTravel = travel / max(length(travel), 1e-6);
    } else {
        lightTravel = line / lengthLine;
    }
    float t = blockAttenuation(p, uBlock0, lightTravel)
            * blockAttenuation(p, uBlock1, lightTravel)
            * blockAttenuation(p, uBlock2, lightTravel)
            * blockAttenuation(p, uBlock3, lightTravel);
    return clamp(t * (1.0 - uParticleAtten), 0.60, 1.0);
}

float acceptedBeamExtent(vec3 p) {
    vec3 line = uRayEnd - uRaySource;
    float lengthLine = length(line);
    if (lengthLine < 0.001) return 0.0;
    float along = dot(p - uRaySource, line / lengthLine);
    // Real authored physical start and end; soft exit to avoid a hard lighting sheet.
    return smoothstep(-1.8, 1.2, along) * (1.0 - smoothstep(lengthLine - 2.0, lengthLine + 1.5, along));
}
float beamShaftFan(vec3 ray, vec3 sunBelow, float t) {
    // Azimuth round the sun axis, zero pointing down (the seam faces up, behind the sun).
    vec3 down = normalize(vec3(0.0, -1.0, 0.0) - sunBelow * -sunBelow.y + vec3(1e-4, 0.0, 0.0));
    vec3 side = cross(sunBelow, down);
    float phi = atan(dot(ray, side), dot(ray, down)) / 6.2831853;
    float theta = acos(clamp(dot(ray, sunBelow), -1.0, 1.0));
    phi /= uLightingScene > 0.5 ? 1.0 : max(uBeamWidth,0.01);
    float x = phi * uFanRays;
    float broad = skyNoise2(vec2(x + t * 0.04, 0.5), 83u);
    float mid = skyNoise2(vec2(x * 2.7 - t * 0.07, 3.5), 89u);
    float fine = skyNoise2(vec2(x * 7.3 + t * 0.1, 7.5), 97u);
    // Many fine and medium rays packed side by side (mocks), never a few solid wedges: soft contrast over a floor.
    float n = broad * 0.3 + mid * 0.4 + fine * 0.3;
    float rays = (1.0 - uFanMix.x) * n + uFanMix.x * smoothstep(0.42, 0.78, n);
    // Ray Flicker: each ray brightens and dims on its own as the shimmer runs.
    rays *= 1.0 + uFlicker * 1.6 * (skyNoise2(vec2(x * 1.9, uShimmer * 1.3), 107u) - 0.5);
    // Each ray reaches its own length; all fade with the angle from the sun, gone by about two thirds down.
    float reach = mix(uFanReach * 0.55, uFanReach * 1.25, skyNoise2(vec2(x * 1.3, 11.5), 101u));
    // The fan hangs below the sun: rays leaving sideways (toward the top corners) are faint (mocks).
    float spread = smoothstep(0.24, 0.1, abs(phi));
    return rays * spread * exp(-theta / reach) * smoothstep(0.02, 0.12, theta);
}
float shaftPattern(vec2 q, float t) {
    q *= uShaftScale;
    float a = skyNoise2(q * 2.1 + vec2(t * 0.12, -t * 0.07), 71u);
    float b = skyNoise2(q * 5.3 + vec2(-t * 0.2, t * 0.15), 73u);
    float slow = skyNoise2(q * 0.55 + vec2(t * 0.03, 0.0), 79u);
    float n = a * 0.7 + b * 0.3;
    float lo = mix(0.58, 0.3, uShaftSoft), hi = mix(0.82, 0.95, uShaftSoft);
    float flicker = 1.0 + uFlicker * 1.6 * (skyNoise2(q * 1.4 + vec2(uShimmer * 0.9, -uShimmer * 0.6), 109u) - 0.5);
    return smoothstep(lo, hi, n) * (0.45 + 0.9 * slow) * flicker;
}
// One four-noise world pattern; view-dependent phase changes gain, never placement.
vec2 shaftPatternCoords(vec3 p) {
    if (uSurfaceShaft > 0.5) {
        vec3 origin = vec3(uWorldCenter.x,uShaftY,uWorldCenter.z);
        vec3 delta = p-origin;
        return delta.xz - uSunBelow.xz/max(uSunBelow.y,0.2)*delta.y;
    }
    vec3 delta = p-uLightSource;
    vec3 direction = delta/max(length(delta),1e-6);
    return (direction.xz + direction.y*vec2(.3,.17))*6.0;
}
// How much SCENE light reaches world point p (0..1): inside the tank (a soft edge, never a binary sheet), then
// shaped by the authored extent. Surface: open water, so sunlight enters through the surface plane and fades with
// depth past its reach (Ray End's depth). Deep: falls off with distance from the emitter over its range, brightest
// toward its aim. (The per-face form keeps one rule should a scene ever admit light through another face.)
float sceneLightSupport(vec3 p) {
    vec3 edge = abs((p-uWorldCenter)/max(uWorldHalf,vec3(1e-4)));
    float inside = 1.0 - smoothstep(0.94, 1.0, max(edge.x,max(edge.y,edge.z)));
    if (inside <= 0.0) return 0.0;
    if (uPositionalLight > 0.5) {
        if (uLightReach.x <= 1e-3) return inside;
        vec3 d = p - uLightSource;
        float r = length(d);
        float aim = dot(d / max(r, 1e-4), uLightAxis);
        return inside * (1.0 - smoothstep(0.5*uLightReach.x, 1.1*uLightReach.x, r))
             * mix(0.35, 1.0, smoothstep(-0.3, 0.9, aim));
    }
    float lit = 0.0;
    for (int a = 0; a < 3; ++a) {
        float c = uLightTravel[a];
        if (uLightFaces[a] <= 0.0 || abs(c) < 1e-6) continue;
        float face = uWorldCenter[a] - sign(c) * uWorldHalf[a];
        if (a == 1 && c < 0.0) face = min(face, uShaftY);     // sunlight enters at the water surface
        float depth = max((p[a] - face) * sign(c), 0.0);     // how far past this entry plane
        float reach = uLightReach[a];
        float fade = reach > 1e-3 ? 1.0 - smoothstep(0.9*reach, 1.3*reach, depth) : 1.0;
        lit = max(lit, uLightFaces[a] * fade);
    }
    return inside * lit;
}
const float SCENE_SIDE_SCATTER = 2.0;   // side views of sunlit SCENE shafts (share of the world march)
float worldShafts(vec3 ray, float jitter, out float contributingDistance, out float coverage) {
    const float stepLength = 45.0 / 40.0;
    float sum = 0.0, moment = 0.0, support = 0.0, supportMoment = 0.0;
    contributingDistance = 0.0;
    coverage = 0.0;
    for (int i=0; i<40; ++i) {
        float s = (float(i)+jitter)*stepLength;
        vec3 p = uEye + ray*s;
        if (uSurfaceShaft>0.5 && p.y>=uShaftY) break;
        float extent = sceneLightSupport(p);
        if (extent<=0.0) continue;
        coverage = max(coverage,extent);
        support += extent;
        supportMoment += extent*s;
        float lightDistance = uSurfaceShaft>0.5 ? uShaftY-p.y : length(p-uLightSource);
        float weight = extent * shaftPattern(shaftPatternCoords(p),uTime)
                     * exp(-lightDistance*0.07) * exp(-s*0.035);
        sum += weight;
        moment += weight*s;
    }
    // Shadow where the light is scattered; where the pattern is momentarily empty, where the lit medium is.
    if (sum>0.0) contributingDistance = moment/sum;
    else if (support>0.0) contributingDistance = supportMoment/support;
    return sum*stepLength;
}
float beamShafts(vec3 ray, float maxDistance, vec3 sunBelow, float surfaceY, float t, int samples, float jitter) {
    float stepLength = maxDistance / float(samples);
    vec2 slope = sunBelow.xz / max(sunBelow.y, 0.2);
    float sum = 0.0;
    for (int i = 0; i < samples; ++i) {
        float s = (float(i) + jitter) * stepLength;
        vec3 p = uEye + ray * s;
        float below = surfaceY - p.y;
        if (below <= 0.0) break;
        sum += acceptedBeamExtent(p) * shaftPattern(p.xz + slope * below, t) * exp(-below * 0.07) * exp(-s * 0.035);
    }
    return sum * stepLength;
}
void main() {
    vec3 ray = uViewToWorld * normalize(vec3(vNdc*uTan,-1.0));
    float jitter = fract(52.9829189*fract(dot(gl_FragCoord.xy,vec2(0.06711056,0.00583715))));
    if (uLightingScene < 0.5) {
        float toward = pow(max(dot(ray, uSunBelow), 0.0), 2.0);
        float march = beamShafts(ray, 45.0, uSunBelow, uShaftY, uTime, 40, jitter) * 0.13 * (0.25 + toward);
        // The angle-fan is finite too: the second node changes its actual 3D reach.
        // Assess at two depths to avoid a pinhole slice when the camera physically dollies.
        float fanExtent = max(acceptedBeamExtent(uEye + ray * 12.0), acceptedBeamExtent(uEye + ray * 23.0));
        float fan = beamShaftFan(ray, uSunBelow, uTime) * fanExtent;
        float optical = sceneTransmittance(uEye + ray * 18.0);
        FragColor = vec4(max(0.0, mix(march, fan * 0.9 + march * uFanMix.y, uShaftFan) * optical));
        return;
    }
    float atDistance;
    float coverage;
    float integral = worldShafts(ray,jitter,atDistance,coverage);
    float phase = 0.25 + pow(max(dot(ray,uSunBelow),0.0),2.0);
    // Environmental sunlight retains broad structure about the actual sun;
    // the fixed world supplies support and the all-angle scattering floor.
    float march = integral * 0.13 * phase;
    // Sunlit shafts are world-space columns of lit water, visible from any side: looking away from the sun the
    // sun-angular fan is gone, so the world march itself carries a side-scattering share (none toward the sun,
    // where the fan already shows them).
    float side = 1.0 - smoothstep(0.0, 0.7, dot(ray, uSunBelow));
    float energy = uSurfaceShaft > 0.5
                 ? march*uFanMix.y + beamShaftFan(ray,uSunBelow,uTime)*0.9*coverage
                   + integral * 0.13 * SCENE_SIDE_SCATTER * side
                 : march;
    float optical = coverage>0.0 ? sceneTransmittance(uEye+ray*atDistance) : 1.0;
    FragColor = vec4(max(0.0,energy*optical));
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

EB_LENS_GLSL = """
// Render-only proximity protection. Physical radii, identities and motion stay logical-owned.
vec2 ebLensAxis(float coordinate, float depth, float radius, float tangent) {
    float distance_ = length(vec2(coordinate, depth));
    if (distance_ <= radius) return vec2(-1.0, 1.0);
    float middle = atan(coordinate, depth);
    float halfAngle = asin(clamp(radius / distance_, 0.0, 1.0));
    float sensor = atan(tangent);
    return tan(clamp(vec2(middle - halfAngle, middle + halfAngle), -sensor, sensor)) / tangent;
}
vec2 ebLens(vec4 sphere, mat4 projection, vec2 frameSize, float focus,
            float aperture, float circleScale, float maxCircle) {
    float depth = -sphere.z;
    if (sphere.w <= 0.0 || depth + sphere.w <= 0.05) return vec2(0.0);
    vec2 lower = vec2(-1.0), upper = vec2(1.0);
    if (depth > sphere.w * 1.00001) {
        float denominator = depth * depth - sphere.w * sphere.w;
        vec2 root = sqrt(sphere.xy * sphere.xy + denominator);
        vec2 lens = vec2(projection[0][0], projection[1][1]);
        lower = (sphere.xy * depth - sphere.w * root) / denominator * lens;
        upper = (sphere.xy * depth + sphere.w * root) / denominator * lens;
    } else {
        // A near-plane crossing need not fill the view: retain finite, continuous
        // sensor-clipped angular bounds for an eye-outside, off-axis shell.
        vec2 x = ebLensAxis(sphere.x, depth, sphere.w, 1.0 / projection[0][0]);
        vec2 y = ebLensAxis(sphere.y, depth, sphere.w, 1.0 / projection[1][1]);
        lower = vec2(x.x, y.x);
        upper = vec2(x.y, y.y);
    }
    // Sensor-clipped projected extent: an offscreen giant grazing one corner
    // must not be mistaken for a sphere filling the viewport.
    vec2 extent = max(vec2(0.0), clamp(upper, -1.0, 1.0) - clamp(lower, -1.0, 1.0))
                  * 0.5 * frameSize;
    float share = sqrt(extent.x * extent.y) / max(min(frameSize.x, frameSize.y), 1.0);
    float wide = smoothstep(0.30, 0.52, share);
    float circle = max(sceneNearCircle(depth - sphere.w, focus, aperture, circleScale),
                       maxCircle * wide);
    float opacity = 1.0 - smoothstep(0.78, 1.0, share);
    // Right at the lens a shell no longer reads as a bubble, even off axis where its clipped share stays small: it
    // eases out as its surface nears the eye (within a third of its radius), and back in as it leaves. Measured on the
    // steady lens radius, so breathing never toggles it; the near defocus above is unchanged.
    float surface = length(sphere.xyz) - sphere.w;
    opacity *= smoothstep(0.06, 0.33, surface / sphere.w);
    return vec2(min(circle, maxCircle), opacity);
}
"""

BUBBLE_VERTEX = """#version 460 core
layout(location=0) in vec4 aSphere;   // world centre, radius
layout(location=1) in vec2 aExtra;    // seed, kind (0 bubble, 1 snow)
layout(location=2) in float aOpacity; // logical lifetime, independent of physical radius
layout(location=3) in float aLensRadius; // steady (nominal) radius for the lens: breathing never refocuses
uniform mat3 uWorldToView;
uniform vec3 uEye;
uniform mat4 uProjection;
uniform float uFocus;
uniform float uAperture;
uniform float uPixel;
uniform float uCrisp;
uniform float uNearLayer;      // 1: drawing front-of-focus ordinary shells through shared defocus
uniform float uNearCoc;        // near lens circle scale, shared by both passes
uniform float uNearMax;        // existing defocus compositor budget in framebuffer pixels
uniform vec2 uFrameSize;
out vec2 vCorner;
flat out vec4 vSphere;
flat out float vBlur;
flat out vec3 vExtra;    // seed, kind, true radius / drawn radius
flat out float vOpacity;   // procedural chain lifetime and population fades; 1 for all other shells
flat out float vLensCircle;
""" + SCENE3D_SPHERES_GLSL + EB_LENS_GLSL + """
void main() {
    vOpacity = aOpacity;
    vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1)) * 2.0 - 1.0;
    vec3 centre = uWorldToView * (aSphere.xyz - uEye);
    float depth = -centre.z;
    // Nothing to draw (a generated instance left out, or faded to nothing; one behind the eye): no quad at all. Never
    // the half-pixel floor below, which shaded every such instance as a dot.
    if (aSphere.w <= 0.0 || vOpacity <= 0.0 || depth + aSphere.w <= 0.05) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
    // Blur in proportion to the bubble: a tiny near bubble softens without swelling into a grey disc.
    float blur = min(sceneDefocusRadius(depth, uFocus, uAperture, 0.12, 0.0), aSphere.w * 0.1);
    blur = max(blur, uPixel * depth * mix(0.7, 0.2, uCrisp));
    // Ordinary large bubbles are routed exclusively through ONE layer. Their actual front surface, not
    // their identity or a camera-attached fake, decides whether near-focus bokeh is warranted.
    vec2 lens = ebLens(vec4(centre, aLensRadius), uProjection, uFrameSize,
                      uFocus, uAperture, uNearCoc, uNearMax);
    float coc = lens.x;
    vLensCircle = coc;
    if (aExtra.y < 0.5) vOpacity *= lens.y;
    if (vOpacity <= 0.0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
    bool near_ = aExtra.y < 0.5 && coc > 1.5;
    if (near_) blur = uPixel * depth * 0.5;                  // sharp in its layer; the lens blurs it
    if (near_ != (uNearLayer > 0.5)) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
    // At least half a pixel across so specks resolve; their light is scaled back to their true size.
    float radius = max(aSphere.w, uPixel * depth * 0.5);
    vSphere = vec4(centre, radius);
    vBlur = blur;
    vExtra = vec3(aExtra, (aSphere.w * aSphere.w) / (radius * radius));
    // One pinhole convention for ordinary and fused geometry, including near crossings.
    vCorner = corner;
    gl_Position = sceneSphereClipCorner(centre, radius + blur, corner, uProjection);
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
vec3 sceneLightLobe(vec3 dirWorld, vec3 pointView, float footprint) {
    vec3 lightDirection = uLightDir;
    if (uPositionalLight > 0.5) {
        vec3 delta = uLightSource - (uEye + uViewToWorld * pointView);
        lightDirection = delta / max(length(delta), 1e-6);
    }
    float angle = acos(clamp(dot(normalize(dirWorld), lightDirection), -1.0, 1.0));
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
    float eyeDistance = length(sphere.xyz);
    bool inside = eyeDistance < sphere.w;
    vec3 axis = eyeDistance > 1e-6 ? sphere.xyz / eyeDistance : rayView;
    float along = dot(rayView, axis);
    vec3 offAxis = rayView - axis * along;
    float maxSin = (sphere.w / max(eyeDistance,1e-6)) * (1.0 - 0.6 / max(pixels, 2.0));
    float sinNow = length(offAxis);
    if (!inside && sinNow > maxSin)
        rayView = normalize(axis * sqrt(max(1.0 - maxSin * maxSin, 0.0)) + offAxis / max(sinNow, 1e-6) * maxSin);
    float tN, tF;
    if (!sceneSphereRay(rayView, sphere.xyz, sphere.w, tN, tF)) return vec4(0.0);
    float minT = 0.05 / max(-rayView.z,1e-4);
    vec3 frontView = rayView * (tN >= minT ? tN : tF);
    vec3 facingNormal = normalize(frontView - sphere.xyz) * (inside ? -1.0 : 1.0);
    // A mirror on a sphere turns the view by twice the normal's turn: one pixel spans ~2 / (radius px x facing) rad.
    float facingHere = max(dot(-rayView, facingNormal), 0.15);
    float lobeFootprint = 2.0 / (max(pixels, 1.0) * facingHere) + soft * 0.6;
    vec4 paths[8];
    vec3 pathPoints[8];
    vec3 origin = inside ? -sphere.xyz / sphere.w : (frontView - sphere.xyz) / sphere.w - rayView * 1e-3;
    // Filter small optical footprints with the probe/rim sampling, not a thicker
    // physical wall: a pixel-sized minimum changes the inner sphere with distance
    // and can erase the air core. The lab's explicit single-interface option stays
    // separate; production traces its authored thickness at every projected size.
    float shell = pixels < uShellMin ? 0.0 : uShell;
    int count = sceneHollowSphereTrace(origin, rayView, 1.0, max(1.0 - shell, 0.0), uIors, paths, pathPoints,
                                      uPositionalLight > 0.5);
    vec3 light = vec3(0.0);
    float own = 0.0;
    vec3 reflected = vec3(0.0), transmitted = vec3(0.0);
    // Soap-film interference on what the surface mirrors: thickness drifts over the bubble (gravity thins the top),
    // the hue is kept relative (it recolours reflected scene light, never adds light of its own). Per scene.
    vec3 filmHue = vec3(1.0);
    // Reflections' share: uReflect at the face, full toward the rim (a near giant's face mirrors little).
    float faceOn = clamp(dot(-rayView, facingNormal), 0.0, 1.0);
    float reflectShare = mix(1.0, uReflect, pow(faceOn, 0.6));
    if (uFilm > 0.0) {
        vec3 local = (frontView - sphere.xyz) / sphere.w;
        float c = clamp(dot(-rayView, facingNormal), 0.0, 1.0);
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
            vec3 lobePoint = vec3(0.0);
            if (uPositionalLight > 0.5) lobePoint = sphere.xyz + sphere.w * pathPoints[i];
            lobe = sceneLightLobe(uViewToWorld * paths[i].xyz, lobePoint,
                                 lobeFootprint * (1.0 + float(i)))
                 * smoothstep(0.2, 0.5, facingHere) * smoothstep(2.5, 10.0, pixels) * filmHue;
            seen *= filmHue;
        }
        if (i == count - 1) {
            // What is seen through is out of focus inside the bubble (the lens's depth): softened with its size.
            // The frame is read along the smooth lens of the bubble as a whole (refraction through a plain sphere of the
            // outer index): the traced exit through the glass wall swings chaotically near the rim (speckle). The trace
            // still sets how much light comes through.
            vec3 lensExit;
            vec3 lensDir = inside ? paths[i].xyz : sceneSphereRefraction(rayView, facingNormal, 1.0 / uIors.x, lensExit);
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
            vec3 airExit = vec3(0.0);
            if (inside && uPositionalLight > 0.5) airExit = pathPoints[i];
            vec3 airLens = inside ? paths[i].xyz : sceneSphereRefraction(rayView, facingNormal, uIors.x / uIors.z, airExit);
            vec3 airPoint = vec3(0.0);
            if (uPositionalLight > 0.5) airPoint = sphere.xyz + sphere.w * airExit;
            seen += sceneLightLobe(uViewToWorld * airLens, airPoint,
                                   lobeFootprint * 1.5) * uSpecThrough
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
const float kRimRaysFull = 10.0;  // radius px from which a rim pixel averages eight rays (four below)
const float kSmallShellRays = 6.0;  // radius px below which every pixel of a shell averages rays, its face too
const float kBeadShellFrom = 2.0;   // radius px from which a bead blends from glass speck to a shaded shell
const float kBeadShellFull = 3.5;   // ... and at which it is a shaded shell
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
    // A shell under kSmallShellRays px is all rim: one ray per pixel made it shimmer as it drifted sub-pixel
    // (20% at 3 px), most of all the deepest-contracted bubbles at rest. Its few pixels take the four rays too.
    if (facing > 0.8 && pixels >= kSmallShellRays) {
        sum = shadeBubbleRay(rayView, sphere, pixels, soft, blur);
    } else {
        sum = vec4(0.0);
        // Points spread over the pixel (a rotated-grid pattern), never beyond it: eight, or four on a bead, whose
        // rim is a pixel or two wide (the trace through every point was the beads' cost).
        int rays = pixels < kRimRaysFull ? 4 : 8;
        for (int i = 0; i < rays; ++i) {
            vec2 o = vec2(fract(float(i) * 0.618034 + 0.5 / float(rays)), (float(i) + 0.5) / float(rays)) - 0.5;
            sum += shadeBubbleRay(normalize(rayView + dx * o.x + dy * o.y), sphere, pixels, soft, blur)
                 / float(rays);
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
flat in float vOpacity;
#ifdef NEAR_LAYER
flat in float vLensCircle;
#endif
void main() {
    vec2 ndc = gl_FragCoord.xy / uFrameSize * 2.0 - 1.0 - uLensShift;
    vec3 ray = normalize(vec3(ndc * uTan, -1.0));
    float coverage = sceneSphereCoverage(ray, vSphere.xyz, vSphere.w, vBlur, uPixelSize);
    if (coverage <= 0.0) discard;
    float tNear, tFar;
    bool hit = sceneSphereRay(ray, vSphere.xyz, vSphere.w, tNear, tFar);
    float minT = 0.05 / max(-ray.z, 1e-4);
    if ((hit && tFar < minT) || (!hit && dot(vSphere.xyz, ray) < minT)) discard;
    vec3 front = hit ? ray * (tNear >= minT ? tNear : tFar) : ray * dot(vSphere.xyz, ray);
    vec3 rayW = uViewToWorld * ray;
    float soft = clamp(vBlur / max(vSphere.w, 1e-3), 0.0, 1.0);
    float pixels = vSphere.w / (uPixelSize * max(-front.z, 0.1));
    if (vExtra.y > 0.5 && vExtra.y < 1.5) {
        float a = coverage * 0.45 * vExtra.z * (1.0 - soft * 0.7) * vOpacity;
        float glitter = 1.0 + uSparkle * 7.0 * step(0.86, fract(vExtra.x * 31.7)) * uLightStrength;
#ifndef NEAR_LAYER
        sceneTransparent(mix(uShaftColour, vec3(0.9, 0.95, 1.0), 0.4) * 1.2 * glitter * a, a, -front.z);
        Emission = vec4(0.0);
#endif
        return;
    }
    if (vExtra.y > 2.5 && vExtra.y < 3.5) {
        // Beads below a few pixels should not flip between a refractive highlight and stochastic speck when
        // crossing the 1..2.5 px threshold. A stable, environment-lit glass speck retains water/probe colours,
        // background transmission, mild Fresnel and scene depth, without high-frequency multi-tap refraction.
        vec3 normalV = hit ? normalize(front - vSphere.xyz) : -ray;
        float fresnel = pow(1.0 - clamp(dot(normalV, -ray), 0.0, 1.0), 3.0);
        vec3 probe = textureLod(uProbe, uViewToWorld * reflect(ray, normalV), min(uProbeLevels - 1.0, 3.0)).rgb;
        vec3 waterBehind = texture(uBackground, gl_FragCoord.xy / uTargetSize).rgb;
        float glint = 0.65 + 0.35 * fract(vExtra.x * 17.31); // seeded identity, never the changing radius
        vec3 light = mix(waterBehind, probe, 0.22 + 0.45 * fresnel);
        light += uShaftColour * uSpeckGlow * (0.12 + 0.30 * fresnel) * glint;
        float alpha = coverage * (0.22 + 0.38 * fresnel) * vExtra.z * vOpacity;
        // A bead large enough to resolve reads as micro-glass: a bright Fresnel rim and the light's own glint,
        // filtered by the bead's footprint. The speck alone kept every bead of a microbubble column a dim grey ring
        // however large it was drawn; the full shell trace doubled the frame for thousands of beads. Blended in by
        // size only (beads never breathe), so nothing flips; beads of a pixel or two are unchanged.
        float shell = smoothstep(kBeadShellFrom, kBeadShellFull, pixels);
        if (shell > 0.0) {
            // The glint is a pixel or two on the side facing the light, whatever the bead's size (the shell's own
            // lobe, filtered over so small a footprint, all but vanishes).
            vec3 toLight = normalize(uLightDir * uViewToWorld);   // world -> view (the transpose of a rotation)
            float spot = pow(max(dot(normalV, normalize(toLight - ray)), 0.0), 2.0 + 0.6 * pixels * pixels);
            vec3 glint = uSpecColour * 0.05 * uSparkle * spot;
            vec3 glass = mix(waterBehind, probe, 0.25 + 0.65 * fresnel) + uShaftColour * uSpeckGlow * 0.4 * fresnel
                       + glint;
            light = mix(light, glass, shell);
            alpha = mix(alpha, coverage * min(1.0, 0.28 + 0.62 * fresnel + 0.5 * spot * uSparkle) * vExtra.z
                               * vOpacity, shell);
        }
        gl_FragDepth = sceneSphereDepth(front, uProjection);
#ifndef NEAR_LAYER
        sceneTransparent(light * alpha, alpha, -front.z);
        Emission = vec4(0.0);
#endif
        return;
    }
    vec4 clipC = uProjection * vec4(vSphere.xyz, 1.0);
    vec2 centrePx = (clipC.xy / clipC.w * 0.5 + 0.5) * uFrameSize;
    gl_FragDepth = sceneSphereDepth(front, uProjection);
    float speck = 1.0 - smoothstep(1.0, 2.5, pixels);
    // A bead of a pixel or less is all speck light below: its trace would be thrown away.
    vec4 shaded = speck < 1.0 ? shadeBubble(ray, vSphere, pixels, soft, front) : vec4(0.0);
    if (uDiag == 5) shaded = vec4(vec3(coverage), 1.0);
    float centreness = clamp(dot(-ray, normalize(front - vSphere.xyz)), 0.0, 1.0);
    vec3 behind = texture(uBackground, gl_FragCoord.xy / uTargetSize).rgb;
    // A bead under a few pixels: a slightly dark core (it bends the darker water below into view) and, on some, a
    // sparkle. Every one adding the same glow turned dense streams into a uniform haze (mocks: glitter, not fog).
    // Material membership follows stable identity, never the breathing radius.
    float sparkle = fract(vExtra.x * 17.31) > 0.8 ? 2.5 : 0.2;
    vec3 speckLight = behind * (0.55 + 0.45 * centreness)
                    + mix(uSkyTint, uShaftColour, 0.4) * uSpeckGlow * sparkle * (0.7 + 0.6 * centreness);
    shaded = mix(shaded, vec4(speckLight, 0.3 + 0.5 * centreness), speck);
    float alpha = shaded.a * coverage * mix(mix(vExtra.z, 1.0, 0.3), max(vExtra.z, 0.55), speck) * vOpacity;
#ifdef NEAR_LAYER
    // The circle this bubble's light spreads over at the lens, in pixels: grows as it nears the camera.
    sceneDefocusWrite(shaded.rgb * alpha * uNearGain, alpha * uNearGain, vLensCircle);
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
                 + "uniform float uNearCoc;\nuniform float uFocus;\nuniform float uAperture;\nuniform float uNearGain;\n" + BUBBLE_FRAGMENT_BODY)

CLUSTER_VERTEX = """#version 460 core
layout(location=0) in vec4 aS0;
layout(location=1) in vec4 aS1;
layout(location=2) in vec4 aS2;
layout(location=3) in vec4 aInfo;     // count, blend, seed, unused
layout(location=4) in vec3 aAlphas;   // lifetime opacity for each union member
uniform mat3 uWorldToView;
uniform vec3 uEye;
uniform mat4 uProjection;
uniform float uFocus;
uniform float uAperture;
uniform float uNearLayer;
uniform float uNearCoc;
uniform float uNearMax;
uniform vec2 uFrameSize;
out vec3 vView;
flat out vec4 vSpheres[3];
flat out vec4 vBound;
flat out vec4 vInfo;
flat out vec3 vAlphas;
flat out vec3 vLensCircles;
""" + SCENE3D_SPHERES_GLSL + EB_LENS_GLSL + """
void main() {
    vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1)) * 2.0 - 1.0;
    vec4 world[3] = vec4[3](aS0, aS1, aS2);
    int count = int(aInfo.x);
    vec3 centre = vec3(0.0);
    for (int i = 0; i < 3; ++i) if (i < count) centre += world[i].xyz;
    centre /= float(count);
    float bound = 0.0;
    vAlphas = aAlphas;
    vLensCircles = vec3(0.0);
    float coc = 0.0;
    for (int i = 0; i < 3; ++i) {
        vSpheres[i] = vec4(uWorldToView * (world[i].xyz - uEye), world[i].w);
        if (i < count) {
            bound = max(bound, distance(centre, world[i].xyz) + world[i].w);
            vec2 lens = ebLens(vSpheres[i], uProjection, uFrameSize,
                              uFocus, uAperture, uNearCoc, uNearMax);
            vAlphas[i] *= lens.y;
            vLensCircles[i] = lens.x;
            if (vAlphas[i] > 0.0) coc = max(coc, lens.x);
        }
    }
    vBound = vec4(uWorldToView * (centre - uEye), bound + aInfo.y);
    vInfo = aInfo;
    if (max(vAlphas.x, max(vAlphas.y, vAlphas.z)) <= 0.0) {
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return;
    }
    if ((coc > 1.5) != (uNearLayer > 0.5)) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
    vView = sceneSphereCorner(vBound.xyz, vBound.w, 0.0, corner);
    gl_Position = sceneSphereClipCorner(vBound.xyz, vBound.w, corner, uProjection);
}
"""
CLUSTER_FRAGMENT_BODY = (SCENE3D_SPHERES_GLSL + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + SCENE3D_PROBE_GLSL + COMMON
                    + SHADE_GLSL + """
in vec3 vView;
flat in vec4 vSpheres[3];
flat in vec4 vBound;
flat in vec4 vInfo;
flat in vec3 vAlphas;
flat in vec3 vLensCircles;
void main() {
    vec2 ndc = gl_FragCoord.xy / uFrameSize * 2.0 - 1.0 - uLensShift;
    vec3 ray = normalize(vec3(ndc * uTan, -1.0));
    float tNear, tFar, t, closest;
    vec3 normal;
    if (!sceneSphereRay(ray, vBound.xyz, vBound.w, tNear, tFar)) discard;
    vec4 s[4] = vec4[4](vSpheres[0], vSpheres[1], vSpheres[2], vec4(0.0));
    float minT = 0.05 / max(-ray.z, 1e-4);
    if (tFar < minT) discard;
    bool hit = sceneClusterRay(ray, s, int(vInfo.x), vInfo.y, max(tNear, minT), tFar, t, normal, closest);
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
    // The same smooth-min weights as the union surface, not the first member's alpha.
    float distance_ = length(point - s[0].xyz) - s[0].w;
    float opacity = vAlphas[0];
    float circle = vLensCircles[0];
    for (int i = 1; i < 3; ++i) {
        if (i >= int(vInfo.x)) break;
        float nextDistance = length(point - s[i].xyz) - s[i].w;
        float weight = vInfo.y > 0.0 ? clamp(0.5 + 0.5 * (nextDistance - distance_) / vInfo.y, 0.0, 1.0)
                                    : (distance_ < nextDistance ? 1.0 : 0.0);
        opacity = mix(vAlphas[i], opacity, weight);
        circle = mix(vLensCircles[i], circle, weight);
        distance_ = sceneSmoothMin(distance_, nextDistance, vInfo.y);
    }
    float alpha = shaded.a * coverage * opacity;
#ifdef NEAR_LAYER
    sceneDefocusWrite(shaded.rgb * alpha * uNearGain, alpha * uNearGain, circle);
#else
    sceneTransparent(shaded.rgb * alpha, alpha, -point.z);
    vec3 emitted = max(shaded.rgb - 1.2, 0.0) * alpha * 0.6;
    Emission = vec4(emitted, dot(emitted, vec3(0.2126, 0.7152, 0.0722)));
#endif
}
""")
CLUSTER_FRAGMENT = ("#version 460 core\n" + SCENE_OIT_GLSL + "layout(location=2) out vec4 Emission;\n"
                    + CLUSTER_FRAGMENT_BODY)
NEAR_CLUSTER_FRAGMENT = ("#version 460 core\n#define NEAR_LAYER\n" + SCENE_DEFOCUS_GLSL
                         + "uniform float uNearCoc;\nuniform float uFocus;\nuniform float uAperture;\nuniform float uNearGain;\n"
                         + CLUSTER_FRAGMENT_BODY)

PARTICLE_VERTEX = """#version 460 core
layout(location=0) in vec4 aPoint;   // fixed world position, world radius
layout(location=1) in vec4 aLook;    // brightness, warm (lit in the light's colour) or neutral, seed, unused
uniform mat3 uWorldToView;
uniform vec3 uEye;
uniform bool uRowMajor;
uniform mat4 uProjection;
uniform float uPixel;                // view units per pixel at unit distance
uniform vec3 uSunBelow;
uniform vec3 uLightSource;
uniform float uPositionalLight;
uniform float uLightStrength;
uniform float uParticleLighting; // 1: scattering particle, 0: CPU-lit glint proxy
uniform vec3 uLightColour;
uniform vec3 uSpeckWarm;
uniform vec3 uWater;
uniform float uSpecks;
uniform float uParticleRadiusShare; // display contraction; retain authored subpixel light energy
out vec2 vCorner;
flat out vec3 vColour;
void main() {
    vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1)) * 2.0 - 1.0;
    mat3 toView = uRowMajor ? transpose(uWorldToView) : uWorldToView;
    vec3 c = toView * (aPoint.xyz - uEye);
    float depth = -c.z;
    float drawn = max(aPoint.w * uParticleRadiusShare, uPixel * depth * 0.75);
    float energy = min((aPoint.w * aPoint.w) / (drawn * drawn), 1.0);
    vec3 lightDirection = uSunBelow;
    if (uPositionalLight > 0.5) {
        vec3 delta = uLightSource - aPoint.xyz;
        lightDirection = delta / max(length(delta), 1e-6);
    }
    float phase = 0.3 + 2.2 * pow(max(dot(normalize(aPoint.xyz - uEye), lightDirection), 0.0), 4.0)
                            * mix(1.0, uLightStrength, uParticleLighting);
    vec3 tint = aLook.y > 0.5 ? uSpeckWarm : mix(uWater * 6.0, vec3(0.75, 0.82, 0.86), 0.5);
    vColour = tint * aLook.x * phase * energy * uSpecks;
    vCorner = corner;
    // A speck left out (radius 0) draws no quad (its zero light would still be blended over the water).
    gl_Position = depth > 0.05 && aPoint.w > 0.0 ? uProjection * vec4(c + vec3(corner * drawn * 2.0, 0.0), 1.0)
                                                 : vec4(2.0, 2.0, 2.0, 1.0);
}
"""
PARTICLE_FRAGMENT = """#version 460 core
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
in vec2 vCorner;
flat in vec3 vColour;
uniform float uSpeckBloom;
uniform float uParticleActivity; // logical quiet release; light proxies explicitly use 1
void main() {
    float g = exp(-dot(vCorner, vCorner) * 8.0);
    FragColor = vec4(vColour * g * 2.6, 0.0);
    // The embers' own light also feeds the bloom: a smoky glow exactly where they gather (mock 6), never a separate
    // cloud that misses them.
    vec3 glow = max(vColour * g - 1.0, 0.0) * 0.3 + vColour * g * uSpeckBloom;
    glow *= uParticleActivity;
    Emission = vec4(glow, dot(glow, vec3(0.2126, 0.7152, 0.0722)));
}
"""


_SCENE_INLET_GLSL = """
// Shared physical inlet geometry for SCENE. The same weighted upstream
// face law is used by the CPU bubble sampler. Camera-independent and bounded.
vec4 sceneInlet(float faceSeed, vec2 uv, vec3 direction, vec3 centre, vec3 halfExt, vec3 faceWeights) {
    vec3 d = normalize(direction);
    // Weights already resolved once by the authored CPU world authority.
    vec3 area = faceWeights;
    float choice = faceSeed * max(0.000001, area.x + area.y + area.z);
    int axis = choice < area.x ? 0 : (choice < area.x + area.y ? 1 : 2);
    // Two independent coordinates span whichever physical face was chosen.
    // The former construction derived Z from a blend of UV.x/UV.y, even for
    // the floor face, correlating its transverse coordinates and concentrating
    // rendered cohorts despite whole-face CPU admission.
    vec3 p = centre;
    if (axis == 0) {
        p.x -= sign(d.x) * halfExt.x;
        p.y += (uv.x * 2.0 - 1.0) * halfExt.y;
        p.z += (uv.y * 2.0 - 1.0) * halfExt.z;
    } else if (axis == 1) {
        p.x += (uv.x * 2.0 - 1.0) * halfExt.x;
        p.y -= sign(d.y) * halfExt.y;
        p.z += (uv.y * 2.0 - 1.0) * halfExt.z;
    } else {
        p.x += (uv.x * 2.0 - 1.0) * halfExt.x;
        p.y += (uv.y * 2.0 - 1.0) * halfExt.y;
        p.z -= sign(d.z) * halfExt.z;
    }
    vec3 toFar = centre + halfExt;
    vec3 toNear = centre - halfExt;
    float distanceOut = 1e10;
    for (int k = 0; k < 3; ++k) {
        if (d[k] > 1e-6) distanceOut = min(distanceOut, (toFar[k] - p[k]) / d[k]);
        else if (d[k] < -1e-6) distanceOut = min(distanceOut, (toNear[k] - p[k]) / d[k]);
    }
    return vec4(p, max(0.001, distanceOut));
}

// SCENE fades describe physical entry/exit and an actor crossing a wall. A
// percentage of the whole tank used to erase a wide, otherwise valid lateral
// interior slab. The small footprint owns these distances, not the camera.
float scenePathFade(vec3 p, vec3 centre, vec3 halfExt, float travelled, float span, float radius) {
    vec3 inside = halfExt - abs(p - centre);
    float clearance = min(inside.x, min(inside.y, inside.z));
    float wall = smoothstep(0.0, max(2.0 * radius, 1e-5), clearance);
    float width = min(0.25 * span, max(4.0 * radius, 1e-4));
    return wall * smoothstep(0.0, width, travelled)
                * (1.0 - smoothstep(span - width, span, travelled));
}
"""

# The procedural small bubbles' vertex stage: the bubble vertex stage with its per-instance attributes generated.
# Wake trails (the goals' tendrils): behind a bubble the water it has disturbed streams off in a gentle curl, a dense
# stream of microbubbles inside a faint, soft veil of lit water. One shared path per stable wake emitter (the fizz's
# records; retiring emitters dissolve theirs), swaying with the simulation's motion phase. The veil (TRAIL_*) and the
# fizz beads (_BEAD_GLSL) both follow it, so the beads flow inside their veil. Each path is the water the bubble has
# passed through (the simulation's WakePath: sampled history, dragged after the bubble a moment, then drifting with the
# water), so the trail shows where the bubble went and the music steers only the bubble.
TRAIL_FADE = 0.26   # where a trail (its sheet and its beads) begins to thin, as a share of its length
_WAKE_PATH_GLSL = """
layout(std430, binding = 7) readonly buffer EbWakes { float ebWake[]; };    // see core.constants WAKE_STRIDE
const int WAKE_STRIDE = """ + str(WAKE_STRIDE) + """;
const int WAKE_PATH = """ + str(WAKE_PATH) + """;
const int WAKE_POINTS = """ + str(WAKE_POINTS) + """;
const int WAKE_SPACING = """ + str(WAKE_SPACING) + """;
const int WAKE_COUNT = """ + str(WAKE_COUNT) + """;
const int WAKE_WATER = """ + str(WAKE_WATER) + """;
const int WAKE_LEAD = """ + str(WAKE_LEAD) + """;
const int WAKE_RADIUS = """ + str(WAKE_RADIUS) + """;
uniform float uTrails;        // Wake Trails: 0 none .. 1 most bubbles trail a veil
uniform float uTrailTime;     // the simulation's motion phase: the veil's inner light drifts with the water
const float TRAIL_FADE = """ + str(TRAIL_FADE) + """;
float trailHash(float x) { return fract(sin(x * 12.9898) * 43758.5453); }
// The trail's chain: the bubble itself (k = 0), then the water it passed through, newest first.
vec3 wakePoint(int owner, int k) {
    int at = k <= 0 ? owner * WAKE_STRIDE : owner * WAKE_STRIDE + WAKE_PATH + 3 * (min(k, WAKE_POINTS) - 1);
    return vec3(ebWake[at], ebWake[at + 1], ebWake[at + 2]);
}
// Centripetal Catmull-Rom (knots by the square root of each segment's length): it never loops or overshoots where
// neighbouring segments differ greatly in length, as the bubble's own segment does just after it lays a new point
// (a uniform curve looped there in 3.2% of sampled roots, swinging the trail's root off its bubble).
vec3 wakeSpline(vec3 p0, vec3 p1, vec3 p2, vec3 p3, float u) {
    float t1 = sqrt(max(distance(p0, p1), 1e-6));
    float t2 = t1 + sqrt(max(distance(p1, p2), 1e-6));
    float t3 = t2 + sqrt(max(distance(p2, p3), 1e-6));
    float t = mix(t1, t2, u);
    vec3 a1 = mix(p0, p1, t / t1);
    vec3 a2 = mix(p1, p2, (t - t1) / (t2 - t1));
    vec3 a3 = mix(p2, p3, (t - t2) / (t3 - t2));
    vec3 b1 = mix(a1, a2, t / t2);
    vec3 b2 = mix(a2, a3, (t - t1) / (t3 - t1));
    return mix(b1, b2, (t - t1) / (t2 - t1));
}
float wakeField(int owner, int field) { return ebWake[owner * WAKE_STRIDE + field]; }
// How far the trail reaches behind its bubble, in spacings (its water so far, never more than its points span).
float trailReach(int owner) {
    return clamp(wakeField(owner, WAKE_LEAD) + wakeField(owner, WAKE_COUNT) - 1.0, 0.0, float(WAKE_POINTS - 1));
}
// The water c spacings behind the bubble, on the spline through the chain. Placed by water, never by a share of the
// chain's segments: the bubble's own segment grows as it moves and empties when it lays a point, and anything placed
// by segment slid with the bubble and jumped back at every new point (the beads' teleport, the root's snap).
vec3 trailWater(int owner, float c) {
    float lead = wakeField(owner, WAKE_LEAD);
    int last = max(int(wakeField(owner, WAKE_COUNT) + 0.5), 1);
    float f = c <= lead ? c / max(lead, 1e-4) : 1.0 + (c - lead);   // 0 the bubble, k its k-th point
    f = clamp(f, 0.0, float(last));
    int i = min(int(floor(f)), last - 1);
    float t = f - float(i);
    vec3 p1 = wakePoint(owner, i), p2 = wakePoint(owner, i + 1);
    vec3 p0 = i > 0 ? wakePoint(owner, i - 1) : 2.0 * p1 - p2;
    vec3 p3 = i + 2 <= last ? wakePoint(owner, i + 2) : 2.0 * p2 - p1;
    return wakeSpline(p0, p1, p2, p3, t);
}
"""
_BEAD_GLSL = _WAKE_PATH_GLSL + """// GPU procedural populations in the simulation's fixed physical world.
uniform vec3 uWorldCenter;
uniform vec3 uWorldHalf;
uniform vec3 uStreamWorld;
uniform vec3 uStreamAcross;
uniform vec3 uStreamDepth;
uniform vec3 uStreamSource; // same authored physical source as ordinary bubbles/specks
uniform vec3 uStreamEnd;    // same authored destination, no interior spawn origin
uniform float uBeadTravel;     // integrated physical world travel
uniform int uBeadsPerChain;
uniform int uBeadCount;        // chains x beads; instances past it are marine snow
uniform float uBeadSize;       // bead size scale
uniform float uBeadScatter;    // 0 single-file chains .. 1 loose plumes widening as they rise
uniform float uParticleSpread; // free chains and snow only: 1.0 original physical width
uniform int uSceneEmission; // SCENE uses whole upstream faces; BEAM remains identical
uniform vec3 uSceneFaces;    // physically valid face areas selected by Source
uniform float uChainFill;       // continuous (possibly fractional) number of visible chains
uniform float uChainActivity;   // all free chains fade together at rest; never affects attached wakes/snow
uniform float uSnowFill;        // continuous snow allocation; last mote fades at the boundary
uniform float uFizzFill;        // continuous allocation per stable wake, before ceil to integer stride
uniform float uTrailFizz;       // the bead stream inside a wake trail's veil (Wake Trails), independent of Particles
uniform float uSnowDrift;      // how far snow has drifted along the stream (view units)
uniform int uSnowCount;        // instances past chains and snow are fizz: uFizzPer behind each stable wake emitter
uniform int uFizzPer;
uniform int uWakeCount;
vec4 aSphere;
float aLensRadius;
vec2 aExtra;
uint beadHash(uint x) {
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
    return x;
}
float beadRandom(int index, uint salt) {
    return float(beadHash(uint(index) * 0x9e3779b9u ^ salt * 0x85ebca6bu) & 0xffffffu) / 16777215.0;
}
void beadInstance() {
    vec3 path = uStreamEnd - uStreamSource;
    float pathLength = length(path);
    // A zero path is only for isolated legacy GPU diagnostics that do not set
    // the new uniforms. Production always supplies two distinct authored nodes.
    bool pathEnabled = pathLength > 0.001;
    vec3 along = pathEnabled ? path / pathLength : normalize(uStreamWorld);
    vec3 across = uStreamAcross;
    vec3 depthAxis = uStreamDepth;
    if (gl_InstanceID < uBeadCount) {
        int chain = gl_InstanceID / uBeadsPerChain;
        int k = gl_InstanceID - chain * uBeadsPerChain;
        vec3 centre = uWorldCenter + uWorldHalf * (vec3(beadRandom(chain, 1u), beadRandom(chain, 2u),
                                                                     beadRandom(chain, 3u)) * 2.0 - 1.0);
        float scale = 1.0;
        vec4 sceneEntry = sceneInlet(beadRandom(chain, 31u),
                                     vec2(beadRandom(chain, 32u), beadRandom(chain, 33u)),
                                     along, uWorldCenter, uWorldHalf, uSceneFaces);
        float span = uSceneEmission == 1 ? sceneEntry.w
                   : (pathEnabled ? pathLength : 2.0 * length(uWorldHalf));
        float slot = (float(k) + 0.6 * beadRandom(chain * 977 + k, 4u)) / float(uBeadsPerChain);
        float progress = fract(slot + uBeadTravel * scale * mix(0.7, 1.3, beadRandom(chain, 5u)) / span);
        float s = progress * span;
        float phase = 6.2832 * beadRandom(chain, 6u);
        // The same free-chain shape, but travel now follows the authored finite Source -> End.
        float arc = sin(s / scale * 0.23 + phase + uBeadTravel * 0.025) * 0.09
                  + sin(s / scale * 0.45 + phase * 1.7) * 0.01;
        float pathWidth = min(uWorldHalf.x, uWorldHalf.z) * 0.28 * uParticleSpread;
        vec3 sourceLine = uSceneEmission == 1 ? sceneEntry.xyz + along * s
                        : (pathEnabled ? mix(uStreamSource, uStreamEnd, progress)
                                       : centre + along * (s - 0.5 * span));
        vec3 p = sourceLine
               + across * ((pathEnabled && uSceneEmission == 0) ? (beadRandom(chain, 1u) * 2.0 - 1.0) * pathWidth : 0.0)
               + depthAxis * ((pathEnabled && uSceneEmission == 0) ? (beadRandom(chain, 3u) * 2.0 - 1.0) * pathWidth : 0.0)
               + across * 1.15 * scale * (arc + (beadRandom(chain * 977 + k, 7u) - 0.5) * 0.035)
               + depthAxis * (beadRandom(chain * 977 + k, 8u) - 0.5) * 0.1 * scale;
        if (uBeadScatter > 0.0) {
            // A plume: each bead's own (Gaussian) place across and in depth, widening as the chain rises. Stable per
            // bead, so the plume flows rather than flickers.
            vec2 g = sqrt(-2.0 * log(max(beadRandom(chain * 977 + k, 25u), 1e-6)))
                   * vec2(cos(6.2832 * beadRandom(chain * 977 + k, 26u)), sin(6.2832 * beadRandom(chain * 977 + k, 26u)));
            float plume = uBeadScatter * 0.55 * scale * (0.2 + 0.8 * progress);
            p += across * g.x * plume + depthAxis * g.y * plume;
        }
        // A whole-chain lifetime, independent for each stable seed; both population changes and
        // cycling cohorts fade in and out, not jump through integer chain draw-count changes.
        float life = fract(uBeadTravel * 0.035 + beadRandom(chain, 24u));
        float lifetimeFade = smoothstep(0.0, 0.18, life) * (1.0 - smoothstep(0.82, 1.0, life));
        vOpacity = clamp(uChainFill - float(chain), 0.0, 1.0) * lifetimeFade * uChainActivity;
        float size = mix(0.014, 0.040, beadRandom(chain, 9u)) * uBeadSize;
        float px = size * pow(mix(0.3, 1.4, beadRandom(chain * 977 + k, 10u)), 1.5)
                 * (beadRandom(chain * 977 + k, 11u) > 0.94 ? 2.4 : 1.0);
        if (uSceneEmission == 1) {
            vOpacity *= scenePathFade(p, uWorldCenter, uWorldHalf, s, span, px);
        } else {
            float ends = smoothstep(0.0, 0.10, progress) * (1.0 - smoothstep(0.84, 1.0, progress));
            vec3 edge = abs((p - uWorldCenter) / uWorldHalf);
            float boundary = 1.0 - smoothstep(0.9, 1.0, max(edge.x, max(edge.y, edge.z)));
            vOpacity *= ends * boundary;
        }
        aSphere = vec4(p, px);
        aExtra = vec2(beadRandom(chain * 977 + k, 12u), 3.0); // stable environment-lit micro-glass
        return;
    }
    if (gl_InstanceID >= uBeadCount + uSnowCount) {
        // Fizz: a wake of tiny bubbles streaming off behind each bubble (against the stream), widening as it falls
        // behind and flowing back along it with the water's travel.
        int f = gl_InstanceID - uBeadCount - uSnowCount;
        if (uFizzPer <= 0) { aSphere = vec4(0.0); aExtra = vec2(0.0); vOpacity = 0.0; return; }
        int owner = f / uFizzPer;
        int k = f - owner * uFizzPer;
        if (owner >= uWakeCount) { aSphere = vec4(0.0); aExtra = vec2(0.0); vOpacity = 0.0; return; }
        // Stable emitter records survive a parent popping, fusing, leaving or changing shell-array slot.
        vec3 centre = vec3(ebWake[owner * WAKE_STRIDE], ebWake[owner * WAKE_STRIDE + 1], ebWake[owner * WAKE_STRIDE + 2]);
        float r = ebWake[owner * WAKE_STRIDE + 3];
        int seed = int(uint(ebWake[owner * WAKE_STRIDE + 4]) * 131u + uint(k));
        float retirement = ebWake[owner * WAKE_STRIDE + 5]; // -1 live, 0..1 dissolving from front to back
        float sourceAlpha = ebWake[owner * WAKE_STRIDE + 6];
        float nominalRadius = ebWake[owner * WAKE_STRIDE + 7];
        vec3 view = uWorldToView * (centre - uEye);
        float pixels = r / (uPixel * max(-view.z, 0.1));
        // Larger bubbles shed a fuller wake; giants and specks none.
        float share = clamp((r - 0.08) / 0.5, 0.0, 1.0);
        float population = 1.0 - smoothstep(0.30 + 0.65 * share, 0.40 + 0.65 * share, beadRandom(seed, 18u));
        // Parent reaction moves the attachment point, not the whole trail's size/shape.
        float reach = nominalRadius * 9.0;
        float along_ = pow(fract(beadRandom(seed, 19u) + uBeadTravel * 0.05 / max(reach, 1e-3)), 0.7) * reach;
        float spread = nominalRadius * (0.15 + along_ / reach * 0.8);
        vec2 g = sqrt(-2.0 * log(max(beadRandom(seed, 20u), 1e-6))) * vec2(cos(6.2832 * beadRandom(seed, 21u)),
                                                                         sin(6.2832 * beadRandom(seed, 21u)));
        vec3 p = centre - along * (r + along_) + across * (g.x * spread + sin(along_ / nominalRadius) * nominalRadius * 0.3)
               + depthAxis * g.y * spread * 0.6;
        bool trailed = ebWake[owner * WAKE_STRIDE + 8] > 0.5;
        vec4 shape = vec4(trailed ? 1.0 : 0.0, 0.0, 0.0, 0.0);
        float trailEnds = 1.0;
        if (trailed) {
            // Inside its veil: microbubbles left in the water. Each stays where it was left (drifting only with the
            // water) while its bubble moves away; once the trail has left it behind, it is born again at the bubble.
            float span = float(WAKE_POINTS - 1);
            float water = wakeField(owner, WAKE_WATER);
            float c = fract(beadRandom(seed, 19u) + water / span) * span;      // spacings behind the bubble
            float reachNow = trailReach(owner);
            float st = c / span;
            along_ = st * reach;
            vec3 tangent = trailWater(owner, c + 0.2) - trailWater(owner, max(c - 0.2, 0.0));
            tangent = dot(tangent, tangent) > 1e-10 ? normalize(tangent) : vec3(0.0, -1.0, 0.0);
            vec3 axis = normalize(mix(vec3(0.0, 0.0, 1.0), vec3(1.0, 0.0, 0.0), smoothstep(0.75, 0.95, abs(tangent.z))));
            vec3 side = normalize(cross(tangent, axis));
            vec3 deep = cross(tangent, side);
            float body = wakeField(owner, WAKE_RADIUS);
            p = trailWater(owner, c) + (side * g.x + deep * g.y * 0.7) * mix(body * 0.45, nominalRadius * 0.12, sqrt(st));
            // Born at the bubble, gone where the trail ends (or before the trail has reached it).
            // Born at the bubble; thinning with the sheet down the trail (gone before the trail has reached it).
            trailEnds = smoothstep(0.0, 0.4, c) * (1.0 - smoothstep(TRAIL_FADE * reachNow, reachNow, c));
        }
        float size = nominalRadius * mix(0.04, 0.08, beadRandom(seed, 22u))
                   * uBeadSize * (1.0 - 0.5 * along_ / reach);
        // A trail's stream reads as glass beads (the goals' columns): larger, with a few larger still.
        if (shape.x > 0.5) size *= mix(1.6, 2.6, beadRandom(seed, 27u)) * (beadRandom(seed, 28u) > 0.9 ? 1.6 : 1.0);
        // Front = near the former source (along_/reach = 0). The dissolve walks down the remaining tail.
        float tail = along_ / reach;
        float ends = trailed ? trailEnds : smoothstep(0.0, 0.08, tail) * (1.0 - smoothstep(0.85, 1.0, tail));
        float headToTail = retirement < 0.0 ? 1.0
                         : smoothstep(retirement - 0.08, retirement + 0.12, tail);
        float fill = shape.x > 0.5 ? max(uFizzFill, uTrailFizz) : uFizzFill;
        // A trail's own stream is dense from the bubble back (the goals' bead columns), whoever its size.
        float streamed = shape.x > 0.5 ? max(population, 0.85) : population;
        vOpacity = sourceAlpha * ends * headToTail * streamed * clamp(fill - float(k), 0.0, 1.0);
        // Keep even the half-pixel raster footprint strictly below the fading parent's.
        // A tiny/transparent parent cannot acquire equal-sized beads during birth or retirement.
        float parentPixels = pixels;
        float beadPixels = max(size / (uPixel * max(-(uWorldToView * (p - uEye)).z, 0.1)), 0.5);
        float parentGuard = smoothstep(1.05, 1.4, parentPixels / beadPixels);
        vOpacity *= parentGuard;
        if (size >= r) { size = 0.0; vOpacity = 0.0; }
        aSphere = vec4(p, size);
        aExtra = vec2(beadRandom(seed, 23u), 3.0); // micro-glass, same medium and lighting, stable sparkle
        return;
    }
    // Free marine snow: the same source/exit volume as bubbles, chains and
    // decorative specks. Stable seeds recycle ONLY through zero-opacity ends.
    // Attached fizz above deliberately remains sourced at its stable parent.
    int i = gl_InstanceID - uBeadCount;
    vOpacity = clamp(uSnowFill - float(i), 0.0, 1.0);
    vec3 seed = vec3(beadRandom(i, 13u), beadRandom(i, 14u), beadRandom(i, 15u));
    vec3 p;
    if (uSceneEmission == 1) {
        vec4 sceneEntry = sceneInlet(beadRandom(i, 34u), seed.xz, along, uWorldCenter, uWorldHalf, uSceneFaces);
        float progress = fract(seed.y + uSnowDrift / sceneEntry.w);
        p = sceneEntry.xyz + along * (progress * sceneEntry.w);
        vOpacity *= scenePathFade(p, uWorldCenter, uWorldHalf, progress * sceneEntry.w, sceneEntry.w, 0.005);
    } else if (pathEnabled) {
        float progress = fract(seed.y + uSnowDrift / pathLength);
        float width = min(uWorldHalf.x, uWorldHalf.z) * 0.46 * uParticleSpread;
        p = mix(uStreamSource, uStreamEnd, progress)
          + across * (seed.x * 2.0 - 1.0) * width
          + depthAxis * (seed.z * 2.0 - 1.0) * width;
        vOpacity *= smoothstep(0.0, 0.14, progress)
                  * (1.0 - smoothstep(0.82, 1.0, progress));
    } else {
        // Retains the original contract for old native bead diagnostic tests.
        vec3 at = fract(seed + along * uSnowDrift / (2.0 * uWorldHalf));
        p = uWorldCenter + (at * 2.0 - 1.0) * uWorldHalf;
    }
    if (uSceneEmission != 1) {
        vec3 edge = abs((p - uWorldCenter) / uWorldHalf);
        vOpacity *= 1.0 - smoothstep(0.9, 1.0, max(edge.x, max(edge.y, edge.z)));
    }
    aSphere = vec4(p, 0.005);
    aLensRadius = aSphere.w;
    aExtra = vec2(beadRandom(i, 17u), 1.0);
}
"""
_ATTRIBUTES = """layout(location=0) in vec4 aSphere;   // world centre, radius
layout(location=1) in vec2 aExtra;    // seed, kind (0 bubble, 1 snow)
layout(location=2) in float aOpacity; // logical lifetime, independent of physical radius
layout(location=3) in float aLensRadius; // steady (nominal) radius for the lens: breathing never refocuses
"""
assert BUBBLE_VERTEX.count(_ATTRIBUTES) == 1 and BUBBLE_VERTEX.count("void main() {\n") == 1
_SPECK_GLSL = """// Particulate in the same fixed water domain, with seeded stream-aligned clouds.
uniform vec3 uStreamWorld;     // the stream's unit direction in the world
uniform vec3 uStreamAcross;
uniform vec3 uWorldCenter;
uniform vec3 uWorldHalf;
uniform float uWorldUnit;
uniform float uSpeckTravel;    // integrated physical travel at 30% of the bubble stream
uniform float uParticleSpread; // transverse width only; no change to music, lifetime or speed
uniform int uSceneEmission; // world-wide boundary inlet when SCENE
uniform vec3 uSceneFaces;    // physically valid face areas selected by Source
uniform vec3 uSpeckSource;       // world source of seeded particulate paths
uniform vec3 uSpeckEnd;          // world end and fade-out region
uniform float uWarmShare;      // share lit in the particle colour
uniform vec3 uClouds;          // cloud contrast, floor, glow
uniform float uBandFreq;
uniform float uBandGather;      // SCENE: 0 the bands vary the field's glow .. 1 they gather the specks themselves
uniform float uSpeckSize;
vec4 aPoint;
vec4 aLook;
uint speckHash(uint x) {
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
    return x;
}
float speckRandom(int index, uint salt) {
    return float(speckHash(uint(index) * 0x9e3779b9u ^ salt * 0x85ebca6bu) & 0xffffffu) / 16777215.0;
}
vec2 speckGauss(int index, uint salt) {
    float r = sqrt(-2.0 * log(max(speckRandom(index, salt), 1e-7)));
    float a = 6.2831853 * speckRandom(index, salt + 1u);
    return r * vec2(cos(a), sin(a));
}
void speckInstance() {
    int i = gl_InstanceID;
    vec3 seed = vec3(speckRandom(i,1u),speckRandom(i,3u),speckRandom(i,5u));
    vec3 anchor = (seed * 2.0 - 1.0) * uWorldHalf;
    vec3 along = uStreamWorld;
    vec3 across = uStreamAcross;
    float a = dot(anchor, across) / uWorldUnit, b = dot(anchor, along) / uWorldUnit;
    float phase = a * uBandFreq + 1.4 * sin(b * 2.3 + a * 3.0) + 0.8 * sin(b * 5.1 - a * 7.0);
    float clouds = pow(clamp(0.5 + 0.5 * sin(phase), 0.0, 1.0), uClouds.x);
    // BEAM retains its authored, cloud-shaped particle bands. SCENE's whole-
    // face inlet must not turn into a few isolated patches merely because the
    // old BEAM cloud rejection mask drops whole instances. In SCENE the same
    // authored band variation modulates light, not spatial admission; a stable
    // deterministic threshold bounds speck work without camera-dependent births.
    float sceneKeep = clamp(uClouds.y + 0.45 * uClouds.z, 0.35, 0.9);
    // Band Gathering asks for exactly those patches: the diagonal bands with dark water between them (lab, sixth
    // mock), gathering the specks into the clouds as BEAM does.
    bool kept = speckRandom(i, 6u) < (uSceneEmission == 1 ? mix(sceneKeep, uClouds.y + 0.88 * clouds, uBandGather)
                                                         : uClouds.y + 0.88 * clouds);
    // Along the exact Stream Source -> End path. Cohorts recycle *after* fading
    // at End and *before* fading in at Source, avoiding static midpoint debris.
    vec3 path = uSpeckEnd - uSpeckSource;
    float lengthPath = max(length(path), 0.001);
    vec3 pathDir = path / lengthPath;
    vec3 side = normalize(abs(pathDir.y) < 0.9 ? cross(pathDir, vec3(0.0, 1.0, 0.0))
                                                   : cross(pathDir, vec3(0.0, 0.0, 1.0)));
    vec3 depthAxis = normalize(cross(pathDir, side));
    vec4 sceneEntry = sceneInlet(speckRandom(i, 23u), seed.xz, pathDir,
                                  uWorldCenter, uWorldHalf, uSceneFaces);
    float progress = fract(seed.y + uSpeckTravel /
                           (uSceneEmission == 1 ? sceneEntry.w : lengthPath));
    float sideWidth = min(uWorldHalf.x, uWorldHalf.z) * 0.52 * uParticleSpread;
    vec3 p = uSceneEmission == 1 ? sceneEntry.xyz + pathDir * (progress * sceneEntry.w)
             : mix(uSpeckSource, uSpeckEnd, progress)
               + side * (seed.x * 2.0 - 1.0) * sideWidth
               + depthAxis * (seed.z * 2.0 - 1.0) * sideWidth;
    float radius = pow(mix(0.25, 1.1, speckRandom(i, 8u)), 1.3) * 0.025 * uSpeckSize;
    float ends;
    if (uSceneEmission == 1) {
        ends = scenePathFade(p, uWorldCenter, uWorldHalf, progress * sceneEntry.w, sceneEntry.w,
                             radius * uParticleRadiusShare);
    } else {
        vec3 edge = abs((p - uWorldCenter) / uWorldHalf);
        float boundsFade = 1.0 - smoothstep(0.88, 1.0, max(edge.x, max(edge.y,edge.z)));
        ends = smoothstep(0.00, 0.12, progress)
             * (1.0 - smoothstep(0.82, 1.0, progress)) * boundsFade;
    }
    float cloudLight = uSceneEmission == 1 ?
        (0.35 + uClouds.z * (0.45 + 0.55 * clouds)) : (0.35 + uClouds.z * clouds);
    float bright = exp(0.7 * speckGauss(i, 9u).x) * cloudLight * ends;
    aPoint = vec4(p, kept ? radius : 0.0);
    aLook = vec4(kept ? bright : 0.0, speckRandom(i, 11u) < uWarmShare ? 1.0 : 0.0, speckRandom(i, 12u), 0.0);
}
"""
_SPECK_ATTRIBUTES = """layout(location=0) in vec4 aPoint;   // fixed world position, world radius
layout(location=1) in vec4 aLook;    // brightness, warm (lit in the light's colour) or neutral, seed, unused
"""
assert PARTICLE_VERTEX.count(_SPECK_ATTRIBUTES) == 1 and PARTICLE_VERTEX.count("void main() {\n") == 1
# The procedural particulate's vertex stage: the particle vertex stage with its per-instance attributes generated.
SPECK_VERTEX = (PARTICLE_VERTEX.replace(_SPECK_ATTRIBUTES, "")
                .replace("void main() {\n", _SCENE_INLET_GLSL + _SPECK_GLSL + "void main() {\n    speckInstance();\n"))
BEAD_VERTEX = (BUBBLE_VERTEX.replace(_ATTRIBUTES, "")
               .replace("void main() {\n    vOpacity = aOpacity;\n",
               _SCENE_INLET_GLSL + _BEAD_GLSL + "void main() {\n    vOpacity = 1.0;\n    beadInstance();\n"))

TRAIL_SEGMENTS = 40
TRAIL_VERTEX = """#version 460 core
uniform mat3 uWorldToView;
uniform vec3 uEye;
uniform mat4 uProjection;
uniform float uPixel;         // view units per pixel at unit distance
uniform float uFocus;         // the bubbles' near defocus (shared): a blurred bubble trails a blurred wake
uniform float uAperture;
uniform float uNearCoc;
uniform float uNearMax;
""" + SCENE3D_SPHERES_GLSL + _WAKE_PATH_GLSL + """
const int SEGMENTS = """ + str(TRAIL_SEGMENTS) + """;
out vec2 vAcross;             // across the veil (-1..1), along it (0 at the bubble .. 1)
out float vDepth;
out float vWidthPx;           // the veil's half-width on screen here
out float vAlong;             // place in the water along the trail, in its bubble's radii (the strands stay put)
flat out float vBlur;         // its bubble's near-defocus circle (pixels)
out float vUnder;             // distance below the bubble's centre, in its radii (inside the bubble below 1)
out float vHalf;              // the sheet's half-width here, in its bubble's radii
flat out float vStrength;
flat out float vShapeSeed;
void main() {
    int owner = gl_InstanceID, base = owner * WAKE_STRIDE;
    float r = ebWake[base + 3], retirement = ebWake[base + 5], alpha = ebWake[base + 6], nominal = ebWake[base + 7];
    float trailed = ebWake[base + 8], spacing = wakeField(owner, WAKE_SPACING);
    float reachNow = trailReach(owner), trailLength = reachNow * spacing;
    float seed = trailHash(ebWake[base + 4] * 0.618034 + 0.17);
    float fade = retirement < 0.0 ? 1.0 : 1.0 - retirement;
    // A newborn trail grows out of its bubble as the bubble moves away (never popping in at full length).
    vStrength = trailed * alpha * fade * (0.7 + 0.3 * trailHash(seed * 7.1)) * min(1.0, uTrails * 1.5)
              * smoothstep(0.0, 2.0 * nominal, trailLength);
    vec3 bubble = uWorldToView * (vec3(ebWake[base], ebWake[base + 1], ebWake[base + 2]) - uEye);
    vBlur = min(sceneNearCircle(-bubble.z - r, uFocus, uAperture, uNearCoc), uNearMax);
    vShapeSeed = seed;
    int i = gl_VertexID >> 1;
    float sideSign = (gl_VertexID & 1) == 0 ? -1.0 : 1.0;
    float s = float(i) / float(SEGMENTS);
    float c = s * reachNow;                                         // spacings behind the bubble
    float dc = max(0.02 * reachNow, 0.05);
    vec3 here = uWorldToView * (trailWater(owner, c) - uEye);
    vec3 next = uWorldToView * (trailWater(owner, min(c + dc, reachNow)) - uEye);
    vec3 previous = uWorldToView * (trailWater(owner, max(c - dc, 0.0)) - uEye);
    vec3 tangent = next - previous;
    tangent = dot(tangent, tangent) > 1e-12 ? normalize(tangent) : vec3(0.0, -1.0, 0.0);
    vec3 across = normalize(cross(tangent, normalize(-here)));
    // A sheet of disturbed water hanging from the bubble: its edges leave the bubble's widest point (its full width,
    // at its centre plane) and curve inward under it, then run on as a long, slowly narrowing sheet.
    float d = c * spacing / max(r, 1e-4);                           // distance down, in bubble radii (real)
    // At the bubble the edges meet its true outline: a sphere's perspective silhouette is wider than a sheet through
    // its centre by 1 / sqrt(1 - (r / D)^2) (a visible pixel gap on nearer bubbles otherwise).
    vec3 bubble_ = uWorldToView * (vec3(ebWake[base], ebWake[base + 1], ebWake[base + 2]) - uEye);
    float outline = inversesqrt(max(1.0 - r * r / max(dot(bubble_, bubble_), 1e-6), 0.05));
    // The root follows the bubble as it swells with the music; the body its size followed slowly.
    float body = mix(r, wakeField(owner, WAKE_RADIUS), smoothstep(0.5, 2.0, d));
    float width = body * (0.72 + 0.28 * exp(-0.6 * d * d)) * (1.0 - 0.45 * pow(s, 1.6))
                * mix(outline, 1.0, smoothstep(0.0, 1.5, d)) + nominal * 0.05 * smoothstep(0.0, 1.0, d);
    vUnder = d;
    vHalf = width / max(r, 1e-4);
    vWidthPx = width / (uPixel * max(-here.z, 0.1));
    vAcross = vec2(sideSign, s);
    vAlong = (wakeField(owner, WAKE_WATER) - c) * spacing / max(nominal, 1e-3);   // fixed in the water
    vDepth = -here.z;
    gl_Position = vStrength > 0.0 && here.z < -0.05
                ? uProjection * vec4(here + across * sideSign * width, 1.0) : vec4(2.0, 2.0, 2.0, 1.0);
}
"""
TRAIL_FRAGMENT = ("#version 460 core\n" + SCENE_OIT_GLSL + "layout(location=2) out vec4 Emission;\n"
                  + SCENE3D_SPHERES_GLSL + SCENE3D_OPTICS_GLSL + SCENE3D_WATER_GLSL + COMMON + """
uniform sampler2D uBackground;
uniform vec2 uTargetSize;
uniform float uTrailTime;
const float TRAIL_FADE = """ + str(TRAIL_FADE) + """;
in vec2 vAcross;
in float vDepth;
in float vWidthPx;
in float vAlong;
flat in float vBlur;
in float vUnder;
in float vHalf;
flat in float vStrength;
flat in float vShapeSeed;
void main() {
    // Interpolation overshoots the strip's ends by a hair: clamp before any pow (a negative base drew black pixels).
    float s = clamp(vAcross.y, 0.0, 1.0);
    float x = clamp(vAcross.x, -1.0, 1.0);
    float pixel = clamp(1.0 / max(vWidthPx, 1e-3), 1e-3, 1.0);       // one screen pixel, across the sheet
    float blur = clamp(vBlur / max(vWidthPx, 1e-3), 0.0, 1.0);         // its bubble's defocus, across the sheet
    float sharp = 1.0 / (1.0 + 0.5 * vBlur);                          // fine detail a defocused wake keeps
    // Whole from the bubble, thinning away toward the tail.
    // Thinning gently from under a third of the way down, over the whole rest of its length.
    float fade = smoothstep(0.0, 0.02, s) * (1.0 - smoothstep(TRAIL_FADE, 1.0, s));
    // A sheet of clear disturbed water with real edges: it ends crisply (antialiased to a pixel), never a blur.
    float body = 1.0 - smoothstep(1.0 - 1.5 * pixel - blur, 1.0, abs(x));
    // Its two walls, seen edge-on, catch the light as fine bright rims (the goals' glassy outlines).
    float rimWidth = max(1.4 * pixel + blur, 0.05);
    float rim = exp(-pow((1.0 - abs(x)) / rimWidth, 2.0)) * body * mix(1.0, sharp, 0.7);
    // Inside, the light the water focuses runs down it in fine strands (the caustic web drawn out along the flow):
    // they meander, fan apart down the trail, and come and go as the water carries them.
    vec2 q = vec2(x * (1.6 + 1.2 * s) + vShapeSeed * 9.0, vAlong * 0.16);
    float web = waterCaustics(vec2(q.x * 2.2, q.y), uTrailTime * 0.12 + vShapeSeed * 5.0);
    float strands = pow(web, 5.0) * body * sharp;
    float fine = 0.0;
    for (int k = 0; k < 2; ++k) {
        float warp = (skyNoise2(vec2(vAlong * 0.18 + float(k) * 7.1, vShapeSeed * 17.0 + float(k) * 3.0), 191u) - 0.5);
        float u = (x * (1.0 + 0.8 * s) + warp) * (2.5 + 2.0 * float(k)) + vShapeSeed * 5.0 + float(k) * 0.37;
        float line = 1.0 - smoothstep(0.0, 1.3, abs(fract(u) - 0.5) / max(fwidth(u), 1e-4));
        float presence = smoothstep(0.4, 0.8, skyNoise2(vec2(vAlong * 0.12,
                                                             floor(u) * 3.7 + vShapeSeed * 11.0 + float(k) * 19.0), 197u));
        // Every strand runs unbroken out of the bubble's underside, coming and going only farther down.
        presence = mix(1.0, presence, smoothstep(1.2, 3.0, vUnder));
        fine += line * presence * (0.6 - 0.2 * float(k));
    }
    fine *= body * smoothstep(0.85, 0.55, abs(x)) * sharp;
    // Narrower than a few pixels it is one fine thread: keep its rim, lose the inside.
    float resolved = smoothstep(2.0, 6.0, vWidthPx);
    // A wake spanning much of the frame (a big bubble right by the lens) reads only as stray lines across the view:
    // it fades out as it widens, as such bubbles themselves do.
    float strength = vStrength * fade * (1.0 - smoothstep(0.06, 0.16, vWidthPx / max(uTargetSize.y, 1.0)));
    // The water bends what lies behind it like a clear tube (strongest toward its sides).
    vec2 acrossScreen = vec2(dFdx(x), dFdy(x));
    acrossScreen = acrossScreen / max(length(acrossScreen), 1e-6);
    // Under the bubble's own lower half only the walls show (its sides running on into the sheet): the sheet's water,
    // its bend and its inside appear below the bubble, never as a milky fill or a seam across it.
    // The wake comes out of the bubble, not after it: its water and strands rise into the bubble's lower half (seen
    // through its glass), so no dark band of empty water separates the bubble's outline from its wake.
    // Hidden only where it lies inside the bubble's outline (no milky glass); in the crescent between the bubble's
    // curving lower outline and the sheet's straight edges the water shows, filling right up to the bubble's side (it
    // was hidden there too: a dark crescent, then a lone edge, read as a detached wake on larger bubbles).
    float fromCentre = length(vec2(x * vHalf, vUnder));              // radii from the bubble's centre
    float below = max(smoothstep(0.3, 0.9, vUnder), smoothstep(0.95, 1.08, fromCentre));
    // Where it leaves the bubble the disturbed water glows most: one luminous junction binds bubble and wake.
    float junction = exp(-pow((vUnder - 0.9) / 0.45, 2.0)) * body * (1.0 - 0.5 * abs(x));
    vec2 shift = acrossScreen * x * sqrt(max(1.0 - x * x, 0.0)) * min(vWidthPx * 0.18, 7.0) * strength * body * below;
    if (!(abs(shift.x) + abs(shift.y) < 1e4)) shift = vec2(0.0);
    vec3 bent = texture(uBackground, (gl_FragCoord.xy + shift) / uTargetSize).rgb;
    vec3 light = (mix(uSkyTint, uShaftColour, 0.5) * 1.4 + uLightColour * 0.2) * max(uLightStrength, 0.3);
    // Thin water's colour: cyan in the body, a violet cast toward its walls (the goals' iridescent edges).
    vec3 tint = mix(vec3(0.4, 0.82, 1.0), vec3(0.72, 0.55, 1.0), smoothstep(0.55, 1.0, abs(x)));
    float a = clamp(body * 0.12 * strength * below, 0.0, 0.4);
    // A soft luminous fill where it leaves the bubble (lit disturbed water), clearing down the trail.
    float fill = body * (0.03 + 0.14 * (1.0 - smoothstep(0.0, 0.5, s))) * mix(1.0, 0.6, abs(x));
    fill *= below;
    strands *= below;
    fine *= below;
    vec3 glow = light * tint * (rim * 1.1 + (strands * 1.2 + fine * 0.6 + fill + junction * 0.22) * resolved) * strength;
    sceneTransparent(bent * a + glow, a, vDepth);
    Emission = vec4(0.0);
}
""")

__all__ = [
    "BACKDROP_FRAGMENT",
    "BEAD_VERTEX",
    "BLUR_FRAGMENT",
    "BUBBLE_FRAGMENT",
    "BUBBLE_FRAGMENT_BODY",
    "BUBBLE_VERTEX",
    "CLUSTER_FRAGMENT",
    "CLUSTER_VERTEX",
    "COMMON",
    "FULL_VERTEX",
    "NEAR_FRAGMENT",
    "NEAR_CLUSTER_FRAGMENT",
    "PARTICLE_FRAGMENT",
    "PARTICLE_VERTEX",
    "SHADE_GLSL",
    "SHAFT_FRAGMENT",
    "SPECK_VERTEX",
    "SPECKS_GLSL",
    "TRAIL_FRAGMENT",
    "TRAIL_SEGMENTS",
    "TRAIL_VERTEX",
]
