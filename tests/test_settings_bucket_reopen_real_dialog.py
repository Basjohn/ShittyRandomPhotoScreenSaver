"""The real SettingsDialog reopens on one current editing path (Settings bucket persistence contract).

Only the active tab/pill's last-open bucket (with the ancestors it needs) returns on reopen; a pill or tab the user
left presents closed. Drives the production dialog, its lazy tabs and its close path (sources configured, so close
captures the view as in use). Test-owned profile; no authored presets or values are asserted.
"""
from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget

from core.animation import AnimationManager
from core.settings.capability_activation import set_widget_family_activated
from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
from ui.settings_dialog import SettingsDialog
from ui.widgets.continuous_border import BucketToggle

pytestmark = pytest.mark.qt


@pytest.fixture
def manager(tmp_path):
    QApplication.instance() or QApplication([])
    manager = SettingsManager(application="bucket_reopen", storage_base_dir=tmp_path)
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": "extruded_bubble",
                   "mode_activation": build_visualizer_mode_activation(["extruded_bubble", "shockwave_grid"])})
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = config
    for family in ("media", "visualizers", "steam"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    manager.set("sources.folders", [str(tmp_path)])
    yield manager
    assert manager.flush(timeout=5.0)


def _dialog(manager):
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    return dialog


def _close(dialog):
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _page(dialog, key):
    index = dialog._tab_index_for_key(key)
    dialog._switch_tab(index, animate=False)
    return dialog.content_stack.widget(index)


def _depth(toggle):
    depth, widget = 0, toggle.parentWidget()
    while widget is not None:
        depth += widget.__class__.__name__ == "BucketTreeBody"
        widget = widget.parentWidget()
    return depth


def _toggle(scope: QWidget, *titles):
    """The bucket reached by ``titles`` (a top-level title, then child titles inside its body)."""
    candidates = [t for t in scope.findChildren(BucketToggle) if t.text().startswith(titles[0])]
    toggle = min(candidates, key=_depth)
    for title in titles[1:]:
        toggle = next(t for t in toggle._srpss_bucket_body.findChildren(BucketToggle) if t.text() == title)
    return toggle


def _open(scope, *titles):
    for depth in range(1, len(titles) + 1):
        toggle = _toggle(scope, *titles[:depth])
        if not toggle.isChecked():
            toggle.setChecked(True)
        QCoreApplication.processEvents()


def _open_titles(scope):
    return sorted((t.text(), _depth(t)) for t in scope.findChildren(BucketToggle) if t.isChecked())


def _visualizer_bucket(dialog, mode, key):
    host = next(h for h in dialog.findChildren(QWidget) if h.objectName() == f"{mode}_bucket_{key}")
    return host.findChild(BucketToggle)


def test_visualizer_mode_bucket_returns_and_a_left_mode_presents_closed(manager):
    dialog = _dialog(manager)
    _page(dialog, "visualizers")
    dialog.visualizers_tab._select_mode_page("extruded_bubble")
    _visualizer_bucket(dialog, "extruded_bubble", "camera").setChecked(True)
    _close(dialog)

    dialog = _dialog(manager)
    assert dialog.content_stack.currentIndex() == dialog._tab_index_for_key("visualizers")
    assert dialog.visualizers_tab._active_visualizer_mode_id == "extruded_bubble"
    assert _visualizer_bucket(dialog, "extruded_bubble", "camera").isChecked()

    # Another pill becomes the editing context: only its bucket may return.
    dialog.visualizers_tab._select_mode_page("shockwave_grid")
    _visualizer_bucket(dialog, "shockwave_grid", "camera").setChecked(True)
    _close(dialog)
    dialog = _dialog(manager)
    assert dialog.visualizers_tab._active_visualizer_mode_id == "shockwave_grid"
    assert _visualizer_bucket(dialog, "shockwave_grid", "camera").isChecked()
    dialog.visualizers_tab._select_mode_page("extruded_bubble")
    assert not _visualizer_bucket(dialog, "extruded_bubble", "camera").isChecked()

    # Leaving the tab retires its editing path.
    _page(dialog, "display")
    _close(dialog)
    dialog = _dialog(manager)
    _page(dialog, "visualizers")
    for mode in ("extruded_bubble", "shockwave_grid"):
        dialog.visualizers_tab._select_mode_page(mode)
        assert not _visualizer_bucket(dialog, mode, "camera").isChecked()
    _close(dialog)


def test_sources_bucket_returns_only_while_its_tab_stays_current(manager):
    dialog = _dialog(manager)
    page = _page(dialog, "sources")
    _open(page, "Online Wallpaper Feeds")
    _close(dialog)
    dialog = _dialog(manager)
    page = dialog.content_stack.widget(dialog._tab_index_for_key("sources"))
    assert dialog.content_stack.currentIndex() == dialog._tab_index_for_key("sources")
    assert _toggle(page, "Online Wallpaper Feeds").isChecked()
    _page(dialog, "display")
    _close(dialog)
    dialog = _dialog(manager)
    page = _page(dialog, "sources")
    assert _open_titles(page) == []
    _close(dialog)


def test_nested_widget_leaf_returns_with_its_ancestor_and_a_new_pill_replaces_it(manager):
    dialog = _dialog(manager)
    page = _page(dialog, "widgets")
    tab = dialog.widgets_tab
    tab._on_subtab_clicked(tab._widget_section_index("steam"))
    _open(page, "Achievement Pulse", "Content")
    assert _open_titles(page) == [("Achievement Pulse", 0), ("Content", 1)]
    _close(dialog)

    dialog = _dialog(manager)
    page = dialog.content_stack.widget(dialog._tab_index_for_key("widgets"))
    # Exactly the leaf and the ancestor it needs; sibling cards and their children stay closed.
    assert _open_titles(page) == [("Achievement Pulse", 0), ("Content", 1)]
    assert _toggle(page, "Achievement Pulse", "Content").isChecked()

    tab = dialog.widgets_tab
    tab._on_subtab_clicked(tab._widget_section_index("clock"))
    QCoreApplication.processEvents()
    clock_titles = [t for t in tab.findChildren(BucketToggle)
                    if _depth(t) == 0 and t.isVisibleTo(page) and not t.isChecked()]
    title = clock_titles[0].text()
    _open(page, title)
    _close(dialog)
    dialog = _dialog(manager)
    page = dialog.content_stack.widget(dialog._tab_index_for_key("widgets"))
    assert [t for t, _d in _open_titles(page)] == [title]
    _close(dialog)


def test_a_legacy_profile_with_many_dormant_opens_reopens_on_the_current_pill_only(manager):
    # The former contract stored one open bucket per mode scope: every dormant mode kept one.
    manager.set("ui.visualizer_bucket_states", {"extruded_bubble:camera": True, "shockwave_grid:camera": True})
    manager.set("ui.tab_state", {"visualizers": {"view_state": {"page": "mode", "mode_id": "shockwave_grid"}}})
    manager.set("ui.last_tab_key", "visualizers")
    manager.set("ui.last_tab_index", -1)
    dialog = _dialog(manager)
    assert dialog.visualizers_tab._active_visualizer_mode_id == "shockwave_grid"
    assert _visualizer_bucket(dialog, "shockwave_grid", "camera").isChecked()
    dialog.visualizers_tab._select_mode_page("extruded_bubble")
    assert not _visualizer_bucket(dialog, "extruded_bubble", "camera").isChecked()
    _close(dialog)
