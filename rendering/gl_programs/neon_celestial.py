"""Pure position math and GLSL for Neon Lake Basin's optional celestial scene.

The caller owns its logical animation clock, scene pose, shader program and render
resources.  ``basin_body_position`` is only an analytic mirror for the body orbit;
the GLSL fragment below owns no clock or camera transform.
"""
from __future__ import annotations

import math


def basin_body_position(
    x: float,
    y: float,
    z: float,
    half_width: float,
    animation_time: float,
    orbit_enabled: bool,
    orbit_speed: float,
) -> tuple[float, float, float]:
    """Resolve authored basin body coordinates and optional logical-clock orbit.

    ``x`` is authored as a multiple of ``half_width``; ``y`` and ``z`` are scene
    units.  Orbit speed is revolutions per second around the visible basin centre
    at ``(0, 0, -1.2)``.  When disabled, time and speed are deliberately unused
    and the authored world position is returned directly.
    """
    x = float(x)
    y = float(y)
    z = float(z)
    half_width = float(half_width)
    authored_x = x * half_width
    if not all(math.isfinite(value) for value in (x, y, z, half_width, authored_x)):
        raise ValueError("celestial body position must be finite")
    if half_width <= 0.0:
        raise ValueError("basin half-width must be positive")
    if not orbit_enabled:
        return authored_x, y, z

    animation_time = float(animation_time)
    orbit_speed = float(orbit_speed)
    if not math.isfinite(animation_time) or not math.isfinite(orbit_speed):
        raise ValueError("celestial orbit time and speed must be finite")
    angle = animation_time * orbit_speed * math.tau
    if not math.isfinite(angle):
        raise ValueError("celestial orbit angle must be finite")

    cosine = math.cos(angle)
    sine = math.sin(angle)
    offset_z = z + 1.2
    world_x = authored_x * cosine + offset_z * sine
    world_z = -1.2 - authored_x * sine + offset_z * cosine
    return world_x, y, world_z


def basin_body_camera_coverage(camera_distance: float, body_radius: float) -> float:
    """Visible-disc attenuation only, leaving the orbit and scene radiance intact.

    Near-camera spheres create an enormous angular disc even though their
    centre and radius are valid. Blend the visible body out before the eye can
    intersect it; glass/reflection and light continue to use the real sphere.
    """
    camera_distance, body_radius = float(camera_distance), float(body_radius)
    if not math.isfinite(camera_distance) or not math.isfinite(body_radius):
        raise ValueError("celestial camera distance and radius must be finite")
    if body_radius <= 0.0:
        return 0.0
    ratio = body_radius / max(camera_distance, 1e-6)
    t = max(0.0, min(1.0, (ratio - 0.16) / (0.28 - 0.16)))
    return 1.0 - t*t*(3.0 - 2.0*t)


NEON_CELESTIAL_GLSL = r"""
uniform vec3 uBodyPosition;
uniform float uBodySize;
uniform int uBodyKind;              // 0 Sun, 1 Moon
uniform int uSunEnabled;            // canonical Show Sun / Moon body gate
uniform vec4 uSunColor;
uniform vec4 uMoonColor;
uniform float uMoonPhase;
// Camera-nearbody attenuation affects visible sky only, not reflections/light.
float basinCameraBodyCoverage(float cameraDistance,float radius) {
    if (radius<=0.0) return 0.0;
    float ratio=radius/max(cameraDistance,1e-6);
    return 1.0-smoothstep(0.16,0.28,ratio);
}
uniform int uSkyEnabled;
uniform vec4 uSkyColor;
uniform float uSkyStrength;
uniform vec4 uStarColor;
uniform vec2 uStarGlow; // intensity and response for selected beat stars
uniform int uBeatStarCount;
uniform vec4 uBeatStarCells[6];  // panorama star-grid x/y, fade strength
uniform vec4 uCloudColor;
uniform vec4 uHorizonColor;

float basinCelestialHash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float basinMoonCraters(vec2 uv) {
    vec2 grid = uv * vec2(10.0, 7.0);
    vec2 baseCell = floor(grid);
    vec2 local = fract(grid);
    float shade = 1.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            vec2 cell = baseCell + vec2(float(x), float(y));
            vec2 jitter = vec2(
                basinCelestialHash(cell),
                basinCelestialHash(cell + vec2(19.17, 7.31))) * 0.54 + 0.23;
            vec2 delta = vec2(float(x), float(y)) + jitter - local;
            float seed = basinCelestialHash(cell + vec2(37.2, 11.8));
            float largeBasin = step(0.86, seed);
            float craterRadius = mix(mix(0.06, 0.14,
                                         basinCelestialHash(cell + vec2(7.3, 41.1))),
                                     mix(0.28, 0.42,
                                         basinCelestialHash(cell + vec2(5.7, 23.9))),
                                     largeBasin);
            float craterEdge = mix(0.022, 0.055, largeBasin);
            float craterDepth = mix(0.10, 0.045, largeBasin);
            float angle = atan(delta.y, delta.x);
            float warp = 1.0 + 0.055 * sin(angle * 3.0 + seed * 6.2831853)
                       + 0.025 * sin(angle * 5.0 + seed * 11.0);
            float radial = length(delta) * warp;
            float bowl = 1.0 - smoothstep(craterRadius - craterEdge,
                                          craterRadius + craterEdge, radial);
            float rim = 1.0 - smoothstep(0.0, craterEdge * 0.8,
                                         abs(radial - craterRadius));
            float rimHeight = mix(0.012, 0.004, largeBasin);
            shade = min(shade, 1.0 - craterDepth * bowl + rimHeight * rim);

            // A bounded pair of smaller, offset craters gives selected cells a
            // faint irregular cluster instead of repeating the same stamped disc.
            float cluster = step(0.45, basinCelestialHash(cell + vec2(13.4, 51.2)))
                          * (1.0 - largeBasin);
            if (cluster > 0.5) {
                float clusterAngle = basinCelestialHash(cell + vec2(4.6, 29.3)) * 6.2831853;
                vec2 offsetA = vec2(cos(clusterAngle), sin(clusterAngle)) * 0.20;
                vec2 offsetB = vec2(cos(clusterAngle + 2.15), sin(clusterAngle + 2.15)) * 0.29;
                float radiusA = mix(0.05, 0.10,
                                    basinCelestialHash(cell + vec2(31.8, 17.4)));
                float radiusB = mix(0.045, 0.085,
                                    basinCelestialHash(cell + vec2(21.6, 43.2)));
                float craterA = 1.0 - smoothstep(radiusA - 0.018, radiusA + 0.018,
                                                 length(delta - offsetA));
                float craterB = 1.0 - smoothstep(radiusB - 0.016, radiusB + 0.016,
                                                 length(delta - offsetB));
                shade = min(shade, 1.0 - cluster * (0.055 * craterA + 0.045 * craterB));
            }
        }
    }
    return clamp(shade, 0.78, 1.0);
}

// A nearest positive ray-sphere hit.  ``hitPoint`` is in the caller's shared
// Scene3D world space and can be projected through that scene's camera for depth.
vec4 basinCelestial(vec3 eye, vec3 worldRay, out vec3 hitPoint) {
    hitPoint = vec3(0.0);
    if ((uBodyKind != 0 && uBodyKind != 1) || uSunEnabled == 0 || uBodySize <= 0.0) {
        return vec4(0.0);
    }
    float rayLength = length(worldRay);
    if (rayLength <= 1e-8) return vec4(0.0);
    vec3 ray = worldRay / rayLength;
    vec3 offset = eye - uBodyPosition;
    float halfB = dot(offset, ray);
    float discriminant = halfB * halfB - (dot(offset, offset) - uBodySize * uBodySize);
    if (discriminant < 0.0) return vec4(0.0);
    float root = sqrt(max(discriminant, 0.0));
    float distance = -halfB - root;
    if (distance <= 1e-5) distance = -halfB + root;
    if (distance <= 1e-5) return vec4(0.0);

    hitPoint = eye + ray * distance;
    vec3 normal = (hitPoint - uBodyPosition) / uBodySize;
    float facing = max(dot(normal, -ray), 0.0);
    float limb = smoothstep(0.015, 0.10, facing);
    if (uBodyKind == 0) {
        float intensity = 1.0;
        float cutCoverage = 1.0;
        if (normal.y < 0.0) {
            float lowerHemisphere = -normal.y;
            float stripePhase = lowerHemisphere * 7.0;
            float cutDistance = abs(fract(stripePhase) - 0.5);
            float aa = max(fwidth(stripePhase), 0.004);
            cutCoverage = smoothstep(0.11 - aa, 0.11 + aa, cutDistance);
            intensity = mix(0.82, 1.0, 0.5 + 0.5 * sin(lowerHemisphere * 3.14159265));
        }
        vec3 sun = max(uSunColor.rgb, vec3(0.0)) * intensity;
        float alpha = clamp(uSunColor.a, 0.0, 1.0) * limb * cutCoverage;
        return vec4(sun, alpha);
    }

    float longitude = atan(normal.x, normal.z) * 0.15915494309 + 0.5;
    float latitude = asin(clamp(normal.y, -1.0, 1.0)) * 0.31830988618 + 0.5;
    vec2 uv = vec2(longitude, latitude);
    float phaseAngle = clamp(uMoonPhase, 0.0, 1.0) * 6.28318530718;
    vec3 lightDirection = vec3(sin(phaseAngle), 0.0, -cos(phaseAngle));
    float illumination = smoothstep(-0.12, 0.16, dot(normal, lightDirection));
    float craters = basinMoonCraters(uv);
    float brightness = (0.10 + 0.90 * illumination) * craters;
    vec3 moon = max(uMoonColor.rgb, vec3(0.0)) * brightness;
    return vec4(moon, clamp(uMoonColor.a, 0.0, 1.0) * limb);
}

float basinStarHash(vec2 cell) {
    return fract(sin(dot(cell, vec2(41.37, 289.13))) * 24634.6345);
}

float basinStarField(vec3 ray) {
    vec2 grid = vec2(atan(ray.x, -ray.z), asin(clamp(ray.y, -1.0, 1.0))) * 420.0;
    vec2 cell = floor(grid);
    vec2 pixelDistance = (fract(grid) - 0.5) / max(fwidth(grid), vec2(1e-4));
    float pixelAlpha = 1.0 - smoothstep(0.15, 0.65, length(pixelDistance));
    float aboveHorizon = smoothstep(-0.45, -0.25, ray.y);
    return step(0.985, basinStarHash(cell)) * pixelAlpha * aboveHorizon;
}

float basinBeatStarLight(vec3 ray,vec2 glow) {
    if (uBeatStarCount<=0) return 0.0;
    vec2 grid=vec2(atan(ray.x,-ray.z),asin(clamp(ray.y,-1.0,1.0)))*420.0;
    float light=0.0;
    vec2 pixelScale=max(fwidth(grid),vec2(1e-4));
    for (int i=0; i<6; ++i) {
        if (i>=uBeatStarCount) break;
        // Cull far cells before costly halo math. This is an opt-in effect,
        // and only three (occasionally six) small star regions participate.
        vec2 difference=grid-uBeatStarCells[i].xy-0.5;
        if (any(greaterThan(abs(difference),vec2(1.0)+5.5*pixelScale))) continue;
        // Actual panorama cells, with a several-pixel halo. The old equality
        // check confined everything to one subpixel cell and was invisible.
        vec2 delta=difference/pixelScale;
        float radius=length(delta);
        float core=1.0-smoothstep(0.0,1.35,radius);
        float halo=1.0-smoothstep(1.0,5.5,radius);
        float gain=glow.x*(0.50+0.50*clamp(glow.y*uBeatStarCells[i].z*1.8,0.0,1.0));
        light+=gain*uBeatStarCells[i].z*(1.8*core+0.60*halo);
    }
    return light;
}

// Straight-alpha sky radiance.  The independent enable gate makes the sky
// transparent when disabled; the Sun/Moon remains a separate body pass.
vec4 basinSkyBackground(vec3 worldRay) {
    if (uSkyEnabled == 0 || uSkyStrength <= 0.0) return vec4(0.0);
    float rayLength = length(worldRay);
    if (rayLength <= 1e-8) return vec4(0.0);
    vec3 ray = worldRay / rayLength;
    float latitude = asin(clamp(ray.y, -1.0, 1.0));
    float dusk = exp(-pow((ray.y + 0.50) / 0.16, 2.0));
    vec3 colour = max(uSkyColor.rgb, vec3(0.0)) * (0.65 + 0.35 * dusk);
    colour += max(uHorizonColor.rgb, vec3(0.0)) *
              clamp(uHorizonColor.a, 0.0, 1.0) * dusk;

    float longitude = atan(ray.x, -ray.z);
    float clouds = 0.0;
    for (int band = 0; band < 3; ++band) {
        float bandIndex = float(band);
        float phase = bandIndex * 1.7;
        // Wide, discontinuous wisps rather than three near-constant latitude
        // strokes. Those narrow parallel strokes read as a false geometric
        // horizon when the camera swivels above the real mountains.
        float centre = -0.32 - bandIndex * 0.055 +
                       0.024 * sin(longitude * 5.0 + phase) +
                       0.014 * sin(longitude * 17.0 - phase);
        float thickness = 0.014 + 0.004 * bandIndex;
        float shape = 1.0 - smoothstep(thickness, thickness + 0.013,
                                       abs(latitude - centre));
        float gaps = 0.35 + 0.24 * sin(longitude * 11.0 + phase)
                    + 0.24 * sin(longitude * 27.0 - phase);
        float broken = smoothstep(0.33, 0.66, gaps);
        float density = 0.5 + 0.5 * sin(ray.y * 170.0 + longitude * 7.0);
        clouds += shape * broken * density;
    }
    colour += max(uCloudColor.rgb, vec3(0.0)) *
              clamp(uCloudColor.a, 0.0, 1.0) * clamp(clouds, 0.0, 1.0);

    float stars = basinStarField(ray) * clamp(uStarColor.a, 0.0, 1.0);
    stars += basinBeatStarLight(ray,uStarGlow);
    colour += max(uStarColor.rgb, vec3(0.0)) * stars;
    // Keep sky alpha continuous across the camera. The old latitude-based
    // opacity transition created a ruler-straight wallpaper seam unrelated
    // to the terrain skyline, especially when the distant skirt faded out.
    // Dusk/horizon atmosphere varies in *colour* above, not in coverage.
    // Terrain owns its fade/occlusion independently, so no second horizon
    // authority is needed in the sky shader.
    float alpha = clamp(uSkyColor.a * uSkyStrength, 0.0, 1.0);
    return vec4(colour, alpha);
}

// Premultiplied radiance for reflection.  The caller supplies the exact visible
// body after its scene-depth/terrain tests, so buried celestial geometry cannot
// leak into the sky's reflection.
vec3 basinCompositeSkyBody(vec4 sky, vec4 body) {
    float bodyAlpha = clamp(body.a, 0.0, 1.0);
    float skyAlpha = clamp(sky.a, 0.0, 1.0);
    return body.rgb * bodyAlpha + sky.rgb * skyAlpha * (1.0 - bodyAlpha);
}
"""
