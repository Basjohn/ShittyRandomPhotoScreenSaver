#version 440
// Readback metadata/completeness only. Base attachments are written; non-base mips are not generated or judged.
layout(location = 0) out vec4 colour0;
layout(location = 1) out vec4 colour1;
layout(location = 2) out vec4 colour2;
layout(location = 3) out vec4 colour3;
void main()
{
    colour0 = vec4(0.2, 0.4, 0.6, 1.0);
    colour1 = vec4(0.3, 0.5, 0.7, 1.0);
    colour2 = vec4(0.4, 0.6, 0.8, 1.0);
    colour3 = vec4(0.5, 0.7, 0.9, 1.0);
}
