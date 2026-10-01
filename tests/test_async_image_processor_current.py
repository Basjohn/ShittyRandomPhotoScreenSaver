"""Current QImage-first image processing contract.

The retired synchronous QPixmap ``ImageProcessor`` is intentionally absent.
Production resolves display mode and quality flags before calling the
thread-safe ``AsyncImageProcessor`` mechanics covered here.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage

from rendering.display_modes import DisplayMode
from rendering.image_processor_async import AsyncImageProcessor, PILLOW_AVAILABLE


def _image(width: int, height: int, *, alpha: bool = False) -> QImage:
    image_format = QImage.Format.Format_RGBA8888 if alpha else QImage.Format.Format_RGB32
    image = QImage(QSize(width, height), image_format)
    image.fill(QColor(40, 120, 220, 128 if alpha else 255))
    return image


@pytest.mark.parametrize("mode", (DisplayMode.FILL, DisplayMode.FIT, DisplayMode.SHRINK))
@pytest.mark.parametrize("resample_filter", ("smooth", "hamming", "lanczos"))
def test_resolved_modes_return_exact_screen_canvas(mode, resample_filter) -> None:
    if resample_filter != "smooth" and not PILLOW_AVAILABLE:
        pytest.skip("PIL/Pillow not installed")
    result = AsyncImageProcessor.process_qimage(
        _image(1600, 900),
        QSize(1920, 1080),
        mode,
        resample_filter=resample_filter,
        sharpen=False,
    )
    assert not result.isNull()
    assert result.size() == QSize(1920, 1080)


def test_fill_portrait_crops_to_exact_screen() -> None:
    result = AsyncImageProcessor.process_qimage(
        _image(1080, 1920),
        QSize(1920, 1080),
        DisplayMode.FILL,
        resample_filter="smooth",
        sharpen=False,
    )
    assert result.size() == QSize(1920, 1080)


@pytest.mark.parametrize("source_size,target_size", [
    ((4014, 2258), (3840, 2160)),  # Dimensions from the rejected operator batch.
    ((2258, 4014), (2160, 3840)),
    ((23, 13), (16, 9)),
    ((13, 23), (9, 16)),
])
@pytest.mark.parametrize("alpha", (False, True))
@pytest.mark.parametrize("resample_filter", ("smooth", "hamming", "lanczos"))
def test_fill_rounding_covers_every_edge_without_padding(source_size, target_size, alpha, resample_filter):
    if resample_filter != "smooth" and not PILLOW_AVAILABLE:
        pytest.skip("PIL/Pillow not installed")
    result = AsyncImageProcessor.process_qimage(
        _image(*source_size, alpha=alpha), QSize(*target_size), DisplayMode.FILL,
        resample_filter=resample_filter, sharpen=False,
    )
    assert result.size() == QSize(*target_size)
    # A solid source must reach every edge; padding a short derivative would
    # satisfy the byte count but introduce a black strip, especially with alpha.
    centre = result.pixelColor(result.width() // 2, result.height() // 2)
    assert centre.alpha() == 255 and centre.blue() > 100
    for x in (0, result.width() - 1):
        for y in (0, result.height() - 1):
            edge = result.pixelColor(x, y)
            assert edge.alpha() == 255
            assert max(abs(a - b) for a, b in zip(edge.getRgb(), centre.getRgb())) <= 1


def test_shrink_small_image_does_not_upscale_source_pixels() -> None:
    source = _image(200, 160)
    screen = QSize(800, 600)
    result = AsyncImageProcessor.process_qimage(
        source,
        screen,
        DisplayMode.SHRINK,
        resample_filter="smooth",
        sharpen=False,
    )
    assert result.size() == screen
    # The original image is centered on a black canvas. Sampling just outside
    # the authored source proves SHRINK did not enlarge it to fill the screen.
    x0 = (screen.width() - source.width()) // 2
    y0 = (screen.height() - source.height()) // 2
    assert result.pixelColor(x0, y0) != QColor(Qt.GlobalColor.black)
    assert result.pixelColor(max(0, x0 - 2), y0) == QColor(Qt.GlobalColor.black)


def test_null_qimage_returns_black_screen_sized_fallback() -> None:
    screen = QSize(640, 360)
    result = AsyncImageProcessor.process_qimage(
        QImage(),
        screen,
        DisplayMode.FILL,
        resample_filter="smooth",
        sharpen=False,
    )
    assert result.size() == screen
    assert result.pixelColor(0, 0) == QColor(Qt.GlobalColor.black)


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="PIL/Pillow not installed")
def test_lanczos_aggressive_downscale_keeps_resolved_canvas_size() -> None:
    result = AsyncImageProcessor.process_qimage(
        _image(3840, 2160),
        QSize(960, 540),
        DisplayMode.FIT,
        resample_filter="lanczos",
        sharpen=True,
    )
    assert not result.isNull()
    assert result.size() == QSize(960, 540)


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="PIL/Pillow not installed")
def test_lanczos_rgba_path_preserves_alpha_capability() -> None:
    result = AsyncImageProcessor.process_qimage(
        _image(600, 600, alpha=True),
        QSize(300, 300),
        DisplayMode.FIT,
        resample_filter="lanczos",
        sharpen=False,
    )
    assert not result.isNull()
    assert result.hasAlphaChannel()


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="PIL/Pillow not installed")
@pytest.mark.parametrize("alpha", (False, True))
def test_lanczos_preserves_odd_width_rows_and_channel_order(alpha):
    source = _image(5, 3, alpha=alpha)
    for y in range(source.height()):
        for x in range(source.width()):
            source.setPixelColor(x, y, QColor(10 + x * 20, 30 + y * 60, 200 - x * 13 - y * 7))
    result = AsyncImageProcessor.process_qimage(
        source, source.size(), DisplayMode.FIT, resample_filter="lanczos", sharpen=False,
    )
    # No resize: the oracle is the authored source, not a second conversion.
    # RGB888 rows have one byte of alignment padding at this width.
    assert result.size() == source.size()
    for y in range(source.height()):
        for x in range(source.width()):
            assert result.pixelColor(x, y) == source.pixelColor(x, y)


def test_display_mode_string_contract() -> None:
    assert DisplayMode.from_string("fill") is DisplayMode.FILL
    assert DisplayMode.from_string("FILL") is DisplayMode.FILL
    assert DisplayMode.from_string("fit") is DisplayMode.FIT
    assert DisplayMode.from_string("shrink") is DisplayMode.SHRINK
    assert str(DisplayMode.FILL) == "fill"
    with pytest.raises(ValueError, match="Invalid display mode"):
        DisplayMode.from_string("invalid")


def test_dead_sync_image_processor_has_no_runtime_importers() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    production_roots = ("core", "engine", "rendering", "ui", "utils", "widgets")
    offenders: list[str] = []
    for dirname in production_roots:
        for path in (root / dirname).rglob("*.py"):
            if path.as_posix().endswith("/rendering/image_processor.py"):
                continue
            text = path.read_text(encoding="utf-8")
            if "rendering.image_processor import" in text or "rendering.image_processor." in text:
                offenders.append(path.relative_to(root).as_posix())
    assert offenders == []
