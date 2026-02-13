"""Unit tests for ImgurWidget.

Tests cover:
- Widget initialization
- Grid layout
- Lifecycle hooks
- Settings application
"""
import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect, QPoint
from PySide6.QtGui import QColor

from widgets.imgur.widget import (
    ImgurWidget, ImgurPosition, LayoutMode, GridCell,
    DEFAULT_GRID_ROWS, DEFAULT_GRID_COLS,
)


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestImgurPosition:
    """Tests for ImgurPosition enum."""
    
    def test_all_positions_defined(self):
        """Test all 9 positions are defined."""
        positions = list(ImgurPosition)
        assert len(positions) == 9
    
    def test_position_values(self):
        """Test position values match expected strings."""
        assert ImgurPosition.TOP_LEFT.value == "top_left"
        assert ImgurPosition.CENTER.value == "center"
        assert ImgurPosition.BOTTOM_RIGHT.value == "bottom_right"


class TestLayoutMode:
    """Tests for LayoutMode enum."""
    
    def test_layout_modes(self):
        """Test all layout modes are defined."""
        assert LayoutMode.VERTICAL.value == "vertical"
        assert LayoutMode.SQUARE.value == "square"
        assert LayoutMode.HYBRID.value == "hybrid"


class TestGridCell:
    """Tests for GridCell dataclass."""
    
    def test_cell_creation(self):
        """Test basic GridCell creation."""
        rect = QRect(0, 0, 100, 100)
        cell = GridCell(rect=rect)
        assert cell.rect == rect
        assert cell.image_id is None
        assert cell.pixmap is None
    
    def test_cell_with_image(self):
        """Test GridCell with image data."""
        rect = QRect(10, 20, 120, 80)
        cell = GridCell(
            rect=rect,
            image_id="test123",
            gallery_url="https://imgur.com/gallery/test123",
            aspect_ratio=1.5,
        )
        assert cell.image_id == "test123"
        assert cell.gallery_url == "https://imgur.com/gallery/test123"
        assert cell.aspect_ratio == 1.5


class TestImgurWidget:
    """Tests for ImgurWidget class."""
    
    @pytest.fixture
    def widget(self, qapp):
        """Create a test widget."""
        widget = ImgurWidget(
            parent=None,
            tag="test",
            position=ImgurPosition.TOP_RIGHT,
        )
        yield widget
        # Cleanup
        try:
            widget.deleteLater()
        except Exception:
            pass
    
    def test_init_defaults(self, widget):
        """Test widget initializes with correct defaults."""
        assert widget._tag == "test"
        assert widget._imgur_position == ImgurPosition.TOP_RIGHT
        assert widget._grid_rows == DEFAULT_GRID_ROWS
        assert widget._grid_cols == DEFAULT_GRID_COLS
    
    def test_set_tag(self, widget):
        """Test setting tag."""
        widget.set_tag("cats")
        assert widget._tag == "cats"
    
    def test_set_custom_tag(self, widget):
        """Test setting custom tag."""
        widget.set_custom_tag("nature")
        assert widget._custom_tag == "nature"
    
    def test_set_grid_rows(self, widget):
        """Test setting grid rows."""
        widget.set_grid_rows(3)
        assert widget._grid_rows == 3
    
    def test_set_grid_rows_clamped(self, widget):
        """Test grid rows are clamped to valid range."""
        widget.set_grid_rows(100)
        assert widget._grid_rows <= 6
        
        widget.set_grid_rows(0)
        assert widget._grid_rows >= 1
    
    def test_set_grid_columns(self, widget):
        """Test setting grid columns."""
        widget.set_grid_columns(5)
        assert widget._grid_cols == 5
    
    def test_set_grid_columns_clamped(self, widget):
        """Test grid columns are clamped to valid range."""
        widget.set_grid_columns(100)
        assert widget._grid_cols <= 8
        
        widget.set_grid_columns(0)
        assert widget._grid_cols >= 1
    
    def test_set_layout_mode(self, widget):
        """Test setting layout mode."""
        widget.set_layout_mode("square")
        assert widget._layout_mode == LayoutMode.SQUARE
        
        widget.set_layout_mode("vertical")
        assert widget._layout_mode == LayoutMode.VERTICAL
    
    def test_set_layout_mode_invalid(self, widget):
        """Test invalid layout mode is ignored."""
        original = widget._layout_mode
        widget.set_layout_mode("invalid_mode")
        assert widget._layout_mode == original
    
    def test_set_image_spacing(self, widget):
        """Test setting image spacing."""
        widget.set_image_spacing(10)
        assert widget._image_spacing == 10
    
    def test_set_image_spacing_clamped(self, widget):
        """Test image spacing is clamped."""
        widget.set_image_spacing(-5)
        assert widget._image_spacing >= 0
        
        widget.set_image_spacing(100)
        assert widget._image_spacing <= 20
    
    def test_set_update_interval(self, widget):
        """Test setting update interval."""
        widget.set_update_interval(900)  # 15 minutes
        assert widget._update_interval_sec == 900
    
    def test_set_update_interval_clamped(self, widget):
        """Test update interval is clamped."""
        widget.set_update_interval(60)  # Too short
        assert widget._update_interval_sec >= 300
        
        widget.set_update_interval(9999)  # Too long
        assert widget._update_interval_sec <= 3600
    
    def test_set_show_header(self, widget):
        """Test setting header visibility."""
        widget.set_show_header(False)
        assert not widget._show_header
        
        widget.set_show_header(True)
        assert widget._show_header
    
    def test_set_image_border_enabled(self, widget):
        """Test setting image border enabled."""
        widget.set_image_border_enabled(False)
        assert not widget._image_border_enabled
    
    def test_set_image_border_width(self, widget):
        """Test setting image border width."""
        widget.set_image_border_width(3)
        assert widget._image_border_width == 3
    
    def test_set_image_border_color(self, widget):
        """Test setting image border color."""
        color = QColor(255, 0, 0)
        widget.set_image_border_color(color)
        assert widget._image_border_color == color
    
    def test_set_image_border_radius(self, widget):
        """Test setting image border radius."""
        widget.set_image_border_radius(8)
        assert widget._image_border_radius == 8
    
    def test_set_click_opens_browser(self, widget):
        """Test setting click behavior."""
        widget.set_click_opens_browser(False)
        assert not widget._click_opens_browser
    
    def test_get_cell_hit_rects(self, widget):
        """Test getting cell hit rectangles."""
        rects = widget.get_cell_hit_rects()
        assert isinstance(rects, list)
    
    def test_get_header_hit_rect(self, widget):
        """Test getting header hit rectangle."""
        # Initially may be None until painted
        widget.get_header_hit_rect()
        # Just verify it doesn't crash


class TestImgurWidgetLifecycle:
    """Tests for widget lifecycle methods."""
    
    @pytest.fixture
    def widget(self, qapp):
        """Create a test widget."""
        widget = ImgurWidget()
        yield widget
        try:
            widget.deleteLater()
        except Exception:
            pass
    
    def test_initialize_creates_components(self, widget):
        """Test that initialize creates scraper and cache."""
        widget._initialize_impl()
        
        assert widget._scraper is not None
        assert widget._image_cache is not None
    
    def test_cleanup_clears_state(self, widget):
        """Test that cleanup clears state."""
        widget._initialize_impl()
        widget._images = [MagicMock()]
        
        widget._cleanup_impl()
        
        assert len(widget._images) == 0


class TestImgurWidgetClickHandling:
    """Tests for click handling."""
    
    @pytest.fixture
    def widget(self, qapp):
        """Create a test widget with cells."""
        widget = ImgurWidget()
        widget._cell_hit_rects = [
            (QRect(0, 50, 100, 100), "https://imgur.com/gallery/abc"),
            (QRect(110, 50, 100, 100), "https://imgur.com/gallery/def"),
        ]
        widget._header_hit_rect = QRect(0, 0, 200, 40)
        yield widget
        try:
            widget.deleteLater()
        except Exception:
            pass
    
    def test_handle_click_on_cell(self, widget):
        """Test clicking on an image cell."""
        widget._click_opens_browser = True
        
        # Click inside first cell
        result = widget.handle_click(QPoint(50, 100))
        
        assert result == "https://imgur.com/gallery/abc"
    
    def test_handle_click_on_header(self, widget):
        """Test clicking on header."""
        widget._click_opens_browser = True
        widget._tag = "cats"
        
        # Click inside header
        result = widget.handle_click(QPoint(100, 20))
        
        assert isinstance(result, str)
        assert "cats" in result
    
    def test_handle_click_disabled(self, widget):
        """Test that clicks are ignored when disabled."""
        widget._click_opens_browser = False
        
        result = widget.handle_click(QPoint(50, 100))
        
        assert not result
    
    def test_handle_click_outside(self, widget):
        """Test clicking outside all elements."""
        widget._click_opens_browser = True
        
        # Click outside all cells and header
        result = widget.handle_click(QPoint(500, 500))
        
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
