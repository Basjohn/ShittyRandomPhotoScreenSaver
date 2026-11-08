"""Native core P2: the engine worker's import weight (Docs/Future_Work/Native_Core_P2_Engine_Design.md, Risks).

The worker runs the logical tick and every mode's frame runtime, plus the packet ABI and frame codec. It may import
QtCore at most: never QtGui, QtQml, QtQuick or QtWidgets, which would load the GUI stack (and its DLLs, fonts and
plugins) into a process that draws nothing. One fresh interpreter imports the whole tick side and reports what came
with it."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_PROBE = r"""
import importlib, json, sys
names = ["widgets.spotify_visualizer.logical_runtime", "widgets.spotify_visualizer.tick_pipeline",
         "widgets.spotify_visualizer.render_state", "core.visualizer_engine.frame_codec",
         "core.visualizer_engine.packet_abi", "core.visualizer_engine.packet_mailbox",
         "core.visualizer_engine.engine_worker", "widgets.spotify_visualizer.feature_replay",
         "widgets.spotify_visualizer.runtime_controller"]
runtimes = sorted(p.stem for p in __import__("pathlib").Path("widgets/spotify_visualizer").glob("*_frame_runtime.py"))
names += ["widgets.spotify_visualizer." + stem for stem in runtimes]
for name in names:
    importlib.import_module(name)
print(json.dumps({"modules": names, "qt": sorted(m for m in sys.modules if m.startswith("PySide6.Qt"))}))
"""


def test_the_tick_side_imports_qtcore_at_most():
    out = subprocess.run([sys.executable, "-c", _PROBE], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    report = json.loads(out.stdout.strip().splitlines()[-1])
    assert sum(name.endswith("_frame_runtime") for name in report["modules"]) >= 8   # every mode runtime was imported
    assert set(report["qt"]) <= {"PySide6.QtCore"}, report["qt"]
