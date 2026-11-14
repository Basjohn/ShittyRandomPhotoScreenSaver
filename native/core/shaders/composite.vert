#version 440
// The composite's vertex stage (Current_Plan.md item 8b, N2.4; native/core/src/composite.h): Qt Quick's item quad, its
// texture coordinates spanning the item (0,0 at the item's top-left, 1,1 at its bottom-right). The block is the
// fragment stage's (Qt Quick gives both stages one uniform buffer at binding 0).
//
// The quad on whole pixels (R-NEW): the item's origin is moved onto the nearest pixel corner of the render target and
// the quad moves rigidly with it, so every pixel centre falls on a texel's centre (uv x the item's device size is k +
// 0.5) and never on the fragment stage's floor() thresholds, wherever the item is placed. At a half-pixel origin those
// thresholds sat on the centres and each of the quad's two triangles interpolated v_uv to its own side of them: the
// content broke by a texel along the diagonal. The shift is computed from the block alone, the same in every vertex,
// and in window pixels whichever way the backend's NDC or framebuffer runs (the viewport's size is whole, so a corner
// is whole from either edge). An item already on whole pixels moves by float rounding only (no pixel changes).

layout(location = 0) in vec4 qt_VertexPosition;
layout(location = 1) in vec2 qt_VertexTexCoord;

layout(location = 0) out vec2 v_uv;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float coverageOn;      // 1: the card's coverage applies; 0: skipped (an admitted overflow)
    float coverageRadius;  // device pixels
    float quarters;        // the content's clockwise quarter turns
    vec4 coverageRect;     // device pixels, item-local: x, y, width, height
    vec4 sizes;            // the item's device pixels (x, y), the texture's (z, w)
    vec4 viewport;         // the render target's viewport in its pixels: x, y, width, height (Qt's viewportRect)
};

void main()
{
    v_uv = qt_VertexTexCoord;
    vec4 position = qt_Matrix * qt_VertexPosition;
    vec4 origin = qt_Matrix * vec4(0.0, 0.0, 0.0, 1.0);
    if (viewport.z > 0.0 && viewport.w > 0.0 && origin.w > 0.0) {
        vec2 corner = (origin.xy / origin.w * 0.5 + 0.5) * viewport.zw;
        vec2 shift = floor(corner + 0.5) - corner;
        position.xy += shift * (2.0 / viewport.zw) * position.w;
    }
    gl_Position = position;
}
