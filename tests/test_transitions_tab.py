"""Tests for TransitionsTab behaviour (UI-level transition settings)."""
import pytest
import uuid
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
    # Block Flip's page is lazy; selecting its pill builds it.
    tab._on_nav_selected("Block Puzzle Flip")
    tab.grid_rows_spin.setValue(7)
    tab.grid_cols_spin.setValue(9)
    tab._save_settings()

    block_flip = settings_manager.get("transitions", {})["block_flip"]
    assert block_flip["rows"] == 7
    assert block_flip["cols"] == 9
    assert "columns" not in block_flip
