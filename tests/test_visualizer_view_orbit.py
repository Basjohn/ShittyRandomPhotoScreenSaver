"""Live view orbiting for 3D freeform Visualizers: which modes offer it; held W/A/S/D turning at
a steady rate on the logical clock (whatever the OS key repeat does, several keys at once); Alt +
left drag in interaction mode, through the real display window and runtime relay; wrapping and
clamping; and saving: once, when orbiting stops, never per step; on a curated preset the view
moves the mode to Custom."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from core.settings.default_contract import get_raw_default_settings
from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS, get_visualizer_mode_descriptor
from widgets.spotify_visualizer.view_orbit import (
    orbit_visualizer_view,
    view_orbit_settings,
    view_orbit_values,
)

_DEFAULTS = get_raw_default_settings()["widgets"]["spotify_visualizer"]
_ORBITING = [mode for mode in VISUALIZER_MODE_IDS if view_orbit_settings(mode)]


def _key(kind, key, *, repeat=False):
    return QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier, "", repeat)


def _host():
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

    from core.settings.scene3d_quality import resolve_visualizer_tier

    host = SimpleNamespace()
    # The activation adds the resolved 3D Detail tier beside the Visualizer section's values.
    apply_presentation_vis_mode_kwargs(
        host, {**dict(_DEFAULTS), "scene3d_detail": resolve_visualizer_tier(None, "extruded_spectrum")})
    return host


def test_only_3d_freeform_modes_orbit_through_their_own_view_settings():
    assert "extruded_spectrum" in _ORBITING
    for mode in VISUALIZER_MODE_IDS:
        keys = view_orbit_settings(mode)
        if not keys:
            continue
        descriptor = get_visualizer_mode_descriptor(mode)
        assert descriptor.presentation_policy.shell_policy.value == "frameless", mode
        assert len(keys) == 2 and all(key.startswith(descriptor.setting_prefixes) for key in keys)
        assert all(key in _DEFAULTS for key in keys)


@pytest.mark.parametrize("mode", _ORBITING)
def test_turn_goes_round_a_full_circle_and_tilt_stops_at_its_ends(mode):
    turn, tilt = view_orbit_settings(mode)
    turn_step, tilt_step = get_visualizer_mode_descriptor(mode).view_orbit_steps
    host = _host()
    before = view_orbit_values(host, mode)
    after = orbit_visualizer_view(host, mode, 1, 0)
    assert after == view_orbit_values(host, mode)                 # the live state the capture reads
    assert after[turn] == pytest.approx((before[turn] + turn_step + 1.0) % 2.0 - 1.0)
    # Turning on and on goes round and comes back: a whole circle is 2 in setting units.
    steps = round(2.0 / turn_step)
    seen = [orbit_visualizer_view(host, mode, 1, 0)[turn] for _ in range(steps)]
    assert min(seen) < -0.9 and max(seen) > 0.9 and all(-1.0 <= value <= 1.0 for value in seen)
    assert seen[-1] == pytest.approx(after[turn], abs=1e-6)
    # Tilt stops at its ends.
    for _ in range(round(2.0 / tilt_step)):
        orbit_visualizer_view(host, mode, 0, 1)
    high = view_orbit_values(host, mode)[tilt]
    assert orbit_visualizer_view(host, mode, 0, 1)[tilt] == high
    for _ in range(round(2.0 / tilt_step)):
        orbit_visualizer_view(host, mode, 0, -1)
    low = view_orbit_values(host, mode)[tilt]
    assert low < high and orbit_visualizer_view(host, mode, 0, -1)[tilt] == low


def test_a_mode_without_a_view_ignores_orbiting():
    host = _host()
    snapshot = dict(vars(host))
    assert orbit_visualizer_view(host, "spectrum", 1, 1) == {}
    assert vars(host) == snapshot


def _owner():
    from rendering.runtime_input import RuntimeInputOwner

    owner = RuntimeInputOwner()
    steps, finished, exits = [], [], []
    owner.view_orbit_rates_changed.connect(lambda turn, tilt: steps.append((turn, tilt)))
    owner.view_orbit_finished.connect(lambda: finished.append(True))
    owner.exit_requested.connect(lambda: exits.append(True))
    return owner, steps, finished, exits


def test_wasd_orbit_only_when_a_3d_visualizer_is_shown_and_s_no_longer_opens_settings(qt_app):
    owner, steps, finished, exits = _owner()
    assert not hasattr(owner, "settings_requested")
    assert owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_W)) is True
    assert steps == [] and exits == [True]                        # no 3D view: any key exits, as before

    owner, steps, finished, exits = _owner()
    owner.set_view_orbit_enabled(True)
    for key in (Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D):
        assert owner.handle_key_press(_key(QEvent.Type.KeyPress, key)) is True
        assert owner.handle_key_release(_key(QEvent.Type.KeyRelease, key)) is True
    # Each press starts that key's direction, each release stops it.
    assert steps == [(0, 1), (0, 0), (1, 0), (0, 0), (0, -1), (0, 0), (-1, 0), (0, 0)]
    assert finished == [True] * 4 and exits == []


def test_held_keys_turn_together_and_finish_once_whatever_the_key_repeat_does(qt_app):
    owner, steps, finished, _exits = _owner()
    owner.set_view_orbit_enabled(True)
    owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_W))
    for _ in range(10):                                           # key repeat: release/press pairs
        owner.handle_key_release(_key(QEvent.Type.KeyRelease, Qt.Key.Key_W, repeat=True))
        owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_W, repeat=True))
    assert steps == [(0, 1)]                                      # repeat changes nothing
    # The OS stops repeating W once D is pressed; both still turn the view, and releasing D
    # leaves W turning it (the "stuck" orbit of OS-repeat stepping).
    owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_D))
    owner.handle_key_release(_key(QEvent.Type.KeyRelease, Qt.Key.Key_D))
    assert steps == [(0, 1), (-1, 1), (0, 1)] and finished == []
    owner.handle_key_release(_key(QEvent.Type.KeyRelease, Qt.Key.Key_W))
    assert steps[-1] == (0, 0) and finished == [True]
    # Losing the 3D view mid-orbit (mode change, retirement) ends the orbit too.
    owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_A))
    owner.set_view_orbit_enabled(False)
    assert finished == [True, True]


class _Settings:
    def __init__(self, section):
        from core.settings.visualizer_presets import VISUALIZER_CUSTOM_STORAGE_KEY

        self.values = {"widgets.spotify_visualizer": section, VISUALIZER_CUSTOM_STORAGE_KEY: {}}
        self.writes = []

    def get(self, key, default=None):
        return deepcopy(self.values.get(key, default))

    def replace_visualizer_runtime_preset_state(self, section, custom):
        self.writes.append((deepcopy(section), deepcopy(custom)))
        self.values["widgets.spotify_visualizer"] = deepcopy(section)


def _manager(section, mode="extruded_spectrum"):
    controller = SimpleNamespace(mode_id=mode, presentation_state=_host())
    return SimpleNamespace(
        _quick_visualizer_owner=SimpleNamespace(is_retired=False, controller=controller),
        _quick_view_orbit_pending=None,
        settings_manager=_Settings(section),
        _widgets_config_snapshot={},
        _refresh_all_quick_context_menus=lambda: None,
        _refresh_quick_visualizer_edit_content_envelope=lambda: None,
    )


def test_held_keys_turn_the_view_on_the_logical_clock_and_settle_when_released():
    from widgets.spotify_visualizer.view_orbit import (
        VIEW_ORBIT_STEPS_PER_SECOND,
        apply_view_orbit_motion,
        set_view_orbit_rates,
        stop_view_orbit_motion,
    )

    mode = "extruded_spectrum"
    turn, tilt = view_orbit_settings(mode)
    turn_step, _tilt_step = get_visualizer_mode_descriptor(mode).view_orbit_steps
    host = _host()
    start = view_orbit_values(host, mode)
    set_view_orbit_rates(host, mode, 1.0, 0.0, now=100.0)
    rate = turn_step * VIEW_ORBIT_STEPS_PER_SECOND
    # The capture (logical thread) sees the view its own frame time has reached; nothing is written.
    for now in (100.0, 100.5, 101.0):
        seen = apply_view_orbit_motion(host, mode, dict(start), now)
        assert seen[turn] == pytest.approx((start[turn] + rate * (now - 100.0) + 1.0) % 2.0 - 1.0)
        assert seen[tilt] == pytest.approx(start[tilt])
    assert view_orbit_values(host, mode) == start                 # settings untouched while held
    # The production capture reads its parameters through the same evaluation at its frame time.
    from widgets.spotify_visualizer.config_applier import extruded_spectrum_parameters

    captured = extruded_spectrum_parameters(host, 101.0)
    assert captured[turn] == pytest.approx(apply_view_orbit_motion(host, mode, dict(start), 101.0)[turn])
    assert captured[turn] != pytest.approx(start[turn])
    settled = stop_view_orbit_motion(host, now=101.0)
    assert settled[0] == mode and view_orbit_values(host, mode) == pytest.approx(settled[1])
    assert apply_view_orbit_motion(host, mode, {"x": 1}, 999.0) == {"x": 1}   # no motion any more
    assert stop_view_orbit_motion(host, now=102.0) is None


def test_the_view_is_saved_once_when_orbiting_stops_never_per_step():
    from core.settings.visualizer_presets import get_custom_preset_index
    from engine.display_manager import DisplayManager

    section = {**deepcopy(_DEFAULTS), "mode": "extruded_spectrum",
               "preset_extruded_spectrum": get_custom_preset_index("extruded_spectrum")}
    manager = _manager(section)
    for _ in range(30):
        DisplayManager._orbit_quick_visualizer_view(manager, 0.5, 0.25)    # a drag's steps
    DisplayManager._set_quick_view_orbit_rates(manager, 1.0, 0.0)          # then a held key
    assert manager.settings_manager.writes == []                  # live only while orbiting
    DisplayManager._persist_quick_visualizer_view(manager)
    DisplayManager._persist_quick_visualizer_view(manager)        # a second release saves nothing
    assert len(manager.settings_manager.writes) == 1
    saved, _cache = manager.settings_manager.writes[0]
    live = view_orbit_values(manager._quick_visualizer_owner.controller.presentation_state, "extruded_spectrum")
    assert {key: saved[key] for key in live} == pytest.approx(live)
    assert saved["mode"] == "extruded_spectrum"


def test_orbiting_a_curated_preset_moves_the_mode_to_custom_holding_what_was_shown():
    from core.settings.visualizer_presets import get_custom_preset_index, get_presets
    from core.settings.visualizer_view_orbit import resolve_visualizer_view_orbit

    mode = "extruded_spectrum"
    turn, tilt = view_orbit_settings(mode)
    preset = next(p for p in get_presets(mode) if not p.is_custom and p.settings)
    index = get_presets(mode).index(preset)
    section = {**deepcopy(_DEFAULTS), "mode": "bubble", f"preset_{mode}": index}
    original = deepcopy(section)
    config, cache = resolve_visualizer_view_orbit(section, {}, mode=mode, values={turn: 0.42, tilt: 0.13})
    assert section == original                                    # inputs untouched
    assert config["mode"] == "bubble"                             # orbiting never switches the shown mode
    assert config[f"preset_{mode}"] == get_custom_preset_index(mode)
    assert (config[turn], config[tilt]) == (0.42, 0.13)
    shown = {key: value for key, value in preset.settings.items() if key.startswith(mode) and key not in (turn, tilt)}
    assert shown and all(config[key] == value for key, value in shown.items())
    assert cache[mode][turn] == 0.42 and cache[mode][tilt] == 0.13

    # Already on Custom: only the view changes, and the Custom cache is left alone.
    config, cache = resolve_visualizer_view_orbit({**original, f"preset_{mode}": get_custom_preset_index(mode)},
                                                  {}, mode=mode, values={turn: -0.3, tilt: 0.9})
    assert config[f"preset_{mode}"] == get_custom_preset_index(mode)
    assert (config[turn], config[tilt]) == (-0.3, 0.9) and cache == {}


def test_saving_an_orbit_normalizes_only_the_snapshot_it_replaces(tmp_path, monkeypatch, qt_app):
    """A finished orbit is saved on the GUI thread between frames, so it must stay cheap: only the
    orbited mode's Custom snapshot is (re)built, every other stored snapshot passes through as it
    is (normalizing each one built a whole settings model, ~50 ms a save: a visible jump). What
    is persisted is exactly what normalizing everything would have persisted."""
    import core.settings.visualizer_presets as presets
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_presets import (
        VISUALIZER_CUSTOM_STORAGE_KEY,
        build_normalized_custom_snapshot,
        get_custom_preset_index,
        get_presets,
        normalize_visualizer_custom_snapshot_cache,
    )
    from core.settings.visualizer_view_orbit import resolve_visualizer_view_orbit

    mode = "extruded_spectrum"
    turn, tilt = view_orbit_settings(mode)
    settings = SettingsManager(application="orbit_save_test", storage_base_dir=tmp_path)
    stored = {other: build_normalized_custom_snapshot(other, {**deepcopy(_DEFAULTS), "mode": other})
              for other in VISUALIZER_MODE_IDS}
    curated = next(index for index, p in enumerate(get_presets(mode)) if not p.is_custom and p.settings)
    for index, values in ((get_custom_preset_index(mode), {turn: -0.3, tilt: 0.2}),
                          (curated, {turn: 0.42, tilt: 0.13})):
        section = {**deepcopy(_DEFAULTS), "mode": mode, f"preset_{mode}": index}
        settings.replace_visualizer_runtime_preset_state(section, stored)
        normalized = []
        real = presets.normalize_visualizer_mode_payload
        monkeypatch.setattr(presets, "normalize_visualizer_mode_payload",
                            lambda key, payload: normalized.append(key) or real(key, payload))
        config, cache = resolve_visualizer_view_orbit(settings.get("widgets.spotify_visualizer"),
                                                      settings.get(VISUALIZER_CUSTOM_STORAGE_KEY, {}),
                                                      mode=mode, values=values)
        settings.replace_visualizer_runtime_preset_state(config, cache)
        monkeypatch.undo()
        assert set(normalized) <= {mode}                         # never the modes it left alone
        assert len(normalized) <= 2                               # built once, checked once
        persisted = settings.get(VISUALIZER_CUSTOM_STORAGE_KEY, {})
        assert persisted == normalize_visualizer_custom_snapshot_cache(cache)
        assert {key: persisted[key] for key in stored if key != mode} == {
            key: value for key, value in stored.items() if key != mode}


def test_canonical_defaults_are_never_handed_out_mutable():
    """Default lookups are cached per key; a caller mutating what it got must not change the next."""
    from core.settings.default_contract import require_canonical_default

    key = "widgets.spotify_visualizer.spectrum_shape_nodes"
    first = require_canonical_default(key)
    assert isinstance(first, list) and first
    first.clear()
    assert require_canonical_default(key) and require_canonical_default(key) is not first


def _mouse(kind, x, y, *, button=Qt.MouseButton.LeftButton, alt=True):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent

    modifiers = Qt.KeyboardModifier.AltModifier if alt else Qt.KeyboardModifier.NoModifier
    buttons = button if kind != QEvent.Type.MouseButtonRelease else Qt.MouseButton.NoButton
    return QMouseEvent(kind, QPointF(x, y), QPointF(x, y), button, buttons, modifiers)


def _quick_owner(*, interaction=True, on_visualizer=lambda point: point.x() < 500):
    from rendering.quick.input_controller import QuickInputController
    from rendering.runtime_input import clear_runtime_pointer_input_suppression

    clear_runtime_pointer_input_suppression()
    owner = QuickInputController(screen_index=0, runtime_generation=1, interaction_mode_enabled=interaction)
    steps, finished, exits = [], [], []
    owner.view_orbit_requested.connect(lambda turn, tilt: steps.append((turn, tilt)))
    owner.view_orbit_finished.connect(lambda: finished.append(True))
    owner.exit_requested.connect(lambda: exits.append(True))
    owner.set_view_orbit_enabled(True)
    owner.set_view_orbit_hit_test(on_visualizer)
    return owner, steps, finished, exits


def test_alt_drag_on_the_visualizer_orbits_it_in_interaction_mode(qt_app):
    owner, steps, finished, exits = _quick_owner()
    assert owner.handle_mouse_press(_mouse(QEvent.Type.MouseButtonPress, 100, 100)) is True
    assert owner.passive_mouse_move_requires_routing                 # routed even in interaction mode
    owner.handle_mouse_move(_mouse(QEvent.Type.MouseMove, 108, 100))  # right: the scene turns toward it
    owner.handle_mouse_move(_mouse(QEvent.Type.MouseMove, 108, 96))   # up: the camera lowers
    step = owner.VIEW_ORBIT_DRAG_PIXELS_PER_STEP
    assert steps == [(8 / step, 0.0), (0.0, -4 / step)] and finished == []
    assert owner.handle_mouse_release(_mouse(QEvent.Type.MouseButtonRelease, 108, 96)) is True
    assert finished == [True] and exits == []
    assert not owner.passive_mouse_move_requires_routing             # back to interaction routing
    owner.deleteLater()


def test_alt_drag_needs_interaction_alt_and_the_visualizer_under_the_pointer(qt_app):
    for kwargs, event in ((dict(), _mouse(QEvent.Type.MouseButtonPress, 700, 100)),        # off the Visualizer
                          (dict(), _mouse(QEvent.Type.MouseButtonPress, 100, 100, alt=False)),
                          (dict(), _mouse(QEvent.Type.MouseButtonPress, 100, 100,
                                          button=Qt.MouseButton.RightButton))):
        owner, steps, finished, exits = _quick_owner(**kwargs)
        handled = owner.handle_mouse_press(event)
        if event.button() == Qt.MouseButton.LeftButton:
            assert handled is False                                 # the widgets get it as before
        owner.handle_mouse_move(_mouse(QEvent.Type.MouseMove, 150, 120))
        assert steps == [] and finished == []
        owner.deleteLater()
    # Outside interaction mode a click still exits, Alt or not.
    owner, steps, _finished, exits = _quick_owner(interaction=False)
    owner.handle_mouse_press(_mouse(QEvent.Type.MouseButtonPress, 100, 100))
    assert steps == [] and exits == [True]
    owner.deleteLater()


def test_orbiting_finishes_once_after_both_keys_and_drag_end_and_retirement_drops_the_drag(qt_app):
    owner, steps, finished, _exits = _quick_owner()
    owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_W))
    owner.handle_mouse_press(_mouse(QEvent.Type.MouseButtonPress, 100, 100))
    owner.handle_key_release(_key(QEvent.Type.KeyRelease, Qt.Key.Key_W))
    assert finished == []                                            # still dragging
    owner.handle_mouse_release(_mouse(QEvent.Type.MouseButtonRelease, 100, 100))
    assert finished == [True]
    owner.handle_mouse_press(_mouse(QEvent.Type.MouseButtonPress, 100, 100))
    owner.set_view_orbit_hit_test(None)                              # the display's runtime retires
    assert not owner.passive_mouse_move_requires_routing
    owner.handle_mouse_move(_mouse(QEvent.Type.MouseMove, 140, 100))
    assert steps == []                                               # the drag is gone
    owner.deleteLater()


def test_alt_drag_through_the_real_display_window_reaches_the_runtime_in_fractions(qt_app):
    """The production seam: window events -> input owner -> QuickDisplayRuntime relay. A drag's
    steps are fractions of a step per mouse move; the relay must carry them (an int signature
    once truncated every one to zero, so dragging did nothing)."""
    from PySide6.QtCore import QPointF

    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from rendering.runtime_input import clear_runtime_pointer_input_suppression

    clear_runtime_pointer_input_suppression()
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(screen_index=0, runtime_generation=31, screen=qt_app.primaryScreen(),
                                  scene_factory=factory,
                                  window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
                                  interaction_mode_enabled=True)
    steps, rates, finished = [], [], []
    runtime.view_orbit_requested.connect(lambda turn, tilt: steps.append((turn, tilt)))
    runtime.view_orbit_rates_changed.connect(lambda turn, tilt: rates.append((turn, tilt)))
    runtime.view_orbit_finished.connect(lambda: finished.append(True))
    controller = runtime.input_controller
    try:
        # The runtime lends its own scene's Visualizer hit test (no Visualizer here: it says no).
        assert controller._view_orbit_hit_test == runtime.scene_controller.visualizer_contains_scene_position
        assert not controller._view_orbit_hit_test(QPointF(10.0, 10.0))
        controller.set_view_orbit_enabled(True)
        controller.set_view_orbit_hit_test(lambda point: True)    # stand in for a shown Visualizer
        window = runtime.window
        window.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, 100, 100))
        window.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, 102, 101))
        window.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, 103, 101))
        window.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, 103, 101))
        step = controller.VIEW_ORBIT_DRAG_PIXELS_PER_STEP
        assert steps == [pytest.approx((2 / step, 1 / step)), pytest.approx((1 / step, 0.0))]
        assert finished == [True]
        window.keyPressEvent(_key(QEvent.Type.KeyPress, Qt.Key.Key_A))
        window.keyReleaseEvent(_key(QEvent.Type.KeyRelease, Qt.Key.Key_A))
        assert rates == [(1.0, 0.0), (0.0, 0.0)] and finished == [True, True]
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()
    assert controller._view_orbit_hit_test is None                # retirement dropped the scene's test
