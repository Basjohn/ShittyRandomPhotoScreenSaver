"""Bounded opt-in single-scattering volume for an authored Scene3D heightfield.

`HEIGHTFIELD_VOLUME_GLSL` includes the shared `HEIGHTFIELD_GLSL` sampler and
classification helpers. Call `sceneHeightfieldVolume` from a fullscreen volume
pass after opaque terrain, using the same world-space ray and body position as
the scene projection. Its result is premultiplied RGBA; a zero strength or a
fully occluded light returns transparent black.

The ray marches at most 12 view samples. Each admitted sample uses at most four
bilinear heightfield samples toward the body for coarse land occlusion, so the
worst case is 60 scalar terrain samples per fragment. Density is concentrated
near the water plane and fades with world height, without extra terrain reads or
animated noise. Thin ridges between the four occlusion samples can be missed by
design; there is no high-tap fallback.
"""

from rendering.gl_programs.heightfield_glsl import HEIGHTFIELD_GLSL


HEIGHTFIELD_VOLUME_MAX_STEPS = 12
HEIGHTFIELD_VOLUME_LIGHT_SAMPLES = 4
HEIGHTFIELD_VOLUME_QUALITY_STEPS = {
    "High": 12,
    "Balanced": 8,
    "Performance": 6,
    "KAK": 4,
}


HEIGHTFIELD_VOLUME_GLSL = HEIGHTFIELD_GLSL + """
const int SCENE_HEIGHTFIELD_VOLUME_MAX_STEPS = 12;
const int SCENE_HEIGHTFIELD_VOLUME_LIGHT_SAMPLES = 4;

bool sceneHeightfieldVolumeRayBox(
    vec3 origin, vec3 direction, vec3 boxMin, vec3 boxMax,
    out float tEnter, out float tExit)
{
    tEnter = -1e30;
    tExit = 1e30;
    for (int axis = 0; axis < 3; ++axis) {
        float component = direction[axis];
        if (abs(component) < 1e-6) {
            if (origin[axis] < boxMin[axis] || origin[axis] > boxMax[axis]) return false;
            continue;
        }
        float a = (boxMin[axis] - origin[axis]) / component;
        float b = (boxMax[axis] - origin[axis]) / component;
        tEnter = max(tEnter, min(a, b));
        tExit = min(tExit, max(a, b));
    }
    tEnter = max(tEnter, 0.0);
    return tExit > tEnter;
}

vec2 sceneHeightfieldVolumeUv(vec3 world, float halfWidth, float depth) {
    return vec2(world.x / (2.0 * halfWidth) + 0.5, -world.z / depth);
}

float sceneHeightfieldVolumeTerrainHeight(
    sampler2D heightfield, int heightfieldSize, vec3 world,
    float halfWidth, float depth, float heightScale)
{
    vec2 uv = sceneHeightfieldVolumeUv(world, halfWidth, depth);
    // A program whose grid reaches past its basin maps basin uv to grid uv (identity by default).
#ifdef SCENE_HEIGHTFIELD_GRID
    uv = SCENE_HEIGHTFIELD_GRID(uv);
#endif
    float authoredHeight = sceneHeightfield(heightfield, heightfieldSize, uv);
    // Exact authored-zero water stays at base level and never occludes light.
    return sceneHeightfieldWater(authoredHeight)
        ? 0.0 : authoredHeight * max(heightScale, 0.0) * 1.25;
}

bool sceneHeightfieldVolumeLightOccluded(
    sampler2D heightfield, int heightfieldSize, vec3 point, vec3 bodyWorldPosition,
    float halfWidth, float depth, float heightScale)
{
    vec3 toBody = bodyWorldPosition - point;
    for (int tap = 1; tap <= SCENE_HEIGHTFIELD_VOLUME_LIGHT_SAMPLES; ++tap) {
        float t = float(tap) / float(SCENE_HEIGHTFIELD_VOLUME_LIGHT_SAMPLES + 1);
        vec3 samplePoint = point + toBody * t;
        if (samplePoint.x < -halfWidth || samplePoint.x > halfWidth
            || samplePoint.z < -depth || samplePoint.z > 0.0) {
            continue;
        }
        float terrainHeight = sceneHeightfieldVolumeTerrainHeight(
            heightfield, heightfieldSize, samplePoint, halfWidth, depth, heightScale);
        if (terrainHeight > 0.0 && samplePoint.y <= terrainHeight) {
            return true;
        }
    }
    return false;
}

float sceneHeightfieldVolumePhase(float cosineAngle, float anisotropy) {
    float g = clamp(anisotropy, -0.5, 0.5);
    float denominator = max(1.0 + g * g - 2.0 * g * clamp(cosineAngle, -1.0, 1.0), 1e-4);
    float hg = (1.0 - g * g) / (denominator * sqrt(denominator));
    float peak = (1.0 + abs(g)) / ((1.0 - abs(g)) * (1.0 - abs(g)));
    return clamp(hg / peak, 0.0, 1.0);
}

vec4 sceneHeightfieldVolume(
    vec3 bodyWorldPosition,
    vec3 rayOrigin,
    vec3 rayDirection,
    float fieldHalfWidth,
    float fieldDepth,
    float heightScale,
    sampler2D heightfield,
    int heightfieldSize,
    vec4 bodyColour,
    float density,
    float phaseAnisotropy,
    float strength,
    int qualitySteps)
{
    if (any(isnan(bodyWorldPosition)) || any(isinf(bodyWorldPosition))
        || any(isnan(rayOrigin)) || any(isinf(rayOrigin))
        || any(isnan(rayDirection)) || any(isinf(rayDirection))
        || any(isnan(bodyColour)) || any(isinf(bodyColour))
        || isnan(fieldHalfWidth) || isinf(fieldHalfWidth)
        || isnan(fieldDepth) || isinf(fieldDepth)
        || isnan(heightScale) || isinf(heightScale)
        || isnan(density) || isinf(density)
        || isnan(phaseAnisotropy) || isinf(phaseAnisotropy)
        || isnan(strength) || isinf(strength)) {
        return vec4(0.0);
    }
    if (fieldHalfWidth <= 1e-5 || fieldDepth <= 1e-5 || heightfieldSize < 2
        || density <= 0.0 || strength <= 0.0 || bodyColour.a <= 0.0
        || dot(rayDirection, rayDirection) <= 1e-12) {
        return vec4(0.0);
    }

    vec3 direction = normalize(rayDirection);
    float heightMax = max(max(heightScale, 0.0) * 1.30, fieldDepth * 0.25);
    vec3 boxMin = vec3(-fieldHalfWidth, 0.0, -fieldDepth);
    vec3 boxMax = vec3(fieldHalfWidth, heightMax, 0.0);
    float tEnter, tExit;
    if (!sceneHeightfieldVolumeRayBox(rayOrigin, direction, boxMin, boxMax, tEnter, tExit)) {
        return vec4(0.0);
    }

    int steps = clamp(qualitySteps, 4, SCENE_HEIGHTFIELD_VOLUME_MAX_STEPS);
    float stepLength = (tExit - tEnter) / float(steps);
    if (stepLength <= 1e-6) return vec4(0.0);
    vec3 radiance = vec3(0.0);
    float transmittance = 1.0;
    vec3 safeBodyColour = clamp(bodyColour.rgb, vec3(0.0), vec3(1.0));
    float baseDensity = clamp(density, 0.0, 4.0) * clamp(strength, 0.0, 1.0)
                      * clamp(bodyColour.a, 0.0, 1.0);
    float worldScale = max(max(2.0 * fieldHalfWidth, fieldDepth), heightMax);

    for (int step = 0; step < SCENE_HEIGHTFIELD_VOLUME_MAX_STEPS; ++step) {
        if (step >= steps || transmittance < 0.01) break;
        float t = tEnter + (float(step) + 0.5) * stepLength;
        vec3 point = rayOrigin + direction * t;
        float terrainHeight = sceneHeightfieldVolumeTerrainHeight(
            heightfield, heightfieldSize, point, fieldHalfWidth, fieldDepth, heightScale);
        if (terrainHeight > 0.0 && point.y <= terrainHeight) {
            break;
        }
        if (sceneHeightfieldVolumeLightOccluded(
                heightfield, heightfieldSize, point, bodyWorldPosition,
                fieldHalfWidth, fieldDepth, heightScale)) {
            continue;
        }

        vec3 toBody = bodyWorldPosition - point;
        float bodyDistance = max(length(toBody), 1e-4);
        vec3 lightDirection = toBody / bodyDistance;
        float phase = sceneHeightfieldVolumePhase(dot(direction, lightDirection), phaseAnisotropy);
        float lightAttenuation = 1.0 / (1.0 + 0.08 * (bodyDistance / worldScale) * (bodyDistance / worldScale));
        float worldHeight = clamp(point.y / max(heightMax, 1e-4), 0.0, 1.0);
        // Keep more scattering near water/lower slopes, fading toward high air.
        float heightDensity = 1.0 - smoothstep(0.06, 0.42, worldHeight);
        float opticalDepth = baseDensity * phase * lightAttenuation * heightDensity * stepLength;
        float sampleAlpha = 1.0 - exp(-opticalDepth);
        radiance += transmittance * sampleAlpha * safeBodyColour;
        transmittance *= 1.0 - sampleAlpha;
    }
    float alpha = clamp(1.0 - transmittance, 0.0, 1.0);
    return vec4(clamp(radiance, vec3(0.0), vec3(alpha)), alpha);
}
"""


__all__ = [
    "HEIGHTFIELD_VOLUME_GLSL",
    "HEIGHTFIELD_VOLUME_MAX_STEPS",
    "HEIGHTFIELD_VOLUME_LIGHT_SAMPLES",
    "HEIGHTFIELD_VOLUME_QUALITY_STEPS",
]
