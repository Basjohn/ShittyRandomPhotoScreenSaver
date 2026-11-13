"""Execute the production generator against frozen logical displacement on native GL."""
import numpy as np
import pytest
from tests.test_extruded_bubble_renderer import target, _snapshot
from rendering.quick.render.gl_resources import delete_program


def test_production_beads_sample_frozen_paths_without_changing_radius(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import BEAD_VERTEX
    from rendering.quick.render.gl_resources import compile_program
    from tools.labs.render_target import OffscreenRenderTarget
    from widgets.spotify_visualizer.extruded_bubble_material_paths import PATH_NODES
    prefix=BEAD_VERTEX.split('void main() {\n    vOpacity = 1.0;\n')[0]
    vertex=prefix+'''
layout(std430,binding=5) buffer DriftResults { vec4 driftResults[]; };
void main() {
    vOpacity=1.0;beadInstance();driftResults[gl_InstanceID]=aSphere;
    gl_Position=vec4(0.0,0.0,0.0,1.0);
}
'''
    target=OffscreenRenderTarget(64,64);program=0;buffers=[]
    try:
        program=compile_program(vertex,'#version 460 core\nout vec4 colour;\nvoid main(){colour=vec4(0);}',label='production frozen bead drift')
        gl.glUseProgram(program)
        names=np.empty(2,dtype='u4');gl.glCreateBuffers(2,names);buffers=list(map(int,names))
        result,paths=buffers
        gl.glNamedBufferData(result,160*16,None,gl.GL_DYNAMIC_READ)
        data=np.zeros((PATH_NODES,4),dtype='f4');data[:,:3]=(1.25,0.,-.75)
        gl.glNamedBufferData(paths,data.nbytes,data,gl.GL_STATIC_DRAW)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,5,result)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,6,paths)
        for key,value in (('uBeadCount',160),('uBeadsPerChain',160),('uSceneEmission',0)):
            gl.glUniform1i(gl.glGetUniformLocation(program,key),value)
        for key,value in (('uBeadTravel',2.),('uBeadSize',1.),('uParticleSpread',1.)):
            gl.glUniform1f(gl.glGetUniformLocation(program,key),value)
        for key,value in (('uStreamSource',(0,-8,0)),('uStreamEnd',(0,8,0)),('uStreamWorld',(0,1,0)),
                          ('uStreamAcross',(1,0,0)),('uStreamDepth',(0,0,-1)),('uWorldHalf',(18,8,18))):
            gl.glUniform3f(gl.glGetUniformLocation(program,key),*value)
        gl.glBindVertexArray(target.vao);gl.glEnable(gl.GL_RASTERIZER_DISCARD)
        output=[]
        for enabled in (0,1,0):
            gl.glUniform1i(gl.glGetUniformLocation(program,'uChainDriftEnabled'),enabled)
            gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,160)
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT|gl.GL_SHADER_STORAGE_BARRIER_BIT)
            rows=np.empty((160,4),dtype='f4');gl.glGetNamedBufferSubData(result,0,rows.nbytes,rows);output.append(rows)
        assert np.array_equal(output[0],output[2])
        assert np.allclose(output[1][:,:3]-output[0][:,:3],(1.25,0,-.75),atol=2e-6)
        assert np.array_equal(output[0][:,3],output[1][:,3])
        # A layer fading out (uDriftFadeOut): its contribution scales by what is left of it, down to none.
        gl.glUniform1i(gl.glGetUniformLocation(program,'uChainDriftEnabled'),1)
        for fade in (.25,.5,1.):
            gl.glUniform1f(gl.glGetUniformLocation(program,'uDriftFadeOut'),fade)
            gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,160)
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT|gl.GL_SHADER_STORAGE_BARRIER_BIT)
            rows=np.empty((160,4),dtype='f4');gl.glGetNamedBufferSubData(result,0,rows.nbytes,rows)
            assert np.allclose(rows[:,:3]-output[0][:,:3],(1.-fade)*np.array((1.25,0,-.75)),atol=2e-6), fade
        gl.glUniform1f(gl.glGetUniformLocation(program,'uDriftFadeOut'),0.)
        assert gl.glGetError()==gl.GL_NO_ERROR
    finally:
        gl.glDisable(gl.GL_RASTERIZER_DISCARD)
        if buffers:gl.glDeleteBuffers(len(buffers),buffers)
        if program:delete_program(program)
        target.close()


def test_production_host_integrates_only_live_drift_and_restores_zero_picture(target):
    from dataclasses import replace
    from widgets.spotify_visualizer.extruded_bubble_simulation import (
        ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput)
    capture,host=target
    snap=_snapshot(extruded_bubble_bead_chains=[2.,2.],extruded_bubble_particles=[0.,0.])
    state=replace(snap.logical.mode_state,chain_activity=1.)
    snap=replace(snap,logical=replace(snap.logical,mode_state=state))
    capture.render(host,snap);base=capture.render(host,snap)
    renderer=host._implementations['extruded_bubble']
    assert not renderer._drift.output
    # A real logical drift log: chains only, strong Clockwise drift for two seconds.
    controls=ExtrudedBubbleControls(large_count=(0,0),mid_count=(0,0),bead_chains=(2.,2.),emission=(0.,0.),
        stream_path=(0.,-1.,0.,0.,1.,0.),drift=(1.,1.),drift_chains=(2.,2.),drift_direction='swirl_cw',
        stream_speed=(.1,.1))
    sim=ExtrudedBubbleSimulation(7)
    for _ in range(120):
        logical=sim.advance(MusicInput(1/60,True,1.,(),(.6,.5,.3)),controls)
        assert [family.family for family in logical.drift_families]==['chains']
        changed=replace(snap,logical=replace(snap.logical,mode_state=replace(
            state,drift_families=logical.drift_families,drift_steps=logical.drift_steps,
            drift_knots=logical.drift_knots)))
        moved=capture.render(host,changed)
    assert renderer._drift.output
    assert np.abs(moved-base).mean()>.01
    assert np.array_equal(capture.render(host,snap),base)


def test_a_drift_program_that_fails_to_compile_is_logged_once_and_the_mode_draws_without_drift(target,monkeypatch,
                                                                                                caplog):
    """What a device whose compiler refuses a drift program gets: the shared resources cache the failure (one compile
    attempt and one logged error per program and context), the warm-up completes, and every frame that carries drift
    draws Extruded Bubble without drift (the picture of the same frame without drift), never an empty card."""
    from dataclasses import replace
    from rendering.quick.scene3d import resources as scene_resources
    from rendering.quick.visualizer.implementations import extruded_bubble as eb
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as solver
    from widgets.spotify_visualizer.extruded_bubble_simulation import (
        ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput)
    capture,host=target
    snap=_snapshot(extruded_bubble_bead_chains=[2.,2.],extruded_bubble_particles=[0.,0.])
    base=capture.render(host,snap)                   # the healthy drift-free picture (programs compiled as shipped)
    host.release_resources()
    broken=(('drift_chains_broken',solver.CHAIN_COMPUTE+'\nthis is not GLSL;\n'),*solver.PROGRAMS[1:])
    monkeypatch.setattr(solver,'PROGRAMS',broken)
    monkeypatch.setattr(eb,'_DRIFT_PROGRAMS',broken)
    attempts=[]
    compile_compute=scene_resources.compile_compute_program
    monkeypatch.setattr(scene_resources,'compile_compute_program',
                        lambda source,label: (attempts.append(label),compile_compute(source,label=label))[1])
    from rendering.quick.visualizer import render_host
    monkeypatch.setattr(render_host,'PREPARE_SPACING_S',0.)
    hidden=_snapshot(fade=0.0,extruded_bubble_bead_chains=[2.,2.],extruded_bubble_particles=[0.,0.])
    assert np.abs(base-base[0,0]).max()>0                     # the healthy picture is not an empty card
    with caplog.at_level('ERROR'):
        for _ in range(400):                              # the warm-up's units, one per hidden frame: it completes
            capture.render(host,hidden)
            if host.prepared_activation is not None:
                break
        assert host.prepared_activation is not None
        controls=ExtrudedBubbleControls(large_count=(0,0),mid_count=(0,0),bead_chains=(2.,2.),emission=(0.,0.),
            stream_path=(0.,-1.,0.,0.,1.,0.),drift=(1.,1.),drift_chains=(2.,2.),drift_direction='swirl_cw',
            stream_speed=(.1,.1))
        sim=ExtrudedBubbleSimulation(7)
        for _ in range(30):
            logical=sim.advance(MusicInput(1/60,True,1.,(),(.6,.5,.3)),controls)
            drifting=replace(snap,logical=replace(snap.logical,mode_state=replace(
                snap.logical.mode_state,drift_families=logical.drift_families,drift_steps=logical.drift_steps,
                drift_knots=logical.drift_knots)))
            assert np.array_equal(capture.render(host,drifting),base)   # drawn, without drift
    broken_label=[label for label in attempts if 'drift_chains_broken' in label]
    assert len(broken_label)==1, attempts                                  # one compile attempt in all those frames
    lines=[record for record in caplog.records if record.levelname=='ERROR']
    assert len(lines)==1 and 'drift_chains_broken' in lines[0].getMessage(), [r.getMessage() for r in lines]
    renderer=host._implementations['extruded_bubble']
    assert not renderer._drift.output and not renderer._drift.has_resources
    assert np.array_equal(capture.render(host,snap),base)   # no drift: Extruded Bubble draws exactly as before


def test_a_history_carried_into_a_window_whose_drift_programs_fail_fades_out_instead_of_vanishing(target,monkeypatch):
    """A display move carries a drift history into a window whose drift programs do not compile: the history cannot
    advance there, so its drift layer fades out over the mode's fade-out length (counted in the logical steps' time),
    decreasing frame by frame, and only then is the mode drawn without drift (fade, never vanish)."""
    from dataclasses import replace
    from rendering.quick.visualizer.implementations import extruded_bubble as eb
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as solver
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost,VisualizerRenderCarryover
    from widgets.spotify_visualizer.extruded_bubble_simulation import (
        ExtrudedBubbleControls, ExtrudedBubbleSimulation, FADE_OUT_SECONDS, MusicInput)
    capture,host=target
    snap=_snapshot(extruded_bubble_bead_chains=[2.,2.],extruded_bubble_particles=[0.,0.])
    snap=replace(snap,logical=replace(snap.logical,mode_state=replace(snap.logical.mode_state,chain_activity=1.)))
    capture.render(host,snap);base=capture.render(host,snap)       # the picture without drift
    controls=ExtrudedBubbleControls(large_count=(0,0),mid_count=(0,0),bead_chains=(2.,2.),emission=(0.,0.),
        stream_path=(0.,-1.,0.,0.,1.,0.),drift=(1.,1.),drift_chains=(2.,2.),drift_direction='swirl_cw',
        stream_speed=(.1,.1))
    sim=ExtrudedBubbleSimulation(7);frames=[]
    for _ in range(90+int(1.5*FADE_OUT_SECONDS*60)):
        logical=sim.advance(MusicInput(1/60,True,1.,(),(.6,.5,.3)),controls)
        frames.append(replace(snap,logical=replace(snap.logical,mode_state=replace(
            snap.logical.mode_state,drift_families=logical.drift_families,drift_steps=logical.drift_steps,
            drift_knots=logical.drift_knots))))
    for frame in frames[:90]:
        moved=capture.render(host,frame)
    assert np.abs(moved-base).mean()>.01                            # the source draws a strong drift
    payload=host._implementations['extruded_bubble'].export_carryover()
    assert payload is not None
    # The target window's context cannot compile the drift programs (its own shared resources, as on another device).
    broken=(('drift_chains_broken',solver.CHAIN_COMPUTE+'\nthis is not GLSL;\n'),*solver.PROGRAMS[1:])
    monkeypatch.setattr(solver,'PROGRAMS',broken)
    monkeypatch.setattr(eb,'_DRIFT_PROGRAMS',broken)
    second=QuickVisualizerRenderHost()
    try:
        box=VisualizerRenderCarryover();box.deposit('extruded_bubble',payload);box.close()
        second.expect_carryover(box)
        drift,fades=[],[]
        for frame in frames[90:]:
            drift.append(float(np.abs(capture.render(second,frame)-base).mean()))
            renderer=second._implementations['extruded_bubble']
            # The fade the draws were given this frame (what scales the drift layer's contribution in the shaders).
            uploaded={value for (_program,name),value in renderer._uniforms._values.items() if name=='uDriftFadeOut'}
            assert len(uploaded)==1, uploaded
            fades.append((uploaded.pop(),bool(renderer._drift.output)))
        fading=[i for i,(fade,held) in enumerate(fades) if 0.<fade<1. and held]
        # The drawn contribution is (1 - fade) of the carried drift: it decreases on every frame of about the mode's
        # fade-out length (the shaders' scaling is pinned by the generator tests above and below).
        assert fading==list(range(len(fading))) and len(fading)>=int(.8*FADE_OUT_SECONDS*60), fades
        assert all(later[0]>earlier[0] for earlier,later in zip(fades[:len(fading)],fades[1:len(fading)]))
        assert drift[0]>.5*np.abs(moved-base).mean()                 # the first frame still draws the carried drift
        assert all(value>0. for value in drift[:len(fading)])         # drawn with drift on every fading frame
        assert drift[-1]==0. and fades[-1]==(0.,False)                # then drawn without drift, the output released
        assert not second._implementations['extruded_bubble']._drift.has_resources
    finally:
        second.release_resources()


@pytest.mark.parametrize('family',('snow','specks'))
@pytest.mark.parametrize('coverage',('BEAM','SCENE'))
def test_production_cloud_generators_read_nonuniform_stable_id_offsets_without_resizing_motes(qt_app,family,coverage):
    from OpenGL import GL
    from rendering.gl_programs.extruded_bubble_program import BEAD_VERTEX,PARTICLE_BLOCK,SPECK_VERTEX
    from rendering.quick.render.gl_resources import compile_program
    from tools.labs.render_target import OffscreenRenderTarget
    from tools.pass_block_gl import PassBlockGL
    gl=PassBlockGL(GL)          # the generators' values are their pass block (N1.6), set by name as before
    block={'specks':PARTICLE_BLOCK}.get(family)
    from widgets.spotify_visualizer.extruded_bubble_simulation import ExtrudedBubbleControls
    from widgets.spotify_visualizer.extruded_bubble_material_paths import cloud_geometry,ProceduralOffsets
    from widgets.spotify_visualizer.extruded_bubble_geometry import stream_basis,scene_source_face_weights,WORLD_HALF
    from core.settings.visualizer_paths import world_point,direction_of
    controls=ExtrudedBubbleControls(stream_path=(0.,-1.,0.,.4,1.,.3) if coverage=='SCENE' else (0.,-1.,0.,0.,1.,0.),
                                    emission_geometry=coverage)
    direction=direction_of(controls.stream_path,WORLD_HALF);across,depth=stream_basis(direction)
    weights=scene_source_face_weights(controls.stream_path[:3],direction)
    geometry=cloud_geometry(controls,direction,across,depth,weights,family,160)
    if family=='snow':
        prefix=BEAD_VERTEX.split('void main() {\n    vOpacity = 1.0;\n')[0]
        generate='vOpacity=1.0;beadInstance();';value='aSphere';visibility='vOpacity';control='uSnowDriftOffset'
    else:
        prefix=SPECK_VERTEX.split('void main() {\n    speckInstance();\n')[0]
        generate='speckInstance();';value='aPoint';visibility='aLook.x';control='uSpeckDriftOffset'
    vertex=prefix+'''layout(std430,binding=5) buffer DriftResults { vec4 driftResults[]; };
void main() {'''+generate+'driftResults[gl_InstanceID]='+value+';driftResults[160+gl_InstanceID]=vec4('+visibility+''');
gl_Position=vec4(0.0,0.0,0.0,1.0);}
'''
    target=OffscreenRenderTarget(64,64);program=0;buffers=[]
    try:
        program=compile_program(vertex,'#version 460 core\nout vec4 colour;\nvoid main(){colour=vec4(0);}',label='production cloud drift '+family)
        if block is not None:
            gl.register(program,block)
        gl.glUseProgram(program)
        names=np.empty(2,dtype='u4');gl.glCreateBuffers(2,names);buffers=list(map(int,names))
        result,paths=buffers;gl.glNamedBufferData(result,320*16,None,gl.GL_DYNAMIC_READ)
        data=np.zeros((160,4),dtype='f4')
        data[:,0]=.1+np.arange(160)*.003;data[:,2]=-.4+np.arange(160)*.002
        gl.glNamedBufferData(paths,data.nbytes,data,gl.GL_STATIC_DRAW)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,5,result);gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,6,paths)
        for key,value_ in (('uBeadCount',0),('uSnowCount',160),('uSceneEmission',int(coverage=='SCENE'))):
            gl.glUniform1i(gl.glGetUniformLocation(program,key),value_)
        for key,value_ in (('uParticleSpread',1.),('uWorldUnit',9.),('uSnowDrift',2.),('uSnowFill',160.),('uSpeckTravel',2.),('uSpeckSize',1.)):
            gl.glUniform1f(gl.glGetUniformLocation(program,key),value_)
        source=world_point(controls.stream_path[:3],WORLD_HALF);end=world_point(controls.stream_path[3:],WORLD_HALF)
        for key,value_ in (('uStreamSource',source),('uStreamEnd',end),('uSpeckSource',source),
                ('uSpeckEnd',end),('uStreamWorld',direction),('uStreamAcross',across),('uStreamDepth',depth),
                ('uWorldHalf',WORLD_HALF),('uSceneFaces',weights),('uClouds',(1.,1.,1.))):
            gl.glUniform3f(gl.glGetUniformLocation(program,key),*value_)
        gl.glBindVertexArray(target.vao);gl.glEnable(gl.GL_RASTERIZER_DISCARD)
        output=[]
        for encoded in (0,1,0):
            gl.glUniform1i(gl.glGetUniformLocation(program,control),encoded)
            gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,160)
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT|gl.GL_SHADER_STORAGE_BARRIER_BIT)
            rows=np.empty((160,4),dtype='f4');gl.glGetNamedBufferSubData(result,0,rows.nbytes,rows);output.append(rows)
            if encoded==0 and len(output)==1:
                data[:,3]=np.mod(geometry[2]+2./geometry[1],1.)
                gl.glNamedBufferSubData(paths,0,data.nbytes,data)
        assert np.array_equal(output[0],output[2])
        # Legacy float32 travel/span vs logical resolved progress: bound the
        # activation difference in pixels, not a weakened relative world error.
        assert np.abs(output[1][:,:3]-output[0][:,:3]-data[:,:3]).max()*350.<.03
        assert np.array_equal(output[0][:,3],output[1][:,3])
        # A layer fading out (uDriftFadeOut): half its displacement, on the procedural progress it converges to.
        gl.glUniform1i(gl.glGetUniformLocation(program,control),1)
        gl.glUniform1f(gl.glGetUniformLocation(program,'uDriftFadeOut'),.5)
        gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,160)
        gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT|gl.GL_SHADER_STORAGE_BARRIER_BIT)
        rows=np.empty((160,4),dtype='f4');gl.glGetNamedBufferSubData(result,0,rows.nbytes,rows)
        assert np.abs(rows[:,:3]-output[0][:,:3]-.5*data[:,:3]).max()*350.<.03
        gl.glUniform1f(gl.glGetUniformLocation(program,'uDriftFadeOut'),0.)
        owner=ProceduralOffsets();travel=2./geometry[3]
        for i in range(3):
            travel+=1/60
            packed=owner.advance(geometry,'actual',travel,1.,1/60,kind='swirl_cw',phase=.7,
                direction=direction,across=across,depth_axis=depth,origin=(0,0,0),amount=18.)
            gl.glNamedBufferSubData(paths,0,packed.nbytes,packed)
            gl.glUniform1i(gl.glGetUniformLocation(program,control),1)
            gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,160)
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT|gl.GL_SHADER_STORAGE_BARRIER_BIT)
            rows=np.empty((160,4),dtype='f4');gl.glGetNamedBufferSubData(result,0,rows.nbytes,rows)
            assert np.abs(rows[:,:3]-owner.previous_base-owner.displacement).max()*350.<.01
        visibility_rows=np.empty((160,4),dtype='f4')
        gl.glGetNamedBufferSubData(result,160*16,visibility_rows.nbytes,visibility_rows)
        assert visibility_rows[:,0].max()>0.
        packed[:,3]=np.mod(packed[:,3],1.)-1.
        gl.glNamedBufferSubData(paths,0,packed.nbytes,packed)
        gl.glDrawArraysInstanced(gl.GL_POINTS,0,1,160)
        gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT|gl.GL_SHADER_STORAGE_BARRIER_BIT)
        gl.glGetNamedBufferSubData(result,160*16,visibility_rows.nbytes,visibility_rows)
        assert np.max(np.abs(visibility_rows))==0.
        assert gl.glGetError()==gl.GL_NO_ERROR
    finally:
        gl.release()
        gl.glDisable(gl.GL_RASTERIZER_DISCARD)
        if buffers:gl.glDeleteBuffers(len(buffers),buffers)
        if program:delete_program(program)
        target.close()
