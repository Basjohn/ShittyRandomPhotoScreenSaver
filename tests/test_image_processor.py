"""Tests for image processor."""
import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap, QImage
from rendering.image_processor import ImageProcessor
from rendering.display_modes import DisplayMode
from rendering.image_processor_async import AsyncImageProcessor


@pytest.fixture
def create_test_image(qt_app):
    """Factory for creating test images of various sizes."""
    def _create(width: int, height: int, color=Qt.GlobalColor.red) -> QPixmap:
        """Create a solid color test image."""
        pixmap = QPixmap(width, height)
        pixmap.fill(color)
        return pixmap
    return _create


def test_fill_mode_wider_image(create_test_image):
    """Test FILL mode with wider image (landscape)."""
    # Create 1600x900 image for 1920x1080 screen
    image = create_test_image(1600, 900)
    screen_size = QSize(1920, 1080)
    
    result = ImageProcessor.process_image(image, screen_size, DisplayMode.FILL)
    
    # Result should be exact screen size
    assert result.width() == 1920
    assert result.height() == 1080
    
    # Should not be null
    assert not result.isNull()


def test_fill_mode_taller_image(create_test_image):
    """Test FILL mode with taller image (portrait)."""
    # Create 1080x1920 image for 1920x1080 screen
    image = create_test_image(1080, 1920)
    screen_size = QSize(1920, 1080)
    
    result = ImageProcessor.process_image(image, screen_size, DisplayMode.FILL)
    
    # Result should be exact screen size
    assert result.width() == 1920
    assert result.height() == 1080
    assert not result.isNull()


def test_fill_mode_small_image(create_test_image):
    """Test FILL mode with small image (needs upscaling)."""
    # Create 800x600 image for 1920x1080 screen
    image = create_test_image(800, 600)
    screen_size = QSize(1920, 1080)
    
    result = ImageProcessor.process_image(image, screen_size, DisplayMode.FILL)
    
    # Result should be exact screen size
    assert result.width() == 1920
    assert result.height() == 1080
    assert not result.isNull()


def test_fit_mode_landscape(create_test_image):
    """Test FIT mode with landscape image."""
    # Create 1600x900 image for 1920x1080 screen
    image = create_test_image(1600, 900)
    screen_size = QSize(1920, 1080)
    
    result = ImageProcessor.process_image(image, screen_size, DisplayMode.FIT)
    
    # Result should be exact screen size (background)
    assert result.width() == 1920
    assert result.height() == 1080
    
    # Image should be scaled to fit width
    # Scale factor: 1920/1600 = 1.2
    # New size: 1920x1080 (happens to fit perfectly)
    assert not result.isNull()


def test_fit_mode_portrait(create_test_image):
    """Test FIT mode with portrait image."""
    # Create 1080x1920 image for 1920x1080 screen
    image = create_test_image(1080, 1920)
    screen_size = QSize(1920, 1080)
    
    result = ImageProcessor.process_image(image, screen_size, DisplayMode.FIT)
    
    # Result should be exact screen size (with letterboxing)
    assert result.width() == 1920
    assert result.height() == 1080
    assert not result.isNull()


def test_shrink_mode_large_image(create_test_image):
    """Test SHRINK mode with image larger than screen."""
    # Create 2560x1440 image for 1920x1080 screen
    image = create_test_image(2560, 1440)
    screen_size = QSize(1920, 1080)
    
    result = ImageProcessor.process_image(image, screen_size, DisplayMode.SHRINK)
    
    # Result should be exact screen size (with background)
    assert result.width() == 1920
    assert result.height() == 1080
    
    # Image should be scaled down
    assert not result.isNull()


def test_shrink_mode_small_image(create_test_image):
    """Test SHRINK mode with image smaller than screen (no upscaling)."""
    # Create 800x600 image for 1920x1080 screen
    image = create_test_image(800, 600)
    screen_size = QSize(1920, 1080)
    
    result = ImageProcessor.process_image(image, screen_size, DisplayMode.SHRINK)
    
    # Result should be exact screen size (with background)
    assert result.width() == 1920
    assert result.height() == 1080
    
    # Image should NOT be upscaled (original size preserved)
    assert not result.isNull()


def test_null_image_fallback(create_test_image):
    """Test handling of null/invalid image."""
    null_image = QPixmap()
    screen_size = QSize(1920, 1080)
    
    result = ImageProcessor.process_image(null_image, screen_size, DisplayMode.FILL)
    
    # Should return empty pixmap of screen size
    assert result.width() == 1920
    assert result.height() == 1080


def test_square_image_fill(create_test_image):
    """Test FILL mode with square image."""
    # Create 1080x1080 square image for 1920x1080 screen
    image = create_test_image(1080, 1080)
    screen_size = QSize(1920, 1080)
    
    result = ImageProcessor.process_image(image, screen_size, DisplayMode.FILL)
    
    # Result should be exact screen size
    assert result.width() == 1920
    assert result.height() == 1080
    assert not result.isNull()


def test_aspect_ratio_preservation_fit(create_test_image):
    """Test that FIT mode preserves aspect ratio."""
    # Create 16:9 image
    image = create_test_image(1600, 900)
    screen_size = QSize(1920, 1080)
    
    result = ImageProcessor.process_image(image, screen_size, DisplayMode.FIT)
    
    # The scaled portion should maintain 16:9 ratio
    # (We can't directly measure the scaled portion, but output should be valid)
    assert result.width() == 1920
    assert result.height() == 1080


def test_calculate_scale_factors_fill():
    """Test scale factor calculation for FILL mode."""
    source = QSize(1600, 900)
    target = QSize(1920, 1080)
    
    scale_x, scale_y = ImageProcessor.calculate_scale_factors(source, target, DisplayMode.FILL)
    
    # Should scale to cover screen (scale by width in this case)
    assert scale_x == scale_y  # Uniform scaling
    assert scale_x == pytest.approx(1920 / 1600, rel=0.01)


def test_calculate_scale_factors_fit():
    """Test scale factor calculation for FIT mode."""
    source = QSize(2560, 1440)
    target = QSize(1920, 1080)
    
    scale_x, scale_y = ImageProcessor.calculate_scale_factors(source, target, DisplayMode.FIT)
    
    # Should scale to fit within screen
    assert scale_x == scale_y  # Uniform scaling
    # Should use smaller scale factor (1080/1440 in this case)
    assert scale_x == pytest.approx(1080 / 1440, rel=0.01)


def test_calculate_scale_factors_shrink_no_scaling():
    """Test scale factor calculation for SHRINK mode (no scaling needed)."""
    source = QSize(800, 600)
    target = QSize(1920, 1080)
    
    scale_x, scale_y = ImageProcessor.calculate_scale_factors(source, target, DisplayMode.SHRINK)
    
    # No scaling needed (image is smaller)
    assert scale_x == 1.0
    assert scale_y == 1.0


def test_calculate_scale_factors_shrink_with_scaling():
    """Test scale factor calculation for SHRINK mode (scaling needed)."""
    source = QSize(2560, 1440)
    target = QSize(1920, 1080)
    
    scale_x, scale_y = ImageProcessor.calculate_scale_factors(source, target, DisplayMode.SHRINK)
    
    # Should scale down
    assert scale_x == scale_y  # Uniform scaling
    assert scale_x < 1.0
    assert scale_x == pytest.approx(1080 / 1440, rel=0.01)


def test_get_crop_rect():
    """Test crop rectangle calculation."""
    source_size = QSize(2560, 1440)
    target_size = QSize(1920, 1080)
    
    crop_rect = ImageProcessor.get_crop_rect(source_size, target_size)
    
    # Crop should be centered
    assert crop_rect.width() == 1920
    assert crop_rect.height() == 1080
    
    # Should be centered (x offset = (2560-1920)/2 = 320)
    assert crop_rect.x() == (2560 - 1920) // 2
    # (y offset = (1440-1080)/2 = 180)
    assert crop_rect.y() == (1440 - 1080) // 2


def test_display_mode_from_string():
    """Test DisplayMode creation from string."""
    assert DisplayMode.from_string('fill') == DisplayMode.FILL
    assert DisplayMode.from_string('FILL') == DisplayMode.FILL
    assert DisplayMode.from_string('fit') == DisplayMode.FIT
    assert DisplayMode.from_string('shrink') == DisplayMode.SHRINK


def test_display_mode_from_string_invalid():
    """Test DisplayMode with invalid string."""
    with pytest.raises(ValueError, match="Invalid display mode"):
        DisplayMode.from_string('invalid')


def test_display_mode_str():
    """Test DisplayMode string representation."""
    assert str(DisplayMode.FILL) == 'fill'
    assert str(DisplayMode.FIT) == 'fit'
    assert str(DisplayMode.SHRINK) == 'shrink'


@pytest.mark.parametrize("mode", [DisplayMode.FILL, DisplayMode.FIT, DisplayMode.SHRINK])
def test_qimage_sync_matches_pixmap(create_test_image, mode):
    pixmap = create_test_image(1600, 900)
    qimage = pixmap.toImage()
    screen_size = QSize(1920, 1080)

    pix_result = ImageProcessor.process_image(pixmap, screen_size, mode)
    qi_result = AsyncImageProcessor.process_qimage(qimage, screen_size, mode)

    assert qi_result.width() == pix_result.width()
    assert qi_result.height() == pix_result.height()
    assert _to_argb32_bytes(qi_result) == _to_argb32_bytes(pix_result)


@pytest.mark.parametrize("mode", [DisplayMode.FILL, DisplayMode.FIT, DisplayMode.SHRINK])
def test_qimage_async_matches_sync(create_test_image, thread_manager, mode):
    """Async QImage path should match the sync QImage helper pixel-for-pixel.

    We use a callback + polling rather than get_task_result so the test does
    not depend on ThreadManager's internal _active_tasks bookkeeping.
    """

    from core.threading.manager import TaskResult  # local import for tests
    import time

    pixmap = create_test_image(1600, 900)
    qimage = pixmap.toImage()
    screen_size = QSize(1920, 1080)

    sync_img = AsyncImageProcessor.process_qimage(qimage, screen_size, mode)

    results: list[TaskResult] = []

    def _on_done(res: TaskResult) -> None:
        results.append(res)

    AsyncImageProcessor.process_qimage_async(
        thread_manager,
        qimage,
        screen_size,
        mode,
        callback=_on_done,
    )

    deadline = time.time() + 2.0
    while not results and time.time() < deadline:
        time.sleep(0.01)

    assert results, "Async QImage task did not complete in time"
    task_result = results[0]
    assert task_result.success
    async_img = task_result.result
    assert isinstance(async_img, QImage)

    assert async_img.width() == sync_img.width()
    assert async_img.height() == sync_img.height()
    assert _to_argb32_bytes(async_img) == _to_argb32_bytes(sync_img)


def _to_argb32_bytes(value) -> bytes:
    if isinstance(value, QPixmap):
        image = value.toImage()
    else:
        image = QImage(value)
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    ptr = image.constBits()
    if hasattr(ptr, "setsize"):
        ptr.setsize(image.sizeInBytes())
        return bytes(ptr)
    return ptr.tobytes()
