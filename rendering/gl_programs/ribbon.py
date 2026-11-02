"""Independent oriented-strip expansion and its filament material; no mode, simulation or camera owner.

Three fragment programs share one vertex stage:

- ``RIBBON_FRAGMENT``: diagnostics (flat colour, face normals, strand phase).
- ``RIBBON_BODY_FRAGMENT``: the faint translucent sheet, written inside ``SceneTarget.transparent_writes``
  through the shared weighted-blended OIT (order-independent, depth-tested, no depth writes).
- ``RIBBON_LIGHT_FRAGMENT``: sheet glow, rims, longitudinal filament strands and glints, added to colour (location 0)
  and to the overlay's emission (location 1) after the OIT resolve. Addition is order-independent, and
  crossings sum in HDR until the target's single tone map turns them white-hot.

The material knows widths, strands and light, never music: callers feed per-knot emission (``side.w``) and
per-ribbon colours, and choose the knobs. Strands and rims are box-filtered over the pixel footprint and fade
to their average density once sub-pixel to limit crawling under slow motion.
"""
from core.ribbon_geometry import MAX_PATH_SAMPLES
from rendering.gl_programs.mist import MIST_GLSL
from rendering.quick.scene3d.target import SCENE_OIT_GLSL

RIBBON_GRADE_GLSL = """
// World colour grade (a preset look): up to GRADE_STOPS colour nodes at ascending positions across a world-x range,
// and the share they take of the ribbon's own colour. Share 0 leaves every ribbon its own colours. Between two nodes
// the colour eases (smoothstep), so a node is a soft waypoint, never a visible seam.
const int GRADE_STOPS=6;
uniform vec4 uGradeStops[GRADE_STOPS];  // rgb, position along the range (0..1, strictly ascending)
uniform vec4 uGrade;                    // world x of position 0, world x of position 1, share, node count
vec3 graded(vec3 colour, float worldX) {
    if(uGrade.z<=0.0) return colour;
    float t=clamp((worldX-uGrade.x)/max(uGrade.y-uGrade.x,1e-3),0.0,1.0);
    int count=clamp(int(uGrade.w),1,GRADE_STOPS);
    vec3 grade=uGradeStops[0].rgb;
    for(int i=1;i<count;++i)
        grade=mix(grade,uGradeStops[i].rgb,smoothstep(uGradeStops[i-1].w,uGradeStops[i].w,t));
    return mix(colour,grade,clamp(uGrade.z,0.0,1.0));
}
"""

_RIBBON_SURFACE_GLSL = """
struct Knot { vec4 p; vec4 q; vec4 tangent; vec4 side; vec4 tint; };  // tint: colour and its share
uniform vec2 uSurface;     // camber in half-widths; transverse subdivision count
uniform vec3 uSweepAxis;   // zero: transported width; otherwise fixed cross-section plane
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
uniform vec3 uFloorContact;  // floor height (packet-local y), gap, softness
float floorEased(float y) {
    float low=uFloorContact.x+uFloorContact.y;
    float x=(y-low)/uFloorContact.z;
    return low+uFloorContact.z*(x>0.0?x+log(1.0+exp(-x)):log(1.0+exp(x)));
}
float floorSlope(float y) {  // d floorEased / dy
    return 1.0/(1.0+exp(-(y-uFloorContact.x-uFloorContact.y)/uFloorContact.z));
}
vec3 floorContact(vec3 p) {
    return uFloorContact.z>0.0?vec3(p.x,floorEased(p.y),p.z):p;
}
vec3 surfacePoint(vec3 low, vec3 high, vec3 normal, float across) {
    vec3 side=normalize(high-low);
    vec3 bow=dot(uSweepAxis,uSweepAxis)>0.5?cross(uSweepAxis,side):normal;
    float q=2.0*across-1.0;
    return floorContact(mix(low,high,across)+bow*0.5*length(high-low)*uSurface.x*(1.0-q*q));
}
"""

RIBBON_VERTEX = ("#version 460 core\n" + _RIBBON_SURFACE_GLSL + """
struct Ribbon { vec4 meta; vec4 extra; vec4 colourA; vec4 colourB; Knot knots[MAX_KNOTS]; };
layout(std430, binding=0) readonly buffer Paths { Ribbon paths[]; };
uniform mat4 uMvp;
uniform vec2 uViewport;     // pixels; with uRim.w (minimum on-screen width) zero, no widening
uniform vec4 uRim;
uniform vec3 uEye;
uniform vec3 uForward;
uniform int uOrthographic;
out vec3 vWorld;
out vec3 vNormal;
out float vPhase;
out float vAcross;
out float vEmission;
out float vLocal;
out float vCoverage;
out float vExpanded;
out float vFaceScale;
flat out vec4 vColour;
flat out vec4 vColourB;
out vec4 vTint;
// Chronological knot i lives in ring slot (start+i)%capacity; a stateless packet has start 0.
int ringStart, ringCapacity;
Knot knotAt(int owner, int i) { return paths[owner].knots[(ringStart+i)%ringCapacity]; }
void main() {
    int owner=gl_InstanceID;
    ringCapacity=clamp(int(paths[owner].extra.z),1,MAX_KNOTS);
    ringStart=clamp(int(paths[owner].extra.y),0,ringCapacity-1);
    int count=clamp(int(paths[owner].meta.x),0,ringCapacity);
    int divisions=clamp(int(paths[owner].meta.y),1,8);
    int crossDiv=max(int(uSurface.y),1);
    int interval=gl_VertexID/(6*crossDiv), corner=gl_VertexID%6;
    int acrossStrip=(gl_VertexID/6)%crossDiv;
    int segment=interval/divisions;
    gl_Position=vec4(2,2,2,1); vWorld=vec3(0); vNormal=vec3(0,0,1); vPhase=0; vAcross=0; vEmission=0;
    vColour=vec4(0); vColourB=vec4(0); vTint=vec4(0);
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
    if(uFloorContact.z>0.0) acrossSlope.y*=floorSlope(unsquashed.y);
    vNormal=normalize(cross(along,acrossSlope));
    vAcross=acrossFraction;
    vEmission=monotone(guardBefore.side.w,left.side.w,right.side.w,guardAfter.side.w,u);
    vLocal=mix(left.q.x,right.q.x,u);
    vPhase=paths[owner].meta.z+mix(left.q.x,right.q.x,u)/paths[owner].meta.w;
    vColour=paths[owner].colourA;
    vColourB=paths[owner].colourB;
    vTint=mix(left.tint,right.tint,u);
    gl_Position=uMvp*vec4(vWorld,1);
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
            vec3 view=uOrthographic==1?normalize(uForward):normalize(middle-uEye);
            // Orient the widened edges by the sheet's facing, sign(N.V), computed in world space: it flips once
            // where the sheet turns over. The sign of the projected width is numerical noise along a long
            // near-edge-on stretch, and each flip drew a bow-tie (the fold broke into a gap). In screen space
            // the projected across direction is -sign(N.V) times the tangent's left normal.
            vec2 perp=normalize(vec2(-along.y,along.x))*(dot(next?n1:n0,view)>0.0?-1.0:1.0);
            vec2 centre=cc.xy/cc.w*half_+perp*signWidth*0.5*minimum;
            gl_Position=vec4(centre/half_*cc.w,cc.z,cc.w);
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
""").replace('MAX_KNOTS', str(MAX_PATH_SAMPLES))

# Sparks attached to the ribbon's history (no state, no CPU per tick): every knot owns a few spark slots; tangent.w
# is the share alive (the highs when the knot was admitted). A spark is born on the ribbon between its knot and the
# next, then drifts off along a hashed direction as it ages on the ribbon's own clock, fading over its lifetime. Its
# identity hashes the knot's absolute coordinate (stable across rebases) with integers: a sine hash of an interpolated
# or large float is not stable (3D foundation lessons).
RIBBON_SPARK_VERTEX = ("#version 460 core\n" + _RIBBON_SURFACE_GLSL + """
struct Ribbon { vec4 meta; vec4 extra; vec4 colourA; vec4 colourB; Knot knots[MAX_KNOTS]; };
layout(std430, binding=0) readonly buffer Paths { Ribbon paths[]; };
uniform mat4 uMvp;
uniform vec4 uSpark;       // slots per knot, lifetime (s), drift speed (units/s), rise bias
uniform vec4 uSparkLook;   // smallest size (px), largest size (px), light, twinkle (Hz)
uniform vec2 uSparkClock;  // local now (s), absolute coordinate origin mod 1000 (stable identity)
out vec3 vWorld;
out float vBright;
flat out vec3 vColour;
int ringStart, ringCapacity;
Knot knotAt(int owner, int i) { return paths[owner].knots[(ringStart+i)%ringCapacity]; }
uint mixBits(uint x) { x^=x>>16; x*=0x7feb352dU; x^=x>>15; x*=0x846ca68bU; x^=x>>16; return x; }
float unit(uint x) { return float(mixBits(x)&0xffffffU)/16777216.0; }
void main() {
    int owner=gl_InstanceID;
    ringCapacity=clamp(int(paths[owner].extra.z),1,MAX_KNOTS);
    ringStart=clamp(int(paths[owner].extra.y),0,ringCapacity-1);
    int count=clamp(int(paths[owner].meta.x),0,ringCapacity);
    int perKnot=max(int(uSpark.x),1);
    int index=gl_VertexID/perKnot, slot=gl_VertexID%perKnot;
    gl_Position=vec4(2.0,2.0,2.0,1.0); gl_PointSize=0.0; vBright=0.0; vWorld=vec3(0.0); vColour=vec3(0.0);
    if(index>=count-1) return;
    Knot k=knotAt(owner,index), n=knotAt(owner,index+1);
    if(k.q.z<0.5 || n.q.z<0.5 || n.q.w>0.5 || k.tangent.w<=0.0) return;
    // Each slot re-emits in staggered cycles for as long as its knot lives: knots are born at the head, far off
    // view, so sparks tied to the knot's birth died before the ribbon carried them into the hall.
    uint key=uint(floor(mod(k.q.x+uSparkClock.y,1000.0)*256.0+0.5));
    uint base=mixBits(key*747796405U+uint(slot)*2891336453U+uint(owner)*104729U);
    float cycle=uSpark.y*1.6;
    float since=uSparkClock.x-k.q.x+unit(base)*cycle;
    if(since<0.0) return;
    float generation=floor(since/cycle);
    float age=since-generation*cycle;
    if(age>uSpark.y) return;
    uint seed=mixBits(base+uint(generation)*2246822519U);
    float r1=unit(seed), r2=unit(seed+1U), r3=unit(seed+2U), r4=unit(seed+3U), r5=unit(seed+4U), r6=unit(seed+5U);
    if(r1>k.tangent.w) return;                       // the knot's sparkle is the share of its slots alive
    Knot before=knotAt(owner,max(index-1,0)), after=knotAt(owner,min(index+2,count-1));
    bool joinsBefore=index>0 && before.q.z>0.5 && k.q.w<0.5;
    bool joinsAfter=index+2<count && after.q.z>0.5 && after.q.w<0.5;
    guardBefore=joinsBefore?before:k;
    guardAfter=joinsAfter?after:n;
    vec3 a=joinsBefore?before.p.xyz:2.0*k.p.xyz-n.p.xyz;
    vec3 d=joinsAfter?after.p.xyz:2.0*n.p.xyz-k.p.xyz;
    vec3 lo,hi,normal,tangent;
    if(!station(a,k.p.xyz,n.p.xyz,d,k,n,paths[owner].extra.x,r3,lo,hi,normal,tangent)) return;
    vec3 birth=surfacePoint(lo,hi,normal,r2);
    vec3 direction=normalize(vec3(r4-0.5,r5-0.5+uSpark.w,r6-0.5)+vec3(1e-4));
    vec3 position=birth+direction*uSpark.z*(0.25+r1)*age/(1.0+0.5*age);
    if(uFloorContact.z>0.0) position.y=floorEased(position.y);
    float life=age/uSpark.y;
    float fade=smoothstep(0.0,0.06,life)*(1.0-smoothstep(0.55,1.0,life));
    float twinkle=0.55+0.45*sin(6.2831853*(uSparkLook.w*age+r2));
    vBright=uSparkLook.z*fade*twinkle*(0.35+0.65*r5)*mix(k.side.w,n.side.w,r3);
    gl_PointSize=mix(uSparkLook.x,uSparkLook.y,r6*r6);
    vec4 tint=mix(k.tint,n.tint,r3);
    vColour=mix(mix(paths[owner].colourA.rgb,paths[owner].colourB.rgb,r2),tint.rgb,clamp(tint.a,0.0,1.0));
    vWorld=position;
    gl_Position=uMvp*vec4(position,1.0);
}
""").replace('MAX_KNOTS', str(MAX_PATH_SAMPLES))

# Free strands: liquid filaments that peel off a sheet and flow with its history. Each is attached at its first knot
# and leaves the surface along a smooth curve (offset zero and flat at the attachment, growing with distance along
# it and with the knot's age), wobbles gently, tapers to a free tip and carries droplet beads. Every term is a smooth
# function of (stray coordinate, knot age), so no setting can kink one. The knot's sparkle gates how many live.
RIBBON_STRAY_VERTEX = ("#version 460 core\n" + _RIBBON_SURFACE_GLSL + """
struct Ribbon { vec4 meta; vec4 extra; vec4 colourA; vec4 colourB; Knot knots[MAX_KNOTS]; };
layout(std430, binding=0) readonly buffer Paths { Ribbon paths[]; };
uniform mat4 uMvp;
uniform vec2 uViewport;
uniform vec4 uStray;       // strays per knot, length (knots), reach (world units), chance
uniform vec4 uStrayLook;   // width (px), light, beads per stray, peel time (s)
uniform vec2 uStrayClock;  // local now (s), absolute coordinate origin mod 1000 (stable identity)
uniform float uStrayAdmission;
out vec3 vWorld;
out float vAlong;
out float vAcross;
out float vBright;
out float vSeed;
flat out vec3 vColour;
const int STRAY_SEGMENTS=24;
int ringStart, ringCapacity, ringCount;
Knot knotAt(int owner, int i) { return paths[owner].knots[(ringStart+i)%ringCapacity]; }
uint mixBits(uint x) { x^=x>>16; x*=0x7feb352dU; x^=x>>15; x*=0x846ca68bU; x^=x>>16; return x; }
float unit(uint x) { return float(mixBits(x)&0xffffffU)/16777216.0; }
// The sheet point at fractional knot coordinate kp and across fraction, with its across and normal directions.
bool sheetAt(int owner, float kp, float across, out vec3 p, out vec3 side, out vec3 normal) {
    int segment=int(floor(kp));
    float u=kp-float(segment);
    if(segment<0 || segment>=ringCount-1) return false;
    Knot left=knotAt(owner,segment), right=knotAt(owner,segment+1);
    if(left.q.z<0.5 || right.q.z<0.5 || right.q.w>0.5) return false;
    Knot before=knotAt(owner,max(segment-1,0)), after=knotAt(owner,min(segment+2,ringCount-1));
    bool joinsBefore=segment>0 && before.q.z>0.5 && left.q.w<0.5;
    bool joinsAfter=segment+2<ringCount && after.q.z>0.5 && after.q.w<0.5;
    guardBefore=joinsBefore?before:left;
    guardAfter=joinsAfter?after:right;
    vec3 a=joinsBefore?before.p.xyz:2.0*left.p.xyz-right.p.xyz;
    vec3 d=joinsAfter?after.p.xyz:2.0*right.p.xyz-left.p.xyz;
    vec3 lo,hi,t;
    if(!station(a,left.p.xyz,right.p.xyz,d,left,right,paths[owner].extra.x,u,lo,hi,normal,t)) return false;
    p=surfacePoint(lo,hi,normal,across);
    side=normalize(hi-lo);
    return true;
}
vec3 strayPoint(vec3 p, vec3 side, vec3 normal, float s, float peel, float theta, float wobble) {
    float leave=s*s*(3.0-2.0*s);  // zero and flat at the attachment
    // The leaving direction turns along the stray (a curl, like a splash leaving the crest), smoothly in s.
    float curl=theta+(wobble-0.5)*4.0*s;
    vec3 away=normalize(normal*cos(curl)+side*sin(curl));
    vec3 q=p+away*uStray.z*peel*leave+side*uStray.z*0.25*peel*leave*sin(6.2831853*(1.2*s+wobble));
    return floorContact(q);
}
void main() {
    int owner=gl_InstanceID;
    ringCapacity=clamp(int(paths[owner].extra.z),1,MAX_KNOTS);
    ringStart=clamp(int(paths[owner].extra.y),0,ringCapacity-1);
    ringCount=clamp(int(paths[owner].meta.x),0,ringCapacity);
    int perKnot=max(int(uStray.x),1);
    int stray=gl_VertexID/(6*STRAY_SEGMENTS), corner=gl_VertexID%6, segment=(gl_VertexID/6)%STRAY_SEGMENTS;
    int index=stray/perKnot, slot=stray%perKnot;
    gl_Position=vec4(2.0,2.0,2.0,1.0); vWorld=vec3(0.0); vAlong=0.0; vAcross=0.0; vBright=0.0; vSeed=0.0;
    vColour=vec3(0.0);
    float length_=max(uStray.y,1.0);
    if(index+int(ceil(length_))>=ringCount) return;
    Knot k=knotAt(owner,index);
    if(k.q.z<0.5) return;
    uint key=uint(floor(mod(k.q.x+uStrayClock.y,1000.0)*256.0+0.5));
    uint seed=mixBits(key*747796405U+uint(slot)*2891336453U+uint(owner)*104729U+17U);
    float r1=unit(seed), r2=unit(seed+1U), r3=unit(seed+2U), r4=unit(seed+3U), r5=unit(seed+4U);
    float gate=k.tangent.w*uStray.w;
    float admission=uStrayAdmission>0.0?smoothstep(r1,r1+uStrayAdmission,gate):step(r1,gate);
    if(admission<=0.0) return;
    bool next=corner==1 || corner>=4;
    bool outer=corner==2 || corner==3 || corner==5;
    float s=float(segment+(next?1:0))/float(STRAY_SEGMENTS);
    float ds=1.0/float(STRAY_SEGMENTS);
    // Strays grow out of a rim line, exactly on it (the bow is zero at the edges), so each emerges from a line
    // instead of starting in mid-air.
    float across=r2<0.5?0.0:1.0;
    float theta=(r4-0.5)*2.4+(r2<0.5?-0.6:0.6);
    float age=max(uStrayClock.x-k.q.x,0.0);
    float peel=admission*(0.35+0.65*r5)*(1.0-exp(-age/max(uStrayLook.w,1e-3)));
    float kp=float(index)+s*length_;
    float kq=float(index)+min(s+ds,1.0)*length_;
    float kr=float(index)+max(s-ds,0.0)*length_;
    vec3 p,side,normal,pq,sq,nq,pr,sr,nr;
    if(!sheetAt(owner,kp,across,p,side,normal) || !sheetAt(owner,kq,across,pq,sq,nq)
       || !sheetAt(owner,kr,across,pr,sr,nr)) return;
    vec3 here=strayPoint(p,side,normal,s,peel,theta,r3);
    vec3 ahead=strayPoint(pq,sq,nq,min(s+ds,1.0),peel,theta,r3);
    vec3 behind=strayPoint(pr,sr,nr,max(s-ds,0.0),peel,theta,r3);
    vec4 c=uMvp*vec4(here,1.0), ca=uMvp*vec4(ahead,1.0), cb=uMvp*vec4(behind,1.0);
    vec2 half_=0.5*uViewport;
    vec2 along=(ca.xy/ca.w-cb.xy/cb.w)*half_;
    if(dot(along,along)<1e-10) return;
    vec2 perp=normalize(vec2(-along.y,along.x));
    // Quad twice the line's width: the droplet beads fill it, the line's core stays narrow.
    float width=admission*uStrayLook.x*(1.0-0.6*s);
    vec2 offset=perp*(outer?1.0:-1.0)*width;
    gl_Position=vec4((c.xy/c.w*half_+offset)/half_*c.w,c.z,c.w);
    vWorld=here;
    vAlong=s;
    vAcross=outer?1.0:-1.0;
    vSeed=r4;
    float tip=1.0-smoothstep(0.75,1.0,s);
    // From nothing on the rim to full as it peels away: no visible start.
    float attach=smoothstep(0.0,0.25,s);
    vBright=admission*uStrayLook.y*k.side.w*tip*attach*(0.5+0.5*r5);
    vec3 own=mix(paths[owner].colourA.rgb,paths[owner].colourB.rgb,across);
    vColour=mix(own,k.tint.rgb,clamp(k.tint.a,0.0,1.0));
}
""").replace('MAX_KNOTS', str(MAX_PATH_SAMPLES))

RIBBON_STRAY_FRAGMENT = ("#version 460 core\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\n"
                         "in vec3 vWorld;\nin float vAlong;\nin float vAcross;\nin float vBright;\nin float vSeed;\n"
                         "flat in vec3 vColour;\nuniform vec3 uMistOrigin;\nuniform vec4 uStrayLook;\n"
                         "uniform vec2 uStrayGlow;  // soft halo around the filament, share sent to the bloom\n"
                         + MIST_GLSL + RIBBON_GRADE_GLSL + """
void main() {
    float a=vAcross*vAcross;
    float line=exp(-a*9.0);                                   // the filament: narrow core in a quad twice its width
    float along=fract(vAlong*uStrayLook.z+vSeed)-0.5;         // droplets strung along it, round over the full quad
    // Droplets gather toward the free tip, where the liquid breaks up.
    float bead=exp(-(along*along*uStrayLook.z*uStrayLook.z*0.35+a)*3.5)*smoothstep(0.3,0.9,vAlong);
    float halo=uStrayGlow.x*exp(-a*1.2)*(1.0-0.5*vAlong);  // a fuzzy splash around the clean line
    float light=(line+halo+1.6*bead)*vBright;
    if(light<=1e-4) discard;
    vec3 colour=graded(vColour,vWorld.x+uMistOrigin.x)*light*mistTransmittance(vWorld+uMistOrigin);
    FragColor=vec4(colour,dot(colour,vec3(0.2126,0.7152,0.0722))*(vWorld.y+uMistOrigin.y));  // as the light pass
    Emission=vec4(colour,dot(colour,vec3(0.2126,0.7152,0.0722)))*uStrayGlow.y;
}
""")


RIBBON_SPARK_FRAGMENT = ("#version 460 core\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\n"
                         "in vec3 vWorld;\nin float vBright;\nflat in vec3 vColour;\nuniform vec3 uMistOrigin;\n"
                         "uniform float uSparkWhite;\n" + MIST_GLSL + RIBBON_GRADE_GLSL + """
void main() {
    vec2 c=gl_PointCoord*2.0-1.0;
    float d2=dot(c,c);
    if(d2>1.0) discard;
    float core=exp(-d2*4.0)*(1.0-d2);
    vec3 light=mix(graded(vColour,vWorld.x+uMistOrigin.x),vec3(1.0),uSparkWhite)*core*vBright
               *mistTransmittance(vWorld+uMistOrigin);
    FragColor=vec4(light,dot(light,vec3(0.2126,0.7152,0.0722))*(vWorld.y+uMistOrigin.y));  // as the light pass
    Emission=vec4(light,dot(light,vec3(0.2126,0.7152,0.0722)));
}
""")

RIBBON_FRAGMENT = """#version 460 core
in vec3 vWorld;
in float vPhase;
flat in vec4 vColour;
uniform int uDiagnostic;
out vec4 FragColor;
void main() {
    vec3 colour=vColour.rgb;
    if(uDiagnostic==1) {
        vec3 n=cross(dFdx(vWorld),dFdy(vWorld));
        if(dot(n,n)<1e-20) discard;
        n=normalize(n)*(gl_FrontFacing?1.0:-1.0);
        colour=n*0.5+0.5;
    } else if(uDiagnostic==2) colour=vec3(fract(vPhase));
    FragColor=vec4(colour,vColour.a);
}
"""

RIBBON_STRAND_COORDINATE_GLSL = """
// A monotone stretch of the material coordinate: gather at one edge and fan at the other, without folding or
// creating/destroying strand identities. An additive sine warp could reverse its derivative at large strengths.
float ribbonStrandCoordinate(float across,float phase,float strength,float frequency,float jitter) {
    float stretch=exp(clamp(4.0*strength*sin(6.2831853*phase*frequency),-4.0,4.0));
    float warped=across/max(across+(1.0-across)*stretch,1e-6);
    return warped+jitter*sin(6.2831853*warped*3.0+1.3)/(6.2831853*3.0);
}
"""

# Shared by the body and light passes; every input is packet-local (the owner rebases eye/view with the MVP).
_RIBBON_MATERIAL_GLSL = """
in vec3 vWorld;
in vec3 vNormal;
in float vPhase;
in float vAcross;
in float vEmission;
in float vLocal;
in float vCoverage;
in float vExpanded;
in float vFaceScale;
flat in vec4 vColour;
flat in vec4 vColourB;
in vec4 vTint;
uniform vec4 uViewZ;        // local -> view-space z (row 2 of the rebased view matrix)
uniform vec3 uEye;          // local eye (Perspective)
uniform vec3 uForward;      // view direction (Orthographic; directions are unchanged by rebasing)
uniform int uOrthographic;
uniform vec4 uRim;          // half-width (across units), light, path-length cap, minimum on-screen width (px)
uniform vec4 uStrands;      // count across the width, half-width (strand spacing units), light, warp
uniform vec4 uBody;         // alpha, tint, strand intensity variation, warp frequency (per phase unit)
uniform vec4 uFill;         // emissive sheet light, its centre level (edges are 1), rim glow width (across), rim glow light
uniform vec4 uGlint;        // glints per strand per phase unit, chance, light, radius (strand units)
uniform vec4 uTone;         // strand whiteness, rim whiteness, strand spacing jitter, glint minimum radius (px)
uniform vec4 uAge;          // local now, fade-in, maximum age, fade-out (seconds); fades off when both are zero
uniform vec3 uMistOrigin;   // packet-local -> mist world translation (packet origin plus the caller's frame)
uniform vec2 uGlow;         // share of the light sent to the bloom (local glow), white-hot share of the brightest strands
""" + RIBBON_GRADE_GLSL + MIST_GLSL + RIBBON_STRAND_COORDINATE_GLSL + """

// Integral of the periodic pulse, then exact box filtering over the pixel footprint. The old single-line
// approximation faded at 0.35 spacings/pixel and erased still-resolved filaments into a solid sheet.
float strandIntegral(float x, float halfWidth) {
    return floor(x)*2.0*halfWidth+clamp(fract(x)-(0.5-halfWidth),0.0,2.0*halfWidth);
}
float strandCoverage(float x, float halfWidth, float w) {
    float filtered=(strandIntegral(x+0.5*w,halfWidth)-strandIntegral(x-0.5*w,halfWidth))/max(w,1e-4);
    return mix(filtered,2.0*halfWidth,smoothstep(0.65,1.2,w));
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
    vec3 view=uOrthographic==1?normalize(uForward):normalize(vWorld-uEye);
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
"""

RIBBON_BODY_FRAGMENT = ("#version 460 core\n" + SCENE_OIT_GLSL + "layout(location=2) out vec4 Emission;\n"
                        + _RIBBON_MATERIAL_GLSL + """
void main() {
    float alpha=clamp((1.0-pow(1.0-uBody.x,pathLength()))*clamp(vCoverage,0.0,1.0)*ageFade()
                      *mistTransmittance(vWorld+uMistOrigin)*clamp(vColour.a,0.0,1.0),0.0,0.95);
    sceneTransparent(ribbonColour()*uBody.y*alpha,alpha,viewDepth());
    Emission=vec4(0.0);
}
""")

RIBBON_LIGHT_FRAGMENT = ("#version 460 core\nlayout(location=0) out vec4 FragColor;\n"
                         "layout(location=1) out vec4 Emission;\n" + _RIBBON_MATERIAL_GLSL + """
void main() {
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
        if(cellHash(k,j)<uGlint.y && abs(determinant)>1e-10) {
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
    // The body glows in its saturated colour; strands and rims carry the near-white light (the mock's look).
    vec3 colour=ribbonColour();
    // The brightest strands burn white-hot at their cores; the rest keep their colour.
    float hot=clamp(uTone.x+uGlow.y*smoothstep(0.9,1.9,strength),0.0,1.0);
    vec3 sheet=colour*fill+mix(colour,vec3(1.0),hot)*strands*uStrands.z
               +mix(colour,vec3(1.0),0.6)*glints*uGlint.z;
    vec3 boundary=colour*rimGlow+mix(colour,vec3(1.0),uTone.y)*rims*uRim.y;
    vec3 light=(sheet*pathLength()*clamp(vCoverage,0.0,1.0)+boundary)*max(vEmission,0.0)*ageFade()
                *mistTransmittance(vWorld+uMistOrigin);
    // Alpha: luminance-weighted world height, for contact-hardened reflections. Scene targets keep their
    // alpha (blend ZERO, ONE); a reflection target accumulates it (ONE, ONE).
    FragColor=vec4(light,dot(light,vec3(0.2126,0.7152,0.0722))*(vWorld.y+uMistOrigin.y));
    Emission=vec4(light,dot(light,vec3(0.2126,0.7152,0.0722)))*uGlow.x;
}
""")
