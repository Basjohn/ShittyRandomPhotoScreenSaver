# Window Behavior System Guide

Complete guide to the window behavior system for drag, resize, snap, and multi-monitor support.

## Table of Contents

1. [Overview](#overview)
2. [WindowBehaviorManager](#windowbehaviormanager)
3. [Dragging Windows](#dragging-windows)
4. [Resizing Windows](#resizing-windows)
5. [Snapping System](#snapping-system)
6. [Multi-Monitor Support](#multi-monitor-support)
7. [Real-World Examples](#real-world-examples)

---

## Overview

The window behavior system provides a **production-ready, unified interface** for all window interactions:

- **Dragging**: Click and drag to move windows with multi-monitor support
- **Resizing**: Drag edges/corners to resize with minimum size enforcement
- **Snapping**: Intelligent snapping to screen edges, corners, and centers
- **Multi-Monitor**: Seamless behavior across multiple screens
- **Screen Bounds**: Prevents windows from going off-screen
- **Cursor Management**: Automatic cursor changes for resize handles
- **Windows Integration**: Native WM_MOVING filter for smooth dragging

### Key Features

✅ **Lock-Free**: No mutexes, uses Qt signal/slot patterns  
✅ **Multi-Monitor Aware**: Handles complex multi-display setups  
✅ **Production-Tested**: 18+ months in SPQDocker  
✅ **Configurable**: Adjustable snap distances and resize margins  
✅ **Native Integration**: Uses Windows native events for smooth dragging  

---

## WindowBehaviorManager

The main class that manages all window behavior.

### Basic Usage

```python
from PySide6.QtWidgets import QWidget
from utils.window import WindowBehaviorManager

class MyWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        # Initialize window behavior manager
        self.window_behavior = WindowBehaviorManager(
            widget=self,
            min_width=400,
            min_height=300
        )
    
    def mousePressEvent(self, event):
        # Handle mouse press for drag/resize
        self.window_behavior.handle_mouse_press(event)
    
    def mouseMoveEvent(self, event):
        # Handle mouse move for drag/resize
        self.window_behavior.handle_mouse_move(event)
    
    def mouseReleaseEvent(self, event):
        # Handle mouse release
        self.window_behavior.handle_mouse_release(event)
```

### Constructor Parameters

```python
WindowBehaviorManager(
    widget: QWidget,          # The widget to manage
    min_width: int = 100,     # Minimum window width
    min_height: int = 50      # Minimum window height
)
```

### Methods

#### `handle_mouse_press(event, is_draggable_region=None, restrict_to_bottom_right=False)`

Handles mouse press events to initiate dragging or resizing.

**Parameters**:
- `event`: Qt mouse event
- `is_draggable_region`: Optional function `(QPoint) -> bool` to determine if position is draggable
- `restrict_to_bottom_right`: If `True`, only allow resizing from bottom-right corner

**Example**:
```python
def is_title_bar(pos: QPoint) -> bool:
    """Only allow dragging from title bar area."""
    return pos.y() < 60  # Top 60 pixels

self.window_behavior.handle_mouse_press(
    event,
    is_draggable_region=is_title_bar
)
```

#### `handle_mouse_move(event, restrict_to_bottom_right=False)`

Handles mouse move events during dragging or resizing.

#### `handle_mouse_release(event)`

Handles mouse release to end dragging or resizing with final snap.

#### `set_snap_distance(pixels: int)`

Sets the snap distance for this window.

```python
# Increase snap sensitivity
self.window_behavior.set_snap_distance(60)

# Decrease snap sensitivity
self.window_behavior.set_snap_distance(20)

# Disable snapping
self.window_behavior.set_snap_distance(0)
```

### Properties

#### `state: DragState`

Access the current drag/resize state.

```python
if self.window_behavior.state.is_dragging:
    print("Currently dragging")

if self.window_behavior.state.is_resizing:
    print(f"Resizing from edge: {self.window_behavior.state.resize_edge}")
```

---

## Dragging Windows

### Full Dragging Example

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from utils.window import WindowBehaviorManager

class DraggableWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        # Frameless window
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        # Setup UI
        layout = QVBoxLayout(self)
        self.title_bar = QLabel("Drag me!")
        self.title_bar.setFixedHeight(40)
        self.content = QLabel("Content area")
        layout.addWidget(self.title_bar)
        layout.addWidget(self.content)
        
        # Initialize window behavior
        self.window_behavior = WindowBehaviorManager(
            widget=self,
            min_width=300,
            min_height=200
        )
    
    def is_title_bar_region(self, pos):
        """Check if position is in title bar."""
        return pos.y() < 40
    
    def mousePressEvent(self, event):
        self.window_behavior.handle_mouse_press(
            event,
            is_draggable_region=self.is_title_bar_region
        )
    
    def mouseMoveEvent(self, event):
        self.window_behavior.handle_mouse_move(event)
    
    def mouseReleaseEvent(self, event):
        self.window_behavior.handle_mouse_release(event)

# Usage
window = DraggableWindow()
window.show()
```

### Cursor Feedback During Drag

The system automatically sets `Qt.SizeAllCursor` during dragging and restores it on release.

---

## Resizing Windows

### Resize Handles

The system detects 8 resize positions:
- **Corners**: `top_left`, `top_right`, `bottom_left`, `bottom_right`
- **Edges**: `left`, `right`, `top`, `bottom`

### Full Resizing Example

```python
class ResizableWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        # Setup window behavior
        self.window_behavior = WindowBehaviorManager(
            widget=self,
            min_width=400,
            min_height=300
        )
        
        # Enable mouse tracking for cursor updates
        self.setMouseTracking(True)
    
    def mousePressEvent(self, event):
        # No is_draggable_region means anywhere can start resize/drag
        self.window_behavior.handle_mouse_press(event)
    
    def mouseMoveEvent(self, event):
        self.window_behavior.handle_mouse_move(event)
    
    def mouseReleaseEvent(self, event):
        self.window_behavior.handle_mouse_release(event)
```

### Cursor Shapes

The system automatically sets appropriate cursors:

| Edge/Corner | Cursor |
|-------------|--------|
| Left/Right | `Qt.SizeHorCursor` (↔) |
| Top/Bottom | `Qt.SizeVerCursor` (↕) |
| Top-Left/Bottom-Right | `Qt.SizeFDiagCursor` (⤢) |
| Top-Right/Bottom-Left | `Qt.SizeBDiagCursor` (⤡) |

### Restrict Resize to Corner

For dialog-like windows, restrict resizing to bottom-right corner only:

```python
def mousePressEvent(self, event):
    self.window_behavior.handle_mouse_press(
        event,
        restrict_to_bottom_right=True
    )

def mouseMoveEvent(self, event):
    self.window_behavior.handle_mouse_move(
        event,
        restrict_to_bottom_right=True
    )
```

### Minimum Size Enforcement

```python
# Set minimum size in constructor
self.window_behavior = WindowBehaviorManager(
    widget=self,
    min_width=600,  # Window won't resize smaller than 600px wide
    min_height=400  # Window won't resize smaller than 400px tall
)
```

---

## Snapping System

### Intelligent Multi-Monitor Snapping

The snapping system provides magnetic edges that "pull" windows into alignment.

**Snap Points**:
- **Screen Edges**: Left, right, top, bottom of each screen
- **Screen Centers**: Horizontal and vertical center of each screen
- **Multi-Screen**: Snaps work across all connected displays

### Snap Distance

Default snap distance is **40 pixels**. Adjust per-window:

```python
# More aggressive snapping
self.window_behavior.set_snap_distance(60)

# Less aggressive snapping
self.window_behavior.set_snap_distance(20)

# Disable snapping
self.window_behavior.set_snap_distance(0)
```

### Manual Snapping

Use the snap function directly:

```python
from utils.window import apply_snap
from PySide6.QtCore import QPoint, QSize

# Current window position and size
pos = QPoint(100, 100)
size = QSize(400, 300)

# Apply snapping
snapped_pos = apply_snap(pos, size, snap_distance=40)

# Move window to snapped position
self.move(snapped_pos)
```

### Custom Snap Points

```python
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

# Get screen geometries
screens = QApplication.screens()
screen_rects = [screen.availableGeometry() for screen in screens]

# Apply snap with custom screen list
snapped_pos = apply_snap(
    pos=current_pos,
    size=window_size,
    snap_distance=50,
    screen_rects=screen_rects
)
```

---

## Multi-Monitor Support

### Automatic Screen Detection

The system automatically:
1. Detects which screen the window is on
2. Uses that screen's work area (excludes taskbar)
3. Prevents window from going off-screen
4. Supports moving between monitors

### Work Area vs Full Screen

**Work Area**: Screen space excluding taskbar (default)  
**Full Screen**: Entire screen including taskbar area

The system uses work area to prevent windows from being hidden behind the taskbar.

### Screen Boundaries

Windows are automatically constrained to screen boundaries:

```python
# Window is automatically prevented from:
# - Moving completely off-screen
# - Being positioned where it can't be grabbed
# - Overlapping into non-visible areas
```

### Multi-Monitor Snapping

When dragging across monitors, snapping works seamlessly:

```python
# Window snaps to:
# - Edges of the current screen
# - Edges of adjacent screens
# - Centers of any visible screen
# - Gap between screens (if configured)
```

---

## Real-World Examples

### Example 1: Dialog with Resize Corner

```python
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton
from PySide6.QtCore import Qt
from utils.window import WindowBehaviorManager

class SettingsDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        
        # Setup UI
        layout = QVBoxLayout(self)
        layout.addWidget(QPushButton("Save"))
        layout.addWidget(QPushButton("Cancel"))
        
        # Window behavior - resize only from bottom-right
        self.window_behavior = WindowBehaviorManager(
            widget=self,
            min_width=400,
            min_height=300
        )
        self.setMouseTracking(True)
    
    def mousePressEvent(self, event):
        self.window_behavior.handle_mouse_press(
            event,
            restrict_to_bottom_right=True
        )
    
    def mouseMoveEvent(self, event):
        self.window_behavior.handle_mouse_move(
            event,
            restrict_to_bottom_right=True
        )
    
    def mouseReleaseEvent(self, event):
        self.window_behavior.handle_mouse_release(event)
```

### Example 2: Custom Drag Region with Resize

```python
class CustomWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        # Create title bar
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(40)
        
        # Create content area
        self.content = QWidget()
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.title_bar)
        layout.addWidget(self.content)
        
        # Window behavior
        self.window_behavior = WindowBehaviorManager(
            widget=self,
            min_width=500,
            min_height=350
        )
        self.setMouseTracking(True)
    
    def is_draggable(self, pos):
        """Only drag from title bar, not from resize edges."""
        # Check if in title bar
        if pos.y() > 40:
            return False
        
        # Check if on resize edge (take priority)
        from utils.window import get_resize_edge_for_pos
        if get_resize_edge_for_pos(pos, self):
            return False
        
        return True
    
    def mousePressEvent(self, event):
        self.window_behavior.handle_mouse_press(
            event,
            is_draggable_region=self.is_draggable
        )
    
    def mouseMoveEvent(self, event):
        self.window_behavior.handle_mouse_move(event)
    
    def mouseReleaseEvent(self, event):
        self.window_behavior.handle_mouse_release(event)
```

### Example 3: Overlay Window with Snapping

```python
class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        # Overlay window flags
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Window behavior with aggressive snapping
        self.window_behavior = WindowBehaviorManager(
            widget=self,
            min_width=200,
            min_height=150
        )
        self.window_behavior.set_snap_distance(60)  # Strong snap
        
        self.setMouseTracking(True)
    
    def mousePressEvent(self, event):
        self.window_behavior.handle_mouse_press(event)
    
    def mouseMoveEvent(self, event):
        self.window_behavior.handle_mouse_move(event)
    
    def mouseReleaseEvent(self, event):
        self.window_behavior.handle_mouse_release(event)
```

### Example 4: Utility Functions

```python
from utils.window import get_resize_edge_for_pos, get_cursor_for_edge
from PySide6.QtCore import QPoint

# Check if mouse is on resize edge
pos = QPoint(395, 295)  # Near bottom-right of 400x300 window
edge = get_resize_edge_for_pos(pos, my_widget, margin=12)

if edge:
    print(f"On edge: {edge}")
    
    # Get appropriate cursor
    cursor = get_cursor_for_edge(edge)
    my_widget.setCursor(cursor)
else:
    my_widget.unsetCursor()
```

---

## Advanced Features

### Windows Native Integration

On Windows, the system installs a native event filter for `WM_MOVING` messages. This provides:
- **Smooth dragging**: Native Windows drag feel
- **Screen bounds**: Automatic clamping to screen edges
- **Taskbar awareness**: Respects taskbar position
- **Multi-monitor**: Seamless monitor boundary handling

### DragState Access

Monitor the current drag state:

```python
state = self.window_behavior.state

# Check what's happening
if state.is_dragging:
    print("Dragging window")
    print(f"Start position: {state.drag_start_position}")
    print(f"Global start: {state.drag_global_start}")

if state.is_resizing:
    print(f"Resizing from: {state.resize_edge}")
    
# Check cursor override
if state.cursor_overridden:
    print("Cursor is managed by behavior system")
```

### Configuration Constants

```python
from utils.window import (
    DEFAULT_SNAP_DISTANCE,    # 40 pixels
    DEFAULT_RESIZE_MARGIN,    # 12 pixels
    MIN_WINDOW_SIZE           # QSize(100, 50)
)

# Use in your application
CUSTOM_SNAP = DEFAULT_SNAP_DISTANCE * 1.5  # 60 pixels
CUSTOM_MARGIN = DEFAULT_RESIZE_MARGIN + 5   # 17 pixels
```

---

## Best Practices

### 1. Always Enable Mouse Tracking

```python
self.setMouseTracking(True)  # Required for cursor updates
```

### 2. Set Appropriate Minimum Sizes

```python
# Too small: Hard to use
WindowBehaviorManager(widget=self, min_width=50, min_height=30)  # ❌

# Good: Usable minimum
WindowBehaviorManager(widget=self, min_width=300, min_height=200)  # ✅
```

### 3. Use Draggable Regions for Complex UIs

```python
def is_draggable(self, pos):
    # Don't allow dragging from interactive elements
    if self.button.geometry().contains(pos):
        return False
    if self.text_edit.geometry().contains(pos):
        return False
    return pos.y() < 60  # Title bar only
```

### 4. Respect User Expectations

```python
# Dialogs: Resize from corner only
self.window_behavior.handle_mouse_press(event, restrict_to_bottom_right=True)

# Main windows: All edges/corners
self.window_behavior.handle_mouse_press(event)
```

### 5. Adjust Snap Distance for Window Type

```python
# Overlay windows: Strong snap (easy to align)
overlay_behavior.set_snap_distance(60)

# Main windows: Moderate snap (balanced)
main_behavior.set_snap_distance(40)

# Precise positioning: Weak snap (fine control)
precise_behavior.set_snap_distance(15)
```

---

## Troubleshooting

### Cursor Doesn't Change on Edges

**Solution**: Enable mouse tracking
```python
self.setMouseTracking(True)
```

### Window Doesn't Snap

**Check**:
1. Snap distance is > 0
2. Window is near a snap point
3. Screen geometries are valid

```python
# Debug snapping
from utils.window import apply_snap

pos = self.pos()
snapped = apply_snap(pos, self.size(), 40)
print(f"Original: {pos}, Snapped: {snapped}")
```

### Resize Not Working

**Check**:
1. Mouse events are being handled
2. Minimum size isn't preventing resize
3. `restrict_to_bottom_right` isn't too restrictive

```python
# Debug resize detection
from utils.window import get_resize_edge_for_pos

edge = get_resize_edge_for_pos(event.pos(), self)
print(f"Resize edge: {edge}")
```

### Window Goes Off-Screen

The system should prevent this automatically. If it happens:
1. Check for custom positioning code that overrides the behavior
2. Verify screen geometries are correct
3. On Windows, ensure native event filter is installed

---

## Performance Notes

- **Lock-Free**: No blocking operations
- **Efficient**: Only processes events when needed
- **Minimal Overhead**: ~1-2ms per mouse move
- **Native Integration**: Uses Windows messages for smooth dragging

---

This window behavior system has been battle-tested in SPQDocker for 18+ months with complex multi-window, multi-monitor setups. It handles edge cases like:
- Screen resolution changes
- Monitor hot-plugging
- DPI scaling
- Taskbar position changes
- Multi-monitor with different DPI
- Virtual desktops

Copy the `utils/window/` directory to your project and start using professional window management!
