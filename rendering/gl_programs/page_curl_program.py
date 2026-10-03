"""Page Curl: shaders and CPU mirrors (loaded only when Page Curl renders).

The old picture is a laminated print that peels from a corner or edge and rolls up. A straight
peel line sweeps across it (``direction``, world units, y up). Each row of the page along the
direction is a strip: the part behind the line has peeled and wound into a loose spiral roll that
rides the line, its free edge innermost (radius ``PAGE_CURL_ROLL_INNER``), each turn
``2 pi PAGE_CURL_ROLL_PITCH`` further out, so the roll grows as more is peeled. The spiral is
solved for arc length exactly, so the sheet bends but never stretches, and it leaves the flat page
tangentially, so there is no crease. Once a row has peeled completely its roll rolls on, off the
far side. The shared bendable grid draws it (``sceneDisplace``), so the flat part is the photograph
exactly.

The new picture lies beneath, shaded under the roll; the shade fades to nothing before the roll
leaves the page, so the run ends on the new picture exactly. The peeled sheet is a glossy laminate:
a vivid print, gently shaded by its turn (never greyed), under a clear coat lit by the shared
physically based material; its back shows the print mirrored through the plastic. The lighting is
blended in by how far the sheet has lifted, so the flat page stays exact.
"""

from __future__ import annotations

import math

import numpy as np

from rendering.gl_programs.scene3d import SCENE3D_GLSL, scene3d_grid_vertex_source

# The roll: its innermost radius (the free edge's curl) and its growth per radian.
PAGE_CURL_ROLL_INNER = 0.05
PAGE_CURL_ROLL_PITCH = 0.01
# The shade's strength on the new picture under the roll, and its reach (in roll radii).
PAGE_CURL_SHADE = 0.45
PAGE_CURL_SHADE_REACH = 1.2
# How far past the far side (in final roll radii) the line travels so the roll has left the view.
PAGE_CURL_EXIT = 1.6
# The share of the run spent speeding up (and again slowing down): the rest is an even pace.
PAGE_CURL_RAMP = 0.25
_NEWTON_STEPS = 4
_ORIGIN_CORNERS = {
    "bottom_right": (1.0, -1.0), "bottom_left": (-1.0, -1.0), "top_right": (1.0, 1.0), "top_left": (-1.0, 1.0),
    "right": (1.0, 0.0), "left": (-1.0, 0.0), "bottom": (0.0, -1.0), "top": (0.0, 1.0),
}


def page_curl_direction(origin: str, aspect: float) -> tuple[float, float]:
    """The unit direction the peel line travels: from the origin toward the opposite side."""
    sx, sy = _ORIGIN_CORNERS[origin]
    x, y = -sx * aspect, -sy
    length = math.hypot(x, y)
    return x / length, y / length


def page_curl_span(direction: tuple[float, float], aspect: float) -> tuple[float, float]:
    """Where along ``direction`` the page begins and ends (its nearest and farthest corners)."""
    values = [direction[0] * x * aspect / 2 + direction[1] * y / 2 for x in (-1, 1) for y in (-1, 1)]
    return min(values), max(values)


def _arc(r):
    """The spiral's arc length from the centre to radius ``r`` (up to a constant)."""
    b = PAGE_CURL_ROLL_PITCH
    root = np.sqrt(r * r + b * b)
    return (r * root + b * b * np.log(r + root)) / (2.0 * b)


def page_curl_roll_radius(length):
    """CPU mirror of ``pageCurlRadius``: the roll's radius ``length`` along the sheet from its
    free edge (arrays welcome)."""
    r0, b = PAGE_CURL_ROLL_INNER, PAGE_CURL_ROLL_PITCH
    s = np.maximum(np.asarray(length, dtype=np.float64), 0.0)
    target = _arc(r0) + s
    r = np.sqrt(r0 * r0 + 2.0 * b * s)
    for _ in range(_NEWTON_STEPS):
        r = r - (_arc(r) - target) * b / np.sqrt(r * r + b * b)
    return np.maximum(r, r0)


def page_curl_end_radius(near: float, far: float) -> float:
    """The largest roll the run makes: the page's longest strip wound up."""
    return float(page_curl_roll_radius(far - near))


def page_curl_line(progress: float, near: float, far: float) -> float:
    """The peel line's position at ``progress``: from the page's first corner (nothing peeled)
    until the roll and its shade have left the far side. An even pace with soft ends."""
    t = max(0.0, min(1.0, float(progress)))
    a = PAGE_CURL_RAMP
    if t < a:
        e = t * t / (2.0 * a * (1.0 - a))
    elif t > 1.0 - a:
        e = 1.0 - (1.0 - t) * (1.0 - t) / (2.0 * a * (1.0 - a))
    else:
        e = (t - 0.5 * a) / (1.0 - a)
    end = far + PAGE_CURL_EXIT * page_curl_end_radius(near, far)
    return near + (end - near) * e


def page_curl_shade_weight(line: float, near: float, far: float) -> float:
    """The shade's fade as the roll leaves the page: 1 until it is half a roll past the far
    side, 0 at the end of the run."""
    radius = page_curl_end_radius(near, far)
    lo, hi = far + 0.5 * radius, far + PAGE_CURL_EXIT * radius
    x = max(0.0, min(1.0, (line - lo) / (hi - lo)))
    return 1.0 - x * x * (3.0 - 2.0 * x)


def page_curl_row(point, direction, aspect: float):
    """CPU mirror of ``pageCurlRow``: how far the page extends behind and ahead of ``point``
    along ``direction`` (arrays welcome)."""
    back, ahead = np.full(np.shape(point[0]), 1e6), np.full(np.shape(point[0]), 1e6)
    for p, d, half in ((point[0], direction[0], aspect / 2), (point[1], direction[1], 0.5)):
        if abs(d) > 1e-6:
            t1, t2 = (half - p) / d, (-half - p) / d
            ahead = np.minimum(ahead, np.maximum(t1, t2))
            back = np.minimum(back, -np.minimum(t1, t2))
    return back, ahead


def page_curl_row_radius(point, direction, line: float, aspect: float):
    """CPU mirror of ``pageCurlRowRadius``: the radius of the roll in ``point``'s strip."""
    back, ahead = page_curl_row(point, direction, aspect)
    along = point[0] * direction[0] + point[1] * direction[1]
    peeled = np.minimum(line, along + ahead) - (along - back)
    return page_curl_roll_radius(peeled)


def page_curl_displace(point: tuple[float, float], direction: tuple[float, float], line: float,
                       aspect: float) -> tuple[float, float, float]:
    """CPU mirror of ``pageCurlDisplace``: where the page's point (world xy at rest) lies."""
    along = point[0] * direction[0] + point[1] * direction[1]
    u = line - along
    if u <= 0.0:
        return point[0], point[1], 0.0
    back, ahead = (float(v) for v in page_curl_row(point, direction, aspect))
    far_row = along + ahead
    r = float(page_curl_roll_radius(back))                      # the sheet's own place in the roll
    rc = float(page_curl_roll_radius(min(line, far_row) - (along - back)))
    b = PAGE_CURL_ROLL_PITCH
    contact = -0.5 * math.pi + math.atan2(b, rc)
    angle = contact - (rc - r) / b - max(line - far_row, 0.0) / rc
    across = r * math.cos(angle) - rc * math.cos(contact)
    height = r * math.sin(angle) - rc * math.sin(contact)
    return (point[0] + direction[0] * (u + across), point[1] + direction[1] * (u + across), height)


PAGE_CURL_GLSL = f"""
const float ROLL_INNER = {PAGE_CURL_ROLL_INNER:.6f};
const float ROLL_PITCH = {PAGE_CURL_ROLL_PITCH:.6f};
float pageCurlArc(float r) {{
    float root = sqrt(r * r + ROLL_PITCH * ROLL_PITCH);
    return (r * root + ROLL_PITCH * ROLL_PITCH * log(r + root)) / (2.0 * ROLL_PITCH);
}}
// The roll's radius the given length along the sheet from its free edge (the spiral solved
// for arc length exactly, so the sheet never stretches).
float pageCurlRadius(float length) {{
    float s = max(length, 0.0);
    float target = pageCurlArc(ROLL_INNER) + s;
    float r = sqrt(ROLL_INNER * ROLL_INNER + 2.0 * ROLL_PITCH * s);
    for (int i = 0; i < {_NEWTON_STEPS}; ++i)
        r -= (pageCurlArc(r) - target) * ROLL_PITCH / sqrt(r * r + ROLL_PITCH * ROLL_PITCH);
    return max(r, ROLL_INNER);
}}
// How far the page extends behind (x) and ahead of (y) p along d; extent is the page's half size.
vec2 pageCurlRow(vec2 p, vec2 d, vec2 extent) {{
    vec2 row = vec2(1e6);
    if (abs(d.x) > 1e-6) {{
        float t1 = (extent.x - p.x) / d.x, t2 = (-extent.x - p.x) / d.x;
        row = min(row, vec2(-min(t1, t2), max(t1, t2)));
    }}
    if (abs(d.y) > 1e-6) {{
        float t1 = (extent.y - p.y) / d.y, t2 = (-extent.y - p.y) / d.y;
        row = min(row, vec2(-min(t1, t2), max(t1, t2)));
    }}
    return row;
}}
// The radius of the roll in p's strip of the page.
float pageCurlRowRadius(vec2 p, vec2 d, float line, vec2 extent) {{
    vec2 row = pageCurlRow(p, d, extent);
    float along = dot(p, d);
    return pageCurlRadius(min(line, along + row.y) - (along - row.x));
}}
// Where the page's point p (world xy at rest) lies when the peel line, travelling along d,
// stands at line: flat ahead of the line; behind it wound into the strip's roll, which stands
// on the line (and, once the strip has peeled completely, rolls on along d).
vec3 pageCurlDisplace(vec2 p, vec2 d, float line, vec2 extent) {{
    float along = dot(p, d);
    float u = line - along;
    if (u <= 0.0) return vec3(p, 0.0);
    vec2 row = pageCurlRow(p, d, extent);
    float farRow = along + row.y;
    float r = pageCurlRadius(row.x);
    float rc = pageCurlRadius(min(line, farRow) - (along - row.x));
    float contact = -1.57079633 + atan(ROLL_PITCH, rc);
    float angle = contact - (rc - r) / ROLL_PITCH - max(line - farRow, 0.0) / rc;
    float across = r * cos(angle) - rc * cos(contact);
    return vec3(p + d * (u + across), r * sin(angle) - rc * sin(contact));
}}
"""

_CURL_UNIFORMS = "uniform vec2 uDirection;\nuniform float uLine;\n"

PAGE_CURL_VERTEX_SOURCE = scene3d_grid_vertex_source(
    """
vec3 sceneDisplace(vec2 uv) {
    float aspect = uItemSize.x / uItemSize.y;
    vec3 p = scenePlanePoint(uv, aspect);
    return pageCurlDisplace(p.xy, uDirection, uLine, vec2(0.5 * aspect, 0.5));
}
""",
    _CURL_UNIFORMS + PAGE_CURL_GLSL,
)

PAGE_CURL_FRAGMENT_SOURCE = (
    "#version 460 core\n"
    "in vec2 vUv;\nin vec3 vWorld;\nin vec3 vNormal;\nout vec4 FragColor;\n"
    "uniform vec2 uItemSize;\nuniform sampler2D uOldTex;\nuniform sampler2D uEnvironment;\nuniform float uGloss;\n"
    + _CURL_UNIFORMS + SCENE3D_GLSL + PAGE_CURL_GLSL
    + """
void main() {
    vec3 photo = texture(uOldTex, vUv).rgb;
    // How far this point of the sheet has lifted: 0 flat, 1 from a quarter of the free edge's curl on.
    float u = uLine - dot(scenePlanePoint(vUv, uItemSize.x / uItemSize.y).xy, uDirection);
    float lift = clamp(u / (0.5 * 3.14159265 * ROLL_INNER), 0.0, 1.0);
    if (lift <= 0.0) {
        FragColor = vec4(photo, 1.0);   // the flat page: the photograph exactly
        return;
    }
    vec3 n = normalize(vNormal);
    bool back = dot(n, normalize(vec3(0.0, 0.0, SCENE_CAMERA) - vWorld)) < 0.0;
    // The back: the print seen mirrored through the clear laminate, its colour kept.
    vec3 albedo = back ? photo * 0.94 + 0.03 : photo;
    if (back) n = -n;
    // A vivid print under a clear coat: the print is only gently shaded by the turn (never greyed),
    // and the coat adds its highlights and a reflection of the new picture on top.
    float facing = max(dot(n, SCENE_KEY), 0.0);
    SceneMaterial coat = SceneMaterial(vec3(0.0), mix(0.35, 0.05, uGloss), 0.0, 0.5, vec3(0.0));
    vec3 lit = albedo * (0.8 + 0.32 * facing)
             + sceneMaterialLit(coat, n, vWorld, vec3(2.4), vec3(0.0))
             + (0.35 + 0.65 * uGloss) * sceneMaterialEnvironment(uEnvironment, coat, n, vWorld);
    // The laminate's cut edge catches the light.
    vec2 edge = min(vUv, 1.0 - vUv) * uItemSize / uItemSize.y;
    lit = mix(lit, vec3(0.96), 0.55 * (1.0 - smoothstep(0.0, 0.004, min(edge.x, edge.y))));
    FragColor = vec4(mix(photo, lit, back ? 1.0 : lift), 1.0);
}
"""
)

PAGE_CURL_BACKDROP_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform vec2 uItemSize;\nuniform sampler2D uNewTex;\nuniform float uShade;\n"
    + _CURL_UNIFORMS + SCENE3D_GLSL + PAGE_CURL_GLSL
    + f"""
void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float aspect = uItemSize.x / uItemSize.y;
    vec2 p = scenePlanePoint(uv, aspect).xy;
    // Uncovered page lies behind the line; the roll stands over it, darkest at its foot.
    float behind = uLine - dot(p, uDirection);
    float shade = 0.0;
    if (behind > 0.0) {{
        float radius = pageCurlRowRadius(p, uDirection, uLine, vec2(0.5 * aspect, 0.5));
        shade = uShade * {PAGE_CURL_SHADE:.6f}
              * exp(-max(behind - 0.5 * radius, 0.0) / ({PAGE_CURL_SHADE_REACH:.6f} * radius));
    }}
    FragColor = vec4(texture(uNewTex, uv).rgb * (1.0 - shade), 1.0);
}}
"""
)
