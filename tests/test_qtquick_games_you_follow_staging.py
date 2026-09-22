"""G2 retained presentation gate. No live Steam/network/source admission."""
from __future__ import annotations

from dataclasses import replace
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
            article_url=f"https://store.steampowered.com/news/app/{10000+n}/view/{80000+n}",
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
        # Story content is clipped by the frame while the directional outer
        # shadow remains a sibling. Tiny CUSTOM geometry must never let text or
        # inline art paint outside its story tile.
        frame0 = _find_visual(item, "followedStoryFrame0")
        shadow0 = _find_visual(item, "followedStoryShadow0")
        headline0 = _find_visual(item, "followedStoryHeadline0")
        source0 = _find_visual(item, "followedStorySource0")
        assert frame0 is not None and shadow0 is not None and headline0 is not None and source0 is not None
        assert bool(frame0.property("clip"))
        assert headline0.parentItem() is frame0 and source0.parentItem() is frame0
        assert shadow0.parentItem() is tiles[0]
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
    assert requests == [("news_article", "https://store.steampowered.com/news/app/10000/view/80000")]
    assert not model.open_story(-1) and not model.open_story(2)
    assert not model.open_story("0") and not model.open_story(True)
    # The event ID and API GID are intentionally different. A replacement
    # source revision must not re-open a stale article or synthesize a GID URL.
    bad = replace(_snapshot(1).stories[0], article_url="https://evil.example/bad")
    assert model.accept_snapshot(replace(_snapshot(1), stories=(bad,)))
    assert model.open_story(0)  # Invalid article URL cannot launch; safe game index instead.
    assert requests[-1] == ("news_hub", "https://store.steampowered.com/news/app/10000/")
    # A private URL change with identical public rows is a true no-op for the
    # retained QML model, but the click must use the *new* private snapshot.
    assert not model.accept_snapshot(_snapshot(1))
    assert not model.open_story(1)
    assert model.open_story(0)
    # Pre-link-migration rows remain clickable at their game's safe news hub.
    old = replace(_snapshot(1).stories[0], action_available=True, article_url="")
    assert not model.accept_snapshot(replace(_snapshot(1), stories=(old,)))
    assert model.storyRows.data(model.storyRows.index(0, 0), FollowedStoryRows.ActionRole)
    assert model.open_story(0)
    assert requests[-1] == ("news_hub", "https://store.steampowered.com/news/app/10000/")
    model.retire()
    assert not model.open_story(0) and not model.request_manual_refresh()
    assert len(requests) == 4


def test_followed_syndicated_story_opens_steams_original_externalpost_not_news_hub(qt_app) -> None:
    """The actual private syndicated URL survives the retained click seam."""
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

    model = GamesYouFollowPresentationModel()
    model.set_runtime_service(Lease())
    requests: list[tuple[str, str]] = []
    model.set_article_action(lambda kind, url: requests.append((kind, url)) or True)
    assert model.activate(object())
    initial = _snapshot(1)
    original = initial.stories[0]
    external = (f"https://steamstore-a.akamaihd.net/news/externalpost/"
                f"PCGamesN/{original.gid}")
    news = replace(initial, stories=(replace(original, article_url=external),))
    assert model.accept_snapshot(news)
    assert model.open_story(0)
    assert requests == [("news_article", external)]
    assert not model.accept_snapshot(initial)  # Public rows unchanged; private URL changed.
    assert model.open_story(0)
    assert requests[-1] == ("news_article", original.article_url)
    model.retire()


def test_followed_story_cap_reports_source_overflow_without_replacing_retained_slots(qt_app) -> None:
    model = GamesYouFollowPresentationModel(
        replace(FollowedPresentationConfig.from_widgets_mapping({}), story_cap=3)
    )
    rows = model.storyRows
    assert model.accept_snapshot(_snapshot(8))
    assert model.selectedStoryCount == 3 and model.omittedBySetting == 5
    assert model.storyRows is rows and rows.rowCount() == 8
    assert model.accept_snapshot(_snapshot(4))
    assert model.omittedBySetting == 1
    assert model.accept_snapshot(_snapshot(3))
    assert model.omittedBySetting == 0
    model.retire()


def test_followed_mixed_artwork_preserves_game_identity_and_retained_qml_rail(qt_app, tmp_path: Path) -> None:
    """Native paint gate: a single absent image must not remove any other art."""
    model = GamesYouFollowPresentationModel()
    from PySide6.QtGui import QImage
    art = tmp_path / "local-art.png"
    png = QImage(4, 4, QImage.Format.Format_ARGB32)
    png.fill(0xffaacc11)
    assert png.save(str(art))
    snapshot = replace(
        _snapshot(3),
        stories=tuple(replace(story, game_name=f"Named game {story.appid}")
                      for story in _snapshot(3).stories),
        artwork_paths=(str(art), "", str(art)),
    )
    rows = model.storyRows
    resets: list[int] = []
    rows.modelReset.connect(lambda: resets.append(1))
    assert model.accept_snapshot(snapshot)
    assert model.anyStoryArtwork
    for slot in range(3):
        assert rows.data(rows.index(slot, 0), FollowedStoryRows.GameRole) == f"Named game {10000 + slot}"
        assert bool(rows.data(rows.index(slot, 0), FollowedStoryRows.ArtworkRole)) == (slot != 1)
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_ROOT / "GamesYouFollowPresentation.qml")))
    assert component.status() == QQmlComponent.Status.Ready, [error.toString() for error in component.errors()]
    root = component.createWithInitialProperties({"followedModel": model})
    assert isinstance(root, QQuickItem), [error.toString() for error in component.errors()]
    root.setWidth(model.authoredWidth)
    root.setHeight(model.authoredHeight)
    try:
        qt_app.processEvents()
        for slot in range(3):
            tile = _find_visual(root, f"followedStoryTile{slot}")
            game = _find_visual(root, f"followedStoryGame{slot}")
            fallback = _find_visual(root, f"followedStoryArtworkFallback{slot}")
            artwork = _find_visual(root, f"followedStoryArtwork{slot}")
            assert tile is not None and game is not None and fallback is not None and artwork is not None
            assert game.property("text") == f"Named game {10000 + slot}"
            if tile.isVisible():
                assert game.isVisible() and fallback.isVisible() and artwork.isVisible()
                assert bool(artwork.property("source")) == (slot != 1)
        assert model.accept_snapshot(replace(snapshot, artwork_paths=("", "", "")))
        qt_app.processEvents()
        assert not model.anyStoryArtwork
        assert not resets and rows is model.storyRows
        assert all(rows.data(rows.index(slot, 0), FollowedStoryRows.GameRole) == f"Named game {10000 + slot}"
                   for slot in range(3))
    finally:
        root.deleteLater()
        engine.deleteLater()


def test_followed_inline_article_thumbnails_keep_local_sources_and_retained_slots(qt_app, tmp_path: Path) -> None:
    """Native gate for image-macro thumbnails as a distinct preview rail.

    This cannot be inferred from a green Python-only source test; QML has to
    instantiate the real retained delegates without a property-binding error.
    """
    from PySide6.QtGui import QImage

    art1 = tmp_path / "news-1.png"
    art2 = tmp_path / "news-2.png"
    art3 = tmp_path / "news-3.png"
    image = QImage(16, 16, QImage.Format.Format_ARGB32)
    image.fill(0xff808080)
    assert image.save(str(art1)) and image.save(str(art2)) and image.save(str(art3))
    source = _snapshot(1)
    story = replace(source.stories[0], game_name="Limbus Company",
                    preview="Preview text without URL paths")
    snapshot = replace(source, stories=(story,), artwork_paths=(str(art1),),
                       inline_image_paths=((str(art1), str(art2), str(art3)),))
    model = GamesYouFollowPresentationModel()
    assert model.accept_snapshot(snapshot)
    model.set_content_extent(730.0, 440.0)
    assert model.storyRows.data(model.storyRows.index(0, 0),
                                FollowedStoryRows.InlineArt1Role) == art1.as_uri()
    assert model.storyRows.data(model.storyRows.index(0, 0),
                                FollowedStoryRows.InlineArt2Role) == art2.as_uri()
    assert model.storyRows.data(model.storyRows.index(0, 0),
                                FollowedStoryRows.InlineArt3Role) == art3.as_uri()
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "GamesYouFollowPresentation.qml")))
    assert component.status() == QQmlComponent.Status.Ready, [e.toString() for e in component.errors()]
    root = component.createWithInitialProperties({"followedModel": model})
    assert isinstance(root, QQuickItem), [e.toString() for e in component.errors()]
    root.setWidth(730.0)
    root.setHeight(440.0)
    try:
        qt_app.processEvents()
        tile = _find_visual(root, "followedStoryTile0")
        first = _find_visual(root, "followedStoryInlineImage1" + str(0))
        second = _find_visual(root, "followedStoryInlineImage2" + str(0))
        third = _find_visual(root, "followedStoryInlineImage3" + str(0))
        first_frame = _find_visual(root, "followedStoryInlineImageFrame1" + str(0))
        third_frame = _find_visual(root, "followedStoryInlineImageFrame3" + str(0))
        outline = _find_visual(root, "followedStoryArtworkOutline0")
        assert tile is not None and first is not None and second is not None and third is not None
        assert first_frame is not None and third_frame is not None and outline is not None
        contact = _find_visual(root, "followedStoryArtworkContactShadow0")
        tile_shadow = _find_visual(root, "followedStoryShadow0")
        inline_contact = _find_visual(root, "followedStoryInlineContactShadow10")
        assert all(obj is not None for obj in (contact, tile_shadow, inline_contact))
        assert bool(tile.property("canActivate"))  # Hover and tap cannot be inert on a live story.
        # A 730 x 440 grid may yield a narrow two-image tile. The third
        # retained role exists, but its QML Image must *not* acquire its local
        # file until the third frame actually fits and becomes visible.
        if first_frame.isVisible():
            assert first.width() > 0 and second.width() > 0
            assert Path(first.property("source").toLocalFile()) == art1
            if int(tile.property("inlineCount")) >= 2:
                assert Path(second.property("source").toLocalFile()) == art2
            else:
                assert not second.property("source").toString()
            if int(tile.property("inlineCount")) >= 3:
                assert third_frame.isVisible()
                assert Path(third.property("source").toLocalFile()) == art3
                assert third_frame.x() > first_frame.x()
            else:
                assert not third_frame.isVisible()
                assert not third.property("source").toString()
            assert first_frame.y() + first_frame.height() <= tile.height() - 25.0

        # Exercise the actual three-image painted state too: a tall, broad
        # single-column card gives this same retained tile enough text width.
        assert model.set_content_extent(730.0, 1100.0)
        root.setWidth(730.0)
        root.setHeight(1100.0)
        qt_app.processEvents()
        assert tile.isVisible() and int(tile.property("inlineCount")) == 3
        assert all(frame.isVisible() for frame in (
            first_frame, _find_visual(root, "followedStoryInlineImageFrame20"), third_frame))
        assert Path(first.property("source").toLocalFile()) == art1
        assert Path(second.property("source").toLocalFile()) == art2
        assert Path(third.property("source").toLocalFile()) == art3
        assert third_frame.x() > first_frame.x()
        assert outline.isVisible() == bool(tile.property("showArt"))
        preview = _find_visual(root, "followedStoryPreview0")
        assert preview is not None
        if int(tile.property("inlineCount")) >= 2:
            assert not preview.isVisible()  # No cramped text beside 2-3 images.
        two = replace(snapshot, inline_image_paths=((str(art1), str(art2)),))
        assert model.accept_snapshot(two)
        qt_app.processEvents()
        if int(tile.property("inlineCount")) == 2:
            assert not preview.isVisible()
        lone = replace(snapshot, inline_image_paths=((str(art1),),))
        assert model.accept_snapshot(lone)
        qt_app.processEvents()
        if int(tile.property("inlineCount")) == 1:
            assert preview.isVisible() and not third_frame.isVisible()
        assert model.accept_snapshot(replace(snapshot, inline_image_paths=((),)))
        qt_app.processEvents()
        assert model.storyRows.data(model.storyRows.index(0, 0),
                                    FollowedStoryRows.InlineArt1Role) == ""
        assert model.storyRows.data(model.storyRows.index(0, 0),
                                    FollowedStoryRows.InlineArt3Role) == ""
        assert not first_frame.isVisible()
        assert not third_frame.isVisible()
        assert not first.property("source").toString()
    finally:
        root.deleteLater()
        engine.deleteLater()
