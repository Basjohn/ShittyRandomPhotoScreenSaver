"""Seamless Studio clips: the audio seam, the wrap through every Studio's evaluator, and the budgeted replay across it.

The shipped clips (``tools/build_studio_clips.py``) are loops: searched loop points and a crossfade baked into the
capture stream, so the first frame follows the last as the recording's own next moment. The Studio plays on through
the wrap (``ui/studio/clip_loop.py``): its evaluators step their production logic over the clip's ticks again, shifted
whole periods, instead of restarting at zero. Proven here:

* the audio: the loop's capture stream is periodic, its join is the source's own continuation, the level, spectral
  flux and beat grid pass through it as they do inside the loop (a hard cut of the same loop is the control);
* the picture: for every recorded-input family (Bubble, Sphere, Extruded Bubble, Waveform and the engine-answer modes),
  the frame step across the wrap is as ordinary as any other step; the old restart at zero (the control) is not;
* the exact replay: a rewind deep into a run replays one pass, its checkpoints stay bounded, and a budgeted replay
  across the wrap converges to the unbudgeted frame;
* the analysis: a worker primed with the loop's end records the lanes a running loop has, not a cold start.
"""
from __future__ import annotations

import json
import types
from pathlib import Path

import numpy as np
import pytest

from tools import studio_clip_loop_wrap as wrap

ROOT = Path(__file__).resolve().parents[1]
CLIPS = ROOT / "assets" / "production" / "studio_clips"
CLIP = "growing_pains"                 # the strongest groove of the three, and the shortest to analyse


def _manifest():
    return {entry["id"]: entry for entry in json.loads((CLIPS / "clips.json").read_text(encoding="utf-8"))["clips"]}


def _values():
    return wrap.values()


# ----------------------------------------------------------------------------------------------- audio
@pytest.mark.parametrize("clip_id", ["rag_doll", "human", "growing_pains"])
def test_a_loop_clip_is_periodic_and_joins_the_sources_own_continuation(clip_id):
    from tools.studio_clip_loop import histories_follow_the_loop
    from widgets.spotify_visualizer.compact_clip import load_feature_clip, read_header
    path = CLIPS / (clip_id + ".srclip")
    loop = read_header(path)["provenance"]["loop"]
    frames = load_feature_clip(path).frames
    assert len(frames) == loop["frames"]
    # Periodic: every frame's capture history (the first frame's included, which holds the loop's last samples) is
    # the one periodic stream read up to the frame's position.
    assert histories_follow_the_loop(frames, loop["period_samples"])
    # The period the frames name is the period the audio has (the frame clock and the sample clock agree to ~1 frame).
    spacing = float(np.mean(np.diff([f.timestamp_us for f in frames]))) / 1e6
    assert abs((frames[-1].timestamp_us - frames[0].timestamp_us) / 1e6 + spacing - loop["period_s"]) < 0.03
    assert abs(loop["period_samples"] / 48000.0 - loop["period_s"]) < 0.03
    # No click: the sample step across the seam is the source's own step, and the last 5 ms are the source's.
    measured = loop["measured"]
    assert measured["join_error_db"] < -30.0
    assert measured["step_loop"] == pytest.approx(measured["step_source"], rel=0.05, abs=1e-4)
    # The crossfade holds the level of an equal-power blend of its two sources.
    assert measured["level_deviation_db"] < 0.5


@pytest.mark.parametrize("clip_id", ["rag_doll", "human", "growing_pains"])
def test_level_flux_and_beat_grid_pass_through_the_seam_as_they_do_inside_the_loop(clip_id):
    from tools.studio_clip_loop_report import report_clip
    report = report_clip(CLIPS / (clip_id + ".srclip"))
    seam = report["seam"]
    assert seam["rms"]["within"]                                   # the level changes no more than the music does
    assert seam["flux"]["after_seam"] <= seam["flux"]["p95"]       # no spectral burst after the join
    beat = seam["beat"]
    assert abs(beat["jump_ms"]) <= beat["interior_p95_ms"]         # the beat grid steps no more than inside the loop


def test_the_control_a_clip_cut_short_of_its_period_is_not_periodic():
    """The periodic test above must fail for a restart: a period that ends where the crossfade starts (a hard cut)
    does not match the frames' histories."""
    from tools.studio_clip_loop import histories_follow_the_loop
    from widgets.spotify_visualizer.compact_clip import load_feature_clip, read_header
    path = CLIPS / "human.srclip"
    loop = read_header(path)["provenance"]["loop"]
    frames = load_feature_clip(path).frames
    cut = loop["period_samples"] - int(round(loop["crossfade_s"] * 48000))
    assert not histories_follow_the_loop(frames, cut)


def test_the_manifest_describes_the_loops_it_ships():
    from widgets.spotify_visualizer.compact_clip import read_header
    for clip_id, entry in _manifest().items():
        header = read_header(CLIPS / entry["file"])
        assert header["provenance"]["loop"] == entry["loop"]
        assert entry["seconds"] == pytest.approx(entry["loop"]["period_s"], abs=1e-3)
        assert 10.0 <= entry["seconds"] <= 20.0


# ----------------------------------------------------------------------------------------------- transport
def test_the_transport_counts_its_passes_and_hands_a_loop_its_unrolled_time():
    from ui.studio.transport import StudioTransport
    now = [0.0]
    transport = StudioTransport(2.0, clock=lambda: now[0])
    transport.play()
    transport.on_frame()
    for _ in range(50):
        now[0] += 0.1
        transport.on_frame()
    assert transport.cycles == 2 and transport.time < 2.0
    assert transport.unrolled == pytest.approx(2.0 * transport.cycles + transport.time)
    assert transport.evaluation_time(True) == transport.unrolled
    assert transport.evaluation_time(False) == transport.time          # a clip that is not a loop: its own time
    transport.seek(0.5)
    assert transport.cycles == 0 and transport.unrolled == 0.5


def test_the_controller_asks_a_loop_for_unrolled_time():
    from ui.studio.controller import StudioController
    from ui.studio.transport import StudioTransport
    transport = StudioTransport(3.0)
    transport.cycles, transport.time = 4, 1.0
    for loop, expected in ((True, 13.0), (False, 1.0)):
        stub = types.SimpleNamespace(transport=transport, evaluator=types.SimpleNamespace(
            fixture=types.SimpleNamespace(loop=loop)))
        assert StudioController.evaluation_time(stub) == expected


# ----------------------------------------------------------------------------------------------- ticks
def _onset_serials(value) -> list:
    if isinstance(value, dict):
        if value.get("data") == "MusicalOnset":
            return [value["fields"]["serial"]]
        return [s for item in value.values() for s in _onset_serials(item)]
    if isinstance(value, list):
        return [s for item in value for s in _onset_serials(item)]
    return []


def test_later_passes_move_whole_periods_on_and_keep_onsets_increasing(qt_app):
    from ui.studio import clip_loop
    inputs = wrap.recorded_inputs("oscilloscope", CLIP)
    ticks = clip_loop.unrolled_ticks(inputs, inputs.fixture.duration)
    n = ticks.per_pass
    times = [ticks[i].now for i in range(3 * n)]
    assert all(b > a for a, b in zip(times, times[1:]))                 # strictly increasing through two wraps
    assert times[n] - times[0] == pytest.approx(inputs.period)
    serials = []
    for i in range(3 * n):
        for key, value in ticks[i].answers.items():
            if key.startswith("get_onset_events"):
                serials += _onset_serials(value)
    assert serials == sorted(serials) and len(set(serials)) == len(serials) and serials
    # the query's own argument (the runtime's last-seen serial) moves with them
    firsts = [int(k.split("[[")[1].split("]")[0]) for k in ticks[0].answers if k.startswith("get_onset_events")]
    shifted = [int(k.split("[[")[1].split("]")[0]) for k in ticks[n].answers if k.startswith("get_onset_events")]
    assert shifted[0] == firsts[0] + inputs._span > firsts[0]


# ----------------------------------------------------------------------------------------------- the picture
@pytest.mark.parametrize("family", sorted(wrap.FAMILIES))
def test_the_preview_passes_through_the_wrap_without_a_jump(qt_app, family):
    """Every Studio with recorded inputs: the step across the wrap is as ordinary as any other, and the old wrap (the
    transport's time restarting at zero) is the control that is not."""
    probe = wrap.probe(family, CLIP)
    carried, restart = probe["carried"], probe["restart"]
    assert carried["wrap"] <= 1.25 * carried["p95"]              # as ordinary as the steps around it
    assert carried["after_wrap_moves"]                           # and the preview plays on after it (not frozen)
    assert restart["wrap"] > 2.0 * restart["p95"]                # the restart at zero is a visible event
    assert restart["wrap"] > 3.0 * carried["wrap"]


# ----------------------------------------------------------------------------------------------- exact replay
def test_a_rewind_deep_into_a_run_replays_one_pass_and_the_checkpoints_stay_bounded(qt_app):
    values = _values()
    evaluator, inputs = wrap.evaluator_for("waveform", CLIP)
    period = inputs.fixture.duration
    per_pass = len([t for t in inputs.steps(period) if t.now >= inputs._origin])
    for k in range(1, 61):                       # 6+ passes in 1 s hops
        evaluator.evaluate(k * 1.2, values, exact=True)
    kept = sum(len(v) for v in evaluator._checkpoints.values())
    assert kept <= 3 * (2 * per_pass // evaluator.CHECKPOINT_TICKS + 3)
    # An edit forty passes in replays the pass the instant is in, not the forty before it.
    key = next(k for k, v in values.items() if k.startswith("waveform_ribbon_") and isinstance(v, float))
    edited = dict(values)
    edited[key] = float(values[key]) * 0.5 + 0.01
    before = evaluator.steps_run
    evaluator.evaluate(evaluator._unrolled + 0.5, edited, exact=True)
    assert 0 < evaluator.steps_run - before <= per_pass + 400
    # And so does a history that starts there (an extent change, new answers).
    fresh, _ = wrap.evaluator_for("waveform", CLIP)
    fresh.evaluate(40 * period + 3.0, values, exact=True)
    assert fresh.steps_run <= per_pass + 400


def test_a_budgeted_replay_across_the_wrap_converges_to_the_unbudgeted_frame(qt_app):
    values = _values()
    evaluator, inputs = wrap.evaluator_for("waveform", CLIP)
    period = inputs.fixture.duration
    at = 2.0 * period + 1.0
    # play to the instant carrying state, then change the values: the replay restarts at the pass the instant is in
    for k in range(1, int(at / 0.9)):
        evaluator.evaluate(k * 0.9, values, exact=True)
    edited = dict(values)
    key = next(k for k, v in values.items() if k.startswith("waveform_ribbon_") and isinstance(v, float))
    edited[key] = float(values[key]) * 0.5 + 0.01
    rewinds = evaluator.rewinds
    evaluator.set_frame_budget(0.0005)
    frame, rounds = None, 0
    while True:
        frame = evaluator.evaluate(at, edited, exact=True)
        rounds += 1
        if not evaluator.converging:
            break
        assert rounds < 5000
    assert rounds > 1 and evaluator.rewinds > rewinds       # it really replayed, spread over frames
    fresh, _ = wrap.evaluator_for("waveform", CLIP)
    expected = fresh.evaluate(at, edited, exact=True)
    assert wrap.state_map(frame) == wrap.state_map(expected)


# ----------------------------------------------------------------------------------------------- the analysis
def test_a_worker_primed_with_the_loops_end_records_the_lanes_of_a_running_loop(qt_app, monkeypatch):
    from ui.studio import bubble_recorded_inputs as worker, clip_loop
    from widgets.spotify_visualizer.compact_clip import load_feature_clip
    path = CLIPS / (CLIP + ".srclip")
    frames = load_feature_clip(path).frames
    period = clip_loop.loop_period(path)
    start = frames[0].timestamp_us / 1e6
    values = _values()

    def lanes(data, after):
        rows = [s for s in data["steps"] if s["now_ts"] >= after - 1e-9]
        return np.array([s["bubble"] + s["transient"][:3] for s in rows])
    running = worker.extract(path, values, features=clip_loop.tiled_features(frames, period, 3), seconds=None)
    steady = lanes(running, start + 2 * period)                              # the third pass of an unbroken run
    primed = lanes(worker.extract(path, values), start)
    n = min(len(primed), len(steady))
    assert np.abs(primed[:n] - steady[:n]).sum(1).mean() < 1e-3
    # The control: without the lead-in the first second is the engine's cold start.
    monkeypatch.setattr(clip_loop, "PREROLL_S", 0.0)
    cold = lanes(worker.extract(path, values), start)
    assert np.abs(cold[:90] - steady[:90]).sum(1).mean() > 0.05


def test_a_clip_re_analysed_deep_into_a_run_lands_at_the_same_instant_in_one_pass(qt_app):
    """An engine-owned edit re-analyses the clip; its new inputs replace the old at the transport's instant
    (``add_recorded`` and ``select``) and the history starts at the pass that instant is in, not at pass zero."""
    values = _values()
    evaluator, inputs = wrap.evaluator_for("bubble", CLIP)
    period = inputs.fixture.duration
    per_pass = len(list(inputs.steps(period)))
    at = 4.0 * period + 1.0
    for k in range(1, int(at / 1.1)):
        evaluator.evaluate(k * 1.1, values, exact=True)
    evaluator.evaluate(at, values, exact=True)
    before = evaluator.steps_run
    evaluator.add_recorded(inputs)                      # the re-analysed inputs (here the same record)
    evaluator.select(inputs.fixture.id)
    frame = evaluator.evaluate(at, values, exact=True)
    assert 0 < evaluator.steps_run - before <= per_pass
    assert frame is not None
