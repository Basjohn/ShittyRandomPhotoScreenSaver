"""Zero-burden coverage for the opt-in presentation attribution counters (P4 H1/H2).

The counters distinguish the separate presentation-request edges (pacer
opportunities, publications, item present requests, fallback window updates, frame
swaps) so H2 amplification can be measured without collapsing them into one
generic metric. They must impose nothing on ordinary runtime: until the experiment
admission allocates the block, every note is a no-op and the snapshot is None.
"""

from __future__ import annotations

import pytest

from core.diagnostics import experiment_flags as ef
from core.diagnostics import visualizer_attribution as va


@pytest.fixture(autouse=True)
def _reset():
    ef.override_active_flags_for_testing(None)
    va.reset_for_testing()
    yield
    ef.override_active_flags_for_testing(None)
    va.reset_for_testing()


def test_disabled_by_default_notes_are_noops():
    assert va.is_enabled() is False
    # None admission -> notes do nothing, snapshot is None.
    va.note_pacer_opportunity()
    va.note_publication()
    va.note_present_request()
    va.note_window_update_fallback()
    va.note_frame_swap()
    assert va.snapshot() is None
    assert va.is_enabled() is False


def test_not_enabled_without_admission():
    ef.activate_experiment_flags(ef.parse_experiment_flags(["main.py", "/s"]))
    assert va.enable_if_admitted() is False
    assert va.snapshot() is None


@pytest.mark.parametrize("argv", [["main.py", "--viz-switch-telemetry"], ["main.py", "--abc-drive=B"]])
def test_enabled_when_admitted_counts_each_edge_separately(argv):
    ef.activate_experiment_flags(ef.parse_experiment_flags(argv))
    assert va.enable_if_admitted() is True
    va.note_pacer_opportunity()
    va.note_pacer_opportunity()
    va.note_publication()
    va.note_present_request()
    va.note_present_request()
    va.note_present_request()
    va.note_window_update_fallback()
    va.note_frame_swap()
    va.note_frame_swap()
    va.note_frame_swap()
    va.note_frame_swap()
    snap = va.snapshot()
    assert snap == {
        "pacer_opportunities": 2,
        "publications": 1,
        "present_requests": 3,
        "window_update_fallbacks": 1,
        "frame_swaps": 4,
    }


def test_fence_timing_disabled_by_default():
    ef.activate_experiment_flags(ef.parse_experiment_flags(["main.py", "/s"]))
    va.enable_if_admitted()
    assert va.fence_timing() is None  # no fence accumulator without admission


def test_fence_timing_buckets_and_stats_when_admitted():
    ef.activate_experiment_flags(ef.parse_experiment_flags(["main.py", "--abc-drive=B"]))
    va.enable_if_admitted()
    fence = va.fence_timing()
    assert fence is not None
    # capture: a fast one and a very slow one (>100 ms) land in different buckets.
    fence.note_capture(800)          # 0.5-1 us bucket
    fence.note_capture(800)
    fence.note_capture(120_000_000)  # >100 ms overflow bucket
    fence.note_restore(3_000)        # 2-5 us bucket
    snap = fence.snapshot()
    cap = snap["capture"]
    assert cap["count"] == 3
    assert cap["total_ns"] == 800 + 800 + 120_000_000
    assert cap["max_ns"] == 120_000_000
    assert cap["thread_id"] is not None
    # two in an early bucket, one in the final (overflow) bucket
    assert cap["buckets"][-1] == 1
    assert sum(cap["buckets"]) == 3
    assert snap["restore"]["count"] == 1
    assert len(snap["bucket_upper_ns"]) == len(cap["buckets"]) - 1


def test_enable_is_idempotent():
    ef.activate_experiment_flags(ef.parse_experiment_flags(["main.py", "--abc-drive=A"]))
    assert va.enable_if_admitted() is True
    va.note_publication()
    assert va.enable_if_admitted() is True  # does not reallocate/reset
    assert va.snapshot()["publications"] == 1
