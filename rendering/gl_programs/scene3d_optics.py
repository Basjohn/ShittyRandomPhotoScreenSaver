"""Shared optics for transparent 3D surfaces (§4A G3B): exact Fresnel, thin-film interference, refraction through a
sphere. Import-safe GLSL plus CPU mirrors (no GL).

* ``sceneFresnelDielectric(cosIncident, eta)``: the exact unpolarised Fresnel reflectance at a smooth interface,
  ``eta`` = outside index / inside index along the incident ray (water into air is 1.33). Past the critical angle the
  light is totally reflected (1): the bright rim of an air bubble under water.
* ``sceneThinFilm(cosIncident, thicknessNm, filmIor, outsideIor)``: the RGB reflectance of a thin film (a soap or oil
  layer) from two-beam interference with the phase shift of the film's inner reflection, sampled at seven
  wavelengths and folded into RGB with smooth spectral weights, so fringes run through the familiar magenta, gold,
  green and blue as the thickness or angle changes; 0 thickness gives no colour.
* ``sceneSphereRefraction(ray, normal, eta)``: the direction a ray leaves a homogeneous sphere after refracting in at
  its front surface (normal ``normal``) and out at the back, for consumers that bend what they see through a sphere
  (an air bubble in water diverges the view: the background through it appears shrunk); a ray totally reflected
  inside returns the in-sphere reflection instead.
* ``sceneSpherePaths(ray, normal, eta, reflected, transmitted, bounced)``: the three ways light reaches the eye from
  a homogeneous sphere at one point of its front surface, with their exact Fresnel weights (returned as
  (reflected, transmitted, bounced)): mirrored off the front surface (F, 1 past the critical angle: the mirror band
  round an air bubble in water), refracted in and out through the back (``(1-F)^2``), and refracted in, mirrored
  once off the inside of the back and refracted out (``(1-F)^2 F``: the bright inner arc of a glass ball). A
  consumer looks each direction up in its scene (a ``SceneProbe``) and sums them by weight; the rest of the light
  (further bounces) is under ``F^2`` and left out. By symmetry the back surface meets the ray at its entry angle, so
  one Fresnel serves every crossing.
* ``sceneHollowSphereTrace(origin, ray, outerRadius, innerRadius, iors, paths)``: a ray traced through a hollow
  sphere (a shell between two concentric spheres round the origin; ``iors`` = (outside, shell, core)), from an
  ``origin`` just outside it. At every interface the ray splits by exact Fresnel: the reflected share is handed back
  as a path (its direction, weight) and the refracted share is followed; past the critical angle the ray is totally
  reflected and followed without loss, so light that enters a glass wall near the silhouette is guided round inside
  it (the bright, warped band of a glass bubble) and the edge of the core shows as an inner line. The ray that
  finally leaves is the last path. Returns the number of paths (at most 8; ``paths[i].xyz`` direction, ``.w``
  weight; the weights sum to at most 1). A consumer looks each direction up in its scene (a ``SceneProbe``).
"""
from __future__ import annotations

import math

Vec3 = tuple[float, float, float]

# Seven wavelengths (nm) and their smooth RGB weights (each column sums to one over the samples).
_WAVELENGTHS = (440.0, 480.0, 520.0, 560.0, 600.0, 640.0, 680.0)
_WEIGHTS = ((0.06, 0.00, 0.62), (0.00, 0.10, 0.38), (0.00, 0.40, 0.00), (0.10, 0.38, 0.00),
            (0.32, 0.12, 0.00), (0.32, 0.00, 0.00), (0.20, 0.00, 0.00))

SCENE3D_OPTICS_GLSL = """
#ifndef SCENE3D_OPTICS_GLSL
#define SCENE3D_OPTICS_GLSL
float sceneFresnelDielectric(float cosIncident, float eta) {
    float c = clamp(cosIncident, 0.0, 1.0);
    float sinT2 = eta * eta * (1.0 - c * c);
    if (sinT2 >= 1.0) return 1.0;                       // total internal reflection
    float cosT = sqrt(1.0 - sinT2);
    float rs = (eta * c - cosT) / max(eta * c + cosT, 1e-6);
    float rp = (c - eta * cosT) / max(c + eta * cosT, 1e-6);
    return 0.5 * (rs * rs + rp * rp);
}
const float SCENE_FILM_WAVELENGTHS[7] = float[7](%s);
const vec3 SCENE_FILM_WEIGHTS[7] = vec3[7](%s);
vec3 sceneThinFilm(float cosIncident, float thicknessNm, float filmIor, float outsideIor) {
    float c = clamp(cosIncident, 0.0, 1.0);
    float sinT2 = (outsideIor / filmIor) * (outsideIor / filmIor) * (1.0 - c * c);
    float cosT = sqrt(max(1.0 - sinT2, 0.0));
    float r = sceneFresnelDielectric(c, outsideIor / filmIor);
    vec3 colour = vec3(0.0);
    for (int i = 0; i < 7; ++i) {
        // Path difference 2 n d cos(t); the inner reflection adds half a wave.
        float phase = 6.28318530718 * (2.0 * filmIor * thicknessNm * cosT / SCENE_FILM_WAVELENGTHS[i] + 0.5);
        float reflectance = 2.0 * r * (1.0 + cos(phase)) / max(1.0 + r * r + 2.0 * r * cos(phase), 1e-6);
        colour += SCENE_FILM_WEIGHTS[i] * reflectance;
    }
    return colour;
}
vec3 sceneSphereRefraction(vec3 ray, vec3 normal, float eta) {
    vec3 inside = refract(ray, normal, eta);
    if (dot(inside, inside) < 1e-8) return reflect(ray, normal);
    // The chord through the sphere is symmetric: leaving, the ray meets the surface at the angle it entered with.
    vec3 exitNormal = reflect(normal, inside);          // outward at the exit point
    vec3 leaving = refract(inside, -exitNormal, 1.0 / eta);
    return dot(leaving, leaving) < 1e-8 ? reflect(inside, -exitNormal) : leaving;
}
float sceneShellHit(vec3 o, vec3 d, float r) {
    float b = dot(o, d);
    float c = dot(o, o) - r * r;
    float h = b * b - c;
    if (h < 0.0) return -1.0;
    h = sqrt(h);
    float t0 = -b - h, t1 = -b + h;
    float eps = 1e-5 * r;
    return t0 > eps ? t0 : (t1 > eps ? t1 : -1.0);
}
int sceneHollowSphereTrace(vec3 origin, vec3 ray, float outerRadius, float innerRadius, vec3 iors, out vec4 paths[8]) {
    for (int i = 0; i < 8; ++i) paths[i] = vec4(0.0);
    vec3 o = origin, d = normalize(ray);
    int region = 0;                // 0 outside, 1 shell, 2 core
    float weight = 1.0;
    int count = 0;
    for (int step = 0; step < 12; ++step) {
        float tOuter = region <= 1 ? sceneShellHit(o, d, outerRadius) : -1.0;
        float tInner = region >= 1 && innerRadius > 0.0 ? sceneShellHit(o, d, innerRadius) : -1.0;
        if (region == 0 && tOuter < 0.0) break;
        bool inner = tInner > 0.0 && (tOuter < 0.0 || tInner < tOuter);
        float tHit = inner ? tInner : tOuter;
        if (tHit < 0.0) break;
        vec3 p = o + d * tHit;
        vec3 outward = normalize(p);
        bool entering = dot(d, outward) < 0.0;          // moving inward through this surface
        vec3 facing = entering ? outward : -outward;
        int next = inner ? (entering ? 2 : 1) : (entering ? 1 : 0);
        float n1 = region == 0 ? iors.x : (region == 1 ? iors.y : iors.z);
        float n2 = next == 0 ? iors.x : (next == 1 ? iors.y : iors.z);
        float eta = n1 / n2;
        float f = sceneFresnelDielectric(dot(-d, facing), eta);
        vec3 mirrored = reflect(d, facing);
        if (f >= 1.0) {                                  // totally reflected: followed without loss
            d = mirrored;
            o = p;
            continue;
        }
        if (count < 7) paths[count++] = vec4(mirrored, weight * f);
        weight *= 1.0 - f;
        d = normalize(refract(d, facing, eta));
        o = p;
        region = next;
        if (region == 0) break;
    }
    paths[count++] = vec4(d, weight);
    return count;
}
vec3 sceneSpherePaths(vec3 ray, vec3 normal, float eta, out vec3 reflected, out vec3 transmitted, out vec3 bounced) {
    float f = sceneFresnelDielectric(dot(-ray, normal), eta);
    reflected = reflect(ray, normal);
    vec3 inside = refract(ray, normal, eta);
    if (f >= 1.0 || dot(inside, inside) < 1e-8) {
        transmitted = reflected;
        bounced = reflected;
        return vec3(1.0, 0.0, 0.0);
    }
    inside = normalize(inside);
    vec3 exitNormal = reflect(normal, inside);                  // outward at the back
    transmitted = normalize(refract(inside, -exitNormal, 1.0 / eta));
    vec3 back = reflect(inside, exitNormal);                    // mirrored off the inside of the back
    vec3 secondNormal = reflect(exitNormal, back);
    bounced = normalize(refract(back, -secondNormal, 1.0 / eta));
    float t = 1.0 - f;
    return vec3(f, t * t, t * t * f);
}
#endif
""" % (", ".join(f"{w:.1f}" for w in _WAVELENGTHS), ", ".join(f"vec3({r:.2f}, {g:.2f}, {b:.2f})" for r, g, b in _WEIGHTS))


def scene3d_fresnel_dielectric(cos_incident: float, eta: float) -> float:
    """CPU mirror of ``sceneFresnelDielectric``."""
    c = max(0.0, min(1.0, cos_incident))
    sin_t2 = eta * eta * (1.0 - c * c)
    if sin_t2 >= 1.0:
        return 1.0
    cos_t = math.sqrt(1.0 - sin_t2)
    rs = (eta * c - cos_t) / max(eta * c + cos_t, 1e-6)
    rp = (c - eta * cos_t) / max(c + eta * cos_t, 1e-6)
    return 0.5 * (rs * rs + rp * rp)


def scene3d_thin_film(cos_incident: float, thickness_nm: float, film_ior: float, outside_ior: float) -> Vec3:
    """CPU mirror of ``sceneThinFilm``."""
    c = max(0.0, min(1.0, cos_incident))
    ratio = outside_ior / film_ior
    cos_t = math.sqrt(max(1.0 - ratio * ratio * (1.0 - c * c), 0.0))
    r = scene3d_fresnel_dielectric(c, ratio)
    colour = [0.0, 0.0, 0.0]
    for wavelength, weight in zip(_WAVELENGTHS, _WEIGHTS):
        phase = 2.0 * math.pi * (2.0 * film_ior * thickness_nm * cos_t / wavelength + 0.5)
        reflectance = 2.0 * r * (1.0 + math.cos(phase)) / max(1.0 + r * r + 2.0 * r * math.cos(phase), 1e-6)
        for channel in range(3):
            colour[channel] += weight[channel] * reflectance
    return colour[0], colour[1], colour[2]


def _refract(i, n, eta):
    d = sum(a * b for a, b in zip(n, i))
    k = 1.0 - eta * eta * (1.0 - d * d)
    if k < 0.0:
        return (0.0, 0.0, 0.0)
    s = eta * d + math.sqrt(k)
    return tuple(eta * a - s * b for a, b in zip(i, n))


def _reflect(i, n):
    d = sum(a * b for a, b in zip(n, i))
    return tuple(a - 2.0 * d * b for a, b in zip(i, n))


def _normalize(v):
    length = math.sqrt(sum(a * a for a in v))
    return tuple(a / length for a in v)


def _shell_hit(o, d, r):
    b = sum(a * c for a, c in zip(o, d))
    c = sum(a * a for a in o) - r * r
    h = b * b - c
    if h < 0.0:
        return -1.0
    h = math.sqrt(h)
    t0, t1 = -b - h, -b + h
    eps = 1e-5 * r
    return t0 if t0 > eps else (t1 if t1 > eps else -1.0)


def scene3d_hollow_sphere_trace(origin, ray, outer_radius, inner_radius, iors):
    """CPU mirror of ``sceneHollowSphereTrace``: a list of (direction, weight)."""
    o, d = tuple(origin), _normalize(ray)
    region, weight, paths = 0, 1.0, []
    for _step in range(12):
        t_outer = _shell_hit(o, d, outer_radius) if region <= 1 else -1.0
        t_inner = _shell_hit(o, d, inner_radius) if region >= 1 and inner_radius > 0.0 else -1.0
        if region == 0 and t_outer < 0.0:
            break
        inner = t_inner > 0.0 and (t_outer < 0.0 or t_inner < t_outer)
        t_hit = t_inner if inner else t_outer
        if t_hit < 0.0:
            break
        p = tuple(a + b * t_hit for a, b in zip(o, d))
        outward = _normalize(p)
        entering = sum(a * b for a, b in zip(d, outward)) < 0.0
        facing = outward if entering else tuple(-a for a in outward)
        nxt = (2 if entering else 1) if inner else (1 if entering else 0)
        eta = iors[region] / iors[nxt]
        f = scene3d_fresnel_dielectric(-sum(a * b for a, b in zip(d, facing)), eta)
        mirrored = _reflect(d, facing)
        if f >= 1.0:
            d, o = mirrored, p
            continue
        if len(paths) < 7:
            paths.append((mirrored, weight * f))
        weight *= 1.0 - f
        d, o, region = _normalize(_refract(d, facing, eta)), p, nxt
        if region == 0:
            break
    paths.append((d, weight))
    return paths


def scene3d_sphere_paths(ray, normal, eta):
    """CPU mirror of ``sceneSpherePaths``: ((F, T, B) weights, reflected, transmitted, bounced)."""
    f = scene3d_fresnel_dielectric(-sum(a * b for a, b in zip(ray, normal)), eta)
    reflected = _reflect(ray, normal)
    inside = _refract(ray, normal, eta)
    if f >= 1.0 or sum(a * a for a in inside) < 1e-8:
        return (1.0, 0.0, 0.0), reflected, reflected, reflected
    inside = _normalize(inside)
    exit_normal = _reflect(normal, inside)
    transmitted = _normalize(_refract(inside, tuple(-a for a in exit_normal), 1.0 / eta))
    back = _reflect(inside, exit_normal)
    second = _reflect(exit_normal, back)
    bounced = _normalize(_refract(back, tuple(-a for a in second), 1.0 / eta))
    t = 1.0 - f
    return (f, t * t, t * t * f), reflected, transmitted, bounced


__all__ = ["SCENE3D_OPTICS_GLSL", "scene3d_fresnel_dielectric", "scene3d_hollow_sphere_trace", "scene3d_sphere_paths",
           "scene3d_thin_film"]
