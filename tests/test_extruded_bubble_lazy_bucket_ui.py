"""EB sectional lazy Settings/preset persistence and cross-bucket conditions.

Run on the operator's PySide6 native environment, never assume a green logical
simulation proves native frame quality.
"""
from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
from core.settings.visualizer_presets import get_custom_preset_index
from ui.tabs.media.extruded_bubble_settings_binding import (
    collect_extruded_bubble_mode_settings, load_extruded_bubble_mode_settings,
)
from ui.tabs.visualizers_tab import VisualizersTab
from ui.widgets.continuous_border import BucketToggle

pytestmark = pytest.mark.qt


@pytest.fixture
def eb_tab(qt_app, tmp_path):
    manager = SettingsManager(organization="SRPSSFocusedTests",
                              application=f"ExtrudedBubbleLazy_{tmp_path.name}",
                              storage_base_dir=tmp_path)
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": "extruded_bubble",
                   "mode_activation": build_visualizer_mode_activation(["extruded_bubble"]),
                   "preset_extruded_bubble": get_custom_preset_index("extruded_bubble")})
    manager.set("widgets", {"spotify_visualizer": config})
    tab = VisualizersTab(manager)
    tab._select_mode_page("extruded_bubble")
    try:
        yield tab, config
    finally:
        tab._flush_pending_visualizer_save()
        tab.close()
        tab.deleteLater()
        QCoreApplication.sendPostedEvents(tab, QEvent.Type.DeferredDelete)
        assert manager.flush(timeout=5.0)


def toggle_bucket(tab, key):
    host = tab._extruded_bubble_settings_container.findChild(
        __import__("PySide6").QtWidgets.QWidget, f"extruded_bubble_bucket_{key}")
    assert host is not None
    toggle = host.findChild(BucketToggle)
    assert toggle is not None
    if not toggle.isChecked():
        toggle.setChecked(True)
    return toggle


def test_closed_buckets_preserve_authoritative_values_through_hydration(eb_tab):
    tab, config = eb_tab
    assert not tab._extruded_bubble_lazy_built
    # New source values must exist in persistence even with zero child widgets.
    payload = {**config, "extruded_bubble_large_size": 1.7,
               "extruded_bubble_small_size": 0.65,
               "extruded_bubble_bead_size": 1.15,
               "extruded_bubble_camera_fov": 37.0}
    load_extruded_bubble_mode_settings(tab, payload)
    assert not hasattr(tab, "extruded_bubble_large_size")
    collected = collect_extruded_bubble_mode_settings(tab)
    for key in ("extruded_bubble_large_size", "extruded_bubble_small_size",
                "extruded_bubble_bead_size", "extruded_bubble_camera_fov"):
        assert collected[key] == pytest.approx(payload[key])
    toggle_bucket(tab, "bubbles")
    assert tab._extruded_bubble_lazy_built == {"bubbles"}
    assert collect_extruded_bubble_mode_settings(tab)["extruded_bubble_large_size"] == pytest.approx(1.7)
    # A changed preset/hydration must update both built and still-unbuilt buckets.
    load_extruded_bubble_mode_settings(tab, {**payload, "extruded_bubble_large_size": .9,
                                           "extruded_bubble_camera_fov": 53.0})
    assert collect_extruded_bubble_mode_settings(tab)["extruded_bubble_large_size"] == pytest.approx(.9)
    assert collect_extruded_bubble_mode_settings(tab)["extruded_bubble_camera_fov"] == pytest.approx(53.)
    toggle_bucket(tab, "camera")
    assert collect_extruded_bubble_mode_settings(tab)["extruded_bubble_camera_fov"] == pytest.approx(53.)


def test_cross_bucket_conditional_survives_out_of_order_expansion(eb_tab):
    tab, config = eb_tab
    load_extruded_bubble_mode_settings(tab, {**config, "extruded_bubble_light_type": "Deep Light"})
    toggle_bucket(tab, "water")    # dependent built BEFORE controlling Light bucket
    assert tab._extruded_bubble_rows["extruded_bubble_surface_brightness"].isHidden()
    toggle_bucket(tab, "light")
    tab.extruded_bubble_light_type.setCurrentText("Sunlit Surface")
    assert not tab._extruded_bubble_rows["extruded_bubble_surface_brightness"].isHidden()
    assert collect_extruded_bubble_mode_settings(tab)["extruded_bubble_light_type"] == "Sunlit Surface"
