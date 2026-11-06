"""DevCurve kicks keep their response in continuous play (operator, 5 Nov: adaptive gain on Waveform muted
kicks/beats ~30 s into a sustained passage; "you likely did not check later in the songs from continuous play").

The production frame runtime plays, without any reset, a quieter verse and then a long sustained loud chorus: the
same kick every 0.5 s over a steady bed, with an occasional bigger accent (a crash). A lockstep twin plays the same
verse, chorus, passage and loudness with no flux spikes, so the passage's own ramps (the chorus entry eases the swing
up over seconds, the body follows the loudness) cancel out of the comparison. A kick's visible response is the rise
of the live-minus-twin reaction (the drawn undulation's amplitude as a share of its geometric ceiling: the solver's
published ``reaction_*``, height x travelling swell) within 150 ms of the kick over its mean in the 300 ms before,
with the swell ON at the shipped presets' strength (lead review, 6 Nov: switching it off hid the muting the operator
complained about). Kicks 40-55 s into the chorus must respond at least ~85% as much as the same kicks near its start,
and a kick in the sustained chorus must stay clearly visible. Test-owned settings; structure only."""
from __future__ import annotations

import numpy as np

import widgets.spotify_visualizer.devcurve_runtime as devcurve
from widgets.spotify_visualizer.devcurve_frame_runtime import DevCurveFrameRuntime
from widgets.spotify_visualizer.render_state import VisualizerEnergyState, VisualizerTransientState
from tests.test_qtquick_visualizer_devcurve import _nodes, _parameters

DT = 1 / 60           # a coarser logical clock keeps the minute of play quick; every response is timed in seconds
PERIOD = 0.5          # a kick every half second
KICK = 0.06           # seconds a kick lasts at the bus
VERSE = 8.0           # seconds of quieter verse before the chorus
VERSE_BED, VERSE_HIT = 5.0, 8.0
BED, HIT, CRASH = 9.0, 14.0, 18.0
_BODY = ("bass", "vocals", "mids")


def _play(chorus=56.0):
    """(time into the chorus, is a plain chorus kick, per-layer reaction live - twin) for every tick of play."""
    runtime, twin, rows, params = DevCurveFrameRuntime(), DevCurveFrameRuntime(), [], {**_parameters(), "devcurve_swell_strength": 1.0}
    for index in range(round((VERSE + chorus) / DT)):
        t = index * DT
        beat = int(t / PERIOD)
        on = (t - beat * PERIOD) < KICK
        chorus_now = t >= VERSE
        bed = BED if chorus_now else VERSE_BED
        if chorus_now:
            loud = (CRASH if beat % 16 == 7 else HIT) if on else BED
        else:
            loud = VERSE_HIT if on else VERSE_BED
        common = dict(
            now_ts=50.0 + t, runtime_generation=1, engine_generation=1, activation_id=1, source_generation=1,
            source_activation_id=1, source_timestamp=50.0 + t, playing=True,
            musical_intensity=0.9 if chorus_now else 0.4, layer_shape_nodes=_nodes(), parameters=params,
            energy=VisualizerEnergyState(bass=1.0, mid=0.8, high=0.4, overall=0.8))
        live = runtime.advance(musical_level=(loud, 1.0), transient=VisualizerTransientState(
            bass=0.9 if on else 0.03, mid=0.4 if on else 0.03, high=0.1), **common)
        rest = twin.advance(musical_level=(loud, 1.0), transient=VisualizerTransientState(
            bass=0.03, mid=0.03, high=0.1), **common)
        drives, still = live.diagnostics["drives"], rest.diagnostics["drives"]
        rows.append((t - VERSE, chorus_now and on and (t - beat * PERIOD) < DT / 2 and beat % 16 != 7,
                     {key: float(drives[f"reaction_{key}"] - still[f"reaction_{key}"]) for key in _BODY},
                     float(drives["reaction_bass"])))
    return rows


def _response(rows, start, stop, layers=_BODY):
    times = np.asarray([row[0] for row in rows])
    out = []
    for t, kick, _, _ in rows:
        if not kick or not start <= t < stop:
            continue
        before = [rows[j][2] for j in np.nonzero((times >= t - 0.3) & (times < t))[0]]
        after = [rows[j][2] for j in np.nonzero((times >= t) & (times <= t + 0.15))[0]]
        out.append(np.mean([max(a[key] for a in after) - np.mean([b[key] for b in before]) for key in layers]))
    return float(np.mean(out))


def _early_late(rows=None):
    rows = _play() if rows is None else rows
    early = _response(rows, 1.5, 5.0)       # near the start, once the chorus has entered (~1 s)
    late = _response(rows, 40.0, 55.0)
    level = np.mean([row[3] for row in rows if 40.0 <= row[0] < 55.0])
    return early, late, level


def test_kicks_late_in_a_sustained_passage_respond_like_kicks_near_its_start():
    rows = _play()
    early, late, level = _early_late(rows)
    assert late >= 0.85 * early, (late, early)
    # No layer fades as the passage goes on: once the chorus has settled (passage ease, swell bed), each layer's
    # kick 40-55 s in responds like the same kick 6-12 s in.
    for key in _BODY:
        settled, later = _response(rows, 6.0, 12.0, (key,)), _response(rows, 40.0, 55.0, (key,))
        assert later >= 0.9 * settled, (key, later, settled)
    # Visible, not merely proportional: a sustained-chorus kick lifts the undulation by a clear share of its level
    # (normalising the beats by the passage's remembered peak left ~2% of the level here).
    assert late > 0.025 * level, (late, level)


def test_negative_control_normalising_the_beats_mutes_sustained_passage_kicks(monkeypatch):
    """The first cut: the whole height (beats included) through the fast stages and divided by the remembered
    peak, no accents. The same measurement must see its sustained-chorus kicks fade or vanish."""
    monkeypatch.setattr(devcurve, "DEVCURVE_BODY_STAGE_S", devcurve.DEVCURVE_SWING_STAGE_S)
    monkeypatch.setattr(devcurve, "DEVCURVE_ACCENT_ROOM", dict.fromkeys(devcurve.DEVCURVE_ACCENT_ROOM, 0.0))
    monkeypatch.setattr(devcurve, "DEVCURVE_BODY_TOP", dict.fromkeys(devcurve.DEVCURVE_BODY_TOP, 0.95))
    early, late, level = _early_late()
    assert late < 0.85 * early or late <= 0.025 * level, (late, early, level)
