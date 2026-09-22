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

    The first two images are already local; the third is unavailable. A one-row
    viewport must show the first image, while a taller viewport must switch the
    entire visible group back to text. No image network work belongs in QML.
    """
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtGui import QImage
    from core.feeds.models import (FeedDocument, FeedImageCandidate, FeedHealth,
                                    FeedItem, FeedRefreshResult, FeedSnapshot)
    from rendering.quick.widgets.feeds import (FeedPresentationConfig,
                                               FeedPresentationModel, FeedPresentationStyle)
    from time import time

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
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_ROOT / "FeedPresentation.qml")))
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()]
    root = component.createWithInitialProperties({"feedModel": model})
    assert isinstance(root, QQuickItem), [error.toString() for error in component.errors()]
    try:
        root.setWidth(400.0)
        root.setHeight(178.0)  # One 84px grid row at the authored font size.
        qt_app.processEvents()
        first = root.findChild(QQuickItem, "feedGridArtwork0")
        frame = root.findChild(QQuickItem, "feedGridArtworkFrame0")
        assert first is not None and frame is not None
        assert frame.isVisible()
        assert Path(first.property("source").toLocalFile()) == files[0]
        root.setHeight(620.0)  # All three image-capable rows visible; third art is missing.
        qt_app.processEvents()
        assert not frame.isVisible()
        assert not first.property("source").toString()
        root.setHeight(178.0)
        qt_app.processEvents()
        assert frame.isVisible()
        assert Path(first.property("source").toLocalFile()) == files[0]
    finally:
        root.deleteLater()
        engine.deleteLater()
