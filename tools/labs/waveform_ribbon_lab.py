"""Waveform Ribbon scene lab: world-first floor, waveform and distance mist over shared primitives.

The world is authored in world units and viewed through the shared framed camera (``core.settings.framed_camera``)
with the shared scene spec; nothing is placed relative to the camera or the card. ``POSES['mock']`` reproduces the mock's
view for comparison; the other poses navigate the same world. No walls or pillars: the floor disappears into mist
beyond a corridor of clear air. Volumetric clearance and illumination follow the live Lab Plan.

Ribbons are flowing history (Lab Plan section 4A): one ``RibbonRing`` fed by a labelled synthetic head (no music)
whose head and tail sit at fixed world x and fade by age. Two renders per state and pose:

- ``flat``: solid colours, no light, bloom or mist; ribbon envelopes measured against the WR-00 target table.
- ``lit``: ribbon material, wet floor, mist and bloom through the Visualizer-shaped scope.

The floor uses saved generated concrete colour, roughness and smooth wet-surface height with the shared planar reflection
(S3D-5): ribbon light drawn through the mirrored camera, sampled at the floor's own screen position,
streaked and blurred by wet roughness and perturbed by the micro-surface.

    .venv\\Scripts\\python.exe tools/labs/waveform_ribbon_lab.py --output .artifacts/evidence/visualizers/waveform_ribbon/lab/<YYYYMMDD>_<label>
        [--cards <lossless preflight cards in .artifacts/scratch/<owner>/>] [--recipe complete|alternate|range]

Named looks (``RECIPES``) share every program and function; they differ in values only.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rendering.gl_error_policy import disable_per_call_gl_error_checking
# As a script, GL must load under the production error policy; imported (tests) it reuses the caller's GL.
if not disable_per_call_gl_error_checking() and __name__ == '__main__':
    raise RuntimeError('GL imported before benchmark production policy')
import numpy as np
from PIL import Image, ImageDraw
from core.ribbon_ring import RibbonRing
from core.ribbon_style import RibbonStrays
from core.waveform_ribbon_scene import (Environment, Fog, Floor, Flow, Shaping, Recipe, SPEC,
    VIEW_SLOPE, FLOOR_CONTACT, PALETTE, hue_between)
from rendering.quick.scene3d.waveform import (WaveformScene, gradient_at, colour_grade,
    capped, floor_vertices, load_floor_textures)
from tools.labs.render_target import OffscreenRenderTarget
from tools.labs.waveform_ribbon_targets import ENVELOPE
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402

# Lab poses author inputs only. The production grounded Perspective camera is shared;
# the older WR-00 camera is historical evidence.


@dataclass(frozen=True)
class Pose:
    turn: float = 0.
    tilt: float = 0.
    scale: float = 1.
    pan_x: float = 0.
    pan_y: float = 0.
    fov: float = 5.


POSES = {'mock': Pose(), 'turned': Pose(turn=.14), 'raised': Pose(tilt=-.12), 'dolly': Pose(scale=1.6, pan_x=.12),
         'wide': Pose(fov=35.)}


STATES = {'low': dict(react=0.), 'high': dict(react=1.)}  # labelled synthetic reactivity, not music
SOURCES = ('loudness', 'bass')  # the synthetic energy sources a tuner target can follow (see synthetic_sources)


def synthetic_sources(state: str, t: float, shaping: Shaping) -> dict:
    """The labelled states' synthetic energy (0..1), not music: loudness holds the state's reactivity; bass swells
    for ``length`` seconds once every ``every`` seconds (a raised cosine), scaled by the reactivity."""
    react = STATES[state]['react']
    every, length, offset = shaping.bass
    u = ((t - offset) % every)/length
    return dict(loudness=react, bass=react*(.5 - .5*math.cos(2*math.pi*u)) if u < 1. else 0.)


# Second look: the preset-range board (Lab Plan section 0). The same lab, programs and functions with other values
# only: a tight braided bundle, more and smaller waves, one bass arc that towers over the rest when loud, and a
# gradient that runs on to orange at the right in high react. The sheets take most of the gradient, so the whole
# bundle shares one colour at each x as on the board. Mist stays (core to every look).
PRESET_RANGE = Recipe(
    flow=Flow(head_hz=.42, phase_swell=.2, amplitude_swell=.1, depth_sway=.5),
    shaping=Shaping(
        ranges=dict(width=(.16, .5), width_swell=(.04, .16), twist=(.9, 1.6), emission=(.7, .9), spread=(.12, .45),
                    amplitude=(.3, .8), lift=(.35, .55), sparkle=(.18, .9), deformation=(.08, .15), arc=(.15, 1.8),
                    tint=(0., 0.)),
        bass=(12., 2.4, 8.8),
        characters=((1., 1., 1., 0., 1.), (.92, .9, 1., .35, 1.2), (.85, .8, 1., .7, .8))),
    material=replace(Recipe().material, strand_white=0., rim_white=.03),
    palette=dict(low=((0., (0., .9, 1.)), (.3, (.1, .3, 1.)), (.55, (.55, .12, 1.)), (.8, (1., .15, .85)),
                      (1., (1., .15, .85))),
                 high=((0., (0., .9, 1.)), (.3, (.15, .25, 1.)), (.55, (1., .1, .8)), (.8, (1., .22, .03)),
                       (1., (1., .22, .03)))),
    grade_range=(-5.5, 5.5), grade_share=(.8, .85))
# Second goal (operator, 1 November): the package's alternate board. Three broad ribbons, one per band (bass, mid,
# high), coloured by ribbon rather than by the world grade: blue, teal and lavender when quiet; magenta, orange and
# blue-violet when loud, taken knot by knot so the colour flows with the history. Long sweeping waves with large
# depth sway, dense bright filaments, many sparks when loud. Mist stays.
ALTERNATE = Recipe(
    flow=Flow(head_hz=.2, phase_swell=.3, amplitude_swell=.3, depth_sway=2.),
    shaping=Shaping(
        ranges=dict(width=(.95, .9), width_swell=(.1, .3), twist=(.9, 1.7), emission=(.75, .75), spread=(1.6, 2.4),
                    amplitude=(1.2, 1.5), lift=(.3, .6), sparkle=(.25, 1.), deformation=(.15, .3), arc=(0., 0.),
                    tint=(0., .9)),
        characters=((1., 1., 1., 0., 1.), (.8, 1.2, .9, 1.6, 1.3), (.7, .85, 1.15, 2.8, .9))),
    # Colours are linear light: orange is about (1, .2, .03); (1, .4, .05) displays as gold.
    ribbon_colours=dict(low=(((.15, .35, 1.), (.35, .25, 1.)), ((0., .7, .9), (.1, .4, 1.)), ((.5, .2, 1.), (.4, .15, 1.))),
                        high=(((1., .1, .7), (.6, .05, 1.)), ((1., .2, .03), (1., .13, .06)), ((.15, .2, 1.), (.45, .1, 1.)))),
    # Loud ribbons stay narrower and further apart than quiet ones: broad overlapping sheets summed to pastel pink.
    # Luminous silk: a glowing body, local bloom on the sheets only (glow), white-hot cores on the brightest strands.
    material=replace(Recipe().material, strands=48., strand_half_width=.022, strand_light=2.4, strand_white=0.,
                     rim_white=.02, fill_light=.1, rim_glow_light=.45, body_tint=.85, glint_density=3.,
                     glint_chance=.3, glint_light=5., glow=2., hot=.3),
    # Sparks hug the ribbons (little drift or rise), mostly fine with a few large.
    sparks=replace(Recipe().sparks, drift=1.1, rise=.15, light=40., smallest=1.2, largest=8., lifetime=6., white=.04),
    palette=dict(low=((0., (.2, .6, 1.)), (1., (.55, .35, 1.))), high=((0., (1., .3, .85)), (1., (1., .22, .05)))),
    # Free strands splash off the sheets and curl away, droplets toward their tips (short, far-reaching).
    strays=RibbonStrays(per_knot=4, length=6., reach=1.6, chance=.6, width=1.6, light=3.2, beads=4., peel_time=1.5,
                        halo=.5, glow=2.2),
    # More tint for any colour pair: less highlight compression (exposure), less white-hot, more body tint.
    grade_share=(0., .35), bloom=.12, exposure=.85)
RECIPES = {'complete': Recipe(), 'alternate': ALTERNATE, 'range': PRESET_RANGE}


def camera(pose: Pose, aspect: float):
    """(world->view 4x4, projection 4x4, eye) from the shared framed camera; the world never moves."""
    from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
    view,projection,eye,_=physical_view(_pose_parameters(pose),aspect)
    return view,projection,eye


def _pose_parameters(pose):
    return {'waveform_ribbon_'+key:value for key,value in dict(turn=pose.turn,tilt=pose.tilt,scene_scale=pose.scale,
        scene_pan_x=pose.pan_x,scene_pan_y=pose.pan_y,camera_fov=pose.fov,camera_position=(0.,0.,0.)).items()}


def lens(pose: Pose, aspect: float) -> tuple[float, float]:
    """The fog volume's lens for a pose: Perspective tangents."""
    from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
    return physical_view(_pose_parameters(pose),aspect)[3]


def fill_ring(recipe: Recipe, state: str, knots: int = 256, *, at: float | None = None) -> tuple[RibbonRing, float]:
    """Synthetic head: band-limited shape controls (Lab Plan section 4A) through the recipe's shape tuner; returns
    the ring and newest time."""
    flow, shaping = recipe.flow, recipe.shaping
    now = (knots-1)/flow.knot_hz if at is None else float(at)
    if not math.isfinite(now) or not (knots-1)/flow.knot_hz <= now <= 120.:
        raise ValueError('Lab sample time must contain warm history and stay within 120 seconds')
    quiet, loud = recipe.ribbon_colours['low'], recipe.ribbon_colours['high']
    ring = RibbonRing(len(PALETTE), colours=[(*a, 1.) for a, _ in quiet], edge_colours=[(*b, 1.) for _, b in quiet], period=.5)
    loud_colours = [tuple((np.asarray(a) + np.asarray(b))/2) for a, b in loud]
    alpha = 1 - math.exp(-1/flow.knot_hz/flow.shape_tau)
    count = len(PALETTE)
    if len(shaping.characters) != count:
        raise ValueError('The shape tuner needs one character per ribbon')
    stages = [[0., 0.] for _ in range(count)]
    levels = None  # per source, the two smoothing stages (band-limited like every history-carried control)
    pivot_y = SPEC.pivot[1]
    t = 0.
    for i in range(math.floor(now*flow.knot_hz)+1):
        t = i/flow.knot_hz
        positions, widths, twists, light, sparkle, tints = [], [], [], [], [], []
        raw = synthetic_sources(state, t, shaping)
        if levels is None:
            levels = {k: [v, v] for k, v in raw.items()}
        for k, v in raw.items():
            levels[k][0] += (v - levels[k][0])*alpha
            levels[k][1] += (levels[k][0] - levels[k][1])*alpha
        s = {target: quiet + (loud - quiet)*levels[shaping.drive.get(target, 'loudness')][1]
             for target, (quiet, loud) in shaping.ranges.items()}
        arc = 1. + s['arc']*levels['bass'][1]
        for r in range(count):
            k = r - (count - 1)/2  # a fixed fan in height and depth, identical in low/high
            amplitude, width, frequency, offset, brightness = shaping.characters[r]
            phase = 2*math.pi*flow.head_hz*frequency*t + offset + flow.phase
            phase += flow.phase_swell*math.sin(.31*phase+r*.6)
            envelope = 1. + flow.amplitude_swell*math.sin(.23*phase+.4)
            section = 1. if math.sin(2*math.pi*.3*t + r*2.) > .2 else 0.
            stages[r][0] += (section - stages[r][0])*alpha
            stages[r][1] += (stages[r][0] - stages[r][1])*alpha
            swell = stages[r][1]
            deformation = s['deformation']*(.24*math.sin(2*phase+.7)+.18*math.sin(.61*phase+offset))
            half = width*(s['width'] + s['width_swell']*swell)*(1.0 + .2*math.sin(phase))
            y = pivot_y + s['lift'] + s['amplitude']*arc*amplitude*envelope*(math.sin(phase)+deformation) \
                + .5*k*s['spread']*math.cos(.37*phase)
            positions.append((flow.speed*t, y, .65*k + flow.depth_sway*math.cos(phase*.55+r)))
            widths.append(half)
            twists.append(s['twist']*(.7*math.sin(.48*phase+r*1.3)+.3*math.sin(.87*phase+.4)))
            light.append(brightness*s['emission']*(.85 + .3*swell))
            highs = .5 + .5*math.sin(2*math.pi*.53*t + r*1.7)  # synthetic highs: sparkle density
            sparkle.append(min(1., s['sparkle']*(.35 + .65*highs)))
            tints.append((*loud_colours[r], min(max(s['tint'], 0.), 1.)))
        ring.append(t, positions, widths, twists, light, sparkle, tints)
    return ring, now


class Lab(WaveformScene):
    """Diagnostic target and explicit fixture camera over the same retained scene as production."""
    def __init__(self, recipe: Recipe, size: tuple[int, int]):
        super().__init__()
        self.recipe, self.size = recipe, size
        self.target = OffscreenRenderTarget(*size)

    def close(self):
        with self.target.current():
            self.release()
        self.target.close()

    def render(self, state, *, flat, pose='mock', at=None):
        with self.target.current():
            ring, now = fill_ring(self.recipe, state, at=at)
            return self._capture(ring, now, flat=flat, pose=pose, react=STATES[state]['react'])

    def render_history(self, ring, now, *, flat=False, pose='mock'):
        if not math.isfinite(now):
            raise ValueError('History render time must be finite')
        with self.target.current():
            return self._capture(ring, now, flat=flat, pose=pose)

    def _capture(self, ring, now, *, flat=False, pose='mock', react=0.):
        width, height = self.size
        packet=ring.packet()
        view, projection, eye = camera(POSES[pose], width/height)
        card = SimpleNamespace(viewport=(0,0,width,height),logical_size=(float(width),float(height)),
            matrix_values=(2/width,0,0,0,0,-2/height,0,0,0,0,1,0,-1,1,0,1),quad_vao=self.target.vao)
        self.target.bind(clear=(0.,0.,0.,0.))
        super().render(packet,capacity=ring.capacity,now=now,recipe=self.recipe,size=self.size,
            travel=self.recipe.flow.speed*now,
            view=view,projection=projection,eye=eye,camera_lens=lens(POSES[pose],width/height),card=card,
            flat=flat,react=react)
        return self.target.read_rgba()


def measure_flat(pixels: np.ndarray) -> dict:
    """Ribbon envelope from a flat mock-pose render, as panel fractions."""
    height, width = pixels.shape[:2]
    rgb = pixels[:, :, :3].astype(int)
    ribbon = (rgb[:, :, 0] > 120) & (rgb[:, :, 2] > 120) & (rgb[:, :, 1] < 60)  # FLAT['ribbon'] magenta
    envelope = {}
    for x in ENVELOPE['low']:
        column = np.where(ribbon[:, min(x, width - 1)])[0]
        envelope[str(x)] = [float(column.min()/height), float(column.max()/height)] if column.size else None
    return dict(envelope=envelope)


def landmark_report(measured: dict, state: str, height: int = 709) -> dict:
    target = {str(x): (top/height, bottom/height) for x, (top, bottom) in ENVELOPE[state].items()}
    rows, errors = {}, []
    for x, value in measured['envelope'].items():
        goal = target.get(x)
        if value is None or goal is None:
            continue
        rows[x] = dict(lab=value, target=list(goal))
        errors += [value[0] - goal[0], value[1] - goal[1]]
    present = [v for v in measured['envelope'].values() if v]
    return dict(rows=rows, envelope_mean_abs_error=float(np.mean(np.abs(errors))) if errors else None,
                lab_envelope=[min(v[0] for v in present), max(v[1] for v in present)] if present else None,
                target_envelope=[min(t for t, _ in target.values()), max(b for _, b in target.values())])


def overlay(image: Image.Image, state: str) -> Image.Image:
    """Target ribbon envelope over an image; the scene has no visible horizon/contact boundary."""
    sheet = image.convert('RGB')
    draw = ImageDraw.Draw(sheet)
    xs = sorted(ENVELOPE[state])
    for edge in (0, 1):
        draw.line([(x, ENVELOPE[state][x][edge]) for x in xs], fill=(255, 230, 0), width=1)
    return sheet


def run(output: Path, cards: Path | None, *, board: str = 'primary', recipe_name: str = 'complete') -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Refusing to overwrite evidence: {output}')
    output.mkdir(parents=True, exist_ok=True)
    if board not in ('primary','fog'):
        raise ValueError('Unknown reference board')
    width,height = (820,718) if board=='fog' else (640,709)
    recipe = RECIPES[recipe_name]
    report, images = {}, {}
    lab = Lab(recipe, (width,height))
    try:
        for state in STATES:
            flat = lab.render(state, flat=True)
            lit = lab.render(state, flat=False)
            images[state] = (Image.fromarray(flat), Image.fromarray(lit))
            Image.fromarray(flat).save(output/f'flat_{state}.png')
            Image.fromarray(lit).save(output/f'lit_{state}.png')
            report[state] = (landmark_report(measure_flat(flat), state) if board=='primary'
                             else dict(status='Use fog ROI comparisons; no ribbon envelope has been traced for this board'))
    finally:
        lab.close()
    wide = Lab(recipe, (1280, 720))
    try:
        for state in STATES:
            for pose in POSES:
                Image.fromarray(wide.render(state, flat=False, pose=pose)).save(output/f'wide_{state}_{pose}.png')
    finally:
        wide.close()
    if cards is not None:
        sheet = Image.new('RGB', (width*3 + 16, height*2 + 8))
        for row, state in enumerate(STATES):
            mock = Image.open(cards/f'{state}.png')
            expected = (width if board=='fog' or state=='low' else 638,height)
            if mock.size != expected:
                raise ValueError(f'Expected native {board} {state} card of size {expected}')
            picture = (lambda im: overlay(im,state)) if board=='primary' else (lambda im: im.convert('RGB'))
            sheet.paste(picture(mock), (0,row*(height+8)))
            sheet.paste(picture(images[state][0]), (width+8,row*(height+8)))
            sheet.paste(images[state][1].convert('RGB'), (2*width+16,row*(height+8)))
        sheet.save(output/'mock_flat_lit.png')
    poses = Image.new('RGB', (640*len(POSES), 360*2))
    for row, state in enumerate(STATES):
        for column, pose in enumerate(POSES):
            poses.paste(Image.open(output/f'wide_{state}_{pose}.png').convert('RGB').resize((640, 360)), (column*640, row*360))
    poses.save(output/'navigation_poses.png')
    receipt = dict(stage='WR-04 floor, waveform and dense distance mist; navigation poses', board=board, recipe_name=recipe_name,
                   card_size=(width,height),
                   recipe=json.loads(json.dumps(asdict(recipe), default=str)), states=STATES,
                   poses={k: asdict(v) for k, v in POSES.items()}, landmarks=report,
                   producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=artifact_paths.evidence_arg, required=True)
    parser.add_argument('--cards', type=Path)
    parser.add_argument('--board', choices=('primary','fog'), default='primary')
    parser.add_argument('--recipe', choices=tuple(RECIPES), default='complete',
                        help='named look: the complete-scene board, the alternate board, or the preset-range board')
    args = parser.parse_args()
    evidence_media.redirect_output(args, "output", "waveform_ribbon_lab")
    result = run(args.output, args.cards, board=args.board, recipe_name=args.recipe)
    print(json.dumps({state: {k: v for k, v in r.items() if k != 'rows'} for state, r in result['landmarks'].items()}, indent=2))
    evidence_media.finish(0)
