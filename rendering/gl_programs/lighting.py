"""Bounded, unshadowed soft-source irradiance. No resources, simulation or camera owner.

Positions/radii and integrated RGB strengths are caller-supplied in world units. The finite radius regularises
inverse-square irradiance near an extended source. This is a low-frequency lighting approximation, not area-light
visibility or specular reflection. Ninety-six sources fit inside the GL 4.6 minimum fragment-uniform budget.
"""

MAX_SOFT_LIGHTS = 96

SOFT_LIGHT_GLSL = """
uniform int uLightCount;
uniform vec4 uLightPosition[96]; // xyz world centre, squared soft radius
uniform vec3 uLightFlux[96];
vec3 softIrradiance(vec3 position, vec3 normal) {
    vec3 result=vec3(0.0);
    for(int i=0;i<uLightCount;i++) {
        vec3 delta=uLightPosition[i].xyz-position;
        float d2=max(dot(delta,delta)+uLightPosition[i].w,1e-6);
        result+=uLightFlux[i]*max(dot(normal,delta),0.0)/(d2*sqrt(d2));
    }
    return result/3.14159265359;
}
"""
