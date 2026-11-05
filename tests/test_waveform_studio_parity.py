"""The Waveform Studio has full parity with the Settings body it replaced.

Everything Settings' Waveform builder used to build (the spec buckets and their visual editors, the
per-mode technical / audio-analysis controls, the preset row) is derived here from the canonical
registries, never from a hand list, and must be editable in the Studio. The Settings body itself is
now only the preset row and the Studio launcher; values still load, save and switch presets through the
unchanged owners. Nothing here shows a window.
"""
from __future__ import annotations

import pytest

from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
from core.settings.visualizer_mode_settings import (
    Colour,
    Range,
    SceneCameraPosition,
    Slider,
    Toggle,
    Choice,
    VisualEditor,
    require_mode_settings,
)
from core.settings.visualizer_presets import get_custom_preset_index, get_preset_names
from ui.studio.schema import CHOICE, QUIET_PEAK, SCALAR, SWITCH
from ui.studio.waveform_adapter import WaveformStudioAdapter, build_schema

MODE = "waveform_ribbon"
SPEC = require_mode_settings(MODE)


def _general(path) -> tuple:
    return tuple("#" if isinstance(part, int) else part for part in path)


def _leaves(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item, (*path, key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _leaves(item, (*path, index))
    else:
        yield path


def _covered(leaf, prefixes) -> bool:
    general = _general(leaf)
    return any(general[:len(prefix)] == prefix for prefix in prefixes)


def _curated_configs():
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    for index in range(len(get_preset_names(MODE)) - 1):
        yield resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": index},
                                                    mode=MODE).resolved_config


def _uncovered(properties) -> set[str]:
    """Settings-built keys (spec bucket entries and technical controls) with no Studio property."""
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    roots = {prop.path[0] for prop in properties}
    built = {entry.key for entry in SPEC.entries if entry.bucket}
    built |= {_storage_key(MODE, defn) for defn in _control_defs_for_mode(MODE)}
    return built - roots


def test_parity_check_detects_a_missing_control_negative_control():
    properties = build_schema().properties
    assert _uncovered(properties) == set()
    for dropped in (f"{MODE}_ribbons", f"{MODE}_sensitivity", f"{MODE}_camera_fov"):
        assert _uncovered([p for p in properties if p.path[0] != dropped]) == {dropped}


def test_every_spec_control_of_the_retired_buckets_is_a_studio_property():
    schema = build_schema()
    by_root: dict[str, list] = {}
    for prop in schema.properties:
        by_root.setdefault(prop.path[0], []).append(prop)
    for entry in SPEC.entries:
        if not entry.bucket:
            continue
        assert entry.key in by_root, f"{entry.key} ({type(entry).__name__}) is not editable in the Studio"
        props = by_root[entry.key]
        if isinstance(entry, VisualEditor):
            continue                                  # leaf coverage below
        if isinstance(entry, SceneCameraPosition):
            assert sorted(p.path[1] for p in props) == [0, 1, 2], entry.key
            continue
        (prop,) = props
        expected = {Range: QUIET_PEAK, Toggle: SWITCH, Choice: CHOICE}
        kind = next((k for k in expected if isinstance(entry, k)), None)
        if kind is not None:
            assert prop.instrument == expected[kind], entry.key
        if isinstance(entry, Choice):
            assert tuple(prop.choice_values or prop.choices) == tuple(entry.choices), entry.key
        if isinstance(entry, (Slider, Range)):
            assert (prop.minimum, prop.maximum) == (entry.low, entry.high), entry.key
        if isinstance(entry, Colour):
            assert prop.instrument == "colour", entry.key
        # The Settings condition carries over (e.g. Field of View only for a perspective projection).
        when = entry.when
        terms = () if not when else ((when,) if isinstance(when[0], str) else when)
        assert {key for key, _v in terms} == {key for key, _a in prop.when}, entry.key


def test_every_leaf_of_the_visual_editors_is_editable_in_the_studio():
    """Ribbons, routing and palette: every leaf any curated preset (or the default) authors."""
    from core.settings.default_contract import require_canonical_default
    defaults = require_canonical_default("widgets.spotify_visualizer")
    schema = build_schema()
    editors = [entry for entry in SPEC.entries if isinstance(entry, VisualEditor) and entry.bucket]
    assert editors
    for entry in editors:
        prefixes = {_general(prop.path) for prop in schema.properties if prop.path[0] == entry.key}
        for config in (defaults, *_curated_configs()):
            value = entry.admit(config.get(entry.key, defaults[entry.key]), defaults[entry.key])
            for leaf in _leaves(value, (entry.key,)):
                assert _covered(leaf, prefixes), f"{_general(leaf)} has no Studio control"


def test_every_technical_audio_control_is_a_studio_property_with_the_same_range():
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    schema = build_schema()
    defs = _control_defs_for_mode(MODE)
    assert defs
    for defn in defs:
        prop = schema.find(_storage_key(MODE, defn))
        if defn.widget_kind == "checkbox":
            assert prop.instrument == SWITCH
        elif defn.widget_kind == "combo":
            assert prop.instrument == CHOICE
            assert tuple(prop.choice_values) == tuple(value for _label, value in defn.options)
        else:
            assert prop.instrument == SCALAR
            assert (prop.minimum, prop.maximum) == (float(defn.minimum), float(defn.maximum))
        # Admission is the technical owner's own (clamping, not the spec's).
        if prop.instrument == SCALAR:
            assert schema.admit(prop.id, float(defn.maximum) * 10, defn.minimum) == pytest.approx(defn.maximum)


# Each interactive part of Settings' preset row -> the Studio bridge slot doing the same job.
PRESET_ROW = {
    "_slider": ("selectPreset",),
    "_edit_btn": ("editPresetFile",),
    "_custom_action_btn": ("moveToCustom", "savePresetAs"),
    "_include_starting_view": ("setIncludeView",),
}


def test_every_interactive_part_of_the_preset_row_has_a_studio_action(qt_app):
    from PySide6.QtWidgets import QAbstractButton, QAbstractSlider
    from ui.studio.controller import StudioBridge
    from ui.tabs.media.preset_slider import VisualizerPresetSlider
    slider = VisualizerPresetSlider(MODE)
    try:
        interactive = slider.findChildren(QAbstractButton) + slider.findChildren(QAbstractSlider)
        named = {id(getattr(slider, attr)): attr for attr in PRESET_ROW if getattr(slider, attr, None) is not None}
        for widget in interactive:
            assert id(widget) in named, f"preset row control {widget.objectName() or widget!r} has no Studio action"
        for slots in PRESET_ROW.values():
            for slot in slots:
                assert callable(getattr(StudioBridge, slot, None)), slot
    finally:
        slider.deleteLater()


# --------------------------------------------------------------------- through the real Settings tab
@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="WaveformStudioParity",
                              storage_base_dir=tmp_path / "profile")
    yield manager
    assert manager.flush(timeout=5.)


class _Adapter(WaveformStudioAdapter):
    def create_renderer(self):
        class Quiet:
            def prepare(self, card, frame):
                return True

            def render(self, card, frame):
                pass

            def release(self):
                pass
        return Quiet()

    def recorded_clips(self):
        return ()


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

    def make_tab(preset_index=None):
        if preset_index is not None:          # None: a fresh tab on the settings as they are now
            settings_manager.set("widgets", {"spotify_visualizer": {
                "enabled": True, "visualizers_enabled": True, "mode": MODE,
                "mode_activation": build_visualizer_mode_activation([MODE]),
                f"preset_{MODE}": preset_index}})
        dialog = QDialog()
        tab = VisualizersTab(settings_manager)
        QVBoxLayout(dialog).addWidget(tab)
        tab._select_mode_page(MODE)
        built.append(dialog)
        return tab

    def open_on(preset_index=None):
        tab = make_tab(get_custom_preset_index(MODE) if preset_index is None else preset_index)
        surfaces = []

        def factory(controller):
            surface = OffscreenStudioSurface(controller, size=(960, 600), present_on_show=False)
            surfaces.append(surface)
            return surface
        controller = open_mode_studio(tab, MODE, adapter=_Adapter(), surface_factory=factory)
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


def _different(prop, value):
    if prop.instrument == SWITCH:
        return not value
    if prop.instrument == CHOICE:
        return next(choice for choice in prop.choices if choice != value)
    if prop.instrument == QUIET_PEAK:
        return None
    span = prop.maximum - prop.minimum
    target = prop.minimum + span * (0.25 if float(value) > prop.minimum + span / 2 else 0.75)
    return float(round(target)) if prop.integer else round(target, 2)


def test_studio_edits_save_and_reload_every_plain_control_through_settings(studio_on, settings_manager):
    """Replaces the retired buckets' build/save/reload check: each plain spec and technical control is
    edited through the Studio bridge, saved by Settings' owners, and a fresh Settings tab reloads it."""
    from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    tab, controller = studio_on()
    bridge = controller.bridge
    schema = build_schema()
    technical = {_storage_key(MODE, defn) for defn in _control_defs_for_mode(MODE)}
    plain = {entry.key for entry in SPEC.controls if entry.bucket and isinstance(entry, (Slider, Toggle, Choice))}
    wanted = {}
    for prop in schema.properties:
        if len(prop.path) != 1 or prop.id not in plain | technical or prop.view_pose:
            continue
        shown = bridge.values[prop.id]
        target = _different(prop, shown)
        bridge.commitValue(prop.id, 0, target)
        assert bridge.values[prop.id] == pytest.approx(target), prop.id
        wanted[prop.id] = (prop.choice_values[prop.choices.index(target)]
                           if prop.instrument == CHOICE and prop.choice_values else target)
    assert technical <= set(wanted) and len(wanted) > len(technical)
    controller.close()
    stored = _stored(settings_manager)
    for key, value in wanted.items():
        assert stored[key] == pytest.approx(value), key
    assert stored[f"preset_{MODE}"] == get_custom_preset_index(MODE)

    reloaded = studio_on.make_tab()
    body = collect_spec_mode_settings(reloaded, MODE)
    from ui.tabs.media.technical_controls import collect_per_mode_technical_controls
    technical_values: dict = {}
    collect_per_mode_technical_controls(reloaded, technical_values, current_mode=MODE)
    for key, value in wanted.items():
        shown = technical_values[key] if key in technical else body[key]
        assert shown == pytest.approx(value), key


def test_move_to_custom_and_the_camera_view_choice_work_from_the_studio(studio_on, settings_manager):
    tab, controller = studio_on(preset_index=0)
    bridge = controller.bridge
    slider = tab._get_visualizer_preset_slider(MODE)
    curated = bridge.presetLabel
    assert any(p["current"] and not p["custom"] for p in bridge.presets)
    before = _stored(settings_manager)[f"{MODE}_ribbons"]
    bridge.moveToCustom()
    custom = get_custom_preset_index(MODE)
    assert slider.preset_index() == custom and _stored(settings_manager)[f"preset_{MODE}"] == custom
    assert bridge.presetLabel != curated and any(p["current"] and p["custom"] for p in bridge.presets)
    assert _stored(settings_manager)[f"{MODE}_ribbons"] == before      # the curated values came along
    assert bridge.includeView in (0, 1)
    was = bridge.includeView
    bridge.setIncludeView(not was)
    assert bridge.includeView == int(not was) and slider._include_starting_view.isChecked() == (not was)
    bridge.moveToCustom()                                                # already Custom: nothing changes
    assert slider.preset_index() == custom


def test_conditional_rows_hide_as_in_settings(studio_on):
    tab, controller = studio_on()
    bridge = controller.bridge
    schema = build_schema()
    conditional = [prop for prop in schema.properties if prop.when]
    if not conditional:
        # The only one (Field of View while Perspective) left with the Projection control (5 Nov 2026).
        pytest.skip("Waveform currently has no conditional Studio rows")
    for prop in conditional:
        for key, accepted in prop.when:
            source = schema.find(key)
            rejected = next(choice for choice in source.choices if choice not in accepted) \
                if source.instrument == CHOICE else not accepted[0]
            bridge.commitValue(key, 0, rejected)
            assert bridge.conditionHidden.get(prop.id) is True, prop.id
            bridge.commitValue(key, 0, accepted[0])
            assert not bridge.conditionHidden.get(prop.id), prop.id


def test_the_settings_body_is_only_the_preset_row_and_the_studio_launcher(studio_on):
    from PySide6.QtWidgets import QAbstractButton, QAbstractSlider, QComboBox, QScrollBar, QWidget
    tab = studio_on.make_tab(get_custom_preset_index(MODE))
    body = getattr(tab, f"_{SPEC.prefix}_settings_container")
    slider = tab._get_visualizer_preset_slider(MODE)
    button = getattr(tab, f"_{SPEC.prefix}_studio_button")
    assert body.isAncestorOf(button) and not button.isHidden()
    for bucket in SPEC.buckets:
        assert body.findChild(QWidget, f"{MODE}_bucket_{bucket.key}") is None, bucket.key
    holder = body.findChild(QWidget, f"{MODE}_studio_owned_values")
    assert holder is not None and holder.isHidden()
    # Nothing interactive is reachable in the body except the preset row and the launcher.
    for widget in body.findChildren(QAbstractButton) + body.findChildren(QAbstractSlider) \
            + body.findChildren(QComboBox):
        if holder.isAncestorOf(widget) or widget is button or slider.isAncestorOf(widget):
            continue
        if widget.isHidden() or isinstance(widget, QScrollBar):
            continue
        pytest.fail(f"unexpected Settings control {widget.objectName() or widget!r}")
    # On a curated preset too, the launcher stays offered.
    slider._slider.setValue(0)
    assert not button.isHidden() and holder.isHidden()
