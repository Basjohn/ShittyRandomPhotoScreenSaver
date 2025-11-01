# Quick Reference Card

Fast reference for common patterns. See full docs in `docs/` for details.

## Themes

```python
# Apply theme
with open("themes/dark.qss", "r") as f:
    app.setStyleSheet(f.read())

# Runtime switch
def toggle_theme():
    theme = "light" if current == "dark" else "dark"
    with open(f"themes/{theme}.qss", "r") as f:
        app.setStyleSheet(f.read())
```

## ThreadManager

```python
from core.threading import ThreadManager, ThreadPoolType

tm = ThreadManager()

# Submit task
tm.submit_task(ThreadPoolType.IO, my_function, arg1, arg2)

# With callback
tm.submit_task(ThreadPoolType.COMPUTE, calc, callback=on_done)

# UI thread
tm.run_on_ui_thread(widget.update)

# Timer
tm.single_shot(1000, delayed_func)  # 1 second

# Recurring
timer_id = tm.schedule_recurring(500, periodic_func)
tm.cancel_timer(timer_id)

# Shutdown
tm.shutdown()
```

### Pool Types
- `CAPTURE` - Screen capture (2 workers)
- `RENDER` - OpenGL/Graphics (1 worker)
- `IO` - Files/Network (4 workers)
- `COMPUTE` - CPU work (N-1 workers)
- `UI` - UI tasks (2 workers)

## ResourceManager

```python
from core.resources import ResourceManager, ResourceType

rm = ResourceManager()

# Register
rid = rm.register(resource, ResourceType.FILE_HANDLE, "My file")

# With cleanup
rid = rm.register(
    resource,
    ResourceType.CUSTOM,
    "My resource",
    cleanup_handler=lambda r: r.close()
)

# Get
resource = rm.get(rid)

# Qt widget
rid = rm.register_qt(widget, ResourceType.GUI_COMPONENT, "My widget")

# File
rid = rm.register_file(file_handle, "Config file")

# Temp file (auto-delete)
rid = rm.register_temp_file("/tmp/temp.dat", "Temp data", delete=True)

# Unregister
rm.unregister(rid)

# Shutdown (cleans all)
rm.shutdown()
```

### Resource Types
- `GUI_COMPONENT` - Qt widgets
- `WINDOW` - Qt windows
- `TIMER` - Qt timers
- `FILE_HANDLE` - Files
- `NETWORK_CONNECTION` - Sockets
- `DATABASE_CONNECTION` - DB connections
- `THREAD_POOL` - Executors
- `CUSTOM` - Custom resources

## EventSystem

```python
from core.events import EventSystem

es = EventSystem()

# Subscribe
sub_id = es.subscribe("window.created", on_window_created)

# With priority
sub_id = es.subscribe("startup", handler, priority=100)

# With filter
sub_id = es.subscribe(
    "log.message",
    handler,
    filter_fn=lambda e: e.data.get("level") == "error"
)

# UI thread dispatch
sub_id = es.subscribe("data.ready", update_ui, dispatch_on_ui=True)

# Publish
es.publish("window.created", data={"hwnd": 12345})

# Unsubscribe
es.unsubscribe(sub_id)
```

## SettingsManager

```python
from core.settings import SettingsManager

sm = SettingsManager()

# Get with default
width = sm.get("window.width", 800)
theme = sm.get("appearance.theme", "dark")

# Set
sm.set("window.width", 1024)
sm.set("appearance.theme", "light")

# Save
sm.save()

# Change notifications
sm.on_changed("appearance.theme", on_theme_changed)

# Reset
sm.reset_to_defaults()
```

## Overlay Window

```python
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout
from PySide6.QtCore import Qt

class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        
        # Frameless, transparent, on top
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Border frame
        self.border = QFrame()
        self.border.setObjectName("borderOverlay")
        
        # Content
        self.content = QFrame()
        self.content.setObjectName("overlayBackdrop")
        
        # Layout
        border_layout = QVBoxLayout(self.border)
        border_layout.addWidget(self.content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.border)
        
        self.resize(400, 300)

overlay = Overlay()
overlay.show()
```

## Custom Button Styles

```python
# Action button
button = QPushButton("Save")
button.setObjectName("actionButton")

# Select button
button = QPushButton("Choose")
button.setObjectName("selectButton")

# Small toggle
button = QPushButton("Option")
button.setObjectName("QSmolselect")
button.setCheckable(True)

# Mini toggle
button = QPushButton("5")
button.setObjectName("QSmolselectMini")
button.setCheckable(True)

# Basic button
button = QPushButton("OK")
button.setObjectName("QBasicBitchButton")

# Combo arrow
button = QPushButton(">>")
button.setObjectName("QComboArrow")
```

## Toast Notification

```python
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer, QPropertyAnimation

class Toast(QWidget):
    def __init__(self, message, duration=3000):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        frame = QFrame()
        frame.setObjectName("borderOverlay")
        
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        
        layout = QVBoxLayout(frame)
        layout.addWidget(label)
        
        main = QVBoxLayout(self)
        main.addWidget(frame)
        
        self.setFixedSize(300, 80)
        
        # Position bottom-right
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.width() - 320,
            screen.height() - 100
        )
        
        # Auto-close
        QTimer.singleShot(duration, self.close)
        
        self.show()

# Usage
Toast("Saved successfully!")
```

## Draggable Window

```python
class DraggableWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._dragging = False
        self._drag_pos = None
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPos() - self.pos()
    
    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPos() - self._drag_pos)
    
    def mouseReleaseEvent(self, event):
        self._dragging = False
```

## Fade Animation

```python
from PySide6.QtCore import QPropertyAnimation

def fade_in(widget, duration=300):
    widget.setWindowOpacity(0.0)
    animation = QPropertyAnimation(widget, b"windowOpacity")
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(0.95)
    animation.start()
    return animation

def fade_out(widget, duration=300, close_after=True):
    animation = QPropertyAnimation(widget, b"windowOpacity")
    animation.setDuration(duration)
    animation.setStartValue(widget.windowOpacity())
    animation.setEndValue(0.0)
    if close_after:
        animation.finished.connect(widget.close)
    animation.start()
    return animation

# Usage
fade_in(my_overlay)
```

## Task Result Handling

```python
def handle_result(task_result):
    if task_result.success:
        print(f"Success: {task_result.result}")
        print(f"Time: {task_result.execution_time}s")
    else:
        print(f"Error: {task_result.error}")
        logger.exception("Task failed", exc_info=task_result.error)

thread_manager.submit_task(
    ThreadPoolType.IO,
    load_data,
    callback=handle_result
)
```

## Multi-Monitor Support

```python
def get_screen_at_pos(pos):
    """Get screen containing position"""
    for screen in QApplication.screens():
        if screen.geometry().contains(pos):
            return screen
    return QApplication.primaryScreen()

# Center on current screen
screen = get_screen_at_pos(QCursor.pos())
overlay.move(
    screen.geometry().center() - overlay.rect().center()
)
```

## Color Customization

```python
# In QSS file, search for rgba() values

# Dark theme base
background-color: rgba(43, 43, 43, 0.8);

# Light theme base
background-color: rgba(212, 212, 212, 0.8);

# Change to your colors
background-color: rgba(R, G, B, Alpha);
```

## Common Object Names

### Overlays
- `overlayHostWindow` - Root overlay widget
- `borderOverlay` - Border frame (5px border)
- `overlayBackdrop` - Content backdrop

### Title Bar
- `titleBar` - Title bar frame
- `titleIcon` - App icon label
- `titleLabel` - Title text label
- `closeButton` - Close button

### Buttons
- `actionButton` - Primary action
- `selectButton` - Selection button
- `startButton` - Start/launch button
- `settingsButton` - Settings button
- `QSmolselect` - Toggle button
- `QSmolselectMini` - Mini toggle
- `QBasicBitchButton` - General button
- `QComboArrow` - Combo arrow (>>)

### Dialogs
- `subsettingsDialog` - Settings dialog
- `aboutDialog` - About dialog
- `settingsDialogBorder` - Border frame
- `aboutDialogBorder` - Border frame

## Common Pitfalls

### Qt Updates from Threads
```python
# ❌ Wrong - may crash
def worker():
    widget.setText("Updated")

# ✅ Right - safe
def worker():
    thread_manager.run_on_ui_thread(widget.setText, "Updated")
```

### Resource Cleanup
```python
# ❌ Wrong - manual tracking
resources = []
def cleanup():
    for r in resources:
        r.close()

# ✅ Right - ResourceManager
rm.register(resource, cleanup_handler=lambda r: r.close())
# Automatic cleanup on shutdown
```

### Event Coupling
```python
# ❌ Wrong - tight coupling
other_module.on_data_ready(data)

# ✅ Right - event bus
event_system.publish("data.ready", data=data)
```

### Settings Validation
```python
# ❌ Wrong - no validation
opacity = settings.get("opacity", 0.95)
widget.setWindowOpacity(opacity)  # May crash if invalid

# ✅ Right - validate
opacity = settings.get("opacity", 0.95)
opacity = max(0.1, min(1.0, opacity))  # Clamp
widget.setWindowOpacity(opacity)
```

## Performance Tips

1. **Use appropriate thread pool**: IO for files, COMPUTE for CPU work
2. **Batch UI updates**: Use UICoalescer for high-frequency updates
3. **Avoid blocking UI thread**: Submit heavy work to thread pools
4. **Use weak references**: Let ResourceManager use weakrefs
5. **Unsubscribe from events**: When component is destroyed
6. **Cache computed values**: Don't recalculate in loops

## Debug Helpers

```python
# List all resources
resources = rm.list_resources()
for r in resources:
    print(f"{r.resource_id}: {r.description}")

# Event history
events = es.get_event_history(limit=50)
for e in events:
    print(f"{e.timestamp}: {e.type}")

# Thread stats
stats = tm.get_stats()
print(stats)

# Settings dump
all_settings = sm.get_all()
print(all_settings)
```

---

For complete documentation, see:
- **docs/CORE_MODULES.md** - Full module docs
- **docs/THEME_GUIDE.md** - Theme customization
- **docs/OVERLAY_GUIDE.md** - Overlay patterns
