"""Qt-free guard: EB behavioral replay must never use mutable shipped preset art."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_eb_behavior_replay_uses_only_test_owned_controls():
    # Architecture negative-control: do not restore the one-off startup probe
    # or make deterministic replay depend on live curated Preset 1/7 artwork.
    helper = ROOT / "tools/visualizer_replay/eb_simulation_support.py"
    source = helper.read_text(encoding="utf-8")
    tree = ast.parse(source)
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    strings = {node.value for node in ast.walk(tree)
               if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert "controls_from_authored_preset" not in used
    assert "resolve_visualizer_activation_payload" not in used
    assert not any("preset_1_" in value or "preset_7_" in value for value in strings)
    # Exercise two purpose-built input fixtures; test numbers never come from
    # current user settings or preset snapshots.
    from tools.visualizer_replay.eb_simulation_support import simulation_module, synthetic_controls
    simulation = simulation_module()
    gentle = synthetic_controls(simulation, "gentle")
    strong = synthetic_controls(simulation, "strong")
    assert strong.breathing[1] > gentle.breathing[1]
    assert strong.small_pulse[1] > gentle.small_pulse[1]


def test_eb_behavior_cases_never_import_authored_preset_oracle():
    for name in ("test_extruded_bubble_startup_and_sizes.py",
                 "test_extruded_bubble_recovery_candidate.py",
                 "test_extruded_bubble_lazy_bucket_ui.py"):
        source = (ROOT / "tests" / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        assert "controls_from_authored_preset" not in names
        assert "resolve_visualizer_activation_payload" not in names
