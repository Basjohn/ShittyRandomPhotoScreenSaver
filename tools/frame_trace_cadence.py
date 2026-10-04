"""Visualizer presentation cadence from an SRPSS ``--frame-trace``: python tools/frame_trace_cadence.py <trace>

Two views, both from the binary trace (read through ``tools/frame_trace_report.py``):

* per second and screen: Visualizer publications, draws, repeated draws of an already drawn revision, and
  background (transition) renders on that screen and the other, then the repeat rate by transition state;
* gaps: publication gaps and swap gaps above a threshold, how often they come and how periodic they are,
  plus the logical dt the simulation integrated.

Current_Plan "Next up" N1 (Bubble micro-flicker, DevCurve travel jerk) starts here.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.frame_trace_report import HEADER, RECORD, _read_trace_chain  # noqa: E402

LOGICAL_PUBLISH, RENDER_DRAW, FRAME_SWAP, BACKGROUND_RENDER_BEGIN = 1, 5, 6, 19


def _records(path: Path):
    raw, _segments = _read_trace_chain(path)
    for offset in range(HEADER.size, len(raw) - RECORD.size + 1, RECORD.size):
        ts, event, screen, revision, logical_ns, aux = RECORD.unpack_from(raw, offset)
        if ts:
            yield ts, event, screen, revision, logical_ns, aux


def per_second(rows, *, verbose: bool) -> None:
    t0 = rows[0][0]
    windows = defaultdict(lambda: defaultdict(int))
    seen = defaultdict(set)
    for ts, event, screen, revision, _logical, aux in rows:
        key = (int((ts - t0) / 1e9), screen)
        if event == LOGICAL_PUBLISH:
            windows[key]["pub"] += 1
        elif event == RENDER_DRAW:
            windows[key]["draw"] += 1
            # Revisions restart with each runtime generation (aux), as frame_trace_report keys them.
            if (aux, revision) in seen[screen]:
                windows[key]["repeat"] += 1
            seen[screen].add((aux, revision))
        elif event == BACKGROUND_RENDER_BEGIN:
            windows[key]["bg"] += 1
    screens = sorted({screen for _second, screen in windows})
    seconds = sorted({second for second, _screen in windows})
    if verbose:
        print("sec | " + " | ".join(f"s{s} pub draw rep bg" for s in screens))
    by_state = defaultdict(lambda: [0, 0, 0])
    for second in seconds:
        cells = [windows[(second, screen)] for screen in screens]
        if verbose:
            print(f"{second:4d} | " + " | ".join(
                f"{c['pub']:4d} {c['draw']:4d} {c['repeat']:4d} {c['bg']:4d}" for c in cells))
        for screen, cell in zip(screens, cells):
            if cell["pub"] < 50:
                continue
            other = any(windows[(second, s)]["bg"] for s in screens if s != screen)
            state = by_state[(screen, cell["bg"] > 0, other)]
            state[0] += 1
            state[1] += cell["draw"]
            state[2] += cell["repeat"]
    print("repeats by (screen, own transition, other transition): seconds, draws/s, repeats/s")
    for (screen, own, other), (n, draws, repeats) in sorted(by_state.items()):
        print(f"  screen={screen} own={own!s:5} other={other!s:5} seconds={n:4d} "
              f"draws/s={draws / n:6.1f} repeats/s={repeats / n:6.1f}")


def _gap_report(name: str, series, threshold_ms: float) -> None:
    for screen, stamps in sorted(series.items()):
        stamps.sort()
        gaps = [((b - a) / 1e6, b) for a, b in zip(stamps, stamps[1:]) if 0 < (b - a) / 1e6 < 1000]
        if not gaps:
            continue
        big = [(gap, at) for gap, at in gaps if gap > threshold_ms]
        spacing = sorted((b[1] - a[1]) / 1e9 for a, b in zip(big, big[1:]) if (b[1] - a[1]) / 1e9 < 20)
        duration = max(1e-9, (stamps[-1] - stamps[0]) / 1e9)
        line = (f"{name} screen={screen} n={len(gaps)} median={statistics.median(g for g, _ in gaps):.2f}ms "
                f">{threshold_ms:g}ms={len(big)} ({len(big) / duration:.2f}/s) max={max(g for g, _ in gaps):.1f}ms")
        if spacing:
            line += (f" spacing median={statistics.median(spacing):.2f}s "
                     f"p25/p75={spacing[len(spacing) // 4]:.2f}/{spacing[3 * len(spacing) // 4]:.2f}s")
        print(line)
        if big:
            print("   largest ms: " + ", ".join(f"{g:.1f}" for g, _ in sorted(big, reverse=True)[:8]))


def gaps(rows, *, publish_ms: float, swap_ms: float) -> None:
    publications, swaps, logical = defaultdict(list), defaultdict(list), defaultdict(list)
    for ts, event, screen, _revision, logical_ns, _aux in rows:
        if event == LOGICAL_PUBLISH:
            publications[screen].append(ts)
            logical[screen].append(logical_ns)
        elif event == FRAME_SWAP:
            swaps[screen].append(ts)
    _gap_report("publish", publications, publish_ms)
    for screen, stamps in sorted(logical.items()):
        dts = sorted((b - a) / 1e6 for a, b in zip(stamps, stamps[1:]) if 0 < (b - a) / 1e6 < 1000)
        if dts:
            print(f"logical dt screen={screen} median={statistics.median(dts):.2f}ms "
                  f"p99={dts[int(0.99 * (len(dts) - 1))]:.2f}ms >16ms={sum(d > 16 for d in dts)} "
                  f">25ms={sum(d > 25 for d in dts)}")
    _gap_report("swap", swaps, swap_ms)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("trace", type=Path)
    parser.add_argument("--seconds", action="store_true", help="print every second's row")
    parser.add_argument("--publish-gap-ms", type=float, default=16.0)
    parser.add_argument("--swap-gap-ms", type=float, default=25.0)
    args = parser.parse_args()
    rows = sorted(_records(args.trace))
    if not rows:
        raise SystemExit("empty trace")
    per_second(rows, verbose=args.seconds)
    gaps(rows, publish_ms=args.publish_gap_ms, swap_ms=args.swap_gap_ms)


if __name__ == "__main__":
    main()
