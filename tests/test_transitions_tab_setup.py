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


def test_setup_module_grid_and_pills_are_responsive(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab.resize(1000, 700)
    tab.show()
    qapp.processEvents()
    # Activation modules lay out as a responsive grid (>=2 columns when wide).
    cbs = list(tab._activation_checkboxes.values())
    assert all(c.width() > 0 and c.height() > 0 for c in cbs)
    first_row_y = min(c.y() for c in cbs)
    assert len([c for c in cbs if c.y() == first_row_y]) >= 2
    # Pills lay out (wrap) rather than collapsing.
    pills = [b for b in tab._nav_buttons.values() if not b.isHidden()]
    assert all(b.width() > 0 for b in pills)
    tab.hide()


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


def test_disable_all_normalizes_to_crossfade_recovery(qapp, settings_manager, qtbot):
    # Disable All would zero the activated set; the canonical normalization
    # (§2A) immediately repairs it by reactivating Crossfade and reflects that
    # in the live UI. Every OTHER transition is deactivated; pool prefs intact.
    tab = _make(qapp, settings_manager, qtbot)
    before_pool = dict(tab._pool_by_type)

    tab._set_all_transition_activation(False)
    cfg = settings_manager.get("transitions", {})
    assert is_transition_activated(cfg, "Crossfade") is True
    assert tab._activation_checkboxes["Crossfade"].isChecked() is True
    assert tab._nav_buttons["Crossfade"].isHidden() is False
    for name in get_transition_setting_names():
        if name == "Crossfade":
            continue
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


def test_transition_page_is_lazy(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    # Nothing transition-specific is built at construction (SETUP landing).
    assert tab._built_transition_pages == set()
    assert not hasattr(tab, "burn_group")
    assert not hasattr(tab, "particle_group")

    # Selecting one pill builds only that page.
    tab._on_nav_selected("Burn")
    assert hasattr(tab, "burn_group")
    assert tab._built_transition_pages == {"Burn"}
    assert not hasattr(tab, "particle_group")

    # Selecting a second builds only it (does not materialize all others).
    tab._on_nav_selected("Particle")
    assert hasattr(tab, "particle_group")
    assert tab._built_transition_pages == {"Burn", "Particle"}
    assert not hasattr(tab, "flip_group")


def test_programmatic_nav_to_deactivated_transition_redirects_to_setup(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._activation_checkboxes["Burn"].setChecked(False)
    # A stale/programmatic navigation to a deactivated transition must be
    # admitted to SETUP before any state mutation / page build / save.
    tab._on_nav_selected("Burn")
    assert tab._nav_buttons[_SETUP_NAV_KEY].isChecked() is True
    assert not tab._setup_page.isHidden()
    assert not hasattr(tab, "burn_group")
    assert tab._current_transition != "Burn"
    assert settings_manager.get("transitions", {}).get("type") != "Burn"


def test_deactivated_transition_never_built(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._activation_checkboxes["Burn"].setChecked(False)
    # Even a programmatic selection must not build a deactivated page.
    tab._on_nav_selected("Burn")
    assert not hasattr(tab, "burn_group")
    assert "Burn" not in tab._built_transition_pages


def test_deactivate_selected_retires_page_then_reactivate_rebuilds(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._on_nav_selected("Burn")
    assert hasattr(tab, "burn_group")

    # Deactivate the selected transition -> nav returns to SETUP, page retired.
    tab._activation_checkboxes["Burn"].setChecked(False)
    assert tab._nav_buttons[_SETUP_NAV_KEY].isChecked() is True
    assert not hasattr(tab, "burn_group")
    assert "Burn" not in tab._built_transition_pages

    # Reactivation restores the pill but does NOT rebuild the page.
    tab._activation_checkboxes["Burn"].setChecked(True)
    assert tab._nav_buttons["Burn"].isHidden() is False
    assert not hasattr(tab, "burn_group")

    # Selecting it after reactivation rebuilds + hydrates.
    tab._on_nav_selected("Burn")
    assert hasattr(tab, "burn_group")


def test_detailed_settings_survive_deactivate_reactivate(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._on_nav_selected("Ripple")
    tab.ripple_count_spin.setValue(7)
    tab._save_settings()

    tab._activation_checkboxes["Ripple"].setChecked(False)  # retire
    tab._activation_checkboxes["Ripple"].setChecked(True)   # restore pill
    tab._on_nav_selected("Ripple")                          # rebuild + hydrate
    assert tab.ripple_count_spin.value() == 7
    assert settings_manager.get("transitions", {}).get("ripple", {}).get("ripple_count") == 7


def test_unrelated_save_preserves_unbuilt_transition_detail(qapp, settings_manager, qtbot):
    # Persist a distinctive Burn detail, then construct the tab (Burn unbuilt).
    cfg = dict(settings_manager.get("transitions", {}))
    cfg["burn"] = dict(cfg.get("burn", {}))
    cfg["burn"]["char_width"] = 0.99
    settings_manager.set("transitions", cfg)
    settings_manager.save()

    tab = _make(qapp, settings_manager, qtbot)
    assert not hasattr(tab, "burn_group")
    # An unrelated SETUP mutation triggers a save while Burn is unbuilt.
    tab._pool_checkboxes["Wipe"].setChecked(True)
    # Burn detail preserved (not reconstructed from never-built controls).
    assert settings_manager.get("transitions", {}).get("burn", {}).get("char_width") == 0.99


def test_hidden_combo_is_not_a_second_authority(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._on_nav_selected("Wipe")
    assert settings_manager.get("transitions", {}).get("type") == "Wipe"
    # Poking the hidden mirror combo must NOT change the authoritative manual type.
    tab.transition_combo.setCurrentText("Burn")
    tab._save_settings()
    assert settings_manager.get("transitions", {}).get("type") == "Wipe"


def test_empty_effective_pool_disables_random_live(qapp, settings_manager, qtbot):
    # Random on; make the effective pool empty by clearing all pool membership.
    tab = _make(qapp, settings_manager, qtbot)
    tab._use_random_checkbox.setChecked(True)
    for name in get_transition_setting_names():
        cb = tab._pool_checkboxes[name]
        if cb.isChecked():
            cb.setChecked(False)
    # Live UI reflects the normalization: Random turned off.
    assert tab._use_random_checkbox.isChecked() is False
    cfg = settings_manager.get("transitions", {})
    assert cfg.get("random_always") is False
    assert is_transition_activated(cfg, cfg.get("type")) is True


def test_manual_deactivation_persists_activated_replacement(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._use_random_checkbox.setChecked(False)
    tab._on_nav_selected("Wipe")
    assert settings_manager.get("transitions", {}).get("type") == "Wipe"
    # Deactivating the current manual transition -> deterministic activated type.
    tab._activation_checkboxes["Wipe"].setChecked(False)
    cfg = settings_manager.get("transitions", {})
    assert cfg.get("type") != "Wipe"
    assert is_transition_activated(cfg, cfg.get("type")) is True


def test_browsing_while_random_on_leaves_random_enabled(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._use_random_checkbox.setChecked(True)
    assert settings_manager.get("transitions", {}).get("random_always") is True
    tab._on_nav_selected("Wipe")
    assert settings_manager.get("transitions", {}).get("random_always") is True


def test_random_state_live_links_with_external_authority(qapp, settings_manager, qtbot):
    # Use Random Transitions and the context-menu Random action are two views of
    # the one canonical transitions.random_always. An open TransitionsTab must
    # reflect an external change and must not resurrect its stale value on save.
    tab = _make(qapp, settings_manager, qtbot)
    tab._use_random_checkbox.setChecked(False)
    assert settings_manager.get("transitions", {}).get("random_always") is False

    # External authority (e.g. context menu) flips random_always -> True.
    cfg = dict(settings_manager.get("transitions", {}))
    cfg["random_always"] = True
    settings_manager.set("transitions", cfg)
    qapp.processEvents()
    assert tab._use_random_checkbox.isChecked() is True

    # An unrelated tab save must NOT write the stale False back.
    tab._pool_checkboxes["Wipe"].setChecked(True)
    assert settings_manager.get("transitions", {}).get("random_always") is True

    # Reverse direction: external -> False is reflected and not resurrected.
    cfg = dict(settings_manager.get("transitions", {}))
    cfg["random_always"] = False
    settings_manager.set("transitions", cfg)
    qapp.processEvents()
    assert tab._use_random_checkbox.isChecked() is False
    tab._pool_checkboxes["Wipe"].setChecked(False)
    assert settings_manager.get("transitions", {}).get("random_always") is False


def test_external_manual_type_change_is_reflected(qapp, settings_manager, qtbot):
    tab = _make(qapp, settings_manager, qtbot)
    tab._use_random_checkbox.setChecked(False)
    tab._on_nav_selected("Slide")
    assert tab._current_transition == "Slide"

    # External concrete selection (context menu) changes type -> Wipe.
    cfg = dict(settings_manager.get("transitions", {}))
    cfg["type"] = "Wipe"
    cfg["random_always"] = False
    settings_manager.set("transitions", cfg)
    qapp.processEvents()
    assert tab._current_transition == "Wipe"
    # A later unrelated save must not overwrite type back to the stale Slide.
    tab._pool_checkboxes["Wipe"].setChecked(True)
    assert settings_manager.get("transitions", {}).get("type") == "Wipe"


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

def test_burn_exposes_and_persists_independent_ember_colour(qapp, settings_manager, qtbot):
    from PySide6.QtGui import QColor

    tab = _make(qapp, settings_manager, qtbot)
    tab._on_nav_selected("Burn")
    assert hasattr(tab, "burn_glow_color_btn")
    assert hasattr(tab, "burn_ember_color_btn")

    tab._burn_ember_color = QColor(20, 90, 210, 240)
    tab._apply_burn_ember_color_btn()
    tab._save_settings()

    burn = settings_manager.get("transitions", {}).get("burn", {})
    assert burn.get("ember_color") == [20, 90, 210, 240]
    # The primary edge glow remains independently authored.
    assert burn.get("glow_color") != burn.get("ember_color")

