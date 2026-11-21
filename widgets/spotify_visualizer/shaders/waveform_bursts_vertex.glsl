
#ifndef SRPSS_VERTEX_INDEX
#define SRPSS_VERTEX_INDEX
#ifdef VULKAN
#define srpssVertexIndex gl_VertexIndex
#define srpssInstanceIndex gl_InstanceIndex
#else
#define srpssVertexIndex gl_VertexID
#define srpssInstanceIndex gl_InstanceID
#endif
#endif
layout(std140, binding = 18) uniform RibbonBurstDraw {
    mat4 uMvp;
    vec2 uViewport;
    vec2 u_target_px;
    float uNow;
    vec4 uMist;
    vec4 uMistShape;
    mat4 uFogView;
    vec4 uFogLens;
    vec4 uFogRange;
    vec4 uGradeStops[6];
    vec4 uGrade;
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

layout(location=0) in vec2 aPosition;
struct Burst { vec4 p; vec4 velocity; vec4 colour; vec4 look; };
layout(std430,binding=1) readonly buffer Bursts { Burst particles[]; };




layout(location = 0) out vec2 vUv;
layout(location = 1) out vec3 vWorld;
layout(location = 2) flat out vec3 vColour;
layout(location = 3) flat out float vLight;
layout(location = 4) flat out float vGlow;
layout(location = 5) flat out float vCore;
void main() {
    Burst b=particles[srpssInstanceIndex];
    gl_Position=vec4(2.0,2.0,2.0,1.0); vUv=vec2(0);vWorld=vec3(0);vColour=vec3(0);vLight=0.0;vGlow=0.0;vCore=1.0;
    float age=uNow-b.p.w, life=b.velocity.w;
    if(life<=0.0 || age<0.0 || age>=life) return;
    vec3 world=b.p.xyz+b.velocity.xyz*age/(1.0+0.5*age);
    world.y=max(0.03,world.y);
    vec4 clip=uMvp*vec4(world,1.0);
    if(clip.w<=1e-6) return;
    vUv=aPosition*2.0-1.0;vWorld=world;
    vGlow=b.look.w;
    // Gentle finite life: a quick ignition, a bright first third, then a long smooth fade to zero at death.
    float fade=smoothstep(0.0,0.12,age)*(1.0-smoothstep(0.3*life,life,age));
    float extent=b.colour.w*(1.0+4.0*vGlow)*0.5;  // pixel half-extent; raster support mirrors this bound
    // The lit core never collapses below a readable pixel; the remaining quad is the particle's own halo.
    float core=max(0.5*b.colour.w*(0.6+0.4*fade),1.0), reach=max(extent,core);
    vCore=core/reach;
    clip.xy+=vUv*2.0*reach/uViewport*clip.w;
    gl_Position=srpssTargetClip(clip,uViewport,u_target_px);
    vColour=mix(b.colour.rgb,vec3(1.0),b.look.y);
    vLight=b.look.x*fade*(0.8+0.2*sin(age*10.0+b.look.z*6.2831853));
}
