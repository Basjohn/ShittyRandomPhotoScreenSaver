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
    9: "render_prep_ready",
    10: "render_host_begin",
    11: "render_gl_state_ready",
    12: "render_mode_begin",
    13: "render_mode_ready",
    14: "render_host_ready",
    15: "audio_analysis_begin",
    16: "audio_analysis_ready",
    17: "audio_smooth_begin",
    18: "audio_smooth_ready",
    19: "background_render_begin",
    20: "background_texture_ready",
    21: "background_draw_begin",
    22: "background_draw_ready",
    23: "background_render_ready",
    24: "clip_begin_resources_ready",
    25: "clip_begin_inherited_ready",
    26: "clip_begin_setup_ready",
    27: "clip_begin_mask_state_ready",
    28: "clip_begin_mask_draw_ready",
    29: "clip_begin_mask_restore_ready",
    30: "clip_end_setup_ready",
    31: "clip_end_mask_state_ready",
    32: "clip_end_mask_draw_ready",
    33: "clip_end_mask_restore_ready",
    34: "clip_end_inherited_ready",
    35: "clip_begin_inherited_scissor_ready",
    36: "clip_begin_inherited_front_ready",
    37: "clip_begin_mask_bindings_ready",
    38: "clip_begin_mask_gl_state_applied",
    39: "clip_begin_mask_uniforms_ready",
    40: "clip_end_mask_bindings_ready",
    41: "clip_end_mask_gl_state_applied",
    42: "clip_end_mask_uniforms_ready",
    43: "clip_begin_shared_gl_state_ready",
    44: "gui_presentation_commit_ready",
    45: "gui_present_request_ready",
    46: "quick_sync_item_entry",
    47: "quick_sync_snapshot_acquired",
    48: "quick_before_frame_begin",
    49: "quick_before_synchronizing",
    50: "quick_after_synchronizing",
    51: "quick_before_rendering",
    52: "quick_before_render_pass_recording",
    53: "quick_after_render_pass_recording",
    54: "quick_after_rendering",
}

RENDER_CYCLE_EVENT_IDS = frozenset(range(48, 55))
RENDER_CYCLE_STAGES = (
    (48, 49, "before_frame_begin->before_synchronizing"),
    (49, 50, "before_synchronizing->after_synchronizing"),
    (50, 51, "after_synchronizing->before_rendering"),
    (51, 52, "before_rendering->before_render_pass"),
    (52, 53, "render_pass_recording"),
    (53, 54, "after_render_pass->after_rendering"),
)


CLIP_BEGIN_STAGES = (
    (9, 24, "resource_guard"),
    (24, 25, "inherited_state_capture"),
    (25, 26, "scissor_stencil_setup"),
    (26, 27, "mask_state_capture"),
    (27, 28, "mask_draw"),
    (28, 29, "mask_local_restore"),
    (29, 10, "final_stencil_admission"),
)
CLIP_END_STAGES = (
    (14, 30, "stencil_teardown_setup"),
    (30, 31, "mask_state_capture"),
    (31, 32, "mask_draw"),
    (32, 33, "mask_local_restore"),
    (33, 34, "inherited_state_restore"),
    (34, 5, "post_clip_bookkeeping"),
)

# CHK25 leaves the CHK24 aggregate stage contract intact for historical traces
# and emits this deeper split only when the new optional markers are present.
CLIP_BEGIN_REFINED_STAGES = (
    (9, 24, "resource_guard"),
    (24, 35, "inherited_scissor_capture"),
    (35, 36, "inherited_front_stencil_capture"),
    (36, 25, "inherited_back_stencil_capture"),
    (25, 26, "scissor_stencil_setup"),
    (26, 37, "mask_binding_state_capture"),
    (37, 27, "mask_flag_state_capture"),
    (27, 38, "mask_state_programming"),
    (38, 39, "mask_uniform_upload"),
    (39, 28, "mask_draw_call"),
    (28, 29, "mask_local_restore"),
    (29, 10, "final_stencil_admission"),
)

# CHK26 carries one non-stencil state snapshot through mask -> mode -> mask.
# Event 43 isolates the additional blend-function/equation queries that used to
# live in the render-host capture so the old CHK25 marker meanings remain intact.
CLIP_BEGIN_REFINED_SHARED_STAGES = (
    (9, 24, "resource_guard"),
    (24, 35, "inherited_scissor_capture"),
    (35, 36, "inherited_front_stencil_capture"),
    (36, 25, "inherited_back_stencil_capture"),
    (25, 26, "scissor_stencil_setup"),
    (26, 37, "mask_binding_state_capture"),
    (37, 27, "mask_flag_state_capture"),
    (27, 43, "shared_render_state_extra_capture"),
    (43, 38, "mask_state_programming"),
    (38, 39, "mask_uniform_upload"),
    (39, 28, "mask_draw_call"),
    (28, 29, "mask_local_restore"),
    (29, 10, "final_stencil_admission"),
)

CLIP_END_REFINED_STAGES = (
    (14, 30, "stencil_teardown_setup"),
    (30, 40, "mask_binding_state_capture"),
    (40, 31, "mask_flag_state_capture"),
    (31, 41, "mask_state_programming"),
    (41, 42, "mask_uniform_upload"),
    (42, 32, "mask_draw_call"),
    (32, 33, "mask_local_restore"),
    (33, 34, "inherited_state_restore"),
    (34, 5, "post_clip_bookkeeping"),
)




def _trace_segment_paths(path: Path) -> list[Path]:
    """Return retained rolling trace segments oldest -> newest.

    Legacy/small traces remain a single ``screensaver_frame_trace.bin``.  The
    soak-safe writer keeps numeric siblings where ``.1`` is the immediately
    previous segment, so descending numeric order reconstructs chronology.
    """

    path = Path(path)
    prefix = f"{path.stem}."
    suffix = path.suffix
    rotated: list[tuple[int, Path]] = []
    for candidate in path.parent.glob(f"{path.stem}.*{suffix}"):
        name = candidate.name
        if not name.startswith(prefix) or not name.endswith(suffix):
            continue
        middle = name[len(prefix): -len(suffix)] if suffix else name[len(prefix):]
        if middle.isdigit():
            rotated.append((int(middle), candidate))
    paths = [candidate for _index, candidate in sorted(rotated, reverse=True)]
    if path.is_file():
        paths.append(path)
    return paths


def _read_trace_chain(path: Path) -> tuple[bytes, int]:
    paths = _trace_segment_paths(path)
    if not paths:
        raise SystemExit(f"trace does not exist: {path}")
    payloads: list[bytes] = []
    first_header: bytes | None = None
    for segment in paths:
        raw = segment.read_bytes()
        if len(raw) < HEADER.size:
            raise SystemExit(f"trace segment is too short: {segment}")
        magic, version, record_size, _capacity = HEADER.unpack_from(raw, 0)
        if magic != MAGIC or version != 1 or record_size != RECORD.size:
            raise SystemExit(f"unsupported frame trace format: {segment}")
        if first_header is None:
            first_header = raw[:HEADER.size]
        payloads.append(raw[HEADER.size:])
    assert first_header is not None
    return first_header + b"".join(payloads), len(paths)

def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(round((len(values) - 1) * q)))]


def _paired_worker_intervals(
    worker_events: dict[tuple[int, int], dict[int, list[int]]],
    start_event: int,
    end_event: int,
) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    for events in worker_events.values():
        starts = events.get(start_event, ())
        ends = events.get(end_event, ())
        for start, end in zip(starts, ends):
            if end >= start:
                intervals.append((start, end))
    intervals.sort()
    return intervals


def _interval_overlap_ns(
    start_ns: int,
    end_ns: int,
    intervals: list[tuple[int, int]],
) -> int:
    if end_ns <= start_ns or not intervals:
        return 0
    total = 0
    for left, right in intervals:
        if right <= start_ns:
            continue
        if left >= end_ns:
            break
        total += max(0, min(end_ns, right) - max(start_ns, left))
    return total


def _print_render_gap_overlap(
    *,
    screen: int,
    gaps: list[tuple[int, int]],
    label: str,
    intervals: list[tuple[int, int]],
) -> None:
    if not gaps or not intervals:
        return
    durations_ms = [(end - start) / 1_000_000.0 for start, end in gaps]
    threshold_ms = _pct(durations_ms, .95)
    for scope, scoped in (
        ("all", gaps),
        (
            "p95_tail",
            [
                (start, end)
                for start, end in gaps
                if (end - start) / 1_000_000.0 >= threshold_ms
            ],
        ),
    ):
        overlap_ns = [
            _interval_overlap_ns(start, end, intervals)
            for start, end in scoped
        ]
        overlapping = sum(1 for value in overlap_ns if value > 0)
        total_gap_ns = sum(end - start for start, end in scoped)
        total_overlap_ns = sum(overlap_ns)
        overlapping_gap_ms = [
            (end - start) / 1_000_000.0
            for (start, end), value in zip(scoped, overlap_ns)
            if value > 0
        ]
        nonoverlapping_gap_ms = [
            (end - start) / 1_000_000.0
            for (start, end), value in zip(scoped, overlap_ns)
            if value == 0
        ]
        conditional = ""
        if overlapping_gap_ms:
            conditional += (
                f" overlap_gap_median_ms={statistics.median(overlapping_gap_ms):.3f}"
            )
        if nonoverlapping_gap_ms:
            conditional += (
                f" nonoverlap_gap_median_ms={statistics.median(nonoverlapping_gap_ms):.3f}"
            )
        print(
            f"screen={screen} sync_ready_render_begin_{label}_overlap "
            f"scope={scope} gaps={len(scoped)} overlap_gaps={overlapping} "
            f"overlap_gap_pct={(100.0 * overlapping / len(scoped)) if scoped else 0.0:.2f} "
            f"overlap_time_pct={(100.0 * total_overlap_ns / total_gap_ns) if total_gap_ns else 0.0:.2f}"
            f"{conditional}"
        )


def _print_clip_stage_breakdown(
    *,
    screen: int,
    by_window_revision: dict[tuple[int, int, int], dict[int, list[int]]],
    phase: str,
    parent_start_event: int,
    parent_end_event: int,
    parent_label: str,
    stages: tuple[tuple[int, int, str], ...],
) -> None:
    parent_occurrences = 0
    complete_occurrences = 0
    for (event_screen, _generation, _revision), stage_events in by_window_revision.items():
        if event_screen != screen:
            continue
        parent_occurrences += min(
            len(stage_events.get(parent_start_event, ())),
            len(stage_events.get(parent_end_event, ())),
        )
        if all(stage_events.get(event) for pair in stages for event in pair[:2]):
            complete_occurrences += min(
                *(len(stage_events.get(event, ())) for pair in stages for event in pair[:2]),
                len(stage_events.get(parent_start_event, ())),
                len(stage_events.get(parent_end_event, ())),
            )
    if complete_occurrences:
        print(
            f"screen={screen} clip_{phase}_coverage "
            f"parent_interval={parent_label} parent_n={parent_occurrences} "
            f"fully_attributed_n={complete_occurrences}"
        )

    for start_event, end_event, label in stages:
        stage_ns: list[int] = []
        parent_ns: list[int] = []
        for (event_screen, _generation, _revision), stage_events in by_window_revision.items():
            if event_screen != screen:
                continue
            starts = stage_events.get(start_event, ())
            ends = stage_events.get(end_event, ())
            parent_starts = stage_events.get(parent_start_event, ())
            parent_ends = stage_events.get(parent_end_event, ())
            count = min(len(starts), len(ends), len(parent_starts), len(parent_ends))
            for index in range(count):
                start = starts[index]
                end = ends[index]
                parent_start = parent_starts[index]
                parent_end = parent_ends[index]
                if end < start or parent_end < parent_start:
                    continue
                if start < parent_start or end > parent_end:
                    continue
                stage_ns.append(end - start)
                parent_ns.append(parent_end - parent_start)
        if not stage_ns:
            continue
        values_ms = [value / 1_000_000.0 for value in stage_ns]
        parent_total_ns = sum(parent_ns)
        share = (100.0 * sum(stage_ns) / parent_total_ns) if parent_total_ns else 0.0
        print(
            f"screen={screen} clip_{phase}_stage={label} "
            f"parent_interval={parent_label} n={len(values_ms)} "
            f"median_ms={statistics.median(values_ms):.3f} "
            f"p95_ms={_pct(values_ms, .95):.3f} "
            f"p99_ms={_pct(values_ms, .99):.3f} "
            f"parent_total_share_pct={share:.2f}"
        )


def _print_clip_tail_breakdown(
    *,
    screen: int,
    by_window_revision: dict[tuple[int, int, int], dict[int, list[int]]],
    phase: str,
    parent_start_event: int,
    parent_end_event: int,
    parent_label: str,
    stages: tuple[tuple[int, int, str], ...],
) -> None:
    rows: list[tuple[int, dict[str, int]]] = []
    for (event_screen, _generation, _revision), stage_events in by_window_revision.items():
        if event_screen != screen:
            continue
        parent_starts = stage_events.get(parent_start_event, ())
        parent_ends = stage_events.get(parent_end_event, ())
        event_counts = [len(parent_starts), len(parent_ends)]
        for start_event, end_event, _label in stages:
            event_counts.extend((
                len(stage_events.get(start_event, ())),
                len(stage_events.get(end_event, ())),
            ))
        count = min(event_counts) if event_counts else 0
        for index in range(count):
            parent_start = parent_starts[index]
            parent_end = parent_ends[index]
            if parent_end < parent_start:
                continue
            values: dict[str, int] = {}
            valid = True
            for start_event, end_event, label in stages:
                start = stage_events[start_event][index]
                end = stage_events[end_event][index]
                if end < start or start < parent_start or end > parent_end:
                    valid = False
                    break
                values[label] = end - start
            if valid:
                rows.append((parent_end - parent_start, values))
    if not rows:
        return
    threshold_ns = _pct([parent for parent, _values in rows], .95)
    tail = [(parent, values) for parent, values in rows if parent >= threshold_ns]
    if not tail:
        return
    total_parent_ns = sum(parent for parent, _values in tail)
    print(
        f"screen={screen} clip_{phase}_p95_tail "
        f"parent_interval={parent_label} threshold_ms={threshold_ns / 1_000_000.0:.3f} "
        f"tail_n={len(tail)}"
    )
    dominant: Counter[str] = Counter()
    for _parent, values in tail:
        if values:
            dominant[max(values, key=values.get)] += 1
    for _start_event, _end_event, label in stages:
        values_ns = [values[label] for _parent, values in tail]
        values_ms = [value / 1_000_000.0 for value in values_ns]
        share = (100.0 * sum(values_ns) / total_parent_ns) if total_parent_ns else 0.0
        print(
            f"screen={screen} clip_{phase}_p95_tail_stage={label} "
            f"n={len(values_ms)} median_ms={statistics.median(values_ms):.3f} "
            f"p95_ms={_pct(values_ms, .95):.3f} "
            f"parent_tail_share_pct={share:.2f} "
            f"dominant_frames={dominant.get(label, 0)}"
        )

def _summary_ms(values_ns: list[int]) -> tuple[float, float, float] | None:
    if not values_ns:
        return None
    values_ms = [value / 1_000_000.0 for value in values_ns]
    return (
        statistics.median(values_ms),
        _pct(values_ms, .95),
        _pct(values_ms, .99),
    )


def _print_render_cycle_attribution(
    *,
    screen: int,
    render_cycle_events: dict[tuple[int, int, int], dict[int, list[int]]],
    by_window_revision: dict[tuple[int, int, int], dict[int, list[int]]],
) -> None:
    """Report Qt-native frame phases and bridge them to visualizer markers.

    Render-cycle identities are intentionally separate from visualizer logical
    revisions. Cross-boundary attribution is reconstructed by containment in the
    same QQuickWindow synchronization/render cycle.
    """

    cycles: list[dict[int, int]] = []
    for (event_screen, _generation, _cycle), events in render_cycle_events.items():
        if event_screen != screen:
            continue
        row: dict[int, int] = {}
        for event, stamps in events.items():
            if stamps:
                row[event] = stamps[0]
        if 48 in row:
            cycles.append(row)
    cycles.sort(key=lambda row: row[48])
    if not cycles:
        return

    print(f"screen={screen} quick_render_cycles={len(cycles)}")
    for start_event, end_event, label in RENDER_CYCLE_STAGES:
        values = [
            row[end_event] - row[start_event]
            for row in cycles
            if start_event in row
            and end_event in row
            and row[end_event] >= row[start_event]
        ]
        summary = _summary_ms(values)
        if summary is None:
            continue
        median, p95, p99 = summary
        print(
            f"screen={screen} quick_phase={label} n={len(values)} "
            f"median_ms={median:.3f} p95_ms={p95:.3f} p99_ms={p99:.3f}"
        )

    # Index cycles by synchronization start. updatePaintNode() must occur between
    # beforeSynchronizing and afterSynchronizing in the threaded render loop.
    sync_cycles = [row for row in cycles if 49 in row and 50 in row]
    sync_starts = [row[49] for row in sync_cycles]

    def cycle_for_sync_timestamp(ts_ns: int) -> dict[int, int] | None:
        import bisect
        index = bisect.bisect_right(sync_starts, ts_ns) - 1
        if index < 0:
            return None
        row = sync_cycles[index]
        if row[49] <= ts_ns <= row[50]:
            return row
        return None

    admission_parts: dict[str, list[int]] = defaultdict(list)
    post_sync_parts: dict[str, list[int]] = defaultdict(list)
    for (event_screen, _generation, _revision), events in by_window_revision.items():
        if event_screen != screen:
            continue
        requests = events.get(45, ())
        entries = events.get(46, ())
        ready = events.get(7, ())
        render_begin = events.get(8, ())
        for request_ts, entry_ts in zip(requests, entries):
            if entry_ts < request_ts:
                continue
            row = cycle_for_sync_timestamp(entry_ts)
            if row is None:
                continue
            if 48 in row and row[48] >= request_ts:
                admission_parts["present_request->before_frame_begin"].append(
                    row[48] - request_ts
                )
                if 49 in row and row[49] >= row[48]:
                    admission_parts["before_frame_begin->before_synchronizing"].append(
                        row[49] - row[48]
                    )
            if 49 in row and entry_ts >= row[49]:
                admission_parts["before_synchronizing->item_entry"].append(
                    entry_ts - row[49]
                )

        for ready_ts, render_ts in zip(ready, render_begin):
            if render_ts < ready_ts:
                continue
            row = cycle_for_sync_timestamp(ready_ts)
            if row is None:
                continue
            if 50 in row and row[50] >= ready_ts:
                post_sync_parts["sync_ready->after_synchronizing"].append(
                    row[50] - ready_ts
                )
            if 50 in row and 51 in row and row[51] >= row[50]:
                post_sync_parts["after_synchronizing->before_rendering"].append(
                    row[51] - row[50]
                )
            if 51 in row and 52 in row and row[52] >= row[51]:
                post_sync_parts["before_rendering->before_render_pass"].append(
                    row[52] - row[51]
                )
            if 52 in row and render_ts >= row[52]:
                post_sync_parts["before_render_pass->visualizer_render_begin"].append(
                    render_ts - row[52]
                )

    for family, parts in (("quick_admission", admission_parts), ("quick_post_sync", post_sync_parts)):
        for label, values in parts.items():
            summary = _summary_ms(values)
            if summary is None:
                continue
            median, p95, p99 = summary
            print(
                f"screen={screen} {family}_stage={label} n={len(values)} "
                f"median_ms={median:.3f} p95_ms={p95:.3f} p99_ms={p99:.3f}"
            )


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
    raw, trace_segments = _read_trace_chain(args.trace)
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
    worker_events: dict[tuple[int, int], dict[int, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    # Background QSGRenderNode events are independent of visualizer logical
    # revisions. Their revision field is a node-local render sequence and aux is
    # the active transition run id (0 for steady background rendering).
    background_events: dict[tuple[int, int], dict[int, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    background_transition_by_key: dict[tuple[int, int], int] = {}
    # QQuickWindow phase events use a render-cycle sequence, not a visualizer
    # logical revision. Keep them in a distinct identity namespace.
    render_cycle_events: dict[tuple[int, int, int], dict[int, list[int]]] = defaultdict(
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
        if event in (15, 16, 17, 18) and revision >= 0:
            worker_events[(int(aux), int(revision))][event].append(ts_ns)
        if event in RENDER_CYCLE_EVENT_IDS and screen >= 0 and revision >= 0:
            render_cycle_events[(int(screen), int(aux), int(revision))][event].append(ts_ns)
        elif event in (19, 20, 21, 22, 23) and screen >= 0 and revision >= 0:
            key = (int(screen), int(revision))
            background_events[key][event].append(ts_ns)
            background_transition_by_key[key] = int(aux)
        elif revision >= 0:
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
    if trace_segments > 1:
        print(f"trace_segments={trace_segments} retention=rolling_oldest_to_newest")
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

    audio_analysis_intervals = _paired_worker_intervals(worker_events, 15, 16)
    audio_smooth_intervals = _paired_worker_intervals(worker_events, 17, 18)
    if audio_analysis_intervals:
        durations = [
            (end - start) / 1_000_000.0
            for start, end in audio_analysis_intervals
        ]
        print(
            "audio_analysis_ms "
            f"n={len(durations)} median={statistics.median(durations):.3f} "
            f"p95={_pct(durations, .95):.3f} p99={_pct(durations, .99):.3f} "
            f"max={max(durations):.3f}"
        )
    if audio_smooth_intervals:
        durations = [
            (end - start) / 1_000_000.0
            for start, end in audio_smooth_intervals
        ]
        print(
            "audio_smooth_ms "
            f"n={len(durations)} median={statistics.median(durations):.3f} "
            f"p95={_pct(durations, .95):.3f} p99={_pct(durations, .99):.3f} "
            f"max={max(durations):.3f}"
        )

    background_intervals_by_screen: dict[int, list[tuple[int, int]]] = defaultdict(list)
    background_idle_intervals_by_screen: dict[int, list[tuple[int, int]]] = defaultdict(list)
    background_transition_intervals_by_screen: dict[int, list[tuple[int, int]]] = defaultdict(list)
    if background_events:
        for screen in sorted({key[0] for key in background_events}):
            screen_keys = sorted(
                (key for key in background_events if key[0] == screen),
                key=lambda key: key[1],
            )
            for start_event, end_event, label in (
                (19, 20, "background_begin->texture_ready"),
                (20, 21, "background_texture_ready->draw_begin"),
                (21, 22, "background_draw_begin->draw_ready"),
                (22, 23, "background_draw_ready->render_ready"),
                (19, 23, "background_render_begin->render_ready"),
            ):
                values: list[float] = []
                idle_values: list[float] = []
                transition_values: list[float] = []
                for key in screen_keys:
                    events = background_events[key]
                    starts = events.get(start_event, ())
                    ends = events.get(end_event, ())
                    if not starts or not ends:
                        continue
                    start, end = starts[0], ends[0]
                    if end < start:
                        continue
                    value = (end - start) / 1_000_000.0
                    values.append(value)
                    if background_transition_by_key.get(key, 0) > 0:
                        transition_values.append(value)
                    else:
                        idle_values.append(value)
                    if start_event == 19 and end_event == 23:
                        interval = (start, end)
                        background_intervals_by_screen[screen].append(interval)
                        if background_transition_by_key.get(key, 0) > 0:
                            background_transition_intervals_by_screen[screen].append(interval)
                        else:
                            background_idle_intervals_by_screen[screen].append(interval)
                if values:
                    print(
                        f"screen={screen} {label}_ms n={len(values)} "
                        f"median={statistics.median(values):.3f} "
                        f"p95={_pct(values, .95):.3f} "
                        f"p99={_pct(values, .99):.3f} max={max(values):.3f}"
                    )
                if idle_values and transition_values:
                    print(
                        f"screen={screen} {label}_split "
                        f"idle_n={len(idle_values)} idle_median={statistics.median(idle_values):.3f} "
                        f"idle_p95={_pct(idle_values, .95):.3f} "
                        f"transition_n={len(transition_values)} "
                        f"transition_median={statistics.median(transition_values):.3f} "
                        f"transition_p95={_pct(transition_values, .95):.3f}"
                    )

    screens = sorted(
        {key[0] for key in publish_by_window_revision}
        | {key[0] for key in by_window_revision}
        | {key[0] for key in background_events}
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
            (9, "publish->render_prep_ready"),
            (10, "publish->render_host_begin"),
            (11, "publish->render_gl_state_ready"),
            (12, "publish->render_mode_begin"),
            (13, "publish->render_mode_ready"),
            (14, "publish->render_host_ready"),
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
            (3, 44, "gui_snapshot->presentation_commit_ready"),
            (44, 45, "presentation_commit_ready->present_request_ready"),
            (45, 46, "present_request_ready->quick_sync_item_entry"),
            (46, 47, "quick_sync_item_entry->snapshot_acquired"),
            (47, 4, "quick_sync_snapshot_acquired->quick_sync_consume"),
            (4, 7, "quick_sync->quick_sync_ready"),
            (7, 8, "quick_sync_ready->render_begin"),
            (8, 9, "render_begin->render_prep_ready"),
            (9, 10, "render_prep_ready->render_host_begin"),
            (9, 24, "render_prep_ready->clip_begin_resources_ready"),
            (24, 25, "clip_begin_resources_ready->inherited_ready"),
            (25, 26, "clip_begin_inherited_ready->setup_ready"),
            (26, 27, "clip_begin_setup_ready->mask_state_ready"),
            (27, 28, "clip_begin_mask_state_ready->mask_draw_ready"),
            (28, 29, "clip_begin_mask_draw_ready->mask_restore_ready"),
            (29, 10, "clip_begin_mask_restore_ready->render_host_begin"),
            (24, 35, "clip_begin_resources_ready->inherited_scissor_ready"),
            (35, 36, "clip_begin_inherited_scissor_ready->inherited_front_ready"),
            (36, 25, "clip_begin_inherited_front_ready->inherited_ready"),
            (26, 37, "clip_begin_setup_ready->mask_bindings_ready"),
            (37, 27, "clip_begin_mask_bindings_ready->mask_state_ready"),
            (27, 38, "clip_begin_mask_state_ready->mask_gl_state_applied"),
            (38, 39, "clip_begin_mask_gl_state_applied->mask_uniforms_ready"),
            (39, 28, "clip_begin_mask_uniforms_ready->mask_draw_ready"),
            (10, 11, "render_host_begin->render_gl_state_ready"),
            (11, 12, "render_gl_state_ready->render_mode_begin"),
            (12, 13, "render_mode_begin->render_mode_ready"),
            (13, 14, "render_mode_ready->render_host_ready"),
            (14, 5, "render_host_ready->draw"),
            (14, 30, "render_host_ready->clip_end_setup_ready"),
            (30, 31, "clip_end_setup_ready->mask_state_ready"),
            (31, 32, "clip_end_mask_state_ready->mask_draw_ready"),
            (32, 33, "clip_end_mask_draw_ready->mask_restore_ready"),
            (33, 34, "clip_end_mask_restore_ready->inherited_ready"),
            (34, 5, "clip_end_inherited_ready->draw"),
            (30, 40, "clip_end_setup_ready->mask_bindings_ready"),
            (40, 31, "clip_end_mask_bindings_ready->mask_state_ready"),
            (31, 41, "clip_end_mask_state_ready->mask_gl_state_applied"),
            (41, 42, "clip_end_mask_gl_state_applied->mask_uniforms_ready"),
            (42, 32, "clip_end_mask_uniforms_ready->mask_draw_ready"),
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
                if start_event >= 8 or end_event >= 8:
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

        _print_render_cycle_attribution(
            screen=screen,
            render_cycle_events=render_cycle_events,
            by_window_revision=by_window_revision,
        )
        _print_clip_stage_breakdown(
            screen=screen,
            by_window_revision=by_window_revision,
            phase="begin",
            parent_start_event=9,
            parent_end_event=10,
            parent_label="render_prep_ready->render_host_begin",
            stages=CLIP_BEGIN_STAGES,
        )
        _print_clip_stage_breakdown(
            screen=screen,
            by_window_revision=by_window_revision,
            phase="end",
            parent_start_event=14,
            parent_end_event=5,
            parent_label="render_host_ready->draw",
            stages=CLIP_END_STAGES,
        )
        if counts.get(35, 0) > 0:
            refined_begin_stages = (
                CLIP_BEGIN_REFINED_SHARED_STAGES
                if counts.get(43, 0) > 0
                else CLIP_BEGIN_REFINED_STAGES
            )
            _print_clip_stage_breakdown(
                screen=screen,
                by_window_revision=by_window_revision,
                phase="begin_refined",
                parent_start_event=9,
                parent_end_event=10,
                parent_label="render_prep_ready->render_host_begin",
                stages=refined_begin_stages,
            )
            if counts.get(43, 0) > 0:
                _print_clip_tail_breakdown(
                    screen=screen,
                    by_window_revision=by_window_revision,
                    phase="begin_refined",
                    parent_start_event=9,
                    parent_end_event=10,
                    parent_label="render_prep_ready->render_host_begin",
                    stages=refined_begin_stages,
                )
        if counts.get(40, 0) > 0:
            _print_clip_stage_breakdown(
                screen=screen,
                by_window_revision=by_window_revision,
                phase="end_refined",
                parent_start_event=14,
                parent_end_event=5,
                parent_label="render_host_ready->draw",
                stages=CLIP_END_REFINED_STAGES,
            )

        render_entry_gaps: list[tuple[int, int]] = []
        for (event_screen, _generation, _revision), stage_events in by_window_revision.items():
            if event_screen != screen:
                continue
            starts = stage_events.get(7, ())
            ends = stage_events.get(8, ())
            for start, end in zip(starts, ends):
                if end >= start:
                    render_entry_gaps.append((start, end))
        render_entry_gaps.sort()
        _print_render_gap_overlap(
            screen=screen,
            gaps=render_entry_gaps,
            label="audio_analysis",
            intervals=audio_analysis_intervals,
        )
        _print_render_gap_overlap(
            screen=screen,
            gaps=render_entry_gaps,
            label="audio_smooth",
            intervals=audio_smooth_intervals,
        )
        _print_render_gap_overlap(
            screen=screen,
            gaps=render_entry_gaps,
            label="background_render",
            intervals=background_intervals_by_screen.get(screen, []),
        )
        _print_render_gap_overlap(
            screen=screen,
            gaps=render_entry_gaps,
            label="background_transition",
            intervals=background_transition_intervals_by_screen.get(screen, []),
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
                sync_work: list[float] = []
                sync_ready_to_render: list[float] = []
                render_cost: list[float] = []
                render_prep: list[float] = []
                render_host: list[float] = []
                render_mode: list[float] = []
                render_post: list[float] = []
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
                    render_prep_ready = stage_events.get(9, ())
                    render_host_begin = stage_events.get(10, ())
                    render_mode_begin = stage_events.get(12, ())
                    render_mode_ready = stage_events.get(13, ())
                    render_host_ready = stage_events.get(14, ())
                    if syncs and sync_ready and sync_ready[0] >= syncs[0]:
                        sync_work.append(
                            (sync_ready[0] - syncs[0]) / 1_000_000.0
                        )
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
                    if render_begin and render_prep_ready:
                        render_prep.extend(
                            (ready - begin) / 1_000_000.0
                            for begin, ready in zip(render_begin, render_prep_ready)
                            if ready >= begin
                        )
                    if render_host_begin and render_host_ready:
                        render_host.extend(
                            (ready - begin) / 1_000_000.0
                            for begin, ready in zip(render_host_begin, render_host_ready)
                            if ready >= begin
                        )
                    if render_mode_begin and render_mode_ready:
                        render_mode.extend(
                            (ready - begin) / 1_000_000.0
                            for begin, ready in zip(render_mode_begin, render_mode_ready)
                            if ready >= begin
                        )
                    if render_host_ready and draws:
                        render_post.extend(
                            (draw - ready) / 1_000_000.0
                            for ready, draw in zip(render_host_ready, draws)
                            if draw >= ready
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
                if sync_work:
                    fields.extend(
                        (
                            f"sync_work_n={len(sync_work)}",
                            f"sync_work_median_ms={statistics.median(sync_work):.3f}",
                            f"sync_work_p95_ms={_pct(sync_work, .95):.3f}",
                        )
                    )
                if sync_ready_to_render:
                    fields.extend(
                        (
                            f"sync_ready_render_begin_n={len(sync_ready_to_render)}",
                            "sync_ready_render_begin_median_ms="
                            f"{statistics.median(sync_ready_to_render):.3f}",
                            "sync_ready_render_begin_p95_ms="
                            f"{_pct(sync_ready_to_render, .95):.3f}",
                        )
                    )
                if render_cost:
                    fields.extend(
                        (
                            f"render_begin_draw_n={len(render_cost)}",
                            f"render_begin_draw_median_ms={statistics.median(render_cost):.3f}",
                            f"render_begin_draw_p95_ms={_pct(render_cost, .95):.3f}",
                        )
                    )
                for metric_name, values in (
                    ("render_prep", render_prep),
                    ("render_host", render_host),
                    ("render_mode", render_mode),
                    ("render_post", render_post),
                ):
                    if values:
                        fields.extend(
                            (
                                f"{metric_name}_n={len(values)}",
                                f"{metric_name}_median_ms={statistics.median(values):.3f}",
                                f"{metric_name}_p95_ms={_pct(values, .95):.3f}",
                            )
                        )
                print(" ".join(fields))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
