"""Closing Settings while the first-run Guided Setup holds an unsaved source asks Keep/Discard first.

The real SettingsDialog is shown with ``WA_DontShowOnScreen`` (visible to Qt, no native window), so its own
first-run edge opens Guided Setup with no sources in the store. The wizard's draft gains a folder; closing the window
must offer to keep it (and then close with it saved), never judge the empty store and show the No Image Sources prompt.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication

from core.animation import AnimationManager
from core.settings.settings_manager import SettingsManager
from ui.settings_dialog import SettingsDialog
from ui.styled_popup import StyledPopup

pytestmark = pytest.mark.qt


@pytest.fixture
def manager(tmp_path):
    QApplication.instance() or QApplication([])
    manager = SettingsManager(application="guided_close_sources", storage_base_dir=tmp_path / "profile")
    manager.set("sources.folders", [])
    manager.set("sources.rss_feeds", [])
    manager.set("sources.wallpaper_pools.enabled", False)
    manager.set("sources.guided_setup_silenced", False)
    yield manager
    assert manager.flush(timeout=5.0)


@pytest.mark.parametrize("answer,saved", [("keep", True), ("discard", False)])
def test_closing_first_run_setup_with_a_new_folder_asks_keep_or_discard_first(manager, tmp_path, qtbot,
                                                                               monkeypatch, answer, saved):
    asked = []

    def fake_exec(popup):
        labels = [label for label, _value in popup._buttons]
        asked.append(labels)
        popup._result_value = answer if "Keep Changes" in labels else None  # never choose on another prompt

    monkeypatch.setattr(StyledPopup, "exec", fake_exec)
    dialog = SettingsDialog(manager, AnimationManager())
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    dialog.show()
    try:
        qtbot.waitUntil(lambda: dialog._guided_setup_panel is not None, timeout=5000)  # the first-run entry point
        panel = dialog._guided_setup_panel
        folder = str(tmp_path / "pictures")
        panel.settings.set("sources.folders", [folder])
        dialog.close()
        QCoreApplication.processEvents()
        assert asked and "Keep Changes" in asked[0]  # Keep/Discard came first
        if saved:
            assert manager.get("sources.folders") == [folder]
            assert len(asked) == 1  # no No Image Sources prompt: there is a source now
            assert not dialog.isVisible()
        else:
            assert manager.get("sources.folders") == []
            assert len(asked) == 2 and "Keep Changes" not in asked[1]  # nothing kept: the no-sources prompt follows
    finally:
        dialog._closing = True
        dialog.hide()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
