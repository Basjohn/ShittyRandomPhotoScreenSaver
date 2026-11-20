"""Every tool file has its row in ``Docs/Reference/Tooling.md`` (the page's own rule: a new file under ``tools/``,
``scripts/`` or ``native/core/python/`` needs a row in the same commit)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLING = ROOT / "Docs" / "Reference" / "Tooling.md"
FOLDERS = ("tools", "tools/visualizer_replay", "scripts", "native/core/python")
_TOKEN = re.compile(r"`([^`]+\.py)`")


def listed_files(text: str) -> set[str]:
    """Files named in the first cell of a table row; a bare name belongs to the folder of the path before it in
    the same cell (rows write ``tools/x/a.py``, ``b.py``)."""
    listed: set[str] = set()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cell = line.split("|")[1]
        folder = ""
        for token in _TOKEN.findall(cell):
            if "/" in token:
                folder = token.rsplit("/", 1)[0]
                listed.add(token)
            else:
                listed.add(f"{folder}/{token}" if folder else token)
    return listed


def tool_files(root: Path) -> list[str]:
    found = []
    for folder in FOLDERS:
        for path in sorted((root / folder).glob("*.py")):
            if not path.name.startswith("_"):
                found.append(path.relative_to(root).as_posix())
    return found


def missing_rows(root: Path, text: str) -> list[str]:
    listed = listed_files(text)
    return [name for name in tool_files(root) if name not in listed]


def test_every_tool_file_has_a_tooling_row():
    missing = missing_rows(ROOT, TOOLING.read_text(encoding="utf-8"))
    assert not missing, "add a row to Docs/Reference/Tooling.md for: " + ", ".join(missing)


def test_an_unlisted_file_is_reported(tmp_path):
    """Negative control: a new file in a covered folder that no row names is found missing."""
    for folder in FOLDERS:
        (tmp_path / folder).mkdir(parents=True)
    (tmp_path / "tools" / "listed_tool.py").write_text("")
    (tmp_path / "tools" / "unlisted_tool.py").write_text("")
    (tmp_path / "tools" / "_private.py").write_text("")
    text = "| `tools/listed_tool.py` | does a thing |\n"
    assert missing_rows(tmp_path, text) == ["tools/unlisted_tool.py"]
