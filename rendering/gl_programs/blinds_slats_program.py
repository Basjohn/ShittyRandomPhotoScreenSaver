"""Blinds -> 3D Slats: shaders, mesh and CPU mirrors (loaded only when Blinds renders).

Each stripe of the picture is a solid slat: the old picture on its front, the new one on its
back, a thin laminated edge between. The slats turn over one after another in a wave (each
for ``BLINDS_SLAT_TURN`` of the run, eased in and out) about their long axis, which runs
through the middle of the slat's thickness, so a slat's front lies exactly on the
photograph at rest and its back lies exactly there once turned. Through the gaps a turning
slat opens, the new picture shows, shaded by the slats in front of it.

Lighting uses the shared physically based material (``sceneMaterialLit`` and a photo
reflection of the new picture through ``sceneMaterialEnvironment``), blended in by each
slat's ``lift`` (4e(1 - e) of its eased turn): zero at rest, so both ends of the run and every
slat not yet turning or done are the photographs exactly.
"""

from __future__ import annotations

from rendering.gl_programs.scene3d import SCENE3D_GLSL

# Each slat's share of the run, and its thickness as a share of its width.
BLINDS_SLAT_TURN = 0.5
BLINDS_SLAT_THICKNESS = 0.12
# How much a turning slat darkens the new picture behind it (at its steepest).
BLINDS_SLAT_SHADE = 0.55


def blinds_slat_phase(progress: float, index: int, count: int) -> float:
    """The slat's eased turn, 0 (front) to 1 (turned over): CPU mirror of ``blindsSlatPhase``."""
    start = (index / (count - 1) if count > 1 else 0.0) * (1.0 - BLINDS_SLAT_TURN)
    u = max(0.0, min(1.0, (float(progress) - start) / BLINDS_SLAT_TURN))
    return u * u * (3.0 - 2.0 * u)


def blinds_slat_lift(progress: float, index: int, count: int) -> float:
    """How far the slat is from resting flat (0 at rest, 1 edge-on): CPU mirror of ``blindsSlatLift``."""
    e = blinds_slat_phase(progress, index, count)
    return 4.0 * e * (1.0 - e)


def _box() -> tuple[float, ...]:
    """A unit box (positions in [-0.5, 0.5]^3) as 36 vertices of position + outward normal."""
    faces = (
        ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
        ((1, 0, 0), (0, 1, 0), (0, 0, 1)), ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
        ((0, 1, 0), (0, 0, 1), (1, 0, 0)), ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
    )
    values: list[float] = []
    for normal, a, b in faces:
        centre = [0.5 * n for n in normal]
        corners = [[centre[k] + 0.5 * (sa * a[k] + sb * b[k]) for k in range(3)]
                   for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        for corner in (corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]):
            values.extend((*corner, *normal))
    return tuple(float(value) for value in values)


BLINDS_SLAT_BOX_VERTICES = _box()
BLINDS_SLAT_BOX_ATTRIBUTES = (3, 3)

_SCHEDULE_GLSL = f"""
const float SLAT_TURN = {BLINDS_SLAT_TURN:.6f};
float blindsSlatPhase(float progress, int index, int count) {{
    float start = (count > 1 ? float(index) / float(count - 1) : 0.0) * (1.0 - SLAT_TURN);
    float u = clamp((progress - start) / SLAT_TURN, 0.0, 1.0);
    return u * u * (3.0 - 2.0 * u);
}}
float blindsSlatLift(float progress, int index, int count) {{
    float e = blindsSlatPhase(progress, index, count);
    return 4.0 * e * (1.0 - e);
}}
"""

BLINDS_SLATS_VERTEX_SOURCE = (
    "#version 460 core\n"
    "layout(location = 0) in vec3 aPosition;\n"
    "layout(location = 1) in vec3 aNormal;\n"
    "uniform mat4 uMatrix;\nuniform vec2 uItemSize;\n"
    "uniform float uProgress;\nuniform int uCount;\nuniform int uVertical;\n"
    "out vec2 vSourceUv;\nout vec2 vDestinationUv;\nout vec3 vWorld;\nout vec3 vNormal;\n"
    "out float vFrontHalf;\nflat out int vFace;\nflat out float vLift;\n"
    + SCENE3D_GLSL + _SCHEDULE_GLSL
    + f"""
const float SLAT_THICKNESS = {BLINDS_SLAT_THICKNESS:.6f};
// A point of the slat (along, across) in the frame: across runs from the slat's centre line
// toward the top (rows) or the right (columns); turned is its height and its across offset.
vec3 slatPoint(float centre, float along, vec2 turned, float aspect) {{
    if (uVertical == 1) return vec3((centre - 0.5) * aspect + turned.x, along, turned.y);
    return vec3(along, 0.5 - centre + turned.x, turned.y);
}}
void main() {{
    int index = gl_InstanceID;
    float count = float(uCount);
    float aspect = uItemSize.x / uItemSize.y;
    float along = (uVertical == 1 ? 1.0 : aspect) * aPosition.x;
    float width = uVertical == 1 ? aspect / count : 1.0 / count;
    float thick = SLAT_THICKNESS * width;
    float centre = (float(index) + 0.5) / count;
    float across = aPosition.y * width;
    // Turn about the long axis through the middle of the thickness (z = -thick / 2).
    float angle = SCENE_PI * blindsSlatPhase(uProgress, index, uCount);
    float c = cos(angle), s = sin(angle);
    float z = aPosition.z * thick;
    vec2 turned = vec2(across * c - z * s, across * s + z * c - 0.5 * thick);
    vec2 normal = vec2(aNormal.y * c - aNormal.z * s, aNormal.y * s + aNormal.z * c);
    vec3 world = slatPoint(centre, along, turned, aspect);
    vWorld = world;
    vNormal = uVertical == 1 ? vec3(normal.x, aNormal.x, normal.y) : vec3(aNormal.x, normal.x, normal.y);
    // The front shows the old picture where the slat rests; the back the new picture where
    // it rests once turned over (across mirrored).
    vSourceUv = scenePlaneUv(slatPoint(centre, along, vec2(across, 0.0), aspect).xy, aspect);
    vDestinationUv = scenePlaneUv(slatPoint(centre, along, vec2(-across, 0.0), aspect).xy, aspect);
    vFrontHalf = aPosition.z + 0.5;
    vFace = aNormal.z > 0.5 ? 0 : (aNormal.z < -0.5 ? 1 : 2);
    vLift = blindsSlatLift(uProgress, index, uCount);
    gl_Position = sceneProject(uMatrix, uItemSize, world);
}}
"""
)

BLINDS_SLATS_FRAGMENT_SOURCE = (
    "#version 460 core\n"
    "in vec2 vSourceUv;\nin vec2 vDestinationUv;\nin vec3 vWorld;\nin vec3 vNormal;\n"
    "in float vFrontHalf;\nflat in int vFace;\nflat in float vLift;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform sampler2D uEnvironment;\n"
    "uniform float uGloss;\n"
    + SCENE3D_GLSL
    + """
void main() {
    vec3 photo;
    if (vFace == 0) {
        photo = texture(uOldTex, vSourceUv).rgb;
    } else if (vFace == 1) {
        photo = texture(uNewTex, vDestinationUv).rgb;
    } else {
        // The laminated edge: the old picture's border in its front half, the new one's behind.
        photo = (vFrontHalf > 0.5 ? texture(uOldTex, vSourceUv).rgb : texture(uNewTex, vDestinationUv).rgb) * 0.8;
    }
    if (vLift <= 0.0) {
        FragColor = vec4(photo, 1.0);   // at rest: the photograph exactly
        return;
    }
    vec3 n = normalize(vNormal);
    SceneMaterial material = SceneMaterial(photo, mix(0.7, 0.18, uGloss), 0.0, 0.5, vec3(0.0));
    vec3 lit = sceneMaterialLit(material, n, vWorld, vec3(2.6), vec3(0.32))
             + uGloss * sceneMaterialEnvironment(uEnvironment, material, n, vWorld);
    FragColor = vec4(mix(photo, lit, vLift), 1.0);
}
"""
)

# The new picture behind the slats, darkened where its slat is turning.
BLINDS_BACKDROP_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uNewTex;\nuniform float uProgress;\nuniform int uCount;\nuniform int uVertical;\n"
    + _SCHEDULE_GLSL
    + f"""
void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float position = uVertical == 1 ? uv.x : uv.y;
    int index = clamp(int(floor(position * float(uCount))), 0, uCount - 1);
    float shade = {BLINDS_SLAT_SHADE:.6f} * blindsSlatLift(uProgress, index, uCount);
    FragColor = vec4(texture(uNewTex, uv).rgb * (1.0 - shade), 1.0);
}}
"""
)
