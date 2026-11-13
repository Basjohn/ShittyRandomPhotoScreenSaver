"""Soft irradiance must light the surface under a 3D source, with continuous distance falloff."""
import numpy as np
import pytest

from rendering.gl_error_policy import disable_per_call_gl_error_checking
disable_per_call_gl_error_checking()
from OpenGL import GL as gl
from rendering.gl_programs.lighting import SOFT_LIGHT_GLSL
from rendering.quick.render.gl_resources import compile_program, delete_program
from tools.labs.render_target import OffscreenRenderTarget

pytestmark=pytest.mark.qt

VERTEX='''#version 460 core
out vec3 world;
void main() {
    vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2)*2.0-1.0;
    world=vec3(p.x*4.0,0.0,p.y*4.0);
    gl_Position=vec4(p,0,1);
}
'''
FRAGMENT='#version 460 core\nin vec3 world;\nout vec4 FragColor;\n'+SOFT_LIGHT_GLSL+'''
void main() { FragColor=vec4(softIrradiance(world,vec3(0,1,0)),1); }
'''


def test_soft_irradiance_follows_source_position_normal_and_distance(qt_app):
    target=OffscreenRenderTarget(100,100)
    program=compile_program(VERTEX,FRAGMENT,label='soft light test')
    vao=int(gl.glGenVertexArrays(1))
    try:
        gl.glBindVertexArray(vao)
        gl.glUseProgram(program)
        position=gl.glGetUniformLocation(program,'uLightPosition[0]')
        count=gl.glGetUniformLocation(program,'uLightCount')
        gl.glUniform3fv(gl.glGetUniformLocation(program,'uLightFlux[0]'),1,np.array([[4.,0.,0.]],np.float32))
        for x,height,n in ((0.,2.,1),(1.6,2.,1),(0.,-2.,1),(0.,2.,0)):
            target.bind(clear=(0.,0.,0.,1.))
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glUniform1i(count,n)
            gl.glUniform4fv(position,1,np.array([[x,height,0.,.25]],np.float32))
            gl.glDrawArrays(gl.GL_TRIANGLES,0,3)
            pixels=target.read_rgba()[:,:,:3].astype(float)/255.
            row,col=np.indices(pixels.shape[:2])
            wx=(col+.5)/100*8.-4.
            wz=(1.-(row+.5)/100)*8.-4.
            d2=(wx-x)**2+wz**2+height**2+.25
            expected=n*4.*max(height,0.)/(np.pi*d2**1.5)
            np.testing.assert_allclose(pixels[:,:,0],expected,atol=1./255.)
            assert not pixels[:,:,1:].any()
    finally:
        gl.glDeleteVertexArrays(1,[vao])
        delete_program(program)
        target.close()
