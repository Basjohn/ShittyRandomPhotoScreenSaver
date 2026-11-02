"""Analytic event-owned ribbon sparks; birth records are authored once on the logical clock."""
from rendering.gl_programs.mist import MIST_GLSL
from rendering.gl_programs.ribbon import RIBBON_GRADE_GLSL

VERTEX="""#version 460 core
layout(location=0) in vec2 aPosition;
struct Burst { vec4 p; vec4 velocity; vec4 colour; vec4 look; };
layout(std430,binding=1) readonly buffer Bursts { Burst particles[]; };
uniform mat4 uMvp;
uniform vec2 uViewport;
uniform float uNow;
out vec2 vUv;
out vec3 vWorld;
flat out vec3 vColour;
flat out float vLight;
void main() {
    Burst b=particles[gl_InstanceID];
    gl_Position=vec4(2.0,2.0,2.0,1.0); vUv=vec2(0);vWorld=vec3(0);vColour=vec3(0);vLight=0.0;
    float age=uNow-b.p.w, life=b.velocity.w;
    if(life<=0.0 || age<0.0 || age>=life) return;
    vec3 world=b.p.xyz+b.velocity.xyz*age/(1.0+0.5*age);
    world.y=max(0.03,world.y);
    vec4 clip=uMvp*vec4(world,1.0);
    if(clip.w<=1e-6) return;
    vUv=aPosition*2.0-1.0;vWorld=world;
    clip.xy+=vUv*b.colour.w/uViewport*clip.w;
    gl_Position=clip;
    vColour=mix(b.colour.rgb,vec3(1.0),b.look.y);
    vLight=b.look.x*smoothstep(0.0,0.08,age)*smoothstep(0.0,0.25,life-age)
           *(0.8+0.2*sin(age*10.0+b.look.z*6.2831853));
}
"""

FRAGMENT="""#version 460 core
in vec2 vUv;
in vec3 vWorld;
flat in vec3 vColour;
flat in float vLight;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
"""+MIST_GLSL+RIBBON_GRADE_GLSL+"""
void main() {
    float r=dot(vUv,vUv);
    if(r>1.0) discard;
    vec3 light=graded(vColour,vWorld.x)*vLight*exp(-4.0*r)*mistTransmittance(vWorld);
    FragColor=vec4(light,0.0);
    Emission=vec4(light,dot(light,vec3(0.2126,0.7152,0.0722)));
}
"""
