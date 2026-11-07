"""The seam of the shipped Studio clips, measured (audio side of ``Docs/Reference/Visualizer_Studio.md`` "Studio clips").

    .venv/Scripts/python tools/studio_clip_loop_report.py [--out DIR] [--before-rev REV]

For each shipped clip it plays the loop back to back and measures the wrap four ways (``tools/studio_clip_loop.py``
``seam_report``): the sample step across it, the RMS across it, the spectral flux after it and the beat grid across
it. Two controls sit beside it: the same loop cut hard at the start of its crossfade (what a restart does to this very
music) and, with ``--before-rev``, the clip the repository shipped at that revision restarted at its first frame (what
the Studio did before). ``--out`` writes ``seam_report.json``.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import artifact_paths  # noqa: E402

CLIPS = ROOT / "assets" / "production" / "studio_clips"
PASSES = 4


def _beat(stream: np.ndarray, period: int) -> tuple[float, float]:
    from tools.studio_clip_loop import beat_period, onset_envelope, refine_beat, tiled
    flux, _rms, _bands = onset_envelope(tiled(stream, period, PASSES))
    tempo, strength = beat_period(flux)
    return refine_beat(flux, tempo)[0], strength


def clip_stream(frames, period: int | None = None):
    """(stream, period in samples) of a clip's frames: the periodic stream from the first frame's end on."""
    from tools.studio_clip_loop import loop_stream
    from widgets.spotify_visualizer.compact_clip import _history_stream
    stream, slices = _history_stream(frames)
    if period is None:
        period = int(slices[-1][1] - slices[0][1]) + int(round(float(np.mean(np.diff([e for _s, e in slices])))))
    return loop_stream(frames, period), period


def report_clip(path: Path) -> dict:
    from tools.studio_clip_loop import seam_report
    from widgets.spotify_visualizer.compact_clip import load_feature_clip, read_header
    header = read_header(path)
    loop = (header.get("provenance") or {}).get("loop") or {}
    frames = load_feature_clip(path).frames
    stream, period = clip_stream(frames, loop.get("period_samples"))
    beat = _beat(stream, period)
    out = {"period_s": period / 48000.0, "beat_s": beat[0], "beat_strength": beat[1],
           "seam": seam_report(stream, period, beat=beat, passes=PASSES)}
    if loop:
        cut = period - int(round(float(loop["crossfade_s"]) * 48000))
        out["hard_cut_control"] = seam_report(stream[:cut], cut, beat=beat, passes=PASSES)
    return out


def report_before(rev: str, name: str) -> dict | None:
    """The clip ``name`` as shipped at ``rev``, restarted at its first frame (the Studio's old wrap)."""
    from tools.studio_clip_loop import seam_report
    from widgets.spotify_visualizer.compact_clip import decode
    git = subprocess.run(["git", "show", f"{rev}:assets/production/studio_clips/{name}.srclip"], cwd=ROOT,
                         capture_output=True)
    if git.returncode:
        return None
    frames = decode(git.stdout).frames
    stream, period = clip_stream(frames)
    beat = _beat(stream, period)
    return {"period_s": period / 48000.0, "seam": seam_report(stream, period, beat=beat, passes=PASSES)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=artifact_paths.evidence_arg)
    parser.add_argument("--before-rev")
    args = parser.parse_args(argv)
    manifest = json.loads((CLIPS / "clips.json").read_text(encoding="utf-8"))["clips"]
    result = {}
    for entry in manifest:
        item = report_clip(CLIPS / entry["file"])
        if args.before_rev:
            item["before"] = report_before(args.before_rev, entry["id"])
        result[entry["id"]] = item
        seam = item["seam"]
        print(f"{entry['id']}: step {seam['step']['seam']:.4f} (p{seam['step']['percentile']:.2f})  "
              f"rms {seam['rms']['seam_db']:.2f} dB (p95 {seam['rms']['p95_db']:.2f})  "
              f"flux p{seam['flux']['percentile']:.0f}  beat jump {seam.get('beat', {}).get('jump_ms', float('nan')):.0f} ms "
              f"(interior p95 {seam.get('beat', {}).get('interior_p95_ms', float('nan')):.0f})")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "seam_report.json").write_text(json.dumps(result, indent=1, default=float), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
