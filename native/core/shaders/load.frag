#version 440
// The known-cost pass (Current_Plan.md item 8b, N2.6; native/core/src/load_pass.h): every fragment runs the same chain of
// dependent steps (each reads the last, so none can be hoisted or skipped), its length a uniform, and adds a small value
// to the target (additive blending), so each draw costs the same and every draw is executed.

layout(location = 0) in vec2 seed;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform Load {
    vec4 params;   // x: the chain's length
};

void main()
{
    vec2 p = seed;
    float acc = 0.0;
    int steps = int(params.x);
    for (int i = 0; i < steps; ++i) {
        p = vec2(sin(p.x * 1.7 + p.y + 0.3), cos(p.y * 1.3 - p.x + 0.1));
        acc += p.x * p.y;
    }
    fragColor = vec4(fract(acc) * (1.0 / 1024.0));
}
