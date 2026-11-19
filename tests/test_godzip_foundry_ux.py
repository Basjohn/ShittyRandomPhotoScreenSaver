"""Godzip Foundry UX contracts (Foundry UX audit quick wins): button text, CLI help."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "godzip_foundry.py"


def _button_texts() -> list[tuple[int, str]]:
    """Every literal text given to a QPushButton or set on a ``*_button`` attribute."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        arg = node.args[0]
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id == "QPushButton":
            found.append((node.lineno, arg.value))
        elif isinstance(fn, ast.Attribute) and fn.attr == "setText":
            owner = fn.value
            name = owner.attr if isinstance(owner, ast.Attribute) else getattr(owner, "id", "")
            if name.endswith("_button") or name in {"ok", "copy", "close", "b", "button"}:
                found.append((node.lineno, arg.value))
    return found


def test_button_ampersands_are_escaped_so_no_accidental_mnemonic() -> None:
    texts = _button_texts()
    assert texts
    bad = [(line, text) for line, text in texts if re.search(r"(?<!&)&(?!&)", text)]
    assert not bad, f"single '&' is a Qt mnemonic marker: {bad}"
    assert any("&&" in text for _line, text in texts)


class _Label:
    def __init__(self) -> None:
        self.text = "Ready"

    def setText(self, text: str) -> None:  # noqa: N802
        self.text = text


class _Tabs:
    def __init__(self) -> None:
        self.current = "create"

    def currentWidget(self) -> str:  # noqa: N802
        return self.current


def _status_host(task_active: bool = False):
    from types import SimpleNamespace

    return SimpleNamespace(status_label=_Label(), tabs=_Tabs(), _status_tab=None, _task_active=task_active)


def _window_class():
    sys.path.insert(0, str(ROOT))
    from tools import godzip_foundry

    return godzip_foundry.GodzipFoundryWindow


def test_tab_bound_status_clears_when_the_tab_changes() -> None:
    window = _window_class()
    host = _status_host()
    window.set_status(host, "PULL inspection failed: boom")
    assert host.status_label.text == "PULL inspection failed: boom"
    window._clear_tab_status(host, "create")  # same tab: kept
    assert host.status_label.text == "PULL inspection failed: boom"
    host.tabs.current = "run"
    window._clear_tab_status(host, "run")
    assert host.status_label.text == "Ready"


def test_status_set_on_the_tab_you_moved_to_is_not_cleared_and_untied_status_survives() -> None:
    window = _window_class()
    host = _status_host()
    window.set_status(host, "Git header refresh failed", tab_bound=False)
    host.tabs.current = "push"
    window._clear_tab_status(host, "push")
    assert host.status_label.text == "Git header refresh failed"
    window.set_status(host, "Fetched")
    window._clear_tab_status(host, "push")
    assert host.status_label.text == "Fetched"


def test_a_running_task_keeps_its_progress_line_across_tab_changes() -> None:
    window = _window_class()
    host = _status_host(task_active=True)
    window.set_status(host, "Hashing files…")
    host.tabs.current = "diff"
    window._clear_tab_status(host, "diff")
    assert host.status_label.text == "Hashing files…"


def test_help_has_real_strings_and_needs_no_qt_resources(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-X", "importtime", str(SOURCE), "--help"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=60,
        env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "--repo" in out and "--open" in out
    # Every option carries a description line beyond its bare name.
    options = out.split("options:", 1)[-1].split("\n\n")
    flagged = [chunk for chunk in options if "--repo" in chunk or "--open" in chunk]
    assert flagged
    body = " ".join(flagged)
    # Each of the two options has a sentence of help, not just its metavar.
    assert len(re.findall(r"[A-Za-z]{3,}", body)) > 14
    assert "Qt resource" not in result.stderr
    # The Qt stack is never imported to print help (importtime lists every import on stderr).
    assert "PySide6" not in result.stderr and "ui.resources" not in result.stderr
