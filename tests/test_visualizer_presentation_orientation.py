"""CUSTOM Visualizer quarter-turn presentation contracts."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from tests._visualizer_presentation import (
    resolve_presentation as resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.presentation_geometry import (
    resize_visualizer_presentation,
)
from widgets.spotify_visualizer.presentation_orientation import (
    CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY,
    CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY,
    content_rotation_map_from_legacy,
    logical_rect_from_physical_rect,
    logical_uv_from_physical_uv,
    normalize_content_rotation_by_mode,
    normalize_content_rotation_quarters,
    oriented_size,
    resolve_content_rotation_for_mode,
    rotate_quarters_clockwise,
    set_content_rotation_for_mode,
)


def test_quarter_turn_token_is_optional_backward_compatible_layout_state() -> None:
    assert CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY == "content_rotation_quarters"
    assert normalize_content_rotation_quarters(None) == 0
    assert normalize_content_rotation_quarters("bad") == 0
    assert normalize_content_rotation_quarters(-1) == 0
    assert normalize_content_rotation_quarters(4) == 0
    assert [normalize_content_rotation_quarters(value) for value in range(4)] == [0, 1, 2, 3]



def test_per_mode_rotation_map_is_sparse_capability_gated_and_legacy_safe() -> None:
    assert CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY == "content_rotation_quarters_by_mode"
    rotations = normalize_content_rotation_by_mode(
        {
            "bubble": 1,
            "spectrum": 3,
            "oscilloscope": 0,
            "sphere": 2,
            "unknown": 1,
        }
    )
    assert rotations == {"bubble": 1, "spectrum": 3}
    assert resolve_content_rotation_for_mode(rotations, "bubble") == 1
    assert resolve_content_rotation_for_mode(rotations, "spectrum") == 3
    assert resolve_content_rotation_for_mode(rotations, "oscilloscope") == 0
    assert resolve_content_rotation_for_mode(rotations, "sphere") == 0
    assert resolve_content_rotation_for_mode({}, "bubble", legacy_value=2) == 2
    migrated = content_rotation_map_from_legacy(2)
    assert migrated == {
        "spectrum": 2,
        "oscilloscope": 2,
        "sine_wave": 2,
        "bubble": 2,
        "devcurve": 2,
    }
    assert "sphere" not in migrated

    rotations = set_content_rotation_for_mode(rotations, "bubble", 2)
    rotations = set_content_rotation_for_mode(rotations, "devcurve", 1)
    rotations = set_content_rotation_for_mode(rotations, "spectrum", 0)
    assert rotations == {"bubble": 2, "devcurve": 1}


def test_four_clockwise_clicks_are_identity_and_odd_turns_only_swap_axes() -> None:
    rotation = 0
    seen = []
    for _ in range(4):
        rotation = rotate_quarters_clockwise(rotation)
        seen.append(rotation)
    assert seen == [1, 2, 3, 0]
    assert rotate_quarters_clockwise(1, 3) == 0

    size = (630.0, 280.0)
    assert oriented_size(size, 0) == size
    assert oriented_size(size, 1) == (280.0, 630.0)
    assert oriented_size(size, 2) == size
    assert oriented_size(size, 3) == (280.0, 630.0)


def test_shared_physical_to_logical_transform_has_expected_clockwise_basis() -> None:
    assert logical_uv_from_physical_uv((0.0, 0.0), 0) == (0.0, 0.0)
    assert logical_uv_from_physical_uv((0.0, 0.0), 1) == (0.0, 1.0)
    assert logical_uv_from_physical_uv((0.0, 0.0), 2) == (1.0, 1.0)
    assert logical_uv_from_physical_uv((0.0, 0.0), 3) == (1.0, 0.0)

    physical = (10.0, 20.0, 100.0, 50.0)
    assert logical_rect_from_physical_rect(
        physical,
        physical_size=(300.0, 200.0),
        content_rotation_quarters=1,
    ) == pytest.approx((20.0, 190.0, 50.0, 100.0))
    assert logical_rect_from_physical_rect(
        physical,
        physical_size=(300.0, 200.0),
        content_rotation_quarters=3,
    ) == pytest.approx((130.0, 10.0, 50.0, 100.0))


def test_rotation_changes_logical_domain_without_changing_physical_custom_geometry() -> None:
    policy = get_visualizer_presentation_policy("bubble")
    baseline = resolve_visualizer_presentation(
        policy=policy,
        display_size=(1920.0, 1080.0),
        outer_origin=(80.0, 60.0),
        viewport_extent=(630.0, 280.0),
    )
    rotated = resize_visualizer_presentation(
        baseline,
        display_size=(1920.0, 1080.0),
        outer_origin=(80.0, 60.0),
        relative_scale=1.0,
        viewport_extent=(630.0, 280.0),
        content_rotation_quarters=1,
    )

    assert rotated.outer_rect == baseline.outer_rect
    assert rotated.uniform_visual_scale == baseline.uniform_visual_scale
    assert rotated.viewport_extent == baseline.viewport_extent == (630.0, 280.0)
    assert baseline.logical_viewport_extent == (630.0, 280.0)
    assert rotated.logical_viewport_extent == (280.0, 630.0)
    assert rotated.current_aspect_ratio == pytest.approx(280.0 / 630.0)


def test_only_accepted_carded_modes_admit_custom_content_rotation() -> None:
    for mode_id in ("spectrum", "oscilloscope", "sine_wave", "bubble", "devcurve"):
        assert get_visualizer_presentation_policy(mode_id).content_rotation_capable is True
    assert get_visualizer_presentation_policy("sphere").content_rotation_capable is False


def test_per_mode_rotation_roundtrip_stays_on_existing_custom_layout_owner() -> None:
    root = Path(__file__).resolve().parents[1]
    custom_owner = (root / "rendering/quick/custom_layout_owner.py").read_text(encoding="utf-8")
    scene = (root / "rendering/quick/scene_controller.py").read_text(encoding="utf-8")
    display = (root / "engine/display_manager.py").read_text(encoding="utf-8")
    quick_owner = (
        root / "widgets/spotify_visualizer/quick_display_visualizer_owner.py"
    ).read_text(encoding="utf-8")

    assert "CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY" in custom_owner
    assert "owner.controller.committed_content_rotations" in custom_owner
    assert "content_rotation_by_mode=item.current_size_payload.get(" in custom_owner
    assert "CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY" in scene
    assert "resolve_content_rotation_for_mode" in scene
    assert "CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY" in display
    assert "content_rotation_by_mode=custom_entry.size_payload.get(" in display
    assert "commit_content_rotation_map(content_rotation_by_mode)" in quick_owner
