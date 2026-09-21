"""Closed fracture solids and instanced debris shaders for Crumble."""

from __future__ import annotations


def _chip_vertices() -> tuple[float, ...]:
    points = (
        (0.0, 0.0, 0.62),
        (0.58, 0.0, 0.0),
        (0.0, 0.48, 0.0),
        (-0.58, 0.0, 0.0),
        (0.0, -0.48, 0.0),
        (0.0, 0.0, -0.62),
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

CRUMBLE_VERTEX = """#version 410 core
layout(location=0) in vec2 aUv; layout(location=1) in vec2 aCenter; layout(location=2) in float aZ; layout(location=3) in vec3 aNormal; layout(location=4) in float aInset; layout(location=5) in float aFace; layout(location=6) in float aVariation; layout(location=7) in float aRadius;
uniform mat4 uMatrix; uniform vec2 uItemSize; uniform float uProgress,uDepth,uThickness,uSeed,uWeightMode;
out vec2 vUv; out vec3 vNormal,vRock; out float vFace,vMotion;
float hash1(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7))+uSeed)*43758.5453123);}
vec3 rotateAxis(vec3 p,vec3 a,float t){float c=cos(t),s=sin(t);return p*c+cross(a,p)*s+a*dot(a,p)*(1.-c);}
float rank(vec2 c,float v){float m=uWeightMode; if(m==3.)m=hash1(vec2(uSeed,.37))<.34?0.:hash1(vec2(uSeed,.37))<.67?1.:2.; if(m<.5)return c.y; if(m<1.5)return 1.-c.y; if(m<2.5)return mix(c.y,1.-c.y,step(.5,hash1(c+19.))); return v;}
void main(){float aspect=uItemSize.x/uItemSize.y,begin=clamp(.035+clamp(rank(aCenter,aVariation),0.,1.)*.31+(hash1(aCenter)-.5)*.06,0.,.46),raw=clamp((uProgress-begin)/max(.001,.98-begin),0.,1.),local=raw*raw*(3.-2.*raw),impact=smoothstep(0.,.12,local); vec2 localUv=aCenter+(aUv-aCenter)*(1.-.075*aInset*uThickness*impact),delta=vec2((localUv.x-aCenter.x)*aspect,aCenter.y-localUv.y); float thickness=aRadius*.72*uThickness*impact; vec3 axis=normalize(vec3(hash1(aCenter+2.)*2.-1.,hash1(aCenter+5.)*2.-1.,hash1(aCenter+9.)*2.-1.)); vec3 p=rotateAxis(vec3(delta,aZ*thickness),axis,local*(4.5+5.*aVariation)); vec2 center=vec2((aCenter.x-.5)*aspect,.5-aCenter.y); p.x+=center.x+(hash1(aCenter+31.)-.5)*local*local*(.25+.25*uDepth); p.y+=center.y-local*local*(3.1+1.9*aVariation); p.z+=uDepth*(.38*sin(local*3.14159265)-.28*local*local); float w=max(1.55,3.15-p.z); vec2 uv=vec2(p.x/aspect,-p.y)*3.15/w+.5; vec4 q=uMatrix*vec4(uv*uItemSize,0.,1.); q*=w; q.z=clamp(-p.z/5.,-.9,.9)*q.w; gl_Position=q; vUv=localUv;vNormal=rotateAxis(normalize(aNormal),axis,local*(4.5+5.*aVariation));vFace=aFace;vMotion=impact;vRock=vec3(delta,aZ*thickness)/max(aRadius,.001);}"""

CRUMBLE_FRAGMENT = """#version 410 core
in vec2 vUv;
in vec3 vNormal,vRock;
in float vFace,vMotion;
out vec4 FragColor;
uniform sampler2D uOldTex;
float hash3(vec3 p){return fract(sin(dot(p,vec3(127.1,311.7,74.7)))*43758.5453);}
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
    FragColor=vec4(body,1.);
}"""

DEBRIS_VERTEX = """#version 410 core
layout(location=0) in vec3 aPosition;layout(location=1) in vec3 aNormal;layout(location=2) in vec2 aEdge;layout(location=3) in vec2 aParent;layout(location=4) in vec2 aMeta;uniform mat4 uMatrix;uniform vec2 uItemSize;uniform float uProgress,uDepth,uDebris,uSeed,uWeightMode;out vec3 vNormal;out vec3 vRock;out float vMotion;
vec3 rotateAxis(vec3 p,vec3 a,float t){float c=cos(t),s=sin(t);return p*c+cross(a,p)*s+a*dot(a,p)*(1.-c);}
float hash1(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7))+uSeed)*43758.5453123);}
float rank(vec2 c,float v){float m=uWeightMode;if(m==3.)m=hash1(vec2(uSeed,.37))<.34?0.:hash1(vec2(uSeed,.37))<.67?1.:2.;if(m<.5)return c.y;if(m<1.5)return 1.-c.y;if(m<2.5)return mix(c.y,1.-c.y,step(.5,hash1(c+19.)));return v;}
void main(){float begin=clamp(.035+clamp(rank(aParent,aMeta.x),0.,1.)*.31+(hash1(aParent)-.5)*.06,0.,.46),raw=clamp((uProgress-begin)/max(.001,.98-begin),0.,1.);if(raw<=0.){gl_Position=vec4(2.,2.,2.,1.);vMotion=0.;return;}float local=raw*raw*(3.-2.*raw),aspect=uItemSize.x/uItemSize.y,scale=(.012+.026*aMeta.y)*uDebris*smoothstep(0.,.09,local);vec3 axis=normalize(vec3(fract(aMeta.x*17.)*2.-1.,fract(aMeta.y*29.)*2.-1.,.55));vec3 p=rotateAxis(aPosition*scale,axis,local*(6.+7.*aMeta.x));vec2 c=vec2((aEdge.x-.5)*aspect,.5-aEdge.y),spray=normalize(vec2(aEdge.x-.5,.5-aEdge.y)+vec2(.0001));p.xy+=c+vec2(spray.x*aspect,-spray.y)*local*(.35+.55*aMeta.x);p.y-=local*local*(2.7+1.8*aMeta.y);p.z+=uDepth*(.26+local*.24)*(1.-local*.35)*local;float w=max(1.55,3.15-p.z);vec2 uv=vec2(p.x/aspect,-p.y)*3.15/w+.5;vec4 q=uMatrix*vec4(uv*uItemSize,0.,1.);q*=w;q.z=clamp(-p.z/5.,-.9,.9)*q.w;gl_Position=q;vNormal=rotateAxis(aNormal,axis,local*(6.+7.*aMeta.x));vRock=aPosition;vMotion=local;}"""

DEBRIS_FRAGMENT = """#version 410 core
in vec3 vNormal;in vec3 vRock;in float vMotion;out vec4 FragColor;void main(){float d=.16+.84*max(dot(normalize(vNormal),normalize(vec3(-.4,.62,.7))),0.),grain=fract(sin(dot(vRock,vec3(41.3,67.7,17.1)))*43758.5);vec3 rock=mix(vec3(.09,.065,.042),vec3(.31,.22,.14),d);rock*=.82+.22*grain;FragColor=vec4(rock*(.72+.28*vMotion),1.);}"""
