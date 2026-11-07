"""WR-00 target table for the approved Waveform Ribbon board; measurement only, no scene or renderer.

Reads the low/high cards a preflight run extracted (`waveform_ribbon_preflight.py`), never the originals'
replacements. Geometry is hand-traced on gridded 2x cards and labelled as an estimate: automatic
segmentation cannot separate the ribbons from bloom haze and light-column halos (Lab Plan section 1.3).
Colour, luminance and clipping are measured automatically inside fixed ROIs with annotations masked out.
The camera is a historical WR-00 analytic Orthographic fit to the traced landmarks (Orthographic was retired
5 Nov 2026; the product camera is Perspective only).

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
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
if str(_Path(__file__).resolve().parents[2]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402

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
FOG_MASKS = {'low': ((16,12,340,92),), 'high': ((16,12,440,92),)}
FOG_ROIS = {
    'low': {'waveform': (8,290,812,450), 'floor': (8,510,812,710), 'mist': (8,95,812,290)},
    'high': {'crest_strands': (160,180,410,375), 'overlap_trough': (340,350,610,480),
             'floor': (8,510,812,710), 'mist': (8,95,812,180)},
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
                saturation_median=float(np.median(chroma/np.maximum(peak, 1e-6))),
                mean_rgb=[float(v) for v in rgb.mean(axis=0)],
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


def compare(cards: Path, renders: Path, output: Path, *, board: str = 'primary') -> dict:
    """Fixed masked ROIs and native-size crops; neither reference nor render is stretched to match the other."""
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Refusing to overwrite evidence: {output}')
    output.mkdir(parents=True, exist_ok=True)
    if board not in ('primary','fog'):
        raise ValueError('Unknown reference board')
    rois,masks = (FOG_ROIS,FOG_MASKS) if board=='fog' else (ROIS,MASKS)
    width,height = (820,718) if board=='fog' else (640,709)
    report = {'board': board, 'rois': rois, 'masks': masks, 'panels': {}, 'inputs': {}}
    full = Image.new('RGB', (width*2, height*2))
    for row, state in enumerate(('low', 'high')):
        paths = {'mock': cards/f'{state}.png', 'lab': renders/f'lit_{state}.png'}
        images = {label: Image.open(path).convert('RGB') for label, path in paths.items()}
        mock_size = (width if board=='fog' or state=='low' else 638,height)
        if images['mock'].size != mock_size or images['lab'].size != (width,height):
            raise ValueError(f'Comparison needs native {board} cards and {width}x{height} lab captures')
        report['inputs'][state] = {label: dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                                   for label, path in paths.items()}
        report['panels'][state] = {}
        crop_width = max(x1-x0 for x0,y0,x1,y1 in rois[state].values())*2
        crop_height = sum((y1-y0)*2+24 for x0,y0,x1,y1 in rois[state].values())
        crops = Image.new('RGB', (crop_width*2+8, crop_height), (12,12,16))
        pen = ImageDraw.Draw(crops)
        for column, (label, image) in enumerate(images.items()):
            full.paste(image, (column*width,row*height))
            pixels = np.asarray(image)
            valid = np.ones(pixels.shape[:2], bool)
            for x0,y0,x1,y1 in masks[state]:
                valid[y0:y1,x0:x1] = False
            report['panels'][state][label] = {}
            y = 0
            for region, box in rois[state].items():
                x0,y0,x1,y1 = box
                select = np.zeros_like(valid)
                select[y0:y1,x0:x1] = True
                report['panels'][state][label][region] = roi_stats(pixels, valid & select)
                x = column*(crop_width+8)
                pen.text((x,y+4), f'{label} | {region} | native pixels at 2x', fill='white')
                crops.paste(image.crop(box).resize(((x1-x0)*2,(y1-y0)*2), Image.Resampling.NEAREST), (x,y+24))
                y += (y1-y0)*2+24
        crops.save(output/f'crops_{state}.png')
    full.save(output/'mock_lab.png')
    report['producer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (output/'comparison.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cards', type=Path, required=True)
    parser.add_argument('--output', type=artifact_paths.evidence_arg, required=True)
    parser.add_argument('--renders', type=Path, help='Compare a lab capture using fixed masked ROIs and 2x crops')
    parser.add_argument('--board', choices=('primary','fog'), default='primary')
    args = parser.parse_args()
    evidence_media.redirect_output(args, "output", "waveform_ribbon_targets")
    if args.renders:
        compare(args.cards, args.renders, args.output, board=args.board)
        print(f'Comparison saved to {args.output}')
    else:
        if args.board != 'primary':
            parser.error('The fog board currently has ROI comparisons only; pass --renders')
        result = run(args.cards, args.output)
        json.dump(dict(envelope={k: v['envelope'] for k, v in result['panels'].items()}, camera=result['camera']), sys.stdout, indent=2)
    evidence_media.finish(0)
