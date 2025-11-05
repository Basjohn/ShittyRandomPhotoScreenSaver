# ShittyRandomPhotoScreenSaver - Module Index

**Purpose**: Living file map of all modules, their purposes, and key classes/functions.  
**Last Updated**: Day 4 Complete (Core + Infrastructure + Image Sources + Animation)  
**Implementation Status**: 🟢 Core Framework | 🟢 Animation | 🟢 Entry Point & Monitors | 🟢 Image Sources | ⚪ Engine | ⚪ Display | ⚪ UI  
**Note**: Update this file after any major structural changes.

---

## Entry Point

### `main.py` 🟢 COMPLETE
**Purpose**: Application entry point and command-line handling  
**Status**: ✅ Implemented, ✅ Tested  
**Key Functions**:
- `parse_screensaver_args()` - Parse Windows screensaver arguments (/s, /c, /p <hwnd>)
- `main()` - Main application entry point with logging and QApplication setup

**Key Enums**:
- `ScreensaverMode` - RUN, CONFIG, PREVIEW

**Features**: 
- Command-line argument parsing with fallback to RUN mode
- Debug mode support (--debug or -d flags)
- Colored logging output in debug mode
- Proper logging initialization
- Mode routing (RUN, CONFIG, PREVIEW placeholders)

**Dependencies**: Core logging, Qt Application  
**Implemented**: Day 2

---

## Core Framework (`core/`) 🟢 IMPLEMENTED

### `core/threading/manager.py` 🟢 COMPLETE
**Purpose**: Lock-free thread pool management  
**Status**: ✅ Implemented, ✅ Tested (5 tests passing)  
**Key Classes**:
- `ThreadManager` - Main thread manager
  - `submit_task(pool_type, func, *args, callback=None)` - Submit async task
  - `run_on_ui_thread(func, *args)` - Execute on UI thread
  - `single_shot(delay_ms, func)` - Single-shot timer
  - `schedule_recurring(interval_ms, func)` - Recurring timer
  - `shutdown()` - Graceful shutdown

**Key Enums**:
- `ThreadPoolType` - IO, COMPUTE

**Adapted From**: `MyReuseableUtilityModules/core/threading/manager.py`  
**Tests**: `tests/test_threading.py`

---

### `core/resources/manager.py` 🟢 COMPLETE
**Purpose**: Deterministic resource cleanup  
**Status**: ✅ Implemented, ✅ Tested (6 tests passing)  
**Key Classes**:
- `ResourceManager` - Centralized resource registration
  - `register(resource, type, description, cleanup_handler=None)` - Register resource
  - `register_qt(widget, type, description)` - Register Qt widget
  - `register_temp_file(path, description, delete=True)` - Register temp file
  - `get(resource_id)` - Get resource by ID
  - `unregister(resource_id)` - Unregister and cleanup
  - `shutdown()` - Cleanup all resources

**Features**: Strong/weak reference support, Qt widget cleanup, temp file management  
**Adapted From**: `MyReuseableUtilityModules/core/resources/manager.py`  
**Tests**: `tests/test_resources.py`

---

### `core/resources/types.py` 🟢 COMPLETE
**Purpose**: Resource type definitions  
**Status**: ✅ Implemented  
**Key Enums**:
- `ResourceType` - GUI_COMPONENT, WINDOW, TIMER, FILE_HANDLE, NETWORK_CONNECTION, IMAGE_CACHE, TEMP_IMAGE

**Adapted From**: `MyReuseableUtilityModules/core/resources/types.py`

---

### `core/events/event_system.py` 🟢 COMPLETE
**Purpose**: Publish-subscribe event bus  
**Status**: ✅ Implemented, ✅ Tested (6 tests passing)  
**Key Classes**:
- `EventSystem` - Event coordination
  - `subscribe(event_type, handler, priority=50, filter_fn=None)` - Subscribe to event
  - `publish(event_type, data=None)` - Publish event
  - `unsubscribe(subscription_id)` - Unsubscribe
  - `get_event_history(limit=100)` - Get event history

**Features**: Priority-based ordering, event filtering, history tracking  
**Adapted From**: `MyReuseableUtilityModules/core/events/event_system.py`  
**Tests**: `tests/test_events.py`

---

### `core/events/event_types.py` 🟢 COMPLETE
**Purpose**: Event type definitions  
**Status**: ✅ Implemented  
**Key Constants**:
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

---

### `core/settings/settings_manager.py` 🟢 COMPLETE
**Purpose**: Persistent configuration management  
**Status**: ✅ Implemented, ✅ Tested (6 tests passing)  
**Key Classes**:
- `SettingsManager` - Configuration handling (QSettings-based)
  - `get(key, default=None)` - Get setting value
  - `set(key, value)` - Set setting value
  - `save()` - Persist to disk
  - `load()` - Load from disk
  - `on_changed(key, handler)` - Change notification
  - `reset_to_defaults()` - Reset all settings

**Features**: Automatic defaults, change notifications, QSettings persistence  
**Adapted From**: `MyReuseableUtilityModules/core/settings/settings_manager.py`  
**Tests**: `tests/test_settings.py`

---

### `core/logging/logger.py` 🟢 COMPLETE
**Purpose**: Centralized logging configuration  
**Status**: ✅ Implemented  
**Key Functions**:
- `setup_logging(debug=False)` - Configure application logging with file rotation
- `ColoredFormatter` - ANSI colored console output for debug mode

**Features**: 
- Rotating file handler (10MB, 5 backups)
- Colored console output in debug mode (cyan=DEBUG, green=INFO, yellow=WARNING, red=ERROR, magenta=CRITICAL)
- Logs stored in `logs/screensaver.log`

**Key Loggers**:
- `screensaver.engine` - Engine logs
- `screensaver.display` - Display logs
- `screensaver.source` - Source logs
- `screensaver.transition` - Transition logs
- `screensaver.ui` - UI logs

**Adapted From**: `MyReuseableUtilityModules/core/logging/`

---

### `core/animation/` 🟢 COMPLETE
**Purpose**: Centralized animation framework for ALL animations  
**Status**: ✅ Implemented, ✅ Tested (10 tests passing)  
**Key Classes**:
- `AnimationManager` - Centralized animation coordinator
  - `animate_property(target, property, start, end, duration, easing)` - Animate property value
  - `create_animation_group(animations, parallel=True)` - Group animations
  - `cancel_animation(animation_id)` - Cancel running animation
  - `pause_animation(animation_id)` - Pause animation
  - `resume_animation(animation_id)` - Resume paused animation
- `Animator` - Base animator class
  - Delta-time based updates (FPS independent)
  - Easing curve support
  - Event callbacks (onStart, onUpdate, onComplete, onCancel)
- `EasingCurve` - Easing function enum

**Key Enums**:
- `EasingCurve` - LINEAR, QUAD_IN, QUAD_OUT, QUAD_IN_OUT, CUBIC, SINE, EXPO, ELASTIC, BOUNCE, BACK
- `AnimationType` - PROPERTY, CUSTOM, GROUP
- `AnimationState` - IDLE, RUNNING, PAUSED, COMPLETE, CANCELLED

**Features**:
- Centralized management of ALL animations (transitions, UI, widgets)
- FPS-independent timing with delta-time
- Complete easing curve library
- Animation groups (parallel/sequential)
- Resource integration (auto-cleanup via ResourceManager)
- Event integration (publishes animation.started, animation.progress, animation.complete)
- No raw QPropertyAnimation or QTimer allowed anywhere else

**Used By**:
- All transition effects (crossfade, slide, diffuse, block puzzle)
- Settings dialog transitions
- Widget animations (clock fade, weather updates)
- Any custom animations

**Implemented**: Day 4  
**Tests**: `tests/test_animation.py`

---

## Image Sources (`sources/`) 🟢 IMPLEMENTED

### `sources/base_provider.py` 🟢 COMPLETE
**Purpose**: Abstract base classes for image providers  
**Status**: ✅ Implemented, ✅ Tested  
**Key Classes**:
- `ImageMetadata` - Dataclass for image metadata
  - `is_local()` - Check if image is local
  - `is_remote()` - Check if image is remote
  - `get_display_name()` - Get human-readable name
- `ImageProvider` (ABC) - Abstract base for all image sources
  - `get_images()` - Get all available images (abstract)
  - `refresh()` - Refresh image list (abstract)
  - `is_available()` - Check source availability (abstract)
  - `get_source_info()` - Get source metadata

**Key Enums**:
- `ImageSourceType` - FOLDER, RSS, CUSTOM

**Features**: Flexible metadata structure supporting both local and remote images  
**Implemented**: Day 3

---

### `sources/folder_source.py` 🟢 COMPLETE
**Purpose**: Scan local folders for images  
**Status**: ✅ Implemented, ✅ Tested (137 images scanned in 0.03s)  
**Key Classes**:
- `FolderSource(ImageProvider)` - Folder-based image provider
  - `get_images()` - Get all images from folder
  - `refresh()` - Rescan folder
  - `is_available()` - Check folder exists and readable
  - `get_source_info()` - Get folder metadata
  - `get_supported_extensions()` - Get supported image formats

**Features**:
- Recursive and non-recursive scanning
- Supports jpg, jpeg, png, bmp, gif, webp, tiff, tif, ico, jfif
- Automatic metadata extraction (file size, timestamps, format)
- Permission error handling
- Fast scanning with caching

**Implemented**: Day 3

---

### `sources/rss_source.py` ⚪ NOT IMPLEMENTED
**Purpose**: RSS feed image source  
**Key Classes**:
- `RSSSource(ImageProvider)` - RSS feed-based provider
  - Parse RSS feeds for images
  - Download and cache images
  - Handle feed errors

**Planned**: Optional (Day 4 or later)

---

## Engine (`engine/`) ⚪ NOT IMPLEMENTED

### `engine/screensaver_engine.py`
**Purpose**: Main screensaver controller  
**Key Classes**:
- `ScreensaverEngine` - Central orchestrator
  - `start()` - Start screensaver
  - `stop()` - Stop screensaver
  - `_initialize_sources()` - Setup image sources
  - `_build_image_queue()` - Build image queue
  - `_display_current_image()` - Display current image
  - `_next_image()` - Advance to next image

**Dependencies**: All core systems, DisplayManager, image sources

---

### `engine/display_manager.py`
**Purpose**: Multi-monitor coordination  
**Key Classes**:
- `DisplayManager` - Manage multiple displays
  - `initialize()` - Detect and setup displays
  - `_create_display_widget(screen)` - Create widget for screen
  - `_on_image_ready(event)` - Handle image ready event
  - `_on_screen_added(screen)` - Handle monitor connected
  - `_on_screen_removed(screen)` - Handle monitor disconnected
  - `show_error(message)` - Display error on all screens

**Dependencies**: DisplayWidget, EventSystem, SettingsManager

---

### `engine/image_queue.py`
**Purpose**: Image queue management  
**Key Classes**:
- `ImageQueue` - Queue of images
  - `add_images(images)` - Add images to queue
  - `next()` - Get next image
  - `current()` - Get current image
  - `size()` - Queue size
  - `clear()` - Clear queue

**Key Dataclasses**:
- `ImageMetadata` - Image metadata (path, width, height, aspect_ratio, file_size, modified_time, source)

---

## Image Sources (`sources/`)

### `sources/base_provider.py`
**Purpose**: Abstract base for image providers  
**Key Classes**:
- `ImageProvider` (ABC) - Interface for image sources
  - `get_images()` - Get list of available images
  - `refresh()` - Refresh image list

**Key Dataclasses**:
- `ImageMetadata` - Image metadata structure

---

### `sources/folder_source.py`
**Purpose**: Local folder scanning  
**Key Classes**:
- `FolderSource(ImageProvider)` - Scan local folders
  - `get_images()` - Get images from folders
  - `refresh()` - Rescan folders
  - `_scan_folder(folder)` - Recursively scan folder
  - `_get_image_metadata(path)` - Extract image metadata

**Key Constants**:
- `SUPPORTED_EXTENSIONS` - Set of supported image extensions

---

### `sources/rss_source.py`
**Purpose**: RSS feed parsing and image download  
**Key Classes**:
- `RSSSource(ImageProvider)` - Parse RSS feeds
  - `get_images()` - Get images from RSS
  - `refresh()` - Refresh feeds
  - `_fetch_feed(url)` - Fetch RSS feed
  - `_parse_feed(content)` - Parse feed XML
  - `_download_image(url)` - Download image

**Dependencies**: requests, xml.etree

---

## Rendering (`rendering/`)

### `rendering/display_widget.py`
**Purpose**: Fullscreen display on single monitor  
**Key Classes**:
- `DisplayWidget(QWidget)` - Display widget
  - `set_image(pixmap, metadata)` - Set new image
  - `show_error(message)` - Display error
  - `_execute_transition()` - Execute transition
  - `_setup_widgets()` - Setup clock/weather widgets
  - Input handlers: `mouseMoveEvent()`, `mousePressEvent()`, `keyPressEvent()`

**Dependencies**: ImageProcessor, Transitions, ClockWidget, WeatherWidget

---

### `rendering/image_processor.py`
**Purpose**: Image scaling and processing  
**Key Classes**:
- `ImageProcessor` - Process images for display
  - `process_image(pixmap, target_size, mode)` - Main processing function
  - `_fill_mode(pixmap, target_size)` - Fill mode (crop to fit)
  - `_fit_mode(pixmap, target_size)` - Fit mode (letterbox)
  - `_shrink_mode(pixmap, target_size)` - Shrink mode (no upscale)

---

### `rendering/display_modes.py`
**Purpose**: Display mode definitions  
**Key Enums**:
- `DisplayMode` - FILL, FIT, SHRINK

---

### `rendering/pan_scan_animator.py`
**Purpose**: Pan & scan animation  
**Key Classes**:
- `PanScanAnimator(QObject)` - Animate pan & scan
  - `start()` - Start animation
  - `stop()` - Stop animation
  - `get_visible_region()` - Get current visible region

**Signals**:
- `position_updated` - Emitted on position change
- `animation_complete` - Emitted on completion

---

## Transitions (`transitions/`)

### `transitions/base_transition.py`
**Purpose**: Abstract base for transitions  
**Key Classes**:
- `BaseTransition(QObject, ABC)` - Transition base
  - `start()` - Start transition
  - `stop()` - Stop transition
  - `update(delta_time)` - Update transition state

**Signals**:
- `finished` - Emitted on completion
- `progress` - Emitted with progress (0.0 to 1.0)

---

### `transitions/crossfade.py`
**Purpose**: Opacity-based crossfade  
**Key Classes**:
- `CrossfadeTransition(BaseTransition)` - Crossfade effect
  - Uses QGraphicsOpacityEffect and QPropertyAnimation

---

### `transitions/slide.py`
**Purpose**: Slide transition  
**Key Classes**:
- `SlideTransition(BaseTransition)` - Slide effect
  - Supports left, right, up, down directions
  - Uses QPropertyAnimation on position

---

### `transitions/diffuse.py`
**Purpose**: Random block reveal  
**Key Classes**:
- `DiffuseTransition(BaseTransition)` - Diffuse effect
  - Configurable block size
  - Random reveal order

---

### `transitions/block_puzzle_flip.py`
**Purpose**: 3D block flip effect (STAR FEATURE)  
**Key Classes**:
- `BlockPuzzleFlipTransition(BaseTransition)` - Block puzzle flip
  - Configurable grid size
  - 3D flip animation per block
  - Random flip order
  - Uses QGraphicsScene/QGraphicsView

---

### `transitions/__init__.py`
**Purpose**: Transition factory  
**Key Functions**:
- `create_transition(type, target_widget, old_pixmap, new_pixmap, settings)` - Create transition instance

**Key Constants**:
- `TRANSITION_TYPES` - Dict of transition type to class

---

## Widgets (`widgets/`)

### `widgets/clock_widget.py`
**Purpose**: Clock overlay  
**Key Classes**:
- `ClockWidget(QLabel)` - Display time
  - 12h/24h format support
  - Timezone support
  - Auto-update every second
  - Configurable position and transparency

**Key Constants**:
- `POSITIONS` - Dict of position names to offsets

---

### `widgets/weather_widget.py`
**Purpose**: Weather overlay  
**Key Classes**:
- `WeatherWidget(QWidget)` - Display weather
  - Temperature, condition, location display
  - Auto-update every 30 minutes
  - Configurable position and transparency

**Dependencies**: WeatherProvider

---

### `widgets/weather_provider.py`
**Purpose**: Weather API integration  
**Key Classes**:
- `WeatherProvider` - Fetch weather data
  - `get_weather(location)` - Get weather for location
  - Uses wttr.in API
  - Caches results

---

## UI (`ui/`)

### `ui/settings_dialog.py`
**Purpose**: Main settings window  
**Key Classes**:
- `SettingsDialog(QDialog)` - Settings dialog
  - Side-tab navigation
  - Dark theme
  - 1080x720 minimum size

**Dependencies**: All tab widgets, SettingsManager

---

### `ui/sources_tab.py`
**Purpose**: Sources configuration  
**Key Classes**:
- `SourcesTab(QWidget)` - Sources tab
  - Folder list and management
  - RSS feed list and management
  - Source mode selection

**Features**: Instant save

---

### `ui/transitions_tab.py`
**Purpose**: Transitions configuration  
**Key Classes**:
- `TransitionsTab(QWidget)` - Transitions tab
  - Transition type selector
  - Duration slider
  - Display mode selector
  - Pan & scan options
  - Block puzzle grid config

**Features**: Instant save

---

### `ui/widgets_tab.py`
**Purpose**: Widgets configuration  
**Key Classes**:
- `WidgetsTab(QWidget)` - Widgets tab
  - Clock settings
  - Weather settings
  - Multiple timezone dialog
  - Position and transparency controls

**Features**: Instant save

---

### `ui/about_tab.py`
**Purpose**: About page  
**Key Classes**:
- `AboutTab(QWidget)` - About information
  - Version info
  - Credits
  - Links

---

### `ui/preview_window.py`
**Purpose**: Preview mode handler  
**Key Classes**:
- `PreviewWindow(QWidget)` - Preview mode
  - Embed in Windows preview window
  - Handle /p <hwnd> argument

---

## Utilities (`utils/`)

### `utils/monitors.py` 🟢 COMPLETE
**Purpose**: Multi-monitor detection and utilities  
**Status**: ✅ Implemented, ✅ Tested (multi-monitor with DPI scaling support)  
**Key Functions**:
- `get_all_screens()` - Get all connected screens
- `get_primary_screen()` - Get primary screen
- `get_screen_count()` - Get number of screens
- `is_multi_monitor()` - Check if multi-monitor setup
- `get_screen_geometry(screen)` - Get logical (DPI-scaled) geometry
- `get_physical_resolution(screen)` - Get physical pixel resolution (DPI-aware)
- `get_screen_available_geometry(screen)` - Get available geometry (excluding taskbar)
- `get_screen_by_index(index)` - Get screen by index
- `get_screen_by_name(name)` - Get screen by name
- `get_virtual_desktop_rect()` - Get bounding rect of all screens
- `get_screen_at_point(point)` - Get screen containing point
- `get_screen_info_dict(screen)` - Get comprehensive screen info with physical + logical sizes
- `log_screen_configuration()` - Log detailed screen info for debugging

**Features**: 
- DPI-aware resolution detection (physical pixels vs logical pixels)
- Comprehensive screen info including device pixel ratio and DPI scaling percentage
- Virtual desktop support for multi-monitor setups
- Simplified interface from original 652 lines

**Adapted From**: `MyReuseableUtilityModules/utils/window/monitors.py` (652 lines → 270 lines)  
**Implemented**: Day 2

---

### `utils/lockfree/` 🟢 COMPLETE
**Purpose**: Lock-free data structures for high-frequency cross-thread communication  
**Status**: ✅ Implemented, ✅ Used by ThreadManager  
**Key Classes**:
- `SPSCQueue` - Single-producer/single-consumer bounded ring buffer
  - `try_push(item)` - Non-blocking push
  - `try_pop()` - Non-blocking pop
  - `push_drop_oldest(item)` - Push with drop-oldest policy
- `TripleBuffer` - Lock-free latest-value exchange
  - `publish(value)` - Publish new value
  - `consume_latest()` - Consume latest value

**Features**: No locks, relies on GIL atomic operations, strict SPSC usage  
**Adapted From**: `MyReuseableUtilityModules/utils/lockfree/`  
**Implemented**: Day 1

---

### `utils/image_cache.py` 🟢 COMPLETE
**Purpose**: LRU image cache for QPixmap objects  
**Status**: ✅ Implemented, ✅ Tested (5 items, 4MB memory usage)  
**Key Classes**:
- `ImageCache` - LRU cache with automatic eviction
  - `get(key)` - Get cached pixmap (moves to end = most recently used)
  - `put(key, pixmap)` - Cache pixmap (auto-evicts if needed)
  - `contains(key)` - Check if key is cached
  - `remove(key)` - Remove entry from cache
  - `clear()` - Clear all cached images
  - `size()` - Get number of cached images
  - `memory_usage()` - Get approximate memory usage
  - `get_stats()` - Get cache statistics

**Features**:
- OrderedDict-based LRU implementation
- Dual limits: max_items and max_memory_mb
- Automatic LRU eviction when limits exceeded
- QPixmap memory estimation (width × height × 4 bytes)
- Cache hit/miss logging

**Implemented**: Day 3

---

## Themes (`themes/`)

### `themes/dark.qss`
**Purpose**: Dark theme stylesheet  
**Features**:
- Complete dark theme
- Glass effects
- Custom button styles
- Overlay support
- All Qt widgets styled

**Copied From**: `MyReuseableUtilityModules/themes/dark.qss`

---

## Tests (`tests/`)

### `tests/conftest.py`
**Purpose**: Shared pytest fixtures  
**Key Fixtures**:
- `qt_app` - QApplication instance
- `settings_manager` - SettingsManager instance
- `thread_manager` - ThreadManager instance
- `resource_manager` - ResourceManager instance
- `event_system` - EventSystem instance
- `temp_image` - Temporary test image

---

### `tests/test_threading.py`
**Purpose**: ThreadManager tests  
**Tests**: Initialization, task submission, UI dispatch, timers

---

### `tests/test_resources.py`
**Purpose**: ResourceManager tests  
**Tests**: Registration, cleanup, Qt widgets, temp files

---

### `tests/test_events.py`
**Purpose**: EventSystem tests  
**Tests**: Subscribe/publish, priority, filtering, unsubscribe

---

### `tests/test_settings.py`
**Purpose**: SettingsManager tests  
**Tests**: Get/set, defaults, persistence, change notifications

---

### `tests/test_image_processor.py`
**Purpose**: ImageProcessor tests  
**Tests**: All display modes, aspect ratios, edge cases

---

### `tests/test_transitions.py`
**Purpose**: Transition tests  
**Tests**: All transition types, creation, completion

---

### `tests/test_sources.py`
**Purpose**: Image source tests  
**Tests**: Folder scanning, RSS parsing, image cache

---

### `tests/test_integration.py`
**Purpose**: Integration tests  
**Tests**: Complete workflows, multi-monitor, end-to-end

---

## Configuration Files

### `requirements.txt`
**Purpose**: Python dependencies  
**Packages**: PySide6, requests, pytz, pytest, pytest-qt

---

### `screensaver.spec`
**Purpose**: PyInstaller build specification  
**Output**: ShittyRandomPhotoScreenSaver.scr

---

### `README.md`
**Purpose**: User documentation  
**Contents**: Installation, usage, features, troubleshooting

---

## Documentation (`Docs/`)

### Planning Documents (Read in Order)
1. `00_PROJECT_OVERVIEW.md` - Project summary and objectives
2. `01_ARCHITECTURE_DESIGN.md` - Architecture and design patterns
3. `02_REUSABLE_MODULES_INTEGRATION.md` - Integration plan for reusable modules
4. `03_CORE_IMPLEMENTATION.md` - Core infrastructure implementation
5. `04_IMAGE_SOURCES.md` - Image source implementations
6. `05_DISPLAY_AND_RENDERING.md` - Display modes and rendering
7. `06_TRANSITIONS.md` - Transition effects implementation
8. `07_WIDGETS_AND_UI.md` - Overlay widgets and configuration UI
9. `08_TESTING_AND_DEPLOYMENT.md` - Testing strategy and deployment
10. `09_IMPLEMENTATION_ORDER.md` - Step-by-step implementation guide

### Reference Documents
- `INDEX.md` (this file) - Module index and quick reference
- `SPEC.md` - Technical specification (single source of truth)
- `initial_screensaver_plan.md` - Original planning document
- `settings_gui.txt` - Original GUI requirements

---

## Module Dependencies Graph

```
main.py
├── core/
│   ├── threading/manager.py
│   ├── resources/manager.py
│   ├── events/event_system.py
│   ├── settings/settings_manager.py
│   └── logging/logger.py
│
├── engine/
│   ├── screensaver_engine.py
│   │   ├── core/*
│   │   ├── engine/display_manager.py
│   │   ├── sources/*
│   │   └── engine/image_queue.py
│   │
│   └── display_manager.py
│       ├── rendering/display_widget.py
│       └── core/*
│
├── sources/
│   ├── folder_source.py (base_provider)
│   └── rss_source.py (base_provider)
│
├── rendering/
│   ├── display_widget.py
│   │   ├── rendering/image_processor.py
│   │   ├── transitions/*
│   │   └── widgets/*
│   │
│   ├── image_processor.py
│   └── pan_scan_animator.py
│
├── transitions/
│   ├── crossfade.py (base_transition)
│   ├── slide.py (base_transition)
│   ├── diffuse.py (base_transition)
│   └── block_puzzle_flip.py (base_transition)
│
├── widgets/
│   ├── clock_widget.py
│   └── weather_widget.py
│       └── weather_provider.py
│
└── ui/
    ├── settings_dialog.py
    │   ├── ui/sources_tab.py
    │   ├── ui/transitions_tab.py
    │   ├── ui/widgets_tab.py
    │   └── ui/about_tab.py
    │
    └── preview_window.py
```

---

## Quick Lookup: Where to Find...

### To add a new image source:
1. Create new class in `sources/` inheriting from `ImageProvider`
2. Implement `get_images()` and `refresh()`
3. Register in `engine/screensaver_engine.py` `_initialize_sources()`

### To add a new transition:
1. Create new class in `transitions/` inheriting from `BaseTransition`
2. Implement `start()`, `stop()`, `update()`
3. Add to `transitions/__init__.py` `TRANSITION_TYPES`
4. Add UI option in `ui/transitions_tab.py`

### To add a new widget:
1. Create new class in `widgets/` inheriting from QWidget
2. Implement positioning and update logic
3. Add to `rendering/display_widget.py` `_setup_widgets()`
4. Add UI options in `ui/widgets_tab.py`

### To add a new setting:
1. Add to schema in `core/settings/types.py`
2. Add UI control in appropriate tab in `ui/`
3. Use in code via `settings_manager.get()`

### To add a new event:
1. Define constant in `core/events/event_types.py`
2. Publish with `event_system.publish(event_type, data=...)`
3. Subscribe with `event_system.subscribe(event_type, handler)`

---

## Update Checklist

When making major changes, update:
- [ ] This INDEX.md file
- [ ] SPEC.md if requirements change
- [ ] Relevant planning document in Docs/
- [ ] Tests in tests/
- [ ] README.md if user-facing changes

---

**This index is a living document. Keep it updated as the codebase evolves.**
