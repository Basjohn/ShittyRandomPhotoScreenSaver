"""Real-GL proof of the production celestial transfer and optional rim marks."""
from dataclasses import asdict
import numpy as np
import pytest
from OpenGL import GL as gl
from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_settings import require_mode_settings, Toggle
from rendering.gl_programs.neon_celestial import NEON_CELESTIAL_GLSL
from tools.transition_contact_sheet import TransitionCapture


@pytest.mark.qt
def test_production_moon_exterior_halo_surrounds_every_phase(qt_app):
    """Observe the actual pre-bloom corona, so face spill cannot hide a missing side."""
    from tests.test_neon_lake_renderer import _snapshot, _wire_frame, _resolved_emission_pixels
    from tests.test_qtquick_extruded_spectrum import _Target, W, H
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost

    capture, host = _Target(), QuickVisualizerRenderHost()
    base = _snapshot(shockwave_grid_sun_mode='Moon', shockwave_grid_sun_x=0.,
                     shockwave_grid_sun_y=3., shockwave_grid_sun_z=-6., shockwave_grid_sun_size=.45,
                     shockwave_grid_sun_orbit_enabled=False, shockwave_grid_sun_rays_enabled=False,
                     shockwave_grid_water_reflection=0., shockwave_grid_glow=.55,
                     shockwave_grid_sky_enabled=True, shockwave_grid_starscape_beat=False,
                     shockwave_grid_star_color=[0,0,0,0], shockwave_grid_cloud_color=[0,0,0,0],
                     shockwave_grid_moon_color=[190,220,255,255],
                     shockwave_grid_celestial_glow_strength=1.,
                     shockwave_grid_celestial_glow_reactivity=0., shockwave_grid_celestial_rim_vertices=False,
                     shockwave_grid_tilt=.17, shockwave_grid_turn=0., shockwave_grid_scene_scale=.75)
    try:
        def draw(phase, halo, enabled=True):
            colour = capture.render(host, _wire_frame(base, 'Vertices',
                shockwave_grid_moon_phase=phase, shockwave_grid_sun_enabled=enabled,
                shockwave_grid_celestial_glow_enabled=halo))
            return colour, _resolved_emission_pixels(host._implementations['shockwave_grid'])

        absent, _ = draw(.5, False, False)
        full, _ = draw(.5, False)
        y, x = np.nonzero(np.max(np.abs(full-absent),axis=2)>8)
        assert len(x)>30
        cx, cy = .5*(x.min()+x.max()), .5*(y.min()+y.max())
        rx, ry = .5*(x.max()-x.min()+1), .5*(y.max()-y.min()+1)
        yy, xx = np.mgrid[:H,:W]
        radius = np.sqrt(((xx-cx)/rx)**2+((yy-cy)/ry)**2)
        annulus = (radius>1.06) & (radius<1.18)
        quadrants = [annulus & (xx>=cx) & (yy>=cy), annulus & (xx<cx) & (yy>=cy),
                     annulus & (xx<cx) & (yy<cy), annulus & (xx>=cx) & (yy<cy)]
        assert all(np.count_nonzero(part)>5 for part in quadrants)
        for phase in (0., .025, .25, .5, .75, .975):
            _, off = draw(phase, False)
            _, on = draw(phase, True)
            corona = np.mean(on[...,:3]-off[...,:3],axis=2)
            assert np.isfinite(corona).all()
            # Every exterior quadrant needs its own source emission. An
            # illuminated-only halo has an empty hemisphere at quarter/New.
            means = [float(np.mean(corona[part])) for part in quadrants]
            assert min(means)>1e-4, (phase,means)
    finally:
        host.release_resources()
        capture.close()


def test_rim_experiment_has_one_default_off_typed_settings_roundtrip():
    key='shockwave_grid_celestial_rim_vertices'
    assert isinstance(DEFAULT_SETTINGS['widgets']['spotify_visualizer'][key], bool)
    entry=next(c for c in require_mode_settings('shockwave_grid').entries if getattr(c,'key',None)==key)
    assert isinstance(entry,Toggle) and entry.bucket=='glow'
    assert entry.when == (('shockwave_grid_sun_enabled',True),('shockwave_grid_celestial_glow_enabled',True))
    for enabled in (False,True):
        model=SpotifyVisualizerSettings.from_mapping({key:enabled},apply_preset_overlay=False,resolve_preset_indices=False)
        assert asdict(model)[key] is enabled
        assert asdict(SpotifyVisualizerSettings.from_mapping(asdict(model),apply_preset_overlay=False,resolve_preset_indices=False))[key] is enabled


@pytest.mark.qt
def test_gl_halo_retains_high_reactivity_contrast_and_rim_marks_follow_phase(qt_app):
    from rendering.quick.render.gl_resources import compile_program
    capture=TransitionCapture(64,64)
    program=compile_program('''#version 460 core
void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);gl_Position=vec4(p*2.-1.,0.,1.);}''',
        '#version 460 core\nout vec4 FragColor;\nuniform vec4 uInput;\nuniform int uProbe;\n'+NEON_CELESTIAL_GLSL+'''
void main(){
 if(uProbe==0){FragColor=vec4(basinCelestialHaloGain(uInput.zw,uInput.x,uInput.y),0.,0.,1.);return;}
 vec2 p=(gl_FragCoord.xy/64.-.5)*.36;
 vec3 ray=normalize(vec3(p,-1.));
 float angle=length(ray.xy)/(max(-ray.z,1e-5)*(.45/3.2));
 float marks=basinCelestialRimMarks(vec3(0.),ray,angle);
 FragColor=vec4(vec3(marks),1.);
}''',label='Neon celestial response probe')
    vao=int(gl.glGenVertexArrays(1)); texture=int(gl.glGenTextures(1)); fbo=int(gl.glGenFramebuffers(1))
    try:
        gl.glBindTexture(gl.GL_TEXTURE_2D,texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA32F,64,64,0,gl.GL_RGBA,gl.GL_FLOAT,None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT0,gl.GL_TEXTURE_2D,texture,0)
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)==gl.GL_FRAMEBUFFER_COMPLETE
        gl.glViewport(0,0,64,64);gl.glDisable(gl.GL_BLEND);gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glUseProgram(program);gl.glBindVertexArray(vao)
        gl.glUniform3f(gl.glGetUniformLocation(program,'uBodyPosition'),0.,0.,-3.2)
        gl.glUniform1f(gl.glGetUniformLocation(program,'uBodySize'),.45)
        def draw(mid=0.,beat=0.,intensity=1.,reactivity=2.,probe=0,kind=1,phase=.5):
            gl.glUniform4f(gl.glGetUniformLocation(program,'uInput'),mid,beat,intensity,reactivity)
            gl.glUniform1i(gl.glGetUniformLocation(program,'uProbe'),probe)
            gl.glUniform1i(gl.glGetUniformLocation(program,'uBodyKind'),kind)
            gl.glUniform1f(gl.glGetUniformLocation(program,'uMoonPhase'),phase)
            gl.glDrawArrays(gl.GL_TRIANGLES,0,3)
            return np.frombuffer(bytes(gl.glReadPixels(0,0,64,64,gl.GL_RGBA,gl.GL_FLOAT)),dtype=np.float32).reshape(64,64,4)
        assert draw()[0,0,0] == pytest.approx(.54,abs=1e-6)
        assert draw(.55,1.,reactivity=0.)[0,0,0] == pytest.approx(.54,abs=1e-6)
        assert draw(.55,1.,intensity=0.)[0,0,0] == 0.
        for reactivity in (.25,1.,2.):
            values=[float(draw(.5,b,reactivity=reactivity)[0,0,0]) for b in (.0,.2,.4,.6,.8,1.)]
            assert all(b>a+.003 for a,b in zip(values,values[1:]))
            if reactivity==2.: assert values[-1]-values[0]>.9 and values[-1]>1.8
        new=draw(probe=1,phase=0.)[:,:,0]
        full=draw(probe=1,phase=.5)[:,:,0]
        waxing=draw(probe=1,phase=.25)[:,:,0]
        waning=draw(probe=1,phase=.75)[:,:,0]
        sun=draw(probe=1,kind=0)[:,:,0]
        assert new.max()==0. and full.max()>.5 and sun.max()>.5
        assert np.count_nonzero(full>.05)<450 # sparse marks, never a full ring/lattice
        assert np.count_nonzero(waxing>.05)<np.count_nonzero(full>.05)*.75
        assert np.count_nonzero(waning>.05)<np.count_nonzero(full>.05)*.75
        assert waxing[:,32:].sum()>waxing[:,:32].sum()*4
        assert waning[:,:32].sum()>waning[:,32:].sum()*4
        assert full[20:44,20:44].max()==0. # centre stays untouched
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,0)
        gl.glDeleteFramebuffers(1,[fbo]);gl.glDeleteTextures([texture]);gl.glDeleteVertexArrays(1,[vao]);gl.glDeleteProgram(program)
        capture.close()
