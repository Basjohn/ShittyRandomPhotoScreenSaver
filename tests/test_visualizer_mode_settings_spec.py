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
    Gradient,
    ScenePath,
    SceneCameraPosition,
    Range,
    Slider,
    Toggle,
    Triangle,
    VisualEditor,
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
    if isinstance(control,VisualEditor):
        from copy import deepcopy
        changed=deepcopy(value)
        if control.validator.endswith(':admit_routing'):
            row=next(iter(changed.values()));row[0][0]=.25 if row[0][0]!=.25 else .75
        elif control.validator.endswith(':admit_ribbons'):
            changed[0]['height']=.35 if changed[0]['height']!=.35 else .7
        elif control.validator.endswith(':admit_palette'):
            changed['low'][0][1]=[.25,.1,.5]
        else:raise AssertionError('A structured editor needs a meaningful edit fixture')
        return changed
    if isinstance(control, Gradient):
        return [.1, .8, .7, .15] if list(value) != [.1, .8, .7, .15] else [.2, .6, .85, .3]
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
        elif isinstance(control, VisualEditor):
            wild[control.key] = DEFAULTS[control.key]  # strict structured ingress is tested separately below
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
