"""Shared authored widget stacking planner for non-CUSTOM overlays."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Literal


StackLane = Literal["left", "center", "right"]
StackBand = Literal["top", "middle", "bottom"]


@dataclass(frozen=True)
class StackParticipant:
    """One authored-position widget participating in non-CUSTOM stacking."""

    key: str
    lane: StackLane
    band: StackBand
    base_y: int
    height: int
    order: int


@dataclass(frozen=True)
class StackObstacle:
    """A fixed occupied lane interval that movable widgets must avoid."""

    key: str
    lane: StackLane
    top_y: int
    height: int


@dataclass(frozen=True)
class StackPlacement:
    """Resolved stacking placement for one participant."""

    desired_y: int
    offset_y: int


@dataclass(frozen=True)
class StackPlan:
    """Resolved stacking plan for one layout pass."""

    placements: Dict[str, StackPlacement]
    lane_fit: Dict[StackLane, bool]
    lane_spacing: Dict[StackLane, int]


def get_stack_lane(position_key: str) -> StackLane | None:
    pos = str(position_key or "").strip().lower()
    if "left" in pos:
        return "left"
    if "right" in pos:
        return "right"
    if "center" in pos:
        return "center"
    return None


def get_stack_band(position_key: str) -> StackBand | None:
    pos = str(position_key or "").strip().lower()
    if "top" in pos:
        return "top"
    if "bottom" in pos:
        return "bottom"
    if "middle" in pos or "center" in pos:
        return "middle"
    return None


def build_stack_plan(
    participants: Iterable[StackParticipant],
    *,
    obstacles: Iterable[StackObstacle] | None = None,
    container_height: int,
    spacing: int = 10,
    margin: int = 20,
) -> StackPlan:
    grouped: dict[StackLane, list[StackParticipant]] = {
        "left": [],
        "center": [],
        "right": [],
    }
    for participant in participants:
        grouped[participant.lane].append(participant)

    grouped_obstacles: dict[StackLane, list[StackObstacle]] = {
        "left": [],
        "center": [],
        "right": [],
    }
    for obstacle in obstacles or ():
        grouped_obstacles[obstacle.lane].append(obstacle)

    placements: Dict[str, StackPlacement] = {}
    lane_fit: Dict[StackLane, bool] = {}
    lane_spacing: Dict[StackLane, int] = {}

    for lane, members in grouped.items():
        lane_placements, fits, resolved_spacing = _plan_lane(
            members,
            obstacles=grouped_obstacles[lane],
            container_height=container_height,
            spacing=spacing,
            margin=margin,
        )
        placements.update(lane_placements)
        lane_fit[lane] = fits
        lane_spacing[lane] = resolved_spacing

    return StackPlan(placements=placements, lane_fit=lane_fit, lane_spacing=lane_spacing)


def _plan_lane(
    members: list[StackParticipant],
    *,
    obstacles: list[StackObstacle],
    container_height: int,
    spacing: int,
    margin: int,
) -> tuple[Dict[str, StackPlacement], bool, int]:
    if not members:
        return {}, True, spacing

    fixed_intervals = _normalize_obstacles(
        obstacles,
        container_height=container_height,
        margin=margin,
    )

    band_rank = {"top": 0, "middle": 1, "bottom": 2}
    ordered = sorted(members, key=lambda item: (band_rank[item.band], item.base_y, item.order))
    available_height = max(1, container_height - (margin * 2))
    available_height -= sum(bottom - top for top, bottom in fixed_intervals)
    total_height = sum(member.height for member in ordered)
    gap_count = max(0, len(ordered) - 1)
    fits = (total_height + (gap_count * spacing)) <= available_height

    top_members = [member for member in ordered if member.band == "top"]
    middle_members = [member for member in ordered if member.band == "middle"]
    bottom_members = [member for member in ordered if member.band == "bottom"]
    desired_map: Dict[str, int] = {}

    # Top band: preserve authored y unless overlap forces a push downward.
    cursor_y = margin
    for member in top_members:
        desired_y = _push_down_past_obstacles(
            max(member.base_y, cursor_y),
            member.height,
            fixed_intervals,
            spacing,
        )
        desired_map[member.key] = desired_y
        cursor_y = desired_y + member.height + spacing
    top_limit = cursor_y - spacing if top_members else margin

    # Bottom band: preserve authored y unless overlap forces a pull upward.
    bottom_limit = container_height - margin
    cursor_bottom = bottom_limit
    for member in reversed(bottom_members):
        authored_y = _pull_up_above_obstacles(
            min(member.base_y, cursor_bottom - member.height),
            member.height,
            fixed_intervals,
            spacing,
            margin,
        )
        desired_map[member.key] = authored_y
        cursor_bottom = authored_y - spacing
    bottom_start = cursor_bottom + spacing if bottom_members else bottom_limit

    # Middle band: fit the authored cluster into the gap between top and bottom.
    if middle_members:
        middle_total_height = sum(member.height for member in middle_members)
        middle_gap_count = max(0, len(middle_members) - 1)
        middle_cluster_height = middle_total_height + (middle_gap_count * spacing)
        authored_start = min(member.base_y for member in middle_members)
        free_segments = _compute_free_segments(
            fixed_intervals,
            top_limit + (spacing if top_members else 0),
            bottom_start - (spacing if bottom_members else 0),
        )
        middle_start = authored_start
        if free_segments:
            middle_start = _resolve_middle_start(
                free_segments,
                authored_start,
                middle_cluster_height,
            )

        cursor_y = middle_start
        for member in middle_members:
            desired_map[member.key] = cursor_y
            cursor_y += member.height + spacing

    desired_positions = [desired_map.get(member.key, member.base_y) for member in ordered]

    placements: Dict[str, StackPlacement] = {}
    for member, desired_y in zip(ordered, desired_positions):
        placements[member.key] = StackPlacement(
            desired_y=desired_y,
            offset_y=desired_y - member.base_y,
        )

    resolved_spacing = spacing
    if len(desired_positions) > 1:
        resolved_spacing = min(
            desired_positions[index + 1] - (desired_positions[index] + ordered[index].height)
            for index in range(len(desired_positions) - 1)
        )
    return placements, fits, resolved_spacing


def _normalize_obstacles(
    obstacles: list[StackObstacle],
    *,
    container_height: int,
    margin: int,
) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    lower_bound = margin
    upper_bound = max(lower_bound, container_height - margin)
    for obstacle in sorted(obstacles, key=lambda item: item.top_y):
        top = max(lower_bound, int(obstacle.top_y))
        bottom = min(upper_bound, top + max(0, int(obstacle.height)))
        if bottom > top:
            intervals.append((top, bottom))
    return intervals


def _push_down_past_obstacles(
    y: int,
    height: int,
    obstacles: list[tuple[int, int]],
    spacing: int,
) -> int:
    candidate = y
    while True:
        overlap = next(
            (
                (top, bottom)
                for top, bottom in obstacles
                if candidate < bottom + spacing and candidate + height > top - spacing
            ),
            None,
        )
        if overlap is None:
            return candidate
        _top, bottom = overlap
        candidate = bottom + spacing


def _pull_up_above_obstacles(
    y: int,
    height: int,
    obstacles: list[tuple[int, int]],
    spacing: int,
    margin: int,
) -> int:
    candidate = y
    while True:
        overlap = next(
            (
                (top, bottom)
                for top, bottom in reversed(obstacles)
                if candidate < bottom + spacing and candidate + height > top - spacing
            ),
            None,
        )
        if overlap is None:
            return max(margin, candidate)
        top, _bottom = overlap
        candidate = top - spacing - height


def _compute_free_segments(
    obstacles: list[tuple[int, int]],
    lower_bound: int,
    upper_bound: int,
) -> list[tuple[int, int]]:
    if upper_bound <= lower_bound:
        return []
    segments: list[tuple[int, int]] = []
    cursor = lower_bound
    for top, bottom in obstacles:
        if bottom <= lower_bound or top >= upper_bound:
            continue
        clipped_top = max(lower_bound, top)
        clipped_bottom = min(upper_bound, bottom)
        if clipped_top > cursor:
            segments.append((cursor, clipped_top))
        cursor = max(cursor, clipped_bottom)
    if cursor < upper_bound:
        segments.append((cursor, upper_bound))
    return segments


def _resolve_middle_start(
    segments: list[tuple[int, int]],
    authored_start: int,
    cluster_height: int,
) -> int:
    fitting_segments = [
        (start, end)
        for start, end in segments
        if (end - start) >= cluster_height
    ]
    if fitting_segments:
        best_start = fitting_segments[0][0]
        best_distance = None
        for start, end in fitting_segments:
            candidate = max(start, min(authored_start, end - cluster_height))
            distance = abs(candidate - authored_start)
            if best_distance is None or distance < best_distance:
                best_start = candidate
                best_distance = distance
        return best_start
    largest = max(segments, key=lambda item: item[1] - item[0], default=(authored_start, authored_start))
    return largest[0]
