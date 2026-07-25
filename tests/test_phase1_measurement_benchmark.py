from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import phase1_measurement_benchmark as benchmark


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_projection_reports_paired_cpu_and_p99_metrics():
    result = benchmark.run_benchmark(
        duration_seconds=0.5,
        repeats=3,
        frame_rate=60,
        work_items=20,
    )

    assert result["kind"] == "phase1_composite_diagnostic_budget_projection"
    assert result["configuration"]["frames_per_condition"] == 30
    assert result["instrumented"]["recorder_samples"] == 10
    components = {component["name"]: component for component in result["components"]}
    assert set(components) == {
        "event_loop_recorder",
        "display_0_frame_recorder",
        "display_1_frame_recorder",
        "task_category_accounting",
        "resource_aggregate_snapshot",
    }
    assert components["display_0_frame_recorder"]["rate_hz"] == 165.0
    assert components["display_1_frame_recorder"]["rate_hz"] == 60.0
    for name in ("display_0_frame_recorder", "display_1_frame_recorder"):
        assert components[name]["method"] == (
            "_PaintMetrics.record_render_request + record_paint_start + record"
        )
        assert "exact Phase 1 paint-delivery collector path" in components[name]["fidelity"]
    assert components["task_category_accounting"]["rate_hz"] == 171.0
    assert components["resource_aggregate_snapshot"]["rate_hz"] == pytest.approx(1.0 / 15.0)
    assert components["resource_aggregate_snapshot"]["method"] == (
        "collect_resource_accounting(ImageCache + ResourceManager)"
    )
    assert "24-cache + 64-registry" in components["resource_aggregate_snapshot"]["fidelity"]
    assert set(result["overhead"]) == {
        "cpu_estimation",
        "cpu_seconds",
        "cpu_percent_of_baseline_workload",
        "projected_cpu_percent_of_one_core",
        "p99_frame_work_delta_ms",
    }
    assert result["methodology"]["real_gl_runtime"] is False


def test_verdict_fails_each_budget_independently():
    result = {
        "overhead": {
            "cpu_percent_of_baseline_workload": 2.01,
            "p99_frame_work_delta_ms": 0.26,
        }
    }

    verdict = benchmark._add_verdict(result, max_cpu_percent=2.0, max_p99_delta_ms=0.25)

    assert verdict["verdict"] == {"cpu_pass": False, "p99_pass": False, "pass": False}


def test_main_returns_failure_when_any_budget_is_exceeded(monkeypatch, capsys):
    monkeypatch.setattr(
        benchmark,
        "run_benchmark",
        lambda **_kwargs: {"overhead": {"cpu_percent_of_baseline_workload": 2.01, "p99_frame_work_delta_ms": 0.0}},
    )

    assert benchmark.main([]) == 1
    assert json.loads(capsys.readouterr().out)["verdict"]["pass"] is False


@pytest.mark.parametrize("arguments", [("--duration-seconds", "0.4"), ("--repeats", "2")])
def test_invalid_bounds_return_machine_readable_failure(arguments):
    completed = subprocess.run(
        [sys.executable, "tools/phase1_measurement_benchmark.py", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert json.loads(completed.stdout)["pass"] is False


def test_help_exits_without_running_benchmark():
    completed = subprocess.run(
        [sys.executable, "tools/phase1_measurement_benchmark.py", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "--max-cpu-overhead-percent" in completed.stdout
