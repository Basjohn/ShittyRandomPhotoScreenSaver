"""The frozen build's QML import contract, readable from Python.

``tools/build_layout.ps1`` owns the allowlist of Qt QML namespaces the frozen products package (``$allowedImports``)
and refuses any authored QML import outside it at build time. This module parses that same allowlist, so tests can
fail on a new import long before a release build does (twice an unreviewed import reached the build: QtQuick.Window on
26 October, QtQml.Models on 1 November).
"""
from __future__ import annotations

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_SCRIPT = REPO_ROOT / "tools" / "build_layout.ps1"
QML_ROOT = REPO_ROOT / "rendering" / "quick" / "qml"
_IMPORT = re.compile(r"\s*import\s+([A-Za-z0-9_.]+)(?:\s|$)")


def allowed_imports(script: Path = LAYOUT_SCRIPT) -> frozenset[str]:
    block = re.search(r"\$allowedImports = @\((.*?)\)", script.read_text(encoding="utf-8"), re.S)
    if block is None:
        raise ValueError(f"QML import allowlist not found in {script}")
    return frozenset(re.findall(r"'([^']+)'", block.group(1)))


def violations(qml_root: Path = QML_ROOT, script: Path = LAYOUT_SCRIPT) -> list[str]:
    """``path:line: namespace`` for every authored Qt QML import outside the build's allowlist."""
    allowed = allowed_imports(script)
    found = []
    for qml in sorted(qml_root.rglob("*.qml")):
        for number, line in enumerate(qml.read_text(encoding="utf-8").splitlines(), 1):
            match = _IMPORT.match(line)
            if match and match.group(1).startswith("Qt") and match.group(1) not in allowed:
                where = qml.relative_to(REPO_ROOT) if qml.is_relative_to(REPO_ROOT) else qml
                found.append(f"{where}:{number}: {match.group(1)}")
    return found
