"""G2 retained presentation gate. No live Steam/network/source admission."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from core.steam.games_followed_source import FollowedNewsSnapshot, FollowedNewsStory
from rendering.quick.widgets.games_you_follow import (
    FOLLOWED_CHILD_ROLES, GamesYouFollowPresentationModel, FollowedStoryRows,
)

pytestmark = pytest.mark.usefixtures("qt_app")
ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / "rendering" / "quick" / "qml"


def _snapshot(count: int = 8) -> FollowedNewsSnapshot:
    return FollowedNewsSnapshot(
        "available",
        tuple(FollowedNewsStory(
            appid=10000 + n, gid=str(90000 + n), title=f"Update {n}",
            published_at=1700000000 + n, feed_name="News", action_available=True,
        ) for n in range(count)),
        followed_count=142, checked_count=4,
    )


def _find_visual(root: QQuickItem, name: str) -> QQuickItem | None:
    if root.objectName() == name:
        return root
    for child in root.childItems():
        found = _find_visual(child, name)
        if found is not None:
            return found
    return None


def test_followed_retained_model_has_stable_eight_slots_and_no_refresh_reset(qt_app) -> None:
    model = GamesYouFollowPresentationModel()
    rows = model.storyRows
    resets: list[int] = []
    changes: list[int] = []
    rows.modelReset.connect(lambda: resets.append(1))
    rows.dataChanged.connect(lambda *_: changes.append(1))
    assert rows.rowCount() == 8
    assert model.visibleStoryCount == 0
    assert model.accept_snapshot(_snapshot())
    assert 0 < len(changes) <= 8
    assert not resets and rows.rowCount() == 8
    assert model.visibleStoryCount <= 8
    assert rows.data(rows.index(0, 0), FollowedStoryRows.TitleRole) == "Update 0"
    assert rows.data(rows.index(0, 0), FollowedStoryRows.ActionRole) is False
    assert model.storyRows is rows
    changes.clear()
    assert model.accept_snapshot(_snapshot()) is False
    assert changes == [] and resets == []
    assert model.set_content_extent(950.0, 270.0)
    assert model.layoutArrangement == "wide"
    assert model.visibleStoryCount + model.overflowStoryCount == 8
    assert not resets and rows is model.storyRows
    assert model.set_content_extent(290.0, 1200.0)
    assert model.layoutArrangement == "tall"
    assert model.set_content_extent(600.0, 620.0)
    assert model.layoutArrangement == "grid"
    assert model.set_content_extent(None, None)
    assert model.authoredWidth == model.baseAuthoredWidth
    assert model.authoredHeight == model.baseAuthoredHeight
    model.retire()
    assert not model.accept_snapshot(_snapshot(4))


def test_followed_stable_grouped_children_reflow_and_restore_without_delegate_churn(qt_app) -> None:
    model = GamesYouFollowPresentationModel()
    assert model.accept_snapshot(_snapshot())
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "GamesYouFollowPresentation.qml")),
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"followedModel": model})
    assert isinstance(item, QQuickItem), [error.toString() for error in component.errors()]
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    try:
        qt_app.processEvents()
        header = _find_visual(item, "followedHeader")
        group = _find_visual(item, "followedStoryGroup")
        summary = _find_visual(item, "followedOverflowSummary")
        tiles = tuple(_find_visual(item, f"followedStoryTile{n}") for n in range(8))
        assert all(obj is not None for obj in (header, group, summary, *tiles))
        assert len({id(tile) for tile in tiles}) == 8
        initial_header_x = header.x()
        initial_group = (group.x(), group.y(), group.width(), group.height())
        roles = item.property("customEditableChildRoles")
        if hasattr(roles, "toVariant"):
            roles = roles.toVariant()
        assert {role["roleId"] for role in roles} == {role.role_id for role in FOLLOWED_CHILD_ROLES}
        assert not _find_visual(item, "followedRefreshTarget").isVisible()

        for width, height in ((920, 270), (300, 950), (565, 565), (180, 130), (920, 270)) * 4:
            assert model.set_content_extent(width, height) or (model.authoredWidth, model.authoredHeight) == (width, height)
            item.setWidth(width)
            item.setHeight(height)
            qt_app.processEvents()
            assert model.visibleStoryCount + model.overflowStoryCount == 8
            assert all(_find_visual(item, f"followedStoryTile{n}") is tile for n, tile in enumerate(tiles))
            live_roles = item.property("customEditableChildRoles")
            if hasattr(live_roles, "toVariant"):
                live_roles = live_roles.toVariant()
            assert {role["roleId"] for role in live_roles} == {role["roleId"] for role in roles}
            actual_count = sum(bool(tile.isVisible()) for tile in tiles)
            assert actual_count <= model.visibleStoryCount
            assert int(summary.property("omitted")) == 8 - actual_count
            assert summary.isVisible() == (actual_count < 8)

        assert model.set_custom_child_geometry({
            "header": {"alignment": "right", "x_offset": -0.02},
            "story_tiles": {
                "width_scale": 0.81, "height_scale": 0.87,
                "x_offset": 0.02, "y_offset": 0.01,
            },
        })
        qt_app.processEvents()
        assert header.x() > initial_header_x
        assert (group.x(), group.y(), group.width(), group.height()) != initial_group
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert header.x() == pytest.approx(initial_header_x)
        assert group.x() == pytest.approx(initial_group[0])
        assert all(_find_visual(item, f"followedStoryTile{n}") is tile for n, tile in enumerate(tiles))
        # A source revision may change the bounded story set, but must not
        # reconstruct ordinal delegates or turn vanished stories into ghost
        # editable roles. A subsequent larger revision reveals retained slots.
        assert model.accept_snapshot(_snapshot(4))
        qt_app.processEvents()
        assert all(_find_visual(item, f"followedStoryTile{n}") is tile for n, tile in enumerate(tiles))
        assert all(not tiles[n].isVisible() for n in range(4, 8))
        assert model.accept_snapshot(_snapshot(8))
        qt_app.processEvents()
        assert all(_find_visual(item, f"followedStoryTile{n}") is tile for n, tile in enumerate(tiles))
        assert not component.errors()
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


def test_followed_qml_is_source_inert_and_does_not_register_an_unproven_family() -> None:
    qml = (QML_ROOT / "GamesYouFollowPresentation.qml").read_text(encoding="utf-8")
    registry = (ROOT / "rendering/quick/widgets/registry.py").read_text(encoding="utf-8")
    binder = (ROOT / "rendering/quick/widgets/family_binder.py").read_text(encoding="utf-8")
    assert 'family_id="steam_progress"' not in registry
    assert 'qml_filename="GamesYouFollowPresentation.qml"' not in registry
    assert 'class GamesYouFollowFamilyAdapter' not in binder
    assert "customEditableChildRoles" in qml
    assert "model: followedModel.storyRows" in qml
    assert "uniformScaleTransform: true" in qml
    assert not any(token in qml for token in (
        "Timer {", "MouseArea {", "onClicked:", "Qt.openUrlExternally",
        "XMLHttpRequest", "http://", "https://", "QQuickWidget",
    ))
