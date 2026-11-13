"""Waveform GPU cost per render stage, by skip variants (headless, offscreen, production render host).

    .venv/Scripts/python tools/waveform_gpu_stage_cost.py --clip logs/visualizer_recordings/human_heavy1.jsonl --preset 2
    .venv/Scripts/python tools/waveform_gpu_stage_cost.py --clip <clip> --preset 2 --size 3875x1450 --frames 40 --json out.json

Same method as ``tools/eb_gpu_stage_cost.py``: a ``GL_TIME_ELAPSED`` begin inside a frame is taken while the previous
stage still drains, so stages are never timed in place. Whole frames are timed (flushed and finished per frame) and one
stage at a time is amplified (drawn ``1 + extra`` times: cost ``(variant - full) / extra``) or, if it cannot repeat,
removed (``full - variant``). Variants run round-robin in one process, in a rotated
order each round, and each instant's cost is the fastest of its repeats (outside load only adds time). Each round
also times a fixed control job (a synthetic full-screen ALU pass that no source change touches) so runs taken under different clocks or outside load compare as ``ms / control``.

The ``full`` variant also records render-thread CPU per frame: the submit time of ``host.render`` (the Python that
the render thread spends with the GIL), the GL calls it made and how many of them read state back (each a round trip
to the driver thread). Pictures of skipped variants are
wrong by design; this measures cost, never looks. The card uses the edge-resize world aperture at ``--size``, as the
operator's TV card does.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import statistics
import sys
import time
from bisect import bisect_left
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rendering.gl_error_policy import disable_per_call_gl_error_checking  # noqa: E402
from tools import artifact_paths  # noqa: E402

MODE = "waveform_ribbon"
CONTROL_FRAGMENT = """#version 460 core
layout(location=0) out vec4 FragColor;
void main(){vec2 p=gl_FragCoord.xy*0.001;vec4 a=vec4(0);
for(int i=0;i<1200;i++){p=vec2(sin(p.x*1.3+p.y),cos(p.y*1.7-p.x))+0.01*float(i);a+=vec4(p,p.yx);}
FragColor=a*0.01;}
"""
CONTROL_VERTEX = """#version 460 core
void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);gl_Position=vec4(p*2.0-1.0,0.0,1.0);}
"""


def _variants(extra: int):
    """name -> (sign, [(owner, attribute, replacement)]). Most stages are *amplified*: the frame draws that stage
    ``1 + extra`` times, so its cost is ``(variant - full) / extra`` and a sub-millisecond pass stands well clear of
    outside-load noise. Only a stage that cannot be repeated is removed instead (``full - variant``)."""
    from rendering.quick.scene3d import post, reflection, target, floor_give, waveform_field, ribbon_bursts, ribbon
    from rendering.quick.scene3d import waveform as wf
    from OpenGL import GL as gl
    Scene = wf.WaveformScene
    reflect = Scene._reflect
    state = {"reflecting": False}

    def tracked_reflect(self, *a, **k):
        state["reflecting"] = True
        try:
            return reflect(self, *a, **k)
        finally:
            state["reflecting"] = False

    def repeated(original, when=lambda *a, **k: True):
        def run(*a, **k):
            result = original(*a, **k)
            if when(*a, **k):
                for _ in range(extra):
                    original(*a, **k)
            return result
        return run

    def end_with_mips(self):
        for _ in range(extra):
            gl.glGenerateTextureMipmap(self._colour)
        return end(self)

    end = reflection.PlanarReflection.end
    draw, burst = ribbon.RibbonPrimitive.draw, ribbon_bursts.RibbonBurstRenderer.draw
    fog, sky = Scene._update_fog, Scene._sky
    flat_give = property(lambda self: (self._span[0], 0., self._span[2], self._span[3]))
    track = [(Scene, "_reflect", tracked_reflect)]

    def shading(kind, reflected):
        return lambda self, packet, mvp, **k: k.get("shading") == kind and state["reflecting"] == reflected

    def bursts(reflected):
        return lambda *a, **k: state["reflecting"] == reflected

    amplified = {
        "floor give compute": [(floor_give.FloorGiveField, "update", repeated(floor_give.FloorGiveField.update))],
        "mist field compute": [(waveform_field.WaveformField, "update", repeated(waveform_field.WaveformField.update))],
        "mist volume main": [(Scene, "_update_fog", repeated(fog, lambda self, volume, *a, **k: volume is self.fog))],
        "mist volume reflected": [(Scene, "_update_fog",
                                   repeated(fog, lambda self, volume, *a, **k: volume is self.reflected_fog))],
        "sky main": [(Scene, "_sky", repeated(sky, lambda self, volume, *, reflection=False: not reflection))],
        "sky reflected": [(Scene, "_sky", repeated(sky, lambda self, volume, *, reflection=False: bool(reflection)))],
        "reflection (all)": [(Scene, "_reflect", repeated(reflect))],
        "reflection mips": [(reflection.PlanarReflection, "end", end_with_mips)],
        "floor (incl. reflection term)": [(Scene, "_floor", repeated(Scene._floor))],
        "ribbon body OIT": [*track, (ribbon.RibbonPrimitive, "draw", repeated(draw, shading("body", False)))],
        "OIT resolve": [(target.SceneTarget, "_resolve_transparent", repeated(target.SceneTarget._resolve_transparent))],
        "ribbon light main": [*track, (ribbon.RibbonPrimitive, "draw", repeated(draw, shading("light", False)))],
        "ribbon light reflected": [*track, (ribbon.RibbonPrimitive, "draw", repeated(draw, shading("light", True)))],
        "strands main": [*track, (ribbon.RibbonPrimitive, "draw", repeated(draw, shading("strays", False)))],
        "strands reflected": [*track, (ribbon.RibbonPrimitive, "draw", repeated(draw, shading("strays", True)))],
        "sparks main": [*track, (ribbon_bursts.RibbonBurstRenderer, "draw", repeated(burst, bursts(False)))],
        "sparks reflected": [*track, (ribbon_bursts.RibbonBurstRenderer, "draw", repeated(burst, bursts(True)))],
        "emission resolve": [(target.SceneTarget, "_resolve_emission", repeated(target.SceneTarget._resolve_emission))],
        "bloom chain": [(post.BloomChain, "apply", repeated(post.BloomChain.apply))],
    }
    def target_only(self, flat, packet, draw, mvp, eye, view, ribbon_mvp, card, now, fogged):
        recipe = self.recipe
        with self.scene.scope(card, 4, self.resources, overlay=self._overlay, bloom=0. if flat else recipe.bloom,
                              oit=True, hdr=None if flat or not recipe.bloom else recipe.exposure):
            gl.glViewport(0, 0, *self.size)
            gl.glClearBufferfv(gl.GL_COLOR, 0, (0., 0., 0., 1.))
            with self.scene.transparent_writes(card, self.resources):
                pass

    removed = {
        # The yielding floor as a whole: its compute and every consumer's march/normal (the field reads as flat).
        "floor give (all, removed)": [(floor_give.FloorGiveField, "update", lambda *a, **k: None),
                                      (floor_give.FloorGiveField, "uniforms", flat_give)],
        # The scene's draws but not its target (MSAA clears, OIT clear/resolve, emission resolve, bloom, composite):
        # the scene target's own cost is "scene draws and target" minus this.
        "scene draws (target kept)": [(Scene, "_draw_scene", target_only)],
        "scene draws and target": [(Scene, "_draw_scene", lambda *a, **k: None)],
    }
    return {**{key: (1, patches) for key, patches in amplified.items()},
            **{key: (-1, patches) for key, patches in removed.items()}}


class _CountingGL:
    """Stands in for ``OpenGL.GL`` in the render modules: counts every function call made through it."""

    def __init__(self, module, counter):
        self._module, self._counter, self._cache = module, counter, {}

    def __getattr__(self, name):
        value = getattr(self._module, name)
        if not callable(value) or not name.startswith("gl"):
            return value
        wrapped = self._cache.get(name)
        if wrapped is None:
            counter = self._counter

            def wrapped(*a, _f=value, _n=name, **k):
                counter[_n] = counter.get(_n, 0) + 1
                return _f(*a, **k)
            self._cache[name] = wrapped
        return wrapped


QUERY_HELPERS = {"rendering.quick.gl_query": ("get_int", "get_ints", "get_bool", "get_bools", "get_float", "get_floats",
                                               "is_enabled", "get_indexed_int", "get_indexed_bools",
                                               "get_indexed_int64"),
                 "rendering.quick.visualizer.gl_state": ("_int_state", "_int_states", "_bool_states", "_is_enabled")}


def is_query(name: str) -> bool:
    """A call that reads GL state back (a round trip to the driver thread), not one that submits work."""
    return name.startswith(("glGet", "glIs", "glCheck", "query:"))


def _count_gl_calls(counter):
    """Swap the counting proxy into every render module that imported ``OpenGL.GL`` as ``gl``, and count the raw
    state-query helpers (``gl_query``, the host fence) as ``query:<helper>``; returns an undo."""
    from OpenGL import GL
    swapped, helpers = [], []
    for name, module in list(sys.modules.items()):
        if module is None or not name.startswith(("rendering.", "widgets.spotify_visualizer.")):
            continue
        if getattr(module, "gl", None) is GL:
            swapped.append(module)
            module.gl = _CountingGL(GL, counter)
    for module_name, names in QUERY_HELPERS.items():
        module = sys.modules.get(module_name)
        for helper in names if module is not None else ():
            original = getattr(module, helper)

            def counted(*a, _f=original, _n=f"query:{helper}", **k):
                counter[_n] = counter.get(_n, 0) + 1
                return _f(*a, **k)
            helpers.append((module, helper, original))
            setattr(module, helper, counted)

    def undo():
        for module in swapped:
            module.gl = GL
        for module, helper, original in helpers:
            setattr(module, helper, original)
    return undo


def snapshots_for(clip: Path, preset: int, size, start: float, frames: int, fps: float, overrides: dict):
    from widgets.spotify_visualizer.feature_frame import load_jsonl, FeatureClip
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from tools.visualizer_replay.pcm_reanalysis import reanalyzed_bubble_bands
    from tools.visualizer_replay.driver import replay_clip
    from widgets.spotify_visualizer.presentation_geometry import resize_visualizer_presentation
    loaded = load_jsonl(clip)
    origin = loaded.frames[0].timestamp_us
    times = [(frame.timestamp_us - origin) / 1e6 for frame in loaded.frames]
    indices = sorted({bisect_left(times, start + i / fps) for i in range(frames)})
    activation = resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": preset - 1}, mode=MODE)
    if activation.is_custom or activation.preset_index != preset - 1:
        raise ValueError(f"No curated Waveform preset {preset}")
    settings = {**activation.resolved_config, **overrides}
    with reanalyzed_bubble_bands():
        result = replay_clip(FeatureClip("waveform_cost", tuple(loaded.frames[:indices[-1] + 1])), MODE,
                             settings=settings, snapshots_at=indices)
    width, height = size
    snapshots = []
    for index in indices:
        snapshot = result["snapshots"][index]
        presentation = resize_visualizer_presentation(snapshot.presentation, display_size=(width, height),
            outer_origin=(0., 0.), relative_scale=1., viewport_extent=(width, height),
            committed_outer_size=(width, height))
        snapshots.append(replace(snapshot, presentation=presentation))
    return snapshots, activation.preset_name


def measure(clip: Path, *, preset: int, size: tuple[int, int], frames: int, rounds: int, start: float,
            overrides: dict, stages: bool = True, extra: int = 4) -> dict:
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    import numpy as np
    from OpenGL import GL as gl
    from OpenGL.raw.GL.VERSION import GL_3_3 as raw33
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from rendering.quick.render.gl_resources import compile_program, delete_program
    from tools.bench_stability import SystemSampler, summarise_environment
    from tools.labs.render_target import OffscreenRenderTarget

    width, height = size
    snapshots, name = snapshots_for(clip, preset, size, start, frames, 30., overrides)
    target = OffscreenRenderTarget(width, height, label="waveform stage cost")
    host = QuickVisualizerRenderHost()
    matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
    skips = {key: patches for key, (_, patches) in _variants(extra).items()} if stages else {}
    signs = {key: sign for key, (sign, _) in _variants(extra).items()} if stages else {}
    variants = ["full", *skips]
    results: dict[str, list[list[float]]] = {key: [[] for _ in snapshots] for key in variants}
    control: list[float] = []
    cpu_ms: list[float] = []
    interval_ms: list[float] = []
    calls: list[int] = []
    queries: list[int] = []
    sampler = SystemSampler()
    conditions = [sampler.sample()]
    with target.current():
        query = int(np.asarray(gl.glGenQueries(1)).ravel()[0])
        control_program = compile_program(CONTROL_VERTEX, CONTROL_FRAGMENT, label="waveform cost control")
        control_vao = int(np.asarray(gl.glGenVertexArrays(1)).ravel()[0])

        def timed(job) -> float:
            gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
            job()
            gl.glEndQuery(gl.GL_TIME_ELAPSED)
            gl.glFlush()
            gl.glFinish()
            value = ctypes.c_uint64()
            raw33.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
            return value.value / 1e6

        def draw_control():
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            gl.glViewport(0, 0, width, height)
            gl.glUseProgram(control_program)
            gl.glBindVertexArray(control_vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glBindVertexArray(0)
            gl.glUseProgram(0)

        def render(snapshot):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            gl.glViewport(0, 0, width, height)
            host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                        logical_size=(float(width), float(height)), matrix_values=matrix)

        try:
            for snapshot in snapshots[:12]:
                timed(lambda: render(snapshot))           # warm every program and target
            for round_ in range(rounds):
                # Interleaved per snapshot: every variant renders the same instant back to back (rotated order), so
                # slow drift in clocks or outside load lands on all variants alike; stage costs are paired medians.
                for ordinal, snapshot in enumerate(snapshots):
                    shift = (round_ + ordinal) % len(variants)
                    for key in variants[shift:] + variants[:shift]:
                        saved = [(owner, attr, owner.__dict__[attr]) for owner, attr, _ in skips.get(key, ())]
                        for owner, attr, replacement in skips.get(key, ()):
                            setattr(owner, attr, replacement)
                        try:
                            results[key][ordinal].append(timed(lambda: render(snapshot)))
                        finally:
                            for owner, attr, original in reversed(saved):
                                setattr(owner, attr, original)
                    control.append(timed(draw_control))
                # Render-thread CPU: submit time and PyOpenGL calls of the full frame (after a finish: no backlog).
                counter: dict[str, int] = {}
                undo = _count_gl_calls(counter)
                try:
                    render(snapshots[0]); gl.glFinish(); counter.clear()
                    render(snapshots[1]); gl.glFinish()
                    calls.append(sum(counter.values()))
                    queries.append(sum(n for key, n in counter.items() if is_query(key)))
                    top = sorted(counter.items(), key=lambda kv: -kv[1])[:12]
                    query_top = sorted(((k, n) for k, n in counter.items() if is_query(k)), key=lambda kv: -kv[1])
                finally:
                    undo()
                for snapshot in snapshots:
                    gl.glFinish()
                    begun = time.perf_counter()
                    render(snapshot)
                    cpu_ms.append((time.perf_counter() - begun) * 1e3)
                gl.glFinish()
                # Sustained frame interval with at most two frames in flight (a swap chain's queue), no per-frame
                # finish: what the render loop can hold, CPU and GPU overlapping as they do live.
                fences, last = [], time.perf_counter()
                for ordinal, snapshot in enumerate(snapshots * 2):
                    render(snapshot)
                    fences.append(gl.glFenceSync(gl.GL_SYNC_GPU_COMMANDS_COMPLETE, 0))
                    gl.glFlush()
                    if len(fences) > 2:
                        fence = fences.pop(0)
                        gl.glClientWaitSync(fence, gl.GL_SYNC_FLUSH_COMMANDS_BIT, 1_000_000_000)
                        gl.glDeleteSync(fence)
                    now = time.perf_counter()
                    if ordinal >= 3:
                        interval_ms.append((now - last) * 1e3)
                    last = now
                for fence in fences:
                    gl.glClientWaitSync(fence, gl.GL_SYNC_FLUSH_COMMANDS_BIT, 1_000_000_000)
                    gl.glDeleteSync(fence)
                conditions.append(sampler.sample())
        finally:
            host.release_resources()
            delete_program(control_program)
            gl.glDeleteVertexArrays(1, [control_vao])
            gl.glDeleteQueries(1, [query])
    target.close()
    # Outside GPU work only ever adds time to a frame: the fastest repeat of each instant is its least contended
    # cost. Stage costs are per-instant differences of those minima, then the median over instants.
    least = {key: [min(repeats) for repeats in per] for key, per in results.items()}
    every = [value for repeats in results["full"] for value in repeats]
    full = statistics.median(least["full"])
    ordered = sorted(least["full"])
    control_ms = min(control)
    return {"preset": preset, "name": name, "size": size, "clip": str(clip), "start": start, "overrides": overrides,
            "frames": len(snapshots), "rounds": rounds,
            "full_ms": full, "full_p90_ms": ordered[int(0.9 * len(ordered))], "control_ms": control_ms,
            "full_per_control": full / control_ms,
            "full_all_median_ms": statistics.median(every), "control_median_ms": statistics.median(control),
            "stage_ms": {key: statistics.median((b - a) / extra if signs[key] > 0 else a - b
                                                for a, b in zip(least["full"], values))
                         for key, values in least.items() if key != "full"}, "amplify_extra": extra,
            "cpu_submit_ms_median": statistics.median(cpu_ms), "cpu_submit_ms_p90": sorted(cpu_ms)[int(.9*len(cpu_ms))],
            "interval_ms_median": statistics.median(interval_ms),
            "interval_ms_p90": sorted(interval_ms)[int(.9 * len(interval_ms))],
            "gl_calls_per_frame": statistics.median(calls), "gl_calls_top": top,
            "gl_queries_per_frame": statistics.median(queries), "gl_queries": query_top,
            "conditions": summarise_environment(conditions)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--preset", type=int, default=2)
    parser.add_argument("--size", default="3875x1450", help="card size in device pixels (edge-resize aperture)")
    parser.add_argument("--start", type=float, default=20.)
    parser.add_argument("--frames", type=int, default=30, help="distinct snapshots per round (30 fps spacing)")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--extra", type=int, default=4, help="extra repeats of an amplified stage")
    parser.add_argument("--whole", action="store_true", help="whole frame, control and CPU only (no stage variants)")
    parser.add_argument("--set", action="append", default=[], help="KEY=JSON setting override")
    parser.add_argument("--json", type=artifact_paths.evidence_arg, help="write the result here")
    args = parser.parse_args()
    if not disable_per_call_gl_error_checking():
        raise SystemExit("could not disable per-call GL error checking")
    width, height = (int(v) for v in args.size.split("x"))
    overrides = {key: json.loads(value) for key, value in (item.split("=", 1) for item in args.set)}
    result = measure(args.clip, preset=args.preset, size=(width, height), frames=args.frames, rounds=args.rounds,
                     start=args.start, overrides=overrides, stages=not args.whole, extra=args.extra)
    print(f"{width}x{height} {result['name']}: whole frame GPU median {result['full_ms']:.2f} ms "
          f"(p90 {result['full_p90_ms']:.2f}); control {result['control_ms']:.3f} ms; "
          f"frame/control {result['full_per_control']:.2f}")
    for key, ms in sorted(result["stage_ms"].items(), key=lambda kv: -kv[1]):
        print(f"  {key:24s} {ms:6.2f} ms")
    print(f"sustained frame interval (two in flight) median {result['interval_ms_median']:.2f} ms "
          f"(p90 {result['interval_ms_p90']:.2f})")
    print(f"render-thread CPU submit median {result['cpu_submit_ms_median']:.2f} ms (p90 {result['cpu_submit_ms_p90']:.2f}); "
          f"GL calls/frame {result['gl_calls_per_frame']} of which state queries {result['gl_queries_per_frame']}")
    print(f"  top calls {result['gl_calls_top']}")
    print(f"  queries {result['gl_queries']}")
    print(f"conditions: {result['conditions']}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
