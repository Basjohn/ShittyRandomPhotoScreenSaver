from __future__ import annotations

import math

from rendering.custom_child_geometry import (
    CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY,
    CHILD_RESIZE_HANDLES,
    CustomChildRoleDescriptor,
    CustomChildSize,
    flip_child_alignment,
    freeform_layout_block_child_role,
    normalize_child_geometry,
    resolve_child_move_geometry,
    resolve_child_resize_geometry,
    set_child_semantic_anchor,
    update_child_geometry_payload,
)


def _movable_role(role_id: str = "title") -> CustomChildRoleDescriptor:
    return freeform_layout_block_child_role(
        role_id,
        resize_handles=("top_left", "bottom_right"),
        movable=True,
    )


def test_legacy_size_only_child_payload_remains_authored_relative() -> None:
    role = _movable_role()
    resolved = normalize_child_geometry(
        {"title": {"width_scale": 1.4, "height_scale": 0.8}},
        (role,),
    )

    assert resolved["title"] == CustomChildSize(1.4, 0.8, 0.0, 0.0)


def test_movable_child_offsets_round_trip_inside_existing_geometry_carrier() -> None:
    role = _movable_role()
    geometry = CustomChildSize(1.25, 0.75, -0.12, 0.18)

    payload = update_child_geometry_payload({}, (role,), {"title": geometry})
    assert payload == {
        CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY: {
            "title": {
                "width_scale": 1.25,
                "height_scale": 0.75,
                "x_offset": -0.12,
                "y_offset": 0.18,
            }
        }
    }
    assert normalize_child_geometry(
        payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY], (role,)
    ) == {"title": geometry}


def test_non_movable_role_sanitizes_persisted_offsets_without_second_authority() -> None:
    role = CustomChildRoleDescriptor(
        "badge",
        resize_handles=("bottom_right",),
        movable=False,
    )
    resolved = normalize_child_geometry(
        {
            "badge": {
                "width_scale": 1.3,
                "height_scale": 1.2,
                "x_offset": 0.9,
                "y_offset": -0.7,
            }
        },
        (role,),
    )

    assert resolved["badge"] == CustomChildSize(1.3, 1.2, 0.0, 0.0)


def test_live_child_mutation_preserves_unknown_role_payload_for_forward_tolerance() -> None:
    role = _movable_role()
    payload = {
        CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY: {
            "retired_future_role": {"width_scale": 2.0, "x_offset": 0.4},
            "title": {"width_scale": 1.1},
        },
        "content_extent": [800, 500],
    }

    updated = update_child_geometry_payload(
        payload,
        (role,),
        {"title": CustomChildSize(1.5, 1.0, 0.2, 0.0)},
    )

    assert updated["content_extent"] == [800, 500]
    assert updated[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY]["retired_future_role"] == {
        "width_scale": 2.0,
        "x_offset": 0.4,
    }
    assert updated[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY]["title"] == {
        "width_scale": 1.5,
        "height_scale": 1.0,
        "x_offset": 0.2,
    }


def test_resize_preview_resolver_clamps_before_parent_can_observe_overflow() -> None:
    role = freeform_layout_block_child_role(
        "title",
        resize_handles=("bottom_right",),
        minimum_scale=(0.5, 0.5),
        maximum_scale=(1.5, 1.25),
        movable=True,
    )

    resolved = resolve_child_resize_geometry(
        role,
        CustomChildSize(),
        handle="bottom_right",
        raw_dx=5000.0,
        raw_dy=5000.0,
        visible_width=200.0,
        visible_height=100.0,
        normalization_width=600.0,
        normalization_height=300.0,
        outer_scale=1.0,
    )

    assert resolved.geometry == CustomChildSize(1.5, 1.25, 0.0, 0.0)
    assert resolved.visible_width == 300.0
    assert resolved.visible_height == 125.0


def test_left_top_resize_resolver_persists_clamped_opposite_edge_anchor() -> None:
    role = _movable_role()

    resolved = resolve_child_resize_geometry(
        role,
        CustomChildSize(),
        handle="top_left",
        raw_dx=40.0,
        raw_dy=20.0,
        visible_width=200.0,
        visible_height=100.0,
        normalization_width=400.0,
        normalization_height=200.0,
        outer_scale=2.0,
    )

    assert resolved.visible_width == 160.0
    assert resolved.visible_height == 80.0
    assert resolved.geometry.width_scale == 0.8
    assert resolved.geometry.height_scale == 0.8
    # Shrinking from left/top moves the authored-relative origin inward by the
    # exact rendered delta divided by outer scale and stable normalization box.
    assert resolved.geometry.x_offset == 0.05
    assert resolved.geometry.y_offset == 0.05


def test_uniform_resize_resolver_uses_one_canonical_scale_for_preview_and_commit() -> None:
    role = CustomChildRoleDescriptor(
        "badge",
        minimum_scale=(0.5, 0.5),
        maximum_scale=(1.4, 1.4),
        uniform_scale=True,
        movable=False,
        resize_handles=("bottom_right",),
    )

    resolved = resolve_child_resize_geometry(
        role,
        CustomChildSize(),
        handle="bottom_right",
        raw_dx=120.0,
        raw_dy=10.0,
        visible_width=100.0,
        visible_height=50.0,
        normalization_width=500.0,
        normalization_height=250.0,
        outer_scale=1.0,
    )

    assert resolved.geometry == CustomChildSize(1.4, 1.4, 0.0, 0.0)
    assert resolved.visible_width == 140.0
    assert resolved.visible_height == 70.0


def test_move_resolver_folds_reflow_compensation_only_on_real_movement() -> None:
    role = _movable_role()
    origin = CustomChildSize()

    untouched = resolve_child_move_geometry(
        role,
        origin,
        raw_dx=0.0,
        raw_dy=0.0,
        normalization_width=700.0,
        normalization_height=400.0,
        outer_scale=1.0,
        placement_compensation_x=70.0,
        placement_compensation_y=40.0,
    )
    assert untouched == origin

    detached = resolve_child_move_geometry(
        role,
        origin,
        raw_dx=7.0,
        raw_dy=4.0,
        normalization_width=700.0,
        normalization_height=400.0,
        outer_scale=1.0,
        placement_compensation_x=70.0,
        placement_compensation_y=40.0,
    )
    assert detached.x_offset == 0.11
    assert detached.y_offset == 0.11

    repeated = resolve_child_move_geometry(
        role,
        detached,
        raw_dx=7.0,
        raw_dy=4.0,
        normalization_width=700.0,
        normalization_height=400.0,
        outer_scale=1.0,
    )
    assert repeated.x_offset == 0.12
    assert repeated.y_offset == 0.12


def test_child_roles_default_to_all_four_resize_corners() -> None:
    role = freeform_layout_block_child_role("title", movable=True)
    assert role.resize_handles == CHILD_RESIZE_HANDLES


def test_alignment_flip_round_trips_inside_existing_child_geometry_record() -> None:
    role = CustomChildRoleDescriptor(
        "title",
        movable=True,
        alignment_flip=True,
        authored_alignment="left",
    )
    authored = CustomChildSize()
    flipped = flip_child_alignment(role, authored)
    assert flipped.alignment == "right"
    payload = update_child_geometry_payload({}, (role,), {"title": flipped})
    assert payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY]["title"] == {
        "width_scale": 1.0,
        "height_scale": 1.0,
        "alignment": "right",
    }
    assert normalize_child_geometry(
        payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY], (role,)
    )["title"].alignment == "right"

    restored = flip_child_alignment(role, flipped)
    assert restored.is_authored
    assert update_child_geometry_payload({}, (role,), {"title": restored}) == {}


def test_semantic_corner_anchor_round_trips_and_detaches_only_on_real_move() -> None:
    role = CustomChildRoleDescriptor(
        "header",
        movable=True,
        uniform_scale=True,
        alignment_flip=True,
        semantic_corner_anchor=True,
    )
    anchored = set_child_semantic_anchor(role, CustomChildSize(), "top_right")
    assert anchored.anchor == "top_right"
    payload = update_child_geometry_payload({}, (role,), {"header": anchored})
    assert payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY]["header"]["anchor"] == "top_right"
    assert normalize_child_geometry(
        payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY], (role,)
    )["header"].anchor == "top_right"

    clicked = resolve_child_move_geometry(
        role,
        anchored,
        raw_dx=0.0,
        raw_dy=0.0,
        normalization_width=600.0,
        normalization_height=300.0,
        outer_scale=1.0,
        placement_compensation_x=120.0,
        placement_compensation_y=0.0,
    )
    assert clicked.anchor == "top_right"
    assert clicked.x_offset == 0.0

    detached = resolve_child_move_geometry(
        role,
        anchored,
        raw_dx=-20.0,
        raw_dy=10.0,
        normalization_width=600.0,
        normalization_height=300.0,
        outer_scale=1.0,
        placement_compensation_x=120.0,
        placement_compensation_y=0.0,
    )
    assert detached.anchor is None
    assert math.isclose(detached.x_offset, (120.0 - 20.0) / 600.0)
    assert math.isclose(detached.y_offset, 10.0 / 300.0)


def test_semantic_anchor_is_ignored_for_roles_that_do_not_declare_it() -> None:
    role = _movable_role("ordinary")
    attempted = set_child_semantic_anchor(role, CustomChildSize(), "bottom_left")
    assert attempted == CustomChildSize()
    resolved = normalize_child_geometry(
        {"ordinary": {"width_scale": 1.2, "anchor": "bottom_left"}}, (role,)
    )
    assert resolved["ordinary"].anchor is None


def test_one_axis_child_resize_edges_follow_role_semantics() -> None:
    free = CustomChildRoleDescriptor(
        "free",
        axes=("horizontal", "vertical"),
        movable=True,
    )
    assert free.resize_edges() == ("left", "right", "top", "bottom")
    assert free.admits_resize_handle("left")
    assert free.admits_resize_handle("bottom")

    size_only = CustomChildRoleDescriptor(
        "size_only",
        axes=("horizontal", "vertical"),
        movable=False,
    )
    assert size_only.resize_edges() == ("right", "bottom")
    assert not size_only.admits_resize_handle("left")

    intrinsic = CustomChildRoleDescriptor(
        "intrinsic",
        axes=("horizontal", "vertical"),
        movable=True,
        uniform_scale=True,
    )
    assert intrinsic.resize_edges() == ()


def test_one_axis_resize_changes_only_requested_axis_and_preserves_opposite_edge() -> None:
    role = CustomChildRoleDescriptor(
        "block",
        axes=("horizontal", "vertical"),
        movable=True,
    )
    origin = CustomChildSize(width_scale=1.0, height_scale=1.0)

    horizontal = resolve_child_resize_geometry(
        role,
        origin,
        handle="right",
        raw_dx=40.0,
        raw_dy=999.0,
        visible_width=200.0,
        visible_height=100.0,
        normalization_width=600.0,
        normalization_height=300.0,
        outer_scale=1.0,
    )
    assert horizontal.geometry.width_scale == 1.2
    assert horizontal.geometry.height_scale == 1.0

    left = resolve_child_resize_geometry(
        role,
        origin,
        handle="left",
        raw_dx=20.0,
        raw_dy=0.0,
        visible_width=200.0,
        visible_height=100.0,
        normalization_width=600.0,
        normalization_height=300.0,
        outer_scale=1.0,
    )
    assert left.geometry.width_scale == 0.9
    assert math.isclose(left.geometry.x_offset, 20.0 / 600.0)

    vertical = resolve_child_resize_geometry(
        role,
        origin,
        handle="bottom",
        raw_dx=777.0,
        raw_dy=25.0,
        visible_width=200.0,
        visible_height=100.0,
        normalization_width=600.0,
        normalization_height=300.0,
        outer_scale=1.0,
    )
    assert vertical.geometry.width_scale == 1.0
    assert vertical.geometry.height_scale == 1.25
