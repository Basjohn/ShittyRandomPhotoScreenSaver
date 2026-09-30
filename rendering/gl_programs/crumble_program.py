"""Closed fracture solids and instanced debris shaders for Crumble."""

from __future__ import annotations

from rendering.gl_programs.scene3d import SCENE3D_GLSL, scene3d_ghost_fragment, scene3d_motion_fragment, scene3d_motion_vertex


def _chip_vertices() -> tuple[float, ...]:
    # Deliberately asymmetric base chip.  Per-instance anisotropic scaling in
    # DEBRIS_VERTEX mutates it further, so debris reads as irregular fragments
    # rather than a repeated box/diamond primitive.
    points = (
        (0.05, -0.04, 0.56),
        (0.62, 0.06, 0.03),
        (0.10, 0.43, -0.04),
        (-0.47, 0.02, 0.08),
        (-0.06, -0.52, -0.02),
        (-0.09, 0.04, -0.48),
    )
    faces = (
        (0, 1, 2),
        (0, 2, 3),
        (0, 3, 4),
        (0, 4, 1),
        (5, 2, 1),
        (5, 3, 2),
        (5, 4, 3),
        (5, 1, 4),
    )
    values = []
    for face in faces:
        for index in face:
            point = points[index]
            length = max(0.001, sum(v * v for v in point) ** 0.5)
            values.extend((*point, *(v / length for v in point)))
    return tuple(values)


CRUMBLE_CHIP_VERTICES = _chip_vertices()

CRUMBLE_VERTEX = """#version 460 core
layout(location=0) in vec2 aUv; layout(location=1) in vec2 aCenter; layout(location=2) in float aZ; layout(location=3) in vec3 aNormal; layout(location=4) in float aInset; layout(location=5) in float aFace; layout(location=6) in float aVariation; layout(location=7) in float aRadius; layout(location=8) in vec3 aCrack;
// Per-chunk motion drawn once per run on the CPU (crumble_dynamics): release
// progress, sideways drift and this chunk's row in the motion table; tumble
// axis. The table holds the baked collision response (offset, extra tumble)
// at uMotionFrames keyframes over [0, .98]; it is all zero without collisions.
layout(location=9) in vec4 aRelease; layout(location=10) in vec3 aAxis;
uniform mat4 uMatrix; uniform vec2 uItemSize; uniform float uProgress,uDepth,uThickness,uMotionFrames; uniform sampler2D uMotion;
out vec2 vUv,vCrack; out vec3 vNormal,vRock; out float vFace,vMotion; flat out float vCrackPhase;
vec3 rotateAxis(vec3 p,vec3 a,float t){float c=cos(t),s=sin(t);return p*c+cross(a,p)*s+a*dot(a,p)*(1.-c);}
void main(){float aspect=uItemSize.x/uItemSize.y,begin=aRelease.x,raw=clamp((uProgress-begin)/max(.001,.98-begin),0.,1.),local=raw*raw*(3.-2.*raw),impact=smoothstep(0.,.12,local); float frame=clamp(uProgress/.98,0.,1.)*(uMotionFrames-1.); int k0=int(frame),k1=min(k0+1,int(uMotionFrames)-1),row=int(aRelease.z+.5); vec4 motion=mix(texelFetch(uMotion,ivec2(k0,row),0),texelFetch(uMotion,ivec2(k1,row),0),frame-float(k0)); float angle=local*(4.5+5.*aVariation)+motion.w; vec2 localUv=aCenter+(aUv-aCenter)*(1.-.075*aInset*uThickness*impact),delta=vec2((localUv.x-aCenter.x)*aspect,aCenter.y-localUv.y); float thickness=aRadius*.72*uThickness*impact; vec3 axis=normalize(aAxis); vec3 p=rotateAxis(vec3(delta,aZ*thickness),axis,angle); vec2 center=vec2((aCenter.x-.5)*aspect,.5-aCenter.y); p.x+=center.x+aRelease.y*local*local*(.25+.25*uDepth); p.y+=center.y-local*local*(3.1+1.9*aVariation); p.z+=uDepth*(.38*sin(local*3.14159265)-.28*local*local); p+=motion.xyz; float w=max(1.55,3.15-p.z); vec2 uv=vec2(p.x/aspect,-p.y)*3.15/w+.5; vec4 q=uMatrix*vec4(uv*uItemSize,0.,1.); q*=w; q.z=clamp(-p.z/5.,-.9,.9)*q.w; gl_Position=q; vUv=localUv;vNormal=rotateAxis(normalize(aNormal),axis,angle);vFace=aFace;vMotion=impact;vCrack=aCrack.xy;vCrackPhase=aCrack.z;vRock=vec3(delta,aZ*thickness)/max(aRadius,.001);}"""

CRUMBLE_FRAGMENT = """#version 460 core
in vec2 vUv,vCrack;
flat in float vCrackPhase;
in vec3 vNormal,vRock;
in float vFace,vMotion;
out vec4 FragColor;
uniform sampler2D uOldTex;
uniform float uProgress,uSeed;
""" + SCENE3D_GLSL + """
// Stone lattice values from the exact integer hash (R-94: identical on every GPU).
float hash3(vec3 p){uvec3 u=uvec3(ivec3(floor(p))+1048576);return sceneRandom(u.x^(u.y*0x27d4eb2du)^(u.z*0x165667b1u),0u,7u);}
float stone(vec3 p){
    vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(mix(hash3(i),hash3(i+vec3(1,0,0)),f.x),
                   mix(hash3(i+vec3(0,1,0)),hash3(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(hash3(i+vec3(0,0,1)),hash3(i+vec3(1,0,1)),f.x),
                   mix(hash3(i+vec3(0,1,1)),hash3(i+vec3(1,1,1)),f.x),f.y),f.z);
}
void main(){
    vec3 source=texture(uOldTex,vUv).rgb,n=normalize(vNormal),light=normalize(vec3(-.38,.64,.68));
    float diffuse=.25+.75*max(dot(n,light),0.);
    float side=step(.5,vFace),bevel=1.-step(.2,abs(vFace-1.));
    float grain=.62*stone(vRock*19.)+.38*stone(vRock*53.);
    vec3 broken=mix(vec3(.23,.215,.19),source*.35+vec3(.14),.45);
    broken*=(.45+.65*diffuse+.12*bevel)*(.65+.65*grain);
    vec3 body=mix(source,mix(source*(.74+.26*diffuse),broken,side),vMotion);
    // A visible crack stage precedes all gravity/tumble. The stroke crawls
    // along the actual cell border, then widens into a dark recessed fissure.
    float variation=sceneRandom(floatBitsToUint(vCrackPhase),1u,uint(uSeed+.5));
    float start=.025+.105*variation;
    float progress=clamp((uProgress-start)/.12,0.,1.);
    float stroke=smoothstep(-.025,.025,progress-vCrack.y)*smoothstep(0.,.018,uProgress-start);
    float opening=smoothstep(start,start+.13,uProgress);
    float width=mix(.00045,.0030,opening)*(.84+.16*sin(vCrack.y*51.+vCrackPhase));
    float aa=max(fwidth(vCrack.x),.00015);
    float groove=1.-smoothstep(width,width+aa,vCrack.x);
    float lip=(1.-smoothstep(width+aa,width+aa+.0012,vCrack.x))-groove;
    body=mix(body,body*.055,groove*stroke*(1.-side));
    body+=vec3(.30,.27,.21)*lip*stroke*(1.-side);
    FragColor=vec4(body,1.);
}"""

DEBRIS_VERTEX = """#version 460 core
layout(location=0) in vec3 aPosition;layout(location=1) in vec3 aNormal;layout(location=2) in vec2 aEdge;layout(location=3) in vec2 aParent;layout(location=4) in vec2 aMeta;layout(location=5) in vec2 aRelease;uniform mat4 uMatrix;uniform vec2 uItemSize;uniform float uProgress,uDepth,uDebris;out vec3 vNormal;out vec3 vRock;out float vMotion;
vec3 rotateAxis(vec3 p,vec3 a,float t){float c=cos(t),s=sin(t);return p*c+cross(a,p)*s+a*dot(a,p)*(1.-c);}
// A chip breaks off when its parent chunk is released (aRelease.x), which a
// collision may bring forward.
void main(){float begin=aRelease.x,raw=clamp((uProgress-begin)/max(.001,.98-begin),0.,1.);if(raw<=0.){gl_Position=vec4(2.,2.,2.,1.);vMotion=0.;return;}float local=raw*raw*(3.-2.*raw),aspect=uItemSize.x/uItemSize.y;float sizeSeed=fract(aMeta.y*23.17+aMeta.x*11.83),shapeSeed=fract(aMeta.y*41.71+aMeta.x*7.29);vec3 shape=vec3(.52+.70*sizeSeed,.46+.76*shapeSeed,.42+.62*fract(sizeSeed*5.31+shapeSeed*3.17));float scale=(.006+.014*aMeta.y)*uDebris*smoothstep(0.,.09,local);vec3 axis=normalize(vec3(fract(aMeta.x*17.)*2.-1.,fract(aMeta.y*29.)*2.-1.,.55));vec3 p=rotateAxis(aPosition*shape*scale,axis,local*(6.+7.*aMeta.x));vec2 c=vec2((aEdge.x-.5)*aspect,.5-aEdge.y),spray=normalize(vec2(aEdge.x-.5,.5-aEdge.y)+vec2(.0001));p.xy+=c+vec2(spray.x*aspect,-spray.y)*local*(.35+.55*aMeta.x);p.y-=local*local*(2.7+1.8*aMeta.y);p.z+=uDepth*(.26+local*.24)*(1.-local*.35)*local;float w=max(1.55,3.15-p.z);vec2 uv=vec2(p.x/aspect,-p.y)*3.15/w+.5;vec4 q=uMatrix*vec4(uv*uItemSize,0.,1.);q*=w;q.z=clamp(-p.z/5.,-.9,.9)*q.w;gl_Position=q;vNormal=rotateAxis(normalize(aNormal/shape),axis,local*(6.+7.*aMeta.x));vRock=aPosition*shape;vMotion=local;}"""

DEBRIS_FRAGMENT = """#version 460 core
""" + SCENE3D_GLSL + """
// Fine rock grain: an exact integer hash on a 1/300 lattice of the chip surface.
float sceneRandomRock(vec3 p){uvec3 u=uvec3(ivec3(floor(p*300.))+1048576);return sceneRandom(u.x^(u.y*0x27d4eb2du)^(u.z*0x165667b1u),2u,11u);}
in vec3 vNormal;in vec3 vRock;in float vMotion;out vec4 FragColor;void main(){float d=.16+.84*max(dot(normalize(vNormal),normalize(vec3(-.4,.62,.7))),0.),grain=sceneRandomRock(vRock);vec3 rock=mix(vec3(.09,.065,.042),vec3(.31,.22,.14),d);rock*=.82+.22*grain;FragColor=vec4(rock*(.72+.28*vMotion),1.);}"""

# With motion blur: the same shaders, also writing each point's screen motion.
CRUMBLE_MOTION_VERTEX = scene3d_motion_vertex(CRUMBLE_VERTEX)
CRUMBLE_MOTION_FRAGMENT = scene3d_motion_fragment(CRUMBLE_FRAGMENT)
DEBRIS_MOTION_VERTEX = scene3d_motion_vertex(DEBRIS_VERTEX)
DEBRIS_MOTION_FRAGMENT = scene3d_motion_fragment(DEBRIS_FRAGMENT)
# With motion trails: the same chunks and chips as flat ghost silhouettes.
CRUMBLE_GHOST_FRAGMENT = scene3d_ghost_fragment(CRUMBLE_MOTION_FRAGMENT)
DEBRIS_GHOST_FRAGMENT = scene3d_ghost_fragment(DEBRIS_MOTION_FRAGMENT)
