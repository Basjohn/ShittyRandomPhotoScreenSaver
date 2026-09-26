"""Arrange canvas interaction through real Qt input events (offscreen, no shown window)."""
from __future__ import annotations

from copy import deepcopy

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest

from core.settings.default_settings import DEFAULT_SETTINGS
from rendering.visualizer_media_adjacency import resolve_visualizer_media_origin
from ui.onboarding.arrange import _ArrangeCanvas
from ui.onboarding.arrange_model import ArrangeDisplay, ArrangeModel


def _displays():
    return (ArrangeDisplay("screen:a", ("screen:a",), QRect(0, 0, 1000, 700), "1"),
            ArrangeDisplay("screen:b", ("screen:b",), QRect(1000, 0, 1000, 700), "2"))


def _weather_only() -> dict:
    return {"family_activation": {"weather": True},
            "weather": {"enabled": True, "position": "Top Right", "monitor": "1", "margin": 24}}


@pytest.fixture
def canvas(qt_app):
    model = ArrangeModel(_weather_only(), _displays())
    widget = _ArrangeCanvas(model)
    widget.resize(820, widget.heightForWidth(820))
    yield widget
    widget.deleteLater()


def _centre(canvas, item) -> QPoint:
    return canvas._project(item.current_global_rect).center()


def test_drag_moves_places_and_reports_snap_guides(canvas) -> None:
    item = next(iter(canvas.model.session.active_items()))
    before = QRect(item.current_global_rect)
    start = _centre(canvas, item)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    guides = []
    for step in range(1, 6):
        QTest.mouseMove(canvas, start - QPoint(18 * step, -8 * step))
        guides.append(canvas.model.last_snap)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start - QPoint(90, -40))
    assert item.current_global_rect != before
    assert not canvas.model.is_authored(item.source_key)  # a drag places it
    assert canvas.model.pending
    assert any(guide is not None for guide in guides)
    assert canvas.model.last_snap is None  # guides are drawn only while dragging


def test_corner_handle_scales_uniformly_and_keyboard_nudges(canvas) -> None:
    item = next(iter(canvas.model.session.active_items()))
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _centre(canvas, item))
    handle = canvas._handles(item)[3].center().toPoint()
    ratio = item.current_global_rect.width() / item.current_global_rect.height()
    scale_before = item.resize_scale
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, handle)
    QTest.mouseMove(canvas, handle - QPoint(25, 25))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, handle - QPoint(25, 25))
    assert item.resize_scale < scale_before
    assert abs(item.current_global_rect.width() / item.current_global_rect.height() - ratio) < 0.05

    start = QRect(item.current_global_rect)
    QTest.keyClick(canvas, Qt.Key.Key_Left)
    QTest.keyClick(canvas, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert item.current_global_rect.topLeft() == start.topLeft() + QPoint(-1, 10)  # nudges never snap back


def test_delete_resets_to_the_authored_anchor_immediately(canvas) -> None:
    item = next(iter(canvas.model.session.active_items()))
    authored = QRect(item.current_global_rect)
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _centre(canvas, item))
    for _ in range(3):
        QTest.keyClick(canvas, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert item.current_global_rect != authored
    QTest.keyClick(canvas, Qt.Key.Key_Delete)
    assert item in canvas.model.session.active_items()  # stays on the canvas
    assert canvas.model.is_authored(item.source_key)
    assert item.current_global_rect == authored
    assert canvas.model.apply()["weather"].get("position") == "Top Right"  # nothing was placed


def test_escape_and_empty_click_clear_selection(canvas) -> None:
    item = next(iter(canvas.model.session.active_items()))
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _centre(canvas, item))
    assert canvas._selected is item
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    assert canvas._selected is None
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _centre(canvas, item))
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(3, 3))
    assert canvas._selected is None


def _media_and_visualizer(media_enabled: bool) -> dict:
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    for family in widgets["family_activation"]:
        widgets["family_activation"][family] = family in {"media", "visualizers"}
    for key, section in widgets.items():
        if isinstance(section, dict) and "enabled" in section and key not in {"media", "spotify_visualizer"}:
            section["enabled"] = False
    widgets["media"]["enabled"] = media_enabled
    widgets["spotify_visualizer"]["enabled"] = True
    return widgets


def test_visualizer_docks_to_media_exactly_like_the_saver(qt_app) -> None:
    display = ArrangeDisplay("screen:a", ("screen:a",), QRect(0, 0, 1920, 1080), "1")
    model = ArrangeModel(_media_and_visualizer(True), (display,))
    items = {item.model_identity: item for item in model.session.active_items()}
    media, visualizer = items["media"].current_global_rect, items["spotify_visualizer"].current_global_rect
    assert not media.intersects(visualizer)
    x, y, overfull = resolve_visualizer_media_origin(
        (media.x(), media.y(), media.width(), media.height()),
        (visualizer.width(), visualizer.height()), (1920, 1080))
    assert (visualizer.x(), visualizer.y()) == (round(x), round(y)) and not overfull


def test_visualizer_without_media_takes_media_anchor(qt_app) -> None:
    display = ArrangeDisplay("screen:a", ("screen:a",), QRect(0, 0, 1920, 1080), "1")
    model = ArrangeModel(_media_and_visualizer(False), (display,))
    items = {item.model_identity: item for item in model.session.active_items()}
    assert set(items) == {"spotify_visualizer"}
    margin = DEFAULT_SETTINGS["widgets"]["media"]["margin"]
    assert items["spotify_visualizer"].current_global_rect.topLeft() == QPoint(margin, margin)  # Media: Top Left


def test_adjacency_prefers_the_roomier_vertical_side() -> None:
    assert resolve_visualizer_media_origin((30, 30, 400, 200), (400, 250), (1920, 1080))[:2] == (30, 250)
    assert resolve_visualizer_media_origin((30, 800, 400, 250), (400, 250), (1920, 1080))[:2] == (30, 530)
    x, y, overfull = resolve_visualizer_media_origin((30, 30, 400, 1000), (400, 900), (1920, 1080))
    assert (x, overfull) == (450, False)  # horizontal fallback
    assert resolve_visualizer_media_origin((0, 0, 1920, 1000), (1900, 900), (1920, 1080))[2] is True
