#version 440
// N0.3 scene 1, first pass: the checkerboard with its gradients, placed by geometry alone (the item position the
// corrected matrix put here), never by gl_FragCoord. Texel t of the content: red 2 t.x, green 4 t.y, blue 255 or 64 by
// checker parity (cells of params.x pixels), alpha 255; the four corner cells differ in red and green.
//@n03_common

layout(location = 0) out vec4 fragColor;

void main()
{
    ivec2 t = ivec2(floor(v_item));
    ivec2 cell = t / int(params.x);
    float blue = ((cell.x + cell.y) & 1) == 1 ? 255.0 : 64.0;
    fragColor = vec4(float(t.x * 2) / 255.0, float(t.y * 4) / 255.0, blue / 255.0, 1.0 + consumeVaryings());
}
