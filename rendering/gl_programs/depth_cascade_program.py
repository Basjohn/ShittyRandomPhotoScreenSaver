"""Depth Card Cascade: shaders and CPU mirrors (loaded only when Depth Card Cascade renders).

The old picture separates into a few large cards (``card_partition``,
rendering/gl_programs/depth_cards.py) that lift off one after another in a wave across the
picture, tilt as they rise and slide past the viewer and out of the frame, accelerating, so later
cards pass over the ones still lying flat; the new picture lies beneath. Each lifted card casts a
soft shadow on the new picture that grows fainter and softer as it rises; its face picks up the
shared material's light as it tilts and a thin bright rim marks its edge. A card that has not
moved is the photograph exactly; every card has left the frame by ``CASCADE_DONE``.
"""

from __future__ import annotations

import math
import random

from rendering.gl_programs.depth_cards import CARD_GLSL, card_partition, card_pose
from rendering.gl_programs.scene3d import SCENE3D_CAMERA, SCENE3D_GLSL

CASCADE_CARDS_RANGE = (4, 14)
CASCADE_STAGGER = 0.5       # the run's share over which cards start, first to last along the sweep
CASCADE_JITTER = 0.05
CASCADE_FLIGHT = 0.4        # each card's flight, a share of the run
CASCADE_DONE = round(CASCADE_STAGGER + CASCADE_JITTER + CASCADE_FLIGHT, 6)
CASCADE_LIFT = 0.9
CASCADE_TURN = 0.7
CASCADE_SPREAD = 0.6         # radians either side of the sweep a card's slide may turn
CASCADE_SHADOW = 0.5
CASCADE_LIGHT = (-0.35, 0.5, 1.0)


def cascade_cards(seed: int, count: int, aspect: float, sweep: tuple[float, float]) -> list[tuple[float, ...]]:
    """Per card: (x0, y0, x1, y1, start, slide angle, turn sign, slide distance)."""
    rng = random.Random(seed ^ 0x5C4D)
    rects = card_partition(seed, count, aspect)
    reach = 0.5 * aspect * abs(sweep[0]) + 0.5 * abs(sweep[1])
    heading = math.atan2(sweep[1], sweep[0])
    cards = []
    for x0, y0, x1, y1 in rects:
        cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        rank = 0.5 + (cx * sweep[0] + cy * sweep[1]) / (2.0 * reach)
        start = CASCADE_STAGGER * max(0.0, min(1.0, rank)) + rng.uniform(0.0, CASCADE_JITTER)
        angle = heading + rng.uniform(-CASCADE_SPREAD, CASCADE_SPREAD)
        cards.append((x0, y0, x1, y1, start, angle, rng.choice((-1.0, 1.0)),
                      cascade_exit((x0, y0, x1, y1), angle, aspect)))
    return cards


def cascade_exit(rect, angle: float, aspect: float) -> float:
    """How far a card slides along ``angle`` to clear the frame by the end of its flight: past
    the edge it heads for by its own half-diagonal (whatever its turn) and a margin."""
    x0, y0, x1, y1 = rect
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    half = 0.5 * math.hypot(x1 - x0, y1 - y0)
    dx, dy = math.cos(angle), math.sin(angle)
    reach = []
    if abs(dx) > 1e-6:
        reach.append(((0.5 * aspect if dx > 0 else -0.5 * aspect) - cx) / dx)
    if abs(dy) > 1e-6:
        reach.append(((0.5 if dy > 0 else -0.5) - cy) / dy)
    return min(reach) + half + 0.12


def _smooth(edge0: float, edge1: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def cascade_flight(progress: float, start: float) -> float:
    return max(0.0, min(1.0, (progress - start) / CASCADE_FLIGHT))


def cascade_corner(card, local: tuple[float, float], progress: float) -> tuple[float, float, float]:
    """CPU mirror of a card corner's world position (``cascadePose``)."""
    x0, y0, x1, y1, start, angle, sign, distance = card
    tau = cascade_flight(progress, start)
    corner = (x0 + (x1 - x0) * local[0], y0 + (y1 - y0) * local[1])
    centre = (0.5 * (x0 + x1), 0.5 * (y0 + y1))
    direction = (math.cos(angle), math.sin(angle))
    lift = CASCADE_LIFT * _smooth(0.0, 0.6, tau) + 0.3 * tau
    slide = (direction[0] * distance * tau ** 2.2, direction[1] * distance * tau ** 2.2)
    turn = sign * CASCADE_TURN * _smooth(0.0, 1.0, tau)
    return card_pose((corner[0] - centre[0], corner[1] - centre[1]), centre, (-direction[1], direction[0]), turn,
                     lift, slide)


def screen_point(world) -> tuple[float, float]:
    """The pinhole projection of a world point onto the picture plane (picture heights)."""
    scale = SCENE3D_CAMERA / (SCENE3D_CAMERA - world[2])
    return world[0] * scale, world[1] * scale


_POSE = f"""
uniform float uProgress;
const float FLIGHT = {CASCADE_FLIGHT:.6f};
const float LIFT = {CASCADE_LIFT:.6f};
const float TURN = {CASCADE_TURN:.6f};
// A card corner's world position, its face normal and how far through its flight it is.
vec3 cascadePose(vec2 local, vec4 rect, vec4 card, out vec3 normal, out float flight) {{
    vec2 corner = mix(rect.xy, rect.zw, local);
    vec2 centre = 0.5 * (rect.xy + rect.zw);
    flight = clamp((uProgress - card.x) / FLIGHT, 0.0, 1.0);
    vec2 direction = vec2(cos(card.y), sin(card.y));
    float lift = LIFT * smoothstep(0.0, 0.6, flight) + 0.3 * flight;
    vec2 slide = direction * card.w * pow(flight, 2.2);
    float turn = card.z * TURN * smoothstep(0.0, 1.0, flight);
    vec2 axis = vec2(-direction.y, direction.x);
    normal = vec3(axis.y * sin(turn), -axis.x * sin(turn), cos(turn));
    return cardPose(corner - centre, centre, axis, turn, lift, slide);
}}
"""

_VERTEX_HEAD = ("#version 460 core\nlayout(location = 0) in vec2 aLocal;\nlayout(location = 1) in vec4 aRect;\n"
                "layout(location = 2) in vec4 aCard;\nuniform mat4 uMatrix;\nuniform vec2 uItemSize;\n")

CASCADE_VERTEX_SOURCE = (
    _VERTEX_HEAD + "out vec2 vUv;\nout vec2 vLocal;\nout vec2 vSize;\nout vec3 vWorld;\nout vec3 vNormal;\n"
    "out float vFlight;\n" + SCENE3D_GLSL + CARD_GLSL + _POSE + """
void main() {
    vec3 normal;
    float flight;
    vec3 world = cascadePose(aLocal, aRect, aCard, normal, flight);
    float aspect = uItemSize.x / uItemSize.y;
    vUv = scenePlaneUv(mix(aRect.xy, aRect.zw, aLocal), aspect);
    vLocal = aLocal;
    vSize = aRect.zw - aRect.xy;
    vWorld = world;
    vNormal = normal;
    vFlight = flight;
    gl_Position = sceneProject(uMatrix, uItemSize, world);
}
""")

CASCADE_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nin vec2 vLocal;\nin vec2 vSize;\nin vec3 vWorld;\nin vec3 vNormal;\n"
    "in float vFlight;\nout vec4 FragColor;\nuniform sampler2D uOldTex;\nuniform sampler2D uEnvironment;\n"
    "uniform float uGloss;\n" + SCENE3D_GLSL + """
void main() {
    vec3 photo = texture(uOldTex, vUv).rgb;
    if (vFlight <= 0.0) {
        FragColor = vec4(photo, 1.0);      // not yet moving: the photograph exactly
        return;
    }
    float moving = smoothstep(0.0, 0.15, vFlight);
    vec3 n = normalize(vNormal);
    SceneMaterial m = SceneMaterial(photo, mix(0.6, 0.2, uGloss), 0.0, 0.5, vec3(0.0));
    vec3 lit = sceneMaterialLit(m, n, vWorld, vec3(2.3), vec3(0.4))
             + uGloss * 0.6 * sceneMaterialEnvironment(uEnvironment, m, n, vWorld);
    // The card's edge: a thin bright rim over a slight bevel shadow.
    vec2 fromEdge = min(vLocal, 1.0 - vLocal) * vSize;
    float edge = min(fromEdge.x, fromEdge.y);
    float aa = max(fwidth(edge), 1e-5);
    float rim = 1.0 - smoothstep(0.0, 1.6 * aa, edge);
    float bevel = 1.0 - smoothstep(0.0, 6.0 * aa, edge);
    vec3 colour = mix(photo, lit, moving) * (1.0 - 0.25 * bevel * moving) + vec3(0.95) * 0.55 * rim * moving;
    FragColor = vec4(colour, 1.0);
}
""")

CASCADE_SHADOW_VERTEX_SOURCE = (
    _VERTEX_HEAD + "out vec2 vLocal;\nout vec2 vSize;\nout float vLift;\nout float vFlight;\n" + SCENE3D_GLSL + CARD_GLSL + _POSE
    + f"""
const vec3 LIGHT = vec3({CASCADE_LIGHT[0]:.6f}, {CASCADE_LIGHT[1]:.6f}, {CASCADE_LIGHT[2]:.6f});
void main() {{
    vec3 normal;
    float flight;
    vec3 world = cascadePose(aLocal, aRect, aCard, normal, flight);
    vLocal = aLocal;
    vSize = aRect.zw - aRect.xy;
    vLift = world.z;
    vFlight = flight;
    gl_Position = sceneProject(uMatrix, uItemSize, vec3(cardShadow(world, LIGHT), 0.0));
}}
""")

CASCADE_SHADOW_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vLocal;\nin vec2 vSize;\nin float vLift;\nin float vFlight;\nout vec4 FragColor;\n"
    + f"""
void main() {{
    // Fainter and softer the higher the card: a soft-edged dark print of it on the new picture.
    vec2 fromEdge = min(vLocal, 1.0 - vLocal) * vSize;
    float soft = 0.012 + 0.07 * vLift;
    float inside = smoothstep(0.0, soft, min(fromEdge.x, fromEdge.y));
    // ...and gone before its card leaves: a high card's shadow falls aside of it and could linger.
    float strength = {CASCADE_SHADOW:.6f} * smoothstep(0.0, 0.08, vLift) * (1.0 - smoothstep(0.4, 1.6, vLift))
                   * (1.0 - smoothstep(0.55, 0.85, vFlight));
    FragColor = vec4(0.0, 0.0, 0.0, strength * inside);
}}
""")
