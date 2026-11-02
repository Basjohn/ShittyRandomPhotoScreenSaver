"""S3D-7 fog volume and detail march: exact slab integration in both projections, world anchoring, the steady
(never eroded) share, the ground stop and ownership (offscreen)."""
import math

import numpy as np
import pytest

from rendering.gl_error_policy import disable_per_call_gl_error_checking
disable_per_call_gl_error_checking()
from OpenGL import GL as gl
from rendering.gl_programs.fog_volume import fog_inject_source
from rendering.quick.render.gl_resources import compile_compute_program
from rendering.quick.scene3d.fog_volume import FogMarch, FogVolume
from tools.labs.render_target import OffscreenRenderTarget

pytestmark = pytest.mark.qt
SIGMA, RADIANCE = .5, (.2, .4, .8)
# A slab between world z -6 and -4 (the eye looks down -z from the origin), optionally clear inside a sphere.
MEDIUM = """
uniform vec4 uSphere;   // clear-air centre xyz, radius (radius 0: none)
uniform float uSteady;  // 1: the whole slab is steady (never eroded)
void fogMedium(vec3 world, out vec3 radiance, out float extinction, out float steady) {
    bool slab=world.z<-4.0 && world.z>-6.0 && length(world-uSphere.xyz)>uSphere.w;
    extinction=slab?%f:0.0;
    radiance=vec3(%f,%f,%f);
    steady=uSteady*extinction;
}
""" % (SIGMA, *RADIANCE)
GRID = (8, 8, 64)
DEPTHS = (1., 20.)


def view_at(eye):
    view = np.identity(4)
    view[:3, 3] = -np.asarray(eye, float)
    return view


@pytest.fixture
def gl_context(qt_app):
    target = OffscreenRenderTarget(16, 16)
    parts = dict(target=target, program=compile_compute_program(fog_inject_source(MEDIUM), label='slab medium'),
                 volume=FogVolume('fog test'), march=FogMarch('fog test'))
    yield parts
    with target.current():
        parts['volume'].release()
        parts['march'].release()
        gl.glDeleteProgram(parts['program'])
    target.close()


def update(parts, *, eye=(0., 0., 0.), orthographic=True, sphere=(0., 0., 0., 0.), steady=0.):
    program = parts['program']

    def medium(program):
        gl.glUniform4f(gl.glGetUniformLocation(program, 'uSphere'), *sphere)
        gl.glUniform1f(gl.glGetUniformLocation(program, 'uSteady'), steady)
    parts['volume'].update(program, view=view_at(eye), lens=(2., 2., orthographic) if orthographic else (.5, .5, False),
                           depth_range=DEPTHS, grid=GRID, medium=medium)


def integrated(volume):
    values = np.empty((GRID[2], GRID[1], GRID[0], 4), np.float32)
    gl.glGetTextureImage(volume.texture, 0, gl.GL_RGBA, gl.GL_FLOAT, values.nbytes, values)
    return values


def boundary_depth(k):
    near, far = DEPTHS
    return near*(far/near)**((k + 1)/GRID[2])


@pytest.mark.parametrize('orthographic', (True, False))
def test_a_slab_integrates_exactly_in_front_and_behind(gl_context, orthographic):
    update(gl_context, orthographic=orthographic)
    values = integrated(gl_context['volume'])
    column = values[:, GRID[1]//2, GRID[0]//2]
    ndc = (GRID[0]//2 + .5)/GRID[0]*2 - 1
    stretch = 1. if orthographic else math.sqrt(2*(ndc*.5)**2 + 1)
    for k in range(GRID[2]):
        depth = boundary_depth(k)
        # Cell centres decide membership: the analytic path through the slab is the sum of member slice lengths.
        inside = sum((boundary_depth(j) - (boundary_depth(j - 1) if j else DEPTHS[0]))
                     for j in range(k + 1) if 4. < DEPTHS[0]*(DEPTHS[1]/DEPTHS[0])**((j + .5)/GRID[2]) < 6.)
        expected = math.exp(-SIGMA*inside*stretch)
        assert column[k, 3] == pytest.approx(expected, abs=2e-3), (k, depth)
        np.testing.assert_allclose(column[k, :3], np.asarray(RADIANCE)*(1 - expected), atol=2e-3)
    assert column[0, 3] == 1. and column[-1, 3] < .5


def test_the_medium_is_world_anchored(gl_context):
    # Moving a clear sphere (world data) clears the slab where it now is; moving the eye along the view
    # axis changes depths but not the world-space medium the columns integrate.
    update(gl_context)
    solid = integrated(gl_context['volume'])[-1, :, :, 3]
    update(gl_context, sphere=(1.5, 1.5, -5., 1.2))
    holed = integrated(gl_context['volume'])[-1, :, :, 3]
    assert holed[-1, -1] > solid[-1, -1] + .3 and holed[0, 0] == pytest.approx(solid[0, 0], abs=1e-3)
    update(gl_context, eye=(0., 0., 2.))  # within one slice of discretisation of the sharp slab
    assert integrated(gl_context['volume'])[-1, :, :, 3] == pytest.approx(solid, abs=.03)


def test_march_keeps_the_steady_share_and_stops_at_the_ground(gl_context):
    target, volume, march = gl_context['target'], gl_context['volume'], gl_context['march']

    def transmittance(**options):
        # Coverage is extinction over the maximum: half coverage, which the remap erodes (a full core stays solid).
        march.march(volume, size=(8, 8), steps=256, max_extinction=2*SIGMA, erosion=1., detail_frequency=.7,
                    step=(.02, .05), shadow=(0., 0.), **options)
        values = np.empty((8, 8, 4), np.float32)
        gl.glGetTextureImage(march.texture, 0, gl.GL_RGBA, gl.GL_FLOAT, values.nbytes, values)
        return values[..., 3]
    update(gl_context, steady=1.)
    steady = transmittance()
    assert np.allclose(steady, math.exp(-SIGMA*2.), atol=.03)  # full erosion cannot touch the steady share
    update(gl_context, steady=0.)
    assert transmittance().mean() > steady.mean() + .1  # the erodible share is eroded
    # The eye looks along -z, so a ground plane only stops rays that descend; a level view keeps its slab.
    update(gl_context, steady=1.)
    assert np.allclose(transmittance(ground=-100.), steady, atol=.01)


def test_volume_allocates_lazily_admits_bounds_and_retires_in_its_context(gl_context):
    volume = gl_context['volume']
    assert not volume.has_resources
    with pytest.raises(RuntimeError, match='before its first update'):
        volume.uniforms
    with pytest.raises(ValueError):
        volume.warm((0, 4, 4))
    with pytest.raises(ValueError):
        volume.warm((4096, 4096, 64))
    assert volume.warm((4, 4, 4)) is False and volume.warm((4, 4, 4)) is True
    other = OffscreenRenderTarget(8, 8)
    try:
        with pytest.raises(RuntimeError, match='foreign'):
            volume.warm((4, 4, 4))
    finally:
        other.close()
    gl_context['target'].make_current()
    volume.release()
    assert not volume.has_resources


def test_composite_fringe_smoothing_is_opt_in_and_reaches_pixels(gl_context):
    target, volume, march = gl_context['target'], gl_context['volume'], gl_context['march']
    update(gl_context)
    march.march(volume, size=(8, 8), steps=32)
    # A high-frequency, coloured fringe isolates composite filtering from ray-march variation.
    yy, xx = np.indices((8, 8))
    fixture = np.zeros((8, 8, 4), np.float32)
    fixture[:, :, :3] = ((xx + yy) % 2)[:, :, None] * np.array((.1, .3, .9))
    fixture[:, :, 3] = .5
    gl.glTextureSubImage2D(march.texture, 0, 0, 0, 8, 8, gl.GL_RGBA, gl.GL_FLOAT, fixture)
    def pixels(**options):
        target.bind(clear=(0., 0., 0., 0.))
        march.composite(**options)
        return target.read_rgba()
    default = pixels()
    np.testing.assert_array_equal(default, pixels(fringe_smoothing=0.))
    assert np.abs(default.astype(int) - pixels(fringe_smoothing=1.).astype(int)).max() > 5
    with pytest.raises(ValueError, match='smoothing'):
        march.composite(fringe_smoothing=float('nan'))
