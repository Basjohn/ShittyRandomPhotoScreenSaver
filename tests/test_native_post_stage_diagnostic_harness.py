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
    assert tool._effective_sample_counts({"scene_targets": {}}) == {}
    assert tool._effective_sample_counts({}) == {}


@pytest.fixture
def diagnostic(monkeypatch):
    state = dict.fromkeys(("time_defocus_draws", "flush_defocus_before_gather", "flush_defocus_between_draws",
                           "flush_defocus_after_sprites", "declare_defocus_external",
                           "disable_defocus_compute_tracking"), False)
    calls, counters = [], {"stage_defocus_timed": 0, "stage_defocus_time_skipped": 0,
                           "stage_defocus_records": 0, "stage_defocus_flushes": 0,
                           "stage_defocus_external_passes": 0, "stage_defocus_untracked_passes": 0}
    class Module:
        def stage_control(self, name, value):
            if name == "flush_defocus_draws":
                for key in tuple(state)[1:4]:
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
    monkeypatch.setattr(tool, "build", lambda case, packs: (
        (SimpleNamespace(case=case, declaration=lambda: {"name": "draw"}),), None, {}))
    monkeypatch.setattr(tool.stc, "Scene", lambda *a, **kw: SimpleNamespace(mode=SimpleNamespace(
        state=lambda: {"scene_targets": {"targets": [{"name": "scene", "effective_samples": kw["passes"][0].case.samples}]},
                       "program": {"passes": [{"name": "draw"}]}}, settings=lambda _: None)))
    monkeypatch.setattr(tool, "_frame", lambda *_: np.zeros((1, 1, 4), dtype=np.uint8))
    monkeypatch.setattr(tool, "_close", lambda *_: None)
    monkeypatch.setattr(tool.host_check, "_flush_deletes", lambda *_: None)
    monkeypatch.setattr(tool, "_live", lambda _: dict(counters))
    def timed(_host, _scene, _values, frames, **kwargs):
        assert frames == 240
        calls.append(tuple(state.values()))
        records = frames - 1
        counters["stage_defocus_records"] += records
        counters["stage_defocus_flushes"] += records * sum(tuple(state.values())[1:4])
        counters["stage_defocus_external_passes"] += records * int(any(tuple(state.values())[:5]))
        counters["stage_defocus_untracked_passes"] += records * int(state["disable_defocus_compute_tracking"])
        if state["time_defocus_draws"]:
            counters["stage_defocus_timed"] += tool.stc.COST_MIN_SAMPLES
        return {"samples": tool.stc.COST_MIN_SAMPLES, "median_ms": 2., "p10_ms": 1., "p90_ms": 3., "records": frames}
    monkeypatch.setattr(tool.stc, "_timed", timed)
    return core, state, calls, host


def test_phases_are_ordered_independent_and_reset(diagnostic):
    core, state, calls, host = diagnostic
    result = tool.round_defocus_boundaries(core, None, None, "opengl", {})
    assert result["pass"]
    phases = [(False, False, False, False, False, False), (False, True, True, True, False, False),
              (False, True, False, False, False, False), (False, False, True, False, False, False),
              (False, False, False, True, False, False), (False, False, False, False, True, False),
              (False, False, False, False, False, True), (True, False, False, False, False, False),
              (False, False, False, False, False, False)]
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
                "stage_defocus_records": 0, "stage_defocus_flushes": 0,
                "stage_defocus_external_passes": 0, "stage_defocus_untracked_passes": 0}
    monkeypatch.setattr(tool, "_live", lambda _: dict(counters))
    if bad == "state_error":
        monkeypatch.setattr(tool.stc, "Scene", lambda *a, **kw: SimpleNamespace(
            mode=SimpleNamespace(state=lambda: {"content_failing": True, "content_failure": "failure"},
                                 settings=lambda _: None)))
    def timed(*_a, **_kw):
        counters["stage_defocus_records"] += 239
        counters["stage_defocus_flushes"] += 239 * sum(tuple(state.values())[1:4])
        counters["stage_defocus_external_passes"] += 239 * int(any(tuple(state.values())[:5]))
        counters["stage_defocus_untracked_passes"] += 239 * int(state["disable_defocus_compute_tracking"])
        if state["time_defocus_draws"]:
            counters["stage_defocus_timed"] += tool.stc.COST_MIN_SAMPLES
            if bad == "skipped_query":
                counters["stage_defocus_time_skipped"] += 1
        elif bad == "unexpected_query":
            counters["stage_defocus_timed"] += 1
        return {"samples": tool.stc.COST_MIN_SAMPLES, "median_ms": 2., "p10_ms": 1., "p90_ms": 3., "records": 240}
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


@pytest.mark.parametrize("key, phase", (("stage_defocus_external_passes", "declarations_only"),
                                       ("stage_defocus_untracked_passes", "tracking_disabled")))
def test_a_control_without_its_actual_pass_flag_cannot_pass(diagnostic, monkeypatch, key, phase):
    core, _, _, _ = diagnostic
    live = tool._live
    monkeypatch.setattr(tool, "_live", lambda core: dict(live(core), **{key: 0}))
    result = tool.round_defocus_boundaries(core, None, None, "opengl", {})
    assert not result["checks"][f"x1_{phase}_full"]
    assert result["checks"][f"x1_{phase}_full_pixels"]


@pytest.mark.parametrize("bad", ("actual_records", "attempted_records", "actual_samples"))
def test_exact_record_and_sample_evidence_is_required(diagnostic, monkeypatch, bad):
    core, _, _, _ = diagnostic
    if bad == "actual_records":
        live = tool._live
        monkeypatch.setattr(tool, "_live", lambda core: dict(live(core), stage_defocus_records=0))
    elif bad == "attempted_records":
        timed = tool.stc._timed
        monkeypatch.setattr(tool.stc, "_timed", lambda *a, **kw: dict(timed(*a, **kw), records=241))
    else:
        monkeypatch.setattr(tool, "_effective_sample_counts", lambda _: {"scene": 1})
    result = tool.round_defocus_boundaries(core, None, None, "opengl", {})
    assert not result["checks"]["x4_declarations_only_full"]
    assert not result["checks"]["x4_tracking_disabled_full"]


def test_tracking_disabled_rejects_compute_anywhere_in_the_canonical_program():
    from rendering.native.mode import ComputePass, ModePass

    draw = ModePass("draw", b"unused")
    compute = ComputePass("compute", b"unused", groups=(1, 1, 1))
    assert tool._compute_free_program((draw,))
    assert not tool._compute_free_program(())
    for passes in ((compute, draw), (draw, compute, draw), (draw, compute)):
        assert not tool._compute_free_program(passes)


def test_compute_precondition_is_checked_before_enabling_tracking_control(diagnostic, monkeypatch):
    core, state, calls, host = diagnostic
    monkeypatch.setattr(tool, "build", lambda case, packs: (
        (SimpleNamespace(case=case, declaration=lambda: {"compute": True}),), None, {}))
    with pytest.raises(ValueError, match="no compute pass anywhere"):
        tool.round_defocus_boundaries(core, None, None, "opengl", {})
    assert not any(call[-1] for call in calls)
    assert all(not value for value in state.values()) and host.closed


def test_published_native_compute_entry_rejects_tracking_disabled_proof(diagnostic, monkeypatch):
    core, _, _, _ = diagnostic
    monkeypatch.setattr(tool.stc, "Scene", lambda *a, **kw: SimpleNamespace(mode=SimpleNamespace(
        state=lambda: {"scene_targets": {"targets": [{"name": "scene", "effective_samples": kw["passes"][0].case.samples}]},
                       "program": {"passes": [{"compute": {"trigger": "frame"}}]}}, settings=lambda _: None)))
    result = tool.round_defocus_boundaries(core, None, None, "opengl", {})
    assert not result["checks"]["x1_tracking_disabled_full"]
    assert not result["facts"]["x1_tracking_disabled"]["full"]["compute_free_program"]


def test_native_parser_accepts_new_boolean_control_keys_when_matching_module_is_installed():
    from rendering.native import loader

    module_dir = Path(__file__).resolve().parents[1] / "release" / "native_module"
    if not (module_dir / f"{loader.MODULE_NAME}.pyd").is_file():
        pytest.skip("matching GitHub-built native module not installed")
    core = loader.load(module_dir)
    keys = ("declare_defocus_external", "disable_defocus_compute_tracking")
    try:
        for key in keys:
            assert core.module.stage_control(key, True)
            assert core.module.stage_control(key, False)
        # The individual bits can coexist with each other and with the existing query/boundary bits.
        for key in (*keys, "time_defocus_draws", "flush_defocus_draws"):
            assert core.module.stage_control(key, True)
    finally:
        for key in (*keys, "time_defocus_draws", "flush_defocus_draws"):
            core.module.stage_control(key, False)
