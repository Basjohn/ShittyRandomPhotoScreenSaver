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


def test_enable_is_idempotent():
    ef.activate_experiment_flags(ef.parse_experiment_flags(["main.py", "--abc-drive=A"]))
    assert va.enable_if_admitted() is True
    va.note_publication()
    assert va.enable_if_admitted() is True  # does not reallocate/reset
    assert va.snapshot()["publications"] == 1
