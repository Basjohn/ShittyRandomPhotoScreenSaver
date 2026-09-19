"""Retained Qt scene regression for ordinary-card child paint ownership.

This checks the actual retained item ancestry and clipping boundaries after
geometry changes and while Edit opens/closes. It does NOT sample GPU pixels or
claim rounded-corner masking; the card's rectangular clip is intentional.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, QPoint, QRect
from PySide6.QtQuick import QQuickItem

from rendering.custom_layout_session import (
    CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem,
)
from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry


def _walk(root: QQuickItem):
    yield root
    for child in root.childItems():
        yield from _walk(child)


def _one(root: QQuickItem, name: str) -> QQuickItem:
    found = [item for item in _walk(root) if item.objectName() == name]
    assert len(found) == 1, (name, len(found))
    return found[0]


def _has_ancestor(item: QQuickItem, ancestor: QQuickItem) -> bool:
    current = item.parentItem()
    while current is not None:
        if current is ancestor:
            return True
        current = current.parentItem()
    return False


@pytest.mark.qt
@pytest.mark.parametrize("family,accessory_width", [
    ("reddit", 0.0), ("friend_pulse", 0.0), ("media", 66.0),
])
def test_card_child_and_media_only_accessory_stay_in_independent_clip_lanes(
    qt_app, family: str, accessory_width: float,
) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=1924,
    )
    root.setWidth(1200.0)
    root.setHeight(800.0)
    host = OrdinaryWidgetPresentationHost(
        host_item=_one(root, "ordinaryWidgetHost"),
        shadow_host_item=_one(root, "ordinaryWidgetShadowHost"),
        context=context, create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
    )
    presentation = host.create_widget(
        object_name=family, model_identity=family,
        geometry=OverlayWidgetGeometry(100.0, 90.0, 600.0, 320.0),
    )
    widget = presentation.item
    boundary = _one(widget, "overlayCardChildPaintBoundary")
    content = _one(widget, "overlayCardContent")
    card = _one(widget, "overlayWidgetCard")
    shadow = _one(widget, "overlayCardShadow")
    accessory = _one(widget, "overlayAccessoryLayer")
    ordinary_child = QQuickItem()
    external_child = QQuickItem()
    overlay = RetainedCustomLayoutOverlay(_one(root, "customLayoutOverlay"))
    try:
        ordinary_child.setParentItem(content)
        ordinary_child.setX(-500.0)
        ordinary_child.setY(-150.0)
        ordinary_child.setWidth(1500.0)
        ordinary_child.setHeight(700.0)
        external_child.setParentItem(accessory)
        external_child.setX(-100.0)
        external_child.setY(-60.0)
        external_child.setWidth(260.0)
        external_child.setHeight(450.0)
        if accessory_width:
            assert widget.setProperty("accessoryExtent", accessory_width)
        qt_app.processEvents()
        for width, height in ((600.0, 320.0), (420.0, 210.0), (690.0, 410.0)):
            widget.setWidth(width)
            widget.setHeight(height)
            qt_app.processEvents()
            assert not widget.clip() and not card.clip(), family
            assert boundary.clip() and accessory.clip(), family
            assert _has_ancestor(ordinary_child, boundary), family
            assert not _has_ancestor(shadow, boundary), family
            assert _has_ancestor(external_child, accessory), family
            assert not _has_ancestor(external_child, boundary), family
            assert boundary.width() == pytest.approx(card.width())
            assert boundary.height() == pytest.approx(card.height())
            assert accessory.height() == pytest.approx(widget.height())
            assert accessory.width() == pytest.approx(accessory_width)
            # This oversized test child really crosses the card. Its *ancestor*
            # boundary must contain paint, not a fragile authored-size clamp.
            top_left = ordinary_child.mapToItem(boundary, 0.0, 0.0)
            bottom_right = ordinary_child.mapToItem(
                boundary, ordinary_child.width(), ordinary_child.height()
            )
            assert top_left.x() < 0 and top_left.y() < 0
            assert bottom_right.x() > boundary.width()
            assert bottom_right.y() > boundary.height()
        # The same retained card remains bounded during Edit, with no special
        # containment switch and no accessory reparenting.
        rect = QRect(100, 90, 690, 410)
        session = CustomLayoutSession()
        session.add_item(CustomLayoutSessionItem(
            source_key=CustomLayoutKey(family, "display:clip"),
            model_identity=family, baseline_global_rect=rect,
            current_global_rect=rect, baseline_size_payload={},
            current_size_payload={}, baseline_enabled=True,
            current_enabled=True,
        ))
        overlay.bind_session(
            session, display_identity="display:clip",
            display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: widget,
        )
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        assert boundary.clip() and accessory.clip()
        assert _has_ancestor(ordinary_child, boundary)
        assert _has_ancestor(external_child, accessory)
        overlay.clear_session()
        qt_app.processEvents()
        assert boundary.clip() and accessory.clip()
        assert _has_ancestor(ordinary_child, boundary)
        assert _has_ancestor(external_child, accessory)
    finally:
        overlay.clear_session()
        host.retire_all()
        for item in (ordinary_child, external_child):
            item.setParentItem(None)
            item.deleteLater()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()
