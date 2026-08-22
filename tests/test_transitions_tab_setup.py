"""Transitions SETUP subtab + E2.6 type="Random" normalization (Phase E2)."""
import uuid

import pytest
from PySide6.QtWidgets import QApplication

from core.settings.capability_activation import is_transition_activated
from core.settings.settings_manager import SettingsManager
from rendering.transition_registry import get_transition_setting_names
from ui.tabs.transitions_tab import TransitionsTab, _SETUP_NAV_KEY


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def settings_manager(tmp_path):
    mgr = SettingsManager(
        organization="Test",
        application=f"TransitionsSetupTest_{uuid.uuid4().hex}",
        storage_base_dir=tmp_path,
    )
    mgr.reset_to_defaults()
    return mgr


def _make(qapp, settings_manager, qtbot):
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    return tab


def test_setup_is_default_landing(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    assert _SETUP_NAV_KEY in tab._nav_buttons
    assert tab._nav_buttons[_SETUP_NAV_KEY].isChecked() is True
    assert tab._setup_page.isVisible() is True or not tab._setup_page.isHidden()
    for group in tab._transition_setting_groups:
        assert group.isHidden() is True
    # One activation pill/checkbox per transition.
    assert set(tab._activation_checkboxes) == set(get_transition_setting_names())
    for cb in tab._activation_checkboxes.values():
        assert cb.isChecked() is True  # default: all activated


def test_no_visible_dropdown_or_old_pool_checkbox(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    # The old dropdown is retained only as a hidden selection model.
    assert tab.transition_combo.isHidden() is True
    # The old per-transition "Include in Switch/Random Pool" checkbox is gone.
    assert not hasattr(tab, "pool_checkbox")


def test_deactivate_transition_hides_pill_and_pool_row_and_persists(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._activation_checkboxes["Burn"].setChecked(False)

    assert tab._nav_buttons["Burn"].isHidden() is True
    assert tab._pool_checkboxes["Burn"].isHidden() is True
    cfg = settings_manager.get("transitions", {})
    assert is_transition_activated(cfg, "Burn") is False
    # Other transitions unaffected.
    assert tab._nav_buttons["Wipe"].isHidden() is False
    assert is_transition_activated(cfg, "Wipe") is True


def test_enable_disable_all_affect_activation_only(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    before_pool = dict(tab._pool_by_type)

    tab._set_all_transition_activation(False)
    cfg = settings_manager.get("transitions", {})
    for name in get_transition_setting_names():
        assert is_transition_activated(cfg, name) is False
    # Pool membership preferences untouched by activation.
    assert cfg.get("pool") == before_pool

    tab._set_all_transition_activation(True)
    cfg = settings_manager.get("transitions", {})
    for name in get_transition_setting_names():
        assert is_transition_activated(cfg, name) is True
    assert cfg.get("pool") == before_pool


def test_use_random_toggles_random_always(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._use_random_checkbox.setChecked(False)
    assert settings_manager.get("transitions", {}).get("random_always") is False
    tab._use_random_checkbox.setChecked(True)
    assert settings_manager.get("transitions", {}).get("random_always") is True


def test_pool_membership_toggle_persists_and_only_activated_rows_shown(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._pool_checkboxes["Wipe"].setChecked(True)
    assert settings_manager.get("transitions", {}).get("pool", {}).get("Wipe") is True
    tab._pool_checkboxes["Wipe"].setChecked(False)
    assert settings_manager.get("transitions", {}).get("pool", {}).get("Wipe") is False

    # Deactivating a transition hides it from the pool list.
    tab._activation_checkboxes["Diffuse"].setChecked(False)
    assert tab._pool_checkboxes["Diffuse"].isHidden() is True


def test_selecting_transition_pill_sets_manual_type(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._on_nav_selected("Wipe")
    # Transition settings shown, setup hidden.
    assert tab._setup_page.isHidden() is True
    assert tab.transition_combo.currentText() == "Wipe"
    assert settings_manager.get("transitions", {}).get("type") == "Wipe"


def test_deactivating_current_transition_returns_to_setup(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._on_nav_selected("Wipe")
    assert tab._setup_page.isHidden() is True
    tab._activation_checkboxes["Wipe"].setChecked(False)
    # Editing a hidden transition is not allowed: nav falls back to SETUP.
    assert tab._nav_buttons[_SETUP_NAV_KEY].isChecked() is True
    assert not tab._setup_page.isHidden()


def test_e26_legacy_type_random_normalized_on_load(qapp, settings_manager, qtbot):
    # Legacy state: type="Random" acting as a second random authority.
    cfg = settings_manager.get("transitions", {})
    cfg = dict(cfg) if isinstance(cfg, dict) else {}
    cfg["type"] = "Random"
    cfg["random_always"] = False
    cfg["pool"] = {name: True for name in get_transition_setting_names()}
    settings_manager.set("transitions", cfg)
    settings_manager.save()

    tab = _make(qapp, settings_manager, qtbot)

    persisted = settings_manager.get("transitions", {})
    # Normalized: single random_always authority on, concrete manual type.
    assert persisted.get("random_always") is True
    assert persisted.get("type") != "Random"
    assert is_transition_activated(persisted, persisted.get("type")) is True
    # UI reflects it.
    assert tab._use_random_checkbox.isChecked() is True
    assert tab.transition_combo.currentText() != "Random"
