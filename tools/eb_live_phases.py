"""Run the real MC saver with per-phase timers on Extruded Bubble's render thread and logical publish.

    .venv/Scripts/python tools/eb_live_phases.py --out logs/eb_live_phases.json -- --perf --frame-trace --exit-after 120 /s

Starts ``main_mc.py`` in this process (MC never takes over both displays) with tool-only wrappers around EB's
render stages (probe, shafts, near layer, background capture, drift solver, uniforms, instance packing), every
``gl_query`` / host fence state read, and the logical ``_publish_logical_state``; at exit it writes median/p90/p99
milliseconds per frame (and per tick) plus solver restarts to ``--out``. The first 200 frames are dropped (startup).

Use it under the real competing load the question is about, with ``SRPSS_FORCE_LOG_DIR`` pointing at a scratch
folder so the operator's own logs stay untouched. Offline harnesses (``eb_gpu_stage_cost``, ``eb_logical_cost_probe``)
cannot see Qt's scene, the swap chain, the real driver queue or the other displays; this can.
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import runpy
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_local = threading.local()
_frames: list[dict] = []
_ticks: list[float] = []
_restarts: list = []
_waveform_signals: list = []
_waveform_configuration: dict = {}


def _wrap(owner, attr, label):
    original = getattr(owner, attr)

    def timed(*args, **kwargs):
        current = getattr(_local, "frame", None)
        start = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            if current is not None:
                current[label] = current.get(label, 0.0) + (time.perf_counter() - start) * 1000.0
    setattr(owner, attr, timed)


def production_startup() -> None:
    """``main.py``'s process preamble, before anything here imports numpy, OpenGL or Qt.

    The wrappers below import OpenGL; done first, they would leave PyOpenGL's per-call error checking on (45-60% of
    render-thread CPU, ``rendering/gl_error_policy.py``) and measure a slower renderer than the product runs.
    """
    from core.native_threads import configure_native_thread_pools
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from rendering.quick.bootstrap import configure_quick_environment

    configure_native_thread_pools()
    if not disable_per_call_gl_error_checking():
        raise RuntimeError("OpenGL.GL was imported before the production GL error policy")
    configure_quick_environment()


def _install() -> None:
    from rendering.quick import gl_query
    from rendering.quick.scene3d import defocus, probe, target
    from rendering.quick.visualizer import gl_state
    from rendering.quick.visualizer.implementations import extruded_bubble as eb
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as solver
    from widgets.spotify_visualizer import tick_pipeline

    render = eb.QuickExtrudedBubbleRenderer.render

    def framed(self, frame):
        _local.frame = {}
        start = time.perf_counter()
        try:
            return render(self, frame)
        finally:
            _local.frame["eb_render"] = (time.perf_counter() - start) * 1000.0
            _frames.append(_local.frame)
            _local.frame = None
    eb.QuickExtrudedBubbleRenderer.render = framed
    for owner, attr, label in ((probe.SceneProbe, "capture", "probe"), (defocus.DefocusLayer, "begin", "near_begin"),
                               (defocus.DefocusLayer, "end", "near_end"),
                               (defocus.DefocusLayer, "composite", "near_composite"),
                               (target.SceneTarget, "background", "target_background"),
                               (solver.DriftSolver, "update", "drift_solver"), (eb._Uniforms, "set", "uniforms"),
                               (eb.QuickExtrudedBubbleRenderer, "_draw_shafts", "shafts"),
                               (eb, "bubble_instances", "pack_bubbles"), (eb, "wake_instances", "pack_wakes")):
        _wrap(owner, attr, label)
    for name in [n for n in dir(gl_query) if n.startswith(("get_", "is_enabled"))]:
        _wrap(gl_query, name, "state_reads")
    for name in ("_int_state", "_int_states", "_bool_state", "_bool_states", "_is_enabled"):
        if hasattr(gl_state, name):
            _wrap(gl_state, name, "host_state_reads")
    dispatch = solver.DriftSolver._dispatch

    def logged_dispatch(self, resources, name, state, offset, upload, pending, *, fresh, old_geometry=0,
                        old_carry=0.0):
        if fresh or old_geometry:
            _restarts.append((time.time(), name, int(state.serial), bool(fresh), bool(old_geometry)))
        return dispatch(self, resources, name, state, offset, upload, pending, fresh=fresh,
                        old_geometry=old_geometry, old_carry=old_carry)
    solver.DriftSolver._dispatch = logged_dispatch
    publish = tick_pipeline._publish_logical_state

    def ticked(*args, **kwargs):
        start = time.perf_counter()
        try:
            return publish(*args, **kwargs)
        finally:
            _ticks.append((time.perf_counter() - start) * 1000.0)
    tick_pipeline._publish_logical_state = ticked


def _summary() -> dict:
    rows = _frames[200:]
    summary: dict = {"frames": len(rows), "ticks": len(_ticks), "restarts": _restarts}
    for label in sorted({key for row in rows for key in row}):
        values = sorted(row.get(label, 0.0) for row in rows)
        summary[label] = {"median": round(statistics.median(values), 3),
                          "p90": round(values[int(0.9 * (len(values) - 1))], 3),
                          "p99": round(values[int(0.99 * (len(values) - 1))], 3)}
    ticks = sorted(_ticks[200:])
    if ticks:
        summary["logical_publish"] = {"median": round(statistics.median(ticks), 3),
                                      "p90": round(ticks[int(0.9 * (len(ticks) - 1))], 3)}
    if _waveform_signals:summary['waveform_signals']=_waveform_signals
    if _waveform_configuration:summary['waveform_configuration']=_waveform_configuration
    return summary


def _install_waveform() -> None:
    """The same passive timers around Waveform's actual scene owners; no alternate render path."""
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    from rendering.quick.scene3d import waveform, ribbon, ribbon_bursts, fog_volume,waveform_envelope
    from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime
    from widgets.spotify_visualizer import waveform_ribbon_capture
    capture=waveform_ribbon_capture.capture_waveform_ribbon
    def captured(widget,engine,context):
        result=capture(widget,engine,context)
        if engine is not None:
            _waveform_configuration.update(waveform_worker_configuration(engine))
        return result
    waveform_ribbon_capture.capture_waveform_ribbon=captured
    configure=WaveformRibbonFrameRuntime.configure
    last_configuration=None
    def configured(self,values):
        global _waveform_configuration
        nonlocal last_configuration
        result=configure(self,values)
        if result is not None and result is not last_configuration:
            _waveform_configuration=dict(values)
            last_configuration=result
        return result
    WaveformRibbonFrameRuntime.configure=configured
    advance=WaveformRibbonFrameRuntime.advance
    count=0;serial=-1
    def observed(self,**kwargs):
        nonlocal count,serial
        state=advance(self,**kwargs);count+=1
        if state is not None and state.ready and (count%30==0 or state.particle_serial!=serial):
            _waveform_signals.append(dict(time=state.time,identity=kwargs['identity'],
                source_identity=kwargs['source_identity'],playing=kwargs['playing'],bands=kwargs['body_bands'],intensity=kwargs['intensity'],
                loudness=kwargs['loudness'],presence=kwargs['presence'],drives=dict(state.drives),
                bursts=state.particle_serial,particle_bytes=len(state.particles),
                onsets=[dict(serial=event.serial,kind=event.kind,confidence=event.strength,magnitude=event.magnitude,
                             loudness=event.loudness,presence=event.presence) for event in kwargs['onsets']]))
            serial=state.particle_serial
        return state
    WaveformRibbonFrameRuntime.advance=observed
    render=QuickWaveformRibbonRenderer.render
    def framed(self,frame):
        _local.frame={};start=time.perf_counter()
        try:return render(self,frame)
        finally:
            _waveform_configuration.update(dict(frame.snapshot.logical.mode_state.parameters))
            _local.frame['waveform_render']=(time.perf_counter()-start)*1000.
            _frames.append(_local.frame);_local.frame=None
    QuickWaveformRibbonRenderer.render=framed
    for owner,attr,label in ((waveform,'waveform_envelope','waveform_envelope'),
        (waveform_envelope.WaveformEnvelope,'update','gpu_envelope_submit'),
        (waveform.WaveformScene,'_update_fog','fog_update'),(waveform.WaveformScene,'_bake_shape','fog_bake'),
        (waveform.WaveformScene,'_fog_uniforms','fog_uniforms'),(waveform.WaveformScene,'_reflect','reflection'),
        (waveform.WaveformScene,'_floor','floor'),(ribbon.RibbonPrimitive,'draw','ribbons'),
        (ribbon_bursts.RibbonBurstRenderer,'draw','bursts'),(fog_volume.FogMarch,'march','fog_march'),
        (fog_volume.FogMarch,'composite','fog_composite')):
        _wrap(owner,attr,label)


def waveform_worker_configuration(engine):
    """Observe applied worker values, rather than assuming a requested technical cache reached it."""
    worker=engine._audio_worker
    attrs={'bar_count':'_bar_count','audio_block_size':'_preferred_block_size',
           'adaptive_sensitivity':'_use_recommended','sensitivity':'_user_sensitivity',
           'dynamic_floor':'_use_dynamic_floor','manual_floor':'_manual_floor','input_gain':'_input_gain'}
    return {'waveform_ribbon_'+key:getattr(worker,attribute) for key,attribute in attrs.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("mc_args", nargs=argparse.REMAINDER, help="arguments for main_mc.py after --")
    args = parser.parse_args()
    mc_args = args.mc_args[1:] if args.mc_args[:1] == ["--"] else args.mc_args
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    sys.argv = [str(ROOT / "main_mc.py"), *mc_args]
    production_startup()
    _install()
    atexit.register(lambda: args.out.write_text(json.dumps(_summary(), indent=1), encoding="utf-8"))
    runpy.run_path(str(ROOT / "main_mc.py"), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
