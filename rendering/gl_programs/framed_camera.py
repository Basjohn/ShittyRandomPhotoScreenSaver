"""Shared framed-camera GLSL: one projection choice, explicit view rays and footprints.

``span`` is tangent-half-angle for Perspective and half-world-extent for
Orthographic. The CPU projection matrix and these ray uniforms are resolved
from the same camera. Cubemap captures always publish Perspective explicitly.
"""

FRAMED_CAMERA_GLSL = """
#ifndef FRAMED_CAMERA_GLSL
#define FRAMED_CAMERA_GLSL
uniform float uOrthographic;
vec3 framedRayOrigin(vec2 ndc, vec2 span) {
    return uOrthographic > 0.5 ? vec3(ndc * span, 0.0) : vec3(0.0);
}
vec3 framedRayDirection(vec2 ndc, vec2 span) {
    return uOrthographic > 0.5 ? vec3(0.0, 0.0, -1.0) : normalize(vec3(ndc * span, -1.0));
}
float framedPixelDepth(float depth) {
    return uOrthographic > 0.5 ? 1.0 : depth;
}
#endif
"""
