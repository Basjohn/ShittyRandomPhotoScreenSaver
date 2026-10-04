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


def fresh_presentation(rows, refresh_hz: dict[int, float]) -> None:
    """What the viewer sees: for each revision's first swap, publish -> swap age, the spacing of fresh swaps
    against the spacing of their logical times, and (given the display refresh) how many refreshes each
    state is held for at the display. Seconds containing a transition or extra frames are included."""
    published, first_swap, logical = {}, {}, {}
    for ts, event, screen, revision, logical_ns, aux in rows:
        key = (screen, aux, revision)
        if event == LOGICAL_PUBLISH:
            published.setdefault(key, ts)
            logical[key] = logical_ns
        elif event == FRAME_SWAP and key in published and key not in first_swap:
            first_swap[key] = ts
    by_screen = defaultdict(list)
    for key, swap in first_swap.items():
        by_screen[key[0]].append((swap, published[key], logical[key]))
    for screen, items in sorted(by_screen.items()):
        items.sort()
        ages = sorted((swap - pub) / 1e6 for swap, pub, _ in items)
        errors = []
        for (s0, _p0, l0), (s1, _p1, l1) in zip(items, items[1:]):
            swap_gap, logical_gap = (s1 - s0) / 1e6, (l1 - l0) / 1e6
            if 0 < logical_gap < 40 and 0 < swap_gap < 60:
                errors.append(abs(swap_gap - logical_gap))
        errors.sort()
        line = (f"fresh screen={screen} n={len(items)} publish->swap median={statistics.median(ages):.2f}ms "
                f"p95={ages[int(0.95 * (len(ages) - 1))]:.2f}ms | spacing error vs logical median="
                f"{statistics.median(errors):.2f}ms p95={errors[int(0.95 * (len(errors) - 1))]:.2f}ms")
        hz = refresh_hz.get(screen)
        if hz:
            period = 1000.0 / hz
            vsyncs = [int(((s - items[0][0]) / 1e6) // period) for s, _p, _l in items]
            holds = defaultdict(int)
            for a, b in zip(vsyncs, vsyncs[1:]):
                holds[min(4, b - a)] += 1
            total = max(1, sum(holds.values()))
            line += " | held refreshes " + " ".join(
                f"{k if k < 4 else '4+'}:{holds[k] / total:.0%}" for k in sorted(holds))
        print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("trace", type=Path)
    parser.add_argument("--seconds", action="store_true", help="print every second's row")
    parser.add_argument("--publish-gap-ms", type=float, default=16.0)
    parser.add_argument("--swap-gap-ms", type=float, default=25.0)
    parser.add_argument("--refresh", action="append", default=[], metavar="SCREEN=HZ",
                        help="display refresh per screen for the held-refresh histogram, e.g. 0=164.835")
    args = parser.parse_args()
    rows = sorted(_records(args.trace))
    if not rows:
        raise SystemExit("empty trace")
    per_second(rows, verbose=args.seconds)
    gaps(rows, publish_ms=args.publish_gap_ms, swap_ms=args.swap_gap_ms)
    refresh = {int(k): float(v) for k, v in (item.split("=", 1) for item in args.refresh)}
    fresh_presentation(rows, refresh)


if __name__ == "__main__":
    main()
