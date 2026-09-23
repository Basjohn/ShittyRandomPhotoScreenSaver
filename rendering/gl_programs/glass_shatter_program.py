"""Perspective motion and independently authored optical material for glass prisms.

Collisions and in-flight re-shattering are solved per run at build time
(``rendering/quick/transitions/glass_dynamics.py``); each piece carries a
visibility window and a velocity/spin kick that start at its event time. With
no event the kick is zero and the path is exactly the plain shatter.
"""

GLASS_VERTEX = """#version 410 core
layout(location=0) in vec2 aUv;
layout(location=1) in vec2 aCenter;
layout(location=2) in float aZ;
layout(location=3) in vec3 aNormal;
layout(location=4) in float aInset;
layout(location=5) in float aFace;
layout(location=6) in float aVariation;
layout(location=7) in float aRadius;
layout(location=8) in vec2 aLife;    // visible from .x until .y (split parents/children)
layout(location=9) in vec4 aKick;    // velocity kick xyz from time .w
layout(location=10) in vec4 aSpin;   // extra spin axis xyz and rate .w from aKick.w
layout(location=11) in vec2 aPivot;  // stage-1 spin pivot
layout(location=12) in vec4 aKick2;  // second crack: kick xyz from time .w
layout(location=13) in vec4 aSpin2;  // second crack: spin axis xyz, rate .w
layout(location=14) in vec2 aPivot2; // second crack: this piece's own centre
uniform mat4 uMatrix;
uniform vec2 uItemSize;
uniform vec2 uDirection;
uniform int uRadial;
uniform float uProgress;
uniform float uDepth;
uniform float uThickness;
out vec2 vUv;
noperspective out vec2 vScreenUv;
out vec3 vNormal;
out float vMotion;
out vec3 vView;
out float vThickness;
flat out float vFace;

vec3 rotateAxis(vec3 p, vec3 axis, float angle) {
    float c=cos(angle), s=sin(angle);
    return p*c + cross(axis,p)*s + axis*dot(axis,p)*(1.0-c);
}
void main() {
    if(uProgress<aLife.x||uProgress>=aLife.y) {
        // Not this piece's turn (a shard before or after it cracks apart).
        gl_Position=vec4(2.0,2.0,2.0,1.0);
        vScreenUv=vec2(0.0);vUv=vec2(0.0);vNormal=vec3(0.0,0.0,1.0);
        vView=vec3(0.0,0.0,1.0);vMotion=0.0;vThickness=0.0;vFace=0.0;
        return;
    }
    float aspect=uItemSize.x/uItemSize.y;
    vec2 center=vec2((aCenter.x-.5)*aspect,.5-aCenter.y);
    vec2 direction=vec2(uDirection.x,-uDirection.y);
    float rank;
    if(uRadial==1) {
        direction=normalize(center+vec2(.00001));
        rank=length(center)/length(vec2(aspect*.5,.5));
    } else {
        rank=.5+dot(aCenter-.5,uDirection)/(abs(uDirection.x)+abs(uDirection.y));
    }
    float delay=.34*clamp(rank,0.0,1.0)+.025*aVariation;
    float local=clamp((uProgress-delay)/(.98-delay),0.0,1.0);
    float impact=smoothstep(0.0,.10,local);
    // Out-of-plane tumble is the dominant motion, not a spinning paper mask.
    vec3 axis=normalize(vec3(cos(aVariation*37.0),sin(aVariation*29.0),.18*sin(aVariation*17.0)));
    float angle=local*(3.8+4.5*aVariation)*(.5+.65*uDepth);
    float inset=1.0-.07*aInset*uThickness*impact;
    vec2 localUv=aCenter+(aUv-aCenter)*inset;
    vec2 delta=vec2((localUv.x-aCenter.x)*aspect,aCenter.y-localUv.y);
    float thickness=aRadius*.65*uThickness*impact;
    vec3 position=rotateAxis(vec3(delta,aZ*thickness),axis,angle);
    vec3 normal=rotateAxis(normalize(aNormal),axis,angle);
    // Build-time events: from aKick.w the piece takes a velocity kick and spins
    // about its pivot; a second crack adds another stage from aKick2.w. Time
    // freezes with the path at the exit.
    float tau=max(min(uProgress,.98)-aKick.w,0.0);
    float tau2=max(min(uProgress,.98)-aKick2.w,0.0);
    vec3 pivot=vec3(0.0);
    if(tau>0.0) {
        vec2 pivotDelta=vec2((aPivot.x-aCenter.x)*aspect,aCenter.y-aPivot.y);
        pivot=rotateAxis(vec3(pivotDelta,-.5*thickness),axis,angle);
        float spin=aSpin.w*tau;
        position=pivot+rotateAxis(position-pivot,aSpin.xyz,spin);
        normal=rotateAxis(normal,aSpin.xyz,spin);
    }
    if(tau2>0.0) {
        vec2 pivotDelta2=vec2((aPivot2.x-aCenter.x)*aspect,aCenter.y-aPivot2.y);
        vec3 pivot2=rotateAxis(vec3(pivotDelta2,-.5*thickness),axis,angle);
        if(tau>0.0) pivot2=pivot+rotateAxis(pivot2-pivot,aSpin.xyz,aSpin.w*tau);
        float spin2=aSpin2.w*tau2;
        position=pivot2+rotateAxis(position-pivot2,aSpin2.xyz,spin2);
        normal=rotateAxis(normal,aSpin2.xyz,spin2);
    }
    direction=normalize(direction+vec2(-direction.y,direction.x)*(.35*(aVariation-.5)));
    // Ray/expanded-rectangle exit accounts for the entire rotating prism and
    // the largest possible receding projection. No scale/fade retirement.
    vec2 extent=(vec2(aspect*.5,.5)+vec2(aRadius*2.0+.10))*(1.0+.6*uDepth/3.0);
    vec2 distanceToEdge=(sign(direction)*extent-center)/
                         (sign(direction)*max(abs(direction),vec2(.00001)));
    if(abs(direction.x)<.00001) distanceToEdge.x=1e5;
    if(abs(direction.y)<.00001) distanceToEdge.y=1e5;
    float exitDistance=min(distanceToEdge.x,distanceToEdge.y);
    float travel=.12*local+.88*local*local;
    position.xy+=center+direction*exitDistance*travel;
    position.y-=.16*sin(3.14159265*local)*local;
    position.z+=uDepth*(.56*sin(3.14159265*local)-.6*local*local);
    position+=aKick.xyz*tau+aKick2.xyz*tau2;
    float w=3.0-position.z;
    vec2 uv=vec2(position.x/aspect,-position.y)*3.0/w+.5;
    vec4 projected=uMatrix*vec4(uv*uItemSize,0,1);
    projected*=w;
    projected.z=clamp(-position.z/5.0,-.9,.9)*projected.w;
    gl_Position=projected;
    vScreenUv=uv;
    vUv=localUv;
    vNormal=normal;
    vView=vec3(-position.xy,3.0-position.z);
    vMotion=impact;
    vThickness=thickness;
    vFace=aFace;
}
"""

GLASS_FRAGMENT = """#version 410 core
in vec2 vUv;
noperspective in vec2 vScreenUv;
in vec3 vNormal;
in float vMotion;
in vec3 vView;
in float vThickness;
flat in float vFace;
out vec4 FragColor;
uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform vec2 uItemSize;
uniform float uTransparency;
uniform float uRefraction;
uniform float uDispersion;
uniform float uSheen;
void main() {
    vec3 n=normalize(vNormal);
    vec3 view=normalize(vView);
    if(dot(n,view)<0.0) n=-n;
    float facing=clamp(dot(n,view),0.,1.);
    float fresnel=.035+.965*pow(1.0-facing,5.0);
    float wall=step(.5,vFace)*(1.0-step(2.5,vFace));
    float bevel=1.0-step(.2,abs(vFace-1.0));
    vec2 distortion=vec2(n.x/(uItemSize.x/uItemSize.y),-n.y)*
                    (vThickness+.015)*uRefraction/(.35+facing);
    // Destination is sampled where the fragment actually lies on screen.
    // This makes transmission move independently of the printed image face.
    vec2 uv=clamp(vScreenUv+distortion,0.,1.);
    vec2 chromatic=distortion*uDispersion*.55;
    vec3 transmitted=vec3(texture(uNewTex,clamp(uv+chromatic,0.,1.)).r,
                           texture(uNewTex,uv).g,
                           texture(uNewTex,clamp(uv-chromatic,0.,1.)).b);
    vec3 source=texture(uOldTex,vUv).rgb;
    vec3 tint=mix(vec3(.80,.94,1.),sqrt(max(source,vec3(.02))),.25);
    transmitted*=mix(vec3(1),tint,vMotion*wall*.45);
    float transmission=uTransparency*vMotion*(1.0-.75*fresnel);
    vec3 body=mix(source,transmitted,transmission);
    vec3 light=normalize(vec3(-.45,.75,1.2));
    float diffuse=.38+.62*abs(dot(n,light));
    body*=mix(1.,diffuse,vMotion*wall*.70);
    // Broad reflected softbox and a fine second glint travel across bevels as
    // they rotate. Independent sheen zero removes all authored reflection.
    vec3 reflected=reflect(-view,n);
    float softbox=pow(max(0.,dot(reflected,normalize(vec3(-.5,.8,1.)))),28.);
    float strip=pow(max(0.,1.0-abs(reflected.y-.38)),90.)*
                smoothstep(-.9,-.2,reflected.x);
    vec3 reflection=vec3(.64,.83,1.)*(fresnel*.42+softbox*.55+strip*.45);
    reflection+=vec3(.86,.96,1.)*bevel*(.12+.65*pow(facing,.5));
    body+=reflection*uSheen*vMotion;
    FragColor=vec4(body,1.0);
}
"""
