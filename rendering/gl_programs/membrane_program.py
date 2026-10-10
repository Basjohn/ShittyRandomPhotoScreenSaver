"""Membrane Turnover: shaders and CPU mirrors (loaded only when Membrane Turnover renders).

The old picture is printed on a taut, glossy membrane lying over the new one. A broad twist
travels across it: each cross-section across the sweep turns over about the sweep's axis
(``sheetTwist``, rendering/gl_programs/sheet_fold.py), rising off the picture as it turns, so
the membrane twists like a ribbon, stretching between cross-sections that have turned by
different amounts, while a gentle billow and a wandering axis keep it alive. Turned past its
edge-on moment it shows its back: the same print seen through a thin, translucent sheet that
fades as it lands, leaving the new picture. Lighting (the shared material, a Fresnel sheen and
reflections of the new picture through its renderer-owned copy) is blended in by how far each
part has turned, so the flat sheet at the start is the photograph exactly; every part has landed
and vanished by ``MEMBRANE_DONE``.
"""

from __future__ import annotations

import math

from rendering.gl_programs.refraction import REFRACTION_GLSL
from rendering.gl_programs.scene3d import SCENE3D_GLSL, scene3d_grid_vertex_source
from rendering.gl_programs.sheet_fold import SHEET_SIDES_GLSL, SHEET_TWIST_GLSL

MEMBRANE_FRONT = 0.55        # the share of the sweep a cross-section spends turning
MEMBRANE_DONE = 0.92         # the run's share by which every cross-section has landed and faded
MEMBRANE_BILLOW = 0.05
MEMBRANE_WANDER = 0.08
MEMBRANE_BACK = 0.72         # opacity of the turned membrane's back before it fades


def membrane_rank(point: tuple[float, float], sweep: tuple[float, float], aspect: float) -> float:
    """Where a picture point (picture heights, centred, y up) lies along the sweep, 0 first to 1 last."""
    reach = 0.5 * aspect * abs(sweep[0]) + 0.5 * abs(sweep[1])
    return 0.5 + (point[0] * sweep[0] + point[1] * sweep[1]) / (2.0 * reach)


def membrane_phase(progress: float, rank: float) -> float:
    """CPU mirror of ``membranePhase``: 0 untouched, 1 turned over and landed."""
    t = max(0.0, min(1.0, float(progress) / MEMBRANE_DONE))
    s = max(0.0, min(1.0, (t * (1.0 + MEMBRANE_FRONT) - rank) / MEMBRANE_FRONT))
    return s * s * (3.0 - 2.0 * s)


def membrane_back_opacity(phase: float) -> float:
    """How opaque the turned membrane's back is: fading to nothing as it lands."""
    x = max(0.0, min(1.0, (phase - 0.6) / 0.4))
    return MEMBRANE_BACK * (1.0 - x * x * (3.0 - 2.0 * x))


_COMMON = f"""
uniform vec2 uSweep;
uniform float uProgress;
uniform float uSpin;
uniform float uSeed;
const float MEMBRANE_FRONT = {MEMBRANE_FRONT:.6f};
const float MEMBRANE_DONE = {MEMBRANE_DONE:.6f};
float membraneRank(vec2 p, float aspect) {{
    float reach = 0.5 * aspect * abs(uSweep.x) + 0.5 * abs(uSweep.y);
    return 0.5 + dot(p, uSweep) / (2.0 * reach);
}}
float membranePhase(vec2 p, float aspect) {{
    float t = clamp(uProgress / MEMBRANE_DONE, 0.0, 1.0);
    float s = clamp((t * (1.0 + MEMBRANE_FRONT) - membraneRank(p, aspect)) / MEMBRANE_FRONT, 0.0, 1.0);
    return s * s * (3.0 - 2.0 * s);
}}
"""

MEMBRANE_VERTEX_SOURCE = scene3d_grid_vertex_source(
    f"""
vec3 sceneDisplace(vec2 uv) {{
    float aspect = uItemSize.x / uItemSize.y;
    vec3 p = scenePlanePoint(uv, aspect);
    float s = membranePhase(p.xy, aspect);
    if (s <= 0.0) return p;
    // The twist turns about the sweep's axis; uSpin picks which edge comes forward.
    vec2 axis = uSweep * uSpin;
    vec2 across = vec2(-axis.y, axis.x);
    float along = dot(p.xy, axis), off = dot(p.xy, across);
    float halfWidth = 0.5 * aspect * abs(across.x) + 0.5 * abs(across.y);
    float life = sin(3.14159265 * s);
    vec2 pivot = across * ({MEMBRANE_WANDER:.6f} * sin(along * 2.5 + uSeed) * life);
    vec3 q = sheetTwist(p.xy, axis, pivot, 3.14159265 * s, halfWidth);
    q.z += {MEMBRANE_BILLOW:.6f} * life * (0.5 + 0.5 * sin(off * 7.0 + along * 3.0 + uSeed * 1.7));
    return q;
}}
""",
    _COMMON + SHEET_TWIST_GLSL,
)

MEMBRANE_FRAGMENT_SOURCE = (
    "#version 460 core\n"
    "in vec2 vUv;\nin vec3 vWorld;\nin vec3 vNormal;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform sampler2D uEnvironment;\n"
    "uniform vec2 uItemSize;\nuniform float uGloss;\n"
    + SCENE3D_GLSL + REFRACTION_GLSL + SHEET_SIDES_GLSL + _COMMON
    + f"""
void main() {{
    float aspect = uItemSize.x / uItemSize.y;
    float s = membranePhase(scenePlanePoint(vUv, aspect).xy, aspect);
    vec3 photo = texture(uOldTex, vUv).rgb;
    if (s <= 0.0) {{
        FragColor = vec4(photo, 1.0);     // flat and untouched: the photograph exactly
        return;
    }}
    float life = sin(3.14159265 * s);
    bool back = sheetShowsBack(vNormal, vWorld);
    vec3 n = normalize(vNormal) * (back ? -1.0 : 1.0);
    vec3 view = normalize(vec3(0.0, 0.0, SCENE_CAMERA) - vWorld);
    SceneMaterial m = SceneMaterial(photo, mix(0.55, 0.12, uGloss), 0.0, 0.5, vec3(0.0));
    vec3 lit = sceneMaterialLit(m, n, vWorld, vec3(2.4), vec3(0.36))
             + uGloss * sceneMaterialEnvironment(uEnvironment, m, n, vWorld);
    float sheen = fresnelSchlick(abs(dot(n, view)), 0.04) * uGloss;
    if (!back) {{
        FragColor = vec4(mix(photo, lit + vec3(0.8, 0.9, 1.0) * sheen * 0.9, life), 1.0);
        return;
    }}
    // From behind, the print shows through a thin sheet: dimmer and softer, fading as it lands.
    float fade = clamp((s - 0.6) / 0.4, 0.0, 1.0);
    float opacity = {MEMBRANE_BACK:.6f} * (1.0 - fade * fade * (3.0 - 2.0 * fade));
    vec3 membrane = mix(lit, vec3(dot(lit, vec3(0.333))), 0.25) * 0.85 + vec3(0.8, 0.9, 1.0) * sheen * 1.1;
    FragColor = vec4(membrane, clamp(opacity * (1.0 + sheen), 0.0, 1.0));
}}
"""
)
