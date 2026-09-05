"""One static 3D mesh, deformed and lit from the authored Sphere snapshot."""

from __future__ import annotations

import ctypes
import math

import numpy as np
from OpenGL import GL as gl

from core.settings.shadow_direction import ShadowDirection, shadow_direction_signs
from rendering.quick.render.gl_resources import compile_program
from widgets.spotify_visualizer.render_state import SphereFrame

from ..render_contract import QuickVisualizerRenderFrame


# Reserve the canonical 280px height for every bounded deformation setting.
SPHERE_RADIUS_FRACTION = 0.245

_MATERIAL_IDS = {"Chrome": 0, "Obsidian": 1, "Magma": 2, "Silver": 3, "Water": 4}


def build_sphere_mesh(subdivisions: int = 4) -> np.ndarray:
    """Build outward unit triangles in bulk, only at first GL initialization."""
    if not 0 <= subdivisions <= 4:
        raise ValueError("Sphere subdivisions must be between zero and four")
    golden = (1.0 + math.sqrt(5.0)) * 0.5
    points = np.array((
        (-1, golden, 0), (1, golden, 0), (-1, -golden, 0), (1, -golden, 0),
        (0, -1, golden), (0, 1, golden), (0, -1, -golden), (0, 1, -golden),
        (golden, 0, -1), (golden, 0, 1), (-golden, 0, -1), (-golden, 0, 1),
    ), dtype=np.float32)
    points /= np.linalg.norm(points, axis=1, keepdims=True)
    faces = np.array((
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ), dtype=np.int32)
    triangles = points[faces]
    for _ in range(subdivisions):
        a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
        ab, bc, ca = a + b, b + c, c + a
        for midpoint in (ab, bc, ca):
            midpoint /= np.linalg.norm(midpoint, axis=1, keepdims=True)
        triangles = np.concatenate((np.stack((a, ab, ca), axis=1),
                                    np.stack((b, bc, ab), axis=1),
                                    np.stack((c, ca, bc), axis=1),
                                    np.stack((ab, bc, ca), axis=1)), axis=0)
    return np.ascontiguousarray(triangles.reshape(-1))


def sphere_pixel_geometry(presentation) -> tuple[float, float, float]:
    """Resolve Sphere geometry from the actual assigned content footprint.

    A CUSTOM viewport may represent a very large logical world at a small
    uniform scale.  The old canonical-height-times-scale metric then made the
    mesh microscopic even though its current visible content rectangle was
    perfectly usable.  Sphere is a presentation-local object, so derive one
    finite, isotropic pixel metric from that resolved rectangle.  Whole-scale
    edits change this rectangle and therefore the mesh; edge edits resize the object when they change the shorter content axis
    and otherwise change its available framing.
    """
    x, y, width, height = presentation.content_rect
    outer_x, outer_y, _, _ = presentation.outer_rect
    radius = min(width, height) * SPHERE_RADIUS_FRACTION
    return x - outer_x + width * 0.5, y - outer_y + height * 0.5, radius


def sphere_depth_scissor(frame: QuickVisualizerRenderFrame) -> tuple[int, int, int, int]:
    """Project the assigned viewport, independently of Qt's optional scissor.

    glClear ignores the stencil clip. Sphere therefore bounds its depth clear
    to the assigned rectangle before drawing into the existing stencil mask.
    Visualizer viewport transforms are translations and uniform scales; reject
    a future rotated/projective viewport until its depth ownership is designed.
    """
    p = frame.snapshot.presentation
    x, y, width, height = p.content_rect
    x -= p.outer_rect[0]
    y -= p.outer_rect[1]
    m = frame.matrix_values
    if abs(m[1]) > 1e-7 or abs(m[4]) > 1e-7 or abs(m[3]) > 1e-7 or abs(m[7]) > 1e-7:
        raise ValueError("Sphere depth viewport requires an axis-aligned transform")
    if abs(m[15]) < 1e-9:
        raise ValueError("Sphere depth viewport has an invalid homogeneous scale")
    vx, vy, vw, vh = frame.viewport
    xs = tuple(vx + ((m[0] * px + m[12]) / m[15] + 1.0) * vw * 0.5 for px in (x, x + width))
    ys = tuple(vy + ((m[5] * py + m[13]) / m[15] + 1.0) * vh * 0.5 for py in (y, y + height))
    left, right = max(vx, math.floor(min(xs))), min(vx + vw, math.ceil(max(xs)))
    bottom, top = max(vy, math.floor(min(ys))), min(vy + vh, math.ceil(max(ys)))
    return left, bottom, max(0, right - left), max(0, top - bottom)


_VERTEX_SOURCE = """#version 410 core
layout(location = 0) in vec3 aDirection;
uniform mat4 uMatrix;
uniform vec3 uGeometry;
uniform float uTime;
uniform vec3 uEnergy;
uniform float uDeformation;
uniform float uIdleMotion;
uniform float uRotationSpeed;
uniform vec3 uBandResponse;
uniform float uEnergyCurve;
uniform float uVocalResponse;
uniform float uSizePulse;
uniform int uMaterial;
out vec3 vPosition;
out vec3 vNormal;
out vec3 vObjectPosition;

vec3 surface(vec3 n) {
    float t = uTime * 0.7;
    float broad = sin(2.6*n.x + t) * cos(2.4*n.y - 0.7*t)
                * sin(2.1*n.z + 0.4*t);
    float lobes = sin(3.2*n.x - 0.8*t) * sin(2.8*n.y + t)
                * cos(3.0*n.z - 0.6*t);
    float ripples = sin(10.0*n.x - 2.0*t) * sin(9.0*n.y + 1.7*t)
                  * sin(8.0*n.z + t);
    // Smooth band transfer keeps ordinary music visible and remains responsive
    // at high settings. Never clamp the combined displacement: that clips the
    // moving lobes into a constant radius during a strong bass passage.
    vec3 drive = pow(clamp(uEnergy, 0.0, 1.0), vec3(max(uEnergyCurve, 0.05)))
                 * max(uBandResponse, vec3(0.0));
    vec3 e = vec3(1.0) - exp(-2.8 * drive);
    if (uMaterial == 4) {
        broad = sin(3.2*n.y + 1.4*sin(2.5*n.x - t)) * cos(2.0*n.z + 0.7*t);
        lobes = 0.5*(sin(4.0*n.x + 2.0*n.z - t) + cos(4.0*n.y + 1.3*t));
    } else if (uMaterial == 2) {
        broad = sin(2.8*n.y + 0.9*sin(3.0*n.x + 0.5*t)) * cos(2.0*n.z - t);
    } else if (uMaterial == 1) {
        lobes = sin(4.0*n.x + 0.7*t) * cos(4.0*n.y - 0.5*t);
    } else if (uMaterial == 3) {
        broad = sin(2.4*n.x + 0.8*t) * cos(3.0*n.y - 0.4*t);
    }
    float bassShape = 0.20 + 0.80 * broad;
    // Match the existing visualizer vocal-range weighting. This is frequency
    // emphasis, not a vocal-separation model or a second analysis lane.
    float vocalRange = dot(clamp(uEnergy.yz, 0.0, 1.0), vec2(0.62, 0.38));
    float vocal = 1.0 - exp(-2.8 * pow(vocalRange, max(uEnergyCurve, 0.05)) * uVocalResponse);
    float vocalShape = sin(2.6*n.y + 1.4*sin(2.2*n.x - 0.9*t))
                     * cos(2.0*n.z + 0.6*t);
    // Each field and each band is independently bounded by one. Their absolute
    // coefficients sum to .27, so max idle/audio/pulse radius is 1.84 while
    // every lobe remains free to evolve at maximum gain.
    float driven = e.x * 0.100 * bassShape + e.y * 0.035 * lobes
                 + e.z * 0.025 * ripples + vocal * 0.110 * vocalShape;
    float radius = 1.0 + uSizePulse + uIdleMotion * 0.10 * broad
        + uDeformation * driven;
    return n * radius;
}

mat3 rotation() {
    vec3 angle = uTime * uRotationSpeed * vec3(0.27, 0.65, 0.31);
    vec3 c = cos(angle), s = sin(angle);
    mat3 rx = mat3(1,0,0, 0,c.x,s.x, 0,-s.x,c.x);
    mat3 ry = mat3(c.y,0,-s.y, 0,1,0, s.y,0,c.y);
    mat3 rz = mat3(c.z,s.z,0, -s.z,c.z,0, 0,0,1);
    return rz * ry * rx;
}

void main() {
    vec3 n = normalize(aDirection);
    vec3 axis = abs(n.y) < 0.85 ? vec3(0,1,0) : vec3(1,0,0);
    vec3 tangent = normalize(cross(axis, n));
    vec3 bitangent = cross(n, tangent);
    vec3 p = surface(n);
    vec3 da = surface(normalize(n + 0.002*tangent)) - p;
    vec3 db = surface(normalize(n + 0.002*bitangent)) - p;
    mat3 turn = rotation();
    vNormal = turn * normalize(cross(da, db));
    vPosition = turn * p;
    vObjectPosition = p;
    // Real perspective with a common X/Y pixel metric. The homogeneous W
    // also makes position/normal interpolation perspective-correct.
    float cameraW = (4.6 - vPosition.z) / 4.6;
    vec2 local = uGeometry.xy * cameraW
               + vec2(vPosition.x, -vPosition.y) * uGeometry.z;
    gl_Position = uMatrix * vec4(local, 0.0, cameraW);
    gl_Position.z = (-vPosition.z / 3.0) * gl_Position.w;
}
"""

_EFFECT_VERTEX_SOURCE = """#version 410 core
layout(location = 0) in vec3 aDirection;
uniform mat4 uMatrix;
uniform vec3 uGeometry;
uniform float uTime;
uniform vec3 uEnergy;
uniform int uMaterial;
uniform float uFx;
uniform vec3 uLight;
uniform float uFade;
out vec3 vPosition;
out vec3 vNormal;
out float vAlpha;
out float vHeat;

float hash(float n) { return fract(sin(n * 91.17) * 43758.5453); }
vec3 teardropShape(vec3 n) {
    // The narrow pole is the upper attachment. The weighted lower pole makes
    // a falling drop bulbous below its neck, in y-up coordinates.
    float bulb = 1.0 - smoothstep(-0.15, 0.72, n.y);
    float neck = mix(0.34, 1.0, bulb);
    return vec3(n.x * neck, n.y * (1.05 + 0.35 * bulb), n.z * neck);
}
vec3 waterBlobShape(vec3 n, float id) {
    // Water leaves the surface as a rounded, irregular liquid volume. Its
    // low-order lobes avoid a pointed neck while retaining real 3D normals.
    float lobe = 1.0 + 0.10*sin(3.0*n.x + 1.7*n.z + id*1.31)
                 + 0.055*cos(4.0*n.y - 2.4*n.x + id*0.73);
    return n * lobe;
}
void main() {
    float id = float(gl_InstanceID);
    float seed = hash(id + 1.0);
    float a = seed * 6.2831853;
    // A particle may wrap in mathematical time, but it is fully transparent
    // at both ends of its finite life.  It therefore appears to condense from
    // the skin and retire rather than teleporting across the viewport.
    float phase = fract(uTime * mix(0.16, 0.28, hash(id + 3.0)) + hash(id + 7.0));
    float life = smoothstep(0.05, 0.17, phase) * (1.0 - smoothstep(0.80, 0.98, phase));
    bool magma = uMaterial == 2;
    float reactive = pow(clamp(max(uEnergy.x, max(uEnergy.y, uEnergy.z)), 0.0, 1.0), 0.60);
    float waterLane = mix(0.82, 1.04, hash(id + 11.0));
    float side = magma ? mix(-0.72, 0.72, hash(id + 11.0))
                       : (seed < 0.5 ? -waterLane : waterLane);
    float wobble = sin(uTime * (1.1 + hash(id + 5.0)) + id) * 0.055;
    // In y-up coordinates lava starts at the lower skin and falls. Water
    // sheds from the upper skin and falls farther, with x-separated lanes so
    // translucent drops do not rely on accidental depth ordering.
    float startY = magma ? -0.52 + 0.08 * hash(id + 13.0) : 0.58 + 0.11 * hash(id + 13.0);
    float fall = magma ? phase * 0.48 : phase * 1.32;
    vec3 center = vec3(side + wobble, startY - fall, 0.42 + 0.16 * sin(a + uTime * 0.47));
    float radius = mix(0.040, 0.078, hash(id + 19.0)) * (0.70 + 0.55 * reactive) * min(uFx, 2.0);
    vec3 n = normalize(aDirection);
    // Magma retains its attached teardrop neck; Water uses a distinct rounded
    // irregular volume so detached liquid does not read as another drip.
    vec3 particle = magma ? teardropShape(n) : waterBlobShape(n, id);
    vec3 scale = magma ? vec3(radius * 0.72, radius * 1.30, radius * 0.72)
                       : vec3(radius * 1.02, radius * 0.98, radius * 1.02);
    vec3 p = center + particle * scale;
    float cameraW = (4.6 - p.z) / 4.6;
    vec2 local = uGeometry.xy * cameraW + vec2(p.x, -p.y) * uGeometry.z;
    gl_Position = uMatrix * vec4(local, 0.0, cameraW);
    gl_Position.z = (-p.z / 3.0) * gl_Position.w;
    vPosition = p;
    // Both the non-affine lava neck and Water's lobed volume need normals
    // from their real finite tangents rather than an ellipsoid shortcut.
    vec3 axis = abs(n.y) < 0.85 ? vec3(0,1,0) : vec3(1,0,0);
    vec3 tangent = normalize(cross(axis, n));
    vec3 bitangent = cross(n, tangent);
    vec3 na = normalize(n + 0.002*tangent), nb = normalize(n + 0.002*bitangent);
    vec3 pa = magma ? teardropShape(na) : waterBlobShape(na, id);
    vec3 pb = magma ? teardropShape(nb) : waterBlobShape(nb, id);
    vec3 da = (pa - particle) * scale;
    vec3 db = (pb - particle) * scale;
    vNormal = normalize(cross(da, db));
    vAlpha = life * uFade;
    vHeat = reactive;
}
"""

_EFFECT_FRAGMENT_SOURCE = """#version 410 core
in vec3 vPosition;
in vec3 vNormal;
in float vAlpha;
in float vHeat;
uniform int uMaterial;
uniform vec3 uLight;
out vec4 fragColor;
void main() {
    vec3 n = normalize(vNormal);
    vec3 view = normalize(vec3(0,0,4.6) - vPosition);
    float diffuse = max(dot(n, uLight), 0.0);
    float fresnel = pow(1.0 - max(dot(n, view), 0.0), 4.0);
    float specular = pow(max(dot(n, normalize(view + uLight)), 0.0), 72.0);
    if (uMaterial == 2) {
        // Standard alpha compositing must receive the finite life/global fade;
        // otherwise an invisible newborn can still write depth as opaque lava.
        if (vAlpha < 0.004) discard;
        float crust = 0.46 + 0.54 * sin(31.0*vPosition.x + 19.0*vPosition.y
                                        - 17.0*vPosition.z + vHeat*4.0);
        crust = smoothstep(0.20, 0.78, crust);
        float hotCore = pow(max(0.0, 1.0 - abs(n.y + 0.20)), 2.0) * (1.0 - 0.42*crust);
        vec3 skin = mix(vec3(0.018, 0.003, 0.001), vec3(0.18, 0.018, 0.002), 1.0-crust);
        vec3 core = mix(vec3(0.85, 0.055, 0.002), vec3(1.0, 0.56, 0.045), hotCore);
        vec3 color = skin * (0.18 + 0.72*diffuse) + core * (0.35 + hotCore*1.05)
                   + vec3(1.0, 0.62, 0.24) * specular * (0.32 + 0.48*hotCore);
        fragColor = vec4(color, vAlpha);
    } else {
        vec3 transmitted = mix(vec3(0.006, 0.055, 0.09), vec3(0.05, 0.52, 0.68), 0.35 + 0.45*diffuse);
        vec3 color = transmitted * (0.55 + 0.65*diffuse)
                   + vec3(0.42, 0.91, 1.0) * fresnel
                   + vec3(0.95, 1.0, 1.0) * specular * 1.35;
        fragColor = vec4(color, min(0.70, (0.22 + 0.42*fresnel) * vAlpha));
    }
}
"""

_FIRE_VERTEX_SOURCE = """#version 410 core
layout(location = 0) in vec2 aCorner;
uniform mat4 uMatrix;
uniform vec3 uGeometry;
uniform float uTime;
uniform vec3 uEnergy;
uniform float uFx;
uniform float uFade;
uniform int uEffectPass;
out vec2 vUv;
out float vLife;
out float vHeat;
float hash(float n) { return fract(sin(n * 91.17) * 43758.5453); }
void main() {
    float id = float(gl_InstanceID);
    float phase = fract(uTime * mix(0.31, 0.53, hash(id + 3.0)) + hash(id + 7.0));
    float life = smoothstep(0.03, 0.17, phase) * (1.0 - smoothstep(0.68, 0.96, phase));
    float heat = pow(clamp(max(uEnergy.x, max(uEnergy.y, uEnergy.z)), 0.0, 1.0), 0.55);
    float lane = mix(0.68, 0.94, hash(id + 11.0));
    float side = hash(id + 11.0) < 0.5 ? -lane : lane;
    // Warm clouds rise above the enlarged reactive body silhouette rather
    // than spending their visible life occluded inside it.
    float y = 0.78 + phase * 0.36;
    float width = mix(0.045, 0.090, hash(id + 17.0)) * (0.70 + 0.60*heat) * min(uFx, 2.0);
    // Broad cloud volumes stay diffuse throughout their life. At FX=2 width
    // <= .234, height <= .386 and their upper extent remains below 1.21.
    float height = width * mix(0.95, 1.65, hash(id + 19.0)) * (0.85 + 0.15*(1.0 - phase));
    if (uEffectPass == 0) {
        // Four smoke wisps grow as they ascend but their coupled drift keeps
        // every corner below 1.31 at FX=2.
        phase = fract(uTime * mix(0.10, 0.17, hash(id + 23.0)) + hash(id + 29.0));
        life = smoothstep(0.04, 0.20, phase) * (1.0 - smoothstep(0.72, 0.98, phase));
        float smokeSize = mix(0.08, 0.12, hash(id + 31.0)) * (0.75 + 0.55*heat) * min(uFx, 2.0);
        side = mix(-0.85, 0.85, hash(id + 37.0));
        y = 0.90 + phase * 0.32;
        width = smokeSize;
        height = smokeSize * (0.72 + 0.46*phase);
    } else if (uEffectPass == 1) {
        // Six small ash/ember flakes rise inside a finite 1.20 envelope.
        phase = fract(uTime * mix(0.24, 0.41, hash(id + 41.0)) + hash(id + 43.0));
        life = smoothstep(0.03, 0.14, phase) * (1.0 - smoothstep(0.76, 0.98, phase));
        side = mix(-0.82, 0.82, hash(id + 47.0));
        y = 0.76 + phase * 0.44;
        width = mix(0.012, 0.027, hash(id + 53.0)) * (0.75 + 0.45*heat) * min(uFx, 2.0);
        height = width * mix(0.65, 1.35, hash(id + 59.0));
    }
    vec3 p = vec3(side + sin(uTime*(1.3+hash(id+5.0))+id)*0.055 + aCorner.x*width,
                  y + aCorner.y*height, 0.30 + 0.12*sin(id + uTime));
    float cameraW = (4.6 - p.z) / 4.6;
    vec2 local = uGeometry.xy * cameraW + vec2(p.x, -p.y) * uGeometry.z;
    gl_Position = uMatrix * vec4(local, 0.0, cameraW);
    gl_Position.z = (-p.z / 3.0) * gl_Position.w;
    vUv = aCorner;
    vLife = life * uFade;
    vHeat = heat;
}
"""

_FIRE_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
in float vLife;
in float vHeat;
uniform float uTime;
uniform int uEffectPass;
out vec4 fragColor;
void main() {
    // Warm fire is a diffuse turbulent volume, not a pointed icon. Every
    // cloud remains inside its finite quad and fades before its edges.
    float taper = 1.0 - smoothstep(-0.82, 0.82, vUv.y);
    float warpedX = vUv.x + 0.12*sin(uTime*5.3 + vUv.y*7.0)*taper;
    if (uEffectPass == 0) {
        // Filter the procedural wisp with its real fragment footprint so the
        // soft grey plume cannot turn into a hard noisy billboard at scale.
        float radial = dot(vUv, vUv * vec2(0.72, 1.15));
        float noise = sin(12.0*warpedX + 4.0*uTime) * sin(9.0*vUv.y - 3.0*uTime);
        float filtered = 0.5 + 0.5 * noise * (1.0 - smoothstep(0.10, 0.85, fwidth(noise)*8.0));
        float alpha = (1.0-smoothstep(0.18, 0.92, radial)) * (0.58 + 0.30*filtered) * vLife;
        if (alpha < 0.004) discard;
        vec3 smoke = mix(vec3(0.18,0.16,0.14), vec3(0.58,0.53,0.46), filtered);
        fragColor = vec4(smoke, alpha);
        return;
    }
    if (uEffectPass == 1) {
        float flake = 1.0-smoothstep(0.18, 0.82, length(vUv));
        float ember = smoothstep(0.64, 0.92, sin(uTime*4.0 + vUv.x*13.0 + vUv.y*7.0));
        float alpha = flake * vLife * (0.34 + 0.44*ember);
        if (alpha < 0.004) discard;
        fragColor = vec4(mix(vec3(0.028,0.018,0.012), vec3(0.58,0.13,0.012), ember), alpha);
        return;
    }
    float warpedY = vUv.y + 0.10*sin(uTime*3.7 - warpedX*8.0);
    float cloudRadius = dot(vec2(warpedX*0.82, warpedY*0.68), vec2(warpedX*0.82, warpedY*0.68));
    float turbulence = sin(8.0*warpedX + 3.0*uTime) * sin(7.0*warpedY - 2.0*uTime);
    float filteredTurbulence = turbulence * (1.0 - smoothstep(0.10, 0.85, fwidth(turbulence)*7.0));
    float edge = 1.0 - smoothstep(0.70, 0.98, max(abs(vUv.x), abs(vUv.y)));
    float halo = exp(-2.6*cloudRadius) * edge;
    float innerHeat = exp(-9.0*cloudRadius) * (0.72 + 0.28*filteredTurbulence);
    float alpha = halo * (0.11 + 0.10*max(filteredTurbulence, 0.0)) * vLife;
    if (alpha < 0.004) discard;
    vec3 color = mix(vec3(0.52, 0.055, 0.006), vec3(1.0, 0.72, 0.14), innerHeat)
               * (0.58 + 0.46*vHeat);
    fragColor = vec4(color, alpha);
}
"""

_FRAGMENT_SOURCE = """#version 410 core
in vec3 vPosition;
in vec3 vNormal;
in vec3 vObjectPosition;
uniform vec3 uLight;
uniform float uGloss;
uniform float uSpecular;
uniform int uMaterial;
uniform float uFade;
uniform float uSurfaceDetail;
uniform float uBumpReactivity;
uniform vec3 uEnergy;
uniform float uEnergyCurve;
uniform float uTime;
out vec4 fragColor;

float grain(vec3 p) {
    return sin(p.x + sin(1.17*p.y)) * sin(p.y + sin(0.83*p.z))
           * sin(p.z + sin(0.91*p.x));
}
float filteredGrain(vec3 p, float frequency, float footprint) {
    return grain(p * frequency) * (1.0 - smoothstep(0.8, 2.2, footprint * frequency));
}
vec3 bumpedNormal(vec3 normal, float height) {
    // Surface-gradient bump mapping follows the deformed object, with screen
    // derivatives providing the actual local metric. No UV poles or texture seam.
    vec3 dpdx = dFdx(vPosition), dpdy = dFdy(vPosition);
    vec3 r1 = cross(dpdy, normal), r2 = cross(normal, dpdx);
    float determinant = dot(dpdx, r1);
    vec3 gradient = sign(determinant) * (dFdx(height)*r1 + dFdy(height)*r2)
                    / max(abs(determinant), 0.0000001);
    gradient /= max(1.0, length(gradient) / 1.5);
    return normalize(normal - gradient);
}
void main() {
    vec3 p = vObjectPosition;
    float footprint = max(length(dFdx(p)), length(dFdy(p)));
    float mediumGrain = filteredGrain(p, 36.0, footprint);
    float fineGrain = filteredGrain(p + vec3(0.3,1.7,2.1), 93.0, footprint);
    float cracks = abs(sin(9.0*p.x + 2.4*sin(5.0*p.z) + grain(p*7.0))
                     + sin(8.0*p.y - 1.8*sin(6.0*p.x)));
    float crackAA = max(fwidth(cracks), 0.012);
    float crust = smoothstep(0.06-crackAA, 0.28+crackAA, cracks);
    float height, roughness;
    if (uMaterial == 0) {
        float brush = sin(410.0*p.y + 4.0*grain(p*14.0))
                    * (1.0-smoothstep(0.8,2.2,footprint*410.0));
        float machining = filteredGrain(p + vec3(0.6,0.2,0.0), 14.0, footprint);
        height = 0.0008*brush + 0.0011*fineGrain + 0.0024*machining;
        roughness = 0.10 + 0.05*fineGrain + 0.04*machining;
    } else if (uMaterial == 1) {
        height = 0.009*mediumGrain + 0.002*fineGrain + 0.013*crust;
        roughness = mix(0.12, 0.48, crust) + 0.08*mediumGrain;
    } else if (uMaterial == 2) {
        height = 0.043*crust + crust*(0.010*mediumGrain + 0.003*fineGrain);
        roughness = mix(0.12,0.85,crust);
    } else if (uMaterial == 4) {
        float wave = sin(14.0*p.x + 9.0*p.y - uTime*0.85 + 0.7*sin(11.0*p.z+uTime))
                   + 0.45*sin(23.0*p.z - 11.0*p.x + uTime*0.64);
        height = 0.018*wave + 0.003*mediumGrain;
        roughness = 0.06;
    } else {
        height = 0.004*mediumGrain + 0.0012*fineGrain;
        roughness = 0.22 + 0.10*fineGrain;
    }
    float bumpBand = dot(clamp(uEnergy, 0.0, 1.0), vec3(0.20, 0.60, 0.20));
    float bumpDrive = 1.0 - exp(-2.8 * pow(bumpBand, max(uEnergyCurve, 0.05)));
    float bumpStrength = uSurfaceDetail * (1.0 + 0.75*uBumpReactivity*bumpDrive);
    vec3 n = bumpedNormal(normalize(vNormal), height * bumpStrength);
    vec3 view = normalize(vec3(0,0,4.6) - vPosition);
    vec3 reflection = reflect(-view, n);
    float diffuse = max(dot(n, uLight), 0.0);
    float fresnel = pow(1.0 - max(dot(n, view), 0.0), 3.5);
    float gloss = clamp(uGloss*(1.0 - roughness*.7), 0.0, 1.0);
    float highlight = pow(max(dot(n, normalize(view + uLight)), 0.0),
                          mix(18.0, 240.0, gloss)) * uSpecular;
    // A dark studio horizon and two softboxes make rotating dents/bulges legible.
    float panel = pow(max(dot(reflection, normalize(vec3(-0.8,1.1,0.7))), 0.0),
                      mix(8.0, 48.0, gloss));
    float rimPanel = pow(max(dot(reflection, normalize(vec3(1.0,0.2,-0.15))), 0.0), 22.0);
    float horizon = smoothstep(-0.12, 0.12, reflection.y);
    vec3 studio = mix(vec3(0.008,0.014,0.026), vec3(0.14,0.20,0.27), horizon);
    float strip = exp(-pow((reflection.x + 0.38) * 10.0, 2.0))
                * smoothstep(-0.35, 0.5, reflection.y);
    studio += panel * vec3(1.1,1.18,1.28) + rimPanel * vec3(0.35,0.5,0.7)
            + strip * vec3(0.7,0.82,1.0);
    vec3 color;
    float alpha = uFade;
    if (uMaterial == 1) {
        float stone = 0.75 + 0.25*mediumGrain;
        float fracture = 1.0 - smoothstep(0.05, 0.15+crackAA, cracks);
        color = vec3(0.004,0.003,0.009) * (0.3 + diffuse) * stone
              + studio * (0.12 + 0.06*stone) + vec3(0.065,0.035,0.12) * fresnel
              + vec3(0.022,0.013,0.042) * fracture * (0.3+fresnel);
        highlight *= 0.65;
    } else if (uMaterial == 2) {
        float flow = 0.65 + 0.35*grain(p*24.0 + vec3(0,uTime*1.8,0));
        float fire = 1.0-crust;
        float core = 1.0-smoothstep(0.015,0.075+crackAA,cracks);
        float hotEdge = exp(-cracks*5.0);
        color = vec3(0.009,0.006,0.005) * (0.35+diffuse) * (0.75+0.25*mediumGrain)
              + fire*flow*vec3(3.0,0.35,0.004) + core*vec3(1.9,1.0,0.10)
              + hotEdge*vec3(0.16,0.009,0.001)
              + studio*0.035*crust;
        highlight *= mix(0.8,0.08,crust);
    } else if (uMaterial == 4) {
        float waterField = grain(p*13.0 + vec3(0,uTime*.3,0))
                         + 0.35*grain(p*26.0 - vec3(uTime*.2,0,0));
        float caustic = exp(-abs(waterField)*15.0);
        color = studio * vec3(0.32,0.75,1.0) * (0.35+1.7*fresnel)
              + vec3(0.005,0.055,0.10)*(0.35+diffuse) + caustic*vec3(0.05,0.24,0.29);
        // Transmission through the single front surface leaves the real scene
        // visible at the centre; Fresnel and highlights define the liquid edge.
        alpha *= clamp(0.18 + 0.64*fresnel + 0.12*highlight, 0.18, 0.94);
        highlight *= 1.7;
    } else if (uMaterial == 3) {
        color = vec3(0.22,0.245,0.28) * (0.17+0.75*diffuse)
              + studio*0.50 + fresnel*vec3(0.10,0.13,0.19);
    } else {
        color = studio * (0.85+0.15*diffuse) + vec3(0.06,0.10,0.17)*fresnel;
    }
    color += vec3(1.0,0.96,0.89)*highlight;
    color = pow(color / (vec3(1.0)+color), vec3(1.0/2.2));
    fragColor = vec4(color, alpha);
}
"""


class QuickSphereRenderer:
    mode_id = "sphere"

    def __init__(self) -> None:
        self._program = self._vao = self._vbo = self._vertex_count = 0
        self._effect_program = 0
        self._effect_uniforms: dict[str, int] = {}
        self._effect_vao = self._effect_vbo = self._effect_vertex_count = 0
        self._fire_program = self._fire_vao = self._fire_vbo = 0
        self._fire_uniforms: dict[str, int] = {}
        self._ready = False
        self._uniforms: dict[str, int] = {}
        self._parameters = None
        self._light = (0.0, 0.0, 1.0)
        self._material = 0

    @property
    def has_resources(self) -> bool:
        return bool(self._program or self._vao or self._vbo or self._effect_program
                    or self._effect_vao or self._effect_vbo or self._fire_program
                    or self._fire_vao or self._fire_vbo)

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        state = frame.snapshot.logical.mode_state
        if not isinstance(state, SphereFrame):
            raise TypeError("Sphere renderer received another mode frame")
        if not self._ready:
            self._initialize()
        parameters = state.parameters
        if parameters != self._parameters:
            material = parameters.get("sphere_material", "Chrome")
            if material not in _MATERIAL_IDS:
                raise ValueError(f"unknown Sphere material: {material!r}")
            direction = ShadowDirection(parameters.get("sphere_light_direction", "NW"))
            x, y = shadow_direction_signs(direction)
            length = math.sqrt(x*x + y*y + 2.25)
            self._light = (x / length, -y / length, 1.5 / length)
            self._material = _MATERIAL_IDS[material]
            self._parameters = parameters
        u = self._uniforms
        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(u["uMatrix"], 1, False, frame.matrix_values)
        gl.glUniform3f(u["uGeometry"], *sphere_pixel_geometry(frame.snapshot.presentation))
        gl.glUniform1f(u["uTime"], state.authored_time)
        energy = frame.snapshot.logical.common.energy
        gl.glUniform3f(u["uEnergy"], *(max(0.0, min(1.0, value)) for value in
                                      (energy.bass, energy.mid, energy.high)))
        gl.glUniform3f(
            u["uBandResponse"],
            *(float(parameters.get(key, 1.0)) for key in (
                "sphere_bass_response", "sphere_mid_response", "sphere_high_response"
            )),
        )
        gl.glUniform1f(u["uEnergyCurve"], float(parameters.get("sphere_energy_curve", 0.60)))
        gl.glUniform1f(u["uVocalResponse"], float(parameters.get("sphere_vocal_response", 1.4)))
        # The shared transient bus already owns attack/decay. Read its immutable
        # envelope directly; the render callback adds no clock or mutable filter.
        transient = frame.snapshot.logical.common.transient
        pulse_drive = max(0.0, min(1.0, max(
            energy.overall * 0.25, energy.bass * 0.35,
            transient.bass, transient.mid, transient.high,
        )))
        size_pulse = (0.10 * float(parameters.get("sphere_size_response", 1.5))
                      * pulse_drive ** float(parameters.get("sphere_energy_curve", 0.60)))
        gl.glUniform1f(u["uSizePulse"], size_pulse)
        for uniform, key, default in (
            ("uDeformation", "sphere_deformation", 1.0),
            ("uSurfaceDetail", "sphere_surface_detail", 1.15),
            ("uBumpReactivity", "sphere_bump_reactivity", 0.65),
            ("uIdleMotion", "sphere_idle_motion", 0.12),
            ("uRotationSpeed", "sphere_rotation_speed", 0.35),
            ("uGloss", "sphere_gloss", 0.65),
            ("uSpecular", "sphere_specular", 0.8),
        ):
            gl.glUniform1f(u[uniform], float(parameters.get(key, default)))
        gl.glUniform3f(u["uLight"], *self._light)
        gl.glUniform1i(u["uMaterial"], self._material)
        p = frame.snapshot.presentation
        gl.glUniform1f(u["uFade"], p.scene_fade * p.content_fade)
        previous_function = int(gl.glGetIntegerv(gl.GL_DEPTH_FUNC))
        previous_clear = float(gl.glGetDoublev(gl.GL_DEPTH_CLEAR_VALUE))
        previous_cull_face = int(gl.glGetIntegerv(gl.GL_CULL_FACE_MODE))
        previous_front_face = int(gl.glGetIntegerv(gl.GL_FRONT_FACE))
        previous_scissor_enabled = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        previous_scissor = tuple(int(value) for value in gl.glGetIntegerv(gl.GL_SCISSOR_BOX))
        left, bottom, width, height = sphere_depth_scissor(frame)
        if previous_scissor_enabled:
            sx, sy, sw, sh = previous_scissor
            right, top = min(left + width, sx + sw), min(bottom + height, sy + sh)
            left, bottom = max(left, sx), max(bottom, sy)
            width, height = max(0, right - left), max(0, top - bottom)
        try:
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(left, bottom, width, height)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDepthFunc(gl.GL_LESS)
            # Water blends only the visible surface. Back faces must not add
            # order-dependent opacity; the common host restores cull enable.
            gl.glEnable(gl.GL_CULL_FACE)
            gl.glCullFace(gl.GL_BACK)
            gl.glFrontFace(gl.GL_CW if frame.matrix_values[0] * frame.matrix_values[5] > 0 else gl.GL_CCW)
            gl.glClearDepth(1.0)
            gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
            gl.glBindVertexArray(self._vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._vertex_count)
            if self._material in (_MATERIAL_IDS["Magma"], _MATERIAL_IDS["Water"]):
                fx = max(0.0, min(2.0, float(parameters.get("sphere_material_fx", 1.0))))
                if fx > 0.0:
                    self._render_effects(frame, state.authored_time, energy, fx)
        finally:
            # The common host restores enable/write; these are Sphere-only state.
            gl.glDepthFunc(previous_function)
            gl.glClearDepth(previous_clear)
            gl.glCullFace(previous_cull_face)
            gl.glFrontFace(previous_front_face)
            gl.glScissor(*previous_scissor)
            if not previous_scissor_enabled:
                gl.glDisable(gl.GL_SCISSOR_TEST)

    def _initialize(self) -> None:
        # A failed allocation/cleanup retains its IDs for retry. Never overwrite
        # them with fresh resources on a later render attempt.
        if self.has_resources:
            self.release_resources()
        self._program = compile_program(_VERTEX_SOURCE, _FRAGMENT_SOURCE, label="Quick Sphere")
        try:
            names = ("uMatrix", "uGeometry", "uTime", "uEnergy", "uDeformation",
                     "uIdleMotion", "uRotationSpeed", "uLight", "uGloss", "uSpecular",
                     "uMaterial", "uFade", "uSurfaceDetail", "uBumpReactivity", "uBandResponse", "uEnergyCurve", "uVocalResponse", "uSizePulse")
            self._uniforms = {name: int(gl.glGetUniformLocation(self._program, name)) for name in names}
            missing = [name for name, location in self._uniforms.items() if location < 0]
            if missing:
                raise RuntimeError("Quick Sphere uniforms are incomplete: " + ", ".join(missing))
            mesh = build_sphere_mesh()
            self._vertex_count = len(mesh) // 3
            self._vao = int(gl.glGenVertexArrays(1))
            self._vbo = int(gl.glGenBuffers(1))
            if not self._vao or not self._vbo:
                raise RuntimeError("Quick Sphere mesh creation failed")
            gl.glBindVertexArray(self._vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, len(mesh) * mesh.itemsize, mesh.tobytes(), gl.GL_STATIC_DRAW)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, False, 12, ctypes.c_void_p(0))
            self._ready = True
        except Exception:
            self.release_resources()
            raise

    def _discard_effect_resources(self) -> None:
        """Retire an incomplete lazy effect allocation before its next retry."""
        for attribute, deleter in (
            ("_fire_vbo", lambda resource: gl.glDeleteBuffers(1, [resource])),
            ("_fire_vao", lambda resource: gl.glDeleteVertexArrays(1, [resource])),
            ("_fire_program", gl.glDeleteProgram),
            ("_effect_vbo", lambda resource: gl.glDeleteBuffers(1, [resource])),
            ("_effect_vao", lambda resource: gl.glDeleteVertexArrays(1, [resource])),
            ("_effect_program", gl.glDeleteProgram),
        ):
            resource = getattr(self, attribute)
            if resource:
                try:
                    deleter(resource)
                except Exception:
                    # The body release path reports final teardown failures;
                    # a failed lazy allocation must still forget every partial
                    # handle so a later render can make a clean retry.
                    pass
                finally:
                    setattr(self, attribute, 0)
        self._effect_uniforms.clear()
        self._fire_uniforms.clear()
        self._effect_vertex_count = 0

    def _ensure_effect_resources(self) -> None:
        """Create effect-only immutable meshes lazily in the owning GL context."""
        if not self._effect_program:
            self._effect_program = compile_program(_EFFECT_VERTEX_SOURCE, _EFFECT_FRAGMENT_SOURCE, label="Quick Sphere effects")
            names = ("uMatrix", "uGeometry", "uTime", "uEnergy", "uMaterial", "uFx", "uLight", "uFade")
            self._effect_uniforms = {name: int(gl.glGetUniformLocation(self._effect_program, name)) for name in names}
            missing = [name for name, location in self._effect_uniforms.items() if location < 0]
            if missing:
                raise RuntimeError("Quick Sphere effect uniforms are incomplete: " + ", ".join(missing))
        if not self._effect_vao:
            # 320 triangles are smooth enough at FX=2 but are a bounded static
            # cost, replacing eight copies of the 5,120-triangle body mesh.
            mesh = build_sphere_mesh(2)
            self._effect_vertex_count = len(mesh) // 3
            self._effect_vao = int(gl.glGenVertexArrays(1))
            self._effect_vbo = int(gl.glGenBuffers(1))
            if not self._effect_vao or not self._effect_vbo:
                raise RuntimeError("Quick Sphere effect mesh creation failed")
            gl.glBindVertexArray(self._effect_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._effect_vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, len(mesh) * mesh.itemsize, mesh.tobytes(), gl.GL_STATIC_DRAW)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, False, 12, ctypes.c_void_p(0))
        if self._material == _MATERIAL_IDS["Magma"] and not self._fire_program:
            self._fire_program = compile_program(_FIRE_VERTEX_SOURCE, _FIRE_FRAGMENT_SOURCE, label="Quick Sphere fire")
            names = ("uMatrix", "uGeometry", "uTime", "uEnergy", "uFx", "uFade", "uEffectPass")
            self._fire_uniforms = {name: int(gl.glGetUniformLocation(self._fire_program, name)) for name in names}
            missing = [name for name, location in self._fire_uniforms.items() if location < 0]
            if missing:
                raise RuntimeError("Quick Sphere fire uniforms are incomplete: " + ", ".join(missing))
            corners = np.array((
                -1.0, -1.0,  1.0, -1.0,  1.0,  1.0,
                -1.0, -1.0,  1.0,  1.0, -1.0,  1.0,
            ), dtype=np.float32)
            self._fire_vao = int(gl.glGenVertexArrays(1))
            self._fire_vbo = int(gl.glGenBuffers(1))
            if not self._fire_vao or not self._fire_vbo:
                raise RuntimeError("Quick Sphere fire mesh creation failed")
            gl.glBindVertexArray(self._fire_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._fire_vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, len(corners) * corners.itemsize, corners.tobytes(), gl.GL_STATIC_DRAW)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, False, 8, ctypes.c_void_p(0))

    def _render_effects(self, frame: QuickVisualizerRenderFrame, authored_time: float, energy, fx: float) -> None:
        """Draw finite falling drops and Magma's separate rising soft flames."""
        try:
            self._ensure_effect_resources()
        except Exception:
            # A uniform/mesh/fire allocation failure must not leave a partial
            # program marked ready; the next owning-context frame retries from
            # a complete, known-empty effect resource set.
            self._discard_effect_resources()
            raise
        u = self._effect_uniforms
        gl.glUseProgram(self._effect_program)
        gl.glUniformMatrix4fv(u["uMatrix"], 1, False, frame.matrix_values)
        gl.glUniform3f(u["uGeometry"], *sphere_pixel_geometry(frame.snapshot.presentation))
        gl.glUniform1f(u["uTime"], authored_time)
        gl.glUniform3f(u["uEnergy"], *(max(0.0, min(1.0, value)) for value in (energy.bass, energy.mid, energy.high)))
        gl.glUniform1i(u["uMaterial"], self._material)
        gl.glUniform1f(u["uFx"], fx)
        gl.glUniform3f(u["uLight"], *self._light)
        p = frame.snapshot.presentation
        gl.glUniform1f(u["uFade"], p.scene_fade * p.content_fade)
        old_src_rgb, old_dst_rgb = int(gl.glGetIntegerv(gl.GL_BLEND_SRC_RGB)), int(gl.glGetIntegerv(gl.GL_BLEND_DST_RGB))
        old_src_alpha, old_dst_alpha = int(gl.glGetIntegerv(gl.GL_BLEND_SRC_ALPHA)), int(gl.glGetIntegerv(gl.GL_BLEND_DST_ALPHA))
        old_depth_write = bool(gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK))
        old_blend_enabled = bool(gl.glIsEnabled(gl.GL_BLEND))
        old_cull_enabled = bool(gl.glIsEnabled(gl.GL_CULL_FACE))
        try:
            gl.glBindVertexArray(self._effect_vao)
            if self._material == _MATERIAL_IDS["Magma"]:
                # Lit lava uses normal alpha so lifecycle/content fades reach
                # the framebuffer. Its front surface still owns depth.
                gl.glEnable(gl.GL_CULL_FACE)
                gl.glCullFace(gl.GL_BACK)
                gl.glEnable(gl.GL_BLEND)
                gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA,
                                       gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, self._effect_vertex_count, 6)
                fu = self._fire_uniforms
                gl.glUseProgram(self._fire_program)
                gl.glUniformMatrix4fv(fu["uMatrix"], 1, False, frame.matrix_values)
                gl.glUniform3f(fu["uGeometry"], *sphere_pixel_geometry(frame.snapshot.presentation))
                gl.glUniform1f(fu["uTime"], authored_time)
                gl.glUniform3f(fu["uEnergy"], *(max(0.0, min(1.0, value)) for value in (energy.bass, energy.mid, energy.high)))
                gl.glUniform1f(fu["uFx"], fx)
                gl.glUniform1f(fu["uFade"], p.scene_fade * p.content_fade)
                # Smoke and ash are ordinary translucent material layers. They
                # draw before the bright additive flame without allocating any
                # extra particle data or changing the body depth buffer.
                gl.glEnable(gl.GL_BLEND)
                # Only camera-facing billboards need two-sided rasterization.
                gl.glDisable(gl.GL_CULL_FACE)
                gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA,
                                       gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
                gl.glDepthMask(gl.GL_FALSE)
                gl.glBindVertexArray(self._fire_vao)
                gl.glUniform1i(fu["uEffectPass"], 0)
                gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, 6, 4)
                gl.glUniform1i(fu["uEffectPass"], 1)
                gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, 6, 6)
                gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
                gl.glUniform1i(fu["uEffectPass"], 2)
                gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, 6, 10)
            else:
                # Water lanes are deliberately separated; standard alpha plus
                # no depth writes preserves their translucent front surfaces.
                gl.glEnable(gl.GL_CULL_FACE)
                gl.glCullFace(gl.GL_BACK)
                gl.glEnable(gl.GL_BLEND)
                gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA,
                                       gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
                gl.glDepthMask(gl.GL_FALSE)
                gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, self._effect_vertex_count, 6)
        finally:
            gl.glBlendFuncSeparate(old_src_rgb, old_dst_rgb, old_src_alpha, old_dst_alpha)
            gl.glDepthMask(gl.GL_TRUE if old_depth_write else gl.GL_FALSE)
            if old_blend_enabled:
                gl.glEnable(gl.GL_BLEND)
            else:
                gl.glDisable(gl.GL_BLEND)
            if old_cull_enabled:
                gl.glEnable(gl.GL_CULL_FACE)
            else:
                gl.glDisable(gl.GL_CULL_FACE)

    def release_resources(self) -> None:
        self._ready = False
        errors = []
        for attribute, deleter in (
            ("_fire_vbo", lambda resource: gl.glDeleteBuffers(1, [resource])),
            ("_fire_vao", lambda resource: gl.glDeleteVertexArrays(1, [resource])),
            ("_fire_program", gl.glDeleteProgram),
            ("_effect_vbo", lambda resource: gl.glDeleteBuffers(1, [resource])),
            ("_effect_vao", lambda resource: gl.glDeleteVertexArrays(1, [resource])),
            ("_effect_program", gl.glDeleteProgram),
            ("_vbo", lambda resource: gl.glDeleteBuffers(1, [resource])),
            ("_vao", lambda resource: gl.glDeleteVertexArrays(1, [resource])),
            ("_program", gl.glDeleteProgram),
        ):
            resource = getattr(self, attribute)
            if resource:
                try:
                    deleter(resource)
                except Exception as exc:
                    errors.append(f"{attribute}: {exc}")
                else:
                    setattr(self, attribute, 0)
        if not errors:
            self._uniforms.clear()
            self._effect_uniforms.clear()
            self._fire_uniforms.clear()
            self._vertex_count = 0
            self._effect_vertex_count = 0
        if errors:
            raise RuntimeError("Quick Sphere cleanup incomplete: " + " | ".join(errors))


def create_visualizer_renderer() -> QuickSphereRenderer:
    return QuickSphereRenderer()
