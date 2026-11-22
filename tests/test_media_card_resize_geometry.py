"""Now Playing card geometry under resize and flip (operator defects, 22 Nov): real QML, never on screen."""

from __future__ import annotations
from tests._invisible_windows import keep_off_screen  # real but never on screen

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtQuick import QQuickItem

from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.quick.widgets.media import RetainedMediaPresentation
from rendering.quick.window import QuickDisplayWindow
from tests.test_qtquick_media_presentation import _FakeMediaRuntime, _image, _model, _snapshot


@pytest.fixture
def media_card(qt_app):
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0, runtime_generation=177, screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime = _FakeMediaRuntime()
    model, _, _ = _model(factory.media_artwork_provider, runtime)
    presentation = RetainedMediaPresentation(
        host=controller.ordinary_widget_host, model=model,
        geometry=OverlayWidgetGeometry(25.0, 30.0, 700.0, 340.0),
    )
    presentation.activate(object())
    runtime.publish(_snapshot(1, image=_image()))
    qt_app.processEvents()
    item = presentation.item

    def find(name):
        found = item.findChild(QQuickItem, name)
        assert found is not None, name
        return found

    def resize(width, height, custom=None):
        model.set_custom_child_geometry(custom or {})
        model.set_content_extent(width, height)
        qt_app.processEvents()

    def rect(part):
        """``part``'s rectangle in the content column's coordinates: (left, top, right, bottom)."""
        top_left = part.mapToItem(find("mediaContent"), QPointF(0.0, 0.0))
        return (top_left.x(), top_left.y(), top_left.x() + part.width(), top_left.y() + part.height())

    class Card:
        pass

    card = Card()
    card.item, card.model, card.find, card.resize, card.rect = item, model, find, resize, rect
    try:
        yield card
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


SIZES = ((600, 260), (700, 340), (950, 455), (500, 420), (900, 600))


@pytest.mark.qt
def test_media_artwork_widens_to_the_square_its_height_asks_for(media_card) -> None:
    """The artwork is as wide as it is tall wherever the card leaves the text its room (never a narrow strip)."""
    art = media_card.find("mediaArtworkFrame")
    metadata = media_card.find("mediaMetadata")
    column = media_card.find("mediaContent")
    seek = media_card.find("mediaProgressTrack")
    seek_widths = []
    for width, height in SIZES:
        media_card.resize(width, height)
        assert art.isVisible() and art.height() > 32.0
        text_room = float(art.property("minimumMetadataRoom"))
        assert column.width() - art.height() >= text_room, "fixture card must leave the text its room"
        # The Media card's spec: never wider than tall, and as wide as tall when the text room allows.
        assert art.width() == pytest.approx(art.height(), abs=1.0), (width, height)
        assert media_card.rect(art)[2] <= column.width() + 1.0
        assert metadata.width() > 32.0
        # The seek bar spans the content column at every size (it widens with the box).
        assert seek.width() == pytest.approx(column.width(), abs=1.0), (width, height)
        seek_widths.append(seek.width())
    assert seek_widths[1] > seek_widths[0] and seek_widths[2] > seek_widths[1]
