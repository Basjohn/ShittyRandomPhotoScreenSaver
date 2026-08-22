"""Production-shaped real-GL bar for the inline Quick visualizer clip."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _run_clip_smoke(policy: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.qtquick_visualizer_clip_smoke",
            "--policy",
            policy,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout[completed.stdout.index("{") :])


def _assert_rgb(actual: list[int], expected: list[int]) -> None:
    assert len(actual) >= 3
    assert all(
        abs(int(component) - int(target)) <= 2
        for component, target in zip(actual[:3], expected[:3], strict=True)
    )


@pytest.mark.parametrize("policy", ("rect", "rounded", "nested"))
def test_inline_visualizer_clip_covers_only_its_canonical_content(policy: str) -> None:
    report = _run_clip_smoke(policy)

    assert report["valid"] is True
    assert report["error"] is None
    assert report["policy"] == policy
    capture = report["captures"][policy]
    colors = capture["colors"]
    background = report["background_rgb"]
    drawn = report["draw_rgb"]

    _assert_rgb(colors["center"], drawn)
    if policy == "rect":
        for name in (
            "rect_inside_left",
            "rect_inside_right",
            "rect_inside_top",
            "rect_inside_bottom",
        ):
            _assert_rgb(colors[name], drawn)
        for name in (
            "rect_outside_left",
            "rect_outside_right",
            "rect_outside_top",
            "rect_outside_bottom",
        ):
            _assert_rgb(colors[name], background)
    elif policy == "rounded":
        for name in (
            "rounded_edge_left",
            "rounded_edge_right",
            "rounded_edge_top",
            "rounded_edge_bottom",
            "rounded_corner_in_tl",
            "rounded_corner_in_tr",
            "rounded_corner_in_bl",
            "rounded_corner_in_br",
        ):
            _assert_rgb(colors[name], drawn)
        for name in (
            "rounded_corner_out_tl",
            "rounded_corner_out_tr",
            "rounded_corner_out_bl",
            "rounded_corner_out_br",
            "card_border_left",
            "card_border_right",
            "card_border_top",
            "card_border_bottom",
        ):
            _assert_rgb(colors[name], background)
    else:
        for name in (
            "rounded_edge_left",
            "rounded_edge_top",
            "rounded_edge_bottom",
            "rounded_corner_in_tl",
            "rounded_corner_in_bl",
        ):
            _assert_rgb(colors[name], drawn)
        for name in (
            "rounded_edge_right",
            "rounded_corner_in_tr",
            "rounded_corner_in_br",
            "rounded_corner_out_tl",
            "rounded_corner_out_tr",
            "rounded_corner_out_bl",
            "rounded_corner_out_br",
            "card_border_left",
            "card_border_right",
            "card_border_top",
            "card_border_bottom",
        ):
            _assert_rgb(colors[name], background)

    if policy == "nested":
        assert capture["render_state"]["scissor_enabled"] is True
        assert capture["render_state"]["stencil_enabled"] is True
        assert capture["render_state"]["stencil_value"] == 1
        assert capture["stencil_samples"] == {
            "center": 2,
            "rect_outside_left": 0,
            "rounded_corner_out_tl": 1,
            "rounded_edge_right": 1,
        }
        assert capture["restored_stencil_samples"] == {
            "center": 1,
            "rect_outside_left": 0,
            "rounded_corner_out_tl": 1,
            "rounded_edge_right": 1,
        }
    else:
        assert capture["stencil_samples"]["center"] == 1
        assert capture["stencil_samples"]["rect_outside_left"] == 0
        assert set(capture["restored_stencil_samples"].values()) == {0}
    assert capture["restored_gl"] == capture["inherited_gl"]
    assert set(capture["final_stencil_samples"].values()) == {0}
    assert capture["final_gl"] == capture["outer_inherited_gl"]
    assert capture["clip_frame"]["viewport"][2:] == capture["target_size"]
    assert capture["render_thread_id"] != report["gui_thread_id"]

    telemetry = report["telemetry"]
    assert telemetry["error"] is None
    assert telemetry["render_thread_id"] != report["gui_thread_id"]
    assert telemetry["release_thread_id"] == telemetry["render_thread_id"]
    assert telemetry["release_count"] == 1
    assert telemetry["invalidation_count"] == 1
    assert report["release_context_current"] is True
