"""Safety contract for the bounded Qt Quick presentation spike."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools.presentation_benchmark_core import (
    TargetPacerState,
    parse_spike_args,
    percentile,
    validate_window_screen_count,
)


ROOT = Path(__file__).resolve().parents[1]


def _parse(*args: str):
    return parse_spike_args(args, description="test")


def test_safe_defaults_are_bounded_target_paced_and_load_passive():
    args = _parse()

    assert args.seconds == 15.0
    assert args.windows == 2
    assert args.target_hz == (165.0, 60.0)
    assert args.load_label == "light"
    assert args.throughput_probe is False
    assert not hasattr(args, "heavy")


def test_one_target_rate_expands_to_every_window():
    args = _parse("--windows", "3", "--target-hz", "90")

    assert args.target_hz == (90.0, 90.0, 90.0)


@pytest.mark.parametrize(
    "argv",
    (
        ("--seconds", "0"),
        ("--seconds", "121"),
        ("--windows", "0"),
        ("--target-hz", "0"),
        ("--target-hz", "165,60,90"),
    ),
)
def test_invalid_or_unbounded_shapes_are_rejected(argv):
    with pytest.raises(SystemExit):
        _parse(*argv)


def test_delayed_pacer_coalesces_missed_deadlines_without_catch_up_burst():
    pacer = TargetPacerState(100.0)
    pacer.start(0)

    first = pacer.consume(0)
    delayed = pacer.consume(45_000_000)

    assert first.due_opportunities == 1
    assert delayed.due_opportunities == 4
    assert pacer.requested_opportunities == 5
    assert pacer.paced_requests == 2
    assert pacer.skipped_deadlines == 3
    assert delayed.next_delay_ms == 5


def test_early_pacer_callback_waits_without_creating_an_opportunity():
    pacer = TargetPacerState(60.0)
    pacer.start(10_000_000)

    decision = pacer.consume(9_000_000)

    assert decision.due_opportunities == 0
    assert decision.next_delay_ms == 1
    assert pacer.requested_opportunities == 0
    assert pacer.paced_requests == 0


def test_window_count_cannot_silently_alias_missing_physical_screens():
    validate_window_screen_count(2, 2)

    with pytest.raises(ValueError, match="2 windows.*only 1 physical screens"):
        validate_window_screen_count(2, 1)

    with pytest.raises(ValueError, match="no screens"):
        validate_window_screen_count(1, 0)


def test_gap_percentile_uses_the_shared_deterministic_rule():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]

    assert percentile(values, 0.50) == 3.0
    assert percentile(values, 0.95) == 5.0
    assert percentile([], 0.95) == 0.0


def test_render_callback_self_requeue_is_throughput_probe_only():
    source = (ROOT / "tools" / "qtquick_presentation_spike.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    connections = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "connect":
            continue
        signal = node.func.value
        if isinstance(signal, ast.Attribute) and signal.attr == "afterFrameEnd":
            connections.append(node)

    assert len(connections) == 1
    ancestor = parents.get(connections[0])
    while ancestor is not None and not isinstance(ancestor, ast.If):
        ancestor = parents.get(ancestor)
    assert isinstance(ancestor, ast.If)
    assert "_throughput_probe" in ast.unparse(ancestor.test)
    assert "--heavy" not in source
    assert "spawn N CPU-burn" not in source


def test_report_labels_do_not_claim_physical_presentation_or_qt_acceptance():
    source = (ROOT / "tools" / "qtquick_presentation_spike.py").read_text(encoding="utf-8")

    assert "completed=" not in source
    assert " accepted=" not in source
    assert "render_callbacks=" in source
    assert "render_callback_fps=" in source
    assert "paced_requests=" in source
