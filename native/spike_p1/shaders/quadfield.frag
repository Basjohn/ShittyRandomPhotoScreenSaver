#version 440

layout(location = 0) in vec2 v_uv;
layout(location = 1) in vec3 v_color;

layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 unitToClip;
    vec4 params;
};

void main()
{
    float r = length(v_uv);
    float a = 1.0 - smoothstep(0.70, 1.0, r);
    fragColor = vec4(v_color * a, a);   // premultiplied alpha, as Qt Quick expects
}
