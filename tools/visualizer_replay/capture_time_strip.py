"""Side-by-side time strip from capture MP4s: rows are source times, columns are runs (motion review aid).

Example:
  .venv\\Scripts\\python.exe tools/visualizer_replay/capture_time_strip.py --ffmpeg <ffmpeg.exe> --output strip.png
      --start 5 --step .125 --count 8 <run-dir-with-motion_with_audio.mp4> [<run-dir> ...]
"""
from __future__ import annotations
import argparse, io, subprocess
from pathlib import Path
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
if str(_Path(__file__).resolve().parents[2]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402


def main():
    from PIL import Image, ImageDraw
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', type=Path, required=True)
    parser.add_argument('--output', type=artifact_paths.evidence_arg, required=True)
    parser.add_argument('--start', type=float, default=0.)
    parser.add_argument('--step', type=float, default=.25)
    parser.add_argument('--count', type=int, default=8)
    parser.add_argument('--width', type=int, default=640)
    parser.add_argument('runs', type=Path, nargs='+')
    args = parser.parse_args()
    evidence_media.redirect_output(args, "output", "capture_time_strip")
    if args.output.exists():
        parser.error('Refusing to overwrite an existing strip')
    rows = []
    for index in range(args.count):
        t = args.start+index*args.step
        tiles = []
        for run in args.runs:
            data = subprocess.check_output([str(args.ffmpeg.resolve()), '-loglevel', 'error', '-ss', f'{t:.3f}', '-i',
                                            str((run/'motion_with_audio.mp4').resolve()), '-frames:v', '1',
                                            '-f', 'image2pipe', '-vcodec', 'png', '-'])
            image = Image.open(io.BytesIO(data)).convert('RGB')
            image = image.resize((args.width, round(image.height*args.width/image.width)))
            ImageDraw.Draw(image).text((6, 6), f'{run.name}  t+{t:.3f}s', fill='white')
            tiles.append(image)
        rows.append(tiles)
    height = rows[0][0].height
    sheet = Image.new('RGB', (args.width*len(args.runs), height*args.count))
    for row, tiles in enumerate(rows):
        for column, image in enumerate(tiles):
            sheet.paste(image, (column*args.width, row*height))
    sheet.save(args.output)
    print(args.output)


if __name__ == '__main__':
    main()
    evidence_media.finish(0)
