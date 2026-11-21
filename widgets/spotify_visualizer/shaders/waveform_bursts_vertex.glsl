
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
layout(std140, binding = 18) uniform RibbonBurstDraw {
    mat4 uMvp;
    vec2 uViewport;
    float uNow;
    vec4 uMist;
    vec4 uMistShape;
    mat4 uFogView;
    vec4 uFogLens;
    vec4 uFogRange;
    vec4 uGradeStops[6];
    vec4 uGrade;
};
layout(location=0) in vec2 aPosition;
struct Burst { vec4 p; vec4 velocity; vec4 colour; vec4 look; };
layout(std430,binding=1) readonly buffer Bursts { Burst particles[]; };



layout(location = 0) out vec2 vUv;
layout(location = 1) out vec3 vWorld;
layout(location = 2) flat out vec3 vColour;
layout(location = 3) flat out float vLight;
layout(location = 4) flat out float vGlow;
layout(location = 5) flat out float vCore;
void main() {
    Burst b=particles[srpssInstanceIndex];
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
