"""Recorded music through DevCurve's production logical path and the Quick render host, offscreen.

Replays a recording (``--reanalyze-pcm`` semantics of ``devcurve_reactivity_audit``: DevCurve's own body lanes
from the recorded PCM through the preset's configured DSP) and renders frames at a uniform cadence that divides
the ~90 Hz logical clock (default 45 fps) into an offscreen GL target: PNG frames, a time strip (consecutive
frames stacked, newest at the bottom) and a contact sheet. No window is ever shown.

Example:
  .venv\\Scripts\\python.exe -m tools.visualizer_replay.devcurve_capture --clip <recording.jsonl>
      --output <new dir> --preset 1 --start 20 --duration 4
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from bisect import bisect_left
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def capture(args):
    from PySide6.QtGui import QGuiApplication
    from PIL import Image, ImageDraw
    import numpy as np
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
    from widgets.spotify_visualizer.compact_clip import load_feature_clip
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    from widgets.spotify_visualizer.feature_replay import PcmReanalysis, ReplayBeatEngine
    from tools.visualizer_replay.driver import replay_clip
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from dataclasses import replace
    from widgets.spotify_visualizer.presentation_geometry import resize_visualizer_presentation
    app = QGuiApplication.instance() or QGuiApplication([])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    clip = load_feature_clip(args.clip)
    origin = clip.frames[0].timestamp_us
    times = [(f.timestamp_us - origin) / 1e6 for f in clip.frames]
    stop = args.start + args.duration
    if stop > times[-1]:
        raise ValueError("Requested recording window is incomplete")
    indices = sorted({bisect_left(times, args.start + i / args.fps) for i in range(math.ceil(args.duration * args.fps))})
    frames = clip.frames[:indices[-1] + 1]
    overrides = {key: json.loads(value) for key, value in (item.split("=", 1) for item in args.set)}
    reanalysis = PcmReanalysis()
    original_accept = ReplayBeatEngine.accept_feature_frame

    def accept(engine, feature):
        result = original_accept(engine, feature)
        reanalysis.accept(engine, feature)
        return result

    with ExitStack() as stack:
        stack.enter_context(patch.object(ReplayBeatEngine, "accept_feature_frame", accept))
        stack.enter_context(patch.object(ReplayBeatEngine, "get_pre_agc_energy_bands",
                                         _SpotifyBeatEngine.get_pre_agc_energy_bands))
        result = replay_clip(FeatureClip("devcurve_capture", tuple(frames)), "devcurve", preset=args.preset - 1,
                             overrides=overrides or None, snapshots_at=indices)
    width, height = (int(v) for v in args.size.split("x"))
    target = OffscreenRenderTarget(width, height)
    host = QuickVisualizerRenderHost()
    matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
    images = []
    try:
        for ordinal, index in enumerate(indices):
            snapshot = result["snapshots"][index]
            if args.fill:
                presentation = resize_visualizer_presentation(
                    snapshot.presentation, display_size=(width, height), outer_origin=(0.0, 0.0), relative_scale=1.0,
                    viewport_extent=(width, height), committed_outer_size=(width, height))
                snapshot = replace(snapshot, presentation=presentation)
            with target.current():
                target.resize(width, height)
                target.bind(clear=(0.04, 0.04, 0.06, 1.0))
                host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                            logical_size=(float(width), float(height)), matrix_values=matrix)
                pixels = target.read_rgba()
            image = Image.fromarray(pixels).convert("RGB")
            if args.png_all:
                image.save(output / f"frame_{ordinal:04d}.png")
            images.append((times[index], image))
    finally:
        with target.current():
            host.release_resources()
        target.close()
    # Time strip: consecutive frames as thin rows would hide shape; stack scaled frames instead.
    tile_w = args.strip_width
    tiles = []
    for t, image in images[:: max(1, args.strip_every)]:
        tile = image.resize((tile_w, round(image.height * tile_w / image.width)))
        ImageDraw.Draw(tile).text((4, 2), f"{args.label} t={t:.3f}s", fill="white")
        tiles.append(tile)
    columns = max(1, args.strip_columns)
    rows = math.ceil(len(tiles) / columns)
    sheet = Image.new("RGB", (tile_w * columns, tiles[0].height * rows), (0, 0, 0))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i // rows) * tile_w, (i % rows) * tile.height))
    sheet.save(output / f"{args.label}_strip.png")
    for k in (0, len(images) // 2, len(images) - 1):
        images[k][1].save(output / f"{args.label}_still_{images[k][0]:.2f}s.png")
    print("captured", len(images), "frames ->", output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preset", type=int, default=1)
    parser.add_argument("--start", type=float, default=20.0)
    parser.add_argument("--duration", type=float, default=4.0)
    parser.add_argument("--fps", type=float, default=45.0)
    parser.add_argument("--size", default="960x360")
    parser.add_argument("--label", default="run")
    parser.add_argument("--strip-every", type=int, default=3)
    parser.add_argument("--strip-width", type=int, default=480)
    parser.add_argument("--strip-columns", type=int, default=2)
    parser.add_argument("--png-all", action="store_true")
    parser.add_argument("--canonical", dest="fill", action="store_false",
                        help="keep the canonical card geometry instead of filling the target")
    parser.add_argument("--set", action="append", default=[])
    args = parser.parse_args()
    capture(args)


if __name__ == "__main__":
    main()
