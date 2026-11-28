"""Render deterministic transition frames through the native core, as the product draws them.

No runtime timers or settings writes. This diagnostic draws through ``tools/native_transition_capture.py``
(``NativeTransitionCapture``: the native background layer in the process's hidden host, no window), checks exact
endpoints and writes optional contact sheets. ``fixture_images`` (textured, nonblack test scenes) and
``production_transition_spec`` (a transition resolved through the complete production resolver) are the owners the
capture, the media tools and the reference checks share. Physical Quick multi-display/load acceptance remains a
separate gate.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402


def fixture_images(width: int, height: int):
    """Textured, nonblack test scenes expose UV discontinuity and image holes."""
    import numpy as np
    from PIL import Image, ImageDraw

    y, x = np.mgrid[0:height, 0:width]
    u, v = x / max(1, width-1), y / max(1, height-1)
    images = []
    for index in range(2):
        pixels = np.empty((height, width, 4), dtype=np.uint8)
        pixels[..., 0] = (45 + 135 * (1-v) + 30*np.sin(u*8+index)).clip(20, 245)
        pixels[..., 1] = (65 + 110 * (u if index else v)).clip(20, 245)
        pixels[..., 2] = (90 + 100 * (v if index else 1-u)).clip(20, 245)
        if index: pixels[..., :3] = pixels[..., [2, 0, 1]]
        pixels[..., 3] = 255
        image = Image.fromarray(pixels)
        draw = ImageDraw.Draw(image)
        sunx = width * (.76 if index else .23)
        suny = height * .28
        radius = min(width, height) * .09
        draw.ellipse((sunx-radius, suny-radius, sunx+radius, suny+radius), fill=(247, 221, 144, 255))
        for layer in range(3):
            points = [(0, height), (0, height*(.55+layer*.11))]
            for j in range(13):
                points.append((j*width/12, height*(.48+layer*.14 + .11*math.sin(j*1.9+index+layer))))
            points.append((width, height))
            color = ((48+layer*14, 62+layer*17, 112+layer*20, 255) if not index else
                     (35+layer*12, 116+layer*14, 101+layer*17, 255))
            draw.polygon(points, fill=color)
        # Fine linework distinguishes real tile translation from threshold reveal.
        for j in range(1, 12):
            draw.line((j*width/12, 0, j*width/12, height), fill=(217, 193, 166, 255), width=1)
        images.append(image)
    return tuple(images)


def production_transition_spec(identity: str, duration_ms: int | None = None, settings: dict | None = None,
                               seed: int = 713, detail: str | None = "High"):
    """Resolve ``identity`` through the complete production resolver: the canonical transitions
    settings with ``settings`` laid over them, the transition selected and activated, its duration
    ``duration_ms`` (canonical when None) and the 3D Detail tier ``detail`` (canonical when None)."""
    import copy

    from core.settings.default_contract import require_canonical_default
    from rendering.quick.transitions.request_resolution import resolve_quick_transition_spec
    from rendering.transition_registry import get_transition_descriptor, get_transition_descriptor_for_runtime_identity

    descriptor = get_transition_descriptor(identity) or get_transition_descriptor_for_runtime_identity(identity)
    if descriptor is None or not descriptor.available:
        raise ValueError(f"unavailable transition {identity}")
    defaults = copy.deepcopy(require_canonical_default("transitions"))
    values = {**defaults, **(settings or {}), "type": descriptor.setting_name, "random_always": False,
              "activation": {**defaults["activation"], descriptor.setting_name: True},
              "pool": {**defaults["pool"], descriptor.setting_name: True}}
    if duration_ms is not None:
        values["durations"] = {**defaults["durations"], descriptor.setting_name: int(duration_ms)}

    class _CaptureSettings:
        def get(self, key, default=None):
            if key == "transitions":
                return values
            if key == "scene3d.detail" and detail is not None:
                return detail
            try:
                return require_canonical_default(key)
            except KeyError:
                return default

        def get_bool(self, _key):            # read only for Random selection, which is off here
            return True

    spec = resolve_quick_transition_spec(_CaptureSettings(), random_source=random.Random(seed))
    if spec is None or spec.transition_id != descriptor.stable_id:
        raise ValueError(f"production resolver did not admit selected transition {identity}")
    return spec


def main(argv=None):
    from PIL import Image, ImageDraw
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effect", default="glass_shatter")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--direction")
    parser.add_argument("--seed", type=int, default=713)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--animate", action="store_true", help="also export a two-second, 60-frame WebP motion preview")
    parser.add_argument("--output-dir", type=artifact_paths.evidence_arg,
                        help="default .artifacts/evidence/transitions/<effect>/contact_sheet/<YYYYMMDD>_<time>")
    args = parser.parse_args(argv)
    if args.output_dir is None:
        args.output_dir = artifact_paths.evidence_dir(f"transitions/{artifact_paths.slug(args.effect)}",
                                                      "contact_sheet", artifact_paths.run_label("sheet"))
    evidence_media.redirect_output(args, "output_dir", "transition_contact_sheet")
    from tools.native_transition_capture import NativeTransitionCapture

    capture = NativeTransitionCapture(args.width, args.height,
                                Image.open(args.source) if args.source else None,
                                Image.open(args.destination) if args.destination else None)
    report = {"effect": args.effect, "route": "native core", "size": [args.width, args.height]}
    try:
        run = capture.run(args.effect, seed=args.seed, direction=args.direction)
        report["parameters"] = run.request.parameter_dict()
        report["direction"] = run.request.direction
        frames, timings = [], []
        times = (0., .12, .28, .45, .65, .82, .95, 1.)
        for progress in times:
            image, ms = capture.render(run, progress)
            frames.append(image)
            timings.append(ms)
        assert frames[0].tobytes() == capture.images[0].tobytes(), "source endpoint mismatch"
        assert frames[-1].tobytes() == capture.images[1].tobytes(), "destination endpoint mismatch"
        assert capture.render(run, .45)[0].tobytes() == frames[3].tobytes(), "nondeterministic render"
        assert frames[3].tobytes() not in (frames[0].tobytes(), frames[-1].tobytes()), "static midpoint"
        report["frame_ms_max"] = max(timings)
        report["endpoints_exact"] = report["repeatable"] = True
        args.output_dir.mkdir(parents=True, exist_ok=True)
        thumb_w = min(args.width, 480)
        thumb_h = round(args.height*thumb_w/args.width)
        sheet = Image.new("RGB", (thumb_w*4, (thumb_h+26)*2), (18, 22, 31))
        draw = ImageDraw.Draw(sheet)
        for index, (progress, frame) in enumerate(zip(times, frames)):
            x, y = index % 4 * thumb_w, index // 4 * (thumb_h+26)
            sheet.paste(frame.resize((thumb_w, thumb_h)), (x, y+26))
            draw.text((x+8, y+7), f"{args.effect}  {progress:.0%}", fill=(235, 240, 248))
            frame.save(args.output_dir/f"{args.effect}_{progress:.2f}.png")
        sheet.save(args.output_dir/f"{args.effect}_contact.png")
        if args.animate:
            motion = [capture.render(run, index/59)[0] for index in range(60)]
            motion[0].save(args.output_dir/f"{args.effect}_motion.webp", save_all=True,
                           append_images=motion[1:], duration=34, loop=0, quality=85, method=4)
    finally:
        capture.close()
    report["retired"] = True
    (args.output_dir/f"{args.effect}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(evidence_media.finish(main()))
