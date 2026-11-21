
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

layout(binding = 13) uniform sampler2D uFloorGiveField;
  // field edge x (world), inverse covered length (0: off), maximum depth, x derivative step
float floorGiveDepth(vec2 xz) {
    float u=(xz.x-uFloorGive.x)*uFloorGive.y;
    if(u<=0.0 || u>=1.0) return 0.0;
    vec4 depth=textureLod(uFloorGiveField,vec2(u,0.5/3.0),0.0);
    vec4 centre=textureLod(uFloorGiveField,vec2(u,1.5/3.0),0.0);
    vec4 inverse=textureLod(uFloorGiveField,vec2(u,2.5/3.0),0.0);
    vec4 d=xz.y-centre;
    float total=dot(depth,exp(-d*d*inverse));
    return uFloorGive.z*(1.0-exp(-total/uFloorGive.z));
}
// d depth / d (x, z): central differences, one field column along x.
vec2 floorGiveGradient(vec2 xz) {
    vec2 e=vec2(uFloorGive.w,0.05);
    return vec2(floorGiveDepth(xz+vec2(e.x,0.0))-floorGiveDepth(xz-vec2(e.x,0.0)),
                floorGiveDepth(xz+vec2(0.0,e.y))-floorGiveDepth(xz-vec2(0.0,e.y)))/(2.0*e);
}

struct Knot { vec4 p; vec4 q; vec4 tangent; vec4 side; vec4 tint; };  // tint: colour and its share
     // camber in half-widths; transverse subdivision count
   // zero: transported width; otherwise fixed cross-section plane
vec3 curve(vec3 a, vec3 b, vec3 c, vec3 d, float u) {
    if(u==0.0 || all(equal(b,c))) return b;
    if(u==1.0) return c;
    float t1=sqrt(max(distance(a,b),1e-6));
    float t2=t1+sqrt(max(distance(b,c),1e-6));
    float t3=t2+sqrt(max(distance(c,d),1e-6));
    float t=mix(t1,t2,u);
    vec3 a1=mix(a,b,t/t1), a2=mix(b,c,(t-t1)/(t2-t1)), a3=mix(c,d,(t-t2)/(t3-t2));
    return mix(mix(a1,a2,t/t2),mix(a2,a3,(t-t1)/(t3-t1)),(t-t1)/(t2-t1));
}
// A knot owns ONE slope, the harmonic mean of its two adjacent secants. Limiting separately against each
// interval's delta gave different slopes at the same knot, leaving little corners on the edges of the sheet.
float monotoneSlope(float a, float b, float c) {
    float left=b-a, right=c-b;
    if(left==0.0 || right==0.0 || sign(left)!=sign(right)) return 0.0;
    float small=min(abs(left),abs(right)), large=max(abs(left),abs(right));
    return sign(left)*2.0*small/(1.0+small/large);
}
// Shape-preserving cubic Hermite on the uniform knot lattice: C1 and bounded by the endpoint values.
float monotone(float a, float b, float c, float d, float u) {
    float m1=monotoneSlope(a,b,c), m2=monotoneSlope(b,c,d);
    float u2=u*u, u3=u2*u;
    return (2.0*u3-3.0*u2+1.0)*b+(u3-2.0*u2+u)*m1+(3.0*u2-2.0*u3)*c+(u3-u2)*m2;
}
vec3 hermite(vec3 a, vec3 b, vec3 c, vec3 d, float u) {
    float u2=u*u, u3=u2*u;
    return (2.0*u3-3.0*u2+1.0)*b+(u3-2.0*u2+u)*0.5*(c-a)+(3.0*u2-2.0*u3)*c+(u3-u2)*0.5*(d-b);
}
vec4 clothWeights(float u) {
    // Uniform cubic B-spline: convex weights keep positive widths and monotone axial samples monotone.
    // Both slope and curvature agree across knots. History samples are controls, not forced interpolation
    // points; forcing every control point left small shoulders even after the slope discontinuity was fixed.
    float u2=u*u, u3=u2*u, v=1.0-u;
    return vec4(v*v*v,3.0*u3-6.0*u2+4.0,-3.0*u3+3.0*u2+3.0*u+1.0,u3)/6.0;
}
vec3 clothPoint(vec3 a, vec3 b, vec3 c, vec3 d, float u) {
    vec4 w=clothWeights(u);
    return a*w.x+b*w.y+c*w.z+d*w.w;
}
vec3 pathPoint(vec3 a, vec3 b, vec3 c, vec3 d, float u) {
    return dot(uSweepAxis,uSweepAxis)>0.5?clothPoint(a,b,c,d,u):curve(a,b,c,d,u);
}
// Guard knots outside the drawable run repeat the endpoint: zero slope there, never a value from across a break.
Knot guardBefore, guardAfter;
bool station(vec3 a, vec3 b, vec3 c, vec3 d, Knot left, Knot right, float originTwist, float u,
             out vec3 lo, out vec3 hi, out vec3 normal, out vec3 pathTangent) {
    vec3 localA=a-b, localC=c-b, localD=d-b;
    vec3 at=b+pathPoint(localA,vec3(0),localC,localD,u);
    vec3 tangent=pathPoint(localA,vec3(0),localC,localD,min(1.0,u+0.001))
                -pathPoint(localA,vec3(0),localC,localD,max(0.0,u-0.001));
    if(dot(tangent,tangent)<1e-18) return false;
    tangent=normalize(tangent);
    pathTangent=tangent;
    bool cloth=dot(uSweepAxis,uSweepAxis)>0.5;
    vec3 axis=cloth?uSweepAxis:tangent;
    // A fixed sweep plane has a fixed world reference: authored twist is its sole rotation. Projecting a
    // transported path frame into this plane amplified its torsion near steep bends, creating tight turns.
    vec3 reference=abs(axis.y)<0.95?vec3(0,1,0):vec3(0,0,1);
    vec3 side=cloth?reference:hermite(guardBefore.side.xyz,left.side.xyz,right.side.xyz,guardAfter.side.xyz,u);
    side-=axis*dot(side,axis);
    if(dot(side,side)<1e-12) return false;
    side=normalize(side);
    vec4 weights=clothWeights(u);
    float twist=originTwist+(cloth?dot(weights,vec4(guardBefore.q.y,left.q.y,right.q.y,guardAfter.q.y))
                                 :monotone(guardBefore.q.y,left.q.y,right.q.y,guardAfter.q.y,u));
    side=cos(twist)*side+sin(twist)*cross(axis,side);
    float width=cloth?dot(weights,vec4(guardBefore.p.w,left.p.w,right.p.w,guardAfter.p.w))
                      :clamp(monotone(guardBefore.p.w,left.p.w,right.p.w,guardAfter.p.w,u),
                      min(left.p.w,right.p.w),max(left.p.w,right.p.w));
    lo=at-width*side; hi=at+width*side;
    normal=normalize(cross(tangent,side));
    return !all(equal(lo,hi));
}
// Floor contact: where the sheet would pass below the floor it deforms along it, like cloth settling. Height is eased
// (softplus) onto the floor plus a small gap: a smooth, strictly increasing map of y alone, so the sheet can never
// fold over itself or crease, and points clear of the floor keep their shape. A sideways spread was rejected: it
// folded the sheet at its centre into sharp corners. Softness 0 is off.
  // floor height (packet-local y), gap, softness
float floorEased(float y) {
    float low=uFloorContact.x+uFloorContact.y;
    float x=(y-low)/uFloorContact.z;
    return low+uFloorContact.z*(x>0.0?x+log(1.0+exp(-x)):log(1.0+exp(x)));
}
float floorSlope(float y) {  // d floorEased / dy
    return 1.0/(1.0+exp(-(y-uFloorContact.x-uFloorContact.y)/uFloorContact.z));
}
// With the floor's give the same map eases onto the yielding surface: the ribbon dips into the dent under it.
  // packet-local -> world: x, z offsets; Travel Direction sign (-1 mirrors x; 0: +1)
vec2 floorGiveWorld(vec3 p) {
    vec2 xz=p.xz+uFloorGiveFrame.xy;
    return vec2(uFloorGiveFrame.z<0.0?-xz.x:xz.x,xz.y);
}
float floorGiveSurface(vec3 p) {  // the yielding floor's height under a packet-local point, relative to the plane
    return -floorGiveDepth(floorGiveWorld(p));
}
vec3 floorContact(vec3 p) {
    if(uFloorContact.z>0.0 && uFloorGive.y>0.0) {
        float h=floorGiveSurface(p);
        return vec3(p.x,h+floorEased(p.y-h),p.z);
    }
    return uFloorContact.z>0.0?vec3(p.x,floorEased(p.y),p.z):p;
}
vec3 surfacePoint(vec3 low, vec3 high, vec3 normal, float across) {
    vec3 side=normalize(high-low);
    vec3 bow=dot(uSweepAxis,uSweepAxis)>0.5?cross(uSweepAxis,side):normal;
    float q=2.0*across-1.0;
    return floorContact(mix(low,high,across)+bow*0.5*length(high-low)*uSurface.x*(1.0-q*q));
}

struct Ribbon { vec4 meta; vec4 extra; vec4 colourA; vec4 colourB; Knot knots[256]; };
layout(std430, binding=0) readonly buffer Paths { Ribbon paths[]; };

     // pixels; with uRim.w (minimum on-screen width) zero, no widening
   // the drawn target's pixels (the native core's member; srpssTargetClip)


layout(location = 0) out vec3 vWorld;
layout(location = 1) out vec3 vNormal;
layout(location = 2) out float vPhase;
layout(location = 3) out float vAcross;
layout(location = 4) out float vEmission;
layout(location = 5) out float vLocal;
layout(location = 6) out float vCoverage;
layout(location = 7) out float vExpanded;
layout(location = 8) out float vFaceScale;
layout(location = 9) flat out vec4 vColour;
layout(location = 10) flat out vec4 vColourB;
layout(location = 11) out vec4 vTint;
// Chronological knot i lives in ring slot (start+i)%capacity; a stateless packet has start 0.
int ringStart, ringCapacity;
Knot knotAt(int owner, int i) { return paths[owner].knots[(ringStart+i)%ringCapacity]; }

// One draw (N5.4): the culled body, then the before and the after extension, as consecutive vertex ranges (the native
// core's draw is a count from vertex 0, D15 point 6; one pass where three draws were). Each part's vertex count and its
// first vertex in the culled strip, and each extension's packet-local min/max x, subdivisions and side (-1, +1).
// The ranges are whole numbers held as floats (exact below 2^24): the native core fills a vec4 from the record, an
// int vector only under a range rule its schema gives scalars alone.




int drawnVertex;
vec4 drawnContinuation;  // the body's 0: no continuation
void continuationMain(int owner,int crossDiv);
bool continuationAnchored(int owner);
int continuationAnchorKnot(int owner,bool before);

void main() {
    int drawn=srpssVertexIndex;
    ivec4 drawCounts=ivec4(uDrawCounts), drawBases=ivec4(uDrawBases);
    int part=drawn<drawCounts.x?0:(drawn<drawCounts.x+drawCounts.y?1:2);
    drawnVertex=drawn-(part==0?0:(part==1?drawCounts.x:drawCounts.x+drawCounts.y))+drawBases[part];
    drawnContinuation=part==0?vec4(0.0):(part==1?uContinuationBefore:uContinuationAfter);

    int owner=srpssInstanceIndex;
    ringCapacity=clamp(int(paths[owner].extra.z),1,256);
    ringStart=clamp(int(paths[owner].extra.y),0,ringCapacity-1);
    int count=clamp(int(paths[owner].meta.x),0,ringCapacity);
    int divisions=clamp(int(paths[owner].meta.y),1,8);
    int crossDiv=max(int(uSurface.y),1);
    int vertexId=drawnVertex;
    int interval=vertexId/(6*crossDiv), corner=vertexId%6;
    int acrossStrip=(vertexId/6)%crossDiv;
    int segment=interval/divisions;
    gl_Position=vec4(2,2,2,1); vWorld=vec3(0); vNormal=vec3(0,0,1); vPhase=0; vAcross=0; vEmission=0;
    vColour=vec4(0); vColourB=vec4(0); vTint=vec4(0);
    if(drawnContinuation.w!=0.0) { continuationMain(owner,crossDiv); return; }
    if(segment>=count-1) return;
    Knot left=knotAt(owner,segment), right=knotAt(owner,segment+1);
    // q.w marks a knot that starts a new strip (ring break/reseed): nothing joins into it.
    if(left.q.z<0.5 || right.q.z<0.5 || right.q.w>0.5 || all(equal(left.p.xyz,right.p.xyz))) return;
    // Independent triangles: L0 L1 R0, R0 L1 R1. No bridge across invalid intervals.
    bool next=corner==1 || corner>=4;
    bool highAcross=corner==2 || corner==3 || corner==5;
    float acrossFraction=float(acrossStrip+(highAcross?1:0))/float(crossDiv);
    float signWidth=acrossFraction*2.0-1.0;
    float u=float(interval%divisions+(next?1:0))/float(divisions);
    vec3 b=left.p.xyz,c=right.p.xyz;
    Knot before=knotAt(owner,max(segment-1,0)), after=knotAt(owner,min(segment+2,count-1));
    vec3 a=segment>0?before.p.xyz:2*b-c;
    vec3 d=segment+2<count?after.p.xyz:2*c-b;
    // Invalid guard knots must not pull an otherwise valid interval across a gap.
    bool joinsBefore=segment>0 && before.q.z>0.5 && left.q.w<0.5;
    bool joinsAfter=segment+2<count && after.q.z>0.5 && after.q.w<0.5;
    if(segment>0 && !joinsBefore) a=2*b-c;
    if(segment+2<count && !joinsAfter) d=2*c-b;
    guardBefore=joinsBefore?before:left;
    guardAfter=joinsAfter?after:right;
    float u0=float(interval%divisions)/float(divisions), u1=float(interval%divisions+1)/float(divisions);

    if(continuationAnchored(owner)) {
        int tailKnot=continuationAnchorKnot(owner,true),headKnot=continuationAnchorKnot(owner,false);
        if(segment<tailKnot || segment>headKnot) return;
        float share=clamp(paths[owner].extra.w,0.0,1.0);
        float low=segment==tailKnot?share:0.0,high=segment==headKnot?share:1.0;
        if(high<=low) return;
        u0=mix(low,high,u0);u1=mix(low,high,u1);u=mix(low,high,u);
    }
    vec3 l0,r0,l1,r1,n0,n1,t0,t1;
    // Both endpoints must admit before ANY corner is emitted; partial rejection
    // would stretch the surviving triangle towards the offscreen sentinel.
    if(!station(a,b,c,d,left,right,paths[owner].extra.x,u0,l0,r0,n0,t0) ||
       !station(a,b,c,d,left,right,paths[owner].extra.x,u1,l1,r1,n1,t1)) return;
    vec3 low=next?l1:l0, high=next?r1:r0;
    vec3 side=normalize(high-low), normal=next?n1:n0;
    float halfWidth=0.5*length(high-low);
    // A bowed cross section remains a smooth sheet through an edge-on fold instead of pinching to a flat line.
    // Edges are unchanged; the surface and its analytic cross derivative are continuous across all eight strips.
    vec3 bow=dot(uSweepAxis,uSweepAxis)>0.5?cross(uSweepAxis,side):normal;
    vWorld=surfacePoint(low,high,normal,acrossFraction);
    // Differentiate the actual swept surface, including width, twist and camber changes along its length.
    // Centreline tangents alone give incorrect grazing light on a twisting sheet. Both samples are local to
    // this interval, so breaks never enter the derivative; shared knot slopes make the one-sided limits agree.
    vec3 lm,hm,nm,tm,lp,hp,np,tp;
    if(!station(a,b,c,d,left,right,paths[owner].extra.x,max(0.0,u-0.002),lm,hm,nm,tm) ||
       !station(a,b,c,d,left,right,paths[owner].extra.x,min(1.0,u+0.002),lp,hp,np,tp)) return;
    vec3 along=surfacePoint(lp,hp,np,acrossFraction)-surfacePoint(lm,hm,nm,acrossFraction);
    vec3 acrossSlope=side-2.0*uSurface.x*signWidth*bow;
    // The floor contact squashes height: the across derivative's y scales with the eased height's slope.
    vec3 unsquashed=mix(low,high,acrossFraction)+bow*0.5*length(high-low)*uSurface.x*(1.0-signWidth*signWidth);
    if(uFloorContact.z>0.0 && uFloorGive.y>0.0) {
        // Eased onto the yielding surface h(x,z): y' = h + E(y-h), so dy'/da = E'(y-h)(dy/da-dh/da)+dh/da.
        float h=floorGiveSurface(unsquashed);
        vec2 slope=floorGiveGradient(floorGiveWorld(unsquashed));
        if(uFloorGiveFrame.z<0.0) slope.x=-slope.x;  // d world x / d local x
        float dh=-dot(slope,acrossSlope.xz);
        float s=floorSlope(unsquashed.y-h);
        acrossSlope.y=s*(acrossSlope.y-dh)+dh;
    } else if(uFloorContact.z>0.0) acrossSlope.y*=floorSlope(unsquashed.y);
    vNormal=normalize(cross(along,acrossSlope));
    vAcross=acrossFraction;
    vEmission=monotone(guardBefore.side.w,left.side.w,right.side.w,guardAfter.side.w,u);
    vLocal=mix(left.q.x,right.q.x,u);
    vPhase=paths[owner].meta.z+mix(left.q.x,right.q.x,u)/paths[owner].meta.w;
    vColour=paths[owner].colourA;
    vColourB=paths[owner].colourB;
    vTint=mix(left.tint,right.tint,u);
    gl_Position=srpssTargetClip(uMvp*vec4(vWorld,1),uViewport,u_target_px);
    vCoverage=1.0; vExpanded=0.0; vFaceScale=1.0;
    // An edge-on sheet projects narrower than a pixel and MSAA catches it in dashes. Keep at least uRim.w pixels
    // across the screen-space tangent. Light per unit length must stay that of the real sheet through the fold:
    // the fragment's path-length gain becomes (face-on width)/(drawn width), which equals 1/|N.V| where widening
    // starts, so the two meet continuously (a capped gain times shrinking coverage went dark at the fold).
    float minimum=uSurface.x>0.0?0.0:uRim.w;
    if(minimum>0.0) {
        vec3 lo=next?l1:l0, hi=next?r1:r0;
        vec4 clo=uMvp*vec4(lo,1.0), chi=uMvp*vec4(hi,1.0), cc=uMvp*vec4((lo+hi)*0.5,1.0);
        vec2 half_=0.5*uViewport;
        float drawn=length((chi.xy/chi.w-clo.xy/clo.w)*half_);
        vec4 ca=uMvp*vec4((l0+r0)*0.5,1.0), cb=uMvp*vec4((l1+r1)*0.5,1.0);
        vec2 along=(cb.xy/cb.w-ca.xy/ca.w)*half_;
        if(drawn<minimum && dot(along,along)>1e-8) {
            vec3 middle=(lo+hi)*0.5;
            vec3 view=normalize(middle-uEye);
            // Orient the widened edges by the sheet's facing, sign(N.V), computed in world space: it flips once
            // where the sheet turns over. The sign of the projected width is numerical noise along a long
            // near-edge-on stretch, and each flip drew a bow-tie (the fold broke into a gap). In screen space
            // the projected across direction is -sign(N.V) times the tangent's left normal.
            vec2 perp=normalize(vec2(-along.y,along.x))*(dot(next?n1:n0,view)>0.0?-1.0:1.0);
            vec2 centre=cc.xy/cc.w*half_+perp*signWidth*0.5*minimum;
            gl_Position=srpssTargetClip(vec4(centre/half_*cc.w,cc.z,cc.w),uViewport,u_target_px);
            vCoverage=max(drawn,1e-3)/minimum;
            vec3 across=cross(view,(l1+r1)*0.5-(l0+r0)*0.5);
            if(dot(across,across)>1e-24) {
                across=normalize(across)*0.5*length(hi-lo);
                vec4 fa=uMvp*vec4(middle+across,1.0), fb=uMvp*vec4(middle-across,1.0);
                vFaceScale=length((fa.xy/fa.w-fb.xy/fb.w)*half_)/minimum;
                vExpanded=1.0;
            }
        }
    }
}

Knot continuationControl(int owner,int i) {
    int count=int(paths[owner].meta.x),cap=int(paths[owner].extra.z),start=int(paths[owner].extra.y);
    return paths[owner].knots[(start+clamp(i,0,count-1))%cap];
}
// Components: transverse centre y/z, half width, axial twist.
vec4 continuationValues(Knot k) { return vec4(k.p.yz,k.p.w,k.q.y); }
vec4 continuationWeights(float u) {
    float u2=u*u,u3=u2*u,v=1.0-u;
    return vec4(v*v*v,3.0*u3-6.0*u2+4.0,-3.0*u3+3.0*u2+3.0*u+1.0,u3)/6.0;
}
vec4 clothField(int owner,float x) {
    int last=int(paths[owner].meta.x)-1,lo=0,hi=last;
    while(hi-lo>1) { int mid=(lo+hi)/2;if(continuationControl(owner,mid).p.x<=x)lo=mid;else hi=mid; }
    Knot a=continuationControl(owner,lo-1),b=continuationControl(owner,lo),
         c=continuationControl(owner,hi),d=continuationControl(owner,hi+1);
    vec4 av=continuationValues(a),bv=continuationValues(b),cv=continuationValues(c),dv=continuationValues(d);
    if(lo==0) { a.p.xyz=2.0*b.p.xyz-c.p.xyz;av.xy=a.p.yz; }
    if(hi==last) { d.p.xyz=2.0*c.p.xyz-b.p.xyz;dv.xy=d.p.yz; }
    vec4 xs=vec4(a.p.x,b.p.x,c.p.x,d.p.x);
    float u=clamp((x-b.p.x)/(c.p.x-b.p.x),0.0,1.0);
    for(int i=0;i<5;i++) {
        vec4 w=continuationWeights(u);
        vec4 dw=vec4(-3.0*(1.0-u)*(1.0-u),9.0*u*u-12.0*u,-9.0*u*u+6.0*u+3.0,3.0*u*u)/6.0;
        u=clamp(u-(dot(w,xs)-x)/max(dot(dw,xs),1e-8),0.0,1.0);
    }
    vec4 w=continuationWeights(u);
    return av*w.x+bv*w.y+cv*w.z+dv*w.w;
}
const int ANCHOR_INSET=2;
bool continuationAnchored(int owner) { return int(paths[owner].meta.x)>=2*ANCHOR_INSET+2; }
// The anchor segment's first chronological knot: its controls never include an admitted or evicted knot.
int continuationAnchorKnot(int owner,bool before) {
    return before?ANCHOR_INSET:int(paths[owner].meta.x)-2-ANCHOR_INSET;
}
float continuationAnchor(int owner,bool before) {
    int last=int(paths[owner].meta.x)-1;
    if(!continuationAnchored(owner)) return continuationControl(owner,before?0:last).p.x;
    int i=continuationAnchorKnot(owner,before);
    return mix(continuationControl(owner,i).p.x,continuationControl(owner,i+1).p.x,clamp(paths[owner].extra.w,0.0,1.0));
}
// Exact cloth value and its first/second axial derivatives at x (same spline and guards as clothField).
void clothJet(int owner,float x,out vec4 value,out vec4 first,out vec4 second) {
    int last=int(paths[owner].meta.x)-1,lo=0,hi=last;
    while(hi-lo>1) { int mid=(lo+hi)/2;if(continuationControl(owner,mid).p.x<=x)lo=mid;else hi=mid; }
    Knot a=continuationControl(owner,lo-1),b=continuationControl(owner,lo),
         c=continuationControl(owner,hi),d=continuationControl(owner,hi+1);
    vec4 av=continuationValues(a),bv=continuationValues(b),cv=continuationValues(c),dv=continuationValues(d);
    if(lo==0) { a.p.xyz=2.0*b.p.xyz-c.p.xyz;av.xy=a.p.yz; }
    if(hi==last) { d.p.xyz=2.0*c.p.xyz-b.p.xyz;dv.xy=d.p.yz; }
    vec4 xs=vec4(a.p.x,b.p.x,c.p.x,d.p.x);
    float u=clamp((x-b.p.x)/(c.p.x-b.p.x),0.0,1.0);
    for(int i=0;i<5;i++) {
        vec4 w=continuationWeights(u);
        vec4 dw=vec4(-3.0*(1.0-u)*(1.0-u),9.0*u*u-12.0*u,-9.0*u*u+6.0*u+3.0,3.0*u*u)/6.0;
        u=clamp(u-(dot(w,xs)-x)/max(dot(dw,xs),1e-8),0.0,1.0);
    }
    vec4 w=continuationWeights(u);
    vec4 dw=vec4(-3.0*(1.0-u)*(1.0-u),9.0*u*u-12.0*u,-9.0*u*u+6.0*u+3.0,3.0*u*u)/6.0;
    vec4 ddw=vec4(6.0*(1.0-u),18.0*u-12.0,-18.0*u+6.0,6.0*u)/6.0;
    float dx=dot(dw,xs),ddx=dot(ddw,xs);
    vec4 du=av*dw.x+bv*dw.y+cv*dw.z+dv*dw.w,ddu=av*ddw.x+bv*ddw.y+cv*ddw.z+dv*ddw.w;
    value=av*w.x+bv*w.y+cv*w.z+dv*w.w;
    first=du/dx;second=(ddu*dx-du*ddx)/(dx*dx*dx);
}
vec4 continuationField(int owner,float x) {
    int last=int(paths[owner].meta.x)-1;
    if(continuationAnchored(owner)) {
        float tail=continuationAnchor(owner,true),head=continuationAnchor(owner,false);
        bool before=x<=0.5*(tail+head);
        float origin=before?tail:head,delta=x-origin,sign_=before?-1.0:1.0;
        vec4 f,first,second;
        clothJet(owner,origin,f,first,second);
        int i=continuationAnchorKnot(owner,before);
        float reach=max(abs(continuationControl(owner,i+1).p.x-continuationControl(owner,i).p.x),1e-5);
        vec4 result=f;
        result.xy+=first.xy*sin(delta)+second.xy*(1.0-cos(delta));
        float s=abs(delta),scaled=min(s/reach,80.0),decay=exp(-scaled);
        vec2 g1=first.zw*sign_,g2=second.zw;
        g2.x=g2.x/f.z-pow(g1.x/f.z,2.0);g1.x/=f.z;
        vec2 correction=(g1*reach*scaled+(0.5*g2*reach*reach+g1*reach)*scaled*scaled)*decay;
        result.z=f.z*exp(correction.x);result.w=f.w+correction.y;
        return result;
    }
    bool before=x<=0.5*(continuationControl(owner,0).p.x+continuationControl(owner,last).p.x);
    Knot b=continuationControl(owner,before?0:last-1),c=continuationControl(owner,before?1:last);
    Knot a=continuationControl(owner,before?0:last-2),d=continuationControl(owner,before?2:last);
    vec4 av=continuationValues(a),bv=continuationValues(b),cv=continuationValues(c),dv=continuationValues(d);
    // Geometric guard positions extrapolate; scalar width/twist guards repeat, exactly as station().
    if(before) { a.p.xyz=2.0*b.p.xyz-c.p.xyz;av.xy=a.p.yz; }
    else { d.p.xyz=2.0*c.p.xyz-b.p.xyz;dv.xy=d.p.yz; }
    vec4 f=before?(av+4.0*bv+cv)/6.0:(bv+4.0*cv+dv)/6.0;
    vec4 du=before?(cv-av)*0.5:(dv-bv)*0.5;
    vec4 ddu=before?av-2.0*bv+cv:bv-2.0*cv+dv;
    float dx=before?(c.p.x-a.p.x)*0.5:(d.p.x-b.p.x)*0.5;
    float ddx=before?a.p.x-2.0*b.p.x+c.p.x:b.p.x-2.0*c.p.x+d.p.x;
    vec4 first=du/dx,second=(ddu*dx-du*ddx)/(dx*dx*dx);
    float origin=before?b.p.x:c.p.x,delta=x-origin,sign_=before?-1.0:1.0;
    // Fixed world-unit frequency; phase is inherited from the actual endpoint jets, never from the view.
    float frequency=1.0;
    vec4 result=f;
    result.xy+=first.xy*sin(frequency*delta)/frequency+second.xy*(1.0-cos(frequency*delta))/(frequency*frequency);
    // Positive widths: continue log(width). Twist and width settle smoothly over one control spacing.
    float reach=max(abs(c.p.x-b.p.x),1e-5),s=abs(delta),scaled=min(s/reach,80.0),decay=exp(-scaled);
    vec2 g1=first.zw*sign_,g2=second.zw;
    g2.x=g2.x/f.z-pow(g1.x/f.z,2.0);g1.x/=f.z;
    vec2 correction=(g1*reach*scaled+(0.5*g2*reach*reach+g1*reach)*scaled*scaled)*decay;
    result.z=f.z*exp(correction.x);result.w=f.w+correction.y;
    return result;
}

vec3 continuedSurface(int owner,float x,float across) {
    vec4 f=continuationField(owner,x);
    vec3 centre=vec3(x,f.xy);
    float angle=paths[owner].extra.x+f.w;
    vec3 side=vec3(0,cos(angle),sin(angle));
    return surfacePoint(centre-f.z*side,centre+f.z*side,cross(vec3(1,0,0),side),across);
}
void continuationMain(int owner,int crossDiv) {
    int last=int(paths[owner].meta.x)-1;
    bool before=drawnContinuation.w<0.0;
    float edgeX=continuationAnchor(owner,before);
    float limit=before?drawnContinuation.x:drawnContinuation.y;
    if((before && limit>=edgeX) || (!before && limit<=edgeX))return;
    int vertexId=drawnVertex;
    int interval=vertexId/(6*crossDiv),corner=vertexId%6;
    int strip=(vertexId/6)%crossDiv;
    bool next=corner==1 || corner>=4,highAcross=corner==2 || corner==3 || corner==5;
    float across=float(strip+(highAcross?1:0))/float(crossDiv);
    float t=float(interval+(next?1:0))/drawnContinuation.z;
    // Cluster stations at the C2 join without moving any world-space point.
    float x=mix(edgeX,limit,t*t);
    vec4 f=continuationField(owner,x);
    vWorld=continuedSurface(owner,x,across);
    vec3 along=continuedSurface(owner,x+0.001,across)-continuedSurface(owner,x-0.001,across);
    vec3 across_=continuedSurface(owner,x,min(1.0,across+0.001))-continuedSurface(owner,x,max(0.0,across-0.001));
    vNormal=normalize(cross(along,across_));
    // Local time, emission and tint continue from the anchor segment (phase-weighted, so they never step either).
    int i=continuationAnchored(owner)?continuationAnchorKnot(owner,before):(before?0:last-1);
    Knot k0=continuationControl(owner,i),k1=continuationControl(owner,i+1);
    float share=continuationAnchored(owner)?clamp(paths[owner].extra.w,0.0,1.0):(before?0.0:1.0);
    vAcross=across;vEmission=mix(k0.side.w,k1.side.w,share);
    vLocal=k0.q.x+(x-k0.p.x)*(k1.q.x-k0.q.x)/(k1.p.x-k0.p.x);
    vPhase=paths[owner].meta.z+vLocal/paths[owner].meta.w;
    vColour=paths[owner].colourA;vColourB=paths[owner].colourB;vTint=mix(k0.tint,k1.tint,share);
    vCoverage=1.0;vExpanded=0.0;vFaceScale=1.0;
    gl_Position=srpssTargetClip(uMvp*vec4(vWorld,1),uViewport,u_target_px);
}
