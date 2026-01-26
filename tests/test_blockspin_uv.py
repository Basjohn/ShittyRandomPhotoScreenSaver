"""Test BlockSpin UV mapping for all 6 directions.

This test creates a labeled test image and verifies that each BlockSpin direction
shows the correct image orientation at the end of the transition.
"""
import sys
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from transitions.slide_transition import SlideDirection
from transitions.gl_compositor_blockspin_transition import GLCompositorBlockSpinTransition
from rendering.gl_compositor import GLCompositorWidget


def create_test_image(label: str, width: int = 800, height: int = 600) -> QPixmap:
    """Create a test image with clear orientation markers."""
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(40, 40, 40))
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw label in center
    font = QFont("Arial", 72, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, label)
    
    # Draw orientation markers
    # TOP marker (red)
    painter.setPen(QColor(255, 0, 0))
    font.setPointSize(36)
    painter.setFont(font)
    painter.drawText(width // 2 - 50, 50, "TOP")
    
    # BOTTOM marker (green)
    painter.setPen(QColor(0, 255, 0))
    painter.drawText(width // 2 - 80, height - 20, "BOTTOM")
    
    # LEFT marker (blue)
    painter.setPen(QColor(0, 0, 255))
    painter.drawText(20, height // 2, "LEFT")
    
    # RIGHT marker (yellow)
    painter.setPen(QColor(255, 255, 0))
    painter.drawText(width - 100, height // 2, "RIGHT")
    
    painter.end()
    return pixmap


class TestWindow(QLabel):
    """Test window for BlockSpin transitions."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BlockSpin UV Test")
        self.resize(800, 600)
        
        # Create GL compositor
        self._gl_compositor = GLCompositorWidget(self)
        self._gl_compositor.setGeometry(0, 0, 800, 600)
        self._gl_compositor.show()
        
        # Test directions
        self.directions = [
            (SlideDirection.LEFT, "LEFT"),
            (SlideDirection.RIGHT, "RIGHT"),
            (SlideDirection.UP, "UP"),
            (SlideDirection.DOWN, "DOWN"),
            (SlideDirection.DIAG_TL_BR, "DIAG_TL_BR"),
            (SlideDirection.DIAG_TR_BL, "DIAG_TR_BL"),
        ]
        self.current_test = 0
        
        # Create test images
        self.old_image = create_test_image("OLD IMAGE")
        self.new_image = create_test_image("NEW IMAGE")
        
        # Show initial image
        self.setPixmap(self.old_image)
        
        # Start first test after 1 second
        QTimer.singleShot(1000, self.run_next_test)
    
    def run_next_test(self):
        """Run the next direction test."""
        if self.current_test >= len(self.directions):
            print("\n=== ALL TESTS COMPLETE ===")
            print("Review the final image on screen.")
            print("It should show 'NEW IMAGE' with correct orientation:")
            print("  - TOP marker at top (red)")
            print("  - BOTTOM marker at bottom (green)")
            print("  - LEFT marker at left (blue)")
            print("  - RIGHT marker at right (yellow)")
            return
        
        direction, name = self.directions[self.current_test]
        print(f"\n=== Testing {name} ===")
        print(f"Direction: {direction}")
        print(f"Expected: NEW IMAGE with correct orientation")
        
        # Create and start transition
        transition = GLCompositorBlockSpinTransition(
            duration_ms=3000,
            easing="Linear",
            direction=direction
        )
        
        # Connect finished signal
        transition.finished.connect(self.on_transition_finished)
        
        # Start transition
        transition.start(self.old_image, self.new_image, self)
        
    def on_transition_finished(self):
        """Called when transition finishes."""
        direction, name = self.directions[self.current_test]
        print(f"✓ {name} transition finished")
        print(f"  Check if image shows 'NEW IMAGE' with correct orientation")
        
        # Update display to show new image
        self.setPixmap(self.new_image)
        
        # Move to next test after 2 seconds
        self.current_test += 1
        QTimer.singleShot(2000, self.run_next_test)


def main():
    """Run the test."""
    app = QApplication(sys.argv)
    
    print("=== BlockSpin UV Mapping Test ===")
    print("This test will cycle through all 6 BlockSpin directions.")
    print("After each transition, verify that:")
    print("  1. The final image shows 'NEW IMAGE' (not 'OLD IMAGE')")
    print("  2. TOP marker is at the top (red)")
    print("  3. BOTTOM marker is at the bottom (green)")
    print("  4. LEFT marker is at the left (blue)")
    print("  5. RIGHT marker is at the right (yellow)")
    print("\nPress Ctrl+C to exit\n")
    
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
