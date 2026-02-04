"""Standalone test for weather widget detail row rendering.

This module can be run directly to verify the detail row layout and icon scaling
without needing the full screensaver application.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QFontMetrics, QColor, QPixmap, QPainter

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestDetailIcon(QWidget):
    """Test detail icon with proper scaling."""
    
    def __init__(self, size_px: int, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._size_px = size_px
        self._box = QSize(size_px + 6, size_px + 6)
        self.setFixedSize(self._box)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._vertical_inset = 3
        
    def set_pixmap(self, pixmap):
        self._pixmap = pixmap
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._pixmap is None or self._pixmap.isNull():
            painter.end()
            return
        target = self.rect().adjusted(3, self._vertical_inset, -3, -self._vertical_inset)
        # Scale and center like old code
        scaled = self._pixmap.scaled(
            target.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = target.x() + (target.width() - scaled.width()) // 2
        y = target.y() + (target.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()


class TestDetailRow(QWidget):
    """Test detail row matching old code approach."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._metrics = []
        self._font = QFont()
        self._text_color = QColor(255, 255, 255)
        self._icon_size = 16
        
        # Outer layout
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        
        # Segments layout with stretch
        self._segments_layout = QHBoxLayout()
        self._segments_layout.setContentsMargins(0, 0, 0, 0)
        self._segments_layout.setSpacing(12)
        self._segments_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._segments_layout.addStretch(1)
        
        outer.addLayout(self._segments_layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Segment pool
        self._segment_pool = {}
        
    def update_metrics(self, metrics, font, color, icon_size):
        """Update metrics like old code."""
        self._metrics = list(metrics)
        self._font = QFont(font)
        self._text_color = QColor(color)
        self._icon_size = max(18, int(icon_size))
        self._rebuild_segments()
        self.setVisible(bool(metrics))
        
    def _rebuild_segments(self):
        """Rebuild segments with pooling like old code."""
        has_metrics = bool(self._metrics)
        self._segments_layout.setContentsMargins(
            0, 6 if has_metrics else 0, 0, 4 if has_metrics else 0
        )
        self._segments_layout.setSpacing(
            max(12, self._icon_size // 2 + 4) if has_metrics else 0
        )
        
        active_keys = []
        for key, value in self._metrics:
            active_keys.append(key)
            segment = self._segment_pool.get(key)
            if segment is None:
                segment = self._create_segment()
                self._segment_pool[key] = segment
                # Insert before stretch
                insert_pos = max(0, self._segments_layout.count() - 1)
                self._segments_layout.insertWidget(insert_pos, segment['widget'])
            self._configure_segment(segment, key, value)
            segment['widget'].setVisible(True)
            
        # Hide inactive segments
        for key, segment in self._segment_pool.items():
            if key not in active_keys:
                segment['widget'].setVisible(False)
                
    def _create_segment(self):
        """Create a segment like old code."""
        segment_widget = QWidget(self)
        segment_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        segment_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(segment_widget)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        icon_label = TestDetailIcon(self._icon_size, segment_widget)
        text_label = QLabel(segment_widget)
        text_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        text_label.setWordWrap(False)
        text_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        text_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        
        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        
        return {
            'widget': segment_widget,
            'icon': icon_label,
            'text': text_label
        }
        
    def _configure_segment(self, segment, key, value):
        """Configure segment like old code."""
        segment['text'].setFont(self._font)
        segment['text'].setText(value)
        segment['text'].setStyleSheet(
            f"color: rgba({self._text_color.red()}, {self._text_color.green()}, "
            f"{self._text_color.blue()}, {self._text_color.alpha()});"
        )
        # Fixed height like old code
        fm = QFontMetrics(self._font)
        line_height = fm.height()
        height = max(self._icon_size + 10, line_height + 6)
        segment['widget'].setFixedHeight(height)


def load_test_pixmap(size):
    """Create a simple test pixmap."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QColor(200, 200, 200))
    painter.drawEllipse(2, 2, size-4, size-4)
    painter.end()
    return pixmap


def main():
    app = QApplication(sys.argv)
    
    # Main window
    window = QWidget()
    window.setWindowTitle("Weather Detail Row Test")
    window.resize(600, 200)
    window.setStyleSheet("background-color: #2d2d2d;")
    
    layout = QVBoxLayout(window)
    layout.setSpacing(20)
    
    # Title
    title = QLabel("Weather Detail Row Test")
    title.setStyleSheet("color: white; font-size: 18pt; font-weight: bold;")
    layout.addWidget(title)
    
    # Separator
    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setStyleSheet("background-color: rgba(255,255,255,0.3);")
    separator.setFixedHeight(1)
    layout.addWidget(separator)
    
    # Test row 1: All 3 metrics
    row1_label = QLabel("All 3 metrics (rain, humidity, wind):")
    row1_label.setStyleSheet("color: #aaa; font-size: 10pt;")
    layout.addWidget(row1_label)
    
    row1 = TestDetailRow()
    row1.setStyleSheet("background-color: rgba(255,255,255,0.05); border: 1px dashed rgba(255,255,255,0.2);")
    metrics1 = [
        ("rain", "45%"),
        ("humidity", "72%"),
        ("wind", "12.5 km/h")
    ]
    font = QFont("Segoe UI", 10)
    row1.update_metrics(metrics1, font, QColor(255, 255, 255), 24)
    layout.addWidget(row1)
    
    # Test row 2: Only 2 metrics (missing humidity)
    row2_label = QLabel("Only 2 metrics (simulating missing humidity):")
    row2_label.setStyleSheet("color: #aaa; font-size: 10pt;")
    layout.addWidget(row2_label)
    
    row2 = TestDetailRow()
    row2.setStyleSheet("background-color: rgba(255,255,255,0.05); border: 1px dashed rgba(255,255,255,0.2);")
    metrics2 = [
        ("rain", "45%"),
        ("wind", "12.5 km/h")
    ]
    row2.update_metrics(metrics2, font, QColor(255, 255, 255), 24)
    layout.addWidget(row2)
    
    # Test row 3: Large icons
    row3_label = QLabel("Large icons (36px):")
    row3_label.setStyleSheet("color: #aaa; font-size: 10pt;")
    layout.addWidget(row3_label)
    
    row3 = TestDetailRow()
    row3.setStyleSheet("background-color: rgba(255,255,255,0.05); border: 1px dashed rgba(255,255,255,0.2);")
    row3.update_metrics(metrics1, font, QColor(255, 255, 255), 36)
    layout.addWidget(row3)
    
    layout.addStretch()
    
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
