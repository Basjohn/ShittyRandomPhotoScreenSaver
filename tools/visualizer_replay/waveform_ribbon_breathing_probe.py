"""Waveform Ribbon reaction over whole songs in continuous play: kick response by time in song, and breathing.

``record`` runs the production logical mode (configured worker, transient bus, frame runtime) on one or more
recorded clips played back to back WITHOUT a reset (timestamps continue), with deterministic timestamps, and stores:
the exact per-tick inputs ``WaveformDynamics.advance`` receives, the published body's visible amplitude, three
geometry drives, and every typed onset the frame runtime consumed. It runs from whatever checkout contains it, so the
same file copied into an older tree records that tree's behaviour (used for the pre-adaptive-gain control).

``analyse`` replays recorded inputs through the CURRENT ``WaveformDynamics`` for curated presets (controls compiled
from each preset exactly as production does) and reports:
  * kick response per onset: rise of the body drives and of the swell the onset launches (largest geometric gain over
    the pulse field, times the height level) against the 300 ms before it, tabulated by time in the song
    (0-15, 15-45, 45-90, later) and by passage (quiet / mid / sustained loud, tertiles of the held level);
  * breathing: per-drive peak-to-trough contrast within sliding 3 s windows, soft vs loud windows;
  * reach: p95 and time above 0.9 of each drive.
Inputs are identical across presets and code variants, so A/B comparisons isolate the dynamics. No renderer.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from tools import artifact_paths  # noqa: E402
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

DRIVES=('height','width','lift','bend','twist','depth')
WINDOW,HOP=3.,.5
TIME_BINS=((0.,15.),(15.,45.),(45.,90.),(90.,1e9))
# Input columns: dt, bass, mid, high, intensity, presence, hit, bend/torsion/depth components, accent (-1 = None),
# song index, time in song.
INPUT_COLUMNS=13


def view_amplitude(snapshot,span=18.):
    """Mean per-ribbon vertical peak-to-peak of the published body over |x| <= span (world units)."""
    import numpy as np
    from core.ribbon_packet import KNOT_ROWS
    packet=snapshot.packet
    data=np.frombuffer(packet.payload,np.float32).reshape(4,-1,4)
    values=[]
    for path in data:
        count,start,capacity=int(path[0,0]),int(path[1,1]),int(path[1,2])
        if count<4:continue
        knots=path[4:].reshape(-1,KNOT_ROWS,4)[(start+np.arange(count))%capacity]
        x=knots[:,0,0]+packet.world_origin[0]+snapshot.head_x-snapshot.travel
        y=knots[:,0,1]
        inside=np.abs(x)<=span
        if inside.sum()>=4 and float(np.abs(knots[inside,0,3]).max())>2e-5:
            values.append(float(np.ptp(y[inside])))
    return float(np.mean(values)) if values else 0.


def record(clips,output):
    import numpy as np
    from dataclasses import replace
    from unittest.mock import patch
    from PySide6.QtCore import QCoreApplication
    from core.waveform_ribbon_dynamics import WaveformDynamics
    from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime
    from widgets.spotify_visualizer.feature_frame import load_jsonl
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from tools.visualizer_replay.driver import _configure,deterministic_clock
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from tools.visualizer_replay.pcm_reanalysis import PcmReanalysis
    from widgets.spotify_visualizer.tick_pipeline import logical_tick
    QCoreApplication.instance() or QCoreApplication([])
    rows,onsets=[],[]
    song=[0,0.]  # index, start time
    now=[0.]
    original=WaveformDynamics.advance
    def observe(self,dt,**kwargs):
        ready=self.ready
        snapshot=original(self,dt,**kwargs)
        if ready:
            comps=kwargs.get('hit_components') or (0.,0.,0.)
            accent=kwargs.get('accent')
            drives=dict(snapshot.drives)
            rows.append((dt,*kwargs['bands'],kwargs['intensity'],kwargs['presence'],kwargs.get('hit',0.),*comps,
                         -1. if accent is None else accent,song[0],now[0]-song[1],
                         view_amplitude(snapshot),drives.get('height',0.),drives.get('bend',0.),drives.get('width',0.)))
        return snapshot
    runtime_advance=WaveformRibbonFrameRuntime.advance
    kinds=('kick','snare','vocal_swell','onset')
    def runtime_observe(self,*,onsets,**kwargs):
        serial=self.onset_serial
        for onset in onsets:
            if onset.serial>serial:
                captured.append((len(rows),song[0],now[0]-song[1],kinds.index(onset.kind) if onset.kind in kinds else -1,
                                 float(onset.magnitude),float(onset.loudness),float(onset.presence)))
        return runtime_advance(self,onsets=onsets,**kwargs)
    captured=onsets
    with patch.object(WaveformDynamics,'advance',observe),patch.object(WaveformRibbonFrameRuntime,'advance',runtime_observe),\
            deterministic_clock() as clock:
        engine=ReplayBeatEngine(32)
        controller=VisualizerRuntimeController(runtime_generation=0,initial_mode='waveform_ribbon',engine_factory=lambda _:engine)
        controller.engine=engine
        _configure(controller,'waveform_ribbon',0)
        reanalysis=PcmReanalysis()
        offset=0.
        serial=[0,None]  # last published capture serial, this song's serial shift
        try:
            for index,clip_path in enumerate(clips):
                clip=load_jsonl(clip_path);origin=clip.frames[0].timestamp_us
                song[0],song[1]=index,offset
                serial[1]=None  # capture serials continue across songs (the device never restarts)
                last=offset
                for feature in clip.frames:
                    t=offset+(feature.timestamp_us-origin)/1e6
                    now[0]=last=t
                    # One continuous clock across songs (strictly positive, as real capture time is).
                    feature=replace(feature,timestamp_us=int(round((1.+t)*1e6)))
                    history=feature.capture_history
                    if history is not None:
                        if serial[1] is None:serial[1]=serial[0]+1-history.capture_serial
                        history=replace(history,capture_serial=history.capture_serial+serial[1])
                        serial[0]=history.capture_serial
                        feature=replace(feature,capture_history=history)
                    clock[0]=feature.timestamp_us/1e6
                    controller.playing=feature.playing
                    engine.set_playback_state(feature.playing);engine.accept_feature_frame(feature)
                    reanalysis.accept(engine,feature)
                    logical_tick(controller.logical_tick_state)
                offset=last+1/90
        finally:
            engine.force_stop()
    output.parent.mkdir(parents=True,exist_ok=True)
    np.save(output,np.asarray(rows,np.float64))
    np.save(output.with_name(output.stem+'_onsets.npy'),np.asarray(onsets,np.float64).reshape(-1,7))
    print('recorded',len(rows),'ticks',round(float(np.asarray(rows)[:,0].sum()),1),'s',len(onsets),'onsets ->',output,flush=True)


def preset_controls(index):
    """Controls compiled from curated preset ``index`` (0-based) exactly as production configures it."""
    from dataclasses import asdict
    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
    activation=resolve_visualizer_activation_payload({'mode':'waveform_ribbon','preset_waveform_ribbon':index})
    model=SpotifyVisualizerSettings.from_mapping(activation.resolved_config,apply_preset_overlay=False,resolve_preset_indices=False)
    values={k:v for k,v in asdict(model).items() if k.startswith('waveform_ribbon_')}
    return CompiledWaveformSettings(values).controls


VIEW=30.  # the authored long lens sees about +-30 world units (TROUGH_VIEW)


def swell_of(model):
    """Largest visible swell the travelling field puts on the body: (gain - 1) x height level over |x| <= VIEW.
    Scene x of a pulse-grid cell is the grid coordinate (the field lives in scene space)."""
    import numpy as np
    from core.waveform_ribbon_dynamics import PULSE_GRID
    share=model._geom_share[0]
    inside=np.abs(PULSE_GRID)<=VIEW
    return float(share*.7*model._value('bend')*np.max(model._geom[inside]))*model._value('height')


def replay(inputs,controls,*,model_factory=None,view=False):
    """Drive WaveformDynamics with recorded inputs; per tick: time, loudness, power, swell, drives (, view amp)."""
    import numpy as np
    from core.waveform_ribbon_dynamics import WaveformDynamics
    model=(model_factory or WaveformDynamics)(controls)
    while not model.ready:model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
    out=[]
    t=0.
    for row in inputs:
        dt,b,m,h,intensity,presence,hit,c0,c1,c2,accent=row[:11]
        snap=model.advance(float(dt),bands=(b,m,h),intensity=intensity,presence=presence,hit=hit,
                           hit_components=(c0,c1,c2),accent=None if accent<0 else accent)
        t+=dt
        out.append((t,intensity*presence,model.power,swell_of(model),*(dict(snap.drives)[k] for k in DRIVES),
                    *((view_amplitude(snap,VIEW),) if view else ())))
    return np.asarray(out)


def kick_table(trace,inputs,onsets,*,columns,kinds=(0,),pre=.3,post=(.3,2.5)):
    """Per typed onset: response = max over the post window minus mean over the pre window, per measure column.
    Binned by time in song and by passage tertile (held level over the 3 s before the onset)."""
    import numpy as np
    t=trace[:,0];level=trace[:,1]
    song_time=inputs[:,12] if inputs.shape[1]>12 else t
    events=[]
    for row in onsets:
        tick,song,_,kind,magnitude=int(row[0]),int(row[1]),row[2],int(row[3]),row[4]
        if kind not in kinds or tick>=len(t) or tick<int(3*90):continue
        t0=t[tick]
        held=float(level[(t>=t0-3.)&(t<t0)].mean())
        rec=dict(time=float(song_time[tick]),song=song,held=held,magnitude=float(magnitude),hit=float(inputs[tick:tick+3,6].max()))
        before=(t>=t0-pre)&(t<t0)
        for name,(col,window) in columns.items():
            after=(t>=t0)&(t<t0+window)
            rec[name]=float(trace[after,col].max()-trace[before,col].mean())
        events.append(rec)
    if not events:return dict(count=0)
    held=np.asarray([e['held'] for e in events])
    q1,q2=np.percentile(held,33),np.percentile(held,67)
    def stats(group):
        if not group:return None
        return dict(n=len(group),**{key:float(np.median([e[key] for e in group])) for key in ('hit','magnitude',*columns)})
    table=dict(by_time={f'{lo:g}-{hi:g}':stats([e for e in events if lo<=e['time']<hi]) for lo,hi in TIME_BINS},
               by_passage=dict(quiet=stats([e for e in events if e['held']<=q1]),
                               mid=stats([e for e in events if q1<e['held']<q2]),
                               loud=stats([e for e in events if e['held']>=q2])),
               loud_by_time={f'{lo:g}-{hi:g}':stats([e for e in events if e['held']>=q2 and lo<=e['time']<hi]) for lo,hi in TIME_BINS})
    return table


def windows(trace,col_level=1,first=4,window=WINDOW,hop=HOP):
    import numpy as np
    t=trace[:,0];rows=[]
    start=t[0]+5.
    while start+window<=t[-1]:
        seg=trace[(t>=start)&(t<start+window)]
        rows.append((float(seg[:,col_level].mean()),*(float(np.ptp(seg[:,first+i])) for i in range(len(DRIVES)))))
        start+=hop
    return np.asarray(rows)


def breathing(trace):
    import numpy as np
    w=windows(trace)
    loud=w[:,0]
    soft=loud<=np.percentile(loud,33);hot=loud>=np.percentile(loud,67)
    body=trace[trace[:,0]>=trace[0,0]+5.]
    out={}
    for i,key in enumerate(DRIVES):
        d=body[:,4+i]
        out[key]=dict(soft_contrast=float(np.median(w[soft,1+i])),loud_contrast=float(np.median(w[hot,1+i])),
                      p05=float(np.percentile(d,5)),p50=float(np.percentile(d,50)),p95=float(np.percentile(d,95)),
                      above90=float((d>=.9).mean()))
    return out


MEASURES=dict(swell=(3,2.5),height=(4,.6),bend=(7,.6),width=(5,.6))


def analyse(args):
    import numpy as np
    report={}
    presets=[int(p) for p in args.presets.split(',')]
    for path in args.inputs:
        inputs=np.load(path)
        onsets=np.load(path.with_name(path.stem+'_onsets.npy'))
        report[path.stem]={}
        for index in presets:
            trace=replay(inputs,preset_controls(index-1),view=args.view)
            columns=dict(MEASURES)
            if args.view:columns['view']=(trace.shape[1]-1,2.5)
            report[path.stem][f'preset_{index}']=dict(kicks=kick_table(trace,inputs,onsets,columns=columns),breathing=breathing(trace))
            if args.traces:
                np.save(args.output.with_name(f'{args.output.stem}_{path.stem}_p{index}_trace.npy'),trace)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=1),encoding='utf-8')
    print_report(report)


def recorded_table(args):
    """Kick table straight from a recording's own published body (any checkout, incl. the pre-gain control)."""
    import numpy as np
    report={}
    for path in args.inputs:
        rows=np.load(path);onsets=np.load(path.with_name(path.stem+'_onsets.npy'))
        t=np.cumsum(rows[:,0])
        trace=np.column_stack((t,rows[:,4]*rows[:,5],rows[:,13],rows[:,14],rows[:,15],rows[:,16]))
        report[path.stem]=kick_table(trace,rows,onsets,columns=dict(view=(2,2.5),height=(3,.6),bend=(4,.6),width=(5,.6)))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=1),encoding='utf-8')
    print(json.dumps(report,indent=1))


def print_report(report):
    for clip,presets in report.items():
        for name,r in presets.items():
            k=r['kicks']
            if not k.get('by_time'):continue
            print(clip[:24],name)
            for label,group in (('time',k['by_time']),('passage',k['by_passage']),('loud@time',k['loud_by_time'])):
                print('  ',label.ljust(9),' '.join(f"{key}:n{g['n']} hit {g['hit']:.2f} sw {g['swell']:+.3f} h {g['height']:+.3f} b {g['bend']:+.3f}"
                                                  +(f" v {g['view']:+.3f}" if 'view' in g else '') for key,g in group.items() if g))
            b=r['breathing']
            print('   breathing',' '.join(f"{key} {b[key]['soft_contrast']:.3f}/{b[key]['loud_contrast']:.3f} p95 {b[key]['p95']:.2f} >.9 {b[key]['above90']:.2f}"
                                          for key in ('height','width','lift','bend')))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    rec=sub.add_parser('record');rec.add_argument('--clip',type=Path,action='append',required=True)
    rec.add_argument('--output',type=artifact_paths.evidence_arg,required=True)
    ana=sub.add_parser('analyse');ana.add_argument('inputs',type=Path,nargs='+');ana.add_argument('--output',type=artifact_paths.evidence_arg,required=True)
    ana.add_argument('--presets',default='1,2,3,4,5,6,7');ana.add_argument('--traces',action='store_true')
    ana.add_argument('--view',action='store_true',help='also measure the published body amplitude in view (slower)')
    tab=sub.add_parser('recorded');tab.add_argument('inputs',type=Path,nargs='+');tab.add_argument('--output',type=artifact_paths.evidence_arg,required=True)
    args=parser.parse_args()
    if args.command=='record':record(args.clip,args.output)
    elif args.command=='recorded':recorded_table(args)
    else:analyse(args)


if __name__=='__main__':main()
