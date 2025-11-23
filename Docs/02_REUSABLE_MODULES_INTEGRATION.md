# Reusable Modules Integration Plan

> **Status (Cleaning Pass)**: All listed reusable modules have already been copied and adapted into the
> `core/`, `utils/`, and `themes/` packages. The original `MyReuseableUtilityModules/` directory has been
> removed/ignored; this document is retained as a historical reference for how that integration was done.

## Overview
The `MyReuseableUtilityModules/` directory contains production-tested modules from SPQDocker. These modules must be **copied and adapted** into the proper application structure, NOT edited in place.

## Modules to Adapt

### 1. ThreadManager ✅
**Source**: `MyReuseableUtilityModules/core/threading/manager.py`
**Destination**: `core/threading/manager.py`

**What It Provides**:
- Lock-free thread pool management
- Specialized pools: IO, COMPUTE, UI
- Task submission with callbacks
- Timer scheduling (single-shot and recurring)
- UI thread dispatch
- Graceful shutdown

**Adaptations Needed**:
- Update import paths (remove SPQDocker references)
- Adjust pool sizes for screensaver workload:
  - IO Pool: 4 workers (file scanning, RSS fetching)
  - COMPUTE Pool: N-1 workers (image processing)
  - Remove CAPTURE and RENDER pools (not needed)
- Add screensaver-specific task types if needed

**Usage in Screensaver**:
```python
# Image loading
thread_manager.submit_task(ThreadPoolType.IO, load_image, path, callback=on_loaded)

# Image processing
thread_manager.submit_task(ThreadPoolType.COMPUTE, process_image, pixmap, callback=on_processed)

# RSS fetching
thread_manager.submit_task(ThreadPoolType.IO, fetch_rss, url, callback=on_fetched)

# Weather updates
thread_manager.schedule_recurring(1800000, update_weather)  # Every 30 min

# Image rotation timer
thread_manager.single_shot(5000, next_image)  # Every 5 seconds
```

---

### 2. ResourceManager ✅
**Source**: `MyReuseableUtilityModules/core/resources/manager.py` + `types.py`
**Destination**: `core/resources/manager.py` + `types.py`

**What It Provides**:
- Centralized resource registration
- Deterministic cleanup ordering
- Type-safe resource tracking
- Weak reference support
- Custom cleanup handlers

**Adaptations Needed**:
- Update import paths
- Add screensaver-specific resource types:
  - `IMAGE_CACHE`: Cached QPixmap objects
  - `NETWORK_REQUEST`: RSS/weather HTTP requests
  - `TEMP_IMAGE`: Downloaded RSS images
- Keep existing types: GUI_COMPONENT, WINDOW, TIMER, FILE_HANDLE

**Usage in Screensaver**:
```python
# Register display widget
widget_id = resource_manager.register_qt(
    display_widget,
    ResourceType.GUI_COMPONENT,
    "Monitor 1 Display"
)

# Register cached image
cache_id = resource_manager.register(
    pixmap,
    ResourceType.IMAGE_CACHE,
    f"Cached: {image_path}",
    cleanup_handler=lambda p: p = None  # Allow GC
)

# Register temp RSS image
temp_id = resource_manager.register_temp_file(
    temp_path,
    "RSS Image",
    delete=True
)

# Automatic cleanup on shutdown
resource_manager.shutdown()
```

---

### 3. EventSystem ✅
**Source**: `MyReuseableUtilityModules/core/events/event_system.py` + `event_types.py`
**Destination**: `core/events/event_system.py` + `event_types.py`

**What It Provides**:
- Publish-subscribe event bus
- Priority-based handlers
- Event filtering
- UI thread dispatch
- Event history

**Adaptations Needed**:
- Update import paths
- Define screensaver-specific events in `event_types.py`:
  ```python
  # Image events
  IMAGE_LOADED = "image.loaded"
  IMAGE_READY = "image.ready"
  IMAGE_FAILED = "image.failed"
  IMAGE_QUEUE_EMPTY = "image.queue.empty"
  
  # Display events
  DISPLAY_READY = "display.ready"
  TRANSITION_STARTED = "transition.started"
  TRANSITION_COMPLETE = "transition.complete"
  
  # Monitor events
  MONITOR_CONNECTED = "monitor.connected"
  MONITOR_DISCONNECTED = "monitor.disconnected"
  
  # User events
  USER_INPUT = "user.input"
  EXIT_REQUEST = "exit.request"
  
  # Source events
  RSS_UPDATED = "rss.updated"
  RSS_FAILED = "rss.failed"
  WEATHER_UPDATED = "weather.updated"
  WEATHER_FAILED = "weather.failed"
  
  # Settings events
  SETTINGS_CHANGED = "settings.changed"
  ```

**Usage in Screensaver**:
```python
# Subscribe to events
event_system.subscribe(
    "image.loaded",
    engine.on_image_loaded,
    priority=100
)

event_system.subscribe(
    "transition.complete",
    engine.schedule_next_image,
    dispatch_on_ui=True
)

# Publish events
event_system.publish("image.ready", data={
    'pixmap': processed_pixmap,
    'metadata': image_metadata
})

event_system.publish("monitor.connected", data={
    'screen_id': screen.name(),
    'geometry': screen.geometry()
})
```

---

### 4. SettingsManager ✅
**Source**: `MyReuseableUtilityModules/core/settings/settings_manager.py` + `types.py`
**Destination**: `core/settings/settings_manager.py` + `types.py`

**What It Provides**:
- Type-safe configuration management
- QSettings backend integration
- Change notifications
- Default value handling
- Validation support

**Adaptations Needed**:
- Update import paths
- Define screensaver settings schema in `types.py`:
  ```python
  SETTINGS_SCHEMA = {
      'sources.folders': [],
      'sources.rss_feeds': [],
      'sources.mode': 'folders',  # 'folders', 'rss', 'both'
      
      'display.mode': 'fill',  # 'fill', 'fit', 'shrink'
      'display.pan_scan_enabled': False,
      'display.pan_scan_speed': 1.0,
      'display.pan_scan_zoom': 1.3,
      
      'transitions.type': 'crossfade',
      'transitions.duration': 1.0,
      'transitions.block_puzzle_grid': (6, 6),
      'transitions.block_puzzle_speed': 2.0,
      
      'timing.image_duration': 5.0,
      
      'widgets.clock_enabled': True,
      'widgets.clock_format': '24h',
      'widgets.clock_position': 'top-right',
      'widgets.clock_timezone': 'local',
      'widgets.clock_multiple': False,
      'widgets.clock_timezones': [],
      
      'widgets.weather_enabled': False,
      'widgets.weather_location': '',
      'widgets.weather_position': 'top-left',
      
      'multi_monitor.mode': 'same',  # 'same', 'different'
  }
  ```

**Usage in Screensaver**:
```python
# Load settings
settings_manager.load()

# Get with default
duration = settings_manager.get('timing.image_duration', 5.0)
transition = settings_manager.get('transitions.type', 'crossfade')

# Set and save
settings_manager.set('display.mode', 'fill')
settings_manager.save()

# Change notification
settings_manager.on_changed('transitions.type', on_transition_changed)
```

---

### 5. Logging System ✅
**Source**: `MyReuseableUtilityModules/core/logging/__init__.py`
**Destination**: `core/logging/logger.py`

**What It Provides**:
- Centralized logging configuration
- Rotating file handlers
- Console and file output
- Log level management

**Adaptations Needed**:
- Update import paths
- Configure for screensaver:
  - Log directory: `logs/`
  - Rotating logs: Max 10MB, keep 5 files
  - Format: `[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s`
  - Default level: INFO (DEBUG when --debug flag)
- Add screensaver-specific loggers:
  ```python
  ENGINE_LOGGER = "screensaver.engine"
  DISPLAY_LOGGER = "screensaver.display"
  SOURCE_LOGGER = "screensaver.source"
  TRANSITION_LOGGER = "screensaver.transition"
  UI_LOGGER = "screensaver.ui"
  ```

**Usage in Screensaver**:
```python
import logging
logger = logging.getLogger("screensaver.engine")

logger.info("Screensaver starting")
logger.debug(f"Loaded settings: {settings}")
logger.warning("RSS feed failed, falling back to cache")
logger.error("Failed to load image", exc_info=True)
```

---

### 6. Monitor Utilities (Partial) ⚠️
**Source**: `MyReuseableUtilityModules/utils/window/monitors.py`
**Destination**: `utils/monitors.py`

**What It Provides**:
- Multi-monitor enumeration
- Screen geometry utilities
- DPI awareness

**Adaptations Needed**:
- Extract only monitor-related functions
- Remove window-specific functionality
- Simplify for screensaver use case
- Use Qt's QScreen API primarily

**Usage in Screensaver**:
```python
from utils.monitors import get_all_screens, get_screen_geometry

screens = get_all_screens()
for screen in screens:
    geometry = get_screen_geometry(screen)
    print(f"Monitor: {screen.name()}, Size: {geometry.size()}")
```

---

### 7. Dark Theme ✅
**Source**: `MyReuseableUtilityModules/themes/dark.qss`
**Destination**: `themes/dark.qss`

**What It Provides**:
- Complete dark theme styling
- Overlay support
- Custom button styles
- Glass effect styling

**Adaptations Needed**:
- Copy as-is (no changes needed)
- Reference in settings dialog
- Apply at application startup

**Usage in Screensaver**:
```python
# In main.py or settings dialog
with open("themes/dark.qss", "r", encoding="utf-8") as f:
    app.setStyleSheet(f.read())
```

---

## Modules NOT Needed

### Hotkeys System ❌
- **Reason**: Screensaver doesn't need global hotkeys
- **Alternative**: Any mouse/keyboard input exits screensaver

### Lock-Free Data Structures ❌
- **Reason**: Qt's signals/slots and thread manager handle concurrency
- **Alternative**: Use Qt's thread-safe mechanisms

### Window Behavior Utilities ❌
- **Reason**: Screensaver uses fullscreen widgets, not managed windows
- **Alternative**: Qt's fullscreen mode

---

## Integration Checklist

### Phase 1: Core Systems
- [ ] Copy ThreadManager to `core/threading/`
- [ ] Update ThreadManager imports
- [ ] Remove unused pool types (CAPTURE, RENDER)
- [ ] Adjust pool sizes for screensaver
- [ ] Test ThreadManager with simple tasks

### Phase 2: Resource Management
- [ ] Copy ResourceManager to `core/resources/`
- [ ] Update ResourceManager imports
- [ ] Add screensaver-specific resource types
- [ ] Test resource registration and cleanup

### Phase 3: Event System
- [ ] Copy EventSystem to `core/events/`
- [ ] Update EventSystem imports
- [ ] Define screensaver events in event_types.py
- [ ] Test pub-sub with dummy handlers

### Phase 4: Settings
- [ ] Copy SettingsManager to `core/settings/`
- [ ] Update SettingsManager imports
- [ ] Define settings schema in types.py
- [ ] Test settings persistence

### Phase 5: Logging
- [ ] Copy logging utilities to `core/logging/`
- [ ] Configure rotating file handler
- [ ] Create logs/ directory
- [ ] Test logging from different modules

### Phase 6: Theme
- [ ] Copy dark.qss to `themes/`
- [ ] Test theme loading
- [ ] Verify all UI elements render correctly

### Phase 7: Utilities
- [ ] Extract monitor utilities to `utils/monitors.py`
- [ ] Test multi-monitor detection
- [ ] Verify screen geometry calculations

---

## Import Path Updates

### Before (in MyReuseableUtilityModules)
```python
from core.threading import ThreadManager
from core.resources import ResourceManager
from core.events import EventSystem
from core.settings import SettingsManager
```

### After (in ShittyRandomPhotoScreenSaver)
```python
from core.threading import ThreadManager
from core.resources import ResourceManager
from core.events import EventSystem
from core.settings import SettingsManager
```

**Note**: Import paths remain the same because we're maintaining the `core/` structure!

---

## Testing After Integration

### Unit Tests
```python
# tests/test_threading.py
def test_thread_manager_initialization():
    tm = ThreadManager()
    assert tm is not None
    tm.shutdown()

# tests/test_resources.py
def test_resource_registration():
    rm = ResourceManager()
    rid = rm.register(object(), ResourceType.CUSTOM, "Test")
    assert rm.get(rid) is not None
    rm.shutdown()

# tests/test_events.py
def test_event_publish_subscribe():
    es = EventSystem()
    received = []
    es.subscribe("test.event", lambda e: received.append(e))
    es.publish("test.event", data={"test": True})
    assert len(received) == 1

# tests/test_settings.py
def test_settings_persistence():
    sm = SettingsManager()
    sm.set("test.key", "test_value")
    sm.save()
    assert sm.get("test.key") == "test_value"
```

---

## Completion Marker

**When all modules are integrated and tested**, update this section:

```
✅ REUSABLE MODULES INTEGRATION COMPLETE

All modules have been successfully adapted from MyReuseableUtilityModules/ 
to the proper application structure. The MyReuseableUtilityModules/ directory 
can now be:
1. Deleted, OR
2. Added to .gitignore

Date Completed: [TO BE FILLED]
Completed By: [TO BE FILLED]
```

---

**Next Document**: `03_CORE_IMPLEMENTATION.md` - Core infrastructure implementation details
