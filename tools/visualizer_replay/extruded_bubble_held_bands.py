"""Hold one real hot band frame without repeating its discrete events or transients.

This is a controlled steady-body comparison, not continuous real music or a live
tuple receipt. --simulation-ref overrides only that module inside this process;
all other source stays current. Never checks out or writes Settings/presets.
"""
import argparse,hashlib,json,subprocess,sys,types
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
parser=argparse.ArgumentParser();parser.add_argument('--simulation-ref');parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if args.output.exists():raise FileExistsError(args.output)
name='widgets.spotify_visualizer.extruded_bubble_simulation';path='widgets/spotify_visualizer/extruded_bubble_simulation.py'
source=(subprocess.check_output(['git','show',f'{args.simulation_ref}:{path}']) if args.simulation_ref else (root/path).read_bytes())
if args.simulation_ref:
    module=types.ModuleType(name);module.__file__=str(root/path);sys.modules[name]=module
    exec(compile(source,module.__file__,'exec'),module.__dict__)
if args.simulation_ref and b'extruded_bubble_geometry import' not in source:
    raise ValueError('Historical simulation uses the old normalized metric; run its archived tool to reproduce those receipts')
from dataclasses import replace,asdict
from unittest.mock import patch
import numpy as np
from tools.visualizer_replay import driver
from tools.visualizer_replay.extruded_bubble_forensics import load_clip
from widgets.spotify_visualizer.feature_frame import FeatureClip
from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
from widgets.spotify_visualizer.extruded_bubble_frame_runtime import ExtrudedBubbleFrameRuntime
from core.settings.visualizer_presets import resolve_visualizer_activation_payload
clip=load_clip(root/'logs/visualizer_recordings/cindarellaman_heavy2.jsonl',10)
peak=max(clip.frames,key=lambda f:.7*f.energy.bubble.mid+.35*f.energy.bubble.high)
no_events=replace(peak.real,onsets=(),events=())
zero=replace(peak.energy.transient,bass=0.,mid=0.,high=0.,overall=0.,onset_detected=False,onset_type='',onset_strength=0.)
energy=replace(peak.energy,transient=zero)
held=FeatureClip('controlled_band_hold_no_new_events',tuple(replace(peak,timestamp_us=peak.timestamp_us+i*11000,real=no_events,energy=energy) for i in range(1200)))
result={'scope':'one real feature frame bands held for 13.2s; no new onsets/events/transients; not continuous music or live reproduction',
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'source_timestamp_us':peak.timestamp_us,'simulation_override':args.simulation_ref,'simulation_sha256':hashlib.sha256(source).hexdigest(),
        'bands':asdict(peak.energy.bubble)}
records=[];original=BubbleSimulation.snapshot;scale=(1672*941/1.5)**.5
configure=driver._configure
def full(controller,*a,**kw):configure(controller,*a,**kw);controller.set_custom_viewport_override((1672.,941.))
def observe(sim,**kw):
    value=original(sim,**kw);records.clear()
    records.extend((b.is_big,float(r[2])*scale) for b,r in zip(sim._bubbles,np.asarray(value[0]).reshape(-1,4)) if r[3]>.999 and not b.popping and not b.exiting)
    return value
with patch.object(BubbleSimulation,'snapshot',observe),patch.object(driver,'_configure',full):driver.replay_clip(held,'bubble',preset=0)
def summary(items):
    return {str(k):{'count':len(v:=[r for large,r in items if large==k]),'radius_px_median_max':([float(np.median(v)),max(v)] if v else [])} for k in (True,False)}
result['bubble']=summary(records)
result['bubble_settings']={k:v for k,v in resolve_visualizer_activation_payload(
    {'mode':'bubble','preset_bubble':0},mode='bubble').resolved_config.items() if k.startswith('bubble_')}
classes={};followers={};original_advance=ExtrudedBubbleFrameRuntime.advance
def observe_eb(runtime,**kw):
    value=original_advance(runtime,**kw);classes.clear();classes.update({b.ident:b.large for b in runtime._simulation._bubbles})
    followers.update({k:getattr(runtime._simulation,k) for k in ('_body_small_envelope','_small_body_reference','_sustain')})
    return value
activation=resolve_visualizer_activation_payload({'mode':'extruded_bubble','preset_extruded_bubble':6},mode='extruded_bubble')
result['extruded_bubble_settings']={k:v for k,v in activation.resolved_config.items() if k.startswith('extruded_bubble_')}
result['extruded_bubble_settings'].update(extruded_bubble_large_bubbles=(0,4),extruded_bubble_mid_bubbles=(20,50))
with patch.object(ExtrudedBubbleFrameRuntime,'advance',observe_eb):
    state=driver.replay_clip(held,'extruded_bubble',settings={**activation.resolved_config,'extruded_bubble_large_bubbles':(0,4),'extruded_bubble_mid_bubbles':(20,50)})['logical_series'][-1].mode_state
from rendering.gl_programs import extruded_bubble_scene as scene
parameters=activation.resolved_config
_,world_to_view,tan,_=scene.camera(parameters['extruded_bubble_turn'],parameters['extruded_bubble_tilt'],1672/941,parameters['extruded_bubble_scene_scale'])
records=[]
for r in np.asarray(state.bubbles).reshape(-1,8):
    view=r[:3]@np.asarray(world_to_view).reshape(3,3)
    depth=-float(view[2])
    candidate=(abs(view[0])<tan[0]*depth+r[3] and abs(view[1])<tan[1]*depth+r[3])
    if r[4]>.999 and r[7]<0 and depth>r[3]+.05 and candidate:
        records.append((classes[int(r[6])],float(r[3])*941/(2*tan[1]*depth)))
result['projection_scope']='first-order radius estimate for fully-forward ordinary frustum candidates; not segmented visible silhouettes'
from tools.visualizer_replay.extruded_bubble_forensics import distribution
result['extruded_bubble_logical_ratios']={str(large):distribution([
    1.+r[5] for r in np.asarray(state.bubbles).reshape(-1,8)
    if classes[int(r[6])]==large and r[4]>.999 and r[7]<0]) for large in (True,False)}
result['extruded_bubble']=summary(records);result['followers']=followers
args.output.write_text(json.dumps(result,indent=2))
print(json.dumps({k:result[k] for k in ('scope','simulation_override','bands','bubble','extruded_bubble','followers')},indent=2))
