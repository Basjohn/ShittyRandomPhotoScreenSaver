"""Bounded owner-level CUSTOM child Save/reopen and content-floor regressions.

These exercise the real normalized persistence writer and committed hydration
reader without an artificial Qt scene or a new runtime observer.  Painted-child
and pointer-delivery assertions belong to separate, real QQuickWindow tests.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from rendering.custom_layout_commit import _write_item  # shared CUSTOM item write
import pytest
from PySide6.QtCore import QPoint, QRect, QSize

from rendering.custom_child_geometry import (
    CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY,
    CustomChildSize,
    normalize_child_geometry,
    update_child_geometry_payload,
)
from rendering.custom_layout_contract import (
    load_custom_layout_map,
    resolve_resize_edge_snap,
    write_custom_layout_map,
)
from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSessionItem
from rendering.quick.custom_layout_hydration import resolve_quick_committed_variant_state
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner, _DisplayBinding
from rendering.widget_descriptors import get_widget_runtime_descriptor


FAMILIES = (
    "reddit", "reddit2", "gmail", "media", "friend_pulse",
    "system_stats", "achievement_pulse", "abandonment_issues", "weather",
)


def _owner_and_item(family: str, *, display_width=1920, display_height=1080):
    descriptor = get_widget_runtime_descriptor(family)
    assert descriptor is not None
    assert len([role for role in descriptor.custom_child_roles if role.movable]) >= 2
    assert set(descriptor.content_extent_axes) == {"horizontal", "vertical"}
    # A deterministic display identity and working box without binding or
    # instrumenting any live runtime.  The production writer/reader use its
    # geometry() and the same normalized display-bucket contract as QScreen.
    screen = SimpleNamespace(geometry=lambda: QRect(0, 0, display_width, display_height))
    rect = QRect(90, 70, 700, 380)
    item = CustomLayoutSessionItem(
        source_key=CustomLayoutKey(family, "display:roundtrip"),
        model_identity=family,
        baseline_global_rect=rect,
        current_global_rect=rect,
        baseline_size_payload={},
        current_size_payload={},
        baseline_enabled=True,
        current_enabled=True,
        resize_capable=True,
        content_extent_axes=frozenset(descriptor.content_extent_axes),
        custom_child_roles=descriptor.custom_child_roles,
        authored_reference_size=(700.0, 380.0),
    )
    owner = QuickCustomLayoutOwner(
        settings_manager=SimpleNamespace(), participants_provider=lambda: (),
        visualizer_provider=lambda: (None, None), reload_request=lambda _reason: None,
    )
    owner._bindings = {"display:roundtrip": _DisplayBinding(
        identity="display:roundtrip", monitor_route="1", unit=SimpleNamespace(),
        screen=screen, geometry=QRect(0, 0, display_width, display_height),
    )}
    owner._descriptors = {item.source_key: descriptor}
    return owner, item, descriptor, screen


@pytest.mark.parametrize("family", FAMILIES)
def test_child_records_survive_owner_write_and_committed_rehydrate_after_parent_resize(family):
    owner, item, descriptor, screen = _owner_and_item(family)
    roles = descriptor.custom_child_roles
    first, second = tuple(role.role_id for role in roles if role.movable)[:2]
    # Edit two independent semantic children. Preserve a not-yet-admitted role
    # record exactly; a normal edit must not become a destructive schema migration.
    first_size = CustomChildSize(x_offset=0.08, y_offset=0.04)
    second_size = CustomChildSize(x_offset=-0.03, y_offset=0.06)
    assert item.set_child_size(first, first_size)
    assert item.set_child_size(second, second_size)
    unknown_record = {"width_scale": 1.17, "x_offset": 0.37, "future": "keep"}
    item.current_size_payload = update_child_geometry_payload(
        {CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY: {"future_child": unknown_record}},
        roles, item.current_child_sizes,
    )
    header = next((role for role in roles if role.role_id == "header" and role.alignment_flip), None)
    if header is not None:
        assert owner.flip_child_alignment(item, header.role_id)
    # Uniform parent geometry must not overwrite the independently authored child
    # offsets or the header flip. No reliance on transient Edit-only floor data.
    item.set_geometry(QRect(90, 70, 770, 418))
    original = deepcopy(item.current_size_payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY])
    widgets = {family: {"enabled": True, "position": "Custom", "monitor": "1"}}
    custom_map = load_custom_layout_map(widgets)
    _write_item(widgets, custom_map, item, descriptor, "1", owner._bindings["display:roundtrip"])
    write_custom_layout_map(widgets, custom_map)

    # Reopen through the actual committed reader, never by just comparing an
    # in-memory session payload with itself. The reader must not rewrite Settings.
    before_read = deepcopy(widgets)
    resolved = resolve_quick_committed_variant_state(
        widgets, screen, family, geometry_variant="default",
    )
    assert resolved is not None, family
    geometry, reopened_payload = resolved
    assert (geometry.x, geometry.y, geometry.width, geometry.height) == pytest.approx(
        (90.0, 70.0, 770.0, 418.0), abs=1.0,
    )
    assert reopened_payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY] == original
    assert reopened_payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY]["future_child"] == unknown_record
    assert normalize_child_geometry(
        reopened_payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY], roles,
    ) == item.current_child_sizes
    assert widgets == before_read, "Committed hydration must be read-only"


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("required_extent,display_size", [
    ((760.25, 420.75), (1920, 1080)),
    ((4000.5, 2000.25), (1000, 680)),
])
def test_child_reports_never_grow_outer_geometry_or_create_a_floor(
    family, required_extent, display_size, monkeypatch,
):
    owner, item, _descriptor, _screen = _owner_and_item(
        family, display_width=display_size[0], display_height=display_size[1],
    )
    publications = []
    real_set_geometry = CustomLayoutSessionItem.set_geometry

    def record_geometry(target, global_rect, **kwargs):
        assert target is item
        publications.append(QRect(global_rect))
        return real_set_geometry(target, global_rect, **kwargs)

    monkeypatch.setattr(CustomLayoutSessionItem, "set_geometry", record_geometry)
    original = (QRect(item.current_global_rect), item.current_content_extent,
                deepcopy(item.current_size_payload))
    for _ in range(20):
        assert owner.ensure_child_content_extent(item, *required_extent) is False
        assert item.current_global_rect == original[0]
        assert item.current_content_extent == original[1]
        assert item.current_size_payload == original[2]
        assert item.child_content_requirement is None
    assert publications == [], (family, required_extent, publications)
    assert owner.clear_child_content_extent(item) is False


@pytest.mark.parametrize("edge,rect,expected", [
    ("right", QRect(90, 70, 700, 380), QRect(90, 70, 910, 380)),
    ("left", QRect(0, 70, 790, 380), QRect(0, 70, 790, 380)),
    ("bottom", QRect(90, 70, 700, 380), QRect(90, 70, 700, 610)),
    ("top", QRect(90, 0, 700, 450), QRect(90, 0, 700, 450)),
    ("bottom_right", QRect(90, 70, 700, 380), QRect(90, 70, 910, 610)),
])
def test_resize_snap_cannot_resurrect_an_impossible_child_floor(edge, rect, expected):
    # The preceding drag resolver can already have stopped at the display edge.
    # The shared snap must not inflate that bounded rectangle back to a logical
    # child minimum larger than the monitor, or move the opposite anchor.
    horizontal = ("left" if edge == "left" else "right"
                  if edge in {"right", "bottom_right"} else None)
    vertical = ("top" if edge == "top" else "bottom"
                if edge in {"bottom", "bottom_right"} else None)
    snapped = resolve_resize_edge_snap(
        rect, QSize(1000, 680), horizontal_edge=horizontal,
        vertical_edge=vertical, min_size=QSize(4001, 2001),
        threshold_px=0,
    ).rect
    assert snapped == expected
    assert snapped.x() >= 0 and snapped.y() >= 0
    assert snapped.x() + snapped.width() <= 1000
    assert snapped.y() + snapped.height() <= 680


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("handle,dx,dy", [
    ("right", 2000, 0),
    ("bottom", 0, 2000),
    ("content_bottom_right", 2000, 2000),
])
def test_parent_content_gesture_and_reopen_remain_physically_bounded_with_impossible_child(
    family, handle, dx, dy,
):
    owner, item, descriptor, screen = _owner_and_item(
        family, display_width=1000, display_height=680,
    )
    item.child_content_requirement = (4000.5, 2000.25)
    first, second = tuple(role.role_id for role in descriptor.custom_child_roles if role.movable)[:2]
    assert item.set_child_size(first, CustomChildSize(x_offset=0.08, y_offset=0.04))
    assert item.set_child_size(second, CustomChildSize(x_offset=-0.03, y_offset=0.06))
    item.current_size_payload = update_child_geometry_payload(
        item.current_size_payload, descriptor.custom_child_roles, item.current_child_sizes,
    )
    child_records = deepcopy(item.current_size_payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY])
    start = QPoint(item.current_global_rect.center())
    assert owner.begin_resize(item, handle, start)
    assert owner.update_resize(item, handle, QPoint(start.x() + dx, start.y() + dy), True)
    rect = item.current_global_rect
    assert rect.x() == 90 and rect.y() == 70
    assert 0 < rect.width() <= 910 and 0 < rect.height() <= 610
    if dx:
        assert rect.width() == 910
    if dy:
        assert rect.height() == 610
    assert item.child_content_requirement == (4000.5, 2000.25)
    assert item.current_content_extent == pytest.approx(
        (rect.width() / item.resize_scale, rect.height() / item.resize_scale)
    )
    assert item.current_size_payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY] == child_records

    widgets = {family: {"enabled": True, "position": "Custom", "monitor": "1"}}
    custom_map = load_custom_layout_map(widgets)
    _write_item(widgets, custom_map, item, descriptor, "1", owner._bindings["display:roundtrip"])
    write_custom_layout_map(widgets, custom_map)
    resolved = resolve_quick_committed_variant_state(
        widgets, screen, family, geometry_variant="default",
    )
    assert resolved is not None
    geometry, payload = resolved
    assert (geometry.x, geometry.y, geometry.width, geometry.height) == pytest.approx(
        (rect.x(), rect.y(), rect.width(), rect.height()), abs=1.0,
    )
    assert payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY] == child_records
    assert payload["content_extent"] == pytest.approx(item.current_content_extent)
    assert "child_content_requirement" not in payload


@pytest.mark.parametrize("family", FAMILIES)
def test_clamped_content_drag_publishes_once_across_repeated_identical_pointer_samples(
    family, monkeypatch,
):
    owner, item, descriptor, _screen = _owner_and_item(
        family, display_width=1000, display_height=680,
    )
    item.child_content_requirement = (4000.5, 2000.25)
    publications = []
    real_set_geometry = CustomLayoutSessionItem.set_geometry

    def record_geometry(target, global_rect, **kwargs):
        assert target is item
        publications.append(QRect(global_rect))
        return real_set_geometry(target, global_rect, **kwargs)

    monkeypatch.setattr(CustomLayoutSessionItem, "set_geometry", record_geometry)
    start = QPoint(item.current_global_rect.center())
    cursor = QPoint(start.x() + 2000, start.y() + 2000)
    assert owner.begin_resize(item, "content_bottom_right", start)
    assert owner.update_resize(item, "content_bottom_right", cursor, False)
    settled = (QRect(item.current_global_rect), deepcopy(item.current_size_payload),
               item.current_content_extent)
    for _ in range(20):
        assert owner.update_resize(item, "content_bottom_right", cursor, False) is False
        assert item.current_global_rect == settled[0]
        assert item.current_size_payload == settled[1]
        assert item.current_content_extent == settled[2]
    assert owner.update_resize(item, "content_bottom_right", cursor, True) is False
    assert len(publications) == 1, (family, publications)
    assert publications[0] == QRect(90, 70, 910, 610)
