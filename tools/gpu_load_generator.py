"""Game-like competing GPU load for headless benchmarks (its own process and offscreen GL context).

    .venv/Scripts/python tools/gpu_load_generator.py --seconds 120 --fps 75 --packet-ms 8
    .venv/Scripts/python tools/gpu_load_generator.py --seconds 120 --busy 60          # calibrates the packet

Each "frame" draws one full-screen 4K fragment-heavy packet, finishes it, and sleeps to the next frame deadline, like
a game at ``--fps`` whose GPU work takes ``--packet-ms``; ``--busy`` instead calibrates the packet to that share of
the GPU at ``--fps``. A ~60% game-like load is the reference case for SRPSS (operator, 2026-10-31); 90%+ only for
diagnosis. The process stops itself at ``--seconds`` (a hard deadline: it can never outlive a benchmark) and prints
its PID, achieved frame rate and packet time.

Measure SRPSS against it from the benchmark's own process; record ``tools/bench_stability.SystemSampler`` conditions
with the result. Never leave one running: check for strays (``*gpu_load_generator*``) before an idle measurement.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_VERTEX = """#version 460 core
out vec2 uv;
void main() { vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2); uv = p; gl_Position = vec4(p * 2.0 - 1.0, 0, 1); }
"""
_FRAGMENT = """#version 460 core
in vec2 uv; out vec4 colour; uniform int uIterations; uniform float uTime;
void main() {
    vec2 z = uv * 2.0 - 1.0; float a = 0.0;
    for (int i = 0; i < uIterations; ++i) {
        z = vec2(z.x * z.x - z.y * z.y, 2.0 * z.x * z.y) + vec2(sin(uTime + a), cos(a)) * 0.3;
        a += length(z) * 0.001;
    }
    colour = vec4(fract(a), fract(a * 3.0), z.x, 1.0);
}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--fps", type=float, default=75.0)
    parser.add_argument("--packet-ms", type=float, default=8.0)
    parser.add_argument("--busy", type=float, help="calibrate the packet to this GPU share (percent) at --fps")
    args = parser.parse_args()
    deadline = time.monotonic() + args.seconds
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    from OpenGL import GL as gl
    from rendering.quick.render.gl_resources import compile_program
    from tools.labs.render_target import OffscreenRenderTarget

    width, height = 3840, 2160
    target = OffscreenRenderTarget(width, height, label="gpu load")
    program = compile_program(_VERTEX, _FRAGMENT, label="gpu load")
    gl.glUseProgram(program)
    gl.glBindVertexArray(gl.glGenVertexArrays(1))
    iterations_at, time_at = gl.glGetUniformLocation(program, "uIterations"), gl.glGetUniformLocation(program, "uTime")
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
    gl.glViewport(0, 0, width, height)

    def packet(iterations: int) -> float:
        gl.glUniform1i(iterations_at, iterations)
        gl.glUniform1f(time_at, time.monotonic() % 100.0)
        start = time.perf_counter()
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glFinish()
        return (time.perf_counter() - start) * 1000.0

    packet_ms = args.packet_ms if args.busy is None else args.busy / 100.0 * 1000.0 / args.fps
    iterations = 64
    for _ in range(8):                       # calibrate iterations to the packet time
        measured = sorted(packet(iterations) for _ in range(5))[2]
        iterations = max(1, int(iterations * packet_ms / max(measured, 0.05)))
    print(f"gpu load pid {os.getpid()}: {args.fps:.0f} fps, packet {packet_ms:.1f} ms ({iterations} iterations)",
          flush=True)
    period, frames, spent = 1.0 / args.fps, 0, 0.0
    next_frame = time.monotonic()
    while time.monotonic() < deadline:
        spent += packet(iterations)
        frames += 1
        next_frame += period
        delay = next_frame - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_frame = time.monotonic()
    elapsed = args.seconds
    print(f"gpu load done: {frames / elapsed:.1f} fps achieved, packet median ~{spent / max(frames, 1):.2f} ms",
          flush=True)
    target.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
