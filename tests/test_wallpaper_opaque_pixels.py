"""PR-04 Stage A: wallpaper pixels are opaque, so the native branch labels them premultiplied.

One compositing rule: transparent source pixels are composited over opaque black
by the image-processing owners (the ImageWorker prescale in every display mode;
the in-process AsyncImageProcessor, whose FILL perfect-fit branch used to return
the source unchanged). The retained native background then hands Qt a
``Format_RGBA8888_Premultiplied`` QImage, byte-identical for opaque pixels, which
spares Qt a full straight->premultiplied conversion before every upload.
"""

from __future__ import annotations

import pytest
from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage

from core.process.types import MessageType, WorkerMessage, WorkerType
from core.process.workers.image_worker import ImageWorker
from rendering.display_modes import DisplayMode
from rendering.image_processor_async import AsyncImageProcessor
from rendering.quick.display_image_route import presentation_image_from_processed_qimage
from rendering.quick.image_state import PresentationImage
from rendering.quick.render.background_image_node import RetainedBackgroundSceneNode
from rendering.quick.render.telemetry import RenderNodeTelemetry

# Straight-alpha source colour and its expected result over opaque black.
_SOURCE_RGBA = (200, 100, 40, 128)
_OVER_BLACK = tuple(round(channel * 128 / 255) for channel in _SOURCE_RGBA[:3])


def _rgba_pixels(image: QImage) -> bytes:
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    view = converted.constBits()
    data = view.tobytes() if hasattr(view, "tobytes") else bytes(view)
    return data[: converted.bytesPerLine() * converted.height()]


def _assert_opaque_over_black(rgba: bytes) -> None:
    assert rgba, "no pixels"
    alphas = set(rgba[3::4])
    assert alphas == {255}, f"non-opaque wallpaper alpha values: {sorted(alphas)[:5]}"
    for offset, expected in enumerate(_OVER_BLACK):
        channel = set(rgba[offset::4])
        # Either the composited source or the black padding, nothing else.
        assert channel <= {expected, expected - 1, expected + 1, 0}, (offset, sorted(channel)[:5])


def _transparent_qimage(width: int, height: int) -> QImage:
    image = QImage(QSize(width, height), QImage.Format.Format_RGBA8888)
    image.fill(QColor(*_SOURCE_RGBA))
    return image


@pytest.mark.parametrize(
    ("mode", "source", "screen"),
    [
        (DisplayMode.FILL, (64, 48), (64, 48)),  # perfect fit: the branch that leaked alpha
        (DisplayMode.FILL, (96, 48), (64, 48)),  # crop
        (DisplayMode.FIT, (96, 48), (64, 48)),
        (DisplayMode.SHRINK, (32, 24), (64, 48)),
    ],
)
def test_in_process_processor_returns_opaque_pixels_for_transparent_sources(
    qt_app, mode, source, screen
) -> None:
    result = AsyncImageProcessor.process_qimage(
        _transparent_qimage(*source), QSize(*screen), mode, use_lanczos=False, sharpen=False
    )
    assert result.size() == QSize(*screen)
    _assert_opaque_over_black(_rgba_pixels(result))


def test_in_process_perfect_fit_leaves_opaque_sources_untouched(qt_app) -> None:
    source = QImage(QSize(64, 48), QImage.Format.Format_RGB32)
    source.fill(QColor(12, 34, 56))
    result = AsyncImageProcessor.process_qimage(
        source, QSize(64, 48), DisplayMode.FILL, use_lanczos=False, sharpen=False
    )
    assert result.cacheKey() == source.cacheKey()


@pytest.fixture
def worker():
    class _Queue:
        def put_nowait(self, _item) -> None:
            pass

    image_worker = ImageWorker(_Queue(), _Queue())
    try:
        yield image_worker
    finally:
        image_worker._cleanup()


@pytest.mark.parametrize(
    ("mode", "source", "target"),
    [
        ("fill", (64, 48), (64, 48)),  # exact size: returned unchanged before the fix
        ("fill", (96, 48), (64, 48)),  # centre crop
        ("fit", (96, 48), (64, 48)),  # black padding via paste()
        ("shrink", (32, 24), (64, 48)),
    ],
)
def test_worker_prescale_returns_opaque_pixels_for_transparent_sources(
    worker, tmp_path, mode, source, target
) -> None:
    path = tmp_path / "transparent.png"
    Image.new("RGBA", source, _SOURCE_RGBA).save(path, "PNG")
    response = worker.handle_message(
        WorkerMessage(
            msg_type=MessageType.IMAGE_PRESCALE,
            seq_no=1,
            correlation_id=f"opaque-{mode}",
            payload={
                "path": str(path),
                "target_width": target[0],
                "target_height": target[1],
                "mode": mode,
                "use_lanczos": False,
                "sharpen": False,
            },
            worker_type=WorkerType.IMAGE,
        )
    )
    assert response is not None and response.success is True
    assert (response.payload["width"], response.payload["height"]) == target
    _assert_opaque_over_black(response.payload["rgba_data"])


def test_processed_route_captures_opaque_presentation_pixels(qt_app) -> None:
    processed = AsyncImageProcessor.process_qimage(
        _transparent_qimage(64, 48), QSize(64, 48), DisplayMode.FILL,
        use_lanczos=False, sharpen=False,
    )
    presentation = presentation_image_from_processed_qimage(processed, image_path="t.png")
    _assert_opaque_over_black(presentation.rgba8)


def test_native_background_labels_opaque_pixels_premultiplied(qt_app) -> None:
    from PySide6.QtQuick import QSGSimpleTextureNode

    handed: list[QImage] = []

    class _Window:
        def createImageNode(self):
            return QSGSimpleTextureNode()

        def createTextureFromImage(self, image, _options):
            handed.append(QImage(image))
            return None  # stop after the upload hand-off; no scene graph here

    width, height = 8, 4
    rgba = bytes(255 if i % 4 == 3 else (10 * i) % 256 for i in range(width * height * 4))
    image = PresentationImage(
        identity="opaque-8x4",
        source_path="",
        logical_size=(float(width), float(height)),
        device_pixel_ratio=1.0,
        pixel_size=(width, height),
        row_stride=width * 4,
        rgba8=rgba,
    )
    node = RetainedBackgroundSceneNode(
        window=_Window(),
        telemetry=RenderNodeTelemetry(gui_thread_id=1),
        screen_index=0,
        frame_trace=None,
    )
    with pytest.raises(RuntimeError, match="did not create a retained background texture"):
        node._synchronize_native_image(image, logical_size=(float(width), float(height)))

    assert len(handed) == 1
    assert handed[0].format() == QImage.Format.Format_RGBA8888_Premultiplied
    # Same bytes: premultiplied and straight RGBA agree for opaque pixels.
    assert _rgba_pixels(handed[0]) == rgba
    straight = QImage(rgba, width, height, width * 4, QImage.Format.Format_RGBA8888)
    assert _rgba_pixels(straight) == _rgba_pixels(handed[0])
