"""Production-shaped waveform configuration, ownership and native preparation gates."""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import require_mode_settings
from core.waveform_ribbon_dynamics import WaveformDynamics
from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime
from widgets.spotify_visualizer.render_state import WaveformRibbonFrame, freeze_render_fields


def parameters():
    return {control.key:require_canonical_default('widgets.spotify_visualizer.'+control.key)
            for control in require_mode_settings('waveform_ribbon').controls}


def test_nested_configuration_edits_invalidate_the_compiled_consumer():
    values=parameters();runtime=WaveformRibbonFrameRuntime()
    first=runtime.configure(values)
    assert runtime.configure(values) is first
    values['waveform_ribbon_routing']['height'][0][0]=.4
    second=runtime.configure(values)
    assert second is not first and second.controls.routing['height'][0][0]==.4
    values['waveform_ribbon_ribbons'][0]['quiet'][0][0]=.42
    third=runtime.configure(values)
    assert third is not second and third.controls.cards[0]['quiet'][0][0]==.42
    runtime.retire()
    assert runtime.configure(values) is None


def test_floor_and_mist_ranges_follow_passage_independently_of_light_routing():
    values=parameters()
    values['waveform_ribbon_mist_enabled']=True  # Explicitly exercise the optional retained volume.
    values['waveform_ribbon_routing']['light']=[[0.,1.] for _ in range(6)]
    values['waveform_ribbon_floor_brightness']=[.2,2.]
    values['waveform_ribbon_fog_density']=[.01,.1]
    config=CompiledWaveformSettings(values);model=WaveformDynamics(config.controls)
    for _ in range(64):model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
    quiet=config.scene(model.snapshot())
    for _ in range(90):snapshot=model.advance(1/90,bands=(.8,.7,.6),intensity=.9,presence=1.)
    hot=config.scene(snapshot)
    assert dict(snapshot.drives)['light']==0.
    assert hot.floor.albedo_gain>quiet.floor.albedo_gain+1.
    assert hot.fog.density>quiet.fog.density+.04


@pytest.mark.qt
def test_floor_material_remains_visible_without_any_reflection_or_atmosphere(qt_app):
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target=OffscreenRenderTarget(640,300);renderer=QuickWaveformRibbonRenderer()
    try:
        frame=frame_for(target);state=frame.snapshot.logical.mode_state
        floor=replace(state.scene.floor,reflection=0.,albedo_gain=2.)
        scene=replace(state.scene,fog=None,floor=floor)
        frame.snapshot.logical.mode_state=replace(state,scene=scene)
        target.bind();renderer.render(frame)
        material=target.read_rgba()[230:290,20:620,:3].astype(float)
        assert np.median(material)>8.,'Foreground material is still black outside core reflections'
        assert np.std(material.mean(2))>1.,'Filtered concrete lost all readable surface variation'
        frame.snapshot.logical.mode_state=replace(state,scene=replace(scene,floor=replace(floor,albedo_gain=0.)))
        target.bind();renderer.render(frame)
        dark=target.read_rgba()[230:290,20:620,:3].astype(float)
        assert material.mean()>dark.mean()+8.
    finally:renderer.release_resources();target.close()


def frame_for(target, *, ready=True):
    values=parameters();values['waveform_ribbon_mist_enabled']=True
    configuration=CompiledWaveformSettings(values)
    model=WaveformDynamics(configuration.controls)
    for _ in range(64):snapshot=model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
    camera={key:value for key,value in values.items() if key.startswith('waveform_ribbon_camera_')
            or key in ('waveform_ribbon_turn','waveform_ribbon_tilt','waveform_ribbon_scene_scale',
                       'waveform_ribbon_scene_pan_x','waveform_ribbon_scene_pan_y')}
    state=WaveformRibbonFrame(snapshot.packet,configuration.scene(snapshot),snapshot.time,snapshot.travel,
        snapshot.rotation_angle,snapshot.rotation_speed,snapshot.drives,snapshot.realized,
        ready=ready,parameters=freeze_render_fields(camera))
    presentation=SimpleNamespace(content_fade=1.,viewport_extent=(420.,280.),baseline_viewport_size=(420.,280.),
        outer_rect=(0.,0.,420.,280.),content_rect=(0.,0.,420.,280.),uniform_visual_scale=1.,
        shell_style=freeze_render_fields({'content_inset':0.,'authored_border_width':0.}))
    return SimpleNamespace(snapshot=SimpleNamespace(logical=SimpleNamespace(mode_state=state),presentation=presentation),
        content_rotation_quarters=0,scene_output_rotation=0,
        viewport=(0,0,target.width,target.height),logical_size=(float(target.width),float(target.height)),
        matrix_values=(2/target.width,0,0,0,0,-2/target.height,0,0,0,0,1,0,-1,1,0,1),quad_vao=target.vao)


@pytest.mark.qt
def test_cancel_after_shader_warm_before_any_draw_retires_in_the_admitted_context(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from tools.labs.render_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target=OffscreenRenderTarget(80,60);renderer=QuickWaveformRibbonRenderer()
    try:
        frame=frame_for(target,ready=False)
        for _ in range(30):assert renderer.prepare_step(frame) is False
        assert renderer.has_resources
        foreign=OffscreenRenderTarget(16,16)
        try:
            with pytest.raises(RuntimeError,match='foreign'):renderer.release_resources()
            assert renderer.has_resources
        finally:foreign.close()
        with target.current():
            renderer.release_resources()
            assert not renderer.has_resources
    finally:
        with target.current():renderer.release_resources()
        target.close()


@pytest.mark.qt
def test_preparation_spreads_shader_compiles_and_visible_draw_compiles_nothing(qt_app,monkeypatch):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from tools.labs.render_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target=OffscreenRenderTarget(160,120);renderer=QuickWaveformRibbonRenderer()
    links=[];original=gl.glLinkProgram
    def link(program):links.append(program);return original(program)
    monkeypatch.setattr(gl,'glLinkProgram',link)
    try:
        frame=frame_for(target)
        for _ in range(80):
            before=len(links);prepared=renderer.prepare_step(frame)
            assert len(links)-before<=1
            if prepared:break
        else:pytest.fail('Waveform preparation did not finish')
        before=len(links);target.bind(clear=(0.,0.,0.,0.));renderer.render(frame)
        assert len(links)==before
        assert target.read_rgba()[:,:,:3].max()>100
    finally:
        renderer.release_resources();target.close()


@pytest.mark.qt
@pytest.mark.parametrize('initial_sparks',(False,True))
def test_revealed_sparks_off_on_recreates_resources_and_draws_birth_records(qt_app,initial_sparks):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from tools.labs.render_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    from core.ribbon_bursts import CAPACITY
    target=OffscreenRenderTarget(160,120);renderer=QuickWaveformRibbonRenderer()
    try:
        frame=frame_for(target);original=frame.snapshot.logical.mode_state
        if not initial_sparks:
            frame.snapshot.logical.mode_state=replace(original,scene=replace(original.scene,sparks=None))
        for _ in range(80):
            if renderer.prepare_step(frame):break
        off=replace(original,scene=replace(original.scene,sparks=None),time=.2)
        frame.snapshot.logical.mode_state=off
        target.bind();renderer.render(frame);before=target.read_rgba()
        assert not renderer._scene.bursts.has_resources
        births=np.zeros((CAPACITY,16),np.float32)
        births[0,:]=(0.,2.,0.,0.,0.,0.,0.,2.,1.,1.,1.,24.,40.,.5,.3,1.)
        frame.snapshot.logical.mode_state=replace(original,time=.2,particles=births.tobytes())
        target.bind();renderer.render(frame);after=target.read_rgba()
        assert renderer._scene.bursts.has_resources
        assert np.max(np.abs(after.astype(int)-before.astype(int)))>10
        frame.snapshot.logical.mode_state=off
        target.bind();renderer.render(frame)
        assert not renderer._scene.bursts.has_resources
    finally:
        renderer.release_resources();target.close()


@pytest.mark.qt
def test_settings_preview_uses_current_controls_and_retires_its_context(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from PySide6.QtGui import QOpenGLContext
    from ui.widgets.waveform_ribbon_preview import render_samples
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    caller=OffscreenRenderTarget(16,16)
    try:
        images=render_samples(parameters(),size=(160,120))
        assert len(images)==3 and all((image.width(),image.height())==(160,120) for image in images)
        assert images[0]!=images[2]
        assert QOpenGLContext.currentContext() is caller.context
    finally:caller.close()


@pytest.mark.qt
def test_scene_uploads_one_packet_for_all_passes_and_keeps_pixels(qt_app,monkeypatch):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    from rendering.quick.scene3d.stream import StreamRing
    target=OffscreenRenderTarget(160,120);renderer=QuickWaveformRibbonRenderer()
    copies=[];original=StreamRing.rebind
    def recorded(self,target_,binding,data):
        if self.label=='ribbon knots':copies.append(len(data))
        return original(self,target_,binding,data)
    monkeypatch.setattr(StreamRing,'rebind',recorded)
    try:
        frame=frame_for(target)
        for _ in range(80):
            if renderer.prepare_step(frame):break
        copies.clear();target.bind();renderer.render(frame)
        assert copies==[len(frame.snapshot.logical.mode_state.packet.payload)]
        assert target.read_rgba()[:,:,:3].max()>100
    finally:renderer.release_resources();target.close()




@pytest.mark.qt
def test_non_origin_host_scissor_clips_only_final_composition(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target=OffscreenRenderTarget(320,240);renderer=QuickWaveformRibbonRenderer()
    try:
        frame=frame_for(target);frame.logical_size=(160.,120.)
        frame.matrix_values=(2/320,0,0,0,0,-2/240,0,0,0,0,1,0,-1,1,0,1)
        target.bind();renderer.render(frame);baseline=target.read_rgba()[:120,:160]
        frame.matrix_values=(*frame.matrix_values[:12],-.5,.5,0,1)
        target.bind();gl.glScissor(80,60,160,120);gl.glEnable(gl.GL_SCISSOR_TEST)
        renderer.render(frame);positioned=target.read_rgba()[60:180,80:240]
        assert bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        np.testing.assert_allclose(positioned,baseline,atol=1)
    finally:
        gl.glDisable(gl.GL_SCISSOR_TEST);renderer.release_resources();target.close()


@pytest.mark.qt
def test_floor_draw_count_is_its_mesh_not_the_envelope_sample_count(qt_app,monkeypatch):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target=OffscreenRenderTarget(160,120);renderer=QuickWaveformRibbonRenderer();counts=[]
    draw=gl.glDrawArrays
    def checked(mode,first,count):
        if int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM))==renderer._scene.resources._programs.get('floor'):
            counts.append(count)
        return draw(mode,first,count)
    monkeypatch.setattr(gl,'glDrawArrays',checked)
    try:
        target.bind();renderer.render(frame_for(target))
        assert counts and all(count==6 for count in counts),counts
    finally:renderer.release_resources();target.close()


@pytest.mark.qt
def test_floor_specular_cap_preserves_reflection_at_identical_view_and_snapshot(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target=OffscreenRenderTarget(320,240);renderer=QuickWaveformRibbonRenderer()
    try:
        frame=frame_for(target);state=frame.snapshot.logical.mode_state
        def pixels(cap,reflection):
            floor=replace(state.scene.floor,specular_max_height=cap,reflection=reflection)
            frame.snapshot.logical.mode_state=replace(state,scene=replace(state.scene,floor=floor))
            target.bind();renderer.render(frame)
            return target.read_rgba()[160:225,35:285,:3].astype(float)
        inline=pixels(10000,4.5)-pixels(10000,0.)
        capped=pixels(120,4.5)-pixels(120,0.)
        a,b=inline.clip(0).mean(),capped.clip(0).mean()
        assert a>1. and .8<b/a<1.2,(a,b,b/a)
    finally:renderer.release_resources();target.close()
