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
from core.ribbon_packet import pack_ribbons
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
        receipt = dict(stage='WR-02a oriented geometry only', driver=driver, frames=frames, viewport=[640, 384],
            results=results, full_reference_packet_build_ms=builds, dynamic_cpu_budget_accepted=False, oit=False, defocus=False, scene_likeness_accepted=False,
            timing='TIME_ELAPSED around draw only; CPU includes bindings/upload/fences, excludes readback/wait/packing',
            producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        receipt['implementation_sha256'] = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
            'core/ribbon_packet.py', 'core/ribbon_frames.py', 'rendering/gl_programs/ribbon.py',
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
