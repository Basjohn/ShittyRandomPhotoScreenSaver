#version 440
// The composite's vertex stage (Current_Plan.md item 8b, N2.4; native/core/src/composite.h): Qt Quick's item quad, its
// texture coordinates spanning the item (0,0 at the item's top-left, 1,1 at its bottom-right). The block is the
// fragment stage's (Qt Quick gives both stages one uniform buffer at binding 0).

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
};

void main()
{
    v_uv = qt_VertexTexCoord;
    gl_Position = qt_Matrix * qt_VertexPosition;
}
