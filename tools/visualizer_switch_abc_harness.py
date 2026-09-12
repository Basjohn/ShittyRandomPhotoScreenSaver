"""A/B/C causal harness for the visualizer post-switch presentation tail (P4).

Authority: ``Docs/Future_Work/Visualizer_Post_Switch_Performance.md`` phase P4.
Guardrail: ``Docs/Guardrails/Performance_Optimization_Contract.md``.

The physical slowdown must be measured in the real product path; synthetic GL
tests cannot prove scheduler/QML/whole-scene behaviour. This harness owns the
parts that can be automated and kept identical between runs:

* a repeatable CPU **contention** workload (``contention``);
* a **scorer** (``score``) that reads the app's own diagnostic metric plane over
  the driver's named steady windows (``steady_A`` / ``steady_B`` /
  ``steady_C_pre`` / ``steady_C_post``), validates freshness/reactivity, and
  fails a run closed when evidence is missing;
* a **classifier** (``classify``) applying the phase-P4 regression threshold,
  persistence requirement and metric-matched recovery rule to three matched
  A/B/C repetitions; and
* an optional **auto** orchestrator (``auto``) that launches one condition
  through the real app under the opt-in ``--abc-drive`` driver plus matched
  contention, then scores the run it produced.

It deliberately does not invent instrumentation: the built-in PERF/usage/QML
output is the evidence plane; this only scores and classifies it. Tool output can
never authorise a change forbidden by the reactivity/freshness/latency-tail
checklist.

Two ways to run each condition (three matched reps of each — A, B, C):

Automatic (opt-in in-app driver drives the exact interaction and quits the app)::

    python tools/visualizer_switch_abc_harness.py auto \
        --condition B --layout-slot 1 --workers 4 \
        --log logs/screensaver.log --out B1.json

Manual (operator drives the interaction; the driver is not used)::

    1. start the app in RUN mode with diagnostics and the boundary telemetry::
         python main.py /s --usage --viz --perf --viz-switch-telemetry
    2. start matched contention for the whole run::
         python tools/visualizer_switch_abc_harness.py contention --workers 4 --seconds 400
    3. perform the condition's interactions from the SAME saved-layout Bubble
       baseline (A: hold Bubble; B: exactly five Sphere->Spectrum->Oscilloscope->
       Sine->Bubble cycles then hold; C: same exposure, hold, reload the same
       slot, hold again). Emit the steady-window markers by hand only if not
       using the driver — otherwise prefer ``auto``.
    4. score the produced log::
         python tools/visualizer_switch_abc_harness.py score --log run_B1.log --out B1.json

Then classify three matched reps::

    python tools/visualizer_switch_abc_harness.py classify \
        --a A1.json A2.json A3.json \
        --b B1.json B2.json B3.json \
        --c C1.json C2.json C3.json --out verdict.json

Optional discriminator D: repeat A and B without contention; if B only diverges
under contention the bug may be a latent amplification rather than a leak.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import statistics
import sys
import time
from pathlib import Path

# --- investigation thresholds (challengeable; not product SLAs) -------------
MIN_SCORED_SECONDS = 60.0        # a scored window must cover at least this long
# The event-loop recorder emits one summary every ~15 s, so a settled 120 s window
# carries ~8. Require 5 (margin below 8) so a genuinely stalled recorder still
# fails closed, without rejecting a healthy window for the normal cadence.
MIN_EVENTLOOP_SAMPLES = 5
BUCKET_SECONDS = 20.0            # persistence bucket granularity
PERSIST_SECONDS = 60.0           # a regression must persist at least this long
P99_ABS_MS = 2.0                 # event-loop p99 absolute worsening floor
P99_REL = 0.35                   # event-loop p99 relative worsening floor
SKIP_PP = 5.0                    # frame-pacer skip percentage-point worsening floor
RECOVERY_FRACTION = 0.70         # C must remove this fraction of the introduced delta
REVISION_HZ_FLOOR = 45.0         # below this, logical/source starvation is suspected
SOURCE_AGE_CEILING_MS = 120.0    # above this mean age, freshness is unhealthy
REQUIRED_REPS = 3                # matched reps needed before a causal verdict
CONDITION_WINDOWS = {
    "A": ("steady_A",),
    "B": ("steady_B",),
    "C": ("steady_C_pre", "steady_C_post"),
}


# ---------------------------------------------------------------------------
# Contention workload — repeatable, bounded, cancellable by duration.
# ---------------------------------------------------------------------------

def _cpu_spin(deadline: float) -> None:
    """Bounded floating-point busy-work until ``deadline`` (monotonic seconds)."""
    x = 1.000001
    while time.monotonic() < deadline:
        for _ in range(200_000):
            x = (x * 1.0000003) % 9_999_991.0
            x += 1.0000007


def run_contention(workers: int, seconds: float) -> int:
    """Spawn ``workers`` CPU-bound processes for ``seconds`` of matched load."""
    import multiprocessing

    deadline = time.monotonic() + max(0.0, float(seconds))
    procs: list[multiprocessing.Process] = []
    for _ in range(max(1, int(workers))):
        proc = multiprocessing.Process(target=_cpu_spin, args=(deadline,), daemon=True)
        proc.start()
        procs.append(proc)
    print(
        json.dumps(
            {"contention": "started", "workers": len(procs), "seconds": seconds},
            sort_keys=True,
        ),
        flush=True,
    )
    for proc in procs:
        proc.join()
    print(json.dumps({"contention": "done"}, sort_keys=True), flush=True)
    return 0


# ---------------------------------------------------------------------------
# Log-line grammar (matches the app's real diagnostic output).
# ---------------------------------------------------------------------------

# Logging timestamp prefix. The app's file handlers format seconds-precision
# ("2026-09-12 15:04:41 - logger - INFO - ..."); the millisecond fraction is
# optional so both that and "…03,123" forms parse.
_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:[,.](\d{3}))?")
# core/performance/event_loop_recorder.py summary line.
_EVENTLOOP_RE = re.compile(
    r"late_p50_ms=(?P<p50>[-\d.]+) late_p90_ms=(?P<p90>[-\d.]+) "
    r"late_p95_ms=(?P<p95>[-\d.]+) late_p99_ms=(?P<p99>[-\d.]+) "
    r"late_max_ms=(?P<max>[-\d.]+) over_25_ms=(?P<over25>\d+)"
)
# rendering/quick/scene_controller.py structured PERF_HUD line: skip ratio plus the
# reactivity/freshness plane (revision Hz, source age) in one record.
_PERF_HUD_RE = re.compile(
    r"pacer_target_hz=(?P<target_hz>[-\d.]+) pacer_skip_pct=(?P<skip>[-\d.]+) "
    r"transition=(?P<transition>\S+) viz_mode=(?P<viz_mode>\S+) "
    r"viz_draw_fps=(?P<draw_fps>[-\d.]+) viz_revision_hz=(?P<rev_hz>[-\d.]+) "
    r"viz_age_ms=(?P<age_ms>[-\d.]+) viz_geometry_mismatches=(?P<geo>\d+)"
)
# widgets/spotify_visualizer/tick_helpers.py Bubble integration line.
_BUBBLE_RE = re.compile(
    r"integration_ratio=(?P<ratio>[-\d.]+) integration_failures=(?P<fail>\d+)"
)
# Driver phase-window markers and INVALID marker.
_ABC_WINDOW_RE = re.compile(
    r"\[ABC\] condition=(?P<cond>[ABC]) phase=(?P<phase>steady_\w+) "
    r"state=(?P<state>start|end) epoch=(?P<epoch>[\d.]+)"
)
_ABC_CONDITION_RE = re.compile(r"\[ABC\] condition=(?P<cond>[ABC]) ")
_ABC_INVALID_RE = re.compile(
    r"\[ABC\] condition=(?P<cond>[ABC]) INVALID reason=(?P<reason>.+?) epoch="
)


def _line_epoch(line: str) -> float | None:
    match = _TS_RE.match(line)
    if match is None:
        return None
    try:
        base = time.mktime(time.strptime(match.group(1), "%Y-%m-%d %H:%M:%S"))
        millis = match.group(2)
        return base + (int(millis) / 1000.0 if millis else 0.0)
    except (ValueError, OverflowError):
        return None


# ---------------------------------------------------------------------------
# Marker extraction.
# ---------------------------------------------------------------------------

def named_windows_from_markers(path: Path) -> dict[str, tuple[float, float]]:
    """Map each named steady window to its (start, end) epoch pair.

    Unlike a "last pair wins" slice, this keeps ``steady_A`` / ``steady_B`` /
    ``steady_C_pre`` / ``steady_C_post`` distinct so condition C retains BOTH the
    pre-recreation and post-recreation windows.
    """
    starts: dict[str, float] = {}
    windows: dict[str, tuple[float, float]] = {}
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            m = _ABC_WINDOW_RE.search(line)
            if m is None:
                continue
            phase = m.group("phase")
            epoch = float(m.group("epoch"))
            if m.group("state") == "start":
                starts[phase] = epoch
            elif phase in starts:
                windows[phase] = (starts[phase], epoch)
    return windows


def run_condition_from_markers(path: Path) -> str | None:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            m = _ABC_CONDITION_RE.search(line)
            if m is not None:
                return m.group("cond")
    return None


def run_invalid_reason(path: Path) -> str | None:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            m = _ABC_INVALID_RE.search(line)
            if m is not None:
                return m.group("reason").strip()
    return None


# ---------------------------------------------------------------------------
# Per-window scoring — the full metric plane the prose requires.
# ---------------------------------------------------------------------------

def _agg(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {"mean": statistics.fmean(values), "max": max(values),
            "min": min(values), "samples": len(values)}


def score_window(path: Path, start: float, end: float) -> dict[str, object]:
    """Aggregate the diagnostic metric plane within one steady window.

    Retains temporal series for event-loop p99 and frame-pacer skip so the
    classifier can enforce the >=60 s persistence requirement rather than letting
    a transition spike make a whole window count.
    """
    p95s: list[float] = []
    p99_series: list[tuple[float, float]] = []
    maxes: list[float] = []
    over25: list[int] = []
    skip_series: list[tuple[float, float]] = []
    draw_fps: list[float] = []
    rev_hz: list[float] = []
    age_ms: list[float] = []
    ratios: list[float] = []
    failures = 0
    eventloop_samples = 0

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            epoch = _line_epoch(line)
            if epoch is None or epoch < start or epoch > end:
                continue
            offset = epoch - start
            m = _EVENTLOOP_RE.search(line)
            if m is not None:
                p95s.append(float(m.group("p95")))
                p99_series.append((offset, float(m.group("p99"))))
                maxes.append(float(m.group("max")))
                over25.append(int(m.group("over25")))
                eventloop_samples += 1
                continue
            m = _PERF_HUD_RE.search(line)
            if m is not None:
                skip_series.append((offset, float(m.group("skip"))))
                draw_fps.append(float(m.group("draw_fps")))
                rev_hz.append(float(m.group("rev_hz")))
                age_ms.append(float(m.group("age_ms")))
                continue
            m = _BUBBLE_RE.search(line)
            if m is not None:
                ratios.append(float(m.group("ratio")))
                failures += int(m.group("fail"))

    return {
        "window_seconds": round(end - start, 2),
        "eventloop_samples": eventloop_samples,
        "eventloop_p95_ms": _agg(p95s),
        "eventloop_p99_ms": _agg([v for _o, v in p99_series]),
        "eventloop_max_ms": _agg(maxes),
        "eventloop_over_25_ms_total": sum(over25),
        "pacer_skip_pct": _agg([v for _o, v in skip_series]),
        "viz_draw_fps": _agg(draw_fps),
        "viz_revision_hz": _agg(rev_hz),
        "viz_age_ms": _agg(age_ms),
        "bubble_integration_ratio": _agg(ratios),
        "bubble_integration_failures_total": failures,
        # Temporal series retained for persistence analysis.
        "p99_series": [[round(o, 2), v] for o, v in p99_series],
        "skip_series": [[round(o, 2), v] for o, v in skip_series],
    }


def _freshness_ok(window: dict) -> tuple[bool, str | None]:
    rev = window.get("viz_revision_hz")
    age = window.get("viz_age_ms")
    if rev is None or age is None:
        return False, "freshness/reactivity evidence missing (no PERF_HUD lines)"
    if float(rev["mean"]) < REVISION_HZ_FLOOR:
        return False, (
            f"logical revision starved (mean {rev['mean']:.1f} Hz < "
            f"{REVISION_HZ_FLOOR:.0f} Hz): tail not attributable to switching"
        )
    if float(age["mean"]) > SOURCE_AGE_CEILING_MS:
        return False, (
            f"source age degraded (mean {age['mean']:.1f} ms > "
            f"{SOURCE_AGE_CEILING_MS:.0f} ms): tail not attributable to switching"
        )
    return True, None


def score_run(path: Path) -> dict[str, object]:
    """Score one condition's run into per-window metrics, failing closed.

    A run is INVALID (never usable as performance evidence) when: the driver
    emitted an INVALID marker; no ABC markers exist; a required named window is
    missing/incomplete; a scored window is too short or too sparse; or the
    freshness/reactivity plane is missing or unhealthy enough to explain a tail.
    """
    path = Path(path)
    condition = run_condition_from_markers(path)
    invalid = run_invalid_reason(path)
    result: dict[str, object] = {
        "log": str(path),
        "condition": condition,
        "valid": False,
        "reason": None,
        "windows": {},
    }
    if invalid is not None:
        result["reason"] = f"driver marked run INVALID: {invalid}"
        return result
    if condition is None or condition not in CONDITION_WINDOWS:
        result["reason"] = "no ABC condition markers found in log"
        return result

    windows = named_windows_from_markers(path)
    scored: dict[str, object] = {}
    for name in CONDITION_WINDOWS[condition]:
        if name not in windows:
            result["reason"] = f"required scored window missing: {name}"
            result["windows"] = scored
            return result
        start, end = windows[name]
        window = score_window(path, start, end)
        scored[name] = window
        if float(window["window_seconds"]) < MIN_SCORED_SECONDS:
            result["reason"] = (
                f"{name} too short ({window['window_seconds']}s < {MIN_SCORED_SECONDS}s)"
            )
            result["windows"] = scored
            return result
        if int(window["eventloop_samples"]) < MIN_EVENTLOOP_SAMPLES:
            result["reason"] = (
                f"{name} insufficient event-loop samples "
                f"({window['eventloop_samples']} < {MIN_EVENTLOOP_SAMPLES})"
            )
            result["windows"] = scored
            return result
        fresh_ok, fresh_reason = _freshness_ok(window)
        if not fresh_ok:
            result["reason"] = f"{name}: {fresh_reason}"
            result["windows"] = scored
            return result

    result["valid"] = True
    result["windows"] = scored
    return result


# ---------------------------------------------------------------------------
# Classification — persistence + metric-matched recovery over matched reps.
# ---------------------------------------------------------------------------

def _mean(window: dict, key: str) -> float | None:
    agg = window.get(key)
    return None if agg is None else float(agg["mean"])


def _persistent_seconds_above(series: list, threshold: float) -> float:
    """Approximate seconds within a window where a bucketed mean exceeds threshold."""
    buckets: dict[int, list[float]] = {}
    for offset, value in series:
        buckets.setdefault(int(float(offset) // BUCKET_SECONDS), []).append(float(value))
    seconds = 0.0
    for values in buckets.values():
        if statistics.fmean(values) >= threshold:
            seconds += BUCKET_SECONDS
    return seconds


def _regression(window: dict, baseline: dict) -> dict[str, object]:
    """Metric-matched, persistence-checked regression of a window vs its baseline A."""
    a_p99, w_p99 = _mean(baseline, "eventloop_p99_ms"), _mean(window, "eventloop_p99_ms")
    a_skip, w_skip = _mean(baseline, "pacer_skip_pct"), _mean(window, "pacer_skip_pct")

    p99_worse = False
    p99_persist_s = 0.0
    if a_p99 is not None and w_p99 is not None and a_p99 > 0:
        threshold = a_p99 + max(P99_ABS_MS, P99_REL * a_p99)
        p99_persist_s = _persistent_seconds_above(window.get("p99_series", []), threshold)
        p99_worse = (
            (w_p99 - a_p99) >= P99_ABS_MS
            and (w_p99 - a_p99) / a_p99 >= P99_REL
            and p99_persist_s >= PERSIST_SECONDS
        )

    skip_worse = False
    skip_persist_s = 0.0
    if a_skip is not None and w_skip is not None:
        threshold = a_skip + SKIP_PP
        skip_persist_s = _persistent_seconds_above(window.get("skip_series", []), threshold)
        skip_worse = (w_skip - a_skip) >= SKIP_PP and skip_persist_s >= PERSIST_SECONDS

    triggered = [m for m, worse in (("p99", p99_worse), ("skip", skip_worse)) if worse]
    return {
        "regressed": bool(triggered),
        "triggered": triggered,
        "p99_worse": p99_worse,
        "skip_worse": skip_worse,
        "a_p99_ms": a_p99,
        "w_p99_ms": w_p99,
        "p99_persist_s": p99_persist_s,
        "a_skip_pct": a_skip,
        "w_skip_pct": w_skip,
        "skip_persist_s": skip_persist_s,
    }


def _recovery_fraction(cpre: dict, cpost: dict, baseline: dict, metric: str) -> float | None:
    key = "eventloop_p99_ms" if metric == "p99" else "pacer_skip_pct"
    a = _mean(baseline, key)
    pre = _mean(cpre, key)
    post = _mean(cpost, key)
    if a is None or pre is None or post is None:
        return None
    introduced = pre - a
    if introduced <= 0:
        return None
    return (pre - post) / introduced


def _classify_triple(a_run: dict, b_run: dict, c_run: dict) -> dict[str, object]:
    a = a_run["windows"]["steady_A"]
    b = b_run["windows"]["steady_B"]
    cpre = c_run["windows"]["steady_C_pre"]
    cpost = c_run["windows"]["steady_C_post"]

    b_reg = _regression(b, a)
    cpre_reg = _regression(cpre, a)

    # C recovery is measured on the SAME metric(s) that triggered B, and only when
    # C_pre demonstrates the same B-like degradation. Recreation cannot be credited
    # with fixing a regression on a metric that did not regress.
    b_metrics = set(b_reg["triggered"])
    cpre_matches = b_reg["regressed"] and b_metrics.issubset(set(cpre_reg["triggered"]))
    recoveries = {m: _recovery_fraction(cpre, cpost, a, m) for m in b_reg["triggered"]}
    c_cleared = bool(
        cpre_matches
        and recoveries
        and all(v is not None and v >= RECOVERY_FRACTION for v in recoveries.values())
    )

    return {
        "b_vs_a": b_reg,
        "c_pre_vs_a": cpre_reg,
        "c_pre_matches_b": bool(cpre_matches),
        "c_recovery_fraction_by_metric": recoveries,
        "c_cleared": c_cleared,
    }


def classify(a_reps: list[dict], b_reps: list[dict], c_reps: list[dict]) -> dict[str, object]:
    """Apply the phase-P4 threshold, persistence and recovery rules to matched reps."""
    valid_a = [r for r in a_reps if r.get("valid")]
    valid_b = [r for r in b_reps if r.get("valid")]
    valid_c = [r for r in c_reps if r.get("valid")]
    n = min(len(valid_a), len(valid_b), len(valid_c))

    base = {
        "valid_reps": {"A": len(valid_a), "B": len(valid_b), "C": len(valid_c)},
        "total_reps": {"A": len(a_reps), "B": len(b_reps), "C": len(c_reps)},
        "required_reps": REQUIRED_REPS,
    }
    if n < REQUIRED_REPS:
        base.update(
            verdict="insufficient_valid_reps",
            interpretation=(
                "Fewer than three matched VALID repetitions of each condition. "
                "No causal verdict: collect (or repair) runs until at least three "
                "matched valid A/B/C reps exist. Invalid runs (driver INVALID, "
                "missing windows, unhealthy freshness) are excluded, not counted."
            ),
            pairs=[],
        )
        return base

    pairs = [_classify_triple(valid_a[i], valid_b[i], valid_c[i]) for i in range(n)]
    regressed = sum(1 for p in pairs if p["b_vs_a"]["regressed"])
    cleared = sum(1 for p in pairs if p["c_cleared"])
    swap_sensitive = regressed >= 2 and cleared >= 2

    if swap_sensitive:
        verdict = "swap_sensitive"
        interpretation = (
            "B worse than A (persistent >=60 s, freshness healthy) and C_pre shows "
            "the same regression which C_post clears >=70% on the triggering "
            "metric, in >=2/3 reps: switch-accumulation supported. Attribute "
            "ownership (P1 render-host lifecycle) vs invalidation (H1/H2) before "
            "touching perf code; do not add a runtime/layout self-heal."
        )
    elif regressed >= 2 and cleared < 2:
        verdict = "b_regressed_c_did_not_clear"
        interpretation = (
            "B degraded persistently but recreation did not reverse >=70% of the "
            "introduced tail on the triggering metric (or C_pre did not reproduce "
            "it): investigate other Quick-generation state (H4) or contention "
            "(H0/H3); do not assume a GL leak."
        )
    else:
        verdict = "not_reproduced"
        interpretation = (
            "A ~= B (or B did not persistently regress in >=2/3 reps): switching "
            "hypothesis not reproduced for this build/load. Investigate contention/"
            "fixed per-frame cost (H0/H3); mark the swap-leak theory rejected for "
            "the tested build/load rather than carrying it forward."
        )

    base.update(
        matched_reps=n,
        b_vs_a_regressed_count=regressed,
        c_cleared_count=cleared,
        swap_sensitive=swap_sensitive,
        verdict=verdict,
        interpretation=interpretation,
        pairs=pairs,
        note=(
            "Investigation thresholds, not product SLAs. Preserve raw logs so the "
            "thresholds can be challenged. Freshness/reactivity health is enforced "
            "at scoring time: a run whose revision Hz/source age could explain the "
            "tail is INVALID and excluded here, never counted as evidence."
        ),
    )
    return base


def _load_reps(paths: list[str]) -> list[dict]:
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]


# ---------------------------------------------------------------------------
# Auto orchestration — launch the app under the opt-in driver + contention.
# ---------------------------------------------------------------------------

def run_auto(args) -> int:
    """Launch one condition through the real app + driver, then score it.

    Requires a live display/GL surface. The opt-in ``--abc-drive`` driver quits
    the app when the condition completes (exit 0 valid, 3 INVALID), so process
    exit is the run boundary. The run is scored from the driver's named markers;
    a run is reported failed when the child exits non-zero OR scoring finds the
    run invalid.
    """
    import multiprocessing
    import subprocess

    condition = str(args.condition).strip().upper()
    repo_root = Path(__file__).resolve().parents[1]
    base_cmd = args.run_cmd if isinstance(args.run_cmd, list) else shlex.split(args.run_cmd)
    run_cmd = list(base_cmd) + [
        f"--abc-drive={condition}",
        f"--abc-layout-slot={args.layout_slot}",
    ]

    # Matched contention for the whole run (torn down after the app exits).
    deadline = time.monotonic() + float(args.contention_seconds)
    workers = [
        multiprocessing.Process(target=_cpu_spin, args=(deadline,), daemon=True)
        for _ in range(max(0, int(args.workers)))
    ]
    for worker in workers:
        worker.start()

    started = time.time()
    child_exit: int | None = None
    timed_out = False
    try:
        proc = subprocess.Popen(run_cmd, cwd=str(repo_root))
        try:
            child_exit = proc.wait(timeout=float(args.deadline_seconds))
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                child_exit = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                child_exit = proc.wait()
            timed_out = True
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()

    log_path = Path(args.log)
    scored = score_run(log_path) if log_path.exists() else None
    run_valid = bool(scored and scored.get("valid"))
    child_ok = child_exit == 0 and not timed_out
    result = {
        "condition": condition,
        "run_cmd": run_cmd,
        "layout_slot": str(args.layout_slot),
        "child_exit_code": child_exit,
        "child_ok": child_ok,
        "app_timed_out": timed_out,
        "elapsed_s": round(time.time() - started, 1),
        "run_valid": run_valid,
        "scored": scored,
    }
    if not child_ok and scored is not None and scored.get("valid"):
        # A clean-looking score cannot stand over an unexpected/failed child exit.
        result["run_valid"] = False
        result["reason"] = f"child exited unexpectedly (code={child_exit}, timed_out={timed_out})"
    payload = json.dumps(result, sort_keys=True, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    # Write the scored rep too, so it feeds `classify` directly.
    if args.rep_out and scored is not None:
        Path(args.rep_out).write_text(
            json.dumps(scored, sort_keys=True, indent=2), encoding="utf-8"
        )
    print(payload, flush=True)
    return 0 if (child_ok and run_valid) else 1


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="A/B/C harness for the visualizer post-switch tail investigation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_con = sub.add_parser("contention", help="run matched CPU contention")
    p_con.add_argument("--workers", type=int, default=4)
    p_con.add_argument("--seconds", type=float, default=400.0)

    p_score = sub.add_parser("score", help="score one run's named steady windows")
    p_score.add_argument("--log", required=True)
    p_score.add_argument("--out", default=None)

    p_class = sub.add_parser("classify", help="classify matched A/B/C scored reps")
    p_class.add_argument("--a", nargs="+", required=True)
    p_class.add_argument("--b", nargs="+", required=True)
    p_class.add_argument("--c", nargs="+", required=True)
    p_class.add_argument("--out", default=None)

    p_auto = sub.add_parser(
        "auto",
        help="opt-in: launch the app under --abc-drive + contention, then score",
        description=(
            "Launch one condition's run through the real app with the opt-in "
            "in-app driver (--abc-drive=<A|B|C>, which implicitly admits the "
            "boundary telemetry) plus matched contention, wait for the driver to "
            "quit the app, then score the named windows. Requires a live display."
        ),
    )
    p_auto.add_argument("--condition", required=True, choices=["A", "B", "C"])
    p_auto.add_argument(
        "--run-cmd",
        default="python main_mc.py /s --usage --viz --perf",
        help=(
            "canonical RUN launch command as ONE quoted string (shlex-split); "
            "--abc-drive=<condition> and --abc-layout-slot=<slot> are appended. "
            "Use the real RUN argument (script: main_mc.py '/s'; frozen build: the "
            ".scr with '/s'), not a fallthrough. Default targets the MC build so "
            "the saver does not quit on operator input mid-run."
        ),
    )
    p_auto.add_argument("--layout-slot", default="1", dest="layout_slot")
    p_auto.add_argument(
        "--log", required=True, help="app diagnostic log to score after exit"
    )
    p_auto.add_argument("--workers", type=int, default=4)
    p_auto.add_argument("--contention-seconds", type=float, default=600.0)
    p_auto.add_argument(
        "--deadline-seconds", type=float, default=1200.0,
        help="overall watchdog: hard timeout for the app subprocess",
    )
    p_auto.add_argument("--out", default=None, help="full auto result JSON")
    p_auto.add_argument(
        "--rep-out", default=None,
        help="write just the scored rep JSON here (feeds `classify` directly)",
    )

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "contention":
        return run_contention(args.workers, args.seconds)

    if args.command == "score":
        result = score_run(Path(args.log))
        payload = json.dumps(result, sort_keys=True, indent=2)
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
        print(payload, flush=True)
        return 0 if result.get("valid") else 1

    if args.command == "auto":
        return run_auto(args)

    if args.command == "classify":
        result = classify(_load_reps(args.a), _load_reps(args.b), _load_reps(args.c))
        payload = json.dumps(result, sort_keys=True, indent=2)
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
        print(payload, flush=True)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
