"""Conditional controls (``when`` / ``enabled_when``) are consistent and live in every mode, derived from the registry.

6 Nov: "Tilt Shift is unclickable". The Studio's one switch row was the defect (``test_studio_switch_rows_click``); these
check the rest of the class across every mode, with nothing shown: a condition must name a real control of its mode and
only values that control can hold (a mismatch hides a row forever), every Studio schema's conditions must do the same
against the stored representation, and in the real Settings tab (a dialog that is never shown) a conditional toggle is
live exactly while its condition holds.
"""
from __future__ import annotations

import pytest

from core.settings.visualizer_mode_settings import Choice, Toggle, iter_mode_settings, require_mode_settings

SPECS = [spec.mode_id for spec in iter_mode_settings()]


def _terms(condition):
    return (condition,) if condition and isinstance(condition[0], str) else tuple(condition or ())


def _values(value):
    return value if isinstance(value, tuple) else (value,)


def _holdable(control, value) -> bool:
    if isinstance(control, Toggle):
        return isinstance(value, bool)
    if isinstance(control, Choice):
        if control.indexed:
            return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(control.choices)
        return value in control.choices
    return True


@pytest.mark.parametrize("mode", SPECS)
def test_every_condition_names_a_control_of_its_mode_and_a_value_it_can_hold(mode):
    spec = require_mode_settings(mode)
    for control in spec.controls:
        for attribute in ("when", "enabled_when"):
            for key, value in _terms(getattr(control, attribute, ())):
                driver = spec.control(key)                         # KeyError: a condition on a control that does not exist
                assert all(_holdable(driver, v) for v in _values(value)), (control.key, attribute, key, value)


def test_every_studio_schema_condition_names_a_property_and_a_value_it_can_hold():
    from ui.studio.registry import create_adapter, studio_modes
    from ui.studio.schema import CHOICE, SWITCH
    checked = 0
    for entry in studio_modes():
        schema = create_adapter(entry.mode_id).schema()
        properties = {prop.id: prop for prop in schema.properties}
        for prop in schema.properties:
            for key, accepted in prop.when:
                driver = properties.get(key)
                assert driver is not None, (entry.mode_id, prop.id, key)
                if driver.instrument == SWITCH:
                    assert all(isinstance(v, bool) for v in accepted), (entry.mode_id, prop.id, key, accepted)
                elif driver.instrument == CHOICE:
                    stored = driver.choice_values or driver.choices
                    assert all(v in stored for v in accepted), (entry.mode_id, prop.id, key, accepted, stored)
                checked += 1
    assert checked, "the Studios declare conditional rows"


@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="ConditionalToggles",
                              storage_base_dir=tmp_path / "profile")
    yield manager
    assert manager.flush(timeout=5.)


def _conditional_toggles(mode):
    spec = require_mode_settings(mode)
    return [c for c in spec.controls if isinstance(c, Toggle) and c.when and c.bucket]


def _set(widget, control, value):
    if isinstance(control, Toggle):
        widget.setChecked(bool(value))
    else:
        widget.setCurrentIndex(value) if control.indexed else widget.setCurrentText(str(value))


@pytest.mark.parametrize("mode", [m for m in SPECS if _conditional_toggles(m) and m != "extruded_bubble"])
def test_settings_conditional_toggle_is_live_while_its_condition_holds_and_hidden_otherwise(
        qt_app, settings_manager, monkeypatch, mode):
    """The real Visualizers tab: shown and clickable exactly while the condition holds (negative control: not before)."""
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation, get_visualizer_mode_descriptor
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui import styled_popup
    from ui.tabs.visualizers_tab import VisualizersTab
    if get_visualizer_mode_descriptor(mode).settings_builder_module == "":
        pytest.skip("no Settings builder")
    monkeypatch.setattr(styled_popup.StyledPopup, "exec", lambda self: 0)
    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": mode,
        "mode_activation": build_visualizer_mode_activation([mode]),
        f"preset_{mode}": get_custom_preset_index(mode)}})
    dialog = QDialog()
    QVBoxLayout(dialog).addWidget(tab := VisualizersTab(settings_manager))
    tab._select_mode_page(mode)
    qt_app.processEvents()
    spec = require_mode_settings(mode)
    rows = getattr(tab, f"_{spec.prefix}_rows")
    if not rows:           # a Studio-owned body builds no control: its toggles are the Studio's (test_studio_switch_rows_click)
        from ui.studio.registry import has_studio
        assert has_studio(mode)
        pytest.skip("Studio-owned body")
    toggles = [c for c in _conditional_toggles(mode) if c.key in rows]
    assert toggles, mode
    for control in toggles:
        terms = _terms(control.when)
        widget, row = getattr(tab, control.key), rows[control.key]
        for key, value in (*terms, *_terms(control.enabled_when)):   # the condition holds
            _set(getattr(tab, key), spec.control(key), _values(value)[0])
        assert not row.isHidden() and widget.isEnabled(), control.key
        before = widget.isChecked()
        widget.click()
        assert widget.isChecked() is (not before), f"{control.key} does not toggle"
        widget.click()
        key, value = terms[0]                                      # it stops holding
        driver = spec.control(key)
        other = next(v for v in ((False, True) if isinstance(driver, Toggle) else driver.choices
                                 if not driver.indexed else range(len(driver.choices))) if v not in _values(value))
        _set(getattr(tab, key), driver, other)
        assert row.isHidden(), f"{control.key} stays shown while its condition fails"
    dialog.deleteLater()
    qt_app.processEvents()
