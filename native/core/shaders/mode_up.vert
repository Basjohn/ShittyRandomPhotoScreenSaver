#version 440
// The core's triangle for a pass whose fragment reads vUv (the item quad's uv over the target, y up: the fullscreen
// transitions, the background layer, the scene targets' composites, the environment and bloom steps): mode.vert with
// its location-0 output named as that fragment's input. The pipeline already feeds the up uv into `uv` (location 1);
// only the name differs. Vulkan, D3D and Metal match the stages by location, but Qt's OpenGL backend matches them by
// name and warned "Vertex output name 'v_uv' does not match fragment input 'vUv'" for every such pipeline (older GLSL
// links varyings by name, so a mismatch there reads an unset input).

layout(location = 0) in vec2 position;
layout(location = 1) in vec2 uv;
layout(location = 0) out vec2 vUv;

void main()
{
    vUv = uv;
    gl_Position = vec4(position, 0.0, 1.0);
}
