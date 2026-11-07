"""What clip length costs: size and a re-analysis (an engine-owned edit re-runs a Studio's worker over the whole clip).

    .venv/Scripts/python tools/studio_clip_length_cost.py [--recordings DIR] [--seconds 30] [--out FILE]

Compares each shipped loop clip (``assets/production/studio_clips``, primed as its worker runs it) with a plain window
of ``--seconds`` cut from the same recording (what option (b) of ``Current_Plan.md`` "Studio clips" would ship): its
compact size and the time of the Bubble, Sphere, Extruded Bubble, Waveform and Spectrum workers, in this process.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import artifact_paths  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--recordings", type=Path, default=ROOT / "logs" / "visualizer_recordings")
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--out", type=artifact_paths.evidence_arg)
    args = parser.parse_args(argv)
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication([])          # noqa: F841  (the workers need one)
    from core.settings.default_contract import require_canonical_default
    from tools.build_studio_clips import window_frames
    from ui.studio import (bubble_recorded_inputs, extruded_bubble_recorded_inputs, sphere_recorded_inputs,
                           spectrum_recorded_inputs, waveform_recorded_inputs)
    from widgets.spotify_visualizer.compact_clip import encode
    values = dict(require_canonical_default("widgets.spotify_visualizer"))
    workers = {"bubble": bubble_recorded_inputs, "sphere": sphere_recorded_inputs,
               "extruded_bubble": extruded_bubble_recorded_inputs, "waveform": waveform_recorded_inputs,
               "spectrum": spectrum_recorded_inputs}
    manifest = json.loads((ROOT / "assets" / "production" / "studio_clips" / "clips.json").read_text(encoding="utf-8"))
    result = {}
    with tempfile.TemporaryDirectory() as folder:
        for entry in manifest["clips"]:
            first = float(entry["loop"]["first_source_s"])
            frames = window_frames(args.recordings / entry["source"], first, first + args.seconds)
            long_path = Path(folder) / (entry["id"] + "_long.srclip")
            data = encode(frames, name=entry["id"] + "_long")
            long_path.write_bytes(data)
            row = {"loop_bytes": entry["bytes"], "loop_s": entry["seconds"], "long_bytes": len(data),
                   "long_s": round((frames[-1].timestamp_us - frames[0].timestamp_us) / 1e6, 2), "workers_s": {}}
            for name, module in workers.items():
                timings = []
                for path in (ROOT / "assets" / "production" / "studio_clips" / entry["file"], long_path):
                    start = time.perf_counter()
                    if name == "spectrum":
                        module.extract(str(path), values, seconds=None)
                    else:
                        module.extract(path, values, seconds=None)
                    timings.append(round(time.perf_counter() - start, 2))
                row["workers_s"][name] = {"loop": timings[0], "long": timings[1],
                                          "ratio": round(timings[1] / timings[0], 2)}
            result[entry["id"]] = row
            print(entry["id"], json.dumps(row))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
