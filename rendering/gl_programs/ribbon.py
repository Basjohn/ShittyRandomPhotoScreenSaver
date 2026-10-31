"""Independent oriented-strip expansion and its filament material; no mode, simulation or camera owner.

Three fragment programs share one vertex stage:

- ``RIBBON_FRAGMENT``: diagnostics (flat colour, face normals, strand phase).
- ``RIBBON_BODY_FRAGMENT``: the faint translucent sheet, written inside ``SceneTarget.transparent_writes``
  through the shared weighted-blended OIT (order-independent, depth-tested, no depth writes).
- ``RIBBON_LIGHT_FRAGMENT``: rims, longitudinal filament strands and fold glow, added to colour (location 0)
  and to the overlay's emission (location 1) after the OIT resolve. Addition is order-independent, and
  crossings sum in HDR until the target's single tone map turns them white-hot.

The material knows widths, strands and light, never music: callers feed per-knot emission (``side.w``) and
per-ribbon colours, and choose the knobs. Strands and rims are box-filtered over the pixel footprint and fade
to their average density once sub-pixel, so slow motion cannot make them crawl or sparkle.
"""
from core.ribbon_geometry import MAX_PATH_SAMPLES
from rendering.quick.scene3d.target import SCENE_OIT_GLSL

RIBBON_VERTEX = """#version 460 core
struct Knot { vec4 p; vec4 q; vec4 tangent; vec4 side; };
struct Ribbon { vec4 meta; vec4 extra; vec4 colourA; vec4 colourB; Knot knots[MAX_KNOTS]; };
layout(std430, binding=0) readonly buffer Paths { Ribbon paths[]; };
uniform mat4 uMvp;
out vec3 vWorld;
out vec3 vNormal;
out float vPhase;
out float vAcross;
out float vEmission;
flat out vec4 vColour;
flat out vec4 vColourB;
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
// Monotone cubic Hermite (Fritsch-Carlson limited) on the uniform knot lattice: C1 through every knot, never
// outside [min(b,c), max(b,c)], so widths stay positive and no knot leaves a corner (linear did: lumps).
float monotone(float a, float b, float c, float d, float u) {
    float delta=c-b;
    float m1=0.5*(c-a), m2=0.5*(d-b);
    if(abs(delta)<=1e-12*max(abs(b),abs(c))) { m1=0.0; m2=0.0; }
    else {
        m1=m1*delta<=0.0?0.0:sign(m1)*min(abs(m1),3.0*abs(delta));
        m2=m2*delta<=0.0?0.0:sign(m2)*min(abs(m2),3.0*abs(delta));
    }
    float u2=u*u, u3=u2*u;
    return (2.0*u3-3.0*u2+1.0)*b+(u3-2.0*u2+u)*m1+(3.0*u2-2.0*u3)*c+(u3-u2)*m2;
}
vec3 hermite(vec3 a, vec3 b, vec3 c, vec3 d, float u) {
    float u2=u*u, u3=u2*u;
    return (2.0*u3-3.0*u2+1.0)*b+(u3-2.0*u2+u)*0.5*(c-a)+(3.0*u2-2.0*u3)*c+(u3-u2)*0.5*(d-b);
}
// Guard knots outside the drawable run repeat the endpoint: zero slope there, never a value from across a break.
Knot guardBefore, guardAfter;
bool station(vec3 a, vec3 b, vec3 c, vec3 d, Knot left, Knot right, float originTwist, float u,
             out vec3 lo, out vec3 hi, out vec3 normal) {
    vec3 localA=a-b, localC=c-b, localD=d-b;
    vec3 at=b+curve(localA,vec3(0),localC,localD,u);
    vec3 tangent=curve(localA,vec3(0),localC,localD,min(1.0,u+0.001))
                -curve(localA,vec3(0),localC,localD,max(0.0,u-0.001));
    if(dot(tangent,tangent)<1e-18) return false;
    tangent=normalize(tangent);
    vec3 side=hermite(guardBefore.side.xyz,left.side.xyz,right.side.xyz,guardAfter.side.xyz,u);
    side-=tangent*dot(side,tangent);
    if(dot(side,side)<1e-12) return false;
    side=normalize(side);
    float twist=originTwist+monotone(guardBefore.q.y,left.q.y,right.q.y,guardAfter.q.y,u);
    side=cos(twist)*side+sin(twist)*cross(tangent,side);
    float width=clamp(monotone(guardBefore.p.w,left.p.w,right.p.w,guardAfter.p.w,u),
                      min(left.p.w,right.p.w),max(left.p.w,right.p.w));
    lo=at-width*side; hi=at+width*side;
    normal=cross(tangent,side);
    return !all(equal(lo,hi));
}
// Chronological knot i lives in ring slot (start+i)%capacity; a stateless packet has start 0.
int ringStart, ringCapacity;
Knot knotAt(int owner, int i) { return paths[owner].knots[(ringStart+i)%ringCapacity]; }
void main() {
    int owner=gl_InstanceID;
    ringCapacity=clamp(int(paths[owner].extra.z),1,MAX_KNOTS);
    ringStart=clamp(int(paths[owner].extra.y),0,ringCapacity-1);
    int count=clamp(int(paths[owner].meta.x),0,ringCapacity);
    int divisions=clamp(int(paths[owner].meta.y),1,8);
    int interval=gl_VertexID/6, corner=gl_VertexID%6;
    int segment=interval/divisions;
    gl_Position=vec4(2,2,2,1); vWorld=vec3(0); vNormal=vec3(0,0,1); vPhase=0; vAcross=0; vEmission=0;
    vColour=vec4(0); vColourB=vec4(0);
    if(segment>=count-1) return;
    Knot left=knotAt(owner,segment), right=knotAt(owner,segment+1);
    // q.w marks a knot that starts a new strip (ring break/reseed): nothing joins into it.
    if(left.q.z<0.5 || right.q.z<0.5 || right.q.w>0.5 || all(equal(left.p.xyz,right.p.xyz))) return;
    // Independent triangles: L0 L1 R0, R0 L1 R1. No bridge across invalid intervals.
    bool next=corner==1 || corner>=4;
    float signWidth=(corner==2 || corner==3 || corner==5)?1.0:-1.0;
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
    vec3 l0,r0,l1,r1,n0,n1;
    // Both endpoints must admit before ANY corner is emitted; partial rejection
    // would stretch the surviving triangle towards the offscreen sentinel.
    if(!station(a,b,c,d,left,right,paths[owner].extra.x,u0,l0,r0,n0) ||
       !station(a,b,c,d,left,right,paths[owner].extra.x,u1,l1,r1,n1)) return;
    vWorld=next?(signWidth<0?l1:r1):(signWidth<0?l0:r0);
    vNormal=next?n1:n0;
    vAcross=signWidth<0?0.0:1.0;
    vEmission=monotone(guardBefore.side.w,left.side.w,right.side.w,guardAfter.side.w,u);
    vPhase=paths[owner].meta.z+mix(left.q.x,right.q.x,u)/paths[owner].meta.w;
    vColour=paths[owner].colourA;
    vColourB=paths[owner].colourB;
    gl_Position=uMvp*vec4(vWorld,1);
}
""".replace('MAX_KNOTS', str(MAX_PATH_SAMPLES))

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

# Shared by the body and light passes; every input is packet-local (the owner rebases eye/view with the MVP).
_RIBBON_MATERIAL_GLSL = """
in vec3 vWorld;
in vec3 vNormal;
in float vPhase;
in float vAcross;
in float vEmission;
flat in vec4 vColour;
flat in vec4 vColourB;
uniform vec4 uViewZ;        // local -> view-space z (row 2 of the rebased view matrix)
uniform vec3 uEye;          // local eye (Perspective)
uniform vec3 uForward;      // view direction (Orthographic; directions are unchanged by rebasing)
uniform int uOrthographic;
uniform vec4 uStrands;      // count across the width, half-width (strand spacing units), light, warp
uniform vec4 uRim;          // half-width (across units), light, fold boost, fold power
uniform vec4 uBody;         // alpha, tint, fold alpha boost, warp frequency (per phase unit)
uniform vec4 uFill;         // emissive sheet light, its centre level (edges are 1), rim glow width (across), rim glow light
uniform vec4 uGlint;        // glints per strand per phase unit, chance, light, radius (strand units)

// Box filter of the unit-spaced lines |x - (k + 0.5)| <= halfWidth over a pixel footprint w (strand units).
// Once w nears a strand spacing the pattern is sub-pixel: it fades to its mean density instead of aliasing.
float strandCoverage(float x, float halfWidth, float w) {
    float d=abs(fract(x)-0.5);
    float overlap=max(0.0,min(d+0.5*w,halfWidth)-max(d-0.5*w,-halfWidth));
    float filtered=overlap/max(w,1e-4);
    return mix(filtered,2.0*halfWidth,smoothstep(0.35,0.9,w));
}
float strandHash(float k) { return fract(sin(k*12.9898+3.1)*43758.5453); }
float cellHash(float k, float j) { return fract(sin(k*12.9898+j*78.233+1.7)*43758.5453); }
// One-sided rim of half-width h (across units) at an edge, box-filtered over w.
float rimCoverage(float edgeDistance, float h, float w) {
    return clamp((h-edgeDistance)/max(w,1e-4)+0.5,0.0,1.0)*min(1.0,2.0*h/max(w,1e-4)+0.25);
}
float viewDepth() { return -dot(uViewZ,vec4(vWorld,1.0)); }
float grazing() {
    vec3 n=normalize(vNormal);
    vec3 view=uOrthographic==1?normalize(uForward):normalize(vWorld-uEye);
    return 1.0-abs(dot(n,view));
}
// MSAA shades a covered sample at the pixel centre, which on an edge-on sliver lies far outside the triangle:
// interpolants extrapolate there (across reached -50 and exp() overflowed into the bloom). Clamp before use.
float acrossClamped() { return clamp(vAcross,0.0,1.0); }
vec3 ribbonColour() { return mix(vColour.rgb,vColourB.rgb,acrossClamped()); }
"""

RIBBON_BODY_FRAGMENT = ("#version 460 core\n" + SCENE_OIT_GLSL + "layout(location=2) out vec4 Emission;\n"
                        + _RIBBON_MATERIAL_GLSL + """
void main() {
    float fold=pow(grazing(),max(uRim.w,1e-3));
    float alpha=clamp(uBody.x*(1.0+uBody.z*fold),0.0,0.95);
    sceneTransparent(ribbonColour()*uBody.y*alpha,alpha,viewDepth());
    Emission=vec4(0.0);
}
""")

RIBBON_LIGHT_FRAGMENT = ("#version 460 core\nlayout(location=0) out vec4 FragColor;\n"
                         "layout(location=1) out vec4 Emission;\n" + _RIBBON_MATERIAL_GLSL + """
void main() {
    float across=acrossClamped();
    // Strands spread and gather along the path: a warp fixed to the absolute path phase, zero at both edges.
    float warp=uStrands.w*sin(6.2831853*vPhase*uBody.w+across*3.0)*across*(1.0-across)*4.0;
    float x=(across+warp)*uStrands.x;
    float w=max(fwidth(x),1e-4);
    float strands=strandCoverage(x,uStrands.y,w)*(0.55+0.45*strandHash(floor(x)));
    float wa=max(fwidth(across),1e-5);
    float rims=rimCoverage(across,uRim.x,wa)+rimCoverage(1.0-across,uRim.x,wa);
    float fold=pow(grazing(),max(uRim.w,1e-3));
    // The sheet itself glows (both references): a fill brightening toward the edges, a wide rim glow beside
    // the crisp rim line, then strands and their glints on top.
    float edge=min(across,1.0-across);
    float fill=uFill.x*mix(uFill.y,1.0,pow(1.0-2.0*edge,2.0));
    float rimGlow=uFill.w*exp(-edge/max(uFill.z,1e-4));
    float glints=0.0;
    if(uGlint.x>0.0 && uGlint.z>0.0) {
        // Sparse bright points riding strands, fixed to the absolute path phase: they travel with the history.
        float k=floor(x);
        float along=vPhase*uGlint.x+strandHash(k)*7.0;
        float j=floor(along);
        if(cellHash(k,j)<uGlint.y) {
            float alongPx=(fract(along)-0.5)/max(fwidth(along),1e-4);
            float acrossPx=(fract(x)-0.5)/max(w,1e-4);
            float radiusPx=max(uGlint.w/max(w,1e-4),0.75);
            float r2=(alongPx*alongPx+acrossPx*acrossPx)/(radiusPx*radiusPx);
            glints=exp(-3.0*r2)*min(1.0,radiusPx*radiusPx);
        }
    }
    vec3 light=ribbonColour()*(fill+rimGlow+strands*uStrands.z+rims*uRim.y)*(1.0+uRim.z*fold);
    light=(light+mix(ribbonColour(),vec3(1.0),0.6)*glints*uGlint.z)*max(vEmission,0.0);
    FragColor=vec4(light,0.0);
    Emission=vec4(light,dot(light,vec3(0.2126,0.7152,0.0722)));
}
""")
