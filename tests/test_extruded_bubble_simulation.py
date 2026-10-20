"""Extruded Bubble's own logical simulation (``widgets/spotify_visualizer/extruded_bubble_simulation.py``): pure,
deterministic, driven only by the inputs it is given (no Qt, GL or clock of its own). Control values here are the
test's own, never presets or defaults."""
from __future__ import annotations

import math

import pytest

from widgets.spotify_visualizer.extruded_bubble_simulation import (
    BUBBLE_STRIDE,
    CLUSTER_STRIDE,
    MAX_BUBBLES,
    ExtrudedBubbleControls,
    ExtrudedBubbleSimulation,
    MusicInput,
    stream_vector,
)

STEP = 1.0 / 60.0


def _music(dt, playing, intensity=0.0, onsets=()):
    """Synthetic bands explicitly enter the same input branch as production."""
    return MusicInput(dt, playing, intensity, onsets, (intensity,) * 3)


def _run(simulation, controls, seconds, *, intensity=0.5, onsets_every=0.0, kind="kick"):
    snapshot = None
    steps = int(round(seconds / STEP))
    for i in range(steps):
        onsets = ((kind, 1.0),) if onsets_every and i % int(onsets_every / STEP) == 0 else ()
        snapshot = simulation.advance(_music(STEP, True, intensity, onsets), controls)
    return snapshot


def _records(snapshot):
    values = snapshot.bubbles
    return [values[i:i + BUBBLE_STRIDE] for i in range(0, len(values), BUBBLE_STRIDE)]


def test_the_same_inputs_give_the_same_frames():
    controls = ExtrudedBubbleControls()
    first = _run(ExtrudedBubbleSimulation(7), controls, 4.0, onsets_every=0.5)
    second = _run(ExtrudedBubbleSimulation(7), controls, 4.0, onsets_every=0.5)
    assert first == second
    other = _run(ExtrudedBubbleSimulation(8), controls, 4.0, onsets_every=0.5)
    assert other.bubbles != first.bubbles


def test_the_population_follows_the_passage_between_its_quiet_and_loud_counts():
    controls = ExtrudedBubbleControls(large_count=(4.0, 12.0), mid_count=(10.0, 40.0), collision_scope="off")

    def live(snapshot, large):
        return sum(1 for r in _records(snapshot) if r[4] > 0.5 and ((r[3] >= 0.07) == large))

    simulation = ExtrudedBubbleSimulation(3)
    quiet = _run(simulation, controls, 12.0, intensity=0.0)
    assert 9 <= len(_records(quiet)) <= 22                     # about 4 + 10
    loud = _run(simulation, controls, 25.0, intensity=1.0)
    assert 40 <= len(_records(loud)) <= MAX_BUBBLES             # grew toward 12 + 40, upstream, never a burst
    assert loud.level > 0.9 and quiet.level < 0.1


def test_bubbles_travel_along_the_stream_direction_and_stay_near_the_volume():
    for around, height in ((0.0, 0.0), (90.0, 0.0), (35.0, 30.0)):
        controls = ExtrudedBubbleControls(stream_direction=(around, height), drift=(0.0, 0.0), sway=0.0,
                                          collision_scope="off")
        simulation = ExtrudedBubbleSimulation(11)
        before = {r[6]: r[:3] for r in _records(_run(simulation, controls, STEP))}
        after = {r[6]: r[:3] for r in _records(_run(simulation, controls, 1.0))}
        shared = [k for k in before if k in after]
        dx = sum(after[k][0] - before[k][0] for k in shared) / len(shared)
        dy = sum(after[k][1] - before[k][1] for k in shared) / len(shared)
        dz = sum(after[k][2] - before[k][2] for k in shared) / len(shared)
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        expected = stream_vector(around, height)
        assert sum(a * b for a, b in zip((dx / length, dy / length, dz / length), expected)) > 0.99
        for x, y, z, radius, *_rest in _records(_run(simulation, controls, 10.0)):
            assert abs(x) <= 1.6 and abs(y) <= 1.6 and -0.4 <= z <= 1.4


def test_kicks_make_the_large_bubbles_breathe_and_smoothing_softens_the_release():
    controls = ExtrudedBubbleControls(breathing=(0.1, 0.3), collision_scope="off")
    simulation = ExtrudedBubbleSimulation(5)
    calm = _run(simulation, controls, 3.0)
    large_ids = {b.ident for b in simulation._bubbles if b.large}
    kicked = simulation.advance(_music(STEP, True, 0.5, (("kick", 1.0),)), controls)
    assert kicked.breath > calm.breath + 0.5
    baseline = {int(r[6]): r[5] for r in _records(calm) if int(r[6]) in large_ids}
    for _ in range(12):
        kicked = simulation.advance(_music(STEP, True, 0.5), controls)
    changes = [r[5] - baseline[int(r[6])] for r in _records(kicked) if int(r[6]) in baseline]
    assert changes and min(changes) > 0.1  # eased onset growth, not a positive-only radius floor
    soft = ExtrudedBubbleSimulation(5)
    snappy = ExtrudedBubbleSimulation(5)
    for sim, smoothing in ((soft, 1.0), (snappy, 0.0)):
        c = ExtrudedBubbleControls(breathing=(0.1, 0.3), collision_scope="off", smoothing=smoothing)
        _run(sim, c, 3.0)
        sim.advance(_music(STEP, True, 0.5, (("kick", 1.0),)), c)
    after_soft = _run(soft, ExtrudedBubbleControls(collision_scope="off", smoothing=1.0), 0.3)
    after_snappy = _run(snappy, ExtrudedBubbleControls(collision_scope="off", smoothing=0.0), 0.3)
    assert after_soft.breath > after_snappy.breath


def _crowded(collision, scope="all"):
    return ExtrudedBubbleControls(large_count=(20.0, 20.0), mid_count=(60.0, 60.0), collision=collision,
                                  collision_scope=scope, stream_speed=(0.1, 0.1))


def test_only_fuse_joins_bubbles_into_clusters_of_at_most_three():
    snapshot = _run(ExtrudedBubbleSimulation(2), _crowded((1.0, 0.0, 0.0)), 6.0)
    clusters = [snapshot.clusters[i:i + CLUSTER_STRIDE] for i in range(0, len(snapshot.clusters), CLUSTER_STRIDE)]
    assert clusters
    assert all(2 <= c[0] <= 3 for c in clusters)
    records = _records(snapshot)
    for c in clusters:                                     # members point back at their cluster and touch
        members = [records[int(i)] for i in c[1:1 + int(c[0])]]
        assert len({m[7] for m in members}) == 1 and members[0][7] >= 0
    none = _run(ExtrudedBubbleSimulation(2), _crowded((0.0, 0.0, 1.0)), 6.0)
    assert none.clusters == ()


def test_only_pop_fades_bubbles_out_and_only_bounce_leaves_nothing_overlapping():
    popping = ExtrudedBubbleSimulation(4)
    seen_pop = False
    controls = _crowded((0.0, 1.0, 0.0))
    for _ in range(int(6.0 / STEP)):
        snapshot = popping.advance(_music(STEP, True, 0.5, ()), controls)
        seen_pop = seen_pop or any(0.0 < r[4] < 1.0 and r[3] > 0 for r in _records(snapshot))
    assert seen_pop and snapshot.clusters == ()
    bouncing = _run(ExtrudedBubbleSimulation(4), _crowded((0.0, 0.0, 1.0)), 6.0)
    records = [r for r in _records(bouncing) if r[4] > 0.9]
    overlaps = 0
    for i, a in enumerate(records):
        for b in records[i + 1:]:
            if math.dist(a[:3], b[:3]) < (a[3] + b[3]) * 0.6:
                overlaps += 1
    assert overlaps <= 2                                   # pushed apart (a fresh arrival may just be meeting)


def test_collision_off_lets_bubbles_pass_through_and_scope_picks_who_collides():
    passing = _run(ExtrudedBubbleSimulation(4), _crowded((1.0, 0.0, 0.0), scope="off"), 6.0)
    assert passing.clusters == () and all(r[7] == -1.0 for r in _records(passing))
    big_only = _run(ExtrudedBubbleSimulation(4), _crowded((1.0, 0.0, 0.0), scope="big"), 8.0)
    records = _records(big_only)
    for c in (big_only.clusters[i:i + CLUSTER_STRIDE] for i in range(0, len(big_only.clusters), CLUSTER_STRIDE)):
        for slot in c[1:1 + int(c[0])]:
            assert records[int(slot)][3] >= 0.06          # only large bubbles fused


def test_silence_keeps_a_gentle_idle_and_reset_starts_over():
    simulation = ExtrudedBubbleSimulation(9)
    idle = None
    for _ in range(120):
        idle = simulation.advance(_music(STEP, False), ExtrudedBubbleControls())
    assert idle.count > 0 and idle.level == 0.0 and idle.stream_speed > 0.0
    simulation.reset()
    assert simulation.time == 0.0
    restarted = simulation.advance(_music(STEP, False), ExtrudedBubbleControls())
    fresh = ExtrudedBubbleSimulation(9).advance(_music(STEP, False), ExtrudedBubbleControls())
    assert restarted == fresh


# --- the frame runtime ------------------------------------------------------------------------------------------

def _onset(serial, kind="kick", magnitude=1.5, loudness=12.0, presence=1.0):
    from widgets.spotify_visualizer.transient_bus import MusicalOnset
    return MusicalOnset(serial, 0.0, kind, 1.0, magnitude, loudness, presence)


def _capture(runtime, now, onsets=(), *, identity=(1, 2, 3), source=(2, 3), playing=True):
    return runtime.advance(onsets=onsets, now_ts=now, playing=playing, intensity=0.6, identity=identity,
                           source_identity=source, controls=ExtrudedBubbleControls(), body_bands=(0.6,) * 3)


def test_the_runtime_steps_on_logical_time_takes_each_onset_once_and_fences_activations():
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import ExtrudedBubbleFrameRuntime, MAX_STEP_SECONDS

    runtime = ExtrudedBubbleFrameRuntime(1)
    assert _capture(runtime, 100.0).time == 0.0                       # the first capture only starts the clock
    assert _capture(runtime, 100.05).time == pytest.approx(0.05)
    assert _capture(runtime, 105.0).time == pytest.approx(0.05 + MAX_STEP_SECONDS)   # a stall never leaps
    kicked = _capture(runtime, 105.02, (_onset(7),))
    assert kicked.breath > 0.5 and runtime.onset_serial == 7
    again = _capture(runtime, 105.04, (_onset(7),))                    # the same onset is not taken twice
    assert again.breath < kicked.breath
    quiet = _capture(runtime, 105.06, (_onset(8, loudness=0.1, presence=0.05),))
    assert runtime.onset_serial == 8 and quiet.breath < kicked.breath  # a near-silent onset barely counts
    # A new activation, or a clock that went back, starts over.
    assert _capture(runtime, 106.0, identity=(1, 2, 4), source=(2, 4)).time == 0.0
    _capture(runtime, 106.1, identity=(1, 2, 4), source=(2, 4))
    assert _capture(runtime, 50.0, identity=(1, 2, 4), source=(2, 4)).time == 0.0
    # A source that is not ready is silent: no level, no onsets.
    silent = [_capture(runtime, 50.0 + i * 0.05, (_onset(20 + i),), source=(9, 9), identity=(1, 2, 4)) for i in range(3)]
    assert silent[-1].level == 0.0 and silent[-1].breath < 0.2      # only the idle sway, no onsets taken
    runtime.retire()
    assert _capture(runtime, 60.0, identity=(1, 2, 4), source=(2, 4)) is None



def test_stream_speed_rises_quickly_decays_slowly_and_never_jumps_or_stops():
    controls = ExtrudedBubbleControls(stream_speed=(0.04, 0.2), collision_scope="off")
    simulation = ExtrudedBubbleSimulation(6)
    speeds = []
    for i in range(int(4.0 / STEP)):                               # quiet
        speeds.append(simulation.advance(_music(STEP, True, 0.0), controls).stream_speed)
    quiet = speeds[-1]
    for i in range(int(4.0 / STEP)):                               # a saturated passage with a hit every beat
        onsets = (("kick", 1.0),) if i % 30 == 0 else ()
        speeds.append(simulation.advance(_music(STEP, True, 1.0, onsets), controls).stream_speed)
    loud = speeds[-1]
    rise = next(i for i, s in enumerate(speeds[int(4.0 / STEP):]) if s > quiet + 0.6 * (loud - quiet))
    for i in range(int(6.0 / STEP)):                               # the music stops
        speeds.append(simulation.advance(_music(STEP, False), controls).stream_speed)
    assert loud > quiet * 2.5
    assert rise * STEP < 1.6                                       # quick attack
    one_second_later = speeds[int(8.0 / STEP) + int(1.0 / STEP)]
    assert one_second_later > quiet + 0.55 * (loud - quiet)        # slow decay: most of it still there after 1 s
    assert speeds[-1] > 0.0                                        # never a sudden stop
    steps = [abs(b - a) for a, b in zip(speeds, speeds[1:])]
    span = max(speeds) - min(speeds)
    assert max(steps) < 0.025 * span                               # no frame moves it by more than 2.5% of its span


def test_travel_is_the_distance_the_stream_carried_the_water_so_procedural_layers_never_jump():
    """The bead chains and snow move by ``travel`` (the integral of stream speed on the logical clock), not by time x
    the current speed: a change of speed changes how fast it grows, never where it is."""
    controls = ExtrudedBubbleControls(stream_speed=(0.04, 0.2), collision_scope="off")
    simulation = ExtrudedBubbleSimulation(6)
    previous = simulation.advance(_music(STEP, True, 0.0), controls)
    expected = previous.travel
    for i in range(int(6.0 / STEP)):
        intensity = 0.0 if i < 120 else 1.0                       # a sudden loud passage
        onsets = (("kick", 1.0),) if i % 30 == 0 else ()
        snapshot = simulation.advance(_music(STEP, True, intensity, onsets), controls)
        expected += snapshot.stream_speed * STEP
        assert snapshot.travel > previous.travel                  # always moving on
        assert snapshot.travel - previous.travel <= max(previous.stream_speed, snapshot.stream_speed) * STEP * 1.0001
        previous = snapshot
    assert previous.travel == pytest.approx(expected, rel=1e-9)

def _lane_offsets(snapshot, stream):
    """Each bubble's distance across the stream from its nearest lane."""
    ax, ay = -stream[1], stream[0]
    length = math.hypot(ax, ay)
    offsets = []
    for record in _records(snapshot):
        across = (record[0] * ax + record[1] * ay) / length
        offsets.append(abs(across - round(across / 0.26) * 0.26))
    return offsets


def test_columns_line_bubbles_up_along_the_stream():
    stream = stream_vector(40.0, 0.0)
    lined = ExtrudedBubbleControls(columns=1.0, stream_direction=(40.0, 0.0), drift=(0.0, 0.0), sway=0.0,
                                   collision_scope="off")
    loose = ExtrudedBubbleControls(columns=0.0, stream_direction=(40.0, 0.0), drift=(0.0, 0.0), sway=0.0,
                                   collision_scope="off")
    lined_offsets = _lane_offsets(_run(ExtrudedBubbleSimulation(9), lined, 0.5), stream)
    loose_offsets = _lane_offsets(_run(ExtrudedBubbleSimulation(9), loose, 0.5), stream)
    assert sum(lined_offsets) / len(lined_offsets) < 0.3 * sum(loose_offsets) / len(loose_offsets)


def test_the_rays_move_through_a_saturated_passage_rise_quickly_fall_slowly_and_never_stutter():
    """The passage level holds at 1 through loud music; the rays' driver must still move with its hits, stay below
    the top, and never step abruptly."""
    controls = ExtrudedBubbleControls(collision_scope="off")
    simulation = ExtrudedBubbleSimulation(5)
    quiet = _run(simulation, controls, 4.0, intensity=0.0)
    rays, shimmer = [], []
    for i in range(int(10.0 / STEP)):                               # saturated, a hit every 0.75 s
        onsets = (("kick", 1.0),) if i % 45 == 0 else ()
        snapshot = simulation.advance(_music(STEP, True, 1.0, onsets), controls)
        rays.append(snapshot.rays)
        shimmer.append(snapshot.shimmer)
    assert rays[int(0.6 / STEP)] > quiet.rays + 0.4                 # quick attack
    held = rays[int(4.0 / STEP):]
    assert max(held) < 1.0                                          # never on the top
    assert max(held) - min(held) > 0.04                             # still moving with the hits
    # Never a jump: even the quick attack out of silence takes several frames to cross a tenth of the range.
    assert max(abs(b - a) for a, b in zip(rays, rays[1:])) < 0.1
    assert all(b > a for a, b in zip(shimmer, shimmer[1:]))         # the shimmer runs on, never back
    loud = rays[-1]
    after = _run(simulation, controls, 1.0, intensity=0.0)
    assert after.rays > quiet.rays + 0.4 * (loud - quiet.rays)      # slow decay


def test_the_shimmer_runs_faster_on_the_hits():
    controls = ExtrudedBubbleControls(collision_scope="off")
    calm, busy = ExtrudedBubbleSimulation(2), ExtrudedBubbleSimulation(2)
    calm_start = _run(calm, controls, 2.0, intensity=0.6).shimmer
    busy_start = _run(busy, controls, 2.0, intensity=0.6).shimmer
    calm_gain = _run(calm, controls, 4.0, intensity=0.6).shimmer - calm_start
    busy_gain = _run(busy, controls, 4.0, intensity=0.6, onsets_every=0.5).shimmer - busy_start
    assert busy_gain > 1.5 * calm_gain > 0.0


def test_drift_and_emission_follow_music_then_settle_without_an_idle_size_oscillator():
    controls = ExtrudedBubbleControls(drift=(0.2, 0.9), emission=(0.1, 0.9), collision_scope="off", idle=0.6)
    simulation = ExtrudedBubbleSimulation(4)
    quiet = _run(simulation, controls, 5.0, intensity=0.0)
    loud = _run(simulation, controls, 6.0, intensity=1.0)
    assert loud.drift > quiet.drift + 0.5 and loud.emission > quiet.emission + 0.6
    for _ in range(720):
        idle = simulation.advance(_music(STEP, False), controls)
    assert idle.breath < 1e-8
    assert idle.stream_speed < loud.stream_speed * 0.1
    assert idle.emission < loud.emission * 0.1
    assert all(r[5] < 0 for r in _records(idle))


def test_sustained_response_changes_the_actual_small_body_lane_without_autonomous_pulses():
    from dataclasses import replace
    controls = ExtrudedBubbleControls(large_count=(0, 0), mid_count=(16, 16),
        small_pulse=(0.15, 0.8), collision_scope="off")
    cold, supported = ExtrudedBubbleSimulation(12), ExtrudedBubbleSimulation(12)
    low = _run(cold, replace(controls, sustained=0), 12, intensity=0.8)
    high = _run(supported, replace(controls, sustained=1), 12, intensity=0.8)
    mean = lambda snap: sum(r[5] for r in _records(snap)) / snap.count
    assert high.sustain > 0.8
    assert mean(high) > mean(low) + 0.1
    later = _run(supported, replace(controls, sustained=1), 4, intensity=0.8)
    assert abs(mean(later) - mean(high)) < 0.002  # constant sound holds; no fabricated per-bubble sine


def test_large_size_tracks_changing_body_bands_even_when_presence_stays_saturated():
    controls = ExtrudedBubbleControls(large_count=(8, 8), mid_count=(0, 0),
        breathing=(0.15, 0.6), collision_scope="off")
    sim = ExtrudedBubbleSimulation(14)
    values = []
    for i in range(600):
        bass = 0.2 if i % 60 < 30 else 0.75
        snap = sim.advance(MusicInput(STEP, True, 1, (), (bass, 0.1, 0.05)), controls)
        values.append(sum(r[5] for r in _records(snap)) / snap.count)
    assert min(values[-120:]) < 0 and max(values[-120:]) > 0.5



def test_nothing_pins_flat_at_the_top_of_its_range():
    from widgets.spotify_visualizer.extruded_bubble_simulation import _soft_top
    assert _soft_top(0.5) == 0.5
    assert 0.8 < _soft_top(0.95) < _soft_top(1.2) < _soft_top(3.0) < 1.0      # still rising, never flat on 1


def test_all_large_and_small_bubbles_can_reach_tiny_rest_at_normal_reaction_strength():
    controls = ExtrudedBubbleControls(large_count=(8, 8), mid_count=(16, 16), collision_scope="off",
                                     breathing=(.15, .6), small_pulse=(.15, .8))
    sim = ExtrudedBubbleSimulation(88)
    snap = _run(sim, controls, 20, intensity=0)
    bases = {b.ident: b.radius for b in sim._bubbles}
    assert snap.count == 24
    assert all(.12 < r[3] / bases[int(r[6])] < .15 for r in _records(snap))


def test_only_regular_bubbles_exist_no_synthetic_near_cohort_under_any_playback():
    controls = ExtrudedBubbleControls(large_count=(9.0, 9.0), mid_count=(0.0, 0.0), collision_scope="off")
    sim = ExtrudedBubbleSimulation(91)
    for playing, intensity, seconds in ((False, 0.0, 2.0), (True, 0.9, 10.0), (False, 0.0, 2.0)):
        for _ in range(int(seconds / STEP)):
            frame = sim.advance(_music(STEP, playing, intensity), controls)
            assert not frame.near_bubbles
            assert frame.count > 0



def test_water_and_bead_motion_are_slow_in_idle_and_speed_up_during_playback_without_phase_jumps():
    controls = ExtrudedBubbleControls(stream_speed=(0.0625, 0.2), idle=0.5, collision_scope="off")
    sim = ExtrudedBubbleSimulation(101)
    def segment(playing, intensity, seconds):
        data = []
        for _ in range(round(seconds / STEP)):
            data.append(sim.advance(_music(STEP, playing, intensity), controls))
        assert all(b.motion_phase >= a.motion_phase and b.travel >= a.travel
                   for a, b in zip(data, data[1:]))
        return (data[-1].motion_phase - data[-61].motion_phase,
                5.0 * (data[-1].travel - data[-61].travel))
    quiet_surface, quiet_beads = segment(False, 0.0, 5.0)
    loud_surface, loud_beads = segment(True, 1.0, 9.0)
    assert quiet_surface < 0.35 and quiet_beads < 0.4
    assert loud_surface > quiet_surface * 4.0
    assert loud_beads > quiet_beads * 2.5
    segment(False, 0.0, 12.0)  # gentle release, no reversal or snap to another phase
