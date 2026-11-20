"""Qt Quick frame-cycle cadence and late-frame attribution from an SRPSS ``--frame-trace``.

On Vulkan the native core draws inside Qt's frame and writes no Python render or swap records, so
``tools/visualizer_live_check.py`` reports ``frames_per_s 0`` there (20 Nov 2026). This reads Qt Quick's own frame
cycles instead: the intervals between ``quick_before_frame_begin`` events, outside the lifecycle windows (startup and
teardown are reported apart, never counted). It is layer T's presentation measure on native paths
(``Docs/Guides/Native_Parity_And_Timing_Proof.md`` section 4) until the live check reads frame cycles itself, and it
works the same on OpenGL, so a Vulkan run and an OpenGL control compare like for like.

    python tools/quick_frame_cadence.py TRACE [TRACE ...] [--phases] [--split] [--requests] [--late-ms 16.7]

Default: per trace, steady frames, median, p90, p99, counts over 16.7, 25 and 50 ms, and the maximum.
--phases    render-thread durations per frame (quick_before_rendering -> quick_after_rendering, and the sync), overall
            and for late frames: whether late frames spend their time recording on the render thread.
--split     each late frame's interval split into begin -> synchronising, synchronising -> after rendering, and after
            rendering -> next frame begin: where the time goes (20 Nov: all of it after rendering, on Bubble Vulkan).
--requests  per late frame, whether a visualizer publication fell inside the gap, and whether a present request
            (gui_present_request_ready) was ready more than 8 ms before the next frame began: Qt starting frames late
            although work was waiting.
"""

from __future__ import annotations

import argparse
import bisect
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import frame_trace_report as ftr  # noqa: E402

_QUICK = ("quick_before_frame_begin", "quick_before_synchronizing", "quick_after_synchronizing",
          "quick_before_rendering", "quick_after_rendering")


def read_events(path: Path) -> list[tuple[int, str]]:
    raw, _ = ftr._read_trace_chain(path)
    events = []
    for offset in range(ftr.HEADER.size, len(raw) - ftr.RECORD.size + 1, ftr.RECORD.size):
        stamp, kind, _screen, _revision, _logical, _aux = ftr.RECORD.unpack_from(raw, offset)
        events.append((stamp, ftr.EVENT_NAMES.get(kind, kind)))
    events.sort()
    return events


def lifecycle_windows(events: list[tuple[int, str]]) -> list[tuple[float, float]]:
    windows, start = [], None
    for stamp, name in events:
        if name == "lifecycle_begin":
            start = stamp
        elif name == "lifecycle_end" and start is not None:
            windows.append((start, stamp))
            start = None
    if start is not None:
        windows.append((start, float("inf")))
    return windows


def steady_frames(events: list[tuple[int, str]]) -> list[dict[str, int]]:
    """One dict per Qt frame cycle outside lifecycle windows: its quick_* event stamps (first of each)."""
    windows = lifecycle_windows(events)
    frames, current = [], None
    for stamp, name in events:
        if any(a <= stamp <= b for a, b in windows):
            continue
        if name == "quick_before_frame_begin":
            if current:
                frames.append(current)
            current = {"begin": stamp}
        elif current is not None and name in _QUICK:
            current.setdefault(name, stamp)
    if current:
        frames.append(current)
    return frames


def frame_begins(path: Path) -> list[int]:
    """``quick_before_frame_begin`` timestamps outside lifecycle windows, sorted (ns)."""
    return [frame["begin"] for frame in steady_frames(read_events(path))]


def cadence(begins: list[int]) -> dict[str, float]:
    gaps = sorted((b - a) / 1e6 for a, b in zip(begins, begins[1:]))
    if not gaps:
        return {"frames": len(begins)}

    def pct(q: float) -> float:
        return gaps[min(len(gaps) - 1, int(q * len(gaps)))]

    return {"frames": len(begins), "median": statistics.median(gaps), "p90": pct(.9), "p99": pct(.99),
            "over_16_7": sum(g > 16.7 for g in gaps), "over_25": sum(g > 25 for g in gaps),
            "over_50": sum(g > 50 for g in gaps), "max": gaps[-1]}


def _late_pairs(frames: list[dict[str, int]], late_ms: float):
    for a, b in zip(frames, frames[1:]):
        if (b["begin"] - a["begin"]) / 1e6 > late_ms:
            yield a, b


def phases(frames: list[dict[str, int]], late_ms: float) -> dict[str, float]:
    def duration(frame, start, end):
        return (frame[end] - frame[start]) / 1e6 if start in frame and end in frame else None

    render = [d for f in frames if (d := duration(f, "quick_before_rendering", "quick_after_rendering")) is not None]
    sync = [d for f in frames if (d := duration(f, "quick_before_synchronizing", "quick_after_synchronizing")) is not None]
    late = list(_late_pairs(frames, late_ms))
    late_render = [d for a, _ in late if (d := duration(a, "quick_before_rendering", "quick_after_rendering")) is not None]
    late_sync = [d for a, _ in late if (d := duration(a, "quick_before_synchronizing", "quick_after_synchronizing")) is not None]
    out = {"render_median": statistics.median(render) if render else 0.0,
           "render_p99": sorted(render)[int(.99 * (len(render) - 1))] if render else 0.0,
           "sync_median": statistics.median(sync) if sync else 0.0, "late": len(late),
           "late_render_median": statistics.median(late_render) if late_render else 0.0,
           "late_sync_median": statistics.median(late_sync) if late_sync else 0.0}
    return out


def split(frames: list[dict[str, int]], late_ms: float) -> dict[str, float]:
    pre, mid, post = [], [], []
    for a, b in _late_pairs(frames, late_ms):
        if "quick_before_synchronizing" not in a or "quick_after_rendering" not in a:
            continue
        pre.append((a["quick_before_synchronizing"] - a["begin"]) / 1e6)
        mid.append((a["quick_after_rendering"] - a["quick_before_synchronizing"]) / 1e6)
        post.append((b["begin"] - a["quick_after_rendering"]) / 1e6)
    if not pre:
        return {"late": 0}
    return {"late": len(pre), "begin_to_sync_median": statistics.median(pre), "begin_to_sync_max": max(pre),
            "sync_to_after_render_median": statistics.median(mid),
            "after_render_to_next_median": statistics.median(post), "after_render_to_next_max": max(post)}


def requests(events: list[tuple[int, str]], frames: list[dict[str, int]], late_ms: float) -> dict[str, int]:
    publishes = [t for t, n in events if n == "logical_publish"]
    ready = [t for t, n in events if n == "gui_present_request_ready"]
    late = no_publish = waited = 0
    for a, b in _late_pairs(frames, late_ms):
        late += 1
        i, j = bisect.bisect_right(publishes, a["begin"]), bisect.bisect_left(publishes, b["begin"])
        if i == j:
            no_publish += 1
            continue
        k = bisect.bisect_right(ready, a["begin"])
        if k < len(ready) and ready[k] < b["begin"] and (b["begin"] - ready[k]) / 1e6 > 8:
            waited += 1
    return {"late": late, "no_publish_in_gap": no_publish, "request_ready_over_8ms_before_begin": waited}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("traces", nargs="+", type=Path)
    parser.add_argument("--phases", action="store_true")
    parser.add_argument("--split", action="store_true")
    parser.add_argument("--requests", action="store_true")
    parser.add_argument("--late-ms", type=float, default=16.7)
    args = parser.parse_args(argv)
    for path in args.traces:
        events = read_events(path)
        frames = steady_frames(events)
        figures = cadence([f["begin"] for f in frames])
        if "median" not in figures:
            print(f"{path}: frames={figures['frames']} (too few for intervals)")
            continue
        print(f"{path}: frames={figures['frames']} median={figures['median']:.2f}ms p90={figures['p90']:.2f} "
              f"p99={figures['p99']:.2f} >16.7={figures['over_16_7']} >25={figures['over_25']} "
              f">50={figures['over_50']} max={figures['max']:.1f}")
        if args.phases:
            print("   phases:", " ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}"
                                         for k, v in phases(frames, args.late_ms).items()))
        if args.split:
            print("   split:", " ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}"
                                        for k, v in split(frames, args.late_ms).items()))
        if args.requests:
            print("   requests:", " ".join(f"{k}={v}" for k, v in requests(events, frames, args.late_ms).items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
