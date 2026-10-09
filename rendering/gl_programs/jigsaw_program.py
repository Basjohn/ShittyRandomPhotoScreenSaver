"""Jigsaw Piece Flip: shaders and CPU mirrors (loaded only when Jigsaw Piece Flip renders).

The cut lines of a jigsaw fade in over the old picture. Then the pieces flip, one after another
in the run's order: each lifts toward the viewer, turns over about an axis across the way the
flips travel and lands on its own place showing its part of the new picture, and its cut line
fades once it has landed. Where a piece is in the air its empty place shows the puzzle board.

A piece is cut from the layout of ``rendering/quick/transitions/piece_layout.py`` (a solid
card: faces, bevel rings, walls). A half turn mirrors a card, and jigsaw pieces are not
symmetric, so while the card is nearly edge-on its outline morphs into its own mirror image; the
half turn then mirrors it back and it lands exactly on its place.

Two passes draw it. The flat pass draws every piece's front face where it rests: the old picture
before the piece flips, the board while it is in the air, the new picture once it has landed,
and the cut lines (measured in screen pixels). The flight pass draws only the pieces in the air,
lit by the shared physically based material blended in by ``sin(pi e)`` of each flip, so both
ends of every flip are the flat pass's pixels. Optional soft shadows (the shared piece shadow)
fall from the pieces in the air.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_GLSL

JIGSAW_MAX_PIECES = 160
JIGSAW_OUTLINE_IN = 0.10      # the cut lines fade in over the first part of the run
JIGSAW_FLIP_START = 0.06
JIGSAW_FLIP_END = 0.97
JIGSAW_LAND_FADE = 0.03       # a landed piece's cut line fades over this much of the run
JIGSAW_THICKNESS = 0.09       # a card's thickness, as a share of the smaller cell side
JIGSAW_HOP = 0.30             # extra lift at mid-flip, as a share of the smaller cell side
JIGSAW_SHADOW = 0.42
_BOARD = (0.88, 0.87, 0.84)
_CARD = (0.80, 0.72, 0.58)


def jigsaw_flip_window(count: int) -> float:
    """Each piece's flip as a share of the run: longer flips for fewer pieces."""
    span = JIGSAW_FLIP_END - JIGSAW_FLIP_START
    return span * max(0.07, min(0.30, 3.5 / max(1, int(count))))


def jigsaw_piece_start(rank: int, count: int) -> float:
    span = JIGSAW_FLIP_END - JIGSAW_FLIP_START
    order = rank / (count - 1) if count > 1 else 0.0
    return JIGSAW_FLIP_START + order * (span - jigsaw_flip_window(count))


def jigsaw_piece_phase(progress: float, rank: int, count: int) -> float:
    """The piece's flip, 0 (resting, old picture up) to 1 (landed): CPU mirror of ``jigsawPhase``."""
    return max(0.0, min(1.0, (float(progress) - jigsaw_piece_start(rank, count)) / jigsaw_flip_window(count)))


def jigsaw_outline_alpha(progress: float, rank: int, count: int) -> float:
    """How strongly the piece's cut line shows: CPU mirror of ``jigsawOutline``."""
    t = float(progress)
    u = max(0.0, min(1.0, t / JIGSAW_OUTLINE_IN))
    alpha = u * u * (3.0 - 2.0 * u)
    end = jigsaw_piece_start(rank, count) + jigsaw_flip_window(count)
    v = max(0.0, min(1.0, (t - end) / JIGSAW_LAND_FADE))
    return alpha * (1.0 - v * v * (3.0 - 2.0 * v))


def jigsaw_flip_pose(phase: float) -> tuple[float, float, float]:
    """(turn angle, outline morph toward the mirror image, light blend) of a flip at ``phase``."""
    e = max(0.0, min(1.0, float(phase)))
    s = e * e * (3.0 - 2.0 * e)
    m = max(0.0, min(1.0, (s - 0.38) / 0.24))
    return math.pi * s, m * m * (3.0 - 2.0 * m), math.sin(math.pi * e)


_SCHEDULE_GLSL = f"""
const float OUTLINE_IN = {JIGSAW_OUTLINE_IN:.6f};
const float FLIP_START = {JIGSAW_FLIP_START:.6f};
const float FLIP_END = {JIGSAW_FLIP_END:.6f};
const float LAND_FADE = {JIGSAW_LAND_FADE:.6f};
uniform float uProgress;
uniform int uCount;
uniform vec4 uPieces[{JIGSAW_MAX_PIECES}];   // centre uv, rank, axis angle
float jigsawWindow() {{
    return (FLIP_END - FLIP_START) * clamp(3.5 / float(max(uCount, 1)), 0.07, 0.30);
}}
float jigsawStart(float rank) {{
    float order = uCount > 1 ? rank / float(uCount - 1) : 0.0;
    return FLIP_START + order * (FLIP_END - FLIP_START - jigsawWindow());
}}
float jigsawPhase(float rank) {{
    return clamp((uProgress - jigsawStart(rank)) / jigsawWindow(), 0.0, 1.0);
}}
float jigsawOutline(float rank) {{
    float end = jigsawStart(rank) + jigsawWindow();
    return smoothstep(0.0, OUTLINE_IN, uProgress) * (1.0 - smoothstep(end, end + LAND_FADE, uProgress));
}}
"""

# The cut line: a dark line on the cut with a faint light lip inside it, both in screen pixels,
# kept off the picture's own border. ``bevel`` is the distance from the cut (scene units).
_OUTLINE_GLSL = """
vec3 jigsawCut(vec3 colour, float bevel, float alpha, vec2 uv, vec2 itemSize) {
    if (alpha <= 0.0) return colour;
    float pixels = bevel / max(fwidth(bevel), 1e-7);
    vec2 border = min(uv, 1.0 - uv) * itemSize;
    float keep = smoothstep(1.5, 3.5, min(border.x, border.y));
    float line = (1.0 - smoothstep(0.35, 1.15, pixels)) * keep * alpha;
    float lip = smoothstep(1.0, 1.6, pixels) * (1.0 - smoothstep(1.6, 2.6, pixels)) * keep * alpha;
    colour = mix(colour, colour * 0.18, 0.85 * line);
    return colour + (1.0 - colour) * 0.22 * lip;
}
"""

_INPUTS_GLSL = (
    "layout(location = 0) in vec2 aUv;\nlayout(location = 1) in float aSide;\n"
    "layout(location = 2) in vec3 aNormal;\nlayout(location = 3) in float aBevel;\n"
    "layout(location = 4) in float aPiece;\n"
    "uniform mat4 uMatrix;\nuniform vec2 uItemSize;\n"
)

JIGSAW_FLAT_VERTEX_SOURCE = (
    "#version 460 core\n" + _INPUTS_GLSL
    + "out vec2 vUv;\nout float vBevel;\nflat out int vState;\nflat out float vAlpha;\nflat out float vShade;\n"
    + SCENE3D_GLSL + _SCHEDULE_GLSL
    + """
void main() {
    vec4 piece = uPieces[int(aPiece)];
    float e = jigsawPhase(piece.z);
    vState = e <= 0.0 ? 0 : (e >= 1.0 ? 2 : 1);
    vAlpha = jigsawOutline(piece.z);
    vShade = 0.30 * sin(SCENE_PI * e);
    vUv = aUv;
    vBevel = aBevel;
    gl_Position = sceneProject(uMatrix, uItemSize, scenePlanePoint(aUv, uItemSize.x / uItemSize.y));
}
"""
)

JIGSAW_FLAT_FRAGMENT_SOURCE = (
    "#version 460 core\n"
    "in vec2 vUv;\nin float vBevel;\nflat in int vState;\nflat in float vAlpha;\nflat in float vShade;\n"
    "out vec4 FragColor;\nuniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform vec2 uItemSize;\n"
    + _OUTLINE_GLSL
    + f"""
void main() {{
    vec3 colour = vState == 0 ? texture(uOldTex, vUv).rgb
                : (vState == 2 ? texture(uNewTex, vUv).rgb
                               : vec3({_BOARD[0]:.6f}, {_BOARD[1]:.6f}, {_BOARD[2]:.6f}) * (1.0 - vShade));
    FragColor = vec4(jigsawCut(colour, vBevel, vAlpha, vUv, uItemSize), 1.0);
}}
"""
)

# The card in the air: rest point -> (morphed, turned, lifted) world point.
_FLIGHT_GLSL = """
uniform vec2 uCell;        // cell width and height (scene units)
uniform float uThick;
uniform float uRadius;     // a card's reach from its centre, knobs included
uniform float uHop;
struct JigsawPose { vec3 axis; float angle; float morph; float lift; float light; vec3 centre; };
JigsawPose jigsawPose(vec4 piece, float e, float aspect) {
    JigsawPose pose;
    float s = e * e * (3.0 - 2.0 * e);
    float m = clamp((s - 0.38) / 0.24, 0.0, 1.0);
    pose.axis = vec3(cos(piece.w), sin(piece.w), 0.0);
    pose.angle = SCENE_PI * s;
    pose.morph = m * m * (3.0 - 2.0 * m);
    pose.light = sin(SCENE_PI * e);
    pose.lift = 0.85 * uRadius * abs(sin(pose.angle)) + uHop * sin(SCENE_PI * e);
    pose.centre = vec3(scenePlanePoint(piece.xy, aspect).xy, pose.lift - 0.5 * uThick);
    return pose;
}
vec2 jigsawMirror(vec2 v, vec2 axis, float morph) {
    return mix(v, 2.0 * dot(v, axis) * axis - v, morph);
}
"""

JIGSAW_FLIGHT_VERTEX_SOURCE = (
    "#version 460 core\n" + _INPUTS_GLSL
    + "out vec2 vUv;\nout vec3 vWorld;\nout vec3 vNormal;\nout float vBevel;\n"
    + "flat out int vKind;\nflat out float vLight;\nflat out float vAlpha;\n"
    + SCENE3D_GLSL + _SCHEDULE_GLSL + _FLIGHT_GLSL
    + """
void main() {
    vec4 piece = uPieces[int(aPiece)];
    float e = jigsawPhase(piece.z);
    if (e <= 0.0 || e >= 1.0) {
        gl_Position = vec4(0.0, 0.0, 2.0, 1.0);   // resting: the flat pass draws it
        return;
    }
    float aspect = uItemSize.x / uItemSize.y;
    JigsawPose pose = jigsawPose(piece, e, aspect);
    vec2 local = scenePlanePoint(aUv, aspect).xy - pose.centre.xy;
    vec3 p = vec3(jigsawMirror(local, pose.axis.xy, pose.morph), aSide * uThick);
    vec3 world = pose.centre + sceneRotate(p, pose.axis, pose.angle);
    vec3 n = vec3(jigsawMirror(aNormal.xy, pose.axis.xy, pose.morph), aNormal.z);
    n = dot(n, n) > 1e-8 ? normalize(n) : vec3(0.0, 0.0, 1.0);
    vWorld = world;
    vNormal = sceneRotate(n, pose.axis, pose.angle);
    vUv = aUv;
    vBevel = aBevel;
    vKind = abs(aNormal.z) < 0.01 ? 2 : (aSide > 0.0 ? 0 : 1);
    vLight = pose.light;
    vAlpha = jigsawOutline(piece.z);
    gl_Position = sceneProject(uMatrix, uItemSize, world);
}
"""
)

JIGSAW_FLIGHT_FRAGMENT_SOURCE = (
    "#version 460 core\n"
    "in vec2 vUv;\nin vec3 vWorld;\nin vec3 vNormal;\nin float vBevel;\n"
    "flat in int vKind;\nflat in float vLight;\nflat in float vAlpha;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform sampler2D uEnvironment;\n"
    "uniform vec2 uItemSize;\n"
    + SCENE3D_GLSL + _OUTLINE_GLSL
    + f"""
void main() {{
    vec3 photo;
    if (vKind == 2) {{
        photo = vec3({_CARD[0]:.6f}, {_CARD[1]:.6f}, {_CARD[2]:.6f});
    }} else {{
        photo = vKind == 0 ? texture(uOldTex, vUv).rgb : texture(uNewTex, vUv).rgb;
        photo = jigsawCut(photo, vBevel, vAlpha, vUv, uItemSize);
    }}
    vec3 n = normalize(vNormal);
    SceneMaterial card = SceneMaterial(photo, 0.5, 0.0, 0.5, vec3(0.0));
    vec3 lit = sceneMaterialLit(card, n, vWorld, vec3(2.6), vec3(0.32))
             + 0.3 * sceneMaterialEnvironment(uEnvironment, card, n, vWorld);
    FragColor = vec4(mix(photo, lit, vLight), 1.0);
}}
"""
)

JIGSAW_SHADOW_VERTEX_SOURCE = (
    "#version 460 core\nlayout(location = 0) in vec2 aPosition;\n"
    "uniform mat4 uMatrix;\nuniform vec2 uItemSize;\n"
    + "out vec2 vLocal;\nflat out float vFeather;\nflat out float vStrength;\n"
    + SCENE3D_GLSL + _SCHEDULE_GLSL + _FLIGHT_GLSL
    + f"""
void main() {{
    vec4 piece = uPieces[gl_InstanceID];
    float e = jigsawPhase(piece.z);
    if (e <= 0.0 || e >= 1.0) {{
        gl_Position = vec4(0.0, 0.0, 2.0, 1.0);
        vLocal = vec2(0.0); vFeather = 0.0; vStrength = 0.0;
        return;
    }}
    JigsawPose pose = jigsawPose(piece, e, uItemSize.x / uItemSize.y);
    ScenePiece card = ScenePiece(pose.centre, vec3(uCell * 1.12, uThick), pose.axis, pose.angle,
                                 vec3(0.0, 0.0, 1.0), 0.0);
    SceneShadow shadow = scenePieceShadow(uMatrix, uItemSize, card, 0.0, aPosition);
    gl_Position = shadow.clip;
    vLocal = shadow.local;
    vFeather = shadow.feather;
    vStrength = {JIGSAW_SHADOW:.6f} * pose.light * shadow.onScreen * shadow.low;
}}
"""
)

# Multiplied onto what is beneath (the flat pass), so the shadow darkens board and pictures alike.
JIGSAW_SHADOW_FRAGMENT_SOURCE = (
    "#version 460 core\n"
    "in vec2 vLocal;\nflat in float vFeather;\nflat in float vStrength;\nout vec4 FragColor;\n"
    + SCENE3D_GLSL
    + """
void main() {
    FragColor = vec4(vec3(1.0 - sceneSoftRect(vLocal, vFeather) * vStrength), 1.0);
}
"""
)
