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
    7: "quick_sync_ready",
    8: "render_begin",
}


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(round((len(values) - 1) * q)))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument(
        "--timeline-seconds",
        type=float,
        default=0.0,
        help=(
            "emit fixed relative-time freshness windows (for example 15) "
            "without changing runtime tracing"
        ),
    )
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
    payload_bytes = len(raw) - HEADER.size
    records, trailing_bytes = divmod(payload_bytes, RECORD.size)
    if trailing_bytes:
        print(
            f"warning: trailing_bytes={trailing_bytes}; "
            "incomplete final record ignored"
        )
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

    screens = sorted(
        {key[0] for key in publish_by_window_revision}
        | {key[0] for key in by_window_revision}
    )
    for screen in screens:
        published = {
            (generation, revision)
            for event_screen, generation, revision in publish_by_window_revision
            if event_screen == screen
        }
        for end_event, label in (
            (2, "publish->gui_wake"),
            (3, "publish->gui_snapshot"),
            (4, "publish->quick_sync"),
            (7, "publish->quick_sync_ready"),
            (8, "publish->render_begin"),
            (5, "publish->draw"),
            (6, "publish->frame_swap"),
        ):
            if counts.get(end_event, 0) <= 0:
                print(
                    f"screen={screen} {label}_correlation "
                    "unavailable=event_not_present"
                )
                continue
            latencies = []
            matched_occurrences = 0
            unmatched_downstream = 0
            reached_publications: set[tuple[int, int]] = set()
            for (event_screen, generation, revision), events in by_window_revision.items():
                if event_screen != screen:
                    continue
                ends = events.get(end_event, ())
                if not ends:
                    continue
                identity = (generation, revision)
                start = publish_by_window_revision.get(
                    (event_screen, generation, revision)
                )
                if start is None:
                    unmatched_downstream += len(ends)
                    continue
                reached_publications.add(identity)
                # Repeated draws/swaps of one logical revision are exactly the
                # stale-presentation evidence this trace exists to expose. Keep
                # every occurrence in the age distribution rather than only the
                # first timestamp for that revision.
                for end in ends:
                    if end >= start:
                        matched_occurrences += 1
                        latencies.append((end - start) / 1_000_000.0)
                    else:
                        # A downstream timestamp before its publication cannot be
                        # correlated honestly. Surface it rather than fabricating
                        # a negative/zero latency sample.
                        unmatched_downstream += 1
            missing_publications = len(published - reached_publications)
            print(
                f"screen={screen} {label}_correlation "
                f"publications={len(published)} "
                f"matched_occurrences={matched_occurrences} "
                f"unmatched_downstream={unmatched_downstream} "
                f"missing_publications={missing_publications}"
            )
            if latencies:
                print(
                    f"screen={screen} {label}_ms n={len(latencies)} "
                    f"median={statistics.median(latencies):.3f} "
                    f"p95={_pct(latencies, .95):.3f} "
                    f"p99={_pct(latencies, .99):.3f} max={max(latencies):.3f}"
                )

        # Fine-grained stage deltas answer the remaining R-87 question without
        # another logger/timer: is post-sync age spent inside SRPSS's Python/GL
        # render work, or waiting between Qt Quick synchronization and rendering?
        # Pair equal-index occurrences for repeatable stages (render begin/draw)
        # and otherwise use the first ordered occurrence for one-per-publication
        # stages. Missing stages are surfaced by the publication correlations above.
        for start_event, end_event, label in (
            (2, 3, "gui_wake->gui_snapshot"),
            (3, 4, "gui_snapshot->quick_sync"),
            (4, 7, "quick_sync->quick_sync_ready"),
            (7, 8, "quick_sync_ready->render_begin"),
            (8, 5, "render_begin->draw"),
        ):
            deltas: list[float] = []
            for (event_screen, _generation, _revision), stage_events in by_window_revision.items():
                if event_screen != screen:
                    continue
                starts = stage_events.get(start_event, ())
                ends = stage_events.get(end_event, ())
                if not starts or not ends:
                    continue
                if start_event == 8 and end_event == 5:
                    pairs = zip(starts, ends)
                else:
                    pairs = ((starts[0], ends[0]),)
                for start, end in pairs:
                    if end >= start:
                        deltas.append((end - start) / 1_000_000.0)
            if deltas:
                print(
                    f"screen={screen} {label}_ms n={len(deltas)} "
                    f"median={statistics.median(deltas):.3f} "
                    f"p95={_pct(deltas, .95):.3f} "
                    f"p99={_pct(deltas, .99):.3f} max={max(deltas):.3f}"
                )

    timeline_seconds = max(0.0, float(args.timeline_seconds))
    if timeline_seconds > 0.0:
        window_ns = max(1, int(timeline_seconds * 1_000_000_000.0))
        print(f"timeline_window_seconds={timeline_seconds:g}")
        for screen in screens:
            screen_publications = sorted(
                (
                    (generation, revision, ts_ns)
                    for (event_screen, generation, revision), ts_ns
                    in publish_by_window_revision.items()
                    if event_screen == screen
                ),
                key=lambda row: row[2],
            )
            if not screen_publications:
                continue
            origin_ns = screen_publications[0][2]
            last_ns = max(
                [screen_publications[-1][2]]
                + draw_timestamps_by_screen.get(screen, [])
                + swap_timestamps_by_screen.get(screen, [])
            )
            bucket_count = max(1, ((last_ns - origin_ns) // window_ns) + 1)
            for bucket in range(int(bucket_count)):
                start_ns = origin_ns + bucket * window_ns
                end_ns = start_ns + window_ns
                keys = [
                    (generation, revision)
                    for generation, revision, ts_ns in screen_publications
                    if start_ns <= ts_ns < end_ns
                ]
                if not keys:
                    continue
                publish_draw: list[float] = []
                publish_sync: list[float] = []
                sync_ready_to_render: list[float] = []
                render_cost: list[float] = []
                reached_draw = 0
                draw_occurrences = 0
                for generation, revision in keys:
                    identity = (screen, generation, revision)
                    publish_ts = publish_by_window_revision[identity]
                    stage_events = by_window_revision.get(identity, {})
                    syncs = stage_events.get(4, ())
                    if syncs:
                        publish_sync.extend(
                            (ts - publish_ts) / 1_000_000.0
                            for ts in syncs
                            if ts >= publish_ts
                        )
                    draws = stage_events.get(5, ())
                    if draws:
                        reached_draw += 1
                        draw_occurrences += len(draws)
                        publish_draw.extend(
                            (ts - publish_ts) / 1_000_000.0
                            for ts in draws
                            if ts >= publish_ts
                        )
                    sync_ready = stage_events.get(7, ())
                    render_begin = stage_events.get(8, ())
                    if sync_ready and render_begin and render_begin[0] >= sync_ready[0]:
                        sync_ready_to_render.append(
                            (render_begin[0] - sync_ready[0]) / 1_000_000.0
                        )
                    if render_begin and draws:
                        render_cost.extend(
                            (draw - begin) / 1_000_000.0
                            for begin, draw in zip(render_begin, draws)
                            if draw >= begin
                        )
                missing_draw = len(keys) - reached_draw
                repeat_draws = max(0, draw_occurrences - reached_draw)
                fields = [
                    f"screen={screen}",
                    "timeline",
                    f"t={bucket * timeline_seconds:.0f}-{(bucket + 1) * timeline_seconds:.0f}s",
                    f"publications={len(keys)}",
                    f"draw_occurrences={draw_occurrences}",
                    f"repeat_draws={repeat_draws}",
                    f"missing_draw_publications={missing_draw}",
                ]
                if publish_draw:
                    fields.extend(
                        (
                            f"publish_draw_median_ms={statistics.median(publish_draw):.3f}",
                            f"publish_draw_p95_ms={_pct(publish_draw, .95):.3f}",
                            f"publish_draw_p99_ms={_pct(publish_draw, .99):.3f}",
                        )
                    )
                if publish_sync:
                    fields.append(f"publish_sync_p95_ms={_pct(publish_sync, .95):.3f}")
                if sync_ready_to_render:
                    fields.append(
                        "sync_ready_render_begin_p95_ms="
                        f"{_pct(sync_ready_to_render, .95):.3f}"
                    )
                if render_cost:
                    fields.append(
                        f"render_begin_draw_p95_ms={_pct(render_cost, .95):.3f}"
                    )
                print(" ".join(fields))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
