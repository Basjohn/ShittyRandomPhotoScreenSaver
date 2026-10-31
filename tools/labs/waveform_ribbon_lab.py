"""Waveform Ribbon scene lab (WR-03 onward): the mock's hall composed by hand over the shared primitives.

The lab owns its recipe (camera, hall, flow, synthetic head, palette) and explicit time. No Settings, presets,
registration, clock or music yet. Ribbons come from one `RibbonRing` drawn by `RibbonPrimitive`; the hall is
lab-local geometry. Two renders per state:

- ``flat``: solid colours, no light or bloom. The ribbon envelope and floor line are measured from its pixels and
  compared with the WR-00 target table, so the camera fit is checked against the picture, not assumed.
- ``lit``: ribbon material, emissive light columns and bloom through the Visualizer-shaped scope.

Missing by design until their primitives land: floor reflection (S3D-5) and particles (S3D-2).

    .venv\\Scripts\\python.exe tools/labs/waveform_ribbon_lab.py --output .artifacts/evidence/waveform_ribbon/<new-run>
        [--cards .artifacts/evidence/waveform_ribbon/wr00_reference_projection]
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
import struct
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
from OpenGL import GL as gl
import numpy as np
from PIL import Image, ImageDraw

from core.ribbon_ring import RibbonRing
from core.settings.framed_camera import orthographic_matrix
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.ribbon import RibbonMaterial, RibbonPrimitive
from rendering.quick.scene3d.target import SceneTarget
from tools.labs.render_target import OffscreenRenderTarget
from tools.labs.waveform_ribbon_targets import ENVELOPE, TRACED


@dataclass(frozen=True)
class Camera:  # WR-00 analytic proposal (Lab Plan section 1.3)
    half_height: float = 4.975
    pitch_degrees: float = 15.
    pivot: tuple = (0., 2., 0.)
    distance: float = 30.


@dataclass(frozen=True)
class Hall:
    back_wall: float = 2.29         # behind the pivot
    near_floor: float = 14.         # floor extent toward the camera
    half_length: float = 40.        # along the flow
    # Light columns at the measured fractions of the reference panel width (WR-00), on the back wall.
    column_fractions: tuple = (.04, .14, .30, .50, .74, .95)
    column_half_width: float = .07
    column_height: float = 12.
    column_colours: tuple = ((.35, .7, 1.), (.7, .55, 1.), (.4, .75, 1.), (.55, .6, 1.), (.4, .8, 1.), (.6, .7, 1.))
    column_light: float = 2.2
    floor_colour: tuple = (.018, .024, .045)
    wall_colour: tuple = (.008, .011, .024)


@dataclass(frozen=True)
class Flow:  # Lab Plan section 4A: newest knot just off the right edge, history drifts left
    speed: float = 1.6
    head_hz: float = .4
    knot_hz: float = 20.
    shape_tau: float = .45          # per smoothing stage of history-carried shape controls
    head_margin: float = 1.5


PALETTE = (((.08, .62, 1.), (.15, .42, 1.)),    # electric cyan -> blue
           ((.2, .28, 1.), (.42, .24, 1.)),     # blue -> violet
           ((.62, .2, 1.), (.95, .2, .85)))     # violet -> magenta
STATES = {  # labelled synthetic controls sized from the WR-00 target table; not music
    'low': dict(width=.11, width_swell=.04, twist=1.1, emission=.9, spread=.32, amplitude=.55, lift=0.),
    'high': dict(width=.32, width_swell=.12, twist=2.4, emission=1.25, spread=1.1, amplitude=.85, lift=.5),
}


@dataclass(frozen=True)
class Recipe:
    camera: Camera = field(default_factory=Camera)
    hall: Hall = field(default_factory=Hall)
    flow: Flow = field(default_factory=Flow)
    material: RibbonMaterial = field(default_factory=RibbonMaterial)
    bloom: float = .55
    exposure: float = 1.


HALL_VERTEX = """#version 460 core
layout(location=0) in vec3 aPosition;
layout(location=1) in vec4 aColour;   // rgb, emission
layout(location=2) in vec3 aLocal;    // across (-1..1), height (world), column seed; unused for planes
uniform mat4 uMvp;
out vec4 vColour;
out vec3 vLocal;
void main() { vColour=aColour; vLocal=aLocal; gl_Position=uMvp*vec4(aPosition,1.0); }
"""
HALL_FRAGMENT = """#version 460 core
in vec4 vColour;
in vec3 vLocal;
uniform int uFlat;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
void main() {
    if(uFlat==1) { FragColor=vec4(vColour.rgb,1.0); Emission=vec4(0.0); return; }
    vec3 colour=vColour.rgb;
    float light=0.0;
    if(vColour.a>0.0) {
        // A light column as in the mock: mostly dim haze, two localized bright segments at seeded heights, and a
        // bright pool where it meets the floor. Uniform full-height tubes read as neon signage.
        float core=exp(-pow(vLocal.x*2.2,2.0));
        float height=vLocal.y, seed=vLocal.z;
        float h1=1.6+2.6*fract(sin(seed*91.7)*4375.85), h2=3.8+3.0*fract(sin(seed*37.1)*9123.17);
        float segments=exp(-pow((height-h1)/0.45,2.0))+0.7*exp(-pow((height-h2)/0.7,2.0));
        float base=1.4*exp(-height*2.4);
        float profile=0.07+segments+base;
        light=vColour.a*core*profile*smoothstep(0.0,0.05,height);
        colour=mix(colour,vec3(1.0),0.35*core*core)*light;
    }
    FragColor=vec4(colour,1.0);
    Emission=vec4(colour*step(0.001,light),dot(colour,vec3(0.2126,0.7152,0.0722))*step(0.001,light));
}
"""
FLAT = {'floor': (.25, .25, .25), 'wall': (.1, .1, .1), 'column': (.6, .6, .1), 'ribbon': (1., 0., 1.)}


def look_at(eye, target, up=(0., 1., 0.)):
    forward = (target-eye)/np.linalg.norm(target-eye)
    side = np.cross(forward, up)
    side /= np.linalg.norm(side)
    upward = np.cross(side, forward)
    view = np.identity(4)
    view[0, :3], view[1, :3], view[2, :3] = side, upward, -forward
    view[:3, 3] = -view[:3, :3] @ eye
    return view


def hall_vertices(hall: Hall, flat: bool, reference_width: float) -> bytes:
    """Floor, back wall and columns as one static triangle list: position, colour+emission, local."""
    rows = []

    def quad(corners, colour, emission, locals_):
        for i in (0, 1, 2, 0, 2, 3):
            rows.append((*corners[i], *colour, emission, *locals_[i]))
    z_wall, near, half = -hall.back_wall, hall.near_floor, hall.half_length
    zero = ((0., 0., 0.),)*4
    quad(((-half, 0., z_wall), (half, 0., z_wall), (half, 0., near), (-half, 0., near)),
         FLAT['floor'] if flat else hall.floor_colour, 0., zero)
    quad(((-half, 0., z_wall), (-half, hall.column_height, z_wall), (half, hall.column_height, z_wall), (half, 0., z_wall)),
         FLAT['wall'] if flat else hall.wall_colour, 0., zero)
    # The measured pattern repeats along the hall, so a wider card reveals more hall at the same scale.
    repeats = range(-int(half/reference_width) - 1, int(half/reference_width) + 2)
    columns = [((fraction - .5 + k)*reference_width, colour, 1 + i + 7*(k - repeats[0]))
               for k in repeats for i, (fraction, colour) in enumerate(zip(hall.column_fractions, hall.column_colours))]
    for x, colour, seed in columns:
        if abs(x) > half:
            continue
        w, h, z = hall.column_half_width*(2.5 if not flat else 1.), hall.column_height, z_wall + .02
        quad(((x - w, 0., z), (x - w, h, z), (x + w, h, z), (x + w, 0., z)), FLAT['column'] if flat else colour,
             0. if flat else hall.column_light, ((-1., 0., seed), (-1., h, seed), (1., h, seed), (1., 0., seed)))
    return b''.join(struct.pack('10f', *row) for row in rows)


def fill_ring(recipe: Recipe, state: str, knots: int = 256) -> tuple[RibbonRing, float]:
    """Synthetic head: band-limited shape controls (Lab Plan section 4A); returns the ring and newest time."""
    s, flow = STATES[state], recipe.flow
    ring = RibbonRing(3, colours=[(*a, 1.) for a, _ in PALETTE], edge_colours=[(*b, 1.) for _, b in PALETTE], period=.5)
    alpha = 1 - math.exp(-1/flow.knot_hz/flow.shape_tau)
    stages = [[0., 0.] for _ in range(3)]
    pivot_y = recipe.camera.pivot[1]
    t = 0.
    for i in range(knots):
        t = i/flow.knot_hz
        positions, widths, twists, light = [], [], [], []
        for r in range(3):
            phase = 2*math.pi*flow.head_hz*t + r*1.1
            section = 1. if math.sin(2*math.pi*.3*t + r*2.) > .2 else 0.
            stages[r][0] += (section - stages[r][0])*alpha
            stages[r][1] += (stages[r][0] - stages[r][1])*alpha
            swell = stages[r][1]
            positions.append((flow.speed*t, pivot_y + s['lift'] + s['amplitude']*math.sin(phase) + (r-1)*s['spread']*math.cos(.37*phase),
                              (r-1)*.5 + .35*math.cos(phase*.8)))
            widths.append(s['width'] + s['width_swell']*swell)
            twists.append(s['twist']*math.sin(2*math.pi*.07*t + r*2.))
            light.append(s['emission']*(.85 + .3*swell))
        ring.append(t, positions, widths, twists, light)
    return ring, t


class Lab:
    """Owns the diagnostic target and lab GL resources; `close()` retires them under the target's context."""

    def __init__(self, recipe: Recipe, size: tuple[int, int]):
        self.recipe, self.size = recipe, size
        self.target = OffscreenRenderTarget(*size)
        self.resources, self.scene, self.ribbons = MeshResources('waveform lab'), SceneTarget('waveform lab'), RibbonPrimitive()

    def close(self):
        with self.target.current():
            self.ribbons.release()
            self.scene.release()
            self.resources.release_resources()
        self.target.close()

    def matrices(self, now: float):
        camera, (width, height) = self.recipe.camera, self.size
        aspect = width/height
        pitch = math.radians(camera.pitch_degrees)
        pivot = np.asarray(camera.pivot, float)
        eye = pivot + camera.distance*np.array((0., math.sin(pitch), math.cos(pitch)))
        view = look_at(eye, pivot)
        projection = np.asarray(orthographic_matrix((camera.half_height*aspect, camera.half_height), .1, 80.)).reshape(4, 4, order='F')
        flow = np.identity(4)
        flow[0, 3] = camera.half_height*aspect + self.recipe.flow.head_margin - self.recipe.flow.speed*now
        return projection, view, flow

    def render(self, state: str, *, flat: bool) -> np.ndarray:
        recipe, (width, height) = self.recipe, self.size
        ring, now = fill_ring(recipe, state)
        projection, view, flow = self.matrices(now)
        hall_mvp = tuple((projection @ view).flatten(order='F'))
        ribbon_view = view @ flow
        ribbon_mvp = tuple((projection @ ribbon_view).flatten(order='F'))
        reference_width = 2*recipe.camera.half_height*640/709  # the panel the column fractions were measured on
        key = 'hall_flat' if flat else 'hall'
        vao, count = self.resources.mesh(key, hall_vertices(recipe.hall, flat, reference_width), (3, 4, 3))
        program = self.resources.program('hall', HALL_VERTEX, HALL_FRAGMENT)
        uniforms = self.resources.uniforms('hall', ('uMvp', 'uFlat'))
        card = SimpleNamespace(viewport=(0, 0, width, height), logical_size=(float(width), float(height)),
                               matrix_values=(2/width, 0, 0, 0, 0, -2/height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                               quad_vao=self.target.vao)
        packet = ring.packet()
        self.target.bind(clear=(0., 0., 0., 0.))
        bloom = 0. if flat else recipe.bloom
        with self.scene.scope(card, 4, self.resources, overlay=1.0, bloom=bloom if bloom else 0.,
                              oit=True, hdr=recipe.exposure if bloom else None):
            gl.glViewport(0, 0, width, height)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LESS)
            gl.glDepthMask(gl.GL_TRUE)
            with self.scene.emission_writes():
                gl.glUseProgram(program)
                gl.glUniformMatrix4fv(uniforms['uMvp'], 1, gl.GL_FALSE, np.asarray(hall_mvp, np.float32))
                gl.glUniform1i(uniforms['uFlat'], int(flat))
                gl.glBindVertexArray(vao)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
                if flat:
                    self._flat_ribbons(packet, ribbon_mvp)
            if not flat:
                view_values = tuple(ribbon_view.flatten(order='F'))
                with self.scene.transparent_writes(card, self.resources):
                    self.ribbons.draw(packet, ribbon_mvp, shading='body', view=view_values, material=recipe.material)
                with self.scene.emission_writes():
                    gl.glEnablei(gl.GL_BLEND, 0)
                    gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
                    gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
                    gl.glDepthMask(gl.GL_FALSE)
                    self.ribbons.draw(packet, ribbon_mvp, shading='light', view=view_values, material=recipe.material)
                    gl.glDepthMask(gl.GL_TRUE)
                    gl.glDisablei(gl.GL_BLEND, 0)
        return self.target.read_rgba()

    def _flat_ribbons(self, packet, mvp):
        """Flat ribbon silhouettes in one known colour: rewrite every ribbon's colours in a copy of the packet."""
        data = np.frombuffer(packet.payload, np.float32).copy().reshape(packet.instances, -1, 4)
        data[:, 2] = data[:, 3] = (*FLAT['ribbon'], 1.)
        flat = type(packet)(data.tobytes(), packet.instances, packet.vertices, packet.world_origin)
        self.ribbons.draw(flat, mvp)


def measure_flat(pixels: np.ndarray) -> dict:
    """Envelope, floor line and column positions read from a flat render, as fractions like the target table."""
    height, width = pixels.shape[:2]
    rgb = pixels[:, :, :3].astype(int)
    ribbon = (rgb[:, :, 0] > 120) & (rgb[:, :, 2] > 120) & (rgb[:, :, 1] < 60)  # FLAT['ribbon'] magenta
    envelope = {}
    for x in ENVELOPE['low']:
        column = np.where(ribbon[:, min(x, width - 1)])[0]
        envelope[str(x)] = [float(column.min()/height), float(column.max()/height)] if column.size else None
    floor_rows = np.where((np.abs(rgb - rgb[height - 2, width//2]).max(2) <= 6).mean(1) > .5)[0]
    return dict(envelope=envelope, floor_top=float(floor_rows.min()/height) if floor_rows.size else None)


def landmark_report(measured: dict, state: str, height: int = 709) -> dict:
    target = {str(x): (top/height, bottom/height) for x, (top, bottom) in ENVELOPE[state].items()}
    rows, errors = {}, []
    for x, value in measured['envelope'].items():
        goal = target.get(x)
        if value is None or goal is None:
            continue
        rows[x] = dict(lab=value, target=list(goal))
        errors += [value[0] - goal[0], value[1] - goal[1]]
    floor_goal = TRACED['floor_contact_y'][state]/height
    return dict(rows=rows, envelope_mean_abs_error=float(np.mean(np.abs(errors))) if errors else None,
                floor=dict(lab=measured['floor_top'], target=floor_goal),
                lab_envelope=[min(v[0] for v in measured['envelope'].values() if v), max(v[1] for v in measured['envelope'].values() if v)],
                target_envelope=[min(t for t, _ in target.values()), max(b for _, b in target.values())])


def overlay(image: Image.Image, state: str) -> Image.Image:
    """Target landmarks over an image: traced envelope (yellow), floor contact (orange)."""
    sheet = image.convert('RGB').resize((640, 709))
    draw = ImageDraw.Draw(sheet)
    xs = sorted(ENVELOPE[state])
    for edge in (0, 1):
        draw.line([(x, ENVELOPE[state][x][edge]) for x in xs], fill=(255, 230, 0), width=1)
    floor = TRACED['floor_contact_y'][state]
    draw.line([(0, floor), (640, floor)], fill=(255, 140, 0))
    return sheet


def run(output: Path, cards: Path | None) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Refusing to overwrite evidence: {output}')
    output.mkdir(parents=True, exist_ok=True)
    recipe = Recipe()
    report, images = {}, {}
    lab = Lab(recipe, (640, 709))
    try:
        for state in STATES:
            flat = lab.render(state, flat=True)
            lit = lab.render(state, flat=False)
            images[state] = (Image.fromarray(flat), Image.fromarray(lit))
            Image.fromarray(flat).save(output/f'flat_{state}.png')
            Image.fromarray(lit).save(output/f'lit_{state}.png')
            report[state] = landmark_report(measure_flat(flat), state)
    finally:
        lab.close()
    wide = Lab(recipe, (1280, 720))
    try:
        for state in STATES:
            Image.fromarray(wide.render(state, flat=False)).save(output/f'wide_{state}.png')
    finally:
        wide.close()
    if cards is not None:
        sheet = Image.new('RGB', (640*3 + 16, 709*2 + 8))
        for row, state in enumerate(STATES):
            mock = Image.open(cards/f'{state}.png')
            sheet.paste(overlay(mock, state), (0, row*717))
            sheet.paste(overlay(images[state][0], state), (648, row*717))
            sheet.paste(images[state][1].convert('RGB'), (1296, row*717))
        sheet.save(output/'mock_flat_lit.png')
    receipt = dict(stage='WR-03 blockout: hall, flat and lit ribbons; no floor reflection or particles',
                   recipe=json.loads(json.dumps(asdict(recipe), default=str)), states=STATES, landmarks=report,
                   producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cards', type=Path)
    args = parser.parse_args()
    result = run(args.output, args.cards)
    print(json.dumps({state: {k: v for k, v in r.items() if k != 'rows'} for state, r in result['landmarks'].items()}, indent=2))
