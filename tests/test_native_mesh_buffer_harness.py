"""GPU-free verdict and measurement contracts of the mesh-buffer proof harness."""
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native/core/python"))
harness = importlib.import_module("mesh_buffer_check")


@pytest.mark.parametrize("target", ("opengl", "reference"))
@pytest.mark.parametrize("failure", ("timeout", "exit"))
def test_failed_child_never_reuses_success(target, failure, monkeypatch, tmp_path):
    from tools import artifact_paths

    monkeypatch.setattr(artifact_paths, "evidence_dir", lambda *_: tmp_path)
    monkeypatch.setattr(harness, "_gpu_conditions", lambda: {})
    monkeypatch.setattr(harness, "bake_packs", lambda *_: {})
    monkeypatch.setattr(harness, "cross_compare", lambda *_: {
        key: {"pass": True} for key in ("rule_a", "rule_b", "control_offset_stream_differs")})
    good = {"module_loaded": True, "rounds": [], "reference": {"pass": True}}
    path = tmp_path / f"child_{target}.json"
    path.write_text(json.dumps(good), encoding="utf-8")

    def run(command, **kwargs):
        api = command[command.index("--api") + 1]
        child_path = Path(command[command.index("--child-json") + 1])
        if api == target:
            assert not child_path.exists(), "stale success survived until launch"
        child_path.write_text(json.dumps(good), encoding="utf-8")
        if api == target and failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 9 if api == target else 0, "", "crash")

    monkeypatch.setattr(harness.subprocess, "run", run)
    harness.main(["--apis", "opengl", "--rounds", "parity", "--label", "r226_mesh"])
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert not summary["pass"]
    assert not summary["verdicts"][target]["pass"]
    assert "child process failed" in " ".join(summary["verdicts"][target]["failed"])


@pytest.mark.parametrize("exit_code", ("timeout", 9))
def test_reference_result_cannot_overrule_failed_exit(exit_code):
    ok, failed = harness.api_verdict("reference", {"reference": {"pass": True}, "exit_code": exit_code}, False)
    assert not ok and "child process failed" in " ".join(failed)


def metric(p10, median, p90, samples=30):
    return dict(p10_ms=p10, median_ms=median, p90_ms=p90, samples=samples)


def test_idle_spread_is_inconclusive_even_when_old_absolute_guard_failed():
    route = metric(.055, .097, .110)
    before, after = metric(.025, .050, .060), metric(.015, .028, .040)
    assert route["median_ms"] - after["median_ms"] > harness.FLOOR_MARGIN_MS
    result = harness._floor_comparison(route, before, after)
    assert result["status"] == "inconclusive"
    assert result["raw_median_exceeds_margin"]
    assert result["excess_observed_spread_ms"][0] < harness.FLOOR_MARGIN_MS
    assert result["excess_observed_spread_ms"][1] > harness.FLOOR_MARGIN_MS


@pytest.mark.parametrize("route,status", [(metric(.025, .030, .035), "within"),
                                          (metric(.150, .160, .170), "material")])
def test_floor_comparison_preserves_material_slowdown(route, status):
    result = harness._floor_comparison(route, metric(.010, .015, .020), metric(.012, .016, .022))
    assert result["status"] == status
    assert result["margin_ms"] == harness.FLOOR_MARGIN_MS
    assert result["route_to_floor_median_ratio"] > 1


@pytest.mark.parametrize("bad", [metric(.01, None, .02), metric(.01, float("nan"), .02),
                                  metric(.01, .02, float("inf")), metric(.01, .02, .03, 0),
                                  metric(.03, .02, .01)])
def test_missing_or_nonfinite_measurement_fails_closed(bad):
    result = harness._floor_comparison(metric(.01, .02, .03), bad, metric(.01, .02, .03))
    assert result["status"] == "invalid"


def test_missing_native_record_counters_cannot_use_wall_time():
    from types import SimpleNamespace
    host = SimpleNamespace(set_gpu_timer=lambda _: None, frames=lambda _: None,
                           gpu_samples=lambda: [SimpleNamespace(kind=2, nanoseconds=20000)])
    scene = SimpleNamespace(draw=lambda _: None, publish=lambda: None,
                            mode=SimpleNamespace(update=lambda: None,
                                                 _module=SimpleNamespace(composite_live=lambda: {})))
    with pytest.raises(RuntimeError, match="mesh_buffers_records_timed"):
        harness._timed(host, scene, frames=20, min_samples=1)


@pytest.mark.parametrize("status", ("within", "inconclusive", "material", "invalid", "missing_cpu"))
def test_stream_round_brackets_each_route_and_never_passes_unresolved(status, monkeypatch):
    from types import SimpleNamespace

    calls = []
    monkeypatch.setattr(harness, "RING_PAYLOADS", (("probe", 1024),))
    monkeypatch.setattr(harness, "_scenes", lambda: SimpleNamespace(ring_scene=lambda p, n, k, **kw: k))
    monkeypatch.setattr(harness, "_host", lambda *_: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(harness, "_close", lambda *_: None)
    monkeypatch.setattr(harness.host_check, "_flush_deletes", lambda *_: None)
    monkeypatch.setattr(harness, "Scene", lambda c, e, h, kind: SimpleNamespace(
        kind=kind, mode=SimpleNamespace(state=lambda: {})))
    monkeypatch.setattr(harness, "_copy_summary", lambda _: metric(.001, .001, .001))

    def measured(host, scene):
        calls.append(scene.kind)
        value = metric(.01, .015, .02)
        if scene.kind in ("instance", "storage"):
            value = {"within": metric(.02, .03, .04), "inconclusive": metric(.055, .097, .110),
                     "material": metric(.15, .16, .17), "invalid": metric(.01, None, .03),
                     "missing_cpu": metric(.02, .03, .04)}[status]
        if status == "missing_cpu":
            return value | {"wall_median_ms": .001, "wall_p10_ms": .001}
        return value | {"record_cpu_" + key: item for key, item in metric(.01, .015, .02).items()}

    monkeypatch.setattr(harness, "_timed", measured)
    result = harness.round_stream_ring(None, None, None, "opengl", {}, only=("probe",))
    assert calls == ["none", "floor", "instance", "floor", "floor", "storage", "floor"]
    assert result["pass"] == (status == "within")
    for route in ("instance", "storage"):
        comparison = result["facts"]["probe"][route]["comparison"]
        if status == "missing_cpu":
            assert comparison["gpu"]["status"] == "within"
            assert comparison["cpu"]["status"] == "invalid"
        else:
            assert comparison["gpu"]["status"] == status
