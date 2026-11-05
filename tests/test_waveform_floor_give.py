"""Floor Give: the opt-in yielding floor under the Waveform ribbons.

Off (the default) draws exactly what the rigid floor drew: the production render with give 0 is pixel-identical to the
same programs with every give branch removed from their source. On, one yielding surface is shared by the floor's ray
hit (still on its own pixel's ray, still covering exactly the plane's pixels, first crossing, depth of the dented point)
and the ribbons' floor contact (a point may go below the plane only where the floor yields, and never below the yielding
surface). The field is reduced from the production packet and changes as smoothly as the ribbons do.
Test-owned fields and packets only; no preset value is read.
"""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest
from core.waveform_ribbon_scene import Floor
from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
from tests.test_waveform_ribbon_camera import camera
from tests.test_waveform_ribbon_mode import parameters

pytestmark = pytest.mark.qt

# Test-owned synthetic field: one ribbon's dent, a Gaussian along x at the origin, centred in z at Z0.
FIELD_SPAN = (-20., 20., 256)
DENT_DEPTH, DENT_SIGMA, Z0, RADIUS, CAP = .6, 3., .5, 1., .9


def _gl():
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    return gl


def synthetic_field(gl):
    first, last, samples = FIELD_SPAN
    x = np.linspace(first, last, samples)
    rows = np.zeros((3, samples, 4), np.float32)
    rows[0, :, 0] = DENT_DEPTH*np.exp(-.5*(x/DENT_SIGMA)**2)
    rows[1, :, 0] = Z0
    rows[2] = 1.
    rows[2, :, 0] = 1./RADIUS**2
    name = (gl.GLuint*1)(); gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name); texture = int(name[0])
    gl.glTextureStorage2D(texture, 1, gl.GL_RGBA32F, samples, 3)
    gl.glTextureSubImage2D(texture, 0, 0, 0, samples, 3, gl.GL_RGBA, gl.GL_FLOAT, np.ascontiguousarray(rows))
    for key, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                       (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
        gl.glTextureParameteri(texture, key, value)
    step = (last-first)/(samples-1)
    return texture, (first-.5*step, 1./(last-first+step), CAP, step)


def reference_depth(x, z):
    """The synthetic field's capped surface depth (linear filtering of the dense field is within tolerance)."""
    total = DENT_DEPTH*np.exp(-.5*(np.asarray(x)/DENT_SIGMA)**2)*np.exp(-(np.asarray(z)-Z0)**2/RADIUS**2)
    return CAP*(1.-np.exp(-total/CAP))


def _ssbo(gl, data, binding):
    buffer = int(np.asarray(gl.glGenBuffers(1)).reshape(-1)[0])
    gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER, buffer)
    gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER, data.nbytes, data, gl.GL_DYNAMIC_READ)
    gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, binding, buffer)
    return buffer


def _read(gl, buffer, like):
    gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
    gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER, buffer)
    return np.frombuffer(gl.glGetBufferSubData(gl.GL_SHADER_STORAGE_BUFFER, 0, like.nbytes), np.float32).reshape(like.shape).copy()


def test_ribbon_contact_goes_below_the_plane_only_where_the_floor_yields(qt_app):
    gl = _gl()
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.gl_programs.ribbon import _RIBBON_SURFACE_GLSL
    target = OffscreenRenderTarget(8, 8); resources = MeshResources('floor give contact probe')
    try:
        with target.current():
            source = '#version 460 core\nlayout(local_size_x=64) in;\n' + _RIBBON_SURFACE_GLSL + '''
layout(std430,binding=5) buffer Probe { vec4 points[]; };
uniform int uCount;
void main(){ int i=int(gl_GlobalInvocationID.x); if(i>=uCount) return; vec3 p=points[i].xyz;
points[i]=vec4(floorContact(p),floorGiveSurface(p)); }'''
            program = resources.compute_program('contact', source)
            texture, give = synthetic_field(gl)
            xs, ys, zs = np.meshgrid(np.linspace(-15., 15., 31), np.linspace(-1.5, 1.5, 31), np.linspace(-3., 3., 13), indexing='ij')
            points = np.stack((xs.ravel(), ys.ravel(), zs.ravel(), np.zeros(xs.size)), -1).astype(np.float32)
            location = lambda name: gl.glGetUniformLocation(program, name)
            def run(on):
                buffer = _ssbo(gl, points, 5)
                gl.glUseProgram(program)
                gl.glUniform1i(location('uCount'), len(points))
                gl.glUniform3f(location('uFloorContact'), 0., .03, .15)
                gl.glBindTextureUnit(13, texture); gl.glUniform1i(location('uFloorGiveField'), 13)
                gl.glUniform4f(location('uFloorGive'), *(give if on else (0., 0., 1., 1.)))
                gl.glUniform3f(location('uFloorGiveFrame'), 0., 0., 1.)
                gl.glDispatchCompute(-(-len(points)//64), 1, 1)
                result = _read(gl, buffer, points); gl.glDeleteBuffers(1, [buffer])
                return result
            rigid, giving = run(False), run(True)
            gl.glDeleteTextures(1, [texture])
        expected = reference_depth(points[:, 0], points[:, 2])
        # Off: the rigid map, nothing below the plane plus its gap, and the field is never read into the result.
        assert rigid[:, 1].min() > .03
        np.testing.assert_array_equal(rigid[:, [0, 2]], points[:, [0, 2]])
        # On: the surface the contact eases onto is the yielding floor, and the ribbon never passes below it.
        np.testing.assert_allclose(-giving[:, 3], expected, atol=2e-3)
        assert (giving[:, 1] > giving[:, 3]+.03).all()
        below = giving[:, 1] < 0.
        assert below.any()                                 # the ribbon does dip into the dent
        assert (expected[below] > .01).all()               # only where the floor yields
        clear = expected < 1e-6
        np.testing.assert_allclose(giving[clear, 1], rigid[clear, 1], atol=1e-5)  # elsewhere the rigid contact
        # A point well above the floor keeps its shape exactly as before.
        high = points[:, 1] > 1.2
        np.testing.assert_allclose(giving[high, 1], points[high, 1], atol=1e-4)
    finally:
        with target.current(): resources.release_resources()
        target.close()


def test_yielding_floor_hit_keeps_coverage_ray_and_depth(qt_app):
    gl = _gl()
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.scene3d.waveform import floor_vertices
    from rendering.gl_programs.waveform_ribbon import FLOOR_VERTEX, FLOOR_WORLD_GLSL
    width, height = 160, 120
    target = OffscreenRenderTarget(width, height); resources = MeshResources('floor give ground probe')
    fragment = '#version 460 core\n' + FLOOR_WORLD_GLSL + '''
layout(std430,binding=5) writeonly buffer WorldHits { vec4 hits[]; };
uniform float uTestWidth;
out vec4 FragColor;
void main(){vec3 world;float depth;if(!floorWorldHit(world,depth))discard;
gl_FragDepth=depth;FragColor=vec4(1,0,0,1);
hits[int(gl_FragCoord.y)*int(uTestWidth)+int(gl_FragCoord.x)]=vec4(world,depth);}
'''
    try:
        with target.current():
            program = resources.program('ground', FLOOR_VERTEX, fragment)
            vao, count = resources.mesh('coverage', floor_vertices(), (3,))
            texture, give = synthetic_field(gl)
        view, projection, eye, lens = physical_view(camera(tilt=-1.), width/height)
        mvp = projection@view

        def draw(on):
            with target.current():
                data = np.full((height, width, 4), np.nan, np.float32)
                buffer = _ssbo(gl, data, 5)
                target.bind(); gl.glEnable(gl.GL_DEPTH_TEST); gl.glDepthFunc(gl.GL_LESS); gl.glDepthMask(gl.GL_TRUE)
                gl.glClearBufferfv(gl.GL_DEPTH, 0, (1.,))
                gl.glUseProgram(program); gl.glBindVertexArray(vao)
                location = lambda name: gl.glGetUniformLocation(program, name)
                for name, matrix in (('uMvp', mvp), ('uFloorInverseMvp', np.linalg.inv(mvp))):
                    gl.glUniformMatrix4fv(location(name), 1, gl.GL_FALSE, np.asarray(matrix.flatten(order='F'), np.float32))
                gl.glUniform3f(location('uEye'), *eye)
                gl.glUniform1f(location('uTestWidth'), width)
                gl.glBindTextureUnit(13, texture); gl.glUniform1i(location('uFloorGiveField'), 13)
                gl.glUniform4f(location('uFloorGive'), *(give if on else (0., 0., 1., 1.)))
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
                hits = _read(gl, buffer, data)[::-1]; gl.glDeleteBuffers(1, [buffer])
                return target.read_rgba()[:, :, 0] > 200, hits
        plane_mask, plane = draw(False)
        mask, hits = draw(True)
        with target.current(): gl.glDeleteTextures(1, [texture])
        np.testing.assert_array_equal(mask, plane_mask)        # the same rays meet the ground
        valid = mask
        surface = reference_depth(hits[..., 0], hits[..., 2])
        dented = valid & (surface > .05)
        assert dented.sum() > 20                               # the dent is in view
        np.testing.assert_allclose(hits[valid, 1], -surface[valid], atol=4e-3)   # on the yielding surface
        # Still on its own pixel's ray.
        clip = np.einsum('ij,hwj->hwi', mvp, np.concatenate((hits[..., :3], np.ones((height, width, 1))), -1))
        yy, xx = np.mgrid[:height, :width]
        ndc = np.stack(((xx+.5)/width*2.-1., 1.-(yy+.5)/height*2.), -1)
        error = np.abs(clip[..., :2]/clip[..., 3:4]-ndc)*np.array((width, height))/2.
        assert error[valid].max() < .05
        # Depth is the dented point's own (deeper than the plane where the floor yields).
        depth = .5*(clip[..., 2]/clip[..., 3]+1.)
        np.testing.assert_allclose(hits[valid, 3], np.minimum(depth[valid], 1.-1e-7), atol=1e-5)
        assert (hits[dented, 3] > plane[dented, 3]).all()
        # First crossing: between the plane hit and the dented hit the ray stays above the surface, to the march's
        # resolution (a grazing ray may cut a sub-pixel sliver of the shallow rim between two steps).
        for t in np.linspace(.05, .95, 19):
            point = plane[..., :3]+(hits[..., :3]-plane[..., :3])*t
            assert (point[dented, 1] >= -reference_depth(point[dented, 0], point[dented, 2])-.01).all()
    finally:
        with target.current(): resources.release_resources()
        target.close()


def lowered_states(target, *, ticks=(64,), lower=1.5):
    """Production frames (fixture defaults, mist on) with the packet lowered so the ribbons reach the floor."""
    from core.waveform_ribbon_dynamics import WaveformDynamics
    from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
    from widgets.spotify_visualizer.render_state import WaveformRibbonFrame, freeze_render_fields
    values = parameters(); values['waveform_ribbon_mist_enabled'] = True
    configuration = CompiledWaveformSettings(values)
    model = WaveformDynamics(configuration.controls)
    camera_values = {key: value for key, value in values.items() if key.startswith('waveform_ribbon_camera_')
                     or key in ('waveform_ribbon_turn', 'waveform_ribbon_tilt', 'waveform_ribbon_scene_scale',
                                'waveform_ribbon_scene_pan_x', 'waveform_ribbon_scene_pan_y')}
    states = []
    for tick in range(max(ticks)+1):
        snapshot = model.advance(1/90, bands=(.6, .4, .3), intensity=.6, presence=1.)
        if tick in ticks:
            packet = snapshot.packet
            low = type(packet)(packet.payload, packet.instances, packet.vertices,
                               (packet.world_origin[0], packet.world_origin[1]-lower, packet.world_origin[2]),
                               packet.coordinate_origin)
            states.append(WaveformRibbonFrame(low, configuration.scene(snapshot), snapshot.time, snapshot.travel,
                snapshot.rotation_angle, snapshot.rotation_speed, snapshot.drives, snapshot.realized,
                ready=True, parameters=freeze_render_fields(camera_values)))
    return states


def frame_of(target, state):
    presentation = SimpleNamespace(content_fade=1., viewport_extent=(420., 280.), baseline_viewport_size=(420., 280.),
        outer_rect=(0., 0., 420., 280.), content_rect=(0., 0., 420., 280.), uniform_visual_scale=1.,
        shell_style={'content_inset': 0., 'authored_border_width': 0.})
    from widgets.spotify_visualizer.render_state import freeze_render_fields
    presentation.shell_style = freeze_render_fields(presentation.shell_style)
    return SimpleNamespace(snapshot=SimpleNamespace(logical=SimpleNamespace(mode_state=state), presentation=presentation),
        viewport=(0, 0, target.width, target.height), logical_size=(float(target.width), float(target.height)),
        matrix_values=(2/target.width, 0, 0, 0, 0, -2/target.height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1), quad_vao=target.vao)


def _render(renderer, target, frame, state, give):
    frame.snapshot.logical.mode_state = replace(state, scene=replace(state.scene, floor=replace(state.scene.floor, give=give)))
    for _ in range(80):
        if renderer.prepare_step(frame):
            break
    target.bind(); renderer.render(frame)
    return target.read_rgba().copy()


def _stripped_sources(monkeypatch):
    """Every give branch removed from the production sources the scene compiles (constant false)."""
    import rendering.quick.scene3d.ribbon as ribbon_module
    import rendering.quick.scene3d.waveform as waveform_module
    import rendering.quick.visualizer.implementations.waveform_ribbon as implementation_module
    branch = 'uFloorGive.y>0.0'
    replaced = 0
    # The renderer's warm-up compiles the floor from its own import: patch that name too, or the reference reuses it.
    for module, names in ((ribbon_module, ('RIBBON_VERTEX', 'RIBBON_CONTINUOUS_VERTEX', 'RIBBON_SPARK_VERTEX',
                                           'RIBBON_STRAY_VERTEX', 'RIBBON_COHORT_STRAY_VERTEX')),
                          (waveform_module, ('FLOOR_FRAGMENT',)), (implementation_module, ('FLOOR_FRAGMENT',))):
        for name in names:
            source = getattr(module, name)
            replaced += source.count(branch)
            monkeypatch.setattr(module, name, source.replace(branch, 'false'))
    assert replaced >= 12


def test_floor_give_off_is_pixel_identical_to_the_rigid_floor(qt_app, monkeypatch):
    gl = _gl()
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target = OffscreenRenderTarget(240, 160)
    try:
        state, = lowered_states(target)
        frame = frame_of(target, state)
        renderer = QuickWaveformRibbonRenderer()
        try:
            off = _render(renderer, target, frame, state, 0.)
            assert not renderer._scene.floor_give.has_resources
            on = _render(renderer, target, frame, state, 1.)
            assert renderer._scene.floor_give.has_resources and np.abs(on.astype(int)-off).max() > 8
            again = _render(renderer, target, frame, state, 0.)
            assert not renderer._scene.floor_give.has_resources
        finally:
            with target.current():
                renderer.release_resources()
                gl.glUseProgram(0)  # the next renderer in this context must not restore a released program
        np.testing.assert_array_equal(again, off)            # nothing of the give leaks into a later rigid frame
        with monkeypatch.context() as patch:
            _stripped_sources(patch)
            reference_renderer = QuickWaveformRibbonRenderer()
            try:
                reference = _render(reference_renderer, target, frame, state, 0.)
            finally:
                with target.current(): reference_renderer.release_resources()
        np.testing.assert_array_equal(off, reference)        # the rigid floor's exact pixels
    finally:
        target.close()


def test_production_field_is_bounded_follows_contact_and_moves_smoothly(qt_app):
    gl = _gl()
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target = OffscreenRenderTarget(240, 160); renderer = QuickWaveformRibbonRenderer()

    def field():
        scene = renderer._scene
        samples = int(scene.recipe.floor.give_span[2])
        with target.current():
            data = np.empty((3, samples, 4), np.float32)
            gl.glGetTextureImage(scene.floor_give.texture, 0, gl.GL_RGBA, gl.GL_FLOAT, data.nbytes, data)
        return data
    try:
        states = lowered_states(target, ticks=tuple(range(64, 76)), lower=2.5)
        frame = frame_of(target, states[0])
        fields = []
        for state in states:
            _render(renderer, target, frame, state, 1.)
            fields.append(field())
        floor = states[0].scene.floor
        depths = np.stack([f[0] for f in fields])
        assert depths.max() > .05 and depths.min() >= 0.
        assert np.all(np.isfinite(np.stack(fields)))
        # Bounded by its owner: each ribbon's dent is at most the share of its reach, the sum soft-capped on sampling.
        assert (fields[0][2] > 0.).all()
        # Smooth in time: from one 90 Hz tick to the next the dent moves by a small part of its depth.
        change = np.abs(np.diff(depths, axis=0)).max()
        assert change < .2*depths.max(), (change, depths.max())
        # The same frame raised clear of the floor leaves (practically) no dent: it follows contact, not presence.
        raised = replace(states[0], packet=type(states[0].packet)(states[0].packet.payload, states[0].packet.instances,
            states[0].packet.vertices, (states[0].packet.world_origin[0], states[0].packet.world_origin[1]+3.,
            states[0].packet.world_origin[2]), states[0].packet.coordinate_origin))
        _render(renderer, target, frame, raised, 1.)
        assert field()[0].max() < 1e-3*floor.give_depth
    finally:
        with target.current(): renderer.release_resources()
        target.close()


def test_floor_give_is_one_canonical_setting_resolved_into_the_scene():
    from core.settings.visualizer_mode_settings import require_mode_settings
    from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
    control = next(c for c in require_mode_settings('waveform_ribbon').controls if c.key == 'waveform_ribbon_floor_give')
    assert control.bucket == 'floor'
    values = parameters()
    assert CompiledWaveformSettings(values).base.floor.give == 0. == Floor().give
    from types import SimpleNamespace as NS
    snapshot = NS(ready=False, passage=0., drives={}, realized={})
    for give in (0., .5, 1.):
        values['waveform_ribbon_floor_give'] = give
        assert CompiledWaveformSettings(values).scene(snapshot).floor.give == give


def test_floor_give_repeat_renders_are_renderer_deterministic(qt_app, monkeypatch):
    """With Floor Give on, the same frame drawn again is the same image once the driver's 4x MSAA noise is out of the
    way (tests/_msaa_render_noise.py): single-sample, repeat renders are bit-identical, so no renderer state (field
    reduction, fog, reflection, packet stream) leaks from one frame into the next. A different frame is not."""
    gl = _gl()
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d import target as scene_target
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    scope = scene_target.SceneTarget.scope
    monkeypatch.setattr(scene_target.SceneTarget, 'scope',
                        lambda self, frame, samples, *args, **kwargs: scope(self, frame, 1, *args, **kwargs))
    target = OffscreenRenderTarget(240, 160); renderer = QuickWaveformRibbonRenderer()
    try:
        first, later = lowered_states(target, ticks=(64, 70), lower=2.5)
        frame = frame_of(target, first)
        images = [_render(renderer, target, frame, first, 1.) for _ in range(12)]
        assert renderer._scene.floor_give.has_resources
        for image in images[1:]:
            np.testing.assert_array_equal(image, images[0])
        other = _render(renderer, target, frame, later, 1.)
        assert np.abs(other.astype(int)-images[0]).max() > 8       # negative control: another frame differs
    finally:
        with target.current(): renderer.release_resources(); gl.glUseProgram(0)
        target.close()
