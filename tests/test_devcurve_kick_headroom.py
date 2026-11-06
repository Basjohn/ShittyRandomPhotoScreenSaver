"""DevCurve bass shows its kicks in a sustained loud passage even where the authored power puts the layer at its
geometric cap (lead review, 6 Nov 2026: "bass barely moving on kicks is a defect, not an artistic call. The kick is
bass").

A layer with a large authored power (test-owned: Bass Power 3 at Motion Power 1.72, as strong as the shipped presets
go) plays a long sustained loud passage with a kick every 0.5 s. Its body alone would drive the undulation past the
drawn ceiling (the smoothness slope limiter). The kick's visible response is the rise of the bass curve's
peak-to-trough height within 150 ms of the kick over its mean in the 300 ms before, 20-30 s into the passage, and
it must be delivered by the curve, not by the limiter: the curve may ride the slope limiter on only a minority of
ticks (straight runs at the limit are the cap the lead measured on 76-89% of ticks).

Negative controls (same measurement, the mapping swapped):
* pre-headroom (07d1afd1 and earlier): amplitude = authored unit x drive x swell straight into the limiter -> the
  curve rides the limiter on most ticks;
* the paused WIP (c0ca4ffa): body compressed into 0.65 of the ceiling, the accent added on top, then the TOTAL
  soft-capped near the ceiling -> the steady accent fills the cap and the kick barely shows.
Structure only: no preset values."""
from __future__ import annotations

import numpy as np

import widgets.spotify_visualizer.devcurve_runtime as devcurve
from widgets.spotify_visualizer.devcurve_frame_runtime import DevCurveFrameRuntime
from widgets.spotify_visualizer.render_state import VisualizerEnergyState, VisualizerTransientState
from tests.test_qtquick_visualizer_devcurve import _nodes, _parameters

DT = 1 / 60
PERIOD, KICK = 0.5, 0.06
BED, HIT = 9.0, 14.0
_VISIBLE = 0.012        # the kick lifts the bass curve's peak-to-trough height by at least this share of the view
_MOSTLY = 0.5


def _kick_rise(seconds=30.0):
    """(mean kick rise of the bass curve's peak-to-trough height 20-30 s in, share of those ticks slope-limited)."""
    params = {**_parameters(), "devcurve_layer_bass_power": 3.0, "devcurve_motion_power": 1.72}
    max_step = 0.040 - 0.020 * min(1.0, max(0.0, float(params["devcurve_smoothness"])))
    runtime = DevCurveFrameRuntime()
    times, height, kicks, limited = [], [], [], []
    for index in range(round(seconds / DT)):
        t = index * DT
        phase = t - int(t / PERIOD) * PERIOD
        on = phase < KICK
        frame = runtime.advance(
            now_ts=50.0 + t, runtime_generation=1, engine_generation=1, activation_id=1, source_generation=1,
            source_activation_id=1, source_timestamp=50.0 + t, playing=True, musical_intensity=0.9,
            musical_level=(HIT if on else BED, 1.0), layer_shape_nodes=_nodes(), parameters=params,
            energy=VisualizerEnergyState(bass=1.0, mid=0.8, high=0.4, overall=0.8),
            transient=VisualizerTransientState(bass=0.9 if on else 0.03, mid=0.4 if on else 0.03, high=0.1))
        curve = np.asarray(dict(frame.curves)["bass"])
        times.append(t)
        height.append(float(np.ptp(curve)))
        kicks.append(phase < DT / 2)
        limited.append(bool((np.abs(np.diff(curve)) >= 0.97 * max_step).any()))
    times, height = np.asarray(times), np.asarray(height)
    rises = []
    for i in np.nonzero(kicks)[0]:
        if 20.0 <= times[i] < seconds - 0.2:
            before = height[(times >= times[i] - 0.3) & (times < times[i])]
            after = height[(times >= times[i]) & (times <= times[i] + 0.15)]
            rises.append(after.max() - before.mean())
    return float(np.mean(rises)), float(np.mean(np.asarray(limited)[times >= 20.0]))


def _visible_without_the_limiter(rise, limited):
    return rise > _VISIBLE and limited < _MOSTLY


def test_bass_kicks_show_in_a_sustained_loud_passage_at_the_authored_cap():
    rise, limited = _kick_rise()
    assert _visible_without_the_limiter(rise, limited), (rise, limited)


def test_negative_control_pre_headroom_mapping_rides_the_limiter(monkeypatch):
    monkeypatch.setattr(devcurve, "reaction_amplitudes",
                        lambda unit, body, accent, bed, ceiling, key, fresh=0.0:
                        unit * ((body + accent) * (1.0 + bed + fresh)))
    rise, limited = _kick_rise()
    assert not _visible_without_the_limiter(rise, limited), (rise, limited)


def test_negative_control_capping_the_total_squashes_the_kick(monkeypatch):
    def capped_total(unit, body, accent, bed, ceiling, key, fresh=0.0):
        gain = 1.0 + bed + fresh
        body_amp = devcurve._soft_ceiling(unit * (body * gain), 0.65 * ceiling, 0.6)
        return devcurve._soft_ceiling(body_amp + unit * (accent * gain), 1.15 * ceiling, 0.9 / 1.15)

    monkeypatch.setattr(devcurve, "reaction_amplitudes", capped_total)
    rise, limited = _kick_rise()
    assert not _visible_without_the_limiter(rise, limited), (rise, limited)
