layout(std140, binding = 18) uniform RibbonDraw {
    vec4 uFloorGive;
    vec2 uSurface;
    vec3 uSweepAxis;
    vec3 uFloorContact;
    vec3 uFloorGiveFrame;
    mat4 uMvp;
    vec2 uViewport;
    vec2 u_target_px;
    vec4 uRim;
    vec3 uEye;
    vec4 uDrawCounts;
    vec4 uDrawBases;
    vec4 uContinuationBefore;
    vec4 uContinuationAfter;
    int uDiagnostic;
    vec4 uViewZ;
    vec4 uStrands;
    vec4 uBody;
    vec4 uFill;
    vec4 uGlint;
    vec4 uTone;
    vec4 uAge;
    vec3 uMistOrigin;
    vec3 uGlow;
    vec4 uLattice;
    vec2 uLatticeTone;
    vec4 uGradeStops[6];
    vec4 uGrade;
    vec4 uMist;
    vec4 uMistShape;
    mat4 uFogView;
    vec4 uFogLens;
    vec4 uFogRange;
    vec4 uPulseRim;
    vec2 uPulseRimShape;
};

#define SRPSS_CONVENTIONS_FRAGMENT
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
layout(location=0) out vec4 FragColor;

#ifdef SRPSS_NO_EMISSION
vec4 Emission;
#else
layout(location=1) out vec4 Emission;
#endif

layout(location = 0) in vec3 vWorld;
layout(location = 1) in vec3 vNormal;
layout(location = 2) in float vPhase;
layout(location = 3) in float vAcross;
layout(location = 4) in float vEmission;
layout(location = 5) in float vLocal;
layout(location = 6) in float vCoverage;
layout(location = 7) in float vExpanded;
layout(location = 8) in float vFaceScale;
layout(location = 9) flat in vec4 vColour;
layout(location = 10) flat in vec4 vColourB;
layout(location = 11) in vec4 vTint;
        // local -> view-space z (row 2 of the rebased view matrix)
          // local eye
          // half-width (across units), light, path-length cap, minimum on-screen width (px)
      // count across the width, half-width (strand spacing units), light, warp
         // alpha, tint, strand intensity variation, warp frequency (per phase unit)
         // emissive sheet light, its centre level (edges are 1), rim glow width (across), rim glow light
        // glints per strand per phase unit, chance, light, radius (strand units)
         // strand whiteness, rim whiteness, strand spacing jitter, glint minimum radius (px)
          // local now, fade-in, maximum age, fade-out (seconds); fades off when both are zero
   // packet-local -> mist world translation (packet origin plus the caller's frame)
         // local bloom share, white-hot share, local musical highlight admission
      // spacings across the width, spacings per phase unit (whole), half-width (spacings), light
  // musical gain above the quiet emission, share sent to the bloom

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

// A monotone stretch of the material coordinate: gather at one edge and fan at the other, without folding or
// creating/destroying strand identities. An additive sine warp could reverse its derivative at large strengths.
float ribbonStrandCoordinate(float across,float phase,float strength,float frequency,float jitter) {
    float stretch=exp(clamp(4.0*strength*sin(6.2831853*phase*frequency),-4.0,4.0));
    float warped=across/max(across+(1.0-across)*stretch,1e-6);
    return warped+jitter*sin(6.2831853*warped*3.0+1.3)/(6.2831853*3.0);
}


// Integral of the periodic pulse, then exact box filtering over the pixel footprint. The old single-line
// approximation faded at 0.35 spacings/pixel and erased still-resolved filaments into a solid sheet.
float strandIntegral(float x, float halfWidth) {
    return floor(x)*2.0*halfWidth+clamp(fract(x)-(0.5-halfWidth),0.0,2.0*halfWidth);
}
float strandCoverage(float x, float halfWidth, float w) {
    float filtered=(strandIntegral(x+0.5*w,halfWidth)-strandIntegral(x-0.5*w,halfWidth))/max(w,1e-4);
    return mix(filtered,2.0*halfWidth,smoothstep(0.65,1.2,w));
}
// The woven lattice: two diagonal line families in the sheet's own (warped across, path phase) coordinates.
// Each family is box-filtered like the strands and fades to its average once a spacing nears a pixel, so
// distant or grazing cells settle into an even glow instead of moire. Families combine as a union: a node
// where they cross is no brighter than a line, so the net never knots into white points.
float ribbonLattice(float across, float phase) {
    float u=across*uLattice.x, v=phase*uLattice.y;
    float a=u+v, b=u-v;
    float la=strandCoverage(a,uLattice.z,max(fwidth(a),1e-4));
    float lb=strandCoverage(b,uLattice.z,max(fwidth(b),1e-4));
    return la+lb-la*lb;
}
float strandHash(float k) { return fract(sin(k*12.9898+3.1)*43758.5453); }
float cellHash(float k, float j) { return fract(sin(k*12.9898+j*78.233+1.7)*43758.5453); }
// One-sided rim of half-width h (across units) at an edge, box-filtered over w.
float rimCoverage(float edgeDistance, float h, float w) {
    return clamp((h-edgeDistance)/max(w,1e-4)+0.5,0.0,1.0)*min(1.0,2.0*h/max(w,1e-4)+0.25);
}
float viewDepth() { return -dot(uViewZ,vec4(vWorld,1.0)); }
// A thin emissive translucent sheet seen at an angle: light and optical depth grow with the path through it,
// 1/|N.V| (capped), while its projected width shrinks by the same factor, so light per unit length is conserved.
// A fixed "grazing" boost instead lit the whole near-edge-on stretch as one flat neon band.
float pathLength() {
    vec3 n=normalize(vNormal);
    vec3 view=normalize(vWorld-uEye);
    float path=min(1.0/max(abs(dot(n,view)),1e-4),max(uRim.z,1.0));
    return mix(path,vFaceScale,clamp(vExpanded,0.0,1.0));
}
// MSAA shades a covered sample at the pixel centre, which on an edge-on sliver lies far outside the triangle:
// interpolants extrapolate there (across reached -50 and exp() overflowed into the bloom). Clamp before use.
float acrossClamped() { return clamp(vAcross,0.0,1.0); }
// The ribbon's ends live in the world where a navigating camera can see them: the head fades in and the tail
// fades out by AGE (continuous logical time), never by knot index, which would step at every admitted knot.
float ageFade() {
    float age=uAge.x-vLocal;
    float fadeIn=uAge.y>0.0?smoothstep(0.0,uAge.y,age):1.0;
    float fadeOut=uAge.w>0.0?1.0-smoothstep(uAge.z-uAge.w,uAge.z,age):1.0;
    return fadeIn*fadeOut;
}
vec3 ribbonColour() {
    vec3 own=mix(mix(vColour.rgb,vColourB.rgb,acrossClamped()),vTint.rgb,clamp(vTint.a,0.0,1.0));
    return graded(own,vWorld.x+uMistOrigin.x);
}

layout(std430,binding=2) readonly buffer PulseRimField { float pulseRimSamples[]; };
       // field edge x (history axis), inverse covered length, strength (0: off), tap spread (u)
  // inverse reference field level, response ceiling
const int PULSE_RIM_SAMPLES=385;
float pulseRimTap(float u) {
    // Every index stays inside the bound buffer whatever its size (no robust buffer access).
    int last=min(PULSE_RIM_SAMPLES,pulseRimSamples.length())-1;
    float s=u*float(PULSE_RIM_SAMPLES)-0.5;
    float i=floor(s);
    int a=clamp(int(i),0,last), b=clamp(int(i)+1,0,last);
    return mix(pulseRimSamples[a],pulseRimSamples[b],s-i);
}
float pulseRimField(float x) {
    float u=(x-uPulseRim.x)*uPulseRim.y;
    return 0.25*pulseRimTap(u-uPulseRim.w)+0.5*pulseRimTap(u)+0.25*pulseRimTap(u+uPulseRim.w);
}
float pulseRimResponse(float x) {
    float level=max(pulseRimField(x),0.0)*uPulseRimShape.x;
    return uPulseRimShape.y*tanh(level*level/uPulseRimShape.y);
}

void main() {
    srpssItemOnly(uViewport,u_target_px);
    float across=acrossClamped();
    float x=ribbonStrandCoordinate(across,vPhase,uStrands.w,uBody.w,uTone.z)*uStrands.x;
    float w=max(fwidth(x),1e-4);
    float hash=strandHash(floor(x));
    float strength=mix(0.55+0.45*hash,0.08+2.1*hash*hash,uBody.z);
    // Once unresolved, preserve the average emitted energy instead of hashing whichever line the pixel lands on.
    strength=mix(strength,mix(0.775,0.78,uBody.z),smoothstep(0.65,1.2,w));
    float strands=strandCoverage(x,uStrands.y,w)*strength;
    float wa=max(fwidth(across),1e-5);
    // The boundaries are luminous filaments, not a slab of emissive sheet. Give both a resolved core even in
    // quiet/narrow sheets. Their brightness must not depend on the two edges' different surface normals.
    float rimWidth=max(uRim.x,min(.5,1.2*wa));
    float rims=rimCoverage(across,rimWidth,wa)+rimCoverage(1.0-across,rimWidth,wa);
    // The sheet itself glows (both references): a fill brightening toward the edges, a wide rim glow beside
    // the crisp rim line, then strands and their glints on top.
    float edge=min(across,1.0-across);
    float fill=uFill.x*mix(uFill.y,1.0,pow(1.0-2.0*edge,2.0));
    float rimGlow=uFill.w*exp(-edge/max(uFill.z,min(.5,2.0*wa)));
    float glints=0.0;
    if(uGlint.x>0.0 && uGlint.z>0.0) {
        // Sparse bright points riding strands, fixed to the absolute path phase: they travel with the history.
        // Differentiate continuous coordinates before the divergent cell test. The hashed cell offset is
        // constant within each cell and must never enter derivatives at a neighbouring strand boundary.
        vec2 alongGradient=vec2(dFdx(vPhase),dFdy(vPhase))*uGlint.x;
        vec2 acrossGradient=vec2(dFdx(x),dFdy(x));
        float determinant=alongGradient.x*acrossGradient.y-alongGradient.y*acrossGradient.x;
        float k=floor(x);
        float along=vPhase*uGlint.x+strandHash(k)*7.0;
        float j=floor(along);
        float chance=clamp(uGlint.y*(1.0+uGlow.z*max(vEmission-0.6,0.0)),0.0,1.0);
        if(cellHash(k,j)<chance && abs(determinant)>1e-10) {
            // Invert the local surface-to-screen Jacobian. Dividing each coordinate by fwidth separately
            // assumes perpendicular projected axes and stretches points into dashes on skewed folds.
            vec2 delta=vec2(fract(along)-0.5,fract(x)-0.5);
            vec2 pixel=vec2(acrossGradient.y*delta.x-alongGradient.y*delta.y,
                            -acrossGradient.x*delta.x+alongGradient.x*delta.y)/determinant;
            float radiusPx=max(uGlint.w/max(w,1e-4),max(uTone.w,0.75));
            float r2=dot(pixel,pixel)/(radiusPx*radiusPx);
            // Glints belong to resolved strands: they fade with them, never smear across a sub-pixel sheet.
            glints=exp(-3.0*r2)*min(1.0,radiusPx*radiusPx)*(1.0-smoothstep(0.35,0.9,w));
        }
    }
    // The lattice glows in the sheet's own colour, quiet at rest and lit by the knot's music above its quiet level.
    float lattice=0.0;
    if(uLattice.w>0.0)
        lattice=ribbonLattice(x/uStrands.x,vPhase)*uLattice.w*(1.0+uLatticeTone.x*max(vEmission-0.6,0.0));
    // The body glows in its saturated colour; strands and rims carry the near-white light (the mock's look).
    vec3 colour=ribbonColour();
    // The brightest strands burn white-hot at their cores; the rest keep their colour.
    float hot=clamp(uTone.x+uGlow.y*smoothstep(0.9,1.9,strength),0.0,1.0);
    vec3 sheet=colour*fill+mix(colour,vec3(1.0),hot)*strands*uStrands.z
               +mix(colour,vec3(1.0),0.6)*glints*uGlint.z;
    vec3 boundary=colour*rimGlow+mix(colour,vec3(1.0),uTone.y)*rims*uRim.y;
    if(uPulseRim.z>0.0) boundary*=1.0+uPulseRim.z*pulseRimResponse(vWorld.x+uMistOrigin.x);
    float sheetScale=pathLength()*clamp(vCoverage,0.0,1.0);
    float scale=max(vEmission,0.0)*ageFade()*mistTransmittance(vWorld+uMistOrigin);
    vec3 net=colour*lattice*sheetScale*scale;
    vec3 light=(sheet*sheetScale+boundary)*scale+net;
    // Alpha: luminance-weighted world height, for contact-hardened reflections. Scene targets keep their
    // alpha (blend ZERO, ONE); a reflection target accumulates it (ONE, ONE).
    FragColor=vec4(light,dot(light,vec3(0.2126,0.7152,0.0722))*(vWorld.y+uMistOrigin.y));
    // The lattice keeps its own (smaller) bloom share: a lit net must stay a net, not a white haze.
    vec3 glowing=light-net*(1.0-uLatticeTone.y);
    Emission=vec4(glowing,dot(glowing,vec3(0.2126,0.7152,0.0722)))*uGlow.x;
}
