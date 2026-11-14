#version 440
// N3.1's harness, D14 point 10's means (b): scene_nearer.frag's nearer plane and its two partial-coverage bands
// (gl_SampleMask: every sample but 0, then sample 0 alone), its depth written to the window depth and the R32F
// "nearest" attachment alike (depth test less, so a sample keeps the nearer of the two planes in both).
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 colour;
layout(location = 1) out vec4 lin;

layout(std140, binding = 18) uniform LinNearer {
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
    colour = vec4(0.1, 0.6, 0.9, 1.0);
    lin = vec4(u_nearer_depth, 0.0, 0.0, 1.0);
    gl_FragDepth = u_nearer_depth;
}
