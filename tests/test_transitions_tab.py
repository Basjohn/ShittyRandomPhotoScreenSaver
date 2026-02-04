"""Tests for TransitionsTab behaviour (UI-level transition settings)."""
import pytest
import uuid
from PySide6.QtWidgets import QApplication

from ui.tabs.transitions_tab import TransitionsTab
from core.settings.settings_manager import SettingsManager


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def settings_manager():
    # Use a dedicated org/app so we don't pollute real settings
    mgr = SettingsManager(organization="Test", application=f"TransitionsTabTest_{uuid.uuid4().hex}")
    mgr.reset_to_defaults()
    return mgr


def test_slide_and_wipe_directions_are_independent(qapp, settings_manager, qtbot):
    """Changing Slide direction should not overwrite Wipe direction and vice versa."""
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)

    # Start from defaults: both should be Random according to spec
    transitions_cfg = settings_manager.get('transitions', {}) or {}
    slide_cfg = transitions_cfg.get('slide', {}) if isinstance(transitions_cfg.get('slide', {}), dict) else {}
    wipe_cfg = transitions_cfg.get('wipe', {}) if isinstance(transitions_cfg.get('wipe', {}), dict) else {}

    assert slide_cfg.get('direction', 'Random') == 'Random'
    assert wipe_cfg.get('direction', 'Random') == 'Random'

    # Set Slide to Left to Right, keep Wipe at Random
    tab.transition_combo.setCurrentText("Slide")
    tab._update_specific_settings()
    idx = tab.direction_combo.findText("Left to Right")
    assert idx >= 0
    tab.direction_combo.setCurrentIndex(idx)
    tab._save_settings()

    transitions_cfg = settings_manager.get('transitions', {}) or {}
    slide_cfg = transitions_cfg.get('slide', {}) if isinstance(transitions_cfg.get('slide', {}), dict) else {}
    wipe_cfg = transitions_cfg.get('wipe', {}) if isinstance(transitions_cfg.get('wipe', {}), dict) else {}

    assert slide_cfg.get('direction') == 'Left to Right'
    # Wipe direction should remain Random and not be forced to Left to Right
    assert wipe_cfg.get('direction', 'Random') == 'Random'

    # Now set Wipe to Top to Bottom, ensuring Slide stays as previously chosen
    tab.transition_combo.setCurrentText("Wipe")
    tab._update_specific_settings()
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
    """Verify defaults match spec: type=Ripple, Slide/Wipe directions Random."""
    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)

    transitions_cfg = settings_manager.get('transitions', {}) or {}
    assert transitions_cfg.get('type') == 'Ripple'
    assert transitions_cfg.get('duration_ms') == 7200

    slide_cfg = transitions_cfg.get('slide', {}) if isinstance(transitions_cfg.get('slide', {}), dict) else {}
    wipe_cfg = transitions_cfg.get('wipe', {}) if isinstance(transitions_cfg.get('wipe', {}), dict) else {}

    assert slide_cfg.get('direction', 'Random') == 'Random'
    assert wipe_cfg.get('direction', 'Random') == 'Random'
