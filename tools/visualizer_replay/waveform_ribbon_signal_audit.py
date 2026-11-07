"""Bounded native-PCM floor A/B and pooled raw/music statistics through the configured production worker."""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools import artifact_paths  # noqa: E402


def distribution(values,*,normalised=True):
    import numpy as np
    a=np.asarray(values,float)
    return dict(p05=float(np.percentile(a,5)),p50=float(np.percentile(a,50)),p95=float(np.percentile(a,95)),
                minimum=float(a.min()),maximum=float(a.max()),std=float(a.std()),
                upper15=float((a>=.85).mean()) if normalised else None,
                ceiling=float((a>=1.-1e-6).mean()) if normalised else None)


def audit(args):
    import numpy as np
    from PySide6.QtCore import QCoreApplication
    from widgets.spotify_visualizer.feature_frame import load_jsonl
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from tools.visualizer_replay.driver import _configure,deterministic_clock
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from tools.visualizer_replay.pcm_reanalysis import PcmReanalysis
    from widgets.spotify_visualizer.raw_audio_scale import WAVEFORM_USUAL_RAW_LEVEL
    from widgets.spotify_visualizer.transient_bus import MUSICAL_USUAL_LOUDNESS
    from widgets.spotify_visualizer.tick_pipeline import logical_tick
    app=QCoreApplication.instance() or QCoreApplication([])
    results=[];pooled=[]
    for path in args.clips:
        clip=load_jsonl(path);origin=clip.frames[0].timestamp_us
        frames=[frame for frame in clip.frames if (frame.timestamp_us-origin)/1e6<=args.seconds]
        for dynamic in (False,True):
            rows=[];events=[];serial=0;drivers=[];digest=hashlib.sha256()
            with deterministic_clock() as clock:
                engine=ReplayBeatEngine(32)
                controller=VisualizerRuntimeController(runtime_generation=0,initial_mode='waveform_ribbon',engine_factory=lambda _:engine)
                controller.engine=engine
                _configure(controller,'waveform_ribbon',args.preset-1,
                           overrides={'waveform_ribbon_audio_block_size':args.block})
                # Waveform owns no floor setting (retired 8 Nov: nothing it reads sits behind the floor); the A/B
                # moves the shared worker's floor directly, which its raw lanes must ignore.
                worker=engine._audio_worker
                engine.set_floor_config(dynamic,worker._manual_floor)
                reanalysis=PcmReanalysis()
                try:
                    for feature in frames:
                        clock[0]=feature.timestamp_us/1e6
                        engine.set_playback_state(feature.playing);engine.accept_feature_frame(feature)
                        reanalysis.accept(engine,feature)
                        if args.mode_output:
                            logical=logical_tick(controller.logical_tick_state);state=logical.mode_state
                            if state.ready:
                                digest.update(state.packet.payload);digest.update(state.particles);digest.update(state.strands)
                                drivers.append(dict(state.drives))
                        worker=engine._audio_worker;bus=worker._transient_bus
                        raw=(worker._last_raw_bass,worker._last_raw_mid,worker._last_raw_treble)
                        band=engine.get_waveform_ribbon_body_bands()
                        if (feature.timestamp_us-origin)/1e6>=3.:
                            rows.append((*raw,band.bass,band.mid,band.high,*bus.musical_level,bus.musical_intensity,bus._intensity._level*WAVEFORM_USUAL_RAW_LEVEL/MUSICAL_USUAL_LOUDNESS))
                        for event in bus.recent_onsets:
                            if event.serial>serial:
                                events.append((event.timestamp,event.kind,event.magnitude,event.loudness,event.presence))
                                serial=event.serial
                    data=np.asarray(rows,float)
                    keys=('raw_bass','raw_mid','raw_high','bass','mid','high','loudness','presence','passage','held_raw')
                    results.append(dict(clip=path.name,dynamic_floor=dynamic,block=args.block,frames=len(rows),
                        lanes={key:distribution(data[:,index],normalised=key in ('bass','mid','high','passage')) for index,key in enumerate(keys)},
                        onsets=events,mode_sha256=digest.hexdigest() if drivers else None,
                        drives={key:distribution([row[key] for row in drivers]) for key in drivers[0]} if drivers else None))
                    if not dynamic:pooled.append(data)
                    print(path.name,'dynamic',dynamic,'rawmax p50',float(np.median(data[:,:3].max(axis=1))),
                          'passage p50',float(np.median(data[:,-2])),'onsets',len(events),flush=True)
                finally:engine.force_stop()
    all_=np.concatenate(pooled)
    result=dict(scope='Configured production PCM FFT and transient bus; deterministic source timestamps; no renderer/physical acceptance',
        pooled_raw_max=distribution(all_[:,:3].max(axis=1),normalised=False),
        pooled_held_raw=distribution(all_[:,-1],normalised=False),
        pooled_raw_bands=[distribution(all_[:,index],normalised=False) for index in range(3)],results=results)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clips',nargs='+',type=Path,required=True);parser.add_argument('--output',type=artifact_paths.evidence_arg,required=True)
    parser.add_argument('--seconds',type=float,default=60.);parser.add_argument('--preset',type=int,choices=(1,2,3),default=1)
    parser.add_argument('--block',type=int,choices=(128,256,441,512,1024),default=256)
    parser.add_argument('--mode-output',action='store_true',help='Also execute the real logical mode and hash every body/birth publication')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not 4.<=args.seconds<=300.:parser.error('Use a bounded 4..300 second source window')
    if args.worker:return audit(args)
    from tools.build_runner import BuildProcessOwner
    owner=BuildProcessOwner();process=owner.start([sys.executable,__file__,*sys.argv[1:],'--worker'],cwd=ROOT)
    try:
        try:code=process.wait(timeout=900)
        except subprocess.TimeoutExpired:owner.cancel();process.wait(timeout=10);raise
    finally:owner.retire(process);owner.shutdown()
    raise SystemExit(code)


if __name__=='__main__':main()
