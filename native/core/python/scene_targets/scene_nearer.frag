#version 440
// N3.1's harness scene, pass 2: a nearer plane over the content's lower half (depth test less, writes on), a flat
// colour and no emission (its emission attachment masked): the nearer plane wins where it is nearer than pass 1's.
// D14 point 10's proof: u_mask_band > 0 extends it by two bands of partial coverage (gl_SampleMask), every sample but
// sample 0 in the first band above the half and sample 0 alone in the second, so a multisampled pixel there holds both
// planes' depths: its nearest resolve is the nearer plane where it is nearer, and sample 0 alone (the negative control)
// is not in the first band. u_mask_band 0 (every other round) writes every sample: unchanged.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 colour;
layout(location = 1) out vec4 emission;

layout(std140, binding = 18) uniform SceneNearer {
    vec4 u_nearer_colour;
    float u_nearer_depth;
    float u_mask_band;
};

void main()
{
    if (vUv.y > 0.5 + 2.0 * u_mask_band)
        discard;
    int mask = -1;
    if (vUv.y > 0.5 + u_mask_band)
        mask = 1;
    else if (vUv.y > 0.5)
        mask = ~1;
    gl_SampleMask[0] = mask;
    colour = u_nearer_colour;
    emission = vec4(0.0);
    gl_FragDepth = u_nearer_depth;
}
