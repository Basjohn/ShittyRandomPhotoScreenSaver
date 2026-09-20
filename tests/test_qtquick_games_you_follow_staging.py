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
    FollowedPresentationConfig,
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
    assert rows.data(rows.index(0, 0), FollowedStoryRows.ActionRole) is True
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
        refresh = _find_visual(item, "followedRefreshTarget")
        assert refresh.isVisible()
        model.set_content_extent(180.0, 520.0)
        item.setWidth(180.0)
        item.setHeight(520.0)
        qt_app.processEvents()
        assert not refresh.isVisible()  # Narrow header claims the refresh paint rail.
        model.set_content_extent(None, None)
        item.setWidth(model.authoredWidth)
        item.setHeight(model.authoredHeight)
        qt_app.processEvents()
        assert refresh.isVisible()

        for width, height in ((920, 270), (960, 450), (1300, 900),
                              (300, 950), (565, 565), (180, 130), (920, 270)) * 4:
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
            # The default painted group and the pure parent layout must agree,
            # including a wide card with room for two rows and a large grid.
            assert actual_count == model.visibleStoryCount, (
                width, height, model.layoutArrangement, model.layoutColumns,
                model.layoutRows, group.property("columns"), group.property("rows"),
                group.property("columnsFit"), group.property("rowsFit"),
                group.width(), group.height(), group.property("paintHeight"),
            )
            assert int(summary.property("omitted")) == 8 - actual_count
            assert summary.isVisible() == (actual_count < 8 or model.remainingFollowedCount > 0)

        baseline_group = (group.x(), group.y(), group.width(), group.height())
        assert model.set_custom_child_geometry({
            "header": {"alignment": "right", "x_offset": -0.02},
            "story_tiles": {
                "width_scale": 0.81, "height_scale": 0.87,
                "x_offset": 0.02, "y_offset": 0.01,
            },
        })
        qt_app.processEvents()
        assert header.x() > initial_header_x
        assert bool(item.property("headerFlipped"))
        # The standard alignment control flips placement, not image pixels.
        assert tiles[0].x() > tiles[1].x()
        assert (group.x(), group.y(), group.width(), group.height()) != initial_group
        assert group.width() == pytest.approx(baseline_group[2] * 0.81, rel=0.05)
        assert group.height() == pytest.approx(baseline_group[3] * 0.87, rel=0.05)
        # CUSTOM Y must remain a freely resizable group, even when the card's
        # paint rail ends at its fixed footer. Hide complete tiles instead of
        # clamping the actual edit target to that footer.
        old_height = group.height()
        assert model.set_custom_child_geometry({
            "header": {"alignment": "right"},
            "story_tiles": {"width_scale": 0.81, "height_scale": 1.40},
        })
        qt_app.processEvents()
        assert group.height() > old_height
        assert bool(item.property("headerFlipped"))
        # The flip survives an OUTER size change before Save/reopen.
        model.set_content_extent(1050.0, 390.0)
        item.setWidth(1050.0)
        item.setHeight(390.0)
        qt_app.processEvents()
        assert bool(item.property("headerFlipped")) and tiles[0].x() > tiles[1].x()
        assert model.set_custom_child_geometry({})
        model.set_content_extent(920.0, 270.0)
        item.setWidth(920.0)
        item.setHeight(270.0)
        qt_app.processEvents()
        assert header.x() == pytest.approx(initial_header_x)
        assert group.x() == pytest.approx(baseline_group[0])
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


def test_followed_qml_is_source_inert_and_registered_through_one_real_family() -> None:
    qml = (QML_ROOT / "GamesYouFollowPresentation.qml").read_text(encoding="utf-8")
    registry = (ROOT / "rendering/quick/widgets/registry.py").read_text(encoding="utf-8")
    binder = (ROOT / "rendering/quick/widgets/family_binder.py").read_text(encoding="utf-8")
    assert 'family_id="steam_progress"' in registry
    assert 'qml_filename="GamesYouFollowPresentation.qml"' in registry
    assert 'class GamesYouFollowFamilyAdapter' in binder
    assert "customEditableChildRoles" in qml
    assert "model: followedModel.storyRows" in qml
    assert "uniformScaleTransform: true" in qml
    assert not any(token in qml for token in (
        "Timer {", "MouseArea {", "onClicked:", "Qt.openUrlExternally",
        "XMLHttpRequest", "http://", "https://", "QQuickWidget",
    ))


def test_followed_model_consumes_only_its_retained_source_lease_on_gui_thread(qt_app) -> None:
    """A source change never constructs rows, a provider or a refresh owner in QML."""
    class Lease:
        def __init__(self):
            self.consumer = None
            self.manager = None
            self.started = self.stopped = self.refreshes = 0

        def attach_consumer(self, consumer):
            self.consumer = consumer

        def set_thread_manager(self, manager, *, generation):
            self.manager = manager
            assert generation == 42

        def start(self):
            self.started += 1
            self.consumer.on_games_followed_runtime_snapshot(_snapshot(4))
            return True

        def request_refresh(self):
            self.refreshes += 1
            return True

        def stop(self):
            self.stopped += 1

    model = GamesYouFollowPresentationModel(runtime_generation=42)
    lease = Lease()
    manager = object()
    model.set_runtime_service(lease)
    assert not model.request_manual_refresh()
    assert not model.is_games_followed_consumer_alive()
    assert model.activate(manager)
    assert model.storyRows.rowCount() == 8
    assert model.selectedStoryCount == 4
    assert lease.started == 1 and lease.manager is manager
    assert model.activate(manager)  # no duplicate source admission
    assert lease.started == 1
    assert model.request_manual_refresh()
    assert lease.refreshes == 1
    assert model.on_games_followed_runtime_snapshot(_snapshot(4)) is False
    model.retire()
    assert lease.stopped == 1
    assert not model.is_games_followed_consumer_alive()
    assert not model.on_games_followed_runtime_snapshot(_snapshot(8))
    assert model.selectedStoryCount == 4


def test_followed_story_action_uses_current_private_slot_and_retirement_fence(qt_app) -> None:
    """A QML slot is never a provider URL, and cannot outlive the live lease."""
    class Lease:
        def attach_consumer(self, consumer):
            self.consumer = consumer

        def set_thread_manager(self, manager, *, generation):
            pass

        def start(self):
            return True

        def stop(self):
            pass

        def request_refresh(self):
            return True

    requests: list[tuple[str, str]] = []
    model = GamesYouFollowPresentationModel()
    model.set_runtime_service(Lease())
    model.set_article_action(lambda kind, url: requests.append((kind, url)) or True)
    assert not model.open_story(0)
    assert model.activate(object())
    assert model.accept_snapshot(_snapshot(2))
    assert model.open_story(0)
    assert requests == [("news_article", "https://store.steampowered.com/news/app/10000/view/90000")]
    assert not model.open_story(-1) and not model.open_story(2)
    assert not model.open_story("0") and not model.open_story(True)
    assert model.accept_snapshot(_snapshot(1))
    assert not model.open_story(1)
    assert model.open_story(0)
    model.retire()
    assert not model.open_story(0) and not model.request_manual_refresh()
    assert len(requests) == 2


def test_followed_story_cap_reports_source_overflow_without_replacing_retained_slots(qt_app) -> None:
    model = GamesYouFollowPresentationModel(FollowedPresentationConfig(story_cap=3))
    rows = model.storyRows
    assert model.accept_snapshot(_snapshot(8))
    assert model.selectedStoryCount == 3 and model.omittedBySetting == 5
    assert model.storyRows is rows and rows.rowCount() == 8
    assert model.accept_snapshot(_snapshot(4))
    assert model.omittedBySetting == 1
    assert model.accept_snapshot(_snapshot(3))
    assert model.omittedBySetting == 0
    model.retire()
