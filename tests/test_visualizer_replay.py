"""Offline response floors across the real authored tick and Quick snapshot seam."""
from __future__ import annotations

import json
import shutil

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from tools.visualizer_replay.driver import FIXTURES, MODES, load_clips, replay_clip
from tools.visualizer_replay.engine import ReplayBeatEngine
from tools.visualizer_replay.floors import REFERENCE, check_floors

CASES = tuple(json.loads(REFERENCE.read_text(encoding="utf-8"))["cases"])


@pytest.fixture(scope="module")
def clips():
    return load_clips()


@pytest.fixture(autouse=True)
def drain_retired_qobjects(qt_app):
    yield
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("case", CASES)
def test_current_reactivity_passes_fixed_floors(clips, case):
    fixture, mode = case.split("__")
    result = replay_clip(clips[fixture], mode)
    assert len(result["metrics"]) == 32
    assert len(result["logical_series"]) == len(clips[fixture].frames)
    check_floors(result, case)


@pytest.mark.parametrize("mode", MODES)
def test_presentation_stalls_cannot_change_authored_series(clips, mode):
    ordinary = replay_clip(clips["beats_120_bpm"], mode)
    stalled = replay_clip(clips["beats_120_bpm"], mode, present_every=7)
    assert ordinary["logical_series"] == stalled["logical_series"]
    assert ordinary["metrics"] == stalled["metrics"]
    assert len(stalled["presentation_trace"]) < len(ordinary["presentation_trace"])


def test_fixture_integrity_rejects_tampering(tmp_path):
    target = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, target)
    path = target / "silence.jsonl"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="fixture integrity mismatch: silence"):
        load_clips(target)


def test_silent_bar_regression_fails_floor_at_engine_consumer(clips, monkeypatch):
    monkeypatch.setattr(ReplayBeatEngine, "get_smoothed_bars", lambda self: [0.0] * self._bar_count)
    result = replay_clip(clips["beats_120_bpm"], "spectrum")
    with pytest.raises(AssertionError, match="below floor"):
        check_floors(result, "beats_120_bpm__spectrum")


def test_frozen_devcurve_runtime_fails_own_output_floor(clips, monkeypatch):
    from widgets.spotify_visualizer.devcurve_frame_runtime import DevCurveFrameRuntime

    advance = DevCurveFrameRuntime.advance
    def freeze_after_first(self, **kwargs):
        if self.latest.curves:
            return self.latest
        return advance(self, **kwargs)
    monkeypatch.setattr(DevCurveFrameRuntime, "advance", freeze_after_first)
    result = replay_clip(clips["beats_120_bpm"], "devcurve")
    assert result["metrics"]["bar_peak"] > 0.5
    with pytest.raises(AssertionError, match="output_flux=.*below floor"):
        check_floors(result, "beats_120_bpm__devcurve")


def test_control_fixture_keeps_mode_and_visibility_events(clips):
    clip = clips["mode_visibility_switch"]
    result = replay_clip(clip, "control")
    assert [frame.mode_id for frame in result["logical_series"]] == [frame.mode for frame in clip.frames]
    assert result["presentation_trace"] == [i for i, frame in enumerate(clip.frames) if frame.visible]


def test_every_retained_v1_case_has_a_floor_entry():
    prior = {path.stem for path in (REFERENCE.parent / "v1").glob("*.json") if path.stem != "manifest"}
    assert set(CASES) == prior


def test_sustained_lanes_remain_distinct(clips):
    bass = replay_clip(clips["sustained_bass"], "spectrum")
    treble = replay_clip(clips["sustained_treble"], "spectrum")
    assert bass["metrics"]["bar_centroid"] < treble["metrics"]["bar_centroid"]


def test_devcurve_travel_reacts_within_authored_cruise_envelope(clips):
    rates = replay_clip(clips["beats_180_bpm"], "devcurve")["travel_rates"]
    # Product contract: 0.23 / 1.35 cruise with at most +/-10% modulation.
    # Keep expected values independent of implementation constants.
    cruise = 0.23 / 1.35
    assert min(rates) >= cruise * 0.9 - 1e-9
    assert max(rates) <= cruise * 1.1 + 1e-9
    assert max(rates) - min(rates) > 1e-5
