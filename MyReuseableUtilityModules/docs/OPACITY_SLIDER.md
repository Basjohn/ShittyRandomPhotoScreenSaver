# QSS Opacity Slider - The Impossible Made Possible

A clever trick to create a **fully functional opacity slider using only QSS and basic Qt widgets** - no custom painting required!

## The Problem

QSS (Qt Style Sheets) doesn't support sliders natively. You can't create a traditional slider widget with QSS alone. But we need a beautiful, theme-consistent opacity control!

## The Solution

Use **two QFrames with dynamic width** controlled by Python, styled entirely through QSS. One frame "fills" to show the current value, the other remains empty.

### Visual Result

```
┌─────────────────────────────┐
│ ███████████░░░░░░░░░░░░░░░░ │  ← 45% opacity
│      OPACITY                │
└─────────────────────────────┘
```

The filled portion (███) grows/shrinks as you drag, while the empty portion (░) adjusts accordingly.

---

## Implementation

### 1. HTML Structure (Qt Widgets)

```python
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QPoint

# Container frame
opacity_frame = QFrame()
opacity_frame.setObjectName("opacityControlFrame")
opacity_layout = QVBoxLayout(opacity_frame)
opacity_layout.setContentsMargins(0, 2, 0, 0)
opacity_layout.setSpacing(2)

# Bar container (clickable/draggable area)
opacity_container = QFrame()
opacity_container.setObjectName("opacityControlContainer")
opacity_container.setFixedHeight(14)
opacity_container.setMouseTracking(True)

# Layout for the two frames (side by side)
container_layout = QHBoxLayout(opacity_container)
container_layout.setContentsMargins(3, 2, 3, 2)
container_layout.setSpacing(0)

# Fill frame (the colored part)
opacity_fill = QFrame()
opacity_fill.setObjectName("opacityFill")
opacity_fill.setFixedHeight(10)

# Empty frame (transparent part)
opacity_empty = QFrame()
opacity_empty.setObjectName("opacityEmpty")
opacity_empty.setFixedHeight(10)
opacity_empty.setStyleSheet("background: transparent; border: none;")

# Add both frames to container
container_layout.addWidget(opacity_fill)
container_layout.addWidget(opacity_empty)

# Label below the bar
opacity_label = QLabel("OPACITY")
opacity_label.setObjectName("opacityLabel")

opacity_layout.addWidget(opacity_container)
opacity_layout.addWidget(opacity_label)
```

### 2. QSS Styling

**Dark Theme** (`dark.qss`):

```css
/* ===== OPACITY CONTROL ===== */

/* Outer frame container */
QFrame#opacityControlFrame {
    background-color: transparent;
    border: none;
    margin: 10px 0 5px 0;
}

/* The bar container (border and background) */
QFrame#opacityControlContainer {
    background-color: rgba(42, 42, 42, 1.0);  /* Dark background */
    border: 2px solid rgba(255, 255, 255, 1.0);  /* White border */
    border-radius: 7px;
    min-width: 200px;
    max-width: 280px;
    min-height: 14px;
    max-height: 14px;
    padding: 1px;
}

/* The fill portion (grows/shrinks with opacity value) */
QFrame#opacityFill {
    background-color: rgba(255, 255, 255, 1.0);  /* White fill */
    border-radius: 5px;
    min-height: 10px;
    max-height: 10px;
    margin: 0;
    padding: 0;
}

/* Label below the bar */
QLabel#opacityLabel {
    color: rgba(255, 255, 255, 1.0);
    font-size: 9px;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 0;
    margin: 0 0 0 3px;
}
```

**Light Theme** (`light.qss`):

```css
/* ===== OPACITY CONTROL ===== */

QFrame#opacityControlFrame {
    background-color: transparent;
    border: none;
    margin: 10px 0 5px 0;
}

QFrame#opacityControlContainer {
    background-color: rgba(213, 213, 213, 1.0);  /* Light background */
    border: 2px solid rgba(0, 0, 0, 1.0);  /* Black border */
    border-radius: 7px;
    min-width: 200px;
    max-width: 280px;
    min-height: 14px;
    max-height: 14px;
    padding: 1px;
}

QFrame#opacityFill {
    background-color: rgba(0, 0, 0, 1.0);  /* Black fill */
    border-radius: 5px;
    min-height: 10px;
    max-height: 10px;
    margin: 0;
    padding: 0;
}

QLabel#opacityLabel {
    color: rgba(0, 0, 0, 1.0);
    font-size: 9px;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 0;
    margin: 0 0 0 3px;
}
```

### 3. Python Logic (The Magic)

```python
def set_opacity(self, opacity_percent: int):
    """
    Update the opacity slider to show the given percentage.
    
    Args:
        opacity_percent: Opacity value from 0-100
    """
    # Clamp value
    opacity_percent = max(0, min(100, opacity_percent))
    self.current_opacity = opacity_percent
    
    # Calculate widths
    container_width = self.opacity_container.width()
    
    # Account for container margins (3px left + 3px right = 6px)
    usable_width = container_width - 6
    
    # Calculate fill width based on percentage
    fill_width = int(usable_width * (opacity_percent / 100.0))
    empty_width = usable_width - fill_width
    
    # Set the widths
    self.opacity_fill.setFixedWidth(max(0, fill_width))
    self.opacity_empty.setFixedWidth(max(0, empty_width))
    
    # Apply the actual window opacity
    self.setWindowOpacity(opacity_percent / 100.0)


def _on_opacity_bar_clicked(self, event):
    """Handle click on opacity bar to set value."""
    if event.button() != Qt.LeftButton:
        return
    
    # Get click position
    x = event.pos().x()
    
    # Account for container margins
    usable_width = self.opacity_container.width() - 6
    
    # Calculate percentage (clamp to 0-100)
    percent = int((x / usable_width) * 100)
    percent = max(0, min(100, percent))
    
    # Update opacity
    self.set_opacity(percent)
    
    # Save to settings
    self.settings_manager.set("appearance.opacity", percent)


def _on_opacity_bar_dragged(self, event):
    """Handle dragging on opacity bar."""
    # Only respond to left button drag
    if not (event.buttons() & Qt.LeftButton):
        return
    
    # Same logic as click
    x = event.pos().x()
    usable_width = self.opacity_container.width() - 6
    percent = int((x / usable_width) * 100)
    percent = max(0, min(100, percent))
    
    self.set_opacity(percent)
    
    # Save to settings (can be throttled if needed)
    self.settings_manager.set("appearance.opacity", percent)


# Connect mouse events
self.opacity_container.mousePressEvent = self._on_opacity_bar_clicked
self.opacity_container.mouseMoveEvent = self._on_opacity_bar_dragged
```

---

## How It Works

### The Trick

1. **Two Frames, One Layout**: Place two QFrames side-by-side in a horizontal layout
2. **Dynamic Width**: Adjust the width of each frame based on the slider value
3. **Fill + Empty = Total**: `fill_width + empty_width = container_width`
4. **QSS Styling**: Style each frame with appropriate colors and borders
5. **Mouse Events**: Capture clicks and drags to calculate the new value

### Why This Works

**QHBoxLayout** automatically positions widgets side-by-side. By setting fixed widths on both frames, we control their size. The layout engine handles the rest!

**Key Insight**: We're not creating a custom slider widget. We're just using two colored rectangles whose widths change dynamically.

### Visual Breakdown

```
Container Width: 200px (usable: 194px after margins)
Opacity: 70%

┌────── Container (200px) ──────┐
│  ┌─── Fill (135px) ───┐       │
│  │█████████████████████│░░░░░░ │  Fill=70%, Empty=30%
│  └─────────────────────┘       │
└────────────────────────────────┘
     ↑                   ↑
   Fill (70%)        Empty (30%)
   135px             59px
```

---

## Complete Example

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QPoint

class OpacityControlWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_opacity = 100
        self.setup_ui()
    
    def setup_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        
        # Create opacity control
        self.opacity_frame = QFrame()
        self.opacity_frame.setObjectName("opacityControlFrame")
        opacity_layout = QVBoxLayout(self.opacity_frame)
        opacity_layout.setContentsMargins(0, 2, 0, 0)
        opacity_layout.setSpacing(2)
        
        # Bar container
        self.opacity_container = QFrame()
        self.opacity_container.setObjectName("opacityControlContainer")
        self.opacity_container.setFixedHeight(14)
        self.opacity_container.setMouseTracking(True)
        
        container_layout = QHBoxLayout(self.opacity_container)
        container_layout.setContentsMargins(3, 2, 3, 2)
        container_layout.setSpacing(0)
        
        # Fill and empty frames
        self.opacity_fill = QFrame()
        self.opacity_fill.setObjectName("opacityFill")
        self.opacity_fill.setFixedHeight(10)
        
        self.opacity_empty = QFrame()
        self.opacity_empty.setObjectName("opacityEmpty")
        self.opacity_empty.setFixedHeight(10)
        self.opacity_empty.setStyleSheet(
            "background: transparent; border: none; margin: 0; padding: 0;"
        )
        
        container_layout.addWidget(self.opacity_fill)
        container_layout.addWidget(self.opacity_empty)
        
        # Label
        self.opacity_label = QLabel("OPACITY")
        self.opacity_label.setObjectName("opacityLabel")
        
        opacity_layout.addWidget(self.opacity_container)
        opacity_layout.addWidget(self.opacity_label)
        
        layout.addWidget(self.opacity_frame)
        
        # Connect events
        self.opacity_container.mousePressEvent = self._on_opacity_bar_clicked
        self.opacity_container.mouseMoveEvent = self._on_opacity_bar_dragged
        
        # Initialize
        self.set_opacity(100)
    
    def set_opacity(self, opacity_percent: int):
        """Update opacity slider and window transparency."""
        opacity_percent = max(0, min(100, opacity_percent))
        self.current_opacity = opacity_percent
        
        container_width = self.opacity_container.width()
        usable_width = container_width - 6  # Account for margins
        
        fill_width = int(usable_width * (opacity_percent / 100.0))
        empty_width = usable_width - fill_width
        
        self.opacity_fill.setFixedWidth(max(0, fill_width))
        self.opacity_empty.setFixedWidth(max(0, empty_width))
        
        # Apply to parent window if available
        window = self.window()
        if window:
            window.setWindowOpacity(opacity_percent / 100.0)
    
    def _on_opacity_bar_clicked(self, event):
        """Handle click on opacity bar."""
        if event.button() != Qt.LeftButton:
            return
        
        x = event.pos().x()
        usable_width = self.opacity_container.width() - 6
        percent = int((x / usable_width) * 100)
        percent = max(0, min(100, percent))
        
        self.set_opacity(percent)
    
    def _on_opacity_bar_dragged(self, event):
        """Handle drag on opacity bar."""
        if not (event.buttons() & Qt.LeftButton):
            return
        
        x = event.pos().x()
        usable_width = self.opacity_container.width() - 6
        percent = int((x / usable_width) * 100)
        percent = max(0, min(100, percent))
        
        self.set_opacity(percent)

# Usage
from PySide6.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)

# Load QSS theme
with open("themes/dark.qss", "r") as f:
    app.setStyleSheet(f.read())

# Create widget
opacity_widget = OpacityControlWidget()
opacity_widget.show()

sys.exit(app.exec())
```

---

## Customization

### Change Colors

**Dark Theme**: Edit `QFrame#opacityFill` background color in `dark.qss`

```css
QFrame#opacityFill {
    background-color: rgba(100, 200, 255, 1.0);  /* Blue fill */
    border-radius: 5px;
}
```

**Light Theme**: Edit `QFrame#opacityFill` background color in `light.qss`

```css
QFrame#opacityFill {
    background-color: rgba(255, 100, 50, 1.0);  /* Orange fill */
    border-radius: 5px;
}
```

### Change Size

Adjust width in QSS:

```css
QFrame#opacityControlContainer {
    min-width: 150px;   /* Narrower */
    max-width: 350px;   /* Wider */
}
```

Adjust height in Python and QSS:

```python
# Python
self.opacity_container.setFixedHeight(20)  # Taller bar
self.opacity_fill.setFixedHeight(16)
self.opacity_empty.setFixedHeight(16)
```

```css
/* QSS */
QFrame#opacityControlContainer {
    min-height: 20px;
    max-height: 20px;
}

QFrame#opacityFill {
    min-height: 16px;
    max-height: 16px;
}
```

### Add Percentage Display

```python
# Update label dynamically
def set_opacity(self, opacity_percent: int):
    # ... existing code ...
    
    # Update label to show percentage
    self.opacity_label.setText(f"OPACITY {opacity_percent}%")
```

---

## Advantages

✅ **Pure QSS**: No custom painting or complex Qt widgets  
✅ **Theme Consistent**: Automatically matches your theme  
✅ **Smooth**: Hardware-accelerated rendering  
✅ **Simple**: ~50 lines of Python, ~40 lines of QSS  
✅ **Flexible**: Easy to customize colors, sizes, styles  
✅ **Production-Ready**: Used in SPQDocker for 18+ months  

---

## Why This Is Better Than QSlider

**QSlider** styling in QSS is notoriously difficult:
- Complex pseudo-elements (`:groove`, `:handle`, `:sub-page`)
- Inconsistent across platforms
- Hard to make pixel-perfect
- Limited styling options

**This approach**:
- Simple two-frame layout
- Full QSS control
- Consistent across platforms
- Easy to theme
- No Qt quirks to work around

---

## Advanced: Vertical Slider

The same trick works vertically!

```python
# Use QVBoxLayout instead of QHBoxLayout
container_layout = QVBoxLayout(self.opacity_container)

# Set fixed widths instead of heights
self.opacity_fill.setFixedWidth(10)
self.opacity_empty.setFixedWidth(10)

# Calculate height instead of width
def set_opacity(self, opacity_percent: int):
    container_height = self.opacity_container.height()
    usable_height = container_height - 6
    
    fill_height = int(usable_height * (opacity_percent / 100.0))
    empty_height = usable_height - fill_height
    
    # Fill grows from bottom
    self.opacity_empty.setFixedHeight(max(0, empty_height))
    self.opacity_fill.setFixedHeight(max(0, fill_height))
```

---

## The "Impossible" Made Possible

This technique can be applied to **any slider-like control**:

- **Volume sliders**: Adjust audio levels
- **Brightness controls**: Screen brightness
- **Progress bars**: With click-to-seek
- **Temperature gauges**: With set points
- **Any percentage-based control**

The key insight: **Dynamic widget sizing + QSS styling = Custom slider without custom painting!**

---

## Production Tips

### 1. Throttle Settings Saves

```python
from PySide6.QtCore import QTimer

def __init__(self):
    # ... setup ...
    self.save_timer = QTimer()
    self.save_timer.setSingleShot(True)
    self.save_timer.timeout.connect(self._save_opacity)
    self.pending_opacity = None

def _on_opacity_bar_dragged(self, event):
    # ... calculate percent ...
    
    self.set_opacity(percent)
    
    # Debounce save
    self.pending_opacity = percent
    self.save_timer.start(500)  # Save 500ms after drag stops

def _save_opacity(self):
    if self.pending_opacity is not None:
        self.settings_manager.set("appearance.opacity", self.pending_opacity)
        self.pending_opacity = None
```

### 2. Emit Signals

```python
from PySide6.QtCore import Signal

class OpacityControlWidget(QWidget):
    opacityChanged = Signal(int)  # Emits percentage
    
    def set_opacity(self, opacity_percent: int):
        # ... existing code ...
        
        # Emit signal
        self.opacityChanged.emit(opacity_percent)

# Usage
opacity_control.opacityChanged.connect(lambda p: print(f"Opacity: {p}%"))
```

### 3. Keyboard Support

```python
def keyPressEvent(self, event):
    if event.key() == Qt.Key_Left:
        self.set_opacity(self.current_opacity - 5)
    elif event.key() == Qt.Key_Right:
        self.set_opacity(self.current_opacity + 5)
    else:
        super().keyPressEvent(event)
```

---

This "impossible" QSS slider trick has saved countless hours of custom widget development and provides a polished, theme-consistent control that just works!
