"""Bubble's GPU cost matrix (Current_Plan.md item 8b, "Bubble GPU optimisation"; the guide's layer C): the native
surface's GPU time (every pass of the content, the timer's kind 2) at 4K-class pixel counts on OpenGL and Vulkan, for
three decoration cases at four card shapes, each pass and each stage of the ``bubble`` pass by difference.

Cases (settings from the canonical spec, never presets: ``owner_render_parity.nondefault_settings`` variant a, every
toggle on and every slider at 37 %, with the decoration's switches moved):
  off        variant a with the decoration off (microbubbles and particles: stream, drift and glow off);
  on         variant a as it is (the representative decoration on);
  dense_glow variant a with the decoration at its densest and brightest (densities, sizes, glow intensity, spread and
             reactivity at their spec maxima) and the most heroes the spec allows (30 big, 80 small: on a large card
             R-170's density growth takes the live population to its cap of 72).
Shapes (``tools/visualizer_replay/driver.replay_clip`` at a committed world, uniform scale 1, so a larger card grows its
population as the product's does), each at the ratios named in ``SHAPES``:
  canonical  the canonical card (420 x 280) on a 4K display (ratio 2: 840 x 560) and at a 4K frame's pixel count;
  wide       2400 x 300 at ratio 1.5 (3600 x 450);  tall 280 x 1200 at ratio 1.5 (420 x 1800);
  expanded   the card filling a 2560 x 1440 display at 150 % (3840 x 2160, the operator's TV).
The frame: the first input at or after ``AT_S`` of the recorded take (``human_heavy1``, sustained heavy), one frame
republished each timed frame (``bubble_check._native_cost``), median and p90 of at least 240 frames, the least-loaded of
three interleaved rounds. Variants (each the route's program with one thing left out): ``no_points``, ``no_mask`` (the
ambient passes), ``no_wake``, ``no_ghost``, ``no_heroes`` (``bubble_check.STAGE_VARIANTS``), ``empty_twice`` (the two
ambient passes drawn twice: with the decoration off, the two empty passes' cost) and any ``--candidate`` (a byte-identical
candidate's edit of ``bubble.frag``, timed before it lands). On OpenGL the Python renderer's own cost of the same frame.
``nvidia-smi`` and the whole-machine CPU load before and after each child.

    python native/core/python/bubble_cost_matrix.py --label <label> [--apis opengl vulkan] [--candidate <name>]
        [--only <case/shape/scale prefix> ...] [--no-python]; --table <cost_matrix.json> rewrites its table
Evidence: .artifacts/evidence/native_core/bubble_gpu_optimisation/<date>_<label>/ (cost_matrix.json, its table).
Exit 0 whenever it ran.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (str(HERE), str(ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bubble_check as bc  # noqa: E402

base = bc.base
APIS = ("opengl", "vulkan")
TAKE = "human_heavy1"
AT_S = 20.0
CANONICAL = (420.0, 280.0)
#: shape -> (committed world or None for the canonical baseline, {scale name: ratio}).
SHAPES = {
    "canonical": (None, {"display_4k": 2.0, "card_4k_area": None}),
    "wide": ((2400.0, 300.0), {"r1.5": 1.5}),
    "tall": ((280.0, 1200.0), {"r1.5": 1.5}),
    "expanded": ((2560.0, 1440.0), {"r1.5": 1.5}),
}
DECORATION = ("bubble_microbubble_stream", "bubble_microbubble_drift", "bubble_particle_stream",
              "bubble_particle_drift", "bubble_particle_glow")
VARIANTS = (None, "no_points", "no_mask", "no_wake", "no_ghost", "no_heroes", "empty_twice")
#: Candidates (``--candidate``): name -> (a line of bubble.frag found exactly once, its replacement), each timed as a
#: variant before it lands; a landed candidate is removed (its line is gone). The hero loop's square reject was timed
#: here as ``hero_reject_early`` (20261121_matrix_before) and landed (20261121_matrix_after).
CANDIDATES: dict[str, tuple[str, str]] = {}


def _settings_overlay(case: str) -> dict:
    from core.settings.visualizer_mode_settings import Slider, require_mode_settings
    from tools.visualizer_replay import owner_render_parity as parity

    overlay = parity.nondefault_settings("bubble", "a")
    if case == "off":
        overlay.update({key: False for key in DECORATION})
    elif case == "dense_glow":
        maxima = ("bubble_microbubble_density", "bubble_microbubble_size", "bubble_particle_density",
                  "bubble_particle_size", "bubble_particle_glow_intensity", "bubble_particle_glow_reactivity",
                  "bubble_particle_glow_spread", "bubble_big_count", "bubble_small_count")
        for control in require_mode_settings("bubble").controls:
            if isinstance(control, Slider) and control.key in maxima:
                high = getattr(control, "admission_high", None)
                overlay[control.key] = control.high if high is None else high
        overlay.update({key: True for key in DECORATION})
    return overlay


def _resolved(case: str) -> dict:
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload

    return dict(resolve_visualizer_activation_payload({"mode": "bubble", **_settings_overlay(case)}).resolved_config)


def capture(seconds: float, only=()) -> tuple[list[dict], dict]:
    """Every case's frame at every ratio: (entries, case -> (snapshot, logical size)) for the Python cost."""
    import dataclasses

    from core.visualizer_engine import bubble_native_schema
    from rendering.native.composite import composite_geometry
    from rendering.native.spectrum import spectrum_presentation
    from rendering.quick.visualizer.native_route import BUBBLE_SETTINGS, GENERIC_MODE_TARGET_SIZES
    from tools import expanded_visualizer_evidence as evidence
    from tools.visualizer_replay.driver import replay_clip

    clip = evidence.load_recording(TAKE, seconds)
    start = clip.frames[0].timestamp_us
    index = next(i for i, f in enumerate(clip.frames) if (f.timestamp_us - start) / 1e6 >= AT_S)
    sizer = GENERIC_MODE_TARGET_SIZES["bubble"]
    entries: list[dict] = []
    snapshots: dict = {}
    for case in ("off", "on", "dense_glow"):
        settings = _resolved(case)
        for shape, (extent, scales) in SHAPES.items():
            if only and not any(f"{case}/{shape}/".startswith(p) or p.startswith(f"{case}/{shape}/") for p in only):
                continue
            result = replay_clip(clip, "bubble", settings=settings, viewport_extent=extent, snapshots_at=(index,))
            snapshot = result["snapshots"][index]
            presentation = snapshot.presentation
            record = bubble_native_schema.encode(snapshot.logical)
            decoded = bubble_native_schema.decode(record)
            count = int(decoded["u_bubble_count"])
            alphas = [float(position[3]) for position in list(decoded["u_bubbles_pos"])[:count]]
            for scale, ratio in scales.items():
                moved0 = dataclasses.replace(snapshot, presentation=dataclasses.replace(presentation, dpr=1.0))
                display = (max(1920.0, (extent or CANONICAL)[0]), max(1080.0, (extent or CANONICAL)[1]))
                card0 = spectrum_presentation(moved0.presentation, composite_geometry(moved0.presentation),
                                              window_size=display, window_pixels=tuple(int(v) for v in display))
                width, height = (float(v) for v in card0["item_size"])
                if ratio is None:                               # the card at a 4K frame's pixel count, at most 8
                    ratio = min(bc.COST_MAX_HOST_DPR, (bc.COST_WIDE_PIXELS * 2160.0 / (width * height)) ** 0.5)
                moved = dataclasses.replace(snapshot, presentation=dataclasses.replace(presentation, dpr=ratio))
                pixels = tuple(int(round(v * ratio)) for v in display)
                card = spectrum_presentation(moved.presentation, composite_geometry(moved.presentation),
                                             window_size=display, window_pixels=pixels)
                at = BUBBLE_SETTINGS(moved, card)
                key = f"{case}/{shape}/{scale}"
                entries.append({
                    "key": key, "case": case, "shape": shape, "scale": scale, "dpr": float(ratio), "index": index,
                    "card": card, "shown": base._shown(card, moved.presentation), "settings": at,
                    "sizes": {k: list(v) for k, v in sizer(moved, at).items()}, "record": record,
                    "heroes": {"count": count, "live": sum(1 for a in alphas if float(a) >= 0.01)},
                    "ambient": {"enabled": int(decoded["u_ambient_enabled"]),
                                "points": int(decoded["ambient_point_floats"]) // 6,
                                "occluders": int(decoded["ambient_occluder_floats"]) // 4},
                    "item_pixels": [int(round(width * ratio)), int(round(height * ratio))]})
                snapshots[key] = (snapshot, (width, height))
    return entries, snapshots


def _cpu_load() -> float | None:
    try:
        text = subprocess.run(["powershell", "-NoProfile", "-Command",
                               "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage "
                               "-Average).Average"], capture_output=True, text=True, timeout=60).stdout.strip()
        return float(text)
    except Exception:  # noqa: BLE001
        return None


def _state() -> dict:
    return {"cpu_load_percent": _cpu_load(), **bc._gpu_state()}


#: entry key -> ``nvidia-smi``'s line just after its timing (the clocks its frames ran at).
CLOCKS: dict = {}


def time_entries(core, engine, app, api: str, entries: list[dict], variants: tuple, rounds: int) -> dict:
    """Each entry's variants, ``rounds`` interleaved rounds, each keeping its least-loaded round."""
    results: dict = {}
    for entry in entries:
        width, height = entry["card"]["item_size"]
        dpr = entry["dpr"]
        host = core.hidden_host(int(math.ceil((width + 2 * base.MARGIN) * dpr)),
                                int(math.ceil((height + 2 * base.MARGIN) * dpr)))
        try:
            host.set_device_pixel_ratio(dpr)
            timed: dict = {}
            for _round in range(rounds):
                for variant in variants:
                    timed.setdefault(variant or "route", []).append(
                        bc._native_cost(core, engine, app, host, entry, variant, dpr))
            gpu = bc._gpu_state().get("nvidia_smi")       # the clocks the timed frames just ran at
        finally:
            host.close()
            base.host_check._flush_deletes(app)
        CLOCKS[entry["key"]] = gpu
        kept = {}
        for name, runs in timed.items():
            best = min(runs, key=lambda r: float("inf") if r["median_ms"] is None else r["median_ms"])
            kept[name] = dict(best, round_medians=[r["median_ms"] for r in runs])
        results[entry["key"]] = kept
        route = kept["route"]["median_ms"]
        print(f"[MATRIX] {api} {entry['key']}: route {route} ms "
              + " ".join(f"{n} {v['median_ms']}" for n, v in kept.items() if n != "route"), flush=True)
    return results


def child(args) -> dict:
    record: dict = {"api": args.api, "state_before": _state()}
    out = Path(args.out_dir)
    bc._OUT["dir"] = str(out)
    base.use_mode(SLOT_BYTES=bc._slot_bytes())
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="bubble-cost-matrix")
        from PySide6.QtWidgets import QApplication

        app = QApplication([sys.argv[0]])
    else:
        from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication([sys.argv[0]])
    from PySide6.QtQml import QQmlEngine
    from rendering.native import load

    core = load(ROOT / args.module_dir if not Path(args.module_dir).is_absolute() else Path(args.module_dir))
    record["runtime"] = dict(core.info)
    for name in args.candidate or ():
        bc.STAGE_VARIANTS[name] = CANDIDATES[name]
    variants = VARIANTS + tuple(args.candidate or ())
    entries_path = out / "work" / "entries.json"
    snapshots = {}
    if args.api == "opengl":
        started = time.perf_counter()
        entries, snapshots = capture(AT_S + 1.0, args.only)
        record["capture_s"] = round(time.perf_counter() - started, 1)
        entries_path.parent.mkdir(parents=True, exist_ok=True)
        entries_path.write_text(json.dumps([dict(e, record=base64.b64encode(e["record"]).decode("ascii"))
                                            for e in entries]), encoding="utf-8")
    else:
        entries = [dict(e, record=base64.b64decode(e["record"]))
                   for e in json.loads(entries_path.read_text(encoding="utf-8"))]
        instance = core.vulkan_instance(validation=False)
        if not instance.get("ok"):
            record["error"] = f"the Vulkan instance failed: {instance}"
            return record
    if args.only:
        entries = [e for e in entries if any(e["key"].startswith(prefix) for prefix in args.only)]
    record["entries"] = {e["key"]: {k: e[k] for k in ("case", "shape", "scale", "dpr", "index", "heroes", "ambient",
                                                     "item_pixels", "sizes")} for e in entries}
    engine = QQmlEngine()
    try:
        record["native"] = time_entries(core, engine, app, args.api, entries, variants, args.rounds)
        record["clocks"] = CLOCKS
        if args.api == "opengl" and not args.no_python:
            record["python"] = {}
            for entry in entries:
                snapshot, logical = snapshots[entry["key"]]
                runs = [bc.python_cost(snapshot, logical, entry["dpr"]) for _round in range(args.rounds)]
                best = min(runs, key=lambda r: float("inf") if r["median_ms"] is None else r["median_ms"])
                record["python"][entry["key"]] = dict(best, round_medians=[r["median_ms"] for r in runs])
                print(f"[MATRIX] python {entry['key']}: {best['median_ms']} ms", flush=True)
    finally:
        base.host_check._flush_deletes(app)
        record["live_hosts_at_end"] = core.live_hosts()
        if args.api == "vulkan":
            record["teardown"] = core.destroy_vulkan_instance()
        del engine
    record["state_after"] = _state()
    return record


def per_pass(native: dict) -> dict:
    """Each stage's and pass's median and p90 by difference from the route."""
    table = {}
    for key, kept in native.items():
        row = {}
        for stat in ("median_ms", "p90_ms"):
            route = kept["route"][stat]
            figures = {"whole": route}
            for name, label in (("no_points", "ambient_points"), ("no_mask", "ambient_mask"), ("no_wake", "wake"),
                                ("no_ghost", "ghost"), ("no_heroes", "heroes")):
                other = kept.get(name, {}).get(stat)
                figures[label] = None if route is None or other is None else round(route - other, 4)
            twice = kept.get("empty_twice", {}).get(stat)
            figures["ambient_passes_again"] = None if route is None or twice is None else round(twice - route, 4)
            for name in kept:
                if name not in ("route", *VARIANTS):
                    other = kept[name][stat]
                    figures[f"candidate:{name}"] = other
                    figures[f"candidate:{name}_gain"] = None if route is None or other is None else round(route - other, 4)
            row[stat] = figures
        table[key] = row
    return table


def table(report: dict) -> str:
    """The report as one line per API and entry: the pixels, the live heroes, the ambient instances, the whole
    surface and each stage by difference (median ms), the Python renderer's, the candidates', and the clocks."""
    lines = []
    for api, child in report["children"].items():
        before, after = child.get("state_before", {}), child.get("state_after", {})
        lines.append(f"== {api}: CPU {before.get('cpu_load_percent')} % before, {after.get('cpu_load_percent')} % "
                     f"after; GPU before: {before.get('nvidia_smi')}")
        if child.get("error"):
            lines.append(f"ERROR {child['error']}")
            continue
        entries = child.get("entries", {})
        for key, row in (child.get("per_pass") or {}).items():
            e, m, p = entries.get(key, {}), row["median_ms"], row["p90_ms"]
            python = (child.get("python") or {}).get(key, {}).get("median_ms")
            candidates = " ".join(f"{k[10:]} {v}" for k, v in m.items() if k.startswith("candidate:"))
            lines.append(
                f"{key:34s} {e.get('item_pixels')} heroes {e.get('heroes', {}).get('live')} ambient "
                f"{e.get('ambient', {}).get('points')}/{e.get('ambient', {}).get('occluders')} | whole {m['whole']} "
                f"(p90 {p['whole']}) heroes {m['heroes']} wake {m['wake']} ghost {m['ghost']} points "
                f"{m['ambient_points']} mask {m['ambient_mask']} empty_again {m['ambient_passes_again']} | python "
                f"{python} | {candidates} | clocks {child.get('clocks', {}).get(key)}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default="cost_matrix")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--module-dir", default=str(Path("F:/Programming/Apps/ShittyRandomPhotoScreenSaver/release/native_module")))
    parser.add_argument("--rounds", type=int, default=bc.COST_ROUNDS)
    parser.add_argument("--candidate", nargs="*", default=[], choices=sorted(CANDIDATES))
    parser.add_argument("--only", nargs="*", default=[], help="entry key prefixes (case/shape/scale) to time")
    parser.add_argument("--no-python", action="store_true", help="leave the Python renderer's cost out")
    parser.add_argument("--table", type=Path, default=None, help="write a finished cost_matrix.json's table beside it")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api", choices=APIS, help=argparse.SUPPRESS)
    parser.add_argument("--out-dir", help=argparse.SUPPRESS)
    parser.add_argument("--child-json", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.table is not None:
        report = json.loads(args.table.read_text(encoding="utf-8"))
        (args.table.parent / "cost_matrix_table.txt").write_text(table(report), encoding="utf-8")
        return 0
    if args.child:
        try:
            record = child(args)
        except Exception:
            text = traceback.format_exc()
            record = {"api": args.api, "error": text.strip().splitlines()[-1], "traceback": text}
        args.child_json.write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
        return 0
    if "opengl" not in args.apis:
        parser.error("the OpenGL child captures the frames every other API times")
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "bubble_gpu_optimisation", args.label)
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"take": TAKE, "at_s": AT_S, "shapes": {k: [v[0], v[1]] for k, v in SHAPES.items()},
                    "candidates": {n: CANDIDATES[n] for n in args.candidate}, "children": {}}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
        child_json.unlink(missing_ok=True)
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--out-dir", str(out),
                   "--child-json", str(child_json), "--module-dir", args.module_dir, "--rounds", str(args.rounds)]
        if args.candidate:
            command += ["--candidate", *args.candidate]
        if args.only:
            command += ["--only", *args.only]
        if args.no_python:
            command.append("--no-python")
        started = time.monotonic()
        proc = subprocess.run(command, text=True, cwd=str(ROOT), timeout=7200)
        record = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {
            "api": api, "error": f"the child ended without a record ({proc.returncode})"}
        record["wall_s"] = round(time.monotonic() - started, 1)
        report["children"][api] = record
        if record.get("native"):
            record["per_pass"] = per_pass(record["native"])
        print(f"[MATRIX] {api} done in {record['wall_s']} s" + (f": ERROR {record['error']}" if record.get("error")
                                                                  else ""), flush=True)
        child_json.unlink(missing_ok=True)
        if record.get("error"):
            break
    (out / "cost_matrix.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    (out / "cost_matrix_table.txt").write_text(table(report), encoding="utf-8")
    print(f"[MATRIX] report: {out / 'cost_matrix.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
