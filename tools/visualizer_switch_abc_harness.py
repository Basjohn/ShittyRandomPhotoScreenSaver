"""Installed-runtime A/B/C causal harness for the post-switch presentation tail (P4).

Authority: ``Docs/Future_Work/Visualizer_Post_Switch_Performance.md`` phase P4.
Guardrail: ``Docs/Guardrails/Performance_Optimization_Contract.md``.

The physical slowdown must be measured in the real product path; synthetic GL
tests cannot prove scheduler/QML/whole-scene behaviour. The installed app has no
remote mode-switch API, so the visualizer interactions in each condition are
**operator-driven**; this harness owns only the parts that can be automated and
kept identical between runs:

  * a repeatable CPU **contention** workload (no game required for the oracle),
  * a **scorer** that extracts the app's own diagnostic metric plane over a
    scored window (event-loop lateness percentiles, frame-pacer skip ratio,
    Bubble integration ratio/failures), and
  * a **classifier** applying the phase-P4 working regression threshold and
    interpretation table to three matched A/B/C repetitions.

It deliberately does not launch/drive the app UI or invent new instrumentation:
built-in PERF/usage/QML output is the runtime evidence plane; this only scores
and classifies it. Tool output can never authorise a change forbidden by the
reactivity/freshness/latency-tail checklist.

Operator protocol (run each condition three times, matched build/settings/audio/
extreme-vertical CUSTOM Bubble geometry/topology/diagnostics/contention):

  For every run:
    1. start the app in RUN mode with diagnostics, e.g.::
         python main.py --run --usage --viz --perf
    2. in another shell, start matched contention for the whole run::
         python tools/visualizer_switch_abc_harness.py contention \
             --workers 4 --seconds 200
    3. perform the condition's visualizer interactions:
         A (control):   recreate into Bubble; do NOT visit other modes; hold the
                        settled extreme-vertical Bubble >= 120 s.
         B (exposure):  from the same start, perform 5 complete cycles of
                        Sphere -> Spectrum -> Oscilloscope -> Sine -> Bubble
                        (each transition completes before the next), then hold
                        the same Bubble >= 120 s. Do NOT recreate the runtime.
         C (recreate):  same B exposure, hold to establish the post-switch tail,
                        then load the same saved layout to force Quick-runtime
                        recreation (verify the runtime generation changes), then
                        hold Bubble >= 120 s.
    4. copy the app log for exactly the scored 120 s window (after excluding the
       first 15 s post-activation/recreation) to a per-run file, then::
         python tools/visualizer_switch_abc_harness.py score \
             --log run_A1.log --out A1.json
    5. after three reps of each condition::
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
import statistics
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Contention workload — repeatable, bounded, cancellable by duration.
# ---------------------------------------------------------------------------

def _cpu_spin(deadline: float) -> None:
    """Bounded floating-point busy-work until ``deadline`` (monotonic seconds)."""
    x = 1.000001
    while time.monotonic() < deadline:
        # A tight arithmetic loop keeps one logical CPU busy without allocating.
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
# Scorer — extract the app's own diagnostic metric plane over a window.
# ---------------------------------------------------------------------------

# Standard logging timestamp prefix, e.g. "2026-09-12 00:19:03,123".
_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})[,.](\d{3})")
_EVENTLOOP_RE = re.compile(
    r"late_p50_ms=(?P<p50>[-\d.]+) late_p90_ms=(?P<p90>[-\d.]+) "
    r"late_p95_ms=(?P<p95>[-\d.]+) late_p99_ms=(?P<p99>[-\d.]+) "
    r"late_max_ms=(?P<max>[-\d.]+) over_25_ms=(?P<over25>\d+)"
)
_PACER_RE = re.compile(r"pacer\s+(?P<hz>[-\d.]+)Hz skip\s+(?P<skip>[-\d.]+)%")
_BUBBLE_RE = re.compile(
    r"integration_ratio=(?P<ratio>[-\d.]+) integration_failures=(?P<fail>\d+)"
)


_ABC_MARKER_RE = re.compile(
    r"\[ABC\] condition=(?P<cond>[ABC]) phase=(?P<phase>\S+) "
    r"state=(?P<state>start|end) epoch=(?P<epoch>[\d.]+)"
)


def steady_window_from_markers(path: Path) -> tuple[float, float] | None:
    """Return the LAST scored steady window (start, end) from the driver markers.

    Condition C emits a pre-switch and a post-recreation steady window; the last
    start/end pair is the one to score. Returns None when no markers are present
    (the operator then supplies a window-scoped log or --since/--until).
    """
    last_start: float | None = None
    window: tuple[float, float] | None = None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            m = _ABC_MARKER_RE.search(line)
            if m is None:
                continue
            epoch = float(m.group("epoch"))
            if m.group("state") == "start":
                last_start = epoch
            elif m.group("state") == "end" and last_start is not None:
                window = (last_start, epoch)
    return window


def _line_epoch(line: str) -> float | None:
    match = _TS_RE.match(line)
    if match is None:
        return None
    try:
        base = time.mktime(time.strptime(match.group(1), "%Y-%m-%d %H:%M:%S"))
        return base + int(match.group(2)) / 1000.0
    except (ValueError, OverflowError):
        return None


def score_log(
    path: Path, *, since_epoch: float | None, until_epoch: float | None
) -> dict[str, object]:
    """Aggregate the diagnostic metric lines within an optional epoch window.

    When timestamps are absent or no window is given, every matching line is
    scored; supply a per-window log slice (or --since/--until) to isolate the
    settled 120 s window after the 15 s exclusion.
    """
    p95s: list[float] = []
    p99s: list[float] = []
    maxes: list[float] = []
    over25: list[int] = []
    skips: list[float] = []
    ratios: list[float] = []
    failures = 0
    eventloop_samples = 0

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            epoch = _line_epoch(line)
            if epoch is not None:
                if since_epoch is not None and epoch < since_epoch:
                    continue
                if until_epoch is not None and epoch > until_epoch:
                    continue
            m = _EVENTLOOP_RE.search(line)
            if m is not None:
                p95s.append(float(m.group("p95")))
                p99s.append(float(m.group("p99")))
                maxes.append(float(m.group("max")))
                over25.append(int(m.group("over25")))
                eventloop_samples += 1
                continue
            m = _PACER_RE.search(line)
            if m is not None:
                skips.append(float(m.group("skip")))
                continue
            m = _BUBBLE_RE.search(line)
            if m is not None:
                ratios.append(float(m.group("ratio")))
                failures += int(m.group("fail"))

    def _agg(values: list[float]) -> dict[str, float] | None:
        if not values:
            return None
        return {
            "mean": statistics.fmean(values),
            "max": max(values),
            "samples": len(values),
        }

    return {
        "log": str(path),
        "window": {"since_epoch": since_epoch, "until_epoch": until_epoch},
        "eventloop_samples": eventloop_samples,
        # Worst-window percentiles are the tail evidence; we keep the max of each
        # reported percentile across the window plus its mean.
        "eventloop_p95_ms": _agg(p95s),
        "eventloop_p99_ms": _agg(p99s),
        "eventloop_max_ms": _agg(maxes),
        "eventloop_over_25_ms_total": sum(over25),
        "pacer_skip_pct": _agg(skips),
        "bubble_integration_ratio": _agg(ratios),
        "bubble_integration_failures_total": failures,
    }


# ---------------------------------------------------------------------------
# Classifier — phase-P4 working regression threshold + interpretation table.
# ---------------------------------------------------------------------------

def _p99(entry: dict) -> float | None:
    agg = entry.get("eventloop_p99_ms")
    return None if agg is None else float(agg["mean"])


def _skip(entry: dict) -> float | None:
    agg = entry.get("pacer_skip_pct")
    return None if agg is None else float(agg["mean"])


def _classify_pair(a: dict, b: dict, c: dict) -> dict[str, object]:
    a_p99, b_p99, c_p99 = _p99(a), _p99(b), _p99(c)
    a_skip, b_skip, c_skip = _skip(a), _skip(b), _skip(c)

    p99_worse = (
        a_p99 is not None
        and b_p99 is not None
        and (b_p99 - a_p99) >= 2.0
        and a_p99 > 0
        and (b_p99 - a_p99) / a_p99 >= 0.35
    )
    skip_worse = (
        a_skip is not None
        and b_skip is not None
        and (b_skip - a_skip) >= 5.0
    )
    b_vs_a_regressed = bool(p99_worse or skip_worse)

    # C must remove >= 70% of the B-vs-A introduced p99 tail delta.
    c_clears = False
    if b_vs_a_regressed and a_p99 is not None and b_p99 is not None and c_p99 is not None:
        introduced = b_p99 - a_p99
        removed = b_p99 - c_p99
        c_clears = introduced > 0 and (removed / introduced) >= 0.70

    return {
        "b_vs_a_regressed": b_vs_a_regressed,
        "p99_worse": bool(p99_worse),
        "skip_worse": bool(skip_worse),
        "c_clears_70pct": bool(c_clears),
        "a_p99_ms": a_p99,
        "b_p99_ms": b_p99,
        "c_p99_ms": c_p99,
        "a_skip_pct": a_skip,
        "b_skip_pct": b_skip,
        "c_skip_pct": c_skip,
    }


def classify(a_reps: list[dict], b_reps: list[dict], c_reps: list[dict]) -> dict[str, object]:
    """Apply the phase-P4 threshold and interpretation table to matched reps."""
    n = min(len(a_reps), len(b_reps), len(c_reps))
    pairs = [_classify_pair(a_reps[i], b_reps[i], c_reps[i]) for i in range(n)]
    regressed = sum(1 for p in pairs if p["b_vs_a_regressed"])
    cleared = sum(1 for p in pairs if p["c_clears_70pct"])

    # "swap-sensitive" only when >= 2 of 3 matched B repetitions regress vs A and
    # the paired C recreation clears >= 70% of that introduced tail delta.
    swap_sensitive = regressed >= 2 and cleared >= 2

    if swap_sensitive:
        verdict = "swap_sensitive"
        interpretation = (
            "B worse than A and C clears it in >=2/3 reps: switch-accumulation "
            "hypothesis supported. Attribute ownership (P1 render-host lifecycle) "
            "vs invalidation (H1/H2) before touching perf code; do not add a "
            "runtime/layout self-heal."
        )
    elif regressed >= 2 and cleared < 2:
        verdict = "b_regressed_c_did_not_clear"
        interpretation = (
            "B degraded but recreation did not reverse >=70% of the tail: "
            "investigate other Quick-generation state (H4) or contention (H0/H3); "
            "do not assume a GL leak."
        )
    else:
        verdict = "not_reproduced"
        interpretation = (
            "A ~= B (or B did not regress in >=2/3 reps): switching hypothesis "
            "not reproduced for this build/load. Investigate contention/fixed "
            "per-frame cost (H0/H3); mark the swap-leak theory rejected for the "
            "tested build/load rather than carrying it forward."
        )

    return {
        "matched_reps": n,
        "b_vs_a_regressed_count": regressed,
        "c_cleared_count": cleared,
        "swap_sensitive": swap_sensitive,
        "verdict": verdict,
        "interpretation": interpretation,
        "pairs": pairs,
        "note": (
            "Investigation thresholds, not product SLAs. Preserve raw logs so the "
            "threshold can be challenged. Freshness/reactivity (revision Hz, "
            "snapshot age, integration ratio) must remain healthy for any "
            "regression call to count."
        ),
    }


def _load_reps(paths: list[str]) -> list[dict]:
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]


# ---------------------------------------------------------------------------
# Auto orchestration — launch the app under the opt-in driver + contention.
# ---------------------------------------------------------------------------

def run_auto(args) -> int:
    """Launch one condition's run through the real app + driver, then score it.

    Requires a live display/GL surface (the app runs in RUN mode). The opt-in
    ``--abc-drive`` driver quits the app when the condition completes, so process
    exit is the run boundary; the log is then scored by the driver's markers.
    """
    import multiprocessing
    import subprocess

    condition = str(args.condition).strip().upper()
    run_cmd = list(args.run_cmd) + [f"--abc-drive={condition}"]

    # Matched contention for the whole run (non-blocking; torn down after exit).
    deadline = time.monotonic() + float(args.contention_seconds)
    workers = [
        multiprocessing.Process(target=_cpu_spin, args=(deadline,), daemon=True)
        for _ in range(max(0, int(args.workers)))
    ]
    for worker in workers:
        worker.start()

    started = time.time()
    try:
        proc = subprocess.Popen(run_cmd, cwd=str(Path(__file__).resolve().parents[1]))
        try:
            proc.wait(timeout=float(args.deadline_seconds))
            timed_out = False
        except subprocess.TimeoutExpired:
            proc.terminate()
            timed_out = True
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()

    log_path = Path(args.log)
    window = steady_window_from_markers(log_path) if log_path.exists() else None
    scored = (
        score_log(log_path, since_epoch=(window or (None, None))[0],
                  until_epoch=(window or (None, None))[1])
        if log_path.exists()
        else None
    )
    result = {
        "condition": condition,
        "run_cmd": run_cmd,
        "app_timed_out": timed_out,
        "elapsed_s": round(time.time() - started, 1),
        "steady_window": window,
        "scored": scored,
    }
    payload = json.dumps(result, sort_keys=True, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload, flush=True)
    return 0 if scored is not None and not timed_out else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="A/B/C harness for the visualizer post-switch tail investigation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_con = sub.add_parser("contention", help="run matched CPU contention")
    p_con.add_argument("--workers", type=int, default=4)
    p_con.add_argument("--seconds", type=float, default=200.0)

    p_score = sub.add_parser("score", help="score one run's diagnostic log window")
    p_score.add_argument("--log", required=True)
    p_score.add_argument("--since-epoch", type=float, default=None)
    p_score.add_argument("--until-epoch", type=float, default=None)
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
            "in-app driver (--abc-drive=<A|B|C>) plus matched contention, wait for "
            "the driver to quit the app, then score the settled window from the "
            "driver's phase markers. Requires a live display/GL surface."
        ),
    )
    p_auto.add_argument("--condition", required=True, choices=["A", "B", "C"])
    p_auto.add_argument(
        "--run-cmd",
        nargs="+",
        default=["python", "main.py", "--run", "--usage", "--viz", "--perf"],
        help="app launch argv; --abc-drive=<condition> is appended automatically",
    )
    p_auto.add_argument(
        "--log",
        required=True,
        help="app diagnostic log to score after exit (driver markers slice it)",
    )
    p_auto.add_argument("--workers", type=int, default=4)
    p_auto.add_argument(
        "--contention-seconds",
        type=float,
        default=400.0,
        help="upper bound for the contention workers (torn down at app exit)",
    )
    p_auto.add_argument(
        "--deadline-seconds",
        type=float,
        default=900.0,
        help="hard timeout for the app subprocess before it is terminated",
    )
    p_auto.add_argument("--out", default=None)

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "contention":
        return run_contention(args.workers, args.seconds)

    if args.command == "score":
        since, until = args.since_epoch, args.until_epoch
        # Auto-slice the settled window from the driver's phase markers when the
        # operator did not pin one explicitly.
        if since is None and until is None:
            marked = steady_window_from_markers(Path(args.log))
            if marked is not None:
                since, until = marked
        result = score_log(Path(args.log), since_epoch=since, until_epoch=until)
        payload = json.dumps(result, sort_keys=True, indent=2)
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
        print(payload, flush=True)
        return 0

    if args.command == "auto":
        return run_auto(args)

    if args.command == "classify":
        result = classify(
            _load_reps(args.a), _load_reps(args.b), _load_reps(args.c)
        )
        payload = json.dumps(result, sort_keys=True, indent=2)
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
        print(payload, flush=True)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
