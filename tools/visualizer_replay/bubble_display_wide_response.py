"""Bubble on its card and display-wide: the same recorded take's motion and breathing at both sizes.

Replays a recorded take through the production logical path (``driver.replay_clip``: configured controller,
deterministic clock and seed, the real authored tick, ``BubbleFrameRuntime``) twice: on the card (its committed
world) and display-wide (the same card, with the display-wide card's grown world handed to the controller through the
owner's seam, ``VisualizerRuntimeController.set_drawn_world_extent``). The display-wide world is the production
resolver's (``resolve_expanded_visualizer_presentation`` of the card on the display). A third column, ``before``, is
the card run laid out on the display-wide world, which is what the scene drew before 21 Nov (the simulation kept the
card's world while the renderer drew the grown one).

Motion is measured as ``bubble_shape_invariance.measure`` measures it (canonical-card pixels against the drawn
bubbles' own size); breathing per stable identity as ``bubble_breathing_continuity`` does (displayed radius over
nominal radius per mature segment: range, swings per second, flat share). The music above the traces is the take's
own PCM (RMS dBFS of each frame's capture history), so a response that saturates, dies or races shows against it.

Logical frames only (no renderer, no window, no display): not pixel, display-cadence or listening acceptance.

    python -m tools.visualizer_replay.bubble_display_wide_response --clip <recording.jsonl> --output <evidence dir>
        [--seconds 60] [--preset 0] [--card 1204x144] [--display 2560x1440]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
from unittest.mock import patch
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
if str(_Path(__file__).resolve().parents[2]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from tools import artifact_paths  # noqa: E402


def _size(text: str) -> tuple[float, float]:
    width, _, height = text.lower().partition("x")
    return float(width), float(height)


def display_wide_world(card: tuple[float, float], display: tuple[float, float]) -> tuple[float, float]:
    """The display-wide card's world for ``card`` on ``display`` (the production resolvers, uniform scale 1)."""
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tools.expanded_visualizer_evidence import CARD
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation, resolve_visualizer_presentation,
    )

    ordinary = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("bubble"), display_size=display, outer_origin=(40.0, 40.0),
        dpr=1.0, uniform_visual_scale=1.0, viewport_extent=card, **CARD)
    expanded = resolve_expanded_visualizer_presentation(ordinary, display_size=display)
    return tuple(float(v) for v in expanded.viewport_extent)


def observe(clip, card, *, preset: int, drawn_world=None):
    """One record per published Bubble snapshot: shape-invariance samples plus nominal radii for breathing."""
    from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
    from . import driver

    frames, identities, resolved = [], {}, {}
    snapshot = BubbleSimulation.snapshot

    def recorder(simulation, *args, **kwargs):
        payload = snapshot(simulation, *args, **kwargs)
        samples, breath = [], []
        for index, bubble in enumerate(simulation._bubbles):
            key = id(bubble)
            if key not in identities or identities[key][0] is not bubble:
                identities[key] = (bubble, len(identities))
            track = identities[key][1]
            x, y, radius, alpha = payload[0][index * 4:index * 4 + 4]
            samples.append((track, x, y, radius, alpha, bubble.popping, bubble.exiting, bubble.is_big,
                            bubble.reaches_surface))
            mature = alpha > 0.999 and not bubble.popping and not bubble.exiting and not bubble.promoted
            breath.append((track, radius / bubble.radius, bool(bubble.is_big), bool(mature)))
        frames.append({"samples": samples, "breath": breath,
                       "world_scale": float(getattr(simulation, "_world_scale", 1.0)),
                       "domain": (float(simulation._domain_w), float(simulation._domain_h))})
        return payload

    configure = driver._configure

    def configured(controller, *args, **kwargs):
        configure(controller, *args, **kwargs)
        if drawn_world is not None:
            controller.set_drawn_world_extent(drawn_world)   # the owner's display-wide commit edge
        model = controller.settings_model
        resolved.update(stream=model.bubble_stream_direction, drift=model.bubble_drift_direction)

    with patch.object(BubbleSimulation, "snapshot", recorder), patch.object(driver, "_configure", configured):
        driver.replay_clip(clip, "bubble", preset=preset, viewport_extent=card)
    if len(frames) != len(clip.frames):
        raise RuntimeError("Bubble replay did not observe one snapshot per input frame")
    return frames, [frame.timestamp_us / 1e6 for frame in clip.frames], resolved


def breathing(frames, times, *, min_seconds: float = 2.0):
    from .bubble_breathing_continuity import mature_segments, segment_metrics, summarize

    series: dict[int, list] = {}
    for frame, t in zip(frames, times):
        for track, ratio, large, mature in frame["breath"]:
            series.setdefault(track, []).append((t, ratio, large, mature))
    cadence = median(b - a for a, b in zip(times, times[1:]))
    rows = [m for samples in series.values() for segment in mature_segments(samples, min_seconds, cadence)
            if (m := segment_metrics(segment)) is not None]
    return summarize(rows)


def music_envelope(clip):
    """(time s, RMS dBFS) of each frame's newest 1024 captured samples (None where a frame has no capture)."""
    import numpy as np

    origin = clip.frames[0].timestamp_us
    out = []
    for frame in clip.frames:
        history = frame.capture_history
        if history is None:
            continue
        pcm = np.frombuffer(history.pcm_f32le, "<f4").astype(np.float64)[-1024:]
        if not pcm.size:
            continue
        out.append(((frame.timestamp_us - origin) / 1e6, 20.0 * math.log10(max(1e-6, float(np.sqrt(np.mean(pcm * pcm)))))))
    return out


def speed_series(frames, times, extent, *, bin_s: float = 0.5):
    """Median along-axis speed per ``bin_s`` (canonical-card pixels against the bubbles' own size, both axes)."""
    from .bubble_shape_invariance import CANONICAL, reference_px

    ref = reference_px(extent, frames[-1]["world_scale"])
    to_canon = CANONICAL[1] / ref
    previous, bins = {}, {}
    origin = times[0]
    for index, frame in enumerate(frames):
        current = {}
        for track, x, y, _r, alpha, popping, exiting, _big, _surface in frame["samples"]:
            current[track] = (x * extent[0], y * extent[1], alpha >= 0.99 and not popping and not exiting)
            before = previous.get(track)
            if before is None or not before[2] or not current[track][2] or index == 0:
                continue
            dt = times[index] - times[index - 1]
            if dt > 0.0:
                speed = math.hypot(current[track][0] - before[0], current[track][1] - before[1]) / dt * to_canon
                bins.setdefault(int((times[index] - origin) / bin_s), []).append(speed)
        previous = current
    return [((key + 0.5) * bin_s, median(values)) for key, values in sorted(bins.items())]


def ratio_series(frames, times):
    origin = times[0]
    return [((t - origin), median(r for _track, r, big, mature in frame["breath"] if big and mature))
            for frame, t in zip(frames, times)
            if any(big and mature for _track, _r, big, mature in frame["breath"])]


def plot(path: Path, music, curves: dict, ratios: dict, title: str) -> None:
    from PIL import Image, ImageDraw

    width, panel, pad = 1600, 220, 60
    colours = {"card": (80, 170, 255), "display_wide": (255, 170, 60), "before": (230, 70, 70)}
    image = Image.new("RGB", (width, pad + 3 * (panel + pad)), (18, 20, 24))
    draw = ImageDraw.Draw(image)
    draw.text((pad, 15), title, fill=(230, 230, 230))
    duration = max([t for t, _ in music] + [t for c in curves.values() for t, _ in c] + [1.0])

    def lines(top, series_by_name, label, lo=None, hi=None):
        values = [v for series in series_by_name.values() for _t, v in series]
        if not values:
            return
        lo = min(values) if lo is None else lo
        hi = max(values) if hi is None else hi
        hi = hi if hi > lo else lo + 1.0
        draw.rectangle((pad, top, width - pad, top + panel), outline=(70, 70, 80))
        draw.text((pad + 6, top + 4), f"{label}  [{lo:.2f} .. {hi:.2f}]", fill=(200, 200, 200))
        for index, (name, series) in enumerate(series_by_name.items()):
            colour = colours.get(name, (200, 200, 200))
            points = [(pad + (width - 2 * pad) * t / duration, top + panel - panel * (v - lo) / (hi - lo))
                      for t, v in series]
            if len(points) > 1:
                draw.line(points, fill=colour, width=2)
            draw.text((width - pad - 160, top + 4 + 14 * index), name, fill=colour)

    lines(pad + 20, {"music": [(t, max(-60.0, v)) for t, v in music]}, "music RMS dBFS (newest 1024 samples)",
          lo=-60.0)
    lines(pad + 20 + panel + pad, ratios, "big bubbles: median displayed / nominal radius (breathing)")
    lines(pad + 20 + 2 * (panel + pad), curves, "median speed, canonical px/s against own size (0.5 s bins)", lo=0.0)
    image.save(path)


def main() -> None:
    from PySide6.QtCore import QCoreApplication

    from .extruded_bubble_forensics import load_clip
    from .bubble_shape_invariance import measure

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clip", type=Path, required=True, help="a recording (.jsonl)")
    parser.add_argument("--output", type=artifact_paths.evidence_arg, required=True, help="a new evidence folder")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--preset", type=int, default=0, help="curated preset index (0-based)")
    parser.add_argument("--card", default="1204x144", help="the card's committed world, WxH")
    parser.add_argument("--display", default="2560x1440", help="the display's logical size, WxH")
    args = parser.parse_args()
    QCoreApplication.instance() or QCoreApplication([])
    card, display = _size(args.card), _size(args.display)
    wide = display_wide_world(card, display)
    clip = load_clip(args.clip, args.seconds)
    args.output.mkdir(parents=True, exist_ok=False)
    card_frames, times, resolved = observe(clip, card, preset=args.preset)
    wide_frames, wide_times, _ = observe(clip, card, preset=args.preset, drawn_world=wide)
    if wide_times != times:
        raise RuntimeError("the two replays published different frame times")
    runs = {"card": (card_frames, card), "display_wide": (wide_frames, wide), "before": (card_frames, wide)}
    report = {"clip": str(args.clip), "seconds": args.seconds, "preset": args.preset, "card": card,
              "display": display, "display_wide_world": wide, "stream": resolved.get("stream"),
              "drift": resolved.get("drift"), "runs": {}}
    curves, ratios = {}, {}
    for name, (frames, extent) in runs.items():
        stats = measure(frames, times, extent, resolved)
        stats["domain"] = frames[-1]["domain"]
        if name != "before":
            stats["breathing"] = breathing(frames, times)
            ratios[name] = ratio_series(frames, times)
        report["runs"][name] = stats
        curves[name] = speed_series(frames, times, extent)
    base = report["runs"]["card"]
    for name in ("display_wide", "before"):
        row = report["runs"][name]
        report["runs"][name]["relative_to_card"] = {
            key: row[key] / base[key] - 1.0 for key in ("speed_median", "speed_x_median", "speed_y_median",
                                                       "stream_along_median", "radius_big_median",
                                                       "density_per_canonical_card")
            if base[key] and math.isfinite(base[key]) and math.isfinite(row[key])}
    (args.output / "report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    music = music_envelope(clip)
    plot(args.output / "response.png", music, curves, ratios,
         f"Bubble card {card[0]:g}x{card[1]:g} vs display-wide {wide[0]:.0f}x{wide[1]:.0f} on "
         f"{display[0]:g}x{display[1]:g}; {Path(args.clip).name} first {args.seconds:g} s, preset index {args.preset}")
    for name, row in report["runs"].items():
        line = {k: round(v, 3) for k, v in row.items() if k in ("zoom", "world_scale", "speed_median",
                                                                 "stream_along_median", "radius_big_median",
                                                                 "density_per_canonical_card", "visible_mean")}
        print(name, line, {k: f"{100 * v:+.1f}%" for k, v in row.get("relative_to_card", {}).items()})
        if "breathing" in row:
            print("   breathing", row["breathing"])
    print("->", args.output)


if __name__ == "__main__":
    main()
