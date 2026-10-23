"""Paired real-input, same-window 2D/EB response custody; no product/preset writes.

Ratios describe final logical radius / nominal radius, not native segmented pixels.
Each mode retains its own authored population/geometry. Stable identities within a
window must be mature for at least 80% of that window's input samples.

``--reanalyze-pcm`` recomputes each mode's body bands from the recorded PCM with that
mode's own configured floor/sensitivity (see ``pcm_reanalysis``); ``--set MODE.KEY=JSON``
overrides one resolved setting in memory, e.g. the asymmetric breathing reference
``--set bubble.bubble_dynamic_floor=true`` (2D floor ON) against EB with its floor OFF.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from contextlib import nullcontext
from pathlib import Path
import subprocess
from unittest.mock import patch

import numpy as np

from core.settings.visualizer_presets import resolve_visualizer_activation_payload
from tools.visualizer_replay import driver
from tools.visualizer_replay.extruded_bubble_forensics import distribution, load_clip
from tools.visualizer_replay.pcm_reanalysis import reanalyzed_bubble_bands
from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
from widgets.spotify_visualizer.extruded_bubble_frame_runtime import ExtrudedBubbleFrameRuntime


def observe_mode(clip, mode, settings, size, reanalyze=False):
    rows, identities, retained, actual_energy = [], {}, [], {}
    origin = clip.frames[0].timestamp_us
    configure = driver._configure

    def configured(controller, *args, **kwargs):
        configure(controller, *args, **kwargs)
        controller.set_custom_viewport_override(tuple(map(float, size)))

    def append(objects, **state):
        feature = clip.frames[len(rows)]
        rows.append(dict(timestamp_us=feature.timestamp_us, time_s=(feature.timestamp_us-origin)/1e6,
                         playing=feature.playing, recorded_bands=asdict(feature.energy.bubble),
                         objects=objects, **state))

    snapshot = BubbleSimulation.snapshot
    tick = BubbleSimulation.tick
    advance = ExtrudedBubbleFrameRuntime.advance

    def bubble_tick(simulation, dt, energy_bands, settings):
        actual_energy.clear()
        actual_energy.update(energy_bands)
        return tick(simulation,dt,energy_bands,settings)

    def bubble_snapshot(simulation, **kwargs):
        result = snapshot(simulation, **kwargs)
        objects = []
        for bubble, record in zip(simulation._bubbles, np.asarray(result[0]).reshape(-1, 4), strict=True):
            token = id(bubble)
            if token not in identities:
                identities[token] = len(identities)+1
                retained.append(bubble)  # prevent id reuse; never reinsert
            objects.append(dict(id=identities[token], large=bubble.is_big,
                ratio=float(record[2])/bubble.radius, nominal=bubble.radius,
                mature=bool(record[3]>.999 and not bubble.popping and not bubble.exiting and not bubble.promoted),
                record=list(map(float, record))))
        append(objects,actual_energy=dict(actual_energy),render_pulse=dict(kwargs))
        return result

    def eb_advance(runtime, **kwargs):
        result = advance(runtime, **kwargs)
        if result is None:
            raise RuntimeError('EB replay did not publish a snapshot')
        owners = {b.ident:b for b in runtime._simulation._bubbles}
        objects = [dict(id=int(record[6]), large=owners[int(record[6])].large,
            ratio=1.+float(record[5]), nominal=owners[int(record[6])].radius,
            mature=bool(record[4]>.999 and record[7]<0 and owners[int(record[6])].popping<0
                        and not owners[int(record[6])].leaving), record=list(map(float, record)))
            for record in np.asarray(result.bubbles).reshape(-1, 8)]
        append(objects, actual_bands=kwargs['body_bands'], controls=asdict(kwargs['controls']),
               followers={name:getattr(runtime._simulation,name) for name in (
                   '_body_big_envelope','_body_small_envelope','_big_body_reference','_small_body_reference')})
        return result

    hook = patch.object(BubbleSimulation,'snapshot',bubble_snapshot) if mode=='bubble' else \
        patch.object(ExtrudedBubbleFrameRuntime,'advance',eb_advance)
    bands = reanalyzed_bubble_bands() if reanalyze else nullcontext()
    with hook, bands, patch.object(BubbleSimulation,'tick',bubble_tick), patch.object(driver,'_configure',configured):
        driver.replay_clip(clip,mode,settings=settings)
    if len(rows)!=len(clip.frames):
        raise RuntimeError(f'{mode} snapshot/input count differs: {len(rows)} vs {len(clip.frames)}')
    return rows


def window_summary(rows, start, stop):
    selected = [r for r in rows if start<=r['time_s']<=stop]
    if len(selected)<2:
        raise ValueError('window has fewer than two input samples')
    by_id = {}
    for row in selected:
        for obj in row['objects']:
            if obj['mature']:
                by_id.setdefault(obj['id'],[]).append((row['time_s'],obj))
    result = {}
    for large,label in ((True,'large'),(False,'small')):
        ids = []
        for ident, samples in by_id.items():
            if samples[0][1]['large']!=large or len(samples)<.8*len(selected):
                continue
            values = [o['ratio'] for _,o in samples]
            ids.append(dict(id=ident,samples=len(samples),minimum=min(values),maximum=max(values),
                min_time_s=samples[values.index(min(values))][0],
                max_time_s=samples[values.index(max(values))][0],
                excursion=(max(values)-min(values))/min(values)))
        result[label] = dict(stable_ids=ids,identities=len(ids),
            min_ratio=distribution([o['minimum'] for o in ids]),
            max_ratio=distribution([o['maximum'] for o in ids]),
            excursion=distribution([o['excursion'] for o in ids]))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--duration',type=float,default=12.)
    parser.add_argument('--eb-preset',type=int,default=1)
    parser.add_argument('--bubble-preset',type=int,default=1)
    parser.add_argument('--size',default='1672x941')
    parser.add_argument('--window',action='append',default=[],help='start,stop seconds; repeatable')
    parser.add_argument('--reanalyze-pcm',action='store_true',
                        help="recompute each mode's body bands from recorded PCM with its own floor")
    parser.add_argument('--set',action='append',default=[],metavar='MODE.KEY=JSON',
                        help='in-memory resolved-setting override for one mode; repeatable')
    args=parser.parse_args()
    overrides={'bubble':{},'extruded_bubble':{}}
    for item in args.set:
        target,_,value=item.partition('=')
        mode,_,key=target.partition('.')
        if mode not in overrides or not key or not value:
            parser.error(f'--set expects MODE.KEY=JSON with MODE bubble|extruded_bubble: {item!r}')
        overrides[mode][key]=json.loads(value)
    windows=[tuple(map(float,w.split(','))) for w in args.window] or [(1.507184,3.146924),(4.,8.),(8.,12.)]
    if args.duration<=0 or any(len(w)!=2 or not 0<=w[0]<w[1]<=args.duration for w in windows):
        parser.error('windows must be ordered pairs inside positive duration')
    root=Path(__file__).resolve().parents[2]
    paths=[root/p for p in (
        'tools/visualizer_replay/bubble_response_comparison.py','tools/visualizer_replay/driver.py',
        'tools/visualizer_replay/engine.py','widgets/spotify_visualizer/bubble_simulation.py',
        'widgets/spotify_visualizer/bubble_frame_runtime.py','widgets/spotify_visualizer/extruded_bubble_simulation.py',
        'widgets/spotify_visualizer/extruded_bubble_frame_runtime.py','widgets/spotify_visualizer/extruded_bubble_geometry.py',
        'widgets/spotify_visualizer/logical_frame_capture.py','tools/visualizer_replay/pcm_reanalysis.py',
        'widgets/spotify_visualizer/bar_computation.py','widgets/spotify_visualizer/beat_engine.py')]
    hashes=lambda:{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before=hashes()
    clip=load_clip(args.clip,args.duration)
    args.output.mkdir(parents=True,exist_ok=False)
    summary=dict(clip=str(args.clip.resolve()),clip_sha256=hashlib.sha256(args.clip.read_bytes()).hexdigest(),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_hashes=before,
        scope=('recorded PCM reanalysed per mode with its own floor (hybrid: recorded onsets/cadence)'
               if args.reanalyze_pcm else 'same recorded post-DSP samples/cadence')
              +', independent authored populations; logical radius/nominal only, not pixel or listening acceptance',
        reanalyze_pcm=args.reanalyze_pcm,overrides=overrides,windows={},settings={})
    results={}
    for mode,preset in (('bubble',args.bubble_preset),('extruded_bubble',args.eb_preset)):
        activation=resolve_visualizer_activation_payload({'mode':mode,f'preset_{mode}':preset-1},mode=mode)
        unknown=set(overrides[mode])-set(activation.resolved_config)
        if unknown:
            parser.error(f'unknown {mode} settings: {sorted(unknown)}')
        resolved={**activation.resolved_config,**overrides[mode]}
        summary['settings'][mode]=dict(preset=preset,path=activation.preset_path,values=resolved)
        rows=observe_mode(clip,mode,resolved,tuple(map(int,args.size.split('x'))),args.reanalyze_pcm)
        results[mode]=rows
        with (args.output/f'{mode}.jsonl').open('w',encoding='utf-8') as stream:
            for row in rows:stream.write(json.dumps(row,separators=(',',':'))+'\n')
        for start,stop in windows:
            summary['windows'].setdefault(f'{start:g}-{stop:g}',{})[mode]=window_summary(rows,start,stop)
    if [r['timestamp_us'] for r in results['bubble']]!=[r['timestamp_us'] for r in results['extruded_bubble']]:
        raise RuntimeError('mode timestamps differ')
    mismatches=[]
    for left,right in zip(results['bubble'],results['extruded_bubble'],strict=True):
        if not left['actual_energy']:
            raise RuntimeError('missing actual 2D simulation input')
        clean=tuple(left['actual_energy'][f'pulse_{key}'] for key in ('bass','mid','high'))
        if not np.allclose(clean,right['actual_bands'],rtol=0.,atol=1e-12):
            mismatches.append(dict(time_s=left['time_s'],bubble_clean=clean,eb=right['actual_bands']))
    # Under reanalysis with different floors the modes' inputs differ by design.
    summary['actual_body_input_mismatch_count']=len(mismatches)
    summary['actual_body_input_mismatches']=mismatches[:50]
    if hashes()!=before:
        raise RuntimeError('source changed during paired replay; reject evidence')
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    for window,modes in summary['windows'].items():
        print(window)
        for mode,classes in modes.items():
            print(mode,{k:{m:v[m] for m in ('identities','min_ratio','max_ratio','excursion')} for k,v in classes.items()})


if __name__=='__main__':
    main()
