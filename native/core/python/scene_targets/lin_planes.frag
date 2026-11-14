#version 440
// N3.1's harness, D14 point 10's means (b): the tilted plane of scene_planes.frag written twice, as the window depth
// (gl_FragDepth) and as a depth into an R32F attachment declared "resolve": "nearest" (the multisampled colour
// attachment the core's nearest resolve reads when the depth itself cannot be sampled), beside a plain colour.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 colour;
layout(location = 1) out vec4 lin;

layout(std140, binding = 18) uniform LinPlanes {
    float u_near_depth;  // the plane's depth at the content's left edge
    float u_far_depth;   // and at its right edge
};

void main()
{
    float depth = mix(u_near_depth, u_far_depth, vUv.x);
    colour = vec4(vUv, 0.5, 1.0);
    lin = vec4(depth, 0.0, 0.0, 1.0);
    gl_FragDepth = depth;
}
