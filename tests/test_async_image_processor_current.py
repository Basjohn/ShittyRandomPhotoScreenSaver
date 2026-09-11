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
@pytest.mark.parametrize("use_lanczos", (False, True))
def test_resolved_modes_return_exact_screen_canvas(mode, use_lanczos) -> None:
    if use_lanczos and not PILLOW_AVAILABLE:
        pytest.skip("PIL/Pillow not installed")
    result = AsyncImageProcessor.process_qimage(
        _image(1600, 900),
        QSize(1920, 1080),
        mode,
        use_lanczos=use_lanczos,
        sharpen=False,
    )
    assert not result.isNull()
    assert result.size() == QSize(1920, 1080)


def test_fill_portrait_crops_to_exact_screen() -> None:
    result = AsyncImageProcessor.process_qimage(
        _image(1080, 1920),
        QSize(1920, 1080),
        DisplayMode.FILL,
        use_lanczos=False,
        sharpen=False,
    )
    assert result.size() == QSize(1920, 1080)


def test_shrink_small_image_does_not_upscale_source_pixels() -> None:
    source = _image(200, 160)
    screen = QSize(800, 600)
    result = AsyncImageProcessor.process_qimage(
        source,
        screen,
        DisplayMode.SHRINK,
        use_lanczos=False,
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
        use_lanczos=False,
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
        use_lanczos=True,
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
        use_lanczos=True,
        sharpen=False,
    )
    assert not result.isNull()
    assert result.hasAlphaChannel()


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
