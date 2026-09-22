"""Native mandatory FEEDS gate: detect invalid custom QML component properties.

A source test cannot catch 'Cannot assign to non-existent property wrapMode';
load the real file through the same QQmlComponent path as QuickSceneFactory.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine

from core.settings.default_contract import require_canonical_default

pytestmark = pytest.mark.usefixtures("qt_app")
QML_ROOT = Path(__file__).resolve().parents[1] / "rendering" / "quick" / "qml"


def test_feed_presentation_qml_component_compiles_with_shadowed_text_contract(qt_app):
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_ROOT / "FeedPresentation.qml")))
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]


def test_f3_feed_grid_uses_local_artwork_and_geometry_visible_admission(qt_app, tmp_path):
    """Load the real component, then resize a retained three-story Grid.

    The first two images are local; the third is unavailable. All three
    identities stay stable across resizing. QML only loads visible artwork,
    and the third story uses its image-free text cell.
    """
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    from PySide6.QtGui import QImage
    from core.feeds.models import (FeedDocument, FeedImageCandidate, FeedHealth,
                                    FeedItem, FeedRefreshResult, FeedSnapshot)
    from rendering.quick.widgets.feeds import (FeedPresentationConfig,
                                               FeedPresentationModel, FeedPresentationStyle)
    from time import time

    def visual(root: QQuickItem, object_name: str) -> QQuickItem | None:
        if root.objectName() == object_name:
            return root
        for child in root.childItems():
            found = visual(child, object_name)
            if found is not None:
                return found
        return None

    files = (tmp_path / "a.png", tmp_path / "b.png")
    image = QImage(32, 32, QImage.Format.Format_ARGB32)
    image.fill(0xff808080)
    assert all(image.save(str(path)) for path in files)
    values = {"feeds_custom_1": {
        "enabled": True, "feed_url": "https://example.test/feed.xml",
        "view_mode": "grid", "show_images": True, "item_limit": 3,
    }}
    config = FeedPresentationConfig.from_widgets_mapping(values, widget_id="feeds_custom_1")
    model = FeedPresentationModel(
        config,
        FeedPresentationStyle.project(
            config, dict(require_canonical_default("widgets.shadows"))
        ),
    )
    assert model.monogramSource.startswith("data:image/png;base64,")
    model._active = True  # Test-only consumer admission; no runtime/network owner.
    now = time()
    items = tuple(FeedItem(str(i), f"Photo {i}", f"https://example.test/{i}",
                           images=(FeedImageCandidate(f"https://cdn.example.test/{i}.png"),))
                  for i in range(3))
    result = FeedRefreshResult("available", FeedSnapshot(
        FeedDocument("Photos", "https://example.test", "rss20", items), now),
        FeedHealth(last_success_at=now),
        local_artwork_by_item=(("0", files[0].as_uri()), ("1", files[1].as_uri())))
    model.on_feed_runtime_result(result, from_cache=False)
    assert model.firstArtworkRowIndex == 0
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_ROOT / "FeedPresentation.qml")))
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()]
    root = component.createWithInitialProperties({"feedModel": model})
    assert isinstance(root, QQuickItem), [error.toString() for error in component.errors()]
    window = QQuickWindow()
    window.resize(400, 178)
    root.setParentItem(window.contentItem())
    window.show()
    try:
        root.setWidth(400.0)
        root.setHeight(178.0)
        qt_app.processEvents()
        # Repeater delegates belong to the visual child tree; QObject.findChild
        # is not a valid oracle for their lifetime/paint admission.
        first = visual(root, "feedGridArtwork0")
        frame = visual(root, "feedGridArtworkFrame0")
        assert first is not None and frame is not None
        assert frame.isVisible()
        assert Path(first.property("source").toLocalFile()) == files[0]
        root.setHeight(620.0)  # All three image-capable rows visible; third art is missing.
        qt_app.processEvents()
        assert frame.isVisible()
        assert Path(first.property("source").toLocalFile()) == files[0]
        third_frame = visual(root, "feedGridArtworkFrame2")
        assert third_frame is not None and not third_frame.isVisible()
        root.setHeight(178.0)
        qt_app.processEvents()
        assert frame.isVisible()
        assert Path(first.property("source").toLocalFile()) == files[0]

        # FEEDS is an ordinary CUSTOM widget, not a presentation special case.
        # Outer X/Y extent and stable semantic children must use the shared
        # retained edit contracts without resetting feed rows or touching I/O.
        roles = root.property("customEditableChildRoles")
        if hasattr(roles, "toVariant"):
            roles = roles.toVariant()
        assert {role["roleId"] for role in roles} == {
            "header", "refresh", "articles", "artwork", "overflow"
        }
        rows = model.rowModel
        resets: list[bool] = []
        rows.modelReset.connect(lambda: resets.append(True))
        # Use the shared BrandedHeader item itself for CUSTOM geometry.  Its
        # inner frame is intentionally anchored at local x=0 and therefore is
        # not a valid semantic-flip position oracle.
        header = visual(root, "feedHeader")
        subtitle = visual(root, "feedHeaderSubtitle")
        refresh = visual(root, "feedRefreshTarget")
        body = visual(root, "feedBody")
        artwork = visual(root, "feedCustomArtworkRoleTarget")
        footer = visual(root, "feedOverflowSummary")
        first_card = visual(root, "feedGridCard0")
        second_card = visual(root, "feedGridCard1")
        assert all(item is not None for item in (
            header, subtitle, refresh, body, artwork, footer, first_card, second_card
        ))

        assert model.set_content_extent(900.0, 420.0)
        assert model.preferredWidth == pytest.approx(900.0)
        assert model.preferredHeight == pytest.approx(420.0)
        # One-axis changes remain independent and share the descriptor floor.
        assert model.set_content_extent(960.0, 420.0)
        assert model.preferredWidth == pytest.approx(960.0)
        assert model.preferredHeight == pytest.approx(420.0)
        assert model.set_content_extent(960.0, 520.0)
        assert model.preferredWidth == pytest.approx(960.0)
        assert model.preferredHeight == pytest.approx(520.0)
        assert model.set_content_extent(100.0, 90.0)
        assert model.preferredWidth == pytest.approx(320.0)
        assert model.preferredHeight == pytest.approx(180.0)

        model.set_content_extent(900.0, 520.0)
        # Reproduce the physical dead-strip case: a logical X/Y content box may
        # be uniformly scaled below 1.0 by the ordinary parent editor. Family
        # layout must use the authored OverlayCard content surface, never the
        # already-scaled outer OverlayWidget pixel height.
        root.setWidth(720.0)
        root.setHeight(416.0)
        qt_app.processEvents()
        assert float(root.property("presentationScale")) == pytest.approx(0.8, abs=0.01)
        assert body.parentItem() is footer.parentItem()
        assert body.y() + body.height() == pytest.approx(footer.y(), abs=1.0)
        assert footer.y() + footer.height() == pytest.approx(
            footer.parentItem().height(), abs=1.0
        )

        # Restore a 1:1 outer envelope for easy child-geometry assertions.
        root.setWidth(900.0)
        root.setHeight(520.0)
        qt_app.processEvents()
        assert subtitle.y() >= header.y() + header.height() * float(header.property("scale"))
        assert first_card.x() < second_card.x()
        # The one stable artwork edit proxy sits over real admitted artwork; it
        # is not a phantom row-0 box disconnected from the painted image.
        assert artwork.x() == pytest.approx(first_card.x() + frame.x(), abs=1.0)
        assert artwork.y() == pytest.approx(first_card.y() + frame.y(), abs=1.0)
        assert artwork.width() == pytest.approx(frame.width(), abs=1.0)
        assert artwork.height() == pytest.approx(frame.height(), abs=1.0)
        baseline = {
            "header_x": header.x(), "header_scale": float(header.property("scale")),
            "refresh_w": refresh.width(),
            "body_x": body.x(), "body_w": body.width(), "body_h": body.height(),
            "artwork_w": artwork.width(), "artwork_h": artwork.height(),
            "footer_x": footer.x(), "footer_w": footer.width(),
        }
        assert model.set_custom_child_geometry({
            "header": {"alignment": "right", "width_scale": 0.80},
            "refresh": {"width_scale": 0.80, "x_offset": -0.01},
            "articles": {
                "width_scale": 0.72, "height_scale": 0.68,
                "x_offset": 0.02, "y_offset": 0.01,
            },
            "artwork": {
                "width_scale": 0.55, "height_scale": 0.72,
                "x_offset": 0.01, "y_offset": 0.01,
            },
            "overflow": {"width_scale": 0.78, "x_offset": 0.03},
        })
        qt_app.processEvents()
        assert header.x() > baseline["header_x"]
        assert float(header.property("scale")) < baseline["header_scale"]
        assert refresh.width() < baseline["refresh_w"]
        assert bool(header.property("contentReversed")) is True
        assert refresh.x() < root.width() * 0.5
        # Header alignment is widget-wide semantic orientation. The Grid order
        # mirrors with it; only the image *placement* changes, never its pixels.
        assert first_card.x() > second_card.x()
        assert body.x() > baseline["body_x"]
        assert body.width() < baseline["body_w"]
        assert body.height() < baseline["body_h"]
        assert artwork.width() < baseline["artwork_w"]
        assert artwork.height() < baseline["artwork_h"]
        assert footer.x() > baseline["footer_x"]
        assert footer.width() < baseline["footer_w"]
        assert rows is model.rowModel and not resets
    finally:
        root.setParentItem(None)
        window.hide()
        root.deleteLater()
        window.deleteLater()
        engine.deleteLater()
        qt_app.processEvents()
