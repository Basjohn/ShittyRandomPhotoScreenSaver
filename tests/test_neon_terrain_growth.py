"""Independent terrain envelopes use the sole capture clock and resolved Spectrum bars."""
from dataclasses import FrozenInstanceError, replace
import math
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.shockwave_frame_runtime import ShockwaveGridFrameRuntime
from widgets.spotify_visualizer.render_state import ShockwaveGridFrame


def _advance(runtime, now, bars=(1.0,) * 8, **kwargs):
    return runtime.advance_terrain_growth(bars, now_ts=now, playing=kwargs.pop('playing', True),
        identity=kwargs.pop('identity', (1, 2, 3)), source_identity=kwargs.pop('source_identity', (2, 3)),
        attack=kwargs.pop('attack', 0.35), release=kwargs.pop('release', 1.2), **kwargs)


def test_growth_starts_at_zero_is_spatial_bounded_and_partition_invariant():
    coarse, fine = ShockwaveGridFrameRuntime(), ShockwaveGridFrameRuntime()
    profile = (0.0, 0.1, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0)
    assert _advance(coarse, 10.0, profile).values == (0.0,) * 8
    assert coarse.terrain_growth_pending
    _advance(fine, 10.0, profile)
    expected = _advance(coarse, 11.0, profile).values
    for tick in range(1, 121):
        actual = _advance(fine, 10.0 + tick / 120.0, profile).values
    assert actual == pytest.approx(expected, abs=2e-6)
    assert all(0.0 <= value <= 1.0 for value in actual)
    assert list(actual) == sorted(actual) and actual[0] == 0.0 and actual[-1] > 0.9
    # Profiles shorter than eight bars still contribute all their spatial intervals.
    short = ShockwaveGridFrameRuntime()
    _advance(short, 10.0, (0.0, 1.0))
    result = _advance(short, 10.35, (0.0, 1.0)).values
    assert result[:4] == (0.0,) * 4 and min(result[4:]) > 0.5
    # Release has the same time-partition contract.
    expected = _advance(coarse, 12.0, profile, playing=False).values
    for tick in range(1, 121):
        actual = _advance(fine, 11.0 + tick / 120.0, profile, playing=False).values
    assert actual == pytest.approx(expected, abs=2e-6)


def test_attack_release_hysteresis_same_timestamp_and_pause_never_use_idle_music():
    runtime = ShockwaveGridFrameRuntime()
    _advance(runtime, 1.0)
    rising = _advance(runtime, 1.35)
    assert 0.6 < rising.values[0] < 0.7
    repeated = _advance(runtime, 1.35)
    assert repeated.values == rising.values and not repeated.changed
    paused = _advance(runtime, 1.70, (1.0,) * 8, playing=False)
    assert paused.values[0] > rising.values[0] * 0.7  # slower release than attack
    low = _advance(runtime, 2.05, (0.0,) * 8)
    assert low.values[0] < paused.values[0]
    for now in (10.0, 20.0):
        settled = _advance(runtime, now, (1.0,) * 8, playing=False)
    assert settled.values == (0.0,) * 8 and not settled.pending
    # Fluctuations within the target deadband do not drive a second plateau.
    runtime = ShockwaveGridFrameRuntime()
    _advance(runtime, 1.0, (0.5,) * 8)
    _advance(runtime, 10.0, (0.5,) * 8)
    assert not runtime.terrain_growth_pending
    steady = _advance(runtime, 11.0, (0.51,) * 8)
    assert steady.values == (0.5,) * 8 and not steady.changed


def test_growth_resets_on_generation_source_clock_and_retirement():
    runtime = ShockwaveGridFrameRuntime()
    _advance(runtime, 1.0)
    assert max(_advance(runtime, 2.0).values) > 0.9
    fresh = _advance(runtime, 2.1, identity=(2, 4, 5), source_identity=(4, 5))
    assert fresh.values == (0.0,) * 8 and fresh.pending
    assert max(_advance(runtime, 3.0, identity=(2, 4, 5), source_identity=(4, 5)).values) > 0.9
    stale = _advance(runtime, 3.1, identity=(2, 4, 5), source_identity=(2, 3))
    assert stale.values == (0.0,) * 8 and not stale.pending
    assert _advance(runtime, 4.0, identity=(2, 4, 5), source_identity=(4, 5)).values == (0.0,) * 8
    assert max(_advance(runtime, 5.0, identity=(2, 4, 5), source_identity=(4, 5)).values) > 0.9
    assert _advance(runtime, 1.0).values == (0.0,) * 8
    runtime.reset()
    assert not runtime.terrain_growth_pending and _advance(runtime, 7.0).values == (0.0,) * 8
    runtime.retire()
    assert _advance(runtime, 8.0) is None and not runtime.terrain_growth_pending


def test_disabled_growth_does_no_bar_work_and_reenable_starts_from_zero():
    class UnreadableBars:
        def __bool__(self):
            raise AssertionError('invisible terrain growth must not inspect bars')

    runtime = ShockwaveGridFrameRuntime()
    _advance(runtime, 1.0)
    assert max(_advance(runtime, 1.35).values) > 0.6
    for now in (1.4, 20.0, 100.0):
        disabled = _advance(runtime, now, UnreadableBars(), enabled=False)
        assert disabled.values == (0.0,) * 8 and not disabled.changed and not disabled.pending
        assert not runtime.terrain_growth_pending
    first = _advance(runtime, 100.1)
    assert first.values == (0.0,) * 8 and not first.changed and first.pending
    resumed = _advance(runtime, 100.45)
    assert resumed.values[0] == pytest.approx(1.0 - math.exp(-1.0))


@pytest.mark.parametrize('growth', [(0.0,) * 7, (0.0,) * 9, (float('nan'),) * 8, (-0.1,) * 8, (1.1,) * 8])
def test_typed_growth_rejects_invalid_payload(growth):
    with pytest.raises(ValueError):
        ShockwaveGridFrame(terrain_growth=growth)


def test_typed_frame_detaches_growth_and_rerender_reads_cannot_advance():
    values = [0.25] * 8
    frame = ShockwaveGridFrame(terrain_growth=values)
    values[0] = 1.0
    assert frame.terrain_growth == (0.25,) * 8
    with pytest.raises(FrozenInstanceError):
        frame.terrain_growth = (1.0,) * 8
    assert replace(frame).terrain_growth == frame.terrain_growth


def test_real_family_capture_uses_resolved_bars_and_marks_growth_only_updates(monkeypatch):
    from widgets.spotify_visualizer import logical_frame_capture as capture

    runtime = ShockwaveGridFrameRuntime()
    controller = SimpleNamespace(mode_id='shockwave_grid', presentation_viewport_extent=(640, 400),
        resolve_logical_mode_state=lambda mode, factory: runtime,
        peek_logical_mode_state=lambda mode: runtime)
    widget = SimpleNamespace(runtime_controller=controller, _display_bars=(0.2, 0.6, 1.0, 0.8),
        _bar_count=4, _spectrum_visual_smoothing_enabled=False, _spectrum_visual_smoothing=0.0,
        _spectrum_single_piece=True, _spectrum_ghosting_enabled=False, _spectrum_ghost_decay=0.5)
    parameters = {'shockwave_grid_scroll': 0.0, 'shockwave_grid_idle': 0.0,
                  'shockwave_grid_terrain_reactivity': 0.5,
                  'shockwave_grid_terrain_growth_attack': 0.35, 'shockwave_grid_terrain_growth_release': 1.2}
    monkeypatch.setattr(capture.config_applier, 'shockwave_grid_parameters', lambda owner, now: parameters)
    monkeypatch.setattr(capture, '_base_extras', lambda *args: {})
    engine = SimpleNamespace(get_onset_events=lambda serial: (), get_musical_intensity=lambda: 0.0)
    def context(now, **kwargs):
        return capture._CaptureContext(now_ts=now, runtime_generation=1, engine_generation=2, activation_id=3,
            source_generation=kwargs.pop('source_generation', 2), source_activation_id=3, source_timestamp=now,
            playing=kwargs.pop('playing', True), first_frame=False, **kwargs)
    first, extra = capture._capture_shockwave_grid(widget, engine, context(10.0))
    assert isinstance(first, ShockwaveGridFrame) and first.terrain_growth == (0.0,) * 8
    assert runtime.terrain_growth_pending
    frame, extra = capture._capture_shockwave_grid(widget, engine, context(10.35))
    assert extra['_quick_mode_changed'] and max(frame.terrain_growth) > 0.0
    assert frame.events == ()  # continuous growth needs no water onset
    assert frame.terrain_growth[0] < frame.terrain_growth[-1]
    # A capture at the same authored time (e.g. a configuration rerender) cannot advance.
    again, extra = capture._capture_shockwave_grid(widget, engine, context(10.35))
    assert again.terrain_growth == frame.terrain_growth and not extra['_quick_mode_changed']
    parameters['shockwave_grid_terrain_reactivity'] = 0.0
    disabled, extra = capture._capture_shockwave_grid(widget, engine, context(10.45))
    assert disabled.terrain_growth == (0.0,) * 8 and not runtime.terrain_growth_pending
    assert not extra['_quick_mode_changed'] and disabled.animation_time == again.animation_time
    parameters['shockwave_grid_terrain_reactivity'] = 0.5
    resumed, extra = capture._capture_shockwave_grid(widget, engine, context(10.5))
    assert resumed.terrain_growth == (0.0,) * 8 and not extra['_quick_mode_changed']
    frame, extra = capture._capture_shockwave_grid(widget, engine, context(10.85))
    assert max(frame.terrain_growth) > 0.0 and extra['_quick_mode_changed']
    paused, extra = capture._capture_shockwave_grid(widget, engine, context(11.2, playing=False))
    assert max(paused.terrain_growth) < max(frame.terrain_growth)
    assert max(extra['_quick_resolved_bars']) > 0.0  # Spectrum idle is not musical growth
    stale, extra = capture._capture_shockwave_grid(widget, engine, context(11.3, source_generation=1))
    assert stale.terrain_growth == (0.0,) * 8
    controller.mode_id = 'sphere'
    assert capture._capture_shockwave_grid(widget, engine, context(11.4)) is None
