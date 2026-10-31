"""WR-02a native oriented-strip proof and bounded draw cost; not a Ribbon scene."""
from pathlib import Path
import argparse
import ctypes
import hashlib
import json
import math
import sys
import subprocess
import time

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
from PySide6.QtWidgets import QApplication
from core.ribbon_geometry import PathSample
from core.ribbon_geometry import MAX_PATH_SAMPLES
from core.ribbon_packet import MAX_RIBBONS, pack_ribbons
from core.ribbon_ring import RibbonRing
from core.settings.framed_camera import orthographic_matrix, perspective_matrix
from rendering.quick.scene3d.ribbon import RibbonPrimitive
from tools.labs.render_target import OffscreenRenderTarget


def fixture(count, knots):
    result = []
    for ribbon in range(count):
        samples, tangents = [], []
        for i in range(knots):
            t = i/(knots-1)*6
            phase = t+ribbon*.4
            samples.append(PathSample(1e9+i/60, (t-3, math.sin(phase)+(ribbon-(count-1)/2)*.4,
                                                       -10+.3*math.cos(phase)), .18, 1e5+t*.4))
            tangents.append((1., math.cos(phase), -.3*math.sin(phase)))
        result.append((samples, tangents, None))
    return pack_ribbons(result)


def ring_knot(ribbons, i):
    """Lattice step i of `fixture`'s shapes, continued indefinitely (knots stay where they were admitted)."""
    t = i*6/255
    positions = [(t-3, math.sin(t+r*.4)+(r-(ribbons-1)/2)*.4, -10+.3*math.cos(t+r*.4)) for r in range(ribbons)]
    return 1e9+i/60, positions, .18, [1e5+t*.4 for _ in range(ribbons)]


def scrolled(mvp, x):
    """Uniform scroll in the MVP, as a flowing consumer draws: newest knot stays at the fixture's right edge."""
    moved = list(mvp)
    moved[12] -= moved[0]*(x-3)
    return moved


def stats(values):
    return dict(median=float(np.median(values)), p90=float(np.percentile(values, 90)), max=float(np.max(values)))


def ring_costs(primitive, target, query, mvp, frames):
    """Separate the per-tick producer stages from upload/draw at the cap, steady state (full, evicting)."""
    ring = RibbonRing(MAX_RIBBONS)
    i = 0
    for i in range(MAX_PATH_SAMPLES + 64):
        ring.append(*ring_knot(MAX_RIBBONS, i))
    append, publish = [], []
    for _ in range(2000):  # includes eviction every knot and the rebases a long run meets
        i += 1
        knot = ring_knot(MAX_RIBBONS, i)
        start = time.perf_counter()
        ring.append(*knot)
        middle = time.perf_counter()
        ring.packet()
        append.append((middle-start)*1000)
        publish.append((time.perf_counter()-middle)*1000)
    gpu, cpu = [], []
    for _ in range(frames):
        i += 1
        knot = ring_knot(MAX_RIBBONS, i)
        ring.append(*knot)
        packet = ring.packet()
        target.bind()
        start = time.perf_counter()
        primitive.draw(packet, scrolled(mvp, knot[1][0][0]), timing_query=query)
        cpu.append((time.perf_counter()-start)*1000)
        gl.glFlush()
        elapsed = ctypes.c_uint64()
        glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(elapsed))
        gpu.append(elapsed.value/1e6)
    return dict(ribbons=MAX_RIBBONS, knots=len(ring), vertices_per_instance=packet.vertices,
                packet_bytes=len(packet.payload), append_ms=stats(append), publish_ms=stats(publish),
                cpu_submit_ms=stats(cpu), gpu_draw_ms=stats(gpu)), target.read_rgba()


def run(output, frames):
    if frames < 90 or frames > 600:
        raise ValueError('Warm measurement requires 90..600 frames')
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Refusing to overwrite evidence: {output}')
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    target, primitive = OffscreenRenderTarget(640, 384), RibbonPrimitive()
    query = None
    results = {}
    try:
        query = int(np.asarray(gl.glGenQueries(1)).reshape(-1)[0])
        target.bind()
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        driver = {key: gl.glGetString(enum).decode() for key, enum in (
            ('vendor', gl.GL_VENDOR), ('renderer', gl.GL_RENDERER), ('version', gl.GL_VERSION))}
        builds = {}
        for name, count, knots in (('one', 1, 32), ('maximum', 8, 256)):
            times = []
            for _ in range(3):
                start = time.perf_counter()
                packet = fixture(count, knots)
                times.append((time.perf_counter()-start)*1000)
            builds[name] = dict(median=float(np.median(times)), p90=float(np.percentile(times, 90)))
            for projection in ('orthographic', 'perspective'):
                mvp = orthographic_matrix((5, 3), .1, 100) if projection == 'orthographic' else perspective_matrix((.5, .3), .1, 100)
                for _ in range(8):
                    target.bind()
                    primitive.draw(packet, mvp)
                gpu, cpu = [], []
                for _ in range(frames):
                    target.bind()
                    start = time.perf_counter()
                    primitive.draw(packet, mvp, timing_query=query)
                    cpu.append((time.perf_counter()-start)*1000)
                    gl.glFlush()
                    elapsed = ctypes.c_uint64()
                    glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(elapsed))
                    gpu.append(elapsed.value/1e6)
                pixels = target.read_rgba()
                if not pixels[:, :, 3].any():
                    raise RuntimeError('Native strip produced no coverage')
                Image.fromarray(pixels).save(output/f'{name}_{projection}.png')
                results[f'{name}_{projection}'] = dict(instances=packet.instances, vertices_per_instance=packet.vertices,
                    packet_bytes=len(packet.payload), stream_bytes=primitive.stream_bytes,
                    gpu_draw_ms=dict(median=float(np.median(gpu)), p90=float(np.percentile(gpu, 90))),
                    cpu_submit_ms=dict(median=float(np.median(cpu)), p90=float(np.percentile(cpu, 90))))
        incremental = {}
        for projection in ('orthographic', 'perspective'):
            mvp = orthographic_matrix((5, 3), .1, 100) if projection == 'orthographic' else perspective_matrix((.5, .3), .1, 100)
            incremental[projection], pixels = ring_costs(primitive, target, query, mvp, frames)
            if not pixels[:, :, 3].any():
                raise RuntimeError('Incremental ring produced no coverage')
            Image.fromarray(pixels).save(output/f'ring_maximum_{projection}.png')
        receipt = dict(stage='WR-02 oriented geometry and incremental input path', driver=driver, frames=frames, viewport=[640, 384],
            results=results, full_reference_packet_build_ms=builds, incremental_ring=incremental,
            dynamic_cpu_budget_accepted=False, oit=False, defocus=False, scene_likeness_accepted=False,
            timing='TIME_ELAPSED around draw only; CPU submit includes bindings/upload/fences, excludes readback/wait/packing. '
                   'Ring append/publish are per admitted knot across all ribbons, measured full and evicting',
            producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        receipt['implementation_sha256'] = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
            'core/ribbon_packet.py', 'core/ribbon_ring.py', 'core/ribbon_frames.py', 'rendering/gl_programs/ribbon.py',
            'rendering/quick/scene3d/ribbon.py', 'rendering/quick/scene3d/stream.py')}
        receipt['source_revision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        receipt['tracked_diff_sha256'] = hashlib.sha256(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest()
        receipt['image_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.png')}
        (output/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(receipt, indent=2))
    finally:
        with target.current():
            if query is not None:
                gl.glDeleteQueries(1, [query])
            primitive.release()
        target.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--frames', type=int, default=90)
    args = parser.parse_args()
    run(args.output, args.frames)
