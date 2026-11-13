"""Foundry windows: the native backdrop is applied when the window is shown, never queued at construction.

A ``QTimer.singleShot(0, lambda: ...)`` queued in ``__init__`` closed over the window and reached it after
construction whether or not it was ever shown (or already closed); the native backdrop needs the window's native
handle, which exists once it is shown. The Defaults Foundry moved it to ``showEvent`` first.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests._invisible_windows import keep_off_screen  # real but never on screen
from tests.test_foundry_widget_ownership import _git_repo

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _join_worker(window) -> None:
    thread = getattr(window, "_task_thread", None)
    if thread is not None:
        thread.join(timeout=60)
        assert not thread.is_alive()


def _theme_foundry(monkeypatch, calls, _tmp_path):
    from tools import theme_foundry

    monkeypatch.setattr(theme_foundry, "apply_native_backdrop", lambda window, _r: calls.append(window) or True)
    return theme_foundry.ThemeFoundryWindow(REPO_ROOT)


def _widget_theme_foundry(monkeypatch, calls, _tmp_path):
    from tools import widget_theme_foundry

    monkeypatch.setattr(widget_theme_foundry, "apply_native_backdrop",
                        lambda window, _r: calls.append(window) or True)
    return widget_theme_foundry.WidgetThemeFoundryWindow(REPO_ROOT, None)


def _godzip_foundry(monkeypatch, calls, tmp_path):
    from tools import godzip_foundry

    monkeypatch.setattr(godzip_foundry.GodzipFoundryWindow, "_apply_native_backdrop_theme",
                        lambda window: calls.append(window) or True)
    return godzip_foundry.GodzipFoundryWindow(_git_repo(tmp_path))


@pytest.mark.parametrize("build", [_theme_foundry, _widget_theme_foundry, _godzip_foundry],
                         ids=["theme", "widget_theme", "godzip"])
def test_foundry_applies_its_native_backdrop_when_shown_not_when_built(qt_app, monkeypatch, tmp_path, build):
    calls: list[object] = []
    window = build(monkeypatch, calls, tmp_path)
    try:
        _join_worker(window)
        qt_app.processEvents()
        assert calls == [], "a backdrop was queued at construction"
        keep_off_screen(window)
        window.show()
        qt_app.processEvents()
        assert calls == [window]
    finally:
        _join_worker(window)
        qt_app.processEvents()
        window.close()
        window.deleteLater()
        qt_app.processEvents()
