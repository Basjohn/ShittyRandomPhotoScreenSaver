"""Accordion Fold: shaders and CPU mirrors (loaded only when Accordion Fold renders).

The old picture is the front of an accordion-folded sheet whose back carries the new picture.
It folds into ``pleats`` equal strips, alternately tilted up and down, compressing against an
edge: a point ``a`` from that edge (along the fold axis, world units) lies at ``a cos(fold)``
from it and as high as its distance from the nearest crease times ``sin(fold)``, so every pleat
keeps its width (a fold, never a stretch). The folded stack then flips over toward the viewer
about its own middle (lifting clear of the picture as it turns), and unfolds back across the
picture back up: a point ``a`` then lies at ``(length - a) cos(fold)``, its ridges and valleys
swapped, which is exactly where the turned stack left it. Laid flat, the back's mirrored print
lands exactly on the new picture.

Behind the sheet, a frosted blur of the new picture (its renderer-owned copy). The grid
(``accordion_grid``) puts a vertex row on every crease, so creases stay sharp at any 3D Detail
tier, and each pleat face is shaded flat from its own screen-space normal: a vivid print, shaded
by its tilt, under a light sheen, blended in by how far the sheet is folded so the flat sheet
at either end is the photograph exactly.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_GLSL, scene3d_grid_vertex_source

ACCORDION_MAX_FOLD = 0.36 * math.pi
# The run's thirds: folding up, flipping over, unfolding.
ACCORDION_FOLD_END = 0.4
ACCORDION_FLIP_END = 0.58
ACCORDION_BACKDROP = 0.62
ACCORDION_BACKDROP_BLUR = 4.0


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def accordion_state(progress: float) -> tuple[float, float]:
    """(fold angle, flip angle) at ``progress``: folding up, flipping over (0 to pi), unfolding."""
    t = max(0.0, min(1.0, float(progress)))
    if t < ACCORDION_FOLD_END:
        return ACCORDION_MAX_FOLD * _ease(t / ACCORDION_FOLD_END), 0.0
    if t < ACCORDION_FLIP_END:
        return ACCORDION_MAX_FOLD, math.pi * _ease((t - ACCORDION_FOLD_END) / (ACCORDION_FLIP_END - ACCORDION_FOLD_END))
    return ACCORDION_MAX_FOLD * (1.0 - _ease((t - ACCORDION_FLIP_END) / (1.0 - ACCORDION_FLIP_END))), math.pi


def accordion_lift(fold: float) -> float:
    """How far the sheet's lighting is blended in: 0 flat, 1 from a modest fold on."""
    x = max(0.0, min(1.0, fold / 0.35))
    return x * x * (3.0 - 2.0 * x)


def accordion_fold(a: float, length: float, pleats: int, fold: float, flip: float) -> tuple[float, float]:
    """CPU mirror of ``accordionFold``: (distance from the edge, height) of the point ``a`` from it."""
    width = length / pleats
    local = a - width * math.floor(a / width)
    crease = min(local, width - local)
    if flip >= math.pi:
        return (length - a) * math.cos(fold), (0.5 * width - crease) * math.sin(fold)
    x, z = a * math.cos(fold), crease * math.sin(fold)
    if flip <= 0.0:
        return x, z
    cx, cz = 0.5 * length * math.cos(fold), 0.25 * width * math.sin(fold)
    c, s = math.cos(flip), math.sin(flip)
    dx, dz = x - cx, z - cz
    return cx + dx * c - dz * s, cz + dx * s + dz * c + (cx + 2.0 * cz) * s


def accordion_grid(pleats: int, tier_cells: int, aspect: float, vertical: bool) -> tuple[int, int]:
    """(columns, rows): along the fold axis a whole number of cells per pleat (each crease on a
    vertex row) at about the tier's density; across it one cell (the pleats are flat strips)."""
    along_length = 1.0 if vertical else aspect
    long_side = max(aspect, 1.0)
    cells = max(2, round(tier_cells * along_length / long_side / pleats)) * pleats
    return (1, cells) if vertical else (cells, 1)


ACCORDION_GLSL = """
// A point a from the folding edge (along the fold axis): (distance from the edge, height).
// fold: the pleats' angle; flip: 0 folding front up, pi unfolding back up, between: turning over.
vec2 accordionFold(float a, float len, float pleats, float fold, float flip) {
    float width = len / pleats;
    float local = a - width * floor(a / width);
    float crease = min(local, width - local);
    if (flip >= 3.14159265) return vec2((len - a) * cos(fold), (0.5 * width - crease) * sin(fold));
    vec2 p = vec2(a * cos(fold), crease * sin(fold));
    if (flip <= 0.0) return p;
    vec2 centre = vec2(0.5 * len * cos(fold), 0.25 * width * sin(fold));
    vec2 d = p - centre;
    float c = cos(flip), s = sin(flip);
    return centre + vec2(d.x * c - d.y * s, d.x * s + d.y * c + (centre.x + 2.0 * centre.y) * s);
}
"""

_UNIFORMS = ("uniform vec2 uEdge;\n"          # unit vector from the folding edge into the picture (world, y up)
             "uniform float uLength;\nuniform float uPleats;\nuniform float uFold;\nuniform float uFlip;\n")

ACCORDION_VERTEX_SOURCE = scene3d_grid_vertex_source(
    """
vec3 sceneDisplace(vec2 uv) {
    vec3 p = scenePlanePoint(uv, uItemSize.x / uItemSize.y);
    // Distance from the folding edge along uEdge, and the offset along the edge itself.
    float a = dot(p.xy, uEdge) + 0.5 * uLength;
    vec2 along = p.xy - uEdge * dot(p.xy, uEdge);
    vec2 folded = accordionFold(a, uLength, uPleats, uFold, uFlip);
    return vec3(along + uEdge * (folded.x - 0.5 * uLength), folded.y);
}
""",
    _UNIFORMS + ACCORDION_GLSL,
)

ACCORDION_FRAGMENT_SOURCE = (
    "#version 460 core\n"
    "in vec2 vUv;\nin vec3 vWorld;\nin vec3 vNormal;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform sampler2D uEnvironment;\n"
    "uniform float uGloss;\nuniform float uLift;\nuniform vec2 uMirror;\n"
    + SCENE3D_GLSL
    + """
void main() {
    vec3 view = normalize(vec3(0.0, 0.0, SCENE_CAMERA) - vWorld);
    // The sheet's front carries the old picture; its back the new one, printed mirrored.
    bool back = dot(vNormal, view) < 0.0;
    vec3 photo = back ? texture(uNewTex, mix(vUv, 1.0 - vUv, uMirror)).rgb : texture(uOldTex, vUv).rgb;
    if (uLift <= 0.0) {
        FragColor = vec4(photo, 1.0);   // flat: the photograph exactly
        return;
    }
    // Each pleat is a flat face: shade it from its own screen-space normal, facing the viewer.
    vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
    if (dot(n, view) < 0.0) n = -n;
    float facing = max(dot(n, SCENE_KEY), 0.0);
    SceneMaterial sheen = SceneMaterial(vec3(0.0), mix(0.55, 0.15, uGloss), 0.0, 0.5, vec3(0.0));
    vec3 lit = photo * (0.62 + 0.5 * facing)
             + sceneMaterialLit(sheen, n, vWorld, vec3(2.0), vec3(0.0))
             + uGloss * 0.6 * sceneMaterialEnvironment(uEnvironment, sheen, n, vWorld);
    FragColor = vec4(mix(photo, lit, uLift), 1.0);
}
"""
)

ACCORDION_BACKDROP_FRAGMENT_SOURCE = f"""#version 460 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uEnvironment;
void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    // A smooth frost: a tent of nine taps a blurred texel apart (one tap alone shows the texels).
    vec2 texel = exp2({ACCORDION_BACKDROP_BLUR:.1f}) / vec2(textureSize(uEnvironment, 0));
    vec3 sum = vec3(0.0);
    for (int y = -1; y <= 1; ++y)
        for (int x = -1; x <= 1; ++x)
            sum += textureLod(uEnvironment, uv + vec2(x, y) * texel, {ACCORDION_BACKDROP_BLUR:.1f}).rgb
                 * float((2 - abs(x)) * (2 - abs(y)));
    FragColor = vec4(sum / 16.0 * {ACCORDION_BACKDROP:.6f}, 1.0);
}}
"""

_EDGE_VECTORS = {"left": (1.0, 0.0), "right": (-1.0, 0.0), "top": (0.0, -1.0), "bottom": (0.0, 1.0)}


def accordion_edge(edge: str) -> tuple[float, float]:
    """The unit vector from the folding edge into the picture (world, y up)."""
    return _EDGE_VECTORS[edge]
