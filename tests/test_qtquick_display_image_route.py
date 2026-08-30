"""Quick display image-routing seam bars (H, section 5.5).

Prove the GUI-thread pipeline->runtime image route captures a processed pixmap
into immutable presentation state and publishes it through the runtime's explicit
API, plus the runtime's target-size and clear capabilities the flip needs.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QPixmap

from rendering.quick.display_image_route import (
    present_processed_pixmap,
    presentation_image_from_processed_pixmap,
)
from rendering.quick.image_accounting import aggregate_presentation_image_accounting
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy


def _pixmap(width: int, height: int, color: str = "#3366cc") -> QPixmap:
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(color))
    return pixmap


def _make_runtime(qt_app, generation: int):
    screen = qt_app.primaryScreen()
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


@pytest.mark.qt
def test_capture_processed_pixmap_produces_packed_presentation_image(qt_app) -> None:
    pixmap = _pixmap(6, 4)
    image = presentation_image_from_processed_pixmap(pixmap, image_path="C:/img/a.jpg")
    assert image.pixel_size == (6, 4)
    assert image.source_path == "C:/img/a.jpg"
    assert "a.jpg@6x4" in image.identity
    # Tightly packed RGBA deep copy.
    assert image.row_stride == 6 * 4
    assert image.byte_count == 6 * 4 * 4


@pytest.mark.qt
def test_present_processed_pixmap_publishes_into_runtime(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 94)
    try:
        pixmap = _pixmap(8, 5)
        image = present_processed_pixmap(runtime, pixmap, image_path="p.png")
        # The runtime's scene now owns exactly that immutable base image.
        assert runtime.scene_controller.presentation_image == image
        assert runtime.scene_controller.presentation_image.pixel_size == (8, 5)

        # Clear drops the base image while keeping the generation live.
        runtime.clear()
        assert runtime.scene_controller.presentation_image is None
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_runtime_target_size_is_identity_pixels(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 95)
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
        qt_app.processEvents()
