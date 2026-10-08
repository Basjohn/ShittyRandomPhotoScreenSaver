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
foreshortened below a pixel; head-on nothing changes.

Mirror Faces gives the faces (never the edge lines) a polished
mirror surface reflecting the wallpaper: the displayed photograph, downsampled once per image change
(``widgets/spotify_visualizer/backdrop.py``) into a small mipmapped texture (``BackdropEnvironment``).
A face shows the wallpaper
around it displaced by its reflected ray (taken toward a near virtual eye, so it varies across
the row), sharper with Gloss, so the picture slides across the bars as the view turns.

The view turns a full circle (``turn`` -1..1 is -180..180 degrees and wraps when orbiting) and
tilts from level to straight down (``tilt`` 0..1 is 0..90 degrees).
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import (
    SCENE3D_GLSL,
    SCENE3D_ORBIT_GLSL,
    Scene3DStorageLayout,
    scene3d_orbit_eye,
    scene3d_orbit_project,
)

EXTRUDED_MAX_TILT = math.radians(90.0)
EXTRUDED_MAX_TURN = math.radians(180.0)
# Farther than the transitions' camera: a row of bars spans the whole width, and a near
# camera makes the outer bars lean out like a wide-angle lens.
EXTRUDED_CAMERA = 6.0
EXTRUDED_MAX_DEPTH = 0.6          # a bar's depth never exceeds this many bar-field heights
EXTRUDED_CEILING = 0.95           # Spectrum's tallest bar, in bar-field heights
EXTRUDED_REFLECTION_SPACE = 0.22  # floor lift (bar-field heights) a full reflection reserves
# R127: Two genuinely different shadows, never another maximum-height footprint
# sheet. Nearby is an offset of the actual projected box SILHOUETTE, so it
# follows the visible bar heights. Distant is a ground-contact sweep per bar,
# cast from the actual uploaded height, NOT the fixed scene ceiling. For
# diagonal global directions Distant's lateral motion is deliberately modest:
# preserve the row's horizontal contact baseline instead of the previous giant
# sideways parallelogram. Cardinal E/W retains its full horizontal direction.
EXTRUDED_SHADOW_CAST_REACH = 4.5
EXTRUDED_SHADOW_NEAR_DROP_SCALE = 1.0
EXTRUDED_SHADOW_DIAGONAL_LATERAL_SCALE = 0.15
# The view tilts about the bars' mid-height, so orbiting circles the middle of the scene (level
# views are unchanged; looking straight down keeps the tops where the bars' middle was).
EXTRUDED_PIVOT = 0.5 * EXTRUDED_CEILING
EXTRUDED_HUE_DRIFT_RATE = 0.15    # hue turns per authored second at full drift
# One record per bar, in draw order (``extruded_draw_order``); ``bar`` is the bar's own index.
EXTRUDED_BARS = Scene3DStorageLayout.of("ExtrudedBars", "ExtrudedBar",
                                        (("level", "float"), ("peak", "float"), ("bar", "float")), array="bars")


def extruded_project(point: tuple[float, float, float], tilt: float,
                     turn: float = 0.0) -> tuple[float, float, float]:
    """CPU mirror of ``extrudedProject``: (screen x, screen y up, view depth) of a world point."""
    pivot = (0.0, EXTRUDED_PIVOT, 0.0)
    return scene3d_orbit_project(point, tilt, turn, camera=EXTRUDED_CAMERA, pivot=pivot, anchor=pivot)


def extruded_shadow_project(point: tuple[float, float, float], tilt: float, turn: float,
                            shadow_vector: tuple[float, float],
                            shadow_mode: str = "Distant") -> tuple[float, float, float]:
    """CPU mirror of one shadow vertex, in the same screen axes as the global direction.

    Nearby translates the true 3D projected point (a silhouette/drop shadow).
    Distant starts at the *physical foot* and projects the real audible bar
    height, with reduced lateral travel for diagonal directions. A flat-height
    footprint sheet is never drawn. The camera orbit changes the base point,
    not the global shadow direction.
    """
    sx, sy = shadow_vector
    if shadow_mode == "Nearby":
        screen = extruded_project(point, tilt, turn)
        return (screen[0] + sx * EXTRUDED_SHADOW_NEAR_DROP_SCALE,
                screen[1] - sy * EXTRUDED_SHADOW_NEAR_DROP_SCALE, screen[2])
    if shadow_mode != "Distant":
        raise ValueError(f"invalid Extruded shadow mode {shadow_mode!r}")
    foot = extruded_project((point[0], 0.0, point[2]), tilt, turn)
    reach = point[1] * EXTRUDED_SHADOW_CAST_REACH
    lateral = EXTRUDED_SHADOW_DIAGONAL_LATERAL_SCALE if sx and sy else 1.0
    return (foot[0] + sx * reach * lateral,
            foot[1] - sy * reach, foot[2])


def extruded_draw_order(first: float, step: float, count: int, tilt: float, turn: float) -> list[int]:
    """The bars' indices in a painter's order for the translucent passes (ghost columns, the floor
    reflection): farthest from the eye along the row first. The boxes occupy disjoint x intervals,
    so a plane of constant x separates any two; of two bars on the same side of the eye the
    farther draws first, and two on opposite sides cannot cover each other. ``first`` and ``step``
    are the first bar's centre x and the bar step in world units (``uBarGeometry``)."""
    pivot = (0.0, EXTRUDED_PIVOT, 0.0)
    eye_x = scene3d_orbit_eye(tilt, turn, camera=EXTRUDED_CAMERA, pivot=pivot, anchor=pivot)[0]
    return sorted(range(count), key=lambda index: (-abs(first + index * step - eye_x), index))


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


def extruded_reach(field, centre: float, half_span: float, depth: float, tilt: float, turn: float,
                   fit: tuple[float, float], reflection: float,
                   shadow_vector: tuple[float, float] = (0.0, 0.0),
                   shadow_mode: str = "Distant") -> tuple[float, float, float, float]:
    """The item-local (left, top, right, bottom) extent of everything the bars can draw for this
    view: every bar at the ceiling over its full depth, its floor reflection and, when admitted,
    genuine bar silhouettes for Nearby or the maximum possible actual-height
    cast for Distant. Fixed per view and shape, never per frame of music."""
    scale, floor = fit
    top, height = float(field[1]), float(field[3])
    low = -EXTRUDED_CEILING if reflection > 0.0 else 0.0
    points = [extruded_project((x, y, z), tilt, turn) for x in (-half_span, half_span)
              for y in (low, 1.05 * EXTRUDED_CEILING) for z in (-depth, 0.0)]
    if shadow_vector != (0.0, 0.0):
        # Nearby needs its full, vertically projected silhouette. Distant
        # bounds the actual bar heights (which may approach the ceiling).
        points.extend(
            extruded_shadow_project((x, y, z), tilt, turn, shadow_vector, shadow_mode)
            for x in (-half_span, half_span) for y in (0.0, EXTRUDED_CEILING)
            for z in (-depth, 0.0)
        )
    xs = [centre + p[0] * scale * height for p in points]
    ys = [top + height - (floor + p[1] * scale) * height for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def extruded_footprint(field, centre: float, first: float, step: float, half_width: float,
                       depth: float, tilt: float, turn: float, fit: tuple[float, float],
                       levels, peaks, height_scale: float, *, body_visible: bool,
                       ghost_alpha: float, reflection: float,
                       shadow_vector: tuple[float, float] = (0.0, 0.0),
                       shadow_mode: str = "Distant"):
    """Item-local bounds of the admitted boxes in one accepted rendered frame.

    Inputs are the renderer's *uploaded* levels, not logical Spectrum levels.
    Unlike target-allocation ``extruded_reach``, this projects actual bar/peak
    heights and exactly the enabled pass geometry. It runs only on Edit edges.
    """
    scale, floor = fit
    height = float(field[3])
    projected = []

    def include(x, y, z):
        px, py, _ = extruded_project((x, y, z), tilt, turn)
        projected.append((centre + px * scale * height,
                          field[1] + height - (floor + py * scale) * height))

    def include_shadow(x, y, z):
        px, py, _ = extruded_shadow_project((x, y, z), tilt, turn, shadow_vector, shadow_mode)
        projected.append((centre + px * scale * height,
                          field[1] + height - (floor + py * scale) * height))

    for index, level in enumerate(levels):
        bar_height = extruded_height(level, height_scale)
        peak_height = extruded_height(peaks[index], height_scale)
        xs = (first + index * step - half_width, first + index * step + half_width)
        zs = (-depth, 0.0)
        if bar_height * height >= 0.5:
            for x in xs:
                for z in zs:
                    if body_visible:
                        include(x, 0.0, z)
                        include(x, bar_height, z)
                    if reflection > 0.0:
                        include(x, 0.0, z)
                        include(x, -bar_height, z)
                    if shadow_vector != (0.0, 0.0):
                        # Follow actual admitted audio heights. Nearby shadows
                        # copy the 3D silhouette; Distant sweeps from its base.
                        include_shadow(x, 0.0, z)
                        include_shadow(x, bar_height, z)
        if ghost_alpha > 0.0 and peak_height * height > bar_height * height + 1.0:
            for x in xs:
                for z in zs:
                    include(x, bar_height, z)
                    include(x, peak_height, z)
    if not projected:
        return None
    return (min(p[0] for p in projected), min(p[1] for p in projected),
            max(p[0] for p in projected), max(p[1] for p in projected))


_COMMON_UNIFORMS = """
uniform mat4 uMatrix;
uniform vec4 uField;        // bar field in item coordinates: left, top, width, height
uniform vec2 uCentre;       // bar row centre x and floor's height, item coordinates
uniform vec4 uBarGeometry;  // first bar's centre x, bar step, bar half width, bar depth (world units)
uniform vec2 uFit;          // fit scale, floor height in the field (0 bottom .. 1 top)
uniform vec2 uView;         // tilt, turn (radians)
uniform float uHeightScale;
"""

_PROJECTION_GLSL = SCENE3D_ORBIT_GLSL + f"""
const float EXTRUDED_CEILING = {EXTRUDED_CEILING:.6f};
const float EXTRUDED_CAMERA = {EXTRUDED_CAMERA:.6f};
const float EXTRUDED_SHADOW_CAST_REACH = {EXTRUDED_SHADOW_CAST_REACH:.6f};
const float EXTRUDED_SHADOW_NEAR_DROP_SCALE = {EXTRUDED_SHADOW_NEAR_DROP_SCALE:.6f};
const float EXTRUDED_SHADOW_DIAGONAL_LATERAL_SCALE = {EXTRUDED_SHADOW_DIAGONAL_LATERAL_SCALE:.6f};
const float EXTRUDED_PIVOT = {EXTRUDED_PIVOT:.6f};
// The shared orbit (scene3d.py), the tilt pivoting about the bars' mid-height, which stays put.
vec3 extrudedView(vec3 p, vec2 view) {{ return sceneOrbitView(p, view); }}
vec3 extrudedViewPoint(vec3 p, vec2 view) {{
    vec3 pivot = vec3(0.0, EXTRUDED_PIVOT, 0.0);
    return sceneOrbitPoint(p, view, pivot, pivot);
}}
vec3 extrudedProject(vec3 p, vec2 view) {{
    vec3 pivot = vec3(0.0, EXTRUDED_PIVOT, 0.0);
    return sceneOrbitProject(p, view, pivot, pivot, EXTRUDED_CAMERA);
}}
vec3 extrudedShadowProject(vec3 p, vec2 shadow, vec2 view, int shadowMode) {{
    if (shadowMode == 0) {{
        vec3 silhouette = extrudedProject(p, view);
        silhouette.xy += vec2(shadow.x, -shadow.y) * EXTRUDED_SHADOW_NEAR_DROP_SCALE;
        return silhouette;
    }}
    vec3 foot = extrudedProject(vec3(p.x, 0.0, p.z), view);
    float lateral = (shadow.x != 0.0 && shadow.y != 0.0)
                    ? EXTRUDED_SHADOW_DIAGONAL_LATERAL_SCALE : 1.0;
    foot.xy += vec2(shadow.x * lateral, -shadow.y) * p.y * EXTRUDED_SHADOW_CAST_REACH;
    return foot;
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
    clip.z = clamp(-screen.z / EXTRUDED_CAMERA, -1.0, 1.0) * clip.w;   // nearer than the camera, so inside
    return clip;
}}
"""

EXTRUDED_VERTEX_SOURCE = (
    "#version 460 core\nlayout(location = 0) in vec3 aPosition;\nlayout(location = 1) in vec3 aNormal;\n"
    + _COMMON_UNIFORMS
    + "uniform int uPass;       // 0 opaque bars, 1 ghost columns, 2 reflection, 3 translucent bars, 4 shadow\nuniform int uBarCount;\nuniform vec2 uShadowVector;\nuniform int uShadowMode;\n"
    + "uniform float uHueShift;\n"
    + "flat out vec3 vHue;\nout vec3 vWorld;\nout vec3 vNormal;\nout vec3 vLocal;\nout vec3 vSize;\nout float vItemY;\n"
    + SCENE3D_GLSL + EXTRUDED_BARS.glsl(3) + _PROJECTION_GLSL
    + """
void main() {
    ExtrudedBar bar = bars[gl_InstanceID];        // records come in draw order (extruded_draw_order)
    int index = int(bar.bar + 0.5);
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
    if (uPass == 4) {
        // Nearby: translated SILHOUETTE (same bars, not a connected wedge).
        // Distant: grounded sweep from each ACTUAL bar height. The old
        // constant-ceiling footprint sheet is deliberately impossible here.
        vec3 shadowPoint = extrudedShadowProject(world, uShadowVector, uView, uShadowMode);
        float h = uField.w;
        vec2 item = vec2(uCentre.x + shadowPoint.x * uFit.x * h,
                         uField.y + h - (uFit.y + shadowPoint.y * uFit.x) * h);
        vItemY = item.y;
        gl_Position = uMatrix * vec4(item, 0.0, 1.0);
        vWorld = shadowPoint;
        vNormal = vec3(0.0, 1.0, 0.0);
        vLocal = local;
        vSize = vec3(1.0);
        vHue = vec3(0.0);
        return;
    }
    vWorld = extrudedViewPoint(world, uView);     // lit in the frame the camera sees
    vNormal = extrudedView(normal, uView);
    vLocal = local;
    vSize = vec3(2.0 * uBarGeometry.z, top - bottom, uBarGeometry.w) * uField.w * uFit.x;   // box size in pixels
    // Spectral hues: red at the bass end through to violet at the treble end, drifting.
    float hue = fract(0.8 * float(index) / max(1.0, float(uBarCount - 1)) + uHueShift);
    vHue = mix(vec3(1.0), clamp(abs(mod(hue * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0), 0.85);
    gl_Position = extrudedClip(world, vItemY);
    if (uPass == 1 || uPass == 2 || uPass == 3) {
        // Translucent passes keep only the faces turned toward the eye (at the view frame's
        // (0, 0, camera)), so a box never blends over itself; in painter's order that is exact.
        // (A plane faces the eye at all its points or none, so per-vertex agrees across a face.)
        if (dot(vNormal, vec3(0.0, 0.0, EXTRUDED_CAMERA) - vWorld) <= 0.0) gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    }
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
    "uniform sampler2D uBackdrop;   // what Quick drew under the Visualizer, mipmapped\n"
    "uniform vec4 uBackdropMap;     // (gl_FragCoord.xy + xy) / zw is the backdrop's uv\n"
    "uniform sampler2D uBackdropPrevious; // the wallpaper before a change, faded out by uBackdropBlend\n"
    "uniform float uBackdropBlend;\nuniform vec4 uShadowColor;\nuniform vec2 uShadowVector;\n"
    + SCENE3D_GLSL + SCENE3D_ORBIT_GLSL
    + """
void main() {
    if (uPass == 4) {
        // Shadow union uses GL_MAX inside a transparent overlay target. Store
        // premultiplied RGB so SceneTarget's straight-alpha composite can divide
        // by alpha exactly once; overlapping box faces then never darken twice.
        FragColor = vec4(uShadowColor.rgb * uShadowColor.a, uShadowColor.a);
        return;
    }
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
    float rim = sceneLineCoverage(edge, edgeWidth);
    // 0 spectral bodies with Spectrum's border edges; 1 Spectrum's body with glowing spectral
    // edges; 2 Spectrum's fill and border.
    vec3 body = uColouring == 0 ? vHue : uFill.rgb;
    vec3 trim = uColouring == 1 ? vHue : uBorder.rgb;
    float trimAlpha = uColouring == 1 ? 1.0 : uBorder.a;
    float edgeAlpha = rim * trimAlpha;
    float surfaceAlpha = uFill.a + (1.0 - uFill.a) * edgeAlpha;
    float trimMix = surfaceAlpha > 0.0 ? edgeAlpha / surfaceAlpha : 0.0;
    SceneMaterial bar = SceneMaterial(mix(body, trim, trimMix), mix(0.75, 0.18, uGloss), 0.0, 0.5,
                                      uColouring == 1 ? trim * rim * 0.8 : vec3(0.0));
    vec3 lit = sceneMaterialLit(bar, n, vWorld, vec3(2.3), vec3(0.45));
    if (uMirror > 0.0) {
        // Polished faces reflecting the wallpaper around them: the backdrop where this pixel
        // sits, displaced by the reflected ray toward a near virtual eye at mid-bar height (the
        // real camera is far, so a flat face would mirror one patch), mirrored past the screen's
        // edges, sharper with Gloss. The picture slides across the bars as the view turns.
        // Lightly tinted by the face's colour, stronger at grazing angles.
        // Edge lines stay as they are.
        vec3 v = normalize(vec3(0.0, 0.4, 1.6) - vWorld);
        vec3 r = reflect(-v, n);
        vec2 uv = (gl_FragCoord.xy + uBackdropMap.xy) / uBackdropMap.zw + vec2(r.x, r.y) * 0.35;
        uv = 1.0 - abs(1.0 - mod(uv, 2.0));
        float lod = mix(3.0, 0.4, uGloss);
        vec3 seen = mix(textureLod(uBackdropPrevious, uv, lod).rgb, textureLod(uBackdrop, uv, lod).rgb,
                        uBackdropBlend);
        vec3 tint = mix(vec3(1.0), body * 1.35, 0.25);
        vec3 mirror = seen * tint + lit * 0.15;
        float fresnel = 0.8 + 0.2 * pow(1.0 - max(dot(n, v), 0.0), 5.0);
        lit = mix(lit, mirror, uMirror * fresnel * (1.0 - rim * trimAlpha));
    }
    float alpha = uPass == 3 ? surfaceAlpha : 1.0;
    if (uPass == 1) alpha = uGhostAlpha * mix(0.45, 1.0, rim);
    if (uPass == 2) {
        // The reflection fades with distance below the floor, to nothing at the field's bottom.
        float below = (vItemY - uFloorSpan.x) / max(uFloorSpan.y - uFloorSpan.x, 1.0);
        if (below >= 1.0) discard;
        alpha = uReflection * 0.7 * (1.0 - below) * (1.0 - below);
    }
    // A translucent box now blends once (its far faces are culled); give that one layer the
    // opacity its front and back faces used to add up to, so Ghost and Reflection keep their look.
    if (uPass == 1 || uPass == 2) { alpha = clamp(alpha, 0.0, 1.0); alpha = alpha * (2.0 - alpha); }
    FragColor = vec4(lit, alpha);
}
"""
)
