layout(std140, binding = 18) uniform RibbonCohortStrayDraw {
    vec4 uFloorGive;
    vec2 uSurface;
    vec3 uSweepAxis;
    vec3 uFloorContact;
    vec3 uFloorGiveFrame;
    int uVertexBase;
    mat4 uMvp;
    vec2 uViewport;
    vec4 uStray;
    vec4 uStrayLook;
    vec2 uStrayClock;
    float uStrayAdmission;
    float uStrayBirthNow;
    vec2 uStrayPulse;
    vec3 uMistOrigin;
    vec4 uMist;
    vec4 uMistShape;
    mat4 uFogView;
    vec4 uFogLens;
    vec4 uFogRange;
    vec4 uGradeStops[6];
    vec4 uGrade;
};
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
layout(location = 3) in vec3 vWorld;
layout(location = 4) in float vAlong;
layout(location = 5) in float vAcross;
layout(location = 6) in float vBright;
layout(location = 7) in float vSeed;
layout(location = 8) flat in vec3 vColour;

layout(location = 0) flat in vec4 vCohortLook;
layout(location = 2) flat in float vCohortRemaining;

float strandRemaining(float age,vec4 life) {
    age=max(age,0.0);
    if(life.x<=0.0)return 0.0;
    float expiry=1.0-smoothstep(max(life.x-life.y,0.0),life.x,age);
    float restoration=mix(life.z,1.0,1.0-exp(-age/max(0.1,min(0.4,life.x*0.1))));
    return min(expiry,restoration);
}
float strandLifeCoverage(float remaining,float along) {
    // No moving cutoff: the tip loses light sooner while the root decays slowly through the whole fade.
    return pow(clamp(remaining,0.0,1.0),1.0+2.0*clamp(along,0.0,1.0));
}

layout(location = 1) flat in vec2 vCohortGlow;  // soft halo around the filament, share sent to the bloom

        // clear-air centre x, centre z, radius x, radius z (world units)
   // falloff (radii beyond the edge per e-fold), floor thickening, thickening height, low glow
layout(binding = 8) uniform sampler3D uFogVolume; // integrated in-scatter (rgb) and transmittance (a), exponential view-depth slices
     // world -> the volume camera's view
     // Perspective tangents, unused, asinh scale (0: positive logarithmic depth)
    // near, far, slices, 1 + optional focus depth (0: disabled)

float fogDepthFraction(float depth) {
    if(uFogLens.w>0.0) {
        float focus=max(uFogRange.w-1.0,0.0);
        return (asinh((depth-focus)/uFogLens.w)-asinh((uFogRange.x-focus)/uFogLens.w)) /
            (asinh((uFogRange.y-focus)/uFogLens.w)-asinh((uFogRange.x-focus)/uFogLens.w));
    }
    return log(max(depth,uFogRange.x)/uFogRange.x)/log(uFogRange.y/uFogRange.x);
}
float fogSliceDepth(float f) {
    if(uFogLens.w>0.0) {
        float focus=max(uFogRange.w-1.0,0.0);
        return focus+uFogLens.w*sinh(mix(asinh((uFogRange.x-focus)/uFogLens.w),
            asinh((uFogRange.y-focus)/uFogLens.w),f/uFogRange.z));
    }
    return uFogRange.x*pow(uFogRange.y/uFogRange.x,f/uFogRange.z);
}

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

// Volume coordinates of a world point: xy over the view, z the continuous slice (0 at near, slices at far).
vec3 fogCoordinate(vec3 world) {
    vec3 v=(uFogView*vec4(world,1.0)).xyz;
    float depth=uFogLens.w>0.0?-v.z:max(-v.z,1e-4);
    vec2 ndc=v.xy/(uFogLens.xy*depth);
    float slice=fogDepthFraction(depth);
    return vec3(ndcToUv(ndc),slice*uFogRange.z);
}
vec4 fogVolumeAt(vec3 world) {
    vec3 c=fogCoordinate(world);
    // Texel k holds the integral to the far boundary of slice k; before the first boundary blend from clear air.
    // Level 0 named (the volume has one): no implicit derivative, so a pass may read it after a discard (R-210).
    vec4 s=textureLod(uFogVolume,clamp(vec3(c.xy,(c.z-0.5)/uFogRange.z),vec3(0.0),vec3(1.0)),0.0);
    return mix(vec4(0.0,0.0,0.0,1.0),s,clamp(c.z,0.0,1.0));
}
float mistTransmittance(vec3 world) {
    if(uFogRange.w>0.5) return fogVolumeAt(world).a;
    if(uMistShape.x<=0.0) return 1.0;
    vec2 radii=max(uMist.zw,vec2(1e-3));
    float beyond=max(0.0,length((world.xz-uMist.xy)/radii)-1.0)/uMistShape.x;
    float low=uMistShape.z>0.0?exp(-max(world.y,0.0)/uMistShape.z):0.0;
    return exp(-beyond*beyond*(1.0+uMistShape.y*low));
}
// The mist's own colour: the backdrop, lit where the haze is low and near the edge of the clear air, fading into
// darkness deeper in. (Glow by height alone lit the whole far floor.)
vec3 mistColour(vec3 backdrop, vec3 world) {
    vec2 radii=max(uMist.zw,vec2(1e-3));
    float beyond=max(0.0,length((world.xz-uMist.xy)/radii)-1.0)/max(uMistShape.x,1e-3);
    float low=uMistShape.z>0.0?exp(-max(world.y,0.0)/uMistShape.z):0.0;
    // Deeper mist also darkens (the far floor: dark toward the horizon, lit low).
    return backdrop*(0.35+0.65*exp(-0.25*beyond))*(1.0+uMistShape.w*low*exp(-0.6*beyond*beyond));
}
// An opaque surface seen through the mist: the volume's in-scatter in front of it, or the analytic mix.
vec3 mistOver(vec3 surface, vec3 backdrop, vec3 world) {
    if(uFogRange.w>0.5) { vec4 fog=fogVolumeAt(world); return surface*fog.a+fog.rgb; }
    return mix(mistColour(backdrop,world),surface,mistTransmittance(world));
}

// World colour grade (a preset look): up to GRADE_STOPS colour nodes at ascending positions across a world-x range,
// and the share they take of the ribbon's own colour. Share 0 leaves every ribbon its own colours. Between two nodes
// the colour eases (smoothstep), so a node is a soft waypoint, never a visible seam.
const int GRADE_STOPS=6;
  // rgb, position along the range (0..1, strictly ascending)
                    // world x of position 0, world x of position 1, share, node count
vec3 graded(vec3 colour, float worldX) {
    if(uGrade.z<=0.0) return colour;
    float t=clamp((worldX-uGrade.x)/max(uGrade.y-uGrade.x,1e-3),0.0,1.0);
    int count=clamp(int(uGrade.w),1,GRADE_STOPS);
    vec3 grade=uGradeStops[0].rgb;
    for(int i=1;i<count;++i)
        grade=mix(grade,uGradeStops[i].rgb,smoothstep(uGradeStops[i-1].w,uGradeStops[i].w,t));
    return mix(colour,grade,clamp(uGrade.z,0.0,1.0));
}

void main() {
    float a=vAcross*vAcross;
    float line=exp(-a*9.0);                                   // the filament: narrow core in a quad twice its width
    float along=fract(vAlong*vCohortLook.z+vSeed)-0.5;         // droplets strung along it, round over the full quad
    // Droplets gather toward the free tip, where the liquid breaks up.
    float bead=exp(-(along*along*vCohortLook.z*vCohortLook.z*0.35+a)*3.5)*smoothstep(0.3,0.9,vAlong);
    float halo=vCohortGlow.x*exp(-a*1.2)*(1.0-0.5*vAlong);  // a fuzzy splash around the clean line
    float light=(line+halo+1.6*bead)*vBright*strandLifeCoverage(vCohortRemaining,vAlong);
    if(light<=1e-4) discard;
    vec3 colour=graded(vColour,vWorld.x+uMistOrigin.x)*light*mistTransmittance(vWorld+uMistOrigin);
    FragColor=vec4(colour,dot(colour,vec3(0.2126,0.7152,0.0722))*(vWorld.y+uMistOrigin.y));  // as the light pass
    Emission=vec4(colour,dot(colour,vec3(0.2126,0.7152,0.0722)))*vCohortGlow.y;
}
