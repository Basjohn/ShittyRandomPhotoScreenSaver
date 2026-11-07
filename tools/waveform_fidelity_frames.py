"""Waveform before/after fidelity frames: capture consecutive production frames, then compare two captures.

    .venv/Scripts/python tools/waveform_fidelity_frames.py capture --clip <clip> --preset 2 --out <dir>
    .venv/Scripts/python tools/waveform_fidelity_frames.py compare <before dir> <after dir> --out <dir>

``capture`` renders consecutive instants (default 12 at 45 fps, so frame-to-frame shimmer is visible) of a curated
preset through the production render host at the operator's TV card size with the edge-resize aperture, and saves
lossless PNGs plus a receipt (source revision, preset, instants). Replay is deterministic, so two captures of the same
instants from two source revisions differ only by the renderer.

``compare`` reports per frame the largest channel difference and how many pixels differ by more than 1/255, writes a
difference heat map, a side-by-side (before | after) of the whole frame and 1:1 and 3x crops of fixed regions (ribbon
body, its rims and strands, the reflection on the floor, the mist above the ribbons), and the frame-to-frame change
of each capture (new shimmer shows up as after's temporal change exceeding before's).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402

# Crop regions as fractions of the card (x0, y0, x1, y1): ribbons with rims and strands, the floor reflection under
# them, the mist above them, and the left end where the history leaves the view.
CROPS = {"ribbons": (.42, .30, .58, .62), "reflection": (.40, .62, .60, .92), "mist": (.30, .02, .50, .30),
         "history end": (.02, .30, .18, .70)}


def capture(args) -> int:
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    from PIL import Image
    from OpenGL import GL as gl
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.labs.render_target import OffscreenRenderTarget
    from tools.waveform_gpu_stage_cost import snapshots_for
    width, height = (int(v) for v in args.size.split("x"))
    snapshots, name = snapshots_for(args.clip, args.preset, (width, height), args.start, args.frames, args.fps, {})
    args.out.mkdir(parents=True, exist_ok=False)
    target = OffscreenRenderTarget(width, height, label="waveform fidelity")
    host = QuickVisualizerRenderHost()
    matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
    try:
        with target.current():
            for index, snapshot in enumerate([*snapshots[:4], *snapshots]):   # four warm frames first
                target.bind(clear=(0., 0., 0., 0.))
                host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                            logical_size=(float(width), float(height)), matrix_values=matrix)
                gl.glFinish()
                if index >= 4:
                    Image.fromarray(target.read_rgba()).save(args.out / f"frame_{index - 4:03d}.png", compress_level=1)
            host.release_resources()
    finally:
        target.close()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True)
    (args.out / "capture.json").write_text(json.dumps(dict(
        preset=args.preset, name=name, clip=str(args.clip), start=args.start, fps=args.fps, frames=args.frames,
        size=(width, height), revision=revision, dirty_files=dirty.splitlines()), indent=2) + "\n", encoding="utf-8")
    print("captured", len(snapshots), "frames of", name, "to", args.out)
    return 0


def _crop(image, box):
    width, height = image.size
    return image.crop((int(box[0] * width), int(box[1] * height), int(box[2] * width), int(box[3] * height)))


def compare(args) -> int:
    import numpy as np
    from PIL import Image, ImageDraw
    before_files = sorted(args.before.glob("frame_*.png"))
    after_files = sorted(args.after.glob("frame_*.png"))
    if not before_files or len(before_files) != len(after_files):
        raise SystemExit("captures must hold the same frames")
    args.out.mkdir(parents=True, exist_ok=True)
    rows, previous = [], None
    for index, (b_path, a_path) in enumerate(zip(before_files, after_files)):
        before = np.asarray(Image.open(b_path).convert("RGBA"), np.int16)
        after = np.asarray(Image.open(a_path).convert("RGBA"), np.int16)
        difference = np.abs(after - before)[..., :3].max(axis=-1)
        row = dict(frame=b_path.name, max=int(difference.max()), over_1=int((difference > 1).sum()),
                   over_0=int((difference > 0).sum()), pixels=int(difference.size),
                   mean=float(difference.mean()))
        if previous is not None:
            row["temporal_before"] = float(np.abs(before - previous[0])[..., :3].mean())
            row["temporal_after"] = float(np.abs(after - previous[1])[..., :3].mean())
        previous = (before, after)
        rows.append(row)
        if index in (0, len(before_files) // 2):
            heat = np.clip(difference * 16, 0, 255).astype(np.uint8)
            Image.fromarray(heat).save(args.out / f"diff_x16_{b_path.stem}.png")
            b_image, a_image = Image.open(b_path).convert("RGB"), Image.open(a_path).convert("RGB")
            side = Image.new("RGB", (b_image.width * 2 + 8, b_image.height), (255, 0, 255))
            side.paste(b_image, (0, 0)); side.paste(a_image, (b_image.width + 8, 0))
            ImageDraw.Draw(side).text((10, 10), "BEFORE", fill="white")
            ImageDraw.Draw(side).text((b_image.width + 18, 10), "AFTER", fill="white")
            side.save(args.out / f"side_full_{b_path.stem}.png", compress_level=1)
            for label, box in CROPS.items():
                for scale in (1, 3):
                    first, second = _crop(b_image, box), _crop(a_image, box)
                    if scale > 1:
                        first = first.resize((first.width * scale, first.height * scale), Image.NEAREST)
                        second = second.resize((second.width * scale, second.height * scale), Image.NEAREST)
                    pair = Image.new("RGB", (first.width * 2 + 6, first.height), (255, 0, 255))
                    pair.paste(first, (0, 0)); pair.paste(second, (first.width + 6, 0))
                    pair.save(args.out / f"side_{label.replace(' ', '_')}_{scale}x_{b_path.stem}.png", compress_level=1)
    summary = dict(before=str(args.before), after=str(args.after), frames=rows,
                   max=max(row["max"] for row in rows), over_1=max(row["over_1"] for row in rows),
                   identical=all(row["over_0"] == 0 for row in rows))
    (args.out / "compare.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"{args.after.name}: max channel difference {summary['max']}/255, worst frame pixels >1/255: "
          f"{summary['over_1']}, bit-identical: {summary['identical']}")
    for row in rows:
        print("  ", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--clip", type=Path, required=True)
    cap.add_argument("--preset", type=int, required=True)
    cap.add_argument("--out", type=artifact_paths.evidence_arg, required=True,
                     help="lossless frames for compare: .artifacts/scratch/<owner>/...; elsewhere published unchanged")
    cap.add_argument("--size", default="3875x1450")
    cap.add_argument("--start", type=float, default=20.)
    cap.add_argument("--frames", type=int, default=12)
    cap.add_argument("--fps", type=float, default=45.)
    cmp_ = sub.add_parser("compare")
    cmp_.add_argument("before", type=Path)
    cmp_.add_argument("after", type=Path)
    cmp_.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    args = parser.parse_args()
    evidence_media.redirect_output(args, "out", "waveform_fidelity_frames")
    return capture(args) if args.command == "capture" else compare(args)


if __name__ == "__main__":
    raise SystemExit(evidence_media.finish(main()))
