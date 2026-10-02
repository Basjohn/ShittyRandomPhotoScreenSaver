"""Page Curl: shaders and CPU mirrors (loaded only when Page Curl renders).

The old picture is a page that peels from a corner or edge. A straight curl line sweeps
across it (``direction``, world units, y up); the page behind the line wraps around a
cylinder of radius ``PAGE_CURL_RADIUS`` standing on the line and, past half a turn, lies
folded back over the page at twice the radius, its paper back up. The shared bendable
grid draws it (``sceneDisplace``), so the flat part is the photograph exactly.

The new picture lies beneath, shaded where the curl stands over it; the shade fades to
nothing before the line leaves the page, so the run ends on the new picture exactly. The
curled page is lit by the shared physically based material (photo paper, gloss from
Settings, a reflection of the new picture), blended in by how far the paper has bent, so the
flat page stays exact.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_GLSL, scene3d_grid_vertex_source

PAGE_CURL_RADIUS = 0.075
# The shade's strength on the new picture at the foot of the curl, and its reach (in radii).
PAGE_CURL_SHADE = 0.45
PAGE_CURL_SHADE_REACH = 1.2
_ORIGIN_CORNERS = {
    "bottom_right": (1.0, -1.0), "bottom_left": (-1.0, -1.0), "top_right": (1.0, 1.0), "top_left": (-1.0, 1.0),
    "right": (1.0, 0.0), "left": (-1.0, 0.0), "bottom": (0.0, -1.0), "top": (0.0, 1.0),
}


def page_curl_direction(origin: str, aspect: float) -> tuple[float, float]:
    """The unit direction the curl line travels: from the origin toward the opposite side."""
    sx, sy = _ORIGIN_CORNERS[origin]
    x, y = -sx * aspect, -sy
    length = math.hypot(x, y)
    return x / length, y / length


def page_curl_span(direction: tuple[float, float], aspect: float) -> tuple[float, float]:
    """Where along ``direction`` the page begins and ends (its nearest and farthest corners)."""
    values = [direction[0] * x * aspect / 2 + direction[1] * y / 2 for x in (-1, 1) for y in (-1, 1)]
    return min(values), max(values)


def page_curl_line(progress: float, near: float, far: float) -> float:
    """The curl line's position at ``progress``: from the page's first corner (nothing curled)
    until the curl and its shade have left the far side. Eased in and out."""
    t = max(0.0, min(1.0, float(progress)))
    return near + (far + 3.0 * PAGE_CURL_RADIUS - near) * t * t * (3.0 - 2.0 * t)


def page_curl_shade_weight(line: float, far: float) -> float:
    """The shade's fade as the curl leaves the page: 1 until it reaches the far side, 0 at the end."""
    lo, hi = far + PAGE_CURL_RADIUS, far + 3.0 * PAGE_CURL_RADIUS
    x = max(0.0, min(1.0, (line - lo) / (hi - lo)))
    return 1.0 - x * x * (3.0 - 2.0 * x)


def page_curl_displace(point: tuple[float, float], direction: tuple[float, float], line: float,
                       radius: float = PAGE_CURL_RADIUS) -> tuple[float, float, float]:
    """CPU mirror of ``pageCurlDisplace``: where the page's point (world xy at rest) lies."""
    along = point[0] * direction[0] + point[1] * direction[1]
    u = line - along
    if u <= 0.0:
        return point[0], point[1], 0.0
    foot = (point[0] + direction[0] * u, point[1] + direction[1] * u)
    phi = u / radius
    if phi < math.pi:
        offset, height = -radius * math.sin(phi), radius * (1.0 - math.cos(phi))
    else:
        offset, height = u - math.pi * radius, 2.0 * radius
    return foot[0] + direction[0] * offset, foot[1] + direction[1] * offset, height


PAGE_CURL_GLSL = f"""
const float CURL_RADIUS = {PAGE_CURL_RADIUS:.6f};
// Where the page's point p (world xy at rest) lies when the curl line, travelling along d,
// stands at line: flat ahead of the line, around the cylinder, then folded back on top.
vec3 pageCurlDisplace(vec2 p, vec2 d, float line, float radius) {{
    float u = line - dot(p, d);
    if (u <= 0.0) return vec3(p, 0.0);
    vec2 foot = p + d * u;
    float phi = u / radius;
    if (phi < 3.14159265) return vec3(foot - d * (radius * sin(phi)), radius * (1.0 - cos(phi)));
    return vec3(foot + d * (u - 3.14159265 * radius), 2.0 * radius);
}}
"""

_CURL_UNIFORMS = "uniform vec2 uDirection;\nuniform float uLine;\n"

PAGE_CURL_VERTEX_SOURCE = scene3d_grid_vertex_source(
    """
vec3 sceneDisplace(vec2 uv) {
    vec3 p = scenePlanePoint(uv, uItemSize.x / uItemSize.y);
    return pageCurlDisplace(p.xy, uDirection, uLine, CURL_RADIUS);
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
    // How far this point of the paper has bent: 0 flat, 1 from a quarter turn on.
    float u = uLine - dot(scenePlanePoint(vUv, uItemSize.x / uItemSize.y).xy, uDirection);
    float bend = clamp(u / (0.5 * 3.14159265 * CURL_RADIUS), 0.0, 1.0);
    if (bend <= 0.0) {
        FragColor = vec4(photo, 1.0);   // the flat page: the photograph exactly
        return;
    }
    vec3 n = normalize(vNormal);
    bool back = dot(n, normalize(vec3(0.0, 0.0, SCENE_CAMERA) - vWorld)) < 0.0;
    // The paper's back: off-white with the print faintly showing through (mirrored, as it is).
    vec3 albedo = back ? mix(vec3(0.94, 0.93, 0.90), photo, 0.16) : photo;
    if (back) n = -n;
    SceneMaterial paper = SceneMaterial(albedo, mix(0.75, 0.22, uGloss), 0.0, 0.5, vec3(0.0));
    vec3 lit = sceneMaterialLit(paper, n, vWorld, vec3(2.6), vec3(0.32))
             + uGloss * sceneMaterialEnvironment(uEnvironment, paper, n, vWorld);
    FragColor = vec4(mix(photo, lit, back ? 1.0 : bend), 1.0);
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
    // Uncovered page lies behind the line; the curl stands over its first radius.
    float behind = uLine - dot(scenePlanePoint(uv, uItemSize.x / uItemSize.y).xy, uDirection);
    float shade = behind > 0.0 ? uShade * {PAGE_CURL_SHADE:.6f}
        * exp(-max(behind - CURL_RADIUS, 0.0) / ({PAGE_CURL_SHADE_REACH:.6f} * CURL_RADIUS)) : 0.0;
    FragColor = vec4(texture(uNewTex, uv).rgb * (1.0 - shade), 1.0);
}}
"""
)
