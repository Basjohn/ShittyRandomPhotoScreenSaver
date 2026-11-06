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
    Custom,
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
    customs = {key for entry in spec.entries if isinstance(entry, Custom) for key in entry.keys}
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

    def open_tab(tab, mode):
        surfaces = []

        def factory(controller):
            surface = OffscreenStudioSurface(controller, size=(960, 600), present_on_show=False)
            surfaces.append(surface)
            return surface
        controller = open_mode_studio(tab, mode, adapter=light_adapter(mode), surface_factory=factory)
        surfaces[0].pump()
        return controller

    def open_on(mode, preset_index=None):
        tab = make_tab(mode, get_custom_preset_index(mode) if preset_index is None else preset_index)
        return tab, open_tab(tab, mode)

    open_on.make_tab = make_tab
    open_on.open = open_tab
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


# ----------------------------------------------------------------------------------- the Settings body itself
# Before the flip, this file proved the Studios against the bodies users had (commit db7468ab): every row each body
# collected and every row its spec and hand-written conditions hid (Bubble's Swirl and Particles rules, now
# StudioProperty.when / when_any in the Bubble adapter). The bodies are now the preset row and the launcher.
@pytest.mark.parametrize("mode", MODES)
def test_the_settings_body_collects_exactly_the_body_keys(studio_on, mode):
    from ui.tabs.media.spec_mode_builder import body_keys, collect_spec_mode_settings
    tab = studio_on.make_tab(mode, get_custom_preset_index(mode))
    assert set(collect_spec_mode_settings(tab, mode)) == set(body_keys(mode))


@pytest.mark.parametrize("mode", MODES)
def test_the_settings_body_is_only_the_preset_row_and_the_launcher(studio_on, mode):
    from PySide6.QtWidgets import QAbstractButton, QAbstractSlider, QComboBox, QScrollBar, QWidget
    spec = require_mode_settings(mode)
    tab = studio_on.make_tab(mode, get_custom_preset_index(mode))
    body = getattr(tab, f"_{spec.prefix}_settings_container")
    slider = tab._get_visualizer_preset_slider(mode)
    button = getattr(tab, f"_{spec.prefix}_studio_button")
    assert body.isAncestorOf(button) and not button.isHidden()
    for bucket in spec.buckets:
        assert body.findChild(QWidget, f"{mode}_bucket_{bucket.key}") is None, bucket.key
    holder = body.findChild(QWidget, f"{mode}_studio_owned_values")
    assert holder is not None and holder.isHidden()
    # The page's shared Bar Appearance and Rainbow rows are value owners only: with the mode's other value
    # owners in the hidden holder when the mode owns them, else parked hidden; never on the page.
    tab._update_rainbow_visibility()
    for accessory in (tab._base_appearance_group, tab._rainbow_controls_container):
        assert holder.isAncestorOf(accessory) or accessory.isHidden()
        assert not accessory.isVisibleTo(tab) or holder.isAncestorOf(accessory)
    quality = getattr(tab, f"_{mode}_quality_controls", None)          # the 3D Detail row (Settings' 3D page owner)
    for widget in body.findChildren(QAbstractButton) + body.findChildren(QAbstractSlider) \
            + body.findChildren(QComboBox):
        if holder.isAncestorOf(widget) or widget is button or slider.isAncestorOf(widget):
            continue
        if widget.isHidden() or isinstance(widget, QScrollBar):
            continue
        if quality is not None and quality.isAncestorOf(widget):
            continue
        pytest.fail(f"unexpected Settings control {widget.objectName() or widget!r}")
    # On a curated preset too, the launcher stays offered.
    slider._slider.setValue(0)
    assert not button.isHidden() and holder.isHidden()


# ------------------------------------------------------------------------------------- the terrain brush
def _heightfield_keys(mode: str) -> set[str]:
    """Custom-row records whose canonical value is an authored heightfield (Neon Lake's terrain)."""
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.heightfield import normalize_heightfield
    defaults = require_canonical_default("widgets.spotify_visualizer")
    out = set()
    for entry in require_mode_settings(mode).entries:
        if isinstance(entry, Custom):
            for key in entry.keys:
                try:
                    normalize_heightfield(defaults[key])
                except (ValueError, KeyError):
                    continue
                out.add(key)
    return out


def test_every_authored_heightfield_is_painted_by_the_studio_brush():
    """The Studio's shared brush instrument is the heightfield's Studio home: every mode storing one declares the
    brush, its target is that record, and the record is a carried (``instrument_only``) Studio property. Derived from
    the registries; the negative control is a mode with no heightfield, which declares no brush."""
    painted = {}
    for mode in MODES:
        adapter = create_adapter(mode)
        keys = _heightfield_keys(mode)
        brush = adapter.capabilities().as_map()["brush"]
        assert brush == bool(keys), mode
        if keys:
            target = adapter.brush_target()
            assert target is not None and {target.key} == keys, mode
            prop = next(p for p in adapter.schema().properties if p.path[0] == target.key)
            assert prop.instrument_only
            painted[mode] = target.key
        else:
            assert adapter.brush_target() is None, mode
    assert painted, "a mode authors a heightfield"


def _ground_point(controller, uv):
    """The presented-frame pixel showing grid uv ``uv`` on the drawn ground (through the production camera)."""
    import numpy as np
    from rendering.gl_programs.heightfield import heightfield_basin
    from rendering.gl_programs.neon_terrain_surface import surface_points
    from ui.studio.shockwave_grid_adapter import terrain_view
    values = controller.evaluation_values()
    record = values["shockwave_grid_terrain"]
    world = surface_points(record["size"], record["heights"], heightfield_basin(record), np.array([uv[0]]),
                           np.array([uv[1]]), values["shockwave_grid_terrain_height"])[0]
    view = terrain_view(controller.last_frame, controller.presented_geometry())
    return view.item_point(tuple(world))


def _paint(controller, surface, uv, *, moves=24, per_frame=8):
    """One stroke from ``uv`` sweeping right across the ground; ``per_frame`` pointer moves between frame starts."""
    bridge = controller.bridge
    x, y = _ground_point(controller, uv)
    bridge.brushPress(x, y)
    for index in range(1, moves + 1):
        bridge.brushMove(x + 3.0 * index, y)
        if index % per_frame == 0:
            surface.pump()
    return x, y


def test_the_brush_lands_on_the_ground_the_production_camera_draws(studio_on):
    """A viewport point picks the grid uv the production camera shows there, on the drawn land (not the water plane
    behind it), and the footprint is drawn back round it; off the scene (the sky) picks nothing."""
    from ui.studio.shockwave_grid_adapter import pick_terrain, terrain_footprint
    import math
    _tab, controller = studio_on("shockwave_grid")
    size = 33                    # a test-owned terrain: low land with a tall hill in the middle
    hill = [round(0.3 + 0.6 * math.exp(-((x / (size - 1) - 0.5) ** 2 + (y / (size - 1) - 0.5) ** 2) / 0.02), 4)
            for y in range(size) for x in range(size)]
    controller.session.set(("shockwave_grid_terrain",), {"version": 1, "size": size, "heights": hill}, "Test terrain")
    controller.surface.pump(3)
    geometry = controller.presented_geometry()
    frame, values = controller.last_frame, controller.evaluation_values()
    record = values["shockwave_grid_terrain"]
    land = [(0.3, 0.2), (0.5, 0.3), (0.7, 0.15), (0.5, 0.42)]          # the near land and the hill's front slope
    for uv in land:
        point = _ground_point(controller, uv)
        picked = pick_terrain(frame, values, point, geometry)
        assert picked == pytest.approx(uv, abs=2e-3), uv
        rings = terrain_footprint(frame, values, picked, (0.1, 0.05), geometry)
        assert len(rings) == 2 and all(len(ring) > 10 for ring in rings)
        xs = [p[0] for p in rings[0]]
        assert min(xs) < point[0] < max(xs)
    assert pick_terrain(frame, values, (geometry[0][0] / 2, 2.0), geometry) is None
    # Negative control: the same point met with the flat water plane lands elsewhere on raised land.
    import numpy as np
    from ui.studio.shockwave_grid_adapter import _grid_uv, terrain_view
    from rendering.gl_programs.heightfield import heightfield_basin
    view = terrain_view(frame, geometry)
    point = _ground_point(controller, land[-1])
    fx, fy, fw, fh = view.field
    direction = np.asarray(view.ray((point[0] - fx) / fw, (point[1] - fy) / fh))
    eye = np.asarray(view.eye)
    hit = eye + (-eye[1] / direction[1]) * direction
    flat = _grid_uv(size, heightfield_basin(record), hit[0], hit[2])
    assert flat != pytest.approx(land[-1], abs=0.02)


def test_a_brush_stroke_saves_once_through_settings_and_reloads(studio_on, settings_manager):
    """A stroke painted on the Neon Lake preview is held in the session while the pointer moves (previewed at most
    once per frame start, nothing saved), then saved once on release by Settings' own owners; a fresh Settings tab
    and a new Studio both load exactly the painted record, and Undo restores the exact heightfield."""
    from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings
    from ui.studio.surface import OffscreenStudioSurface
    tab, controller = studio_on("shockwave_grid")
    surface = next(s for s in (controller.surface,) if isinstance(s, OffscreenStudioSurface))
    surface.pump(2)
    session, bridge = controller.session, controller.bridge
    key = "shockwave_grid_terrain"
    before = session.values[key]
    stored_before = _stored(settings_manager).get(key)
    bridge.setBrushActive(True)
    assert bridge.brushState["active"] is True
    bridge.setBrushValue("strength", 0.8)
    commits = session.commit_count
    _paint(controller, surface, (0.45, 0.35))
    brush = bridge.brush
    # Coalesced: 24 moves over 3 frames are at most 3 previews, and nothing is saved before the release.
    assert brush.pointer_events == 25 and 1 <= brush.previews <= 3
    assert session.commit_count == commits and session.gesture_active
    assert _stored(settings_manager).get(key) == stored_before
    bridge.brushRelease()
    painted = session.values[key]
    assert painted != before and session.commit_count == commits + 1 and not session.gesture_active
    assert session.undo_label.startswith("Paint Terrain")
    assert _stored(settings_manager)[key] == painted                      # through Settings' own save
    assert collect_spec_mode_settings(tab, "shockwave_grid")[key] == painted
    # A fresh Settings tab and a new Studio load exactly what was painted.
    controller.close()
    reloaded = studio_on.make_tab("shockwave_grid")
    assert collect_spec_mode_settings(reloaded, "shockwave_grid")[key] == painted
    reopened = studio_on.open(reloaded, "shockwave_grid")
    assert reopened.session.values[key] == painted
    # Undo restores the exact heightfield (the session's history is per Studio: paint, then undo, here).
    surface = reopened.surface
    surface.pump(2)
    reopened.bridge.setBrushActive(True)
    _paint(reopened, surface, (0.6, 0.3))
    reopened.bridge.brushRelease()
    assert reopened.session.values[key] != painted
    reopened.bridge.undo()
    assert reopened.session.values[key] == painted and _stored(settings_manager)[key] == painted


def test_a_stroke_on_the_sky_or_cancelled_saves_nothing_negative_control(studio_on, settings_manager):
    """The brush paints only the drawn ground: a stroke that never meets it, an inactive brush and Escape save
    nothing, so the save above is the stroke's own."""
    _tab, controller = studio_on("shockwave_grid")
    surface = controller.surface
    surface.pump(2)
    session, bridge = controller.session, controller.bridge
    key = "shockwave_grid_terrain"
    before, commits = session.values[key], session.commit_count
    _paint(controller, surface, (0.45, 0.35))                       # brush not active: ignored
    bridge.brushRelease()
    bridge.setBrushActive(True)
    bridge.brushPress(4.0, 4.0)                                     # the top-left corner: sky
    surface.pump()
    bridge.brushRelease()
    _paint(controller, surface, (0.45, 0.35))
    assert session.gesture_active and session.values[key] != before
    bridge.brushCancel()                                            # Escape
    bridge.brushRelease()
    assert session.values[key] == before and session.commit_count == commits
    assert _stored(settings_manager).get(key, before) == before


def test_bar_count_is_named_by_one_descriptor_fact_in_settings_and_the_studio():
    """Bar Count is the drawn bar count only where the mode draws bars (``draws_bars``); elsewhere it is the analysis
    resolution, named and explained as such. One definition feeds Settings' Technical group and the Studio."""
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    names: dict[bool, set] = {True: set(), False: set()}
    for mode in MODES:
        defn = next((d for d in _control_defs_for_mode(mode) if d.config_key == "bar_count"), None)
        assert defn is not None, f"{mode} must keep its Bar Count (it moves every mode's frame)"
        assert defn.tooltip, mode
        names[get_visualizer_mode_descriptor(mode).draws_bars].add((defn.label_text, defn.suffix_text, defn.tooltip))
        prop = _schema(mode).find(_storage_key(mode, defn))
        assert prop.label == defn.label_text.rstrip(":").strip() and prop.tooltip.startswith(defn.tooltip), mode
    assert len(names[True]) == 1 and len(names[False]) == 1 and names[True] != names[False]


@pytest.mark.parametrize("mode", [m for m in MODES if any(isinstance(e, Custom) and e.keys
                                                          for e in require_mode_settings(m).entries)])
def test_studio_edits_of_every_custom_row_save_and_reload_through_settings(studio_on, settings_manager, mode):
    """Each Custom row's record (shape editors, layers, smoothing, the terrain shaper...) edited through the Studio
    bridge is saved by Settings' owners and survives a fresh Settings tab's own save."""
    from core.settings.visualizer_mode_settings import Custom
    from ui.studio.session import read_path
    tab, controller = studio_on(mode)
    bridge, session = controller.bridge, controller.session
    hidden = bridge.conditionHidden
    customs = {key for e in require_mode_settings(mode).entries if isinstance(e, Custom) for key in e.keys}
    wanted = {}
    for prop in session.schema.properties:
        key = prop.path[0]
        if key not in customs or key in wanted or prop.instrument not in (SCALAR, SWITCH) or hidden.get(prop.id):
            continue
        if prop.instrument_only:
            continue
        before = read_path(session.values, prop.path)
        bridge.commitValue(prop.id, 0, _different(prop, before))
        after = read_path(session.values, prop.path)
        if after != before:
            wanted[key] = (prop.path, after)
    assert wanted, f"{mode}: no Custom row was edited"
    controller.close()
    reloaded = studio_on.make_tab(mode)
    reloaded._force_visualizer_preset_to_custom(mode)
    reloaded._save_settings_now()
    stored = _stored(settings_manager)
    for key, (path, value) in wanted.items():
        assert read_path(stored, path) == pytest.approx(value), path


def test_moving_a_bubble_gradient_endpoint_selects_custom_and_undo_restores_both(studio_on, settings_manager):
    """Settings' gradient rule, now the Bubble Studio's: an endpoint move selects the Custom recipe in the same
    undoable edit; named recipes keep the latent endpoints."""
    _tab, controller = studio_on("bubble")
    bridge, session = controller.bridge, controller.session
    direction, endpoints = "bubble_gradient_direction", "bubble_gradient_endpoints"
    named = next(p for p in session.schema.properties if p.id == direction)
    recipe = next(v for v in named.choice_values if v != "custom")
    bridge.commitValue(direction, 0, named.choices[named.choice_values.index(recipe)])
    before = list(session.values[endpoints])
    moved = round(0.2 if before[0] > 0.5 else 0.8, 2)
    bridge.commitValue(f"{endpoints}.0", 0, moved)
    assert session.values[direction] == "custom" and session.values[endpoints][0] == pytest.approx(moved)
    stored = _stored(settings_manager)
    assert stored[direction] == "custom" and stored[endpoints][0] == pytest.approx(moved)
    bridge.undo()
    assert session.values[direction] == recipe and session.values[endpoints] == pytest.approx(before)
