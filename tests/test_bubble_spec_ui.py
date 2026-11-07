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


def test_bubble_builder_failure_restores_previous_mode_without_orphan(body, monkeypatch):
    """A failed lazy Bubble body must not overlay Spectrum's custom accessories.

    Deliberately interrupt AFTER the QWidget factory returns, before the host
    commits it. This reproduces the partial-mode presentation failure class.
    """
    tab, _manager, _config = body
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation

    host = tab._vis_body_host
    host.set_mode_activation(build_visualizer_mode_activation(("bubble", "spectrum")))
    tab._select_mode_page("spectrum")
    assert host.selected_mode == "spectrum"
    host.set_mode_activation(build_visualizer_mode_activation(("spectrum",)))
    host.set_mode_activation(build_visualizer_mode_activation(("spectrum", "bubble")))
    original_factory = host._factory

    def interrupted(mode):
        created = original_factory(mode)
        if mode == "bubble":
            raise RuntimeError("Injected failure before lazy body commit")
        return created

    monkeypatch.setattr(host, "_factory", interrupted)
    with pytest.raises(RuntimeError, match="Injected failure"):
        tab._select_mode_page("bubble")

    assert host.selected_mode == "spectrum"
    assert tab._get_active_visualizer_mode() == "spectrum"
    assert tab._mode_pills["spectrum"].isChecked()
    assert tab._base_appearance_group.parentWidget() is tab._studio_family_values
    assert tab._rainbow_controls_container.parentWidget() is tab._studio_family_values
    assert not any(
        item.widget() is not None and item.widget().objectName() == "visualizer_mode_body_bubble"
        for item in (tab._mode_body_layout.itemAt(i)
                     for i in range(tab._mode_body_layout.count()))
    )

    # A subsequent ordinary selection constructs exactly one clean Bubble body.
    monkeypatch.setattr(host, "_factory", original_factory)
    tab._select_mode_page("bubble")
    assert host.selected_mode == "bubble"
    assert tab._get_active_visualizer_mode() == "bubble"
    assert tab._bubble_settings_container is host.body("bubble")
    assert tab.get_visualizer_bucket_state("bubble", "particles") is False
