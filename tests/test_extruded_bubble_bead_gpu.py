"""Execute the production bead generator on native GL; inspect its emitted geometry."""
from core.constants.extruded_bubble_world import WAKE_STRIDE
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
        gl.glUniform3f(gl.glGetUniformLocation(program,'uStreamWorld'),0,1,0)
        gl.glUniform3f(gl.glGetUniformLocation(program,'uStreamAcross'),1,0,0)
        gl.glUniform3f(gl.glGetUniformLocation(program,'uStreamDepth'),0,0,-1)
        gl.glUniform3f(gl.glGetUniformLocation(program,'uWorldHalf'),18,8,18)
        gl.glUniform2f(gl.glGetUniformLocation(program,'uTan'),1,.6)
        gl.glUniform1f(gl.glGetUniformLocation(program,'uChainFill'),1.)
        gl.glUniform1i(gl.glGetUniformLocation(program,'uBeadsPerChain'),64)
        gl.glUniformMatrix3fv(gl.glGetUniformLocation(program,'uWorldToView'),1,False,np.eye(3,dtype='f4'))
        gl.glUniformMatrix3fv(gl.glGetUniformLocation(program,'uViewToWorld'),1,False,np.eye(3,dtype='f4'))
        gl.glBindVertexArray(target.vao)
        gl.glEnable(gl.GL_RASTERIZER_DISCARD)

        def generated(scale,amount=1.,alpha=1.,free=False):
            data=np.array((0,0,-8,.2*scale,7,-1,alpha,.2)+(0.,)*(WAKE_STRIDE-8),dtype='f4')
            gl.glNamedBufferData(wakes,data.nbytes,data,gl.GL_DYNAMIC_DRAW)
            gl.glUniform1f(gl.glGetUniformLocation(program,'uBeadSize'),amount)
            gl.glUniform1i(gl.glGetUniformLocation(program,'uBeadCount'),64 if free else 0)
            gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,64)
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT | gl.GL_SHADER_STORAGE_BARRIER_BIT)
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
                    assert np.all(drawn_px < .2*scale/(.001*8))
                    common=valid&(nominal[:,0]>0)
                    ratio=rows[common,0]/nominal[common,0]
                    assert np.all((ratio>=.89999)&(ratio<=1.10001))
        free=generated(1.,free=True)
        valid=free[:,0]>0
        assert valid.any()
        activity_location=gl.glGetUniformLocation(program,'uChainActivity')
        assert activity_location >= 0
        gl.glUniform1f(activity_location,1.)
        free=generated(1.,free=True)
        for activity in (0.,.25,1.):
            gl.glUniform1f(activity_location,activity)
            rows=generated(1.,free=True)
            assert np.array_equal(rows[:,[0,1,3]],free[:,[0,1,3]])
            assert rows[:,2] == pytest.approx(free[:,2]*activity)
            # An invisible free-chain envelope must not remove attached wakes.
            assert np.array_equal(generated(1.),nominal)
        gl.glUniform1f(activity_location,1.)
        for amount in (.9,1.1):
            ratio=generated(1.,amount=amount,free=True)[valid,0]/free[valid,0]
            assert np.all((ratio>=.89999)&(ratio<=1.10001))
        # A thinner quality budget represents both stable owners, including a retiring source.
        sources=np.array(((-5,0,-8,.2,7,-1,1,.2)+(0.,)*(WAKE_STRIDE-8),(5,0,-8,.2,9,.4,1,.2)+(0.,)*(WAKE_STRIDE-8)),dtype='f4')
        gl.glNamedBufferData(wakes,sources.nbytes,sources,gl.GL_DYNAMIC_DRAW)
        for name,value in (('uBeadCount',0),('uSnowCount',0),('uWakeCount',2),('uFizzPer',32)):
            gl.glUniform1i(gl.glGetUniformLocation(program,name),value)
        gl.glUniform1f(gl.glGetUniformLocation(program,'uFizzFill'),31.5)
        gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,64)
        gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT | gl.GL_SHADER_STORAGE_BARRIER_BIT)
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
def test_glowing_specks_follow_authored_finite_stream_without_camera_dependent_world_positions(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import SPECK_VERTEX
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture
    prefix=SPECK_VERTEX.split('void main() {\n    speckInstance();\n')[0]
    vertex=prefix+'''
layout(std430,binding=6) buffer Results { vec4 results[]; };
void main(){speckInstance();results[gl_InstanceID]=vec4(aPoint.xyz,aLook.x);gl_Position=vec4(0,0,0,1);}
'''
    target=TransitionCapture(64,64);program=buffer=0
    try:
        program=compile_program(vertex,'#version 460 core\nout vec4 colour;\nvoid main(){colour=vec4(0);}',label='fixed speck volume')
        names=np.empty(1,dtype='u4');gl.glCreateBuffers(1,names);buffer=int(names[0])
        gl.glNamedBufferData(buffer,2048*16,None,gl.GL_DYNAMIC_READ);gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,6,buffer)
        gl.glUseProgram(program);loc=lambda name:gl.glGetUniformLocation(program,name)
        for name,value in (('uWorldUnit',9.),('uSpeckSize',1.),('uBandFreq',9.),('uSpeckTravel',.2)):
            gl.glUniform1f(loc(name),value)
        gl.glUniform3f(loc('uWorldCenter'),0,0,0);gl.glUniform3f(loc('uWorldHalf'),18,8,18)
        gl.glUniform3f(loc('uStreamWorld'),0,.58,.81);gl.glUniform3f(loc('uStreamAcross'),1,0,0)
        gl.glUniform3f(loc('uSpeckSource'),0,-8,-17)
        gl.glUniform3f(loc('uSpeckEnd'),0,8,17)
        gl.glUniform3f(loc('uClouds'),1.5,.12,1.3)
        gl.glBindVertexArray(target.vao);gl.glEnable(gl.GL_RASTERIZER_DISCARD)
        samples=[]
        for pixel,matrix in ((.001,np.eye(3,dtype='f4')),(.003,np.diag((-1.,1.,-1.)).astype('f4'))):
            gl.glUniform1f(loc('uPixel'),pixel);gl.glUniformMatrix3fv(loc('uWorldToView'),1,False,matrix)
            gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,2048);gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT | gl.GL_SHADER_STORAGE_BARRIER_BIT)
            data=np.empty((2048,4),dtype='f4');gl.glGetNamedBufferSubData(buffer,0,data.nbytes,data)
            assert np.isfinite(data).all();samples.append(data)
        assert np.array_equal(*samples)
        live = samples[0][samples[0][:,3] > .0001]
        assert len(live)>100
        assert np.all(np.abs(live[:,:3]) <= np.array((18.,8.,18.)) + 1e-4)
        # Authored source lies at floor/back and destination at ceiling/front;
        # accepted particles span that finite volume rather than a camera-centred halo.
        assert (live[:,1] < -2).sum()>10 and (live[:,1] > 2).sum()>10
        assert np.percentile(np.abs(live[:,0]), 98) < 10.0
        assert gl.glGetError()==gl.GL_NO_ERROR
    finally:
        gl.glDisable(gl.GL_RASTERIZER_DISCARD);gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,6,0)
        if buffer:gl.glDeleteBuffers(1,[buffer])
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
    vertex = vertex.replace('vOpacity = aOpacity;', 'vOpacity = uTestOpacity;')
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
        gl.glUniform2f(location('uTan'), *camera(0,0,1)[2])
        gl.glUniform2f(location('uFrameSize'),64,64)
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


@pytest.mark.qt
def test_procedural_world_positions_and_radii_do_not_follow_camera_or_pixel_size(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import BEAD_VERTEX
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    prefix=BEAD_VERTEX.split('void main() {\n    vOpacity = 1.0;\n')[0]
    vertex=prefix+'''
layout(std430,binding=6) buffer Results { vec4 results[]; };
void main(){vOpacity=1.0;beadInstance();results[gl_InstanceID]=aSphere;gl_Position=vec4(0,0,0,1);}
'''
    target=TransitionCapture(64,64);program=0;buffers=[]
    try:
        program=compile_program(vertex,'#version 460 core\nout vec4 colour;\nvoid main(){colour=vec4(0);}',label='fixed procedural world')
        names=np.empty(2,dtype='u4');gl.glCreateBuffers(2,names);buffers=list(map(int,names))
        result,wakes=buffers
        gl.glNamedBufferData(result,224*16,None,gl.GL_DYNAMIC_READ)
        source=np.array((0,0,-8,.5,7,-1,1,.5)+(0.,)*(WAKE_STRIDE-8),dtype='f4')
        gl.glNamedBufferData(wakes,source.nbytes,source,gl.GL_STATIC_DRAW)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,6,result);gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,7,wakes)
        gl.glUseProgram(program);loc=lambda name:gl.glGetUniformLocation(program,name)
        for name,value in (('uBeadCount',160),('uBeadsPerChain',160),('uSnowCount',32),('uFizzPer',32),('uWakeCount',1)):
            gl.glUniform1i(loc(name),value)
        for name,value in (('uBeadSize',1.),('uChainFill',1.),('uSnowFill',32.),('uFizzFill',32.),('uBeadTravel',.2),('uSnowDrift',.2)):
            gl.glUniform1f(loc(name),value)
        gl.glUniform3f(loc('uWorldCenter'),0,0,0);gl.glUniform3f(loc('uWorldHalf'),18,8,18)
        gl.glUniform3f(loc('uStreamWorld'),.6,.8,0)
        gl.glUniform3f(loc('uStreamAcross'),.8,-.6,0);gl.glUniform3f(loc('uStreamDepth'),0,0,-1)
        gl.glBindVertexArray(target.vao);gl.glEnable(gl.GL_RASTERIZER_DISCARD)
        samples=[]
        for angle,pixel,tan in ((0.,.001,(1.,.6)),(1.7,.003,(.6,1.)),(-2.8,.0005,(2.,.3))):
            c,s=np.cos(angle),np.sin(angle)
            matrix=np.array(((c,0,-s),(0,1,0),(s,0,c)),dtype='f4')
            gl.glUniformMatrix3fv(loc('uWorldToView'),1,False,matrix)
            gl.glUniformMatrix3fv(loc('uViewToWorld'),1,False,matrix.T.copy())
            # Deliberately perturb retired camera-placement inputs: a reintroduced dependency must fail.
            gl.glUniformMatrix3fv(loc('uViewToWorldTurn0'),1,False,matrix.T.copy())
            gl.glUniform3f(loc('uOrbit'),angle,c,s)
            gl.glUniform1f(loc('uPixel'),pixel);gl.glUniform2f(loc('uTan'),*tan)
            gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,224)
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT | gl.GL_SHADER_STORAGE_BARRIER_BIT)
            data=np.empty((224,4),dtype='f4');gl.glGetNamedBufferSubData(result,0,data.nbytes,data)
            assert np.isfinite(data).all();samples.append(data)
        assert all(np.array_equal(samples[0],row) for row in samples[1:])
        assert np.all(samples[0][:,3]>0)
        assert gl.glGetError()==gl.GL_NO_ERROR
    finally:
        gl.glDisable(gl.GL_RASTERIZER_DISCARD)
        for binding in (6,7):gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,binding,0)
        if buffers:gl.glDeleteBuffers(len(buffers),buffers)
        if program:gl.glDeleteProgram(program)
        target.close()


@pytest.mark.qt
def test_free_chain_population_band_on_gpu_matches_its_cpu_mirror(qt_app):
    """The bead shader's population edge is chain_opacity (the renderer sizes the draw by its CPU mirror)."""
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import BEAD_VERTEX
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture
    from widgets.spotify_visualizer.extruded_bubble_material_paths import chain_opacity
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
    target = TransitionCapture(64, 64)
    program = buffer = 0
    chains, per = 12, 16
    try:
        program = compile_program(vertex, '#version 460 core\nout vec4 colour;\nvoid main(){colour=vec4(0);}',
                                  label='free-chain population band')
        gl.glUseProgram(program)
        names = np.empty(1, dtype='u4')
        gl.glCreateBuffers(1, names)
        buffer = int(names[0])
        gl.glNamedBufferData(buffer, chains * per * 16, None, gl.GL_DYNAMIC_READ)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 6, buffer)
        for name, value in (('uBeadCount', chains * per), ('uBeadsPerChain', per), ('uSnowCount', 0), ('uFizzPer', 0),
                            ('uWakeCount', 0)):
            gl.glUniform1i(gl.glGetUniformLocation(program, name), value)
        for name, value in (('uBeadTravel', .2), ('uBeadSize', 1.), ('uChainActivity', 1.), ('uParticleSpread', 1.)):
            gl.glUniform1f(gl.glGetUniformLocation(program, name), value)
        gl.glUniform3f(gl.glGetUniformLocation(program, 'uStreamWorld'), 0, 1, 0)
        gl.glUniform3f(gl.glGetUniformLocation(program, 'uStreamAcross'), 1, 0, 0)
        gl.glUniform3f(gl.glGetUniformLocation(program, 'uStreamDepth'), 0, 0, -1)
        gl.glUniform3f(gl.glGetUniformLocation(program, 'uWorldHalf'), 18, 8, 18)
        gl.glBindVertexArray(target.vao)
        gl.glEnable(gl.GL_RASTERIZER_DISCARD)

        def opacities(fill):
            gl.glUniform1f(gl.glGetUniformLocation(program, 'uChainFill'), fill)
            gl.glDrawArraysInstanced(gl.GL_POINTS, 0, 1, chains * per)
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT | gl.GL_SHADER_STORAGE_BARRIER_BIT)
            rows = np.empty((chains * per, 4), dtype='f4')
            gl.glGetNamedBufferSubData(buffer, 0, rows.nbytes, rows)
            return rows[:, 2].reshape(chains, per)

        full = opacities(100.)
        seen = full > 1e-3
        assert seen.any(axis=1).all()  # every chain has visible beads to compare
        for fill in (0., .4, 1., 1.6, 3.25, 5.5, 8.9):
            expected = np.array([chain_opacity(fill, c) for c in range(chains)], dtype='f4')[:, None]
            got = opacities(fill)
            assert got[seen] == pytest.approx((full * expected)[seen], abs=1e-5)
    finally:
        gl.glDisable(gl.GL_RASTERIZER_DISCARD)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 6, 0)
        if buffer:
            gl.glDeleteBuffers(1, [buffer])
        if program:
            gl.glDeleteProgram(program)
        target.close()
