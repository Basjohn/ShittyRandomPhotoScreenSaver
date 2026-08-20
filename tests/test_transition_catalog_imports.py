"""Import-isolation gates for the lightweight transition catalog."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def _run_import_probe(source: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def test_transition_catalog_imports_no_shader_implementation_modules():
    report = _run_import_probe(
        """
import json
import sys
from rendering.transition_registry import iter_transition_descriptors

descriptors = iter_transition_descriptors()
loaded = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({"count": len(descriptors), "loaded": loaded}))
"""
    )

    assert report["count"] >= 12
    assert report["loaded"] == []


def test_gl_program_public_exports_load_only_the_requested_helper():
    report = _run_import_probe(
        """
import json
import sys
from rendering.gl_programs import CrossfadeProgram

loaded = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({
    "helper": CrossfadeProgram.__name__,
    "loaded": loaded,
}))
"""
    )

    assert report == {
        "helper": "CrossfadeProgram",
        "loaded": [
            "rendering.gl_programs.base_program",
            "rendering.gl_programs.crossfade_program",
        ],
    }
