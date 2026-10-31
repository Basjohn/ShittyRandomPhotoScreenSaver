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
# at its own (lower) resolution. Roughness widens a vertical streak and selects a blurrier mip: wet rough floors
# stretch reflections toward the viewer, which an isotropic blur cannot do.
PLANAR_REFLECTION_GLSL = """
uniform sampler2D uReflection;
uniform vec4 uReflectionLook;   // streak length (uv) at roughness 1, mip at roughness 0, mip at roughness 1, unused
vec3 planarReflection(vec2 screenUv, vec2 offset, float roughness) {
    float lod=mix(uReflectionLook.y,uReflectionLook.z,roughness);
    float streak=uReflectionLook.x*roughness;
    vec3 sum=vec3(0.0);
    float weights=0.0;
    for(int i=-3;i<=3;i++) {
        float w=1.0-abs(float(i))/4.0;
        sum+=w*textureLod(uReflection,clamp(screenUv+offset+vec2(0.0,float(i)*streak/3.0),vec2(0.0),vec2(1.0)),lod).rgb;
        weights+=w;
    }
    return sum/weights;
}
"""
