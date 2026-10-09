"""Volumetric Dissolve: the old picture bursts into coloured particles and mist while the new one
resolves through it (loaded only when it renders).

A seeded release front sweeps the picture along the run's direction (or from the centre out),
roughened by smooth value noise on the exact integer lattice hash (R-94). Each cell of the old
picture is a particle. Until its release it is part of the intact picture; then it flies in 3D
toward the viewer through the shared pinhole camera: it drifts along the sweep, swirls, rises and
grows as it nears the camera, where it defocuses into a soft bokeh disc whose colour fades toward
the mist. About one particle in fifty is a larger flake that tumbles. Behind the front the new
picture resolves from a blurred copy of itself to sharp, through layers of luminous mist coloured
by a blurred copy of the old picture; the layers rush toward the viewer at different rates, which
gives the mist its depth.

Particles are a ``CompactedPopulation`` (live ones evaluated once each in compute, drawn with one
indirect draw in id order). The mist and the resolving picture are analytic in one full-picture
pass: no volume texture, simulation or extra target. Every release falls in [0.04, 0.55] and
every particle, mist band and blur has finished by 0.93, so both ends of the run are the
photographs exactly; at release a particle covers its own cell exactly, so the front has no seam.
The CPU mirrors below define the same schedule and flight for tests.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_CAMERA, SCENE3D_GLSL, Scene3DBlockLayout, scene3d_random

VOLUMETRIC_MAX_PARTICLES = 400_000
VOLUMETRIC_NOISE_SCALE = 4.0
VOLUMETRIC_VERTICES = 4
VOLUMETRIC_RELEASE_START = 0.04
VOLUMETRIC_RELEASE_SPAN = 0.49
VOLUMETRIC_RELEASE_JITTER = 0.02
VOLUMETRIC_LIFE = (0.30, 0.08)        # a particle's flight: base + seeded extra (run progress)
VOLUMETRIC_MIST_LIFE = 0.38
VOLUMETRIC_RESOLVE = 0.38
VOLUMETRIC_DEPTH_MAX = 1.55           # how far toward the camera a particle can fly (scene units)
VOLUMETRIC_FLAKE_SHARE = 0.02
VOLUMETRIC_FLAKE_SIZE = 4.5
VOLUMETRIC_NEAR_SHARE = 0.08          # particles that fly close and spread into large bokeh discs
VOLUMETRIC_NEAR_DEPTH = 2.6
VOLUMETRIC_GLINT_SHARE = 0.25         # particles that catch the light as they turn


def volumetric_grid(width: int, height: int, particle_size: int,
                    *, maximum: int = VOLUMETRIC_MAX_PARTICLES) -> tuple[int, int, int]:
    """(columns, rows, size): the particle grid over ``width`` x ``height`` device pixels, never over ``maximum``."""
    if width <= 0 or height <= 0:
        raise ValueError("Volumetric Dissolve requires a positive viewport")
    size = max(1, int(particle_size))
    while math.ceil(width / size) * math.ceil(height / size) > maximum:
        size += 1
    return math.ceil(width / size), math.ceil(height / size), size


def _lattice(ix: int, iy: int, seed: int) -> float:
    return scene3d_random((ix * 0x8DA6B343 ^ iy * 0xD8163841) & 0xFFFFFFFF, 7, seed)


def volumetric_noise(x: float, y: float, seed: int) -> float:
    """CPU mirror of ``volumeNoise``: smooth value noise in [0, 1] on the exact integer lattice."""
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _lattice(ix, iy, seed), _lattice(ix + 1, iy, seed)
    c, d = _lattice(ix, iy + 1, seed), _lattice(ix + 1, iy + 1, seed)
    return (a + (b - a) * sx) + ((c + (d - c) * sx) - (a + (b - a) * sx)) * sy


def volumetric_rank(cx: float, cy: float, direction: tuple[float, float], radial: bool, aspect: float) -> float:
    """Where the front reaches a point (0 first, 1 last), before noise: CPU mirror of ``volumeRank``."""
    if radial:
        far = math.hypot(0.5 * aspect, 0.5)
        return math.hypot((cx - 0.5) * aspect, cy - 0.5) / far
    return 0.5 + ((cx - 0.5) * direction[0] + (cy - 0.5) * direction[1]) / (abs(direction[0]) + abs(direction[1]))


def volumetric_release(particle: int, columns: int, rows: int, direction: tuple[float, float], radial: bool,
                       aspect: float, seed: int) -> float:
    """CPU mirror of ``volumeRelease``: when the particle leaves the picture (run progress)."""
    cx, cy = (particle % columns + 0.5) / columns, (particle // columns + 0.5) / rows
    noise = volumetric_noise(cx * VOLUMETRIC_NOISE_SCALE * aspect, cy * VOLUMETRIC_NOISE_SCALE, seed)
    front = max(0.0, min(1.0, volumetric_rank(cx, cy, direction, radial, aspect) + 0.24 * (noise - 0.5)))
    return (VOLUMETRIC_RELEASE_START + VOLUMETRIC_RELEASE_SPAN * front
            + VOLUMETRIC_RELEASE_JITTER * scene3d_random(particle, 1, seed))


def volumetric_life(particle: int, seed: int) -> float:
    """CPU mirror of ``volumeLife``: how long the particle flies (run progress)."""
    return VOLUMETRIC_LIFE[0] + VOLUMETRIC_LIFE[1] * scene3d_random(particle, 2, seed)


def volumetric_last_moment() -> float:
    """The latest progress at which anything still moves: every end is exact after it."""
    release = VOLUMETRIC_RELEASE_START + VOLUMETRIC_RELEASE_SPAN + VOLUMETRIC_RELEASE_JITTER
    return release + max(sum(VOLUMETRIC_LIFE), VOLUMETRIC_MIST_LIFE, VOLUMETRIC_RESOLVE)


# One frame's values for every pass, streamed once per frame. uDirection is the sweep in item space
# (y down), unit length; uRadial 1 sweeps from the centre out; uFrameSize the item's size.
VOLUMETRIC_FRAME_BLOCK = Scene3DBlockLayout.of("VolumetricFrame", (
    ("uGrid", "uvec2"), ("uDirection", "vec2"), ("uFrameSize", "vec2"), ("uProgress", "float"), ("uSeed", "uint"),
    ("uDepth", "float"), ("uMist", "float"), ("uRadial", "float"),
))

_COMMON_GLSL = SCENE3D_GLSL + VOLUMETRIC_FRAME_BLOCK.glsl() + f"""
const float RELEASE_START = {VOLUMETRIC_RELEASE_START:.6f};
const float RELEASE_SPAN = {VOLUMETRIC_RELEASE_SPAN:.6f};
const float RELEASE_JITTER = {VOLUMETRIC_RELEASE_JITTER:.6f};
const float MIST_LIFE = {VOLUMETRIC_MIST_LIFE:.6f};
const float RESOLVE = {VOLUMETRIC_RESOLVE:.6f};
const float DEPTH_MAX = {VOLUMETRIC_DEPTH_MAX:.6f};
const float FLAKE_SHARE = {VOLUMETRIC_FLAKE_SHARE:.6f};
const float FLAKE_SIZE = {VOLUMETRIC_FLAKE_SIZE:.6f};
const float NEAR_SHARE = {VOLUMETRIC_NEAR_SHARE:.6f};
const float NEAR_DEPTH = {VOLUMETRIC_NEAR_DEPTH:.6f};
const float GLINT_SHARE = {VOLUMETRIC_GLINT_SHARE:.6f};

float volumeLattice(int x, int y) {{
    return sceneRandom(uint(x) * 0x8DA6B343u ^ uint(y) * 0xD8163841u, 7u, uSeed);
}}
float volumeNoise(vec2 p) {{
    vec2 cell = floor(p), f = p - cell;
    int x = int(cell.x), y = int(cell.y);
    vec2 s = f * f * (3.0 - 2.0 * f);
    float a = volumeLattice(x, y), b = volumeLattice(x + 1, y), c = volumeLattice(x, y + 1), d = volumeLattice(x + 1, y + 1);
    float top = a + (b - a) * s.x;
    return top + ((c + (d - c) * s.x) - top) * s.y;
}}
float volumeAspect() {{ return uFrameSize.x / uFrameSize.y; }}
float volumeRank(vec2 c) {{
    if (uRadial > 0.5) {{
        vec2 off = (c - 0.5) * vec2(volumeAspect(), 1.0);
        return length(off) / length(vec2(0.5 * volumeAspect(), 0.5));
    }}
    return 0.5 + dot(c - 0.5, uDirection) / (abs(uDirection.x) + abs(uDirection.y));
}}
vec2 volumeCentre(uint id) {{
    return (vec2(id % uGrid.x, id / uGrid.x) + 0.5) / vec2(uGrid);
}}
float volumeReleaseAt(vec2 c, uint id) {{
    float noise = volumeNoise(c * vec2({VOLUMETRIC_NOISE_SCALE:.1f} * volumeAspect(), {VOLUMETRIC_NOISE_SCALE:.1f}));
    float front = clamp(volumeRank(c) + 0.24 * (noise - 0.5), 0.0, 1.0);
    return RELEASE_START + RELEASE_SPAN * front + RELEASE_JITTER * sceneRandom(id, 1u, uSeed);
}}
float volumeRelease(uint id) {{ return volumeReleaseAt(volumeCentre(id), id); }}
float volumeLife(uint id) {{
    return {VOLUMETRIC_LIFE[0]:.6f} + {VOLUMETRIC_LIFE[1]:.6f} * sceneRandom(id, 2u, uSeed);
}}
// The sweep's travel at a point (item space, y down): along the direction, or away from the centre.
vec2 volumeHeading(vec2 c) {{
    if (uRadial > 0.5) {{
        vec2 off = (c - 0.5) * vec2(volumeAspect(), 1.0);
        return dot(off, off) > 1e-8 ? normalize(off) : vec2(0.0, -1.0);
    }}
    return uDirection;
}}

struct Particle {{ vec2 pixel; float size; float alpha; float defocus; float spin; float flake; float age; float glint; }};

// A released particle at its flight age s: scene point drifted along the sweep, swirled, lifted and
// flown toward the camera, projected through the shared camera. At s = 0 it is its cell exactly.
Particle volumeParticle(uint id, float s) {{
    Particle p;
    vec2 c = volumeCentre(id);
    float aspect = volumeAspect();
    vec2 heading = volumeHeading(c);
    float strength = 0.55 + 0.9 * sceneRandom(id, 3u, uSeed);
    float swirl = sin(6.2831853 * (sceneRandom(id, 4u, uSeed) + s * (0.6 + sceneRandom(id, 5u, uSeed))));
    vec2 drift = heading * (0.10 * s + 0.32 * s * s) * strength
               + vec2(-heading.y, heading.x) * swirl * 0.05 * s
               + vec2(0.0, -0.10 * s * s * sceneRandom(id, 6u, uSeed));       // item space, y down
    vec3 world = scenePlanePoint(c + drift, aspect);
    p.flake = sceneRandom(id, 9u, uSeed) < FLAKE_SHARE ? 1.0 : 0.0;
    float near = p.flake < 0.5 && sceneRandom(id, 12u, uSeed) < NEAR_SHARE ? 1.0 : 0.0;
    world.z = mix(DEPTH_MAX, NEAR_DEPTH, near) * uDepth * pow(s, 1.3) * (0.35 + 0.65 * sceneRandom(id, 8u, uSeed));
    float scale = SCENE_CAMERA / max(SCENE_CAMERA - world.z, SCENE_NEAR);
    float grow = mix(1.0, FLAKE_SIZE, p.flake * smoothstep(0.0, 0.25, s));
    p.pixel = scenePlaneUv(world.xy * scale, aspect) * uFrameSize;
    p.size = scale * grow * (1.0 - 0.35 * s * (1.0 - p.flake));
    p.defocus = clamp(world.z / max(DEPTH_MAX * 0.75, 1e-4), 0.0, 1.0) * (1.0 - 0.6 * p.flake);
    p.alpha = 1.0 - smoothstep(0.55, 1.0, s);
    p.spin = 6.2831853 * s * (0.5 + sceneRandom(id, 10u, uSeed)) * (sceneRandom(id, 11u, uSeed) < 0.5 ? -1.0 : 1.0);
    p.age = s;
    // A glinting particle flashes as it turns to the light: a few soft flashes over its flight.
    float glints = sceneRandom(id, 13u, uSeed) < GLINT_SHARE ? 1.0 : 0.0;
    p.glint = glints * pow(max(sin(6.2831853 * (sceneRandom(id, 14u, uSeed) + s * (1.5 + 2.0 * sceneRandom(id, 15u, uSeed)))), 0.0), 6.0);
    return p;
}}
"""

# Population hooks: a particle is live from its release for its life; its state is (item-pixel
# centre, size relative to its cell, opacity). The draw recomputes the rest from its id.
VOLUMETRIC_HOOKS = _COMMON_GLSL + """
bool populationActive(uint id) {
    float release = volumeRelease(id);
    return uProgress >= release && uProgress < release + volumeLife(id);
}
vec4 populationState(uint id) {
    Particle p = volumeParticle(id, clamp((uProgress - volumeRelease(id)) / volumeLife(id), 0.0, 1.0));
    return vec4(p.pixel, p.size, p.alpha);
}
"""

# The intact old picture ahead of the front; behind it the new picture resolving from its blurred
# copy to sharp through luminous parallax mist coloured by the old picture's blurred copy.
VOLUMETRIC_BACKDROP_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform sampler2D uNewCopy;\nuniform sampler2D uOldCopy;\n"
    + _COMMON_GLSL + """
float volumeMist(vec2 uv, float age) {
    if (age <= 0.0 || age >= 1.0) return 0.0;
    float band = pow(sin(3.14159265 * age), 1.5);
    float density = 0.0;
    for (int k = 0; k < 3; ++k) {
        float layer = float(k);
        // Each layer rushes toward the viewer at its own rate and rises: parallax depth.
        vec2 q = (uv - 0.5) / (1.0 + (0.18 + 0.22 * layer) * age) + 0.5 - vec2(0.0, (0.03 + 0.03 * layer) * age);
        float scale = 3.0 + 2.6 * layer;
        float n = volumeNoise(q * vec2(scale * volumeAspect(), scale) + vec2(17.0 * layer, 5.0 * layer));
        density += (0.55 - 0.12 * layer) * smoothstep(0.32, 0.85, n);
    }
    return clamp(band * density, 0.0, 1.0);
}
void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    uvec2 cell = min(uvec2(uv * vec2(uGrid)), uGrid - 1u);
    uint id = cell.y * uGrid.x + cell.x;
    float release = volumeRelease(id);
    if (uProgress < release) {
        FragColor = vec4(texture(uOldTex, uv).rgb, 1.0);
        return;
    }
    float since = uProgress - release;
    float haze = 1.0 - smoothstep(0.0, RESOLVE, since);
    vec3 sharp = texture(uNewTex, uv).rgb;
    vec3 colour = haze > 0.0 ? mix(sharp, textureLod(uNewCopy, uv, 1.0 + 4.0 * haze).rgb, haze) : sharp;
    float mist = volumeMist(uv, since / MIST_LIFE) * uMist;
    if (mist > 0.0) {
        vec3 tint = textureLod(uOldCopy, uv + vec2(0.0, 0.02), 3.5).rgb;
        vec3 glow = clamp(mix(tint * 1.4, vec3(1.0), 0.45), 0.0, 1.0);
        colour = 1.0 - (1.0 - colour) * (1.0 - glow * min(1.0, 1.1 * mist));   // screen: light, never a grey veil
    }
    // A thin luminous edge where the front has just passed (hidden under the leaving particles).
    colour += vec3(0.30) * exp(-pow(since / 0.012, 2.0)) * uMist;
    FragColor = vec4(colour, 1.0);
}
"""
)


def _draw_vertex() -> str:
    from rendering.quick.scene3d.population import POPULATION_DRAW_GLSL   # loaded with this module, when it renders

    return ("#version 460 core\n" + POPULATION_DRAW_GLSL + "uniform mat4 uMatrix;\nuniform vec2 uItemSize;\n"
            + _COMMON_GLSL + """
out vec2 vUv;
out vec2 vQuad;
out float vAlpha;
out float vDefocus;
out float vRound;
out float vFlake;
out float vShade;
out float vAge;
out float vGlint;
void main() {
    uint id = populationIds[gl_InstanceID];
    vec4 state = populationStates[gl_InstanceID];
    Particle p = volumeParticle(id, clamp((uProgress - volumeRelease(id)) / volumeLife(id), 0.0, 1.0));
    vec2 corner = vec2(gl_VertexID & 1, gl_VertexID >> 1);
    vec2 cellPixels = uItemSize / vec2(uGrid);
    // A defocused particle spreads over a larger disc; a flake tumbles (one axis foreshortened).
    float spread = 1.0 + 4.0 * p.defocus * p.defocus + 1.0 * p.defocus;
    vec2 local = (corner - 0.5) * cellPixels * state.z * spread;
    float tumble = p.flake > 0.5 ? abs(cos(1.7 * p.spin)) * 0.85 + 0.15 : 1.0;
    local.y *= tumble;
    float c = cos(p.spin * p.flake), s = sin(p.spin * p.flake);
    local = vec2(c * local.x - s * local.y, s * local.x + c * local.y);
    vec2 pixel = state.xy + local;
    // The particle's own cell of the old picture (a flake carries a larger patch of it).
    vec2 reach = (corner - 0.5) * mix(1.0, FLAKE_SIZE, p.flake);
    vUv = volumeCentre(id) + reach / vec2(uGrid);
    vQuad = (corner - 0.5) * 2.0 * spread;
    vAlpha = state.w;
    vDefocus = p.defocus;
    vRound = smoothstep(0.0, 0.12, p.age) * (1.0 - p.flake);
    vFlake = p.flake;
    vShade = 0.75 + 0.45 * tumble;
    vAge = p.age;
    vGlint = p.glint;
    gl_Position = uMatrix * vec4(pixel, 0.0, 1.0);
}
""")


VOLUMETRIC_PARTICLE_VERTEX_SOURCE = _draw_vertex()
VOLUMETRIC_PARTICLE_FRAGMENT_SOURCE = (
    "#version 460 core\n"
    "in vec2 vUv;\nin vec2 vQuad;\nin float vAlpha;\nin float vDefocus;\nin float vRound;\nin float vFlake;\n"
    "in float vShade;\nin float vAge;\nin float vGlint;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uOldCopy;\n" + """
void main() {
    // At release a particle is its square cell exactly; it rounds into a disc as it flies, and
    // a defocused one is a soft bokeh disc whose light spreads (fainter per pixel).
    float spread = 1.0 + 4.0 * vDefocus * vDefocus + 1.0 * vDefocus;
    float soft = 0.08 + 0.85 * vDefocus;
    vec2 q = vQuad / spread;                          // the quad in [-1, 1]
    float disc = 1.0 - smoothstep(1.0 - soft, 1.0, length(q));
    // A flake is a petal: pointed at both ends, widest in the middle, a soft rim.
    float petal = 1.0 - smoothstep(-0.06, 0.02, abs(q.y) - 0.62 * (1.0 - q.x * q.x));
    float roundness = vFlake > 0.5 ? 0.0 : max(vRound, vDefocus);
    float coverage = vFlake > 0.5 ? mix(1.0, petal, smoothstep(0.0, 0.2, vAge)) : mix(1.0, disc, roundness);
    // Bokeh spreads its light: fainter per pixel the larger it grows.
    float alpha = vAlpha * coverage / (1.0 + 0.9 * (spread * spread - 1.0));
    vec3 colour = texture(uOldTex, clamp(vUv, 0.0, 1.0)).rgb;
    // Flying particles brighten into the mist's light (the old picture's blur, lifted toward white).
    vec3 light = clamp(mix(textureLod(uOldCopy, clamp(vUv, 0.0, 1.0), 3.0).rgb * 1.4, vec3(1.0), 0.45), 0.0, 1.0);
    float lift = smoothstep(0.0, 0.5, vAge) * (1.0 - 0.6 * vFlake);   // petals keep the picture's colour
    colour = mix(colour, light, 0.6 * lift);
    colour *= mix(1.0, vShade, vFlake);
    // Emitted light rides on top of the premultiplied colour (it adds light, not coverage): a soft
    // glow as the particle flies and its glints.
    vec3 emit = light * (0.35 * lift + 1.6 * vGlint) * (1.0 - 0.6 * vDefocus);
    FragColor = vec4((colour + emit) * alpha, alpha);   // premultiplied, blended over
}
"""
)
