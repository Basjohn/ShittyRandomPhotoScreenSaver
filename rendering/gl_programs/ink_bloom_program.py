"""A finite raised pigment sheet: seeded vortices, marbling and a wet meniscus."""

from __future__ import annotations

import math


def ink_surface_vertices(aspect: float) -> tuple[float, ...]:
    """Bounded once-per-aspect grid; the GPU owns all fluid deformation."""
    if not math.isfinite(aspect) or aspect <= 0.0:
        raise ValueError("Ink Bloom requires positive finite aspect")
    columns = max(40, min(160, round(96 * math.sqrt(aspect))))
    rows = max(32, min(144, round(96 / math.sqrt(aspect))))
    vertices = []
    for y in range(rows):
        for x in range(columns):
            a, b, c, d = (
                (x / columns, y / rows),
                ((x + 1) / columns, y / rows),
                ((x + 1) / columns, (y + 1) / rows),
                (x / columns, (y + 1) / rows),
            )
            for point in (a, b, c, a, c, d):
                vertices.extend(point)
    return tuple(vertices)


INK_VOLUME_FIELD = """
uniform float uProgress, uSeed, uDetail, uDepth, uGloss;
uniform vec2 uItemSize;
float hash21(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise2(vec2 p) {
    vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f);
    return mix(mix(hash21(i),hash21(i+vec2(1,0)),f.x),
               mix(hash21(i+vec2(0,1)),hash21(i+vec2(1,1)),f.x),f.y);
}
vec2 pigmentFlow(vec2 p) {
    float seed=mod(uSeed,997.);
    for(int i=0;i<3;++i) {
        float j=float(i), a=seed*.021+j*2.094;
        vec2 centre=vec2(cos(a),sin(a))*(.16+.06*j);
        vec2 q=p-centre;
        float twist=(1.3+1.4*uProgress)*exp(-dot(q,q)*(6.+j*3.))*(i==1?-1.:1.);
        float c=cos(twist), s=sin(twist);
        p=centre+vec2(c*q.x-s*q.y,s*q.x+c*q.y);
    }
    return p;
}
float pigmentDistance(vec2 uv, out vec2 flow) {
    float aspect=uItemSize.x/uItemSize.y, seed=mod(uSeed,997.);
    vec2 p=(uv-.5)*vec2(aspect,1.);
    flow=pigmentFlow(p);
    float angle=atan(flow.y,flow.x), reach=length(vec2(aspect*.5,.5));
    float lobes=.045*sin(angle*7.+seed*.013)+.020*sin(angle*13.-seed*.017);
    float veins=(noise2(flow*7.*uDetail+seed*.03)-.5)*.080+
                (noise2(flow*23.*uDetail-seed*.01)-.5)*.021;
    float radius=(reach+.44)*pow(uProgress,1.04)-.17;
    return length(flow)+lobes+veins-radius;
}
float surfaceLife() { return pow(max(0.,sin(3.14159265*uProgress)),.8); }
float inkHeight(vec2 uv) {
    vec2 flow; float d=pigmentDistance(uv,flow);
    float width=.018+.035*uDepth;
    float circle=clamp(1.+d/width,0.,1.);
    float meniscus=sqrt(max(0.,1.-circle*circle));
    float ribs=.5+.5*sin(flow.x*42.+flow.y*19.+noise2(flow*9.)*8.);
    return (.014+.060*uDepth)*surfaceLife()*meniscus*(.97+.03*ribs);
}
"""

INK_BLOOM_VERTEX_SOURCE = (
    """#version 410 core
layout(location=0) in vec2 aUv;
uniform mat4 uMatrix;
out vec2 vSurfaceUv;
out vec3 vWorld;
out vec3 vNormal;
"""
    + INK_VOLUME_FIELD
    + """
void main() {
    float aspect=uItemSize.x/uItemSize.y;
    vec3 world=vec3((aUv.x-.5)*aspect,.5-aUv.y,inkHeight(aUv));
    float w=3.-world.z;
    vec2 uv=vec2(world.x/aspect,-world.y)*3./w+.5;
    vec4 clip=uMatrix*vec4(uv*uItemSize,0,1); clip*=w;
    clip.z=-world.z/5.*clip.w;
    gl_Position=clip; vSurfaceUv=aUv; vWorld=world;
    float e=.002;
    float dx=(inkHeight(aUv+vec2(e/aspect,0))-inkHeight(aUv-vec2(e/aspect,0)))/(2.*e);
    float dy=(inkHeight(aUv+vec2(0,e))-inkHeight(aUv-vec2(0,e)))/(2.*e);
    vNormal=normalize(vec3(-dx,dy,1.));
}
"""
)

INK_BLOOM_FRAGMENT_SOURCE = (
    """#version 410 core
in vec2 vSurfaceUv;
in vec3 vWorld;
in vec3 vNormal;
out vec4 FragColor;
uniform sampler2D uOldTex,uNewTex;
"""
    + INK_VOLUME_FIELD
    + """
void main() {
    vec2 uv=vSurfaceUv, flow;
    float d=pigmentDistance(uv,flow), life=surfaceLife();
    float aa=max(fwidth(d),.00045), cover=1.-smoothstep(-aa,aa,d);
    vec3 old=texture(uOldTex,uv).rgb;
    if(cover<=0.) {
        // Contact shadow is confined to the raised advancing fluid edge.
        float shadow=exp(-max(d,0.)*85.)*.25*uDepth*life;
        FragColor=vec4(old*(1.-shadow),1.); return;
    }
    float ridge=.5+.5*sin(flow.x*42.+flow.y*19.+noise2(flow*9.)*8.);
    vec2 drift=(flow-(uv-.5)*vec2(uItemSize.x/uItemSize.y,1.));
    vec2 transported=clamp(uv+drift*.075*life+vec2(ridge-.5,0.)*.010*uDepth*life,0.,1.);
    vec3 incoming=texture(uNewTex,transported).rgb;
    vec3 dye=texture(uOldTex,clamp(uv+drift*.17,0.,1.)).rgb;
    float edge=exp(-abs(d)*30.);
    // Pigment streaks are transported by the vortices inside the volume,
    // rather than merely perturbing a reveal threshold at its boundary.
    float marbling=pow(ridge,4.)*life;
    vec3 ink=mix(incoming,dye,(.10+.30*edge)*marbling);
    ink*=1.-(.10+.28*edge)*marbling;
    vec3 n=normalize(vNormal);
    vec3 light=normalize(vec3(-.45,.75,1.1)), view=normalize(vec3(-vWorld.xy,3.-vWorld.z));
    float diffuse=.60+.40*max(0.,dot(n,light));
    float spec=pow(max(0.,dot(n,normalize(light+view))),mix(18.,90.,uGloss));
    float fresnel=pow(1.-max(0.,dot(n,view)),3.);
    ink*=mix(1.,diffuse,life*(.4+.6*uDepth));
    ink+=vec3(.80,.92,1.)*uGloss*life*(spec*(.16+.42*edge)+fresnel*.22);
    FragColor=vec4(mix(old,ink,cover),1.);
}
"""
)
