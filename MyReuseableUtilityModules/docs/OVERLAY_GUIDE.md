# Overlay UI Patterns Guide

This document explains how to create beautiful overlay windows using the framework's pre-styled components and patterns.

## Table of Contents

1. [What Are Overlays](#what-are-overlays)
2. [Basic Overlay Window](#basic-overlay-window)
3. [Overlay Styling](#overlay-styling)
4. [Advanced Patterns](#advanced-patterns)
5. [Real-World Examples](#real-world-examples)

---

## What Are Overlays

Overlays are frameless, transparent windows that float above other windows. Common use cases:

- **Window Thumbnails**: Display preview of another window
- **Screen Capture Previews**: Show captured screen regions
- **Floating Controls**: Media controls, volume sliders
- **Tooltips**: Rich, styled informational overlays
- **Notifications**: Toast messages and alerts
- **Picture-in-Picture**: Video or content overlays

The framework provides comprehensive overlay styling with:
- Transparent backgrounds
- Rounded borders with proper clipping
- Shadow effects
- Smooth opacity transitions
- High DPI support
- Multiple visual modes (regular, DWM-backed)

---

## Basic Overlay Window

### Minimal Overlay

```python
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout
from PySide6.QtCore import Qt

class BasicOverlay(QWidget):
    def __init__(self):
        super().__init__()
        
        # Make window frameless and transparent
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # Prevents taskbar entry
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Set object name for styling
        self.setObjectName("overlayHostWindow")
        
        # Create border frame
        self.border_frame = QFrame()
        self.border_frame.setObjectName("borderOverlay")
        
        # Create content frame
        self.content_frame = QFrame()
        self.content_frame.setObjectName("overlayBackdrop")
        
        # Layout
        border_layout = QVBoxLayout(self.border_frame)
        border_layout.setContentsMargins(0, 0, 0, 0)
        border_layout.addWidget(self.content_frame)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.border_frame)
        
        # Initial size and position
        self.resize(400, 300)
        
    def set_opacity(self, opacity: float):
        """Set window opacity (0.0 to 1.0)"""
        self.setWindowOpacity(opacity)

# Usage
overlay = BasicOverlay()
overlay.show()
```

### With Title Bar

```python
class TitledOverlay(QWidget):
    def __init__(self, title="Overlay"):
        super().__init__()
        
        # Frameless and transparent
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Main frame
        self.main_frame = QFrame()
        self.main_frame.setObjectName("main_frame")
        
        # Title bar
        self.title_bar = QFrame()
        self.title_bar.setObjectName("titleBar")
        
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(12, 0, 6, 0)
        
        # Title label
        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleLabel")
        title_layout.addWidget(self.title_label)
        
        title_layout.addStretch()
        
        # Close button
        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("closeButton")
        self.close_button.clicked.connect(self.close)
        title_layout.addWidget(self.close_button)
        
        # Content area
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        
        # Main layout
        main_layout = QVBoxLayout(self.main_frame)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(self.content_frame)
        
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.main_frame)
        
        self.resize(400, 300)
        
        # Enable dragging
        self._dragging = False
        self._drag_pos = None
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Check if click is in title bar
            if self.title_bar.geometry().contains(event.pos()):
                self._dragging = True
                self._drag_pos = event.globalPos() - self.pos()
                event.accept()
    
    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            event.accept()

# Usage
overlay = TitledOverlay("My Overlay")
overlay.content_layout.addWidget(QLabel("Content goes here"))
overlay.show()
```

---

## Overlay Styling

### Theme Integration

The themes provide several object names for overlay components:

#### Standard Overlay Frame

```python
# Border frame with 5px border
border_frame = QFrame()
border_frame.setObjectName("borderOverlay")

# Backdrop (content background)
backdrop = QFrame()
backdrop.setObjectName("overlayBackdrop")
```

**QSS Styling (Dark Theme)**:
```css
QFrame#borderOverlay {
    background-color: rgba(43, 43, 43, 0.8);
    border: 5px solid rgba(255, 255, 255, 1.0);
    border-radius: 6px;
}

QFrame#overlayBackdrop {
    background-color: rgba(43, 43, 43, 1.0);
    border: none;
    border-radius: 1px;
}
```

#### DWM Mode (Hardware-Accelerated)

For overlays that show window thumbnails using DWM (Desktop Window Manager):

```python
# Set dynamic property for DWM mode
border_frame.setProperty("dwm", True)
border_frame.style().unpolish(border_frame)
border_frame.style().polish(border_frame)
```

**QSS Styling**:
```css
QFrame#borderOverlay[dwm="true"] {
    background-color: transparent;
    border: 5px solid rgba(255, 255, 255, 1.0);
    border-radius: 6px;
}

QFrame#overlayBackdrop[dwm="true"] {
    background-color: rgba(0, 0, 0, 0);
    border: none;
}
```

### Opacity Control

```python
class FadingOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self._target_opacity = 0.95
        self._current_opacity = 0.0
        
        # Animation timer
        self.fade_timer = QTimer()
        self.fade_timer.timeout.connect(self._update_fade)
        
    def fade_in(self, duration_ms=300):
        """Fade in over duration"""
        self._target_opacity = 0.95
        self._fade_step = 0.05  # 5% per step
        self._fade_interval = duration_ms // (0.95 / 0.05)
        self.fade_timer.start(int(self._fade_interval))
    
    def fade_out(self, duration_ms=300):
        """Fade out over duration"""
        self._target_opacity = 0.0
        self._fade_step = -0.05
        self._fade_interval = duration_ms // (0.95 / 0.05)
        self.fade_timer.start(int(self._fade_interval))
    
    def _update_fade(self):
        self._current_opacity += self._fade_step
        
        # Clamp
        if self._fade_step > 0:
            self._current_opacity = min(self._current_opacity, self._target_opacity)
        else:
            self._current_opacity = max(self._current_opacity, self._target_opacity)
        
        self.setWindowOpacity(self._current_opacity)
        
        # Stop when reached
        if self._current_opacity == self._target_opacity:
            self.fade_timer.stop()
            
            # Close if faded out
            if self._current_opacity == 0.0:
                self.close()

# Usage
overlay = FadingOverlay()
overlay.show()
overlay.fade_in()
```

### Shadow Effects

```python
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtGui import QColor

def add_shadow(widget, blur_radius=20, color=QColor(0, 0, 0, 160)):
    """Add drop shadow to widget"""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur_radius)
    shadow.setColor(color)
    shadow.setOffset(0, 4)  # Slight downward offset
    widget.setGraphicsEffect(shadow)

# Usage
overlay = BasicOverlay()
add_shadow(overlay.border_frame)
```

---

## Advanced Patterns

### Resizable Overlay

```python
class ResizableOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._resize_margin = 10
        self._resizing = False
        self._resize_direction = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        
        # Setup UI...
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            direction = self._get_resize_direction(event.pos())
            if direction:
                self._resizing = True
                self._resize_direction = direction
                self._resize_start_pos = event.globalPos()
                self._resize_start_geometry = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self._resizing:
            self._handle_resize(event.globalPos())
            event.accept()
            return
        
        # Update cursor based on position
        direction = self._get_resize_direction(event.pos())
        if direction:
            self._set_resize_cursor(direction)
        else:
            self.unsetCursor()
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._resizing:
            self._resizing = False
            self._resize_direction = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)
    
    def _get_resize_direction(self, pos):
        """Determine resize direction from mouse position"""
        rect = self.rect()
        margin = self._resize_margin
        
        left = pos.x() < margin
        right = pos.x() > rect.width() - margin
        top = pos.y() < margin
        bottom = pos.y() > rect.height() - margin
        
        if left and top:
            return "top-left"
        elif right and top:
            return "top-right"
        elif left and bottom:
            return "bottom-left"
        elif right and bottom:
            return "bottom-right"
        elif left:
            return "left"
        elif right:
            return "right"
        elif top:
            return "top"
        elif bottom:
            return "bottom"
        return None
    
    def _set_resize_cursor(self, direction):
        """Set cursor for resize direction"""
        cursors = {
            "top-left": Qt.SizeFDiagCursor,
            "top-right": Qt.SizeBDiagCursor,
            "bottom-left": Qt.SizeBDiagCursor,
            "bottom-right": Qt.SizeFDiagCursor,
            "left": Qt.SizeHorCursor,
            "right": Qt.SizeHorCursor,
            "top": Qt.SizeVerCursor,
            "bottom": Qt.SizeVerCursor,
        }
        self.setCursor(cursors.get(direction, Qt.ArrowCursor))
    
    def _handle_resize(self, global_pos):
        """Handle window resize"""
        delta = global_pos - self._resize_start_pos
        geo = self._resize_start_geometry
        
        x, y, w, h = geo.x(), geo.y(), geo.width(), geo.height()
        
        direction = self._resize_direction
        
        if "left" in direction:
            x += delta.x()
            w -= delta.x()
        if "right" in direction:
            w += delta.x()
        if "top" in direction:
            y += delta.y()
            h -= delta.y()
        if "bottom" in direction:
            h += delta.y()
        
        # Apply minimum size
        w = max(w, 200)
        h = max(h, 150)
        
        self.setGeometry(x, y, w, h)
```

### Aspect Ratio Locked Overlay

```python
class AspectRatioOverlay(ResizableOverlay):
    def __init__(self, aspect_ratio=16/9):
        super().__init__()
        self.aspect_ratio = aspect_ratio
    
    def _handle_resize(self, global_pos):
        """Handle resize with aspect ratio lock"""
        delta = global_pos - self._resize_start_pos
        geo = self._resize_start_geometry
        
        x, y, w, h = geo.x(), geo.y(), geo.width(), geo.height()
        
        direction = self._resize_direction
        
        # Calculate new dimensions
        if "right" in direction or "left" in direction:
            # Width-driven
            if "right" in direction:
                w += delta.x()
            else:
                x += delta.x()
                w -= delta.x()
            h = int(w / self.aspect_ratio)
        else:
            # Height-driven
            if "bottom" in direction:
                h += delta.y()
            else:
                y += delta.y()
                h -= delta.y()
            w = int(h * self.aspect_ratio)
        
        # Apply minimum size
        if w < 200:
            w = 200
            h = int(w / self.aspect_ratio)
        if h < 150:
            h = 150
            w = int(h * self.aspect_ratio)
        
        self.setGeometry(x, y, w, h)
```

### Context Menu Overlay

```python
class ContextMenuOverlay(BasicOverlay):
    def __init__(self):
        super().__init__()
        
        # Create context menu
        self.context_menu = QMenu(self)
        self.context_menu.setObjectName("overlayContextMenu")
        
        # Add actions
        self.context_menu.addAction("Minimize", self.showMinimized)
        self.context_menu.addAction("Maximize", self.toggle_maximize)
        self.context_menu.addSeparator()
        
        opacity_menu = self.context_menu.addMenu("Opacity")
        for opacity in [0.3, 0.5, 0.7, 0.9, 1.0]:
            action = opacity_menu.addAction(f"{int(opacity * 100)}%")
            action.triggered.connect(lambda checked, o=opacity: self.setWindowOpacity(o))
        
        self.context_menu.addSeparator()
        self.context_menu.addAction("Close", self.close)
    
    def contextMenuEvent(self, event):
        """Show context menu on right-click"""
        self.context_menu.exec(event.globalPos())
    
    def toggle_maximize(self):
        """Toggle between normal and maximized"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
```

---

## Real-World Examples

### Toast Notification Overlay

```python
class ToastOverlay(QWidget):
    def __init__(self, message, duration=3000):
        super().__init__()
        
        # Frameless, transparent, stays on top
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        # Frame
        self.frame = QFrame()
        self.frame.setObjectName("borderOverlay")
        
        # Message label
        self.label = QLabel(message)
        self.label.setObjectName("toastLabel")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        
        # Layout
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.addWidget(self.label)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.frame)
        
        # Size
        self.setFixedSize(300, 80)
        
        # Position at bottom-right of screen
        self._position_on_screen()
        
        # Auto-hide timer
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._fade_out)
        self.hide_timer.start(duration)
        
        # Fade in
        self._fade_in()
    
    def _position_on_screen(self):
        """Position at bottom-right with margin"""
        screen = QApplication.primaryScreen().geometry()
        margin = 20
        x = screen.width() - self.width() - margin
        y = screen.height() - self.height() - margin
        self.move(x, y)
    
    def _fade_in(self):
        """Fade in animation"""
        self.setWindowOpacity(0.0)
        self.show()
        
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(0.95)
        self.animation.start()
    
    def _fade_out(self):
        """Fade out animation"""
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(self.windowOpacity())
        self.animation.setEndValue(0.0)
        self.animation.finished.connect(self.close)
        self.animation.start()

# Usage
def show_toast(message, duration=3000):
    toast = ToastOverlay(message, duration)
    return toast

# Show notification
toast = show_toast("Operation completed successfully!")
```

### Picture-in-Picture Overlay

```python
class PiPOverlay(ResizableOverlay):
    def __init__(self, video_widget):
        super().__init__()
        
        # Add video widget to content
        self.content_layout.addWidget(video_widget)
        
        # Control bar
        self.controls = QFrame()
        control_layout = QHBoxLayout(self.controls)
        
        self.play_button = QPushButton("⏯")
        self.play_button.setObjectName("QBasicBitchButton")
        control_layout.addWidget(self.play_button)
        
        control_layout.addStretch()
        
        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("QBasicBitchButton")
        self.close_button.clicked.connect(self.close)
        control_layout.addWidget(self.close_button)
        
        self.content_layout.addWidget(self.controls)
        
        # Initially hide controls
        self.controls.hide()
        
        # Show controls on hover
        self.setMouseTracking(True)
    
    def enterEvent(self, event):
        """Show controls when mouse enters"""
        self.controls.show()
    
    def leaveEvent(self, event):
        """Hide controls when mouse leaves"""
        self.controls.hide()
```

### Screen Capture Preview Overlay

```python
class ScreenCaptureOverlay(AspectRatioOverlay):
    def __init__(self, screenshot_pixmap):
        super().__init__(aspect_ratio=screenshot_pixmap.width() / screenshot_pixmap.height())
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setPixmap(screenshot_pixmap)
        self.image_label.setScaledContents(True)
        self.content_layout.addWidget(self.image_label)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        save_button = QPushButton("Save")
        save_button.setObjectName("QBasicBitchButton")
        save_button.clicked.connect(self.save_screenshot)
        button_layout.addWidget(save_button)
        
        copy_button = QPushButton("Copy")
        copy_button.setObjectName("QBasicBitchButton")
        copy_button.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(copy_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton("Discard")
        close_button.setObjectName("QBasicBitchButton")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        
        self.content_layout.addLayout(button_layout)
        
        self.screenshot = screenshot_pixmap
    
    def save_screenshot(self):
        """Save screenshot to file"""
        from PySide6.QtWidgets import QFileDialog
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Screenshot",
            "",
            "PNG Image (*.png);;JPEG Image (*.jpg)"
        )
        
        if filename:
            self.screenshot.save(filename)
            show_toast("Screenshot saved!")
            self.close()
    
    def copy_to_clipboard(self):
        """Copy screenshot to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(self.screenshot)
        show_toast("Copied to clipboard!")
        self.close()
```

---

## Best Practices

### 1. Always Set Window Flags

```python
self.setWindowFlags(
    Qt.FramelessWindowHint |      # No title bar
    Qt.WindowStaysOnTopHint |     # Stay on top
    Qt.Tool                        # No taskbar entry
)
self.setAttribute(Qt.WA_TranslucentBackground)
```

### 2. Use Object Names

```python
# For theme styling
self.setObjectName("overlayHostWindow")
frame.setObjectName("borderOverlay")
```

### 3. Proper Layering

```python
# Outer to inner:
# 1. Root widget (transparent)
# 2. Border frame (styled border)
# 3. Content frame (backdrop)
# 4. Your content widgets
```

### 4. Handle High DPI

```python
# Qt handles this automatically, but ensure:
QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)
```

### 5. Smooth Animations

```python
# Use QPropertyAnimation for smooth transitions
from PySide6.QtCore import QPropertyAnimation, QEasingCurve

animation = QPropertyAnimation(widget, b"geometry")
animation.setDuration(200)
animation.setEasingCurve(QEasingCurve.OutCubic)
animation.setStartValue(start_rect)
animation.setEndValue(end_rect)
animation.start()
```

### 6. Memory Management

```python
# Use Qt parent-child relationships
widget.setParent(parent_widget)

# Or register with ResourceManager
resource_manager.register_qt(overlay, ResourceType.WINDOW, "My overlay")
```

### 7. Multi-Monitor Support

```python
def get_screen_at_pos(pos):
    """Get screen containing position"""
    for screen in QApplication.screens():
        if screen.geometry().contains(pos):
            return screen
    return QApplication.primaryScreen()

# Position overlay on correct screen
screen = get_screen_at_pos(QCursor.pos())
overlay.move(screen.geometry().center() - overlay.rect().center())
```

---

This completes the overlay patterns guide. For general theme styling, see [THEME_GUIDE.md](./THEME_GUIDE.md).
