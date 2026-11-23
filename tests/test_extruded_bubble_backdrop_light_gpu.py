"""Settings -> production backdrop HDR pixels: direct light preserves ambient."""
import numpy as np
import pytest
from rendering.quick.render.gl_resources import delete_program


@pytest.mark.qt
@pytest.mark.parametrize("native_rows", (False, True))
def test_shaft_blur_and_backdrop_sample_only_odd_content_in_padded_targets(qt_app, native_rows):
    from OpenGL import GL as gl
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs import extruded_bubble_program as shaders
    from rendering.gl_programs.conventions import NATIVE_CORE_DEFINE
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.render.gl_resources import compile_program
    from rendering.quick.scene3d.uniforms import PassBlocks
    from rendering.quick.visualizer.implementations.extruded_bubble import _common, _Uniforms
    from tools.transition_contact_sheet import TransitionCapture

    shaft_size = (5, 3)
    scene_size = (11, 7)
    # Opposite edges and rows have different values. Slack poisoned far above the content exposes either wrong
    # row alignment or bilinear taps crossing an edge.
    pattern = np.array([[.05, .3, .1, .5, .9], [.4, .5, .3, .6, .2], [.8, .2, .5, .3, .3]], dtype="f4")
    target = TransitionCapture(14, 11)
    programs, textures = [], []
    blocks = PassBlocks("EB padded shaft sampling", block_bytes=shaders.FULLSCREEN_BLOCK.size)
    bank = _Uniforms()

    def source_with_rows(source):
        if native_rows:
            first, body = source.split("\n", 1)
            return first + f"\n#define {NATIVE_CORE_DEFINE}\n" + body
        return source

    def texture(shape, pixels=None):
        name = gl.glGenTextures(1)
        textures.append(name)
        gl.glBindTexture(gl.GL_TEXTURE_2D, name)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_R32F, *shape, 0, gl.GL_RED, gl.GL_FLOAT, pixels)
        for key in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, key, gl.GL_LINEAR)
        for key in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, key, gl.GL_CLAMP_TO_EDGE)
        return name

    def draw(program, pixels, source_shape, size, allocation, unit, values):
        origin = allocation[1] - size[1] if native_rows else 0
        src_y = source_shape[1] - shaft_size[1] if native_rows else 0
        source = np.full(source_shape[::-1], 17., dtype="f4")
        source[src_y:src_y + shaft_size[1], :shaft_size[0]] = pixels
        source_tex = texture(source_shape, source)
        output_tex = texture(allocation)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, output_tex, 0)
        gl.glViewport(0, origin, *size)
        gl.glUseProgram(program)
        gl.glBindTextureUnit(unit, source_tex)
        bank.set(program, values)
        with blocks.bound(bank.packed(program)):
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        result = gl.glReadPixels(0, origin, *size, gl.GL_RED, gl.GL_FLOAT)
        assert gl.glGetError() == gl.GL_NO_ERROR
        return np.frombuffer(result, dtype="f4").reshape(size[::-1]).copy()

    try:
        for label, source in (("blur", shaders.BLUR_FRAGMENT), ("backdrop", shaders.BACKDROP_FRAGMENT)):
            program = compile_program(shaders.FULL_VERTEX, source_with_rows(source), label=f"EB padded {label}")
            programs.append(program)
            bank.register(program, shaders.FULLSCREEN_BLOCK, shaders.block_defaults(shaders.FULLSCREEN_BLOCK))
        blur, backdrop = programs
        gl.glBindVertexArray(target.vao)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDrawBuffer(gl.GL_COLOR_ATTACHMENT0)
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)

        differences = {}
        for axis, step in (("horizontal", (1., 0.)), ("vertical", (0., 1.))):
            args = {"u_target_px": shaft_size, "uStep": step}
            exact = draw(blur, pattern, shaft_size, shaft_size, shaft_size, shaders.EB_SAMPLERS["uSource"], args)
            padded = draw(blur, pattern, (8, 7), shaft_size, (8, 7), shaders.EB_SAMPLERS["uSource"], args)
            assert np.ptp(exact) > .05
            differences[axis] = float(np.max(np.abs(padded - exact)))

        knobs = scene_knobs(require_canonical_default("widgets.spotify_visualizer"))
        common = _common(knobs, view_to_world=(1., 0., 0., 0., 1., 0., 0., 0., 1.), tan=(.4, .4), time=.7,
                         surface_travel=.7, rays=.6, streak=(.6, .8))
        values = {**common, "uFrameSize": scene_size, "uShaftContentPx": shaft_size, "uRayFocus": 0.}
        unit = shaders.EB_SAMPLERS["uShafts"]
        exact = draw(backdrop, pattern, shaft_size, scene_size, scene_size, unit, {**values, "u_target_px": scene_size})
        padded = draw(backdrop, pattern, (8, 7), scene_size, (14, 11), unit,
                      {**values, "u_target_px": (14, 11)})
        no_shafts = draw(backdrop, np.zeros_like(pattern), shaft_size, scene_size, scene_size, unit,
                         {**values, "u_target_px": scene_size})
        assert np.max(np.abs(exact - no_shafts)) > .001
        differences["backdrop"] = float(np.max(np.abs(padded - exact)))
        assert all(delta <= 2e-6 for delta in differences.values()), differences
    finally:
        blocks.release()
        for program in programs:
            delete_program(program)
        if textures:
            gl.glDeleteTextures(textures)
        target.close()


@pytest.fixture
def backdrop_light(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import (BACKDROP_FRAGMENT, EB_SAMPLERS, FULL_VERTEX,
                                                               FULLSCREEN_BLOCK, block_defaults)
    from rendering.quick.render.gl_resources import compile_program
    from rendering.quick.scene3d.uniforms import PassBlocks
    from rendering.quick.visualizer.implementations.extruded_bubble import _Uniforms
    from tools.transition_contact_sheet import TransitionCapture

    target = TransitionCapture(1, 1)
    program = texture = shafts = 0
    blocks = PassBlocks('EB direct light backdrop', block_bytes=FULLSCREEN_BLOCK.size)
    try:
        program = compile_program(FULL_VERTEX, BACKDROP_FRAGMENT, label='EB direct light backdrop')
        texture, shafts = gl.glGenTextures(2)
        for name, value in ((texture, None), (shafts, np.ones((1, 1, 4), dtype='f4'))):
            gl.glBindTexture(gl.GL_TEXTURE_2D, name)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 1, 1, 0, gl.GL_RGBA, gl.GL_FLOAT, value)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        gl.glDrawBuffer(gl.GL_COLOR_ATTACHMENT0)
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
        gl.glViewport(0, 0, 1, 1)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glBindVertexArray(target.vao)
        gl.glUseProgram(program)
        bank = _Uniforms()
        bank.register(program, FULLSCREEN_BLOCK, block_defaults(FULLSCREEN_BLOCK))   # the renderer's pass block

        def draw(values):
            gl.glBindTextureUnit(EB_SAMPLERS['uShafts'], shafts)
            bank.set(program, {**values, 'uFrameSize': (1., 1.), 'uLensShift': (0., 0.),
                               'u_target_px': (1., 1.), 'uShaftContentPx': (1., 1.)})
            with blocks.bound(bank.packed(program)):
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            result = np.frombuffer(gl.glReadPixels(0, 0, 1, 1, gl.GL_RGBA, gl.GL_FLOAT), dtype='f4').copy()
            assert gl.glGetError() == gl.GL_NO_ERROR
            assert np.isfinite(result).all()
            return result[:3]

        yield draw
    finally:
        blocks.release()
        if program:
            delete_program(program)
        if texture:
            gl.glBindTextureUnit(EB_SAMPLERS['uShafts'], 0)
            gl.glDeleteTextures([texture, shafts])
        target.close()


@pytest.mark.qt
@pytest.mark.parametrize('light_type', ('Sunlit Surface', 'Deep Light'))
@pytest.mark.parametrize('contribution', ('water', 'shafts', 'veils'))
def test_backdrop_direct_light_scales_once_over_unchanged_ambient(backdrop_light, light_type, contribution):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _common

    parameters = {**require_canonical_default('widgets.spotify_visualizer'),
                  'extruded_bubble_light_type': light_type}
    samples = []
    for strength in (0., .5, 1., 2.):
        knobs = scene_knobs({**parameters, 'extruded_bubble_light_strength': strength})
        values = _common(knobs, view_to_world=(1., 0., 0., 0., 1., 0., 0., 0., 1.),
                         tan=(.4, .4), time=.7, surface_travel=.7,
                         rays=.6 if contribution == 'shafts' else 0., streak=(.6, .8))
        values.update(uSunBelow=(0., 0., -1.), uMist=0., uProbeMode=0., uLightPower=0.,
                      uGlintPower=0., uProbeFill=0., uRayFocus=0.,
                      uVeils=.5 if contribution == 'veils' else 0.)
        if contribution != 'water':
            # Remove only the light-derived medium glow, retaining its ambient water.
            values['uGlow'] = 0.
            # A zero dot leaves a small negative broad term when glow is0;
            # move the sun sideways so that term is exactly zero as well.
            values['uSunBelow'] = (1., 0., 0.)
        samples.append(backdrop_light(values))
    ambient = samples[0]
    assert ambient.sum() > .001
    delta = samples[2] - ambient
    assert delta.sum() > .001, contribution
    np.testing.assert_allclose(samples[1] - ambient, delta * .5, rtol=2e-4, atol=2e-6)
    np.testing.assert_allclose(samples[3] - ambient, delta * 2., rtol=2e-4, atol=2e-6)


@pytest.mark.qt
@pytest.mark.parametrize('light_direction', ((0.,0.,-1.), (1.,0.,0.), (0.,0.,1.)))
def test_deep_scene_scattering_survives_side_and_away_views(backdrop_light, light_direction):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _common

    parameters = {**require_canonical_default('widgets.spotify_visualizer'),
                  'extruded_bubble_light_type': 'Deep Light'}
    deltas = {}
    for coverage in ('BEAM', 'SCENE'):
        knobs = scene_knobs({**parameters, 'extruded_bubble_lighting_coverage': coverage})
        values = _common(knobs, view_to_world=(1.,0.,0.,0.,1.,0.,0.,0.,1.),
                         tan=(.4,.4), time=.7, surface_travel=.7, rays=1., streak=(.6,.8))
        values.update(uSunBelow=light_direction, uMist=0., uDust=0., uGlow=0.,
                      uVeils=0., uProbeMode=0., uLightPower=0., uGlintPower=0., uProbeFill=0.)
        # A constant positive shaft texture isolates the real final compositing
        # gate. Keep the production Deep ray_focus, which formerly erased SCENE.
        deltas[coverage] = backdrop_light(values) - backdrop_light({**values, 'uRays': 0.})
    assert deltas['SCENE'].sum() > .001
    if light_direction != (0.,0.,-1.):
        np.testing.assert_array_equal(deltas['BEAM'], np.zeros(3))


@pytest.mark.qt
def test_deep_beam_width_changes_angular_coverage_without_changing_scene(backdrop_light):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _common
    for coverage in ('BEAM','SCENE'):
        deltas=[]
        for width in (.25,1.,3.):
            knobs=scene_knobs({**require_canonical_default('widgets.spotify_visualizer'),
                              'extruded_bubble_light_type':'Deep Light',
                              'extruded_bubble_lighting_coverage':coverage,
                              'extruded_bubble_beam_width':width})
            values=_common(knobs,view_to_world=(1.,0.,0.,0.,1.,0.,0.,0.,1.),
                           tan=(.4,.4),time=.7,surface_travel=.7,rays=.6,streak=(.6,.8))
            values.update(uSunBelow=(.6,0.,-.8),uMist=0.,uDust=0.,uGlow=0.,uVeils=0.,
                          uProbeMode=0.,uLightPower=0.,uGlintPower=0.,uProbeFill=0.)
            deltas.append(backdrop_light(values)-backdrop_light({**values,'uRays':0.}))
        if coverage=='BEAM':
            assert deltas[0].sum()<deltas[1].sum()<deltas[2].sum()
        else:
            np.testing.assert_array_equal(deltas[0],deltas[1])
            np.testing.assert_array_equal(deltas[1],deltas[2])
