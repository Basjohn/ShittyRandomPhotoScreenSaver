"""Tests for transition system.

Tests base transition state/enum and GL compositor crossfade creation.
GL compositor transitions require an attached GLCompositorWidget to run a
real animation — without one they complete immediately. Tests that relied
on a self-contained SW animation loop are skipped.
"""
import pytest
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from transitions.base_transition import TransitionState, SlideDirection, WipeDirection
from transitions.gl_compositor_crossfade_transition import GLCompositorCrossfadeTransition


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def test_widget(qapp):
    """Create test widget."""
    widget = QWidget()
    widget.resize(400, 300)
    yield widget
    widget.deleteLater()


@pytest.fixture
def test_pixmap():
    """Create test pixmap."""
    pixmap = QPixmap(400, 300)
    pixmap.fill(Qt.GlobalColor.red)
    return pixmap


@pytest.fixture
def test_pixmap2():
    """Create second test pixmap."""
    pixmap = QPixmap(400, 300)
    pixmap.fill(Qt.GlobalColor.blue)
    return pixmap


def test_transition_state_enum():
    """Test TransitionState enum."""
    assert TransitionState.IDLE.value == "idle"
    assert TransitionState.RUNNING.value == "running"
    assert TransitionState.PAUSED.value == "paused"
    assert TransitionState.FINISHED.value == "finished"
    assert TransitionState.CANCELLED.value == "cancelled"


def test_slide_direction_enum():
    """Test SlideDirection enum values."""
    assert SlideDirection.LEFT.value == "left"
    assert SlideDirection.RIGHT.value == "right"
    assert SlideDirection.UP.value == "up"
    assert SlideDirection.DOWN.value == "down"
    assert SlideDirection.DIAG_TL_BR.value == "diag_tl_br"
    assert SlideDirection.DIAG_TR_BL.value == "diag_tr_bl"


def test_wipe_direction_enum():
    """Test WipeDirection enum values."""
    assert WipeDirection.LEFT_TO_RIGHT.value == "left_to_right"
    assert WipeDirection.RIGHT_TO_LEFT.value == "right_to_left"
    assert WipeDirection.TOP_TO_BOTTOM.value == "top_to_bottom"
    assert WipeDirection.BOTTOM_TO_TOP.value == "bottom_to_top"
    assert WipeDirection.DIAG_TL_BR.value == "diag_tl_br"
    assert WipeDirection.DIAG_TR_BL.value == "diag_tr_bl"


def test_crossfade_creation():
    """Test crossfade transition creation."""
    transition = GLCompositorCrossfadeTransition(duration_ms=500)
    
    assert transition is not None
    assert transition.get_duration() == 500
    assert transition.get_state() == TransitionState.IDLE
    assert transition.is_running() is False


def test_crossfade_duration():
    """Test setting duration."""
    transition = GLCompositorCrossfadeTransition(duration_ms=1000)
    
    assert transition.get_duration() == 1000
    
    transition.set_duration(2000)
    assert transition.get_duration() == 2000
    
    # Invalid duration should fall back to 1000ms
    transition.set_duration(-100)
    assert transition.get_duration() == 1000


def test_crossfade_start_no_compositor(qapp, test_widget, test_pixmap, test_pixmap2):
    """GL compositor transition completes immediately when no compositor is attached."""
    transition = GLCompositorCrossfadeTransition(duration_ms=200)
    result = transition.start(test_pixmap, test_pixmap2, test_widget)
    # Without a compositor, should return True but finish immediately
    assert result is True
    assert transition.get_state() == TransitionState.FINISHED


def test_crossfade_invalid_pixmap(qapp, test_widget):
    """Test transition with invalid pixmap."""
    transition = GLCompositorCrossfadeTransition(duration_ms=100)
    
    # Create null pixmap
    null_pixmap = QPixmap()
    
    result = transition.start(None, null_pixmap, test_widget)
    assert result is False


def test_crossfade_easing_constructor():
    """Test easing is set via constructor."""
    transition = GLCompositorCrossfadeTransition(duration_ms=100, easing='OutQuad')
    assert transition._easing_str == 'OutQuad'
    
    transition2 = GLCompositorCrossfadeTransition(duration_ms=100, easing='InCubic')
    assert transition2._easing_str == 'InCubic'


def test_crossfade_repr():
    """Test transition string representation."""
    transition = GLCompositorCrossfadeTransition(duration_ms=500)
    
    repr_str = repr(transition)
    assert '500ms' in repr_str or '500' in repr_str


def test_crossfade_cleanup(qapp, test_widget, test_pixmap, test_pixmap2):
    """Test transition cleanup."""
    transition = GLCompositorCrossfadeTransition(duration_ms=100)
    
    transition.start(test_pixmap, test_pixmap2, test_widget)
    transition.stop()
    transition.cleanup()
    
    # State should be idle, cancelled, or finished
    assert transition.get_state() in [
        TransitionState.IDLE, TransitionState.CANCELLED, TransitionState.FINISHED
    ]
