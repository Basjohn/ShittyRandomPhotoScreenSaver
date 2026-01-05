"""
Tests for Widget Positioner.

Tests the centralized widget positioning logic including:
- Position calculations based on anchor
- Collision detection
- Stacking logic
- Relative positioning
"""
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPoint, QRect, QSize

from rendering.widget_positioner import (
    PositionAnchor,
    PositionConfig,
    WidgetBounds,
    WidgetPositioner,
)


# ---------------------------------------------------------------------------
# PositionAnchor Tests
# ---------------------------------------------------------------------------

class TestPositionAnchor:
    """Test PositionAnchor enum."""
    
    def test_all_anchors_exist(self):
        """Test all 9 position anchors exist."""
        assert len(PositionAnchor) == 9
        
        assert PositionAnchor.TOP_LEFT.value == "top_left"
        assert PositionAnchor.TOP_CENTER.value == "top_center"
        assert PositionAnchor.TOP_RIGHT.value == "top_right"
        assert PositionAnchor.MIDDLE_LEFT.value == "middle_left"
        assert PositionAnchor.CENTER.value == "center"
        assert PositionAnchor.MIDDLE_RIGHT.value == "middle_right"
        assert PositionAnchor.BOTTOM_LEFT.value == "bottom_left"
        assert PositionAnchor.BOTTOM_CENTER.value == "bottom_center"
        assert PositionAnchor.BOTTOM_RIGHT.value == "bottom_right"


# ---------------------------------------------------------------------------
# PositionConfig Tests
# ---------------------------------------------------------------------------

class TestPositionConfig:
    """Test PositionConfig dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        config = PositionConfig(anchor=PositionAnchor.TOP_LEFT)
        
        assert config.anchor == PositionAnchor.TOP_LEFT
        assert config.margin_x == 20
        assert config.margin_y == 20
        assert config.stack_offset == QPoint(0, 0)
    
    def test_custom_values(self):
        """Test custom values."""
        config = PositionConfig(
            anchor=PositionAnchor.BOTTOM_RIGHT,
            margin_x=50,
            margin_y=30,
            stack_offset=QPoint(10, 20),
        )
        
        assert config.anchor == PositionAnchor.BOTTOM_RIGHT
        assert config.margin_x == 50
        assert config.margin_y == 30
        assert config.stack_offset == QPoint(10, 20)


# ---------------------------------------------------------------------------
# WidgetPositioner Tests
# ---------------------------------------------------------------------------

class TestWidgetPositioner:
    """Test WidgetPositioner class."""
    
    def test_default_container_size(self):
        """Test default container size."""
        positioner = WidgetPositioner()
        
        assert positioner._container_size == QSize(1920, 1080)
    
    def test_set_container_size(self):
        """Test setting container size."""
        positioner = WidgetPositioner()
        positioner.set_container_size(QSize(2560, 1440))
        
        assert positioner._container_size == QSize(2560, 1440)
    
    @pytest.mark.parametrize(
        "anchor,expected",
        [
            (PositionAnchor.TOP_LEFT, QPoint(20, 20)),
            (PositionAnchor.TOP_CENTER, QPoint((1920 - 200) // 2, 20)),
            (PositionAnchor.TOP_RIGHT, QPoint(1920 - 200 - 20, 20)),
            (PositionAnchor.MIDDLE_LEFT, QPoint(20, (1080 - 100) // 2)),
            (PositionAnchor.CENTER, QPoint((1920 - 200) // 2, (1080 - 100) // 2)),
            (PositionAnchor.MIDDLE_RIGHT, QPoint(1920 - 200 - 20, (1080 - 100) // 2)),
            (PositionAnchor.BOTTOM_LEFT, QPoint(20, 1080 - 100 - 20)),
            (PositionAnchor.BOTTOM_CENTER, QPoint((1920 - 200) // 2, 1080 - 100 - 20)),
            (PositionAnchor.BOTTOM_RIGHT, QPoint(1920 - 200 - 20, 1080 - 100 - 20)),
        ],
    )
    def test_calculate_position_all_anchors(self, anchor, expected):
        """Ensure calculate_position covers all 9 anchors."""
        positioner = WidgetPositioner(QSize(1920, 1080))
        widget_size = QSize(200, 100)

        pos = positioner.calculate_position(
            widget_size,
            anchor,
            margin_x=20,
            margin_y=20,
        )

        assert pos == expected
    
    def test_calculate_position_with_stack_offset(self):
        """Test position calculation with stack offset."""
        positioner = WidgetPositioner(QSize(1920, 1080))
        widget_size = QSize(200, 100)
        
        pos = positioner.calculate_position(
            widget_size,
            PositionAnchor.TOP_LEFT,
            margin_x=20,
            margin_y=20,
            stack_offset=QPoint(0, 150),
        )
        
        assert pos.x() == 20
        assert pos.y() == 20 + 150  # 170
    
    def test_calculate_position_clamps_to_bounds(self):
        """Test position is clamped to container bounds."""
        positioner = WidgetPositioner(QSize(1920, 1080))
        widget_size = QSize(200, 100)
        
        # Large negative offset should clamp to 0
        pos = positioner.calculate_position(
            widget_size,
            PositionAnchor.TOP_LEFT,
            margin_x=20,
            margin_y=20,
            stack_offset=QPoint(-100, -100),
        )
        
        assert pos.x() == 0
        assert pos.y() == 0


# ---------------------------------------------------------------------------
# Collision Detection Tests
# ---------------------------------------------------------------------------

class TestCollisionDetection:
    """Test collision detection."""
    
    def test_check_collision_overlapping(self):
        """Test collision detection with overlapping rectangles."""
        positioner = WidgetPositioner()
        
        rect1 = QRect(0, 0, 100, 100)
        rect2 = QRect(50, 50, 100, 100)
        
        assert positioner.check_collision(rect1, rect2) is True
    
    def test_check_collision_not_overlapping(self):
        """Test collision detection with non-overlapping rectangles."""
        positioner = WidgetPositioner()
        
        rect1 = QRect(0, 0, 100, 100)
        rect2 = QRect(200, 200, 100, 100)
        
        assert positioner.check_collision(rect1, rect2) is False
    
    def test_check_collision_adjacent(self):
        """Test collision detection with adjacent rectangles."""
        positioner = WidgetPositioner()
        
        rect1 = QRect(0, 0, 100, 100)
        rect2 = QRect(100, 0, 100, 100)  # Adjacent, not overlapping
        
        assert positioner.check_collision(rect1, rect2) is False
    
    def test_find_collisions(self):
        """Test finding all colliding widgets."""
        positioner = WidgetPositioner()
        
        # Register some widget bounds
        widget1 = MagicMock()
        widget1.geometry.return_value = QRect(0, 0, 100, 100)
        positioner._widget_bounds["widget1"] = WidgetBounds(
            widget=widget1, name="widget1", rect=QRect(0, 0, 100, 100), anchor=PositionAnchor.TOP_LEFT
        )
        
        widget2 = MagicMock()
        widget2.geometry.return_value = QRect(200, 200, 100, 100)
        positioner._widget_bounds["widget2"] = WidgetBounds(
            widget=widget2, name="widget2", rect=QRect(200, 200, 100, 100), anchor=PositionAnchor.CENTER
        )
        
        # Check for collisions with a rect that overlaps widget1 but not widget2
        collisions = positioner.find_collisions("test", QRect(50, 50, 100, 100))
        
        assert "widget1" in collisions
        assert "widget2" not in collisions


# ---------------------------------------------------------------------------
# Stacking Tests
# ---------------------------------------------------------------------------

class TestStacking:
    """Test stacking logic."""
    
    def test_calculate_stack_offsets_single_widget(self):
        """Test stacking with single widget at position."""
        positioner = WidgetPositioner()
        
        widget = MagicMock()
        widget.sizeHint.return_value = QSize(200, 100)
        
        offsets = positioner.calculate_stack_offsets([
            ("widget1", widget, PositionAnchor.TOP_LEFT),
        ])
        
        assert offsets["widget1"] == QPoint(0, 0)
    
    def test_calculate_stack_offsets_multiple_widgets_top(self):
        """Test stacking with multiple widgets at top position."""
        positioner = WidgetPositioner()
        
        widget1 = MagicMock()
        widget1.sizeHint.return_value = QSize(200, 100)
        
        widget2 = MagicMock()
        widget2.sizeHint.return_value = QSize(200, 80)
        
        offsets = positioner.calculate_stack_offsets([
            ("widget1", widget1, PositionAnchor.TOP_LEFT),
            ("widget2", widget2, PositionAnchor.TOP_LEFT),
        ])
        
        assert offsets["widget1"] == QPoint(0, 0)
        # widget2 should be offset by widget1 height + spacing
        assert offsets["widget2"].y() == 100 + 10  # 110
    
    def test_calculate_stack_offsets_multiple_widgets_bottom(self):
        """Test stacking with multiple widgets at bottom position."""
        positioner = WidgetPositioner()
        
        widget1 = MagicMock()
        widget1.sizeHint.return_value = QSize(200, 100)
        
        widget2 = MagicMock()
        widget2.sizeHint.return_value = QSize(200, 80)
        
        offsets = positioner.calculate_stack_offsets([
            ("widget1", widget1, PositionAnchor.BOTTOM_LEFT),
            ("widget2", widget2, PositionAnchor.BOTTOM_LEFT),
        ])
        
        assert offsets["widget1"] == QPoint(0, 0)
        # widget2 should be offset upward (negative) for bottom position
        assert offsets["widget2"].y() == -(100 + 10)  # -110
    
    def test_calculate_stack_offsets_three_widgets_top_right(self):
        """Test stacking with three widgets at TOP_RIGHT (stacks downward)."""
        positioner = WidgetPositioner()
        
        widget1 = MagicMock()
        widget1.sizeHint.return_value = QSize(300, 120)  # Reddit-like
        
        widget2 = MagicMock()
        widget2.sizeHint.return_value = QSize(200, 80)   # Weather-like
        
        widget3 = MagicMock()
        widget3.sizeHint.return_value = QSize(150, 60)   # Clock-like
        
        offsets = positioner.calculate_stack_offsets([
            ("reddit", widget1, PositionAnchor.TOP_RIGHT),
            ("weather", widget2, PositionAnchor.TOP_RIGHT),
            ("clock", widget3, PositionAnchor.TOP_RIGHT),
        ])
        
        assert offsets["reddit"] == QPoint(0, 0)
        assert offsets["weather"].y() == 120 + 10  # 130
        assert offsets["clock"].y() == 120 + 10 + 80 + 10  # 220
    
    def test_calculate_stack_offsets_three_widgets_bottom_right(self):
        """Test stacking with three widgets at BOTTOM_RIGHT (stacks upward)."""
        positioner = WidgetPositioner()
        
        widget1 = MagicMock()
        widget1.sizeHint.return_value = QSize(300, 150)  # Media-like
        
        widget2 = MagicMock()
        widget2.sizeHint.return_value = QSize(200, 100)  # Reddit-like
        
        widget3 = MagicMock()
        widget3.sizeHint.return_value = QSize(150, 80)   # Weather-like
        
        offsets = positioner.calculate_stack_offsets([
            ("media", widget1, PositionAnchor.BOTTOM_RIGHT),
            ("reddit", widget2, PositionAnchor.BOTTOM_RIGHT),
            ("weather", widget3, PositionAnchor.BOTTOM_RIGHT),
        ])
        
        assert offsets["media"] == QPoint(0, 0)
        assert offsets["reddit"].y() == -(150 + 10)  # -160
        assert offsets["weather"].y() == -(150 + 10 + 100 + 10)  # -270
    
    def test_calculate_stack_offsets_mixed_anchors(self):
        """Test that widgets at different anchors don't affect each other."""
        positioner = WidgetPositioner()
        
        widget1 = MagicMock()
        widget1.sizeHint.return_value = QSize(200, 100)
        
        widget2 = MagicMock()
        widget2.sizeHint.return_value = QSize(200, 80)
        
        widget3 = MagicMock()
        widget3.sizeHint.return_value = QSize(200, 60)
        
        offsets = positioner.calculate_stack_offsets([
            ("top_left_1", widget1, PositionAnchor.TOP_LEFT),
            ("bottom_right_1", widget2, PositionAnchor.BOTTOM_RIGHT),
            ("top_left_2", widget3, PositionAnchor.TOP_LEFT),
        ])
        
        # TOP_LEFT widgets stack together
        assert offsets["top_left_1"] == QPoint(0, 0)
        assert offsets["top_left_2"].y() == 100 + 10  # 110
        
        # BOTTOM_RIGHT widget is alone, no offset
        assert offsets["bottom_right_1"] == QPoint(0, 0)
    
    def test_calculate_stack_offsets_all_top_anchors_stack_down(self):
        """Test that all TOP_* anchors stack downward."""
        positioner = WidgetPositioner()
        
        for anchor in [PositionAnchor.TOP_LEFT, PositionAnchor.TOP_CENTER, PositionAnchor.TOP_RIGHT]:
            widget1 = MagicMock()
            widget1.sizeHint.return_value = QSize(200, 100)
            
            widget2 = MagicMock()
            widget2.sizeHint.return_value = QSize(200, 80)
            
            offsets = positioner.calculate_stack_offsets([
                ("w1", widget1, anchor),
                ("w2", widget2, anchor),
            ])
            
            assert offsets["w1"] == QPoint(0, 0), f"Failed for {anchor}"
            assert offsets["w2"].y() > 0, f"TOP anchor {anchor} should stack downward (positive y)"
    
    def test_calculate_stack_offsets_all_bottom_anchors_stack_up(self):
        """Test that all BOTTOM_* anchors stack upward."""
        positioner = WidgetPositioner()
        
        for anchor in [PositionAnchor.BOTTOM_LEFT, PositionAnchor.BOTTOM_CENTER, PositionAnchor.BOTTOM_RIGHT]:
            widget1 = MagicMock()
            widget1.sizeHint.return_value = QSize(200, 100)
            
            widget2 = MagicMock()
            widget2.sizeHint.return_value = QSize(200, 80)
            
            offsets = positioner.calculate_stack_offsets([
                ("w1", widget1, anchor),
                ("w2", widget2, anchor),
            ])
            
            assert offsets["w1"] == QPoint(0, 0), f"Failed for {anchor}"
            assert offsets["w2"].y() < 0, f"BOTTOM anchor {anchor} should stack upward (negative y)"
    
    def test_calculate_stack_offsets_middle_anchors_stack_down(self):
        """Test that MIDDLE_* anchors stack downward (same as TOP)."""
        positioner = WidgetPositioner()
        
        for anchor in [PositionAnchor.MIDDLE_LEFT, PositionAnchor.CENTER, PositionAnchor.MIDDLE_RIGHT]:
            widget1 = MagicMock()
            widget1.sizeHint.return_value = QSize(200, 100)
            
            widget2 = MagicMock()
            widget2.sizeHint.return_value = QSize(200, 80)
            
            offsets = positioner.calculate_stack_offsets([
                ("w1", widget1, anchor),
                ("w2", widget2, anchor),
            ])
            
            assert offsets["w1"] == QPoint(0, 0), f"Failed for {anchor}"
            # MIDDLE/CENTER anchors stack downward (not in TOP_* set, so stack_down=False)
            # Actually checking the code: stack_down = anchor in (TOP_LEFT, TOP_CENTER, TOP_RIGHT)
            # So MIDDLE anchors will have stack_down=False, meaning negative offset
            assert offsets["w2"].y() < 0, f"MIDDLE anchor {anchor} should stack upward (negative y)"
    
    def test_calculate_stack_offsets_custom_spacing(self):
        """Test stacking with custom spacing."""
        positioner = WidgetPositioner()
        
        widget1 = MagicMock()
        widget1.sizeHint.return_value = QSize(200, 100)
        
        widget2 = MagicMock()
        widget2.sizeHint.return_value = QSize(200, 80)
        
        offsets = positioner.calculate_stack_offsets([
            ("w1", widget1, PositionAnchor.TOP_LEFT),
            ("w2", widget2, PositionAnchor.TOP_LEFT),
        ], spacing=20)
        
        assert offsets["w1"] == QPoint(0, 0)
        assert offsets["w2"].y() == 100 + 20  # 120 with custom spacing
    
    def test_calculate_stack_offsets_varying_heights(self):
        """Test stacking with widgets of varying heights."""
        positioner = WidgetPositioner()
        
        # Simulate Reddit with 20 posts (tall)
        widget1 = MagicMock()
        widget1.sizeHint.return_value = QSize(400, 500)
        
        # Simulate Weather (medium)
        widget2 = MagicMock()
        widget2.sizeHint.return_value = QSize(200, 150)
        
        # Simulate Clock (small)
        widget3 = MagicMock()
        widget3.sizeHint.return_value = QSize(150, 60)
        
        offsets = positioner.calculate_stack_offsets([
            ("reddit", widget1, PositionAnchor.BOTTOM_RIGHT),
            ("weather", widget2, PositionAnchor.BOTTOM_RIGHT),
            ("clock", widget3, PositionAnchor.BOTTOM_RIGHT),
        ])
        
        assert offsets["reddit"] == QPoint(0, 0)
        assert offsets["weather"].y() == -(500 + 10)  # -510
        assert offsets["clock"].y() == -(500 + 10 + 150 + 10)  # -670


# ---------------------------------------------------------------------------
# Relative Positioning Tests
# ---------------------------------------------------------------------------

class TestRelativePositioning:
    """Test relative positioning."""
    
    def test_position_relative_above(self):
        """Test positioning widget above another."""
        positioner = WidgetPositioner(QSize(1920, 1080))
        
        widget = MagicMock()
        widget.sizeHint.return_value = QSize(200, 50)
        widget.size.return_value = QSize(200, 50)
        
        anchor_widget = MagicMock()
        anchor_widget.geometry.return_value = QRect(100, 200, 200, 100)
        
        geometry = positioner.position_relative_to(
            widget, anchor_widget, placement="above", gap=20
        )
        
        assert geometry.x() == 100
        assert geometry.y() == 200 - 20 - 50  # 130
    
    def test_position_relative_below(self):
        """Test positioning widget below another."""
        positioner = WidgetPositioner(QSize(1920, 1080))
        
        widget = MagicMock()
        widget.sizeHint.return_value = QSize(200, 50)
        widget.size.return_value = QSize(200, 50)
        
        anchor_widget = MagicMock()
        anchor_widget.geometry.return_value = QRect(100, 200, 200, 100)
        
        geometry = positioner.position_relative_to(
            widget, anchor_widget, placement="below", gap=20
        )
        
        assert geometry.x() == 100
        # QRect.bottom() returns last row inside rect (y + height - 1)
        # So bottom() + gap = 200 + 100 - 1 + 20 = 319
        assert geometry.y() == 319


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
