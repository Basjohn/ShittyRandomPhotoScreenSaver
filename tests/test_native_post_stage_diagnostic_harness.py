"""Exercise the boundary diagnostic's control and evidence sequencing without a GPU."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native" / "core" / "python"))
import post_stage_check as tool


def test_gate_evidence_uses_allocated_samples_when_request_was_clamped():
    state = {"scene_targets": {"targets": [{"name": "owner", "samples": 4, "effective_samples": 1}]}}
    assert tool._effective_sample_counts(state) == {"owner": 1}


@pytest.fixture
def diagnostic(monkeypatch):
    state = dict.fromkeys(("time_defocus_draws", "flush_defocus_before_gather", "flush_defocus_between_draws",
                           "flush_defocus_after_sprites"), False)
    calls, counters = [], {"stage_defocus_timed": 0, "stage_defocus_time_skipped": 0,
                           "stage_defocus_records": 0, "stage_defocus_flushes": 0}
    class Module:
        def stage_control(self, name, value):
            if name == "flush_defocus_draws":
                for key in tuple(state)[1:]:
                    state[key] = value
            else:
                state[name] = value
            assert not (state["time_defocus_draws"] and any(tuple(state.values())[1:]))
            return True
    class Host:
        closed = False
        def frames(self, count):
            assert count == 4
        def close(self):
            self.closed = True
    host = Host()
    core = SimpleNamespace(module=Module(), hidden_host=lambda *_: host)
    monkeypatch.setattr(tool, "build", lambda case, packs: (case, None, {}))
    monkeypatch.setattr(tool.stc, "Scene", lambda *a, **kw: SimpleNamespace(
        mode=SimpleNamespace(state=lambda: {}, settings=lambda _: None)))
    monkeypatch.setattr(tool, "_frame", lambda *_: np.zeros((1, 1, 4), dtype=np.uint8))
    monkeypatch.setattr(tool, "_close", lambda *_: None)
    monkeypatch.setattr(tool.host_check, "_flush_deletes", lambda *_: None)
    monkeypatch.setattr(tool, "_live", lambda _: dict(counters))
    def timed(_host, _scene, _values, frames, **kwargs):
        assert frames == 240
        calls.append(tuple(state.values()))
        counters["stage_defocus_records"] += 40
        counters["stage_defocus_flushes"] += 40 * sum(tuple(state.values())[1:])
        if state["time_defocus_draws"]:
            counters["stage_defocus_timed"] += tool.stc.COST_MIN_SAMPLES
        return {"samples": tool.stc.COST_MIN_SAMPLES, "median_ms": 2., "p10_ms": 1., "p90_ms": 3.}
    monkeypatch.setattr(tool.stc, "_timed", timed)
    return core, state, calls, host


def test_phases_are_ordered_independent_and_reset(diagnostic):
    core, state, calls, host = diagnostic
    result = tool.round_defocus_boundaries(core, None, None, "opengl", {})
    assert result["pass"]
    phases = [(False, False, False, False), (False, True, True, True), (False, True, False, False),
              (False, False, True, False), (False, False, False, True), (True, False, False, False),
              (False, False, False, False)]
    assert calls == [phase for _ in (1, 4) for phase in phases for _ in range(2)]
    assert all(not value for value in state.values()) and host.closed
    assert result["facts"]["x1_boundaries"]["full_minus_no_sprites_median_ms"] == 0


@pytest.mark.parametrize("invalid", ({"samples": 0, "median_ms": 2., "p10_ms": 1., "p90_ms": 3.},
                                    {"samples": 30, "median_ms": float("nan"),
                                                    "p10_ms": 1., "p90_ms": 2.}))
def test_missing_or_nonfinite_measurement_fails_closed(diagnostic, monkeypatch, invalid):
    core, state, _, host = diagnostic
    original = tool.stc._timed
    def timed(*args, **kwargs):
        original(*args, **kwargs)
        return invalid
    monkeypatch.setattr(tool.stc, "_timed", timed)
    result = tool.round_defocus_boundaries(core, None, None, "opengl", {})
    assert not result["pass"]
    assert not result["checks"]["x1_off_before_full"]
    assert all(not value for value in state.values()) and host.closed


def test_controls_reset_after_error(diagnostic, monkeypatch):
    core, state, _, host = diagnostic
    def fail(*_a, **_kw):
        raise RuntimeError("measurement failed")
    monkeypatch.setattr(tool.stc, "_timed", fail)
    with pytest.raises(RuntimeError):
        tool.round_defocus_boundaries(core, None, None, "opengl", {})
    assert all(not value for value in state.values()) and host.closed


@pytest.mark.parametrize("bad", ("unexpected_query", "skipped_query", "state_error"))
def test_invalid_counter_or_content_failure_is_rejected(diagnostic, monkeypatch, bad):
    core, state, _, _ = diagnostic
    counters = {"stage_defocus_timed": 0, "stage_defocus_time_skipped": 0,
                "stage_defocus_records": 0, "stage_defocus_flushes": 0}
    monkeypatch.setattr(tool, "_live", lambda _: dict(counters))
    if bad == "state_error":
        monkeypatch.setattr(tool.stc, "Scene", lambda *a, **kw: SimpleNamespace(
            mode=SimpleNamespace(state=lambda: {"content_failing": True, "content_failure": "failure"},
                                 settings=lambda _: None)))
    def timed(*_a, **_kw):
        counters["stage_defocus_records"] += 40
        counters["stage_defocus_flushes"] += 40 * sum(tuple(state.values())[1:])
        if state["time_defocus_draws"]:
            counters["stage_defocus_timed"] += tool.stc.COST_MIN_SAMPLES
            if bad == "skipped_query":
                counters["stage_defocus_time_skipped"] += 1
        elif bad == "unexpected_query":
            counters["stage_defocus_timed"] += 1
        return {"samples": tool.stc.COST_MIN_SAMPLES, "median_ms": 2., "p10_ms": 1., "p90_ms": 3.}
    monkeypatch.setattr(tool.stc, "_timed", timed)
    assert not tool.round_defocus_boundaries(core, None, None, "opengl", {})["pass"]


def test_changed_pixels_in_a_control_phase_fail(diagnostic, monkeypatch):
    core, state, _, _ = diagnostic
    monkeypatch.setattr(tool, "_frame", lambda *_: np.array([int(any(tuple(state.values())[1:]))]))
    result = tool.round_defocus_boundaries(core, None, None, "opengl", {})
    assert not result["checks"]["x1_boundaries_full_pixels"]
    assert not result["pass"]


def test_selected_boundaries_without_flushes_fail(diagnostic, monkeypatch):
    core, _, _, _ = diagnostic
    live = tool._live
    monkeypatch.setattr(tool, "_live", lambda core: dict(live(core), stage_defocus_flushes=0))
    result = tool.round_defocus_boundaries(core, None, None, "opengl", {})
    for phase in ("boundaries", "before_gather", "between_draws", "after_sprites"):
        assert not result["checks"][f"x1_{phase}_full"]
        assert result["checks"][f"x1_{phase}_full_pixels"]
