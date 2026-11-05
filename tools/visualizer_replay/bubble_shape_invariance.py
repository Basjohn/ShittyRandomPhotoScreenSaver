"""Bubble shape invariance: does a card's shape change Bubble's perceived speed, size or density?

Replays recorded music (or a committed fixture) through the production logical path
(``replay_clip``: configured controller, deterministic clock and seed, the real authored tick,
``BubbleFrameRuntime`` and ``BubbleSimulation``) at several committed card extents, observes every
published snapshot, and reports motion in one shape-independent physical unit.

Units. Every card is presented at uniform visual scale 1, so a pixel here is a world unit. The
renderer's own layout (``compute_quick_bubble_layout``) gives the pixels that one authored radius unit
covers on that card (``ref_px``; 280 on the canonical card). Speeds, sizes and densities are reported
in canonical-card pixels: a value times ``280 / ref_px``. That is how fast, how big and how crowded the
card looks next to its own bubbles; on the canonical card it is plain pixels. ``world_px`` columns are
raw pixels at equal uniform scale, and ``zoom`` is ``ref_px / 280``.

Nothing here runs in the product. Usage::

    python -m tools.visualizer_replay.bubble_shape_invariance --report out.json
    python -m tools.visualizer_replay.bubble_shape_invariance --fixture representative_music_features
"""
from __future__ import annotations

import argparse
import inspect
import json
import math
from pathlib import Path
from statistics import median
from unittest.mock import patch

CANONICAL = (420.0, 280.0)
SHAPES = {
    "baseline": CANONICAL,
    "tiny": (210.0, 140.0),
    "square": (600.0, 600.0),
    "tall": (280.0, 1200.0),
    "wide": (2400.0, 300.0),
    "huge": (1260.0, 840.0),
    "tv_card": (3874.710133891547, 1449.5065990010949),
}
# Curated preset indices (0-based): up + swish-H, left + swish-V + Group Drift, right + swish-V, up + swirl.
PRESETS = (0, 2, 3, 6)
RECORDINGS = Path(__file__).resolve().parents[2] / "logs" / "visualizer_recordings"
DEFAULT_RECORDING = "balanced"
_STREAMS = {
    "up": (0.0, -1.0), "down": (0.0, 1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0),
    "top_left": (-0.707, -0.707), "top_right": (0.707, -0.707),
    "bottom_left": (-0.707, 0.707), "bottom_right": (0.707, 0.707),
}


def _quantile(values, q):
    values = sorted(values)
    if not values:
        return float("nan")
    position = (len(values) - 1) * q
    lower = int(position)
    upper = min(len(values) - 1, lower + 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def reference_px(extent, world_scale=1.0) -> float:
    """Pixels one authored radius unit covers on this card, from the production renderer layout."""
    from rendering.quick.visualizer.implementations.bubble import compute_quick_bubble_layout

    kwargs = dict(local_content_rect=(0.0, 0.0, extent[0], extent[1]), visual_scale=1.0,
                  viewport_extent=extent, baseline_viewport_size=CANONICAL)
    if "world_scale" in inspect.signature(compute_quick_bubble_layout).parameters:
        kwargs["world_scale"] = world_scale
    layout = compute_quick_bubble_layout(**kwargs)
    return layout.response_radius_scale * extent[1]


def observe(clip, extent, *, preset=0, settings=None):
    """Replay ``clip`` at ``extent``; one record per published Bubble snapshot."""
    from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
    from .driver import replay_clip

    frames, identities = [], {}
    snapshot = BubbleSimulation.snapshot
    resolved = {}

    def recorder(simulation, *args, **kwargs):
        payload = snapshot(simulation, *args, **kwargs)
        samples = []
        for index, bubble in enumerate(simulation._bubbles):
            key = id(bubble)
            if key not in identities or identities[key][0] is not bubble:
                identities[key] = (bubble, len(identities))
            x, y, radius, alpha = payload[0][index * 4:index * 4 + 4]
            samples.append((identities[key][1], x, y, radius, alpha, bubble.popping, bubble.exiting,
                            bubble.is_big, bubble.reaches_surface))
        frames.append({"samples": samples, "world_scale": float(getattr(simulation, "_world_scale", 1.0))})
        return payload

    from . import driver
    configure = driver._configure

    def configure_and_record(controller, *args, **kwargs):
        configure(controller, *args, **kwargs)
        resolved.update(stream=controller.settings_model.bubble_stream_direction,
                        drift=controller.settings_model.bubble_drift_direction,
                        big=controller.settings_model.bubble_big_count,
                        small=controller.settings_model.bubble_small_count)

    with patch.object(BubbleSimulation, "snapshot", recorder), patch.object(driver, "_configure", configure_and_record):
        replay_clip(clip, "bubble", preset=preset, settings=settings, viewport_extent=extent)
    if len(frames) != len(clip.frames):
        raise RuntimeError("Bubble replay did not observe one snapshot per input frame")
    times = [frame.timestamp_us / 1e6 for frame in clip.frames]
    return frames, times, resolved


def measure(frames, times, extent, resolved, *, skip_s=2.0):
    """Shape-independent motion/size/density statistics (canonical-card pixels unless named ``world``)."""
    width, height = extent
    world_scale = frames[-1]["world_scale"]
    ref = reference_px(extent, world_scale)
    to_canon = CANONICAL[1] / ref
    start = times[0] + skip_s
    stream = _STREAMS.get(resolved.get("stream"), (0.0, 0.0))
    vx, vy, speed, along, lateral, radius_big, radius_small, visible = [], [], [], [], [], [], [], []
    crossings, births = [], 0
    previous = {}
    first_seen, crossed = {}, set()
    lateral_series: dict[int, list[tuple[float, float]]] = {}
    for index, frame in enumerate(frames):
        t = times[index]
        current = {}
        count = 0
        for track, x, y, r, alpha, popping, exiting, big, surface in frame["samples"]:
            px, py = x * width, y * height
            current[track] = (px, py, alpha, popping, exiting)
            if track not in first_seen:
                first_seen[track] = (t, surface)
                if t >= start and index:
                    births += 1
            steady = alpha >= 0.99 and not popping and not exiting
            if steady:
                count += 1
                (radius_big if big else radius_small).append(r * ref * to_canon)
            if exiting and surface and track not in crossed:
                crossed.add(track)
                born, _surface = first_seen[track]
                if born >= start:
                    crossings.append(t - born)
            before = previous.get(track)
            if t < start or before is None or not steady or before[3] or before[4] or before[2] < 0.99:
                continue
            dt = t - times[index - 1]
            if dt <= 0.0:
                continue
            dx = (px - before[0]) / dt * to_canon
            dy = (py - before[1]) / dt * to_canon
            vx.append(abs(dx))
            vy.append(abs(dy))
            speed.append(math.hypot(dx, dy))
            if stream != (0.0, 0.0):
                along.append(dx * stream[0] + dy * stream[1])
                lat = -dx * stream[1] + dy * stream[0]
                lateral.append(abs(lat))
                lateral_series.setdefault(track, []).append((t, lat))
        if t >= start:
            visible.append(count)
        previous = current
    # Swish/drift cadence: oscillations per second of each long-lived track's lateral velocity about its own
    # mean (a per-bubble drift bias is not an oscillation); crossings inside a small noise band are ignored.
    cadence = []
    for series in lateral_series.values():
        if len(series) < 90:
            continue
        values = [v for _t, v in series]
        mean = sum(values) / len(values)
        spread = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
        if spread <= 1e-9:
            continue
        band = 0.25 * spread
        sign, flips = 0, 0
        for v in values:
            if abs(v - mean) < band:
                continue
            current = 1 if v > mean else -1
            if sign and current != sign:
                flips += 1
            sign = current
        cadence.append(0.5 * flips / max(1e-9, series[-1][0] - series[0][0]))
    duration = max(1e-9, times[-1] - start)
    area_canon = (width * to_canon) * (height * to_canon)
    entry_edge = (width if abs(stream[1]) >= abs(stream[0]) else height) * to_canon
    card_along = (height if abs(stream[1]) >= abs(stream[0]) else width) * to_canon
    return {
        "extent": [width, height], "zoom": ref / CANONICAL[1], "world_scale": world_scale,
        "speed_x_median": median(vx) if vx else float("nan"), "speed_x_p90": _quantile(vx, 0.9),
        "speed_y_median": median(vy) if vy else float("nan"), "speed_y_p90": _quantile(vy, 0.9),
        "speed_median": median(speed) if speed else float("nan"), "speed_p90": _quantile(speed, 0.9),
        "stream_along_median": median(along) if along else float("nan"),
        "stream_along_p90": _quantile(along, 0.9),
        "stream_along_world_px": (median(along) / to_canon) if along else float("nan"),
        "lateral_median": median(lateral) if lateral else float("nan"),
        "lateral_p90": _quantile(lateral, 0.9),
        "swish_hz": median(cadence) if cadence else float("nan"),
        "crossing_s_median": median(crossings) if crossings else float("nan"),
        "crossing_s_per_canonical_length": (
            median(crossings) * CANONICAL[1 if abs(stream[1]) >= abs(stream[0]) else 0] / card_along
            if crossings else float("nan")),
        "births_per_s_per_100px_entry": births / duration / (entry_edge / 100.0),
        "radius_big_median": median(radius_big) if radius_big else float("nan"),
        "radius_small_median": median(radius_small) if radius_small else float("nan"),
        "radius_big_world_px": (median(radius_big) / to_canon) if radius_big else float("nan"),
        "visible_mean": sum(visible) / max(1, len(visible)),
        "density_per_canonical_card": sum(visible) / max(1, len(visible)) / (area_canon / (CANONICAL[0] * CANONICAL[1])),
        "samples": len(vx),
    }


def load_clip(name: str, *, fixture: bool, seconds: float, recordings: Path = RECORDINGS):
    from widgets.spotify_visualizer.feature_frame import FeatureClip, load_jsonl

    if fixture:
        from .driver import load_clips
        clip = load_clips()[name]
    else:
        clip = load_jsonl(Path(recordings) / f"{name}.jsonl")
    if seconds > 0.0:
        first = clip.frames[0].timestamp_us
        clip = FeatureClip(name=clip.name, frames=tuple(
            frame for frame in clip.frames if frame.timestamp_us - first <= seconds * 1e6))
    return clip


COLUMNS = ("speed_x_median", "speed_y_median", "speed_median", "speed_p90", "stream_along_median", "lateral_median", "swish_hz",
           "crossing_s_per_canonical_length", "births_per_s_per_100px_entry", "radius_big_median",
           "radius_small_median", "density_per_canonical_card")


def run(clip, *, presets=PRESETS, shapes=SHAPES):
    results = {}
    for preset in presets:
        for shape, extent in shapes.items():
            frames, times, resolved = observe(clip, extent, preset=preset)
            stats = measure(frames, times, extent, resolved)
            stats.update(preset=preset, shape=shape, stream=resolved.get("stream"), drift=resolved.get("drift"))
            results[f"{preset}:{shape}"] = stats
    return results


def deviations(results, *, presets=PRESETS, shapes=SHAPES, columns=COLUMNS):
    """Each shape's relative deviation from the canonical card, per preset and column."""
    table = {}
    for preset in presets:
        base = results[f"{preset}:baseline"]
        for shape in shapes:
            row = results[f"{preset}:{shape}"]
            table[f"{preset}:{shape}"] = {
                column: (row[column] / base[column] - 1.0)
                if base[column] and math.isfinite(base[column]) and math.isfinite(row[column]) else float("nan")
                for column in columns
            }
    return table


def main() -> None:
    from PySide6.QtCore import QCoreApplication

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clip", default=DEFAULT_RECORDING, help="recording name (logs/visualizer_recordings)")
    parser.add_argument("--fixture", action="store_true", help="--clip names a committed replay fixture")
    parser.add_argument("--recordings", type=Path, default=RECORDINGS, help="recordings directory")
    parser.add_argument("--seconds", type=float, default=30.0, help="replay at most this much of the clip")
    parser.add_argument("--preset", type=int, action="append", help="curated preset index (repeatable)")
    parser.add_argument("--report", type=Path, help="write the full results as JSON")
    args = parser.parse_args()
    QCoreApplication.instance() or QCoreApplication([])
    clip = load_clip(args.clip, fixture=args.fixture, seconds=args.seconds, recordings=args.recordings)
    presets = tuple(args.preset) if args.preset else PRESETS
    results = run(clip, presets=presets)
    table = deviations(results, presets=presets)
    short = ("vx", "vy", "|v|", "|v|p90", "along", "lat", "swishHz", "cross", "births", "r_big", "r_small", "density")
    print(f"{'preset:shape':18s} zoom  count " + " ".join(f"{name:>8s}" for name in short)
          + "  world:along  world:r_big")
    for key, row in results.items():
        values = " ".join(f"{row[c]:8.2f}" for c in COLUMNS)
        print(f"{key:18s} {row['zoom']:4.2f} {row['visible_mean']:6.1f} {values}"
              f"  {row['stream_along_world_px']:10.2f}  {row['radius_big_world_px']:10.2f}")
    print("\nrelative to the canonical card (%):")
    for key, row in table.items():
        print(f"{key:18s}       " + " ".join(f"{100.0 * row[c]:+8.1f}" for c in COLUMNS))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"clip": clip.name, "results": results, "deviation": table},
                                          indent=1, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
