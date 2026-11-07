"""The Settings window's forged rounded edge is painted over its content, on light and dark themes alike.

Defect (operator, 8 Nov 2026, "Pearl Blush [Three-Tone] [Glass]"): every light theme broke the outer rounded border.
``SettingsDialog.paintEvent`` painted the edge beneath its children, and the shell surfaces fill the whole window
(``window.dialog_glass`` on the container, the title bar on top). Dark themes author those nearly clear, so the edge
showed through; light themes author them nearly opaque and pale, which washed the border out to the shell colour
and left pale square corners. The edge now paints from ``ForgedWindowEdgeOverlay`` above every child.

Read back from the real dialog (never shown, ``StyledPopup.exec`` patched), rendered with ``QWidget.grab``. The
subjects are one light and one dark shipped theme picked by ``settings_theme_is_light`` (never by name), and every
expected colour is the theme's own ``chrome.outer_border`` / opaque ``window.titlebar.surface``, never a pinned value.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.qt

ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"


def _shipped_theme(light: bool) -> Path:
    from ui.settings_theme_io import load_settings_theme_file
    from ui.theme_semantics import settings_theme_is_light

    for path in sorted(THEMES.glob("*.srtheme")):
        theme = load_settings_theme_file(path)
        # A theme whose shell surface is nearly opaque is the case that hid the edge.
        if settings_theme_is_light(theme) == light and theme.backdrop.mode != "off":
            if not light or theme.color("window.dialog_glass").a >= 128 or theme.color("window.titlebar.surface").a >= 128:
                return path
    pytest.skip(f"the shipped catalogue has no {'light' if light else 'dark'} theme for this check")


@pytest.fixture
def manager(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from core.settings.settings_manager import SettingsManager
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    from ui.styled_popup import StyledPopup

    monkeypatch.setattr(StyledPopup, "exec", lambda popup: setattr(popup, "_result_value", None))
    before = get_active_settings_theme()
    manager = SettingsManager(application="forged_edge_over_content", storage_base_dir=tmp_path)
    manager.set("sources.folders", [str(tmp_path)])
    yield manager
    assert manager.flush(timeout=5.0)
    set_active_settings_theme(before)


def _grab(manager, path: Path):
    from core.animation import AnimationManager
    from ui.settings_dialog import SettingsDialog
    from ui.settings_theme_catalog import activate_persisted_settings_theme

    manager.set("ui.settings_theme_selection", f"file:{path.name}")
    resolution = activate_persisted_settings_theme(manager, THEMES).resolution
    assert not resolution.used_fallback
    dialog = SettingsDialog(manager, AnimationManager())
    try:
        dialog.resize(900, 640)
        QCoreApplication.processEvents()
        # The edge overlay is the topmost child, so nothing the dialog holds paints over it.
        tops = [child for child in dialog.children() if hasattr(child, "isWidgetType") and child.isWidgetType()]
        assert tops and tops[-1].objectName() == "forgedWindowEdge"
        image = dialog.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)
    finally:
        dialog.close()
        QCoreApplication.processEvents()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()
    return resolution.entry.theme, image


def _close(actual: QColor, expected, tolerance: int = 3) -> bool:
    return (actual.alpha() == 255 and abs(actual.red() - expected.r) <= tolerance
            and abs(actual.green() - expected.g) <= tolerance and abs(actual.blue() - expected.b) <= tolerance)


@pytest.mark.parametrize("light", [True, False], ids=["light theme", "dark theme"])
def test_the_outer_border_and_corner_caps_are_the_themes_own_on_top_of_the_content(manager, light) -> None:
    theme, image = _grab(manager, _shipped_theme(light))
    border = theme.color("chrome.outer_border")
    cap = theme.color("window.titlebar.surface")
    w, h = image.width(), image.height()
    # The 4 px border is centred half a pixel inside the window edge: the outermost rows and columns are border
    # on every side, under the title bar, the sidebar and the content alike.
    for x, y in ((w // 2, 0), (w // 2, 1), (0, h // 2), (1, h // 2), (w - 1, h // 2), (w // 2, h - 1),
                 (w // 4, 0), (0, h // 4)):
        assert _close(image.pixelColor(x, y), border), (x, y, image.pixelColor(x, y).name(), border)
    # Outside the rounded outline the window corner pixel is the opaque cap, not a washed blend.
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        assert _close(image.pixelColor(x, y), cap), (x, y, image.pixelColor(x, y).name(), cap)
