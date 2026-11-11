"""A mode's preset files that cannot be read for a moment never fail the catalogue (1C.1, R-190).

The operator's first open of Spectrum after an install failed with Spectrum's presets "not existing" and the
second open worked. The catalogue was built once, when ``core.settings.visualizer_presets`` was first imported:
every file of a mode that could not be read at that moment (held open by the installer or a scanner, or being
replaced) made the build raise ``visualizer mode 'spectrum' has no authored presets`` (Spectrum is the first
mode), so that import failed; Python does not keep a failed import, so the next open imported again and worked.

These run the real import in a fresh interpreter with the curated files of one mode made unreadable (an
``OSError`` from ``Path.read_text``, as a sharing violation gives) until the test releases them. Nothing
here pins a preset's name, count or values: they are read from the catalogue the same process builds.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_CHILD = r"""
import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
mode, scope = sys.argv[2], sys.argv[3]
locked = {"on": True}
original = pathlib.Path.read_text
def read_text(self, *args, **kwargs):
    if locked["on"] and self.parent.name == mode and self.suffix == ".json" and "visualizer_modes" in self.parts:
        if scope == "all" or self.name == sorted(p.name for p in self.parent.glob("*.json"))[0]:
            raise PermissionError(32, "The process cannot access the file because it is being used by another process", str(self))
    return original(self, *args, **kwargs)
pathlib.Path.read_text = read_text
result = {}
try:
    import core.settings.visualizer_presets as vp
    result["import"] = "ok"
except Exception as exc:
    result["import"] = f"{type(exc).__name__}: {exc}"
    print(json.dumps(result)); raise SystemExit(0)
try:
    vp.get_presets(mode)
    result["while_locked"] = "ok"
except Exception as exc:
    result["while_locked"] = f"{type(exc).__name__}: {exc}"
result["names_while_locked"] = list(vp._PRESETS[mode]) and [p.name for p in vp._PRESETS[mode]]
locked["on"] = False
if scope == "one":
    vp.reload_presets_if_changed(mode)
result["names_after"] = [p.name for p in vp.get_presets(mode)]
original_tree = vp._load_mode_presets_from_disk(mode)
result["on_disk"] = len(original_tree)
print(json.dumps(result))
"""


def _run(mode: str, scope: str) -> dict:
    completed = subprocess.run([sys.executable, "-c", _CHILD, str(ROOT), mode, scope], cwd=str(ROOT),
                               capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr[-2000:]
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_every_file_of_the_first_mode_unreadable_at_import_never_fails_the_import():
    from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
    mode = VISUALIZER_MODE_IDS[0]          # the mode the old build named first ("spectrum")
    result = _run(mode, "all")
    assert result["import"] == "ok", result
    # While the files stay unreadable the mode says so when asked (nothing is cached as a failure)...
    assert "NoAuthoredPresets" in result["while_locked"], result
    # ...and once they can be read the very next request has the whole catalogue.
    assert len(result["names_after"]) == result["on_disk"] + 1          # curated presets + Custom


def test_one_unreadable_file_leaves_the_rest_and_is_read_again_at_the_next_open():
    from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
    mode = VISUALIZER_MODE_IDS[0]
    result = _run(mode, "one")
    assert result["import"] == "ok" and result["while_locked"] == "ok", result
    assert len(result["names_while_locked"]) == result["on_disk"]       # one preset missing, Custom still there
    assert len(result["names_after"]) == result["on_disk"] + 1          # the next open reads it again
