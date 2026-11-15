#version 440
// N3.1's harness, the cost breakdown's surface pass (scene_target_check.py cost_parts): the scene's colour read where
// its content lies (image rows [H-h, H), columns [0, w): D14 point 2), so the colour is a read attachment (resolved
// when multisampled). Not a look.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 18) uniform ShowColour {
    vec2 u_target_px;    // the core's: the surface's pixels (the scene's content size)
};
layout(binding = 1) uniform sampler2D u_scene;

void main()
{
    vec2 allocation = vec2(textureSize(u_scene, 0));
    vec2 uv = vec2(vUv.x * u_target_px.x / allocation.x, (allocation.y - vUv.y * u_target_px.y) / allocation.y);
    fragColor = vec4(clamp(texture(u_scene, uv).rgb, 0.0, 1.0), 1.0);
}
