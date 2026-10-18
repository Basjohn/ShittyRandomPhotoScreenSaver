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


def _run(simulation, controls, seconds, *, intensity=0.5, bass=0.2, onsets_every=0.0, kind="kick"):
    snapshot = None
    steps = int(round(seconds / STEP))
    for i in range(steps):
        onsets = ((kind, 1.0),) if onsets_every and i % int(onsets_every / STEP) == 0 else ()
        snapshot = simulation.advance(MusicInput(STEP, True, intensity, bass, onsets), controls)
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
        controls = ExtrudedBubbleControls(stream_direction=(around, height), drift=0.0, sway=0.0,
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
    calm = _run(simulation, controls, 3.0, bass=0.2)
    kicked = simulation.advance(MusicInput(STEP, True, 0.5, 0.2, (("kick", 1.0),)), controls)
    assert kicked.breath > calm.breath + 0.5
    swells = [r[5] for r in _records(kicked) if r[3] >= 0.07]
    assert swells and min(swells) > 0.05
    soft = ExtrudedBubbleSimulation(5)
    snappy = ExtrudedBubbleSimulation(5)
    for sim, smoothing in ((soft, 1.0), (snappy, 0.0)):
        c = ExtrudedBubbleControls(breathing=(0.1, 0.3), collision_scope="off", smoothing=smoothing)
        _run(sim, c, 3.0, bass=0.2)
        sim.advance(MusicInput(STEP, True, 0.5, 0.2, (("kick", 1.0),)), c)
    after_soft = _run(soft, ExtrudedBubbleControls(collision_scope="off", smoothing=1.0), 0.3, bass=0.2)
    after_snappy = _run(snappy, ExtrudedBubbleControls(collision_scope="off", smoothing=0.0), 0.3, bass=0.2)
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
        snapshot = popping.advance(MusicInput(STEP, True, 0.5, 0.2, ()), controls)
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
        idle = simulation.advance(MusicInput(STEP, False), ExtrudedBubbleControls())
    assert idle.count > 0 and idle.level == 0.0 and idle.stream_speed > 0.0
    simulation.reset()
    assert simulation.time == 0.0
    restarted = simulation.advance(MusicInput(STEP, False), ExtrudedBubbleControls())
    fresh = ExtrudedBubbleSimulation(9).advance(MusicInput(STEP, False), ExtrudedBubbleControls())
    assert restarted == fresh


# --- the frame runtime ------------------------------------------------------------------------------------------

def _onset(serial, kind="kick", magnitude=1.5, loudness=12.0, presence=1.0):
    from widgets.spotify_visualizer.transient_bus import MusicalOnset
    return MusicalOnset(serial, 0.0, kind, 1.0, magnitude, loudness, presence)


def _capture(runtime, now, onsets=(), *, identity=(1, 2, 3), source=(2, 3), playing=True):
    return runtime.advance(onsets=onsets, now_ts=now, playing=playing, intensity=0.6, bass=0.3, identity=identity,
                           source_identity=source, controls=ExtrudedBubbleControls())


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
    assert silent[-1].level == 0.0 and silent[-1].breath == 0.0
    runtime.retire()
    assert _capture(runtime, 60.0, identity=(1, 2, 4), source=(2, 4)) is None
