"""Conditional controls (``when`` / ``enabled_when``) are consistent and live in every mode, derived from the registry.

6 Nov: "Tilt Shift is unclickable". The Studio's one switch row was the defect (``test_studio_switch_rows_click``); these
check the rest of the class across every mode, with nothing shown: a condition must name a real control of its mode and
only values that control can hold (a mismatch hides a row forever), and every Studio schema's conditions must do the
same against the stored representation (every mode's controls are edited in its Studio).
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
            for key, accepted in (*prop.when, *prop.when_any):
                driver = properties.get(key)
                assert driver is not None, (entry.mode_id, prop.id, key)
                if driver.instrument == SWITCH:
                    assert all(isinstance(v, bool) for v in accepted), (entry.mode_id, prop.id, key, accepted)
                elif driver.instrument == CHOICE:
                    stored = driver.choice_values or driver.choices
                    assert all(v in stored for v in accepted), (entry.mode_id, prop.id, key, accepted, stored)
                checked += 1
    assert checked, "the Studios declare conditional rows"


