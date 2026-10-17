"""Sphere impostors: exact, ray-traced spheres from one camera-facing quad each (shared, import-safe GLSL + CPU mirrors).

For any number of spheres from a few pixels to most of the screen (bubbles, droplets, beads, planets): each instance
draws one quad in view space that exactly covers the sphere's silhouette cone, and the fragment shader intersects
the view ray with the sphere, so silhouettes are perfect circles at every size (no tessellation facets), normals are
analytic and ``gl_FragDepth`` is the true surface depth, so spheres that touch or interpenetrate meet along their
real intersection and opaque scenery occludes them correctly. Everything is in **view space** with the eye at the
origin looking down -z; a consumer supplies its own world-to-view placement and its projection (which may include
Qt's item matrix).

* ``sceneSphereCorner(centre, radius, blur, corner)`` (vertex): the view-space position of a covering-quad corner
  (``corner`` in [-1, 1]^2). The quad lies in the plane through the centre perpendicular to the line of sight, with
  half-size ``(radius + blur) * d / sqrt(d^2 - (radius + blur)^2)``: exactly the silhouette cone's radius there.
  ``blur`` (view units) widens the sphere's soft edge for defocus. A camera inside the sphere collapses the quad.
* ``sceneSphereRay(ray, centre, radius, tNear, tFar)``: the ray's entry and exit distances (``ray`` normalised).
* ``sceneSphereCoverage(ray, centre, radius, blur)``: antialiased (or, with ``blur``, softened) silhouette coverage
  from the ray's distance to the centre; 0 outside.
* ``sceneSphereDepth(point, projection)``: the window depth of a view-space point.

CPU mirrors (``scene3d_sphere_corner``, ``scene3d_sphere_ray``) let tests reason about the same geometry.
"""
from __future__ import annotations

import math

Vec3 = tuple[float, float, float]

SCENE3D_SPHERES_GLSL = """
#ifndef SCENE3D_SPHERES_GLSL
#define SCENE3D_SPHERES_GLSL
vec3 sceneSphereCorner(vec3 centre, float radius, float blur, vec2 corner) {
    float reach = radius + max(blur, 0.0);
    float d = length(centre);
    if (d <= reach * 1.0001) return centre;           // the eye is inside: nothing to draw
    vec3 toEye = -centre / d;
    vec3 up = abs(toEye.y) > 0.99 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0);
    vec3 u = normalize(cross(up, toEye));
    vec3 v = cross(toEye, u);
    float half_ = reach * d / sqrt(d * d - reach * reach);
    return centre + (u * corner.x + v * corner.y) * half_;
}
bool sceneSphereRay(vec3 ray, vec3 centre, float radius, out float tNear, out float tFar) {
    float b = dot(centre, ray);
    float c = dot(centre, centre) - radius * radius;
    float h = b * b - c;
    if (h < 0.0) { tNear = tFar = b; return false; }
    h = sqrt(h);
    tNear = b - h;
    tFar = b + h;
    return tFar > 0.0;
}
float sceneSphereCoverage(vec3 ray, vec3 centre, float radius, float blur) {
    // The ray's distance from the centre, against the radius: one pixel of antialiasing, or the blur's width.
    float along = dot(centre, ray);
    float miss = length(centre - ray * along);
    float width = max(fwidth(miss), max(blur, 0.0) * 2.0);
    return clamp((radius + max(blur, 0.0) - miss) / max(width, 1e-6) + 0.5 * step(blur, 0.0), 0.0, 1.0);
}
float sceneSphereDepth(vec3 point, mat4 projection) {
    vec4 clip = projection * vec4(point, 1.0);
    return clip.z / clip.w * 0.5 + 0.5;
}
#endif
"""


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _normalize(a: Vec3) -> Vec3:
    length = math.sqrt(_dot(a, a))
    return a[0] / length, a[1] / length, a[2] / length


def scene3d_sphere_corner(centre: Vec3, radius: float, blur: float, corner: tuple[float, float]) -> Vec3:
    """CPU mirror of ``sceneSphereCorner``."""
    reach = radius + max(blur, 0.0)
    d = math.sqrt(_dot(centre, centre))
    if d <= reach * 1.0001:
        return centre
    to_eye = (-centre[0] / d, -centre[1] / d, -centre[2] / d)
    up = (1.0, 0.0, 0.0) if abs(to_eye[1]) > 0.99 else (0.0, 1.0, 0.0)
    u = _normalize(_cross(up, to_eye))
    v = _cross(to_eye, u)
    half = reach * d / math.sqrt(d * d - reach * reach)
    return tuple(centre[i] + (u[i] * corner[0] + v[i] * corner[1]) * half for i in range(3))


def scene3d_sphere_ray(ray: Vec3, centre: Vec3, radius: float) -> tuple[bool, float, float]:
    """CPU mirror of ``sceneSphereRay``: (hit, tNear, tFar)."""
    b = _dot(centre, ray)
    h = b * b - (_dot(centre, centre) - radius * radius)
    if h < 0.0:
        return False, b, b
    h = math.sqrt(h)
    return b + h > 0.0, b - h, b + h


__all__ = ["SCENE3D_SPHERES_GLSL", "scene3d_sphere_corner", "scene3d_sphere_ray"]
