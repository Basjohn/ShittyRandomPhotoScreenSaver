
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

  // the draw's first vertex (N5.4)
struct Ribbon { vec4 meta; vec4 extra; vec4 colourA; vec4 colourB; Knot knots[256]; };
layout(std430, binding=0) readonly buffer Paths { Ribbon paths[]; };


       // strays per knot, length (knots), reach (world units), chance
   // width (px), light, beads per stray, peel time (s)
  // local now (s), absolute coordinate origin mod 1000 (stable identity)



struct StrandBirth { vec4 timing; vec4 shape; vec4 finish; vec4 life; };
layout(std430,binding=1) readonly buffer StrandBirths { StrandBirth strandBirths[]; };
vec4 cohortStray,cohortLook;
layout(location = 0) flat out vec4 vCohortLook;
layout(location = 1) flat out vec2 vCohortGlow;
layout(location = 2) flat out float vCohortRemaining;

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

layout(location = 3) out vec3 vWorld;
layout(location = 4) out float vAlong;
layout(location = 5) out float vAcross;
layout(location = 6) out float vBright;
layout(location = 7) out float vSeed;
layout(location = 8) flat out vec3 vColour;
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
    vec3 q=p+away*cohortStray.z*peel*leave+side*cohortStray.z*0.25*peel*leave*sin(6.2831853*(1.2*s+wobble));
    return floorContact(q);
}
void main() {
    int owner=srpssInstanceIndex;
    ringCapacity=clamp(int(paths[owner].extra.z),1,256);
    ringStart=clamp(int(paths[owner].extra.y),0,ringCapacity-1);
    ringCount=clamp(int(paths[owner].meta.x),0,ringCapacity);
    int perKnot=max(int(uStray.x),1);
    int vertexId=srpssVertexIndex+uVertexBase;   // the draw counts from vertex 0 (N5.4), its first vertex a member
    int stray=vertexId/(6*STRAY_SEGMENTS), corner=vertexId%6, segment=(vertexId/6)%STRAY_SEGMENTS;
    int index=stray/perKnot, slot=stray%perKnot;
    gl_Position=vec4(2.0,2.0,2.0,1.0); vWorld=vec3(0.0); vAlong=0.0; vAcross=0.0; vBright=0.0; vSeed=0.0;
    vColour=vec3(0.0);
    StrandBirth record_=strandBirths[owner*256+(ringStart+index)%ringCapacity];
    vec4 birth=record_.timing;
    float cohortAge=uStrayBirthNow-birth.y;
    if(birth.x<=0.0 || cohortAge<0.0) return;
    vCohortRemaining=strandRemaining(uStrayBirthNow-record_.life.w,record_.life);
    if(vCohortRemaining<=0.0) return;
    float sincePulse=max(uStrayBirthNow-birth.z,0.0);
    float pulse=clamp((birth.w+(1.0-birth.w)*1.3*(1.0-exp(-sincePulse/0.025)))
        *exp(-sincePulse/0.35),0.0,1.0);
    cohortStray=vec4(8.0,record_.shape.x*(1.0+uStrayPulse.x*pulse),record_.shape.y,1.0);
    cohortLook=vec4(record_.shape.z,record_.shape.w*(1.0+uStrayPulse.y*pulse),record_.finish.x,record_.finish.y);
    vCohortLook=cohortLook;vCohortGlow=record_.finish.zw;
    float length_=max(cohortStray.y,1.0);
    length_=min(length_,max(0.0,float(ringCount-1-index)-1e-4));if(length_<=0.0) return;
    Knot k=knotAt(owner,index);
    if(k.q.z<0.5) return;
    uint key=uint(floor(mod(k.q.x+uStrayClock.y,1000.0)*256.0+0.5));
    uint seed=mixBits(key*747796405U+uint(slot)*2891336453U+uint(owner)*104729U+17U);
    float r1=unit(seed), r2=unit(seed+1U), r3=unit(seed+2U), r4=unit(seed+3U), r5=unit(seed+4U);
    float gate=birth.x;
    float admission=uStrayAdmission>0.0?smoothstep(r1,r1+uStrayAdmission*max(gate,1e-4),gate):step(r1,gate);
    admission*=smoothstep(0.0,0.2,cohortAge);
    if(admission<=0.0) return;
    bool next=corner==1 || corner>=4;
    bool outer=corner==2 || corner==3 || corner==5;
    float s=float(segment+(next?1:0))/float(STRAY_SEGMENTS);
    float ds=1.0/float(STRAY_SEGMENTS);
    // Strays grow out of a rim line, exactly on it (the bow is zero at the edges), so each emerges from a line
    // instead of starting in mid-air.
    float across=r2<0.5?0.0:1.0;
    float theta=(r4-0.5)*2.4+(r2<0.5?-0.6:0.6);
    float age=cohortAge;
    float peel=admission*(0.35+0.65*r5)*(1.0-exp(-age/max(cohortLook.w,1e-3)));
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
    float width=admission*cohortLook.x*(1.0-0.6*s);
    vec2 offset=perp*(outer?1.0:-1.0)*width;
    gl_Position=vec4((c.xy/c.w*half_+offset)/half_*c.w,c.z,c.w);
    vWorld=here;
    vAlong=s;
    vAcross=outer?1.0:-1.0;
    vSeed=r4;
    float tip=1.0-smoothstep(0.75,1.0,s);
    // From nothing on the rim to full as it peels away: no visible start.
    float attach=smoothstep(0.0,0.25,s);
    vBright=admission*cohortLook.y*(0.8+0.4*max(k.side.w,0.0)/(1.0+max(k.side.w,0.0)))*tip*attach*(0.5+0.5*r5);
    vec3 own=mix(paths[owner].colourA.rgb,paths[owner].colourB.rgb,across);
    vColour=mix(own,k.tint.rgb,clamp(k.tint.a,0.0,1.0));
}
