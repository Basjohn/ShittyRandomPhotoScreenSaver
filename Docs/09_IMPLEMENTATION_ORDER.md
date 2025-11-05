# Implementation Order

This document outlines the exact order in which to implement the screensaver, with checkboxes for tracking progress.

---

## Phase 1: Foundation Setup (Week 1, Days 1-2)

### Day 1: Project Structure & Core Modules ✅ COMPLETE

- [x] Create directory structure
  - [x] Create `core/`, `engine/`, `sources/`, `rendering/`, `transitions/`, `widgets/`, `ui/`, `utils/`, `themes/`, `tests/`, `logs/`
  - [x] Create all `__init__.py` files

- [x] Copy and adapt reusable modules
  - [x] Copy `ThreadManager` from `MyReuseableUtilityModules/core/threading/` to `core/threading/`
  - [x] Update ThreadManager imports
  - [x] Remove CAPTURE and RENDER pool types (kept IO and COMPUTE only)
  - [x] Adjust pool sizes for screensaver (IO: 4, COMPUTE: cpu_count-1)

  - [x] Copy `ResourceManager` from `MyReuseableUtilityModules/core/resources/` to `core/resources/`
  - [x] Update ResourceManager imports
  - [x] Add IMAGE_CACHE, TEMP_IMAGE, NETWORK_REQUEST resource types

  - [x] Copy `EventSystem` from `MyReuseableUtilityModules/core/events/` to `core/events/`
  - [x] Update EventSystem imports
  - [x] Create `event_types.py` with screensaver events (all image, display, monitor, user, source, settings events)

  - [x] Copy `SettingsManager` from `MyReuseableUtilityModules/core/settings/` to `core/settings/`
  - [x] Update SettingsManager to use QSettings
  - [x] Create default settings schema (sources, display, transitions, timing, widgets, multi-monitor)

  - [x] Copy logging utilities to `core/logging/logger.py`
  - [x] Configure rotating file handler (10MB, 5 backups)
  - [x] Setup log directory (`logs/screensaver.log`)
  - [x] Add ColoredFormatter for debug mode (cyan=DEBUG, green=INFO, yellow=WARNING, red=ERROR, magenta=CRITICAL)

  - [x] Copy `dark.qss` to `themes/` (1147 lines)
  - [x] Copy lock-free utilities (`utils/lockfree/`) - SPSCQueue, TripleBuffer

- [x] Test core modules
  - [x] Create `tests/conftest.py` with fixtures (qt_app, settings_manager, thread_manager, resource_manager, event_system, temp_image)
  - [x] Create `tests/test_threading.py` - 5 tests passing ✅
  - [x] Create `tests/test_resources.py` - 6 tests passing ✅
  - [x] Create `tests/test_events.py` - 6 tests passing ✅
  - [x] Create `tests/test_settings.py` - 6 tests passing ✅

- [x] Create `requirements.txt` with PySide6, requests, pytz, pytest, pytest-qt

**Day 1 Status**: ✅ **23/23 tests passing (100%)** | **Documentation updated** (INDEX.md, TestSuite.md, PLANNING_COMPLETE.md)

### Day 2: Basic Infrastructure ✅ COMPLETE

- [x] Create `main.py`
  - [x] Implement command-line argument parsing (/s, /c, /p with window handle)
  - [x] Add logging setup (setup_logging called with --debug flag support)
  - [x] Add basic QApplication initialization
  - [x] Test `/s`, `/c`, `/p` argument handling (verified in logs)

- [x] Create monitor utilities (`utils/monitors.py`)
  - [x] Simplified from `MyReuseableUtilityModules/utils/window/monitors.py` (652 → 270 lines)
  - [x] Multi-monitor detection with DPI scaling support
  - [x] DPI-aware resolution detection (physical vs logical pixels)
  - [x] Screen geometry and info functions (get_physical_resolution, get_screen_info_dict)
  - [x] Virtual desktop rectangle calculation
  - [x] Comprehensive logging with both physical and logical resolutions

- [x] **CHECKPOINT**: Verify all core systems work independently

**Day 2 Status**: ✅ **Core infrastructure ready** | **Multi-monitor + DPI scaling functional** | **Command-line parsing functional**

---

## Phase 2: Image Sources (Week 1, Days 3-4)

### Day 3: Folder Source ✅ COMPLETE

- [x] Create `sources/base_provider.py`
  - [x] Define `ImageMetadata` dataclass (with local_path, url, metadata fields)
  - [x] Define `ImageProvider` abstract base (get_images, refresh, is_available)
  - [x] Define `ImageSourceType` enum (FOLDER, RSS, CUSTOM)

- [x] Create `sources/folder_source.py`
  - [x] Implement folder scanning (glob pattern-based)
  - [x] Implement recursive search (using **/* pattern)
  - [x] Add support for all image formats (jpg, png, bmp, gif, webp, tiff, ico, jfif)
  - [x] Implement metadata extraction (file stats, paths, timestamps)
  - [x] Add error handling for missing folders and permission errors

- [x] Create `utils/image_cache.py`
  - [x] Implement LRU cache (OrderedDict-based)
  - [x] Add cache size management (max_items + max_memory_mb)
  - [x] Add eviction logic (automatic LRU eviction)
  - [x] Memory estimation for QPixmap

- [x] Test folder source
  - [x] Tested folder scanning (137 images found in 0.03s)
  - [x] Tested supported extensions (all formats working)
  - [x] Tested cache functionality (LRU eviction, hits/misses working)

**Day 3 Status**: ✅ **Image sources ready** | **137 test images scanned** | **LRU cache functional (5 items, 4MB memory)**

### Day 4: Centralized Animation Framework ✅ COMPLETE

- [x] Create `core/animation/types.py`
  - [x] Define `AnimationType` enum (PROPERTY, CUSTOM, GROUP)
  - [x] Define `EasingCurve` enum (24 curves: linear, quad, cubic, quart, quint, sine, expo, circ, elastic, back, bounce)
  - [x] Define `AnimationState` enum (IDLE, RUNNING, PAUSED, COMPLETE, CANCELLED)
  - [x] Define dataclasses (AnimationConfig, PropertyAnimationConfig, CustomAnimationConfig, AnimationGroupConfig)

- [x] Create `core/animation/easing.py`
  - [x] Implement all easing functions (linear, quad_in/out/in_out, cubic, quart, quint, sine, expo, circ, elastic, back, bounce)
  - [x] Create easing function lookup table (EASING_FUNCTIONS dict)
  - [x] Create get_easing_function() and ease() utilities
  - [x] All curves tested (24 total)

- [x] Create `core/animation/animator.py`
  - [x] Implement `Animation` base class (delta-time updates, state management)
  - [x] Implement `PropertyAnimator` (animates Qt properties with interpolation)
  - [x] Implement `CustomAnimator` (custom update callbacks)
  - [x] Implement `AnimationManager` (centralized coordinator with QTimer)
  - [x] Add lifecycle management (start, pause, resume, cancel, cancel_all)
  - [x] Add signal-based callbacks (started, progress_changed, completed, cancelled)
  - [x] FPS-independent timing (60 FPS default, delta-time based)

- [x] Test animation framework
  - [x] Create `tests/test_animation.py` (10 tests)
  - [x] Test manager initialization
  - [x] Test property animation (opacity animation on QGraphicsOpacityEffect)
  - [x] Test custom animation (progress callbacks)
  - [x] Test pause/resume functionality
  - [x] Test animation cancel
  - [x] Test all easing curves (linear, quad, sine, elastic, bounce, back)
  - [x] Test animation with delay
  - [x] Test multiple simultaneous animations
  - [x] Test cancel all animations
  - [x] Test auto-stop when no animations active

**Day 4 Status**: ✅ **Animation framework complete** | **33/33 tests passing (100%)** | **24 easing curves** | **3 animator types**

### Day 5: RSS Source ✅ COMPLETE

- [x] Research safe public RSS feeds
  - [x] NASA Image of the Day: `https://www.nasa.gov/feeds/iotd-feed`
  - [x] NASA Breaking News: `https://www.nasa.gov/news-release/feed/`
  - [x] Wikimedia Picture of the Day: `https://commons.wikimedia.org/w/api.php?action=featuredfeed&feed=potd&feedformat=rss&language=en`
  - [x] Default feeds configured in DEFAULT_RSS_FEEDS dict

- [x] Create `sources/rss_source.py` (382 lines)
  - [x] Implement RSS/Atom feed parsing with feedparser
  - [x] Implement image download with requests (streaming)
  - [x] Add caching to temp directory with MD5 hash filenames
  - [x] Add error handling for failed feeds (with [FALLBACK] logging)
  - [x] Support multiple feed URLs simultaneously
  - [x] Extract images from media:content, enclosures, img tags
  - [x] Cache cleanup based on size limit (LRU by modification time)
  - [x] Feed metadata tracking (title, entries, update time)

- [x] Add dependencies
  - [x] Add feedparser>=6.0.10 to requirements.txt

- [x] Create test script
  - [x] Create `test_rss_source.py` for manual testing
  - [x] Test default NASA feeds
  - [x] Test custom Wikimedia feed
  - [x] Test cache management

- [x] **CHECKPOINT**: Can load images from folders and RSS feeds

**Day 5 Status**: ✅ **RSS source complete** | **3 default safe feeds** | **Auto-caching** | **[FALLBACK] error handling**

---

## Phase 3: Display & Rendering (Week 1, Day 5 - Week 2, Day 1)

### Day 6: Image Processing & Display Widget ✅ COMPLETE

- [x] Create `rendering/display_modes.py` (45 lines)
  - [x] Define `DisplayMode` enum (FILL, FIT, SHRINK)
  - [x] Add from_string() factory method
  - [x] Add string conversion

- [x] Create `rendering/image_processor.py` (281 lines)
  - [x] Implement FILL mode (primary) - scale and crop to fill screen
  - [x] Implement FIT mode - scale to fit with letterboxing
  - [x] Implement SHRINK mode - only scale down, never upscale
  - [x] Proper aspect ratio calculations
  - [x] QPainter-based rendering
  - [x] Center alignment for all modes
  - [x] Helper methods: calculate_scale_factors(), get_crop_rect()

- [x] Create `rendering/display_widget.py` (238 lines)
  - [x] Fullscreen QWidget with frameless window
  - [x] Image display with ImageProcessor integration
  - [x] Input handling (exit on any key press or mouse click)
  - [x] Error message display (centered white text)
  - [x] Signal-based architecture (exit_requested, image_displayed)
  - [x] Per-screen positioning
  - [x] Blank cursor in fullscreen
  - [x] Black background

- [x] Create `engine/display_manager.py` (263 lines)
  - [x] Multi-monitor detection (QGuiApplication.screens())
  - [x] Create DisplayWidget per monitor
  - [x] Monitor hotplug handling (screenAdded/screenRemoved signals)
  - [x] Same image mode (all screens show same image)
  - [x] Different image mode support (per-screen images)
  - [x] Coordinated exit (any display triggers exit for all)
  - [x] Dynamic display creation/cleanup
  - [x] Error message propagation

- [x] Test image processor
  - [x] Create `tests/test_image_processor.py` (18 tests)
  - [x] Test FILL mode (wider, taller, small images)
  - [x] Test FIT mode (landscape, portrait)
  - [x] Test SHRINK mode (large and small images)
  - [x] Test null image fallback
  - [x] Test aspect ratio preservation
  - [x] Test scale factor calculations
  - [x] Test crop rectangle calculations
  - [x] Test DisplayMode enum

- [x] Manual test script
  - [x] Create `test_display.py` for manual fullscreen testing

- [x] **CHECKPOINT**: Can display images fullscreen on all monitors ✅

**Day 6 Status**: ✅ **Display system complete** | **51/51 tests passing** | **3 display modes** | **Multi-monitor support** | **Hotplug detection**

---

## Phase 4: Basic Engine & Image Queue (Week 2, Days 2-3)

### Day 7: Image Queue

- [ ] Create `engine/image_queue.py`
  - [ ] Implement queue management
  - [ ] Add shuffle functionality
  - [ ] Add history tracking
  - [ ] Add queue wraparound

### Day 8: Screensaver Engine (Basic)

- [ ] Create `engine/screensaver_engine.py`
  - [ ] Initialize all core systems
  - [ ] Initialize image sources
  - [ ] Create display manager
  - [ ] Build image queue
  - [ ] Implement image rotation timer
  - [ ] Add image loading (async)
  - [ ] Add event subscriptions
  - [ ] Implement exit handling
  - [ ] Add cleanup

- [ ] Test basic engine
  - [ ] Create `tests/test_integration.py`
  - [ ] Test engine initialization
  - [ ] Test image queue population
  - [ ] Test image rotation

- [ ] **CHECKPOINT**: Basic slideshow works with instant transitions

---

## Phase 5: Transitions (Week 2, Days 4-5 - Week 3, Day 1)

### Day 9: Base Transition & Crossfade

- [ ] Create `transitions/base_transition.py`
  - [ ] Define abstract base class
  - [ ] Add signals for finished/progress

- [ ] Create `transitions/crossfade.py`
  - [ ] Implement opacity-based crossfade
  - [ ] Use Qt animations
  - [ ] Add cleanup

- [ ] Integrate crossfade into DisplayWidget
  - [ ] Update `rendering/display_widget.py`
  - [ ] Add transition execution
  - [ ] Connect transition signals

- [ ] Test crossfade
  - [ ] Create `tests/test_transitions.py`
  - [ ] Test crossfade creation
  - [ ] Test animation completion

### Day 10: Slide & Diffuse Transitions

- [ ] Create `transitions/slide.py`
  - [ ] Implement slide animation
  - [ ] Support all directions
  - [ ] Use Qt animations

- [ ] Create `transitions/diffuse.py`
  - [ ] Implement random block reveal
  - [ ] Add configurable block size
  - [ ] Optimize for performance

- [ ] Test slide and diffuse
  - [ ] Test slide directions
  - [ ] Test diffuse block reveal

### Day 11: Block Puzzle Flip Transition ⭐

- [ ] Create `transitions/block_puzzle_flip.py`
  - [ ] Implement grid-based blocks
  - [ ] Create QGraphicsScene/QGraphicsView
  - [ ] Implement 3D flip effect
  - [ ] Add random order flipping
  - [ ] Add configurable grid size
  - [ ] Optimize performance

- [ ] Create `transitions/__init__.py`
  - [ ] Add transition factory function
  - [ ] Register all transitions

- [ ] Test block puzzle flip
  - [ ] Test different grid sizes
  - [ ] Test flip animation
  - [ ] Test performance on large grids

- [ ] **CHECKPOINT**: All transitions work smoothly

---

## Phase 6: Pan & Scan (Week 3, Days 2-3)

### Day 12: Pan & Scan Animator

- [ ] Create `rendering/pan_scan_animator.py`
  - [ ] Implement zoom logic
  - [ ] Implement pan movement
  - [ ] Add smooth easing
  - [ ] Support configurable speed and zoom
  - [ ] Add timer-based updates

### Day 13: Integrate Pan & Scan

- [ ] Integrate into DisplayWidget
  - [ ] Update `rendering/display_widget.py`
  - [ ] Add pan & scan mode option
  - [ ] Connect to settings

- [ ] Test pan & scan
  - [ ] Test smooth movement
  - [ ] Test different zoom levels
  - [ ] Test performance

- [ ] **CHECKPOINT**: Pan & scan works smoothly

---

## Phase 7: Overlay Widgets (Week 3, Days 4-5 - Week 4, Day 1)

### Day 14: Clock Widget

- [ ] Create `widgets/clock_widget.py`
  - [ ] Implement digital clock
  - [ ] Add 12h/24h format
  - [ ] Add timezone support
  - [ ] Add update timer
  - [ ] Style with dark theme
  - [ ] Position according to settings

- [ ] Test clock widget
  - [ ] Test time updates
  - [ ] Test timezone handling
  - [ ] Test positioning

### Day 15: Weather Widget

- [ ] Create `widgets/weather_provider.py`
  - [ ] Implement wttr.in API integration
  - [ ] Add caching
  - [ ] Add error handling

- [ ] Create `widgets/weather_widget.py`
  - [ ] Implement weather display
  - [ ] Add temperature, condition, location
  - [ ] Add update timer (30 min)
  - [ ] Style with dark theme
  - [ ] Position according to settings

- [ ] Test weather widget
  - [ ] Test API calls
  - [ ] Test caching
  - [ ] Test error handling

### Day 16: Integrate Widgets

- [ ] Integrate into DisplayWidget
  - [ ] Update `rendering/display_widget.py`
  - [ ] Add clock widget creation
  - [ ] Add weather widget creation
  - [ ] Connect to settings
  - [ ] Handle enable/disable

- [ ] **CHECKPOINT**: Clock and weather overlays work

---

## Phase 8: Configuration UI (Week 4, Days 2-5 - Week 5, Day 1)

### Day 17: Settings Dialog Base

- [ ] Create `ui/settings_dialog.py`
  - [ ] Create main dialog window
  - [ ] Apply dark.qss theme
  - [ ] Create side tab bar
  - [ ] Create stacked widget for tabs
  - [ ] Wire tab switching

- [ ] Test settings dialog
  - [ ] Test theme application
  - [ ] Test tab switching

### Day 18: Sources Tab

- [ ] Create `ui/sources_tab.py`
  - [ ] Add folder list widget
  - [ ] Add folder browse button
  - [ ] Add folder remove button
  - [ ] Add RSS feed list widget
  - [ ] Add RSS input field
  - [ ] Add RSS add/remove buttons
  - [ ] Add source mode checkboxes
  - [ ] Connect to settings manager
  - [ ] Implement instant save

- [ ] Test sources tab
  - [ ] Test folder addition/removal
  - [ ] Test RSS addition/removal
  - [ ] Test settings persistence

### Day 19: Transitions Tab

- [ ] Create `ui/transitions_tab.py`
  - [ ] Add transition type selector
  - [ ] Add duration slider
  - [ ] Add display mode selector
  - [ ] Add pan & scan options
  - [ ] Add block puzzle grid config
  - [ ] Connect to settings manager
  - [ ] Implement instant save

- [ ] Test transitions tab
  - [ ] Test all transition types
  - [ ] Test settings changes

### Day 20: Widgets Tab

- [ ] Create `ui/widgets_tab.py`
  - [ ] Add clock enable checkbox
  - [ ] Add clock format selector (12h/24h)
  - [ ] Add clock timezone input
  - [ ] Add clock position selector
  - [ ] Add multiple clocks dialog
  - [ ] Add weather enable checkbox
  - [ ] Add weather location input (with autocomplete)
  - [ ] Add weather position selector
  - [ ] Add transparency sliders
  - [ ] Connect to settings manager
  - [ ] Implement instant save

- [ ] Test widgets tab
  - [ ] Test clock settings
  - [ ] Test weather settings
  - [ ] Test multiple timezones

### Day 21: About Tab & Preview

- [ ] Create `ui/about_tab.py`
  - [ ] Add application info
  - [ ] Add version
  - [ ] Add credits

- [ ] Create `ui/preview_window.py`
  - [ ] Implement `/p <hwnd>` preview mode
  - [ ] Embed in Windows preview window
  - [ ] Scale down for preview

- [ ] Test complete UI
  - [ ] Test all tabs
  - [ ] Test settings persistence
  - [ ] Test preview mode

- [ ] **CHECKPOINT**: Complete configuration UI works

---

## Phase 9: Testing & Polish (Week 5, Days 2-5)

### Day 22: Unit Test Coverage

- [ ] Expand test coverage
  - [ ] Ensure all modules have tests
  - [ ] Add edge case tests
  - [ ] Add error handling tests
  - [ ] Run full test suite with logging

### Day 23: Integration Testing

- [ ] Test complete workflows
  - [ ] Test startup -> slideshow -> exit
  - [ ] Test config -> save -> run
  - [ ] Test all transition types
  - [ ] Test multi-monitor scenarios
  - [ ] Test monitor hotplug

### Day 24: Performance Testing

- [ ] Profile performance
  - [ ] Test memory usage
  - [ ] Test CPU usage during transitions
  - [ ] Test long-duration stability
  - [ ] Optimize bottlenecks

### Day 25: Bug Fixes & Polish

- [ ] Fix identified bugs
- [ ] Polish transitions
- [ ] Optimize image loading
- [ ] Improve error messages
- [ ] Add logging where needed

- [ ] **CHECKPOINT**: All features work, tests pass

---

## Phase 10: Deployment (Week 6, Days 1-2)

### Day 26: Build & Package

- [ ] Create `screensaver.spec` for PyInstaller
- [ ] Create build script
- [ ] Build .exe
- [ ] Rename to .scr
- [ ] Test built package

### Day 27: Installation & Documentation

- [ ] Create installation instructions
- [ ] Create user documentation
- [ ] Create README.md
- [ ] Test system installation
- [ ] Test preview in Windows settings

- [ ] **CHECKPOINT**: Deployable package ready

---

## Phase 11: Finalization (Week 6, Day 3)

### Day 28: Final Testing & Cleanup

- [ ] Run complete test suite
- [ ] Test on clean Windows install
- [ ] Verify all features work
- [ ] Clean up code
- [ ] Remove debug code
- [ ] Finalize documentation

### Reusable Modules Cleanup

- [ ] Verify all modules copied and adapted
- [ ] Update SPEC.md and INDEX.md
- [ ] Add note that reusable modules are fully integrated
- [ ] **DELETE or .gitignore `MyReuseableUtilityModules/`**

---

## Completion Checklist

- [ ] All core systems implemented
- [ ] All image sources implemented
- [ ] All display modes implemented
- [ ] All transitions implemented
- [ ] Pan & scan implemented
- [ ] Clock widget implemented
- [ ] Weather widget implemented
- [ ] Configuration UI implemented
- [ ] All tests passing
- [ ] Performance targets met
- [ ] Package built and tested
- [ ] Documentation complete
- [ ] Reusable modules integrated and cleaned up

---

## Notes

- Use logging for all debugging (terminal output unreliable)
- Run pytest with logging to file
- Test after each major component
- Commit to git after each checkpoint
- Keep SPEC.md and INDEX.md updated

---

**FINAL DELIVERABLE**: Working .scr file that can be installed in Windows and functions as a full-featured screensaver with all requested capabilities.
