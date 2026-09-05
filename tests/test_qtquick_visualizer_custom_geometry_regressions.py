"""Focused regressions for retained Visualizer CUSTOM resize/transfer contracts.

These tests deliberately live in a new file so the migration-close slice does not
replace Claude's separately reconciled historical CUSTOM suite.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QRect

from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSessionItem
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner, _DisplayBinding


class _Settings:
    def get_widgets_map(self):
        return {}


class _Scene:
    def __init__(self, identity=None, events=None) -> None:
        self.visualizer_render_identity = identity
        self.events = [] if events is None else events
        self.discarded = []

    def set_custom_layout_guides(self, *, vertical=(), horizontal=()):
        return None

    def discard_unowned_visualizer_admission(self):
        identity = self.visualizer_render_identity
        self.events.append(("discard", identity))
        self.discarded.append(identity)
        self.visualizer_render_identity = None
        return identity

    def transfer_visualizer_to(self, target) -> None:
        self.events.append(("transfer", target))


class _Unit:
    def __init__(self, scene, *, visualizer_owner=None) -> None:
        self.runtime = SimpleNamespace(scene_controller=scene)
        self.visualizer_owner = visualizer_owner


def _owner() -> QuickCustomLayoutOwner:
    return QuickCustomLayoutOwner(
        settings_manager=_Settings(),
        participants_provider=lambda: (),
        visualizer_provider=lambda: (None, None),
        reload_request=lambda _kind: None,
    )


def _visualizer_item() -> CustomLayoutSessionItem:
    key = CustomLayoutKey("spotify_visualizer", "display:a")
    return CustomLayoutSessionItem(
        source_key=key,
        model_identity="spotify_visualizer",
        baseline_global_rect=QRect(100, 100, 420, 280),
        current_global_rect=QRect(100, 100, 420, 280),
        baseline_size_payload={"width": 420, "height": 280},
        current_size_payload={"width": 420, "height": 280},
        baseline_enabled=True,
        current_enabled=True,
        resize_capable=True,
        viewport_resize_capable=True,
        baseline_viewport_extent=(420.0, 280.0),
        resize_scale=1.0,
        baseline_resize_scale=1.0,
        source_monitor_route="1",
    )


def test_visualizer_corner_is_two_axis_viewport_resize_and_wheel_scale_is_untouched() -> None:
    owner = _owner()
    scene = _Scene()
    unit = _Unit(scene)
    owner._bindings = {
        "display:a": _DisplayBinding(
            identity="display:a",
            monitor_route="1",
            unit=unit,
            screen=object(),
            geometry=QRect(0, 0, 1200, 900),
        )
    }
    item = _visualizer_item()
    owner._visualizer_pixels_per_world[item.source_key] = 1.0

    start = QPoint(519, 379)
    assert owner.begin_resize(item, "bottom_right", start) is True
    assert owner.update_resize(item, "bottom_right", QPoint(619, 429), True) is True

    assert item.current_global_rect == QRect(100, 100, 520, 330)
    assert item.current_viewport_extent == pytest.approx((520.0, 330.0))
    # Corner extent is no longer the generic uniform-scale operation.
    assert item.resize_scale == pytest.approx(1.0)
    assert owner._visualizer_pixels_per_world[item.source_key] == pytest.approx(1.0)


def test_successive_visualizer_side_resizes_share_one_pixels_per_world_authority() -> None:
    owner = _owner()
    unit = _Unit(_Scene())
    owner._bindings = {
        "display:a": _DisplayBinding(
            identity="display:a",
            monitor_route="1",
            unit=unit,
            screen=object(),
            geometry=QRect(0, 0, 1600, 1200),
        )
    }
    item = _visualizer_item()
    owner._visualizer_pixels_per_world[item.source_key] = 0.683

    # First make the viewport taller. The untouched X world extent is preserved.
    assert owner.begin_resize(item, "bottom", QPoint(300, 379)) is True
    assert owner.update_resize(item, "bottom", QPoint(300, 579), True) is True
    first_extent = item.current_viewport_extent
    assert first_extent is not None
    assert first_extent[0] == pytest.approx(420.0)
    assert owner._visualizer_pixels_per_world[item.source_key] == pytest.approx(0.683)

    # A later horizontal drag must not relearn a different live presentation scale.
    assert owner.begin_resize(item, "right", QPoint(519, 300)) is True
    assert owner.update_resize(item, "right", QPoint(619, 300), True) is True
    second_extent = item.current_viewport_extent
    assert second_extent is not None
    assert second_extent[1] == pytest.approx(first_extent[1])
    assert owner._visualizer_pixels_per_world[item.source_key] == pytest.approx(0.683)

    # The resulting integer QRect and logical extent still encode one uniform scale.
    resolved = owner._pixels_per_world_from_geometry(
        item.current_global_rect,
        item.current_viewport_extent,
    )
    assert resolved == pytest.approx(0.683, abs=0.002)


def test_visualizer_transfer_discards_manager_proven_orphan_target_before_live_move() -> None:
    events = []
    source_scene = _Scene(events=events)
    target_scene = _Scene(identity="old-activation", events=events)
    live_owner = object()
    source_unit = _Unit(source_scene, visualizer_owner=live_owner)
    target_unit = _Unit(target_scene, visualizer_owner=None)
    current = {"unit": source_unit}

    def transfer_unit(target):
        events.append(("manager", target))
        source_unit.visualizer_owner = None
        target.visualizer_owner = live_owner
        current["unit"] = target
        return True

    layout = QuickCustomLayoutOwner(
        settings_manager=_Settings(),
        participants_provider=lambda: (),
        visualizer_provider=lambda: (live_owner, current["unit"]),
        reload_request=lambda _kind: None,
        visualizer_unit_transfer=transfer_unit,
    )
    layout._bindings = {
        "source": _DisplayBinding(
            "source", "1", source_unit, object(), QRect(0, 0, 800, 600)
        ),
        "target": _DisplayBinding(
            "target", "2", target_unit, object(), QRect(800, 0, 800, 600)
        ),
    }

    layout._transfer_visualizer_display_transaction(source_scene, target_scene)

    assert target_scene.discarded == ["old-activation"]
    assert events[0] == ("discard", "old-activation")
    assert events[1] == ("transfer", target_scene)
    assert events[2] == ("manager", target_unit)
    assert current["unit"] is target_unit


def test_visualizer_transfer_never_overwrites_target_lifecycle_owner() -> None:
    source_scene = _Scene()
    target_scene = _Scene(identity="other-activation")
    live_owner = object()
    other_owner = object()
    source_unit = _Unit(source_scene, visualizer_owner=live_owner)
    target_unit = _Unit(target_scene, visualizer_owner=other_owner)

    layout = QuickCustomLayoutOwner(
        settings_manager=_Settings(),
        participants_provider=lambda: (),
        visualizer_provider=lambda: (live_owner, source_unit),
        reload_request=lambda _kind: None,
        visualizer_unit_transfer=lambda _unit: True,
    )
    layout._bindings = {
        "source": _DisplayBinding(
            "source", "1", source_unit, object(), QRect(0, 0, 800, 600)
        ),
        "target": _DisplayBinding(
            "target", "2", target_unit, object(), QRect(800, 0, 800, 600)
        ),
    }

    with pytest.raises(RuntimeError, match="owns another visualizer lifecycle"):
        layout._transfer_visualizer_display_transaction(source_scene, target_scene)

    assert target_scene.discarded == []
    assert source_scene.events == []


def test_visualizer_transfer_requires_source_unit_to_own_lifecycle_before_mutating_target() -> None:
    source_scene = _Scene()
    target_scene = _Scene(identity="old-activation")
    live_owner = object()
    # Manager/provider still points at source, but its unit attachment is already
    # incoherent. The transaction must fail before discarding the target shell.
    source_unit = _Unit(source_scene, visualizer_owner=None)
    target_unit = _Unit(target_scene, visualizer_owner=None)

    layout = QuickCustomLayoutOwner(
        settings_manager=_Settings(),
        participants_provider=lambda: (),
        visualizer_provider=lambda: (live_owner, source_unit),
        reload_request=lambda _kind: None,
        visualizer_unit_transfer=lambda _unit: True,
    )
    layout._bindings = {
        "source": _DisplayBinding(
            "source", "1", source_unit, object(), QRect(0, 0, 800, 600)
        ),
        "target": _DisplayBinding(
            "target", "2", target_unit, object(), QRect(800, 0, 800, 600)
        ),
    }

    with pytest.raises(RuntimeError, match="lost lifecycle retirement ownership"):
        layout._transfer_visualizer_display_transaction(source_scene, target_scene)

    assert target_scene.discarded == []
    assert target_scene.visualizer_render_identity == "old-activation"
    assert source_scene.events == []
