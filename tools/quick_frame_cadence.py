"""Qt Quick frame-cycle cadence from an SRPSS ``--frame-trace``, for paths with no Python draw records.

On Vulkan the native core draws inside Qt's frame and writes no Python render or swap records, so
``tools/visualizer_live_check.py`` reports ``frames_per_s 0`` there (20 Nov 2026). This reads Qt Quick's own frame
cycles instead: the intervals between ``quick_before_frame_begin`` events per trace, outside the lifecycle windows
(startup and teardown are reported apart, never counted). It is layer T's interim presentation measure
(``Docs/Guides/Native_Parity_And_Timing_Proof.md`` section 4) until the live check reads frame cycles itself, and it
works the same on OpenGL, so a Vulkan run and an OpenGL control compare like for like.

    python tools/quick_frame_cadence.py TRACE [TRACE ...]

Prints per trace: steady frames, median, p90, p99, and counts of intervals over 16.7, 25 and 50 ms, and the maximum.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import frame_trace_report as ftr  # noqa: E402


def frame_begins(path: Path) -> list[int]:
    """``quick_before_frame_begin`` timestamps outside lifecycle windows, sorted (ns)."""
    raw, _ = ftr._read_trace_chain(path)
    begins: list[int] = []
    edges: list[tuple[int, str]] = []
    for offset in range(ftr.HEADER.size, len(raw) - ftr.RECORD.size + 1, ftr.RECORD.size):
        stamp, kind, _screen, _revision, _logical, _aux = ftr.RECORD.unpack_from(raw, offset)
        name = ftr.EVENT_NAMES.get(kind, kind)
        if name == "quick_before_frame_begin":
            begins.append(stamp)
        elif name in ("lifecycle_begin", "lifecycle_end"):
            edges.append((stamp, name))
    windows: list[tuple[float, float]] = []
    start = None
    for stamp, name in sorted(edges):
        if name == "lifecycle_begin":
            start = stamp
        elif start is not None:
            windows.append((start, stamp))
            start = None
    if start is not None:
        windows.append((start, float("inf")))
    return sorted(t for t in begins if not any(a <= t <= b for a, b in windows))


def cadence(begins: list[int]) -> dict[str, float]:
    gaps = sorted((b - a) / 1e6 for a, b in zip(begins, begins[1:]))
    if not gaps:
        return {"frames": len(begins)}

    def pct(q: float) -> float:
        return gaps[min(len(gaps) - 1, int(q * len(gaps)))]

    return {"frames": len(begins), "median": statistics.median(gaps), "p90": pct(.9), "p99": pct(.99),
            "over_16_7": sum(g > 16.7 for g in gaps), "over_25": sum(g > 25 for g in gaps),
            "over_50": sum(g > 50 for g in gaps), "max": gaps[-1]}


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    for arg in argv:
        figures = cadence(frame_begins(Path(arg)))
        if "median" not in figures:
            print(f"{arg}: frames={figures['frames']} (too few for intervals)")
            continue
        print(f"{arg}: frames={figures['frames']} median={figures['median']:.2f}ms p90={figures['p90']:.2f} "
              f"p99={figures['p99']:.2f} >16.7={figures['over_16_7']} >25={figures['over_25']} "
              f">50={figures['over_50']} max={figures['max']:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
