"""Game-like competing load for SRPSS benchmarks: GPU frames, CPU worker threads and memory traffic, in its own processes.

    .venv/Scripts/python tools/gpu_load_generator.py --seconds 180 --profile game60     # the reference case
    .venv/Scripts/python tools/gpu_load_generator.py --seconds 180 --profile game85     # heavier, diagnosis only
    .venv/Scripts/python tools/gpu_load_generator.py --seconds 120 --gpu 60 --cpu 55     # custom shares
    .venv/Scripts/python tools/gpu_load_generator.py --seconds 120 --busy 60             # legacy: one packet a frame

A real game is not one GPU packet a frame. The operator's reference load (Borderlands 4, 2026-10-31) held the GPU at
60-68% while using ~57% of all 24 logical cores across 168 threads with an 8.4 GB working set; SRPSS's pure-Python
logical and render threads feel that CPU and memory pressure first (their GIL-held work slows and stretches), long
before GPU time limits them. So the ``game`` profiles model:

* **GPU:** frames of several passes (``--passes`` draws over two render targets plus a streamed buffer upload), kept
  two frames in flight with fences like a swap chain, paced to ``--fps``. The per-pass cost is calibrated against
  *measured* whole-GPU utilisation (``nvidia-smi``) to ``--gpu`` percent, not against packet time, so clock changes
  and the driver's own scheduling are included.
* **CPU:** frame-synced worker processes, each doing a burst of mixed work every frame (pure compute plus streaming
  copies over its own buffer, which loads memory bandwidth and caches the way game threads do), sized to ``--cpu``
  percent of all logical cores.

The process prints its PID, then ``ready`` once calibrated (start the measured run after that line), then the achieved
GPU and CPU shares at the end. It stops itself at ``--seconds`` (a hard deadline: it can never outlive a benchmark).
Measure SRPSS from its own process; record ``tools/bench_stability.SystemSampler`` conditions with every result. Never
leave one running: check for strays (``*gpu_load_generator*``) and stop them by PID.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROFILES = {
    # name: (fps, gpu %, cpu % of all logical cores, passes)
    "game60": (90.0, 60.0, 55.0, 24),
    "game85": (120.0, 85.0, 75.0, 32),
}

_VERTEX = """#version 460 core
out vec2 uv;
void main() { vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2); uv = p; gl_Position = vec4(p * 2.0 - 1.0, 0, 1); }
"""
_FRAGMENT = """#version 460 core
in vec2 uv; out vec4 colour; uniform int uIterations; uniform float uTime; uniform sampler2D uPrevious;
void main() {
    vec2 z = uv * 2.0 - 1.0; float a = texture(uPrevious, uv).r * 0.01;
    for (int i = 0; i < uIterations; ++i) {
        z = vec2(z.x * z.x - z.y * z.y, 2.0 * z.x * z.y) + vec2(sin(uTime + a), cos(a)) * 0.3;
        a += length(z) * 0.001;
    }
    colour = vec4(fract(a), fract(a * 3.0), z.x, 1.0);
}
"""


def _cpu_worker(deadline: float, fps: float, duty: float, buffer_mb: int) -> None:
    """One game thread: every frame a burst of compute and streaming copies, then idle until the next frame."""
    import numpy as np

    source = np.ones(buffer_mb * 1024 * 1024 // 8)
    target = np.empty_like(source)
    chunk = len(source) // 16
    period, offset, next_frame = 1.0 / fps, 0, time.monotonic()
    while next_frame < deadline:
        burst_end = time.perf_counter() + period * duty
        while time.perf_counter() < burst_end:
            np.copyto(target[offset:offset + chunk], source[offset:offset + chunk])   # memory bandwidth
            offset = (offset + chunk) % (len(source) - chunk)
            total = 0
            for i in range(2000):                                                     # core compute
                total += i * i
        next_frame += period
        delay = next_frame - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_frame = time.monotonic()


class _GpuSampler:
    """Whole-GPU utilisation from nvidia-smi, sampled once a second on a daemon thread."""

    def __init__(self) -> None:
        self.samples: list[float] = []
        self._smi = shutil.which("nvidia-smi")
        self._process = None
        if self._smi:
            self._process = subprocess.Popen([self._smi, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits",
                                              "-lms", "1000"], stdout=subprocess.PIPE, text=True)
            threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for line in self._process.stdout:
            try:
                self.samples.append(float(line.strip()))
            except ValueError:
                pass

    def mean_since(self, index: int) -> float | None:
        window = self.samples[index:]
        return sum(window) / len(window) if window else None

    def close(self) -> None:
        if self._process is not None:
            self._process.terminate()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), help="a game-like load (fps, GPU, CPU, passes)")
    parser.add_argument("--fps", type=float)
    parser.add_argument("--gpu", type=float, help="target whole-GPU utilisation, percent (calibrated by measurement)")
    parser.add_argument("--cpu", type=float, default=None, help="share of all logical cores kept busy, percent")
    parser.add_argument("--passes", type=int, help="draws per frame")
    parser.add_argument("--buffer-mb", type=int, default=64, help="each CPU worker's streaming buffer")
    parser.add_argument("--busy", type=float, help="legacy: one packet a frame calibrated to this GPU share by time")
    parser.add_argument("--packet-ms", type=float, default=8.0, help="legacy: one packet a frame of this GPU time")
    args = parser.parse_args()
    fps, gpu, cpu, passes = PROFILES.get(args.profile, (75.0, None, 0.0, 1))
    fps = args.fps or fps
    gpu = args.gpu if args.gpu is not None else gpu
    cpu = args.cpu if args.cpu is not None else cpu
    legacy = gpu is None
    passes = args.passes or (passes if legacy or args.profile else 24)
    deadline = time.monotonic() + args.seconds
    workers = []
    cores = os.cpu_count() or 1
    if cpu > 0:
        import multiprocessing
        duty = 0.8
        count = max(1, round(cores * min(cpu, 100.0) / 100.0 / duty))
        workers = [multiprocessing.Process(target=_cpu_worker, args=(deadline, fps, duty, args.buffer_mb), daemon=True)
                   for _ in range(count)]
        for worker in workers:
            worker.start()
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    import numpy as np
    from OpenGL import GL as gl
    from rendering.quick.render.gl_resources import compile_program
    from tools.labs.render_target import OffscreenRenderTarget

    width, height = 3840, 2160
    targets = [OffscreenRenderTarget(width, height, label="load a"),
               OffscreenRenderTarget(width // 2, height // 2, label="load b")]
    program = compile_program(_VERTEX, _FRAGMENT, label="gpu load")
    gl.glUseProgram(program)
    gl.glBindVertexArray(gl.glGenVertexArrays(1))
    iterations_at, time_at = gl.glGetUniformLocation(program, "uIterations"), gl.glGetUniformLocation(program, "uTime")
    gl.glUniform1i(gl.glGetUniformLocation(program, "uPrevious"), 0)
    stream = gl.glGenBuffers(1)
    upload = np.zeros(16 * 1024 * 1024 // 4, dtype=np.float32)          # 16 MB streamed every frame
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, stream)
    gl.glBufferData(gl.GL_ARRAY_BUFFER, upload.nbytes, None, gl.GL_STREAM_DRAW)
    fences: list = []

    def frame(iterations: int) -> None:
        gl.glUniform1f(time_at, time.monotonic() % 100.0)
        gl.glUniform1i(iterations_at, iterations)
        gl.glBufferSubData(gl.GL_ARRAY_BUFFER, 0, upload.nbytes, upload)
        for index in range(passes):
            target = targets[index % 2]
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            gl.glViewport(0, 0, target.width, target.height)
            gl.glBindTexture(gl.GL_TEXTURE_2D, targets[(index + 1) % 2].color_texture)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        fences.append(gl.glFenceSync(gl.GL_SYNC_GPU_COMMANDS_COMPLETE, 0))
        gl.glFlush()
        while len(fences) > 2:                                          # two frames in flight, like a swap chain
            fence = fences.pop(0)
            gl.glClientWaitSync(fence, gl.GL_SYNC_FLUSH_COMMANDS_BIT, 1_000_000_000)
            gl.glDeleteSync(fence)

    period = 1.0 / fps

    def run_until(stop: float, iterations: int) -> int:
        frames, next_frame = 0, time.monotonic()
        while time.monotonic() < min(stop, deadline):
            frame(iterations)
            frames += 1
            next_frame += period
            delay = next_frame - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                next_frame = time.monotonic()
        return frames

    if legacy:
        packet_ms = args.packet_ms if args.busy is None else args.busy / 100.0 * 1000.0 / fps
        iterations = 64
        for _ in range(8):
            start = time.perf_counter()
            for _ in range(5):
                frame(iterations)
            gl.glFinish()
            measured = (time.perf_counter() - start) * 1000.0 / 5
            iterations = max(1, int(iterations * packet_ms / max(measured, 0.05)))
        print(f"gpu load pid {os.getpid()}: legacy {fps:.0f} fps, packet {packet_ms:.1f} ms; ready", flush=True)
        sampler = None
    else:
        sampler = _GpuSampler()
        iterations = 16
        # ~2 s steps toward the measured target, at most a quarter of the run (and 20 s).
        for _ in range(max(1, min(10, int(args.seconds / 8.0)))):
            mark = len(sampler.samples)
            run_until(time.monotonic() + 2.0, iterations)
            measured = sampler.mean_since(mark + 1)
            if measured is None:
                break
            iterations = max(1, int(iterations * min(4.0, max(0.25, gpu / max(measured, 1.0)))))
            if abs(measured - gpu) < 3.0:
                break
        print(f"gpu load pid {os.getpid()}: {fps:.0f} fps, {passes} passes, {iterations} iterations, "
              f"{len(workers)} cpu workers; ready", flush=True)
    mark = len(sampler.samples) if sampler else 0
    started = time.monotonic()
    frames = run_until(deadline, iterations)
    elapsed = max(time.monotonic() - started, 1e-6)
    achieved = sampler.mean_since(mark) if sampler else None
    print(f"gpu load done: {frames / elapsed:.1f} fps achieved"
          + (f", GPU {achieved:.0f}% mean while measured" if achieved is not None else ""), flush=True)
    if sampler:
        sampler.close()
    for target in targets:
        target.close()
    for worker in workers:
        worker.join(timeout=2)
        if worker.is_alive():
            worker.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
