"""Every visualizer mode's Studio has parity+ with the Settings body: what Settings builds and collects for the mode
is editable in its Studio, with the same ranges, choices and conditions, and saves through Settings' own owners.

Membership comes from the mode registry (every descriptor with a registered Studio adapter) and every control from
the canonical registries (the mode's settings spec, its technical control definitions, its shared families), never
from a hand list. The oracle is what the Settings body loads, collects and shows. Nothing here shows a window: the
Visualizers tab lives in a never-shown QDialog and the Studio on a hidden offscreen surface.
"""
from __future__ import annotations

from importlib import import_module

import pytest

from core.settings.visualizer_mode_registry import (
    build_visualizer_mode_activation,
    get_owned_mode_setting_keys,
    get_visualizer_mode_descriptor,
    iter_visualizer_mode_descriptors,
    mode_has_rainbow_controls,
)
from core.settings.visualizer_mode_settings import (
    Choice,
    Colour,
    Range,
    SceneCameraPosition,
    Slider,
    Toggle,
    VisualEditor,
    require_mode_settings,
)
from core.settings.visualizer_presets import get_custom_preset_index, get_preset_names
from ui.studio.registry import create_adapter, has_studio
from ui.studio.schema import CHOICE, QUIET_PEAK, SCALAR, SWITCH, condition_hidden

MODES = tuple(d.mode_id for d in iter_visualizer_mode_descriptors() if has_studio(d.mode_id))


def test_every_registered_visualizer_mode_has_a_studio():
    assert MODES == tuple(d.mode_id for d in iter_visualizer_mode_descriptors())


# ------------------------------------------------------------------------------------------------ the oracle
def _available(control) -> bool:
    """A control Settings shows disabled (its availability flag is off, e.g. Extruded Spectrum's cast shadow) has no
    Studio home until it becomes available."""
    availability = getattr(control, "availability", ())
    if not availability:
        return True
    module, _, name = availability[0].partition(":")
    return bool(getattr(import_module(module), name))


def _technical_keys(mode: str) -> set[str]:
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    return {_storage_key(mode, defn) for defn in _control_defs_for_mode(mode)}


def _family_keys(mode: str) -> set[str]:
    """The shared families Settings shows on the mode's page, outside its body: Rainbow wherever the mode owns it,
    and Bar Appearance (fill / border / border opacity) on a mode that draws bars."""
    keys = set()
    if mode_has_rainbow_controls(mode):
        keys |= set(get_owned_mode_setting_keys(mode, "rainbow").values())
    if get_visualizer_mode_descriptor(mode).draws_bars:
        keys |= set(get_owned_mode_setting_keys(mode, "shared_bar").values())
    return keys


def settings_keys(mode: str) -> set[str]:
    """Every value Settings edits for the mode: its body (spec controls and Custom rows), its technical (audio
    analysis) controls and the shared families on its page."""
    from ui.tabs.media.spec_mode_builder import body_keys
    spec = require_mode_settings(mode)
    unavailable = {control.key for control in spec.controls if not _available(control)}
    return (set(body_keys(mode)) - unavailable) | _technical_keys(mode) | _family_keys(mode)


def uncovered(mode: str, properties) -> set[str]:
    return settings_keys(mode) - {prop.path[0] for prop in properties}


def _schema(mode):
    return create_adapter(mode).schema()


@pytest.mark.parametrize("mode", MODES)
def test_every_settings_control_is_a_studio_property(mode):
    assert uncovered(mode, _schema(mode).properties) == set()


@pytest.mark.parametrize("mode", MODES)
def test_the_parity_check_detects_a_missing_property_negative_control(mode):
    from ui.tabs.media.spec_mode_builder import body_keys
    properties = _schema(mode).properties
    spec = require_mode_settings(mode)
    customs = {key for entry in spec.entries if hasattr(entry, "build") for key in entry.keys}
    dropped = [next(key for key in body_keys(mode) if key not in customs), *sorted(_technical_keys(mode))[:1],
               *sorted(customs)[:1], *sorted(_family_keys(mode))[:1]]
    for key in dropped:
        assert uncovered(mode, [p for p in properties if p.path[0] != key]) == {key}, key


# --------------------------------------------------------------------------- instruments, ranges, conditions
def _terms(when) -> set:
    if not when:
        return set()
    terms = (when,) if isinstance(when[0], str) else when
    return {(key, tuple(value) if isinstance(value, tuple) else (value,)) for key, value in terms}


@pytest.mark.parametrize("mode", MODES)
def test_every_spec_control_keeps_its_instrument_range_choices_and_condition(mode):
    schema = _schema(mode)
    by_root: dict[str, list] = {}
    for prop in schema.properties:
        by_root.setdefault(prop.path[0], []).append(prop)
    for control in require_mode_settings(mode).controls:
        props = by_root.get(control.key, ())
        if not props or isinstance(control, VisualEditor):
            continue                                   # coverage above; visual editors' leaves below
        if isinstance(control, SceneCameraPosition):
            assert sorted(p.path[1] for p in props) == [0, 1, 2], control.key
            continue
        whole = [p for p in props if len(p.path) == 1]
        if isinstance(control, (Slider, Range, Toggle, Choice)):
            (prop,) = whole
            expected = {Range: QUIET_PEAK, Toggle: SWITCH, Choice: CHOICE}
            kind = next((k for k in expected if isinstance(control, k)), None)
            if kind is not None:
                assert prop.instrument == expected[kind], control.key
            if isinstance(control, Choice):
                assert tuple(prop.choice_values or prop.choices) == tuple(control.choices), control.key
            if isinstance(control, (Slider, Range)):
                assert (prop.minimum, prop.maximum) == (control.low, control.high), control.key
        if isinstance(control, Colour):
            assert any(p.instrument == "colour" for p in whole), control.key
        # Settings' condition carries over to every Studio row of the control (the Studio may add Settings'
        # hand-written ones, proven against the body below).
        for prop in props:
            assert _terms(control.when) <= set(prop.when), (control.key, prop.id)


def _leaves(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item, (*path, key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _leaves(item, (*path, index))
    else:
        yield path


def _general(path) -> tuple:
    return tuple("#" if isinstance(part, int) else part for part in path)


def _curated_configs(mode):
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    for index in range(len(get_preset_names(mode)) - 1):
        yield resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": index},
                                                    mode=mode).resolved_config


@pytest.mark.parametrize("mode", [m for m in MODES if any(isinstance(c, VisualEditor)
                                                          for c in require_mode_settings(m).controls)])
def test_every_leaf_any_preset_authors_in_a_visual_editor_is_editable(mode):
    from core.settings.default_contract import require_canonical_default
    defaults = require_canonical_default("widgets.spotify_visualizer")
    schema = _schema(mode)
    for entry in require_mode_settings(mode).controls:
        if not isinstance(entry, VisualEditor) or not entry.bucket:
            continue
        prefixes = {_general(prop.path) for prop in schema.properties if prop.path[0] == entry.key}
        for config in (defaults, *_curated_configs(mode)):
            value = entry.admit(config.get(entry.key, defaults[entry.key]), defaults[entry.key])
            for leaf in _leaves(value, (entry.key,)):
                general = _general(leaf)
                assert any(general[:len(p)] == p for p in prefixes), f"{general} has no Studio control"


@pytest.mark.parametrize("mode", MODES)
def test_every_technical_control_keeps_its_instrument_range_and_admission(mode):
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    schema = _schema(mode)
    for defn in _control_defs_for_mode(mode):
        prop = schema.find(_storage_key(mode, defn))
        if defn.widget_kind == "checkbox":
            assert prop.instrument == SWITCH
        elif defn.widget_kind == "combo":
            assert prop.instrument == CHOICE
            assert tuple(prop.choice_values) == tuple(value for _label, value in defn.options)
        else:
            assert prop.instrument == SCALAR
            assert (prop.minimum, prop.maximum) == (float(defn.minimum), float(defn.maximum))
            assert schema.admit(prop.id, float(defn.maximum) * 10, defn.minimum) == pytest.approx(defn.maximum)
        assert prop.label == (defn.label_text or defn.checkbox_text).replace("\n", " ").rstrip(":").strip()


# Each interactive part of Settings' preset row -> the Studio bridge slot doing the same job.
PRESET_ROW = {
    "_slider": ("selectPreset",),
    "_custom_action_btn": ("moveToCustom", "savePresetAs"),
    "_include_starting_view": ("setIncludeView",),
}


@pytest.mark.parametrize("mode", MODES)
def test_every_interactive_part_of_the_preset_row_has_a_studio_action(qt_app, mode):
    from PySide6.QtWidgets import QAbstractButton, QAbstractSlider
    from ui.studio.controller import StudioBridge
    from ui.tabs.media.preset_slider import VisualizerPresetSlider
    slider = VisualizerPresetSlider(mode)
    try:
        interactive = slider.findChildren(QAbstractButton) + slider.findChildren(QAbstractSlider)
        named = {id(getattr(slider, attr)): attr for attr in PRESET_ROW if getattr(slider, attr, None) is not None}
        assert interactive
        for widget in interactive:
            assert id(widget) in named, f"preset row control {widget.objectName() or widget!r} has no Studio action"
        for slots in PRESET_ROW.values():
            for slot in slots:
                assert callable(getattr(StudioBridge, slot, None)), slot
    finally:
        slider.deleteLater()


# --------------------------------------------------------------------------------- through the real Settings tab
@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="VisualizerStudioParity",
                              storage_base_dir=tmp_path / "profile")
    yield manager
    assert manager.flush(timeout=5.)


class QuietRenderer:
    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        pass

    def release(self):
        pass


class NoJob:
    def cancel(self):
        pass


def light_adapter(mode: str):
    """The registered adapter without recorded clips, background workers or GL drawing."""
    from ui.studio.engine_answers import EngineAnswerEvaluator
    adapter = create_adapter(mode)
    adapter.recorded_clips = lambda: ()
    adapter.create_renderer = QuietRenderer
    probe = adapter.create_evaluator()
    probe.release()
    if isinstance(probe, EngineAnswerEvaluator):        # an engine-answer mode: no out-of-process worker here
        adapter.create_evaluator = lambda: type(probe)(loader=lambda *_a: NoJob())
    return adapter


@pytest.fixture
def studio_on(qt_app, settings_manager):
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioController
    from ui.studio.settings_link import open_mode_studio
    from ui.studio.surface import OffscreenStudioSurface
    from ui.tabs.visualizers_tab import VisualizersTab
    disable_per_call_gl_error_checking()
    built = []

    def make_tab(mode, preset_index=None):
        if preset_index is not None:          # None: a fresh tab on the settings as they are now
            settings_manager.set("widgets", {"spotify_visualizer": {
                "enabled": True, "visualizers_enabled": True, "mode": mode,
                "mode_activation": build_visualizer_mode_activation([mode]),
                f"preset_{mode}": preset_index}})
        dialog = QDialog()
        tab = VisualizersTab(settings_manager)
        QVBoxLayout(dialog).addWidget(tab)
        tab._select_mode_page(mode)
        built.append(dialog)
        return tab

    def open_on(mode, preset_index=None):
        tab = make_tab(mode, get_custom_preset_index(mode) if preset_index is None else preset_index)
        surfaces = []

        def factory(controller):
            surface = OffscreenStudioSurface(controller, size=(960, 600), present_on_show=False)
            surfaces.append(surface)
            return surface
        controller = open_mode_studio(tab, mode, adapter=light_adapter(mode), surface_factory=factory)
        surfaces[0].pump()
        return tab, controller

    open_on.make_tab = make_tab
    yield open_on
    active = StudioController.active()
    if active is not None:
        active.close()
    for dialog in built:
        dialog.deleteLater()
    qt_app.processEvents()


def _stored(settings_manager):
    return settings_manager.get("widgets")["spotify_visualizer"]


def _different(prop, value, control=None):
    if prop.instrument == SWITCH:
        return not value
    if prop.instrument == CHOICE:
        current = (prop.choices[prop.choice_values.index(value)]
                   if prop.choice_values and value in prop.choice_values else value)
        return next(choice for choice in prop.choices if choice != current)
    span = prop.maximum - prop.minimum
    target = prop.minimum + span * (0.25 if float(value) > prop.minimum + span / 2 else 0.75)
    if isinstance(control, Slider):                  # a value on the Settings slider's own step
        return round(target * control.scale) / control.scale
    return float(round(target)) if prop.integer else round(target, 2)


def _stored_value(prop, shown):
    if prop.instrument == CHOICE and prop.choice_values:
        return prop.choice_values[prop.choices.index(shown)]
    return shown


@pytest.mark.parametrize("mode", MODES)
def test_studio_edits_save_and_reload_every_plain_control_through_settings(studio_on, settings_manager, mode):
    """Each plain control Settings edits (spec slider / toggle / choice, technical, shared family) is edited through
    the Studio bridge, saved by Settings' owners and reloaded by a fresh Settings tab."""
    tab, controller = studio_on(mode)
    bridge = controller.bridge
    schema = controller.session.schema
    spec = require_mode_settings(mode)
    plain = {c.key for c in spec.controls if isinstance(c, (Slider, Toggle, Choice)) and _available(c)}
    wanted = {}
    for prop in schema.properties:
        key = prop.path[0]
        if len(prop.path) != 1 or prop.view_pose or key not in settings_keys(mode):
            continue
        if key not in plain | _technical_keys(mode) | _family_keys(mode):
            continue
        if prop.instrument not in (SCALAR, SWITCH, CHOICE):
            continue
        control = next((c for c in spec.controls if c.key == key), None)
        target = _different(prop, bridge.values[prop.id], control)
        bridge.commitValue(prop.id, 0, target)
        assert bridge.values[prop.id] == pytest.approx(target), prop.id
        wanted[key] = _stored_value(prop, target)
    assert wanted and _technical_keys(mode) <= set(wanted)
    controller.close()
    stored = _stored(settings_manager)
    for key, value in wanted.items():
        assert stored[key] == pytest.approx(value), key
    assert stored[f"preset_{mode}"] == get_custom_preset_index(mode)
    # A fresh Settings tab hydrates every one of them: its own save (which collects every owner) keeps them all.
    reloaded = studio_on.make_tab(mode)
    reloaded._force_visualizer_preset_to_custom(mode)
    reloaded._save_settings_now()
    stored = _stored(settings_manager)
    for key, value in wanted.items():
        assert stored[key] == pytest.approx(value), key


@pytest.mark.parametrize("mode", MODES)
def test_move_to_custom_and_the_camera_view_choice_work_from_the_studio(studio_on, settings_manager, mode):
    tab, controller = studio_on(mode, preset_index=0)
    bridge = controller.bridge
    slider = tab._get_visualizer_preset_slider(mode)
    curated = bridge.presetLabel
    assert any(p["current"] and not p["custom"] for p in bridge.presets)
    key = next(k for k in sorted(settings_keys(mode)) if k in _stored(settings_manager))
    before = _stored(settings_manager)[key]
    bridge.moveToCustom()
    custom = get_custom_preset_index(mode)
    assert slider.preset_index() == custom and _stored(settings_manager)[f"preset_{mode}"] == custom
    assert bridge.presetLabel != curated and any(p["current"] and p["custom"] for p in bridge.presets)
    assert _stored(settings_manager)[key] == before                      # the curated values came along
    if getattr(slider, "_include_starting_view", None) is not None:
        was = bridge.includeView
        bridge.setIncludeView(not was)
        assert bridge.includeView == int(not was) and slider._include_starting_view.isChecked() == (not was)
    bridge.moveToCustom()                                                # already Custom: nothing changes
    assert slider.preset_index() == custom


def _rejected(schema, key, accepted):
    source = schema.find(key)
    if source.instrument == CHOICE:
        shown = [c for c, v in zip(source.choices, source.choice_values or source.choices) if v not in accepted]
        return shown[0] if shown else None
    return not accepted[0]


def _accepted(schema, key, accepted):
    source = schema.find(key)
    if source.instrument == CHOICE and source.choice_values:
        return source.choices[source.choice_values.index(accepted[0])]
    return accepted[0]


@pytest.mark.parametrize("mode", MODES)
def test_conditional_rows_hide_and_show_live_in_the_studio(studio_on, mode):
    _tab, controller = studio_on(mode)
    bridge = controller.bridge
    schema = controller.session.schema
    conditional = [prop for prop in schema.properties if prop.when or prop.when_any]
    if not conditional:
        pytest.skip(f"{mode} has no conditional Studio rows")
    seen = set()
    for prop in conditional:
        for key, accepted in prop.when:
            if (key, accepted) in seen:
                continue
            seen.add((key, accepted))
            rejected = _rejected(schema, key, accepted)
            if rejected is None:
                continue
            bridge.commitValue(key, 0, rejected)
            assert bridge.conditionHidden.get(prop.id) is True, prop.id
            bridge.commitValue(key, 0, _accepted(schema, key, accepted))
        if prop.when_any:
            for key, accepted in prop.when_any:
                bridge.commitValue(key, 0, _rejected(schema, key, accepted))
            assert bridge.conditionHidden.get(prop.id) is True, prop.id
            key, accepted = prop.when_any[-1]
            bridge.commitValue(key, 0, _accepted(schema, key, accepted))
            assert not bridge.conditionHidden.get(prop.id) or any(
                not term_holds for term_holds in (bridge.values.get(k) in a for k, a in prop.when)), prop.id


# ------------------------------------------------------------ anchored on the Settings body users have today
@pytest.mark.parametrize("mode", MODES)
def test_the_settings_body_collects_exactly_the_body_keys(studio_on, mode):
    from ui.tabs.media.spec_mode_builder import body_keys, collect_spec_mode_settings
    tab = studio_on.make_tab(mode, get_custom_preset_index(mode))
    _open_every_bucket(tab, mode)
    assert set(collect_spec_mode_settings(tab, mode)) == set(body_keys(mode))


@pytest.mark.parametrize("mode", MODES)
def test_settings_shows_exactly_the_shared_families_the_oracle_names(studio_on, mode):
    tab = studio_on.make_tab(mode, get_custom_preset_index(mode))
    tab._update_rainbow_visibility()
    shown = set()
    if not tab._rainbow_controls_container.isHidden():
        shown |= set(get_owned_mode_setting_keys(mode, "rainbow").values())
    if not tab._base_appearance_group.isHidden():
        shown |= set(get_owned_mode_setting_keys(mode, "shared_bar").values())
    assert shown == _family_keys(mode)


def _open_every_bucket(tab, mode):
    from ui.widgets.continuous_border import BucketToggle
    body = getattr(tab, f"_{require_mode_settings(mode).prefix}_settings_container")
    adv = getattr(tab, f"_{require_mode_settings(mode).prefix}_adv_toggle", None)
    if adv is not None and not adv.isChecked():
        adv.setChecked(True)
    for toggle in body.findChildren(BucketToggle):
        if not toggle.isChecked():
            toggle.setChecked(True)


def _settings_hidden_rows(tab, mode) -> set[str]:
    rows = getattr(tab, f"_{require_mode_settings(mode).prefix}_rows")
    return {key for key, row in rows.items() if row.isHidden()}


def _studio_hidden_roots(schema, values) -> set[str]:
    hidden = condition_hidden(schema, values)
    roots: dict[str, list[bool]] = {}
    for prop in schema.properties:
        roots.setdefault(prop.path[0], []).append(bool(hidden.get(prop.id)))
    return {root for root, flags in roots.items() if all(flags)}


@pytest.mark.parametrize("mode", MODES)
def test_conditional_rows_hide_as_in_the_settings_body(studio_on, mode):
    """For every condition source (each toggle and choice the body edits) and each of its values, the rows the
    Settings body hides (its spec conditions and its hand-written ones) are exactly the rows the Studio hides."""
    from core.settings.default_contract import require_canonical_default
    from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings
    from ui.tabs.widgets_tab_media import _hydrate_visualizer_mode_body
    tab = studio_on.make_tab(mode, get_custom_preset_index(mode))
    _open_every_bucket(tab, mode)
    schema = _schema(mode)
    spec = require_mode_settings(mode)
    rows = getattr(tab, f"_{spec.prefix}_rows")
    compared = set(rows) & {prop.path[0] for prop in schema.properties}
    defaults = dict(require_canonical_default("widgets.spotify_visualizer"))
    sources = [c for c in spec.controls if isinstance(c, (Toggle, Choice)) and _available(c)]
    checked = 0
    for base in (defaults, next(iter(_curated_configs(mode)), defaults)):
        for source in sources:
            for value in ((False, True) if isinstance(source, Toggle) else source.choices):
                config = {**base, source.key: value}
                previous = tab._loading
                tab._loading = True
                try:
                    _hydrate_visualizer_mode_body(tab, mode, config)
                finally:
                    tab._loading = previous
                values = {**config, **collect_spec_mode_settings(tab, mode)}
                settings = _settings_hidden_rows(tab, mode) & compared
                studio = _studio_hidden_roots(schema, values) & compared
                assert settings == studio, (source.key, value, sorted(settings ^ studio))
                checked += 1
    assert checked
