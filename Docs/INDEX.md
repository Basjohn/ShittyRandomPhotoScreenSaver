#### `rendering/backends/base.py`
**Purpose**: Backend-agnostic renderer interfaces (`RendererBackend`, `RenderSurface`, `TransitionPipeline`).
**Status**: ✅ Interfaces defined and reused for OpenGL + software.

#### `rendering/backends/__init__.py`
**Purpose**: Backend registry/factory with settings-driven creation and telemetry.
**Status**: ✅ OpenGL primary, software fallback; diagnostics counters active.

#### `rendering/backends/opengl/backend.py`
**Purpose**: Maintains OpenGL renderer implementation.
**Status**: ✅ Active production backend.

#### `rendering/backends/software/backend.py`
**Purpose**: CPU fallback renderer.
**Status**: ✅ Available for troubleshooting scenarios.

# ShittyRandomPhotoScreenSaver - Module Index

**Purpose**: Living file map of all modules, their purposes, and key classes/functions.  
**Last Updated**: Nov 17, 2025 23:30 UTC+2 - Canonical settings + GL compositor route (Route 3)  
**Implementation Status**: 🟢 Core Framework | 🟢 Animation | 🟢 Entry Point | 🟢 Image Sources | 🟢 Display & Rendering | 🟢 Engine | 🟠 **Transitions (GL compositor + Blinds tuned, remaining GL visuals pending review)** | 🟢 Pan & Scan | 🟢 Widgets | 🟢 UI  
**Test Status**: Runs locally; GL compositor route and settings schema stable, transitions still require targeted visual/manual verification  
**Note**: Update this file after any major structural changes.

**Audit Session (Nov 6, 2025 21:00-21:30) - 48/63 Issues Fixed**:
- ✅ **Memory Leaks**: Fixed 20+ locations across 5 files (transitions, engine, rendering)
- ✅ **Thread Safety**: ImageQueue fully protected with RLock, loading flag atomic
- ✅ **ResourceManager**: Integrated in ALL transitions + pan_and_scan + display_widget
- ✅ **Division by Zero**: Fixed 10 locations (image_processor, pan_and_scan)
- ✅ **Import Organization**: Cleaned up 10 files, removed unused imports
- ✅ **Lambda Closures**: Fixed 3 files (display_widget, animator, display_manager)
- ✅ **Python 3.7+ Compatibility**: Threading manager shutdown parameter
- ✅ **Code Quality**: Removed unused variables, fixed f-strings, added logging
- 🔴 **TRANSITION VISUAL BUGS REMAIN**: Diffuse (black boxes), Block Puzzle (wrong sizing), Wipe (wrong size)
- ⚠️ **15 Minor Issues Remain**: Edge cases, code quality improvements (non-critical)

**Session 1 (Nov 6, 14:00-16:00)**:
- ✅ ALL 17 CRITICAL BUGS FIXED
- ✅ Pan & scan speed adjusted (8-25 px/s auto, 1-50 px/s manual default 5)
- ✅ Settings dialog simplified (QSizeGrip only)
- ✅ Multi-monitor different images working
- ✅ Z/X/C/S hotkeys functional

---

## Entry Point

### `main.py` 🟢 COMPLETE + RUNTIME
**Purpose**: Application entry point, command-line handling, and runtime execution  
**Status**: ✅ Implemented, ✅ Tested, ✅ **FUNCTIONAL**  
**Key Functions**:
- `parse_screensaver_args()` - Parse Windows screensaver arguments (/s, /c, /p <hwnd>)
- `run_screensaver(app)` - **NEW**: Run screensaver with auto-config if no sources
- `run_config(app)` - **NEW**: Open settings dialog
- `main()` - Main application entry point with logging and QApplication setup

**Key Enums**:
- `ScreensaverMode` - RUN, CONFIG, PREVIEW

**Features**: 
- Command-line argument parsing with fallback to RUN mode
- Debug mode support (--debug or -d flags)
- **Auto-open settings if no sources configured**
- **Screensaver engine initialization and startup**
- **Full runtime execution**
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

**Features**: Automatic defaults using the canonical nested settings schema (`display`, `transitions`, `timing`, `widgets`, `input`), change notifications, and QSettings persistence. Legacy flat settings keys (e.g. `transitions.type`, `widgets.clock_*`) are migration-only and not used by the active runtime pipeline.  
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
- All transition effects (crossfade, slide, wipe, diffuse, block puzzle) CPU/GL
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

### `sources/rss_source.py` 🟢 COMPLETE
**Purpose**: RSS feed image source with automatic caching  
**Status**: ✅ Implemented (Day 5)  
**Key Classes**:
- `RSSSource(ImageProvider)` - RSS feed-based provider
  - `get_images()` - Get all cached images from feeds
  - `refresh()` - Refresh all feeds and download new images
  - `add_feed(url)` - Add new RSS feed
  - `remove_feed(url)` - Remove feed
  - `clear_cache()` - Clear cached images
  - `_parse_feed(url)` - Parse single RSS/Atom feed
  - `_download_image(url)` - Download and cache image
  - `_cleanup_cache()` - LRU cleanup when cache exceeds limit

**Features**:
- Parses RSS/Atom feeds with feedparser
- Extracts images from media:content, enclosures, img tags
- Downloads with streaming (8KB chunks)
- MD5-based cache filenames
- Automatic LRU cache cleanup
- Feed metadata tracking
- Network timeout handling (30s default)
- [FALLBACK] logging for failed feeds

**Default Feeds**:
- NASA Image of the Day
- NASA Breaking News  
- Wikimedia Picture of the Day

**Implemented**: Day 5

---

## Rendering (`rendering/`) 🟢 COMPLETE

### `rendering/display_modes.py` 🟢 COMPLETE
**Purpose**: Display mode enumeration  
**Status**: ✅ Implemented (Day 6)  
**Key Classes**:
- `DisplayMode` enum - How images are scaled/positioned
  - `FILL` - Scale and crop to fill screen (no letterboxing) - PRIMARY MODE
  - `FIT` - Scale to fit within screen (with letterboxing)
  - `SHRINK` - Only scale down, never upscale (with letterboxing)
  - `from_string(value)` - Create from string ('fill', 'fit', 'shrink')
  - `__str__()` - Convert to string

**Implemented**: Day 6

---

### `rendering/image_processor.py` 🟢 COMPLETE
**Purpose**: High-quality image scaling and positioning for display  
**Status**: ✅ Implemented, ✅ Tested, 🆕 **Lanczos Scaling Added!**  
**Key Classes**:
- `ImageProcessor` - Static methods for image processing
  - `process_image(image, screen_size, mode, use_lanczos=True, sharpen=False)` - **UPDATED**: Process image with quality options
  - `_scale_pixmap(pixmap, width, height, use_lanczos, sharpen)` - **NEW**: Scale with Lanczos or Qt
  - `_process_fill(image, screen_size, use_lanczos, sharpen)` - **UPDATED**: FILL mode with Lanczos
  - `_process_fit(image, screen_size, use_lanczos, sharpen)` - **UPDATED**: FIT mode with Lanczos
  - `_process_shrink(image, screen_size, use_lanczos, sharpen)` - **UPDATED**: SHRINK mode with Lanczos
  - `calculate_scale_factors(source, target, mode)` - Get scale factors
  - `get_crop_rect(source_size, target_size)` - Calculate crop rectangle

**Features**:
- High‑quality scaling with Qt SmoothTransformation by default (Lanczos optional)
- Aspect ratio preservation
- Center alignment for all modes
- QPainter-based rendering
- Black backgrounds
- QPixmap ↔ PIL Image conversion

**Quality Improvements**:
- **Lanczos vs Qt**: Much better downscaling quality (especially 3-4x downscales)
- **Configurable**: Can disable via settings if performance issues
- **Safe**: Falls back to Qt SmoothTransformation if PIL fails

**Tested**: 18 tests covering all modes and edge cases  
**Implemented**: Day 6, **Updated**: Nov 6 (Lanczos)

---

### `rendering/display_widget.py` 🟢 COMPLETE + TRANSITIONS + WIDGETS
**Purpose**: Fullscreen display widget with transitions and overlay widgets  
**Status**: ✅ Implemented, 🆕 **Transitions Integrated!**, 🆕 **Clock Widget Working!**, 🆕 **GL Compositor route active (Route 3)**  
**Key Classes**:
- `DisplayWidget(QWidget)` - Fullscreen image display with transitions
  - `show_on_screen()` - Position fullscreen, **setup widgets**
  - `set_image(pixmap, path)` - **UPDATED**: Display with transition support
  - `_setup_widgets()` - **NEW**: Setup clock/weather widgets from settings
  - `_create_transition()` - **NEW**: Create transition from settings
  - `_on_transition_finished(pixmap, path)` - **NEW**: Handle transition completion
  - `set_display_mode(mode)` - Change display mode
  - `clear()` - **UPDATED** (Nov 12, 2025): Stops transitions and preserves last rendered pixmap for restart to avoid fallback flash
  - `show_error(message)` - Display error message while retaining previous pixmap for recovery
  - `get_screen_info()` - Get display information
  - `paintEvent()` - Render current image or error
  - `keyPressEvent()` - **UPDATED**: Exit on any key (except hotkeys Z/X/C/S/Esc)

### `temp/display_widget_prev.py` 🟡 LEGACY / REFERENCE ONLY
**Purpose**: Legacy DisplayWidget implementation from the earlier per-transition GL overlay pipeline, retained for comparison during audits and refactors.  
**Status**: 🟡 Legacy; not referenced by the current engine. Do not add new features here—use `rendering.display_widget.DisplayWidget` + `GLCompositorWidget` instead.  
  - `mousePressEvent()` - Exit on any click
  - `mouseMoveEvent()` - **NEW**: Track movement, exit if >5px

**Signals**:
- `exit_requested` - User wants to exit
- `image_displayed(str)` - Image displayed with path
- `settings_requested` - **NEW**: S key pressed
- `next_requested` - **NEW**: X key pressed
- `previous_requested` - **NEW**: Z key pressed
- `cycle_transition` - **NEW**: C key pressed

**Features**:
- 🆕 **Smooth transitions** between images (5 types supported)
- 🆕 **Clock widget integration** with settings-based configuration
- 🆕 **Mouse movement tracking** for screensaver exit (>5px)
- 🆕 **Hotkey support** (Z/X/C/S/Esc)
- 🆕 **Lanczos scaling integration** via settings
- 🆕 **Previous/current pixmap tracking** for transitions
- Frameless fullscreen window
- Blank cursor
- Black background
- Centered error messages
- Per-screen positioning

**Transition Support**:
- Crossfade, Slide, Wipe, Diffuse, Block Puzzle Flip (CPU + GL variants)
- AnimationManager‑driven; persistent overlays; overlay_manager for hide/gating
- Base paint gated when GL overlay has drawn; clock always above overlays
- Fallback to instant display if transition fails

**Implemented**: Day 6, **Updated**: Nov 6 (Transitions, Widgets, Hotkeys)

---

### `rendering/pan_scan_animator.py` 🟢 COMPLETE
**Purpose**: Ken Burns effect animator for pan & scan  
**Status**: ✅ Implemented, ✅ Tested (Days 12-13)  
**Key Classes**:
- `PanDirection(Enum)` - Pan movement directions
  - `LEFT_TO_RIGHT` - Pan from left to right
  - `RIGHT_TO_LEFT` - Pan from right to left
  - `TOP_TO_BOTTOM` - Pan from top to bottom
  - `BOTTOM_TO_TOP` - Pan from bottom to top
  - `DIAGONAL_TL_BR` - Diagonal top-left to bottom-right
  - `DIAGONAL_TR_BL` - Diagonal top-right to bottom-left
  - `RANDOM` - Randomly select direction

- `PanScanAnimator(QObject)` - Ken Burns effect animator
  - `start(image_size, viewport_size, direction)` - Start animation
  - `stop()` - Stop animation
  - `is_active()` - Check if active
  - `set_zoom_range(min, max)` - Configure zoom levels
  - `set_duration(ms)` - Set animation duration
  - `set_fps(fps)` - Set frame rate

**Private Methods**:
- `_calculate_animation_params()` - Calculate start/end zoom and positions
- `_update_frame()` - Update animation frame (timer callback)
- `_calculate_viewport(progress)` - Get viewport rectangle for progress
- `_ease_in_out_cubic(t)` - Cubic easing function

**Signals**:
- `frame_updated(QRectF)` - Emits current viewport rectangle
- `animation_finished()` - Animation completed

**Features**:
- Configurable zoom range (default: 1.2-1.5x)
- 6 directional pans + random selection
- Smooth cubic ease in-out
- Timer-based updates (configurable FPS, default: 30)
- Configurable duration (default: 10 seconds)
- Automatic viewport bounds checking
- Position interpolation
- QRectF viewport for image cropping

**Tested**: 16 tests covering all directions, zoom levels, easing, and configuration

**Implemented**: Days 12-13

---

## Engine (`engine/`) 🟡 PARTIAL

### `engine/display_manager.py` 🟢 COMPLETE
**Purpose**: Multi-monitor coordination  
**Status**: ✅ Implemented (Day 6)  
**Key Classes**:
- `DisplayManager(QObject)` - Manage multiple displays
  - `initialize_displays()` - Create DisplayWidget for each screen
  - `show_image(pixmap, path, screen_index)` - Show image on display(s)
  - `show_image_on_screen(index, pixmap, path)` - Show on specific screen
  - `show_error(message, screen_index)` - Display error
  - `clear_all()` - Clear all displays
  - `set_display_mode(mode)` - Change mode for all displays
  - `set_same_image_mode(enabled)` - Same/different image modes
  - `get_display_count()` - Number of active displays
  - `get_screen_count()` - Number of detected screens
  - `cleanup()` - Clean up all displays

**Signals**:
- `exit_requested` - Any display requested exit
- `monitors_changed(int)` - Monitor count changed

**Features**:
- Multi-monitor detection via QGuiApplication.screens()
- Monitor hotplug handling (screenAdded/screenRemoved signals)
- Same image mode (all screens show same image)
- Different image mode (per-screen images)
- Coordinated exit (any display triggers all)
- Dynamic display creation/cleanup

**Implemented**: Day 6

---

### `engine/screensaver_engine.py` 🟢 COMPLETE
**Purpose**: Main screensaver controller and orchestrator  
**Status**: ✅ Implemented, ✅ Tested (Day 8)  
**Key Classes**:
- `ScreensaverEngine(QObject)` - Central orchestrator for entire screensaver
  - `initialize()` - Initialize all subsystems
  - `start()` - Start screensaver (show first image, start timer)
  - `stop()` - Stop screensaver
  - `cleanup()` - Clean up all resources
  - `is_running()` - Check if engine running
  - `get_stats()` - Get comprehensive statistics
  
**Private Methods**:
  - `_initialize_core_systems()` - Setup Events, Resources, Threading, Settings
  - `_load_settings()` - Load configuration
  - `_initialize_sources()` - Setup Folder and RSS sources
  - `_build_image_queue()` - Populate queue from sources
  - `_initialize_display()` - Create and configure display manager
  - `_setup_rotation_timer()` - Configure QTimer for rotation
  - `_subscribe_to_events()` - Wire up event handlers
  - `_show_next_image()` - Load and display next image
  - `_load_image_task()` - Image loading (thread pool ready)
  - `_load_and_display_image()` - Load and show image
  - `_on_rotation_timer()` - Handle timer tick
  - `_on_exit_requested()` - Handle user exit
  - `_on_settings_changed()` - Handle settings updates
  - `_on_monitors_changed()` - Handle monitor hotplug
  - `_update_rotation_interval()` - Apply interval changes
  - `_update_display_mode()` - Apply display mode changes
  - `_update_shuffle_mode()` - Apply shuffle changes

**Signals**:
- `started` - Engine started
- `stopped` - Engine stopped
- `image_changed(str)` - New image displayed
- `error_occurred(str)` - Error occurred

**Features**:
- Automatic core system initialization
- Default RSS sources if none configured
- Settings-driven configuration
- Hot-reloadable settings
- Monitor hotplug support
- Image rotation with configurable interval
- Async-ready image loading
- Comprehensive error handling with [FALLBACK] logging
- Full lifecycle management (init → start → stop → cleanup)
- Stop is idempotent; rotation timer only stopped (no double‑delete)

**Tested**: 15 integration tests + system tests

**Implemented**: Day 8

**Dependencies**: All core systems, DisplayManager, ImageQueue, FolderSource, RSSSource

---

### `engine/image_queue.py` 🟢 COMPLETE
**Purpose**: Image queue management with shuffle and history  
**Status**: ✅ Implemented, ✅ Tested (Day 7)  
**Key Classes**:
- `ImageQueue` - Queue manager for screensaver images
  - `add_images(images)` - Add images to queue
  - `set_images(images)` - Replace all images
  - `next()` - Get next image (auto-wraparound)
  - `previous()` - Go back to previous image
  - `current()` - Get current image without advancing
  - `peek()` - Look ahead at next image
  - `shuffle()` - Manually shuffle queue
  - `set_shuffle_enabled(enabled)` - Toggle shuffle mode
  - `clear()` - Clear all images
  - `remove_image(path)` - Remove specific image
  - `size()` - Remaining images in queue
  - `total_images()` - Total images available
  - `is_empty()` - Check if queue empty
  - `get_history(count)` - Get recent image history
  - `is_in_recent_history(path, lookback)` - Check if recently shown
  - `get_wrap_count()` - Number of queue wraparounds
  - `get_stats()` - Full queue statistics

**Features**:
- Configurable shuffle (on/off toggle)
- History tracking with configurable size (default 50)
- Automatic queue wraparound when exhausted
- Previous image navigation
- Image removal by path
- Prevents recent repeats
- __len__ and __bool__ support

**Tested**: 24 tests covering all operations and edge cases

**Implemented**: Day 7

---

## Transitions (`transitions/`) ⚠️ CODE CHANGED - NOT TESTED

### `transitions/base_transition.py` 🟢 COMPLETE
**Purpose**: Abstract base class for all image transitions  
**Status**: ✅ Implemented, ✅ Tested (Day 9)  
**Key Classes**:
- `TransitionState(Enum)` - Transition states
  - `IDLE` - Not started
  - `RUNNING` - Currently transitioning
  - `PAUSED` - Paused (not used yet)
  - `FINISHED` - Successfully completed
  - `CANCELLED` - Stopped early

- `QABCMeta` - Combined metaclass for QObject + ABC
  - Resolves metaclass conflict

- `BaseTransition(QObject, metaclass=QABCMeta)` - Abstract base
  - `start(old_pixmap, new_pixmap, widget)` - Begin transition
  - `stop()` - Stop immediately
  - `cleanup()` - Clean up resources
  - `get_state()` - Get current state
  - `is_running()` - Check if running
  - `set_duration(ms)` - Set transition duration
  - `get_duration()` - Get duration

**Signals**:
- `started` - Transition started
- `finished` - Transition completed
- `progress(float)` - Progress update (0.0-1.0)
- `error(str)` - Error occurred

**Features**:
- Abstract interface for all transitions
- Signal-based progress tracking
- State management
- Duration validation
- Progress clamping (0.0-1.0)

**Implemented**: Day 9

---

### `transitions/crossfade_transition.py` COMPLETE (AM‑driven overlay)
**Purpose**: Smooth opacity-based crossfade transition  
**Status**: CODE CHANGED - NOT TESTED (AnimationManager + persistent CPU overlay)  
**Key Classes**:
- `CrossfadeTransition(BaseTransition)` - Crossfade effect
  - `start(old_pixmap, new_pixmap, widget)` - Begin fade
  - `stop()` - Stop immediately
  - `cleanup()` - Clean up effect and animation
  - `set_easing(name)` - Set easing curve

**Private Methods**:
- `_show_image_immediately()` - Skip transition (first image)
- `_on_animation_finished()` - Handle QPropertyAnimation completion
- `_on_transition_finished()` - Final cleanup

**Features**:
- AnimationManager‑driven timing (no QPropertyAnimation)
- Persistent CPU overlay paints old/new pixmaps with opacity
- First‑frame prepaint; clock overlay raised above
- Easing curves supported: InOutQuad, Linear, InQuad, OutQuad
- Handles null old_pixmap (first image)
- Robust cleanup (try/catch for Qt deletions)
- Automatic progress tracking via animation

**Tested**: 16 tests covering all functionality

**Implemented**: Day 9, **Improved**: Nov 6, 2025 (Session 2)

---

### `transitions/slide_transition.py` 🟢 COMPLETE (migrated to AM)
**Purpose**: Directional slide transition effect  
**Status**: ⚠️ CODE CHANGED - NOT TESTED (AnimationManager)
**Key Classes**:
- `SlideDirection(Enum)` - Slide directions
  - `LEFT` - New slides in from right
  - `RIGHT` - New slides in from left
  - `UP` - New slides in from bottom
  - `DOWN` - New slides in from top

- `SlideTransition(BaseTransition)` - Slide effect
  - `start(old_pixmap, new_pixmap, widget)` - Begin slide
  - `stop()` - Stop immediately
  - `cleanup()` - Clean up labels and animations
  - `set_direction(direction)` - Set slide direction
  - `set_easing(name)` - Set easing curve

**Private Methods**:
- `_calculate_positions(width, height)` - Calculate start/end positions for direction
- `_show_image_immediately()` - Skip transition (first image)
- `_on_animation_value_changed(value)` - Track progress by distance
- `_on_animation_finished()` - Handle completion (wait for both animations)
- `_get_easing_curve(name)` - Convert easing name to Qt curve

**Features**:
- AnimationManager‑driven label movement (old out, new in)
- Fitted pixmaps (DPR‑aware), QLabel display, easing via core EasingCurve
- 4 directional slides
- Position calculation per direction
- 21 easing curves supported
- Progress = distance traveled / total distance
- Synchronized dual animations
- Handles null old_pixmap

**Tested**: 13 tests covering all directions and functionality

**Implemented**: Day 10

---

### `transitions/wipe_transition.py` ⚠️ UPDATED – NEEDS TESTING
**Purpose**: Progressive wipe reveal transition  
**Status**: ⚠️ CODE CHANGED - NOT TESTED (mask‑based reveal; full‑rect DPR)
**Key Classes**:
- `WipeDirection(Enum)` - Wipe directions (LEFT_TO_RIGHT, RIGHT_TO_LEFT, TOP_TO_BOTTOM, BOTTOM_TO_TOP)
- `WipeTransition(BaseTransition)` - Wipe effect
  - `start(old_pixmap, new_pixmap, widget)` - Begin wipe
  - `stop()` - Stop immediately
  - `cleanup()` - Clean up resources
  - `set_direction(direction)` - Set wipe direction

**Features**:
- AnimationManager-driven mask reveal
- 4 directional wipes
- Configurable speed
- 🆕 **ResourceManager Integration** (Nov 6 Audit)
- 🆕 **Memory Leak Fixed** (Nov 6 Audit)
- 🆕 **Constructor Bug Fixed** (Nov 6 Audit) - Now passes duration_ms to parent

**CRITICAL BUG** (Confirmed Nov 6, 21:28):
- 🔴 **WRONG SIZE**: Wipe reveals incorrectly sized or scaled content
- Architecture is correct, rendering/sizing logic has bug
- ResourceManager integration complete, memory leaks fixed
- Requires investigation of pixmap sizing and reveal rectangle calculations

**Implemented**: Day 9, **Architecture Fixed**: Nov 6, 2025 (Audit), **Visual Bug Unfixed**

---

### `transitions/diffuse_transition.py` ⚠️ UPDATED – NEEDS TESTING
**Purpose**: Random block reveal transition effect  
**Status**: ⚠️ CODE CHANGED - NOT TESTED (CompositionMode_Clear; AM‑driven)
**Key Classes**:
- `DiffuseTransition(BaseTransition)` - Diffuse effect
  - `start(old_pixmap, new_pixmap, widget)` - Begin diffuse
  - `stop()` - Stop immediately
  - `cleanup()` - Clean up label and timer
  - `set_block_size(size)` - Set block size

**Private Methods**:
- `_create_block_grid(width, height)` - Generate grid of blocks
- `_reveal_pixels(count)` - Reveal blocks by punching holes (timer callback)
- `_update_diffusion()` - Update animation frame
- `_finish_transition()` - Complete transition
- `_show_image_immediately()` - Skip transition (first image)

**Features**:
- QTimer-based progressive reveal
- CompositionMode_Clear for punching holes in old image
- Block grid covering entire widget
- Random shuffle of reveal order
- Configurable block size (default: 50px)
- QPainter composite rendering with transparency
- Edge block size handling
- Progress = revealed blocks / total blocks
- Handles null old_pixmap
- 🆕 **ResourceManager Integration** (Nov 6 Audit)
- 🆕 **Memory Leak Fixed** (Nov 6 Audit)

**CRITICAL BUG** (Confirmed Nov 6, 21:28):
- 🔴 **BLACK BOXES**: Shows black rectangles instead of transparent holes revealing new image
- Architecture is correct, rendering logic has bug
- ResourceManager integration complete, memory leaks fixed
- Requires investigation of CompositionMode_Clear or pixmap copying

**Tested**: 14 tests covering block sizes, randomization, and functionality

**Implemented**: Day 10, **Architecture Fixed**: Nov 6, 2025 (Audit), **Visual Bug Unfixed**

---

### `transitions/block_puzzle_flip_transition.py` ⚠️ UPDATED – NEEDS TESTING ⭐ STAR FEATURE
**Purpose**: 3D block flip transition effect with grid  
**Status**: ⚠️ CODE CHANGED - NOT TESTED (mask union; AM‑driven; grid DPR‑aligned)  
**Key Classes**:
- `FlipBlock` - Individual flipping block
  - `get_current_pixmap()` - Get current frame based on flip progress
  - `_scale_horizontal(pixmap, scale)` - Create horizontal scaling effect
  - Properties: `rect`, `old_piece`, `new_piece`, `flip_progress`, `is_flipping`, `is_complete`

- `BlockPuzzleFlipTransition(BaseTransition)` - Block puzzle flip effect
  - `start(old_pixmap, new_pixmap, widget)` - Begin flip
  - `stop()` - Stop immediately
  - `cleanup()` - Clean up label and timers
  - `set_grid_size(rows, cols)` - Set grid dimensions
  - `set_flip_duration(ms)` - Set single block flip duration

**Private Methods**:
- `_create_block_grid(width, height)` - Generate grid of FlipBlocks
- `_start_next_flip()` - Initiate next block flip (timer callback)
- `_update_flips()` - Update all flipping blocks (60 FPS)
- `_render_scene()` - Composite all blocks with QPainter
- `_finish_transition()` - Complete transition
- `_show_image_immediately()` - Skip transition (first image)

**Features**:
- Grid-based block system (default: 4x6 = 24 blocks)
- FlipBlock class for individual blocks
- 3D flip effect using horizontal scaling
- Two-phase animation:
  - Phase 1 (0.0-0.5): Old image squeezed horizontally
  - Phase 2 (0.5-1.0): New image expanded horizontally
- Random shuffle of flip order
- Two timers:
  - Main timer: Initiates flips progressively
  - Flip timer: Updates all animations at 60 FPS
- QLabel + QPainter composite rendering
- Two-phase progress tracking:
  - First half: Flip initiation progress
  - Second half: Completion progress
- Configurable grid size
- Configurable single-flip duration (default: 500ms)
- Handles null old_pixmap
- Immediate cleanup on finish
- 🆕 **ResourceManager Integration** (Nov 6 Audit)
- 🆕 **Memory Leak Fixed** (Nov 6 Audit)
- 🆕 **Import Organization** (Nov 6 Audit)

**CRITICAL BUG** (Confirmed Nov 6, 21:28):
- 🔴 **WRONG BLOCK SIZING**: Blocks not sized correctly for widget dimensions
- 🔴 **INCOMPLETE FLIP**: Doesn't flip entire image, partial coverage
- Architecture is correct, sizing calculation has bug
- ResourceManager integration complete, memory leaks fixed
- Requires investigation of block grid creation and rect calculations

**Tested**: 18 tests covering grid creation, flip animation, randomization, and all functionality

**Implemented**: Day 11 ⭐ STAR FEATURE, **Architecture Fixed**: Nov 6, 2025 (Audit), **Visual Bugs Unfixed**

---

## Overlay Widgets (`widgets/`) 🟢 COMPLETE

### `widgets/clock_widget.py` 🟢 COMPLETE
**Purpose**: Digital clock overlay widget  
**Status**: ✅ Implemented, ✅ Tested (Days 14-16)  
**Key Classes**:
- `TimeFormat(Enum)` - Time display format
  - `TWELVE_HOUR` - 12-hour format with AM/PM
  - `TWENTY_FOUR_HOUR` - 24-hour format

- `ClockPosition(Enum)` - Clock position on screen
  - `TOP_LEFT`, `TOP_RIGHT`, `TOP_CENTER`
  - `BOTTOM_LEFT`, `BOTTOM_RIGHT`, `BOTTOM_CENTER`

- `ClockWidget(QLabel)` - Digital clock overlay
  - `start()` - Start clock updates
  - `stop()` - Stop clock updates
  - `is_running()` - Check if running
  - `set_time_format(format)` - Set 12h/24h
  - `set_position(position)` - Set screen position
  - `set_show_seconds(show)` - Show/hide seconds
  - `set_font_size(size)` - Set font size
  - `set_text_color(color)` - Set text color
  - `set_margin(margin)` - Set edge margin
  - `cleanup()` - Clean up resources

**Signals**:
- `time_updated(str)` - Emits formatted time string

**Features**:
- QTimer updates every second
- 12h/24h format support
- Show/hide seconds
- 6 position options
- Customizable font (family, size)
- Customizable color with transparency
- Configurable margin from edges
- Auto-positioning on parent resize
- Leading zero removal for 12h format

**Tested**: 19 tests covering formats, positions, signals, and configuration

**Implemented**: Days 14-16

---

### `widgets/weather_widget.py` 🟢 COMPLETE
**Purpose**: Weather information overlay widget  
**Status**: ✅ Implemented, ✅ Tested (Days 14-16)  
**Key Classes**:
- `WeatherPosition(Enum)` - Weather widget position
  - `TOP_LEFT`, `TOP_RIGHT`
  - `BOTTOM_LEFT`, `BOTTOM_RIGHT`

- `WeatherFetcher(QObject)` - Background weather fetcher
  - `fetch()` - Fetch weather from API
  - Signals: `data_fetched(dict)`, `error_occurred(str)`

- `WeatherWidget(QLabel)` - Weather display overlay
  - `start()` - Start weather updates
  - `stop()` - Stop weather updates
  - `is_running()` - Check if running
  - `set_api_key(key)` - Set OpenWeatherMap API key
  - `set_location(location)` - Set location (city name)
  - `set_position(position)` - Set screen position
  - `set_font_size(size)` - Set font size
  - `set_text_color(color)` - Set text color
  - `cleanup()` - Clean up resources

**Private Methods**:
- `_fetch_weather()` - Fetch weather (uses cache if valid)
- `_on_weather_fetched(data)` - Handle fetched data
  - `_on_fetch_error(error)` - Handle fetch error
- `_is_cache_valid()` - Check cache validity
- `_update_display(data)` - Update widget display
- `_update_position()` - Update widget position

**Signals**:
- `weather_updated(dict)` - Emits weather data
- `error_occurred(str)` - Emits error message

**Features**:
- OpenWeatherMap API integration
- Background fetching with QThread
- 30-minute caching to reduce API calls
- Temperature in Celsius
- Weather condition display
- Location display
- 4 position options
- QTimer updates every 30 minutes
- Error handling with fallback to cache
- Customizable font and color
- Auto-positioning on parent resize

**Tested**: 21 tests covering API integration, caching, errors, and display

**Implemented**: Days 14-16

---

## Image Sources (`sources/`)

### `sources/base_provider.py`
**Purpose**: Abstract base for image providers  
**Key Classes**:
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
│   ├── base_transition.py
│   ├── crossfade_transition.py
│   ├── slide_transition.py
│   ├── wipe_transition.py
│   ├── diffuse_transition.py
│   ├── block_puzzle_flip_transition.py
│   ├── gl_crossfade_transition.py
│   ├── gl_slide_transition.py
│   ├── gl_wipe_transition.py
│   ├── gl_diffuse_transition.py
│   ├── gl_block_puzzle_flip_transition.py
│   └── overlay_manager.py
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
