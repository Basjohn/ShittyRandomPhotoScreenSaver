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
    VISUAL_CONTROLS,
    Choice,
    Colour,
    Custom,
    Direction,
    ScenePath,
    SceneCameraPosition,
    Range,
    Slider,
    Toggle,
    Triangle,
    iter_mode_settings,
    control_runtime_attr,
    control_runtime_value,
)

SPECS = iter_mode_settings()
DEFAULTS = require_canonical_default("widgets.spotify_visualizer")
BUCKET_STATES = require_canonical_default("ui.visualizer_bucket_states")


def test_every_registered_original_mode_has_one_typed_settings_spec():
    from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
    assert {spec.mode_id for spec in SPECS} == set(VISUALIZER_MODE_IDS)


@pytest.fixture
def settings_manager(qt_app, tmp_path):
    """Public test-owned storage; this module also runs without the global conftest."""
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests",
                              application=f"ModeSpec_{tmp_path.name}",
                              storage_base_dir=tmp_path)
    yield manager
    assert manager.flush(timeout=5.0)


@pytest.fixture
def open_gate(monkeypatch):
    """Open a gated mode's code gate for this test only (its body is what users get once it opens)."""
    import core.settings.visualizer_mode_registry as registry

    def open_(mode):
        if mode in registry._GATED_MODES:
            monkeypatch.setitem(registry._GATED_MODES, mode, lambda: True)
    return open_


def _different(control, value):
    if isinstance(control, Range):
        low, high = value
        changed = [control.low, control.high] if [low, high] != [control.low, control.high] else \
            [control.low, (control.low + control.high) / 2]
        return [int(round(v)) for v in changed] if control.integer else changed
    if isinstance(control, Triangle):
        return [round(value[1], 4), round(value[2], 4), round(value[0], 4)] if value[0] != value[1] else [0.2, 0.3, 0.5]
    if isinstance(control, ScenePath):
        path = [-.55, .2, .35, .65, -.45, -.3]
        return path if list(value) != path else [.4, -.3, -.2, -.6, .5, .7]
    if isinstance(control, SceneCameraPosition):
        return [.1, 0., 0.] if list(value) != [.1, 0., 0.] else [0., 0., 0.]
    if isinstance(control, Direction):
        return [((value[0] + 90.0 + 180.0) % 360.0) - 180.0,
                (control.height_low + control.height_high) / 2 if value[1] != (control.height_low + control.height_high) / 2
                else control.height_high]
    if isinstance(control, Slider):
        return control.high if value != control.high else control.low
    if isinstance(control, Toggle):
        return not value
    if isinstance(control, Choice):
        if control.indexed:
            return (value + 1) % len(control.choices)
        return next(choice for choice in control.choices if choice != value)
    return [255 - value[0], 255 - value[1], 255 - value[2], 200 if control.alpha else 255]


def _open_control_bucket(tab, spec, control):
    """Hydrate through the user's disclosure, preserving sectional lazy ownership."""
    if not control.bucket:
        return
    from PySide6.QtWidgets import QWidget
    from ui.widgets.continuous_border import BucketToggle
    container = getattr(tab, f"_{spec.prefix}_settings_container")
    bucket = container.findChild(QWidget, f"{spec.mode_id}_bucket_{control.bucket}")
    assert bucket is not None, control.key
    toggle = bucket.findChild(BucketToggle)
    assert toggle is not None, control.key
    toggle.setChecked(True)


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.mode_id)
def test_a_spec_is_a_registered_mode_and_owns_canonical_keys(spec):
    descriptor = get_visualizer_mode_descriptor(spec.mode_id)
    keys = list(spec.keys()) + [key for entry in spec.entries if isinstance(entry, Custom) for key in entry.keys]
    assert len(keys) == len(set(keys))
    for key in keys:
        assert key.startswith(descriptor.setting_prefixes), key
        assert key in DEFAULTS, f"{key} has no canonical default"
    for control in spec.controls:
        assert sum((control.logical, control.source, getattr(control, "authoring", False))) <= 1, control.key
        default = DEFAULTS[control.key]
        if isinstance(control, Colour):
            assert control.admit(default, default) == [int(c) for c in default][:4] + [255] * (4 - len(default))
        elif isinstance(control, ScenePath):
            # Legacy [around, height] values are accepted and projected into
            # six-coordinate scene paths; authored values are not fixed goldens.
            admitted = control.admit(default, default)
            assert len(admitted) == 6
            assert control.admit(admitted, admitted) == admitted, control.key
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
    if spec.mode_id == "bubble":
        from core.settings.bubble_gradient_semantics import CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION
        wild["bubble_gradient_semantics_version"] = CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION
    for control in spec.controls:
        if isinstance(control, Slider):
            wild[control.key] = control.high + 100.0
        elif isinstance(control, Colour):
            wild[control.key] = "not a colour"
        elif isinstance(control, Choice):
            wild[control.key] = DEFAULTS[control.key] if control.ingress_strict else "not a choice"
        elif isinstance(control, VISUAL_CONTROLS):
            wild[control.key] = "not a value"
        else:
            wild[control.key] = "on"
    model = SpotifyVisualizerSettings.from_mapping(wild, apply_preset_overlay=False)
    for control in spec.controls:
        value = getattr(model, control.key)
        if isinstance(control, Slider):
            assert value == (control.high if control.admission_high is None else control.admission_high)
        elif isinstance(control, (Colour, Choice, *VISUAL_CONTROLS)):
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
        if control.source:
            from widgets.spotify_visualizer.source_config_applier import resolve_mode_source_config

            assert not hasattr(logical, f"_{control.key}")
            assert not hasattr(presentation, f"_{control.key}")
            projected = resolve_mode_source_config(spec.mode_id, dict(DEFAULTS))
            suffix = control.key.removeprefix(f"{spec.mode_id}_")
            assert projected[f"spectrum_{suffix}"] == DEFAULTS[control.key]
            continue
        if getattr(control, "authoring", False):
            assert not hasattr(logical, f"_{control.key}") and not hasattr(presentation, f"_{control.key}")
            continue
        owner, other = (logical, presentation) if control.logical else (presentation, logical)
        attr = control_runtime_attr(control)
        assert getattr(owner, attr) == control_runtime_value(control, control.admit_runtime(DEFAULTS[control.key], DEFAULTS[control.key]))
        if getattr(control, "also_presentation", False):
            assert control.logical
            assert getattr(other, attr) == getattr(owner, attr), control.key
        else:
            assert not hasattr(other, attr), control.key
    parameters = spec_mode_parameters(presentation, spec.mode_id)
    assert set(parameters) == {control.key for control in spec.presentation_controls()}


def test_devcurve_production_applier_writes_each_logical_control_once():
    from core.settings.visualizer_mode_settings import require_mode_settings
    from widgets.spotify_visualizer.config_applier import (
        apply_logical_vis_mode_kwargs,
        apply_presentation_vis_mode_kwargs,
    )

    class Owner:
        def __init__(self):
            object.__setattr__(self, "writes", {})

        def __setattr__(self, name, value):
            self.writes[name] = self.writes.get(name, 0) + 1
            object.__setattr__(self, name, value)

    spec = require_mode_settings("devcurve")
    values = {control.key: _different(control, DEFAULTS[control.key]) for control in spec.controls}
    logical, presentation = Owner(), Owner()
    apply_logical_vis_mode_kwargs(logical, values)
    apply_presentation_vis_mode_kwargs(presentation, values)
    assert logical.writes == {f"_{key}": 1 for key in values}
    assert presentation.writes == {}
    for key, value in values.items():
        assert getattr(logical, f"_{key}") == value


def test_a_live_condition_cannot_reenable_a_permanently_unavailable_control(qt_app, settings_manager):
    from dataclasses import replace
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_mode_settings import require_mode_settings
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.media.spec_mode_builder import _bind_conditions, load_spec_mode_settings
    from ui.tabs.visualizers_tab import VisualizersTab

    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": "extruded_spectrum",
        "mode_activation": build_visualizer_mode_activation(["extruded_spectrum"]),
        "preset_extruded_spectrum": get_custom_preset_index("extruded_spectrum"),
    }})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page("extruded_spectrum")
        spec = require_mode_settings("extruded_spectrum")
        combined = replace(spec, entries=tuple(
            replace(entry, enabled_when=("extruded_spectrum_shadow_enabled", True))
            if getattr(entry, "key", "") == "extruded_spectrum_shadow_strength" else entry
            for entry in spec.entries
        ))
        _bind_conditions(tab, combined, tab._extruded_spectrum_rows)
        for enabled in (True, False, True):
            tab.extruded_spectrum_shadow_enabled.setChecked(enabled)
            assert not tab.extruded_spectrum_shadow_strength.isEnabled()
            load_spec_mode_settings(tab, "extruded_spectrum", {**DEFAULTS, "extruded_spectrum_shadow_enabled": enabled})
            assert not tab.extruded_spectrum_shadow_strength.isEnabled()
    finally:
        tab.deleteLater()
        qt_app.processEvents()


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.mode_id)
def test_the_settings_body_builds_saves_and_reloads_every_control(qt_app, settings_manager, spec, open_gate):
    from PySide6.QtGui import QColor

    from ui.tabs.media.spec_mode_builder import _current_value

    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.visualizers_tab import VisualizersTab

    mode = spec.mode_id
    open_gate(mode)
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
            _open_control_bucket(tab, spec, control)
            if isinstance(control, Colour):
                colour = getattr(tab, f"_{control.key}")
                wanted[control.key] = _different(control, [colour.red(), colour.green(), colour.blue()])
                getattr(tab, f"{control.key}_btn").color_changed.emit(QColor(*wanted[control.key]))
                continue
            widget = getattr(tab, control.key)
            if isinstance(control, VISUAL_CONTROLS):
                wanted[control.key] = _different(control, _current_value(tab, control))
                if isinstance(control, Range):
                    widget.setValue(control.positions(wanted[control.key]))
                else:
                    widget.setValue(wanted[control.key])
                wanted[control.key] = control.admit(wanted[control.key], wanted[control.key])
            elif isinstance(control, Slider):
                assert (widget.minimum(), widget.maximum()) == (round(control.low * control.scale),
                                                                round(control.high * control.scale))
                wanted[control.key] = _different(control, widget.value() / control.scale)
                widget.setValue(round(wanted[control.key] * control.scale))
            elif isinstance(control, Toggle):
                wanted[control.key] = _different(control, widget.isChecked())
                widget.setChecked(wanted[control.key])
            elif control.indexed:
                assert [widget.itemText(i) for i in range(widget.count())] == list(control.choices)
                wanted[control.key] = _different(control, widget.currentIndex())
                widget.setCurrentIndex(wanted[control.key])
            else:
                assert [widget.itemText(i) for i in range(widget.count())] == list(control.labels or control.choices)
                current = widget.currentData() if control.labels else widget.currentText()
                wanted[control.key] = _different(control, current)
                if control.labels:
                    assert [widget.itemData(i) for i in range(widget.count())] == list(control.choices)
                    widget.setCurrentIndex(widget.findData(wanted[control.key]))
                else:
                    widget.setCurrentText(wanted[control.key])
        if mode == "extruded_bubble":
            from core.settings.extruded_bubble_camera import admit_camera_parameters
            wanted['extruded_bubble_camera_position'] = list(admit_camera_parameters({**DEFAULTS, **wanted}))
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
            _open_control_bucket(reloaded, spec, control)
            if isinstance(control, Colour):
                colour = getattr(reloaded, f"_{control.key}")
                shown = [colour.red(), colour.green(), colour.blue(), colour.alpha()]
            elif isinstance(control, VISUAL_CONTROLS):
                shown = _current_value(reloaded, control)
            elif isinstance(control, Slider):
                shown = getattr(reloaded, control.key).value() / control.scale
            elif isinstance(control, Toggle):
                shown = getattr(reloaded, control.key).isChecked()
            elif control.indexed:
                shown = getattr(reloaded, control.key).currentIndex()
            else:
                widget = getattr(reloaded, control.key)
                shown = widget.currentData() if control.labels else widget.currentText()
            assert shown == pytest.approx(wanted[control.key]), control.key
    finally:
        reloaded.deleteLater()


def test_controls_read_and_persist_as_declared():
    percent = Slider("x_glow", "", 0.0, 2.0, percent=True)
    assert percent.text(150) == "150%"
    assert Slider("x_speed", "", 0.1, 1.0, suffix="x").text(42) == "0.42x"
    whole = Slider("x_shift", "", -50, 200, scale=1, decimals=0, integer=True)
    assert whole.admit(44.6, 0) == 45 and isinstance(whole.admit("12", 0), int)
    assert whole.admit(900, 0) == 200 and whole.coerce(7.0) == 7 and isinstance(whole.coerce(7.0), int)
    travel = Choice("x_travel", "", ("None", "Left", "Right"), indexed=True)
    assert travel.admit(2, 0) == 2
    # Positions written as numbers of any kind keep their meaning; others fall back to the default.
    assert travel.admit(1.0, 0) == 1 and travel.admit("1", 0) == 1 and travel.admit(5, 1) == 2
    assert travel.admit(-1, 1) == 0
    assert travel.admit("Left", 1) == 1 and travel.admit(True, 0) == 0 and travel.admit(1.5, 0) == 0
    assert travel.coerce(2.0) == 2


CONDITIONAL = [spec for spec in SPECS if any(control.when for control in spec.controls)]


@pytest.mark.parametrize("spec", CONDITIONAL, ids=lambda spec: spec.mode_id)
def test_conditional_controls_follow_their_condition_live_and_on_load(qt_app, settings_manager, spec, open_gate):
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.media.spec_mode_builder import load_spec_mode_settings
    from ui.tabs.visualizers_tab import VisualizersTab

    mode = spec.mode_id
    open_gate(mode)
    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": mode,
        "mode_activation": build_visualizer_mode_activation([mode]),
        f"preset_{mode}": get_custom_preset_index(mode)}})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page(mode)
        rows = getattr(tab, f"_{spec.prefix}_rows")
        def set_condition(condition, value):
            _open_control_bucket(tab, spec, condition)
            switch = getattr(tab, condition.key)
            if isinstance(condition, Toggle):
                switch.setChecked(value)
            elif condition.indexed:
                switch.setCurrentIndex(value)
            elif condition.labels:
                switch.setCurrentIndex(switch.findData(value))
            else:
                switch.setCurrentText(value)

        for control in (control for control in spec.controls if control.when):
            _open_control_bucket(tab, spec, control)
            terms = (control.when,) if isinstance(control.when[0], str) else control.when
            accepted = {key: value[0] if isinstance(value, tuple) else value for key, value in terms}
            for key, value in accepted.items():
                set_condition(spec.control(key), value)
            assert not rows[control.key].isHidden(), control.key
            for key, value in terms:
                condition = spec.control(key)
                if isinstance(condition, Toggle):
                    rejected = not accepted[key]
                else:
                    admitted = value if isinstance(value, tuple) else (value,)
                    rejected = next(option for option in condition.choices if option not in admitted)
                set_condition(condition, rejected)
                assert rows[control.key].isHidden(), control.key
                # Loading blocks signals; every AND predicate must still be applied.
                load_spec_mode_settings(tab, mode, {**DEFAULTS, **accepted, key: rejected})
                assert rows[control.key].isHidden(), control.key
                load_spec_mode_settings(tab, mode, {**DEFAULTS, **accepted})
                assert not rows[control.key].isHidden(), control.key
        for control in spec.controls:
            if isinstance(control, Toggle) and control.bucket and not control.label and not control.row_group:
                _open_control_bucket(tab, spec, control)
                assert rows[control.key] is getattr(tab, control.key), "a label-less toggle stands alone"
    finally:
        tab.deleteLater()
        qt_app.processEvents()



def test_neon_glass_roughness_first_slider_step_respects_shared_material_floor():
    import math
    from core.settings.visualizer_mode_settings import spec_control
    from rendering.gl_programs.scene3d import Scene3DMaterial, _material_roughness
    control=spec_control('shockwave_grid_glass_roughness')
    floor=_material_roughness(Scene3DMaterial((1.0,1.0,1.0),0.0,0.0))
    assert control.low == math.ceil(floor*control.scale)/control.scale
    assert control.admit(0.02,DEFAULTS[control.key]) == control.low
    model=SpotifyVisualizerSettings.from_mapping({control.key:0.02},apply_preset_overlay=False)
    assert getattr(model,control.key)==control.low
