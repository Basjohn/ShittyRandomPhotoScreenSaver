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
# Every shipped QML tree: the saver scene and the Settings-side Studio (6 Nov: the Studio's QtQuick.Controls.Basic was
# never checked, and frozen builds pruned it).
QML_ROOTS = (QML_ROOT, REPO_ROOT / "ui" / "studio" / "qml")
_IMPORT = re.compile(r"\s*import\s+([A-Za-z0-9_.]+)(?:\s|$)")


def allowed_imports(script: Path = LAYOUT_SCRIPT) -> frozenset[str]:
    block = re.search(r"\$allowedImports = @\((.*?)\)", script.read_text(encoding="utf-8"), re.S)
    if block is None:
        raise ValueError(f"QML import allowlist not found in {script}")
    return frozenset(re.findall(r"'([^']+)'", block.group(1)))


def qt_imports(roots=QML_ROOTS) -> dict[str, list[str]]:
    """Every authored Qt QML namespace in ``roots`` -> the ``path:line`` places importing it."""
    found: dict[str, list[str]] = {}
    for root in (roots,) if isinstance(roots, Path) else roots:
        for qml in sorted(Path(root).rglob("*.qml")):
            for number, line in enumerate(qml.read_text(encoding="utf-8").splitlines(), 1):
                match = _IMPORT.match(line)
                if match and match.group(1).startswith("Qt"):
                    found.setdefault(match.group(1), []).append(f"{qml}:{number}")
    return found


def violations(qml_root: Path | tuple[Path, ...] = QML_ROOTS, script: Path = LAYOUT_SCRIPT) -> list[str]:
    """``path:line: namespace`` for every authored Qt QML import outside the build's allowlist."""
    allowed = allowed_imports(script)
    found = []
    roots = (qml_root,) if isinstance(qml_root, Path) else qml_root
    for qml in sorted(q for root in roots for q in Path(root).rglob("*.qml")):
        for number, line in enumerate(qml.read_text(encoding="utf-8").splitlines(), 1):
            match = _IMPORT.match(line)
            if match and match.group(1).startswith("Qt") and match.group(1) not in allowed:
                where = qml.relative_to(REPO_ROOT) if qml.is_relative_to(REPO_ROOT) else qml
                found.append(f"{where}:{number}: {match.group(1)}")
    return found
