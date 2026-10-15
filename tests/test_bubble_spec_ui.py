"""Bubble's real Settings body, isolated through public temporary storage.

Run with --noconftest -p tools.pytest_qt_noenv; no user profile or environment setup.
These are control/persistence contracts, not mutable preset artwork goldens.
"""
from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QCheckBox, QWidget

from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation, get_owned_mode_setting_keys
from core.settings.visualizer_mode_settings import require_mode_settings
from core.settings.visualizer_presets import get_custom_preset_index
from ui.tabs.media.bubble_settings_binding import (
    collect_bubble_mode_settings, load_bubble_mode_settings,
)
from ui.tabs.visualizers_tab import VisualizersTab

pytestmark = pytest.mark.qt


@pytest.fixture
def body(qt_app, tmp_path):
    manager = SettingsManager(organization="SRPSSFocusedTests",
                              application=f"BubbleSpecUI_{tmp_path.name}",
                              storage_base_dir=tmp_path)
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": "bubble",
                   "mode_activation": build_visualizer_mode_activation(["bubble"]),
                   "preset_bubble": get_custom_preset_index("bubble")})
    manager.set("widgets", {"spotify_visualizer": config})
    tab = VisualizersTab(manager)
    tab._select_mode_page("bubble")
    try:
        yield tab, manager, config
    finally:
        tab._flush_pending_visualizer_save()
        tab.close()
        tab.deleteLater()
        QCoreApplication.sendPostedEvents(tab, QEvent.Type.DeferredDelete)
        assert manager.flush(timeout=5.0)


def test_hydration_is_signal_silent_and_keeps_curated_selection(body):
    tab, manager, config = body
    slider = tab._bubble_preset_slider
    previous = slider.blockSignals(True)
    try:
        slider.set_preset_index(0)
    finally:
        slider.blockSignals(previous)
    token = tab._save_coalesce_token
    stored = deepcopy(manager.get("widgets"))
    load_bubble_mode_settings(tab, {**config, "bubble_drift_direction": "swirl_ccw",
                                   "bubble_big_bass_pulse": 0.613,
                                   "bubble_ghosting_enabled": False})
    assert slider.preset_index() == 0
    assert tab._save_coalesce_token == token
    assert manager.get("widgets") == stored


@pytest.mark.parametrize("direction", [
    "none", "left", "right", "diagonal", "swish_horizontal", "swish_vertical",
    "random", "swirl_cw", "swirl_ccw",
])
def test_every_drift_direction_round_trips_as_one_authored_key(body, direction):
    tab, _manager, config = body
    load_bubble_mode_settings(tab, {**config, "bubble_drift_direction": direction})
    values = collect_bubble_mode_settings(tab)
    assert values["bubble_drift_direction"] == direction
    assert not any("swirl" in key for key in values)
    swirl = direction.startswith("swirl_")
    assert tab.bubble_swirl_enabled.isChecked() == swirl
    assert tab._bubble_swirl_direction_row_widget.isHidden() == (not swirl)
    assert tab._bubble_drift_direction_row_widget.isHidden() == swirl
    assert tab._bubble_stream_direction_row_widget.isHidden() == swirl
    assert tab.bubble_stream_direction.isEnabled() == (not swirl)


def test_swirl_edits_save_only_the_canonical_direction_and_switch_to_custom(body):
    tab, manager, config = body
    load_bubble_mode_settings(tab, {**config, "bubble_drift_direction": "left"})
    tab.bubble_swirl_enabled.setChecked(True)
    tab.bubble_swirl_direction.setCurrentIndex(tab.bubble_swirl_direction.findData("swirl_ccw"))
    tab._save_settings_now()
    saved = manager.get("widgets.spotify_visualizer")
    assert saved["bubble_drift_direction"] == "swirl_ccw"
    assert saved["preset_bubble"] == get_custom_preset_index("bubble")
    assert not any(key.startswith("bubble_swirl") for key in saved)


def test_friendly_choices_persist_codes(body):
    tab, _manager, config = body
    load_bubble_mode_settings(tab, {**config, "bubble_stream_direction": "diagonal"})
    assert collect_bubble_mode_settings(tab)["bubble_stream_direction"] == "top_right"
    cases = ((tab.bubble_stream_direction, "Top Left", "top_left", "bubble_stream_direction"),
             (tab.bubble_collision_pop_mode, "One Bubble", "one", "bubble_collision_pop_mode"),
             (tab.bubble_specular_direction, "Bottom Right", "bottom_right", "bubble_specular_direction"),
             (tab.bubble_gradient_direction, "Center Out Reverse", "center_out_reverse", "bubble_gradient_direction"))
    for widget, label, code, key in cases:
        index = widget.findData(code)
        assert index >= 0 and widget.itemText(index) == label
        widget.setCurrentIndex(index)
        assert collect_bubble_mode_settings(tab)[key] == code
    for widget in (tab.bubble_specular_direction, tab.bubble_gradient_direction, tab.bubble_collision_pop_mode):
        assert widget.property("comboSize") == "mini"
    assert tab.bubble_stream_direction.property("comboSize") == "compact"


@pytest.mark.parametrize("version, expected", [(1, "bottom"), (2, "top")])
def test_gradient_input_migrates_once_and_collects_current_version(body, version, expected):
    tab, _manager, config = body
    load_bubble_mode_settings(tab, {**config, "bubble_gradient_direction": "top",
                                   "bubble_gradient_semantics_version": version})
    canonical = collect_bubble_mode_settings(tab)
    assert canonical["bubble_gradient_direction"] == expected
    assert canonical["bubble_gradient_semantics_version"] == 2
    load_bubble_mode_settings(tab, canonical)
    assert collect_bubble_mode_settings(tab)["bubble_gradient_direction"] == expected


def test_ghost_conditions_follow_toggle_without_erasing_values(body):
    tab, _manager, config = body
    load_bubble_mode_settings(tab, {**config, "bubble_ghosting_enabled": True,
                                   "bubble_ghost_alpha": 0.37, "bubble_ghost_decay": 0.64})
    for enabled in (True, False, True):
        tab.bubble_ghosting_enabled.setChecked(enabled)
        for key in ("bubble_ghost_alpha", "bubble_ghost_decay"):
            assert tab._bubble_rows[key].isHidden() == (not enabled)
        values = collect_bubble_mode_settings(tab)
        assert values["bubble_ghosting_enabled"] == enabled
        assert values["bubble_ghost_alpha"] == pytest.approx(0.37)
        assert values["bubble_ghost_decay"] == pytest.approx(0.64)


def test_hydration_retains_truncation_and_ghost_decay_rounding(body):
    tab, _manager, config = body
    load_bubble_mode_settings(tab, {**config, "bubble_big_bass_pulse": 0.619,
                                   "bubble_stream_reactivity": 1.237,
                                   "bubble_big_size_max": 0.0379,
                                   "bubble_ghost_alpha": 0.379, "bubble_ghost_decay": 0.376})
    values = collect_bubble_mode_settings(tab)
    assert values["bubble_big_bass_pulse"] == pytest.approx(0.61)
    assert values["bubble_stream_reactivity"] == pytest.approx(1.23)
    assert values["bubble_big_size_max"] == pytest.approx(0.037)
    assert tab.bubble_big_size_max_label.text() == "37"
    assert values["bubble_ghost_alpha"] == pytest.approx(0.37)
    assert values["bubble_ghost_decay"] == pytest.approx(0.38)


def test_bucket_order_empty_layout_and_external_owners_are_preserved(body):
    tab, _manager, _config = body
    spec = require_mode_settings("bubble")
    assert [bucket.title for bucket in spec.buckets] == [
        "Appearance", "Motion", "Bounce", "Reactivity", "Population", "Layout", "Ghost"]
    for owner, expected in ((tab._bubble_normal, ["appearance", "motion", "bounce"]),
                            (tab._bubble_advanced, ["reactivity", "population", "layout", "ghost"])):
        authored = [owner.layout().itemAt(index).widget().objectName()
                    for index in range(owner.layout().count())
                    if owner.layout().itemAt(index).widget() is not None
                    and owner.layout().itemAt(index).widget().objectName().startswith("bubble_bucket_")]
        assert authored == [f"bubble_bucket_{name}" for name in expected]
    layout_host = tab._bubble_settings_container.findChild(QWidget, "bubble_bucket_layout")
    assert layout_host is not None
    assert layout_host.layout().itemAt(2).widget().layout().count() == 0
    body_keys = set(spec.keys())
    assert not any(key.startswith("bubble_bar_") for key in body_keys)
    for family in ("rainbow", "shared_bar", "technical"):
        assert body_keys.isdisjoint(get_owned_mode_setting_keys("bubble", family).values())
    # The actual tab retains its existing external Rainbow and technical hosts.
    assert tab.rainbow_enabled is not None
    assert [widget for widget in tab.findChildren(QCheckBox)
            if widget.text() == "Taste the Rainbow"] == [tab.rainbow_enabled]
    assert tab._bubble_settings_container.findChildren(QWidget, "bubble_bucket_rainbow") == []
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode
    assert get_per_mode_controls_for_mode(tab, "bubble")
    assert all(control.bucket != "technical" for control in spec.controls)
