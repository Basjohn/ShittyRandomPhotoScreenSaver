"""World-space scene mist: one analytic transmittance every pass of a scene shares (opaque, OIT and additive light).

Mist belongs to the world, not the eye: an Orthographic eye distance is arbitrary and a navigating camera dollies,
so mist by view distance would breathe with the camera. Here clear air fills an ellipse around a centre on the
floor plane (radii along x and z) and the mist thickens beyond it, and more near the floor. Opaque surfaces mix
toward the backdrop colour by ``1 - mistTransmittance``; additive light and translucent coverage are multiplied by it.
With ``uMist.w`` (falloff) zero the function returns 1 and the scene is unchanged.

With a bound S3D-7 volume (``rendering.quick.scene3d.fog_volume.FogVolume``: ``uFogRange.w`` 1) every pass reads the
same integrated froxel volume instead: ``mistTransmittance`` is the transmittance from the volume's eye to the point,
and ``mistOver`` puts the in-scattered light in front of an opaque surface. Each pass binds the volume of the camera it
draws with (a reflection pass binds its mirrored volume). Programs including this must keep ``uFogVolume`` on
``FOG_TEXTURE_UNIT`` so it never shares a unit with a 2D sampler.
"""

FOG_TEXTURE_UNIT = 8

MIST_GLSL = """
uniform vec4 uMist;        // clear-air centre x, centre z, radius x, radius z (world units)
uniform vec4 uMistShape;   // falloff (radii beyond the edge per e-fold), floor thickening, thickening height, low glow
uniform sampler3D uFogVolume; // integrated in-scatter (rgb) and transmittance (a), exponential view-depth slices
uniform mat4 uFogView;     // world -> the volume camera's view
uniform vec4 uFogLens;     // half-extent x, y (Orthographic) or tangent x, y (Perspective); orthographic flag; unused
uniform vec4 uFogRange;    // near, far view depth, slices, enabled
// Volume coordinates of a world point: xy over the view, z the continuous slice (0 at near, slices at far).
vec3 fogCoordinate(vec3 world) {
    vec3 v=(uFogView*vec4(world,1.0)).xyz;
    float depth=max(-v.z,1e-4);
    vec2 ndc=uFogLens.z>0.5?v.xy/uFogLens.xy:v.xy/(uFogLens.xy*depth);
    return vec3(ndc*0.5+0.5,log(max(depth,uFogRange.x)/uFogRange.x)/log(uFogRange.y/uFogRange.x)*uFogRange.z);
}
vec4 fogVolumeAt(vec3 world) {
    vec3 c=fogCoordinate(world);
    // Texel k holds the integral to the far boundary of slice k; before the first boundary blend from clear air.
    vec4 s=texture(uFogVolume,clamp(vec3(c.xy,(c.z-0.5)/uFogRange.z),vec3(0.0),vec3(1.0)));
    return mix(vec4(0.0,0.0,0.0,1.0),s,clamp(c.z,0.0,1.0));
}
float mistTransmittance(vec3 world) {
    if(uFogRange.w>0.5) return fogVolumeAt(world).a;
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
    // Deeper mist also darkens (the far floor is the Orthographic upper field: dark at the top, lit low).
    return backdrop*(0.35+0.65*exp(-0.25*beyond))*(1.0+uMistShape.w*low*exp(-0.6*beyond*beyond));
}
// An opaque surface seen through the mist: the volume's in-scatter in front of it, or the analytic mix.
vec3 mistOver(vec3 surface, vec3 backdrop, vec3 world) {
    if(uFogRange.w>0.5) { vec4 fog=fogVolumeAt(world); return surface*fog.a+fog.rgb; }
    return mix(mistColour(backdrop,world),surface,mistTransmittance(world));
}
"""

FOG_OFF = dict(uFogVolume=FOG_TEXTURE_UNIT, uFogRange=(1., 2., 1., 0.))


def mist_uniforms(centre_xz=(0., 0.), radii_xz=(30., 3.), falloff=.6, floor_thickening=1.5, thickening_height=1.5,
                  low_glow=0.):
    """Uniform values for MIST_GLSL; falloff 0 turns the mist off."""
    values = (*centre_xz, *radii_xz, falloff, floor_thickening, thickening_height)
    if (any(v != v for v in values) or min(radii_xz) <= 0 or falloff < 0 or floor_thickening < 0 or thickening_height < 0
            or not low_glow >= 0):
        raise ValueError('Mist needs finite positive radii and non-negative shape values')
    return dict(uMist=(*centre_xz, *radii_xz), uMistShape=(falloff, floor_thickening, thickening_height, float(low_glow)))
