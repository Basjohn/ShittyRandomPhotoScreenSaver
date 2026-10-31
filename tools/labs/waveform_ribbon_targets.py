"""WR-00 target table for the approved Waveform Ribbon board; measurement only, no scene or renderer.

Reads the low/high cards a preflight run extracted (`waveform_ribbon_preflight.py`), never the originals'
replacements. Geometry is hand-traced on gridded 2x cards and labelled as an estimate: automatic
segmentation cannot separate the ribbons from bloom haze and light-column halos (Lab Plan section 1.3).
Colour, luminance and clipping are measured automatically inside fixed ROIs with annotations masked out.
The Orthographic camera is an analytic fit to the traced landmarks, unverified until a WR-03 render.

    .venv\\Scripts\\python.exe tools/labs/waveform_ribbon_targets.py
        --cards .artifacts/evidence/waveform_ribbon/wr00_reference_projection
        --output .artifacts/evidence/waveform_ribbon/<new-run>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]

# Crop-local pixels, right/bottom exclusive; padded over title panels, callouts, leader lines and end dots.
MASKS = {
    'low': ((10, 10, 300, 85),),
    'high': ((10, 10, 385, 85), (400, 74, 582, 131), (405, 125, 420, 180), (36, 189, 229, 244),
             (165, 238, 195, 300), (24, 459, 219, 516), (130, 395, 165, 465), (420, 592, 584, 650),
             (398, 582, 416, 598)),
}

# Hand-traced estimates (crop-local px): x -> (top, bottom) of the union of ribbon bodies, sparse points
# excluded. Read on 2x cards with 20 px grids; expect about +/-8 px, more where callouts occlude (high x 120-200).
ENVELOPE = {
    'low': {0: (335, 400), 40: (340, 405), 80: (352, 410), 120: (340, 420), 160: (315, 415), 200: (300, 395),
            240: (290, 370), 280: (275, 370), 320: (285, 370), 360: (310, 395), 400: (345, 410), 440: (355, 400),
            480: (320, 380), 520: (300, 360), 560: (310, 365), 600: (320, 375), 639: (310, 370)},
    'high': {0: (265, 400), 40: (280, 405), 80: (300, 410), 120: (300, 420), 160: (290, 430), 200: (265, 440),
             240: (220, 435), 280: (215, 400), 320: (240, 400), 360: (250, 420), 400: (240, 450), 440: (195, 470),
             480: (170, 455), 520: (185, 430), 560: (210, 400), 600: (225, 380), 637: (240, 360)},
}
TRACED = {
    'bodies': 'three in both panels: cyan/light-blue, blue/violet, magenta; inner lines are structure, not ribbons',
    'cyan_peaks_x': {'low': (230, 515), 'high': (250, 490)},
    'wavelength_px': {'low': 285, 'high': 245},
    'body_width_px': {'low': (10, 25), 'high': (40, 90)},
    'floor_contact_y': {'low': 450, 'high': 452},
    'light_columns_x': {'low': (25, 90, 195, 325, 475, 610), 'high': (20, 90, 190, 310, 590)},
    'status': 'estimate; hand-traced on gridded 2x cards',
}

# Lab Plan section 1.3 ROIs, converted from board to crop-local pixels.
ROIS = {
    'low': {'body_crossing': (90, 267, 445, 427), 'floor': (15, 477, 625, 697), 'environment_upper': (300, 90, 640, 230)},
    'high': {'crest_strands': (199, 172, 379, 342), 'overlap_trough': (314, 332, 539, 482), 'floor': (14, 502, 619, 697),
             'environment_upper': (0, 90, 380, 180)},
}


def roi_stats(pixels: np.ndarray, valid: np.ndarray) -> dict:
    rgb = pixels[valid].astype(float)/255
    luminance = rgb @ np.array((.2126, .7152, .0722))
    peak, low = rgb.max(1), rgb.min(1)
    chroma = peak - low
    return dict(pixels=int(valid.sum()),
                luminance=dict(p10=float(np.percentile(luminance, 10)), median=float(np.median(luminance)),
                               p90=float(np.percentile(luminance, 90))),
                median_rgb=[float(v) for v in np.median(rgb, axis=0)],
                chroma_median=float(np.median(chroma)),
                clipped_fraction=float((pixels[valid].max(1) >= 250).mean()),
                dark_fraction=float((luminance < .05).mean()))


def envelope_summary(name: str, height: int) -> dict:
    points = ENVELOPE[name]
    tops = np.array([t for t, _ in points.values()], float)
    bottoms = np.array([b for _, b in points.values()], float)
    centre = (tops + bottoms)/2
    return dict(top_min=float(tops.min()/height), bottom_max=float(bottoms.max()/height),
                centre_mean=float(centre.mean()/height),
                centre_amplitude=float((centre.max() - centre.min())/2/height),
                thickness_mean=float((bottoms - tops).mean()/height),
                thickness_range=[float((bottoms - tops).min()/height), float((bottoms - tops).max()/height)])


def camera_fit(height: int) -> dict:
    """Analytic Orthographic fit to the low panel's landmarks (the scene shared by both panels).

    World: floor y=0, flow along +x, z toward the camera, ribbons centred on the pivot. Screen
    v = (y-yp)cos(pitch) - (z-zp)sin(pitch) for a camera pitched down. Scale from the wavelength.
    """
    wavelength = 4.  # world units, chosen for round numbers
    half_height = wavelength/(TRACED['wavelength_px']['low']/height*2)
    pitch = math.radians(15.)
    ribbon_height = 2.
    contact = half_height*(1 - 2*TRACED['floor_contact_y']['low']/height)
    back_wall = (contact + ribbon_height*math.cos(pitch))/math.sin(pitch)
    near_floor = (half_height - ribbon_height*math.cos(pitch))/math.sin(pitch)
    reflection_v = -2*ribbon_height*math.cos(pitch)
    return dict(status='analytic proposal; verify against the target in the WR-03 blockout render',
                projection='orthographic', half_height=half_height, pitch_down_degrees=15.,
                pivot=[0., ribbon_height, 0.], world_wavelength=wavelength,
                back_wall_depth=back_wall, near_floor_depth=near_floor,
                ribbon_reflection_y_fraction=(1 - reflection_v/half_height)/2,
                note='Low/high share this camera; widening reveals more hall at the same scale.')


def card(image: Image.Image, name: str) -> Image.Image:
    sheet = image.convert('RGB')
    draw = ImageDraw.Draw(sheet)
    for box in MASKS[name]:
        draw.rectangle((box[0], box[1], box[2]-1, box[3]-1), outline=(255, 40, 40))
    for label, box in ROIS[name].items():
        draw.rectangle((box[0], box[1], box[2]-1, box[3]-1), outline=(80, 255, 120))
        draw.text((box[0]+3, box[1]+2), label, fill=(80, 255, 120))
    xs = sorted(ENVELOPE[name])
    draw.line([(x, ENVELOPE[name][x][0]) for x in xs], fill=(255, 230, 0), width=2)
    draw.line([(x, ENVELOPE[name][x][1]) for x in xs], fill=(255, 230, 0), width=2)
    floor = TRACED['floor_contact_y'][name]
    draw.line([(0, floor), (sheet.width, floor)], fill=(255, 140, 0))
    for x in TRACED['light_columns_x'][name]:
        draw.line([(x, 0), (x, 12)], fill=(255, 140, 0), width=3)
    return sheet


def run(cards: Path, output: Path) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Refusing to overwrite evidence: {output}')
    images = {name: Image.open(cards/f'{name}.png') for name in ('low', 'high')}
    for image in images.values():
        image.load()
    if {name: image.size for name, image in images.items()} != {'low': (640, 709), 'high': (638, 709)}:
        raise ValueError('Card sizes changed; review crop authority before measuring')
    output.mkdir(parents=True, exist_ok=True)
    panels = {}
    for name, image in images.items():
        pixels = np.asarray(image.convert('RGB'))
        valid = np.ones(pixels.shape[:2], bool)
        for x0, y0, x1, y1 in MASKS[name]:
            valid[y0:y1, x0:x1] = False
        regions = {}
        for label, (x0, y0, x1, y1) in ROIS[name].items():
            region = np.zeros_like(valid)
            region[y0:y1, x0:x1] = True
            regions[label] = roi_stats(pixels, region & valid)
        panels[name] = dict(size=list(image.size), envelope_px={str(x): list(v) for x, v in ENVELOPE[name].items()},
                            envelope=envelope_summary(name, image.height), rois=regions)
        card(image, name).save(output/f'{name}_targets.png')
    sheet = Image.new('RGB', (640 + 638 + 8, 709), (0, 0, 0))
    sheet.paste(Image.open(output/'low_targets.png'), (0, 0))
    sheet.paste(Image.open(output/'high_targets.png'), (648, 0))
    sheet.save(output/'targets_sheet.png')
    receipt = dict(stage='WR-00 target table', panels=panels, traced=TRACED, masks=MASKS,
                   camera=camera_fit(709), tolerances='set from candidate comparisons with operator review; not invented here',
                   card_sha256={name: hashlib.sha256((cards/f'{name}.png').read_bytes()).hexdigest() for name in images},
                   producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    (output/'targets.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cards', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.cards, args.output)
    json.dump(dict(envelope={k: v['envelope'] for k, v in result['panels'].items()}, camera=result['camera']), sys.stdout, indent=2)
