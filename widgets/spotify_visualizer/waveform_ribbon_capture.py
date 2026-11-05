"""Descriptor-owned logical capture; no GUI/renderer/audio authority."""
from core.settings.visualizer_mode_settings import require_mode_settings, control_runtime_attr
from widgets.spotify_visualizer import config_applier
from widgets.spotify_visualizer.logical_frame_capture import (
    _mode_frame_runtime_type, _resolve_current_mode_runtime, _base_extras)
from widgets.spotify_visualizer.render_state import WaveformRibbonFrame, freeze_render_fields
from widgets.spotify_visualizer.view_orbit import apply_view_orbit_motion, view_camera_operated

MODE='waveform_ribbon'
_CAMERA_KEYS=frozenset(control.key for control in require_mode_settings(MODE).controls
                       if control.bucket=='camera' or not control.bucket)


def capture_waveform_ribbon(widget,engine,context):
    controller=widget.runtime_controller
    runtime=_resolve_current_mode_runtime(controller,MODE,_mode_frame_runtime_type(MODE))
    if runtime is None:return None
    pres=config_applier._presentation_source(widget)
    spec=require_mode_settings(MODE)
    values={control.key:getattr(widget if control.logical else pres,control_runtime_attr(control))
            for control in spec.controls}
    configuration=runtime.configure({key:value for key,value in values.items() if key not in _CAMERA_KEYS})
    if configuration is None:return None
    onsets=engine.get_onset_events(runtime.onset_serial) if engine is not None else ()
    bands=(0.,0.,0.);intensity=loudness=presence=0.
    if engine is not None and context.playing:
        raw=engine.get_waveform_ribbon_body_bands()
        bands=(float(raw.bass),float(raw.mid),float(raw.high))
        intensity=float(engine.get_musical_intensity())
        loudness,presence=engine.get_musical_level()
    snapshot=runtime.advance(onsets=onsets,now_ts=context.now_ts,playing=context.playing,
        identity=(context.runtime_generation,context.engine_generation,context.activation_id),
        source_identity=(context.source_generation,context.source_activation_id),controls=configuration.controls,
        body_bands=bands,intensity=intensity,loudness=loudness,presence=presence,
        dynamic_zoom=bool(values.get('waveform_ribbon_dynamic_zoom',False)),zoom_hold=view_camera_operated(pres,MODE))
    if snapshot is None or controller.peek_logical_mode_state(MODE) is not runtime:return None
    # The renderer needs the resolved immutable scene and compact view parameters, not the complete authoring matrix.
    camera={key:value for key,value in values.items() if key.startswith('waveform_ribbon_camera_')
            or key in ('waveform_ribbon_turn','waveform_ribbon_tilt','waveform_ribbon_scene_scale',
                       'waveform_ribbon_scene_pan_x','waveform_ribbon_scene_pan_y')}
    camera=apply_view_orbit_motion(pres,MODE,camera,context.now_ts)
    frame=WaveformRibbonFrame(snapshot.packet,configuration.scene(snapshot),snapshot.time,snapshot.travel,
        snapshot.rotation_angle,snapshot.rotation_speed,snapshot.drives,snapshot.realized,
        ready=snapshot.ready,particles=snapshot.particles,particle_origin=snapshot.particle_origin,
        particle_serial=snapshot.particle_serial,passage=snapshot.passage,parameters=freeze_render_fields(camera),
        strands=snapshot.strands,strand_origin=snapshot.strand_origin,zoom=snapshot.zoom)
    extra=_base_extras(widget,MODE,engine)
    extra['_quick_mode_changed']=True
    extra['_quick_mode_reveal_ready']=snapshot.ready
    return frame,extra
