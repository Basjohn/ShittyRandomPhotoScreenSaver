"""Instanced block-shell renderer for the experimental Sphere visualizer.

The rejected smooth icosphere representation deliberately does not survive in
this module.  One cube mesh and one static stepped-shell instance buffer are
allocated lazily on the owning GL context, deformed entirely in the vertex
shader from the immutable authored Sphere snapshot, and retired with the normal
visualizer renderer lifecycle.
"""
from __future__ import annotations

import ctypes
import math

import numpy as np
from OpenGL import GL as gl

from core.logging.logger import get_logger, is_viz_diagnostics_enabled
from core.settings.shadow_direction import ShadowDirection, shadow_direction_signs
from rendering.quick.render.gl_resources import compile_program
from widgets.spotify_visualizer.render_state import SphereFrame

from ..render_contract import QuickVisualizerRenderFrame
from .sphere_voxel_geometry import (
    VOXEL_HALF_EXTENT,
    VOXEL_INSTANCE_STRIDE_FLOATS,
    VOXEL_VERTEX_STRIDE_FLOATS,
    build_voxel_cube_mesh,
    build_voxel_shell_instances,
)


# The block shell is intentionally given headroom for authored whole-body pulse
# and radial block extrusion.  This is a new representation, not a compressed
# copy of the rejected smooth-sphere silhouette.
SPHERE_RADIUS_FRACTION = 0.215

_SPHERE_SECTION_COUNT = 8
_PARTICLE_COHORT_COUNT = 4

logger = get_logger(__name__)


def sphere_pixel_geometry(presentation) -> tuple[float, float, float]:
    """Resolve isotropic Sphere geometry from the assigned content footprint."""

    x, y, width, height = presentation.content_rect
    outer_x, outer_y, _, _ = presentation.outer_rect
    radius = min(width, height) * SPHERE_RADIUS_FRACTION
    return x - outer_x + width * 0.5, y - outer_y + height * 0.5, radius


def sphere_depth_scissor(frame: QuickVisualizerRenderFrame) -> tuple[int, int, int, int]:
    """Project the assigned viewport so depth clearing cannot escape ownership."""

    p = frame.snapshot.presentation
    x, y, width, height = p.content_rect
    x -= p.outer_rect[0]
    y -= p.outer_rect[1]
    m = frame.matrix_values
    if abs(m[1]) > 1e-7 or abs(m[4]) > 1e-7 or abs(m[3]) > 1e-7 or abs(m[7]) > 1e-7:
        raise ValueError("Sphere depth viewport requires an axis-aligned transform")
    if abs(m[15]) < 1e-9:
        raise ValueError("Sphere depth viewport has an invalid homogeneous scale")
    vx, vy, vw, vh = frame.viewport
    xs = tuple(vx + ((m[0] * px + m[12]) / m[15] + 1.0) * vw * 0.5 for px in (x, x + width))
    ys = tuple(vy + ((m[5] * py + m[13]) / m[15] + 1.0) * vh * 0.5 for py in (y, y + height))
    left, right = max(vx, math.floor(min(xs))), min(vx + vw, math.ceil(max(xs)))
    bottom, top = max(vy, math.floor(min(ys))), min(vy + vh, math.ceil(max(ys)))
    return left, bottom, max(0, right - left), max(0, top - bottom)


def _project_local_rect(
    frame: QuickVisualizerRenderFrame,
    rect: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    """Project one item-local rect to framebuffer scissor coordinates."""

    x, y, width, height = rect
    m = frame.matrix_values
    if abs(m[1]) > 1e-7 or abs(m[4]) > 1e-7 or abs(m[3]) > 1e-7 or abs(m[7]) > 1e-7:
        raise ValueError("Sphere overflow viewport requires an axis-aligned transform")
    if abs(m[15]) < 1e-9:
        raise ValueError("Sphere overflow viewport has an invalid homogeneous scale")
    vx, vy, vw, vh = frame.viewport
    xs = tuple(vx + ((m[0] * px + m[12]) / m[15] + 1.0) * vw * 0.5 for px in (x, x + width))
    ys = tuple(vy + ((m[5] * py + m[13]) / m[15] + 1.0) * vh * 0.5 for py in (y, y + height))
    left, right = max(vx, math.floor(min(xs))), min(vx + vw, math.ceil(max(xs)))
    bottom, top = max(vy, math.floor(min(ys))), min(vy + vh, math.ceil(max(ys)))
    return left, bottom, max(0, right - left), max(0, top - bottom)


def sphere_overflow_scissor(
    frame: QuickVisualizerRenderFrame,
    *,
    fragment_strength: float,
    particle_distance: float,
) -> tuple[int, int, int, int]:
    """Return the Sphere-only depth-clear footprint for unclipped overflow.

    The local stencil may be bypassed, but depth ownership must remain bounded.
    This expands only to the current mode's worst possible radial travel and is
    clamped to the inherited render target.
    """

    presentation = frame.snapshot.presentation
    cx, cy, radius = sphere_pixel_geometry(presentation)
    fragment_radial = 0.68 * max(0.0, float(fragment_strength))
    particle_radial = 0.88 + 0.42 * max(0.0, float(particle_distance))
    max_radial = max(fragment_radial, particle_radial)
    extent = radius * (1.22 + max_radial)
    return _project_local_rect(
        frame,
        (cx - extent, cy - extent, extent * 2.0, extent * 2.0),
    )


_VERTEX_SOURCE = f"""#version 410 core
layout(location = 0) in vec3 aPosition;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec3 aInstanceCenter;
layout(location = 3) in float aInstanceSeed;
layout(location = 4) in float aRadialPolarity;

uniform mat4 uMatrix;
uniform vec3 uGeometry;
uniform float uSectionDrives[8];
uniform float uFragmentStrength;
uniform float uParticleDistance;
uniform float uParticleAmount;
uniform float uPerspectiveStrength;
uniform float uRotationPhase;
uniform float uSizePulse;
uniform float uBlockRelief;
uniform int uFadeIncoming;
uniform float uIncomingDrive;
uniform float uIncomingDensity;
uniform int uIncomingSection;
uniform int uIncomingPreviousSection;
uniform float uIncomingBlend;
uniform int uCohortCount;
uniform float uCohortProgress[4];
uniform float uCohortStrength[4];
uniform float uCohortDensity[4];
uniform float uCohortVelocity[4];
uniform float uCohortBounce[4];
uniform int uCohortSection[4];
uniform int uCohortLane[4];
uniform int uCohortOuttake[4];
uniform int uRenderPass;
uniform float uTracerDrive;
uniform float uTracerPhase;

out vec3 vScreenCenter;
out vec3 vLocalPosition;
out vec3 vWorldLocalPosition;
flat out vec3 vLocalFaceNormal;
flat out vec3 vWorldFaceNormal;
out float vArrivalFade;
out float vTracer;
flat out float vRainbowCoordinate;

mat3 rotation() {{
    vec3 angle = uRotationPhase * vec3(0.21, 0.57, 0.29);
    vec3 c = cos(angle), s = sin(angle);
    mat3 rx = mat3(1,0,0, 0,c.x,s.x, 0,-s.x,c.x);
    mat3 ry = mat3(c.y,0,-s.y, 0,1,0, s.y,0,c.y);
    mat3 rz = mat3(c.z,s.z,0, -s.z,c.z,0, 0,0,1);
    return rz * ry * rx;
}}

mat3 axisAngle(vec3 axis, float angle) {{
    axis = normalize(axis);
    float c = cos(angle);
    float s = sin(angle);
    float t = 1.0 - c;
    return mat3(
        t*axis.x*axis.x + c,          t*axis.x*axis.y + s*axis.z, t*axis.x*axis.z - s*axis.y,
        t*axis.x*axis.y - s*axis.z,   t*axis.y*axis.y + c,        t*axis.y*axis.z + s*axis.x,
        t*axis.x*axis.z + s*axis.y,   t*axis.y*axis.z - s*axis.x, t*axis.z*axis.z + c
    );
}}

float sectionField(vec3 direction) {{
    const vec3 sectionDirs[8] = vec3[8](
        normalize(vec3( 1.0,  1.0,  1.0)),
        normalize(vec3(-1.0,  1.0,  1.0)),
        normalize(vec3( 1.0, -1.0,  1.0)),
        normalize(vec3(-1.0, -1.0,  1.0)),
        normalize(vec3( 1.0,  1.0, -1.0)),
        normalize(vec3(-1.0,  1.0, -1.0)),
        normalize(vec3( 1.0, -1.0, -1.0)),
        normalize(vec3(-1.0, -1.0, -1.0))
    );
    float drive = 0.0;
    for (int i = 0; i < 8; ++i) {{
        float alignment = dot(direction, normalize(sectionDirs[i]));
        float weight = smoothstep(0.62, 0.95, alignment);
        weight *= weight;
        drive += uSectionDrives[i] * weight;
    }}
    return clamp(drive, 0.0, 1.0);
}}

float stableFlowSelection(vec3 direction, int dominant, int lane, float densityScale) {{
    // Every cohort reuses the same stable per-voxel rank. Event identity and
    // current dominance never re-hash the foundational population. The selected
    // quadrant receives the familiar +24% fringe while all four participate.
    int quadrant = (direction.x < 0.0 ? 1 : 0) | (direction.y < 0.0 ? 2 : 0);
    float admission = 0.46 + (quadrant == (dominant & 3) ? 0.24 : 0.0);
    admission *= clamp(densityScale, 0.0, 1.0);
    admission = clamp(admission * clamp(uParticleAmount, 0.25, 1.75), 0.0, 1.0);
    float pick = fract(
        aInstanceSeed * 19.371
        + float(quadrant) * 0.271
        + 0.137
    );
    float threshold = 1.0 - admission;
    float selected = smoothstep(threshold - 0.028, threshold + 0.028, pick);
    // Four fixed cohort lanes partition the eligible population. Concurrent
    // cohorts therefore travel independently instead of repeatedly resetting
    // the same majority of shell voxels. The partition is spatially scrambled,
    // so it cannot form visible quadrant/lattice seams.
    float lanePick = fract(aInstanceSeed * 43.117 + float(quadrant) * 0.193 + 0.419);
    int stableLane = int(floor(lanePick * 4.0)) & 3;
    selected *= stableLane == (lane & 3) ? 1.0 : 0.0;
    float axisDistance = min(abs(direction.x), abs(direction.y));
    float seamFeather = smoothstep(0.00, 0.16, axisDistance);
    return selected * mix(0.82, 1.0, seamFeather);
}}

float incomingField(vec3 direction) {{
    // Legacy aggregate fallback retained only for no-cohort compatibility.
    // Live Sphere travel is cohort-authored below.
    int dominant = clamp(uIncomingSection, 0, 7) & 3;
    int previousDominant = clamp(uIncomingPreviousSection, 0, 7) & 3;
    int quadrant = (direction.x < 0.0 ? 1 : 0) | (direction.y < 0.0 ? 2 : 0);
    float dominanceBlend = smoothstep(0.0, 1.0, clamp(uIncomingBlend, 0.0, 1.0));
    float previousBoost = quadrant == previousDominant ? 0.24 : 0.0;
    float currentBoost = quadrant == dominant ? 0.24 : 0.0;
    float admission = 0.46 + mix(previousBoost, currentBoost, dominanceBlend);
    admission *= clamp(uIncomingDensity, 0.0, 1.0);
    admission = clamp(admission * clamp(uParticleAmount, 0.25, 1.75), 0.0, 1.0);
    float pick = fract(aInstanceSeed * 19.371 + float(quadrant) * 0.271 + 0.137);
    float threshold = 1.0 - admission;
    float selected = smoothstep(threshold - 0.028, threshold + 0.028, pick);
    float axisDistance = min(abs(direction.x), abs(direction.y));
    float seamFeather = smoothstep(0.00, 0.16, axisDistance);
    return clamp(uIncomingDrive, 0.0, 1.0) * selected * mix(0.82, 1.0, seamFeather);
}}

float cohortTravel(float progress, float velocityAccent) {{
    float p = clamp(progress, 0.0, 1.0);
    float gentle = p * p * (3.0 - 2.0 * p);
    // A strong transient may move faster early, but both curves decelerate to a
    // true settle at p=1. This changes geometry only; cohort admission is already
    // authored by the runtime.
    float transientFast = 1.0 - pow(max(0.0, 1.0 - p), 1.70);
    // Captured duration now carries most of the speed response. Keep only a small
    // curve accent here so a strong hit feels eager without making the visual
    // trajectory collapse back to the old near-binary fast path.
    return mix(gentle, transientFast, 0.18 * clamp(velocityAccent, 0.0, 1.0));
}}

void particleFlow(
    vec3 direction,
    out float intakeRadial,
    out float baseAlpha,
    out float outtakeRadial,
    out float outtakeAlpha,
    out float flowActivity
) {{
    intakeRadial = 0.0;
    baseAlpha = 1.0;
    outtakeRadial = 0.0;
    outtakeAlpha = 0.0;
    flowActivity = 0.0;

    if (uFadeIncoming == 0) return;

    if (uCohortCount <= 0) {{
        float legacy = incomingField(direction);
        intakeRadial = legacy;
        if (legacy > 0.0) {{
            float incomingReturn = 1.0 - smoothstep(0.08, 0.92, legacy);
            baseAlpha = min(baseAlpha, mix(0.08, 1.0, incomingReturn));
            flowActivity = legacy;
        }}
        return;
    }}

    for (int i = 0; i < 4; ++i) {{
        if (i >= uCohortCount) break;
        float strength = clamp(uCohortStrength[i], 0.0, 1.0);
        if (strength <= 0.001) continue;
        float selected = stableFlowSelection(
            direction, uCohortSection[i], uCohortLane[i], uCohortDensity[i]
        );
        if (selected <= 0.001) continue;

        float progress = clamp(uCohortProgress[i], 0.0, 1.0);
        float travel = cohortTravel(progress, uCohortVelocity[i]);
        flowActivity = max(flowActivity, selected * strength * (1.0 - progress));

        if (uCohortOuttake[i] != 0) {{
            // Outtake: source voxel leaves the shell while its canonical
            // replacement fades in underneath. The replacement is rendered in
            // the base pass; the departing source is rendered by uRenderPass=1.
            float radial = selected * strength * travel;
            outtakeRadial = max(outtakeRadial, radial);
            float sourceFade = 1.0 - smoothstep(0.16, 0.96, travel);
            outtakeAlpha = max(outtakeAlpha, selected * sourceFade);
            float replacementFade = smoothstep(0.08, 0.72, travel);
            baseAlpha = min(baseAlpha, mix(1.0, replacementFade, selected));
        }} else {{
            // Intake: the actual shell voxel begins detached and returns to its
            // own canonical slot. Vocal-owned cohorts retain a small late-flight
            // outward recoil before the final settle.
            float recoilX = (progress - 0.70) / 0.115;
            float recoil = 0.15 * clamp(uCohortBounce[i], 0.0, 1.0)
                         * exp(-recoilX * recoilX);
            float remaining = clamp(1.0 - travel + recoil, 0.0, 1.20);
            intakeRadial = max(intakeRadial, selected * strength * remaining);

            // Intake fade is intentionally gentler than outtake and follows
            // authored cohort time rather than the accelerated travel curve.
            // Strong acoustic impacts may become visible sooner, while quiet/flat
            // admitted events fade in across most of their longer journey.
            float velocity = clamp(uCohortVelocity[i], 0.0, 1.0);
            float fadeEnd = mix(0.96, 0.72, velocity);
            float fadeFloor = mix(0.018, 0.060, velocity);
            float arrival = mix(
                fadeFloor, 1.0, smoothstep(0.02, fadeEnd, progress)
            );

            // Vocal recoil is allowed to push an intake voxel farther outward
            // than its launch distance.  Instead of exposing a hard viewport/card
            // clip when that happens, fade only the over-launch excursion through
            // a small radial field; canonical travel/recoil amplitude is untouched.
            float excursionFade = 1.0 - smoothstep(1.00, 1.18, remaining);
            arrival *= excursionFade;
            baseAlpha = min(baseAlpha, mix(1.0, arrival, selected));
        }}
    }}
}}

float wrappedAngle(float angle) {{
    return atan(sin(angle), cos(angle));
}}

float tracerField(vec3 direction) {{
    float drive = clamp(uTracerDrive, 0.0, 1.0);
    if (drive <= 0.002) return 0.0;

    // One connected spherical ribbon segment rather than several tiny moving
    // point heads. The old point sampling crossed gaps between discrete voxels
    // and looked like stationary flicker even while phase was advancing.
    float longitude = atan(direction.z, direction.x);
    float latitude = asin(clamp(direction.y, -1.0, 1.0));
    float pathLatitude = 0.30 * sin(longitude * 1.55 + 0.55);
    float lateral = abs(latitude - pathLatitude);
    // Long and narrow: keep enough soft cross-fade that discrete voxels hand the
    // highlight to neighbours rather than blinking one block on/off in place.
    // Keep geometry nearly constant while intensity changes. Earlier versions
    // resized the ribbon as drive decayed, causing one voxel to blink even when
    // phase movement was numerically correct.
    float ribbonWidth = 0.102;
    float crossGate = 1.0 - smoothstep(ribbonWidth, ribbonWidth + 0.135, lateral);

    float longitudinal = wrappedAngle(longitude - uTracerPhase);
    float tailLength = 0.82 + 0.16 * drive;
    float frontGate = 1.0 - smoothstep(0.08, 0.34, longitudinal);
    float rearGate = smoothstep(-tailLength - 0.24, -tailLength + 0.10, longitudinal);
    float tailTaper = mix(0.34, 1.0, smoothstep(-tailLength, 0.08, longitudinal));
    float driveGate = smoothstep(0.05, 0.18, drive);
    return clamp(crossGate * frontGate * rearGate * tailTaper * driveGate, 0.0, 1.0);
}}

void main() {{
    vec3 direction = normalize(aInstanceCenter);
    float localDrive = sectionField(direction);

    float polarityScale = aRadialPolarity > 0.0 ? 1.12 : 0.72;
    float radial = localDrive * (0.68 * uFragmentStrength) * aRadialPolarity * polarityScale;

    float intakeRadial = 0.0;
    float baseAlpha = 1.0;
    float outtakeRadial = 0.0;
    float outtakeAlpha = 0.0;
    float flowActivity = 0.0;
    particleFlow(
        direction, intakeRadial, baseAlpha, outtakeRadial, outtakeAlpha, flowActivity
    );
    float flowScale = 0.88 + 0.42 * clamp(uParticleDistance, 0.0, 4.5);

    float arrivalFade = 1.0;
    if (uRenderPass == 1) {{
        // Dedicated outgoing-source overlay. The base pass has already rendered
        // the canonical replacement geometry at its authored fade level.
        radial += outtakeRadial * flowScale;
        arrivalFade = outtakeAlpha;
    }} else {{
        radial += intakeRadial * flowScale;
        arrivalFade = baseAlpha;
    }}

    float bodyScale = 1.0 + uSizePulse;
    vec3 center = aInstanceCenter * bodyScale + direction * radial;

    float seedVariation = (aInstanceSeed - 0.5) * 0.18 * uBlockRelief;
    float blockGrowth = 1.0 + 0.28 * uSizePulse;
    float halfExtent = {VOXEL_HALF_EXTENT:.9f}
                     * max(0.58, 1.0 + seedVariation)
                     * blockGrowth;

    // Intentional version of the useful "one bright block" accident.  Stronger
    // articulation extends the head into a short snake. Selected cubes rotate
    // around deterministic local axes before the rigid shell rotation.
    float tracer = uRenderPass == 1 ? 0.0 : tracerField(direction);
    vec3 localAxis = normalize(vec3(
        fract(aInstanceSeed * 7.137 + 0.11) - 0.5,
        fract(aInstanceSeed * 11.731 + 0.37) - 0.5,
        fract(aInstanceSeed * 17.193 + 0.73) - 0.5
    ) + vec3(0.07, 0.11, 0.13));
    float localAngle = tracer * mix(0.008, 0.050, clamp(uTracerDrive, 0.0, 1.0));
    localAngle *= 0.94 + 0.06 * sin(aInstanceSeed * 23.17 + uTracerPhase * 0.61);
    mat3 localTurn = axisAngle(localAxis, localAngle);

    mat3 turn = rotation();
    vec3 turnedCenter = turn * center;
    vec3 turnedPosition = turnedCenter + turn * (localTurn * (aPosition * halfExtent));

    vScreenCenter = turnedCenter;
    vLocalPosition = aPosition;
    vWorldLocalPosition = turn * (localTurn * aPosition);
    // Binding invariant: stable face/bevel identity stays unrotated even when a
    // tracer cube receives local geometric rotation. A separate smoothly rotated
    // face normal is supplied only for physically directed finish lighting.
    vLocalFaceNormal = aNormal;
    vWorldFaceNormal = normalize(turn * (localTurn * aNormal));
    vArrivalFade = arrivalFade;
    vTracer = tracer;
    // A coherent shell-space coordinate gives neighbouring voxels neighbouring
    // hues. Only ~22% of the spectrum is visible across the shell at once; the
    // whole window drifts over time in the fragment stage.
    // Cheap coherent shell-space plane gradient: no atan/trig and no extra
    // per-voxel CPU state. Neighbouring voxels receive neighbouring hues.
    vRainbowCoordinate = clamp(
        0.5 + 0.5 * dot(direction, normalize(vec3(0.71, 0.46, 0.31))),
        0.0,
        1.0
    );
    // 1.0 is the accepted projection exactly; lower values only flatten it
    // toward orthographic so this optional control can never exceed the golden
    // perspective/overflow envelope.
    float cameraW = (4.8 - turnedPosition.z * uPerspectiveStrength) / 4.8;
    vec2 local = uGeometry.xy * cameraW
               + vec2(turnedPosition.x, -turnedPosition.y) * uGeometry.z;
    gl_Position = uMatrix * vec4(local, 0.0, cameraW);
    gl_Position.z = (-turnedPosition.z / 3.2) * gl_Position.w;
}}
"""

_FRAGMENT_SOURCE = """#version 410 core
in vec3 vScreenCenter;
in vec3 vLocalPosition;
in vec3 vWorldLocalPosition;
flat in vec3 vLocalFaceNormal;
flat in vec3 vWorldFaceNormal;
in float vArrivalFade;
in float vTracer;
flat in float vRainbowCoordinate;
out vec4 fragColor;

uniform vec3 uLight;
uniform float uGloss;
uniform float uSpecular;
uniform vec4 uFillColor;
uniform vec4 uEdgeColor;
uniform float uFade;
uniform int uCelShading;
uniform int uRainbowSurfaces;
uniform int uRainbowEdges;
uniform float uRainbowPhase;

vec3 rainbowRgb(float hue) {
    vec3 p = abs(fract(hue + vec3(0.0, 0.6666667, 0.3333333)) * 6.0 - 3.0);
    vec3 pure = clamp(p - 1.0, 0.0, 1.0);
    return mix(vec3(1.0), pure, 0.82);
}

void main() {
    if (vArrivalFade <= 0.001) discard;
    vec3 light = normalize(uLight);
    vec2 lightXY = normalize(light.xy);
    vec2 lightPerp = vec2(-lightXY.y, lightXY.x);

    // Key illumination is screen anchored.  Rigid shell rotation and tracer-local
    // cube rotation cannot move the authored light quadrant.
    float directional = dot(vScreenCenter.xy, lightXY);
    float shellDiffuse = clamp(0.56 + 0.44 * directional, 0.12, 1.0);

    // Stable local face identity is the accepted anti-snap seam.
    vec3 absLocalFace = abs(normalize(vLocalFaceNormal));
    float faceModel = 0.88
                    + absLocalFace.y * 0.10
                    + absLocalFace.z * 0.06
                    - absLocalFace.x * 0.04;
    vec2 faceUV = absLocalFace.x > 0.5
                ? vLocalPosition.yz
                : (absLocalFace.y > 0.5 ? vLocalPosition.xz : vLocalPosition.xy);
    float edgeCoordinate = max(abs(faceUV.x), abs(faceUV.y));
    float edgeAA = max(fwidth(edgeCoordinate), 0.006);
    float edgeDefinition = smoothstep(0.72 - edgeAA, 0.90 + edgeAA, edgeCoordinate);

    float gloss = clamp(uGloss, 0.0, 1.0);
    float specularStrength = clamp(uSpecular, 0.0, 2.0);

    // Finish is tied to the actual fixed light source, not an arbitrary face-UV
    // stripe. The stable local face normal still owns bevel/edge identity; this
    // separately rotated normal may only affect continuous lighting, so it cannot
    // recreate the old UV-axis snapping bug.
    vec3 worldNormal = normalize(vWorldFaceNormal);
    vec3 viewDir = vec3(0.0, 0.0, 1.0);
    vec3 halfDir = normalize(light + viewDir);
    float faceDiffuse = max(0.0, dot(worldNormal, light));
    float sourceSide = smoothstep(0.02, 0.46, directional);
    float specExponent = mix(10.0, 96.0, gloss);
    float specLobe = pow(max(0.0, dot(worldNormal, halfDir)), specExponent) * sourceSide;

    // A narrow edge sheen is permitted only on the side of each face pointing
    // toward the light. This is the "gloss line" and it cannot appear on the
    // dark/opposite side simply because of local UV orientation.
    vec3 faceOffset = vWorldLocalPosition - worldNormal * dot(vWorldLocalPosition, worldNormal);
    float offsetLength = max(length(faceOffset), 1.0e-5);
    float towardLight = dot(faceOffset / offsetLength, light);
    float lineThreshold = mix(0.08, 0.58, gloss);
    float sourceEdge = edgeDefinition * smoothstep(lineThreshold, 0.96, towardLight) * sourceSide;
    float glossSheen = gloss * sourceEdge * (0.08 + 0.20 * faceDiffuse);
    float specEnergy = specularStrength * specLobe * mix(0.05, 0.34, gloss);
    float edgeSheen = sourceEdge * specularStrength * mix(0.04, 0.14, gloss);

    vec3 base = max(uFillColor.rgb, vec3(0.001));
    vec3 edgeColor = uEdgeColor.rgb;
    if (uRainbowSurfaces != 0 || uRainbowEdges != 0) {
        float rainbowHue = fract(uRainbowPhase + 0.22 * vRainbowCoordinate);
        vec3 rainbowColor = rainbowRgb(rainbowHue);
        if (uRainbowSurfaces != 0) base = max(rainbowColor, vec3(0.001));
        if (uRainbowEdges != 0) edgeColor = rainbowColor;
    }
    vec3 color;

    if (uCelShading != 0) {
        // Proper toon: hard diffuse plateaus, strong ink, and a hard highlight
        // patch. No smooth diffuse interpolation survives this branch.
        float toonLighting = clamp(shellDiffuse * 0.38 + faceDiffuse * 0.62, 0.0, 1.0);
        float toonBand = toonLighting < 0.24 ? 0.16
                       : (toonLighting < 0.46 ? 0.40
                       : (toonLighting < 0.70 ? 0.68 : 1.04));
        vec3 toonBase = max(base, vec3(0.045));
        color = toonBase * toonBand * faceModel;
        float ink = clamp(smoothstep(0.42, 0.72, edgeDefinition), 0.0, 1.0);
        color = mix(color, edgeColor * 0.16, ink);
        float toonHighlight = step(0.62, specLobe) * step(0.54, toonLighting);
        color += vec3(1.0, 0.97, 0.86)
               * toonHighlight
               * (0.08 + 0.14 * gloss + 0.14 * specularStrength);
    } else {
        color = base * (0.20 + 0.88 * shellDiffuse) * faceModel;
        color = mix(color, edgeColor, edgeDefinition * 0.46);
        color += vec3(1.0, 0.985, 0.95) * (glossSheen + specEnergy);
        color += mix(edgeColor, vec3(1.0), 0.70) * edgeSheen;
        float rim = smoothstep(0.67, 1.03, length(vScreenCenter.xy));
        color += mix(base, vec3(1.0), 0.48) * rim * (0.025 + 0.18 * gloss);
    }

    // Intentional tracer: preserve the happy-accident bright block as a causal
    // articulation cue.  Stronger drive creates a short snake in the vertex stage.
    color = mix(color, vec3(1.0, 0.95, 0.76), clamp(vTracer * 0.72, 0.0, 0.76));

    // Much gentler mapping than the rejected finish path; it no longer compresses
    // matte and glossy results back toward the same output.
    color = max(color, vec3(0.0));
    color = color / (vec3(1.0) + color * 0.18);
    color = pow(color, vec3(1.0 / 2.2));

    // Fill and edge alpha are independent authored channels. Fully opaque
    // edges remain opaque around a translucent fill interior.
    // Alpha separation needs a decisive edge mask, not the same soft coverage
    // used for RGB shading. This makes a full-alpha Edge Color remain visibly
    // opaque even when the authored fill is very translucent.
    float alphaEdge = smoothstep(0.22, 0.58, edgeDefinition);
    float authoredAlpha = mix(uFillColor.a, uEdgeColor.a, alphaEdge);
    fragColor = vec4(
        color,
        clamp(uFade * vArrivalFade * authoredAlpha, 0.0, 1.0)
    );
}
"""

_SHADOW_VERTEX_SOURCE = """#version 410 core
layout(location = 0) in vec2 aPosition;
uniform mat4 uMatrix;
uniform vec2 uCenter;
uniform float uRadius;
uniform vec2 uScreenOffset;
out vec2 vShadowUV;
void main() {
    vShadowUV = aPosition * 2.0 - 1.0;
    vec2 local = uCenter + uScreenOffset + vShadowUV * uRadius;
    gl_Position = uMatrix * vec4(local, 0.0, 1.0);
}
"""

_SHADOW_FRAGMENT_SOURCE = """#version 410 core
in vec2 vShadowUV;
out vec4 fragColor;
uniform vec4 uShadowColor;
uniform float uFade;
uniform float uFeather;
void main() {
    // A literal flat 2D drop shadow: one soft disc, one alpha value. There is no
    // cube geometry, Z, face overlap or lighting state in this pass.
    float d = length(vShadowUV);
    float feather = clamp(uFeather, 0.03, 0.45);
    float alpha = 1.0 - smoothstep(1.0 - feather, 1.0, d);
    if (alpha <= 0.001) discard;
    fragColor = vec4(uShadowColor.rgb, uShadowColor.a * uFade * alpha);
}
"""

class QuickSphereVoxelRenderer:
    mode_id = "sphere"

    def __init__(self) -> None:
        self._program = 0
        self._shadow_program = 0
        self._shadow_uniforms: dict[str, int] = {}
        self._vao = 0
        self._mesh_vbo = 0
        self._instance_vbo = 0
        self._vertex_count = 0
        self._instance_count = 0
        self._uniforms: dict[str, int] = {}
        self._parameters = None
        self._light = (0.0, 0.0, 1.0)
        self._light_xy = (0.0, 0.0)

    @property
    def has_resources(self) -> bool:
        return bool(
            self._program or self._shadow_program or self._vao
            or self._mesh_vbo or self._instance_vbo
        )

    @staticmethod
    def _upload_particle_cohorts(uniforms: dict[str, int], cohorts) -> None:
        """Upload at most four immutable Sphere travel cohorts to one program."""

        items = tuple(cohorts[:_PARTICLE_COHORT_COUNT])
        progress = np.ones(_PARTICLE_COHORT_COUNT, dtype=np.float32)
        strength = np.zeros(_PARTICLE_COHORT_COUNT, dtype=np.float32)
        density = np.zeros(_PARTICLE_COHORT_COUNT, dtype=np.float32)
        velocity = np.zeros(_PARTICLE_COHORT_COUNT, dtype=np.float32)
        bounce = np.zeros(_PARTICLE_COHORT_COUNT, dtype=np.float32)
        section = np.zeros(_PARTICLE_COHORT_COUNT, dtype=np.int32)
        lane = np.zeros(_PARTICLE_COHORT_COUNT, dtype=np.int32)
        outtake = np.zeros(_PARTICLE_COHORT_COUNT, dtype=np.int32)
        for index, cohort in enumerate(items):
            progress[index] = max(0.0, min(1.0, float(cohort.progress)))
            strength[index] = max(0.0, min(1.0, float(cohort.strength)))
            density[index] = max(0.0, min(1.0, float(cohort.density)))
            velocity[index] = max(0.0, min(1.0, float(cohort.velocity_accent)))
            bounce[index] = max(0.0, min(1.0, float(cohort.vocal_bounce)))
            section[index] = int(cohort.section) & 3
            lane[index] = int(cohort.lane) & 3
            outtake[index] = 1 if bool(cohort.outtake) else 0
        gl.glUniform1i(uniforms["uCohortCount"], len(items))
        gl.glUniform1fv(uniforms["uCohortProgress"], _PARTICLE_COHORT_COUNT, progress)
        gl.glUniform1fv(uniforms["uCohortStrength"], _PARTICLE_COHORT_COUNT, strength)
        gl.glUniform1fv(uniforms["uCohortDensity"], _PARTICLE_COHORT_COUNT, density)
        gl.glUniform1fv(uniforms["uCohortVelocity"], _PARTICLE_COHORT_COUNT, velocity)
        gl.glUniform1fv(uniforms["uCohortBounce"], _PARTICLE_COHORT_COUNT, bounce)
        gl.glUniform1iv(uniforms["uCohortSection"], _PARTICLE_COHORT_COUNT, section)
        gl.glUniform1iv(uniforms["uCohortLane"], _PARTICLE_COHORT_COUNT, lane)
        gl.glUniform1iv(uniforms["uCohortOuttake"], _PARTICLE_COHORT_COUNT, outtake)

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        state = frame.snapshot.logical.mode_state
        if not isinstance(state, SphereFrame):
            raise TypeError("Sphere voxel renderer received another mode frame")
        if not self._program:
            self._initialize()

        parameters = state.parameters
        if parameters != self._parameters:
            direction = ShadowDirection(parameters["sphere_light_direction"])
            x, y = shadow_direction_signs(direction)
            length = math.sqrt(x * x + y * y + 2.25)
            self._light = (x / length, -y / length, 1.5 / length)
            self._light_xy = (float(x), float(y))
            self._parameters = parameters
            if is_viz_diagnostics_enabled():
                logger.debug(
                    "[SPHERE_RENDER] fill_rgba=%s edge_rgba=%s "
                    "toon=%s tracer=%s gloss=%.3f specular=%.3f shadow=%s rainbow=%s/%s/%s light=%s",
                    parameters["sphere_fill_color"],
                    parameters["sphere_edge_color"],
                    bool(parameters["sphere_cel_shading"]),
                    bool(parameters["sphere_light_tracer_enabled"]),
                    float(parameters["sphere_gloss"]),
                    float(parameters["sphere_specular"]),
                    bool(parameters["sphere_shadow_enabled"]),
                    bool(parameters["sphere_taste_the_rainbow_enabled"]),
                    bool(parameters["sphere_taste_the_rainbow_surfaces"]),
                    bool(parameters["sphere_taste_the_rainbow_edges"]),
                    parameters["sphere_light_direction"],
                )

        u = self._uniforms
        count = min(_SPHERE_SECTION_COUNT, len(state.section_drives))
        section_drives = np.zeros(_SPHERE_SECTION_COUNT, dtype=np.float32)
        if count:
            section_drives[:count] = np.asarray(
                [max(0.0, min(1.0, float(value))) for value in state.section_drives[:count]],
                dtype=np.float32,
            )

        presentation = frame.snapshot.presentation
        allow_overflow = bool(parameters["sphere_allow_overflow"])
        fade_incoming = bool(parameters["sphere_fade_incoming_blocks"])
        cel_shading = bool(parameters["sphere_cel_shading"])

        previous_depth_enabled = bool(gl.glIsEnabled(gl.GL_DEPTH_TEST))
        previous_blend_enabled = bool(gl.glIsEnabled(gl.GL_BLEND))
        previous_cull_enabled = bool(gl.glIsEnabled(gl.GL_CULL_FACE))
        previous_depth_write = bool(gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK))
        previous_depth_function = int(gl.glGetIntegerv(gl.GL_DEPTH_FUNC))
        previous_clear = float(gl.glGetDoublev(gl.GL_DEPTH_CLEAR_VALUE))
        previous_cull_face = int(gl.glGetIntegerv(gl.GL_CULL_FACE_MODE))
        previous_front_face = int(gl.glGetIntegerv(gl.GL_FRONT_FACE))
        previous_scissor_enabled = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        previous_scissor = tuple(int(value) for value in gl.glGetIntegerv(gl.GL_SCISSOR_BOX))
        previous_src_rgb = int(gl.glGetIntegerv(gl.GL_BLEND_SRC_RGB))
        previous_dst_rgb = int(gl.glGetIntegerv(gl.GL_BLEND_DST_RGB))
        previous_src_alpha = int(gl.glGetIntegerv(gl.GL_BLEND_SRC_ALPHA))
        previous_dst_alpha = int(gl.glGetIntegerv(gl.GL_BLEND_DST_ALPHA))

        if allow_overflow:
            left, bottom, width, height = sphere_overflow_scissor(
                frame,
                fragment_strength=float(parameters["sphere_fragment_strength"]),
                particle_distance=float(parameters["sphere_particle_distance"]),
            )
        else:
            left, bottom, width, height = sphere_depth_scissor(frame)
        if previous_scissor_enabled:
            sx, sy, sw, sh = previous_scissor
            right, top = min(left + width, sx + sw), min(bottom + height, sy + sh)
            left, bottom = max(left, sx), max(bottom, sy)
            width, height = max(0, right - left), max(0, top - bottom)
        if width <= 0 or height <= 0:
            return

        try:
            self._draw_scene_shadow(
                frame,
                state=state,
                parameters=parameters,
                section_drives=section_drives,
                fade_incoming=fade_incoming,
            )

            # Depth is cleared only inside the Sphere-owned draw footprint. In
            # overflow mode that footprint expands to the worst-case current
            # detachment radius; accepted modes never touch this path.
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(left, bottom, width, height)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDepthFunc(gl.GL_LESS)
            gl.glClearDepth(1.0)
            gl.glClear(gl.GL_DEPTH_BUFFER_BIT)

            # After the bounded depth clear, restore the inherited scissor for
            # overflow drawing. If Qt supplied no scissor, the Sphere may draw
            # across the scene; otherwise its inherited scene bound still wins.
            if allow_overflow:
                if previous_scissor_enabled:
                    gl.glEnable(gl.GL_SCISSOR_TEST)
                    gl.glScissor(*previous_scissor)
                else:
                    gl.glDisable(gl.GL_SCISSOR_TEST)

            gl.glUseProgram(self._program)
            u = self._uniforms
            gl.glUniformMatrix4fv(u["uMatrix"], 1, False, frame.matrix_values)
            gl.glUniform3f(u["uGeometry"], *sphere_pixel_geometry(presentation))
            gl.glUniform1fv(u["uSectionDrives"], _SPHERE_SECTION_COUNT, section_drives)
            gl.glUniform1f(u["uFragmentStrength"], float(parameters["sphere_fragment_strength"]))
            gl.glUniform1f(u["uParticleDistance"], float(parameters["sphere_particle_distance"]))
            gl.glUniform1f(u["uParticleAmount"], float(parameters["sphere_particle_amount"]))
            gl.glUniform1f(u["uPerspectiveStrength"], float(parameters["sphere_perspective_strength"]))
            gl.glUniform1f(u["uRotationPhase"], state.rotation_phase)
            gl.glUniform1f(u["uSizePulse"], state.size_pulse)
            gl.glUniform1f(u["uTracerDrive"], state.tracer_drive)
            gl.glUniform1f(u["uTracerPhase"], state.tracer_phase)
            gl.glUniform1f(u["uBlockRelief"], 0.35)
            gl.glUniform1i(u["uFadeIncoming"], 1 if fade_incoming else 0)
            gl.glUniform1f(u["uIncomingDrive"], float(state.incoming_drive))
            gl.glUniform1f(u["uIncomingDensity"], float(state.incoming_density))
            gl.glUniform1i(u["uIncomingSection"], int(state.incoming_section))
            gl.glUniform1i(u["uIncomingPreviousSection"], int(state.incoming_previous_section))
            gl.glUniform1f(u["uIncomingBlend"], float(state.incoming_blend))
            self._upload_particle_cohorts(u, state.particle_cohorts)
            gl.glUniform1i(u["uRenderPass"], 0)
            gl.glUniform3f(u["uLight"], *self._light)
            gl.glUniform1f(u["uGloss"], float(parameters["sphere_gloss"]))
            gl.glUniform1f(u["uSpecular"], float(parameters["sphere_specular"]))
            fill_color = tuple(float(v) / 255.0 for v in parameters["sphere_fill_color"])
            edge_color = tuple(float(v) / 255.0 for v in parameters["sphere_edge_color"])
            gl.glUniform4f(u["uFillColor"], *fill_color)
            gl.glUniform4f(u["uEdgeColor"], *edge_color)
            gl.glUniform1f(u["uFade"], presentation.scene_fade * presentation.content_fade)
            gl.glUniform1i(u["uCelShading"], 1 if cel_shading else 0)
            rainbow_enabled = bool(parameters["sphere_taste_the_rainbow_enabled"])
            gl.glUniform1i(
                u["uRainbowSurfaces"],
                1 if rainbow_enabled and bool(parameters["sphere_taste_the_rainbow_surfaces"]) else 0,
            )
            gl.glUniform1i(
                u["uRainbowEdges"],
                1 if rainbow_enabled and bool(parameters["sphere_taste_the_rainbow_edges"]) else 0,
            )
            rainbow_phase = math.fmod(
                max(0.0, float(frame.snapshot.logical.logical_timestamp)) * 0.05,
                1.0,
            )
            gl.glUniform1f(u["uRainbowPhase"], rainbow_phase)

            gl.glEnable(gl.GL_CULL_FACE)
            gl.glCullFace(gl.GL_BACK)
            gl.glFrontFace(
                gl.GL_CW
                if frame.matrix_values[0] * frame.matrix_values[5] > 0
                else gl.GL_CCW
            )
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFuncSeparate(
                gl.GL_SRC_ALPHA,
                gl.GL_ONE_MINUS_SRC_ALPHA,
                gl.GL_ONE,
                gl.GL_ONE_MINUS_SRC_ALPHA,
            )
            gl.glBindVertexArray(self._vao)
            gl.glDrawArraysInstanced(
                gl.GL_TRIANGLES,
                0,
                self._vertex_count,
                self._instance_count,
            )

            # Outtake source voxels are an optional second draw of the same static
            # instance buffer. The first pass rendered the canonical replacement
            # fade; this overlay moves only departing cohort members outward and
            # fades them away. No extra geometry owner or per-voxel Python state.
            if fade_incoming and any(cohort.outtake for cohort in state.particle_cohorts):
                gl.glUniform1i(u["uRenderPass"], 1)
                gl.glDepthMask(gl.GL_FALSE)
                gl.glDrawArraysInstanced(
                    gl.GL_TRIANGLES,
                    0,
                    self._vertex_count,
                    self._instance_count,
                )
                gl.glDepthMask(gl.GL_TRUE)
                gl.glUniform1i(u["uRenderPass"], 0)

        finally:
            gl.glBlendFuncSeparate(
                previous_src_rgb,
                previous_dst_rgb,
                previous_src_alpha,
                previous_dst_alpha,
            )
            gl.glDepthFunc(previous_depth_function)
            gl.glDepthMask(gl.GL_TRUE if previous_depth_write else gl.GL_FALSE)
            gl.glClearDepth(previous_clear)
            gl.glCullFace(previous_cull_face)
            gl.glFrontFace(previous_front_face)
            gl.glScissor(*previous_scissor)
            if previous_depth_enabled:
                gl.glEnable(gl.GL_DEPTH_TEST)
            else:
                gl.glDisable(gl.GL_DEPTH_TEST)
            if previous_blend_enabled:
                gl.glEnable(gl.GL_BLEND)
            else:
                gl.glDisable(gl.GL_BLEND)
            if previous_cull_enabled:
                gl.glEnable(gl.GL_CULL_FACE)
            else:
                gl.glDisable(gl.GL_CULL_FACE)
            if previous_scissor_enabled:
                gl.glEnable(gl.GL_SCISSOR_TEST)
            else:
                gl.glDisable(gl.GL_SCISSOR_TEST)

    def _draw_scene_shadow(
        self,
        frame: QuickVisualizerRenderFrame,
        *,
        state: SphereFrame,
        parameters,
        section_drives: np.ndarray,
        fade_incoming: bool,
    ) -> None:
        """Draw one truly flat Sphere-only direct X/Y shadow.

        The old pass re-rendered voxel geometry and therefore looked like a second
        3D object. This pass is a single soft 2D disc on the shared quad; it has no
        Z, cube faces, self-overlap, rotation or displacement state.
        """
        _ = state, parameters, section_drives, fade_incoming
        presentation = frame.snapshot.presentation
        style = presentation.shell_style
        if not bool(parameters["sphere_shadow_enabled"]) or not self._shadow_program:
            return

        cx, cy, radius = sphere_pixel_geometry(presentation)
        light_x, light_y = self._light_xy
        growth = 1.0 + min(0.22, float(state.size_pulse) * 2.1)
        shadow_offset = (
            -light_x * radius * (0.34 + float(state.size_pulse) * 0.55),
            -light_y * radius * (0.34 + float(state.size_pulse) * 0.55),
        )
        raw = style["shadow_color"]
        rgba = tuple(max(0.0, min(1.0, float(channel) / 255.0)) for channel in raw)
        alpha = rgba[3] * (0.28 + min(0.16, float(state.size_pulse) * 1.6))
        if alpha <= 0.0:
            return

        gl.glUseProgram(self._shadow_program)
        su = self._shadow_uniforms
        gl.glUniformMatrix4fv(su["uMatrix"], 1, False, frame.matrix_values)
        gl.glUniform2f(su["uCenter"], cx, cy)
        gl.glUniform1f(su["uRadius"], radius * 1.26 * growth)
        gl.glUniform2f(su["uScreenOffset"], *shadow_offset)
        gl.glUniform4f(su["uShadowColor"], rgba[0], rgba[1], rgba[2], alpha)
        gl.glUniform1f(
            su["uFade"],
            float(presentation.scene_fade) * float(presentation.content_fade),
        )
        gl.glUniform1f(su["uFeather"], 0.18)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFuncSeparate(
            gl.GL_SRC_ALPHA,
            gl.GL_ONE_MINUS_SRC_ALPHA,
            gl.GL_ONE,
            gl.GL_ONE_MINUS_SRC_ALPHA,
        )
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def _initialize(self) -> None:
        if self.has_resources:
            self.release_resources()
        self._program = compile_program(
            _VERTEX_SOURCE,
            _FRAGMENT_SOURCE,
            label="Quick Sphere voxel shell",
        )
        try:
            self._shadow_program = compile_program(
                _SHADOW_VERTEX_SOURCE,
                _SHADOW_FRAGMENT_SOURCE,
                label="Quick Sphere flat shadow",
            )
            names = (
                "uMatrix", "uGeometry", "uSectionDrives",
                "uFragmentStrength", "uParticleDistance", "uParticleAmount", "uPerspectiveStrength",
                "uRotationPhase", "uSizePulse", "uBlockRelief",
                "uFadeIncoming", "uIncomingDrive", "uIncomingDensity", "uIncomingSection",
                "uIncomingPreviousSection", "uIncomingBlend", "uCohortCount", "uCohortProgress",
                "uCohortStrength", "uCohortDensity", "uCohortVelocity", "uCohortBounce",
                "uCohortSection", "uCohortLane", "uCohortOuttake", "uRenderPass",
                "uTracerDrive", "uTracerPhase",
                "uLight", "uGloss", "uSpecular",
                "uFillColor", "uEdgeColor", "uFade", "uCelShading",
                "uRainbowSurfaces", "uRainbowEdges", "uRainbowPhase",
            )
            self._uniforms = {
                name: int(
                    gl.glGetUniformLocation(
                        self._program,
                        (
                            f"{name}[0]"
                            if name in {
                                "uSectionDrives", "uCohortProgress", "uCohortStrength",
                                "uCohortDensity", "uCohortVelocity", "uCohortBounce",
                                "uCohortSection", "uCohortLane", "uCohortOuttake",
                            }
                            else name
                        ),
                    )
                )
                for name in names
            }
            missing = [name for name, location in self._uniforms.items() if location < 0]
            if missing:
                raise RuntimeError(
                    "Quick Sphere voxel uniforms are incomplete: " + ", ".join(missing)
                )
            shadow_names = (
                "uMatrix", "uCenter", "uRadius", "uScreenOffset",
                "uShadowColor", "uFade", "uFeather",
            )
            self._shadow_uniforms = {
                name: int(gl.glGetUniformLocation(self._shadow_program, name))
                for name in shadow_names
            }
            shadow_missing = [
                name for name, location in self._shadow_uniforms.items() if location < 0
            ]
            if shadow_missing:
                raise RuntimeError(
                    "Quick Sphere shadow uniforms are incomplete: "
                    + ", ".join(shadow_missing)
                )

            mesh = build_voxel_cube_mesh()
            instances = build_voxel_shell_instances()
            self._vertex_count = len(mesh) // VOXEL_VERTEX_STRIDE_FLOATS
            self._instance_count = len(instances) // VOXEL_INSTANCE_STRIDE_FLOATS
            self._vao = int(gl.glGenVertexArrays(1))
            self._mesh_vbo = int(gl.glGenBuffers(1))
            self._instance_vbo = int(gl.glGenBuffers(1))
            if not self._vao or not self._mesh_vbo or not self._instance_vbo:
                raise RuntimeError("Quick Sphere voxel resource creation failed")

            gl.glBindVertexArray(self._vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._mesh_vbo)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER,
                len(mesh) * mesh.itemsize,
                mesh.tobytes(),
                gl.GL_STATIC_DRAW,
            )
            mesh_stride = VOXEL_VERTEX_STRIDE_FLOATS * 4
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, False, mesh_stride, ctypes.c_void_p(0))
            gl.glEnableVertexAttribArray(1)
            gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, False, mesh_stride, ctypes.c_void_p(12))

            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._instance_vbo)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER,
                len(instances) * instances.itemsize,
                instances.tobytes(),
                gl.GL_STATIC_DRAW,
            )
            instance_stride = VOXEL_INSTANCE_STRIDE_FLOATS * 4
            gl.glEnableVertexAttribArray(2)
            gl.glVertexAttribPointer(2, 3, gl.GL_FLOAT, False, instance_stride, ctypes.c_void_p(0))
            gl.glVertexAttribDivisor(2, 1)
            gl.glEnableVertexAttribArray(3)
            gl.glVertexAttribPointer(3, 1, gl.GL_FLOAT, False, instance_stride, ctypes.c_void_p(12))
            gl.glVertexAttribDivisor(3, 1)
            gl.glEnableVertexAttribArray(4)
            gl.glVertexAttribPointer(4, 1, gl.GL_FLOAT, False, instance_stride, ctypes.c_void_p(16))
            gl.glVertexAttribDivisor(4, 1)
        except Exception:
            self.release_resources()
            raise

    def release_resources(self) -> None:
        errors: list[str] = []
        for attribute, deleter in (
            ("_instance_vbo", lambda resource: gl.glDeleteBuffers(1, [resource])),
            ("_mesh_vbo", lambda resource: gl.glDeleteBuffers(1, [resource])),
            ("_vao", lambda resource: gl.glDeleteVertexArrays(1, [resource])),
            ("_shadow_program", gl.glDeleteProgram),
            ("_program", gl.glDeleteProgram),
        ):
            resource = getattr(self, attribute)
            if resource:
                try:
                    deleter(resource)
                except Exception as exc:
                    errors.append(f"{attribute}: {exc}")
                else:
                    setattr(self, attribute, 0)
        if not errors:
            self._uniforms.clear()
            self._shadow_uniforms.clear()
            self._vertex_count = 0
            self._instance_count = 0
            self._parameters = None
        if errors:
            raise RuntimeError("Quick Sphere voxel cleanup incomplete: " + " | ".join(errors))


def create_visualizer_renderer() -> QuickSphereVoxelRenderer:
    return QuickSphereVoxelRenderer()


__all__ = [
    "QuickSphereVoxelRenderer",
    "SPHERE_RADIUS_FRACTION",
    "create_visualizer_renderer",
    "sphere_depth_scissor",
    "sphere_pixel_geometry",
]
