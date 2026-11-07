"""AC-21: the page-level Bar Appearance and Rainbow families are spec entries of each owning mode.

The Visualizers page builds no hidden value-owner QWidget for them (their values live in the page's value cache), the
preset guard sees them, and Settings, the Studio and the model admit them through the one spec control. Membership
comes from the registry; every test-owned value is derived from the canonical defaults or the declared control,
never pinned. Settings is the real SettingsDialog, never shown, with ``StyledPopup.exec`` patched.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QCheckBox, QWidget

from core.animation import AnimationManager
from core.settings.capability_activation import set_widget_family_activated
from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import (
    build_visualizer_mode_activation, get_owned_mode_setting_keys, iter_visualizer_mode_descriptors,
)
from core.settings.visualizer_presets import get_custom_preset_index, preset_artwork_keys

pytestmark = pytest.mark.qt

FAMILIES = ("shared_bar", "rainbow")
OWNERS = tuple(d.mode_id for d in iter_visualizer_mode_descriptors()
               if any(get_owned_mode_setting_keys(d.mode_id, family) for family in FAMILIES))
RAINBOW_OWNERS = tuple(m for m in OWNERS if get_owned_mode_setting_keys(m, "rainbow"))


def _family_keys(mode):
    return [key for family in FAMILIES for key in get_owned_mode_setting_keys(mode, family).values()]


@pytest.mark.parametrize("mode", OWNERS)
def test_the_preset_guard_and_repair_fill_cover_both_families(mode):
    missing = set(_family_keys(mode)) - set(preset_artwork_keys(mode))
    assert not missing, f"{mode}: the curated-preset guard cannot see {sorted(missing)}"


@pytest.fixture
def manager(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.styled_popup import StyledPopup
    monkeypatch.setattr(StyledPopup, "exec", lambda popup: setattr(popup, "_result_value", None))
    manager = SettingsManager(application="shared_families", storage_base_dir=tmp_path)
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    manager.set("sources.folders", [str(tmp_path)])
    yield manager
    assert manager.flush(timeout=5.0)


def _use_mode(manager, mode, extra=None):
    widgets = manager.get("widgets", {})
    section = dict(widgets["spotify_visualizer"])
    section.update({"enabled": True, "visualizers_enabled": True, "mode": mode,
                    "mode_activation": build_visualizer_mode_activation([mode]),
                    f"preset_{mode}": get_custom_preset_index(mode), **(extra or {})})
    widgets["spotify_visualizer"] = section
    manager.set("widgets", widgets)


def _open(manager, mode):
    from ui.settings_dialog import SettingsDialog
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    dialog._switch_tab(dialog._tab_index_for_key("visualizers"), animate=False)
    tab = dialog.visualizers_tab
    tab._select_mode_page(mode)
    QCoreApplication.processEvents()
    return dialog, tab


def _destroy(dialog):
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


@pytest.mark.parametrize("mode", OWNERS)
def test_the_visualizers_page_builds_no_hidden_value_owner_for_the_families(manager, mode):
    _use_mode(manager, mode)
    dialog, tab = _open(manager, mode)
    try:
        assert tab.findChild(QWidget, "visualizer_studio_family_values") is None
        hidden_owners = [w for w in tab.findChildren(QCheckBox) if w.text() == "Taste the Rainbow"]
        assert hidden_owners == [], "a never-shown Rainbow checkbox still owns the family's value"
        for attr in ("rainbow_enabled", "rainbow_speed_slider", "vis_fill_color_btn", "vis_border_color_btn",
                     "vis_border_opacity", "_base_appearance_group", "_rainbow_controls_container"):
            assert not isinstance(getattr(tab, attr, None), QWidget), attr
    finally:
        _destroy(dialog)


@pytest.mark.parametrize("mode", RAINBOW_OWNERS)
def test_settings_the_studio_and_the_model_admit_a_rainbow_speed_through_its_spec_control(manager, mode):
    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_mode_settings import require_mode_settings
    from ui.studio.registry import create_adapter
    key = get_owned_mode_setting_keys(mode, "rainbow")["rainbow_speed"]
    control = require_mode_settings(mode).control(key)
    default = require_canonical_default(f"widgets.spotify_visualizer.{key}")
    wild = float(control.high) * 50.0
    expected = control.admit(wild, default)
    assert expected != wild
    assert create_adapter(mode).schema().admit(key, wild, default) == expected
    model = SpotifyVisualizerSettings.from_mapping({"mode": mode, key: wild}, apply_preset_overlay=False)
    assert getattr(model, key) == expected
    _use_mode(manager, mode, {key: wild})
    dialog, tab = _open(manager, mode)
    try:
        from ui.tabs.media.visualizer_mode_binding import FAMILY_CACHE_ATTR
        assert getattr(tab, FAMILY_CACHE_ATTR)[key] == expected
    finally:
        _destroy(dialog)


@pytest.mark.parametrize("mode", OWNERS)
def test_a_studio_family_load_round_trips_through_the_settings_save(manager, mode):
    """The Studio's family load writes the page's cache; the page's own save stores it."""
    from core.settings.visualizer_mode_settings import Colour, Slider, Toggle, require_mode_settings
    from ui.studio.settings_link import VisualizerSettingsStore
    spec = require_mode_settings(mode)
    keys = _family_keys(mode)
    _use_mode(manager, mode)
    dialog, tab = _open(manager, mode)
    try:
        stored = manager.get("widgets")["spotify_visualizer"]
        edited = {}
        for key in keys:
            control, value = spec.control(key), stored[key]
            if isinstance(control, Toggle):
                edited[key] = not bool(value)
            elif isinstance(control, Colour):
                edited[key] = [255 - int(c) for c in value[:3]] + [int(value[3]) if len(value) > 3 else 255]
            elif isinstance(control, Slider):
                edited[key] = control.low if float(value) != float(control.low) else control.high
        VisualizerSettingsStore(tab, mode)._load_families(edited)
        tab._save_settings_now()
        saved = manager.get("widgets")["spotify_visualizer"]
        for key, value in edited.items():
            assert saved[key] == pytest.approx(value), key
    finally:
        _destroy(dialog)
