#version 440
// N3.1's harness, the surface's pass (native only): the scene's captured colour (clamped: N3.4 owns the HDR resolve)
// shaded by the captured depth, and the ambient target's coverage and light over it, each read where its content lies
// in its allocation (image rows [H-h, H), columns [0, w): D14 point 2). A look at the targets through the card, not a
// parity record (rule (a) is the targets' own readbacks).
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 18) uniform SurfaceShow {
    vec2 u_target_px;    // the core's: the surface's pixels (the scene's content size)
    vec2 u_ambient_px;   // a setting: the ambient target's content size
    float u_depth_shade;
};
layout(binding = 1) uniform sampler2D u_scene;
layout(binding = 2) uniform sampler2D u_depth;
layout(binding = 3) uniform sampler2D u_cover;
layout(binding = 4) uniform sampler2D u_light;

vec2 contentUv(vec2 content, vec2 allocation)
{
    return vec2(vUv.x * content.x / allocation.x, (allocation.y - vUv.y * content.y) / allocation.y);
}

void main()
{
    vec2 sceneUv = contentUv(u_target_px, vec2(textureSize(u_scene, 0)));
    vec2 ambientUv = contentUv(u_ambient_px, vec2(textureSize(u_cover, 0)));
    vec3 scene = clamp(texture(u_scene, sceneUv).rgb, 0.0, 1.0);
    float depth = texture(u_depth, sceneUv).r;
    vec4 cover = texture(u_cover, ambientUv);
    vec3 light = texture(u_light, ambientUv).rgb;
    vec3 rgb = scene * mix(1.0, 1.0 - depth, u_depth_shade);
    rgb = cover.rgb + rgb * (1.0 - cover.a) + light;
    fragColor = vec4(clamp(rgb, 0.0, 1.0), 1.0);
}
