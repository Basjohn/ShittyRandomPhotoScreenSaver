"""Every widget inside a Foundry window is Qt's to delete (R-204's ownership test, for each Foundry).

A row layout filled with widgets before it has a parent left those widgets owned by Python while Qt also
owned them as children of the window; PySide's exit-time cleanup then deleted them a second time (an access
violation or abort at process exit, after every test passed).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests._qt_ownership import python_owned_descendants

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ("init",),
        ("config", "user.email", "foundry-ownership@example.invalid"),
        ("config", "user.name", "Foundry Ownership Tests"),
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, capture_output=True)
    return repo


def _retire(window, qt_app) -> None:
    window.close()
    window.deleteLater()
    qt_app.processEvents()


def test_theme_foundry_children_are_owned_by_qt_not_python(qt_app) -> None:
    from tools.theme_foundry import ThemeFoundryWindow

    window = ThemeFoundryWindow(REPO_ROOT)
    try:
        assert python_owned_descendants(window) == []
    finally:
        _retire(window, qt_app)


def test_widget_theme_foundry_children_are_owned_by_qt_not_python(qt_app) -> None:
    from tools.widget_theme_foundry import WidgetThemeFoundryWindow

    window = WidgetThemeFoundryWindow(REPO_ROOT, None)
    try:
        assert python_owned_descendants(window) == []
    finally:
        _retire(window, qt_app)


def test_godzip_foundry_children_are_owned_by_qt_not_python(qt_app, tmp_path) -> None:
    from tools.godzip_foundry import GodzipFoundryWindow

    window = GodzipFoundryWindow(_git_repo(tmp_path))
    try:
        assert python_owned_descendants(window) == []
    finally:
        # The window starts its repository scan on a worker thread; it finishes before the window goes.
        thread = window._task_thread
        if thread is not None:
            thread.join(timeout=60)
            assert not thread.is_alive()
        _retire(window, qt_app)
