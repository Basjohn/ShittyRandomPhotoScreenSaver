"""Same-state native ray-driver/softness interventions from a real recorded clip.

Run as a module; all changes are process-local, with no Settings/preset writes.
"""
from dataclasses import replace
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from rendering.gl_error_policy import disable_per_call_gl_error_checking
assert disable_per_call_gl_error_checking()
from tools import extruded_bubble_capture as capture
from rendering.gl_programs.extruded_bubble_scene import scene_knobs, ray_strength
from PIL import Image, ImageDraw
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--clip',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--preset',type=int,default=1)
parser.add_argument('--at',type=float,default=3.)
args = parser.parse_args()
if not 1 <= args.preset <= 7 or args.at < 0:
    parser.error('preset must be 1..7 and at nonnegative')
out = args.output
out.mkdir(parents=True, exist_ok=False)
root = Path(__file__).resolve().parents[2]
source_paths = [root/'rendering/gl_programs/extruded_bubble_scene.py',
                root/'rendering/gl_programs/extruded_bubble_program.py',
                root/'rendering/quick/visualizer/implementations/extruded_bubble.py']
source_hashes = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
(out/'source_receipt.json').write_text(json.dumps(dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    source_hashes=source_hashes,clip=str(args.clip.resolve()),clip_sha256=hashlib.sha256(args.clip.read_bytes()).hexdigest(),
    preset=args.preset,at=args.at),indent=2))
original = capture._draw
ledger = []

def draw(host, target, snapshot, size, window, passes=None):
    pictures = []
    state = snapshot.logical.mode_state
    for soft in (0., 1.):
        for drive in (0., .5, 1.):
            params = {**dict(state.parameters), 'extruded_bubble_ray_softness': soft}
            altered = replace(state, parameters=params, rays=drive)
            snap = replace(snapshot, logical=replace(snapshot.logical, mode_state=altered))
            pixels, ms = original(host, target, snap, size, window, passes)
            picture = Image.fromarray(pixels).convert('RGB')
            picture.save(out / f'soft_{soft:g}_drive_{drive:g}.png')
            knobs = scene_knobs(params)
            ledger.append(dict(softness=soft, drive=drive, strength=ray_strength(params, drive),
                               shaft_soft=knobs.get('shaft_soft', 0.0), fan_contrast=knobs['fan_contrast'],
                               fan_rays=knobs['fan_rays'], gpu_ms=ms,
                               central_rgb_mean=float(np.asarray(picture)[250:750,400:1200].mean())))
            picture.thumbnail((550,310))
            tile=Image.new('RGB',(550,340),'#101827');tile.paste(picture,(0,0))
            ImageDraw.Draw(tile).text((8,315),f'softness {soft:g} | driver {drive:g} | uRays {ray_strength(params,drive):.3f}',fill='white')
            pictures.append(tile)
    sheet=Image.new('RGB',(1650,680),'#101827')
    for i,picture in enumerate(pictures):sheet.paste(picture,((i%3)*550,(i//3)*340))
    sheet.save(out/'comparison.png')
    (out/'interventions.json').write_text(json.dumps(dict(scope='same recorded logical state; explicit ray-driver and softness interventions only, all other layers unchanged',rows=ledger),indent=2))
    return original(host,target,snapshot,size,window,passes)

with patch.object(capture,'_draw',draw):
    capture.capture(out,args.clip,
                    size=(1672,941),window=(1672,941),overrides={},start=args.at,duration=.02,
                    fps=30,gif=False,preset=args.preset)

if {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths} != source_hashes:
    raise RuntimeError("source changed during ray probe; reject this evidence directory")
