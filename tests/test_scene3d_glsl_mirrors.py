"""The shared 3D library's GLSL functions agree with their CPU mirrors on the GPU.

Tests elsewhere reason about effects through the mirrors (departure, timing,
projection, shadows); this keeps the two from drifting as the library grows.
Each function runs for a table of inputs in an offscreen float target (no window)
and is compared with its mirror. Test-only: production never imports this.
"""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.gl_programs import scene3d as lib

pytestmark = pytest.mark.qt

_ITEM = (1600.0, 900.0)
# Item pixels -> clip space, as Qt Quick hands a full-window item.
_MATRIX = (2 / _ITEM[0], 0, 0, 0, 0, -2 / _ITEM[1], 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
_MATRIX_GLSL = "mat4(" + ", ".join(f"{value:.9f}" for value in _MATRIX) + ")"


class _GlslProbe:
    """Evaluate a GLSL body per input column into an RGBA32F row and read it back."""

    _VERTEX = """#version 410 core
void main() { vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2); gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }
"""

    def __init__(self) -> None:
        from OpenGL import GL as gl
        from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat

        self.gl = gl
        self.app = QGuiApplication.instance() or QGuiApplication([])
        fmt = QSurfaceFormat()
        fmt.setRenderableType(QSurfaceFormat.OpenGL)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setVersion(4, 1)
        self.context = QOpenGLContext()
        self.context.setFormat(fmt)
        assert self.context.create()
        self.surface = QOffscreenSurface()
        self.surface.setFormat(self.context.format())
        self.surface.create()
        assert self.context.makeCurrent(self.surface)
        self.vao = int(gl.glGenVertexArrays(1))
        self.programs: dict[str, int] = {}
        self.names: list[tuple[str, int]] = []

    def run(self, body: str, samples: list[list[tuple[float, ...]]]) -> np.ndarray:
        from rendering.quick.render.gl_resources import compile_program

        gl = self.gl
        count, rows = len(samples), len(samples[0])
        if body not in self.programs:
            fragment = ("#version 410 core\nout vec4 FragColor;\nuniform sampler2D uArgs;\n" + lib.SCENE3D_GLSL
                        + "vec4 arg(int row) { return texelFetch(uArgs, ivec2(int(gl_FragCoord.x), row), 0); }\n"
                        + f"const mat4 MATRIX = {_MATRIX_GLSL};\nconst vec2 ITEM = vec2({_ITEM[0]:.1f}, {_ITEM[1]:.1f});\n"
                        + "void main() {\n" + body + "\n}\n")
            self.programs[body] = compile_program(self._VERTEX, fragment, label="scene3d mirror probe")
        data = np.zeros((rows, count, 4), dtype=np.float32)
        for column, sample in enumerate(samples):
            for row, values in enumerate(sample):
                data[row, column, : len(values)] = values
        args, target, fbo = int(gl.glGenTextures(1)), int(gl.glGenTextures(1)), int(gl.glGenFramebuffers(1))
        try:
            gl.glBindTexture(gl.GL_TEXTURE_2D, args)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, count, rows, 0, gl.GL_RGBA, gl.GL_FLOAT, data)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
            gl.glBindTexture(gl.GL_TEXTURE_2D, target)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, count, 1, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, target, 0)
            assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
            gl.glViewport(0, 0, count, 1)
            gl.glUseProgram(self.programs[body])
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, args)
            gl.glUniform1i(gl.glGetUniformLocation(self.programs[body], "uArgs"), 0)
            gl.glBindVertexArray(self.vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            pixels = gl.glReadPixels(0, 0, count, 1, gl.GL_RGBA, gl.GL_FLOAT)
            return np.asarray(pixels, dtype=np.float64).reshape(count, 4)
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            gl.glDeleteFramebuffers(1, [fbo])
            gl.glDeleteTextures([args, target])

    def close(self) -> None:
        gl = self.gl
        for program in self.programs.values():
            gl.glDeleteProgram(program)
        gl.glDeleteVertexArrays(1, [self.vao])
        self.context.doneCurrent()


@pytest.fixture(scope="module")
def probe(qt_app):
    result = _GlslProbe()
    yield result
    result.close()


def _check(gpu: np.ndarray, cpu: list, *, tolerance: float = 2e-4) -> None:
    expected = np.asarray([list(value) if isinstance(value, tuple) else [value] for value in cpu], dtype=np.float64)
    actual = gpu[:, : expected.shape[1]]
    scale = np.maximum(1.0, np.abs(expected))
    worst = float(np.max(np.abs(actual - expected) / scale))
    assert worst <= tolerance, f"GPU and CPU mirror differ by {worst:.2e} (relative)"


def _unit(rng: random.Random) -> tuple[float, float, float]:
    return lib._normalize((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))


def test_impulse_and_departure_match(probe):
    rng = random.Random(1)
    impulse = [(rng.uniform(0, 1.2), rng.uniform(1, 30), rng.uniform(0, 0.5)) for _ in range(128)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(sceneImpulse(a.x, a.y, a.z));", [[s] for s in impulse])
    _check(gpu, [lib.scene3d_impulse(*s) for s in impulse])

    departures = []
    for _ in range(160):
        angle = rng.uniform(0, 2 * math.pi)
        heading = (math.cos(angle), math.sin(angle))
        if min(abs(heading[0]), abs(heading[1])) < 0.05:
            continue
        departures.append(((rng.uniform(-2, 2), rng.uniform(-1.5, 1.5)), heading, (rng.uniform(0.6, 1.2), rng.uniform(0.4, 0.7))))
    departures += [((0.2, 0.1), (1.0, 0.0), (0.9, 0.5)), ((0.2, 0.9), (1.0, 0.0), (0.9, 0.5)), ((0.0, 0.0), (0.0, -1.0), (0.9, 0.5))]
    gpu = probe.run("vec4 a = arg(0), b = arg(1); FragColor = vec4(sceneDepartureTravel(a.xy, a.zw, b.xy));",
                    [[(*start, *heading), half] for start, heading, half in departures])
    _check(gpu, [lib.scene3d_departure_travel(*d) for d in departures], tolerance=1e-3)


def test_projection_depth_and_shadow_casting_match(probe):
    rng = random.Random(2)
    worlds = [(rng.uniform(-1, 1), rng.uniform(-0.6, 0.6), rng.uniform(-1.0, 2.5)) for _ in range(128)]
    gpu = probe.run(
        "vec4 clip = sceneProject(MATRIX, ITEM, arg(0).xyz);"
        "vec2 ndc = clip.xy / clip.w;"
        "FragColor = vec4((ndc.x + 1.0) * 0.5, (1.0 - ndc.y) * 0.5, clip.z / clip.w, clip.w);",
        [[w] for w in worlds])
    aspect = _ITEM[0] / _ITEM[1]
    _check(gpu, [(*lib.scene3d_screen_uv(w, aspect), lib.scene3d_clip_depth(lib.SCENE3D_CAMERA - w[2]) /
                  (lib.SCENE3D_CAMERA - w[2]), lib.SCENE3D_CAMERA - w[2]) for w in worlds])

    casts = [((rng.uniform(-1, 1), rng.uniform(-0.5, 0.5), rng.uniform(-0.2, 1.0)), rng.uniform(-0.1, 0.0)) for _ in range(64)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(sceneCastOnPlane(a.xyz, a.w), 0.0, 0.0);",
                    [[(*w, plane)] for w, plane in casts])
    _check(gpu, [lib.scene3d_cast_on_plane(w, plane) for w, plane in casts])


def test_pieces_and_their_shadows_match(probe):
    rng = random.Random(9)
    pieces = []
    for _ in range(96):
        piece = lib.Scene3DPiece(
            (rng.uniform(-1.2, 1.2), rng.uniform(-0.7, 0.7), rng.uniform(-0.05, 0.8)),
            (rng.uniform(0.02, 0.1), -rng.uniform(0.02, 0.1), rng.uniform(0.0, 0.05)),
            _unit(rng), rng.uniform(-1, 1), _unit(rng), rng.uniform(-6, 6))
        pieces.append((piece, rng.uniform(-0.05, 0.0), (rng.random(), rng.random()), (rng.uniform(-.5, .5), rng.uniform(-.5, .5))))
    head = ("vec4 c = arg(0), e = arg(1), a = arg(2), b = arg(3), k = arg(4);"
            "ScenePiece piece = ScenePiece(c.xyz, e.xyz, a.xyz, a.w, b.xyz, b.w);")
    rows = [[(*piece.centre, plane), piece.extent, (*piece.tilt_axis, piece.tilt), (*piece.spin_axis, piece.spin),
             (*corner, *unit)] for piece, plane, corner, unit in pieces]
    gpu = probe.run(head + "FragColor = vec4(scenePiecePoint(piece, vec3(k.z, k.w, 0.3)), 0.0);", rows)
    _check(gpu, [lib.scene3d_piece_point(piece, (unit[0], unit[1], 0.3)) for piece, _p, _c, unit in pieces])
    shadows = [lib.scene3d_piece_shadow(_MATRIX, _ITEM, piece, plane, corner) for piece, plane, corner, _u in pieces]
    gpu = probe.run(head + "FragColor = scenePieceShadow(MATRIX, ITEM, piece, c.w, k.xy).clip;", rows)
    _check(gpu, [s["clip"] for s in shadows])
    gpu = probe.run(head + "SceneShadow s = scenePieceShadow(MATRIX, ITEM, piece, c.w, k.xy);"
                           "FragColor = vec4(s.screen, s.local);", rows)
    _check(gpu, [(*s["screen"], *s["local"]) for s in shadows])
    gpu = probe.run(head + "SceneShadow s = scenePieceShadow(MATRIX, ITEM, piece, c.w, k.xy);"
                           "FragColor = vec4(s.feather, s.onScreen, s.low, 0.0);", rows)
    _check(gpu, [(s["feather"], s["on_screen"], s["low"]) for s in shadows])


def test_cameras_match_and_rest_exactly(probe):
    rng = random.Random(7)
    aspect = _ITEM[0] / _ITEM[1]
    cases = []
    for _ in range(96):
        world = (rng.uniform(-1, 1), rng.uniform(-0.6, 0.6), rng.uniform(-0.5, 1.5))
        a = (rng.uniform(2.5, 4.0), rng.uniform(1.0, 1.3), rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05))
        b = (rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 0.0, 0.0)
        cases.append((world, a, b))
    gpu = probe.run(
        "vec4 clip = sceneProjectCamera(MATRIX, ITEM, arg(0).xyz, arg(1), arg(2));"
        "vec2 ndc = clip.xy / clip.w; FragColor = vec4((ndc.x + 1.0) * 0.5, (1.0 - ndc.y) * 0.5, 0.0, 0.0);",
        [[w, a, b] for w, a, b in cases])
    _check(gpu, [lib.scene3d_camera_uv(w, aspect, a, b) for w, a, b in cases])

    distances = [((rng.uniform(-1, 1), rng.uniform(-0.6, 0.6), rng.uniform(-0.5, 1.5)), rng.uniform(2.5, 4.0)) for _ in range(64)]
    gpu = probe.run(
        "vec4 a = arg(0); vec4 clip = sceneProjectAt(MATRIX, ITEM, a.xyz, a.w);"
        "vec2 ndc = clip.xy / clip.w; FragColor = vec4((ndc.x + 1.0) * 0.5, (1.0 - ndc.y) * 0.5, 0.0, 0.0);",
        [[(*w, d)] for w, d in distances])
    _check(gpu, [lib.scene3d_screen_uv_at(w, aspect, d) for w, d in distances])

    # A camera at rest is exactly the resting projection: same clip coordinates, bit for bit.
    gpu = probe.run(
        "vec4 a = arg(0); FragColor = sceneProjectCamera(MATRIX, ITEM, a.xyz, vec4(a.w, 1.0, 0.0, 0.0), vec4(0.0))"
        " - sceneProjectAt(MATRIX, ITEM, a.xyz, a.w);",
        [[(*w, d)] for w, d in distances])
    assert np.count_nonzero(gpu) == 0


def test_rotation_hash_and_colour_functions_match(probe):
    rng = random.Random(3)
    rotations = [((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)), _unit(rng), rng.uniform(-8, 8)) for _ in range(96)]
    gpu = probe.run("vec4 a = arg(0), b = arg(1); FragColor = vec4(sceneRotate(a.xyz, b.xyz, b.w), 0.0);",
                    [[p, (*axis, angle)] for p, axis, angle in rotations])
    _check(gpu, [lib.scene3d_rotate(*r) for r in rotations])

    keys = [(rng.randrange(0, 1 << 20), rng.randrange(0, 64), rng.randrange(1, 65536)) for _ in range(256)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(sceneRandom(uint(a.x), uint(a.y), uint(a.z)));",
                    [[k] for k in keys])
    _check(gpu, [lib.scene3d_random(*k) for k in keys], tolerance=1e-6)

    embers = [rng.uniform(-0.2, 1.2) for _ in range(64)]
    gpu = probe.run("FragColor = vec4(sceneEmber(arg(0).x), 0.0);", [[(t,)] for t in embers])
    _check(gpu, [lib.scene3d_ember(t) for t in embers])

    rects = [((rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8)), rng.uniform(0.01, 0.3)) for _ in range(64)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(sceneSoftRect(a.xy, a.z));", [[(*local, f)] for local, f in rects])
    _check(gpu, [lib.scene3d_soft_rect(*r) for r in rects])


def test_lighting_matches(probe):
    rng = random.Random(4)
    cases = [((rng.random(), rng.random(), rng.random()), _unit(rng),
              (rng.uniform(-1, 1), rng.uniform(-0.5, 0.5), rng.uniform(-0.2, 1.5)),
              (rng.uniform(0.2, 0.6), rng.uniform(0, 0.5), rng.uniform(8, 40), rng.uniform(0, 0.2))) for _ in range(96)]
    gpu = probe.run(
        "vec4 a = arg(0), n = arg(1), w = arg(2), p = arg(3);"
        "FragColor = vec4(sceneShade(a.xyz, n.xyz, w.xyz, p.x, p.y, p.z, p.w), 0.0);",
        [[albedo, normal, world, params] for albedo, normal, world, params in cases])
    _check(gpu, [lib.scene3d_shade(albedo, normal, world, *params) for albedo, normal, world, params in cases], tolerance=5e-4)

    lights = [(_unit(rng), (rng.uniform(-1, 1), rng.uniform(-0.5, 0.5), rng.uniform(-0.2, 1.0)),
               (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), 0.35), (1.0, 0.55, 0.22), rng.uniform(1, 12)) for _ in range(96)]
    gpu = probe.run(
        "vec4 n = arg(0), w = arg(1), l = arg(2), c = arg(3);"
        "FragColor = vec4(scenePointLight(n.xyz, w.xyz, l.xyz, c.xyz, c.w), 0.0);",
        [[normal, world, light, (*colour, falloff)] for normal, world, light, colour, falloff in lights])
    _check(gpu, [lib.scene3d_point_light(*l) for l in lights])


def test_streaks_match(probe):
    rng = random.Random(5)
    streaks = []
    for _ in range(96):
        tail = (rng.uniform(-0.8, 0.8), rng.uniform(-0.4, 0.4), rng.uniform(-0.2, 1.5))
        head = (tail[0] + rng.uniform(-0.1, 0.1), tail[1] + rng.uniform(-0.1, 0.1), tail[2] + rng.uniform(-0.1, 0.1))
        streaks.append((tail, head, rng.uniform(1, 6), (rng.random(), rng.random())))
    gpu = probe.run(
        "vec4 t = arg(0), h = arg(1), c = arg(2);"
        "FragColor = sceneStreak(MATRIX, ITEM, t.xyz, h.xyz, c.z, c.xy);",
        [[tail, head, (*corner, width)] for tail, head, width, corner in streaks])
    _check(gpu, [lib.scene3d_streak(_MATRIX, _ITEM, tail, head, width, corner) for tail, head, width, corner in streaks],
           tolerance=1e-3)


def test_particles_match(probe):
    rng = random.Random(8)
    cases = []
    for _ in range(96):
        origin = (rng.uniform(-0.8, 0.8), rng.uniform(-0.4, 0.4), rng.uniform(0.0, 0.3))
        velocity = (rng.uniform(-4, 4), rng.uniform(-4, 4), rng.uniform(0, 2))
        cases.append((origin, velocity, rng.uniform(2, 20), rng.uniform(0, 3), rng.uniform(0.001, 0.3),
                      rng.uniform(0, 0.01), rng.uniform(1, 6), (rng.random(), rng.random())))
    gpu = probe.run("vec4 o = arg(0), v = arg(1), p = arg(2);"
                    "FragColor = vec4(sceneParticleAt(o.xyz, v.xyz, p.x, p.y, p.z), 0.0);",
                    [[origin, velocity, (drag, fall, t)] for origin, velocity, drag, fall, t, *_ in cases])
    _check(gpu, [lib.scene3d_particle_at(origin, velocity, drag, fall, t)
                 for origin, velocity, drag, fall, t, *_ in cases])
    gpu = probe.run("vec4 o = arg(0), v = arg(1), p = arg(2), c = arg(3);"
                    "FragColor = sceneParticleStreak(MATRIX, ITEM, o.xyz, v.xyz, p.x, p.y, p.z, p.w, c.z, c.xy);",
                    [[origin, velocity, (drag, fall, t, trail), (*corner, width)]
                     for origin, velocity, drag, fall, t, trail, width, corner in cases])
    _check(gpu, [lib.scene3d_particle_streak(_MATRIX, _ITEM, origin, velocity, drag, fall, t, trail, width, corner)
                 for origin, velocity, drag, fall, t, trail, width, corner in cases], tolerance=1e-3)


def test_reflection_uv_matches(probe):
    rng = random.Random(10)
    rays = [_unit(rng) for _ in range(64)]
    gpu = probe.run("FragColor = vec4(sceneReflectionUv(arg(0).xyz), 0.0, 0.0);", [[ray] for ray in rays])
    _check(gpu, [lib.scene3d_reflection_uv(ray) for ray in rays])
    assert lib.scene3d_reflection_uv((0.0, 0.0, 1.0)) == (0.5, 0.5)   # looking straight back: the centre


def test_velocity_matches(probe):
    rng = random.Random(7)
    cases = []
    for _ in range(96):
        now = (rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-1, 1), rng.uniform(-0.2, 3.0))
        previous = (now[0] + rng.uniform(-0.3, 0.3), now[1] + rng.uniform(-0.3, 0.3), now[2],
                    now[3] + rng.uniform(-0.3, 0.3))
        cases.append((now, previous, (rng.uniform(640, 3840), rng.uniform(360, 2160))))
    gpu = probe.run("vec4 a = arg(0), b = arg(1), c = arg(2); FragColor = vec4(sceneVelocity(a, b, c.xy), 0.0, 0.0);",
                    [[now, previous, viewport] for now, previous, viewport in cases])
    _check(gpu, [lib.scene3d_velocity(now, previous, viewport) for now, previous, viewport in cases])
    # Still, and behind the camera, a point has no motion.
    assert lib.scene3d_velocity((0.3, 0.2, 0.0, 1.5), (0.3, 0.2, 0.0, 1.5), (2560, 1440)) == (0.0, 0.0)
    assert lib.scene3d_velocity((0.3, 0.2, 0.0, -0.1), (0.1, 0.2, 0.0, 1.5), (2560, 1440)) == (0.0, 0.0)


def test_a_drifted_mirror_is_caught(probe):
    # Negative control: a mirror that drifts by a hair from its shader fails the bar.
    rng = random.Random(6)
    impulse = [(rng.uniform(0.05, 1.0), rng.uniform(1, 30), rng.uniform(0, 0.5)) for _ in range(64)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(sceneImpulse(a.x, a.y, a.z));", [[s] for s in impulse])
    with pytest.raises(AssertionError):
        _check(gpu, [lib.scene3d_impulse(t, drag, drift + 0.01) for t, drag, drift in impulse])


def test_the_hash_is_uniform():
    values = [lib.scene3d_random(key, 7, 713) for key in range(20000)]
    counts, _edges = np.histogram(values, bins=20, range=(0.0, 1.0))
    assert counts.min() > 850 and counts.max() < 1150
    assert abs(float(np.mean(values)) - 0.5) < 0.01


def test_motion_transforms_keep_the_shader_and_add_its_motion():
    vertex = """#version 410 core
uniform mat4 uMatrix;
// the run's progress
uniform float uProgress, uDepth;
out vec2 vUv;
void main() {
    float t = uProgress * 2.0;
    if (t <= 0.0) { gl_Position = vec4(2., 2., 2., 1.); return; }
    gl_Position = uMatrix * vec4(t, uDepth, 0.0, 1.0);
    vUv = vec2(uProgress);
}
"""
    moving = lib.scene3d_motion_vertex(vertex)
    assert moving.startswith("#version 410 core\n")
    assert "uniform float uProgress, uDepth;" in moving           # the declaration stays
    assert "float t = sceneTime * 2.0;" in moving and "vUv = vec2(sceneTime);" in moving
    assert "void sceneVertexMain()" in moving and moving.count("void main()") == 1
    assert "sceneTime = uProgressBefore;" in moving and "vClipBefore" in moving
    fragment = "#version 410 core\nin vec2 vUv;\nout vec4 FragColor;\nvoid main() { FragColor = vec4(vUv, 0.0, 1.0); }\n"
    writing = lib.scene3d_motion_fragment(fragment)
    assert "layout(location = 0) out vec4 FragColor;" in writing
    assert "layout(location = 1) out vec4 SceneMotion;" in writing and "vec2 sceneVelocity(" in writing
    assert "void sceneFragmentMain()" in writing and writing.count("void main()") == 1
    # Shaders the transform cannot handle safely are refused, never guessed at.
    for broken in ("void main() {}", "#version 410 core\nvoid main() {}\n"):
        with pytest.raises(ValueError):
            lib.scene3d_motion_vertex(broken)
    with pytest.raises(ValueError):
        lib.scene3d_motion_fragment("#version 410 core\nout vec4 Colour;\nvoid main() {}\n")
