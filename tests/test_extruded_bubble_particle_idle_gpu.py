"""Native production particle fragment: idle colour survives while all bloom emission releases."""
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
