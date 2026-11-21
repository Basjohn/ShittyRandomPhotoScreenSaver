"""Coverage selection for the fast long-clip proof (``Docs/Guides/Native_Parity_And_Timing_Proof.md`` section 3; part 2
of ``Current_Plan.md``'s fast-proof box): which windows of a take a port's pixel layer draws, chosen from layer L's
records of one continuous run of the take from its cold start, and the report that proves they cover it.

    python tools/visualizer_replay/coverage_windows.py --mode bubble --recording <take> --seconds 60
        --deliveries <the take's delivery stream (native_record_identity.py --deliveries)> --out <evidence dir>

**The run is never restarted.** The windows are cut from the take's one continuous delivery stream: the simulation,
with Dynamic Floor, Adaptive Sensitivity and AGC, ticked every input from the take's first. A window is drawn by
starting only the GPU drawing at its warm-up (``native_stream_player.py --windows``, ``owner_render_parity.py
--windows``); its records are the continuous run's. ``continuity_check`` proves that for a window run of the layer L
tool (``native_record_identity.run(window=...)``: ticked from input 0, only the window kept), and that a run whose
simulation restarts at the window (``restart=True``) is caught (``tests/test_coverage_windows.py``).

**The windows** (each ``WINDOW_S`` long unless stated, merged where they overlap; every one reported with its inputs
and its time in the take):

- ``cold_start``: the take's first inputs (the reveal);
- ``switch``: the mode switch and the fade to the next mode, to the last native frame;
- ``late``: at least one window in the last ``LATE_S`` seconds before the switch (the loudest second there), where
  adaptive state has drifted most;
- ``loudest`` and ``quietest``: the take's loudest and quietest second (the input's loudness before AGC);
- ``field:<name>:min`` / ``:max``: around the input where each record field's smallest and largest value occurs.

**The coverage report** gives every record field's observed range over the whole take and over the windows' inputs;
acceptance needs them equal (``covered``).

Warm-up per mode (``WARMUP_INPUTS``): the inputs drawn before a window starts so its GPU history is the continuous
run's. The landed modes keep no GPU history between frames (each frame is drawn from its own record and settings): 0.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import artifact_paths  # noqa: E402

WINDOW_S = 1.0
LATE_S = 15.0
#: The inputs drawn before a window (guide section 5's GPU history per mode). Spectrum, Spline Curve and Bubble draw each
#: frame from its record and settings alone; so does the Oscilloscope (its afterglow traces are the record's, its bloom
#: is drawn again each frame from that frame's emission).
WARMUP_INPUTS = {"spectrum": 0, "devcurve": 0, "bubble": 0, "oscilloscope": 0}


def stream_states(folder: Path):
    """Each input of a delivery stream with its state resolved: (input, drawn, record, settings, card, sizes)."""
    lines = (Path(folder) / "deliveries.jsonl").read_text(encoding="utf-8").splitlines()
    state = {"record": None, "settings": None, "card": None, "sizes": None}
    with (Path(folder) / "records.bin").open("rb") as records:
        for raw in lines[1:]:
            line = json.loads(raw)
            if "record" in line:
                offset, size = line["record"]
                records.seek(offset)
                state["record"] = records.read(size)
            for key in ("settings", "card", "sizes"):
                if key in line:
                    state[key] = line[key]
            yield (line["input"], bool(line["drawn"]), state["record"], state["settings"], state["card"],
                   state["sizes"])


def _field_ranges(schema, record: bytes) -> dict:
    """Each record field's (smallest, largest) value in ``record`` (every element; an f32 stream's used floats)."""
    import numpy as np

    values = schema.decode(record)
    out = {}
    for field in schema.layout.fields[2:]:
        value = values[field.name]
        if field.kind == "f32":
            # A stream's used length: the u32 field whose own range rule caps it at the stream's size.
            used = next((name for name, kind, limit in schema.checks if kind == "at_most" and limit == field.count
                         and name != field.name), None)
            array = np.frombuffer(bytes(value), np.float32)
            if used is not None:
                array = array[:int(values[used])]
        else:
            array = np.asarray(value, dtype=np.float64).ravel()
        if array.size:
            out[field.name] = (float(array.min()), float(array.max()))
    return out


def input_loudness(mode: str, recording: str | None, seconds: float) -> tuple[list, list]:
    """Per input of the take's parity script: (its loudness before AGC, its time in the take in seconds)."""
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay import owner_render_parity as parity

    clip = evidence.load_recording(recording, seconds) if recording else evidence.shipped_clip(seconds)
    script = parity.parity_script(clip.frames, mode)
    frames = [value for kind, value in script if kind == "input"]
    start = frames[0].timestamp_us
    return ([float(frame.energy.pre_agc.overall) for frame in frames],
            [round((frame.timestamp_us - start) / 1e6, 3) for frame in frames])


def select(mode: str, deliveries: Path, *, recording: str | None, seconds: float, switch_input: int) -> dict:
    """The windows and the coverage report for one take (``deliveries``: its continuous delivery stream)."""
    from core.visualizer_engine.native_schema import schema_for_mode

    schema = schema_for_mode(mode)
    loudness, times = input_loudness(mode, recording, seconds)
    rate = (len(times) - 1) / max(1e-9, times[-1] - times[0]) if len(times) > 1 else 90.0
    span = max(1, int(round(WINDOW_S * rate)))
    drawn_inputs, ranges, extremes = [], {}, {}
    last_drawn = 0
    for index, drawn, record, _settings, _card, _sizes in stream_states(deliveries):
        if not drawn or record is None:
            continue
        drawn_inputs.append(index)
        last_drawn = index
        for name, (low, high) in _field_ranges(schema, record).items():
            seen = ranges.get(name)
            if seen is None:
                ranges[name] = [low, high]
                extremes[name] = [index, index]
                continue
            if low < seen[0]:
                seen[0], extremes[name][0] = low, index
            if high > seen[1]:
                seen[1], extremes[name][1] = high, index
    shown = [i for i in drawn_inputs if i < switch_input]
    first, last = (shown[0], shown[-1]) if shown else (0, max(0, switch_input - 1))

    def around(index: int) -> list[int]:
        lo = max(first, index - span // 2)
        return [lo, min(lo + span, last_drawn + 1)]

    def loudest_second(lo: int, hi: int, *, quietest: bool = False) -> int:
        best, at = None, lo
        for start in range(lo, max(lo + 1, hi - span + 1)):
            total = sum(loudness[start:start + span])
            if best is None or (total < best if quietest else total > best):
                best, at = total, start
        return at + span // 2

    windows = [{"reason": "cold_start", "inputs": [first, first + span]},
               {"reason": "switch", "inputs": [max(first, switch_input - span // 2), last_drawn + 1]}]
    late_lo = next((i for i, t in enumerate(times) if t >= times[min(switch_input, len(times) - 1)] - LATE_S), first)
    windows.append({"reason": "late", "inputs": around(loudest_second(max(first, late_lo), switch_input))})
    windows.append({"reason": "loudest", "inputs": around(loudest_second(first, switch_input))})
    windows.append({"reason": "quietest", "inputs": around(loudest_second(first, switch_input, quietest=True))})
    for name, (low_at, high_at) in extremes.items():
        windows.append({"reason": f"field:{name}:min", "inputs": around(low_at)})
        windows.append({"reason": f"field:{name}:max", "inputs": around(high_at)})
    merged = _merge(windows)
    for window in merged:
        lo, hi = window["inputs"]
        window["seconds"] = [times[min(lo, len(times) - 1)], times[min(hi - 1, len(times) - 1)]]
        window["warmup_inputs"] = WARMUP_INPUTS[mode]
    chosen = {i for window in merged for i in range(*window["inputs"])}
    report = coverage_of(mode, deliveries, merged, ranges)
    late_windows = [w for w in merged if any(r == "late" for r in w["reasons"])]
    return {"mode": mode, "recording": recording, "switch_input": switch_input, "rate_hz": round(rate, 2),
            "window_inputs": span, "drawn_inputs": len(drawn_inputs), "windows": merged,
            "window_input_count": len(chosen & set(drawn_inputs)),
            "late_window_seconds": [w["seconds"] for w in late_windows],
            "late_window_in_last_15_s": bool(late_windows) and all(
                w["seconds"][1] >= times[min(switch_input, len(times) - 1)] - LATE_S for w in late_windows),
            "coverage": report, "covered": all(entry["covered"] for entry in report.values()),
            "ranges": ranges}


def coverage_of(mode: str, deliveries: Path, windows: list[dict], ranges: dict) -> dict:
    """Per record field: its range over the take (``ranges``), over ``windows``' drawn inputs, and whether they agree."""
    from core.visualizer_engine.native_schema import schema_for_mode

    schema = schema_for_mode(mode)
    chosen = {i for window in windows for i in range(*window["inputs"])}
    covered: dict = {}
    for index, drawn, record, _settings, _card, _sizes in stream_states(deliveries):
        if index not in chosen or not drawn or record is None:
            continue
        for name, (low, high) in _field_ranges(schema, record).items():
            seen = covered.setdefault(name, [low, high])
            seen[0], seen[1] = min(seen[0], low), max(seen[1], high)
    return {name: {"take": ranges[name], "windows": covered.get(name), "covered": covered.get(name) == ranges[name]}
            for name in ranges}


def _merge(windows: list[dict]) -> list[dict]:
    ordered = sorted(windows, key=lambda w: w["inputs"][0])
    merged: list[dict] = []
    for window in ordered:
        lo, hi = window["inputs"]
        if merged and lo <= merged[-1]["inputs"][1]:
            merged[-1]["inputs"][1] = max(merged[-1]["inputs"][1], hi)
            merged[-1]["reasons"].append(window["reason"])
        else:
            merged.append({"inputs": [lo, hi], "reasons": [window["reason"]]})
    return merged


def window_inputs(windows: dict | list, *, warmup: bool = True) -> set[int]:
    """The inputs a windowed drawing run draws (each window with its warm-up before it)."""
    items = windows["windows"] if isinstance(windows, dict) else windows
    out: set[int] = set()
    for window in items:
        lo, hi = window["inputs"]
        lo -= int(window.get("warmup_inputs", 0)) if warmup else 0
        out.update(range(max(0, lo), hi))
    return out


def continuity_check(full: Path, window: Path, start: int, end: int, *, offset: int = 0) -> dict:
    """A window run's delivery stream against the full continuous run's over ``[start, end)``: every input's drawn flag,
    record bytes, settings, card and sizes byte-identical. ``offset``: the window run's first input's index in the take
    (a restarted run numbers from 0)."""
    full_states = {s[0]: s for s in stream_states(full) if start <= s[0] < end}
    differing, compared = [], 0
    for state in stream_states(window):
        index = state[0] + offset
        if not start <= index < end:
            continue
        compared += 1
        other = full_states.get(index)
        if other is None or tuple(json.dumps(v, sort_keys=True) if not isinstance(v, bytes) else v
                                  for v in state[1:]) != tuple(
                json.dumps(v, sort_keys=True) if not isinstance(v, bytes) else v for v in other[1:]):
            differing.append(index)
    return {"compared": compared, "expected": len(full_states), "differing": differing,
            "identical": compared == len(full_states) > 0 and not differing}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", required=True)
    parser.add_argument("--recording", default=None)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--deliveries", type=Path, required=True)
    parser.add_argument("--switch-input", type=int, required=True,
                        help="the take's mode-switch input (the layer L report's switch_input)")
    parser.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    args = parser.parse_args(argv)
    report = select(args.mode, args.deliveries, recording=args.recording, seconds=args.seconds,
                    switch_input=args.switch_input)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "coverage_windows.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"[COVERAGE] {args.mode} {args.recording}: {len(report['windows'])} windows, "
          f"{report['window_input_count']} of {report['drawn_inputs']} drawn inputs; late window(s) at "
          f"{report['late_window_seconds']} s; fields covered {sum(e['covered'] for e in report['coverage'].values())}"
          f" of {len(report['coverage'])}: {'COVERED' if report['covered'] else 'NOT COVERED'}", flush=True)
    for window in report["windows"]:
        print(f"[COVERAGE]   inputs {window['inputs']} ({window['seconds'][0]}-{window['seconds'][1]} s): "
              f"{', '.join(window['reasons'][:6])}{' ...' if len(window['reasons']) > 6 else ''}", flush=True)
    return 0 if report["covered"] and report["late_window_in_last_15_s"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
