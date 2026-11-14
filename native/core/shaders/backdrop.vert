#version 440
// The backdrop pyramid's vertex stage (Current_Plan.md N5.7b; native/core/src/backdrop.h): one triangle over the whole
// target in clip space, uv 0 to 2 along its legs, exactly the Python pyramid's triangle
// (rendering/quick/render/surface_backdrop.py _VERTEX: vUv = p, gl_Position = p * 2 - 1), so every level samples at the
// coordinates the Python passes sample at. No correction: vUv runs along the target's memory rows on every backend
// (clip y -1 is memory row 0 on OpenGL and on Vulkan alike), which is the order every level is kept in.

layout(location = 0) in vec2 position;
layout(location = 0) out vec2 vUv;

void main()
{
    vUv = position * 0.5 + 0.5;
    gl_Position = vec4(position, 0.0, 1.0);
}
