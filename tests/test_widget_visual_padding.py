"""
Tests for BaseOverlayWidget visual padding helpers.

Tests cover:
- Visual padding setter/getter
- Visual offset computation for all 9 anchor positions
- Position update with visual padding applied
"""
import pytest
from PySide6.QtCore import QPoint, QSize
from PySide6.QtWidgets import QWidget

from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition


class ConcreteOverlayWidget(BaseOverlayWidget):
    """Concrete implementation for testing."""
    
    def __init__(self, parent=None, position=OverlayPosition.TOP_RIGHT):
        super().__init__(parent, position, "test_widget")
        self._content_size = QSize(100, 50)
    
    def sizeHint(self):
        return self._content_size
    
    def set_content_size(self, width: int, height: int):
        self._content_size = QSize(width, height)


class TestVisualPaddingSetterGetter:
    """Tests for visual padding setter and getter."""
    
    def test_default_padding_is_zero(self, qtbot):
        """Test that default visual padding is zero."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent)
        qtbot.addWidget(widget)
        
        padding = widget.get_visual_padding()
        assert padding == (0, 0, 0, 0)
    
    def test_set_visual_padding(self, qtbot):
        """Test setting visual padding."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent)
        qtbot.addWidget(widget)
        
        widget.set_visual_padding(top=10, right=20, bottom=15, left=25)
        
        padding = widget.get_visual_padding()
        assert padding == (10, 20, 15, 25)
    
    def test_set_visual_padding_clamps_negative(self, qtbot):
        """Test that negative padding values are clamped to zero."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent)
        qtbot.addWidget(widget)
        
        widget.set_visual_padding(top=-5, right=-10, bottom=-15, left=-20)
        
        padding = widget.get_visual_padding()
        assert padding == (0, 0, 0, 0)


class TestVisualOffsetComputation:
    """Tests for _compute_visual_offset() method."""
    
    def test_top_left_offset(self, qtbot):
        """Test visual offset for TOP_LEFT position."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.TOP_LEFT)
        qtbot.addWidget(widget)
        widget.set_visual_padding(top=10, right=20, bottom=15, left=25)
        
        offset = widget._compute_visual_offset()
        # TOP_LEFT: shift left by left padding, up by top padding
        assert offset.x() == -25
        assert offset.y() == -10
    
    def test_top_right_offset(self, qtbot):
        """Test visual offset for TOP_RIGHT position."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.TOP_RIGHT)
        qtbot.addWidget(widget)
        widget.set_visual_padding(top=10, right=20, bottom=15, left=25)
        
        offset = widget._compute_visual_offset()
        # TOP_RIGHT: shift right by right padding, up by top padding
        assert offset.x() == 20
        assert offset.y() == -10
    
    def test_bottom_left_offset(self, qtbot):
        """Test visual offset for BOTTOM_LEFT position."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        widget.set_visual_padding(top=10, right=20, bottom=15, left=25)
        
        offset = widget._compute_visual_offset()
        # BOTTOM_LEFT: shift left by left padding, down by bottom padding
        assert offset.x() == -25
        assert offset.y() == 15
    
    def test_bottom_right_offset(self, qtbot):
        """Test visual offset for BOTTOM_RIGHT position."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.BOTTOM_RIGHT)
        qtbot.addWidget(widget)
        widget.set_visual_padding(top=10, right=20, bottom=15, left=25)
        
        offset = widget._compute_visual_offset()
        # BOTTOM_RIGHT: shift right by right padding, down by bottom padding
        assert offset.x() == 20
        assert offset.y() == 15
    
    def test_center_offset(self, qtbot):
        """Test visual offset for CENTER position."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.CENTER)
        qtbot.addWidget(widget)
        widget.set_visual_padding(top=10, right=20, bottom=15, left=25)
        
        offset = widget._compute_visual_offset()
        # CENTER: no offset (centered on content)
        assert offset.x() == 0
        assert offset.y() == 0
    
    def test_top_center_offset(self, qtbot):
        """Test visual offset for TOP_CENTER position."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.TOP_CENTER)
        qtbot.addWidget(widget)
        widget.set_visual_padding(top=10, right=20, bottom=15, left=25)
        
        offset = widget._compute_visual_offset()
        # TOP_CENTER: no horizontal offset, up by top padding
        assert offset.x() == 0
        assert offset.y() == -10
    
    def test_bottom_center_offset(self, qtbot):
        """Test visual offset for BOTTOM_CENTER position."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.BOTTOM_CENTER)
        qtbot.addWidget(widget)
        widget.set_visual_padding(top=10, right=20, bottom=15, left=25)
        
        offset = widget._compute_visual_offset()
        # BOTTOM_CENTER: no horizontal offset, down by bottom padding
        assert offset.x() == 0
        assert offset.y() == 15
    
    def test_middle_left_offset(self, qtbot):
        """Test visual offset for MIDDLE_LEFT position."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.MIDDLE_LEFT)
        qtbot.addWidget(widget)
        widget.set_visual_padding(top=10, right=20, bottom=15, left=25)
        
        offset = widget._compute_visual_offset()
        # MIDDLE_LEFT: shift left by left padding, no vertical offset
        assert offset.x() == -25
        assert offset.y() == 0
    
    def test_middle_right_offset(self, qtbot):
        """Test visual offset for MIDDLE_RIGHT position."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.MIDDLE_RIGHT)
        qtbot.addWidget(widget)
        widget.set_visual_padding(top=10, right=20, bottom=15, left=25)
        
        offset = widget._compute_visual_offset()
        # MIDDLE_RIGHT: shift right by right padding, no vertical offset
        assert offset.x() == 20
        assert offset.y() == 0


class TestPositionWithVisualPadding:
    """Tests for position update with visual padding applied."""
    
    def test_top_left_position_with_padding(self, qtbot):
        """Test TOP_LEFT position accounts for visual padding."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.TOP_LEFT)
        widget.set_content_size(100, 50)
        widget.set_margin(20)
        qtbot.addWidget(widget)
        
        # Without padding
        widget._update_position()
        pos_without = widget.pos()
        
        # With padding
        widget.set_visual_padding(left=10, top=5)
        pos_with = widget.pos()
        
        # Position should shift by visual offset
        assert pos_with.x() == pos_without.x() - 10
        assert pos_with.y() == pos_without.y() - 5
    
    def test_bottom_right_position_with_padding(self, qtbot):
        """Test BOTTOM_RIGHT position accounts for visual padding."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.BOTTOM_RIGHT)
        widget.set_content_size(100, 50)
        widget.set_margin(20)
        qtbot.addWidget(widget)
        
        # Without padding
        widget._update_position()
        pos_without = widget.pos()
        
        # With padding
        widget.set_visual_padding(right=15, bottom=10)
        pos_with = widget.pos()
        
        # Position should shift by visual offset
        assert pos_with.x() == pos_without.x() + 15
        assert pos_with.y() == pos_without.y() + 10


class TestVisualPaddingWithPixelShift:
    """Tests for visual padding combined with pixel shift."""
    
    def test_padding_applied_before_pixel_shift(self, qtbot):
        """Test that visual padding is applied before pixel shift."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        
        widget = ConcreteOverlayWidget(parent, OverlayPosition.TOP_LEFT)
        widget.set_content_size(100, 50)
        widget.set_margin(20)
        qtbot.addWidget(widget)
        
        # Set both padding and pixel shift
        widget.set_visual_padding(left=10, top=5)
        widget._pixel_shift_offset = QPoint(3, 3)
        widget._update_position()
        
        # Base position: margin (20, 20)
        # Visual offset: (-10, -5)
        # Pixel shift: (3, 3)
        # Final: (20 - 10 + 3, 20 - 5 + 3) = (13, 18)
        pos = widget.pos()
        assert pos.x() == 13
        assert pos.y() == 18


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
