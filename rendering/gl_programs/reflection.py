"""Planar floor reflection: the mirror maths and the receiver's sampling (S3D-5). Pure; no GL state.

A flat reflector at height ``h`` is rendered by drawing the scene through the camera mirrored in the plane
(``mirror_view``) into ``rendering.quick.scene3d.reflection.PlanarReflection``. For a flat mirror the reflected image
then lines up with the receiver pixel for pixel from any pose, so the receiver
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
# at its own resolution. Roughness defines an elongated texture footprint: wet rough floors stretch reflections
# toward the viewer. Hardware anisotropy integrates at most 16:1, so one footprint longer than that coarsens the
# short axis too and washes neighbouring highlights into one smear; a long streak is split into up to sixteen abutting segments,
# each within the sampler's ratio and Gaussian-weighted along the streak. Separated point taps stamped copies.
# Contact hardening (optional): emitters that write luminance-weighted world height into the reflection's alpha
# (the ribbon light and spark passes do) reflect crisply near the plane and spread with height, as on a wet floor.
PLANAR_REFLECTION_GLSL = """
uniform sampler2D uReflection;
uniform vec4 uReflectionLook;   // streak half-length (uv), min/max optical mip, Gaussian sigma (receiver pixels)
uniform vec4 uReflectionContact; // plane height (world), spread (uv per world unit of height; 0 off), along/across, probe mip
// A discrete nine-tap Gaussian folded into five bilinear taps (offsets in texels of the sampled level), weights sum 1.
void reflectionGaussian(float sigma, out float offsets[5], out float weights[5]) {
    float s=max(sigma,0.05);
    vec4 w=exp(-vec4(0.5,2.0,4.5,8.0)/(s*s));
    float nearWeight=w.x+w.y, farWeight=w.z+w.w;
    float nearOffset=(w.x+2.0*w.y)/max(nearWeight,1e-30);
    float farOffset=(3.0*w.z+4.0*w.w)/max(farWeight,1e-30);
    float total=1.0+2.0*(nearWeight+farWeight);
    offsets=float[5](-farOffset,-nearOffset,0.0,nearOffset,farOffset);
    weights=float[5](farWeight/total,nearWeight/total,1.0/total,nearWeight/total,farWeight/total);
    if(sigma<=0.0) weights=float[5](0.0,0.0,1.0,0.0,0.0);
}
vec3 planarReflection(vec2 screenUv, vec2 offset, float roughness, float streakHalfLength) {
    float lod=mix(uReflectionLook.y,uReflectionLook.z,roughness);
    float streak=streakHalfLength*roughness;
    vec2 size=vec2(textureSize(uReflection,0));
    vec2 uv=screenUv+offset;
    // Respect the receiver's pixel footprint: supersampled reflections must downsample. Differentiate only
    // screenUv: offset may come from a derivative-derived normal (second derivatives are undefined in GLSL).
    float pixelSpan=max(length(dFdx(screenUv)*size),length(dFdy(screenUv)*size));
    float sigma=max(uReflectionLook.w,0.0);
    float span=max(exp2(lod),pixelSpan);
    if(uReflectionContact.y>0.0) {
        // Alpha over luminance at a coarse probe is the light-weighted height of what is reflected here.
        vec4 probe=textureLod(uReflection,clamp(uv,vec2(0),vec2(1)),uReflectionContact.w);
        float luminance=dot(probe.rgb,vec3(0.2126,0.7152,0.0722));
        float height=luminance>1e-6?max(probe.a/luminance-uReflectionContact.x,0.0):0.0;
        float spread=uReflectionContact.y*height;
        span=max(span,spread*size.x);
        streak=max(streak,spread*uReflectionContact.z);
    }
    int segments=int(clamp(ceil(2.0*streak*size.y/(16.0*span)),1.0,16.0));
    vec2 dx=vec2(span/size.x,0.0), dy=vec2(0.0,max(span/size.y,2.0*streak/float(segments)));
    vec2 pixelUv=vec2(abs(dFdx(screenUv.x)),abs(dFdy(screenUv.y)));
    // Gentle Gaussian blur samples the full-resolution footprint: blur must not change the mip (NPOT receivers
    // otherwise spread unequally in X/Y). Along a segmented streak only its across-axis Gaussian remains.
    float across[5], acrossWeights[5], along[16], alongWeights[16];
    reflectionGaussian(sigma,across,acrossWeights);
    int rows=segments;
    if(segments==1) {
        float o[5], w[5];
        reflectionGaussian(sigma,o,w);
        rows=sigma>0.0?5:1;
        for(int i=0;i<5;i++) { along[i]=(sigma>0.0?o[i]:0.0)*pixelUv.y; alongWeights[i]=sigma>0.0?w[i]:1.0; }
    } else {
        float total=0.0;
        // Offset the segments per pixel by up to one spacing: fixed offsets copied a thin highlight into evenly
        // spaced horizontal bands (an unstructured hash; neighbouring pixels average it out).
        uvec2 cell=uvec2(gl_FragCoord.xy);
        uint bits=cell.x*2654435761u^(cell.y*2246822519u+374761393u);
        bits^=bits>>15; bits*=2246822519u; bits^=bits>>13;
        float shift=float(bits&0xffffu)/65536.0-0.5;
        for(int i=0;i<segments;i++) {
            float t=(float(i)+0.5+shift)*2.0/float(segments)-1.0;
            along[i]=t*streak; alongWeights[i]=exp(-2.0*t*t); total+=alongWeights[i];
        }
        for(int i=0;i<segments;i++) alongWeights[i]/=total;
    }
    vec3 colour=vec3(0.0);
    for(int y=0;y<rows;y++) for(int x=0;x<5;x++) {
        if(acrossWeights[x]<=0.0) continue;
        vec2 tap=clamp(uv+vec2(across[x]*pixelUv.x,along[y]),vec2(0),vec2(1));
        colour+=acrossWeights[x]*alongWeights[y]*textureGrad(uReflection,tap,dx,dy).rgb;
    }
    return colour;
}
vec3 planarReflection(vec2 screenUv, vec2 offset, float roughness) {
    return planarReflection(screenUv,offset,roughness,uReflectionLook.x);
}
"""
