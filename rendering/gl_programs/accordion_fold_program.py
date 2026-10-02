"""Accordion Fold: shaders and CPU mirrors (loaded only when Accordion Fold renders).

The old picture folds into ``pleats`` equal strips, alternately tilted up and down like an
accordion, and compresses against an edge: a point ``a`` from that edge (along the fold axis,
world units) lies at ``a cos(angle)`` from it and as high as its distance from the nearest
crease times ``sin(angle)``, so every pleat keeps its width (a fold, never a stretch). The
angle opens to ``ACCORDION_MAX_ANGLE`` over the first ``ACCORDION_FOLD_SHARE`` of the run,
then the folded stack slides out past its edge. The new picture lies beneath, shaded at the
foot of the stack (fading to nothing by the end).

The grid (``accordion_grid``) puts a vertex row on every crease, so creases stay sharp at
any 3D Detail tier, and each pleat face is shaded flat from its own screen-space normal
through the shared physically based material, blended in by the angle so the unfolded
picture is exact.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_GLSL, scene3d_grid_vertex_source

ACCORDION_MAX_ANGLE = 0.47 * math.pi
ACCORDION_FOLD_SHARE = 0.72
ACCORDION_SHADE = 0.42
ACCORDION_SHADE_REACH = 0.06
# How far past the edge the stack travels (beyond its own folded extent).
ACCORDION_SLIDE_MARGIN = 0.12


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def accordion_state(progress: float, length: float, pleats: int) -> tuple[float, float]:
    """(fold angle, slide distance toward the edge) at ``progress`` for a picture ``length`` long."""
    t = max(0.0, min(1.0, float(progress)))
    angle = ACCORDION_MAX_ANGLE * _ease(t / ACCORDION_FOLD_SHARE)
    width = length / pleats
    folded = length * math.cos(ACCORDION_MAX_ANGLE) + width * math.sin(ACCORDION_MAX_ANGLE)
    slide = (folded + ACCORDION_SLIDE_MARGIN) * _ease((t - ACCORDION_FOLD_SHARE) / (1.0 - ACCORDION_FOLD_SHARE))
    return angle, slide


def accordion_shade_weight(progress: float) -> float:
    """The shade at the stack's foot: full while folding, gone as the stack leaves."""
    return 1.0 - _ease((float(progress) - ACCORDION_FOLD_SHARE) / (1.0 - ACCORDION_FOLD_SHARE))


def accordion_fold(a: float, length: float, pleats: int, angle: float, slide: float) -> tuple[float, float]:
    """CPU mirror of ``accordionFold``: (distance from the edge, height) of the point ``a`` from it."""
    width = length / pleats
    local = a - width * math.floor(a / width)
    crease = min(local, width - local)
    return a * math.cos(angle) - slide, crease * math.sin(angle)


def accordion_grid(pleats: int, tier_cells: int, aspect: float, vertical: bool) -> tuple[int, int]:
    """(columns, rows): along the fold axis a whole number of cells per pleat (each crease on a
    vertex row) at about the tier's density; across it one cell (the pleats are flat strips)."""
    along_length = 1.0 if vertical else aspect
    long_side = max(aspect, 1.0)
    cells = max(2, round(tier_cells * along_length / long_side / pleats)) * pleats
    return (1, cells) if vertical else (cells, 1)


ACCORDION_GLSL = """
// A point a from the folding edge (along the fold axis) once folded: (distance from the edge, height).
vec2 accordionFold(float a, float len, float pleats, float angle, float slide) {
    float width = len / pleats;
    float local = a - width * floor(a / width);
    return vec2(a * cos(angle) - slide, min(local, width - local) * sin(angle));
}
"""

_UNIFORMS = ("uniform vec2 uEdge;\n"          # unit vector from the folding edge into the picture (world, y up)
             "uniform float uLength;\nuniform float uPleats;\nuniform float uAngle;\nuniform float uSlide;\n")

ACCORDION_VERTEX_SOURCE = scene3d_grid_vertex_source(
    """
vec3 sceneDisplace(vec2 uv) {
    vec3 p = scenePlanePoint(uv, uItemSize.x / uItemSize.y);
    // Distance from the folding edge along uEdge, and the offset along the edge itself.
    float a = dot(p.xy, uEdge) + 0.5 * uLength;
    vec2 along = p.xy - uEdge * dot(p.xy, uEdge);
    vec2 folded = accordionFold(a, uLength, uPleats, uAngle, uSlide);
    return vec3(along + uEdge * (folded.x - 0.5 * uLength), folded.y);
}
""",
    _UNIFORMS + ACCORDION_GLSL,
)

ACCORDION_FRAGMENT_SOURCE = (
    "#version 460 core\n"
    "in vec2 vUv;\nin vec3 vWorld;\nin vec3 vNormal;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uEnvironment;\nuniform float uGloss;\nuniform float uAngle;\n"
    + SCENE3D_GLSL
    + f"""
void main() {{
    vec3 photo = texture(uOldTex, vUv).rgb;
    float folding = smoothstep(0.0, 0.35, uAngle);
    if (folding <= 0.0) {{
        FragColor = vec4(photo, 1.0);   // unfolded: the photograph exactly
        return;
    }}
    // Each pleat is a flat face: shade it from its own screen-space normal, facing the viewer.
    vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
    if (n.z < 0.0) n = -n;
    SceneMaterial paper = SceneMaterial(photo, mix(0.75, 0.25, uGloss), 0.0, 0.5, vec3(0.0));
    vec3 lit = sceneMaterialLit(paper, n, vWorld, vec3(2.6), vec3(0.32))
             + uGloss * sceneMaterialEnvironment(uEnvironment, paper, n, vWorld);
    FragColor = vec4(mix(photo, lit, folding), 1.0);
}}
"""
)

ACCORDION_BACKDROP_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform vec2 uItemSize;\nuniform sampler2D uNewTex;\nuniform float uShade;\nuniform float uFront;\n"
    + _UNIFORMS + SCENE3D_GLSL
    + f"""
void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    // Distance of this point of the new picture beyond the folded stack's far side.
    float a = dot(scenePlanePoint(uv, uItemSize.x / uItemSize.y).xy, uEdge) + 0.5 * uLength;
    float beyond = a - uFront;
    float shade = beyond > 0.0 ? uShade * {ACCORDION_SHADE:.6f} * exp(-beyond / {ACCORDION_SHADE_REACH:.6f}) : 0.0;
    FragColor = vec4(texture(uNewTex, uv).rgb * (1.0 - shade), 1.0);
}}
"""
)

_EDGE_VECTORS = {"left": (1.0, 0.0), "right": (-1.0, 0.0), "top": (0.0, -1.0), "bottom": (0.0, 1.0)}


def accordion_edge(edge: str) -> tuple[float, float]:
    """The unit vector from the folding edge into the picture (world, y up)."""
    return _EDGE_VECTORS[edge]
