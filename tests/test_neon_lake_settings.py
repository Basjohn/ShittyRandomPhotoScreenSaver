"""Terrain persistence, configuration packing, source ownership and real lazy Settings."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.models import SpotifyVisualizerSettings
from rendering.gl_programs.heightfield import normalize_heightfield


FIELD = {"version": 1, "size": 3, "heights": [0.0, 0.25, 0.5, 0.0, 0.0, 0.75, 0.1, 0.0, 1.0]}


def _packed_host(mode='shockwave_grid'):
    from widgets.spotify_visualizer.presentation_state import VisualizerPresentationState
    return VisualizerPresentationState(SimpleNamespace(mode_id=mode))


def test_old_profiles_get_default_terrain_and_explicit_terrain_is_strict_and_detached():
    from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping
    from core.settings.visualizer_presets import build_normalized_custom_snapshot, normalize_visualizer_custom_snapshot_cache

    old = {"mode": "shockwave_grid", "shockwave_grid_allow_overflow": True,
           "shockwave_grid_shape_nodes": [[0.0, 0.31], [1.0, 0.68]],
           "shockwave_grid_wave_amplitude": 0.61, "shockwave_grid_profile_floor": 0.22,
           "shockwave_grid_drop_speed": 1.77, "shockwave_grid_input_gain": 0.81,
           "shockwave_grid_manual_floor": 0.17, "shockwave_grid_mirrored": False}
    normalized = normalize_visualizer_section_mapping(old, apply_preset_overlay=False)
    canonical = require_canonical_default("widgets.spotify_visualizer.shockwave_grid_terrain")
    assert normalized["shockwave_grid_terrain"] == canonical
    assert "shockwave_grid_allow_overflow" not in normalized
    for key, value in old.items():
        if key != "shockwave_grid_allow_overflow":
            assert normalized[key] == value
    cached = normalize_visualizer_custom_snapshot_cache({"shockwave_grid": old})["shockwave_grid"]
    assert cached["shockwave_grid_terrain"] == canonical
    assert cached["shockwave_grid_shape_nodes"] == old["shockwave_grid_shape_nodes"]
    assert "shockwave_grid_allow_overflow" not in cached
    authored = deepcopy(FIELD)
    model = SpotifyVisualizerSettings.from_mapping({**old, "shockwave_grid_terrain": authored}, apply_preset_overlay=False)
    authored["heights"][0] = 0.91
    saved = model.to_dict()["widgets.spotify_visualizer.shockwave_grid_terrain"]
    assert saved == FIELD
    saved["heights"][0] = 0.99
    assert model.shockwave_grid_terrain == FIELD
    snapshot = build_normalized_custom_snapshot("shockwave_grid", {**old, "shockwave_grid_terrain": FIELD})
    assert snapshot["shockwave_grid_terrain"] == FIELD
    for bad in (None, {"version": 1, "size": 3, "heights": [0.0] * 8}):
        with pytest.raises(ValueError, match="heightfield"):
            SpotifyVisualizerSettings.from_mapping({"shockwave_grid_terrain": bad}, apply_preset_overlay=False)


def test_terrain_is_packed_on_configuration_and_reused_by_identity_in_every_capture(monkeypatch):
    from rendering.gl_programs import heightfield
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs, shockwave_grid_parameters
    from widgets.spotify_visualizer.render_state import FrozenFields, freeze_render_fields

    calls = []
    original = heightfield.heightfield_surface_bytes
    monkeypatch.setattr(heightfield, "heightfield_surface_bytes", lambda data: (calls.append(data["size"]), original(data))[1])
    owner = _packed_host()
    defaults = require_canonical_default("widgets.spotify_visualizer")
    apply_presentation_vis_mode_kwargs(owner, defaults)
    owner._scene3d_detail = "High"
    assert len(calls) == 1
    apply_presentation_vis_mode_kwargs(owner, {"shockwave_grid_terrain": FIELD})
    frozen = owner._shockwave_grid_terrain
    assert isinstance(frozen, FrozenFields)
    assert dict(frozen) == {"size": 3, "data": original(FIELD), "maximum": 1.0}
    for _ in range(4):
        apply_presentation_vis_mode_kwargs(owner, {**defaults, "shockwave_grid_terrain": deepcopy(FIELD)})
        assert owner._shockwave_grid_terrain is frozen
    for _ in range(20):
        parameters = shockwave_grid_parameters(owner)
        assert parameters["shockwave_grid_terrain"] is frozen
        assert freeze_render_fields(parameters)["shockwave_grid_terrain"] is frozen
    configured_sizes = [defaults["shockwave_grid_terrain"]["size"], 3]
    assert calls == configured_sizes  # only the two configure edges; never a frame
    apply_presentation_vis_mode_kwargs(owner, {"shockwave_grid_sky_strength": 0.43})
    assert owner._shockwave_grid_terrain is frozen and calls == configured_sizes
    with pytest.raises(ValueError):
        apply_presentation_vis_mode_kwargs(owner, {"shockwave_grid_terrain": {"version": 1, "size": 2, "heights": [float("nan")] * 4}})


def test_response_controls_project_to_existing_source_without_unused_private_attributes():
    from widgets.spotify_visualizer.config_applier import apply_logical_vis_mode_kwargs, apply_presentation_vis_mode_kwargs
    from widgets.spotify_visualizer.source_config_applier import resolve_mode_source_config

    values = {"shockwave_grid_wave_amplitude": 0.71, "shockwave_grid_profile_floor": 0.23, "shockwave_grid_drop_speed": 2.31}
    projected = resolve_mode_source_config("shockwave_grid", values)
    logical, presentation = SimpleNamespace(), SimpleNamespace()
    apply_logical_vis_mode_kwargs(logical, projected)
    apply_presentation_vis_mode_kwargs(presentation, projected)
    for key, value in values.items():
        assert projected[key.replace("shockwave_grid_", "spectrum_")] == value
        assert not hasattr(logical, f"_{key}") and not hasattr(presentation, f"_{key}")


def test_real_terrain_body_silent_roundtrip_reset_and_stroke_save_batch(qt_app, settings_manager, monkeypatch):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings
    from ui.tabs.visualizers_tab import VisualizersTab

    pose = {"shockwave_grid_turn": 0.18, "shockwave_grid_tilt": 0.53,
            "shockwave_grid_scene_scale": 1.75, "shockwave_grid_scene_pan_x": -0.41, "shockwave_grid_scene_pan_y": 0.23}
    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": "shockwave_grid",
        "mode_activation": build_visualizer_mode_activation(["shockwave_grid"]),
        "preset_shockwave_grid": get_custom_preset_index("shockwave_grid"), **pose,
        "shockwave_grid_terrain": FIELD,
    }})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page("shockwave_grid")
        calls = []
        monkeypatch.setattr(tab, "_save_settings", lambda: calls.append("save"))
        monkeypatch.setattr(tab, "_force_visualizer_preset_to_custom", lambda mode: calls.append(mode))
        load_spec_mode_settings(tab, "shockwave_grid", {
            **require_canonical_default("widgets.spotify_visualizer"), "shockwave_grid_terrain": FIELD,
            "shockwave_grid_sky_enabled": False,
        })
        assert calls == []
        assert not tab.shockwave_grid_sky_color_btn.isEnabled() and not tab.shockwave_grid_sky_strength.isEnabled()
        payload = collect_spec_mode_settings(tab, "shockwave_grid")
        assert payload["shockwave_grid_terrain"] == FIELD
        assert not set(pose) & set(payload) and "shockwave_grid_allow_overflow" not in payload
        for key in pose:
            assert not hasattr(tab, key)
        editor = tab.shockwave_grid_terrain_editor
        canvas = editor.canvas
        canvas.resize(500, 300)
        rect = canvas.field_rect()
        point = QPoint(round(rect.center().x()), round(rect.center().y()))
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=point)
        assert calls == []
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=point)
        assert calls == ["shockwave_grid", "save"]
        edited = collect_spec_mode_settings(tab, "shockwave_grid")["shockwave_grid_terrain"]
        assert edited != FIELD and normalize_heightfield(edited) == edited
        calls.clear()
        load_spec_mode_settings(tab, "shockwave_grid", {**payload, "shockwave_grid_terrain": edited})
        assert calls == [] and editor.get_heightfield() == edited
        editor.reset_button.click()
        assert calls == ["shockwave_grid", "save"]
        assert editor.get_heightfield() == require_canonical_default("widgets.spotify_visualizer.shockwave_grid_terrain")
        # Real Settings save/reopen retains terrain and independent internal view state.
        editor.set_heightfield(edited)
        tab._save_settings_now()
        stored = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert stored["shockwave_grid_terrain"] == edited
        assert all(stored[key] == value for key, value in pose.items())
    finally:
        tab.deleteLater()
        qt_app.processEvents()
    reopened = VisualizersTab(settings_manager)
    try:
        reopened._select_mode_page("shockwave_grid")
        assert reopened.shockwave_grid_terrain_editor.get_heightfield() == edited
    finally:
        reopened.deleteLater()
        qt_app.processEvents()


def test_test_owned_preset_cycle_preserves_custom_terrain_old_frequency_profile_and_view_pose(monkeypatch):
    from core.settings import visualizer_presets as presets
    from core.settings.visualizer_mode_registry import get_visualizer_view_pose_keys

    art = {"shockwave_grid_terrain": FIELD, "shockwave_grid_glow": 0.23}
    catalog = [presets.VisualizerPreset("Test Art", "Test-owned", art), presets.VisualizerPreset("Custom", "", {}, True)]
    monkeypatch.setattr(presets, "get_presets", lambda _mode: catalog)
    pose = {"shockwave_grid_turn": 0.2, "shockwave_grid_tilt": 0.3, "shockwave_grid_scene_scale": 1.6,
            "shockwave_grid_scene_pan_x": -0.4, "shockwave_grid_scene_pan_y": 0.7}
    live = {**require_canonical_default("widgets.spotify_visualizer"), **pose,
            "mode": "shockwave_grid", "shockwave_grid_terrain": {"version": 1, "size": 2, "heights": [0.0, 0.1, 0.0, 0.2]},
            "shockwave_grid_wave_amplitude": 0.72, "shockwave_grid_input_gain": 0.83,
            "shockwave_grid_shape_nodes": [[0.0, 0.31], [1.0, 0.68]], "position": "Custom"}
    assert set(pose) <= set(get_visualizer_view_pose_keys("shockwave_grid"))
    custom = presets.build_normalized_custom_snapshot("shockwave_grid", live)
    assert not set(pose) & set(custom)
    resolved = presets.apply_preset_to_config("shockwave_grid", 0, live)
    assert resolved["shockwave_grid_terrain"] == FIELD
    assert all(resolved[key] == value for key, value in pose.items())
    assert presets.restore_visualizer_snapshot("shockwave_grid", resolved, custom)
    assert resolved["shockwave_grid_terrain"] == live["shockwave_grid_terrain"]
    assert resolved["shockwave_grid_shape_nodes"] == live["shockwave_grid_shape_nodes"]
    assert resolved["shockwave_grid_input_gain"] == 0.83 and resolved["position"] == "Custom"
    assert all(resolved[key] == value for key, value in pose.items())


def test_wire_display_real_body_roundtrip_and_default(qt_app, settings_manager, monkeypatch):
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_mode_settings import Choice, spec_control
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings
    from ui.tabs.visualizers_tab import VisualizersTab
    key = 'shockwave_grid_wire_display'
    control = spec_control(key)
    assert isinstance(control, Choice) and control.choices == ('Vertices', 'Glass', 'Glass + Vertices')
    assert control.bucket == 'render' and not control.when and not control.enabled_when
    assert require_canonical_default('widgets.spotify_visualizer.' + key) in control.choices
    settings_manager.set('widgets', {'spotify_visualizer': {
        'enabled': True, 'visualizers_enabled': True, 'mode': 'shockwave_grid',
        'mode_activation': build_visualizer_mode_activation(['shockwave_grid']),
        'preset_shockwave_grid': get_custom_preset_index('shockwave_grid'), key: 'Glass + Vertices'}})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page('shockwave_grid')
        calls = []
        monkeypatch.setattr(tab, '_save_settings', lambda: calls.append('save'))
        combo = getattr(tab, key)
        assert combo.currentText() == 'Glass + Vertices' and combo.isEnabled()
        defaults = require_canonical_default('widgets.spotify_visualizer')
        load_spec_mode_settings(tab, 'shockwave_grid', defaults)
        assert not calls and combo.currentText() == 'Vertices'
        for value in control.choices:
            load_spec_mode_settings(tab, 'shockwave_grid', {**defaults, key: value})
            assert not calls and combo.currentText() == value
            assert collect_spec_mode_settings(tab, 'shockwave_grid')[key] == value
        tab._save_settings_now()
        assert settings_manager.get('widgets', {})['spotify_visualizer'][key] == 'Glass + Vertices'
    finally:
        tab.deleteLater(); qt_app.processEvents()
    reopened = VisualizersTab(settings_manager)
    try:
        reopened._select_mode_page('shockwave_grid')
        assert getattr(reopened, key).currentText() == 'Glass + Vertices'
    finally:
        reopened.deleteLater(); qt_app.processEvents()


def test_wire_display_model_projection_and_custom_preset_retention(monkeypatch):
    from core.settings import visualizer_presets as presets
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs, shockwave_grid_parameters
    key = 'shockwave_grid_wire_display'
    defaults = require_canonical_default('widgets.spotify_visualizer')
    assert SpotifyVisualizerSettings.from_mapping({}, apply_preset_overlay=False).to_dict()[
        'widgets.spotify_visualizer.' + key] == 'Vertices'
    from core.settings.visualizer_mode_settings import spec_control
    for value in spec_control(key).choices:
        model = SpotifyVisualizerSettings.from_mapping({key: value}, apply_preset_overlay=False)
        stored = model.to_dict()['widgets.spotify_visualizer.' + key]
        assert stored == value
        owner = _packed_host()
        apply_presentation_vis_mode_kwargs(owner, {**defaults, key: stored})
        owner._scene3d_detail = 'High'
        assert shockwave_grid_parameters(owner)[key] == value
    art = {key: 'Vertices'}
    catalog = [presets.VisualizerPreset('Test Art', 'Test-owned', art),
               presets.VisualizerPreset('Custom', '', {}, True)]
    monkeypatch.setattr(presets, 'get_presets', lambda _mode: catalog)
    live = {**defaults, 'mode': 'shockwave_grid', key: 'Glass + Vertices'}
    custom = presets.build_normalized_custom_snapshot('shockwave_grid', live)
    assert custom[key] == 'Glass + Vertices'
    resolved = presets.apply_preset_to_config('shockwave_grid', 0, live)
    assert resolved[key] == 'Vertices'
    assert presets.restore_visualizer_snapshot('shockwave_grid', resolved, custom)
    assert resolved[key] == 'Glass + Vertices'


def test_celestial_and_glass_body_conditions_are_live_silent_and_preserve_latent_values(qt_app, settings_manager, monkeypatch):
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings
    from ui.tabs.visualizers_tab import VisualizersTab
    settings_manager.set('widgets', {'spotify_visualizer': {
        'enabled': True, 'visualizers_enabled': True, 'mode': 'shockwave_grid',
        'mode_activation': build_visualizer_mode_activation(['shockwave_grid']),
        'preset_shockwave_grid': get_custom_preset_index('shockwave_grid')}})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page('shockwave_grid')
        calls = []
        monkeypatch.setattr(tab, '_save_settings', lambda: calls.append('save'))
        defaults = require_canonical_default('widgets.spotify_visualizer')
        latent = {'shockwave_grid_sun_color': [11, 22, 33, 77], 'shockwave_grid_moon_color': [44, 55, 66, 88],
                  'shockwave_grid_sun_rays_color': [77, 88, 99, 111], 'shockwave_grid_glass_tint': [12, 34, 56, 123]}
        config = {**defaults, **latent, 'shockwave_grid_sky_enabled': False, 'shockwave_grid_sun_enabled': True,
                  'shockwave_grid_sun_orbit_enabled': True, 'shockwave_grid_sun_rays_enabled': True}
        load_spec_mode_settings(tab, 'shockwave_grid', config)
        assert not calls
        assert tab.shockwave_grid_sun_enabled.isEnabled() and tab.shockwave_grid_sun_color_btn.isEnabled()
        assert tab.shockwave_grid_sun_orbit_speed.isEnabled() and tab.shockwave_grid_sun_rays_color_btn.isEnabled()
        assert not tab.shockwave_grid_star_color_btn.isEnabled()
        tab.shockwave_grid_sun_enabled.setChecked(False)
        assert not tab.shockwave_grid_sun_orbit_speed.isEnabled()
        assert not tab.shockwave_grid_sun_rays_strength.isEnabled() and not tab.shockwave_grid_sun_rays_color_btn.isEnabled()
        tab.shockwave_grid_sun_enabled.setChecked(True)
        tab.shockwave_grid_sun_orbit_enabled.setChecked(False)
        tab.shockwave_grid_sun_rays_enabled.setChecked(False)
        assert not tab.shockwave_grid_sun_orbit_speed.isEnabled() and not tab.shockwave_grid_sun_rays_strength.isEnabled()
        rows = tab._shockwave_grid_rows
        tab.shockwave_grid_sun_mode.setCurrentText('Moon')
        assert rows['shockwave_grid_sun_color'].isHidden()
        assert not rows['shockwave_grid_moon_color'].isHidden() and not rows['shockwave_grid_moon_phase'].isHidden()
        for style in ('Vertices', 'Glass', 'Glass + Vertices'):
            tab.shockwave_grid_wire_display.setCurrentText(style)
            glass = 'Glass' in style
            points = 'Vertices' in style or 'Glass + Vertices' in style
            assert rows['shockwave_grid_glass_tint'].isHidden() == (not glass)
            assert rows['shockwave_grid_glass_strength'].isHidden() == (not glass)
            assert rows['shockwave_grid_vertex_color'].isHidden() == (not points or glass)
            assert rows['shockwave_grid_vertex_accent_color'].isHidden() == (not points or glass)
            assert rows['shockwave_grid_vertex_outline_color'].isHidden() == (not (glass and points))
        collected = collect_spec_mode_settings(tab, 'shockwave_grid')
        assert all(collected[key] == value for key, value in latent.items())
        model = SpotifyVisualizerSettings.from_mapping(collected, apply_preset_overlay=False)
        saved = model.to_dict()
        assert all(saved['widgets.spotify_visualizer.' + key] == value for key, value in latent.items())
        calls.clear()
        load_spec_mode_settings(tab, 'shockwave_grid', {**config, 'shockwave_grid_sun_enabled': False})
        assert not calls and not tab.shockwave_grid_sun_orbit_speed.isEnabled()
        assert not tab.shockwave_grid_sun_rays_color_btn.isEnabled()
    finally:
        tab.deleteLater(); qt_app.processEvents()


@pytest.mark.parametrize('mode', ['spectrum','extruded_spectrum','sphere','bubble'])
def test_other_mode_default_and_full_configuration_do_no_heightfield_work(monkeypatch, mode):
    from rendering.gl_programs import heightfield
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    from widgets.spotify_visualizer.presentation_state import install_default_presentation_state
    def forbidden(*args):
        raise AssertionError('inactive Neon must not normalize or derive its terrain')
    monkeypatch.setattr(heightfield, 'normalize_heightfield', forbidden)
    monkeypatch.setattr(heightfield, 'heightfield_surface_bytes', forbidden)
    owner = _packed_host(mode)
    install_default_presentation_state(owner)
    apply_presentation_vis_mode_kwargs(owner, require_canonical_default('widgets.spotify_visualizer'))
    assert not hasattr(owner,'_shockwave_grid_terrain') and not hasattr(owner,'_shockwave_grid_terrain_signature')
    unknown = SimpleNamespace()
    apply_presentation_vis_mode_kwargs(unknown, {'shockwave_grid_terrain':FIELD})
    assert not hasattr(unknown,'_shockwave_grid_terrain')


def test_active_neon_default_full_configuration_and_changed_terrain_pack_once(monkeypatch):
    from rendering.gl_programs import heightfield
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs, shockwave_grid_parameters
    from widgets.spotify_visualizer.presentation_state import install_default_presentation_state
    calls=[]
    original=heightfield.heightfield_surface_bytes
    monkeypatch.setattr(heightfield,'heightfield_surface_bytes',lambda data:(calls.append(data['size']),original(data))[1])
    owner=_packed_host()
    defaults=require_canonical_default('widgets.spotify_visualizer')
    install_default_presentation_state(owner)
    frozen=owner._shockwave_grid_terrain
    for _ in range(4):
        apply_presentation_vis_mode_kwargs(owner,deepcopy(defaults))
        assert owner._shockwave_grid_terrain is frozen
        assert shockwave_grid_parameters(owner)['shockwave_grid_terrain'] is frozen
    assert calls == [defaults['shockwave_grid_terrain']['size']]
    changed=deepcopy(FIELD)
    apply_presentation_vis_mode_kwargs(owner,{**defaults,'shockwave_grid_terrain':changed})
    next_frozen=owner._shockwave_grid_terrain
    assert next_frozen is not frozen and calls == [defaults['shockwave_grid_terrain']['size'],3]
    # Callers cannot mutate the admitted cache by retaining their authored record.
    changed['heights'][0]=.4
    assert owner._shockwave_grid_terrain_signature[1][0] == 0.0
    apply_presentation_vis_mode_kwargs(owner,{**defaults,'shockwave_grid_terrain':FIELD})
    assert owner._shockwave_grid_terrain is next_frozen and len(calls)==2
    apply_presentation_vis_mode_kwargs(owner,{**defaults,'shockwave_grid_terrain':changed})
    edited_frozen=owner._shockwave_grid_terrain
    assert edited_frozen is not next_frozen and len(calls)==3
    apply_presentation_vis_mode_kwargs(owner,{**defaults,'shockwave_grid_terrain':deepcopy(changed)})
    assert owner._shockwave_grid_terrain is edited_frozen and len(calls)==3
    # Other-mode full configuration never updates/rederives the dormant bundle.
    owner.runtime_controller.mode_id='sphere'
    apply_presentation_vis_mode_kwargs(owner,defaults)
    assert owner._shockwave_grid_terrain is edited_frozen and len(calls)==3


def test_neon_glow_bucket_live_conditions_and_latent_roundtrip(qt_app, settings_manager, monkeypatch):
    """Cross-bucket Glow dependencies never erase saved values or silently save on load."""
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings
    from ui.tabs.visualizers_tab import VisualizersTab

    settings_manager.set('widgets', {'spotify_visualizer': {
        'enabled': True, 'visualizers_enabled': True, 'mode': 'shockwave_grid',
        'mode_activation': build_visualizer_mode_activation(['shockwave_grid']),
        'preset_shockwave_grid': get_custom_preset_index('shockwave_grid')}})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page('shockwave_grid')
        calls = []
        monkeypatch.setattr(tab, '_save_settings', lambda: calls.append('save'))
        defaults = require_canonical_default('widgets.spotify_visualizer')
        saved = {
            'shockwave_grid_sun_enabled': False,
            'shockwave_grid_celestial_glow_enabled': True,
            'shockwave_grid_celestial_glow_strength': 1.35,
            'shockwave_grid_sun_rays_enabled': True,
            'shockwave_grid_sun_rays_strength': .47,
            'shockwave_grid_sun_rays_color': [31, 92, 147, 168],
            'shockwave_grid_sky_enabled': False,
            'shockwave_grid_starscape_beat': True,
            'shockwave_grid_star_glow_strength': 1.25,
            'shockwave_grid_star_glow_reactivity': 1.15,
            'shockwave_grid_horizon': .55,
        }
        load_spec_mode_settings(tab, 'shockwave_grid', {**defaults, **saved})
        assert not calls
        rows = tab._shockwave_grid_rows
        hidden = ('celestial_glow_enabled', 'celestial_glow_strength', 'celestial_glow_reactivity',
                  'sun_rays_enabled', 'sun_rays_strength', 'sun_rays_color',
                  'starscape_beat', 'star_glow_strength', 'star_glow_reactivity')
        assert all(rows['shockwave_grid_' + key].isHidden() for key in hidden)
        tab.shockwave_grid_sun_enabled.setChecked(True)
        assert not rows['shockwave_grid_celestial_glow_enabled'].isHidden()
        assert not rows['shockwave_grid_celestial_glow_strength'].isHidden()
        assert not rows['shockwave_grid_sun_rays_strength'].isHidden()
        tab.shockwave_grid_celestial_glow_enabled.setChecked(False)
        tab.shockwave_grid_sun_rays_enabled.setChecked(False)
        assert rows['shockwave_grid_celestial_glow_strength'].isHidden()
        assert rows['shockwave_grid_sun_rays_color'].isHidden()
        tab.shockwave_grid_sky_enabled.setChecked(True)
        assert not rows['shockwave_grid_starscape_beat'].isHidden()
        assert not rows['shockwave_grid_star_glow_strength'].isHidden()
        tab.shockwave_grid_starscape_beat.setChecked(False)
        assert rows['shockwave_grid_star_glow_strength'].isHidden()
        # Loading is silent and restores even the hidden controls' authored values.
        calls.clear()
        load_spec_mode_settings(tab, 'shockwave_grid', {**defaults, **saved})
        assert calls == []
        collected = collect_spec_mode_settings(tab, 'shockwave_grid')
        assert all(collected[key] == value for key, value in saved.items())
        assert all(rows['shockwave_grid_' + key].isHidden() for key in hidden)
    finally:
        tab.deleteLater()
        qt_app.processEvents()
