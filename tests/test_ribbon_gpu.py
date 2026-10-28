import numpy as np
import pytest

from rendering.gl_error_policy import disable_per_call_gl_error_checking
disable_per_call_gl_error_checking()
from OpenGL import GL as gl
from core.ribbon_geometry import PathSample
from core.ribbon_packet import pack_ribbons
from core.settings.framed_camera import orthographic_matrix, perspective_matrix
from rendering.quick import gl_query
from rendering.quick.scene3d.ribbon import RibbonPrimitive
from tools.labs.render_target import OffscreenRenderTarget

pytestmark = pytest.mark.qt


def line(origin=0):
    return ([PathSample(origin, (-1, 0, -10), .25), PathSample(origin+1, (1, 0, -10), .25)], [(1, 0, 0)]*2, None)


@pytest.mark.parametrize('projection', ('orthographic', 'perspective'))
def test_native_strip_bounds_normals_depth_and_retirement(qt_app, projection):
    target = OffscreenRenderTarget(160, 120)
    primitive = RibbonPrimitive()
    mvp = orthographic_matrix((2, 1.5), .1, 100) if projection == 'orthographic' else perspective_matrix((.2, .15), .1, 100)
    packet = pack_ribbons([line()])
    try:
        primitive.draw(pack_ribbons([]), mvp)
        assert not primitive.has_resources
        target.bind()
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        primitive.draw(packet, mvp)
        pixels = target.read_rgba()
        yy, xx = np.where(pixels[:, :, 3] > 0)
        assert (xx.min(), xx.max(), yy.min(), yy.max()) == (40, 119, 50, 69)
        target.bind()
        primitive.draw(packet, mvp, diagnostic=1)
        np.testing.assert_allclose(target.read_rgba()[60, 80, :3], (128, 128, 255), atol=1)
        # Closer strip wins through actual depth, independent of submission order.
        target.bind()
        primitive.draw(packet, mvp)
        behind = ([PathSample(0, (-1, 0, -11), .25), PathSample(1, (1, 0, -11), .25)], [(1, 0, 0)]*2, None)
        primitive.draw(pack_ribbons([behind], colour=(1, 0, 0, 1)), mvp)
        assert target.read_rgba()[60, 80, 1] > 100
        assert primitive.stream_bytes >= 3*131584
    finally:
        primitive.release()
        assert not primitive.has_resources
        primitive.release()
        target.close()


def test_native_gap_and_failed_draw_restore_caller_state(qt_app, monkeypatch):
    target = OffscreenRenderTarget(160, 120)
    primitive = RibbonPrimitive()
    mvp = orthographic_matrix((2, 1.5), .1, 100)
    samples = [PathSample(i, (i-2, 0, -10), .2) for i in range(5)]
    packet = pack_ribbons([(samples, [(1, 0, 0)]*2+[(0, 0, 0)]+[(1, 0, 0)]*2, None)])
    sentinel = int(np.asarray(gl.glGenBuffers(1)).reshape(-1)[0])
    gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER, sentinel)
    gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER, 256, None, gl.GL_STATIC_DRAW)
    gl.glBindBufferRange(gl.GL_SHADER_STORAGE_BUFFER, 0, sentinel, 0, 256)
    try:
        target.bind()
        gl.glBindVertexArray(target.vao)
        before = tuple(gl_query.get_int(e) for e in (gl.GL_CURRENT_PROGRAM, gl.GL_VERTEX_ARRAY_BINDING, gl.GL_DRAW_FRAMEBUFFER_BINDING))
        primitive.draw(packet, mvp)
        assert tuple(gl_query.get_int(e) for e in (gl.GL_CURRENT_PROGRAM, gl.GL_VERTEX_ARRAY_BINDING, gl.GL_DRAW_FRAMEBUFFER_BINDING)) == before
        image = target.read_rgba()
        assert image[60, 20, 3] > 0 and image[60, 140, 3] > 0
        assert not image[60, 60:100, 3].any()
        with monkeypatch.context() as patch:
            patch.setattr(gl, 'glDrawArraysInstanced', lambda *_: (_ for _ in ()).throw(RuntimeError('injected draw failure')))
            with pytest.raises(RuntimeError):
                primitive.draw(packet, mvp)
        assert tuple(gl_query.get_int(e) for e in (gl.GL_CURRENT_PROGRAM, gl.GL_VERTEX_ARRAY_BINDING, gl.GL_DRAW_FRAMEBUFFER_BINDING)) == before
        assert gl_query.get_indexed_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING, 0) == sentinel
        assert gl_query.get_indexed_int64(gl.GL_SHADER_STORAGE_BUFFER_SIZE, 0) == 256
        assert gl_query.get_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING) == sentinel
    finally:
        primitive.release()
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 0, 0)
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER, 0)
        gl.glDeleteBuffers(1, [sentinel])
        target.close()


def test_native_context_affinity_and_reactivation(qt_app):
    first = OffscreenRenderTarget(32, 24)
    second = OffscreenRenderTarget(32, 24)
    primitive = RibbonPrimitive()
    matrix = orthographic_matrix((2, 1.5), .1, 100)
    packet = pack_ribbons([line()])
    try:
        first.bind()
        primitive.draw(packet, matrix)
        old_buffer = primitive.stream._buffer
        second.bind()
        with pytest.raises(RuntimeError, match='foreign'):
            primitive.draw(packet, matrix)
        with pytest.raises(RuntimeError, match='foreign'):
            primitive.release()
        assert primitive.stream._buffer == old_buffer
        first.bind()
        primitive.release()
        assert not primitive.has_resources
        second.bind()
        primitive.draw(packet, matrix)
        assert primitive.has_resources
        primitive.release()
    finally:
        if primitive.has_resources:
            first.make_current()
            primitive.release()
        first.close()
        second.close()


def test_native_phase_survives_history_origin_rebase(qt_app):
    target = OffscreenRenderTarget(160, 120)
    primitive = RibbonPrimitive()
    mvp = orthographic_matrix((2, 1.5), .1, 100)
    origin = 1e9
    first = ([PathSample(origin+i*.25, (i-2, 0, -10), .2) for i in range(5)], [(1, 0, 0)]*5, None)
    second = (first[0][1:], first[1][1:], None)
    try:
        target.bind()
        primitive.draw(pack_ribbons([first], period=.7), mvp, diagnostic=2)
        a = target.read_rgba()
        target.bind()
        primitive.draw(pack_ribbons([second], period=.7), mvp, diagnostic=2)
        b = target.read_rgba()
        np.testing.assert_array_equal(a[53:67, 50:150], b[53:67, 50:150])
    finally:
        primitive.release()
        target.close()


def test_native_large_world_translation_preserves_geometry(qt_app):
    target = OffscreenRenderTarget(160, 120)
    primitive = RibbonPrimitive()
    mvp = orthographic_matrix((2, 1.5), .1, 100)
    try:
        target.bind()
        primitive.draw(pack_ribbons([line()]), mvp)
        expected = target.read_rgba()
        shifted = ([PathSample(0, (999998, 0, -10), .25), PathSample(1, (1000000, 0, -10), .25)], [(1, 0, 0)]*2, None)
        moved = list(mvp)
        moved[12] = -999999/2
        target.bind()
        primitive.draw(pack_ribbons([shifted]), moved)
        np.testing.assert_array_equal(target.read_rgba(), expected)
    finally:
        primitive.release()
        target.close()


@pytest.mark.parametrize('projection', ('orthographic', 'perspective'))
def test_native_curved_twisted_strip_follows_cpu_centripetal_centres(projection, qt_app):
    from core.ribbon_geometry import centripetal_point
    points = [(-1.5, 0., -10.), (-.5, 1., -10.), (.5, -1., -10.), (1.5, 0., -10.)]
    samples = [PathSample(i, p, .08, .4+i*.3) for i, p in enumerate(points)]
    target = OffscreenRenderTarget(320, 240)
    primitive = RibbonPrimitive()
    matrix = orthographic_matrix((2, 1.5), .1, 100) if projection == 'orthographic' else perspective_matrix((.2, .15), .1, 100)
    packet = pack_ribbons([(samples, [(1, 0, 0)]*4, None)])
    try:
        target.bind()
        primitive.draw(packet, matrix, diagnostic=1)
        pixels = target.read_rgba()
        for segment in range(3):
            b, c = np.array(points[segment]), np.array(points[segment+1])
            a = np.array(points[segment-1]) if segment else 2*b-c
            d = np.array(points[segment+2]) if segment+2 < 4 else 2*c-b
            for u in (.25, .5, .75):
                x, y, z = centripetal_point(a, b, c, d, u)
                w = matrix[11]*z+matrix[15]
                px = int((1+matrix[0]*x/w)*160)
                py = int((1-matrix[5]*y/w)*120)
                assert pixels[py-1:py+2, px-1:px+2, 3].any()
        normals = pixels[pixels[:, :, 3] > 0, :3]
        assert np.ptp(normals[:, 2]) > 10, 'twisted surface normals must not be constant plane normals'
    finally:
        primitive.release()
        target.close()


def test_context_reactivation_recomputes_larger_alignment_budget(qt_app, monkeypatch):
    from core.ribbon_packet import MAX_PACKET_BYTES
    first, second = OffscreenRenderTarget(32, 24), OffscreenRenderTarget(32, 24)
    primitive = RibbonPrimitive()
    packet = pack_ribbons([line()]*8)
    matrix = orthographic_matrix((2, 1.5), .1, 100)
    original = gl_query.get_int
    try:
        first.bind()
        primitive.draw(packet, matrix)
        primitive.release()
        second.bind()
        with monkeypatch.context() as patch:
            patch.setattr(gl_query, 'get_int', lambda name: 1048576 if name == gl.GL_SHADER_STORAGE_BUFFER_OFFSET_ALIGNMENT else original(name))
            # Simulated stricter alignment is still a multiple of native alignment;
            # reusing the old slot budget fails on the second maximum upload.
            primitive.draw(packet, matrix)
            primitive.draw(packet, matrix)
            assert primitive.stream.hold_bytes >= MAX_PACKET_BYTES+1048576
        primitive.release()
    finally:
        if primitive.has_resources:
            second.make_current()
            primitive.release()
        first.close()
        second.close()
