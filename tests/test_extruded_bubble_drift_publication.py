"""What the drift log publishes so that the GPU solver needs no 64-bit float (D4.2): every float64 decision is
the reference's own, made once on the logical side, and survives the frame codec bit for bit."""
import math

import numpy as np

from widgets.spotify_visualizer.extruded_bubble_drift import PHASE_RATES
from widgets.spotify_visualizer.extruded_bubble_drift_log import (
    KNOT_DECISION, KNOT_DECISION_BYTES, STEP_INDEX as R, MaterialDriftReference, knot_starts, newest_knots,
    unpack_steps,
)
from tests.test_extruded_bubble_drift_precision import long_log, HOUR

_ANGLES = ("angle_wander", "angle_wander_2", "angle_deep", "angle_swish")


def test_published_knot_decisions_are_the_references_own_on_every_tick():
    """Over an edit (the phase offset rebase) and a chain-count change, each step's decisions equal the
    reference's float64 knot clock: ``moved`` as integers, shift and phase offset as their float32 values."""
    reference, ticks = MaterialDriftReference(), 0
    for families, steps, knots in long_log("swirl_cw", 160, HOUR, edit_at=60, resize_at=110, emission=(.1, .2)):
        if not families:
            continue
        records = unpack_steps(steps)
        assert len(knots) == int(knot_starts(records)[-1]) * KNOT_DECISION_BYTES
        reference.apply(families, steps)
        clock = reference._state["chains"][1].clock
        decided = np.frombuffer(newest_knots(steps, knots)[1], dtype=KNOT_DECISION)
        assert len(decided) == int(records[-1, R["chain_rows"]]) == len(clock.moved)
        assert np.array_equal(decided["moved"], clock.moved)
        assert np.array_equal(decided["shift"], clock.shift.astype(np.float32))
        assert np.array_equal(decided["phase_offset"], clock.phase_offset.astype(np.float32))
        ticks += 1
    assert ticks > 150
    assert np.any(clock.phase_offset != 0.)   # the edit rebased the phase offset


def test_step_records_carry_the_reduced_angles_and_the_travel_pair():
    for families, steps, _knots in long_log("wander", 20, HOUR, emission=(.1, .2)):
        record = unpack_steps(steps)[-1]
        t, travel = float(record[R["phase"]]), float(record[R["travel"]])
        for name, rate in zip(_ANGLES, PHASE_RATES):
            angle = record[R[name]]
            assert np.float32(angle) == angle and abs(angle) < 2 * math.pi + 1e-6
            assert abs(math.sin(angle) - math.sin(t * rate)) < 1e-6
        high, low = record[R["travel_high"]], record[R["travel_low"]]
        assert np.float32(high) == high and np.float32(low) == low
        assert abs(high + low - travel) <= travel * 2. ** -47
        for family in families:
            if family.family != "chains":
                start, spans, _seed, carry, _phases = family.source
                rows = np.frombuffer(family.geometry, dtype=np.float32).reshape(-1, 2, 4)
                pair = rows[:, 1, 2].astype(np.float64) + rows[:, 1, 3]
                assert np.abs(pair - carry / spans).max() <= (carry / spans).max() * 2. ** -47
