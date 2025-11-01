# Core Modules Guide

This document explains how to use the centralized core modules for threading, resource management, events, and settings.

## Table of Contents

1. [ThreadManager](#threadmanager)
2. [ResourceManager](#resourcemanager)
3. [EventSystem](#eventsystem)
4. [SettingsManager](#settingsmanager)
5. [Integration Patterns](#integration-patterns)

---

## ThreadManager

Centralized thread management with specialized pools for different workload types.

### Overview

The ThreadManager provides:
- **Lock-free design**: No raw mutexes or locks
- **Specialized pools**: CAPTURE, RENDER, IO, COMPUTE, UI
- **UI thread dispatch**: Safe cross-thread communication
- **Resource tracking**: Automatic cleanup integration
- **Task prioritization**: Priority-based execution
- **Statistics**: Real-time performance monitoring

### Basic Usage

```python
from core.threading import ThreadManager, ThreadPoolType, TaskPriority

# Get or create the thread manager
thread_manager = ThreadManager()

# Submit a task to a specific pool
task_id = thread_manager.submit_task(
    ThreadPoolType.IO,
    my_io_function,
    arg1, arg2,
    priority=TaskPriority.NORMAL,
    callback=on_complete
)

# Run something on the UI thread
thread_manager.run_on_ui_thread(update_ui, data)

# Single-shot timer (runs once after delay)
thread_manager.single_shot(1000, delayed_function)  # 1000ms = 1 second

# Recurring timer
timer_id = thread_manager.schedule_recurring(
    500,  # every 500ms
    periodic_function
)

# Cancel a timer
thread_manager.cancel_timer(timer_id)
```

### Thread Pool Types

```python
class ThreadPoolType(Enum):
    CAPTURE = "capture"  # Screen capture (DWM, DXGI) - 2 workers default
    RENDER = "render"    # Graphics rendering (OpenGL, D3D11) - 1 worker
    IO = "io"           # File I/O, network - 4 workers
    COMPUTE = "compute"  # CPU-intensive - (CPU_COUNT - 1) workers
    UI = "ui"           # UI background tasks - 2 workers
```

### Task Results

```python
def handle_result(task_result):
    if task_result.success:
        print(f"Result: {task_result.result}")
        print(f"Took: {task_result.execution_time}s")
    else:
        print(f"Error: {task_result.error}")

thread_manager.submit_task(
    ThreadPoolType.COMPUTE,
    heavy_computation,
    callback=handle_result
)
```

### UI Coalescing

Batch multiple UI updates to reduce flicker:

```python
# Create a coalescer for a specific operation
ui_coalescer = thread_manager.create_ui_coalescer()

# Schedule updates (only the last one within 16ms executes)
ui_coalescer.schedule(update_position, x, y)
ui_coalescer.schedule(update_position, x2, y2)
ui_coalescer.schedule(update_position, x3, y3)  # Only this one runs

# Manual flush if needed
ui_coalescer.flush()
```

### Custom Pool Configuration

```python
from core.threading import ThreadManager, ThreadPoolType

config = {
    ThreadPoolType.CAPTURE: 4,   # More capture threads
    ThreadPoolType.COMPUTE: 8,   # More compute threads
    ThreadPoolType.RENDER: 1,    # Keep single-threaded
}

thread_manager = ThreadManager(config=config)
```

### Shutdown

```python
# Graceful shutdown (waits for tasks to complete)
thread_manager.shutdown()

# Or register with ResourceManager for automatic cleanup
resource_manager.register(
    thread_manager,
    ResourceType.CUSTOM,
    "Thread manager",
    cleanup_handler=lambda tm: tm.shutdown()
)
```

### Best Practices

1. **Use appropriate pools**:
   - `CAPTURE` for screen capture operations
   - `RENDER` for OpenGL/D3D operations (single-threaded!)
   - `IO` for file/network operations
   - `COMPUTE` for CPU-intensive work
   - `UI` for lightweight background UI tasks

2. **Always use callbacks** instead of blocking on futures

3. **UI thread dispatch**:
   ```python
   # Wrong - may crash Qt
   some_widget.setText("Updated")
   
   # Right - safe from any thread
   thread_manager.run_on_ui_thread(some_widget.setText, "Updated")
   ```

4. **Avoid blocking operations** in callbacks

5. **Use UI coalescing** for high-frequency updates (positions, progress bars)

---

## ResourceManager

Centralized resource lifecycle management with automatic cleanup.

### Overview

The ResourceManager provides:
- **Weak references**: Resources can be garbage collected normally
- **Deterministic cleanup**: Predictable cleanup order
- **Custom handlers**: Per-resource cleanup functions
- **Type-safe access**: `get_typed()` with type checking
- **Metadata tracking**: Store arbitrary metadata
- **Qt integration**: UI-thread-safe cleanup for Qt objects

### Basic Usage

```python
from core.resources import ResourceManager, ResourceType

# Get or create the resource manager
resource_manager = ResourceManager()

# Register a resource
resource_id = resource_manager.register(
    my_file_handle,
    ResourceType.FILE_HANDLE,
    "Configuration file",
    cleanup_handler=lambda f: f.close()
)

# Get a resource back
file_handle = resource_manager.get(resource_id)

# Type-safe retrieval
from pathlib import Path
file_handle = resource_manager.get_typed(resource_id, Path)

# Unregister and cleanup
resource_manager.unregister(resource_id)
```

### Resource Types

```python
class ResourceType(Enum):
    GUI_COMPONENT = "gui_component"          # Qt widgets
    WINDOW = "window"                        # Qt windows
    TIMER = "timer"                          # Qt timers
    THREAD_POOL = "thread_pool"             # Thread executors
    FILE_HANDLE = "file_handle"             # File handles
    NETWORK_CONNECTION = "network"           # Sockets, connections
    DATABASE_CONNECTION = "database"         # DB connections
    WINDOW_MANAGER = "window_manager"        # Window management
    CUSTOM = "custom"                        # Custom resources
    UNKNOWN = "unknown"                      # Unspecified
```

### Cleanup Ordering

Resources are cleaned up in deterministic order:

1. **Qt objects** (GUI_COMPONENT, TIMER, WINDOW)
2. **Network/Database** (NETWORK_CONNECTION, DATABASE_CONNECTION)
3. **OpenGL** (resources with `gl=True` metadata)
4. **Filesystem** (FILE_HANDLE)
5. **Other** (CUSTOM, UNKNOWN)

Within each group, resources with lower `cleanup_priority` metadata are cleaned first.

### Qt Object Registration

```python
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer

# Register a Qt widget (auto deleteLater on cleanup)
widget_id = resource_manager.register_qt(
    my_widget,
    ResourceType.GUI_COMPONENT,
    "My widget"
)

# Register a Qt timer (auto stop + deleteLater)
timer_id = resource_manager.register_qt_timer(
    my_timer,
    "Polling timer"
)

# Register a Qt thread (auto quit + wait + deleteLater)
thread_id = resource_manager.register_qt_thread(
    my_qthread,
    "Worker thread"
)
```

### File Handling

```python
# Simple file handle
file_id = resource_manager.register_file(
    open("data.txt", "r"),
    "Data file"
)

# Temporary file (auto-delete on cleanup)
temp_id = resource_manager.register_temp_file(
    "/tmp/temp_data.txt",
    "Temporary data",
    delete=True
)

# Temporary directory (recursive delete on cleanup)
temp_dir_id = resource_manager.register_temp_dir(
    "/tmp/my_temp_dir",
    "Temporary directory",
    ignore_errors=True
)
```

### OpenGL Resources

```python
from OpenGL.GL import glDeleteTextures, glIsTexture

# Register an OpenGL texture
texture_id = resource_manager.register_gl_texture(
    texture_handle,
    make_current=lambda: gl_context.makeCurrent(surface),
    done_current=lambda: gl_context.doneCurrent(),
    "Scene texture"
)

# Register with liveness check
texture_id = resource_manager.register_gl_texture(
    texture_handle,
    is_alive=glIsTexture,
    make_current=activate_context,
    done_current=deactivate_context,
    "Cached texture"
)
```

### Custom Cleanup

```python
class MyResource:
    def __init__(self):
        self.data = allocate_data()
    
    def cleanup(self):
        free_data(self.data)
        self.data = None

# Register with custom cleanup
resource_id = resource_manager.register(
    MyResource(),
    ResourceType.CUSTOM,
    "My resource",
    cleanup_handler=lambda r: r.cleanup(),
    metadata={"priority": 100, "category": "cache"}
)
```

### Metadata

```python
# Register with metadata
resource_id = resource_manager.register(
    my_resource,
    ResourceType.CUSTOM,
    "Tagged resource",
    tags={"cache", "volatile"},
    category="rendering",
    cleanup_priority=50,
    gl=True  # OpenGL resource flag
)

# Query metadata
info = resource_manager.get_resource_info(resource_id)
print(info.metadata)  # {'tags': ['cache', 'volatile'], 'category': 'rendering', ...}
```

### Listing Resources

```python
# List all resources
all_resources = resource_manager.list_resources()

# Filter by type
qt_widgets = resource_manager.list_resources(ResourceType.GUI_COMPONENT)
file_handles = resource_manager.list_resources(ResourceType.FILE_HANDLE)

# Check existence
if resource_manager.exists(resource_id):
    print("Resource still alive")
```

### Best Practices

1. **Always register resources** that need cleanup
2. **Use appropriate resource types** for correct cleanup ordering
3. **Provide descriptive names** for debugging
4. **Use Qt-specific registration** for Qt objects
5. **Set cleanup_priority** for inter-dependent resources
6. **Let weak references work**: Don't prevent garbage collection
7. **Use metadata** for categorization and filtering

---

## EventSystem

Publish-subscribe event bus for inter-module communication.

### Overview

The EventSystem provides:
- **Decoupled communication**: Modules don't need direct references
- **Priority dispatch**: Higher priority subscribers run first
- **Event filtering**: Per-subscription filter functions
- **Wildcard subscriptions**: Subscribe to event patterns
- **Event history**: Debug and trace event flow
- **UI thread dispatch**: Optional UI-thread callback execution

### Basic Usage

```python
from core.events import EventSystem, Event

# Get or create the event system
event_system = EventSystem()

# Subscribe to events
def on_window_created(event: Event):
    print(f"Window created: {event.data}")

subscription_id = event_system.subscribe(
    "window.created",
    on_window_created
)

# Publish events
event_system.publish(
    "window.created",
    data={"hwnd": 12345, "title": "My Window"}
)

# Unsubscribe
event_system.unsubscribe(subscription_id)
```

### Event Types

```python
from core.events.event_types import EventType

# Use predefined event types
event_system.subscribe(EventType.WINDOW_CREATED, callback)

# Or custom strings
event_system.subscribe("my.custom.event", callback)
```

### Priority Dispatch

```python
# Higher priority runs first
high_priority_id = event_system.subscribe(
    "app.startup",
    early_handler,
    priority=100
)

low_priority_id = event_system.subscribe(
    "app.startup",
    late_handler,
    priority=10
)

# When published, early_handler runs before late_handler
event_system.publish("app.startup")
```

### Event Filtering

```python
# Only receive events matching the filter
def only_errors(event: Event) -> bool:
    return event.data.get("level") == "error"

event_system.subscribe(
    "log.message",
    handle_error,
    filter_fn=only_errors
)
```

### Wildcard Subscriptions

```python
# Match all window events
event_system.subscribe("window.*", handle_any_window_event)

# Match all events
event_system.subscribe("*", log_all_events)
```

### UI Thread Dispatch

```python
# Callback will be invoked on UI thread
event_system.subscribe(
    "data.updated",
    update_ui_widget,
    dispatch_on_ui=True
)

# Safe to update Qt widgets in the callback
def update_ui_widget(event: Event):
    widget.setText(event.data["text"])
```

### Event Objects

```python
class Event:
    type: str           # Event type
    data: Any           # Event data
    id: str             # Unique event ID
    timestamp: float    # Creation timestamp
    source: Any         # Event source object
    is_handled: bool    # Consumption flag

# Custom event classes
from core.events.event_types import Event

class WindowEvent(Event):
    @property
    def hwnd(self):
        return self.data.get("hwnd")
    
    @property
    def title(self):
        return self.data.get("title")

# Publish with custom class
event_system.publish(
    "window.created",
    data={"hwnd": 12345, "title": "My Window"},
    event_class=WindowEvent
)
```

### Event Consumption

```python
def exclusive_handler(event: Event):
    # Handle the event
    process_event(event)
    
    # Mark as handled to stop propagation
    event.is_handled = True

event_system.subscribe("important.event", exclusive_handler, priority=100)
event_system.subscribe("important.event", fallback_handler, priority=50)

# Only exclusive_handler will run
event_system.publish("important.event")
```

### Waiting for Events

```python
# Wait for a specific event with timeout
event = event_system.wait_for(
    "computation.complete",
    timeout=5.0  # seconds
)

if event:
    print(f"Completed: {event.data}")
else:
    print("Timeout!")

# Wait with condition
def is_success(event: Event) -> bool:
    return event.data.get("status") == "success"

event = event_system.wait_for(
    "task.complete",
    timeout=10.0,
    condition=is_success
)
```

### Event History

```python
# Get recent events for debugging
recent_events = event_system.get_event_history(limit=50)

for event in recent_events:
    print(f"{event.timestamp}: {event.type} - {event.data}")

# Clear history
event_system.clear_event_history()
```

### Best Practices

1. **Use descriptive event types**: `"window.created"` not `"wc"`
2. **Namespaces with dots**: `"module.action.detail"`
3. **Avoid blocking** in event handlers
4. **Use priority** for ordering dependencies
5. **Use filters** instead of conditional logic in handlers
6. **Unsubscribe** when no longer needed
7. **Use UI dispatch** for Qt widget updates
8. **Mark events handled** to stop propagation when needed

---

## SettingsManager

Type-safe JSON-based configuration with hot-reload support.

### Overview

The SettingsManager provides:
- **JSON persistence**: Human-readable configuration files
- **Type-safe access**: Automatic type conversion
- **Change notifications**: React to setting changes
- **Fallback hierarchy**: Multiple config file locations
- **Validation**: Type checking on set operations
- **Hot reload**: Runtime configuration updates
- **Thread-safe**: UI-thread-enforced operations

### Basic Usage

```python
from core.settings import SettingsManager

# Get the singleton instance
settings = SettingsManager()

# Get settings with defaults
window_width = settings.get("window.width", 800)
theme = settings.get("appearance.theme", "dark")
enabled = settings.get("features.auto_save", True)

# Set settings
settings.set("window.width", 1024)
settings.set("appearance.theme", "light")
settings.set("features.auto_save", False)

# Save to disk
settings.save()
```

### Setting Structure

Recommended structure with dotted keys:

```python
settings = {
    "appearance": {
        "theme": "dark",
        "font_size": 12,
        "opacity": 0.95
    },
    "behavior": {
        "auto_save": True,
        "save_interval": 300
    },
    "hotkeys": {
        "quickswitch": "shift+x",
        "hide_show": "ctrl+shift+h"
    },
    "features": {
        "experimental_feature": False
    }
}

# Access with dotted notation
theme = settings.get("appearance.theme")
auto_save = settings.get("behavior.auto_save")
```

### Change Notifications

```python
# Subscribe to setting changes
def on_theme_changed(key, new_value, old_value):
    print(f"Theme changed: {old_value} → {new_value}")
    apply_theme(new_value)

settings.on_changed("appearance.theme", on_theme_changed)

# Wildcard subscriptions
def on_any_appearance_change(key, new_value, old_value):
    print(f"Appearance setting changed: {key}")

settings.on_changed("appearance.*", on_any_appearance_change)

# Global change handler
def on_any_change(key, new_value, old_value):
    print(f"Setting changed: {key} = {new_value}")

settings.on_changed("*", on_any_change)
```

### Type Conversion

```python
# Automatic type conversion based on default
width = settings.get("window.width", 800)  # Returns int
opacity = settings.get("window.opacity", 0.8)  # Returns float
enabled = settings.get("auto_save", True)  # Returns bool
theme = settings.get("theme", "dark")  # Returns str

# Type validation on set
settings.set("window.width", "1024")  # Converted to int
settings.set("window.opacity", 95)  # Converted to float (0.95)
settings.set("auto_save", "true")  # Converted to bool
```

### File Location Hierarchy

Settings are loaded from the first existing file in this order:

1. **Explicit path**: `settings_file` parameter (for tests)
2. **Primary**: `<runtime_root>/settings/settings.json`
3. **Fallback**: `<executable_dir>/settings.json`
4. **Last resort**: `~/.appname/settings.json`

```python
# Explicit path (for testing)
settings = SettingsManager(settings_file="/tmp/test_settings.json")

# Query current location
print(settings.get_settings_file())
```

### Defaults

```python
# Define comprehensive defaults
default_settings = {
    "appearance": {
        "theme": "dark",
        "font_family": "Segoe UI",
        "font_size": 12,
        "opacity": 0.95
    },
    "behavior": {
        "auto_save": True,
        "save_interval": 300,
        "startup_minimized": False
    },
    "hotkeys": {
        "quickswitch": "shift+x",
        "hide_show": "ctrl+shift+h",
        "opacity_up": "ctrl+plus",
        "opacity_down": "ctrl+minus"
    }
}

# Set defaults
settings.set_defaults(default_settings)

# Reset to defaults
settings.reset_to_defaults()

# Reset specific section
settings.reset_to_defaults(section="hotkeys")
```

### Validation

```python
# Custom validators
def validate_opacity(value):
    if not 0.1 <= value <= 1.0:
        raise ValueError("Opacity must be between 0.1 and 1.0")
    return value

settings.add_validator("window.opacity", validate_opacity)

# Validation runs on set
settings.set("window.opacity", 1.5)  # Raises ValueError
```

### Batch Updates

```python
# Update multiple settings atomically
with settings.batch_update():
    settings.set("window.width", 1024)
    settings.set("window.height", 768)
    settings.set("window.x", 100)
    settings.set("window.y", 100)
# Only one change notification and one save

# Or use update_many
settings.update_many({
    "window.width": 1024,
    "window.height": 768,
    "window.x": 100,
    "window.y": 100
})
```

### Hot Reload

```python
# Reload from disk (picks up external changes)
settings.reload()

# Auto-reload on file changes
settings.enable_auto_reload(interval=1.0)  # Check every second
```

### Thread Safety

All operations are automatically dispatched to the UI thread:

```python
# Safe from any thread
thread_manager.submit_task(
    ThreadPoolType.IO,
    lambda: settings.set("last_saved", time.time())
)
```

### Testing

```python
# Reset singleton for test isolation
SettingsManager._reset_for_testing()

# Use temporary settings file
import tempfile
temp_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
settings = SettingsManager(settings_file=temp_file.name)

# Clean up after test
settings.shutdown()
os.unlink(temp_file.name)
```

### Best Practices

1. **Use dotted notation** for hierarchical settings
2. **Always provide defaults** in `get()` calls
3. **Define comprehensive defaults** upfront
4. **Use change notifications** for reactive updates
5. **Validate user input** before setting
6. **Use batch updates** for multiple related changes
7. **Save explicitly** after critical changes (auto-save on shutdown)

---

## Integration Patterns

### Full Framework Bootstrap

```python
# main.py
from core.application.bootstrap import bootstrap_application
from PySide6.QtWidgets import QMainWindow

def main():
    app = bootstrap_application(
        app_name="MyApp",
        theme="dark",
        log_level="INFO"
    )
    
    # All core systems are initialized:
    # - ThreadManager
    # - ResourceManager
    # - EventSystem
    # - SettingsManager
    # - Logging
    
    window = QMainWindow()
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
```

### Manual Integration

```python
# Manual setup without bootstrap
from core.threading import ThreadManager
from core.resources import ResourceManager
from core.events import EventSystem
from core.settings import SettingsManager

# Order matters!
resource_manager = ResourceManager()
thread_manager = ThreadManager(resource_manager=resource_manager)
event_system = EventSystem()
settings = SettingsManager()

# Register for automatic cleanup
resource_manager.register(thread_manager, ...)
resource_manager.register(event_system, ...)

# Your application code...

# Shutdown (reverse order)
settings.save()
event_system.shutdown()
thread_manager.shutdown()
resource_manager.shutdown()
```

### Singleton Pattern

```python
# Get singleton instances
from core.threading import get_thread_manager
from core.resources import get_resource_manager
from core.events import get_event_system
from core.settings import get_settings_manager

thread_manager = get_thread_manager()
resource_manager = get_resource_manager()
event_system = get_event_system()
settings = get_settings_manager()
```

### Service Locator Pattern

```python
from core.application.service_locator import ServiceLocator

# Register services
locator = ServiceLocator()
locator.register("thread_manager", thread_manager)
locator.register("resource_manager", resource_manager)
locator.register("event_system", event_system)

# Retrieve services
tm = locator.get("thread_manager")
```

### Dependency Injection

```python
class MyService:
    def __init__(self, thread_manager, resource_manager, event_system):
        self.thread_manager = thread_manager
        self.resource_manager = resource_manager
        self.event_system = event_system
        
        # Register self for cleanup
        self.resource_id = resource_manager.register(
            self,
            ResourceType.CUSTOM,
            "MyService instance",
            cleanup_handler=lambda s: s.shutdown()
        )
    
    def do_work(self):
        # Use injected dependencies
        self.thread_manager.submit_task(
            ThreadPoolType.COMPUTE,
            self._compute
        )
    
    def _compute(self):
        # Heavy work...
        self.event_system.publish("work.complete", data=result)
    
    def shutdown(self):
        # Cleanup
        pass

# Create with DI
service = MyService(
    thread_manager=get_thread_manager(),
    resource_manager=get_resource_manager(),
    event_system=get_event_system()
)
```

### Complete Application Example

```python
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton
from core.threading import ThreadManager, ThreadPoolType
from core.resources import ResourceManager, ResourceType
from core.events import EventSystem
from core.settings import SettingsManager

class MainWindow(QMainWindow):
    def __init__(self, thread_manager, resource_manager, event_system, settings):
        super().__init__()
        self.thread_manager = thread_manager
        self.resource_manager = resource_manager
        self.event_system = event_system
        self.settings = settings
        
        # Register window for cleanup
        self.resource_id = resource_manager.register_qt(
            self,
            ResourceType.WINDOW,
            "Main window"
        )
        
        # Subscribe to events
        self.sub_id = event_system.subscribe(
            "data.updated",
            self.on_data_updated,
            dispatch_on_ui=True
        )
        
        # Setup UI
        button = QPushButton("Load Data", self)
        button.clicked.connect(self.load_data)
        self.setCentralWidget(button)
        
        # Load settings
        geometry = settings.get("window.geometry")
        if geometry:
            self.restoreGeometry(geometry)
    
    def load_data(self):
        # Submit background task
        self.thread_manager.submit_task(
            ThreadPoolType.IO,
            self._load_data_async,
            callback=self.on_load_complete
        )
    
    def _load_data_async(self):
        # Heavy I/O operation
        import time
        time.sleep(2)
        return {"data": "loaded"}
    
    def on_load_complete(self, result):
        if result.success:
            # Publish event
            self.event_system.publish("data.updated", data=result.result)
    
    def on_data_updated(self, event):
        # UI update (safe - dispatched on UI thread)
        print(f"Data updated: {event.data}")
    
    def closeEvent(self, event):
        # Save settings
        self.settings.set("window.geometry", self.saveGeometry())
        self.settings.save()
        
        # Unsubscribe
        self.event_system.unsubscribe(self.sub_id)
        
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    # Initialize core systems
    resource_manager = ResourceManager()
    thread_manager = ThreadManager(resource_manager=resource_manager)
    event_system = EventSystem()
    settings = SettingsManager()
    
    # Create main window
    window = MainWindow(thread_manager, resource_manager, event_system, settings)
    window.show()
    
    # Run application
    result = app.exec()
    
    # Cleanup (automatic with ResourceManager)
    resource_manager.shutdown()
    
    return result

if __name__ == "__main__":
    sys.exit(main())
```

This example demonstrates:
- Dependency injection of core services
- Resource registration for automatic cleanup
- Background task execution with callbacks
- Event-driven communication
- Settings persistence
- Thread-safe UI updates
- Proper shutdown sequence
