# Architecture Design

## Directory Structure

```
ShittyRandomPhotoScreenSaver/
├── main.py                           # Entry point, command-line handling
├── requirements.txt                   # Python dependencies
├── README.md                          # User documentation
│
├── core/                              # Core framework (adapted from reusables)
│   ├── __init__.py
│   ├── threading/
│   │   ├── __init__.py
│   │   └── manager.py                # ThreadManager (adapted)
│   ├── resources/
│   │   ├── __init__.py
│   │   ├── manager.py                # ResourceManager (adapted)
│   │   └── types.py                  # Resource types
│   ├── events/
│   │   ├── __init__.py
│   │   ├── event_system.py           # EventSystem (adapted)
│   │   └── event_types.py            # Event definitions
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── settings_manager.py       # SettingsManager (adapted)
│   │   └── types.py                  # Settings types
│   ├── animation/                     # CENTRALIZED ANIMATION FRAMEWORK
│   │   ├── __init__.py
│   │   ├── animator.py               # Animation manager and coordinator
│   │   ├── easing.py                 # Easing functions
│   │   └── types.py                  # Animation types and enums
│   └── logging/
│       ├── __init__.py
│       └── logger.py                 # Centralized logging
│
├── engine/                            # Screensaver engine
│   ├── __init__.py
│   ├── screensaver_engine.py         # Main controller
│   ├── display_manager.py            # Multi-monitor handling
│   └── image_queue.py                # Image queue management
│
├── sources/                           # Image providers
│   ├── __init__.py
│   ├── base_provider.py              # Abstract image provider
│   ├── folder_source.py              # Local folder scanning
│   └── rss_source.py                 # RSS feed parsing
│
├── rendering/                         # Display and rendering
│   ├── __init__.py
│   ├── display_widget.py             # Fullscreen display widget
│   ├── image_processor.py            # Scaling, cropping, processing
│   ├── pan_scan_animator.py          # Pan & scan logic
│   └── display_modes.py              # Fill/Fit/Shrink implementations
│
├── transitions/                       # Transition effects
│   ├── __init__.py
│   ├── base_transition.py            # Abstract transition
│   ├── crossfade.py                  # Crossfade transition
│   ├── slide.py                      # Slide transition
│   ├── diffuse.py                    # Diffuse transition
│   └── block_puzzle_flip.py          # Block puzzle flip (star feature)
│
├── widgets/                           # Overlay widgets
│   ├── __init__.py
│   ├── clock_widget.py               # Clock overlay
│   └── weather_widget.py             # Weather overlay
│
├── ui/                                # Configuration UI
│   ├── __init__.py
│   ├── settings_dialog.py            # Main settings window
│   ├── sources_tab.py                # Sources configuration
│   ├── transitions_tab.py            # Transitions configuration
│   ├── widgets_tab.py                # Widgets configuration
│   ├── about_tab.py                  # About page
│   └── preview_window.py             # Preview mode handler
│
├── utils/                             # Utilities
│   ├── __init__.py
│   ├── monitors.py                   # Multi-monitor utilities (adapted)
│   └── image_cache.py                # Image caching logic
│
├── themes/                            # Qt stylesheets (copied from reusables)
│   └── dark.qss                      # Dark theme
│
├── assets/                            # Static assets
│   ├── icons/                        # Application icons
│   └── fonts/                        # Custom fonts (if needed)
│
├── tests/                             # Unit tests
│   ├── __init__.py
│   ├── test_threading.py
│   ├── test_resources.py
│   ├── test_image_processor.py
│   ├── test_transitions.py
│   └── test_sources.py
│
├── logs/                              # Log directory (created at runtime)
│
├── Docs/                              # Documentation
│   ├── planning documents...
│   ├── INDEX.md
│   └── SPEC.md
│
└── MyReuseableUtilityModules/         # Historical reusable modules (fully integrated; directory removed)
    └── (various modules)
```

## Core Architecture Principles

### 1. Centralized Management
- **ThreadManager**: All async operations go through thread manager
- **ResourceManager**: All resources registered for deterministic cleanup
- **EventSystem**: All cross-module communication via event bus
- **SettingsManager**: Single source of truth for configuration
- **AnimationManager**: All animations (transitions, UI, widgets) go through centralized animator

### 2. Separation of Concerns
- **Sources**: Only responsible for finding/loading images
- **Rendering**: Only responsible for display and scaling
- **Transitions**: Only responsible for visual effects
- **Engine**: Orchestrates all components

### 3. Event-Driven Architecture
```
Event Flow:
1. Source emits "image.loaded" -> Engine receives
2. Engine emits "image.ready" -> DisplayWidget receives
3. DisplayWidget emits "transition.complete" -> Engine schedules next
4. Engine emits "image.request" -> Source loads next image
```

### 4. Thread Safety
- Main thread: UI updates only
- IO thread pool: File operations, network requests
- Compute thread pool: Image processing, scaling
- No shared mutable state without synchronization
- Qt signals/slots for cross-thread communication
- No Raw QTimers are allowed. No race conditions.

## Key Components

### ScreensaverEngine
**Responsibilities:**
- Initialize all subsystems
- Manage image queue
- Coordinate transitions
- Handle timing and scheduling
- Respond to user input (exit conditions)

**Dependencies:**
- ThreadManager
- ResourceManager
- EventSystem
- SettingsManager
- DisplayManager
- All image sources

### AnimationManager
**Responsibilities:**
- Centralized coordinator for ALL animations in the application
- Manage animation lifecycle (start, pause, stop, cancel)
- Provide consistent easing functions
- Track active animations and prevent conflicts
- Integrate with ResourceManager for cleanup
- Support parallel and sequential animation chains

**Animations Managed:**
- Transition effects (crossfade, slide, diffuse, block puzzle)
- UI animations (settings dialog transitions, widget fades)
- Widget animations (clock fade in/out, weather updates)
- Custom animations via extensible API

**Features:**
- FPS-independent timing (delta-time based)
- Easing curve library (linear, quad, cubic, elastic, bounce, etc.)
- Animation groups (parallel/sequential)
- Event callbacks (onStart, onUpdate, onComplete, onCancel)
- Resource-aware (registers animations with ResourceManager)

**Events Published:**
- `animation.started`
- `animation.progress` (with completion %)
- `animation.complete`
- `animation.cancelled`

**Dependencies:**
- ThreadManager (for UI thread dispatch)
- ResourceManager (for animation cleanup)
- EventSystem (for animation events)

### DisplayManager
**Responsibilities:**
- Detect and track all monitors
- Create DisplayWidget for each monitor
- Synchronize or distribute images per settings
- Handle monitor hotplug events

**Events Published:**
- `monitor.connected`
- `monitor.disconnected`
- `display.ready`

### ImageProvider (Abstract Base)
**Responsibilities:**
- Define interface for all image sources
- Provide metadata about available images
- Load images on demand

**Implementations:**
- FolderSource: Scan directories
- RSSSource: Parse feeds and download

### DisplayWidget
**Responsibilities:**
- Fullscreen window on assigned monitor
- Render current image with display mode
- Execute transitions
- Host overlay widgets (clock, weather)
- Capture mouse/keyboard for exit

**Events Published:**
- `transition.started`
- `transition.complete`
- `user.input` (exit trigger)

### TransitionEngine
**Responsibilities:**
- Execute requested transition
- Manage transition state
- Notify completion

**Transitions:**
- Crossfade
- Slide
- Diffuse
- BlockPuzzleFlip

## Data Flow

### Startup Sequence
```
1. main.py parses command-line args
2. Initialize core systems (Threading, Resources, Events, Settings)
3. Load theme (dark.qss)
4. If /c -> Launch SettingsDialog
5. If /p <hwnd> -> Launch PreviewWindow
6. If /s -> Launch ScreensaverEngine
   a. Load settings
   b. Initialize image sources
   c. Create DisplayManager
   d. Start image queue
   e. Begin slideshow
```

### Image Display Cycle
```
1. Engine requests next image from queue
2. Source loads image (on IO thread)
3. ImageProcessor scales/crops (on Compute thread)
4. Engine emits "image.ready"
5. DisplayWidget receives image
6. Transition starts (old -> new)
7. Transition completes
8. Engine schedules timer for next image
9. Repeat
```

### Multi-Monitor Synchronization
```
Same Mode:
- Single image queue
- DisplayManager broadcasts same image to all widgets
- Transitions synchronized

Different Mode:
- Separate queue per monitor
- Independent timing and transitions

Per-Monitor Mode:
- Separate sources per monitor
- Independent settings per monitor
```

## Error Handling Strategy

### Principle: Fail Explicitly, Degrade Gracefully

1. **Image Loading Failure**
   - Log error with full path and reason
   - Skip to next image
   - If all fail, display error message on screen
   - Never crash

2. **RSS Feed Failure**
   - Log error with URL and HTTP status
   - Fall back to cached images if available
   - Continue with folder sources
   - Retry on next scheduled update

3. **Weather API Failure**
   - Log error
   - Display last known weather
   - Retry on next scheduled update
   - Never block screensaver start
   - If all fail, do not display widget at all.

4. **Monitor Hotplug**
   - Detect via Qt screen change events
   - Create/destroy DisplayWidgets dynamically
   - Preserve settings per monitor ID
   - Log all changes

5. **Resource Exhaustion**
   - Monitor memory usage
   - Evict cached images when threshold reached
   - Log warnings before reaching limits
   - Never OOM crash

## Integration Points

### With Reusable Modules
- Copy modules from `MyReuseableUtilityModules/` to `core/`
- Update all import paths to match new structure
- Adapt ThreadManager for screensaver workloads
- Adapt ResourceManager for image cache management
- Use EventSystem for loose coupling
- Use SettingsManager with QSettings backend

### With Qt
- PySide6.QtWidgets for UI
- PySide6.QtCore for signals/threading
- PySide6.QtGui for graphics
- PySide6.QtNetwork for RSS/weather (optional, can use requests)

### With Windows
- Command-line args for screensaver protocol
- .scr file extension
- Win32 API for preview window embedding (via QWindow.fromWinId)
- System32 installation for system-wide access

## Performance Considerations

### Memory Management
- LRU cache: Keep 10-20 images in memory
- Preload next 3-5 images
- Evict based on memory threshold
- Use QPixmap for GPU-accelerated rendering

### Threading Strategy
- IO Pool (4 workers): File/network operations
- Compute Pool (N-1 workers): Image processing
- UI Thread: Qt updates only
- No blocking operations on main thread

### Optimization Targets
- 60 FPS transitions
- < 500MB memory usage
- < 2s startup time
- Smooth 4K multi-monitor

## Testing Strategy
- Unit tests for all core modules
- Integration tests for image sources
- Visual tests for transitions (manual)
- Performance profiling with cProfile
- Memory profiling with memory_profiler
- Long-duration stress tests (24+ hours)

---

**Next Document**: `02_REUSABLE_MODULES_INTEGRATION.md` - Integration plan for reusable modules
