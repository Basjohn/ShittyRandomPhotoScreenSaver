"""Every transition's Settings spec holds against the canonical defaults, the registry, the real
Settings tab and request admission, so a new transition's spec is checked end to end the moment it
is added (``rendering/transition_settings.py``)."""
from __future__ import annotations

import random
import uuid

import pytest
from PySide6.QtWidgets import QApplication

from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from rendering.quick.transitions.parameter_resolution import (
    PARAMETERIZED_TRANSITION_IDS,
    resolve_parameterized_phase_c_inputs,
)
from rendering.transition_registry import get_transition_descriptor, iter_transition_descriptors
from rendering.transition_settings import (
    Choice,
    Colour,
    Number,
    Toggle,
    iter_transition_settings,
    widget_attr,
)

SPECS = iter_transition_settings()
CANONICAL = require_canonical_default("transitions")


def _different(control, value):
    """A valid value other than ``value`` for ``control``."""
    if isinstance(control, Number):
        return control.high if value != control.high else control.low
    if isinstance(control, Toggle):
        return not value
    if isinstance(control, Choice):
        return next(choice for choice in control.choices if choice != value)
    return [255 - value[0], 255 - value[1], 255 - value[2], 255]


def test_every_transition_with_a_settings_section_has_a_spec_and_every_spec_a_transition():
    sectioned = {d.setting_name: d.settings_section for d in iter_transition_descriptors()
                 if isinstance(CANONICAL.get(d.settings_section), dict)}
    assert {spec.name: spec.section for spec in SPECS} == sectioned
    for spec in SPECS:
        assert get_transition_descriptor(spec.name).settings_section == spec.section


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.section)
def test_a_spec_owns_exactly_its_defaults_section_and_admits_its_defaults(spec):
    defaults = CANONICAL[spec.section]
    assert len(spec.fields()) == len(set(spec.fields())), spec.fields()
    assert set(spec.fields()) == set(defaults), "declare every persisted field, and only those"
    for control in spec.all_controls:
        value = defaults[control.field]
        admitted = control.admit(value, value)
        if isinstance(control, Colour):
            assert list(admitted) == list(value[:3])
        else:
            assert admitted == value, (control.field, value)
        if isinstance(control, Number):
            assert control.low < control.high
            assert isinstance(value, int) is control.integer or not control.integer
    if spec.directions is not None:
        assert defaults["direction"] in spec.directions.choices
        codes = set(spec.directions.codes.values()) | set(spec.directions.aliases.values())
        assert set(spec.directions.random_pool) <= codes
    attrs = [widget_attr(spec.section, control) for control in spec.all_controls]
    assert len(attrs) == len(set(attrs))


@pytest.mark.parametrize("spec", [s for s in SPECS if s.section in PARAMETERIZED_TRANSITION_IDS and not s.custom],
                         ids=lambda spec: spec.section)
def test_request_admission_clamps_page_numbers_to_the_spec_ranges(spec):
    """A page number persisted out of range reaches the renderer clamped to the range the page offers."""
    numbers = [c for c in spec.controls if isinstance(c, Number)]
    for over, expect in ((1e6, "high"), (-1e6, "low")):
        settings = {spec.section: {c.field: over for c in numbers}}
        resolved = resolve_parameterized_phase_c_inputs(spec.section, settings,
                                                        random_source=random.Random(3)).parameter_dict()
        for control in numbers:
            assert resolved[control.field] == getattr(control, expect), (control.field, over)


@pytest.fixture
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.mark.parametrize("spec", [s for s in SPECS if s.has_page], ids=lambda spec: spec.section)
def test_the_tab_builds_saves_and_reloads_every_declared_control(qapp, qtbot, tmp_path, spec):
    from ui.tabs.transitions_tab import TransitionsTab

    manager = SettingsManager(organization="Test", application=f"SpecTab_{uuid.uuid4().hex}", storage_base_dir=tmp_path)
    manager.reset_to_defaults()
    tab = TransitionsTab(manager)
    qtbot.addWidget(tab)
    tab._activation_checkboxes[spec.name].setChecked(True)
    tab._on_nav_selected(spec.name)
    assert hasattr(tab, f"{spec.section}_group")

    wanted = {}
    for control in spec.all_controls:
        widget = getattr(tab, widget_attr(spec.section, control))
        if isinstance(control, Number):
            assert (widget.minimum(), widget.maximum()) == (control.low, control.high)
            wanted[control.field] = _different(control, widget.value())
            widget.setValue(wanted[control.field])
        elif isinstance(control, Toggle):
            wanted[control.field] = _different(control, widget.isChecked())
            widget.setChecked(wanted[control.field])
        elif isinstance(control, Choice):
            assert [widget.itemText(i) for i in range(widget.count())] == list(control.choices)
            wanted[control.field] = _different(control, widget.currentText())
            widget.setCurrentText(wanted[control.field])
        else:
            from PySide6.QtGui import QColor
            color = widget.color()
            wanted[control.field] = _different(control, [color.red(), color.green(), color.blue()])
            widget.set_color(QColor(*wanted[control.field][:3]))
    if spec.directions is not None:
        assert [tab.direction_combo.itemText(i) for i in range(tab.direction_combo.count())] == list(
            spec.directions.choices)
        wanted["direction"] = next(label for label in spec.directions.choices if label != tab.direction_combo.currentText())
        tab.direction_combo.setCurrentText(wanted["direction"])
    else:
        assert tab.direction_group.isHidden()
    tab._save_settings()

    persisted = manager.get("transitions", {})[spec.section]
    assert set(persisted) == set(CANONICAL[spec.section])
    for name, value in wanted.items():
        assert persisted[name] == pytest.approx(value), name

    reloaded = TransitionsTab(manager)
    qtbot.addWidget(reloaded)
    reloaded._on_nav_selected(spec.name)
    for control in spec.all_controls:
        widget = getattr(reloaded, widget_attr(spec.section, control))
        shown = {Number: lambda: widget.value(), Toggle: lambda: widget.isChecked(),
                 Choice: lambda: widget.currentText(),
                 Colour: lambda: [*widget.color().getRgb()[:3], 255]}[type(control)]()
        assert shown == pytest.approx(wanted[control.field]), control.field
    if spec.directions is not None:
        assert reloaded.direction_combo.currentText() == wanted["direction"]
