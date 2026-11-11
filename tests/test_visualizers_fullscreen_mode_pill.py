"""Expanded Visualizer M3b: Visualizers → Fullscreen Mode, on the real SettingsDialog (never shown).

Operator, 8 Nov: "These settings should all go into a new pill in Visualizers "Fullscreen Mode". Have it as the tab
first after Setup." The bars are structural (position, persistence, buckets), never wording or authored values: the
pill sits right after Setup and before every mode pill; each control writes the one canonical value
``widgets.spotify_visualizer.fullscreen_overlays`` (and nothing it does not show, such as Fullscreen Edit's placement);
a reload shows what is stored; its buckets start closed with one open at a time; the page is the remembered
editing path that Settings reopens on. Every value written is test-owned or derived from the canonical default.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QCheckBox, QToolButton

from core.animation import AnimationManager
from core.settings.capability_activation import set_widget_family_activated
from core.settings.default_contract import require_canonical_default
from core.settings.fullscreen_overlays import (
    CORNERS,
    FULLSCREEN_OVERLAYS_KEY,
    OVERLAY_IDS,
    canonical_fullscreen_overlays,
    rebase_offset_for_corner,
)
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation, iter_visualizer_mode_descriptors

pytestmark = pytest.mark.qt


@pytest.fixture
def manager(tmp_path, monkeypatch):
    from ui.styled_popup import StyledPopup

    monkeypatch.setattr(StyledPopup, "exec", lambda popup: 0)
    QApplication.instance() or QApplication([])
    manager = SettingsManager(application="fullscreen_pill", storage_base_dir=tmp_path)
    modes = [d.mode_id for d in iter_visualizer_mode_descriptors()]
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": modes[0],
                   "mode_activation": build_visualizer_mode_activation(modes)})
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = config
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    manager.set("sources.folders", [str(tmp_path)])
    yield manager
    assert manager.flush(timeout=5.0)


def _dialog(manager):
    from ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    dialog._switch_tab(dialog._tab_index_for_key("visualizers"), animate=False)
    QCoreApplication.processEvents()
    return dialog, dialog.visualizers_tab


def _destroy(dialog):
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


def _stored(manager) -> dict:
    return manager.get(FULLSCREEN_OVERLAYS_KEY)


def _flush(tab) -> None:
    tab.flush_pending_changes()
    QCoreApplication.processEvents()


def test_the_pill_is_first_after_setup_and_before_every_mode_pill(manager):
    dialog, tab = _dialog(manager)
    flow = tab._nav_flow.layout()                     # the pills' one ordered row (it wraps on narrow pages)
    pills = [flow.itemAt(index).widget() for index in range(flow.count())]
    assert pills[0] is tab._setup_pill and pills[1] is tab._fullscreen_pill
    assert set(pills[2:]) == set(tab._mode_pills.values())
    assert tab._fullscreen_pill in tab._nav_group.buttons() and tab._fullscreen_pill.isCheckable()
    stack = [tab._page_stack.widget(index) for index in range(tab._page_stack.count())]
    assert stack.index(tab._setup_page) < stack.index(tab._fullscreen_page) < stack.index(tab._mode_page)
    tab._fullscreen_pill.click()
    assert tab._page_stack.currentWidget() is tab._fullscreen_page and tab._fullscreen_pill.isChecked()
    _destroy(dialog)


def test_every_control_writes_the_one_canonical_value_and_keeps_what_it_does_not_show(manager):
    canonical = canonical_fullscreen_overlays()
    # Fullscreen Edit's placement (M3c) is stored but not shown here: a test-owned value it must keep, except that
    # a new Corner rebases the offset by the one owner's rule.
    seeded = deepcopy(canonical)
    for overlay in OVERLAY_IDS:
        seeded[overlay].update(offset_x=0.125, offset_y=-0.25, scale=1.25)
    seeded["now_playing"]["child_geometry"] = {"artwork": {"width_scale": 1.5, "height_scale": 1.5,
                                                           "x_offset": 0.0, "y_offset": 0.0}}
    manager.set(FULLSCREEN_OVERLAYS_KEY, seeded)
    dialog, tab = _dialog(manager)
    page = tab._fullscreen_page
    tab._fullscreen_pill.click()

    checks = {
        (overlay, key): getattr(page, f"{overlay}_{key}")
        for overlay in OVERLAY_IDS for key in ("always_show", "card", "media_controls", "seek_bar", "hover_reveal")
        if hasattr(page, f"{overlay}_{key}")
    }
    assert len(checks) == sum(1 for overlay in OVERLAY_IDS for key, value in canonical[overlay].items()
                              if isinstance(value, bool))
    for (overlay, key), check in checks.items():
        assert check.isChecked() is canonical[overlay][key]
        check.click()
        _flush(tab)
        assert _stored(manager)[overlay][key] is (not canonical[overlay][key]), (overlay, key)
    for overlay, combo in (("preset", page.preset_corner), ("now_playing", page.now_playing_corner)):
        assert [combo.itemData(index) for index in range(combo.count())] == list(CORNERS)
        other = next(corner for corner in CORNERS if corner != canonical[overlay]["corner"])
        combo.setCurrentIndex(combo.findData(other))
        _flush(tab)
        assert _stored(manager)[overlay]["corner"] == other
    page.font_size.setValue(page.font_size.value() + 1)
    _flush(tab)
    assert _stored(manager)["font_size"] == canonical["font_size"] + 1
    # Nothing the page does not show was touched, except the offset the new corner rebased.
    stored = _stored(manager)
    assert stored["font_family"] == canonical["font_family"]
    for overlay in OVERLAY_IDS:
        rebased = rebase_offset_for_corner(seeded[overlay], stored[overlay]["corner"])
        assert (stored[overlay]["offset_x"], stored[overlay]["offset_y"]) == (rebased["offset_x"],
                                                                              rebased["offset_y"])
        assert stored[overlay]["scale"] == 1.25
    assert stored["now_playing"]["child_geometry"]["artwork"]["width_scale"] == 1.5
    _destroy(dialog)


def test_a_reload_shows_the_stored_value(manager):
    dialog, tab = _dialog(manager)
    page = tab._fullscreen_page
    flipped = deepcopy(canonical_fullscreen_overlays())
    flipped["preset"]["always_show"] = not flipped["preset"]["always_show"]
    flipped["now_playing"]["corner"] = next(c for c in CORNERS if c != flipped["now_playing"]["corner"])
    manager.set(FULLSCREEN_OVERLAYS_KEY, flipped)
    tab.load_from_settings()
    assert page.preset_always_show.isChecked() is flipped["preset"]["always_show"]
    assert page.now_playing_corner.currentData() == flipped["now_playing"]["corner"]
    assert page.values() == flipped
    # Reset to defaults: the page shows the canonical value again (and saving it writes exactly that).
    manager.reset_to_defaults()
    tab.load_from_settings()
    assert page.values() == canonical_fullscreen_overlays()
    _destroy(dialog)


def test_transport_style_survives_save_reload_and_keeps_edit_placement(manager):
    dialog, tab = _dialog(manager)
    try:
        page = tab._fullscreen_page
        value = canonical_fullscreen_overlays()
        value["now_playing"].update(media_controls=True, media_controls_style="bar", offset_x=0.125,
                                    child_geometry={"title": {"x_offset": 0.04}})
        manager.set(FULLSCREEN_OVERLAYS_KEY, value)
        tab.load_from_settings()
        before = deepcopy(page.values())
        assert page.now_playing_controls_style.isEnabled()
        page.now_playing_controls_style.setCurrentIndex(page.now_playing_controls_style.findData("floating"))
        _flush(tab)
        expected = deepcopy(before)
        expected["now_playing"]["media_controls_style"] = "floating"
        assert _stored(manager) == expected
        tab.load_from_settings()
        assert page.now_playing_controls_style.currentData() == "floating"
        assert page.values() == expected
    finally:
        _destroy(dialog)


def test_its_buckets_start_closed_one_opens_at_a_time_and_settings_reopens_on_it(manager):
    from core.settings.ui_bucket_state import project_settings_bucket_context
    from ui.settings_tabs import settings_tab_descriptor

    dialog, tab = _dialog(manager)
    tab._fullscreen_pill.click()
    page = tab._fullscreen_page
    toggles = [button for button in page.findChildren(QToolButton) if button.isCheckable()]
    assert len(toggles) >= 3 and not any(button.isChecked() for button in toggles)
    toggles[0].click()
    toggles[1].click()
    assert [button.isChecked() for button in toggles[:2]] == [False, True]
    assert sum(button.isChecked() for button in toggles) == 1
    remembered = dict(manager.get("ui.visualizer_bucket_states"))
    assert len(remembered) == 1 and next(iter(remembered)).startswith("fullscreen:")
    # The page is the editing path: its pill keeps the open bucket through the dialog's projection.
    view = tab.get_view_state()
    pill = settings_tab_descriptor("visualizers").pill_of(view)
    project_settings_bucket_context(manager, "visualizers", pill)
    assert manager.get("ui.visualizer_bucket_states") == remembered
    # Leaving it for Setup closes its editing path.
    tab._setup_pill.click()
    assert not any(button.isChecked() for button in toggles) and not manager.get("ui.visualizer_bucket_states")
    # The view state round-trips onto the page.
    tab.restore_view_state(view)
    assert tab._page_stack.currentWidget() is page
    _destroy(dialog)


def test_its_controls_carry_tooltips_and_the_checkboxes_follow_the_settings_style(manager):
    dialog, tab = _dialog(manager)
    page = tab._fullscreen_page
    for check in page.findChildren(QCheckBox):
        assert check.toolTip() and check.property("circleIndicator") is True
    for combo in (page.preset_corner, page.now_playing_corner, page.font_combo, page.font_size):
        assert combo.toolTip()
    _destroy(dialog)
