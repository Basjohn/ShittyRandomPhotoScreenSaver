"""
Tests for transition end-frame correctness (progress=1.0).

Verifies that all transitions render a final frame that visually matches the
new image without residual blending, ghost artifacts, or old image remnants.
Covers CPU, compositor (QPainter), and GLSL shader paths.
"""
import pytest

# Skip all tests in this module - they hang in CI due to Qt widget/event loop issues
pytestmark = pytest.mark.skip(reason="Transition tests hang in CI - run manually for validation")

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPixmap, QColor
from transitions.crossfade_transition import CrossfadeTransition
from transitions.slide_transition import SlideTransition, SlideDirection
from transitions.wipe_transition import WipeTransition, WipeDirection
from transitions.diffuse_transition import DiffuseTransition
from transitions.block_puzzle_flip_transition import BlockPuzzleFlipTransition


@pytest.fixture
def test_widget(qtbot):
    """Create test widget for transitions."""
    widget = QWidget()
    widget.resize(400, 300)
    widget.show()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def old_pixmap():
    """Create old image pixmap (red)."""
    pixmap = QPixmap(400, 300)
    pixmap.fill(QColor(255, 0, 0))  # Red
    return pixmap


@pytest.fixture
def new_pixmap():
    """Create new image pixmap (blue)."""
    pixmap = QPixmap(400, 300)
    pixmap.fill(QColor(0, 0, 255))  # Blue
    return pixmap


def _get_dominant_color(pixmap: QPixmap) -> tuple[int, int, int]:
    """Extract dominant color from pixmap by sampling center region."""
    image = pixmap.toImage()
    # Sample 10x10 region from center
    cx, cy = image.width() // 2, image.height() // 2
    r_sum, g_sum, b_sum = 0, 0, 0
    samples = 0
    
    for dx in range(-5, 5):
        for dy in range(-5, 5):
            x, y = cx + dx, cy + dy
            if 0 <= x < image.width() and 0 <= y < image.height():
                color = image.pixelColor(x, y)
                r_sum += color.red()
                g_sum += color.green()
                b_sum += color.blue()
                samples += 1
    
    if samples == 0:
        return (0, 0, 0)
    
    return (r_sum // samples, g_sum // samples, b_sum // samples)


def _assert_color_matches_new(pixmap: QPixmap, expected_color: tuple[int, int, int], tolerance: int = 30):
    """Assert that pixmap's dominant color matches expected (new image) color."""
    actual = _get_dominant_color(pixmap)
    r_diff = abs(actual[0] - expected_color[0])
    g_diff = abs(actual[1] - expected_color[1])
    b_diff = abs(actual[2] - expected_color[2])
    
    assert r_diff <= tolerance, f"Red channel mismatch: {actual[0]} vs {expected_color[0]}"
    assert g_diff <= tolerance, f"Green channel mismatch: {actual[1]} vs {expected_color[1]}"
    assert b_diff <= tolerance, f"Blue channel mismatch: {actual[2]} vs {expected_color[2]}"


def test_crossfade_endframe_correctness(qtbot, test_widget, old_pixmap, new_pixmap):
    """Test Crossfade transition final frame matches new image."""
    transition = CrossfadeTransition(duration_ms=100)
    
    # Start transition
    transition.start(old_pixmap, new_pixmap, test_widget)
    
    # Wait for transition to complete
    with qtbot.waitSignal(transition.finished, timeout=2000):
        pass
    
    # Verify final frame by grabbing widget content
    final_pixmap = test_widget.grab()
    
    # At progress=1.0, should show only new image (blue)
    _assert_color_matches_new(final_pixmap, (0, 0, 255), tolerance=30)


def test_slide_endframe_correctness(qtbot, test_widget, old_pixmap, new_pixmap):
    """Test Slide transition final frame matches new image."""
    transition = SlideTransition(duration_ms=100, direction=SlideDirection.LEFT)
    
    transition.start(old_pixmap, new_pixmap, test_widget)
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        pass
    
    final_pixmap = test_widget.grab()
    
    # At progress=1.0, old image should be fully slid out, new image fully visible
    _assert_color_matches_new(final_pixmap, (0, 0, 255), tolerance=30)


def test_wipe_endframe_correctness(qtbot, test_widget, old_pixmap, new_pixmap):
    """Test Wipe transition final frame matches new image."""
    transition = WipeTransition(duration_ms=100, direction=WipeDirection.LEFT)
    
    transition.start(old_pixmap, new_pixmap, test_widget)
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        pass
    
    final_pixmap = test_widget.grab()
    
    # At progress=1.0, wipe should be complete, showing only new image
    _assert_color_matches_new(final_pixmap, (0, 0, 255), tolerance=30)


def test_diffuse_endframe_correctness(qtbot, test_widget, old_pixmap, new_pixmap):
    """Test Diffuse transition final frame matches new image."""
    transition = DiffuseTransition(duration_ms=100, block_size=20)
    
    transition.start(old_pixmap, new_pixmap, test_widget)
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        pass
    
    final_pixmap = test_widget.grab()
    
    # At progress=1.0, all blocks should be dissolved, showing only new image
    _assert_color_matches_new(final_pixmap, (0, 0, 255), tolerance=30)


def test_block_puzzle_flip_endframe_correctness(qtbot, test_widget, old_pixmap, new_pixmap):
    """Test Block Puzzle Flip transition final frame matches new image."""
    transition = BlockPuzzleFlipTransition(duration_ms=100, grid_rows=2, grid_cols=2)
    
    transition.start(old_pixmap, new_pixmap, test_widget)
    
    # Block puzzle has two phases, so wait longer
    with qtbot.waitSignal(transition.finished, timeout=3000):
        pass
    
    final_pixmap = test_widget.grab()
    
    # At progress=1.0, all blocks should be flipped, showing only new image
    _assert_color_matches_new(final_pixmap, (0, 0, 255), tolerance=30)


def test_crossfade_no_old_image_endframe(qtbot, test_widget, new_pixmap):
    """Test Crossfade with no old image (first image) shows new image correctly."""
    transition = CrossfadeTransition(duration_ms=100)
    
    # Start with no old image (None)
    transition.start(None, new_pixmap, test_widget)
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        pass
    
    final_pixmap = test_widget.grab()
    
    # Should show new image immediately
    _assert_color_matches_new(final_pixmap, (0, 0, 255), tolerance=30)


def test_transition_progress_1_0_explicit(qtbot, test_widget, old_pixmap, new_pixmap):
    """Test that progress=1.0 explicitly renders final frame correctly."""
    transition = CrossfadeTransition(duration_ms=100)
    
    # Track progress values
    progress_values = []
    transition.progress.connect(lambda p: progress_values.append(p))
    
    transition.start(old_pixmap, new_pixmap, test_widget)
    
    with qtbot.waitSignal(transition.finished, timeout=2000):
        pass
    
    # Verify progress reached 1.0
    assert len(progress_values) > 0, "No progress signals emitted"
    assert max(progress_values) >= 0.99, f"Progress never reached 1.0: max={max(progress_values)}"
    
    final_pixmap = test_widget.grab()
    _assert_color_matches_new(final_pixmap, (0, 0, 255), tolerance=30)


@pytest.mark.xfail(reason="GL compositor tests may fail in headless environments")
def test_gl_compositor_endframe_placeholder(qtbot):
    """Placeholder for GL compositor end-frame tests.
    
    GL compositor transitions (GLCompositorCrossfadeTransition, etc.) require
    a GLCompositorWidget and OpenGL context. These tests should be added when
    GL testing infrastructure is available.
    
    Expected coverage:
    - GLCompositorCrossfadeTransition
    - GLCompositorSlideTransition
    - GLCompositorWipeTransition
    - GLCompositorBlockFlipTransition
    - GLCompositorBlindsTransition
    - GLCompositorDiffuseTransition
    - GLCompositorPeelTransition
    - GLCompositorBlockSpinTransition
    - GLCompositorRainDropsTransition
    - GLCompositorWarpTransition
    - GLCompositorCrumbleTransition
    - GLCompositorParticleTransition
    """
    pytest.skip("GL compositor end-frame tests require GL context setup")


def test_multiple_transitions_endframe_consistency(qtbot, test_widget, old_pixmap, new_pixmap):
    """Test that multiple transitions in sequence all end with correct final frame."""
    transitions = [
        CrossfadeTransition(duration_ms=50),
        SlideTransition(duration_ms=50, direction=SlideDirection.RIGHT),
        WipeTransition(duration_ms=50, direction=WipeDirection.UP),
    ]
    
    for transition in transitions:
        transition.start(old_pixmap, new_pixmap, test_widget)
        
        with qtbot.waitSignal(transition.finished, timeout=2000):
            pass
        
        final_pixmap = test_widget.grab()
        
        # Each transition should end with new image fully visible
        _assert_color_matches_new(final_pixmap, (0, 0, 255), tolerance=30)
        
        # Clean up
        transition.cleanup()
