"""Tests for TransitionsTab behaviour (UI-level transition settings)."""
import pytest
import uuid
from copy import deepcopy
from PySide6.QtWidgets import QApplication

from ui.tabs.transitions_tab import TransitionsTab
from core.settings.defaults import get_default_settings
from core.settings.settings_manager import SettingsManager
from rendering.transition_registry import get_transition_setting_names


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def settings_manager(tmp_path):
    # Use a dedicated org/app so we don't pollute real settings
    mgr = SettingsManager(organization="Test", application=f"TransitionsTabTest_{uuid.uuid4().hex}", storage_base_dir=tmp_path)
    mgr.reset_to_defaults()
    return mgr


def test_slide_and_wipe_directions_are_independent(qapp, settings_manager, qtbot):
    """Changing Slide direction should not overwrite Wipe direction and vice versa."""
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)

    # Start from defaults
    transitions_cfg = settings_manager.get('transitions', {}) or {}
    slide_cfg = transitions_cfg.get('slide', {}) if isinstance(transitions_cfg.get('slide', {}), dict) else {}
    wipe_cfg = transitions_cfg.get('wipe', {}) if isinstance(transitions_cfg.get('wipe', {}), dict) else {}
    canonical_wipe_direction = get_default_settings()["transitions"]["wipe"]["direction"]

    assert slide_cfg.get('direction', 'Random') == 'Random'
    assert wipe_cfg.get('direction') == canonical_wipe_direction

    # Set Slide to Left to Right, keep Wipe at its default
    tab._on_nav_selected("Slide")
    idx = tab.direction_combo.findText("Left to Right")
    assert idx >= 0
    tab.direction_combo.setCurrentIndex(idx)
    tab._save_settings()

    transitions_cfg = settings_manager.get('transitions', {}) or {}
    slide_cfg = transitions_cfg.get('slide', {}) if isinstance(transitions_cfg.get('slide', {}), dict) else {}
    wipe_cfg = transitions_cfg.get('wipe', {}) if isinstance(transitions_cfg.get('wipe', {}), dict) else {}

    assert slide_cfg.get('direction') == 'Left to Right'
    # Wipe direction should remain unchanged
    assert wipe_cfg.get('direction') == canonical_wipe_direction

    # Now set Wipe to Top to Bottom, ensuring Slide stays as previously chosen
    tab._on_nav_selected("Wipe")
    idx = tab.direction_combo.findText("Top to Bottom")
    assert idx >= 0
    tab.direction_combo.setCurrentIndex(idx)
    tab._save_settings()

    transitions_cfg = settings_manager.get('transitions', {}) or {}
    slide_cfg = transitions_cfg.get('slide', {}) if isinstance(transitions_cfg.get('slide', {}), dict) else {}
    wipe_cfg = transitions_cfg.get('wipe', {}) if isinstance(transitions_cfg.get('wipe', {}), dict) else {}

    assert slide_cfg.get('direction') == 'Left to Right'
    assert wipe_cfg.get('direction') == 'Top to Bottom'


def test_default_transition_type_and_direction(qapp, settings_manager, qtbot):
    """Verify the tab loads the authoritative transition defaults."""
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)

    transitions_cfg = settings_manager.get('transitions', {}) or {}
    canonical = get_default_settings()["transitions"]
    assert transitions_cfg.get('type') == canonical['type']
    assert transitions_cfg.get('duration_ms') == canonical['duration_ms']

    slide_cfg = transitions_cfg.get('slide', {}) if isinstance(transitions_cfg.get('slide', {}), dict) else {}
    wipe_cfg = transitions_cfg.get('wipe', {}) if isinstance(transitions_cfg.get('wipe', {}), dict) else {}

    assert slide_cfg.get('direction') == canonical['slide']['direction']
    assert wipe_cfg.get('direction') == canonical['wipe']['direction']


def test_slide_motion_style_is_lazy_hydrated_and_unbuilt_saves_preserve_it(
    qapp, settings_manager, qtbot,
):
    transitions = settings_manager.get('transitions', {})
    transitions['slide'] = {'direction': 'Right to Left', 'motion_style': 'Flex'}
    settings_manager.set('transitions', transitions)
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)

    assert not hasattr(tab, 'slide_group')
    tab._save_settings()
    assert settings_manager.get('transitions', {})['slide']['motion_style'] == 'Flex'

    tab._on_nav_selected('Slide')
    assert tab.slide_motion_style_combo.currentText() == 'Flex'
    tab.slide_motion_style_combo.setCurrentText('Wobble')
    tab._save_settings()
    assert settings_manager.get('transitions', {})['slide'] == {
        'direction': 'Right to Left', 'motion_style': 'Wobble',
    }


def test_transition_combo_uses_registry_order(qapp, settings_manager, qtbot):
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)

    combo_items = [tab.transition_combo.itemText(i) for i in range(tab.transition_combo.count())]
    assert combo_items == get_transition_setting_names()


def test_glass_shatter_page_is_lazy_and_round_trips_authored_controls(
    qapp, settings_manager, qtbot
):
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    assert not hasattr(tab, "glass_shatter_group")

    tab._activation_checkboxes["Glass Shatter"].setChecked(True)
    tab._on_nav_selected("Glass Shatter")
    assert hasattr(tab, "glass_shatter_group")
    tab.glass_shards_spin.setValue(120)
    tab.glass_depth_spin.setValue(1.1)
    tab.direction_combo.setCurrentText("Center Out")
    tab._save_settings()

    section = settings_manager.get("transitions", {})["glass_shatter"]
    assert section == {**get_default_settings()["transitions"]["glass_shatter"],
                       "shards": 120, "depth": 1.1, "direction": "Center Out"}


def test_external_transition_edit_hydrates_built_page_before_duration_save(
    qapp, settings_manager, qtbot
):
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    tab._activation_checkboxes["Glass Shatter"].setChecked(True)
    tab._on_nav_selected("Glass Shatter")
    assert hasattr(tab, "glass_shatter_group")

    external = deepcopy(settings_manager.get("transitions", {}))
    external["glass_shatter"]["shards"] = 120
    external["glass_shatter"]["depth"] = 1.2
    external["durations"]["Glass Shatter"] = 2345
    settings_manager.set("transitions", external)
    qapp.processEvents()

    assert tab.glass_shards_spin.value() == 120
    assert tab.glass_depth_spin.value() == pytest.approx(1.2)
    assert tab._duration_by_type["Glass Shatter"] == 2345

    # A duration-only save must preserve the externally authored controls.
    tab._duration_by_type["Glass Shatter"] = 2450
    tab._save_settings()
    persisted = settings_manager.get("transitions", {})
    assert persisted["glass_shatter"]["shards"] == 120
    assert persisted["glass_shatter"]["depth"] == pytest.approx(1.2)

    # External deactivation bypasses the checkbox signal, so the live page
    # must still be retired at the settings refresh seam.
    external = deepcopy(persisted)
    external["activation"]["Glass Shatter"] = False
    settings_manager.set("transitions", external)
    qapp.processEvents()
    assert not hasattr(tab, "glass_shatter_group")
    assert tab._current_nav_key() == "__setup__"


def test_external_malformed_new_transition_sections_repair_before_save(
    qapp, settings_manager, qtbot
):
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    names = (
        "Glass Shatter",
        "Exploding Tiles",
        "Directional Pixel Accretion",
        "Ink Bloom",
        "Melt Drip",
    )
    for name in names:
        tab._activation_checkboxes[name].setChecked(True)
        tab._on_nav_selected(name)

    external = deepcopy(settings_manager.get("transitions", {}))
    external["glass_shatter"] = {
        "shards": "bad",
        "depth": "bad",
        "direction": "Center Out",
    }
    for section in (
        "exploding_tiles",
        "pixel_accretion",
        "ink_bloom",
        "melt_drip",
    ):
        external[section] = "bad"
    settings_manager.set("transitions", external)
    qapp.processEvents()

    canonical = get_default_settings()["transitions"]
    assert tab.glass_shards_spin.value() == canonical["glass_shatter"]["shards"]
    assert tab.glass_depth_spin.value() == pytest.approx(canonical["glass_shatter"]["depth"])
    assert tab.exploding_tiles_columns_spin.value() == canonical["exploding_tiles"]["columns"]
    assert tab.exploding_tiles_depth_spin.value() == pytest.approx(canonical["exploding_tiles"]["depth"])
    assert tab.pixel_tile_size_spin.value() == canonical["pixel_accretion"]["tile_size"]
    assert tab.pixel_travel_spin.value() == pytest.approx(canonical["pixel_accretion"]["travel"])
    assert tab.ink_bloom_detail_spin.value() == pytest.approx(canonical["ink_bloom"]["detail"])
    assert tab.melt_drip_detail_spin.value() == pytest.approx(canonical["melt_drip"]["detail"])

    # An unrelated duration write must serialize repaired controls rather than
    # resurrecting malformed external sections.
    tab._duration_by_type["Melt Drip"] = 2400
    tab._save_settings()
    persisted = settings_manager.get("transitions", {})
    assert persisted["glass_shatter"]["shards"] == canonical["glass_shatter"]["shards"]
    assert persisted["exploding_tiles"]["columns"] == canonical["exploding_tiles"]["columns"]
    assert persisted["pixel_accretion"]["tile_size"] == canonical["pixel_accretion"]["tile_size"]
    assert persisted["ink_bloom"]["detail"] == pytest.approx(canonical["ink_bloom"]["detail"])
    assert persisted["melt_drip"]["detail"] == pytest.approx(canonical["melt_drip"]["detail"])


def test_lazy_transition_page_rolls_back_failed_hydration_and_can_retry(
    qapp, settings_manager, qtbot, monkeypatch
):
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    tab._activation_checkboxes["Glass Shatter"].setChecked(True)

    original_hydrate = tab._hydrate_transition_page

    def fail_once(_name):
        raise RuntimeError("test hydration failure")

    monkeypatch.setattr(tab, "_hydrate_transition_page", fail_once)
    with pytest.raises(RuntimeError, match="test hydration failure"):
        tab._ensure_transition_page("Glass Shatter")
    assert not hasattr(tab, "glass_shatter_group")
    assert not hasattr(tab, "glass_shards_spin")
    assert "Glass Shatter" not in tab._built_transition_pages

    monkeypatch.setattr(tab, "_hydrate_transition_page", original_hydrate)
    tab._ensure_transition_page("Glass Shatter")
    assert hasattr(tab, "glass_shatter_group")
    assert hasattr(tab, "glass_shards_spin")
    assert "Glass Shatter" in tab._built_transition_pages


def test_transition_easing_control_and_saved_preference_are_retired(
    qapp,
    settings_manager,
    qtbot,
):
    transitions = settings_manager.get("transitions", {})
    transitions["easing"] = "InOutBack"
    settings_manager.set("transitions", transitions)

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    tab._save_settings()

    assert not hasattr(tab, "easing_combo")
    assert "easing" not in settings_manager.get("transitions", {})


def test_block_flip_grid_saves_the_canonical_rows_and_cols_contract(
    qapp,
    settings_manager,
    qtbot,
):
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    # Nav is activation-gated: a deactivated transition redirects to SETUP and
    # never builds its page. Activate Block Puzzle Flip via its activation
    # checkbox (which takes precedence), then select its pill so the lazy page
    # (with the grid spinboxes) builds.
    tab._activation_checkboxes["Block Puzzle Flip"].setChecked(True)
    tab._on_nav_selected("Block Puzzle Flip")
    tab.grid_rows_spin.setValue(7)
    tab.grid_cols_spin.setValue(9)
    tab._save_settings()

    block_flip = settings_manager.get("transitions", {})["block_flip"]
    assert block_flip["rows"] == 7
    assert block_flip["cols"] == 9
    assert "columns" not in block_flip


def test_melt_origin_combo_offers_origins_and_retires_edge_directions(
    qapp, settings_manager, qtbot
):
    transitions = deepcopy(settings_manager.get("transitions", {}))
    melt = dict(transitions.get("melt_drip") or {})
    melt["direction"] = "Top to Bottom"  # a retired edge direction
    transitions["melt_drip"] = melt
    transitions.setdefault("activation", {})["Melt Drip"] = True
    settings_manager.set("transitions", transitions)

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    tab._on_nav_selected("Melt Drip")
    tab.transition_combo.setCurrentText("Melt Drip")
    items = [tab.direction_combo.itemText(i) for i in range(tab.direction_combo.count())]
    assert items == ["Top Left", "Top Center", "Top Right", "Center Out", "Center In", "Random"]
    assert tab.direction_combo.currentText() == "Random"

    tab.direction_combo.setCurrentText("Center Out")
    tab._save_settings()
    assert settings_manager.get("transitions", {})["melt_drip"]["direction"] == "Center Out"


def test_glass_collision_and_reshatter_options_load_and_persist(qapp, settings_manager, qtbot):
    transitions = deepcopy(settings_manager.get("transitions", {}))
    glass = dict(transitions.get("glass_shatter") or {})
    glass["collisions"] = True
    transitions["glass_shatter"] = glass
    transitions.setdefault("activation", {})["Glass Shatter"] = True
    settings_manager.set("transitions", transitions)

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    tab._on_nav_selected("Glass Shatter")
    assert tab.glass_collisions_check.isChecked()
    assert not tab.glass_reshatter_check.isChecked()

    tab.glass_reshatter_check.setChecked(True)
    persisted = settings_manager.get("transitions", {})["glass_shatter"]
    assert persisted["collisions"] is True
    assert persisted["reshatter"] is True
