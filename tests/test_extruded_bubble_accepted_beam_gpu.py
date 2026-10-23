"""Frozen pre-regression BEAM equations against the real production fragment."""
from pathlib import Path

import numpy as np
import pytest


@pytest.mark.qt
def test_default_beam_matches_the_pre_acceptance_shader_in_both_light_types(qt_app):
    from OpenGL import GL as gl
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_program import SHAFT_FRAGMENT,FULL_VERTEX
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs,physical_camera
    from rendering.quick.render.gl_resources import compile_program
    from rendering.quick.visualizer.implementations.extruded_bubble import _Uniforms,_common
    from tools.transition_contact_sheet import TransitionCapture

    reference=(Path(__file__).parent/'fixtures/extruded_bubble/accepted_beam_a51aab8a.glsl').read_text(encoding='utf-8')
    prefix=SHAFT_FRAGMENT[:SHAFT_FRAGMENT.index('uniform float uShaftScale;')]
    target=TransitionCapture(1,1)
    programs=[]
    texture=0
    maxima=[]
    try:
        programs=[compile_program(FULL_VERTEX,fragment,label='accepted BEAM parity')
                  for fragment in (prefix+reference,SHAFT_FRAGMENT)]
        texture=int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D,texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA32F,1,1,0,gl.GL_RGBA,gl.GL_FLOAT,None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,target.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT0,gl.GL_TEXTURE_2D,texture,0)
        gl.glDrawBuffer(gl.GL_COLOR_ATTACHMENT0)
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
        gl.glViewport(0,0,1,1)
        gl.glDisable(gl.GL_BLEND);gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glBindVertexArray(target.vao)
        bank=_Uniforms()
        for light_type in ('Sunlit Surface','Deep Light'):
            for softness in (.15,.8):
                knobs=scene_knobs({**require_canonical_default('widgets.spotify_visualizer'),
                                  'extruded_bubble_light_type':light_type,
                                  'extruded_bubble_ray_softness':softness})
                for turn,tilt in ((0.,0.),(.3,-.5),(-.4,.25)):
                    view,_,eye,tan,_=physical_camera(turn,tilt,1.5,surface_bound=light_type=='Sunlit Surface')
                    values=_common(knobs,view_to_world=view,eye=eye,tan=tan,time=1.7,
                                   surface_travel=0.,rays=1.,streak=(1.,0.))
                    values.update(uRaySource=knobs['ray_source'],uRayEnd=knobs['ray_end'],
                                  uShimmer=.9,uFlicker=.4,uParticleAtten=.03)
                    for i in range(4):values[f'uBlock{i}']=(0.,-2.,-6.,.6 if i==0 else 0.)
                    results=[]
                    for program in programs:
                        gl.glUseProgram(program);bank.set(program,values)
                        gl.glDrawArrays(gl.GL_TRIANGLES,0,3)
                        results.append(np.frombuffer(gl.glReadPixels(0,0,1,1,gl.GL_RGBA,gl.GL_FLOAT),dtype='f4').copy())
                    assert np.isfinite(results).all()
                    np.testing.assert_allclose(results[1],results[0],rtol=2e-6,atol=2e-7)
                    maxima.append(float(results[0].max()))
        assert max(maxima)>.001  # Reject a vacuous comparison of black fields.
        assert gl.glGetError()==gl.GL_NO_ERROR
    finally:
        if texture:gl.glDeleteTextures([texture])
        for program in programs:gl.glDeleteProgram(program)
        target.close()
