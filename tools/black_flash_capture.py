"""Composed-desktop black-flash detector for the Display-1 flash investigation.

This captures the *composed* output of one physical monitor via DXGI Desktop
Duplication (``dxcam``), which sits below the Qt Quick retained scene. It is the
correct plane for the Display-1 flash, whose telemetry shows the retained scene
and image identity staying valid while a native black clear reaches the desktop.
``QQuickWindow.grabWindow()`` would read the retained scene and miss it.

The tool is passive by default: the operator drives the real screensaver
(A -> B -> A clicks, open/close context menus) while this records per-frame mean
luminance at a high sample rate and flags "flash" events -- a near-black frame
that is bracketed by clearly non-black content within a short window. Each event
is wall-clock timestamped so it can be lined up against ``[QUICK_SURFACE]`` lines
in ``logs/screensaver.log`` for objective before/after comparison.

Usage (run in the project venv, on the operator's dual-display machine):

    python tools/black_flash_capture.py --list
    python tools/black_flash_capture.py --monitor 1 --seconds 40 --fps 120 \
        --out logs/black_flash_display1.csv

Report the printed flash count before a change and after it. It does NOT inject
input; add real input scripting only with explicit operator approval.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path


def _load_dxcam():
    try:
        import dxcam  # type: ignore
    except Exception as exc:  # pragma: no cover - environment probe
        raise SystemExit(
            "dxcam is required for composed-desktop capture. Install it in the "
            f"project environment (pip install dxcam). Import error: {exc}"
        )
    return dxcam


@dataclass
class FlashEvent:
    wall_clock: float
    iso_time: str
    frame_index: int
    luminance: float
    prev_bright_luminance: float
    gap_frames: int


def _mean_luminance(frame) -> float:
    """Rec.601 luma mean of an HxWx3 BGR/RGB uint8 frame (channel order agnostic)."""

    import numpy as np

    # Downsample for speed; luminance mean is stable under a coarse stride.
    sample = frame[::8, ::8, :3].astype("float32")
    # Channel-order-agnostic: equal-ish weights still separate black from content.
    return float(sample.mean())


def list_monitors() -> None:
    dxcam = _load_dxcam()
    print(dxcam.output_info())


def capture(
    *,
    monitor: int,
    seconds: float,
    fps: int,
    near_black: float,
    content: float,
    bracket_ms: float,
    out_path: Path | None,
) -> int:
    dxcam = _load_dxcam()
    import numpy as np  # noqa: F401  (ensures numpy present before the loop)

    camera = dxcam.create(output_idx=monitor, output_color="BGR")
    if camera is None:
        raise SystemExit(f"could not open monitor index {monitor}; use --list")

    bracket_frames = max(1, int((bracket_ms / 1000.0) * fps))
    events: list[FlashEvent] = []
    luminances: list[float] = []
    last_bright_lum = 0.0
    last_bright_gap = 0
    black_run_active = False

    print(
        f"[capture] monitor={monitor} seconds={seconds} fps={fps} "
        f"near_black<{near_black} content>={content} bracket={bracket_frames}f"
    )
    camera.start(target_fps=fps, video_mode=True)
    start = time.perf_counter()
    frame_index = 0
    try:
        while time.perf_counter() - start < seconds:
            frame = camera.get_latest_frame()
            if frame is None:
                continue
            lum = _mean_luminance(frame)
            luminances.append(lum)
            now = time.time()

            if lum >= content:
                last_bright_lum = lum
                last_bright_gap = 0
                black_run_active = False
            else:
                last_bright_gap += 1

            if lum < near_black and not black_run_active:
                # A near-black frame that was recently preceded by real content
                # is a flash, not a legitimately dark image left on screen.
                if last_bright_lum >= content and last_bright_gap <= bracket_frames:
                    black_run_active = True
                    event = FlashEvent(
                        wall_clock=now,
                        iso_time=time.strftime(
                            "%Y-%m-%d %H:%M:%S", time.localtime(now)
                        )
                        + f".{int((now % 1) * 1000):03d}",
                        frame_index=frame_index,
                        luminance=round(lum, 3),
                        prev_bright_luminance=round(last_bright_lum, 3),
                        gap_frames=last_bright_gap,
                    )
                    events.append(event)
                    print(
                        f"[flash] {event.iso_time} frame={frame_index} "
                        f"lum={event.luminance} prev={event.prev_bright_luminance} "
                        f"gap={event.gap_frames}f"
                    )
            frame_index += 1
    finally:
        camera.stop()
        del camera

    total = len(luminances)
    if total:
        lo = min(luminances)
        hi = max(luminances)
        avg = sum(luminances) / total
    else:
        lo = hi = avg = 0.0
    print(
        f"[summary] frames={total} flashes={len(events)} "
        f"lum_min={lo:.2f} lum_avg={avg:.2f} lum_max={hi:.2f}"
    )

    if out_path is not None and events:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "iso_time",
                    "wall_clock",
                    "frame_index",
                    "luminance",
                    "prev_bright_luminance",
                    "gap_frames",
                ]
            )
            for event in events:
                writer.writerow(
                    [
                        event.iso_time,
                        f"{event.wall_clock:.6f}",
                        event.frame_index,
                        event.luminance,
                        event.prev_bright_luminance,
                        event.gap_frames,
                    ]
                )
        print(f"[summary] wrote {len(events)} flash rows -> {out_path}")

    return len(events)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list", action="store_true", help="print dxcam monitor indices and exit"
    )
    parser.add_argument(
        "--monitor", type=int, default=1, help="dxcam output index to capture"
    )
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--fps", type=int, default=120)
    parser.add_argument(
        "--near-black",
        type=float,
        default=12.0,
        help="mean-luminance below this counts as a black frame (0-255)",
    )
    parser.add_argument(
        "--content",
        type=float,
        default=40.0,
        help="mean-luminance at/above this counts as real on-screen content",
    )
    parser.add_argument(
        "--bracket-ms",
        type=float,
        default=350.0,
        help="max time since real content for a black frame to count as a flash",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.list:
        list_monitors()
        return 0

    flashes = capture(
        monitor=args.monitor,
        seconds=args.seconds,
        fps=args.fps,
        near_black=args.near_black,
        content=args.content,
        bracket_ms=args.bracket_ms,
        out_path=args.out,
    )
    # Non-zero exit signals flashes were detected, for scripted before/after runs.
    return 2 if flashes else 0


if __name__ == "__main__":
    sys.exit(main())
