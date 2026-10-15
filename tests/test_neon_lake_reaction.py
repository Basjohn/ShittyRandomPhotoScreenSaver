"""GPU terrain/water invariants using the production basin surface and event layout."""
from copy import deepcopy

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.heightfield import heightfield_bytes, heightfield_surface_bytes, normalize_heightfield, sample_heightfield
from rendering.gl_programs.neon_lake_basin_program import NEON_VERTEX_SOURCE
from rendering.gl_programs.shockwave_grid_program import (
    SHOCKWAVE_DEPTH, SHOCKWAVE_EVENTS, shockwave_height,
)
from rendering.quick.scene3d.heightfield import HeightfieldTexture
from rendering.quick.scene3d.stream import StreamRing
from tests.test_scene3d_heightfield import _VERTEX
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt


class _SurfaceProbe:
    """Evaluate the actual vertex surface function over a dense UV grid into floats."""

    SIZE = 65

    def __init__(self, terrain):
        from rendering.quick.render.gl_resources import compile_program

        self.capture = TransitionCapture(self.SIZE, self.SIZE)
        self.texture = HeightfieldTexture("basin reaction probe", components=2)
        self.stream = StreamRing("basin reaction events")
        self.terrain = terrain
        self.texture.ensure(terrain["size"], heightfield_surface_bytes(terrain))
        # Retain every production function verbatim; replace only the vertex entry point.
        declarations = NEON_VERTEX_SOURCE.partition("out vec3 vWorld;")[0]
        declarations = declarations.replace("layout(location=0) in vec2 aUv;", "")
        fragment = declarations + f"""
        uniform vec4 uProbeUvRect;
        out vec4 FragColor;
        void main() {{
            vec2 uv = mix(uProbeUvRect.xy, uProbeUvRect.zw,
                          (gl_FragCoord.xy - vec2(0.5)) / {self.SIZE - 1}.0);
            float crest, energy, curved;
            vec3 surface = basinSurface(uv, crest, energy, curved);
            FragColor = vec4(surface.y, sceneHeightfieldWater(basinBase(uv)) ? 1.0 : 0.0, energy, crest);
        }}
        """
        self.program = compile_program(_VERTEX, fragment, label="basin reaction probe")
        self.vao = int(gl.glGenVertexArrays(1))
        self.target = int(gl.glGenTextures(1))
        self.fbo = int(gl.glGenFramebuffers(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.target)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, self.SIZE, self.SIZE, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, self.target, 0)
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE

    def draw(self, events=(), *, level=0.0, movement=1.0, detail=0.0, water_detail=0.0, time=0.0,
             bank_band=0.04, uv_rect=(0.0, 0.0, 1.0, 1.0)):
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glViewport(0, 0, self.SIZE, self.SIZE)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_BLEND)
        gl.glUseProgram(self.program)
        def uniform(name):
            return gl.glGetUniformLocation(self.program, name)
        gl.glUniform1i(uniform("uTerrain"), 0)
        gl.glUniform1i(uniform("uTerrainSize"), self.terrain["size"])
        gl.glUniform1f(uniform("uHalfWidth"), 1.7)
        gl.glUniform1i(uniform("uEventCount"), len(events))
        gl.glUniform2f(uniform("uWave"), 0.34, 1.3)
        gl.glUniform2f(uniform("uIdle"), 0.0, 0.0)
        gl.glUniform1f(uniform("uHorizon"), 0.6)
        gl.glUniform1f(uniform("uHeightScale"), 1.85)
        gl.glUniform1i(uniform("uBarCount"), 2)
        gl.glUniform1fv(uniform("uBars"), 2, np.asarray([level, level], dtype=np.float32))
        gl.glUniform3f(uniform("uLand"), 1.5, movement, detail)
        gl.glUniform1fv(uniform("uTerrainGrowth"),8,np.asarray([level]*8,dtype=np.float32))
        gl.glUniform1f(uniform("uTime"), time)
        gl.glUniform1f(uniform("uWaterDetail"), water_detail)
        gl.glUniform1f(uniform("uWaterBankBand"), bank_band)
        gl.glUniform4f(uniform("uProbeUvRect"), *uv_rect)
        records = [{"age": age, "x": x, "z": z, "strength": strength} for age, x, z, strength in events]
        payload = SHOCKWAVE_EVENTS.pack(records or [{"age": 0.0, "x": 0.0, "z": 0.0, "strength": 0.0}])
        gl.glBindVertexArray(self.vao)
        with self.texture.bound(0), self.stream.bound(gl.GL_SHADER_STORAGE_BUFFER, 3, payload):
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        raw = gl.glReadPixels(0, 0, self.SIZE, self.SIZE, gl.GL_RGBA, gl.GL_FLOAT)
        return np.frombuffer(bytes(raw), dtype=np.float32).reshape(self.SIZE, self.SIZE, 4).copy()

    def texture_bytes(self):
        with self.texture.bound(0):
            return bytes(gl.glGetTexImage(gl.GL_TEXTURE_2D, 0, gl.GL_RED, gl.GL_FLOAT))

    def close(self):
        self.stream.release()
        self.texture.release()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDeleteFramebuffers(1, [self.fbo])
        gl.glDeleteTextures([self.target])
        gl.glDeleteVertexArrays(1, [self.vao])
        gl.glDeleteProgram(self.program)
        self.capture.close()


@pytest.fixture
def surface(qt_app):
    # Test-owned flat water with a nonuniform bank and a low positive shore.
    terrain = normalize_heightfield({"version": 1, "size": 5, "heights": [
        0.0, 0.0, 0.0, 0.001, 0.2,
        0.0, 0.0, 0.0, 0.4, 0.7,
        0.0, 0.0, 0.0, 0.6, 1.0,
        0.0, 0.0, 0.0, 0.3, 0.8,
        0.0, 0.0, 0.0, 0.1, 0.5,
    ]})
    probe = _SurfaceProbe(terrain)
    try:
        yield probe
    finally:
        probe.close()


def test_gpu_water_membership_is_authored_and_both_materials_stay_bounded(surface):
    before = deepcopy(surface.terrain)
    packed = heightfield_bytes(before)
    quiet = surface.draw(detail=1.0)
    onset = surface.draw([(0.0, -0.8, -1.2, 2.0)], level=1.0, detail=1.0)
    # Maximum admitted event population, including overlapping crests.
    events = [(0.1 + i * 0.09, -0.8, -1.2, 2.0) for i in range(16)]
    sustained = surface.draw(events, level=1.0, detail=1.0, water_detail=1.0, time=1.0)
    bases = np.asarray([[sample_heightfield(before, x / 64.0, y / 64.0) for x in range(65)] for y in range(65)])
    water = bases == 0.0
    assert water.any() and (~water).any()
    for result in (quiet, onset, sustained):
        assert np.array_equal(result[..., 1], water.astype(np.float32))
        assert np.isfinite(result).all()
        assert np.max(np.abs(result[..., 0][water])) <= 0.1825 + 2e-6
        # The independent land envelope supplies at most 25% geometric growth.
        ratio = result[..., 0][~water] / quiet[..., 0][~water]
        assert ratio.min() >= 1.0 - 2e-6 and ratio.max() <= 1.25 + 2e-6
    assert np.max(np.abs(sustained[..., 0][water] - quiet[..., 0][water])) > 0.01
    assert np.max(sustained[..., 0][~water] - quiet[..., 0][~water]) > 0.01
    assert surface.terrain == before and heightfield_bytes(surface.terrain) == packed
    assert surface.texture_bytes() == packed


def test_gpu_wave_travel_uses_existing_event_age_and_origin(surface):
    water = surface.draw()[..., 1].astype(bool)
    peaks = []
    for age in (0.12, 0.60):
        events = [(age, -0.8, -1.2, 2.0)]
        result = surface.draw(events)
        expected_wave = np.asarray([[shockwave_height((x / 64.0 * 2.0 - 1.0) * 1.7,
                                                      -y / 64.0 * SHOCKWAVE_DEPTH, events, 0.34, 1.3)[0]
                                    for x in range(65)] for y in range(65)])
        # The shared wave's interior peak is retained; banks taper to zero.
        candidate = np.where(water, result[..., 0], -np.inf)
        peak = np.unravel_index(np.argmax(candidate), candidate.shape)
        assert expected_wave[peak] == pytest.approx(expected_wave[water].max(), abs=2e-5)
        peaks.append(peak)
        assert candidate[peak] > 0.001
    assert peaks[0] != peaks[1]
    birth = surface.draw([(0.0, -0.8, -1.2, 2.0)])
    assert np.max(np.abs(birth[..., 0][water])) == 0.0


def test_zero_terrain_movement_freezes_geometry_while_ridge_energy_still_responds(surface):
    quiet = surface.draw(movement=0.0, detail=1.0, time=0.0)
    active = surface.draw([(0.4, -0.8, -1.2, 2.0)], level=1.0, movement=0.0, detail=1.0, time=10.0)
    land = quiet[..., 1] == 0.0
    assert np.array_equal(quiet[..., 0][land], active[..., 0][land])
    assert np.max(quiet[..., 2][land]) == 0.0
    assert np.min(active[..., 2][land]) > 0.9
    assert np.max(active[..., 3]) > 0.0
    assert np.max(np.abs(active[..., 0][~land] - quiet[..., 0][~land])) > 0.001


def test_water_displacement_meets_zero_bank_without_moving_authored_membership(surface):
    active = surface.draw([(0.4, -0.8, -1.2, 2.0)], water_detail=1.0, time=1.0)
    quiet = surface.draw()
    # This field's last zero column is u=.5; positive land starts immediately
    # beyond it. A wave must meet that bank rather than expose a vertical wall.
    assert np.array_equal(active[..., 1], quiet[..., 1])
    assert np.max(np.abs(active[:, 32, 0])) == 0.0
    assert np.max(np.abs(active[:, 30, 0])) < np.max(np.abs(active[:, 27, 0]))
    assert np.max(np.abs(active[:, 27, 0])) > 0.01


@pytest.mark.parametrize("quality", ["High", "Balanced", "Performance", "KAK"])
@pytest.mark.parametrize("style", ["Glass", "Glass + Vertices"])
def test_nearshore_water_follows_wave_attack_and_release_without_a_flat_strip(surface, quality, style):
    from rendering.quick.visualizer.implementations.shockwave_grid import (
        basin_water_bank_band, shockwave_quality,
    )

    cells = shockwave_quality({
        "scene3d_detail": quality, "shockwave_grid_glow": 0.5,
        "shockwave_grid_wire_display": style, "shockwave_grid_density": 0.45,
    })[2]
    # Magnify only the last two water-side columns (the denser mesh axis).
    # This exercises the real packed bank channel and production basinSurface,
    # without a screenshot or
    # mesh-density-dependent raster sample accidentally skipping the near bank.
    uv_rect = (0.5 - 2.0 / cells[0], 0.0, 0.5, 1.0)
    draw = dict(uv_rect=uv_rect, bank_band=basin_water_bank_band(cells))
    quiet = surface.draw(**draw)
    assert np.max(np.abs(quiet[..., 0])) == 0.0
    assert np.all(quiet[..., 1] == 1.0)
    peaks = []
    for age in (0.12, 0.4, 1.4):
        events = [(age, 0.0, -1.2, 2.0)]
        active = surface.draw(events, **draw)
        # An infinitesimal bank band retains this exact wave at every sampled
        # water point except the shoreline itself; no CPU wave mirror decides
        # how much motion should be present.
        untapered = surface.draw(events, uv_rect=uv_rect, bank_band=1e-6)
        assert np.array_equal(active[..., 1], quiet[..., 1])
        assert np.max(np.abs(active[:, -1, 0])) == 0.0
        for column, minimum_share in ((48, 0.65), (32, 0.95)):
            reference = np.max(np.abs(untapered[:, column, 0]))
            assert reference > 0.01
            share = np.max(np.abs(active[:, column, 0])) / reference
            assert share >= minimum_share, (quality, style, age, column, share)
        # Two mesh cells away is ordinary reactive water, with no gain change.
        assert np.allclose(active[:, 0, 0], untapered[:, 0, 0], atol=2e-6)
        peaks.append(float(np.max(np.abs(active[..., 0]))))
    assert peaks[-1] < 0.5 * max(peaks[:2])
    birth = surface.draw([(0.0, 0.0, -1.2, 2.0)], **draw)
    assert np.max(np.abs(birth[..., 0])) == 0.0
    assert np.array_equal(surface.draw(**draw)[..., 0], quiet[..., 0])
