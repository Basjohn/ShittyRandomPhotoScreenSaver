"""Run the real MC saver with per-phase timers on Extruded Bubble's render thread and logical publish.

    .venv/Scripts/python tools/eb_live_phases.py --out logs/eb_live_phases.json -- --perf --frame-trace --exit-after 120 /s

Starts ``main_mc.py`` in this process (MC never takes over both displays) with tool-only wrappers around EB's
render stages (probe, shafts, near layer, background capture, drift solver, uniforms, instance packing), every
``gl_query`` / host fence state read, and the logical ``_publish_logical_state``; at exit it writes median/p90/p99
milliseconds per frame (and per tick) plus solver restarts to ``--out``. The first 200 frames are dropped (startup).

Use it under the real competing load the question is about, with ``SRPSS_FORCE_LOG_DIR`` pointing at a scratch
folder so the operator's own logs stay untouched. Offline harnesses (``eb_gpu_stage_cost``, ``eb_logical_cost_probe``)
cannot see Qt's scene, the swap chain, the real driver queue or the other displays; this can.
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import runpy
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_local = threading.local()
_frames: list[dict] = []
_ticks: list[float] = []
_restarts: list = []


def _wrap(owner, attr, label):
    original = getattr(owner, attr)

    def timed(*args, **kwargs):
        current = getattr(_local, "frame", None)
        start = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            if current is not None:
                current[label] = current.get(label, 0.0) + (time.perf_counter() - start) * 1000.0
    setattr(owner, attr, timed)


def production_startup() -> None:
    """``main.py``'s process preamble, before anything here imports numpy, OpenGL or Qt.

    The wrappers below import OpenGL; done first, they would leave PyOpenGL's per-call error checking on (45-60% of
    render-thread CPU, ``rendering/gl_error_policy.py``) and measure a slower renderer than the product runs.
    """
    from core.native_threads import configure_native_thread_pools
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from rendering.quick.bootstrap import configure_quick_environment

    configure_native_thread_pools()
    if not disable_per_call_gl_error_checking():
        raise RuntimeError("OpenGL.GL was imported before the production GL error policy")
    configure_quick_environment()


def _install() -> None:
    from rendering.quick import gl_query
    from rendering.quick.scene3d import defocus, probe, target
    from rendering.quick.visualizer import gl_state
    from rendering.quick.visualizer.implementations import extruded_bubble as eb
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as solver
    from widgets.spotify_visualizer import tick_pipeline

    render = eb.QuickExtrudedBubbleRenderer.render

    def framed(self, frame):
        _local.frame = {}
        start = time.perf_counter()
        try:
            return render(self, frame)
        finally:
            _local.frame["eb_render"] = (time.perf_counter() - start) * 1000.0
            _frames.append(_local.frame)
            _local.frame = None
    eb.QuickExtrudedBubbleRenderer.render = framed
    for owner, attr, label in ((probe.SceneProbe, "capture", "probe"), (defocus.DefocusLayer, "begin", "near_begin"),
                               (defocus.DefocusLayer, "end", "near_end"),
                               (defocus.DefocusLayer, "composite", "near_composite"),
                               (target.SceneTarget, "background", "target_background"),
                               (solver.DriftSolver, "update", "drift_solver"), (eb._Uniforms, "set", "uniforms"),
                               (eb.QuickExtrudedBubbleRenderer, "_draw_shafts", "shafts"),
                               (eb, "bubble_instances", "pack_bubbles"), (eb, "wake_instances", "pack_wakes")):
        _wrap(owner, attr, label)
    for name in [n for n in dir(gl_query) if n.startswith(("get_", "is_enabled"))]:
        _wrap(gl_query, name, "state_reads")
    for name in ("_int_state", "_int_states", "_bool_state", "_bool_states", "_is_enabled"):
        if hasattr(gl_state, name):
            _wrap(gl_state, name, "host_state_reads")
    dispatch = solver.DriftSolver._dispatch

    def logged_dispatch(self, resources, name, state, offset, upload, pending, *, fresh, old_geometry=0,
                        old_carry=0.0):
        if fresh or old_geometry:
            _restarts.append((time.time(), name, int(state.serial), bool(fresh), bool(old_geometry)))
        return dispatch(self, resources, name, state, offset, upload, pending, fresh=fresh,
                        old_geometry=old_geometry, old_carry=old_carry)
    solver.DriftSolver._dispatch = logged_dispatch
    publish = tick_pipeline._publish_logical_state

    def ticked(*args, **kwargs):
        start = time.perf_counter()
        try:
            return publish(*args, **kwargs)
        finally:
            _ticks.append((time.perf_counter() - start) * 1000.0)
    tick_pipeline._publish_logical_state = ticked


def _summary() -> dict:
    rows = _frames[200:]
    summary: dict = {"frames": len(rows), "ticks": len(_ticks), "restarts": _restarts}
    for label in sorted({key for row in rows for key in row}):
        values = sorted(row.get(label, 0.0) for row in rows)
        summary[label] = {"median": round(statistics.median(values), 3),
                          "p90": round(values[int(0.9 * (len(values) - 1))], 3),
                          "p99": round(values[int(0.99 * (len(values) - 1))], 3)}
    ticks = sorted(_ticks[200:])
    if ticks:
        summary["logical_publish"] = {"median": round(statistics.median(ticks), 3),
                                      "p90": round(ticks[int(0.9 * (len(ticks) - 1))], 3)}
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("mc_args", nargs=argparse.REMAINDER, help="arguments for main_mc.py after --")
    args = parser.parse_args()
    mc_args = args.mc_args[1:] if args.mc_args[:1] == ["--"] else args.mc_args
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    sys.argv = [str(ROOT / "main_mc.py"), *mc_args]
    production_startup()
    _install()
    atexit.register(lambda: args.out.write_text(json.dumps(_summary(), indent=1), encoding="utf-8"))
    runpy.run_path(str(ROOT / "main_mc.py"), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
