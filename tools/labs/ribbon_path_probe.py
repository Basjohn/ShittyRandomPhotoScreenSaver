"""WR-01a CPU geometry cards/trace; no GL strip, scene, audio or visual-fidelity claim."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PIL import Image, ImageDraw
from core.ribbon_geometry import PathSample, RibbonHistory


def capture(output: Path):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Refusing to overwrite path proof: {output}')
    output.mkdir(parents=True, exist_ok=True)
    fixtures = {
        'stationary': [(3., 0., 0.)]*6,
        'straight': [(float(i), 0., 0.) for i in range(6)],
        'unequal spacing': [(0., 0., 0.), (.001, .01, 0.), (.1, .2, 0.), (4., 1., 0.), (5., -.5, 0.)],
        'repeated and reversing': [(0., 0., 0.), (2., .5, 0.), (2., .5, 0.), (1., -.5, 0.), (4., 0., 0.)],
        'growing': [(i*.5, math.sin(i*.6), 0.) for i in range(9)],
        'saturated': [(i*.5, math.sin(i*.6), 0.) for i in range(16)],
    }
    card = Image.new('RGB', (960, 720), '#101722')
    draw = ImageDraw.Draw(card)
    traces = {}
    for index, (name, positions) in enumerate(fixtures.items()):
        history = RibbonHistory(8)
        for i, position in enumerate(positions):
            history.append(PathSample(i/60, position))
        knots = history.records()
        evaluated = [history.evaluate(float(q)) for q in np.linspace(knots[0, 0], knots[-1, 0], 121)]
        x, y = (index % 2)*480, (index // 2)*240
        draw.text((x+16, y+12), name+' (CPU XY plot)', fill='white')
        def pixel(p):
            return (x+25+p[0]*52, y+130-p[1]*65)
        draw.line([pixel(sample.position) for sample in evaluated], fill='#56ced9', width=2)
        for knot in knots:
            px, py = pixel(knot[1:4])
            draw.ellipse((px-3, py-3, px+3, py+3), fill='#dc78e1')
        traces[name] = dict(count=len(history), capacity=history.capacity, payload_bytes=history.payload_bytes,
                            knots=knots.tolist(), positions=[list(s.position) for s in evaluated])
    card.save(output / 'path_cards.png')
    receipt = dict(stage='WR-01a CPU path reference only', fixtures=traces,
                   producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   core_sha256=hashlib.sha256((ROOT/'core/ribbon_geometry.py').read_bytes()).hexdigest(),
                   frame_transport_implemented=False, gpu_strip_implemented=False,
                   scene_likeness_accepted=False, gpu_cost_measured=False)
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(f'CPU path cards/trace: {output}; GPU/frame/fidelity gates open')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    capture(parser.parse_args().output)
