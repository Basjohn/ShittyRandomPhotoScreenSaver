
#ifndef SRPSS_CONVENTIONS_MAPPING
#define SRPSS_CONVENTIONS_MAPPING
vec2 ndcToUv(vec2 ndc) { return ndc * 0.5 + 0.5; }
vec2 uvToNdc(vec2 uv) { return uv * 2.0 - 1.0; }
float viewDepthFromDepthTexture(float depth) { return depth; }
#endif
#if defined(SRPSS_CONVENTIONS_FRAGMENT) && !defined(SRPSS_CONVENTIONS_FRAGMENT_DECLARED)
#define SRPSS_CONVENTIONS_FRAGMENT_DECLARED
layout(std140, binding = 17) uniform SrpssConventions {
    vec4 srpssConventions;   // x: 1 flips gl_FragCoord.y against the target height, 0 keeps it; y, z, w: reserved
};
vec2 fragPixel(vec2 targetSize) {
    return vec2(gl_FragCoord.x, srpssConventions.x > 0.5 ? targetSize.y - gl_FragCoord.y : gl_FragCoord.y);
}
ivec2 fragTexel(ivec2 targetSize) { return ivec2(fragPixel(vec2(targetSize))); }
vec2 fragUv(vec2 targetSize) { return fragPixel(targetSize) / targetSize; }
#endif
