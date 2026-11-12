"""Analytic event-owned ribbon sparks; birth records are authored once on the logical clock."""
from rendering.gl_programs.mist import FOG_TEXTURE_UNIT, MIST_GLSL
from rendering.gl_programs.portable import portable_program
from rendering.gl_programs.ribbon import RIBBON_GRADE_GLSL

# As authored for OpenGL; ``VERTEX`` and ``FRAGMENT`` below are their portable form (N1.6).
_VERTEX="""
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
flat out float vGlow;
flat out float vCore;
void main() {
    Burst b=particles[gl_InstanceID];
    gl_Position=vec4(2.0,2.0,2.0,1.0); vUv=vec2(0);vWorld=vec3(0);vColour=vec3(0);vLight=0.0;vGlow=0.0;vCore=1.0;
    float age=uNow-b.p.w, life=b.velocity.w;
    if(life<=0.0 || age<0.0 || age>=life) return;
    vec3 world=b.p.xyz+b.velocity.xyz*age/(1.0+0.5*age);
    world.y=max(0.03,world.y);
    vec4 clip=uMvp*vec4(world,1.0);
    if(clip.w<=1e-6) return;
    vUv=aPosition*2.0-1.0;vWorld=world;
    vGlow=b.look.w;
    // Gentle finite life: a quick ignition, a bright first third, then a long smooth fade to zero at death.
    float fade=smoothstep(0.0,0.12,age)*(1.0-smoothstep(0.3*life,life,age));
    float extent=b.colour.w*(1.0+4.0*vGlow)*0.5;  // pixel half-extent; raster support mirrors this bound
    // The lit core never collapses below a readable pixel; the remaining quad is the particle's own halo.
    float core=max(0.5*b.colour.w*(0.6+0.4*fade),1.0), reach=max(extent,core);
    vCore=core/reach;
    clip.xy+=vUv*2.0*reach/uViewport*clip.w;
    gl_Position=clip;
    vColour=mix(b.colour.rgb,vec3(1.0),b.look.y);
    vLight=b.look.x*fade*(0.8+0.2*sin(age*10.0+b.look.z*6.2831853));
}
"""

_FRAGMENT="""
in vec2 vUv;
in vec3 vWorld;
flat in vec3 vColour;
flat in float vLight;
flat in float vGlow;
flat in float vCore;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
"""+MIST_GLSL+RIBBON_GRADE_GLSL+"""
void main() {
    float r=dot(vUv,vUv);
    if(r>1.0) discard;
    // Core: a soft disc of the authored size. Halo: a broad, coloured falloff filling the glow extent.
    float core=exp(-2.5*r/(vCore*vCore));
    float halo=0.02*vGlow*exp(-6.0*r)*(1.0-smoothstep(0.5,1.0,r));
    float lightShape=core+halo;
    vec3 light=graded(vColour,vWorld.x)*vLight*lightShape*mistTransmittance(vWorld);
    FragColor=vec4(light,0.0);
    Emission=vec4(light,dot(light,vec3(0.2126,0.7152,0.0722)));
}
"""

# Binding plan: the bursts' storage 1, the mist volume its unit (8), the pass block 18.
VERTEX, (FRAGMENT,), BURSTS_BLOCK = portable_program("#version 460 core" + _VERTEX, ("#version 460 core" + _FRAGMENT,),
                                                     block="RibbonBurstDraw",
                                                     samplers={"uFogVolume": FOG_TEXTURE_UNIT})
