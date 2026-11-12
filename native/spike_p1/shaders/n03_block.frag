#version 440
// N0.3 scene 1, the std140 block (rule 5): a vec3, a scalar that fills its padding, a vec3 array, a mat3 and a
// trailing scalar, packed by the core from the reflected offsets and read back through colour, one value per texel
// of an 8 x 1 target: 0 (a, f0), 1-3 arr[i], 4-6 the columns of m, 7 tail.
//@n03_common

layout(std140, binding = 1) uniform Probe {
    vec3 a;
    float f0;
    vec3 arr[3];
    mat3 m;
    float tail;
};

layout(location = 0) out vec4 outValue;

void main()
{
    int i = int(gl_FragCoord.x);
    vec4 value = vec4(tail, 0.0, 0.0, 0.0);
    if (i == 0)
        value = vec4(a, f0);
    else if (i <= 3)
        value = vec4(arr[i - 1], 0.0);
    else if (i <= 6)
        value = vec4(m[i - 4], 0.0);
    outValue = value + vec4(consumeVaryings());
}
