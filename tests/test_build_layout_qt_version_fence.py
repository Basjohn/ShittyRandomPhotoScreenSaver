"""Source-level runtime-version fence coverage for the shared build preflight."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
LAYOUT_SCRIPT = ROOT / "tools" / "build_layout.ps1"
QT_PINS = {
    "PySide6": "6.11.2",
    "PySide6_Addons": "6.11.2",
    "PySide6_Essentials": "6.11.2",
    "shiboken6": "6.11.2",
}


def _extract_runtime_probe() -> str:
    source = LAYOUT_SCRIPT.read_text(encoding="utf-8")
    function_start = source.index("function Assert-SRPSSPythonRuntimeDependencies")
    probe_start = source.index("$probe = @'", function_start) + len("$probe = @'\n")
    probe_end = source.index("\n'@", probe_start)
    return source[probe_start:probe_end]


def _requirements_text(*, pyside_requirement: str = "PySide6==6.11.2") -> str:
    return "\n".join(
        (
            pyside_requirement,
            "PySide6_Addons==6.11.2",
            "PySide6_Essentials==6.11.2",
            "shiboken6==6.11.2",
            "",
        )
    )


def _run_probe(
    tmp_path: Path,
    *,
    requirements_text: str,
    metadata_versions: dict[str, str] | None = None,
    loaded_versions: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    requirements_path = tmp_path / "requirements.txt"
    requirements_path.write_text(requirements_text, encoding="utf-8")
    probe_path = tmp_path / "runtime_probe.py"
    probe_path.write_text(_extract_runtime_probe(), encoding="utf-8")
    fixture_path = tmp_path / "versions.json"
    fixture_path.write_text(
        json.dumps(
            {
                "metadata": metadata_versions or QT_PINS,
                "loaded": loaded_versions
                or {
                    "PySide6": "6.11.2",
                    "Qt runtime": "6.11.2",
                    "shiboken6": "6.11.2",
                },
            }
        ),
        encoding="utf-8",
    )
    harness_path = tmp_path / "runtime_probe_harness.py"
    harness_path.write_text(
        """
import importlib
import json
from pathlib import Path
import sys
import types

probe_path, requirements_path, fixture_path = map(Path, sys.argv[1:])
fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

metadata = types.ModuleType("importlib.metadata")
metadata.version = lambda distribution: fixture["metadata"][distribution]
sys.modules["importlib.metadata"] = metadata
importlib.metadata = metadata


def install_module(name):
    module = sys.modules.get(name) or types.ModuleType(name)
    sys.modules[name] = module
    if "." in name:
        parent_name, attribute = name.rsplit(".", 1)
        parent = install_module(parent_name)
        setattr(parent, attribute, module)
    return module


pyside = install_module("PySide6")
pyside.__version__ = fixture["loaded"]["PySide6"]
qtcore = install_module("PySide6.QtCore")
qtcore.qVersion = lambda: fixture["loaded"]["Qt runtime"]
shiboken = install_module("shiboken6")
shiboken.__version__ = fixture["loaded"]["shiboken6"]
for name in (
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.QtMultimedia",
    "OpenGL",
    "numpy",
    "PIL",
    "winrt.windows.media.control",
    "winrt.windows.storage.streams",
    "pyaudiowpatch",
    "sounddevice",
    "pycaw",
    "comtypes",
    "psutil",
):
    install_module(name)

sys.argv = [str(probe_path), str(requirements_path)]
exec(compile(probe_path.read_text(encoding="utf-8"), str(probe_path), "exec"))
""".lstrip(),
        encoding="utf-8",
    )
    return subprocess.run(
        [
            sys.executable,
            str(harness_path),
            str(probe_path),
            str(requirements_path),
            str(fixture_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def test_runtime_probe_accepts_exact_metadata_and_loaded_qt_pins(
    tmp_path: Path,
) -> None:
    result = _run_probe(tmp_path, requirements_text=_requirements_text())

    assert result.returncode == 0, result.stderr
    assert "SRPSS_RUNTIME_DEPENDENCIES_OK" in result.stdout


def test_runtime_probe_rejects_metadata_version_drift(tmp_path: Path) -> None:
    metadata = dict(QT_PINS, PySide6="6.9.1")
    result = _run_probe(
        tmp_path,
        requirements_text=_requirements_text(),
        metadata_versions=metadata,
    )

    assert result.returncode != 0
    assert "Qt distribution version mismatch" in result.stderr
    assert "PySide6: installed 6.9.1, required 6.11.2" in result.stderr


def test_runtime_probe_rejects_loaded_qt_runtime_drift(tmp_path: Path) -> None:
    loaded = {"PySide6": "6.11.2", "Qt runtime": "6.9.1", "shiboken6": "6.11.2"}
    result = _run_probe(
        tmp_path,
        requirements_text=_requirements_text(),
        loaded_versions=loaded,
    )

    assert result.returncode != 0
    assert "Loaded Qt/Shiboken version mismatch" in result.stderr
    assert "Qt runtime: loaded 6.9.1, required 6.11.2" in result.stderr


def test_runtime_probe_requires_exact_pins_for_all_qt_distributions(
    tmp_path: Path,
) -> None:
    result = _run_probe(
        tmp_path,
        requirements_text=_requirements_text(pyside_requirement="PySide6>=6.11.2"),
    )

    assert result.returncode != 0
    assert "requirements must pin exact versions for: PySide6" in result.stderr


def test_layout_invokes_the_probe_with_the_requirements_cli_argument() -> None:
    source = LAYOUT_SCRIPT.read_text(encoding="utf-8")

    assert "& $PythonExe -c $probe $RequirementsPath" in source
