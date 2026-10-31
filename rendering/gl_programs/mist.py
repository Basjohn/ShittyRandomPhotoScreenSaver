"""World-space scene mist: one analytic transmittance every pass of a scene shares (opaque, OIT and additive light).

Mist belongs to the world, not the eye: an Orthographic eye distance is arbitrary and a navigating camera dollies,
so mist by view distance would breathe with the camera. Here clear air fills an ellipse around a centre on the
floor plane (radii along x and z) and the mist thickens beyond it, and more near the floor. Opaque surfaces mix
toward the backdrop colour by ``1 - mistTransmittance``; additive light and translucent coverage are multiplied by it.
With ``uMist.w`` (falloff) zero the function returns 1 and the scene is unchanged.
"""

MIST_GLSL = """
uniform vec4 uMist;        // clear-air centre x, centre z, radius x, radius z (world units)
uniform vec4 uMistShape;   // falloff (radii beyond the edge per e-fold), floor thickening, thickening height, low glow
float mistTransmittance(vec3 world) {
    if(uMistShape.x<=0.0) return 1.0;
    vec2 radii=max(uMist.zw,vec2(1e-3));
    float beyond=max(0.0,length((world.xz-uMist.xy)/radii)-1.0)/uMistShape.x;
    float low=uMistShape.z>0.0?exp(-max(world.y,0.0)/uMistShape.z):0.0;
    return exp(-beyond*beyond*(1.0+uMistShape.y*low));
}
// The mist's own colour: the backdrop, lit where the haze is low and near the edge of the clear air, fading into
// darkness deeper in. (Glow by height alone lit the whole far floor, which an Orthographic view shows as the entire
// upper field.)
vec3 mistColour(vec3 backdrop, vec3 world) {
    vec2 radii=max(uMist.zw,vec2(1e-3));
    float beyond=max(0.0,length((world.xz-uMist.xy)/radii)-1.0)/max(uMistShape.x,1e-3);
    float low=uMistShape.z>0.0?exp(-max(world.y,0.0)/uMistShape.z):0.0;
    return backdrop*(1.0+uMistShape.w*low*exp(-0.6*beyond*beyond));
}
"""


def mist_uniforms(centre_xz=(0., 0.), radii_xz=(30., 3.), falloff=.6, floor_thickening=1.5, thickening_height=1.5,
                  low_glow=0.):
    """Uniform values for MIST_GLSL; falloff 0 turns the mist off."""
    values = (*centre_xz, *radii_xz, falloff, floor_thickening, thickening_height)
    if (any(v != v for v in values) or min(radii_xz) <= 0 or falloff < 0 or floor_thickening < 0 or thickening_height < 0
            or not low_glow >= 0):
        raise ValueError('Mist needs finite positive radii and non-negative shape values')
    return dict(uMist=(*centre_xz, *radii_xz), uMistShape=(falloff, floor_thickening, thickening_height, float(low_glow)))
