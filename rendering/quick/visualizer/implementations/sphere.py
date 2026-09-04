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
SPHERE_RADIUS_FRACTION = 0.28

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
    """Viewport edits change framing; whole-scale changes one shared pixel metric."""
    x, y, width, height = presentation.content_rect
    outer_x, outer_y, _, _ = presentation.outer_rect
    radius = presentation.baseline_viewport_size[1] * presentation.uniform_visual_scale * SPHERE_RADIUS_FRACTION
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
    float radius = 1.0 + uIdleMotion * 0.14 * broad
        + uDeformation * (uEnergy.x * (0.09 + 0.035*broad)
                         + uEnergy.y * 0.10 * lobes + uEnergy.z * 0.025 * ripples);
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
    float crust = smoothstep(0.06, 0.28, cracks);
    float height, roughness;
    if (uMaterial == 0) {
        float brush = sin(410.0*p.y + 4.0*grain(p*14.0))
                    * (1.0-smoothstep(0.8,2.2,footprint*410.0));
        height = 0.0002*brush + 0.00025*fineGrain;
        roughness = 0.12 + 0.07*fineGrain;
    } else if (uMaterial == 1) {
        height = 0.0048*mediumGrain + 0.001*fineGrain + 0.006*crust;
        roughness = 0.25 + 0.14*mediumGrain;
    } else if (uMaterial == 2) {
        height = 0.028*crust + crust*(0.004*mediumGrain + 0.001*fineGrain);
        roughness = mix(0.12,0.85,crust);
    } else if (uMaterial == 4) {
        float wave = sin(14.0*p.x + 9.0*p.y - uTime*0.85 + 0.7*sin(11.0*p.z+uTime))
                   + 0.45*sin(23.0*p.z - 11.0*p.x + uTime*0.64);
        height = 0.009*wave + 0.0015*mediumGrain;
        roughness = 0.06;
    } else {
        height = 0.001*mediumGrain + 0.0006*fineGrain;
        roughness = 0.35 + 0.13*fineGrain;
    }
    vec3 n = bumpedNormal(normalize(vNormal), height * uSurfaceDetail);
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
    studio += panel * vec3(1.1,1.18,1.28) + rimPanel * vec3(0.35,0.5,0.7);
    vec3 color;
    float alpha = uFade;
    if (uMaterial == 1) {
        float stone = 0.75 + 0.25*mediumGrain;
        color = vec3(0.004,0.003,0.009) * (0.3 + diffuse) * stone
              + studio * (0.12 + 0.06*stone) + vec3(0.065,0.035,0.12) * fresnel;
        highlight *= 0.65;
    } else if (uMaterial == 2) {
        float flow = 0.7 + 0.3*sin(6.0*p.z-uTime*0.7 + 2.0*grain(p*9.0));
        float fire = 1.0-crust;
        float core = 1.0-smoothstep(0.015,0.06,cracks);
        color = vec3(0.009,0.006,0.005) * (0.35+diffuse) * (0.75+0.25*mediumGrain)
              + fire*flow*vec3(2.6,0.23,0.003) + core*vec3(1.2,0.6,0.04)
              + studio*0.035*crust;
        highlight *= mix(0.8,0.08,crust);
    } else if (uMaterial == 4) {
        float caustic = pow(max(0.0, grain(p*18.0 + vec3(0,uTime*.3,0))), 6.0);
        color = studio * vec3(0.32,0.75,1.0) * (0.35+1.7*fresnel)
              + vec3(0.005,0.09,0.16)*(0.35+diffuse) + caustic*vec3(0.05,0.28,0.34);
        alpha *= 0.40 + 0.55*fresnel;
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
        self._ready = False
        self._uniforms: dict[str, int] = {}
        self._parameters = None
        self._light = (0.0, 0.0, 1.0)
        self._material = 0

    @property
    def has_resources(self) -> bool:
        return bool(self._program or self._vao or self._vbo)

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
        for uniform, key, default in (
            ("uDeformation", "sphere_deformation", 1.0),
            ("uSurfaceDetail", "sphere_surface_detail", 1.0),
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
                     "uMaterial", "uFade", "uSurfaceDetail")
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

    def release_resources(self) -> None:
        self._ready = False
        errors = []
        for attribute, deleter in (
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
            self._vertex_count = 0
        if errors:
            raise RuntimeError("Quick Sphere cleanup incomplete: " + " | ".join(errors))


def create_visualizer_renderer() -> QuickSphereRenderer:
    return QuickSphereRenderer()
