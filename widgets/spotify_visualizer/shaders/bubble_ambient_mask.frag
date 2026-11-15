#version 460 core
layout(location = 0) in vec2 vUnitCircle;
layout(location = 1) in float vOcclusionAlpha;
layout(location=0) out vec4 fragColor;
layout(location=1) out vec4 fragLight;
void main() {
    float distanceFromCentre = length(vUnitCircle);
    float aa = max(fwidth(distanceFromCentre), 0.0001);
    float coverage = (1.0-smoothstep(1.0-aa, 1.0+aa, distanceFromCentre))
        * clamp(vOcclusionAlpha, 0.0, 1.0);
    if (coverage <= 0.0) discard;
    // With GL_ZERO / GL_ONE_MINUS_SRC_ALPHA this removes ONLY the ambience
    // (its coverage and its light) under actual hero surfaces; the gradient
    // and Bubble remain intact.
    fragColor = vec4(0.0, 0.0, 0.0, coverage);
    fragLight = vec4(0.0, 0.0, 0.0, coverage);
}
