"""Native particle stages: quiet size contraction must not erase subpixel colour."""
import numpy as np
import pytest


@pytest.mark.qt
def test_idle_particles_keep_colour_but_emit_no_authored_or_intrinsic_glow(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import PARTICLE_FRAGMENT
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    vertex='''#version 460 core
out vec2 vCorner;
flat out vec3 vColour;
void main(){
    vCorner=vec2(float(gl_VertexID&1),float((gl_VertexID>>1)&1))*2.-1.;
    vColour=vec3(4.,3.,2.);
    gl_Position=vec4(vCorner,0.,1.);
}
'''
    target=TransitionCapture(64,64);program=0;textures=[]
    try:
        program=compile_program(vertex,PARTICLE_FRAGMENT,label='particle idle emission')
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,target.fbo)
        textures=list(map(int,gl.glGenTextures(2)))
        for i,texture in enumerate(textures):
            gl.glBindTexture(gl.GL_TEXTURE_2D,texture)
            gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA32F,64,64,0,gl.GL_RGBA,gl.GL_FLOAT,None)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT0+i,gl.GL_TEXTURE_2D,texture,0)
        gl.glDrawBuffers(2,[gl.GL_COLOR_ATTACHMENT0,gl.GL_COLOR_ATTACHMENT1])
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)==gl.GL_FRAMEBUFFER_COMPLETE
        gl.glUseProgram(program)
        activity=gl.glGetUniformLocation(program,'uParticleActivity')
        assert activity>=0
        gl.glUniform1f(gl.glGetUniformLocation(program,'uSpeckBloom'),2.)
        gl.glBindVertexArray(target.vao);gl.glViewport(0,0,64,64)
        gl.glDisable(gl.GL_BLEND);gl.glDisable(gl.GL_DEPTH_TEST);gl.glDisable(gl.GL_CULL_FACE)
        colours=[];emissions=[]
        for value in (0.,.25,1.):
            gl.glUniform1f(activity,value)
            gl.glClearColor(0,0,0,0);gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP,0,4)
            for attachment,rows in ((0,colours),(1,emissions)):
                gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0+attachment)
                pixels=np.frombuffer(gl.glReadPixels(0,0,64,64,gl.GL_RGBA,gl.GL_FLOAT),dtype='f4')
                assert np.isfinite(pixels).all()
                rows.append(float(pixels.sum()))
        assert colours[0]>0 and colours==pytest.approx([colours[0]]*3)
        assert emissions[0]==0 and 0<emissions[1]<emissions[2]
        assert emissions[1]==pytest.approx(emissions[2]*.25,rel=1e-5)
        assert gl.glGetError()==gl.GL_NO_ERROR
    finally:
        if textures:gl.glDeleteTextures(textures)
        if program:gl.glDeleteProgram(program)
        target.close()


@pytest.fixture
def particle_stage_capture(qt_app):
    """One fixed-depth point, pixel-centred, through both production stages into HDR MRTs."""
    import re
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import PARTICLE_VERTEX, PARTICLE_FRAGMENT
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    target = TransitionCapture(64, 64)
    programs = []
    textures = []
    vao = 0
    try:
        # The reference removes ONLY contraction. At share=1 this is the previous
        # authored-radius draw/energy law, independently compiled in native GL.
        reference, count = re.subn(r'uniform\s+float\s+uParticleRadiusShare\s*;', '', PARTICLE_VERTEX)
        assert count == 1, 'production vertex must expose the explicit radius-share authority'
        reference = re.sub(r'\buParticleRadiusShare\b', '1.0', reference)
        for label, vertex in (('production', PARTICLE_VERTEX), ('active reference', reference)):
            programs.append(compile_program(vertex, PARTICLE_FRAGMENT, label='particle size ' + label))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        textures = list(map(int, gl.glGenTextures(2)))
        for i, texture in enumerate(textures):
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 64, 64, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0 + i,
                                     gl.GL_TEXTURE_2D, texture, 0)
        gl.glDrawBuffers(2, [gl.GL_COLOR_ATTACHMENT0, gl.GL_COLOR_ATTACHMENT1])
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
        # TransitionCapture's quad VAO has enabled arrays; use disabled inputs
        # so constant aPoint/aLook attributes actually reach production GLSL.
        vao = int(gl.glGenVertexArrays(1))
        gl.glBindVertexArray(vao)
        gl.glViewport(0, 0, 64, 64)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)
        # At depth=1, unit sensor half-height means 2/64 view units/pixel.
        # Flatten clip Z only; X/Y and W give the exact unit-depth projection.
        projection = np.diag([1., 1., 0., 1.]).astype('f4')
        for program in programs:
            gl.glUseProgram(program)
            loc = lambda name: gl.glGetUniformLocation(program, name)
            gl.glUniformMatrix3fv(loc('uWorldToView'), 1, False, np.eye(3, dtype='f4'))
            gl.glUniformMatrix4fv(loc('uProjection'), 1, False, projection)
            gl.glUniform3f(loc('uEye'), 0., 0., 0.)
            gl.glUniform1i(loc('uRowMajor'), 0)
            gl.glUniform1f(loc('uPixel'), 2. / 64.)
            gl.glUniform3f(loc('uSunBelow'), 0., 0., -1.)
            gl.glUniform3f(loc('uSpeckWarm'), .4, .6, .8)
            gl.glUniform1f(loc('uSpecks'), 1.)
            gl.glUniform1f(loc('uSpeckBloom'), 2.)
        assert gl.glGetUniformLocation(programs[0], 'uParticleRadiusShare') >= 0

        def draw(radius, share, activity, *, reference=False):
            program = programs[int(reference)]
            gl.glUseProgram(program)
            if not reference:
                gl.glUniform1f(gl.glGetUniformLocation(program, 'uParticleRadiusShare'), share)
            gl.glUniform1f(gl.glGetUniformLocation(program, 'uParticleActivity'), activity)
            gl.glVertexAttrib4f(0, 1. / 64., 1. / 64., -1., radius)
            gl.glVertexAttrib4f(1, 1., 1., .5, 0.)
            gl.glClearColor(0., 0., 0., 0.)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, 1)
            images = []
            for attachment in (0, 1):
                gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0 + attachment)
                image = np.frombuffer(gl.glReadPixels(0, 0, 64, 64, gl.GL_RGBA, gl.GL_FLOAT),
                                      dtype='f4').reshape(64, 64, 4).copy()
                assert np.isfinite(image).all()
                images.append(image)
            assert gl.glGetError() == gl.GL_NO_ERROR
            return tuple(images)

        yield draw
    finally:
        if textures:
            gl.glDeleteTextures(textures)
        for program in programs:
            gl.glDeleteProgram(program)
        if vao:
            gl.glDeleteVertexArrays(1, [vao])
        target.close()


@pytest.mark.qt
def test_production_subpixel_idle_retains_authored_colour_without_glow(particle_stage_capture):
    draw = particle_stage_capture
    active, active_glow = draw(.005, 1., 1.)
    quiet, quiet_glow = draw(.005, .25, 0.)
    assert active[:, :, :3].sum() > 0
    # Both are below the SAME existing pixel floor: contraction cannot alter
    # coverage or the authored-radius energy numerator (the former 16x loss).
    np.testing.assert_array_equal(quiet, active)
    assert np.count_nonzero(quiet_glow) == 0
    assert active_glow[:, :, :3].sum() > 0


@pytest.mark.qt
def test_production_resolved_idle_contracts_area_without_changing_central_colour(particle_stage_capture):
    draw = particle_stage_capture
    active, _ = draw(.125, 1., 1.)
    quiet, quiet_glow = draw(.125, .25, 0.)
    # At the aligned centre, vCorner=0 in either footprint and energy caps at1.
    np.testing.assert_allclose(quiet[32, 32], active[32, 32], rtol=2e-6, atol=0.)
    assert 0 < np.count_nonzero(quiet[:, :, 0]) < np.count_nonzero(active[:, :, 0])
    assert 0 < quiet[:, :, :3].sum() < active[:, :, :3].sum()
    assert np.count_nonzero(quiet_glow) == 0


@pytest.mark.qt
@pytest.mark.parametrize('radius', [0., .005, .125])
def test_production_active_matches_uncontracted_reference_and_zero_stays_absent(particle_stage_capture, radius):
    draw = particle_stage_capture
    active = draw(radius, 1., 1.)
    reference = draw(radius, 1., 1., reference=True)
    for actual, expected in zip(active, reference):
        np.testing.assert_array_equal(actual, expected)
    if radius == 0.:
        for share, activity in ((.25, 0.), (1., 1.)):
            assert all(np.count_nonzero(image) == 0 for image in draw(0., share, activity))


@pytest.mark.qt
def test_production_radius_floor_transition_matches_continuous_gaussian(particle_stage_capture):
    draw = particle_stage_capture
    radius = .0625
    floor = (2. / 64.) * .75
    crossing = floor / radius
    # Avoid quad edges: this neighbour stays strictly inside all three draws.
    # Its ratio to the aligned centre directly measures the physical footprint,
    # independent of authored tint, phase, brightness and HDR calibration.
    ratios = []
    # Binary-exact steps put the edge on 1/64-pixel positions, avoiding
    # implementation raster-grid rounding masquerading as a discontinuity.
    for share in (crossing - 1. / 256., crossing, crossing + 1. / 256.):
        colour, glow = draw(radius, share, 0.)
        ratio = float(colour[32, 33, 0] / colour[32, 32, 0])
        half_width_pixels = 64. * max(radius * share, floor)
        expected = np.exp(-8. / half_width_pixels ** 2)
        assert ratio == pytest.approx(expected, rel=2e-5, abs=0.)
        ratios.append(ratio)
        assert np.count_nonzero(glow) == 0
    assert ratios[0] == pytest.approx(ratios[1], rel=2e-6)
    assert ratios[2] > ratios[1]
