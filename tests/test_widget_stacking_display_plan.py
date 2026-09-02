"""Display-wide authored stacking contracts (non-CUSTOM only)."""
from __future__ import annotations

from rendering.widget_stacking import (
    DisplayStackObstacle,
    DisplayStackParticipant,
    build_display_stack_plan,
)


def _rects_overlap(a, b, spacing=10):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (
        ax + aw + spacing <= bx
        or bx + bw + spacing <= ax
        or ay + ah + spacing <= by
        or by + bh + spacing <= ay
    )


def test_display_stack_spills_same_top_right_destination_across_display_slots():
    participants = [
        DisplayStackParticipant(
            key=f"widget_{index}",
            position_key="Top Right",
            base_x=1670,
            base_y=30,
            width=220,
            height=120,
            order=index,
            margin=30,
        )
        for index in range(10)
    ]

    plan = build_display_stack_plan(
        participants,
        container_width=1920,
        container_height=1080,
        spacing=10,
    )

    assert plan.all_fit is True
    assert plan.unresolved == ()
    assert plan.placements["widget_0"].slot == "top_right"
    assert plan.placements["widget_1"].slot == "middle_right"
    assert plan.placements["widget_2"].slot == "bottom_right"
    assert {placement.slot for placement in plan.placements.values()} >= {
        "top_right",
        "middle_right",
        "bottom_right",
        "top_center",
        "center",
        "bottom_center",
        "top_left",
        "middle_left",
        "bottom_left",
    }

    rects = []
    for participant in participants:
        placement = plan.placements[participant.key]
        rect = (
            placement.desired_x,
            placement.desired_y,
            participant.width,
            participant.height,
        )
        assert not any(_rects_overlap(rect, other) for other in rects)
        rects.append(rect)


def test_display_stack_respects_fixed_media_visualizer_obstacles():
    participants = [
        DisplayStackParticipant(
            key="clock",
            position_key="Top Right",
            base_x=1570,
            base_y=30,
            width=320,
            height=180,
            order=0,
            margin=30,
        ),
        DisplayStackParticipant(
            key="gmail",
            position_key="Top Right",
            base_x=1390,
            base_y=30,
            width=500,
            height=300,
            order=1,
            margin=30,
        ),
    ]
    obstacles = (
        DisplayStackObstacle("media", 1450, 30, 440, 180),
        DisplayStackObstacle("spotify_visualizer", 1450, 230, 420, 280),
    )

    plan = build_display_stack_plan(
        participants,
        obstacles=obstacles,
        container_width=1920,
        container_height=1080,
        spacing=10,
    )

    assert plan.all_fit is True
    for participant in participants:
        placement = plan.placements[participant.key]
        rect = (
            placement.desired_x,
            placement.desired_y,
            participant.width,
            participant.height,
        )
        assert all(
            not _rects_overlap(
                rect,
                (obstacle.x, obstacle.y, obstacle.width, obstacle.height),
            )
            for obstacle in obstacles
        )



def test_display_stack_handles_varied_card_sizes_from_one_authored_corner():
    sizes = [
        ("media", 520, 300),
        ("gmail", 620, 420),
        ("reddit", 520, 440),
        ("weather", 440, 330),
        ("clock", 420, 190),
        ("achievement", 460, 360),
        ("abandonment", 500, 380),
        ("reddit2", 520, 440),
        ("steam_progress", 500, 350),
        ("friend_pulse", 460, 330),
    ]
    participants = [
        DisplayStackParticipant(
            key=key,
            position_key="Top Right",
            base_x=2560 - 30 - width,
            base_y=30,
            width=width,
            height=height,
            order=index,
            margin=30,
        )
        for index, (key, width, height) in enumerate(sizes)
    ]

    plan = build_display_stack_plan(
        participants,
        container_width=2560,
        container_height=1440,
        spacing=10,
    )

    assert plan.all_fit is True
    assert plan.unresolved == ()
    rects = []
    for participant in participants:
        placement = plan.placements[participant.key]
        rect = (
            placement.desired_x,
            placement.desired_y,
            participant.width,
            participant.height,
        )
        assert not any(_rects_overlap(rect, other) for other in rects)
        rects.append(rect)

def test_display_stack_reports_genuinely_overfull_display_without_looping():
    participants = [
        DisplayStackParticipant(
            key=f"huge_{index}",
            position_key="Center",
            base_x=20,
            base_y=20,
            width=760,
            height=560,
            order=index,
            margin=20,
        )
        for index in range(4)
    ]

    plan = build_display_stack_plan(
        participants,
        container_width=800,
        container_height=600,
        spacing=10,
    )

    assert plan.all_fit is False
    assert plan.unresolved
