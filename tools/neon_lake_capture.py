"""Capture current Neon Lake art through the production GL host, without settings writes.

    .venv/Scripts/python tools/neon_lake_capture.py --output logs/neon_before --suite
    .venv/Scripts/python tools/neon_lake_capture.py --output logs/neon_dpr --size 650x375 --dpr 2
    .venv/Scripts/python tools/neon_lake_capture.py --output logs/neon_song --clip logs/visualizer_recordings/dontyouseemetrying_mixed.jsonl --size 650x375 --duration 8 --gif
    .venv/Scripts/python tools/neon_lake_capture.py --output logs/neon_resize --clip logs/visualizer_recordings/dontyouseemetrying_mixed.jsonl --window 2560x1440 --resize 2100x1200,1300x750,650x375 --duration 8 --gif

PNG pixels are actual GPU output, not a golden test. The JSON records the current mutable
Preset 1, canonical resolved settings, physical viewport, logical item and scene allocation.
Single stills use deterministic foundry analyser output. ``--clip`` uses the original
recorded feature frames through replay_clip; the GIF is silent. Offscreen output does
not establish physical-window resize timing or listening acceptance.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Match the production GL policy before importing any GL module.
from rendering.gl_error_policy import disable_per_call_gl_error_checking


def _draw(host, target, snapshot, width, height, window):
    """Draw onto an existing capture/context; callers may retain the production host."""
    from OpenGL import GL as gl
    import numpy as np
    from rendering.gl_error_policy import raise_pending_gl_error
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
    host.render(snapshot=snapshot, viewport=(0, 0, target.width, target.height),
                logical_size=(float(width), float(height)), matrix_values=matrix)
    raise_pending_gl_error(gl, "Neon Lake capture")
    gl.glFinish()
    pixels = gl.glReadPixels(0, 0, target.width, target.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return (np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(target.height, target.width, 4)[::-1].copy(),
            matrix)


def capture(output: Path, *, width=1300, height=750, dpr=1.0, overrides=None, window=None) -> dict:
    from PySide6.QtGui import QImage

    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from rendering.quick.scene3d.frame import item_pixel_rect
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.transition_contact_sheet import TransitionCapture

    activation = resolve_visualizer_activation_payload(
        {"mode": "shockwave_grid", "preset_shockwave_grid": 0}, mode="shockwave_grid")
    settings = {**activation.resolved_config, **(overrides or {})}
    snapshot = _build_spectrum_preview_snapshot(width=width, height=height, mode="shockwave_grid", settings=settings)
    window_width, window_height = window or (width, height)
    pixel_width, pixel_height = round(window_width * dpr), round(window_height * dpr)
    target = TransitionCapture(pixel_width, pixel_height)
    host = QuickVisualizerRenderHost()
    try:
        offset_x, offset_y = (window_width - width) / 2, (window_height - height) / 2
        rgba, matrix = _draw(host, target, snapshot, width, height, (window_width, window_height))
        output.parent.mkdir(parents=True, exist_ok=True)
        image = QImage(rgba.data, pixel_width, pixel_height, 4 * pixel_width, QImage.Format.Format_RGBA8888)
        if not image.save(str(output.with_suffix(".png"))):
            raise OSError(f"could not save {output}")
        renderer = host._implementations["shockwave_grid"]
        render_parameters = dict(snapshot.logical.mode_state.parameters)
        item_rect = item_pixel_rect(SimpleNamespace(viewport=(0, 0, pixel_width, pixel_height),
                                                   logical_size=(width, height), matrix_values=matrix))
        metadata = {
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                     capture_output=True, text=True, check=True).stdout.strip(),
            "renderer": target.driver,
            "preset_name": activation.preset_name, "preset_path": activation.preset_path,
            "logical_size": [width, height], "requested_dpr": dpr,
            "effective_dpr": [pixel_width / window_width, pixel_height / window_height],
            "physical_viewport": [0, 0, pixel_width, pixel_height],
            "physical_card_rect": [round(offset_x * dpr), round(offset_y * dpr),
                                   round(width * dpr), round(height * dpr)],
            "projected_item_pixel_rect_gl": item_rect,
            "logical_window": [window_width, window_height], "matrix": matrix,
            "scene_allocation_width_height_samples": renderer._target.allocation,
            "overrides": overrides or {}, "resolved_settings": settings,
            "effective_pose": {key: render_parameters[key] for key in (
                "shockwave_grid_tilt", "shockwave_grid_turn", "shockwave_grid_scene_scale",
                "shockwave_grid_scene_pan_x", "shockwave_grid_scene_pan_y")},
            "effective_scalar_render_parameters": {key: value for key, value in render_parameters.items()
                                                   if isinstance(value, (str, bool, int, float))},
            "fixture": "onboarding production capture; fixed analyser output at logical time 1.12",
        }
        output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        print(f"captured {output.with_suffix('.png')} ({pixel_width}x{pixel_height}, DPR {dpr})", flush=True)
        return metadata
    finally:
        host.release_resources()
        target.close()


def capture_motion(output: Path, clip_path: Path, *, width, height, dpr, window, overrides,
                   start=0., duration=8., fps=12., resize=(), gif=False, resize_smooth=False,
                   rgb_roi=None, all_frames=False):
    """Replay native recorded features, retaining one real GL context and mode host."""
    from bisect import bisect_left
    from dataclasses import replace
    from PIL import Image, ImageDraw
    import numpy as np
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from widgets.spotify_visualizer.feature_frame import FeatureClip, FeatureFrame
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.transition_contact_sheet import TransitionCapture
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.visualizer_replay.driver import replay_clip

    source_frames = []
    with clip_path.open(encoding="utf-8") as stream:
        for line in stream:
            frame = FeatureFrame.from_dict(json.loads(line))
            origin = source_frames[0].timestamp_us if source_frames else frame.timestamp_us
            if (frame.timestamp_us-origin)/1e6 > start+duration:
                break
            source_frames.append(frame)
    if not source_frames or any(frame.real is None for frame in source_frames):
        raise ValueError("motion capture requires a non-empty real-scale recorded clip")
    clip = FeatureClip("native_music_capture", tuple(source_frames))
    times = [(frame.timestamp_us-clip.frames[0].timestamp_us)/1e6 for frame in clip.frames]
    if start >= times[-1]:
        raise ValueError("requested start is beyond the recorded clip")
    stop = min(start+duration, times[-1])
    wanted = sorted({min(len(times)-1, bisect_left(times, start+index/fps))
                     for index in range(max(1, math.ceil((stop-start)*fps)))})
    sizes = tuple(resize) or ((width, height),)
    window = window or (max(w for w, _h in sizes), max(h for _w, h in sizes))
    activation = resolve_visualizer_activation_payload(
        {"mode": "shockwave_grid", "preset_shockwave_grid": 0}, mode="shockwave_grid")
    settings = {**activation.resolved_config, **overrides}
    target = TransitionCapture(round(window[0]*dpr), round(window[1]*dpr))
    host = QuickVisualizerRenderHost()
    output.mkdir(parents=True, exist_ok=True)
    try:
        result = replay_clip(clip, "shockwave_grid", settings=settings, snapshots_at=wanted)
        presentations = {size: _build_spectrum_preview_snapshot(
            width=size[0], height=size[1], mode="shockwave_grid", settings=settings).presentation for size in sizes}
        first = result["snapshots"][wanted[0]]
        # Establish maximum scene allocation before measuring reuse while resizing.
        for size in sorted(set(sizes), key=lambda size: size[0]*size[1], reverse=True):
            _draw(host, target, replace(first, presentation=presentations[size]), *size, window)
        renderer = host._implementations["shockwave_grid"]
        records, animation, contacts = [], [], []
        for ordinal, index in enumerate(wanted):
            elapsed = times[index]-start
            if resize_smooth and len(sizes)>1:
                position = elapsed/2.
                left = int(position) % len(sizes)
                blend = position-math.floor(position)
                size = tuple(round(a+(b-a)*blend) for a,b in zip(sizes[left],sizes[(left+1)%len(sizes)]))
                if size not in presentations:
                    presentations[size] = _build_spectrum_preview_snapshot(
                        width=size[0],height=size[1],mode="shockwave_grid",settings=settings).presentation
            else:
                size = sizes[int(elapsed) % len(sizes)]
            snapshot = replace(result["snapshots"][index], presentation=presentations[size])
            rgba, _matrix = _draw(host, target, snapshot, *size, window)
            image = Image.fromarray(rgba, "RGBA").convert("RGB")
            sampled_still = ordinal % max(1, round(fps)) == 0 or ordinal == len(wanted)-1
            if all_frames or sampled_still:
                image.save(output / f"frame_{ordinal:04d}.png")
            if sampled_still:
                tile = image.copy()
                tile.thumbnail((400, 250))
                labelled = Image.new("RGB", (400, 275), "#111827")
                labelled.paste(tile, ((400-tile.width)//2, 0))
                ImageDraw.Draw(labelled).text((8, 255), f"{times[index]:.2f}s  {size[0]}x{size[1]} DPR{dpr}", fill="white")
                contacts.append(labelled)
            if gif:
                image.thumbnail((960, 540))
                animation.append(image)
            state = snapshot.logical.mode_state
            records.append({"source_index": index, "source_time_s": times[index], "logical_size": size,
                            "events": list(state.events), "terrain_bands": list(state.terrain_bands), "terrain_phase": state.terrain_phase,
                            "animation_time": state.animation_time,
                            "bars_mean": sum(snapshot.logical.common.bars)/max(1, len(snapshot.logical.common.bars)),
                            "scene_allocation": renderer._target.allocation,
                            "scene_handles": dict(renderer._target._names),
                            "terrain_uploads": renderer._heightfield.uploads,
                            "terrain_texture": renderer._heightfield.texture_id,
                            "point_mesh": renderer._points_data,
                            "terrain_mesh": renderer._mesh_data})
            if rgb_roi:
                left, top, right, bottom = [round(value*extent) for value,extent in
                                           zip(rgb_roi,(target.width,target.height,target.width,target.height))]
                region = rgba[top:bottom,left:right,:3]
                if not region.size:
                    raise ValueError("RGB ROI has no physical pixels")
                records[-1]["rgb_roi"] = {"rect": [left,top,right,bottom],
                    "mean": float(region.mean()),
                    "nearwhite_percent": float(np.mean(np.all(region>=250,axis=2))*100)}
            if ordinal % max(1, round(fps*2)) == 0:
                print(f"rendered {ordinal+1}/{len(wanted)} native music frames", flush=True)
        sheet = Image.new("RGB", (1200, 275*math.ceil(len(contacts)/3)), "#111827")
        for index, tile in enumerate(contacts):
            sheet.paste(tile, ((index % 3)*400, (index // 3)*275))
        sheet.save(output / "contact.png")
        if gif:
            animation[0].save(output / "motion.gif", save_all=True, append_images=animation[1:],
                              duration=round(1000/fps), loop=0)
        document = {"source": str(clip_path.resolve()), "source_frames_replayed": len(clip.frames),
                    "native_history_frames": sum(frame.capture_history is not None for frame in clip.frames),
                    "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             capture_output=True, text=True, check=True).stdout.strip(),
                    "source_schema": sorted({frame.schema_version for frame in clip.frames}),
                    "start_s": start, "stop_s": stop, "fps": fps, "renderer": target.driver,
                    "resize_smooth": resize_smooth,
                    "rgb_roi_normalized": rgb_roi, "saved_all_rgb_frames": all_frames,
                    "physical_viewport": [target.width, target.height], "requested_dpr": dpr,
                    "preset_path": activation.preset_path, "resolved_settings": settings, "frames": records,
                    "same_scene_handles": all(row["scene_handles"] == records[0]["scene_handles"] for row in records),
                    "same_meshes": all((row["point_mesh"], row["terrain_mesh"]) ==
                                       (records[0]["point_mesh"], records[0]["terrain_mesh"]) for row in records),
                    "same_terrain_uploads": all(row["terrain_uploads"] == records[0]["terrain_uploads"] for row in records),
                    "scope": "native recorded-feature replay; silent GIF, sampled frames, offscreen host; no physical resize timing"}
        (output / "motion.json").write_text(json.dumps(document, indent=2)+"\n", encoding="utf-8")
        print(f"saved {output / 'contact.png'} and motion metadata" + (" + GIF" if gif else ""), flush=True)
        return document
    finally:
        host.release_resources()
        target.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True, help="PNG stem, or directory with --suite")
    parser.add_argument("--size", default="1300x750", help="logical item dimensions")
    parser.add_argument("--dpr", type=float, default=1.0)
    parser.add_argument("--window", help="logical render-window size; centres the card inside it")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=JSON", help="in-memory settings override")
    parser.add_argument("--suite", action="store_true", help="baseline size, DPR, angle, zoom and aspect views")
    parser.add_argument("--clip", type=Path, help="native recorded-feature JSONL; enables retained-host motion capture")
    parser.add_argument("--start", type=float, default=0.)
    parser.add_argument("--duration", type=float, default=8.)
    parser.add_argument("--fps", type=float, default=12.)
    parser.add_argument("--resize", help="comma-separated logical card sizes, alternating each second on one host")
    parser.add_argument("--resize-smooth", action="store_true", help="interpolate resize nodes continuously, two seconds per segment")
    parser.add_argument("--gif", action="store_true", help="explicitly export a silent motion GIF, maximum960x540")
    parser.add_argument("--rgb-roi", help="normalized x0,y0,x1,y1 ROI; measure every unquantized RGB frame")
    parser.add_argument("--all-frames", action="store_true", help="save every physical RGB PNG before GIF quantization")
    args = parser.parse_args()
    width, height = map(int, args.size.lower().split("x"))
    window = tuple(map(int, args.window.lower().split("x"))) if args.window else None
    if (min(width, height) <= 0 or not math.isfinite(args.dpr) or args.dpr <= 0
            or (window is not None and (len(window) != 2 or min(window) <= 0))):
        parser.error("dimensions and finite DPR must be positive")
    if min(round(value * args.dpr) for value in (window or (width, height))) <= 0:
        parser.error("DPR must produce positive physical dimensions")
    overrides = {}
    for pair in args.set:
        key, separator, value = pair.partition("=")
        if not separator:
            parser.error("--set requires KEY=JSON")
        overrides[key] = json.loads(value)
    if not disable_per_call_gl_error_checking():
        raise RuntimeError("OpenGL.GL imported before production error policy")
    if args.clip:
        if not all(math.isfinite(value) for value in (args.start, args.duration, args.fps)) or args.start < 0 or min(args.duration, args.fps) <= 0:
            parser.error("motion start must be nonnegative; duration and fps finite and positive")
        resize = [tuple(map(int, part.lower().split('x'))) for part in args.resize.split(',')] if args.resize else ()
        if any(len(size) != 2 or min(size) <= 0 for size in resize):
            parser.error("resize dimensions must be positive WIDTHxHEIGHT pairs")
        rgb_roi = tuple(map(float,args.rgb_roi.split(','))) if args.rgb_roi else None
        if rgb_roi and (len(rgb_roi)!=4 or not all(math.isfinite(v) and 0<=v<=1 for v in rgb_roi)
                        or rgb_roi[0]>=rgb_roi[2] or rgb_roi[1]>=rgb_roi[3]):
            parser.error("RGB ROI requires ordered normalized x0,y0,x1,y1 coordinates")
        capture_motion(args.output, args.clip, width=width, height=height, dpr=args.dpr, window=window,
                       overrides=overrides, start=args.start, duration=args.duration, fps=args.fps,
                       resize=resize, gif=args.gif, resize_smooth=args.resize_smooth,
                       rgb_roi=rgb_roi, all_frames=args.all_frames)
        return
    cases = (
        ("large", 2100, 1200, 1., {}), ("medium", 1300, 750, 1., {}),
        ("small", 650, 375, 1., {}), ("small_dpr2", 650, 375, 2., {}),
        ("low", 1300, 750, 1., {"shockwave_grid_tilt": .17}),
        ("high", 1300, 750, 1., {"shockwave_grid_tilt": .58}),
        ("zoom_out", 1300, 750, 1., {"shockwave_grid_scene_scale": .75}),
        ("zoom_in", 1300, 750, 1., {"shockwave_grid_scene_scale": 1.85}),
        ("wide", 1600, 500, 1., {}), ("tall", 700, 1050, 1., {}),
        ("turned", 1300, 750, 1., {"shockwave_grid_turn": .2}),
        ("embedded_small", 650, 375, 1., {}, (2560, 1440)),
        ("embedded_medium", 1300, 750, 1., {}, (2560, 1440)),
        ("embedded_large", 2100, 1200, 1., {}, (2560, 1440)),
    ) if args.suite else ((None, width, height, args.dpr, {}),)
    for name, w, h, ratio, pose, *embedded in cases:
        capture(args.output / name if name else args.output, width=w, height=h, dpr=ratio,
                overrides={**overrides, **pose}, window=embedded[0] if embedded else window)


if __name__ == "__main__":
    main()
