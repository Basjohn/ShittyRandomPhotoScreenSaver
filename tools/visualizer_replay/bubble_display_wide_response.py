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

By default logical frames only (no renderer, no window, no display). ``--render-fps N`` also draws both cards (the
card's ordinary record at ``--card-scale``, its display-wide record, both at ``--dpr``) through the production render
host offscreen, N frames per second of the take, keeps those frames, and measures each mature big hero's drawn ring
from the pixels it changes when drawn alone: its outer radius in device pixels against its own nominal drawn size,
the drawn card's short side and its equal-area side (``drawn`` in the report, a fourth trace under the music). No
window is shown; not display-cadence or listening acceptance.

    python -m tools.visualizer_replay.bubble_display_wide_response --clip <recording.jsonl> --output <evidence dir>
        [--seconds 60] [--preset 0] [--card 1204x144] [--display 2560x1440]
        [--render-fps 2 --card-scale 2 --dpr 1.5]
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


def drawn_presentations(card: tuple[float, float], display: tuple[float, float], *, scale: float = 1.0,
                        dpr: float = 1.0):
    """(the card's ordinary record, its display-wide record) on ``display`` (the production resolvers; the card at
    uniform ``scale``, both at ``dpr``): the two drawn cards the renderer lays Bubble's frames onto."""
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tools.expanded_visualizer_evidence import CARD
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation, resolve_visualizer_presentation,
    )

    ordinary = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("bubble"), display_size=display, outer_origin=(40.0, 40.0),
        dpr=float(dpr), uniform_visual_scale=float(scale), viewport_extent=card, **CARD)
    return ordinary, resolve_expanded_visualizer_presentation(ordinary, display_size=display)


def display_wide_world(card: tuple[float, float], display: tuple[float, float]) -> tuple[float, float]:
    """The display-wide card's world for ``card`` on ``display`` (the production resolvers, uniform scale 1)."""
    return tuple(float(v) for v in drawn_presentations(card, display)[1].viewport_extent)


def observe(clip, card, *, preset: int, drawn_world=None, snapshots_at=(), snapshots=None):
    """One record per published Bubble snapshot: shape-invariance samples plus nominal radii for breathing.
    ``snapshots``: a dict that receives the published Quick snapshots of the frames in ``snapshots_at``."""
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
        result = driver.replay_clip(clip, "bubble", preset=preset, viewport_extent=card, snapshots_at=snapshots_at)
    if snapshots is not None:
        snapshots.update(result["snapshots"])
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


def drawn_radii(snapshots, frames, times, presentation, frame_dir: Path | None = None):
    """Bubble's big heroes as drawn: each sampled snapshot on its drawn card (``presentation``) through the production
    render host, offscreen; each mature big hero then drawn alone on the same card and its ring's outer radius read
    from the pixels it changed against the card drawn empty. One row per hero and frame: drawn outer radius in device
    pixels, the renderer's own projection of its payload and nominal radius (``bubble_presentation_layout``), and the
    drawn card's content size. ``frame_dir``: the full frames are kept there as PNG."""
    from dataclasses import replace

    import numpy as np
    from PIL import Image

    from rendering.quick.visualizer.implementations.bubble import bubble_presentation_layout
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.extruded_bubble_capture import _draw
    from tools.transition_contact_sheet import TransitionCapture

    outer_x, outer_y, outer_w, outer_h = presentation.outer_rect
    size = (int(round(outer_w)), int(round(outer_h)))
    cx0, cy0, content_w, content_h = presentation.content_rect
    cx0, cy0 = cx0 - outer_x, cy0 - outer_y
    dpr = float(presentation.dpr)
    target = TransitionCapture(int(round(outer_w * dpr)), int(round(outer_h * dpr)))   # device pixels
    host = QuickVisualizerRenderHost()
    rows = []
    origin = times[0]
    try:
        def draw(snapshot, state):
            logical = replace(snapshot.logical, mode_state=state)
            rgba, _ms = _draw(host, target, replace(snapshot, logical=logical), size, size)
            return rgba

        for index in sorted(snapshots):
            snapshot = replace(snapshots[index], presentation=presentation)
            state = snapshot.logical.mode_state
            layout = bubble_presentation_layout(presentation, (cx0, cy0, content_w, content_h), state.world_scale)
            px_per_unit = layout.response_radius_scale * content_h * dpr
            whole = draw(snapshot, state)
            if frame_dir is not None:
                Image.fromarray(whole).convert("RGB").save(frame_dir / f"frame_{index:05d}.png")
            empty = replace(state, positions=(), extras=(), trails=(), bubble_count=0, big_class_bits=(0, 0, 0, 0),
                            ambient_points=(), ambient_occluders=())
            background = draw(snapshot, empty).astype(np.int16)
            for i, ((track, _x, _y, radius, _a, *_rest), (_t, ratio, large, mature)) in enumerate(
                    zip(frames[index]["samples"], frames[index]["breath"])):
                if not (large and mature) or ratio <= 0.0:
                    continue
                alone = replace(empty, positions=state.positions[4 * i:4 * i + 4],
                                extras=state.extras[4 * i:4 * i + 4], bubble_count=1, big_class_bits=(1, 0, 0, 0))
                changed = np.abs(draw(snapshot, alone).astype(np.int16) - background).max(axis=2) > 24
                ys, xs = np.nonzero(changed)
                if not len(xs):
                    continue
                left, right, top, bottom = xs.min(), xs.max(), ys.min(), ys.max()
                lo_x, lo_y = cx0 * dpr, cy0 * dpr
                hi_x, hi_y = (cx0 + content_w) * dpr - 1, (cy0 + content_h) * dpr - 1
                if left <= lo_x + 1 or top <= lo_y + 1 or right >= hi_x - 1 or bottom >= hi_y - 1:
                    continue  # clipped by the card's edge: its extent is not its radius
                drawn = ((right - left + 1) + (bottom - top + 1)) / 4.0
                rows.append({"t": times[index] - origin, "track": track, "drawn_px": float(drawn),
                             "projected_px": radius * px_per_unit, "nominal_px": radius / ratio * px_per_unit,
                             "content_px": (content_w * dpr, content_h * dpr)})
    finally:
        host.release_resources()
        target.close()
    return rows


def _p10_p90(values):
    ordered = sorted(values)
    return ordered[int(0.1 * (len(ordered) - 1))], ordered[int(0.9 * (len(ordered) - 1))]


def drawn_summary(rows, *, min_samples: int = 4):
    """The drawn reaction: per frame, a hero's drawn radius over its own nominal drawn size and over the drawn card's
    short side and equal-area side; per hero (``min_samples`` frames or more), the swing (max - min) of those."""
    if not rows:
        return {}
    by_track: dict[int, list] = {}
    for row in rows:
        by_track.setdefault(row["track"], []).append(row)
    short = min(rows[0]["content_px"])
    side = math.sqrt(rows[0]["content_px"][0] * rows[0]["content_px"][1])
    swings_own, swings_short, swings_side = [], [], []
    for samples in by_track.values():
        if len(samples) < min_samples:
            continue
        drawn = [s["drawn_px"] for s in samples]
        swings_own.append((max(drawn) - min(drawn)) / median(s["nominal_px"] for s in samples))
        swings_short.append((max(drawn) - min(drawn)) / short)
        swings_side.append((max(drawn) - min(drawn)) / side)
    return {
        "heroes": len(by_track), "samples": len(rows), "content_px": rows[0]["content_px"],
        "drawn_px_median": median(r["drawn_px"] for r in rows),
        "drawn_over_projected_median": median(r["drawn_px"] / r["projected_px"] for r in rows),
        "drawn_over_nominal_median": median(r["drawn_px"] / r["nominal_px"] for r in rows),
        "drawn_over_nominal_p10_p90": _p10_p90([r["drawn_px"] / r["nominal_px"] for r in rows]),
        "drawn_over_short_side_median": median(r["drawn_px"] / short for r in rows),
        "drawn_over_equal_area_side_median": median(r["drawn_px"] / side for r in rows),
        "swing_over_nominal_median": median(swings_own) if swings_own else None,
        "swing_over_short_side_median": median(swings_short) if swings_short else None,
        "swing_over_equal_area_side_median": median(swings_side) if swings_side else None,
    }


def plot(path: Path, music, curves: dict, ratios: dict, title: str, drawn: dict | None = None) -> None:
    from PIL import Image, ImageDraw

    width, panel, pad = 1600, 220, 60
    colours = {"card": (80, 170, 255), "display_wide": (255, 170, 60), "before": (230, 70, 70)}
    panels = 4 if drawn else 3
    image = Image.new("RGB", (width, pad + panels * (panel + pad)), (18, 20, 24))
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
    if drawn:
        lines(pad + 20 + 3 * (panel + pad), drawn,
              "drawn: big heroes' median drawn outer radius / own nominal drawn radius (device px, offscreen)")
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
    parser.add_argument("--render-fps", type=float, default=0.0,
                        help="also draw the two cards offscreen at this many frames per second of the take and "
                             "measure the big heroes' drawn radii in device pixels (0: logical frames only)")
    parser.add_argument("--card-scale", type=float, default=1.0, help="the card's uniform visual scale (drawn only)")
    parser.add_argument("--dpr", type=float, default=1.0, help="the display's device pixel ratio (drawn only)")
    args = parser.parse_args()
    if args.render_fps > 0.0:
        from PySide6.QtGui import QGuiApplication
        QCoreApplication.instance() or QGuiApplication([])
    else:
        QCoreApplication.instance() or QCoreApplication([])
    card, display = _size(args.card), _size(args.display)
    ordinary_drawn, wide_drawn = drawn_presentations(card, display, scale=args.card_scale, dpr=args.dpr)
    wide = tuple(float(v) for v in wide_drawn.viewport_extent)
    clip = load_clip(args.clip, args.seconds)
    args.output.mkdir(parents=True, exist_ok=False)
    sampled = []
    if args.render_fps > 0.0:
        stamps = [(frame.timestamp_us - clip.frames[0].timestamp_us) / 1e6 for frame in clip.frames]
        step, next_t = 1.0 / args.render_fps, 2.0   # past the cold start
        for index, t in enumerate(stamps):
            if t >= next_t:
                sampled.append(index)
                next_t += step
    card_snaps, wide_snaps = {}, {}
    card_frames, times, resolved = observe(clip, card, preset=args.preset, snapshots_at=sampled, snapshots=card_snaps)
    wide_frames, wide_times, _ = observe(clip, card, preset=args.preset, drawn_world=wide, snapshots_at=sampled,
                                         snapshots=wide_snaps)
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
    drawn_series = {}
    if sampled:
        for name, snaps, frames, presentation in (("card", card_snaps, card_frames, ordinary_drawn),
                                                  ("display_wide", wide_snaps, wide_frames, wide_drawn)):
            frame_dir = args.output / f"frames_{name}"
            frame_dir.mkdir()
            rows = drawn_radii(snaps, frames, times, presentation, frame_dir)
            report["runs"][name]["drawn"] = drawn_summary(rows)
            (args.output / f"drawn_{name}.json").write_text(json.dumps(rows) + "\n", encoding="utf-8")
            per_t: dict[float, list] = {}
            for row in rows:
                per_t.setdefault(row["t"], []).append(row["drawn_px"] / row["nominal_px"])
            drawn_series[name] = [(t, median(v)) for t, v in sorted(per_t.items())]
    (args.output / "report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    music = music_envelope(clip)
    plot(args.output / "response.png", music, curves, ratios,
         f"Bubble card {card[0]:g}x{card[1]:g} vs display-wide {wide[0]:.0f}x{wide[1]:.0f} on "
         f"{display[0]:g}x{display[1]:g}; {Path(args.clip).name} first {args.seconds:g} s, preset index {args.preset}",
         drawn=drawn_series)
    for name, row in report["runs"].items():
        line = {k: round(v, 3) for k, v in row.items() if k in ("zoom", "world_scale", "speed_median",
                                                                 "stream_along_median", "radius_big_median",
                                                                 "density_per_canonical_card", "visible_mean")}
        print(name, line, {k: f"{100 * v:+.1f}%" for k, v in row.get("relative_to_card", {}).items()})
        if "breathing" in row:
            print("   breathing", row["breathing"])
        if row.get("drawn"):
            print("   drawn", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in row["drawn"].items()})
    print("->", args.output)


if __name__ == "__main__":
    main()
