#version 440
// N3.1's harness scene, pass 1 (native/core/python/scene_target_check.py): into the scene target's two attachments, an
// HDR colour past white (the RGBA16F intermediate) and an emission, at the window depth of a tilted plane written through
// gl_FragDepth (0.25 at the content's left edge to 0.75 at its right). Positions come from vUv (y up over the content),
// so the Python reference (SceneTarget with depth_texture, background() and hdr) draws the same values.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 colour;
layout(location = 1) out vec4 emission;

layout(std140, binding = 18) uniform ScenePlanes {
    float u_hdr_gain;    // colour past white
    float u_near_depth;  // the plane's depth at the content's left edge
    float u_far_depth;   // and at its right edge
    float u_emission;
};

void main()
{
    colour = vec4(vUv.x * u_hdr_gain, vUv.y * u_hdr_gain, 0.25 + 0.5 * vUv.x * vUv.y, 1.0);
    emission = vec4(u_emission * vUv.y, 0.0, u_emission * (1.0 - vUv.y), 1.0);
    gl_FragDepth = mix(u_near_depth, u_far_depth, vUv.x);
}
