"""Save/compare full Bubble replay outputs from sequential native clips.

python -m tools.visualizer_replay.bubble_parity --output logs/bubble_v5_before --gpu
python -m tools.visualizer_replay.bubble_parity --output logs/bubble_v5_after --compare logs/bubble_v5_before --gpu

Frozen test settings are inputs, never regenerated from editable presets. This
offline evidence covers deterministic behaviour, not live cadence/audio acceptance.
"""
from __future__ import annotations

import argparse
import base64
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
import gc
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from .bubble_fidelity import replay_bubbles

ROOT = Path(__file__).resolve().parents[2]
CLIPS = ('nightsolong_acousticsoft1', 'ragdoll_quiet_intro_loud_end1',
         'human_heavy1', 'anything_mixed2')
FROZEN = ROOT/'tests/fixtures/visualizer_frozen_settings/bubble.json'


def canonical_value(value):
    """Lossless supported immutable payloads; fail loudly on an unobserved type."""
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: canonical_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): canonical_value(item) for key,item in value.items()}
    if isinstance(value, (tuple,list)):
        return [canonical_value(item) for item in value]
    if isinstance(value, bytes):
        return {'bytes_base64': base64.b64encode(value).decode('ascii')}
    if value is None or isinstance(value, (str,bool,int,float)):
        return value
    raise TypeError(f'unhandled parity payload {type(value).__name__}')


def canonical_bytes(value):
    return json.dumps(canonical_value(value),sort_keys=True,separators=(',',':'),
                      allow_nan=False).encode('utf-8')


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def frame_record(result, observations, index):
    from rendering.quick.visualizer.implementations.bubble import resolve_quick_bubble_payload
    snapshot=result['snapshots'].get(index)
    return {'index':index,'logical':result['logical_series'][index],
            'published_snapshot':snapshot,
            'renderer_payload':resolve_quick_bubble_payload(snapshot) if snapshot else None,
            'physics':observations[index],'replay_observation':result['frames'][index]}


def semantic_differences(left, right, path='$', limit=20):
    """Small field-level explanation; complete records remain in the gzip files."""
    differences=[]
    if type(left) is not type(right):
        return [{'path':path,'before':left,'after':right}]
    if isinstance(left,dict):
        for key in sorted(left.keys()|right.keys()):
            if key not in left or key not in right:
                differences.append({'path':f'{path}.{key}','before':left.get(key),'after':right.get(key)})
            else:
                differences.extend(semantic_differences(left[key],right[key],f'{path}.{key}',limit))
            if len(differences)>=limit:break
    elif isinstance(left,list):
        if len(left)!=len(right):
            differences.append({'path':path+'.length','before':len(left),'after':len(right)})
        for index,(a,b) in enumerate(zip(left,right)):
            differences.extend(semantic_differences(a,b,f'{path}[{index}]',limit))
            if len(differences)>=limit:break
    elif left!=right:
        differences.append({'path':path,'before':left,'after':right})
    return differences[:limit]


def source_provenance(output):
    paths=sorted({*(ROOT/'widgets/spotify_visualizer').glob('*.py'),
                  *(ROOT/'core/settings').rglob('*.py'),
                  ROOT/'rendering/quick/visualizer/implementations/bubble.py'})
    rows={path.relative_to(ROOT).as_posix():_sha(path.read_bytes()) for path in paths}
    diff=subprocess.run(['git','diff','--','widgets/spotify_visualizer','core/settings',
        'rendering/quick/visualizer/implementations/bubble.py'],cwd=ROOT,
        capture_output=True,check=True).stdout
    (output/'production_worktree.patch').write_bytes(diff)
    (output/'source_provenance.json').write_text(json.dumps({'source_sha256':rows,
        'production_diff_sha256':_sha(diff),'production_diff_bytes':len(diff)},indent=2)+'\n')


def _gpu_snapshots(folder, snapshots, indices):
    import numpy as np
    from OpenGL import GL as gl
    from PIL import Image
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.transition_contact_sheet import TransitionCapture

    width,height=1920,1080
    target,host=TransitionCapture(width,height),QuickVisualizerRenderHost()
    rows=[]
    try:
        for index in indices:
            snapshot=snapshots.get(index)
            if snapshot is None:
                continue
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,target.fbo)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glClearColor(0.,0.,0.,0.)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT|gl.GL_DEPTH_BUFFER_BIT)
            host.render(snapshot=snapshot,viewport=(0,0,width,height),
                logical_size=(float(width),float(height)),
                matrix_values=(2/width,0,0,0,0,-2/height,0,0,0,0,1,0,-1,1,0,1))
            data=gl.glReadPixels(0,0,width,height,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE)
            rgba=np.frombuffer(bytes(data),dtype=np.uint8).reshape(height,width,4)[::-1].copy()
            path=folder/f'gpu_{index:05d}.png'
            Image.fromarray(rgba).save(path)
            rows.append({'frame':index,'file':path.name,'rgba_sha256':_sha(rgba.tobytes())})
        return {'driver':target.driver,'viewport':[width,height],'dpr':1.,'images':rows}
    finally:
        host.release_resources()
        target.close()


def capture(output, *, recordings=ROOT/'logs/visualizer_recordings', compare=None, gpu=False):
    from widgets.spotify_visualizer.feature_frame import FeatureClip

    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    if (output/'manifest.json').exists():
        raise FileExistsError(f'preserve existing parity evidence: {output}')
    source_provenance(output)
    settings_bytes=FROZEN.read_bytes()
    settings=json.loads(settings_bytes)
    (output/'frozen_settings.json').write_bytes(settings_bytes)
    document={'format':1,'head':subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,
        capture_output=True,text=True,check=True).stdout.strip(),
        'settings_path':str(FROZEN),'settings_file_sha256':_sha(settings_bytes),
        'scope':'every full logical frame, published Quick snapshot, renderer payload and identity-preserving physics observation; offline deterministic replay, not live temporal acceptance',
        'clips':[]}
    previous=json.loads((Path(compare)/'manifest.json').read_text()) if compare else None
    if previous and previous['settings_file_sha256']!=document['settings_file_sha256']:
        raise ValueError('frozen input settings changed')
    for name in CLIPS:
        path=Path(recordings)/(name+'.jsonl')
        data=path.read_bytes()
        clip_sha=_sha(data)
        clip=FeatureClip.from_jsonl_bytes(name,data)
        del data
        if any(frame.schema_version!=2 or frame.real is None for frame in clip.frames):
            raise ValueError(f'{name} is not fully native schema2')
        print(f'replaying {name}: {len(clip.frames)} frames',flush=True)
        result,observations,resolved=replay_bubbles(clip,settings=settings,
            snapshots_at=range(len(clip.frames)))
        folder=output/name
        folder.mkdir()
        hashes=[]
        full_digest=hashlib.sha256()
        with gzip.open(folder/'full_output.jsonl.gz','wb') as stream:
            for index,logical in enumerate(result['logical_series']):
                row=frame_record(result,observations,index)
                encoded=canonical_bytes(row)+b'\n'
                stream.write(encoded)
                full_digest.update(encoded)
                hashes.append(_sha(encoded))
        row={'name':name,'path':str(path.resolve()),'clip_sha256':clip_sha,
             'frames':len(clip.frames),'schema':2,
             'native_history_frames':sum(frame.capture_history is not None for frame in clip.frames),
             'resolved_settings_sha256':_sha(canonical_bytes(resolved)),
             'full_output_sha256':full_digest.hexdigest(),
             'frame_sha256':hashes,'presentation_trace':result['presentation_trace'],
             'mode_metrics':result['mode_metrics'],'metrics':result['metrics']}
        if gpu:
            row['gpu']=_gpu_snapshots(folder,result['snapshots'],(0,len(clip.frames)//2,len(clip.frames)-1))
        if previous:
            old=next(item for item in previous['clips'] if item['name']==name)
            if old['clip_sha256']!=clip_sha:
                raise ValueError(f'input clip changed: {name}')
            row['comparison']={'equal':hashes==old['frame_sha256'],
                'resolved_settings_equal':row['resolved_settings_sha256']==old['resolved_settings_sha256'],
                'different_frames':[i for i,(a,b) in enumerate(zip(hashes,old['frame_sha256'])) if a!=b],
                'frame_count_equal':len(hashes)==len(old['frame_sha256'])}
            if gpu and 'gpu' in old:
                row['comparison']['gpu_equal']=row['gpu']['images']==old['gpu']['images']
            print(f"{name}: exact={row['comparison']['equal']}",flush=True)
        document['clips'].append(row)
        (output/'manifest.json').write_text(json.dumps(document,indent=2)+'\n')
        print(f'saved {name} full output: {row["full_output_sha256"]}',flush=True)
        if previous and not (row['comparison']['equal'] and row['comparison']['resolved_settings_equal']
                and row['comparison'].get('gpu_equal',True)):
            different=row['comparison']['different_frames']
            if different:
                first=different[0]
                with gzip.open(Path(compare)/name/'full_output.jsonl.gz','rt') as stream:
                    before=next(line for i,line in enumerate(stream) if i==first)
                details={'frame':first,'differences':semantic_differences(json.loads(before),
                    canonical_value(frame_record(result,observations,first)))}
                (output/'first_difference.json').write_text(json.dumps(details,indent=2)+'\n')
                print(f'FIRST DIFFERENCE {name} frame {first}: '+
                      ', '.join(item['path'] for item in details['differences']),flush=True)
            raise RuntimeError(f'Bubble parity differs for {name}; stopped before later clips')
        del result,observations,resolved,clip
        gc.collect()
    return document


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--recordings',type=Path,default=ROOT/'logs/visualizer_recordings')
    parser.add_argument('--compare',type=Path)
    parser.add_argument('--gpu',action='store_true')
    args=parser.parse_args()
    result=capture(args.output,recordings=args.recordings,compare=args.compare,gpu=args.gpu)
    if args.compare and not all(item['comparison']['equal'] and
            item['comparison']['resolved_settings_equal'] and
            item['comparison'].get('gpu_equal',True) for item in result['clips']):
        raise SystemExit(1)


if __name__=='__main__':
    main()
