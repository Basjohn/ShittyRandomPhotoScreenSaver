"""Widget Opacity is an offset from a theme-authored base: stored values keep their look, unset draws the base."""
import json
import uuid
from dataclasses import dataclass

import pytest

from core.settings.surface_opacity import (
    WIDGET_OPACITY_BASE, admit_opacity_adjust, effective_opacity_adjust, resolve_opacity_adjust,
)
from core.settings.widget_opacity_base_input_compat import OPACITY_BASE_VERSION_KEY

OLD_STORED = -0.2          # an arbitrary old-meaning value (not the default, not the base)


def _manager(tmp_path, name):
    from core.settings.settings_manager import SettingsManager
    return SettingsManager(organization="Test", application=f"opacity_base_{name}_{uuid.uuid4().hex}",
                           storage_base_dir=tmp_path / name)


def _reload(manager, tmp_path, name):
    from core.settings.settings_manager import SettingsManager
    return SettingsManager(organization=manager.get_organization_name(),
                           application=manager.get_application_name(), storage_base_dir=tmp_path / name)


def _rewrite_global(manager, edit):
    with manager._lock:
        widgets = dict(manager._settings.value("widgets"))
        section = dict(widgets["global"])
        edit(section)
        widgets["global"] = section
        manager._settings.setValue("widgets", widgets)
        manager._settings.sync()


def _old_profile(tmp_path, name, stored):
    """A profile saved before the base existed: the value in the old meaning, no marker."""
    manager = _manager(tmp_path, name)

    def edit(section):
        section.pop(OPACITY_BASE_VERSION_KEY, None)
        if stored is None:
            section.pop("widget_opacity_adjust", None)
        else:
            section["widget_opacity_adjust"] = stored
    _rewrite_global(manager, edit)
    return manager


def test_a_stored_offset_keeps_its_look_and_is_shifted_once(tmp_path):
    manager = _old_profile(tmp_path, "stored", OLD_STORED)
    reloaded = _reload(manager, tmp_path, "stored")
    widgets = reloaded.get("widgets")
    assert effective_opacity_adjust(widgets, "widget") == pytest.approx(OLD_STORED)
    assert resolve_opacity_adjust(widgets, "widget") == pytest.approx(OLD_STORED - WIDGET_OPACITY_BASE)
    again = _reload(reloaded, tmp_path, "stored")                       # idempotent: no second shift
    assert effective_opacity_adjust(again.get("widgets"), "widget") == pytest.approx(OLD_STORED)


def test_an_unset_value_takes_the_base(tmp_path):
    manager = _old_profile(tmp_path, "unset", None)
    widgets = _reload(manager, tmp_path, "unset").get("widgets")
    assert resolve_opacity_adjust(widgets, "widget") == 0.0
    assert effective_opacity_adjust(widgets, "widget") == admit_opacity_adjust(WIDGET_OPACITY_BASE)


def test_a_fresh_profile_draws_the_base_and_other_targets_have_none(tmp_path):
    widgets = _manager(tmp_path, "fresh").get("widgets")
    assert effective_opacity_adjust(widgets, "widget") == admit_opacity_adjust(WIDGET_OPACITY_BASE)
    for target in ("settings", "header_surface", "media_controls", "border_surface"):
        assert effective_opacity_adjust(widgets, target) == resolve_opacity_adjust(widgets, target)


def test_an_sst_written_before_the_base_keeps_its_look(tmp_path):
    from core.settings.sst_io import import_from_sst
    manager = _manager(tmp_path, "sst")
    snapshot = tmp_path / "old.sst"
    snapshot.write_text(json.dumps({"snapshot": {"widgets": {"global": {"widget_opacity_adjust": OLD_STORED}}}}),
                        encoding="utf-8")
    assert import_from_sst(manager, str(snapshot), merge=True) is True
    assert effective_opacity_adjust(manager.get("widgets"), "widget") == pytest.approx(OLD_STORED)


def test_the_page_save_keeps_the_marker_so_a_reload_does_not_shift_again(qt_app, tmp_path):
    from ui.tabs.widgets_tab import WidgetsTab
    manager = _manager(tmp_path, "save")
    tab = WidgetsTab(manager, lazy_sections=True, initial_view_state={"subtab_id": "defaults"})
    try:
        tab.widget_opacity_adjust_slider.setValue(30)
        tab.flush_pending_changes()
    finally:
        tab.deleteLater()
    stored = manager.get("widgets")["global"]
    assert stored[OPACITY_BASE_VERSION_KEY] >= 1
    reloaded = _reload(manager, tmp_path, "save").get("widgets")
    assert resolve_opacity_adjust(reloaded, "widget") == pytest.approx(0.30)


def test_the_family_style_seam_draws_the_effective_adjustment():
    from PySide6.QtGui import QColor
    from rendering.quick.widgets.host import OverlayCardStyle
    from rendering.quick.widgets.surface_material import with_surface_material

    @dataclass(frozen=True)
    class Style:
        card_style: OverlayCardStyle

    style = Style(OverlayCardStyle(background_color=QColor(17, 29, 43, 127)))
    for stored in (None, 0.0, 0.25):
        glass = {"global": {"surface_material": "glass"}}
        if stored is not None:
            glass["global"]["widget_opacity_adjust"] = stored
        result = with_surface_material(style, glass, "clock")
        assert result.card_style.surface_opacity_adjust == effective_opacity_adjust(glass, "widget")
