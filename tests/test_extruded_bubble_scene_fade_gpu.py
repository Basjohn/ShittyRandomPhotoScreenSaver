"""SCENE's physical fades must not erase valid thin in-tank regions."""
import numpy as np
import pytest


@pytest.mark.qt
@pytest.mark.parametrize('population,radius_share',[('specks',1.),('specks',.25),('snow',1.)])
def test_scene_particles_keep_near_wall_interior_but_fade_at_real_entry_exit_and_containment(qt_app,population,radius_share):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import SPECK_VERTEX,BEAD_VERTEX
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    # Control only the per-instance input seed. Production inlet, trajectory,
    # opacity and containment code still own the resulting point and brightness.
    if population=='specks':
        prefix=SPECK_VERTEX.split('void main() {\n    speckInstance();\n')[0]
        seed='vec3 seed = vec3(speckRandom(i,1u),speckRandom(i,3u),speckRandom(i,5u));'
        generated='speckInstance();results[gl_InstanceID]=vec4(aPoint.xyz,aLook.x);'
    else:
        prefix=BEAD_VERTEX.split('void main() {\n    vOpacity = 1.0;\n')[0]
        seed='vec3 seed = vec3(beadRandom(i, 13u), beadRandom(i, 14u), beadRandom(i, 15u));'
        generated='vOpacity=1.;beadInstance();results[gl_InstanceID]=vec4(aSphere.xyz,vOpacity);'
    assert seed in prefix
    prefix=prefix.replace(seed,'vec3 seed = uTestSeed;').replace('#version 460 core',
        '#version 460 core\nuniform vec3 uTestSeed;')
    vertex=prefix+'''
layout(std430,binding=6) buffer Results {vec4 results[];};
void main(){'''+generated+'''gl_Position=vec4(0,0,0,1);}
'''
    target=TransitionCapture(64,64);program=buffer=0
    try:
        program=compile_program(vertex,'#version 460 core\nout vec4 colour;void main(){colour=vec4(0);}',label='scene physical entry fade')
        buffer=int(gl.glGenBuffers(1));gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,buffer)
        gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER,8*16,None,gl.GL_DYNAMIC_READ)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,6,buffer)
        gl.glUseProgram(program);loc=lambda name:gl.glGetUniformLocation(program,name)
        for name,value in (('uWorldUnit',9.),('uSpeckSize',1.),('uParticleRadiusShare',radius_share),
                           ('uSpeckTravel',0.),('uBandFreq',9.)):
            gl.glUniform1f(loc(name),value)
        gl.glUniform1i(loc('uSceneEmission'),1)
        assert loc('uSceneEmission')>=0
        for name,value in (('uBeadCount',0),('uSnowCount',8),('uFizzPer',0),('uWakeCount',0)):
            gl.glUniform1i(loc(name),value)
        gl.glUniform1f(loc('uSnowFill'),8.)
        for name,xyz in (('uWorldCenter',(0,0,0)),('uWorldHalf',(18,8,18)),
                         ('uSceneFaces',(0,1,0)),('uSpeckSource',(0,-8,0)),('uSpeckEnd',(0,8,0)),
                         ('uStreamSource',(0,-8,0)),('uStreamEnd',(0,8,0)),
                         ('uStreamWorld',(0,1,0)),('uStreamAcross',(1,0,0)),('uClouds',(1,1,0))):
            gl.glUniform3f(loc(name),*xyz)
        gl.glBindVertexArray(target.vao);gl.glEnable(gl.GL_RASTERIZER_DISCARD)
        def generated(y,z):
            assert loc('uTestSeed')>=0
            gl.glUniform3f(loc('uTestSeed'),.5,(y+8)/16,(z+18)/36)
            current=np.empty(3,dtype='f4')
            gl.glGetUniformfv(program,loc('uTestSeed'),current)
            assert current==pytest.approx((.5,(y+8)/16,(z+18)/36))
            gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,8)
            # CPU readback and subsequent shader writes both need visibility;
            # UPDATE alone can return the previous uniform variant on native GL.
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT | gl.GL_SHADER_STORAGE_BARRIER_BIT)
            rows=np.empty((8,4),dtype='f4');gl.glGetNamedBufferSubData(buffer,0,rows.nbytes,rows)
            return rows
        centre=generated(-7.5,0.);wall=generated(-7.5,17.9)
        assert np.allclose(centre[:,:3],(0,-7.5,0))
        assert np.allclose(wall[:,:3],(0,-7.5,17.9))
        assert centre[:,3].max()>0
        assert wall[:,3] == pytest.approx(centre[:,3],rel=1e-4,abs=1e-7)
        assert generated(-8.,0.)[:,3].max()==0  # Entry remains transparent.
        assert generated(0.,18.)[:,3].max()==0
        assert generated(0.,18.1)[:,3].max()==0
        departing=generated(7.999,0.)[:,3]
        assert 0<departing.max()<centre[:,3].max()
        if population=='specks' and radius_share==.25:
            # The split energy/display owners must preserve the former physical
            # entry/wall/exit fade: contracted authored radius, display share1.
            probes=((-7.99,0.),(0.,17.99),(7.99,0.))
            actual=[generated(y,z).copy() for y,z in probes]
            gl.glUniform1f(loc('uSpeckSize'),radius_share)
            gl.glUniform1f(loc('uParticleRadiusShare'),1.)
            for (y,z),expected in zip(probes,actual):
                assert generated(y,z)==pytest.approx(expected,rel=1e-5,abs=1e-7)
        assert gl.glGetError()==gl.GL_NO_ERROR
    finally:
        gl.glDisable(gl.GL_RASTERIZER_DISCARD);gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,6,0)
        if buffer:gl.glDeleteBuffers(1,[buffer])
        if program:gl.glDeleteProgram(program)
        target.close()
