"""Extruded Spectrum: shaders and CPU mirrors (loaded only when the mode renders).

Spectrum's bars, extruded into lit boxes standing on a floor and seen from slightly above.
Bar placement, widths and heights are exactly Spectrum's (``compute_quick_spectrum_layout``
and the same level transfer: ``0.55`` upload, ``pow 1.15``, the height scale, the 0.95
ceiling), so the mode keeps Spectrum's authored response; only the presentation is 3D.

World units are the bar field's height: x across from the bar row's centre, y up from the
floor, z toward the viewer (a bar's front face lies at z = 0 and it extends back by its
depth). The row turns about the vertical axis by ``turn`` (at most ``EXTRUDED_MAX_TURN``
either way), then the camera tilts down by ``tilt`` (at most ``EXTRUDED_MAX_TILT``) about
the floor line and looks from ``EXTRUDED_CAMERA`` away. A uniform fit (``extruded_fit``)
keeps the tallest possible scene inside the bar field for the current settings and shape,
so nothing moves with the music but the bars; with overflow allowed the bars keep
Spectrum's own size and the 3D (tilted tops, the turn, the reflection) may leave the
rectangle.

Bars are instances of the shared unit box reading one std430 record each (level, peak)
from the stream ring, lit by the shared physically based material. Colouring
(``extruded_spectrum_options``): spectral bodies, spectral glowing edges on Spectrum's
bar body (the Organs look) or Spectrum's bar colours; spectral hues may drift on the
frame's authored animation time. Ghost peaks are translucent columns from the bar's top
to its peak, as in Spectrum; the reflection is the row mirrored under the floor, fading to
nothing at the bar field's bottom.

Edge lines are drawn by the shader along each face's border, sized as if seen head-on. Smooth
Edges measures them in screen pixels (``fwidth`` of the face coordinates) and keeps each at
least 1.2 smoothed pixels wide, so a face seen at an angle keeps a ramped line instead of one
foreshortened below a pixel; head-on nothing changes. Mirror Faces gives the faces (never the edge lines) a polished, faintly brushed
chrome surface reflecting a fixed studio (``extrudedStudio``: a bright sky over a dark ground
at a crisp horizon, and two softbox strips) toward a near virtual eye, so the horizon crosses
the bars and the lights sweep across them as the view turns.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_GLSL, Scene3DStorageLayout

EXTRUDED_MAX_TILT = math.radians(40.0)
EXTRUDED_MAX_TURN = math.radians(40.0)
# Farther than the transitions' camera: a row of bars spans the whole width, and a near
# camera makes the outer bars lean out like a wide-angle lens.
EXTRUDED_CAMERA = 6.0
EXTRUDED_MAX_DEPTH = 0.6          # a bar's depth never exceeds this many bar-field heights
EXTRUDED_CEILING = 0.95           # Spectrum's tallest bar, in bar-field heights
EXTRUDED_REFLECTION_SPACE = 0.22  # floor lift (bar-field heights) a full reflection reserves
# How far (in item heights) an overflowing scene may reach beyond the item on every side.
EXTRUDED_OVERFLOW_PAD = 0.5
EXTRUDED_HUE_DRIFT_RATE = 0.15    # hue turns per authored second at full drift
EXTRUDED_BARS = Scene3DStorageLayout.of("ExtrudedBars", "ExtrudedBar", (("level", "float"), ("peak", "float")),
                                        array="bars")


def extruded_project(point: tuple[float, float, float], tilt: float,
                     turn: float = 0.0) -> tuple[float, float, float]:
    """CPU mirror of ``extrudedProject``: (screen x, screen y up, view depth) of a world point."""
    x, y, z = point
    ct, st = math.cos(turn), math.sin(turn)
    x, z = x * ct + z * st, -x * st + z * ct
    c, s = math.cos(tilt), math.sin(tilt)
    raised, toward = y * c - z * s, y * s + z * c
    scale = EXTRUDED_CAMERA / (EXTRUDED_CAMERA - toward)
    return x * scale, raised * scale, toward


def extruded_height(level: float, height_scale: float) -> float:
    """CPU mirror of ``extrudedHeight``: an uploaded level (Spectrum's x0.55 already applied)
    in bar-field heights, by Spectrum's own transfer."""
    curved = max(0.0, min(1.0, float(level))) ** 1.15
    return min(EXTRUDED_CEILING, curved * max(1.0, min(1.85, float(height_scale))))


def extruded_fit(half_span: float, depth: float, tilt: float, reflection: float, aspect: float,
                 turn: float = 0.0, overflow: bool = False) -> tuple[float, float]:
    """(scale, floor) mapping projected world units to the bar field: the largest scene the
    settings allow (every bar at the ceiling, its full depth, its reflection) fits inside a
    field ``aspect`` times wider than tall, centred; ``floor`` is the floor line's height in
    the field (0 at its bottom, 1 at its top). Fixed per settings and shape, never per frame
    of music. With ``overflow`` the bars keep Spectrum's size and the 3D may leave the field."""
    lift = EXTRUDED_REFLECTION_SPACE * max(0.0, min(1.0, reflection))
    if overflow:
        return 1.0, lift
    corners = [extruded_project((x, y, z), tilt, turn) for x in (-half_span, half_span)
               for y in (0.0, EXTRUDED_CEILING) for z in (-depth, 0.0)]
    half_width = max(abs(p[0]) for p in corners)
    top = max(p[1] for p in corners)
    bottom = min(p[1] for p in corners)
    scale = min(0.5 * aspect / max(half_width, 1e-6), (1.0 - lift) / max(top - bottom, 1e-6), 1.0)
    return scale, lift - bottom * scale


def extruded_overflow_frame(frame, pad: float):
    """A frame like ``frame`` whose item reaches ``pad`` item-local units further on every
    side (its matrix shifted to match), for compositing a scene that leaves the item."""
    from types import SimpleNamespace

    m = list(frame.matrix_values)
    for row in range(4):
        m[12 + row] -= pad * (m[row] + m[4 + row])
    width, height = frame.logical_size
    return SimpleNamespace(viewport=frame.viewport, logical_size=(width + 2.0 * pad, height + 2.0 * pad),
                           matrix_values=tuple(m), quad_vao=frame.quad_vao)


_COMMON_UNIFORMS = """
uniform mat4 uMatrix;
uniform vec4 uField;        // bar field in item coordinates: left, top, width, height
uniform vec2 uCentre;       // bar row centre x and floor's height, item coordinates
uniform vec4 uBarGeometry;  // first bar's centre x, bar step, bar half width, bar depth (world units)
uniform vec2 uFit;          // fit scale, floor height in the field (0 bottom .. 1 top)
uniform vec2 uView;         // tilt, turn (radians)
uniform float uHeightScale;
"""

_PROJECTION_GLSL = f"""
const float EXTRUDED_CEILING = {EXTRUDED_CEILING:.6f};
const float EXTRUDED_CAMERA = {EXTRUDED_CAMERA:.6f};
// A world point or direction turned about the vertical axis, then tilted toward the camera.
vec3 extrudedView(vec3 p, vec2 view) {{
    float ct = cos(view.y), st = sin(view.y);
    p = vec3(p.x * ct + p.z * st, p.y, -p.x * st + p.z * ct);
    float c = cos(view.x), s = sin(view.x);
    return vec3(p.x, p.y * c - p.z * s, p.y * s + p.z * c);
}}
// (screen x, screen y up, view depth) of a world point, as the CPU mirror.
vec3 extrudedProject(vec3 p, vec2 view) {{
    vec3 v = extrudedView(p, view);
    float scale = EXTRUDED_CAMERA / (EXTRUDED_CAMERA - v.z);
    return vec3(v.x * scale, v.y * scale, v.z);
}}
// Spectrum's level transfer: the uploaded level (already x0.55) to bar-field heights.
float extrudedHeight(float level) {{
    return min(EXTRUDED_CEILING, pow(clamp(level, 0.0, 1.0), 1.15) * clamp(max(1.0, uHeightScale), 1.0, 1.85));
}}
vec4 extrudedClip(vec3 world, out float itemY) {{
    vec3 screen = extrudedProject(world, uView);
    float h = uField.w;
    vec2 item = vec2(uCentre.x + screen.x * uFit.x * h,
                     uField.y + uField.w - (uFit.y + screen.y * uFit.x) * h);
    itemY = item.y;
    vec4 clip = uMatrix * vec4(item, 0.0, 1.0);
    clip.z = clamp(-screen.z * 0.4, -1.0, 1.0) * clip.w;
    return clip;
}}
"""

EXTRUDED_VERTEX_SOURCE = (
    "#version 460 core\nlayout(location = 0) in vec3 aPosition;\nlayout(location = 1) in vec3 aNormal;\n"
    + _COMMON_UNIFORMS
    + "uniform int uPass;       // 0 bars, 1 ghost columns, 2 reflection\nuniform int uBarCount;\n"
    + "uniform float uHueShift;\n"
    + "flat out vec3 vHue;\nout vec3 vWorld;\nout vec3 vNormal;\nout vec3 vLocal;\nout vec3 vSize;\nout float vItemY;\n"
    + SCENE3D_GLSL + EXTRUDED_BARS.glsl(3) + _PROJECTION_GLSL
    + """
void main() {
    int index = gl_InstanceID;
    ExtrudedBar bar = bars[index];
    float height = extrudedHeight(bar.level);
    float peak = extrudedHeight(bar.peak);
    float bottom = 0.0, top = height;
    if (uPass == 1) {
        // Spectrum's ghost: the column between the bar's top and its falling peak.
        if (peak * uField.w <= height * uField.w + 1.0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
        bottom = height; top = peak;
    } else if (height * uField.w < 0.5) {
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);    // a silent bar draws nothing, as in Spectrum
        return;
    }
    vec3 local = aPosition + 0.5;                 // 0..1 across, up and back to front
    vec3 world = vec3(uBarGeometry.x + float(index) * uBarGeometry.y + (local.x - 0.5) * 2.0 * uBarGeometry.z,
                      mix(bottom, top, local.y), (local.z - 1.0) * uBarGeometry.w);
    vec3 normal = aNormal;
    if (uPass == 2) {                             // the reflection: mirrored under the floor
        world.y = -world.y;
        normal.y = -normal.y;
    }
    vWorld = extrudedView(world, uView);          // lit in the frame the camera sees
    vNormal = extrudedView(normal, uView);
    vLocal = local;
    vSize = vec3(2.0 * uBarGeometry.z, top - bottom, uBarGeometry.w) * uField.w * uFit.x;   // box size in pixels
    // Spectral hues: red at the bass end through to violet at the treble end, drifting.
    float hue = fract(0.8 * float(index) / max(1.0, float(uBarCount - 1)) + uHueShift);
    vHue = mix(vec3(1.0), clamp(abs(mod(hue * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0), 0.85);
    gl_Position = extrudedClip(world, vItemY);
}
"""
)

EXTRUDED_FRAGMENT_SOURCE = (
    "#version 460 core\nflat in vec3 vHue;\nin vec3 vWorld;\nin vec3 vNormal;\nin vec3 vLocal;\nin vec3 vSize;\n"
    "in float vItemY;\nout vec4 FragColor;\n"
    "uniform vec4 uFill;\nuniform vec4 uBorder;\nuniform float uGloss;\nuniform float uEdgePx;\n"
    "uniform int uPass;\nuniform float uGhostAlpha;\nuniform float uReflection;\nuniform int uColouring;\n"
    "uniform vec2 uFloorSpan;   // item y of the floor line and of the bar field's bottom\n"
    "uniform float uSmooth;     // 1: edge lines measured in screen pixels (anti-aliased at any angle)\n"
    "uniform float uMirror;     // polished, reflective faces (never the edge lines)\n"
    + SCENE3D_GLSL
    + """
// A chrome studio around the bars, by reflected direction in the camera's frame: a bright sky
// falling to a grey ground at a crisp horizon set low (the view looks down on the bars, so their
// faces mostly mirror what lies below eye level), and two softbox strips above it.
vec3 extrudedStudio(vec3 r) {
    float h = r.y + 0.3;
    vec3 sky = mix(vec3(0.95, 0.97, 1.0), vec3(0.3, 0.36, 0.48), smoothstep(0.0, 0.8, h));
    vec3 ground = mix(vec3(0.32, 0.3, 0.29), vec3(0.06), smoothstep(0.0, -0.5, h));
    vec3 env = mix(ground, sky, smoothstep(-0.004, 0.004, h));
    float above = smoothstep(0.0, 0.08, h);
    env += vec3(1.5) * smoothstep(0.05, 0.0, abs(r.x - 0.24)) * above;
    env += vec3(1.0) * smoothstep(0.035, 0.0, abs(r.x + 0.3)) * above;
    return env;
}
void main() {
    vec3 n = normalize(vNormal);
    // Distance to the nearest edge of this face, per face axis. The face is the box axis whose
    // local coordinate sits at 0 or 1 (the normal is in the turned, tilted frame). Off, lines are
    // sized in pixels of the face seen head-on, so foreshortening thins them below a pixel. Smooth
    // Edges measures in screen pixels: each line keeps its head-on width (converted to screen
    // pixels along that axis) but never narrower than SMOOTH_MIN_PX, so head-on nothing changes and
    // at an angle a line stays a smooth ramp instead of breaking up.
    const float SMOOTH_MIN_PX = 1.2;
    vec3 perPixel = max(fwidth(vLocal), vec3(1e-6));
    vec3 lo = min(vLocal, 1.0 - vLocal);
    vec3 onFace = step(lo, vec3(1e-3));
    float width = (uColouring == 1 ? 1.6 : 1.0) * uEdgePx;
    vec3 px = lo * vSize;
    vec3 widths = vec3(width);
    if (uSmooth > 0.5) {
        px = lo / perPixel;
        widths = max(width / max(vSize * perPixel, vec3(1e-6)), vec3(SMOOTH_MIN_PX));
    }
    vec2 edge = onFace.x > 0.5 ? px.zy : (onFace.y > 0.5 ? px.xz : px.xy);
    vec2 edgeWidth = onFace.x > 0.5 ? widths.zy : (onFace.y > 0.5 ? widths.xz : widths.xy);
    float rim = max(1.0 - smoothstep(0.0, edgeWidth.x, edge.x), 1.0 - smoothstep(0.0, edgeWidth.y, edge.y));
    // 0 spectral bodies with Spectrum's border edges; 1 Spectrum's body with glowing spectral
    // edges; 2 Spectrum's fill and border.
    vec3 body = uColouring == 0 ? vHue : uFill.rgb;
    vec3 trim = uColouring == 1 ? vHue : uBorder.rgb;
    float trimAlpha = uColouring == 1 ? 1.0 : uBorder.a;
    SceneMaterial bar = SceneMaterial(mix(body, trim, rim * trimAlpha), mix(0.75, 0.18, uGloss), 0.0, 0.5,
                                      uColouring == 1 ? trim * rim * 0.8 : vec3(0.0));
    vec3 lit = sceneMaterialLit(bar, n, vWorld, vec3(2.3), vec3(0.45));
    if (uMirror > 0.0) {
        // Polished faces: the studio reflected toward a near virtual eye at mid-bar height (the
        // real camera is far, so a flat face would mirror one flat colour), so the studio's
        // horizon and lights cross the bars and sweep as the view turns. Faintly brushed,
        // tinted by the face's colour, stronger at grazing angles. Edge lines stay as they are.
        vec3 v = normalize(vec3(0.0, 0.4, 1.6) - vWorld);
        vec3 r = reflect(-v, n);
        vec2 grainAt = floor(vec2(vLocal.x * vSize.x + vLocal.z * vSize.z, vLocal.y * vSize.y * 0.02) * 0.7);
        float grain = fract(sin(dot(grainAt, vec2(12.9898, 78.233))) * 43758.5453);
        vec3 tint = mix(vec3(1.0), body * 1.35, 0.6);
        vec3 mirror = extrudedStudio(r) * tint * (0.92 + 0.16 * grain);
        float fresnel = 0.75 + 0.25 * pow(1.0 - max(dot(n, v), 0.0), 5.0);
        lit = mix(lit, mirror + lit * 0.2, uMirror * fresnel * (1.0 - rim * trimAlpha));
    }
    float alpha = 1.0;
    if (uPass == 1) alpha = uGhostAlpha * mix(0.45, 1.0, rim);
    if (uPass == 2) {
        // The reflection fades with distance below the floor, to nothing at the field's bottom.
        float below = (vItemY - uFloorSpan.x) / max(uFloorSpan.y - uFloorSpan.x, 1.0);
        if (below >= 1.0) discard;
        alpha = uReflection * 0.7 * (1.0 - below) * (1.0 - below);
    }
    FragColor = vec4(lit, alpha);
}
"""
)
