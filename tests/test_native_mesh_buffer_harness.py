"""GPU-free verdict and measurement contracts of the mesh-buffer proof harness."""
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native/core/python"))
harness = importlib.import_module("mesh_buffer_check")


def test_retarget_counter_gate_rejects_old_rebuild_and_child_verdict():
    """The old-module edge allocated three buffers and advanced stream generation; pixels alone cannot pass it."""
    from copy import deepcopy
    from mesh_retarget_check import edge_checks

    resident = {"mesh_buffers_streams": 1, "mesh_buffers_arenas": 1,
                "mesh_buffers_arena_bytes": 256, "mode_resources": 5}
    before = {"live": dict(resident, mesh_buffers_buffers_created=10),
              "state": {"mesh_buffers": {"generation": 1}}}
    retargeted = deepcopy(before)
    retargeted["live"]["mesh_buffers_buffers_created"] += 1
    assert all(edge_checks(before, retargeted, buffers=1).values())
    rebuilt = deepcopy(before)
    rebuilt["live"]["mesh_buffers_buffers_created"] += 3
    rebuilt["state"]["mesh_buffers"]["generation"] += 1
    failed_checks = edge_checks(before, rebuilt, buffers=1)
    assert not failed_checks["only_mesh_buffers_created"]
    assert not failed_checks["stream_generation_unchanged"]
    ok, reasons = harness.api_verdict("opengl", {
        "module_loaded": True, "rounds": ["retarget"],
        "retarget": {"pass": all(failed_checks.values()), "checks": failed_checks}}, False)
    assert not ok and any("retarget" in reason and "stream_generation_unchanged" in reason for reason in reasons)
    # A genuine layout edge must rebuild; an unchanged generation cannot satisfy that control.
    assert not edge_checks(before, retargeted, rebuild=True)["build_boundary"]
    assert edge_checks(before, rebuilt, rebuild=True)["build_boundary"]


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
    assert result["median_excess_floor_drift_sensitivity_ms"][0] < harness.FLOOR_MARGIN_MS
    assert result["median_excess_floor_drift_sensitivity_ms"][1] > harness.FLOOR_MARGIN_MS


def test_noisy_tails_do_not_replace_median_admission_rule():
    result = harness._floor_comparison(metric(.001, .030, .300), metric(.005, .015, .100),
                                       metric(.006, .015, .120))
    assert result["status"] == "within"
    assert result["excess_observed_spread_ms"][1] > harness.FLOOR_MARGIN_MS
    assert result["median_excess_floor_drift_sensitivity_ms"] == pytest.approx([.015, .015])


def test_cpu_floor_uses_copy_median_without_tail_gate():
    result = harness._floor_comparison(metric(.090, .100, .110), metric(.010, .015, .020),
                                       metric(.010, .015, .020), metric(.001, .010, .300))
    assert result["status"] == "material"
    assert result["raw_median_excess_ms"] == pytest.approx(.075)
    assert result["median_excess_floor_drift_sensitivity_ms"] == pytest.approx([.075, .075])


@pytest.mark.parametrize("route_median,after_floor,status", ((.05, 0, "material"),
                                                           (.05, .01, "inconclusive"),
                                                           (.0499, .01, "within")))
def test_median_margin_boundary_is_strict(route_median, after_floor, status):
    result = harness._floor_comparison(metric(route_median, route_median, route_median), metric(0, 0, 0),
                                       metric(after_floor, after_floor, after_floor))
    assert result["status"] == status


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


@pytest.mark.parametrize("batches,frames", (((20, 0, 20), 60), ((20, 1, 20), 60), ((20, 21, 20), 60),
                                           ((20, 20, 20), 60), ((20, 20, 20, 1), 61),
                                           ((20, 20, 1), 43), ((20, 20, 4), 43)))
def test_native_counter_batches_require_continuous_coverage(batches, frames):
    from types import SimpleNamespace

    count = 0
    snapshots = []
    for advance in (0,) + batches:
        count += advance
        snapshots.append(dict(mesh_buffers_records_timed=count, mesh_buffers_record_ns=count * 10000,
                              mesh_buffers_stream_write_ns=count * 1000))
    snapshots = iter(snapshots)
    host = SimpleNamespace(set_gpu_timer=lambda _: None, frames=lambda _: None,
                           gpu_samples=lambda: [SimpleNamespace(kind=2, nanoseconds=20000)])
    scene = SimpleNamespace(draw=lambda _: None, publish=lambda: None,
                            mode=SimpleNamespace(update=lambda: None,
                                                 _module=SimpleNamespace(composite_live=lambda: next(snapshots))))
    expected = (20,) * (frames // 20) + ((frames % 20,) if frames % 20 else ())
    if batches != expected:
        with pytest.raises(RuntimeError, match="native record timing.*batch"):
            harness._timed(host, scene, frames=frames, min_samples=1)
    else:
        result = harness._timed(host, scene, frames=frames, min_samples=1)
        assert result["record_cpu_samples"] == result["record_cpu_expected_samples"] == len(batches)
        assert result["record_cpu_records"] == sum(batches)
        assert result["record_cpu_sampled_frames"] == result["frames"] == sum(batches)


@pytest.mark.parametrize("samples,frames", ((1, 20), (29, 580), (1, 600), (29, 600)))
def test_cpu_comparison_requires_full_meaningful_batch_set(samples, frames):
    measurement = metric(.01, .015, .02)
    measurement.update({"record_cpu_" + key: value for key, value in metric(.01, .015, .02, samples).items()})
    measurement.update(frames=frames, record_cpu_expected_samples=(frames + 19) // 20,
                       record_cpu_sampled_frames=frames, record_cpu_records=frames)
    cpu = harness._record_metric(measurement)
    result = harness._floor_comparison(cpu, cpu, cpu, metric(.001, .001, .001))
    assert result["status"] == "invalid"


@pytest.mark.parametrize("field,value", (("record_cpu_expected_samples", None),
                                         ("record_cpu_sampled_frames", 580), ("record_cpu_records", 0),
                                         ("record_cpu_records", 30), ("record_cpu_records", 601)))
def test_cpu_comparison_rejects_incomplete_coverage_metadata(field, value):
    measurement = {"record_cpu_" + key: item for key, item in metric(.01, .015, .02).items()}
    measurement.update(frames=600, record_cpu_expected_samples=30, record_cpu_sampled_frames=600,
                       record_cpu_records=600)
    measurement[field] = value
    cpu = harness._record_metric(measurement)
    assert harness._floor_comparison(cpu, cpu, cpu)["status"] == "invalid"


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
        if status == "inconclusive" and scene.kind == "floor":
            value = metric(.01, .02, .03) if calls.count("floor") % 2 else metric(.05, .06, .07)
        if scene.kind in ("instance", "storage"):
            value = {"within": metric(.02, .03, .04), "inconclusive": metric(.055, .097, .110),
                     "material": metric(.15, .16, .17), "invalid": metric(.01, None, .03),
                     "missing_cpu": metric(.02, .03, .04)}[status]
        if status == "missing_cpu":
            return value | {"wall_median_ms": .001, "wall_p10_ms": .001}
        return (value | {"record_cpu_" + key: item for key, item in metric(.01, .015, .02).items()}
                | dict(frames=harness.RING_FRAMES, record_cpu_expected_samples=harness.RING_FRAMES // 20,
                       record_cpu_sampled_frames=harness.RING_FRAMES, record_cpu_records=harness.RING_FRAMES))

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

@pytest.mark.parametrize("name,width", (("uWords2", 2), ("uWords3", 3), ("uWords4", 4)))
def test_unsigned_vector_oracle_requires_every_last_component_and_real_mutations(name, width):
    import numpy as np
    import uniform_vector_check as proof

    original = proof.expected(proof.VALUES)
    assert all(proof.pixel_checks(original, proof.VALUES).values())
    changed = dict(proof.VALUES)
    words = list(changed[name])
    words[-1] ^= 0x80000001
    changed[name] = tuple(words)
    mutated = proof.expected(changed)
    assert not all(proof.pixel_checks(mutated, proof.VALUES).values())
    assert all(proof.pixel_checks(mutated, changed).values())
    assert all(proof.pixel_checks(original, proof.VALUES).values())
    # A stale/missing final component cannot satisfy the complete-vector positive predicate.
    preceding = 0
    for field, components in proof.WIDTHS:
        if field == name:
            break
        preceding += components
    column = 2 * (preceding + width - 1)
    dropped = original.copy()
    dropped[:, column:column+2] = 0
    assert not proof.pixel_checks(dropped, proof.VALUES)["exact_components"]
    # Every low/high half reconstructs the full u32, including bit31, without lossy float32 coercion of the word.
    halves = original[0].astype(np.uint32).reshape(-1, 2)
    reconstructed = halves[:, 0] | (halves[:, 1] << 16)
    assert reconstructed.tolist() == [word for field, _ in proof.WIDTHS for word in proof.VALUES[field]]


@pytest.mark.parametrize("bad", ("shape", "float64", "nan", "different_row"))
def test_unsigned_vector_oracle_fails_closed_on_malformed_pixels(bad):
    import numpy as np
    import uniform_vector_check as proof

    image = proof.expected(proof.VALUES)
    if bad == "shape":
        image = image[:, :-1]
    elif bad == "float64":
        image = image.astype(np.float64)
    elif bad == "nan":
        image[0, 0] = np.nan
    else:
        image[-1, -1] += 1
    assert not all(proof.pixel_checks(image, proof.VALUES).values())


def test_unsigned_vector_readback_uses_bottom_content_and_checks_metadata(monkeypatch):
    import numpy as np
    import scene_target_check
    import uniform_vector_check as proof
    from types import SimpleNamespace

    expected = proof.expected(proof.VALUES)
    allocation = np.full((8, 32), -123, dtype=np.float32)
    allocation[-proof.SIZE[1]:, :proof.SIZE[0]] = expected
    entry = {"name": "scene.colour", "level": 0, "format": "r32f", "size": [32, 8],
             "content": proof.SIZE, "data": allocation.tobytes()}
    published = []
    scene = SimpleNamespace(publish=lambda **record: published.append(record))
    monkeypatch.setattr(scene_target_check, "_metadata_readback", lambda _: [entry])
    assert np.array_equal(proof._readback(scene, proof.VALUES), expected)
    assert published == [proof.VALUES]
    entry["data"] = entry["data"][:-4]
    with pytest.raises(RuntimeError, match="byte count"):
        proof._readback(scene, proof.VALUES)
    entry["format"] = "rgba8"
    with pytest.raises(RuntimeError, match="metadata"):
        proof._readback(scene, proof.VALUES)


def test_unsigned_vector_round_is_explicitly_selectable_but_not_a_default(monkeypatch, tmp_path):
    from tools import artifact_paths

    monkeypatch.setattr(artifact_paths, "evidence_dir", lambda *_: tmp_path)
    monkeypatch.setattr(harness, "_gpu_conditions", lambda: {})
    monkeypatch.setattr(harness, "bake_packs", lambda *_: {})
    monkeypatch.setattr(harness, "cross_compare", lambda *_: {
        key: {"pass": True} for key in ("rule_a", "rule_b", "control_offset_stream_differs")})
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        child_path = Path(command[command.index("--child-json") + 1])
        child_path.write_text(json.dumps({"module_loaded": False, "rounds": []}), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(harness.subprocess, "run", run)
    harness.main(["--apis", "opengl"])
    assert commands and all("uniform_vectors" not in command for command in commands)
    commands.clear()
    harness.main(["--apis", "opengl", "--rounds", "uniform_vectors"])
    assert len(commands) == 1 and commands[0][-2:] == ["--rounds", "uniform_vectors"]
