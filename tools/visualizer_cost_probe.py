"""Measure a Visualizer mode's render cost offscreen, through the production render host.

No window and no runtime: one offscreen GL 4.6 context, the Guided Setup preview snapshot of
the mode (its curated defaults plus fixture music), parameter overrides from the command line,
and ``--frames`` timed frames after a warm-up, measured the way ``tools/overhead_baseline.py``
measures (``tools/bench_stability.PairedBench``): each frame rendered three times right after a
fixed Crossfade control with the fastest repeat kept, passes gated on that control, and the
figures also given relative to it (``gpu_rel`` / ``cpu_rel``, in Crossfade frames), which hold
steady while GPU clocks and outside load move the milliseconds. The system conditions of the run
are printed with it. See ``Docs/Reference/Benchmarks.md``.

    python tools/visualizer_cost_probe.py extruded_spectrum --size 2560x1440
    python tools/visualizer_cost_probe.py shockwave_grid shockwave_grid_glow=0.8 --size 2560x1440

``--calls`` also counts Python-side GL calls per frame (by wrapping the ``OpenGL.GL``
functions the renderer modules call), at some cost to the timing; run it separately.
Parameter values parse as JSON when they can (``true``, ``0.5``), else stay strings.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Measure what production runs: per-call GL error checking off, as main.py sets it before
# OpenGL.GL is first imported (rendering/gl_error_policy.py).
from rendering.gl_error_policy import disable_per_call_gl_error_checking  # noqa: E402

if not disable_per_call_gl_error_checking():
    raise SystemExit("OpenGL.GL was imported before the probe could match production error checking")


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


def visualizer_case(gl, capture, host, snapshot, *, count_calls: bool = True):
    """A ``BenchCase`` drawing ``snapshot`` through ``host`` on ``capture``'s context: its warm-up,
    one render per sampled frame, and its deterministic per-frame GL and Python call counts."""
    import sys as _sys

    from tools.bench_stability import BenchCase

    width, height = capture.width, capture.height
    matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)

    def render():
        gl.glViewport(0, 0, width, height)
        gl.glClearColor(0.1, 0.12, 0.16, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                    logical_size=(float(width), float(height)), matrix_values=matrix)

    def warm():
        for _ in range(10):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
            render()

    def counts():
        if not count_calls:
            return {}
        counter, gl_counts, py_counts = _CallCounter(gl), [], []
        for _ in range(8):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
            calls = [0]

            def profile(_frame, event, _arg, calls=calls):
                if event in ("call", "c_call"):
                    calls[0] += 1

            counter.count = 0
            counter.install()
            _sys.setprofile(profile)
            try:
                render()
            finally:
                _sys.setprofile(None)
                counter.uninstall()
            gl_counts.append(counter.count)
            py_counts.append(calls[0])
        gl.glFinish()
        return {"gl_calls": statistics.median(gl_counts), "py_calls": statistics.median(py_counts)}

    return BenchCase(lambda _index: render, warm, counts)


def measure(mode: str, parameters: dict[str, object], size: tuple[int, int], frames: int = 60,
            calls: bool = False, passes: int = 3, max_rounds: int = 8) -> dict[str, object]:
    """``mode`` drawing a card filling ``size``: median/p90 CPU submit (wall and thread) and GPU ms,
    the same relative to the Crossfade control, and with ``calls`` its per-frame GL and Python call
    counts; ``load`` holds the run's admission and system conditions."""
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.instance() or QGuiApplication(sys.argv)
    from OpenGL import GL as gl

    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.bench_stability import PairedBench, crossfade_control
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.transition_contact_sheet import TransitionCapture

    width, height = size
    capture = TransitionCapture(width, height)
    host = QuickVisualizerRenderHost()
    try:
        snapshot = _build_spectrum_preview_snapshot(width=width, height=height, mode=mode)
        state = snapshot.logical.mode_state
        state = dataclasses.replace(state, parameters={**dict(state.parameters), **parameters})
        snapshot = dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))
        bench = PairedBench(gl, capture, crossfade_control(capture))
        case = visualizer_case(gl, capture, host, snapshot, count_calls=calls)
        result = dict(bench.measure("visualizer", {mode: case}, frames, passes, max_rounds)[mode])
        result["load"] = bench.load()
        return result
    finally:
        host.release_resources()
        capture.close()


class _CallCounter:
    """Counts calls to ``OpenGL.GL`` functions made through the renderer modules' ``gl`` name."""

    _MODULES = ("rendering.quick.visualizer.render_host", "rendering.quick.scene3d.target",
                "rendering.quick.scene3d.post", "rendering.quick.scene3d.stream",
                "rendering.quick.scene3d.resources", "rendering.quick.scene3d.environment",
                "rendering.quick.scene3d.uniforms",
                "rendering.quick.visualizer.implementations.extruded_spectrum",
                "rendering.quick.visualizer.implementations.shockwave_grid",
                "rendering.quick.visualizer.implementations.sphere_voxel",
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
        # The shared stream uses the raw multi-bind entry point, so count it
        # alongside wrapped GL calls rather than omitting its per-pass writes.
        from OpenGL.raw.GL.VERSION import GL_4_4

        self._raw_stream_bind = GL_4_4.glBindBuffersRange
        def bind_range(*args, **kwargs):
            counter.count += 1
            return self._raw_stream_bind(*args, **kwargs)
        GL_4_4.glBindBuffersRange = bind_range

    def uninstall(self) -> None:
        from OpenGL.raw.GL.VERSION import GL_4_4

        GL_4_4.glBindBuffersRange = self._raw_stream_bind
        for module in self._swapped:
            module.gl = self._gl
        self._swapped = []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode")
    parser.add_argument("parameters", nargs="*", help="key=value parameter overrides")
    parser.add_argument("--size", default="2560x1440")
    parser.add_argument("--frames", type=int, default=48)
    parser.add_argument("--passes", type=int, default=3, help="admitted passes to keep the best of")
    parser.add_argument("--calls", action="store_true", help="also count GL and Python calls per frame")
    args = parser.parse_args()
    width, height = (int(value) for value in args.size.lower().split("x"))
    result = measure(args.mode, _parameters(args.parameters), (width, height), args.frames, calls=args.calls,
                     passes=args.passes)
    load = result.pop("load")
    result.pop("env", None)
    print(" ".join(f"{key}={value:.3f}" for key, value in result.items() if isinstance(value, (int, float))))
    print(f"conditions: other processes' CPU {load.get('cpu_others_median', '?')}%, GPU busy "
          f"{load.get('gpu_util_median', '?')}%, GPU clock {load.get('gpu_clock_mhz_median', '?')} MHz, "
          f"{load.get('admitted', '?')}/{load.get('controls', '?')} passes admitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
