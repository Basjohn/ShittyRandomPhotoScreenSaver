"""Both authored handles must reach realized production consumers, independently of preset bytes."""
import copy
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import require_mode_settings, Range
from core.waveform_ribbon_dynamics import WaveformDynamics
from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings


def settings():
    values={control.key:require_canonical_default('widgets.spotify_visualizer.'+control.key)
            for control in require_mode_settings('waveform_ribbon').controls}
    values['waveform_ribbon_strands_enabled']=True
    values['waveform_ribbon_mist_enabled']=True
    values['waveform_ribbon_sparkle']=[1.,1.]  # Admit events while isolating the other particle ranges.
    values['waveform_ribbon_colour_threshold']=.1
    return values


def observed(values,snapshot=None):
    config=CompiledWaveformSettings(values);model=WaveformDynamics(config.controls)
    if snapshot is None:
        for _ in range(64):model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
        for index in range(60):
            snapshot=model.advance(1/90,bands=(.45,.5,.55),intensity=.5,presence=1.,hit=.8 if index in (20,50) else 0.)
    scene=config.scene(snapshot)
    # Read the retained scene inputs and actual body/birth bytes, never the original settings or realized dictionary.
    return (snapshot.packet.payload,snapshot.particles,snapshot.rotation_angle,repr(scene)),snapshot


def test_both_range_handles_reach_the_body_birth_records_or_retained_scene():
    defaults=settings();_,common=observed(defaults);dead=[]
    for control in require_mode_settings('waveform_ribbon').controls:
        if not isinstance(control,Range):continue
        span=control.high-control.low;base=copy.deepcopy(defaults)
        base[control.key]=control.admit((control.low+.2*span,control.low+.8*span),defaults[control.key])
        snapshot=None if control.logical or control.key.startswith('waveform_ribbon_spark') else common
        reference,_=observed(base,snapshot)
        for endpoint in (0,1):
            values=copy.deepcopy(base);pair=list(values[control.key])
            pair[endpoint]+=(.4*span if endpoint==0 else -.4*span)
            values[control.key]=control.admit(pair,base[control.key])
            result,_=observed(values,snapshot)
            if result==reference:dead.append((control.key,endpoint))
    assert not dead,f'No actual consumer changed for {dead}'
