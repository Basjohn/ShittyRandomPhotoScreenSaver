"""Execute the production bead generator on native GL; inspect its emitted geometry."""
import numpy as np
import pytest


@pytest.mark.qt
def test_attached_beads_keep_nominal_size_and_stay_below_every_reacted_parent(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import BEAD_VERTEX
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    # Replace only the raster entry point: the actual production generator writes to a
    # diagnostic SSBO, so this test does not restate its geometry formulas in Python.
    prefix = BEAD_VERTEX.split('void main() {\n    vOpacity = 1.0;\n')[0]
    vertex = prefix + '''
layout(std430, binding=6) buffer BeadResults { vec4 beadResults[]; };
void main() {
    vOpacity = 1.0;
    beadInstance();
    beadResults[gl_InstanceID] = vec4(aSphere.w, aSphere.z, vOpacity, aSphere.x);
    gl_Position = vec4(0.0,0.0,0.0,1.0);
}
'''
    target = TransitionCapture(64,64)
    buffers = []
    program = 0
    try:
        program = compile_program(vertex,'#version 460 core\nout vec4 colour;\nvoid main(){colour=vec4(0);}',
                                  label='production bead geometry contract')
        gl.glUseProgram(program)
        names=np.empty(2,dtype='u4')
        gl.glCreateBuffers(2,names)
        buffers=list(map(int,names))
        result, wakes = buffers
        gl.glNamedBufferData(result,64*16,None,gl.GL_DYNAMIC_READ)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,6,result)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,7,wakes)
        for name,value in (('uBeadCount',0),('uSnowCount',0),('uFizzPer',64),('uWakeCount',1)):
            gl.glUniform1i(gl.glGetUniformLocation(program,name),value)
        for name,value in (('uPixel',.001),('uBeadTravel',.2),('uFizzFill',64.)):
            gl.glUniform1f(gl.glGetUniformLocation(program,name),value)
        gl.glUniform3f(gl.glGetUniformLocation(program,'uStreamView'),0,1,0)
        gl.glUniform3f(gl.glGetUniformLocation(program,'uOrbit'),0,1,0)
        gl.glUniform2f(gl.glGetUniformLocation(program,'uTan'),1,.6)
        gl.glUniform1f(gl.glGetUniformLocation(program,'uSide'),1.9)
        gl.glUniform1f(gl.glGetUniformLocation(program,'uChainFill'),1.)
        gl.glUniform1i(gl.glGetUniformLocation(program,'uBeadsPerChain'),64)
        gl.glUniformMatrix3fv(gl.glGetUniformLocation(program,'uWorldToView'),1,False,np.eye(3,dtype='f4'))
        gl.glUniformMatrix3fv(gl.glGetUniformLocation(program,'uViewToWorld'),1,False,np.eye(3,dtype='f4'))
        gl.glUniformMatrix3fv(gl.glGetUniformLocation(program,'uViewToWorldTurn0'),1,False,np.eye(3,dtype='f4'))
        gl.glBindVertexArray(target.vao)
        gl.glEnable(gl.GL_RASTERIZER_DISCARD)

        def generated(scale,amount=1.,alpha=1.,free=False):
            data=np.array((0,0,-8,.2*scale,7,-1,alpha,.2),dtype='f4')
            gl.glNamedBufferData(wakes,data.nbytes,data,gl.GL_DYNAMIC_DRAW)
            gl.glUniform1f(gl.glGetUniformLocation(program,'uBeadSize'),amount)
            gl.glUniform1i(gl.glGetUniformLocation(program,'uBeadCount'),64 if free else 0)
            gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,64)
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
            data=np.empty((64,4),dtype='f4')
            gl.glGetNamedBufferSubData(result,0,data.nbytes,data)
            return data

        nominal=generated(1.)
        assert (nominal[:,0]>0).sum()>20
        for scale in (.13,.3,1.,3.4,5.):
            for alpha in (.03,1.):
                for amount in (.9,1.1):
                    rows=generated(scale,amount,alpha)
                    valid=(rows[:,0]>0)&(rows[:,2]>0)
                    sizes=rows[valid,0]
                    assert np.all(sizes < .2*scale)
                    drawn_px=np.maximum(sizes/(.001*np.maximum(-rows[valid,1],.1)),.5)
                    assert np.all(drawn_px < .2*scale*alpha**.5/(.001*8))
                    common=valid&(nominal[:,0]>0)
                    ratio=rows[common,0]/nominal[common,0]
                    assert np.all((ratio>=.89999)&(ratio<=1.10001))
        free=generated(1.,free=True)
        valid=free[:,0]>0
        assert valid.any()
        for amount in (.9,1.1):
            ratio=generated(1.,amount=amount,free=True)[valid,0]/free[valid,0]
            assert np.all((ratio>=.89999)&(ratio<=1.10001))
        # A thinner quality budget represents both stable owners, including a retiring source.
        sources=np.array(((-5,0,-8,.2,7,-1,1,.2),(5,0,-8,.2,9,.4,1,.2)),dtype='f4')
        gl.glNamedBufferData(wakes,sources.nbytes,sources,gl.GL_DYNAMIC_DRAW)
        for name,value in (('uBeadCount',0),('uSnowCount',0),('uWakeCount',2),('uFizzPer',32)):
            gl.glUniform1i(gl.glGetUniformLocation(program,name),value)
        gl.glUniform1f(gl.glGetUniformLocation(program,'uFizzFill'),31.5)
        gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,64)
        gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
        rows=np.empty((64,4),dtype='f4');gl.glGetNamedBufferSubData(result,0,rows.nbytes,rows)
        assert np.any((rows[:32,2]>0)&(rows[:32,3]<0))
        assert np.any((rows[32:,2]>0)&(rows[32:,3]>0))
        assert rows[31,2] <= .5 and rows[63,2] <= .5
    finally:
        gl.glDisable(gl.GL_RASTERIZER_DISCARD)
        for binding in (6,7):gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,binding,0)
        if buffers:gl.glDeleteBuffers(len(buffers),buffers)
        if program:gl.glDeleteProgram(program)
        target.close()


@pytest.mark.qt
def test_snow_fragment_honours_fractional_population_opacity(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import BUBBLE_VERTEX, BUBBLE_FRAGMENT
    from rendering.gl_programs.extruded_bubble_scene import camera
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    # Override only the generated population opacity. Exercise the production snow
    # fragment and OIT output, where the old consumer discarded this varying.
    vertex = BUBBLE_VERTEX.replace('void main() {', 'uniform float uTestOpacity;\nvoid main() {')
    vertex = vertex.replace('vOpacity = 1.0;', 'vOpacity = uTestOpacity;')
    target = TransitionCapture(64, 64)
    texture = program = 0
    try:
        texture = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 64, 64, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        gl.glDrawBuffers(1, [gl.GL_COLOR_ATTACHMENT0])
        program = compile_program(vertex, BUBBLE_FRAGMENT, label='production snow opacity contract')
        gl.glUseProgram(program)
        location = lambda name: gl.glGetUniformLocation(program, name)
        gl.glUniformMatrix4fv(location('uProjection'), 1, False, camera(0, 0, 1)[3])
        gl.glUniformMatrix3fv(location('uWorldToView'), 1, False, np.eye(3, dtype='f4'))
        gl.glUniformMatrix3fv(location('uViewToWorld'), 1, False, np.eye(3, dtype='f4'))
        for name, value in (('uPixel', .02), ('uPixelSize', .02), ('uCrisp', 1.)):
            gl.glUniform1f(location(name), value)
        gl.glUniform3f(location('uShaftColour'), 1, 1, 1)
        gl.glBindVertexArray(target.vao)
        gl.glDisableVertexAttribArray(0)
        gl.glDisableVertexAttribArray(1)
        gl.glVertexAttrib4f(0, 0, 0, -5, .5)
        gl.glVertexAttrib2f(1, .3, 1)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glViewport(0, 0, 64, 64)
        energies = []
        for opacity in (0., .25, 1.):
            gl.glUniform1f(location('uTestOpacity'), opacity)
            gl.glClearColor(0, 0, 0, 0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            pixels = np.frombuffer(gl.glReadPixels(0, 0, 64, 64, gl.GL_RGBA, gl.GL_FLOAT), dtype='f4')
            assert np.isfinite(pixels).all()
            energies.append(float(pixels.sum()))
        assert energies[0] == 0
        assert 0 < energies[1] < energies[2]
        assert gl.glGetError() == gl.GL_NO_ERROR
    finally:
        if program: gl.glDeleteProgram(program)
        if texture: gl.glDeleteTextures([texture])
        target.close()
