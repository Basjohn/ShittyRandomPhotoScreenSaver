// Accepted pre-regression BEAM oracle: a51aab8a, 22 Oct 2026.
uniform float uShaftScale;      // source pattern frequency (1: the shared pattern's)
uniform float uShaftSoft;       // threshold softness 0..1
uniform float uShaftFan;        // share of the sun fan (0: depth march only)
uniform float uFanRays;         // broad rays round a full turn of the fan
uniform float uFanReach;        // angle (rad) over which the fan fades
uniform vec2 uFanMix;           // ray contrast 0..1, share of the depth march under the fan
uniform float uFlicker;         // Ray Flicker's depth now (0: steady rays)
uniform float uShimmer;         // the shimmer's phase (the simulation's; faster on the hits)
uniform vec3 uRaySource;        // physical world-space beam segment start
uniform vec3 uRayEnd;           // physical world-space beam segment end
uniform vec4 uBlock0;           // up to four scene bubbles (xyz, physical radius; radius 0 = vacant)
uniform vec4 uBlock1;
uniform vec4 uBlock2;
uniform vec4 uBlock3;
uniform float uParticleAtten;   // bounded aggregate dust opacity; not per-particle shadowing

float beamExtent(vec3 p) {
    vec3 line = uRayEnd - uRaySource;
    float lengthLine = max(length(line), 0.001);
    float along = dot(p - uRaySource, line / lengthLine);
    // Real authored physical start and end; soft exit to avoid a hard lighting sheet.
    return smoothstep(-1.8, 1.2, along) * (1.0 - smoothstep(lengthLine - 2.0, lengthLine + 1.5, along));
}
float blockAttenuation(vec3 samplePoint, vec4 bubble, vec3 lightTravel) {
    if (bubble.w <= 0.0) return 1.0;
    vec3 fromObject = samplePoint - bubble.xyz;
    float afterObject = dot(fromObject, lightTravel);
    float lateral = length(fromObject - afterObject * lightTravel);
    float shadow = (1.0 - smoothstep(bubble.w * 0.8, bubble.w * 3.2, lateral))
                 * smoothstep(-bubble.w * 0.3, bubble.w * 1.2, afterObject);
    // Glass does not black out the shafts. Four strongest bubbles at most; diffuse shadow.
    return 1.0 - 0.16 * shadow;
}
float sceneTransmittance(vec3 p) {
    vec3 lightTravel = normalize(uRayEnd - uRaySource);
    float t = blockAttenuation(p, uBlock0, lightTravel)
            * blockAttenuation(p, uBlock1, lightTravel)
            * blockAttenuation(p, uBlock2, lightTravel)
            * blockAttenuation(p, uBlock3, lightTravel);
    return clamp(t * (1.0 - uParticleAtten), 0.60, 1.0);
}

float labShaftFan(vec3 ray, vec3 sunBelow, float t) {
    // Azimuth round the sun axis, zero pointing down (the seam faces up, behind the sun).
    vec3 down = normalize(vec3(0.0, -1.0, 0.0) - sunBelow * -sunBelow.y + vec3(1e-4, 0.0, 0.0));
    vec3 side = cross(sunBelow, down);
    float phi = atan(dot(ray, side), dot(ray, down)) / 6.2831853;
    float theta = acos(clamp(dot(ray, sunBelow), -1.0, 1.0));
    float x = phi * uFanRays;
    float broad = skyNoise2(vec2(x + t * 0.04, 0.5), 83u);
    float mid = skyNoise2(vec2(x * 2.7 - t * 0.07, 3.5), 89u);
    float fine = skyNoise2(vec2(x * 7.3 + t * 0.1, 7.5), 97u);
    // Many fine and medium rays packed side by side (mocks), never a few solid wedges: soft contrast over a floor.
    float n = broad * 0.3 + mid * 0.4 + fine * 0.3;
    float rays = (1.0 - uFanMix.x) * n + uFanMix.x * smoothstep(0.42, 0.78, n);
    // Ray Flicker: each ray brightens and dims on its own as the shimmer runs.
    rays *= 1.0 + uFlicker * 1.6 * (skyNoise2(vec2(x * 1.9, uShimmer * 1.3), 107u) - 0.5);
    // Each ray reaches its own length; all fade with the angle from the sun, gone by about two thirds down.
    float reach = mix(uFanReach * 0.55, uFanReach * 1.25, skyNoise2(vec2(x * 1.3, 11.5), 101u));
    // The fan hangs below the sun: rays leaving sideways (toward the top corners) are faint (mocks).
    float spread = smoothstep(0.24, 0.1, abs(phi));
    return rays * spread * exp(-theta / reach) * smoothstep(0.02, 0.12, theta);
}
float labShaftPattern(vec2 q, float t) {
    q *= uShaftScale;
    float a = skyNoise2(q * 2.1 + vec2(t * 0.12, -t * 0.07), 71u);
    float b = skyNoise2(q * 5.3 + vec2(-t * 0.2, t * 0.15), 73u);
    float slow = skyNoise2(q * 0.55 + vec2(t * 0.03, 0.0), 79u);
    float n = a * 0.7 + b * 0.3;
    float lo = mix(0.58, 0.3, uShaftSoft), hi = mix(0.82, 0.95, uShaftSoft);
    float flicker = 1.0 + uFlicker * 1.6 * (skyNoise2(q * 1.4 + vec2(uShimmer * 0.9, -uShimmer * 0.6), 109u) - 0.5);
    return smoothstep(lo, hi, n) * (0.45 + 0.9 * slow) * flicker;
}
float labShafts(vec3 ray, float maxDistance, vec3 sunBelow, float surfaceY, float t, int samples, float jitter) {
    float stepLength = maxDistance / float(samples);
    vec2 slope = sunBelow.xz / max(sunBelow.y, 0.2);
    float sum = 0.0;
    for (int i = 0; i < samples; ++i) {
        float s = (float(i) + jitter) * stepLength;
        vec3 p = uEye + ray * s;
        float below = surfaceY - p.y;
        if (below <= 0.0) break;
        sum += beamExtent(p) * labShaftPattern(p.xz + slope * below, t) * exp(-below * 0.07) * exp(-s * 0.035);
    }
    return sum * stepLength;
}
void main() {
    vec3 ray = uViewToWorld * normalize(vec3(vNdc * uTan, -1.0));
    float jitter = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
    float toward = pow(max(dot(ray, uSunBelow), 0.0), 2.0);
    float march = labShafts(ray, 45.0, uSunBelow, uShaftY, uTime, 40, jitter) * 0.13 * (0.25 + toward);
    // The angle-fan is finite too: the second node changes its actual 3D reach.
    // Assess at two depths to avoid a pinhole slice when the camera physically dollies.
    float fanExtent = max(beamExtent(uEye + ray * 12.0), beamExtent(uEye + ray * 23.0));
    float fan = labShaftFan(ray, uSunBelow, uTime) * fanExtent;
    float optical = sceneTransmittance(uEye + ray * 18.0);
    FragColor = vec4(max(0.0, mix(march, fan * 0.9 + march * uFanMix.y, uShaftFan) * optical));
}
