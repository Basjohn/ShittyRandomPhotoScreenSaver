"""Exercise the boundary diagnostic's control and evidence sequencing without a GPU."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native" / "core" / "python"))
import post_stage_check as tool


@pytest.fixture
def diagnostic(monkeypatch):
    state = {"time_defocus_draws": False, "flush_defocus_draws": False}
    calls, counters = [], {"stage_defocus_timed": 0, "stage_defocus_time_skipped": 0}
    class Module:
        def stage_control(self, name, value):
            state[name] = value
            assert not all(state.values())
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
        if state["time_defocus_draws"]:
            counters["stage_defocus_timed"] += tool.stc.COST_MIN_SAMPLES
        return {"samples": tool.stc.COST_MIN_SAMPLES, "median_ms": 2., "p10_ms": 1., "p90_ms": 3.}
    monkeypatch.setattr(tool.stc, "_timed", timed)
    return core, state, calls, host


def test_phases_are_ordered_independent_and_reset(diagnostic):
    core, state, calls, host = diagnostic
    result = tool.round_defocus_boundaries(core, None, None, "opengl", {})
    assert result["pass"]
    assert calls == [(False, False)] * 2 + [(False, True)] * 2 + [(True, False)] * 2 + [(False, False)] * 2 + \
                    [(False, False)] * 2 + [(False, True)] * 2 + [(True, False)] * 2 + [(False, False)] * 2
    assert all(not value for value in state.values()) and host.closed
    assert result["facts"]["x1_boundaries"]["full_minus_no_sprites_median_ms"] == 0


@pytest.mark.parametrize("invalid", ({"samples": 0, "median_ms": 2., "p10_ms": 1., "p90_ms": 3.},
                                    {"samples": 30, "median_ms": float("nan"),
                                                    "p10_ms": 1., "p90_ms": 2.}))
def test_missing_or_nonfinite_measurement_fails_closed(diagnostic, monkeypatch, invalid):
    core, state, _, host = diagnostic
    monkeypatch.setattr(tool.stc, "_timed", lambda *_a, **_kw: invalid)
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
    counters = {"stage_defocus_timed": 0, "stage_defocus_time_skipped": 0}
    monkeypatch.setattr(tool, "_live", lambda _: dict(counters))
    if bad == "state_error":
        monkeypatch.setattr(tool.stc, "Scene", lambda *a, **kw: SimpleNamespace(
            mode=SimpleNamespace(state=lambda: {"content_failing": True, "content_failure": "failure"},
                                 settings=lambda _: None)))
    def timed(*_a, **_kw):
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
    monkeypatch.setattr(tool, "_frame", lambda *_: np.array([int(state["flush_defocus_draws"])]))
    result = tool.round_defocus_boundaries(core, None, None, "opengl", {})
    assert not result["checks"]["x1_boundaries_full_pixels"]
    assert not result["pass"]
