"""Phase C1 gates for detached Qt Quick image presentation state."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import threading

import pytest
from PySide6.QtGui import QColor, QImage, QPixmap

from rendering.quick.image_boundary import capture_qimage, capture_qpixmap
from rendering.quick.image_state import PresentationImage
from rendering.quick.render import BackgroundRenderItem


ROOT = Path(__file__).resolve().parents[1]


def _two_pixel_image() -> QImage:
    image = QImage(2, 1, QImage.Format.Format_RGBA8888)
    image.setPixelColor(0, 0, QColor(10, 20, 30, 40))
    image.setPixelColor(1, 0, QColor(50, 60, 70, 80))
    image.setDevicePixelRatio(2.0)
    return image


def test_qimage_capture_is_tightly_packed_rgba_and_deeply_detached():
    source = _two_pixel_image()

    captured = capture_qimage(
        source,
        identity="processed:path|size:2x1|dpr:2",
        source_path="C:/images/example.png",
    )
    source.fill(QColor(255, 255, 255, 255))

    assert captured.pixel_size == (2, 1)
    assert captured.logical_size == (1.0, 0.5)
    assert captured.device_pixel_ratio == 2.0
    assert captured.row_stride == 8
    assert captured.rgba8 == bytes((10, 20, 30, 40, 50, 60, 70, 80))
    assert captured.byte_count == 8
    assert captured.describe()["byte_count"] == 8
    assert "rgba8" not in captured.describe()


def test_presentation_image_freezes_metadata_and_copies_mutable_payload():
    payload = bytearray((1, 2, 3, 4))
    captured = PresentationImage(
        identity="frame-1",
        source_path="",
        logical_size=(1, 1),
        device_pixel_ratio=1,
        pixel_size=(1, 1),
        row_stride=4,
        rgba8=payload,  # type: ignore[arg-type]
    )
    payload[0] = 99

    assert captured.rgba8 == b"\x01\x02\x03\x04"
    assert isinstance(captured.rgba8, bytes)
    with pytest.raises(FrozenInstanceError):
        captured.identity = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"identity": ""}, "identity"),
        ({"logical_size": (0, 1)}, "logical size"),
        ({"device_pixel_ratio": 0}, "DPR"),
        ({"pixel_size": (0, 1)}, "pixel size"),
        ({"row_stride": 8}, "tightly packed"),
        ({"rgba8": b"\x00"}, "wrong size"),
    ],
)
def test_presentation_image_rejects_ambiguous_or_invalid_state(changes, message):
    values = {
        "identity": "frame-1",
        "source_path": "",
        "logical_size": (1, 1),
        "device_pixel_ratio": 1,
        "pixel_size": (1, 1),
        "row_stride": 4,
        "rgba8": b"\x00\x00\x00\xff",
    }
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        PresentationImage(**values)


def test_capture_rejects_null_qt_images(qt_app):
    with pytest.raises(ValueError, match="non-null QImage"):
        capture_qimage(QImage(), identity="null")
    with pytest.raises(ValueError, match="non-null QPixmap"):
        capture_qpixmap(QPixmap(), identity="null")


def test_gui_thread_qpixmap_capture_detaches_the_legacy_pipeline_object(qt_app):
    pixmap = QPixmap.fromImage(_two_pixel_image())
    expected = capture_qimage(pixmap.toImage(), identity="expected-pixmap-storage")

    captured = capture_qpixmap(
        pixmap,
        identity="legacy-processed-frame",
        source_path="C:/images/legacy.png",
    )
    pixmap.fill(QColor(255, 255, 255, 255))

    assert captured.pixel_size == (2, 1)
    assert captured.logical_size == (1.0, 0.5)
    assert captured.device_pixel_ratio == 2.0
    assert captured.rgba8 == expected.rgba8


def test_qpixmap_capture_is_explicitly_gui_thread_only(qt_app):
    pixmap = QPixmap.fromImage(_two_pixel_image())
    errors: list[BaseException] = []

    def capture_off_thread() -> None:
        try:
            capture_qpixmap(pixmap, identity="off-thread")
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=capture_off_thread)
    worker.start()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert "GUI thread" in str(errors[0])


def test_render_thread_modules_do_not_import_live_qt_image_or_widget_state():
    render_paths = [
        ROOT / "rendering" / "quick" / "image_state.py",
        ROOT / "rendering" / "quick" / "render" / "background_item.py",
        ROOT / "rendering" / "quick" / "render" / "background_node.py",
        ROOT / "rendering" / "quick" / "render" / "image_textures.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in render_paths)

    for forbidden in ("QPixmap", "QImage", "QWidget", "SettingsManager"):
        assert forbidden not in source
    assert "PresentationImage" in source
    assert "image.rgba8" in source


def test_item_rejects_changed_content_reusing_an_existing_identity(qt_app):
    item = BackgroundRenderItem()
    first = capture_qimage(_two_pixel_image(), identity="processed-frame")
    changed_source = _two_pixel_image()
    changed_source.setPixelColor(0, 0, QColor(200, 10, 20, 255))
    conflicting = capture_qimage(changed_source, identity="processed-frame")

    item.set_presentation_image(first)
    item.set_presentation_image(first)
    with pytest.raises(ValueError, match="identity was reused"):
        item.set_presentation_image(conflicting)
