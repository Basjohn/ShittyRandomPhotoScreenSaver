layout(std140, binding = 18) uniform WaveformFloor {
    vec2 uViewport;
    vec2 u_target_px;
    vec4 uFloorGive;
    mat4 uMvp;
    mat4 uFloorInverseMvp;
    vec3 uEye;
    int uFlat;
    int uFogLit;
    vec3 uBackdrop;
    vec3 uAmbient;
    vec3 uFloorTint;
    vec4 uFloor;
    vec3 uFloorTone;
    vec3 uRipple;
    vec4 uStreak;
    vec4 uHot;
    vec4 uMaterial;
    vec3 uMaterialShape;
    float uPool;
    float uPoolZ;
    vec3 uColumn;
    float uReflectionHue;
    vec3 uBound;
    int uSpecMode;
    vec3 uForward;
    vec2 uFloorGiveLook;
    vec4 uFieldOrigin;
    float uFieldSide;
    vec4 uGradeStops[6];
    vec4 uGrade;
    vec2 uBodySpan;
    vec4 uBodyShape;
    vec4 uMist;
    vec4 uMistShape;
    mat4 uFogView;
    vec4 uFogLens;
    vec4 uFogRange;
    vec4 uReflectionLook;
    vec4 uReflectionContact;
};

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

#ifndef SRPSS_TARGET_CLIP
#define SRPSS_TARGET_CLIP
vec4 srpssTargetClip(vec4 clip, vec2 viewport, vec2 targetPx) {
    if (srpssConventions.z > 0.5) {
        vec2 s = viewport / targetPx;
        clip.xy = clip.xy * s + clip.w * (s - 1.0);
    }
    if (srpssConventions.w > 0.5) clip.z = 0.5 * (clip.z + clip.w);
    return clip;
}
#endif
#if defined(SRPSS_CONVENTIONS_FRAGMENT) && !defined(SRPSS_TARGET_CLIP_FRAGMENT)
#define SRPSS_TARGET_CLIP_FRAGMENT
vec2 srpssGlFragUv(vec2 viewport, vec2 targetPx) { return fragPixel(targetPx) / viewport; }
#ifdef SRPSS_SCENE_ITEM_ONLY
bool srpssOutsideItem(vec2 viewport, vec2 targetPx) {
    vec2 p = fragPixel(targetPx);
    return p.x >= viewport.x || p.y >= viewport.y;
}
#define srpssItemOnly(viewport, targetPx) if (srpssOutsideItem(viewport, targetPx)) discard
#else
#define srpssItemOnly(viewport, targetPx)
#endif
#endif

layout(location=0) in vec3 aPosition;


layout(location = 0) out vec2 vFloorNdc;
void main() { vFloorNdc=aPosition.xz*2.0-1.0; gl_Position=srpssTargetClip(vec4(vFloorNdc,0.0,1.0),uViewport,u_target_px); }
