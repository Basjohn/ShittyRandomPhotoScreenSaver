"""CPU width-frame cards through shared projection matrices; not a GL scene render."""
from pathlib import Path
import argparse
from dataclasses import asdict
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw
from core.ribbon_frames import FrameDiscontinuity, strip_path, width_frame
from core.ribbon_geometry import PathSample
from tools.labs.waveform_ribbon_preflight import projection_fixture


def capture(output):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Refusing to overwrite frame evidence: {output}')
    output.mkdir(parents=True, exist_ok=True)
    card = Image.new('RGB', (960, 640), '#101722')
    draw = ImageDraw.Draw(card)
    traces = {}
    for index, (mode, projection, twisting) in enumerate((
        ('oriented', 'orthographic', False), ('oriented', 'orthographic', True),
        ('camera_facing', 'orthographic', False), ('camera_facing', 'perspective', False))):
        samples, tangents = [], []
        for i in range(81):
            q = i*3/80
            samples.append(PathSample(q, (q-1.5, math.sin(q), math.cos(q)-10), .25, q*3 if twisting else 0))
            tangents.append((1., math.cos(q), -math.sin(q)))
        stations = strip_path(samples, tangents, mode=mode, projection=projection, eye=(0, 0, 0))
        fixture = projection_fixture(480, 320, projection, half_height=2.)
        m = fixture['matrix']
        ox, oy = (index % 2)*480, (index // 2)*320
        def pixel(p):
            w = m[11]*p[2]+m[15]
            return (ox+(1+(m[0]*p[0]+m[12])/w)*240,
                    oy+(1-(m[5]*p[1]+m[13])/w)*160)
        label = f'{mode} {projection} twist={twisting}'
        draw.text((ox+12, oy+12), label, fill='white')
        draw.line([pixel(s.left) for s in stations], fill='#56ced9', width=2)
        draw.line([pixel(s.right) for s in stations], fill='#dc78e1', width=2)
        for s in stations[::5]:
            draw.line([pixel(s.left), pixel(s.right)], fill='#b3bfcc')
        traces[label] = [asdict(s) for s in stations]
    diagnostics = {'stationary_gap': width_frame((0, 0, 0)) is None,
                   'camera_parallel_frame': asdict(width_frame((0, 0, -1), mode='camera_facing'))}
    anchor = width_frame((1, 0, 0))
    for name, tangent, options in (
        ('cusp', (-1, 0, 0), {}),
        ('roll_ambiguity', (1, 0, 0), dict(mode='camera_facing', view_direction=(math.sqrt(1-.04**2), .04, 1e-10)))):
        try:
            width_frame(tangent, previous=anchor, **options)
        except FrameDiscontinuity as error:
            diagnostics[name] = str(error)
        else:
            raise AssertionError(f'Degeneracy witness failed: {name}')
    card.save(output/'frame_cards.png')
    receipt = dict(stage='WR-01b CPU frames only', stations=traces, degeneracies=diagnostics, gpu_rendered=False,
                   displaced_surface_normals_validated=False, scene_likeness_accepted=False,
                   producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   core_sha256=hashlib.sha256((ROOT/'core/ribbon_frames.py').read_bytes()).hexdigest(),
                   card_sha256=hashlib.sha256((output/'frame_cards.png').read_bytes()).hexdigest())
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(f'CPU frame proof: {output}; stationary/pole/cusp/roll witnesses recorded; GPU/surface/fidelity gates open')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    capture(parser.parse_args().output)
