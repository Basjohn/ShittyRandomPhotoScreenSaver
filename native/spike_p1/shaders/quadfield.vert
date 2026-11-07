#version 440
// P1 spike: a field of instanced, animated soft dots. Port-readiness rules:
// explicit locations/bindings, one std140 block, no legacy built-ins.

layout(location = 0) in vec2 corner;   // per vertex: quad corner in -1..1
layout(location = 1) in vec4 inst;     // per instance: x, y (unit space, y down), size, hue

layout(location = 0) out vec2 v_uv;
layout(location = 1) out vec3 v_color;

layout(std140, binding = 0) uniform buf {
    mat4 unitToClip;   // unit square of the drawn area -> clip space (backend correction included)
    vec4 params;       // x: time (s), y: aspect (w / h), z, w: unused
};

vec3 hue2rgb(float h)
{
    vec3 k = abs(fract(vec3(h) + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0;
    return clamp(k, 0.0, 1.0);
}

void main()
{
    float t = params.x;
    float phase = inst.w * 6.2831853;
    vec2 centre = inst.xy + 0.012 * vec2(cos(t * 1.7 + phase), sin(t * 2.3 + phase));
    float size = inst.z * (0.8 + 0.2 * sin(t * 3.0 + phase * 2.0));
    vec2 unitPos = centre + corner * vec2(size / params.y, size);
    v_uv = corner;
    v_color = hue2rgb(inst.w + 0.05 * t);
    gl_Position = unitToClip * vec4(unitPos, 0.0, 1.0);
}
