"""Independent oriented-strip expansion; no mode, simulation or camera owner."""
from core.ribbon_geometry import MAX_PATH_SAMPLES

RIBBON_VERTEX = """#version 460 core
struct Knot { vec4 p; vec4 q; vec4 tangent; vec4 side; };
struct Ribbon { vec4 meta; vec4 extra; vec4 colourA; vec4 colourB; Knot knots[MAX_KNOTS]; };
layout(std430, binding=0) readonly buffer Paths { Ribbon paths[]; };
uniform mat4 uMvp;
out vec3 vWorld;
out float vPhase;
flat out vec4 vColour;
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
bool station(vec3 a, vec3 b, vec3 c, vec3 d, Knot left, Knot right, float originTwist, float u,
             out vec3 lo, out vec3 hi) {
    vec3 localA=a-b, localC=c-b, localD=d-b;
    vec3 at=b+curve(localA,vec3(0),localC,localD,u);
    vec3 tangent=curve(localA,vec3(0),localC,localD,min(1.0,u+0.001))
                -curve(localA,vec3(0),localC,localD,max(0.0,u-0.001));
    if(dot(tangent,tangent)<1e-18) return false;
    tangent=normalize(tangent);
    vec3 side=mix(left.side.xyz,right.side.xyz,u);
    side-=tangent*dot(side,tangent);
    if(dot(side,side)<1e-12) return false;
    side=normalize(side);
    float twist=originTwist+mix(left.q.y,right.q.y,u);
    side=cos(twist)*side+sin(twist)*cross(tangent,side);
    float width=clamp(mix(left.p.w,right.p.w,u),min(left.p.w,right.p.w),max(left.p.w,right.p.w));
    lo=at-width*side; hi=at+width*side;
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
    gl_Position=vec4(2,2,2,1); vWorld=vec3(0); vPhase=0; vColour=vec4(0);
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
    if(segment>0 && (before.q.z<0.5 || left.q.w>0.5)) a=2*b-c;
    if(segment+2<count && (after.q.z<0.5 || after.q.w>0.5)) d=2*c-b;
    float u0=float(interval%divisions)/float(divisions), u1=float(interval%divisions+1)/float(divisions);
    vec3 l0,r0,l1,r1;
    // Both endpoints must admit before ANY corner is emitted; partial rejection
    // would stretch the surviving triangle towards the offscreen sentinel.
    if(!station(a,b,c,d,left,right,paths[owner].extra.x,u0,l0,r0) ||
       !station(a,b,c,d,left,right,paths[owner].extra.x,u1,l1,r1)) return;
    vWorld=next?(signWidth<0?l1:r1):(signWidth<0?l0:r0);
    vPhase=paths[owner].meta.z+mix(left.q.x,right.q.x,u)/paths[owner].meta.w;
    vColour=paths[owner].colourA;
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
