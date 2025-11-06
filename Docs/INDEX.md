# ShittyRandomPhotoScreenSaver - Module Index

**Purpose**: Living file map of all modules, their purposes, and key classes/functions.  
**Last Updated**: Nov 6, 2025 - Phase 6 Complete (All Critical Bugs Fixed)  
**Implementation Status**: 🟢 Core Framework | 🟢 Animation | 🟢 Entry Point & Monitors | 🟢 Image Sources | 🟢 RSS Feeds | 🟢 Display & Rendering (+ Lanczos) | 🟢 Engine | 🟢 **Transitions (INTEGRATED!)** | 🟢 Pan & Scan | 🟢 Widgets | 🟢 UI | 🟢 Display Tab | 🟢 **RUNTIME STABLE**  
**Test Status**: 279 tests, 260 passing (93.2%), 18 failures (crossfade rewrite), 1 skipped  
**Note**: Update this file after any major structural changes.

**Recent Updates (Nov 6, 2025 - Phase 6)**:
- ✅ **ALL 8 CRITICAL BUGS FIXED** (Lanczos, transitions, multi-monitor, settings, quality, navigation)
- ✅ Crossfade transition completely rewritten for proper image blending
- ✅ Multi-monitor different image per display mode working
- ✅ Settings persistence fixed (signal blocking during load)
- ✅ Image quality improved with UnsharpMask for aggressive downscaling
- ✅ Fill/Fit modes corrected for proper aspect ratio and coverage
- ✅ Z/X navigation fully functional
- ✅ Test suite updated (260/279 passing)

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

### `rendering/image_processor.py` 🟢 COMPLETE + LANCZOS
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
- 🆕 **Lanczos resampling** via PIL/Pillow for industry-standard quality
- 🆕 **Optional sharpening filter** for downscaled images
- 🆕 **Automatic fallback** to Qt if PIL unavailable
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
**Status**: ✅ Implemented, 🆕 **Transitions Integrated!**, 🆕 **Clock Widget Working!**  
**Key Classes**:
- `DisplayWidget(QWidget)` - Fullscreen image display with transitions
  - `show_on_screen()` - Position fullscreen, **setup widgets**
  - `set_image(pixmap, path)` - **UPDATED**: Display with transition support
  - `_setup_widgets()` - **NEW**: Setup clock/weather widgets from settings
  - `_create_transition()` - **NEW**: Create transition from settings
  - `_on_transition_finished(pixmap, path)` - **NEW**: Handle transition completion
  - `set_display_mode(mode)` - Change display mode
  - `clear()` - **UPDATED**: Clear and stop transitions
  - `show_error(message)` - Display error message
  - `get_screen_info()` - Get display information
  - `paintEvent()` - Render current image or error
  - `keyPressEvent()` - **UPDATED**: Exit on any key (except hotkeys Z/X/C/S/Esc)
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
- Crossfade, Slide, Wipe, Diffuse, Block Puzzle Flip
- Reads settings from `transitions.*`
- Automatic cleanup on transition finish
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

## Transitions (`transitions/`) 🟡 PARTIAL

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

### `transitions/crossfade_transition.py` 🟢 COMPLETE
**Purpose**: Smooth opacity-based crossfade transition  
**Status**: ✅ Implemented, ✅ Tested (Day 9)  
**Key Classes**:
- `CrossfadeTransition(BaseTransition)` - Crossfade effect
  - `start(old_pixmap, new_pixmap, widget)` - Begin fade
  - `stop()` - Stop immediately
  - `cleanup()` - Clean up effect and animation
  - `set_easing(name)` - Set easing curve

**Private Methods**:
- `_show_image_immediately()` - Skip transition (first image)
- `_on_animation_value_changed(value)` - Track progress
- `_on_animation_finished()` - Handle completion
- `_get_easing_curve(name)` - Convert easing name to Qt curve

**Features**:
- QGraphicsOpacityEffect-based fading
- 21 easing curves supported:
  - Linear
  - Quad (In, Out, InOut)
  - Cubic (In, Out, InOut)
  - Quart (In, Out, InOut)
  - Quint (In, Out, InOut)
  - Sine (In, Out, InOut)
  - Expo (In, Out, InOut)
  - Circ (In, Out, InOut)
- Handles null old_pixmap (first image)
- Robust cleanup (try/catch for Qt deletions)
- Progress = inverse of opacity

**Tested**: 16 tests covering all functionality

**Implemented**: Day 9

---

### `transitions/slide_transition.py` 🟢 COMPLETE
**Purpose**: Directional slide transition effect  
**Status**: ✅ Implemented, ✅ Tested (Day 10)  
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
- Dual QPropertyAnimation (old out, new in)
- QLabel widgets for display
- 4 directional slides
- Position calculation per direction
- 21 easing curves supported
- Progress = distance traveled / total distance
- Synchronized dual animations
- Handles null old_pixmap

**Tested**: 13 tests covering all directions and functionality

**Implemented**: Day 10

---

### `transitions/diffuse_transition.py` 🟢 COMPLETE
**Purpose**: Random block reveal transition effect  
**Status**: ✅ Implemented, ✅ Tested (Day 10)  
**Key Classes**:
- `DiffuseTransition(BaseTransition)` - Diffuse effect
  - `start(old_pixmap, new_pixmap, widget)` - Begin diffuse
  - `stop()` - Stop immediately
  - `cleanup()` - Clean up label and timer
  - `set_block_size(size)` - Set block size

**Private Methods**:
- `_create_block_grid(width, height)` - Generate grid of blocks
- `_reveal_next_block()` - Reveal one block (timer callback)
- `_update_display()` - Composite pixmap with revealed blocks
- `_finish_transition()` - Complete transition
- `_show_image_immediately()` - Skip transition (first image)

**Features**:
- QTimer-based progressive reveal
- Block grid covering entire widget
- Random shuffle of reveal order
- Configurable block size (default: 50px)
- QPainter composite rendering
- Edge block size handling
- Progress = revealed blocks / total blocks
- Handles null old_pixmap

**Tested**: 14 tests covering block sizes, randomization, and functionality

**Implemented**: Day 10

---

### `transitions/block_puzzle_flip_transition.py` 🟢 COMPLETE ⭐ STAR FEATURE
**Purpose**: 3D block flip transition effect with grid  
**Status**: ✅ Implemented, ✅ Tested (Day 11)  
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

**Tested**: 18 tests covering grid creation, flip animation, randomization, and all functionality

**Implemented**: Day 11 ⭐ STAR FEATURE

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

### `ui/tabs/display_tab.py` 🆕 NEW!
**Purpose**: Display and quality configuration  
**Status**: ✅ Implemented Nov 6, 2025  
**Key Classes**:
- `DisplayTab(QWidget)` - Display settings tab
  - **Monitor Configuration**:
    - Monitor selection (All/Primary/Monitor 1-4)
    - Same image on all monitors toggle
  - **Display Mode**:
    - Mode dropdown (Fill/Fit/Shrink) with descriptions
  - **Image Timing**:
    - Rotation interval (1-3600 seconds)
    - Shuffle toggle
  - **Image Quality**:
    - High quality scaling (Lanczos) toggle
    - Sharpening filter toggle

**Settings Managed**:
- `display.monitor_selection` - all/primary/monitor_N
- `display.same_image_all_monitors` - bool
- `display.mode` - fill/fit/shrink
- `timing.interval` - seconds
- `queue.shuffle` - bool
- `display.use_lanczos` - bool
- `display.sharpen_downscale` - bool

**Features**: 
- Instant save
- String to bool conversion for settings
- Full descriptions for display modes
- Breathing room spacing (20px)

**Tab Order**: Second tab (after Sources, before Transitions)

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
