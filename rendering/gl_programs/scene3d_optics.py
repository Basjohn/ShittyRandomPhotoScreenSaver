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


__all__ = ["SCENE3D_OPTICS_GLSL", "scene3d_fresnel_dielectric", "scene3d_thin_film"]
