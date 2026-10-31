"""S3D-1 filament material cards: flowing-history ribbons through the Visualizer-shaped scene scope.

Not the Waveform Ribbon lab and not a scene: no hall, floor or particles. Three ribbons on one RibbonRing, fed by a
labelled synthetic head (no music), drawn with the production scope configuration (overlay, bloom, OIT, HDR)
and the WR-00 proposed Orthographic camera. Writes reference-aspect cards beside the mock's low/high crops plus a
wide card, and the material passes' warm GPU cost.

    .venv\\Scripts\\python.exe tools/labs/ribbon_material_probe.py --output .artifacts/evidence/ribbon_material/<new-run>
        [--cards .artifacts/evidence/waveform_ribbon/wr00_reference_projection]
"""
from __future__ import annotations

import argparse
import ctypes
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
if not disable_per_call_gl_error_checking():
    raise RuntimeError('GL imported before benchmark production policy')
from OpenGL import GL as gl
from OpenGL.raw.GL.VERSION.GL_3_3 import glGetQueryObjectui64v
import numpy as np
from PIL import Image

from core.ribbon_ring import RibbonRing
from core.settings.framed_camera import orthographic_matrix
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.ribbon import RibbonMaterial, RibbonPrimitive
from rendering.quick.scene3d.target import SceneTarget
from tools.labs.render_target import OffscreenRenderTarget

# WR-00 proposed camera (Lab Plan section 1.3), unverified until the WR-03 blockout.
HALF_HEIGHT, PITCH, PIVOT = 4.975, math.radians(15.), np.array((0., 2., 0.))
# Flowing history (Lab Plan section 4A): newest knot at the right, history drifts left.
FLOW_SPEED, HEAD_HZ, KNOT_HZ = 1.6, .4, 20.
PALETTE = (((.08, .62, 1., 1.), (.15, .42, 1., 1.)),   # electric cyan -> blue
           ((.2, .28, 1., 1.), (.42, .24, 1., 1.)),    # blue -> violet
           ((.62, .2, 1., 1.), (.95, .2, .85, 1.)))    # violet -> magenta
STATES = {  # labelled synthetic controls, sized from the WR-00 target table (body width ~3.5x, emission up)
    'low': dict(width=.11, width_pulse=.04, twist=.5, emission=.9, spread=.32, amplitude=.55),
    'high': dict(width=.42, width_pulse=.14, twist=1.6, emission=1.25, spread=.8, amplitude=.65),
}
BACKDROP = (.012, .016, .035, 1.)


def look_at(eye, target, up=(0., 1., 0.)):
    forward = (target-eye)/np.linalg.norm(target-eye)
    side = np.cross(forward, up)
    side /= np.linalg.norm(side)
    upward = np.cross(side, forward)
    view = np.identity(4)
    view[0, :3], view[1, :3], view[2, :3] = side, upward, -forward
    view[:3, 3] = -view[:3, :3] @ eye
    return view


def fill(ring, state, knots):
    """Admit `knots` lattice steps of the synthetic head; returns the newest knot time."""
    s = STATES[state]
    t = 0.
    for i in range(knots):
        t = i/KNOT_HZ
        positions, widths, twists, light = [], [], [], []
        for r in range(3):
            phase = 2*math.pi*HEAD_HZ*t + r*1.1
            beat = max(0., math.sin(2*math.pi*.9*t + r))**6  # bass pulses travel with the history
            positions.append((FLOW_SPEED*t, PIVOT[1] + s['amplitude']*math.sin(phase) + (r-1)*s['spread']*math.cos(.37*phase),
                              (r-1)*.5 + .35*math.cos(phase*.8)))
            widths.append(s['width'] + s['width_pulse']*beat)
            twists.append(s['twist']*math.sin(2*math.pi*.23*t + r*2.))
            light.append(s['emission']*(.8 + .4*beat))
        ring.append(t, positions, widths, twists, light)
    return t


def render(primitive, target, resources, scene, card, size, state, material, query=None):
    width, height = size
    ring = RibbonRing(3, colours=[c[0] for c in PALETTE], edge_colours=[c[1] for c in PALETTE], period=.5)
    now = fill(ring, state, 256)
    aspect = width/height
    head = HALF_HEIGHT*aspect + 1.5
    model = np.identity(4)
    model[0, 3] = head - FLOW_SPEED*now
    eye = PIVOT + 30*np.array((0., math.sin(PITCH), math.cos(PITCH)))
    view = look_at(eye, PIVOT) @ model
    projection = np.asarray(orthographic_matrix((HALF_HEIGHT*aspect, HALF_HEIGHT), .1, 80.)).reshape(4, 4, order='F')
    mvp = tuple((projection @ view).flatten(order='F'))
    view_values = tuple(view.flatten(order='F'))
    packet = ring.packet()
    target.bind(clear=(0., 0., 0., 0.))
    timings = {}
    # The Visualizer configuration (as Extruded Bubble): overlay with bloom, OIT and HDR at exposure 1.
    with scene.scope(card, 4, resources, overlay=1.0, bloom=.55, oit=True, hdr=1.0):
        gl.glViewport(0, 0, width, height)
        gl.glClearBufferfv(gl.GL_COLOR, 0, BACKDROP)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        with scene.transparent_writes(card, resources):
            timings['body'] = timed(query, lambda: primitive.draw(packet, mvp, shading='body', view=view_values,
                                                                  material=material, timing_query=query))
        with scene.emission_writes():
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
            gl.glDepthMask(gl.GL_FALSE)
            timings['light'] = timed(query, lambda: primitive.draw(packet, mvp, shading='light', view=view_values,
                                                                   material=material, timing_query=query))
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisablei(gl.GL_BLEND, 0)
    return target.read_rgba(), timings


def timed(query, draw):
    draw()
    if query is None:
        return None
    gl.glFlush()
    elapsed = ctypes.c_uint64()
    glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(elapsed))
    return elapsed.value/1e6


def card_frame(render_target, width, height):
    matrix = (2/width, 0, 0, 0, 0, -2/height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
    return SimpleNamespace(viewport=(0, 0, width, height), logical_size=(float(width), float(height)),
                           matrix_values=matrix, quad_vao=render_target.vao)


def run(output: Path, cards: Path | None, frames: int):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Refusing to overwrite evidence: {output}')
    output.mkdir(parents=True, exist_ok=True)
    material = RibbonMaterial()
    sizes = {'reference': (640, 709), 'wide': (960, 540)}
    render_target = OffscreenRenderTarget(*sizes['reference'])
    primitive, resources, scene = RibbonPrimitive(), MeshResources('ribbon material probe'), SceneTarget('ribbon material probe')
    query = None
    images, cost = {}, {}
    try:
        query = int(np.asarray(gl.glGenQueries(1)).reshape(-1)[0])
        for kind, size in sizes.items():
            render_target.resize(*size)
            card = card_frame(render_target, *size)
            for state in STATES:
                pixels, _ = render(primitive, render_target, resources, scene, card, size, state, material)
                if not pixels[:, :, :3].any():
                    raise RuntimeError('Material produced no light')
                images[f'{kind}_{state}'] = Image.fromarray(pixels[::-1].copy())
                images[f'{kind}_{state}'].save(output/f'{kind}_{state}.png')
        card = card_frame(render_target, *sizes['wide'])
        for state in STATES:
            samples = {'body': [], 'light': []}
            for i in range(frames + 8):
                _, timings = render(primitive, render_target, resources, scene, card, sizes['wide'], state, material, query)
                if i >= 8:
                    for key in samples:
                        samples[key].append(timings[key])
            cost[state] = {key: dict(median=float(np.median(v)), p90=float(np.percentile(v, 90))) for key, v in samples.items()}
        if cards is not None:
            sheet = Image.new('RGB', (640*2 + 8, 709*2 + 8))
            for row, state in enumerate(STATES):
                sheet.paste(Image.open(cards/f'{state}.png').convert('RGB').resize((640, 709)), (0, row*717))
                sheet.paste(images[f'reference_{state}'].convert('RGB'), (648, row*717))
            sheet.save(output/'mock_vs_material.png')
        receipt = dict(stage='S3D-1 filament material, no scene', material=material.__dict__, states=STATES,
                       camera=dict(half_height=HALF_HEIGHT, pitch_degrees=15., pivot=PIVOT.tolist(), status='WR-00 proposal'),
                       flow=dict(speed=FLOW_SPEED, head_hz=HEAD_HZ, knot_hz=KNOT_HZ), scope='overlay 1, bloom .55, OIT, HDR 1, 4x MSAA',
                       driver=render_target.driver, warm_frames=frames, gpu_ms_wide=cost,
                       producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
        (output/'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        return receipt
    finally:
        with render_target.current():
            if query is not None:
                gl.glDeleteQueries(1, [query])
            primitive.release()
            scene.release()
            resources.release_resources()
        render_target.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cards', type=Path)
    parser.add_argument('--frames', type=int, default=90)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.cards, args.frames)['gpu_ms_wide'], indent=2))
