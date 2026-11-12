#version 440
// N0.3 scene 3, second pass (no culling, the same front face): gl_FrontFacing (r), and which triangle this is (g:
// the front-authored one's red, b: the back-authored one's green).
//@n03_common

layout(location = 0) out vec4 outFacing;

void main()
{
    outFacing = vec4(gl_FrontFacing ? 1.0 : 0.0, v_color.r, v_color.g, 1.0 + consumeVaryings());
}
