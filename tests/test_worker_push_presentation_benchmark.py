"""Small contract tests for the bounded worker+push reference harness."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

from tools.presentation_benchmark_core import build_common_bubble_feature_clip
from tools.worker_push_presentation_benchmark import (
    FeatureCursor,
    bubble_rect,
    numeric_summary,
    wall_offset_frame,
)


ROOT = Path(__file__).resolve().parents[1]


def test_feature_cursor_and_wall_offset_keep_the_shared_clip_deadlines():
    frames = build_common_bubble_feature_clip().frames
    cursor = FeatureCursor(frames)

    assert cursor.latest(999_999_999) is None
    index, first = cursor.latest(1_000_000_000)
    assert index == 0
    assert first is frames[0]

    live = wall_offset_frame(first, 1_700_000_000.0)
    assert live.timestamp_us == 1_700_000_001_000_000
    assert replace(live, timestamp_us=first.timestamp_us) == first


def test_bubble_geometry_and_gap_summary_are_deterministic():
    assert bubble_rect(1000, 500).getRect() == (100, 310, 800, 140)
    summary = numeric_summary([50.0, 16.0, 33.0], gap_counts=True)
    assert summary["p50"] == 33.0
    assert summary["max"] == 50.0
    assert summary["counts_gte_ms"]["33"] == 2
    assert summary["counts_gte_ms"]["100"] == 0


def test_p1_population_is_factory_created_but_provider_inert():
    path = ROOT / "tools" / "worker_push_presentation_benchmark.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_add_static_p1_population"
    )
    calls = {
        node.func.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "initialize" in calls
    assert "show" in calls
    assert "activate" not in calls
    assert "start" not in calls
    assert "setup_all_widgets" not in ast.unparse(method)
    assert "_create_factory_widgets" in ast.unparse(method)


def test_report_never_claims_frame_submitted_is_physical():
    source = (
        ROOT / "tools" / "worker_push_presentation_benchmark.py"
    ).read_text(encoding="utf-8")

    assert '"stage": "graphics_submission"' in source
    assert '"physical_presentation_evidence": False' in source
    assert '"internal_frame_submitted_is_physical": False' in source
    assert '"accepted_signal": "external.presentmon.displayed"' in source
    assert "BenchmarkMetricsRecorder" in source
    assert '"common_metrics"' in source
    assert "compositor.raise_()" not in source
    assert "InstrumentedGLCompositorWidget" not in source
    assert "InstrumentedLatestStateMailbox" not in source
    assert "InstrumentedThreadManager" not in source
