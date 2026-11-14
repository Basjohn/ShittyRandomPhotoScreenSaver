#version 460 core
// The display's background layer (Current_Plan.md N5.7a, D7 point 1): the current photo, drawn by the native core's
// fullscreen pass (N4.a; native/core/src/mode_content.h, a still) into the layer's target and retained there. Not a Qt
// Quick ShaderEffect: the core loads this pack at run time (rendering/quick/render/native_background.py). Baked for every
// target by tools/regen_qrc.py --shaders (its --check says whether the pack is current).
//
// vUv is the item quad's uv over the target (x right, y up, 1 at the target's top row), as the fullscreen transitions
// read it; the photo's rows are top first, so its v runs down. u_source_uv is the presenter's placement
// (rendering/quick/background_placement.py, the one owner the Python presenter's QSGImageNode reads too): the photo's
// source rect in its uv, drawn over the whole layer. The photo is sampled linearly with no mips, as the retained node
// samples it; at the item's own device size every fragment lands on a texel's centre.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 18) uniform BackgroundLayerPass {
    vec4 u_source_uv; // x, y: the source rect's top-left in the photo's uv; z, w: its extent
};

layout(binding = 0) uniform sampler2D uPhoto;

void main()
{
    vec2 uv = u_source_uv.xy + vec2(vUv.x, 1.0 - vUv.y) * u_source_uv.zw;
    fragColor = texture(uPhoto, uv);
}
