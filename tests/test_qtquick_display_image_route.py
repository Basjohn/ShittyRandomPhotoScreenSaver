"""Qt Quick image-routing purity contracts.

Steady-state wallpaper presentation is QImage -> detached PresentationImage.
There is deliberately no generic QPixmap route or synchronous compatibility
publication seam in the Quick runtime.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QGuiApplication, QImage

from rendering.quick.display_image_route import presentation_image_from_processed_qimage
from rendering.quick.image_accounting import aggregate_presentation_image_accounting
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy

ROOT = Path(__file__).resolve().parents[1]


def _gui_app() -> QGuiApplication:
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    return app


def _image(width: int, height: int, color: str = "#3366cc") -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(color))
    return image


def _make_runtime(generation: int):
    app = _gui_app()
    screen = app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=generation,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    return runtime, factory


def test_quick_image_accounting_deduplicates_detached_records() -> None:
    shared = {"resource_id": "presentation:a", "tracked_bytes": 64}
    snapshot = aggregate_presentation_image_accounting(
        (
            {"resources": (shared,)},
            {
                "resources": (
                    shared,
                    {"resource_id": "presentation:b", "tracked_bytes": 32},
                )
            },
        ),
        generation=7,
    )
    assert snapshot["generation"] == 7
    assert snapshot["resource_count"] == 2
    assert snapshot["total_tracked_bytes"] == 96


def test_runtime_image_route_has_no_generic_qpixmap_escape_hatch() -> None:
    route = (ROOT / "rendering" / "quick" / "display_image_route.py").read_text(
        encoding="utf-8"
    )
    unit = (ROOT / "rendering" / "quick" / "display_unit.py").read_text(
        encoding="utf-8"
    )
    boundary = (ROOT / "rendering" / "quick" / "image_boundary.py").read_text(
        encoding="utf-8"
    )
    for source in (route, unit, boundary):
        assert "QPixmap" not in source
        assert "capture_qpixmap" not in source
        assert "present_processed_pixmap" not in source
    assert "presentation_image_from_processed_qimage" in route


@pytest.mark.qt
def test_processed_qimage_produces_packed_presentation_image() -> None:
    image = _image(6, 4)
    detached = presentation_image_from_processed_qimage(
        image,
        image_path="C:/img/a.jpg",
    )
    assert detached.pixel_size == (6, 4)
    assert detached.source_path == "C:/img/a.jpg"
    assert "a.jpg@6x4" in detached.identity
    assert detached.row_stride == 6 * 4
    assert detached.byte_count == 6 * 4 * 4


@pytest.mark.qt
def test_processed_qimage_preserves_rgba_semantics() -> None:
    image = QImage(5, 3, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    image.setPixelColor(0, 0, QColor(255, 0, 0, 255))
    image.setPixelColor(1, 0, QColor(0, 255, 0, 128))
    image.setPixelColor(2, 1, QColor(0, 0, 255, 64))

    detached = presentation_image_from_processed_qimage(
        image,
        image_path="C:/img/semantic.png",
    )
    assert detached.source_path == "C:/img/semantic.png"
    assert detached.pixel_size == (5, 3)
    assert detached.row_stride == 20
    assert len(detached.rgba8) == 5 * 3 * 4


@pytest.mark.qt
def test_detached_image_publishes_into_runtime_without_qpixmap() -> None:
    app = _gui_app()
    runtime, factory = _make_runtime(94)
    try:
        detached = presentation_image_from_processed_qimage(
            _image(8, 5),
            image_path="p.png",
        )
        runtime.set_presentation_image(detached)
        assert runtime.scene_controller.presentation_image == detached
        assert runtime.scene_controller.presentation_image.pixel_size == (8, 5)

        runtime.clear()
        assert runtime.scene_controller.presentation_image is None
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        app.processEvents()


@pytest.mark.qt
def test_runtime_target_size_is_identity_pixels() -> None:
    app = _gui_app()
    runtime, factory = _make_runtime(95)
    try:
        identity = runtime.display_identity
        _x, _y, width, height = identity.geometry
        dpr = float(identity.device_pixel_ratio) or 1.0
        target = runtime.get_target_size()
        assert target.width() == max(1, round(width * dpr))
        assert target.height() == max(1, round(height * dpr))
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        app.processEvents()
