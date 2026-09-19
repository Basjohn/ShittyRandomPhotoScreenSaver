"""Edit-only no-op suppression must preserve live moves, snaps, and gesture release.

These are focused owner/model/retained-property tests, not physical paint tests.
No QQuickWindow is kept alive across tests and no global deferred-delete flush is used.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtQml import QJSEngine

from rendering.custom_layout_session import (
    CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem,
)
from rendering.quick.custom_layout_overlay import (
    CustomLayoutOverlayModel, RetainedCustomLayoutOverlay, guide_property_matches,
)
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner, _ResizeOrigin
from rendering.quick.scene_controller import QuickSceneController


@pytest.mark.parametrize("change_width,change_height", [(True, False), (False, True), (True, True)])
def test_viewport_duplicate_samples_do_not_publish_but_changed_and_reversed_edits_do(
    change_width, change_height,
):
    """A no-op checks ALL resulting state; no cursor dead zone is introduced."""
    rect = QRect(20, 30, 200, 100)
    extent = (100.0, 50.0)
    payload = {"width": 200, "height": 100, "viewport_extent": [100.0, 50.0]}
    key = CustomLayoutKey("spotify_visualizer", "display:a")
    publications = []
    item = SimpleNamespace(
        source_key=key,
        current_global_rect=QRect(rect),
        current_viewport_extent=extent,
        current_size_payload=dict(payload),
    )

    def set_geometry(next_rect, *, size_payload, viewport_extent):
        publications.append(QRect(next_rect))
        item.current_global_rect = QRect(next_rect)
        item.current_size_payload = dict(size_payload)
        item.current_viewport_extent = tuple(viewport_extent)

    item.set_geometry = set_geometry
    owner = object.__new__(QuickCustomLayoutOwner)
    owner._visualizer_pixels_per_world = {}
    origin = _ResizeOrigin(QRect(rect), QPoint(0, 0), 1.0, extent, 2.0)
    commit = owner._commit_viewport_resize_geometry

    assert not commit(item, origin, QRect(rect), change_width=change_width, change_height=change_height)
    assert publications == []
    assert owner._visualizer_pixels_per_world[key] == 2.0

    edited = QRect(rect)
    if change_width:
        edited.setWidth(202)
    if change_height:
        edited.setHeight(102)
    assert commit(item, origin, edited, change_width=change_width, change_height=change_height)
    assert publications == [edited]
    assert not commit(item, origin, edited, change_width=change_width, change_height=change_height)
    assert publications == [edited]

    # A real reverse movement always resumes publication, including after the
    # cursor was saturated on the same pixel or snapped to a fixed guide.
    assert commit(item, origin, rect, change_width=change_width, change_height=change_height)
    assert publications == [edited, rect]
    assert item.current_viewport_extent == extent


def test_ordinary_parent_move_runs_resolver_and_guides_on_identical_rect(qt_app):
    rect = QRect(20, 30, 200, 100)
    item = CustomLayoutSessionItem(
        source_key=CustomLayoutKey("clock", "display:a"),
        model_identity="clock",
        baseline_global_rect=QRect(rect),
        current_global_rect=QRect(rect),
        baseline_size_payload={}, current_size_payload={},
        baseline_enabled=True, current_enabled=True,
    )
    session = CustomLayoutSession()
    session.add_item(item)
    guide_samples = []
    notifications = []

    def resolver(_item, proposed, cursor):
        guide_samples.append(cursor.x())
        return QRect(proposed)

    model = CustomLayoutOverlayModel(
        session=session,
        display_identity="display:a",
        geometry_resolver=resolver,
        item_change_publisher=lambda _item: notifications.append(QRect(_item.current_global_rect)),
    )
    model.dataChanged.connect(lambda *_args: notifications.append("dataChanged"))
    # Binding the model must project its initial item once; measure only gesture
    # samples, not scene/session construction.
    notifications.clear()

    model.moveItem(0, 20.0, 30.0, 25.0, 30.0)
    model.moveItem(0, 20.0, 30.0, 26.0, 30.0)
    assert guide_samples == [25, 26], "live snap/guide resolver must run even at a fixed edge"
    assert notifications == [], "unchanged parent must not reproject ordinary widget"

    model.moveItem(0, 21.0, 30.0, 27.0, 30.0)
    assert item.current_global_rect == QRect(21, 30, 200, 100)
    assert notifications, "changed geometry must project immediately"
    publications = len(notifications)
    model.moveItem(0, 21.0, 30.0, 28.0, 30.0)
    assert len(notifications) == publications
    model.moveItem(0, 20.0, 30.0, 29.0, 30.0)
    assert item.current_global_rect == rect
    assert len(notifications) > publications, "moving back must publish, not get stuck"


def test_noop_viewport_resize_release_still_finishes_undo_and_clears_guides():
    """Final pointer sample is a lifecycle event even if geometry is unchanged."""
    owner = object.__new__(QuickCustomLayoutOwner)
    key = CustomLayoutKey("spotify_visualizer", "display:a")
    item = SimpleNamespace(source_key=key, viewport_resize_capable=True)
    origin = _ResizeOrigin(QRect(20, 30, 200, 100), QPoint(), 1.0, (100., 50.), 2.0)
    owner._resize_origins = {key: origin}
    completed = []
    owner._resize_viewport_edge = lambda *_args: False
    owner._finish_undo_gesture = lambda kind: completed.append(kind)
    owner._clear_all_guides = lambda: completed.append("guides cleared")
    assert owner.update_resize(item, "right", QPoint(), finalize=True) is False
    assert key not in owner._resize_origins
    assert completed == ["parent_resize", "guides cleared"]


class _TrackedRetainedItem:
    def __init__(self):
        self.values = {
            "verticalGuides": [], "horizontalGuides": [],
            "verticalCenterGuides": [], "horizontalCenterGuides": [],
        }
        self.writes = []

    def property(self, name):
        return self.values[name]

    def setProperty(self, name, value):
        self.writes.append((name, value))
        self.values[name] = value
        return True


def test_qml_var_guide_property_is_compared_by_value_not_qjsvalue_identity(qt_app):
    engine = QJSEngine()
    retained = _TrackedRetainedItem()
    projected = [{"position": 17, "kind": "peer_center"}]
    retained.values["verticalGuides"] = engine.evaluate(
        '([{position: 17, kind: "peer_center"}])'
    )
    assert guide_property_matches(retained, "verticalGuides", projected)
    assert not guide_property_matches(
        retained, "verticalGuides", [{"position": 18, "kind": "peer_center"}],
    )


@pytest.mark.parametrize("guide_setter", ["overlay", "scene"])
def test_retained_guides_ignore_identical_samples_but_update_and_clear(guide_setter):
    edge = _TrackedRetainedItem()
    center = _TrackedRetainedItem()
    overlay = RetainedCustomLayoutOverlay(edge)
    if guide_setter == "overlay":
        def apply(vertical=(), horizontal=()):
            overlay.set_guides(vertical=vertical, horizontal=horizontal)
        active_vertical = ((26, "peer"),)
    else:
        fake_scene = SimpleNamespace(custom_layout_overlay=overlay,
                                     _custom_layout_guide_underlay=center)
        def apply(vertical=(), horizontal=()):
            QuickSceneController.set_custom_layout_guides(
                fake_scene, vertical=vertical, horizontal=horizontal,
            )
        active_vertical = ((26, "peer"), (30, "display_center"))

    apply()
    assert edge.writes == [] and center.writes == [], "empty release is an actual no-op"
    apply(vertical=active_vertical)
    assert edge.writes, "first active guide must paint"
    if guide_setter == "scene":
        assert center.writes, "center assists must project to underlay"
    first = (len(edge.writes), len(center.writes))
    apply(vertical=active_vertical)
    assert (len(edge.writes), len(center.writes)) == first

    apply(vertical=((27, "peer"),))
    assert len(edge.writes) > first[0], "moving an active snap line must repaint"
    apply()
    assert edge.values["verticalGuides"] == []
    assert center.values["verticalCenterGuides"] == []
    cleared = (len(edge.writes), len(center.writes))
    apply()
    assert (len(edge.writes), len(center.writes)) == cleared
    apply(vertical=active_vertical)
    assert edge.values["verticalGuides"], "guide must repaint on next gesture"
