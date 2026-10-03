"""Measure a Visualizer mode's render cost offscreen, through the production render host.

No window and no runtime: one offscreen GL 4.6 context, the Guided Setup preview snapshot of
the mode (its curated defaults plus fixture music), parameter overrides from the command line,
and ``--frames`` timed frames after a warm-up. Each frame records CPU submit (the render
thread's Python + GL call time, which holds the GIL) and GPU time (``GL_TIME_ELAPSED``),
flushing per frame as presentation does; the report gives median and p90 of both.

    python tools/visualizer_cost_probe.py extruded_spectrum --size 2560x1440
    python tools/visualizer_cost_probe.py shockwave_grid shockwave_grid_glow=0.8 --size 2560x1440

``--calls`` also counts Python-side GL calls per frame (by wrapping the ``OpenGL.GL``
functions the renderer modules call), at some cost to the timing; run it separately.
Parameter values parse as JSON when they can (``true``, ``0.5``), else stay strings.
"""
from __future__ import annotations

import argparse
import ctypes
import dataclasses
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parameters(pairs: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for pair in pairs:
        key, _, raw = pair.partition("=")
        try:
            parsed[key] = json.loads(raw)
        except json.JSONDecodeError:
            parsed[key] = raw
    return parsed


def _p90(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]


def measure(mode: str, parameters: dict[str, object], size: tuple[int, int], frames: int = 60,
            warm: int = 10, calls: bool = False) -> dict[str, float]:
    """Median/p90 CPU submit and GPU ms of ``mode`` drawing a card filling ``size``."""
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.instance() or QGuiApplication(sys.argv)
    from OpenGL import GL as gl

    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.transition_contact_sheet import TransitionCapture

    width, height = size
    capture = TransitionCapture(width, height)
    snapshot = _build_spectrum_preview_snapshot(width=width, height=height, mode=mode)
    state = snapshot.logical.mode_state
    state = dataclasses.replace(state, parameters={**dict(state.parameters), **parameters})
    snapshot = dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))
    matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
    host = QuickVisualizerRenderHost()
    counter = _CallCounter(gl) if calls else None

    def draw() -> float:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glViewport(0, 0, width, height)
        gl.glClearColor(0.1, 0.12, 0.16, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        start = perf_counter()
        host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                    logical_size=(float(width), float(height)), matrix_values=matrix)
        return (perf_counter() - start) * 1e3

    try:
        for _ in range(warm):
            draw()
            gl.glFinish()
        cpu, queries, counts = [], [], []
        for _ in range(frames):
            query = int(gl.glGenQueries(1)[0])
            queries.append(query)
            gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
            if counter is not None:
                counter.count = 0
                counter.install()
            cpu.append(draw())
            if counter is not None:
                counter.uninstall()
                counts.append(counter.count)
            gl.glEndQuery(gl.GL_TIME_ELAPSED)
            gl.glFlush()
        gpu = []
        for query in queries:
            value = ctypes.c_uint64()
            gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
            gpu.append(value.value / 1e6)
        gl.glDeleteQueries(len(queries), queries)
        result = {"cpu_median": statistics.median(cpu), "cpu_p90": _p90(cpu),
                  "gpu_median": statistics.median(gpu), "gpu_p90": _p90(gpu)}
        if counts:
            result["gl_calls"] = statistics.median(counts)
        return result
    finally:
        host.release_resources()
        capture.close()


class _CallCounter:
    """Counts calls to ``OpenGL.GL`` functions made through the renderer modules' ``gl`` name."""

    _MODULES = ("rendering.quick.visualizer.render_host", "rendering.quick.scene3d.target",
                "rendering.quick.scene3d.post", "rendering.quick.scene3d.stream",
                "rendering.quick.scene3d.resources", "rendering.quick.scene3d.environment",
                "rendering.quick.visualizer.implementations.extruded_spectrum",
                "rendering.quick.visualizer.implementations.shockwave_grid",
                "rendering.quick.visualizer.gl_state", "rendering.quick.gl_query")

    def __init__(self, gl) -> None:
        self.count = 0
        self._gl = gl
        self._proxy = None

    def install(self) -> None:
        import importlib

        counter, real = self, self._gl

        class _Proxy:
            def __getattr__(self, name):
                value = getattr(real, name)
                if callable(value) and name.startswith("gl"):
                    def call(*args, **kwargs):
                        counter.count += 1
                        return value(*args, **kwargs)
                    return call
                return value

        self._proxy = _Proxy()
        self._swapped = []
        for name in self._MODULES:
            module = importlib.import_module(name)
            if getattr(module, "gl", None) is real:
                module.gl = self._proxy
                self._swapped.append(module)

    def uninstall(self) -> None:
        for module in self._swapped:
            module.gl = self._gl
        self._swapped = []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode")
    parser.add_argument("parameters", nargs="*", help="key=value parameter overrides")
    parser.add_argument("--size", default="2560x1440")
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--calls", action="store_true", help="count GL calls per frame (separate run)")
    args = parser.parse_args()
    width, height = (int(value) for value in args.size.lower().split("x"))
    result = measure(args.mode, _parameters(args.parameters), (width, height), args.frames, calls=args.calls)
    print(" ".join(f"{key}={value:.3f}" for key, value in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
