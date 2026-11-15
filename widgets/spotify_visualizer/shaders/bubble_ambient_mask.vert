#version 460 core
// Bubble's ambient hero-bubble mask (bubble_ambient_gl.py; the native core draws the same file): one instanced quad a
// rendered hero circle (D15 point 5), a square of the circle's diameter in target texels (the canonical shader's
// `delta.x *= aspect` makes the circle round in texels), erasing the ambience under it.
#ifdef VULKAN
#define srpssVertexIndex gl_VertexIndex
#define srpssInstanceIndex gl_InstanceIndex
#else
#define srpssVertexIndex gl_VertexID
#define srpssInstanceIndex gl_InstanceID
#endif
//@srpss_conventions
//@srpss_geometry
layout(std140, binding = 18) uniform BubbleAmbientMask {
    vec2 u_target_px;                // the ambient target's content size in texels
    float u_response_radius_scale;   // canonical-card radius unit (x world scale) / content height
};
layout(location=0) in vec4 aOccluder;  // per instance: normalized x/y, height-normalized radius, alpha
layout(location = 0) out vec2 vUnitCircle;
layout(location = 1) out float vOcclusionAlpha;
void main() {
    vec2 corner = srpssSpriteCorner(srpssVertexIndex);
    float diameterPx = 2.0 * aOccluder.z * u_response_radius_scale * u_target_px.y;
    gl_Position = (aOccluder.z > 0.0 && aOccluder.w > 0.0)
        ? srpssSpriteClip(vec4(srpssTopDownClip(aOccluder.xy), 0.0, 1.0), corner, diameterPx, u_target_px)
        : srpssSpriteCulled();
    vUnitCircle = corner * 2.0 - 1.0;
    vOcclusionAlpha = min(1.0, aOccluder.w);
}
