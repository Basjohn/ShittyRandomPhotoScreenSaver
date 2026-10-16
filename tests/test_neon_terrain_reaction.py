"""Neon Lake's Terrain Reaction: lane drives on the sole capture clock from the analysis spectrum, the
shaper that biases them along the land's height, and the capture that feeds them."""
from dataclasses import FrozenInstanceError, replace
import math
from types import SimpleNamespace

import pytest

from core.settings.default_contract import require_canonical_default
from rendering.gl_programs.neon_terrain_reaction import (
    REACTION_LANES,
    REACTION_SAMPLES,
    bake_terrain_shaper,
    normalize_terrain_shaper,
    reaction_band_energies,
)
from widgets.spotify_visualizer.render_state import ShockwaveGridFrame
from widgets.spotify_visualizer.shockwave_frame_runtime import (
    REACTION_SUSTAIN,
    ShockwaveGridFrameRuntime,
)

LANES = len(REACTION_LANES)
FLAT = (1.0,) * 20
DEFAULT_SHAPER = require_canonical_default("widgets.spotify_visualizer.shockwave_grid_terrain_shaper")


def _lanes(*levels, per=4):
    """A spectrum whose five stretches hold these energies."""
    return tuple(level for level in levels for _ in range(per))


def _advance(runtime, now, spectrum=FLAT, **kwargs):
    return runtime.advance_terrain_reaction(
        spectrum, now_ts=now, playing=kwargs.pop("playing", True),
        identity=kwargs.pop("identity", (1, 2, 3)), source_identity=kwargs.pop("source_identity", (2, 3)),
        attack=kwargs.pop("attack", 0.35), release=kwargs.pop("release", 1.2),
        motion_speed=kwargs.pop("motion_speed", 0.5), **kwargs)


def test_lane_energies_cover_the_spectrum_in_frequency_order_at_any_length():
    assert reaction_band_energies(()) == (0.0,) * LANES
    assert reaction_band_energies(_lanes(1, 2, 3, 4, 5)) == pytest.approx((1, 2, 3, 4, 5))
    # Seven bands still split into five weighted stretches (partial bands shared, not dropped).
    energies = reaction_band_energies((7.0,) * 7)
    assert energies == pytest.approx((7.0,) * LANES)
    rising = reaction_band_energies(tuple(float(i) for i in range(35)))
    assert list(rising) == sorted(rising)


@pytest.mark.parametrize("gain", [1.0, 0.4])
def test_drives_start_at_rest_stay_bounded_and_ignore_capture_partitioning(gain):
    coarse, fine = ShockwaveGridFrameRuntime(), ShockwaveGridFrameRuntime()
    quiet, hit = _lanes(1, 1, 1, 1, 1), _lanes(1, 3, 1, 1, 1)
    first = _advance(coarse, 10.0, quiet, musical_gain=gain)
    assert first.bands == (0.0,) * LANES and first.phase == 0.0
    _advance(fine, 10.0, quiet, musical_gain=gain)
    # Same rising passage, captured once vs. at 120 Hz: same drives (the recent level is a separate
    # slow follower, so compare with the identical input held across the interval).
    expected = _advance(coarse, 10.5, hit, musical_gain=gain)
    for tick in range(1, 61):
        actual = _advance(fine, 10.0 + tick / 120.0, hit, musical_gain=gain)
    assert actual.bands == pytest.approx(expected.bands, rel=0.08, abs=0.01)
    assert all(0.0 <= value <= gain + 1e-9 for value in actual.bands)
    assert actual.bands[1] == max(actual.bands), "the lane that rose leads"


def test_sustained_bass_settles_modestly_and_never_drowns_a_rising_lane():
    runtime = ShockwaveGridFrameRuntime()
    wall = _lanes(10, 1, 1, 1, 1)                 # a loud, steady bass passage
    for tick in range(0, 400):
        settled = _advance(runtime, 1.0 + tick * 0.05, wall)
    # Nothing new in the bass: only its (capped) share remains, far from pinned.
    assert settled.bands[0] <= REACTION_SUSTAIN + 0.02
    assert settled.bands[0] < 0.4
    # A rise in another lane over the same wall of bass takes the lead.
    for tick in range(1, 8):
        lifted = _advance(runtime, 21.0 + tick * 0.05, _lanes(10, 1, 1, 4, 1))
    assert lifted.bands[3] > lifted.bands[0] + 0.2


def test_rise_settle_repeat_and_pause():
    runtime = ShockwaveGridFrameRuntime()
    _advance(runtime, 1.0, _lanes(1, 1, 1, 1, 1))
    rising = _advance(runtime, 1.35, _lanes(3, 3, 3, 3, 3))
    assert 0.3 < max(rising.bands) < 0.9
    repeated = _advance(runtime, 1.35, _lanes(3, 3, 3, 3, 3))
    assert repeated.bands == rising.bands and repeated.phase == rising.phase and not repeated.changed
    paused = _advance(runtime, 1.70, _lanes(3, 3, 3, 3, 3), playing=False)
    assert max(paused.bands) > max(rising.bands) * 0.6, "settle is slower than rise"
    for now in (10.0, 30.0):
        rested = _advance(runtime, now, playing=False)
    assert rested.bands == (0.0,) * LANES and not rested.pending


def test_the_land_wanders_only_while_the_music_drives_it():
    runtime = ShockwaveGridFrameRuntime()
    _advance(runtime, 1.0, _lanes(1, 1, 1, 1, 1))
    driven = _advance(runtime, 1.5, _lanes(4, 4, 4, 4, 4))
    assert driven.phase > 0.0 and driven.pending
    slow, fast = ShockwaveGridFrameRuntime(), ShockwaveGridFrameRuntime()
    for runtime_, speed in ((slow, 0.0), (fast, 1.0)):
        _advance(runtime_, 1.0, _lanes(1, 1, 1, 1, 1), motion_speed=speed)
        _advance(runtime_, 1.5, _lanes(4, 4, 4, 4, 4), motion_speed=speed)
    assert fast._terrain_phase > slow._terrain_phase > 0.0
    for now in (20.0, 40.0):
        silent = _advance(runtime, now, musical_gain=0.0)
    held = _advance(runtime, 50.0, musical_gain=0.0)
    assert held.phase == silent.phase and not held.pending, "silence holds the land still"


def test_resets_on_generation_source_clock_and_retirement():
    runtime = ShockwaveGridFrameRuntime()
    _advance(runtime, 1.0, _lanes(1, 1, 1, 1, 1))
    assert max(_advance(runtime, 1.5, _lanes(4, 4, 4, 4, 4)).bands) > 0.0
    fresh = _advance(runtime, 1.6, identity=(2, 4, 5), source_identity=(4, 5))
    assert fresh.bands == (0.0,) * LANES and fresh.phase == 0.0
    stale = _advance(runtime, 1.7, identity=(2, 4, 5), source_identity=(2, 3))
    assert stale.bands == (0.0,) * LANES and not stale.pending
    assert _advance(runtime, 1.0, identity=(2, 4, 5), source_identity=(4, 5)).bands == (0.0,) * LANES
    runtime.reset()
    assert not runtime.terrain_reaction_pending
    runtime.retire()
    assert _advance(runtime, 8.0) is None and not runtime.terrain_reaction_pending


def test_disabled_reaction_reads_nothing_and_resumes_from_rest():
    class Unreadable:
        def __iter__(self):
            raise AssertionError("a disabled reaction must not read the spectrum")

        def __len__(self):
            raise AssertionError("a disabled reaction must not read the spectrum")

    runtime = ShockwaveGridFrameRuntime()
    _advance(runtime, 1.0, _lanes(1, 1, 1, 1, 1))
    _advance(runtime, 1.5, _lanes(4, 4, 4, 4, 4))
    for now in (1.6, 20.0):
        disabled = _advance(runtime, now, Unreadable(), enabled=False)
        assert disabled.bands == (0.0,) * LANES and not disabled.changed and not disabled.pending
    resumed = _advance(runtime, 20.1, _lanes(4, 4, 4, 4, 4))
    assert resumed.bands == (0.0,) * LANES and resumed.phase == 0.0


@pytest.mark.parametrize("bands", [(0.0,) * 4, (0.0,) * 6, (float("nan"),) * 5, (-0.1,) * 5, (1.1,) * 5])
def test_typed_frame_rejects_invalid_drives(bands):
    with pytest.raises(ValueError):
        ShockwaveGridFrame(terrain_bands=bands)
    with pytest.raises(ValueError):
        ShockwaveGridFrame(terrain_phase=float("inf"))


def test_typed_frame_detaches_its_drives():
    values = [0.25] * 5
    frame = ShockwaveGridFrame(terrain_bands=values, terrain_phase=1.5)
    values[0] = 1.0
    assert frame.terrain_bands == (0.25,) * 5
    with pytest.raises(FrozenInstanceError):
        frame.terrain_bands = (1.0,) * 5
    assert replace(frame).terrain_bands == frame.terrain_bands


def test_shaper_admission_repairs_each_part_independently():
    assert normalize_terrain_shaper(DEFAULT_SHAPER, DEFAULT_SHAPER) == normalize_terrain_shaper(None, DEFAULT_SHAPER)
    custom = {"nodes": [[0.9, 2.0], [0.1, -1.0]], "notches": [[0.6, "Treble"], [0.2, "Bass"], [0.3, "Low-Mid"],
                                                            [0.4, "Vocal"], [0.5, "Hi-Mid"]],
              "lanes": {"Bass": 3.0, "Treble": "loud"}}
    shaper = normalize_terrain_shaper(custom, DEFAULT_SHAPER)
    assert shaper["nodes"] == [[0.1, 0.0], [0.9, 1.0]], "sorted and clamped"
    assert [label for _x, label in shaper["notches"]] == ["Bass", "Low-Mid", "Vocal", "Hi-Mid", "Treble"]
    assert shaper["notches"][0][0] == 0.0, "the first lane starts at the shoreline"
    assert shaper["lanes"]["Bass"] == 1.0 and shaper["lanes"]["Treble"] == DEFAULT_SHAPER["lanes"]["Treble"]
    broken = normalize_terrain_shaper({"nodes": [[0.5]], "notches": [[0.0, "Bass"]]}, DEFAULT_SHAPER)
    assert broken["nodes"] == DEFAULT_SHAPER["nodes"] and len(broken["notches"]) == LANES


def test_baked_tables_follow_the_shaper_along_the_land_height():
    shaper = normalize_terrain_shaper({
        "nodes": [[0.0, 0.2], [1.0, 1.0]],
        "notches": [[0.0, "Bass"], [0.2, "Low-Mid"], [0.4, "Vocal"], [0.6, "Hi-Mid"], [0.8, "Treble"]],
        "lanes": {"Bass": 1.0, "Low-Mid": 0.5, "Vocal": 0.5, "Hi-Mid": 0.5, "Treble": 0.25}}, DEFAULT_SHAPER)
    tables = bake_terrain_shaper(shaper)
    assert all(len(tables[key]) == REACTION_SAMPLES for key in ("lane", "weight", "bias"))
    assert tables["lane"][0] == 0.0 and tables["lane"][-1] == float(LANES - 1)
    assert list(tables["lane"]) == sorted(tables["lane"]), "lanes run from shoreline to summit"
    assert list(tables["bias"]) == sorted(tables["bias"]), "the bias is the curve itself"
    assert tables["weight"][0] == pytest.approx(tables["bias"][0] * 1.0)
    assert tables["weight"][-1] == pytest.approx(tables["bias"][-1] * 0.25)


def _capture_rig(parameters, engine_overrides=None):
    from widgets.spotify_visualizer import logical_frame_capture as capture

    runtime = ShockwaveGridFrameRuntime()
    controller = SimpleNamespace(mode_id="shockwave_grid", presentation_viewport_extent=(640, 400),
                                 resolve_logical_mode_state=lambda mode, factory: runtime,
                                 peek_logical_mode_state=lambda mode: runtime)
    widget = SimpleNamespace(runtime_controller=controller, _display_bars=(0.2, 0.6, 1.0, 0.8), _bar_count=4,
                             _spectrum_visual_smoothing_enabled=False, _spectrum_visual_smoothing=0.0,
                             _spectrum_single_piece=True, _spectrum_ghosting_enabled=False,
                             _spectrum_ghost_decay=0.5)
    reads = []
    spectrum = {"value": _lanes(1, 1, 1, 1, 1)}
    engine = SimpleNamespace(
        get_onset_events=lambda serial: (),
        get_musical_intensity=lambda: (reads.append("intensity"), 1.0)[1],
        get_musical_level=lambda: (reads.append("level"), (8.5, 1.0))[1],
        get_pre_agc_analysis_spectrum=lambda: (reads.append("spectrum"), spectrum["value"])[1])
    for name, value in (engine_overrides or {}).items():
        setattr(engine, name, value)

    def context(now, **kwargs):
        return capture._CaptureContext(now_ts=now, runtime_generation=1, engine_generation=2, activation_id=3,
                                       source_generation=kwargs.pop("source_generation", 2),
                                       source_activation_id=3, source_timestamp=now,
                                       playing=kwargs.pop("playing", True), first_frame=False, **kwargs)
    return capture, widget, engine, context, runtime, reads, spectrum, controller


def _reaction_parameters(**changes):
    return {"shockwave_grid_scroll": 0.0, "shockwave_grid_idle": 0.0, "shockwave_grid_sun_enabled": False,
            "shockwave_grid_sun_orbit_enabled": False, "shockwave_grid_sun_orbit_speed": 0.03,
            "shockwave_grid_terrain_reaction_enabled": True, "shockwave_grid_terrain_reaction_strength": 0.6,
            "shockwave_grid_terrain_peaks": 0.7, "shockwave_grid_terrain_pulses": 0.8,
            "shockwave_grid_terrain_swell": 0.0, "shockwave_grid_terrain_motion_speed": 0.5,
            "shockwave_grid_terrain_growth_attack": 0.35, "shockwave_grid_terrain_growth_release": 1.2,
            "shockwave_grid_sky_enabled": False, **changes}


def test_capture_feeds_the_analysis_spectrum_and_reads_nothing_when_off(monkeypatch):
    parameters = _reaction_parameters()
    capture, widget, engine, context, runtime, reads, spectrum, controller = _capture_rig(parameters)
    monkeypatch.setattr(capture.config_applier, "shockwave_grid_parameters", lambda owner, now: parameters)
    monkeypatch.setattr(capture, "_base_extras", lambda *args: {})
    first, extra = capture._capture_shockwave_grid(widget, engine, context(10.0))
    assert reads == ["intensity", "level", "spectrum"]
    assert first.terrain_bands == (0.0,) * LANES
    spectrum["value"] = _lanes(1, 1, 4, 1, 1)
    frame, extra = capture._capture_shockwave_grid(widget, engine, context(10.35))
    assert extra["_quick_mode_changed"] and frame.terrain_bands[2] == max(frame.terrain_bands) > 0.0
    again, extra = capture._capture_shockwave_grid(widget, engine, context(10.35))
    assert again.terrain_bands == frame.terrain_bands and not extra["_quick_mode_changed"]
    for change in ({"shockwave_grid_terrain_reaction_enabled": False},
                   {"shockwave_grid_terrain_reaction_strength": 0.0},
                   {"shockwave_grid_terrain_peaks": 0.0, "shockwave_grid_terrain_pulses": 0.0}):
        parameters.update(_reaction_parameters(**change))
        reads.clear()
        off, extra = capture._capture_shockwave_grid(widget, engine, context(11.0 + len(reads)))
        assert reads == ["intensity"], "a land that cannot move asks for no music"
        assert off.terrain_bands == (0.0,) * LANES and not runtime.terrain_reaction_pending
    controller.mode_id = "sphere"
    assert capture._capture_shockwave_grid(widget, engine, context(12.0)) is None


@pytest.mark.parametrize("body,orbit,speed,active", [(True, True, .03, True), (False, True, .03, False),
                                                     (True, False, .03, False), (True, True, 0.0, False)])
def test_celestial_orbit_admits_only_existing_capture_animation_clock(monkeypatch, body, orbit, speed, active):
    parameters = _reaction_parameters(shockwave_grid_terrain_reaction_enabled=False, shockwave_grid_sun_enabled=body,
                                      shockwave_grid_sun_orbit_enabled=orbit, shockwave_grid_sun_orbit_speed=speed,
                                      shockwave_grid_sky_enabled=False)
    capture, widget, engine, context, runtime, reads, spectrum, controller = _capture_rig(
        parameters, {"get_musical_intensity": lambda: 0.0})
    monkeypatch.setattr(capture.config_applier, "shockwave_grid_parameters", lambda owner, now: parameters)
    monkeypatch.setattr(capture, "_base_extras", lambda *args: {})
    first = capture._capture_shockwave_grid(widget, engine, context(10.0))[0]
    second = capture._capture_shockwave_grid(widget, engine, context(10.1))[0]
    assert second.animation_time - first.animation_time == pytest.approx(.1 if active else 0.0)
    assert second.terrain_bands == (0.0,) * LANES and not runtime.terrain_reaction_pending
