"""Music vs Neon Lake response: the song's own envelope against what the lake, island and shore visibly do.

The Neon Lake sibling of ``waveform_music_response`` (whose ``music`` step it reuses unchanged: the recording's own
PCM envelope beside the pipeline's real-music loudness). The ``response`` step replays recorded clips through the
production runtime and renders sampled frames offscreen through the production host (no window), measuring per
frame, on masks taken once from the preset's own geometry:

  lake_lines   the visible line mesh over the lake: mean positive luminance above a 9 px local mean (lines and
               glints, not the mirror's broad light), 0..255;
  lake_mean    the lake's mean luminance;
  island       the island's mean luminance (land enclosed by the lake);
  shore        mean luminance within a few pixels of the lake's edge (the shoreline and its glow);
  frame_mean   the whole frame's mean luminance;
and the logical drives the renderer reads that frame: midband, beat pulse, mean bar level, live wave count, the summed
live wave strength (faded as the shader fades it) and the mean Terrain Reaction drive.

    python -m tools.visualizer_replay.neon_lake_music_response music --clips a.jsonl,b.jsonl --out music.npy
    python -m tools.visualizer_replay.neon_lake_music_response response --clips a.jsonl,b.jsonl --preset 1
        --size 722x1086 --fps 15 --out p1.npy [--set shockwave_grid_key=json ...]
    python -m tools.visualizer_replay.neon_lake_music_response report --music music.npy --response main=p1.npy
        [--response branch=p1b.npy] --out <dir>

Offscreen pixels are real GPU output of the production renderer; the clips are replayed per song from a fresh
activation (as the capture tool does), so this is not continuous play across songs.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402

RESPONSE_COLUMNS = ("t", "song", "song_time", "lake_lines", "lake_mean", "island", "shore", "frame_mean",
                    "midband", "beat_pulse", "bars_mean", "waves", "wave_strength", "terrain_drive")
_LUMA = (0.2126, 0.7152, 0.0722)


def _luma(rgb):
    import numpy as np
    return rgb[..., :3].astype(np.float32) @ np.asarray(_LUMA, np.float32)


def _box_mean(values, radius):
    """Mean over a (2r+1)^2 box, edges clamped (summed-area table)."""
    import numpy as np
    padded = np.pad(values, radius + 1, mode="edge").astype(np.float64)
    table = padded.cumsum(0).cumsum(1)
    k = 2 * radius + 1
    total = table[k:, k:] - table[:-k, k:] - table[k:, :-k] + table[:-k, :-k]
    return (total / (k * k))[: values.shape[0], : values.shape[1]].astype(np.float32)


def region_masks(water):
    """Lake, island (land enclosed by the lake, per row and column) and shore band masks from a water mask."""
    import numpy as np
    # Close the land marks drawn over the mask's water (a few pixels each) and drop specks.
    water = _box_mean(water.astype(np.float32), 3) > 0.5
    rows, cols = water.shape
    enclosed_r = np.zeros_like(water)
    enclosed_c = np.zeros_like(water)
    for y in range(rows):
        xs = np.flatnonzero(water[y])
        if xs.size:
            enclosed_r[y, xs[0]:xs[-1] + 1] = True
    for x in range(cols):
        ys = np.flatnonzero(water[:, x])
        if ys.size:
            enclosed_c[ys[0]:ys[-1] + 1, x] = True
    # An island on the far shore is enclosed by the lake only across it (row-wise); the column test drops specks
    # inside open water.
    enclosed = enclosed_r & ~water & ~(enclosed_c & (_box_mean(water.astype(np.float32), 5) > 0.6))
    # The island is the largest compact enclosed blob; thin slivers along the far bank (land showing between
    # the mask's water and the far shore's fringe) are elongated and left out.
    island = np.zeros_like(water)
    best = 0
    seen = np.zeros_like(water)
    for y0, x0 in zip(*np.nonzero(enclosed)):
        if seen[y0, x0]:
            continue
        stack, members = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            members.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                v, u = y + dy, x + dx
                if 0 <= v < rows and 0 <= u < cols and enclosed[v, u] and not seen[v, u]:
                    seen[v, u] = True
                    stack.append((v, u))
        ys, xs = np.asarray(members).T
        h, w = np.ptp(ys) + 1, np.ptp(xs) + 1
        if len(members) > best and max(h, w) / min(h, w) < 4.0 and len(members) > 0.4 * h * w:
            best = len(members)
            # The island and its glow: the blob's box grown by 6 px, open water left out.
            island = np.zeros_like(water)
            island[max(0, ys.min() - 6):ys.max() + 7, max(0, xs.min() - 6):xs.max() + 7] = True
            island &= ~water
    # The shore: pixels within 3 px of both water and something else (the edge band, either side of it).
    share = _box_mean(water.astype(np.float32), 3)
    shore = (share > 0.02) & (share < 0.98)
    return water, island, shore


def water_mask(rgba):
    """Water pixels of a mask render (water drawn pure green, everything else in its own colours)."""
    rgb = rgba[..., :3].astype("int16")
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (g > 40) & (g > r + 25) & (g > b + 25)


_MASK_OVERRIDES = {
    "shockwave_grid_water_color": [0, 255, 0, 255], "shockwave_grid_water_shine": 0.0,
    "shockwave_grid_water_detail": 0.0, "shockwave_grid_water_glint": 0.0, "shockwave_grid_shore_glow": 0.0,
    "shockwave_grid_water_reflection": 0.0, "shockwave_grid_floor": 1.0, "shockwave_grid_glow": 0.0,
    "shockwave_grid_water_reaction": 0.0,
}


def response(clips, preset, size, fps, out: Path, overrides, start=0.0, duration=None) -> None:
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    import numpy as np
    from bisect import bisect_left
    from dataclasses import replace
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_DECAY, SHOCKWAVE_LIFETIME
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.neon_lake_capture import _draw
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.transition_contact_sheet import TransitionCapture
    from tools.visualizer_replay.driver import replay_clip
    from widgets.spotify_visualizer.feature_frame import load_jsonl

    width, height = size
    activation = resolve_visualizer_activation_payload(
        {"mode": "shockwave_grid", "preset_shockwave_grid": preset - 1}, mode="shockwave_grid")
    settings = {**activation.resolved_config, **overrides}
    target = TransitionCapture(width, height)
    host = QuickVisualizerRenderHost()
    rows = []
    try:
        still = _build_spectrum_preview_snapshot(width=width, height=height, mode="shockwave_grid",
                                                 settings={**settings, **_MASK_OVERRIDES})
        rgba, _ = _draw(host, target, still, width, height, (width, height))
        lake, island, shore = region_masks(water_mask(rgba))
        print(f"masks: lake {lake.sum()} px, island {island.sum()} px, shore {shore.sum()} px", flush=True)
        np.savez_compressed(out.with_suffix(".masks.npz"), lake=lake, island=island, shore=shore)
        presentation = _build_spectrum_preview_snapshot(width=width, height=height, mode="shockwave_grid",
                                                        settings=settings).presentation
        t_total = 0.0
        for song, path in enumerate(clips):
            clip = load_jsonl(Path(path))
            times = [(f.timestamp_us - clip.frames[0].timestamp_us) / 1e6 for f in clip.frames]
            stop = times[-1] if duration is None else min(times[-1], start + duration)
            wanted = sorted({min(len(times) - 1, bisect_left(times, start + i / fps))
                             for i in range(max(1, math.ceil((stop - start) * fps)))})
            result = replay_clip(clip, "shockwave_grid", settings=settings, snapshots_at=wanted)
            for ordinal, index in enumerate(wanted):
                snapshot = replace(result["snapshots"][index], presentation=presentation)
                rgba, _ = _draw(host, target, snapshot, width, height, (width, height))
                lum = _luma(rgba)
                lines = np.maximum(0.0, lum - _box_mean(lum, 4))
                logical = snapshot.logical
                state = logical.mode_state
                bars = list(logical.common.bars)
                count = len(bars)
                low, high = count // 4, max(count // 4 + 1, count * 3 // 5)
                midband = max(0.0, min(1.0, sum(bars[low:high]) / max(1, len(bars[low:high]))))
                live = [e for e in state.events if 0.0 <= float(e[0]) < SHOCKWAVE_LIFETIME]
                pulse = max((min(1.0, s) * math.exp(-a * 2.8) for a, _x, _z, s in live), default=0.0)
                strength = sum(s * math.exp(-a / SHOCKWAVE_DECAY) for a, _x, _z, s in live)
                rows.append((t_total + times[index], song, times[index],
                             float(lines[lake].mean()) if lake.any() else 0.0,
                             float(lum[lake].mean()) if lake.any() else 0.0,
                             float(lum[island].mean()) if island.any() else 0.0,
                             float(lum[shore].mean()) if shore.any() else 0.0,
                             float(lum.mean()), midband, pulse, sum(bars) / max(1, count), len(live), strength,
                             sum(state.terrain_bands) / len(state.terrain_bands)))
                if ordinal % max(1, int(fps * 10)) == 0:
                    print(f"song {song} frame {ordinal + 1}/{len(wanted)} t={times[index]:.1f}s", flush=True)
            t_total += times[-1] + 1.0
    finally:
        host.release_resources()
        target.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    np.save(out, np.asarray(rows, np.float64))
    print("response rows", len(rows), "->", out)


def _smooth(values, width):
    import numpy as np
    if width <= 1 or len(values) < width:
        return values
    return np.convolve(values, np.ones(width) / width, mode="same")


def report(music_path: Path, responses: dict[str, Path], out: Path) -> None:
    """Per song: music (white) on top, every response file overlaid below; per-song metrics in a text file."""
    import numpy as np
    from PIL import Image, ImageDraw
    out.mkdir(parents=True, exist_ok=True)
    m = np.load(music_path)
    loaded = {name: np.load(path) for name, path in responses.items()}
    colours = [(110, 160, 255), (255, 150, 60), (120, 220, 140), (230, 110, 200)]
    col = {name: i for i, name in enumerate(RESPONSE_COLUMNS)}
    lines = []
    for song in sorted(set(m[:, 0].astype(int))):
        ms = m[m[:, 0] == song]
        series = {name: data[data[:, 1] == song] for name, data in loaded.items()}
        series = {name: rs for name, rs in series.items() if len(rs)}
        if not series:
            continue
        width, left, row_h = 1900, 130, 110
        white = (235, 235, 235)
        panels = [("loudness 3-17", [(ms[:, 1], ms[:, 5], white)]), ("rms dBFS", [(ms[:, 1], ms[:, 2], white)]),
                  ("flux", [(ms[:, 1], _smooth(ms[:, 4], 9), white)])]
        for label in ("lake_lines", "island", "shore", "lake_mean", "frame_mean", "midband", "beat_pulse",
                      "wave_strength", "terrain_drive"):
            panels.append((label, [(rs[:, col["song_time"]], rs[:, col[label]], colours[k])
                                   for k, rs in enumerate(series.values())]))
        image = Image.new("RGB", (width, 30 + row_h * len(panels)), (14, 14, 20))
        draw = ImageDraw.Draw(image)
        draw.text((10, 8), f"song {song}: music (white) on top; response: " +
                  ", ".join(f"{n} {c}" for n, c in zip(series, colours)), fill="white")
        t_max = float(ms[-1, 1]) or 1.0
        for row, (label, traces) in enumerate(panels):
            low = float(min(np.min(v) for _t, v, _c in traces))
            high = float(max(np.max(v) for _t, v, _c in traces))
            high = high if high > low else low + 1.0
            top = 30 + row * row_h
            draw.text((10, top + 4), label, fill="white")
            draw.text((10, top + 20), f"{high:.2f}", fill=(140, 140, 140))
            draw.text((10, top + row_h - 18), f"{low:.2f}", fill=(140, 140, 140))
            for second in range(0, int(t_max) + 1, 5):
                x = left + (width - left - 10) * second / t_max
                draw.line((x, top, x, top + row_h - 4), fill=(32, 32, 42))
            for times, values, colour in traces:
                points = [(left + (width - left - 10) * float(tt) / t_max,
                           top + 4 + (row_h - 12) * (1 - (float(v) - low) / (high - low)))
                          for tt, v in zip(times, values)]
                if len(points) > 1:
                    draw.line(points, fill=colour, width=1)
        image.save(out / f"song{song}_music_vs_neon.png")
        # Metrics on 1 s means, response sampled at its own frames against the loudness at the same time.
        for name, rs in series.items():
            t = rs[:, col["song_time"]]
            loud = np.interp(t, ms[:, 1], ms[:, 5])
            seconds = np.floor(t).astype(int)
            keys = np.unique(seconds)
            loud_1s = np.array([loud[seconds == k].mean() for k in keys])
            parts = [f"song {song} {name:8s}"]
            for label in ("lake_lines", "island", "shore", "lake_mean"):
                v = rs[:, col[label]]
                v_1s = np.array([v[seconds == k].mean() for k in keys])
                corr = (float(np.corrcoef(loud_1s, v_1s)[0, 1])
                        if len(keys) > 3 and np.ptp(loud_1s) and np.ptp(v_1s) else float("nan"))
                p5, p50, p95 = np.percentile(v, [5, 50, 95])
                parts.append(f"{label} p5/50/95 {p5:6.2f}/{p50:6.2f}/{p95:6.2f} corr(loud) {corr:+.2f}")
            loud_q = np.percentile(loud, [25, 75])
            quiet_sel, loud_sel = loud <= loud_q[0], loud >= loud_q[1]
            v = rs[:, col["lake_lines"]]
            parts.append(f"lake_lines loud/quiet quartile {v[loud_sel].mean():.2f}/{v[quiet_sel].mean():.2f}")
            parts.append(f"music loudness p5/50/95 {' / '.join(f'{x:.1f}' for x in np.percentile(loud, [5, 50, 95]))}")
            lines.append("  ".join(parts))
    (out / "neon_music_vs_response.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("music")
    p.add_argument("--clips", required=True)
    p.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    p = sub.add_parser("response")
    p.add_argument("--clips", required=True)
    p.add_argument("--preset", type=int, default=1)
    p.add_argument("--size", default="722x1086")
    p.add_argument("--fps", type=float, default=15.0)
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--duration", type=float)
    p.add_argument("--set", action="append", default=[], metavar="KEY=JSON")
    p.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    p = sub.add_parser("report")
    p.add_argument("--music", type=Path, required=True)
    p.add_argument("--response", action="append", required=True, help="name=path.npy")
    p.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    args = parser.parse_args()
    evidence_media.redirect_output(args, "out", "neon_lake_music_response")
    if args.command == "music":
        from tools.visualizer_replay.waveform_music_response import music
        music([Path(c) for c in args.clips.split(",")], args.out)
    elif args.command == "response":
        overrides = {}
        for item in args.set:
            key, _, value = item.partition("=")
            overrides[key] = json.loads(value)
        response(args.clips.split(","), args.preset, tuple(int(v) for v in args.size.split("x")), args.fps,
                 args.out, overrides, args.start, args.duration)
    else:
        report(args.music, dict(item.split("=", 1) for item in args.response), args.out)


if __name__ == "__main__":
    main()
    evidence_media.finish(0)
