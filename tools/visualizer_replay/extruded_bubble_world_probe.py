"""Freeze one real recorded snapshot and inspect its fixed world through a full camera turn.

No simulation advances between views. This is native geometry/coverage evidence,
not playback timing, Auto Rotate behavior or physical acceptance.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def camera_space(points, parameters, size):
    """Use the renderer's physical eye/lens, not the lab's legacy origin camera."""
    import numpy as np
    from rendering.gl_programs.extruded_bubble_scene import physical_camera

    _, world_to_view, eye, tan, _ = physical_camera(
        float(parameters['extruded_bubble_turn']), float(parameters['extruded_bubble_tilt']),
        size[0] / size[1], float(parameters['extruded_bubble_scene_scale']),
        pan_x=float(parameters['extruded_bubble_scene_pan_x']),
        pan_y=float(parameters['extruded_bubble_scene_pan_y']),
        position_offset=tuple(parameters['extruded_bubble_camera_position']),
        fov_y_degrees=float(parameters['extruded_bubble_camera_fov']),
        surface_bound=parameters['extruded_bubble_light_type'] == 'Sunlit Surface')
    view = (np.asarray(points) - np.asarray(eye)) @ np.asarray(world_to_view).reshape(3, 3)
    return view, eye, tan


def frustum_candidates(view, radii, tan):
    """Conservative sphere/side-plane intersection, not segmented visibility."""
    import numpy as np

    depth = -view[:, 2]
    return ((depth + radii > .05) &
            (np.abs(view[:, 0]) < tan[0] * depth + radii * math.sqrt(1. + tan[0] ** 2)) &
            (np.abs(view[:, 1]) < tan[1] * depth + radii * math.sqrt(1. + tan[1] ** 2)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    from core.settings.visualizer_presets import get_custom_preset_index
    parser.add_argument('--preset',type=int,default=1,
                        choices=range(1,get_custom_preset_index('extruded_bubble')+1))
    parser.add_argument('--at',type=float,default=4.)
    parser.add_argument('--size',default='1672x941')
    args=parser.parse_args()
    if args.at<=0:parser.error('--at must be positive')
    size=tuple(map(int,args.size.split('x')))
    if len(size)!=2 or min(size)<=0:parser.error('positive WIDTHxHEIGHT required')
    args.output.mkdir(parents=True,exist_ok=False)
    paths=[ROOT/p for p in ('widgets/spotify_visualizer/extruded_bubble_geometry.py',
        'widgets/spotify_visualizer/extruded_bubble_simulation.py','widgets/spotify_visualizer/extruded_bubble_frame_runtime.py',
        'widgets/spotify_visualizer/logical_frame_capture.py','rendering/gl_programs/extruded_bubble_scene.py',
        'rendering/gl_programs/extruded_bubble_program.py','rendering/gl_programs/scene3d_spheres.py',
        'rendering/gl_programs/scene3d_optics.py',
        'rendering/quick/visualizer/implementations/extruded_bubble.py','tools/visualizer_replay/extruded_bubble_world_probe.py')]
    hashes=lambda:{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt={'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
             'tracked_diff_sha256':hashlib.sha256(subprocess.check_output(['git','diff','HEAD'])).hexdigest(),
             'source_hashes':hashes(),'clip_sha256':hashlib.sha256(args.clip.read_bytes()).hexdigest()}
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    if not disable_per_call_gl_error_checking():raise RuntimeError('GL imported before production policy')
    import numpy as np
    from PIL import Image,ImageDraw
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from rendering.gl_programs.extruded_bubble_scene import bubble_instances
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.extruded_bubble_capture import _draw
    from tools.transition_contact_sheet import TransitionCapture
    from tools.visualizer_replay.driver import replay_clip
    from tools.visualizer_replay.extruded_bubble_forensics import load_clip
    activation=resolve_visualizer_activation_payload({'mode':'extruded_bubble','preset_extruded_bubble':args.preset-1},mode='extruded_bubble')
    clip=load_clip(args.clip,args.at)
    index=len(clip.frames)-1
    snapshot=replay_clip(clip,'extruded_bubble',settings=activation.resolved_config,snapshots_at=[index])['snapshots'][index]
    state=snapshot.logical.mode_state
    shells=bubble_instances(state.bubbles)
    points=shells[:,:3];radii=shells[:,3]
    host=QuickVisualizerRenderHost();target=TransitionCapture(*size)
    rows=[];tiles=[]
    try:
        poses=[(i/6.,float(dict(state.parameters)['extruded_bubble_tilt']),1.,0.) for i in range(12)]
        poses.extend(((0.,-.45,1.,0.),(0.,.45,1.,0.),(0.,0.,2.,.15)))
        for index,(turn,tilt,scale,pan) in enumerate(poses):
            parameters={**dict(state.parameters),'extruded_bubble_turn':turn,'extruded_bubble_tilt':tilt,
                        'extruded_bubble_scene_scale':scale,'extruded_bubble_scene_pan_x':pan}
            current=replace(snapshot,logical=replace(snapshot.logical,mode_state=replace(state,parameters=parameters)))
            rgba,gpu_ms=_draw(host,target,current,size,size)
            picture=Image.fromarray(rgba).convert('RGB');picture.save(args.output/f'view_{index:02d}.png')
            view,eye,tan=camera_space(points,parameters,size)
            visible=frustum_candidates(view,radii,tan)
            rows.append({'turn':turn,'tilt':tilt,'scale':scale,'pan_x':pan,'gpu_ms':gpu_ms,
                         'physical_eye':eye,'tan':tan,
                         'ordinary_frustum_candidates':int(visible.sum()),'scope':'conservative center/radius estimate; not segmented pixel count'})
            picture.thumbnail((400,230));tile=Image.new('RGB',(400,260),'#111827');tile.paste(picture,(0,0))
            ImageDraw.Draw(tile).text((8,237),f'yaw {turn*180:.0f}  tilt {tilt:.2f}  visible ~{visible.sum()}',fill='white');tiles.append(tile)
        sheet=Image.new('RGB',(1200,260*math.ceil(len(tiles)/3)),'#111827')
        for i,tile in enumerate(tiles):sheet.paste(tile,((i%3)*400,(i//3)*260))
        sheet.save(args.output/'contact.png')
        if hashes()!=receipt['source_hashes']:raise RuntimeError('source changed during world probe; reject output')
        metadata={**receipt,'renderer':target.driver,'scope':__doc__,'clip':str(args.clip.resolve()),
                  'size':size,'preset_path':activation.preset_path,'settings':dict(state.parameters),
                  'source_timestamp_us':clip.frames[-1].timestamp_us,'logical_time':state.time,
                  'world_bubbles':state.bubbles,'world_wakes':state.wakes,'world_clusters':state.clusters,
                  'global_bubble_count':len(state.bubbles)//8,'views':rows}
        (args.output/'metadata.json').write_text(json.dumps(metadata,indent=2,default=dict)+'\n',encoding='utf-8')
        print(json.dumps({'global_count':metadata['global_bubble_count'],'views':rows},indent=2))
    finally:
        host.release_resources();target.close()


if __name__=='__main__':main()
