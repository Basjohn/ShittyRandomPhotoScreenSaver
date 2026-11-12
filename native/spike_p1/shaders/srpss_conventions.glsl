
#ifndef SRPSS_CONVENTIONS_MAPPING
#define SRPSS_CONVENTIONS_MAPPING
layout(std140, binding = 17) uniform SrpssConventions {
    vec4 srpssConventions;   // the target's: x 1 flips the fragment row; y 1 negates the clip NDC's Y; z, w reserved
};
#ifdef SRPSS_NATIVE_CORE
vec2 ndcToUv(vec2 ndc) { return vec2(ndc.x, srpssConventions.y > 0.5 ? -ndc.y : ndc.y) * 0.5 + 0.5; }
vec2 uvToNdc(vec2 uv) {
    vec2 ndc = uv * 2.0 - 1.0;
    return vec2(ndc.x, srpssConventions.y > 0.5 ? -ndc.y : ndc.y);
}
#else
// This renderer: y is 0 for every target and never changes, so these are the authored arithmetic, bit for bit.
vec2 ndcToUv(vec2 ndc) { return ndc * 0.5 + 0.5; }
vec2 uvToNdc(vec2 uv) { return uv * 2.0 - 1.0; }
#endif
float viewDepthFromDepthTexture(float depth) { return depth; }
// IEC 61966-2-1, exactly, for an sRGB asset uploaded as plain RGBA8 (decided F4: no backend's sRGB flag is relied on;
// the GPU filters the encoded values before this decode).
vec3 srgbToLinear(vec3 encoded) {
    return mix(pow((encoded + 0.055) / 1.055, vec3(2.4)), encoded / 12.92, lessThanEqual(encoded, vec3(0.04045)));
}
#endif
#if defined(SRPSS_CONVENTIONS_FRAGMENT) && !defined(SRPSS_CONVENTIONS_FRAGMENT_DECLARED)
#define SRPSS_CONVENTIONS_FRAGMENT_DECLARED
vec2 fragPixel(vec2 targetSize) {
    return vec2(gl_FragCoord.x, srpssConventions.x > 0.5 ? targetSize.y - gl_FragCoord.y : gl_FragCoord.y);
}
ivec2 fragTexel(ivec2 targetSize) { return ivec2(fragPixel(vec2(targetSize))); }
vec2 fragUv(vec2 targetSize) { return fragPixel(targetSize) / targetSize; }
#endif
