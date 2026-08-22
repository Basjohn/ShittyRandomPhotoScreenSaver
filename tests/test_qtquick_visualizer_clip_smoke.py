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


def _run_visualizer_smoke(
    mode_id: str,
    case: str,
) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.qtquick_visualizer_clip_smoke",
            "--policy",
            mode_id,
            "--visualizer-case",
            case,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout[completed.stdout.index("{") :])


def _run_spectrum_smoke(case: str) -> dict[str, object]:
    return _run_visualizer_smoke("spectrum", case)


def _run_oscilloscope_smoke(case: str) -> dict[str, object]:
    return _run_visualizer_smoke("oscilloscope", case)


def _run_sine_smoke(case: str) -> dict[str, object]:
    return _run_visualizer_smoke("sine_wave", case)


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


@pytest.mark.parametrize(
    "case",
    ("canonical", "scaled", "wide", "tall", "idle", "ghost"),
)
def test_production_spectrum_draws_and_releases_inside_quick(case: str) -> None:
    report = _run_spectrum_smoke(case)

    assert report["valid"] is True
    assert report["error"] is None
    capture = report["captures"][case]
    assert capture["gl_error"] == 0
    assert capture["lit_pixel_count"] > 0
    assert capture["lit_column_count"] >= 16
    assert capture["lit_row_count"] >= 5
    assert capture["lit_bounds"] is not None

    telemetry = report["telemetry"]
    assert telemetry["error"] is None
    assert telemetry["draw_count"] >= 1
    assert telemetry["drawn_mode_id"] == "spectrum"
    assert telemetry["release_thread_id"] == telemetry["render_thread_id"]
    assert telemetry["release_count"] == 1
    assert telemetry["invalidation_count"] == 1
    assert report["release_context_current"] is True


def test_spectrum_quick_geometry_scales_and_reflows_without_image_stretch() -> None:
    canonical = _run_spectrum_smoke("canonical")["captures"]["canonical"]
    scaled = _run_spectrum_smoke("scaled")["captures"]["scaled"]
    wide = _run_spectrum_smoke("wide")["captures"]["wide"]
    tall = _run_spectrum_smoke("tall")["captures"]["tall"]

    assert scaled["outer_pixel_size"][0] == pytest.approx(
        canonical["outer_pixel_size"][0] * 0.65,
        abs=2,
    )
    assert scaled["outer_pixel_size"][1] == pytest.approx(
        canonical["outer_pixel_size"][1] * 0.65,
        abs=2,
    )
    assert scaled["lit_column_count"] < canonical["lit_column_count"]
    assert scaled["lit_row_count"] < canonical["lit_row_count"]

    assert wide["outer_pixel_size"][0] > canonical["outer_pixel_size"][0]
    assert wide["outer_pixel_size"][1] == canonical["outer_pixel_size"][1]
    assert wide["lit_column_count"] > canonical["lit_column_count"]
    assert tall["outer_pixel_size"][0] == canonical["outer_pixel_size"][0]
    assert tall["outer_pixel_size"][1] > canonical["outer_pixel_size"][1]
    assert tall["lit_row_count"] > canonical["lit_row_count"]


def test_paused_idle_and_peak_ghost_are_visible_real_quick_pixels() -> None:
    idle = _run_spectrum_smoke("idle")["captures"]["idle"]
    ghost = _run_spectrum_smoke("ghost")["captures"]["ghost"]

    assert idle["lit_column_count"] >= 16
    assert idle["lit_row_count"] >= 8
    # Ghost input bars are uniformly low; the immutable peak field must still
    # produce a tall fading trail in the actual Quick shader.
    assert ghost["lit_row_count"] > idle["lit_row_count"] * 2


@pytest.mark.parametrize(
    "case",
    ("canonical", "scaled", "wide", "tall", "idle", "ghost"),
)
def test_production_oscilloscope_draws_and_releases_inside_quick(
    case: str,
) -> None:
    report = _run_oscilloscope_smoke(case)

    assert report["valid"] is True
    assert report["error"] is None
    capture = report["captures"][case]
    assert capture["gl_error"] == 0
    assert capture["lit_pixel_count"] > 0
    assert capture["lit_column_count"] >= 64
    assert capture["lit_row_count"] >= 8
    assert capture["lit_bounds"] is not None

    telemetry = report["telemetry"]
    assert telemetry["error"] is None
    assert telemetry["draw_count"] >= 1
    assert telemetry["drawn_mode_id"] == "oscilloscope"
    assert telemetry["release_thread_id"] == telemetry["render_thread_id"]
    assert telemetry["release_count"] == 1
    assert telemetry["invalidation_count"] == 1
    assert report["release_context_current"] is True


def test_oscilloscope_quick_geometry_reflows_without_bitmap_stretch() -> None:
    canonical = _run_oscilloscope_smoke("canonical")["captures"]["canonical"]
    scaled = _run_oscilloscope_smoke("scaled")["captures"]["scaled"]
    wide = _run_oscilloscope_smoke("wide")["captures"]["wide"]
    tall = _run_oscilloscope_smoke("tall")["captures"]["tall"]

    assert scaled["outer_pixel_size"][0] == pytest.approx(
        canonical["outer_pixel_size"][0] * 0.65,
        abs=2,
    )
    assert scaled["outer_pixel_size"][1] == pytest.approx(
        canonical["outer_pixel_size"][1] * 0.65,
        abs=2,
    )
    assert scaled["lit_column_count"] < canonical["lit_column_count"]
    assert scaled["lit_row_count"] < canonical["lit_row_count"]

    assert wide["outer_pixel_size"][0] > canonical["outer_pixel_size"][0]
    assert wide["outer_pixel_size"][1] == canonical["outer_pixel_size"][1]
    assert wide["lit_column_count"] > canonical["lit_column_count"]
    assert wide["lit_row_count"] == canonical["lit_row_count"]

    assert tall["outer_pixel_size"][0] == canonical["outer_pixel_size"][0]
    assert tall["outer_pixel_size"][1] > canonical["outer_pixel_size"][1]
    assert tall["lit_column_count"] == canonical["lit_column_count"]
    assert tall["lit_row_count"] > canonical["lit_row_count"]


def test_oscilloscope_idle_carrier_and_delayed_ghost_are_real_quick_pixels() -> None:
    canonical = _run_oscilloscope_smoke("canonical")["captures"]["canonical"]
    idle = _run_oscilloscope_smoke("idle")["captures"]["idle"]
    ghost = _run_oscilloscope_smoke("ghost")["captures"]["ghost"]

    assert idle["lit_column_count"] >= 64
    assert idle["lit_row_count"] >= 20
    assert ghost["lit_pixel_count"] > canonical["lit_pixel_count"] * 1.04


@pytest.mark.parametrize(
    "case",
    ("canonical", "scaled", "wide", "tall", "idle", "ghost"),
)
def test_production_sine_draws_and_releases_inside_quick(case: str) -> None:
    report = _run_sine_smoke(case)

    assert report["valid"] is True
    assert report["error"] is None
    capture = report["captures"][case]
    assert capture["gl_error"] == 0
    assert capture["lit_pixel_count"] > 0
    assert capture["lit_column_count"] >= 64
    assert capture["lit_row_count"] >= 8
    assert capture["lit_bounds"] is not None

    telemetry = report["telemetry"]
    assert telemetry["error"] is None
    assert telemetry["draw_count"] >= 1
    assert telemetry["drawn_mode_id"] == "sine_wave"
    assert telemetry["release_thread_id"] == telemetry["render_thread_id"]
    assert telemetry["release_count"] == 1
    assert telemetry["invalidation_count"] == 1
    assert report["release_context_current"] is True


def test_sine_quick_geometry_reflows_without_bitmap_stretch() -> None:
    canonical = _run_sine_smoke("canonical")["captures"]["canonical"]
    scaled = _run_sine_smoke("scaled")["captures"]["scaled"]
    wide = _run_sine_smoke("wide")["captures"]["wide"]
    tall = _run_sine_smoke("tall")["captures"]["tall"]

    assert scaled["outer_pixel_size"][0] == pytest.approx(
        canonical["outer_pixel_size"][0] * 0.65,
        abs=2,
    )
    assert scaled["outer_pixel_size"][1] == pytest.approx(
        canonical["outer_pixel_size"][1] * 0.65,
        abs=2,
    )
    assert scaled["lit_column_count"] < canonical["lit_column_count"]
    assert scaled["lit_row_count"] < canonical["lit_row_count"]

    assert wide["outer_pixel_size"][0] > canonical["outer_pixel_size"][0]
    assert wide["outer_pixel_size"][1] == canonical["outer_pixel_size"][1]
    assert wide["lit_column_count"] > canonical["lit_column_count"]
    assert tall["outer_pixel_size"][0] == canonical["outer_pixel_size"][0]
    assert tall["outer_pixel_size"][1] > canonical["outer_pixel_size"][1]
    assert tall["lit_row_count"] > canonical["lit_row_count"]


def test_sine_idle_carrier_and_peak_ghost_are_real_quick_pixels() -> None:
    canonical = _run_sine_smoke("canonical")["captures"]["canonical"]
    idle = _run_sine_smoke("idle")["captures"]["idle"]
    ghost = _run_sine_smoke("ghost")["captures"]["ghost"]

    assert idle["lit_column_count"] >= 64
    assert idle["lit_row_count"] >= 8
    assert ghost["lit_pixel_count"] > canonical["lit_pixel_count"]
