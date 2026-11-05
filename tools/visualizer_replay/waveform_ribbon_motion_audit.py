"""Recorded PCM -> admitted drives -> realised Waveform geometry, against a same-clip idle control.

Runs the production logical mode (configured worker, transient bus, frame runtime, dynamics projection) on
deterministic source timestamps and measures the published body itself: vertical/depth envelopes, sheet width,
per-ribbon peak-to-peak, along-body lumpiness and frame-to-frame motion. The control replays the same clip with
playback reported paused, so the mode sees silence/idle while every other input is identical. No renderer;
pixels and musical feel remain separate evidence.
"""
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))


def body_metrics(state,*,span):
    """World-space measures of one published body over the scene interval |x| <= span."""
    import numpy as np
    from core.ribbon_packet import KNOT_ROWS
    from core.waveform_ribbon_authoring import RIBBON_CAPACITY
    packet=state.packet
    data=np.frombuffer(packet.payload,np.float32).reshape(RIBBON_CAPACITY,-1,4)
    head=state.scene.flow.head_x
    ribbons=[]
    for index,path in enumerate(data):
        count,start,capacity=int(path[0,0]),int(path[1,1]),int(path[1,2])
        knots=path[4:].reshape(-1,KNOT_ROWS,4)[(start+np.arange(count))%capacity]
        x=knots[:,0,0]+packet.world_origin[0]+head-state.travel
        y=knots[:,0,1]+packet.world_origin[1]
        z=knots[:,0,2]+packet.world_origin[2]
        w=knots[:,0,3]
        twist=knots[:,1,1]
        inside=(x>=-span)&(x<=span)
        if inside.sum()<4 or float(np.abs(w[inside]).max())<=2e-5:
            continue
        xs,ys,zs,ws,ts=x[inside],y[inside],z[inside],w[inside],twist[inside]
        # Lumpiness: sign changes of the second difference of y per world unit. Smooth long sweeps have few;
        # small travelling dents add many. Uniform knot spacing makes the index derivative proportional.
        curvature=np.diff(ys,2)
        flips=int((np.diff(np.sign(curvature[np.abs(curvature)>1e-4]))!=0).sum())
        ribbons.append(dict(index=index,y=(float(ys.min()),float(ys.max())),z=(float(zs.min()),float(zs.max())),
            peak_to_peak=float(ys.max()-ys.min()),half_width=float(ws.mean()),twist_span=float(ts.max()-ts.min()),
            inflections_per_unit=flips/max(1e-6,float(xs.max()-xs.min())),
            sample=(xs.tolist(),ys.tolist())))
    if not ribbons:
        return None
    return dict(envelope=(min(r['y'][0] for r in ribbons),max(r['y'][1] for r in ribbons)),
        depth=(min(r['z'][0] for r in ribbons),max(r['z'][1] for r in ribbons)),ribbons=ribbons)


def run(clip_path,preset,*,playing_override,span,seconds,start,settings_overrides):
    import numpy as np
    from PySide6.QtCore import QCoreApplication
    from widgets.spotify_visualizer.feature_frame import load_jsonl
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from tools.visualizer_replay.driver import _configure,deterministic_clock
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from tools.visualizer_replay.pcm_reanalysis import PcmReanalysis
    from widgets.spotify_visualizer.tick_pipeline import logical_tick
    QCoreApplication.instance() or QCoreApplication([])
    clip=load_jsonl(clip_path);origin=clip.frames[0].timestamp_us
    frames=[frame for frame in clip.frames if (frame.timestamp_us-origin)/1e6<=start+seconds]
    rows=[]
    with deterministic_clock() as clock:
        engine=ReplayBeatEngine(32)
        controller=VisualizerRuntimeController(runtime_generation=0,initial_mode='waveform_ribbon',engine_factory=lambda _:engine)
        controller.engine=engine
        _configure(controller,'waveform_ribbon',preset-1,overrides=settings_overrides or None)
        reanalysis=PcmReanalysis()
        try:
            for feature in frames:
                clock[0]=feature.timestamp_us/1e6
                playing=feature.playing if playing_override is None else playing_override
                # The mode reads the controller's media state; the engine's flag alone leaves it "playing".
                controller.playing=playing
                engine.set_playback_state(playing);engine.accept_feature_frame(feature)
                reanalysis.accept(engine,feature)
                logical=logical_tick(controller.logical_tick_state)
                state=logical.mode_state
                t=(feature.timestamp_us-origin)/1e6
                if state is None or not state.ready or t<start:
                    continue
                band=engine.get_waveform_ribbon_body_bands()
                metrics=body_metrics(state,span=span)
                if metrics is None:
                    continue
                rows.append(dict(t=t,bands=(band.bass,band.mid,band.high),intensity=engine.get_musical_intensity(),
                    passage=state.passage,drives=dict(state.drives),realized=dict(state.realized),
                    rotation=state.rotation_angle,metrics=metrics))
        finally:
            engine.force_stop()
    return rows


def summarise(rows):
    import numpy as np
    def dist(values):
        a=np.asarray(values,float)
        return dict(p05=float(np.percentile(a,5)),p50=float(np.percentile(a,50)),p95=float(np.percentile(a,95)),
                    maximum=float(a.max()))
    env=[r['metrics']['envelope'][1]-r['metrics']['envelope'][0] for r in rows]
    ptp=[np.mean([b['peak_to_peak'] for b in r['metrics']['ribbons']]) for r in rows]
    width=[np.mean([b['half_width'] for b in r['metrics']['ribbons']]) for r in rows]
    lumps=[np.mean([b['inflections_per_unit'] for b in r['metrics']['ribbons']]) for r in rows]
    # Temporal: vertical motion of each ribbon's sample nearest x=0, per logical second.
    centre=[]
    for r in rows:
        values=[]
        for b in r['metrics']['ribbons']:
            xs,ys=np.asarray(b['sample'][0]),np.asarray(b['sample'][1])
            values.append(float(np.interp(0.,xs,ys)))
        centre.append(np.mean(values))
    t=np.asarray([r['t'] for r in rows])
    centre=np.asarray(centre)
    speed=np.abs(np.diff(centre))/np.maximum(np.diff(t),1e-6)
    accel=np.abs(np.diff(centre,2))
    return dict(frames=len(rows),union_envelope=dist(env),mean_peak_to_peak=dist(ptp),mean_half_width=dist(width),
        inflections_per_unit=dist(lumps),centre_speed=dist(speed),centre_second_difference=dist(accel),
        passage=dist([r['passage'] for r in rows]),
        drives={key:dist([r['drives'][key] for r in rows]) for key in rows[0]['drives']})


def correlate(rows,lag_frames=40):
    """Lag (frames) and correlation of union envelope against bass and against passage."""
    import numpy as np
    env=np.asarray([r['metrics']['envelope'][1]-r['metrics']['envelope'][0] for r in rows])
    out={}
    for name,series in (('bass',[r['bands'][0] for r in rows]),('passage',[r['passage'] for r in rows])):
        s=np.asarray(series,float)
        best=(0,0.)
        for lag in range(lag_frames):
            a,b=s[:len(s)-lag],env[lag:]
            if a.std()<1e-9 or b.std()<1e-9:continue
            c=float(np.corrcoef(a,b)[0,1])
            if c>best[1]:best=(lag,c)
        out[name]=dict(lag_frames=best[0],correlation=best[1])
    return out


def audit(args):
    overrides=dict(item.split('=',1) for item in args.set)
    overrides={key:json.loads(value) for key,value in overrides.items()}
    result=dict(scope='production logical mode on reanalysed recorded PCM; deterministic timestamps; no renderer',
                clip=str(args.clip),preset=args.preset,span=args.span,start=args.start,seconds=args.seconds,overrides=overrides)
    music=run(args.clip,args.preset,playing_override=None,span=args.span,seconds=args.seconds,start=args.start,settings_overrides=overrides)
    idle=run(args.clip,args.preset,playing_override=False,span=args.span,seconds=args.seconds,start=args.start,settings_overrides=overrides)
    result['music']=summarise(music);result['idle_control']=summarise(idle);result['music_correlation']=correlate(music)
    # Quiet / hot split on the published passage itself.
    import numpy as np
    passage=np.asarray([r['passage'] for r in music])
    low,high=np.percentile(passage,25),np.percentile(passage,75)
    result['music_quiet_quartile']=summarise([r for r in music if r['passage']<=low])
    result['music_hot_quartile']=summarise([r for r in music if r['passage']>=high])
    if args.trace:
        trace=[dict(t=r['t'],bands=r['bands'],passage=r['passage'],envelope=r['metrics']['envelope'],
                    drives={k:r['drives'][k] for k in ('height','bend','width','torsion')}) for r in music]
        result['trace']=trace
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as out:json.dump(result,out,indent=1)
    m,i=result['music'],result['idle_control']
    print('union envelope p50/p95 music',round(m['union_envelope']['p50'],3),round(m['union_envelope']['p95'],3),
          'idle',round(i['union_envelope']['p50'],3),'| quiet q p50',round(result['music_quiet_quartile']['union_envelope']['p50'],3),
          'hot q p50',round(result['music_hot_quartile']['union_envelope']['p50'],3),
          '| inflections/unit',round(m['inflections_per_unit']['p50'],3),'| corr',result['music_correlation'],flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preset',type=int,choices=(1,2,3),default=3)
    parser.add_argument('--start',type=float,default=5.);parser.add_argument('--seconds',type=float,default=40.)
    parser.add_argument('--span',type=float,default=18.,help='Half-width of the measured scene x interval (world units)')
    parser.add_argument('--set',action='append',default=[],help='Settings-model override KEY=JSON (test-owned only)')
    parser.add_argument('--trace',action='store_true');parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:return audit(args)
    from tools.build_runner import BuildProcessOwner
    owner=BuildProcessOwner();process=owner.start([sys.executable,__file__,*sys.argv[1:],'--worker'],cwd=ROOT)
    try:
        try:code=process.wait(timeout=900)
        except subprocess.TimeoutExpired:owner.cancel();process.wait(timeout=10);raise
    finally:owner.retire(process);owner.shutdown()
    raise SystemExit(code)


if __name__=='__main__':main()
