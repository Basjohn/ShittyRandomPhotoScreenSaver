"""Render Extruded Bubble through the production GL host from a real recorded music clip, without settings writes.

    .venv/Scripts/python tools/extruded_bubble_capture.py --output tmp/eb_capture --clip logs/visualizer_recordings/<clip>.jsonl
    .venv/Scripts/python tools/extruded_bubble_capture.py --output tmp/eb_capture --clip <clip> --size 1672x941 --start 20 --duration 6 --gif
    .venv/Scripts/python tools/extruded_bubble_capture.py --output tmp/eb_capture --clip <clip> --set extruded_bubble_turn=0.25

The clip's recorded feature frames drive the mode's own simulation through ``replay_clip`` (the production logical
capture: real intensity and onsets on the logical clock); each sampled snapshot is drawn by the production
``QuickVisualizerRenderHost`` into an offscreen target. Writes sampled frames, a contact sheet, optional silent GIF and
``capture.json`` (settings, per-frame simulation scalars and GPU time per frame from a TIME_ELAPSED query). Offscreen
output is not physical acceptance (no real window, display timing or listening).
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Match the production GL policy before importing any GL module.
from rendering.gl_error_policy import disable_per_call_gl_error_checking

MODE = "extruded_bubble"


def _draw(host, target, snapshot, size, window):
    """One frame of the card centred in the window; returns RGBA pixels and the frame's GPU milliseconds."""
    from OpenGL import GL as gl
    import numpy as np
    from rendering.gl_error_policy import raise_pending_gl_error
    width, height = size
    window_width, window_height = window
    offset_x, offset_y = (window_width - width) / 2, (window_height - height) / 2
    matrix = (2 / window_width, 0, 0, 0, 0, -2 / window_height, 0, 0, 0, 0, 1, 0,
              -1 + 2 * offset_x / window_width, 1 - 2 * offset_y / window_height, 0, 1)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
    gl.glViewport(0, 0, target.width, target.height)
    gl.glDisable(gl.GL_SCISSOR_TEST)
    gl.glDepthMask(gl.GL_TRUE)
    gl.glClearColor(.1, .12, .16, 1.)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    query = int(np.asarray(gl.glGenQueries(1)).ravel()[0])
    gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
    host.render(snapshot=snapshot, viewport=(0, 0, target.width, target.height),
                logical_size=(float(width), float(height)), matrix_values=matrix)
    gl.glEndQuery(gl.GL_TIME_ELAPSED)
    raise_pending_gl_error(gl, "Extruded Bubble capture")
    gl.glFinish()
    elapsed = int(np.asarray(gl.glGetQueryObjectuiv(query, gl.GL_QUERY_RESULT)).ravel()[0]) / 1e6
    gl.glDeleteQueries(1, [query])
    pixels = gl.glReadPixels(0, 0, target.width, target.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    rgba = np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(target.height, target.width, 4)[::-1].copy()
    return rgba, elapsed


def capture(output: Path, clip_path: Path, *, size, window, overrides, start, duration, fps, gif):
    from bisect import bisect_left
    from PIL import Image, ImageDraw
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.transition_contact_sheet import TransitionCapture
    from tools.visualizer_replay.driver import replay_clip
    from widgets.spotify_visualizer.feature_frame import FeatureClip, FeatureFrame

    frames = []
    with clip_path.open(encoding="utf-8") as stream:
        for line in stream:
            frame = FeatureFrame.from_dict(json.loads(line))
            origin = frames[0].timestamp_us if frames else frame.timestamp_us
            if (frame.timestamp_us - origin) / 1e6 > start + duration:
                break
            frames.append(frame)
    if not frames:
        raise ValueError("the clip holds no frames")
    clip = FeatureClip("extruded_bubble_capture", tuple(frames))
    times = [(frame.timestamp_us - clip.frames[0].timestamp_us) / 1e6 for frame in clip.frames]
    if start >= times[-1]:
        raise ValueError("requested start is beyond the recorded clip")
    stop = min(start + duration, times[-1])
    wanted = sorted({min(len(times) - 1, bisect_left(times, start + index / fps))
                     for index in range(max(1, math.ceil((stop - start) * fps)))})
    activation = resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": 0}, mode=MODE)
    settings = {**activation.resolved_config, **overrides}
    window = window or size
    target = TransitionCapture(*window)
    host = QuickVisualizerRenderHost()
    output.mkdir(parents=True, exist_ok=True)
    try:
        result = replay_clip(clip, MODE, settings=settings, snapshots_at=wanted)
        records, contacts, animation = [], [], []
        for ordinal, index in enumerate(wanted):
            snapshot = result["snapshots"][index]
            rgba, gpu_ms = _draw(host, target, snapshot, size, window)
            image = Image.fromarray(rgba, "RGBA").convert("RGB")
            image.save(output / f"frame_{ordinal:04d}.png")
            state = snapshot.logical.mode_state
            records.append({"source_index": index, "source_time_s": times[index], "gpu_ms": gpu_ms,
                            "bubbles": len(state.bubbles) // 8, "clusters": len(state.clusters) // 4,
                            **{name: getattr(state, name) for name in (
                                "time", "level", "breath", "flash", "sustain", "drift", "emission",
                                "stream_speed")}})
            if ordinal % max(1, round(fps)) == 0 or ordinal == len(wanted) - 1:
                tile = image.copy()
                tile.thumbnail((400, 250))
                labelled = Image.new("RGB", (400, 275), "#111827")
                labelled.paste(tile, ((400 - tile.width) // 2, 0))
                ImageDraw.Draw(labelled).text((8, 255), f"{times[index]:.2f}s  level {state.level:.2f}  "
                                                        f"{gpu_ms:.2f} ms", fill="white")
                contacts.append(labelled)
            if gif:
                image.thumbnail((960, 540))
                animation.append(image)
        sheet = Image.new("RGB", (1200, 275 * math.ceil(len(contacts) / 3)), "#111827")
        for index, tile in enumerate(contacts):
            sheet.paste(tile, ((index % 3) * 400, (index // 3) * 275))
        sheet.save(output / "contact.png")
        if gif:
            animation[0].save(output / "motion.gif", save_all=True, append_images=animation[1:],
                              duration=round(1000 / fps), loop=0)
        steady = sorted(row["gpu_ms"] for row in records[1:]) or [records[0]["gpu_ms"]]
        document = {"source": str(clip_path.resolve()), "start_s": start, "stop_s": stop, "fps": fps,
                    "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             capture_output=True, text=True, check=True).stdout.strip(),
                    "renderer": target.driver, "logical_size": list(size), "window": list(window),
                    "gpu_ms_median_p90": [steady[len(steady) // 2], steady[min(len(steady) - 1, int(len(steady) * 0.9))]],
                    "preset_path": activation.preset_path, "overrides": overrides, "frames": records,
                    "scope": "recorded-feature replay through the production host, offscreen; first frame compiles"}
        (output / "capture.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        print(f"saved {len(records)} frames, {output / 'contact.png'}; GPU median/p90 "
              f"{document['gpu_ms_median_p90'][0]:.2f}/{document['gpu_ms_median_p90'][1]:.2f} ms", flush=True)
        return document
    finally:
        host.release_resources()
        target.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True, help="output directory")
    parser.add_argument("--clip", type=Path, required=True, help="recorded feature JSONL (real-music recording)")
    parser.add_argument("--size", default="1300x750", help="logical card size")
    parser.add_argument("--window", help="logical window size; centres the card inside it")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float, default=4.0)
    parser.add_argument("--fps", type=float, default=6.0)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=JSON", help="in-memory settings override")
    parser.add_argument("--gif", action="store_true", help="also export a silent GIF (at most 960x540)")
    args = parser.parse_args()
    size = tuple(map(int, args.size.lower().split("x")))
    window = tuple(map(int, args.window.lower().split("x"))) if args.window else None
    if len(size) != 2 or min(size) <= 0 or (window is not None and (len(window) != 2 or window[0] < size[0] or window[1] < size[1])):
        parser.error("sizes must be positive WIDTHxHEIGHT and the window at least the card")
    overrides = {}
    for pair in args.set:
        key, separator, value = pair.partition("=")
        if not separator:
            parser.error("--set requires KEY=JSON")
        overrides[key] = json.loads(value)
    if not disable_per_call_gl_error_checking():
        raise RuntimeError("OpenGL.GL imported before production error policy")
    capture(args.output, args.clip, size=size, window=window, overrides=overrides, start=args.start,
            duration=args.duration, fps=args.fps, gif=args.gif)


if __name__ == "__main__":
    main()
