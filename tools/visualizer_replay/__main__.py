"""python -m tools.visualizer_replay [--candidate NEW.json] [--report NEW.html]."""
import argparse
import html
import json
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent

from .driver import MODES, load_clips, replay_clip
from .floors import calibrate, check_floors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, help="write new calibration candidate; refuses overwrite")
    parser.add_argument("--report", type=Path, help="write optional diagnostic HTML; refuses overwrite")
    args = parser.parse_args()
    for path in (args.candidate, args.report):
        if path is not None and path.exists():
            parser.error(f"refusing to overwrite {path}")
    app = QCoreApplication.instance() or QCoreApplication([])
    results = {}
    for name, clip in load_clips().items():
        for mode in (*MODES, "control") if name == "mode_visibility_switch" else MODES:
            case = f"{name}__{mode}"
            results[case] = replay_clip(clip, mode)
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    if args.candidate:
        candidate = calibrate(results)
        with args.candidate.open("x", encoding="utf-8") as out:
            json.dump(candidate, out, indent=2, allow_nan=False)
            out.write("\n")
    else:
        for case, result in results.items():
            check_floors(result, case)
    if args.report:
        rows = "".join(f"<tr><td>{html.escape(case)}</td><td>{r['metrics']['bar_peak']:.5f}</td>"
                       f"<td>{r['mode_metrics']['output_flux']:.5f}</td></tr>" for case, r in results.items())
        with args.report.open("x", encoding="utf-8") as out:
            out.write("<!doctype html><meta charset='utf-8'><title>Replay response</title>"
                      "<h1>Offline response measurements</h1><p>Logical/snapshot evidence; no pixel parity claim.</p>"
                      "<table><tr><th>Fixture/mode</th><th>Bar peak</th><th>Mode output flux</th></tr>" + rows + "</table>")
    print(f"{len(results)} replay cases {'measured' if args.candidate else 'passed'}")


if __name__ == "__main__":
    main()
