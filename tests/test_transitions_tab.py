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
    defaults = get_default_settings()["transitions"]
    canonical_slide_direction = defaults["slide"]["direction"]
    canonical_wipe_direction = defaults["wipe"]["direction"]

    assert slide_cfg.get('direction') == canonical_slide_direction
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
    # Pin both values: the canonical reshatter default is operator-owned and may change.
    glass["reshatter"] = False
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


def test_the_3d_detail_tier_lives_on_the_3d_tab_and_never_in_transitions(qapp, settings_manager, qtbot):
    """3D Detail moved to the 3D Settings tab (``scene3d``); a Transitions save never writes the
    retired ``transitions.detail_3d``."""
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    assert not hasattr(tab, "_detail_3d_combo")
    tab._use_random_checkbox.setChecked(not tab._use_random_checkbox.isChecked())
    qapp.processEvents()
    assert "detail_3d" not in settings_manager.get("transitions", {})


def test_3d_quality_choices_and_bloom_strength_round_trip_on_the_pages(qapp, settings_manager, qtbot):
    from rendering.gl_programs.scene3d import SCENE3D_ANTIALIASING_CHOICES, SCENE3D_EFFECT_CHOICES, SCENE3D_TRAIL_CHOICES

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    canonical = get_default_settings()["transitions"]
    pages = (("Exploding Tiles", "exploding_tiles"), ("Glass Shatter", "glass_shatter"), ("Crumble", "crumble"),
             ("Directional Pixel Accretion", "pixel_accretion"), ("3D Block Spins", "blockspin"))
    for name, section in pages:
        tab._activation_checkboxes[name].setChecked(True)
        tab._on_nav_selected(name)
        combo = getattr(tab, f"{section}_antialiasing_combo")
        assert combo.currentText() == canonical[section]["antialiasing"]
        choice = next(value for value in SCENE3D_ANTIALIASING_CHOICES if value != combo.currentText())
        combo.setCurrentText(choice)
        persisted = settings_manager.get("transitions", {})[section]
        assert persisted["antialiasing"] == choice
        assert set(canonical[section]) <= set(persisted)  # the page's other values survive
        motion_blur = getattr(tab, f"{section}_motion_blur_combo")
        assert motion_blur.currentText() == canonical[section]["motion_blur"]
        motion_blur.setCurrentText(next(value for value in SCENE3D_EFFECT_CHOICES if value != motion_blur.currentText()))
        assert settings_manager.get("transitions", {})[section]["motion_blur"] == motion_blur.currentText()
        trails = getattr(tab, f"{section}_motion_trails_combo")
        assert trails.currentText() == canonical[section]["motion_trails"]
        trails.setCurrentText(next(value for value in SCENE3D_TRAIL_CHOICES if value != trails.currentText()))
        assert settings_manager.get("transitions", {})[section]["motion_trails"] == trails.currentText()
    # Motion Trails is offered only where it can help (operator direction, 2026-09-29).
    assert {section for section, controls in tab._SCENE3D_CHOICES.items()
            if any(control[0] == "motion_trails" for control in controls)} == {section for _name, section in pages}
    bloom = tab.exploding_tiles_bloom_combo
    bloom.setCurrentText(next(value for value in SCENE3D_EFFECT_CHOICES if value != bloom.currentText()))
    tab.exploding_tiles_bloom_strength_spin.setValue(0.35)
    persisted = settings_manager.get("transitions", {})["exploding_tiles"]
    assert persisted["motion_blur"] == tab.exploding_tiles_motion_blur_combo.currentText()
    assert persisted["bloom"] == bloom.currentText()
    assert persisted["bloom_strength"] == pytest.approx(0.35)

    # An external write with an unknown choice is shown as the canonical value.
    external = deepcopy(settings_manager.get("transitions", {}))
    external["glass_shatter"]["antialiasing"] = "16x"
    settings_manager.set("transitions", external)
    qapp.processEvents()
    assert tab.glass_shatter_antialiasing_combo.currentText() == canonical["glass_shatter"]["antialiasing"]


def test_optional_3d_choices_live_in_a_closed_advanced_bucket(qapp, settings_manager, qtbot):
    """Operator direction (2026-09-29): the optional choices, which will grow, are bucketed."""
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    pages = (("Exploding Tiles", "exploding_tiles"), ("Glass Shatter", "glass_shatter"), ("Crumble", "crumble"),
             ("Directional Pixel Accretion", "pixel_accretion"), ("3D Block Spins", "blockspin"))
    for name, section in pages:
        tab._activation_checkboxes[name].setChecked(True)
        tab._on_nav_selected(name)
        toggle, body = getattr(tab, f"{section}_advanced_toggle"), getattr(tab, f"{section}_advanced_body")
        assert not toggle.isChecked() and body.isHidden()
        for field, *_rest in tab._SCENE3D_CHOICES[section]:
            assert body.isAncestorOf(getattr(tab, f"{section}_{field}_combo")), (section, field)
        # Controls that shape the effect itself stay on the page.
        for control in tab._SURFACE_CONTROLS.get(section, ()):
            spin = getattr(tab, f"{section}_{control[0]}_spin")
            attached = {f for fields in tab._ADVANCED_SURFACE_FIELDS.get(section, {}).values() for f in fields}
            assert body.isAncestorOf(spin) is (control[0] in attached), (section, control[0])
        toggle.setChecked(True)
        assert not body.isHidden()
    assert tab.exploding_tiles_advanced_body.isAncestorOf(tab.exploding_tiles_bloom_strength_spin)


def test_block_spins_edge_glass_round_trips_on_its_page(qapp, settings_manager, qtbot):
    from rendering.gl_programs.blockspin_options import BLOCK_SPIN_EDGE_GLASS_CHOICES

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    canonical = get_default_settings()["transitions"]["blockspin"]
    tab._activation_checkboxes["3D Block Spins"].setChecked(True)
    tab._on_nav_selected("3D Block Spins")
    combo = tab.blockspin_edge_glass_combo
    assert combo.currentText() == canonical["edge_glass"]
    for choice in BLOCK_SPIN_EDGE_GLASS_CHOICES:
        combo.setCurrentText(choice)
        persisted = settings_manager.get("transitions", {})["blockspin"]
        assert persisted["edge_glass"] == choice
        assert {"direction", "antialiasing"} <= set(persisted)  # the page's other values survive

    external = deepcopy(settings_manager.get("transitions", {}))
    external["blockspin"]["edge_glass"] = "Mirror"
    settings_manager.set("transitions", external)
    qapp.processEvents()
    assert combo.currentText() == canonical["edge_glass"]



def test_blinds_style_shows_its_own_controls_and_round_trips(qapp, settings_manager, qtbot):
    from rendering.gl_programs.blinds_options import BLINDS_STYLE_CHOICES

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    canonical = get_default_settings()["transitions"]["blinds"]
    tab._activation_checkboxes["Blinds"].setChecked(True)
    tab._on_nav_selected("Blinds")
    combo = tab.blinds_style_combo
    assert combo.currentText() == canonical["style"]
    for choice in BLINDS_STYLE_CHOICES:
        combo.setCurrentText(choice)
        slats = choice != BLINDS_STYLE_CHOICES[0]
        assert tab.blinds_slats_box.isVisibleTo(tab.blinds_group) is slats
        assert tab.blinds_flat_box.isVisibleTo(tab.blinds_group) is not slats
        assert settings_manager.get("transitions", {})["blinds"]["style"] == choice
    tab.blinds_slats_spin.setValue(tab.blinds_slats_spin.maximum())
    tab.blinds_gloss_spin.setValue(0.25)
    tab.blinds_antialiasing_combo.setCurrentText("Off")
    persisted = settings_manager.get("transitions", {})["blinds"]
    assert persisted["slats"] == tab.blinds_slats_spin.maximum()
    assert persisted["gloss"] == 0.25 and persisted["antialiasing"] == "Off"
    assert {"direction", "feather"} <= set(persisted)
    assert tab.blinds_advanced_body.isAncestorOf(tab.blinds_antialiasing_combo)

    external = deepcopy(settings_manager.get("transitions", {}))
    external["blinds"].update({"style": "Hologram", "slats": 999})
    settings_manager.set("transitions", external)
    qapp.processEvents()
    assert combo.currentText() == canonical["style"]
    assert tab.blinds_slats_spin.value() == tab.blinds_slats_spin.maximum()


def test_page_curl_page_offers_origins_and_round_trips(qapp, settings_manager, qtbot):
    from rendering.gl_programs.page_curl_options import PAGE_CURL_ORIGIN_CHOICES

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    tab._activation_checkboxes["Page Curl"].setChecked(True)
    tab._on_nav_selected("Page Curl")
    items = [tab.direction_combo.itemText(i) for i in range(tab.direction_combo.count())]
    assert items == list(PAGE_CURL_ORIGIN_CHOICES)
    tab.direction_combo.setCurrentText("Top Left")
    tab.page_curl_gloss_spin.setValue(0.8)
    tab.page_curl_size_spin.setValue(0.65)
    tab.page_curl_antialiasing_combo.setCurrentText("8x")
    persisted = settings_manager.get("transitions", {})["page_curl"]
    assert persisted == {"direction": "Top Left", "gloss": 0.8, "size": 0.65, "antialiasing": "8x"}
    assert tab.page_curl_advanced_body.isAncestorOf(tab.page_curl_antialiasing_combo)


def test_disintegrate_page_round_trips_its_controls(qapp, settings_manager, qtbot):
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    tab._activation_checkboxes["Disintegrate"].setChecked(True)
    tab._on_nav_selected("Disintegrate")
    assert "Diagonal BR-TL" in [tab.direction_combo.itemText(i) for i in range(tab.direction_combo.count())]
    tab.direction_combo.setCurrentText("Right to Left")
    tab.disintegrate_grain_spin.setValue(6)
    tab.disintegrate_wind_spin.setValue(1.5)
    tab.disintegrate_antialiasing_combo.setCurrentText("Off")
    persisted = settings_manager.get("transitions", {})["disintegrate"]
    assert persisted == {"direction": "Right to Left", "grain_size": 6, "wind": 1.5, "antialiasing": "Off"}

    external = deepcopy(settings_manager.get("transitions", {}))
    external["disintegrate"]["grain_size"] = 99
    settings_manager.set("transitions", external)
    qapp.processEvents()
    assert tab.disintegrate_grain_spin.value() == tab.disintegrate_grain_spin.maximum()


def test_accordion_fold_page_offers_edges_and_round_trips(qapp, settings_manager, qtbot):
    from rendering.gl_programs.accordion_fold_options import ACCORDION_EDGE_CHOICES

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    tab._activation_checkboxes["Accordion Fold"].setChecked(True)
    tab._on_nav_selected("Accordion Fold")
    assert [tab.direction_combo.itemText(i) for i in range(tab.direction_combo.count())] == list(ACCORDION_EDGE_CHOICES)
    tab.direction_combo.setCurrentText("Top")
    tab.accordion_pleats_spin.setValue(12)
    tab.accordion_fold_gloss_spin.setValue(0.6)
    tab.accordion_fold_antialiasing_combo.setCurrentText("2x")
    persisted = settings_manager.get("transitions", {})["accordion_fold"]
    assert persisted == {"direction": "Top", "pleats": 12, "gloss": 0.6, "antialiasing": "2x"}


def test_relief_rise_page_round_trips(qapp, settings_manager, qtbot):
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    tab._activation_checkboxes["Relief Rise"].setChecked(True)
    tab._on_nav_selected("Relief Rise")
    tab.direction_combo.setCurrentText("Diagonal BL-TR")
    tab.relief_rise_depth_spin.setValue(0.9)
    tab.relief_rise_gloss_spin.setValue(0.1)
    tab.relief_rise_antialiasing_combo.setCurrentText("Off")
    persisted = settings_manager.get("transitions", {})["relief_rise"]
    assert persisted == {"direction": "Diagonal BL-TR", "depth": 0.9, "gloss": 0.1, "antialiasing": "Off"}


def test_cube_turn_page_offers_directions_and_round_trips(qapp, settings_manager, qtbot):
    from rendering.gl_programs.cube_turn_options import CUBE_TURN_DIRECTION_CHOICES

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    tab._activation_checkboxes["Cube Turn"].setChecked(True)
    tab._on_nav_selected("Cube Turn")
    assert [tab.direction_combo.itemText(i) for i in range(tab.direction_combo.count())] == list(CUBE_TURN_DIRECTION_CHOICES)
    tab.direction_combo.setCurrentText("Up")
    tab.cube_turn_gloss_spin.setValue(0.7)
    tab.cube_turn_antialiasing_combo.setCurrentText("8x")
    persisted = settings_manager.get("transitions", {})["cube_turn"]
    assert persisted == {"direction": "Up", "gloss": 0.7, "antialiasing": "8x"}


def test_jigsaw_page_offers_orders_and_round_trips(qapp, settings_manager, qtbot):
    from rendering.gl_programs.jigsaw_options import JIGSAW_ORDER_CHOICES, JIGSAW_PIECES_RANGE

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    assert not hasattr(tab, "jigsaw_group")
    tab._activation_checkboxes["Jigsaw Piece Flip"].setChecked(True)
    tab._on_nav_selected("Jigsaw Piece Flip")
    assert [tab.direction_combo.itemText(i) for i in range(tab.direction_combo.count())] == list(JIGSAW_ORDER_CHOICES)
    order = JIGSAW_ORDER_CHOICES[1]
    pieces = JIGSAW_PIECES_RANGE[0] + 1
    tab.direction_combo.setCurrentText(order)
    tab.jigsaw_pieces_spin.setValue(pieces)
    tab.jigsaw_antialiasing_combo.setCurrentText("Off")
    persisted = settings_manager.get("transitions", {})["jigsaw"]
    assert persisted == {"direction": order, "pieces": pieces, "antialiasing": "Off"}


def test_edge_bloom_page_round_trips(qapp, settings_manager, qtbot):
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    assert not hasattr(tab, "edge_bloom_group")
    tab._activation_checkboxes["Edge Bloom Reveal"].setChecked(True)
    tab._on_nav_selected("Edge Bloom Reveal")
    assert not tab.direction_combo.isVisibleTo(tab)
    tab.edge_bloom_glow_spin.setValue(0.3)
    tab.edge_bloom_detail_spin.setValue(0.8)
    tab.edge_bloom_colour_source_combo.setCurrentText("Next Picture")
    assert not tab.edge_bloom_color_btn.isEnabled()          # the custom colour applies only to Custom
    persisted = settings_manager.get("transitions", {})["edge_bloom"]
    assert persisted["glow"] == 0.3 and persisted["detail"] == 0.8 and len(persisted["color"]) == 4
    assert persisted["color_source"] == "Next Picture"


def test_vhs_page_offers_directions_and_round_trips(qapp, settings_manager, qtbot):
    from rendering.gl_programs.vhs_options import VHS_DIRECTION_CHOICES

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    assert not hasattr(tab, "vhs_group")
    tab._activation_checkboxes["VHS Distortion"].setChecked(True)
    tab._on_nav_selected("VHS Distortion")
    assert [tab.direction_combo.itemText(i) for i in range(tab.direction_combo.count())] == list(VHS_DIRECTION_CHOICES)
    label = VHS_DIRECTION_CHOICES[0]
    tab.direction_combo.setCurrentText(label)
    tab.vhs_tracking_spin.setValue(0.2)
    tab.vhs_bleed_spin.setValue(0.9)
    tab.vhs_noise_spin.setValue(0.35)
    persisted = settings_manager.get("transitions", {})["vhs"]
    assert persisted == {"direction": label, "tracking": 0.2, "bleed": 0.9, "noise": 0.35}


def test_volumetric_dissolve_page_offers_directions_and_round_trips(qapp, settings_manager, qtbot):
    from rendering.gl_programs.volumetric_dissolve_options import (
        VOLUMETRIC_DIRECTION_CHOICES,
        VOLUMETRIC_PARTICLE_SIZE_RANGE,
    )

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    assert not hasattr(tab, "volumetric_dissolve_group")
    tab._activation_checkboxes["Volumetric Dissolve"].setChecked(True)
    tab._on_nav_selected("Volumetric Dissolve")
    assert [tab.direction_combo.itemText(i) for i in range(tab.direction_combo.count())] == list(
        VOLUMETRIC_DIRECTION_CHOICES)
    label, size = VOLUMETRIC_DIRECTION_CHOICES[-2], VOLUMETRIC_PARTICLE_SIZE_RANGE[0] + 1
    tab.direction_combo.setCurrentText(label)
    tab.volumetric_dissolve_size_spin.setValue(size)
    tab.volumetric_dissolve_mist_spin.setValue(0.2)
    tab.volumetric_dissolve_depth_spin.setValue(0.9)
    tab.volumetric_dissolve_antialiasing_combo.setCurrentText("2x")
    persisted = settings_manager.get("transitions", {})["volumetric_dissolve"]
    assert persisted == {"direction": label, "particle_size": size, "mist": 0.2, "depth": 0.9,
                         "antialiasing": "2x"}


def test_beam_settings_round_trip_through_the_tab(qapp, settings_manager, qtbot):
    """Beam's direction, colour, sparks and surface values save and load back."""
    from PySide6.QtGui import QColor

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    assert not hasattr(tab, "beam_group")
    tab._activation_checkboxes["Beam"].setChecked(True)
    tab._on_nav_selected("Beam")
    assert hasattr(tab, "beam_group")
    tab.direction_combo.setCurrentIndex(tab.direction_combo.findText("Diagonal BR-TL"))
    tab._beam_color = QColor(12, 200, 99)
    tab.beam_sparks_check.setChecked(not tab.beam_sparks_check.isChecked())
    sparks = tab.beam_sparks_check.isChecked()
    tab.beam_scorch_spin.setValue(0.15)
    tab.beam_cure_spin.setValue(0.9)
    tab._save_settings()

    beam = settings_manager.get('transitions', {})['beam']
    assert beam['direction'] == 'Diagonal BR-TL'
    assert beam['color'][:3] == [12, 200, 99] and beam['sparks'] is sparks
    assert beam['scorch'] == pytest.approx(0.15)
    assert beam['cure'] == pytest.approx(0.9)

    reloaded = TransitionsTab(settings_manager)
    qtbot.addWidget(reloaded)
    reloaded._on_nav_selected("Beam")
    assert reloaded._beam_color.getRgb()[:3] == (12, 200, 99)
    assert reloaded.beam_sparks_check.isChecked() is sparks
    assert reloaded.beam_scorch_spin.value() == pytest.approx(0.15)
    assert reloaded.direction_combo.currentText() == 'Diagonal BR-TL'
