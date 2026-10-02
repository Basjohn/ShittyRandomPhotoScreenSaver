"""Relief Rise: shaders and CPU mirrors (loaded only when Relief Rise renders).

A front sweeps across the picture. Where it passes, the surface rises as a relief of the old
picture's brightness, turns into a relief of the new picture's and settles flat on the new
picture: each point's local phase ``s`` (0 untouched, 1 settled) follows its rank along the
sweep; its height is ``RELIEF_HEIGHT * depth * sin(pi s)`` times the blended brightness, and
its colour crosses from old to new around the peak. Phases of exactly 0 and 1 are the
photographs exactly (flat, unlit), so both ends of the run are exact.

Heights come from the renderer-owned, mipmapped photo copies (``PhotoEnvironment``, both roles)
read at a blurred level, never from the lent photographs, so the relief is smooth at any grid
density. The shared material lights the relief (blended in by ``sin(pi s)``), and a contact
occlusion term darkens hollows: the height field around each point, sampled at a few
offsets, standing above it.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_GLSL, scene3d_grid_vertex_source

RELIEF_HEIGHT = 0.16
RELIEF_FRONT = 0.4            # the share of the sweep a point spends rising and settling
RELIEF_HEIGHT_LEVEL = 1.5     # mip level of the 512 px copies the heights are read at
RELIEF_OCCLUSION = 0.55


def relief_rank(uv: tuple[float, float], direction: tuple[float, float]) -> float:
    """Where the point lies along the sweep, 0 (first) to 1 (last); direction is item space, y down."""
    return 0.5 + ((uv[0] - 0.5) * direction[0] + (uv[1] - 0.5) * direction[1]) / (abs(direction[0]) + abs(direction[1]))


def relief_phase(progress: float, rank: float) -> float:
    """CPU mirror of ``reliefPhase``: 0 untouched, 1 settled on the new picture."""
    t = max(0.0, min(1.0, float(progress)))
    s = max(0.0, min(1.0, (t * (1.0 + RELIEF_FRONT) - rank) / RELIEF_FRONT))
    return s * s * (3.0 - 2.0 * s)


def relief_lift(phase: float) -> float:
    """How far from flat the point is: 0 at both ends of its phase."""
    return math.sin(math.pi * phase) if 0.0 < phase < 1.0 else 0.0


_COMMON = f"""
uniform vec2 uDirection;
uniform float uProgress;
uniform float uDepth;
uniform sampler2D uSourceHeights;
uniform sampler2D uDestinationHeights;
const float RELIEF_FRONT = {RELIEF_FRONT:.6f};
float reliefPhase(vec2 uv) {{
    float rank = 0.5 + dot(uv - 0.5, uDirection) / (abs(uDirection.x) + abs(uDirection.y));
    float s = clamp((uProgress * (1.0 + RELIEF_FRONT) - rank) / RELIEF_FRONT, 0.0, 1.0);
    return s * s * (3.0 - 2.0 * s);
}}
float reliefLift(float phase) {{
    return phase > 0.0 && phase < 1.0 ? sin(3.14159265 * phase) : 0.0;
}}
float reliefBrightness(sampler2D heights, vec2 uv) {{
    return dot(textureLod(heights, uv, {RELIEF_HEIGHT_LEVEL:.2f}).rgb, vec3(0.2126, 0.7152, 0.0722));
}}
// The relief's height at uv (world units, toward the viewer).
float reliefHeight(vec2 uv) {{
    float phase = reliefPhase(uv);
    float lift = reliefLift(phase);
    if (lift <= 0.0) return 0.0;
    float brightness = mix(reliefBrightness(uSourceHeights, uv), reliefBrightness(uDestinationHeights, uv),
                           smoothstep(0.3, 0.7, phase));
    return {RELIEF_HEIGHT:.6f} * uDepth * lift * brightness;
}}
"""

RELIEF_VERTEX_SOURCE = scene3d_grid_vertex_source(
    """
vec3 sceneDisplace(vec2 uv) {
    vec3 p = scenePlanePoint(uv, uItemSize.x / uItemSize.y);
    return vec3(p.xy, reliefHeight(uv));
}
""",
    _COMMON,
)

RELIEF_FRAGMENT_SOURCE = (
    "#version 460 core\n"
    "in vec2 vUv;\nin vec3 vWorld;\nin vec3 vNormal;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform float uGloss;\nuniform vec2 uItemSize;\n"
    + SCENE3D_GLSL + _COMMON
    + f"""
void main() {{
    float phase = reliefPhase(vUv);
    vec3 source = texture(uOldTex, vUv).rgb, destination = texture(uNewTex, vUv).rgb;
    if (phase <= 0.0 || phase >= 1.0) {{
        FragColor = vec4(phase <= 0.0 ? source : destination, 1.0);   // flat: the photograph exactly
        return;
    }}
    vec3 photo = mix(source, destination, smoothstep(0.3, 0.7, phase));
    float lift = reliefLift(phase);
    vec3 n = normalize(vNormal);
    SceneMaterial surface = SceneMaterial(photo, mix(0.8, 0.3, uGloss), 0.0, 0.5, vec3(0.0));
    vec3 lit = sceneMaterialLit(surface, n, vWorld, vec3(2.6), vec3(0.32))
             + uGloss * sceneMaterialEnvironment(uDestinationHeights, surface, n, vWorld);
    // Contact occlusion: how far the relief around stands above this point (hollows darken).
    float here = vWorld.z, above = 0.0;
    vec2 reach = vec2(0.012 * uItemSize.y / uItemSize.x, 0.012);
    for (int i = 0; i < 6; ++i) {{
        float angle = float(i) * 1.0471976;
        above += max(reliefHeight(vUv + vec2(cos(angle), sin(angle)) * reach) - here, 0.0);
    }}
    float occlusion = clamp(above / (6.0 * {RELIEF_HEIGHT:.6f} * max(uDepth, 1e-3)) * 4.0, 0.0, 1.0)
                    * {RELIEF_OCCLUSION:.6f};
    FragColor = vec4(mix(photo, lit * (1.0 - occlusion), lift), 1.0);
}}
"""
)
