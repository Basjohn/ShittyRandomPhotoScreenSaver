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
* Round on screen: a rectilinear camera draws a sphere off its axis as an oval stretched toward the frame's edges
  (wide views make it obvious). ``sceneSphereScreenCorner(centre, radius, blur, corner, projection)`` (vertex) places
  a screen-aligned square round the sphere's projected centre, sized to the sphere's apparent width across the line
  of sight, and ``sceneSphereFacingRay(centre, reach, corner)`` (fragment, with the interpolated ``corner`` and
  ``reach = radius + blur``) gives the view ray as if the sphere were seen straight along the line to its centre, so
  every sphere is a circle wherever it sits; feed that ray to the functions below.
* ``sceneSphereRay(ray, centre, radius, tNear, tFar)``: the ray's entry and exit distances (``ray`` normalised).
* ``sceneSphereCoverage(ray, centre, radius, blur)``: antialiased (or, with ``blur``, softened) silhouette coverage
  from the ray's distance to the centre; 0 outside.
* ``sceneSphereDepth(point, projection)``: the window depth of a view-space point.
* ``sceneDefocusRadius(depth, focus, aperture, nearWeight, farWeight)``: the blur (view units at the sphere) for a
  thin-lens depth of field, weighted separately in front of and behind the focus (deep scenes read best with a long
  field behind the focus and soft foreground); feed it to ``sceneSphereCorner``/``sceneSphereCoverage``.

* ``sceneClusterDistance(p, spheres, count, blend)`` / ``sceneClusterRay(ray, spheres, count, blend, tStart, tEnd,
  t, normal, closest)``: up to four spheres (view-space centre, radius) joined into one smooth body where they meet,
  as touching bubbles merge with a neck (polynomial smooth minimum; ``blend`` is the neck's reach in view units, 0
  keeps plain spheres). The ray is sphere-traced between ``tStart`` and ``tEnd`` (the cluster's bounding sphere,
  drawn with ``sceneSphereCorner``); the normal comes from the distance field's gradient, and ``closest`` (the
  smallest distance the ray passed at, over its distance) antialiases the joined silhouette.

* ``sceneSphereGlint(centre, radius, toLight)``: the view-space point where a sphere mirrors a distant light toward
  the eye (its normal halfway between the light and the eye), for drawing a glint sprite there.
* ``sceneStarburst(deltaPixels, reach, diagonals)``: a sparkle's light at an offset in pixels from its centre: a
  sharp core, four spikes tapering over ``reach`` pixels inside a faint sheath, a soft halo and, with ``diagonals``
  (0..1), four shorter diagonal spikes. Glints on glass and stars both read as these.

CPU mirrors (``scene3d_sphere_corner``, ``scene3d_sphere_ray``, ``scene3d_cluster_distance``) let tests reason about
the same geometry.
"""
from __future__ import annotations

import math

Vec3 = tuple[float, float, float]

SCENE3D_SPHERES_GLSL = """
#ifndef SCENE3D_SPHERES_GLSL
#define SCENE3D_SPHERES_GLSL
float sceneNearCircle(float frontDepth, float focus, float aperture, float pixelScale) {
    return pixelScale * (aperture / 3.0) * max(focus - frontDepth, 0.0) / max(frontDepth, 2.5);
}
// Conservative pinhole bounds, including near-plane/eye-inside spheres. A near
// crossing uses a full-screen quad; actual intersections/depth reject empty pixels.
vec4 sceneSphereClipCorner(vec3 centre, float reach, vec2 corner, mat4 projection) {
    float depth = -centre.z;
    if (reach <= 0.0 || depth + reach <= 0.05) return vec4(2.0, 2.0, 2.0, 1.0);
    if (depth - reach <= 0.05) return vec4(corner, 0.0, 1.0);
    float denominator = depth * depth - reach * reach;
    vec2 root = sqrt(max(centre.xy * centre.xy + denominator, vec2(0.0)));
    vec2 slopes = (centre.xy * depth + corner * reach * root) / denominator;
    vec2 ndc = slopes * vec2(projection[0][0], projection[1][1]) - projection[2].xy;
    return vec4(clamp(ndc, vec2(-1.0), vec2(1.0)), 0.0, 1.0);
}
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
void sceneSphereBasis(vec3 centre, out vec3 axis, out vec3 u, out vec3 v) {
    axis = normalize(centre);
    vec3 toEye = -axis;
    vec3 up = abs(toEye.y) > 0.99 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0);
    u = normalize(cross(up, toEye));
    v = cross(toEye, u);
}
vec4 sceneSphereScreenCorner(vec3 centre, float radius, float blur, vec2 corner, mat4 projection) {
    float reach = radius + max(blur, 0.0);
    float d = length(centre);
    float tanA = reach / sqrt(max(d * d - reach * reach, 1e-8));
    float cosOffAxis = max(-centre.z / d, 1e-3);
    vec4 clip = projection * vec4(centre, 1.0);
    vec2 ndcRadius = vec2(projection[0][0], projection[1][1]) * tanA / cosOffAxis;
    return clip + vec4(corner * ndcRadius * clip.w, 0.0, 0.0);
}
vec3 sceneSphereFacingRay(vec3 centre, float reach, vec2 corner) {
    vec3 axis, u, v;
    sceneSphereBasis(centre, axis, u, v);
    float d = length(centre);
    float tanA = reach / sqrt(max(d * d - reach * reach, 1e-8));
    return normalize(axis + (u * corner.x + v * corner.y) * tanA);
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
    // fwidth reads the 2x2 neighbours; a neighbour's non-finite value must never leak into this pixel.
    float derivative = fwidth(miss);
    if (!(derivative < 1e30)) derivative = 0.0;
    float width = max(derivative, max(blur, 0.0) * 2.0);
    return clamp((radius + max(blur, 0.0) - miss) / max(width, 1e-6) + 0.5 * step(blur, 0.0), 0.0, 1.0);
}
float sceneDefocusRadius(float depth, float focus, float aperture, float nearWeight, float farWeight) {
    return aperture * (max(focus - depth, 0.0) * nearWeight + max(depth - focus, 0.0) * farWeight);
}
float sceneSmoothMin(float a, float b, float blend) {
    if (blend <= 0.0) return min(a, b);
    float h = max(blend - abs(a - b), 0.0) / blend;
    return min(a, b) - h * h * blend * 0.25;
}
float sceneClusterDistance(vec3 p, vec4 spheres[4], int count, float blend) {
    float d = length(p - spheres[0].xyz) - spheres[0].w;
    for (int i = 1; i < 4; ++i) {
        if (i >= count) break;
        d = sceneSmoothMin(d, length(p - spheres[i].xyz) - spheres[i].w, blend);
    }
    return d;
}
bool sceneClusterRay(vec3 ray, vec4 spheres[4], int count, float blend, float tStart, float tEnd,
                     out float t, out vec3 normal, out float closest) {
    t = max(tStart, 0.0);
    closest = 1e9;
    normal = vec3(0.0, 0.0, 1.0);
    for (int i = 0; i < 64; ++i) {
        float d = sceneClusterDistance(ray * t, spheres, count, blend);
        closest = min(closest, abs(d) / max(t, 1e-4));
        if (abs(d) < 1e-4 * max(t, 1.0)) {
            vec2 e = vec2(1.0, -1.0) * 1e-4 * max(t, 1.0);
            vec3 p = ray * t;
            normal = normalize(e.xyy * sceneClusterDistance(p + e.xyy, spheres, count, blend)
                             + e.yyx * sceneClusterDistance(p + e.yyx, spheres, count, blend)
                             + e.yxy * sceneClusterDistance(p + e.yxy, spheres, count, blend)
                             + e.xxx * sceneClusterDistance(p + e.xxx, spheres, count, blend));
            closest = 0.0;
            return true;
        }
        t += abs(d);  // an eye/near plane inside the union traces its exit surface
        if (t > tEnd) break;
    }
    return false;
}
vec3 sceneSphereGlint(vec3 centre, float radius, vec3 toLight) {
    vec3 toEye = normalize(-centre);
    return centre + normalize(normalize(toLight) + toEye) * radius;
}
float sceneStarburst(vec2 deltaPixels, float reach, float diagonals) {
    vec2 span = abs(deltaPixels);
    float core = 1.0 - smoothstep(0.0, 1.6, span.x + span.y);
    float halo = exp(-dot(deltaPixels, deltaPixels) / max(reach * reach * 0.06, 1.0));
    vec2 along = vec2(pow(max(0.0, 1.0 - span.x / reach), 1.4), pow(max(0.0, 1.0 - span.y / reach), 1.4));
    float spikes = along.x * (exp(-span.y * span.y / 0.5) + 0.15 * exp(-span.y * span.y / 3.0))
                 + along.y * (exp(-span.x * span.x / 0.5) + 0.15 * exp(-span.x * span.x / 3.0));
    vec2 turned = abs(vec2(deltaPixels.x + deltaPixels.y, deltaPixels.x - deltaPixels.y)) * 0.70710678;
    float short_ = reach * 0.45;
    float diagonal = (pow(max(0.0, 1.0 - turned.x / short_), 2.0) * exp(-turned.y * turned.y / 0.4)
                    + pow(max(0.0, 1.0 - turned.y / short_), 2.0) * exp(-turned.x * turned.x / 0.4)) * diagonals;
    return 1.4 * core + 0.35 * halo + spikes + 0.6 * diagonal;
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


def scene3d_sphere_facing_ray(centre: Vec3, reach: float, corner: tuple[float, float]) -> Vec3:
    """CPU mirror of ``sceneSphereFacingRay``."""
    d = math.sqrt(_dot(centre, centre))
    axis = (centre[0] / d, centre[1] / d, centre[2] / d)
    to_eye = (-axis[0], -axis[1], -axis[2])
    up = (1.0, 0.0, 0.0) if abs(to_eye[1]) > 0.99 else (0.0, 1.0, 0.0)
    u = _normalize(_cross(up, to_eye))
    v = _cross(to_eye, u)
    tan_a = reach / math.sqrt(max(d * d - reach * reach, 1e-8))
    return _normalize(tuple(axis[i] + (u[i] * corner[0] + v[i] * corner[1]) * tan_a for i in range(3)))


def scene3d_sphere_ray(ray: Vec3, centre: Vec3, radius: float) -> tuple[bool, float, float]:
    """CPU mirror of ``sceneSphereRay``: (hit, tNear, tFar)."""
    b = _dot(centre, ray)
    h = b * b - (_dot(centre, centre) - radius * radius)
    if h < 0.0:
        return False, b, b
    h = math.sqrt(h)
    return b + h > 0.0, b - h, b + h


def scene3d_smooth_min(a: float, b: float, blend: float) -> float:
    """CPU mirror of ``sceneSmoothMin``."""
    if blend <= 0.0:
        return min(a, b)
    h = max(blend - abs(a - b), 0.0) / blend
    return min(a, b) - h * h * blend * 0.25


def scene3d_cluster_distance(p: Vec3, spheres, blend: float) -> float:
    """CPU mirror of ``sceneClusterDistance`` (spheres: [(x, y, z, r), ...], up to four)."""
    distances = [math.sqrt(_dot(_sub(p, s[:3]), _sub(p, s[:3]))) - s[3] for s in spheres]
    d = distances[0]
    for other in distances[1:]:
        d = scene3d_smooth_min(d, other, blend)
    return d


__all__ = ["SCENE3D_SPHERES_GLSL", "scene3d_cluster_distance", "scene3d_smooth_min", "scene3d_sphere_corner",
           "scene3d_sphere_facing_ray", "scene3d_sphere_ray"]
