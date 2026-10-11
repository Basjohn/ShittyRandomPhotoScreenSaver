"""Every spec'd Visualizer mode's Settings (``core/settings/visualizer_mode_settings.py``) hold against
the canonical defaults, the registry, the settings model, the appliers and the real Settings body, so
a mode added to the specs (or a control added to one) is checked end to end at once."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from core.settings.visualizer_mode_settings import (
    Choice,
    Colour,
    Custom,
    Slider,
    Toggle,
    iter_mode_settings,
)

SPECS = iter_mode_settings()
DEFAULTS = require_canonical_default("widgets.spotify_visualizer")
BUCKET_STATES = require_canonical_default("ui.visualizer_bucket_states")


def _different(control, value):
    if isinstance(control, Slider):
        return control.high if value != control.high else control.low
    if isinstance(control, Toggle):
        return not value
    if isinstance(control, Choice):
        return next(choice for choice in control.choices if choice != value)
    return [255 - value[0], 255 - value[1], 255 - value[2], 200 if control.alpha else 255]


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.mode_id)
def test_a_spec_is_a_registered_mode_and_owns_canonical_keys(spec):
    descriptor = get_visualizer_mode_descriptor(spec.mode_id)
    keys = list(spec.keys()) + [key for entry in spec.entries if isinstance(entry, Custom) for key in entry.keys]
    assert len(keys) == len(set(keys))
    for key in keys:
        assert key.startswith(descriptor.setting_prefixes), key
        assert key in DEFAULTS, f"{key} has no canonical default"
    for control in spec.controls:
        default = DEFAULTS[control.key]
        if isinstance(control, Colour):
            assert control.admit(default, default) == [int(c) for c in default][:4] + [255] * (4 - len(default))
        else:
            assert control.admit(default, default) == default, control.key
        if isinstance(control, Slider):
            assert control.low < control.high
    buckets = {bucket.key for bucket in spec.buckets}
    assert {entry.bucket for entry in spec.entries if entry.bucket} <= buckets
    for bucket in buckets:
        assert f"{spec.mode_id}:{bucket}" in BUCKET_STATES


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.mode_id)
def test_the_model_clamps_repairs_and_round_trips_every_control(spec):
    wild = {}
    for control in spec.controls:
        if isinstance(control, Slider):
            wild[control.key] = control.high + 100.0
        elif isinstance(control, Colour):
            wild[control.key] = "not a colour"
        elif isinstance(control, Choice):
            wild[control.key] = "not a choice"
        else:
            wild[control.key] = "on"
    model = SpotifyVisualizerSettings.from_mapping(wild, apply_preset_overlay=False)
    for control in spec.controls:
        value = getattr(model, control.key)
        if isinstance(control, Slider):
            assert value == control.high
        elif isinstance(control, (Colour, Choice)):
            assert value == control.admit(DEFAULTS[control.key], DEFAULTS[control.key])
        else:
            assert value is True
    saved = model.to_dict()
    for control in spec.controls:
        assert saved[f"widgets.spotify_visualizer.{control.key}"] == getattr(model, control.key)


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.mode_id)
def test_the_appliers_store_each_control_on_its_owner_and_the_renderer_gets_the_presentation_ones(spec):
    from widgets.spotify_visualizer.config_applier import (
        _apply_spec_controls,
        spec_mode_parameters,
    )

    logical, presentation = SimpleNamespace(), SimpleNamespace()
    _apply_spec_controls(logical, dict(DEFAULTS), logical=True)
    _apply_spec_controls(presentation, dict(DEFAULTS), logical=False)
    for control in spec.controls:
        owner, other = (logical, presentation) if control.logical else (presentation, logical)
        assert hasattr(owner, f"_{control.key}") and not hasattr(other, f"_{control.key}"), control.key
    parameters = spec_mode_parameters(presentation, spec.mode_id)
    assert set(parameters) == {control.key for control in spec.presentation_controls()}


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.mode_id)
def test_the_settings_body_builds_saves_and_reloads_every_control(qt_app, settings_manager, spec):
    from PySide6.QtGui import QColor

    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.visualizers_tab import VisualizersTab

    mode = spec.mode_id
    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": mode,
        "mode_activation": build_visualizer_mode_activation([mode]),
        f"preset_{mode}": get_custom_preset_index(mode)}})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page(mode)
        wanted = {}
        for control in spec.controls:
            if not control.bucket:
                continue
            if isinstance(control, Colour):
                colour = getattr(tab, f"_{control.key}")
                wanted[control.key] = _different(control, [colour.red(), colour.green(), colour.blue()])
                getattr(tab, f"{control.key}_btn").color_changed.emit(QColor(*wanted[control.key]))
                continue
            widget = getattr(tab, control.key)
            if isinstance(control, Slider):
                assert (widget.minimum(), widget.maximum()) == (round(control.low * control.scale),
                                                                round(control.high * control.scale))
                wanted[control.key] = _different(control, widget.value() / control.scale)
                widget.setValue(round(wanted[control.key] * control.scale))
            elif isinstance(control, Toggle):
                wanted[control.key] = _different(control, widget.isChecked())
                widget.setChecked(wanted[control.key])
            else:
                assert [widget.itemText(i) for i in range(widget.count())] == list(control.choices)
                wanted[control.key] = _different(control, widget.currentText())
                widget.setCurrentText(wanted[control.key])
        tab._save_settings_now()   # the edits' own saves are debounced
        section = settings_manager.get("widgets", {})["spotify_visualizer"]
        for key, value in wanted.items():
            assert section[key] == pytest.approx(value), key
    finally:
        tab.deleteLater()
        qt_app.processEvents()

    reloaded = VisualizersTab(settings_manager)
    try:
        reloaded._select_mode_page(mode)
        for control in spec.controls:
            if not control.bucket:
                continue
            if isinstance(control, Colour):
                colour = getattr(reloaded, f"_{control.key}")
                shown = [colour.red(), colour.green(), colour.blue(), colour.alpha()]
            elif isinstance(control, Slider):
                shown = getattr(reloaded, control.key).value() / control.scale
            elif isinstance(control, Toggle):
                shown = getattr(reloaded, control.key).isChecked()
            else:
                shown = getattr(reloaded, control.key).currentText()
            assert shown == pytest.approx(wanted[control.key]), control.key
    finally:
        reloaded.deleteLater()
