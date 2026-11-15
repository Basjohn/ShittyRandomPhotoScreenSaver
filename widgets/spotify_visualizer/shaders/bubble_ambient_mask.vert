#version 460 core
layout(location=0) in vec2 aPosition;
layout(location=1) in vec2 aUnitCircle;
layout(location=2) in float aOcclusionAlpha;
layout(location = 0) out vec2 vUnitCircle;
layout(location = 1) out float vOcclusionAlpha;
void main() {
    gl_Position = vec4(aPosition.x*2.0-1.0, 1.0-aPosition.y*2.0, 0.0, 1.0);
    vUnitCircle = aUnitCircle;
    vOcclusionAlpha = aOcclusionAlpha;
}
