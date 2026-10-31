"""Extruded Bubble GPU cost per render stage, by skip variants (headless, offscreen, production render host).

    .venv/Scripts/python tools/eb_gpu_stage_cost.py --clip logs/visualizer_recordings/heavy1.jsonl --preset 1
    .venv/Scripts/python tools/eb_gpu_stage_cost.py --clip <clip> --preset 1 --size 1662x888 --frames 60

Stage timers inside a frame misattribute: a ``GL_TIME_ELAPSED`` begin is taken when the command reaches the GPU
front end, while the previous stage's fragments are still draining, so the next stage absorbs them (the probe's
prefilter once showed up as 2.3 ms of "shafts"). This tool times only whole frames (one ``GL_TIME_ELAPSED`` per
frame, flushed and finished per frame) and removes one stage at a time: a stage's cost is the frame it leaves
behind, ``full - skipped``. Variants run round-robin in one process (outside load and clock changes spoil one pass,
not one variant). The pictures of skipped variants are wrong by design; this measures cost, never looks.

Stages: probe capture + prefilter (and each of its prefilter and glint-proxy parts), shafts (march + blurs), the near layer (begin, draw, end, composite), procedural
material draws (beads/snow/fizz and specks), the drift compute solver, and the scene background capture.
"""
from __future__ import annotations

import argparse
import ctypes
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rendering.gl_error_policy import disable_per_call_gl_error_checking  # noqa: E402

MODE = "extruded_bubble"


def _skips():
    from rendering.quick.scene3d import defocus, probe, target
    from rendering.quick.visualizer.implementations import extruded_bubble as eb
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as solver
    noop = lambda *a, **k: None  # noqa: E731
    _capture_probe = eb.QuickExtrudedBubbleRenderer._capture_probe
    return {
        "probe": [(probe.SceneProbe, "capture", noop)],
        "probe prefilter": [(probe.SceneProbe, "_prefilter", noop)],
        "probe glint proxies": [(eb.QuickExtrudedBubbleRenderer, "_capture_probe",
                                 lambda self, probe_, programs, proxy_count, quad_vao:
                                 _capture_probe(self, probe_, programs, 0, quad_vao))],
        "shafts": [(eb.QuickExtrudedBubbleRenderer, "_draw_shafts", noop)],
        "near layer": [(defocus.DefocusLayer, "begin", noop), (defocus.DefocusLayer, "end", noop),
                       (defocus.DefocusLayer, "composite", noop)],
        "near composite": [(defocus.DefocusLayer, "composite", noop)],
        "near mipmaps": [(defocus.DefocusLayer, "end", noop)],
        "material draws": [(eb.QuickExtrudedBubbleRenderer, "_draw_material_instances", noop)],
        "drift compute": [(solver.DriftSolver, "_dispatch", noop)],
        "background capture": [(target.SceneTarget, "background",
                                lambda self, frame, resources: (0, 0))],
    }


def measure(clip: Path, *, preset: int, size: tuple[int, int], frames: int, rounds: int) -> dict:
    import numpy as np
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    from OpenGL import GL as gl
    from OpenGL.raw.GL.VERSION import GL_3_3 as raw33
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.bench_stability import SystemSampler, summarise_environment
    from tools.eb_logical_cost_probe import _load_clip
    from tools.labs.render_target import OffscreenRenderTarget
    from tools.visualizer_replay.driver import replay_clip

    width, height = size
    settings = resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": preset - 1},
                                                     mode=MODE).resolved_config
    wanted = range(900, 900 + 3 * frames, 3)
    snaps = replay_clip(_load_clip(clip, 0.0, (900 + 3 * frames) / 90 + 1), MODE, settings=settings,
                        snapshots_at=wanted)["snapshots"]
    snapshots = [snaps[k] for k in sorted(snaps)]
    target = OffscreenRenderTarget(width, height, label="eb stage cost")
    host = QuickVisualizerRenderHost()
    matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
    query = int(np.asarray(gl.glGenQueries(1)).ravel()[0])
    skips = _skips()
    variants = ["full", *skips]
    results: dict[str, list[float]] = {name: [] for name in variants}
    sampler = SystemSampler()
    conditions = [sampler.sample()]

    def frame(snapshot) -> float:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        gl.glViewport(0, 0, width, height)
        gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
        host.render(snapshot=snapshot, viewport=(0, 0, width, height), logical_size=(float(width), float(height)),
                    matrix_values=matrix)
        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        gl.glFlush()
        gl.glFinish()
        value = ctypes.c_uint64()
        raw33.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
        return value.value / 1e6

    try:
        for snapshot in snapshots[:20]:
            frame(snapshot)                      # warm every program and target
        for _ in range(rounds):
            for name in variants:
                saved = [(owner, attr, getattr(owner, attr)) for owner, attr, _ in skips.get(name, ())]
                for owner, attr, replacement in skips.get(name, ()):
                    setattr(owner, attr, replacement)
                try:
                    results[name].extend(frame(s) for s in snapshots)
                finally:
                    for owner, attr, original in saved:
                        setattr(owner, attr, original)
            conditions.append(sampler.sample())
    finally:
        host.release_resources()
        target.close()
    full = statistics.median(results["full"])
    return {"size": size, "preset": preset, "full_ms": full,
            "full_p90_ms": sorted(results["full"])[int(0.9 * len(results["full"]))],
            "stage_ms": {name: full - statistics.median(values) for name, values in results.items() if name != "full"},
            "conditions": summarise_environment(conditions)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--preset", type=int, default=1)
    parser.add_argument("--size", default="1662x888", help="card size in device pixels")
    parser.add_argument("--frames", type=int, default=60, help="distinct snapshots per round")
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    if not disable_per_call_gl_error_checking():
        raise SystemExit("could not disable per-call GL error checking")
    width, height = (int(v) for v in args.size.split("x"))
    result = measure(args.clip, preset=args.preset, size=(width, height), frames=args.frames, rounds=args.rounds)
    print(f"{width}x{height} preset {args.preset}: whole frame GPU median {result['full_ms']:.2f} ms "
          f"(p90 {result['full_p90_ms']:.2f})")
    for name, ms in sorted(result["stage_ms"].items(), key=lambda kv: -kv[1]):
        print(f"  {name:20s} {ms:6.2f} ms")
    rest = result["full_ms"] - sum(result["stage_ms"].values())
    print(f"  {'everything else':20s} {rest:6.2f} ms  (scene target clears/resolves/bloom/composite, backdrop, shells)")
    print(f"conditions: {result['conditions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
