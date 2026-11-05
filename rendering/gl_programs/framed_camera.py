"""Shared framed-camera GLSL: explicit Perspective view rays and pixel footprints.

``span`` is the tangent-half-angle pair. The CPU projection matrix and these ray
uniforms are resolved from the same camera. Perspective is the only projection
(Orthographic retired 5 Nov 2026); cubemap captures are Perspective too.
"""

FRAMED_CAMERA_GLSL = """
#ifndef FRAMED_CAMERA_GLSL
#define FRAMED_CAMERA_GLSL
vec3 framedRayOrigin(vec2 ndc, vec2 span) {
    return vec3(0.0);
}
vec3 framedRayDirection(vec2 ndc, vec2 span) {
    return normalize(vec3(ndc * span, -1.0));
}
float framedPixelDepth(float depth) {
    return depth;
}
#endif
"""
