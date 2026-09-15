"""Summarize SRPSS --frame-trace binary publication/draw timing."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import statistics
import struct

MAGIC = b"SRPSSFT1"
HEADER = struct.Struct("<8sHHI")
RECORD = struct.Struct("<QHhqqq")
EVENT_NAMES = {
    1: "logical_publish",
    2: "gui_wake_deliver",
    3: "gui_snapshot_publish",
    4: "quick_sync_consume",
    5: "render_draw",
    6: "frame_swap",
}


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(round((len(values) - 1) * q)))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    raw = args.trace.read_bytes()
    if len(raw) < HEADER.size:
        raise SystemExit("trace is too short")
    magic, version, record_size, capacity = HEADER.unpack_from(raw, 0)
    if magic != MAGIC or version != 1 or record_size != RECORD.size:
        raise SystemExit("unsupported frame trace format")

    counts = Counter()
    # Every visualizer display owns an independent logical revision counter.
    # Publication identity is therefore screen + runtime generation + revision;
    # merging equal revision numbers across QQuickWindows would fabricate latency.
    publish_by_window_revision: dict[tuple[int, int, int], int] = {}
    unscoped_logical_publishes = 0
    by_window_revision: dict[tuple[int, int, int], dict[int, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    draws_by_screen = Counter()
    swaps_by_screen = Counter()
    unique_draw_revisions: dict[int, set[tuple[int, int]]] = defaultdict(set)
    unique_swap_revisions: dict[int, set[tuple[int, int]]] = defaultdict(set)
    draw_timestamps_by_screen: dict[int, list[int]] = defaultdict(list)
    swap_timestamps_by_screen: dict[int, list[int]] = defaultdict(list)
    records = (len(raw) - HEADER.size) // RECORD.size
    for index in range(records):
        offset = HEADER.size + index * RECORD.size
        ts_ns, event, screen, revision, logical_ns, aux = RECORD.unpack_from(raw, offset)
        counts[event] += 1
        if revision >= 0:
            identity = (int(aux), int(revision))
            if event == 1:
                if screen >= 0:
                    publish_by_window_revision.setdefault(
                        (int(screen), *identity), ts_ns
                    )
                else:
                    # Early WIP traces used screen=-1 for logical publication.
                    # Count them, but never guess a window and silently merge
                    # independent display revision streams.
                    unscoped_logical_publishes += 1
            elif screen >= 0:
                by_window_revision[(int(screen), *identity)][event].append(ts_ns)
        if event == 5:
            draws_by_screen[screen] += 1
            draw_timestamps_by_screen[screen].append(ts_ns)
            if revision >= 0:
                unique_draw_revisions[screen].add((int(aux), revision))
        elif event == 6:
            swaps_by_screen[screen] += 1
            swap_timestamps_by_screen[screen].append(ts_ns)
            if revision >= 0:
                unique_swap_revisions[screen].add((int(aux), revision))

    print(f"records={records} capacity={capacity}")
    for event in sorted(counts):
        print(f"{EVENT_NAMES.get(event, str(event))}: {counts[event]}")
    if unscoped_logical_publishes:
        print(
            "warning: unscoped_logical_publishes="
            f"{unscoped_logical_publishes}; latency correlation skipped for them"
        )
    for screen, draw_count in sorted(draws_by_screen.items()):
        unique = len(unique_draw_revisions[screen])
        print(
            f"screen={screen} draws={draw_count} unique_revisions={unique} "
            f"repeat_draws={max(0, draw_count - unique)}"
        )
        stamps = draw_timestamps_by_screen.get(screen, [])
        if len(stamps) > 1:
            intervals = [
                (right - left) / 1_000_000.0
                for left, right in zip(stamps, stamps[1:])
                if right >= left
            ]
            if intervals:
                print(
                    f"screen={screen} draw_spacing_ms n={len(intervals)} "
                    f"median={statistics.median(intervals):.3f} "
                    f"p95={_pct(intervals, .95):.3f} "
                    f"p99={_pct(intervals, .99):.3f} max={max(intervals):.3f}"
                )

    for screen, swap_count in sorted(swaps_by_screen.items()):
        unique = len(unique_swap_revisions[screen])
        print(
            f"screen={screen} swaps={swap_count} unique_swap_revisions={unique} "
            f"repeat_swap_revisions={max(0, swap_count - unique)}"
        )
        stamps = swap_timestamps_by_screen.get(screen, [])
        if len(stamps) > 1:
            intervals = [
                (right - left) / 1_000_000.0
                for left, right in zip(stamps, stamps[1:])
                if right >= left
            ]
            if intervals:
                print(
                    f"screen={screen} swap_spacing_ms n={len(intervals)} "
                    f"median={statistics.median(intervals):.3f} "
                    f"p95={_pct(intervals, .95):.3f} "
                    f"p99={_pct(intervals, .99):.3f} max={max(intervals):.3f}"
                )

    screens = sorted({key[0] for key in by_window_revision})
    for screen in screens:
        for end_event, label in (
            (2, "publish->gui_wake"),
            (3, "publish->gui_snapshot"),
            (4, "publish->quick_sync"),
            (5, "publish->draw"),
            (6, "publish->frame_swap"),
        ):
            latencies = []
            for (event_screen, generation, revision), events in by_window_revision.items():
                if event_screen != screen:
                    continue
                start = publish_by_window_revision.get(
                    (event_screen, generation, revision)
                )
                ends = events.get(end_event, ())
                if start is None:
                    continue
                # Repeated draws/swaps of one logical revision are exactly the
                # stale-presentation evidence this trace exists to expose. Keep
                # every occurrence in the age distribution rather than only the
                # first timestamp for that revision.
                for end in ends:
                    if end >= start:
                        latencies.append((end - start) / 1_000_000.0)
            if latencies:
                print(
                    f"screen={screen} {label}_ms n={len(latencies)} "
                    f"median={statistics.median(latencies):.3f} "
                    f"p95={_pct(latencies, .95):.3f} "
                    f"p99={_pct(latencies, .99):.3f} max={max(latencies):.3f}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
