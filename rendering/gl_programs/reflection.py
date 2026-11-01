"""Planar floor reflection: the mirror maths and the receiver's sampling (S3D-5). Pure; no GL state.

A flat reflector at height ``h`` is rendered by drawing the scene through the camera mirrored in the plane
(``mirror_view``) into ``rendering.quick.scene3d.reflection.PlanarReflection``. For a flat mirror the reflected image
then lines up with the receiver pixel for pixel, from any pose and in Orthographic or Perspective, so the receiver
samples it at its own screen position (``PLANAR_REFLECTION_GLSL``). Preconditions: everything drawn into the
reflection lies above the plane (no clip plane is applied), and the receiver itself is not drawn into it.
"""
import numpy as np


def mirror_matrix(plane_y: float) -> np.ndarray:
    """World -> mirrored world across the horizontal plane y = plane_y (4x4, row-major numpy)."""
    mirror = np.diag((1., -1., 1., 1.))
    mirror[1, 3] = 2.*float(plane_y)
    return mirror


def mirror_view(view: np.ndarray, plane_y: float) -> np.ndarray:
    """The view of the mirrored camera: draw the unmirrored scene with this view to get its reflection.
    Triangle winding flips; reflection passes must not cull faces by winding."""
    return np.asarray(view, float) @ mirror_matrix(plane_y)


# Receiver side. screenUv is gl_FragCoord.xy over the receiver's viewport; the reflection target covers the same view
# at its own resolution. Roughness defines an elongated texture footprint. The reflection owner's
# anisotropic sampler integrates that footprint continuously instead of stamping seven separated highlight copies.
PLANAR_REFLECTION_GLSL = """
uniform sampler2D uReflection;
uniform vec4 uReflectionLook;   // streak half-length (uv), min/max optical mip, Gaussian sigma (receiver pixels)
vec3 planarReflection(vec2 screenUv, vec2 offset, float roughness) {
    float lod=mix(uReflectionLook.y,uReflectionLook.z,roughness);
    float streak=uReflectionLook.x*roughness;
    vec2 size=vec2(textureSize(uReflection,0));
    vec2 uv=screenUv+offset;
    // Respect the receiver's pixel footprint: supersampled reflections must downsample. Differentiate only
    // screenUv: offset may come from a derivative-derived normal (second derivatives are undefined in GLSL).
    float pixelSpan=max(length(dFdx(screenUv)*size),length(dFdy(screenUv)*size));
    float sigma=max(uReflectionLook.w,0.0);
    float span=max(exp2(lod),pixelSpan);
    vec2 dx=vec2(span/size.x,0.0), dy=vec2(0.0,max(span/size.y,2.0*streak));
    if(sigma<=0.0) return textureGrad(uReflection,clamp(uv,vec2(0),vec2(1)),dx,dy).rgb;
    vec2 pixelUv=vec2(abs(dFdx(screenUv.x)),abs(dFdy(screenUv.y)));
    // Pair adjacent samples of a discrete nine-tap Gaussian through bilinear filtering. Scaling sparse taps
    // apart and forcing a coarser mip gave NPOT receivers unequal X/Y spread. Blur must not change the mip.
    float s=max(sigma,0.05);
    vec4 w=exp(-vec4(0.5,2.0,4.5,8.0)/(s*s));
    float nearWeight=w.x+w.y, farWeight=w.z+w.w;
    float nearOffset=(w.x+2.0*w.y)/max(nearWeight,1e-30);
    float farOffset=(3.0*w.z+4.0*w.w)/max(farWeight,1e-30);
    float total=1.0+2.0*(nearWeight+farWeight);
    float weights[5]=float[5](farWeight,nearWeight,1.0,nearWeight,farWeight);
    float offsets[5]=float[5](-farOffset,-nearOffset,0.0,nearOffset,farOffset);
    vec3 colour=vec3(0.0);
    for(int y=0;y<5;y++) for(int x=0;x<5;x++) {
        vec2 tap=clamp(uv+vec2(offsets[x],offsets[y])*pixelUv,vec2(0),vec2(1));
        colour+=weights[x]*weights[y]*textureGrad(uReflection,tap,dx,dy).rgb;
    }
    return colour/(total*total);
}
"""
