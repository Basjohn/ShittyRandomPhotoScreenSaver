#version 460 core
// Baked for every target by tools/regen_qrc.py --shaders (its --check says whether the pack is current).
// Card surface materials (Docs/Architecture/Card_Surface_Materials.md). The backdrop coordinate comes from this vertex's own position in the render
// target, so it follows pixel shift, Edit drags and CUSTOM scale with no binding.
layout(location = 0) in vec4 qt_Vertex;
layout(location = 1) in vec2 qt_MultiTexCoord0;
layout(location = 0) out vec2 vLocal;
layout(location = 1) out vec2 vScreen;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 itemSize;
    float cornerRadius;
    float contentInset;
    float borderWidth;
    float opacityAdjust;
    vec4 normalColor;
    vec4 tintColor;
    vec4 textColor;
    vec4 blurTint;
    vec4 lightNoise;
    vec4 glassLegibility;
    vec4 panelLimits;
    float panelCeiling;   // dark ink: the panel's furthest lift toward white (SurfaceContrast.panelCeiling)
};
out gl_PerVertex { vec4 gl_Position; };
void main() {
    vLocal = qt_MultiTexCoord0;
    gl_Position = qt_Matrix * qt_Vertex;
    vScreen = gl_Position.xy / gl_Position.w * 0.5 + 0.5;
}
