# ShittyRandomPhotoScreenSaver - Technical Specification

**Version**: 1.0  
**Last Updated**: Nov 6, 2025 21:30 - Audit Session  
**Status**: Architecture Solid, 3 Transition Visual Bugs Remain

---

## Project Summary

A modern, feature-rich Windows screensaver built with PySide6 that displays photos from local folders or RSS feeds with advanced transitions, multi-monitor support, and overlay widgets (clock and weather).

---

## Core Requirements

### Functional Requirements

#### 1. Image Sources
- **FR-1.1**: Support local folder scanning (recursive)
- **FR-1.2**: Support RSS/Atom feed parsing for images
- **FR-1.3**: Support mixed mode (folders + RSS simultaneously)
- **FR-1.4**: Support common image formats: JPG, PNG, BMP, GIF, WebP, TIFF

#### 2. Display Modes
- **FR-2.1**: Fill mode - crop and scale to fill screen without letterboxing (PRIMARY) ✅ IMPLEMENTED
- **FR-2.2**: Fit mode - scale to fit within screen with letterboxing ✅ IMPLEMENTED
- **FR-2.3**: Shrink mode - only scale down, never upscale ✅ IMPLEMENTED
- **FR-2.4**: Pan & scan - animated movement across zoomed images ✅ IMPLEMENTED (Days 12-13)
  - Ken Burns effect with zoom and pan
  - 6 pan directions + random
  - Configurable zoom range and duration
  - Smooth cubic easing

#### 3. Transitions
- **FR-3.1**: Crossfade - opacity-based smooth transition ✅ WORKING
  - 21 easing curves supported
  - Configurable duration
  - Signal-based progress tracking
  - ResourceManager integration (Nov 6 Audit)
  - Memory leaks fixed (Nov 6 Audit)
- **FR-3.2**: Slide - directional slide (left/right/up/down) ✅ WORKING (Day 10)
  - 4 directions: LEFT, RIGHT, UP, DOWN
  - Dual animation (old out, new in)
  - 21 easing curves
  - ResourceManager integration (Nov 6 Audit)
  - Memory leaks fixed (Nov 6 Audit)
- **FR-3.3**: Wipe - progressive reveal transition 🔴 VISUAL BUG (Day 9)
  - 4 directions: LEFT_TO_RIGHT, RIGHT_TO_LEFT, TOP_TO_BOTTOM, BOTTOM_TO_TOP
  - Architecture fixed (constructor, memory leaks, ResourceManager)
  - 🔴 **BUG**: Wrong size/scaling in reveal
- **FR-3.4**: Diffuse - random block reveal 🔴 VISUAL BUG (Day 10)
  - Random block reveal order
  - Configurable block size
  - Timer-based progressive reveal
  - Architecture fixed (memory leaks, ResourceManager)
  - 🔴 **BUG**: Black boxes instead of transparent holes
- **FR-3.5**: Block Puzzle Flip - 3D flip effect with configurable grid 🔴 VISUAL BUG ⭐ STAR FEATURE (Day 11)
  - Grid-based block flipping
  - 3D horizontal scaling effect
  - Architecture fixed (memory leaks, ResourceManager, imports)
  - 🔴 **BUG**: Wrong block sizing, doesn't flip whole image
  - Random flip order
  - Configurable grid size and flip duration

#### 4. Multi-Monitor Support
- **FR-4.1**: Detect all connected monitors
- **FR-4.2**: Same image mode - synchronized display across all monitors
- **FR-4.3**: Different image mode - independent images per monitor
- **FR-4.4**: Handle monitor hotplug (connect/disconnect)

#### 5. Overlay Widgets
- **FR-5.1**: Clock widget - digital, 12h/24h, timezone support ✅ IMPLEMENTED (Days 14-16)
  - 12h/24h format with TimeFormat enum
  - Show/hide seconds option
  - 6 position options
  - Auto-update every second
  - Customizable styling
- **FR-5.2**: Weather widget - temperature, condition, location ✅ IMPLEMENTED (Days 14-16)
  - OpenWeatherMap API integration
  - Background fetching with QThread
  - 30-minute caching
  - 4 position options
  - Error handling
- **FR-5.3**: Configurable position, transparency, and size
- **FR-5.4**: Multiple clock support for different timezones

#### 6. Configuration
- **FR-6.1**: Dark-themed settings dialog
- **FR-6.2**: Four tabs: Sources, Transitions, Widgets, About
- **FR-6.3**: Instant save and apply
- **FR-6.4**: Persistent settings

#### 7. Windows Integration
- **FR-7.1**: Support `/s` argument (run screensaver)
- **FR-7.2**: Support `/c` argument (configuration)
- **FR-7.3**: Support `/p <hwnd>` argument (preview mode)
- **FR-7.4**: .scr file format

### Non-Functional Requirements

#### 1. Performance
- **NFR-1.1**: 60 FPS transitions on 1080p displays
- **NFR-1.2**: < 500MB memory usage
- **NFR-1.3**: < 2 second startup time
- **NFR-1.4**: Smooth operation on dual 4K monitors

#### 2. Reliability
- **NFR-2.1**: No crashes on missing images
- **NFR-2.2**: Graceful handling of failed RSS feeds
- **NFR-2.3**: Graceful handling of failed weather API
- **NFR-2.4**: No memory leaks during extended runs

#### 3. Quality
- **NFR-3.1**: Unit test coverage for all core modules
- **NFR-3.2**: Logging-first debugging policy
- **NFR-3.3**: No silent fallbacks
- **NFR-3.4**: Professional UI with dark theme
- **NFR-3.5**: Root cause fixes over mitigation/workarounds
- **NFR-3.6**: Main functionality prioritized over fallbacks
- **NFR-3.7**: Fallbacks must log distinctly with colored/styled warnings

---

## Architecture

### Core Systems

#### 1. ThreadManager
- **Purpose**: Centralized thread pool management
- **Pools**: IO (4 workers), COMPUTE (N-1 workers)
- **Features**: Task submission, callbacks, timers, UI dispatch

#### 2. ResourceManager
- **Purpose**: Deterministic resource cleanup
- **Features**: Registration, type tracking, cleanup ordering
- **Types**: GUI_COMPONENT, WINDOW, TIMER, FILE_HANDLE, IMAGE_CACHE

#### 3. EventSystem
- **Purpose**: Loose coupling via publish-subscribe
- **Features**: Priorities, filtering, UI dispatch, history
- **Events**: image.loaded, transition.complete, user.input, etc.

#### 4. SettingsManager
- **Purpose**: Persistent configuration
- **Backend**: QSettings
- **Features**: Type-safe get/set, change notifications, defaults

### Application Components

#### 1. ScreensaverEngine
- **Role**: Main controller
- **Responsibilities**: 
  - Initialize all subsystems
  - Manage image queue
  - Coordinate image loading and display
  - Handle timing and scheduling
  - Exit coordination

#### 2. DisplayManager
- **Role**: Multi-monitor coordinator
- **Responsibilities**:
  - Detect monitors
  - Create DisplayWidget per monitor
  - Synchronize or distribute images
  - Handle hotplug

#### 3. ImageProvider (Abstract)
- **Implementations**: FolderSource, RSSSource
- **Interface**: get_images(), refresh()
- **Returns**: List[ImageMetadata]

#### 4. DisplayWidget
- **Role**: Fullscreen display on one monitor
- **Responsibilities**:
  - Render images
  - Execute transitions
  - Host widgets (clock, weather)
  - Capture input for exit

#### 5. Transitions
- **Base**: BaseTransition (abstract) ✅ IMPLEMENTED
  - QABCMeta metaclass (QObject + ABC)
  - TransitionState enum
  - Signals: started, finished, progress, error
  - Methods: start(), stop(), cleanup()
- **Types**:
  - Crossfade ✅ IMPLEMENTED (Day 9) - QGraphicsOpacityEffect
  - Slide ✅ IMPLEMENTED (Day 10) - QPropertyAnimation with 4 directions
  - Diffuse ✅ IMPLEMENTED (Day 10) - QTimer with random block reveal
  - BlockPuzzleFlip ✅ IMPLEMENTED (Day 11) - 3D flip with grid (STAR FEATURE)
- **Interface**: start(old, new, widget), stop(), finished signal
- **Features**: Progress tracking (0.0-1.0), configurable duration, easing curves

#### 6. Overlay Widgets
- **Types**: ClockWidget, WeatherWidget
- **Features**: Position, transparency, auto-update

#### 7. Configuration UI
- **Main**: SettingsDialog
- **Tabs**: SourcesTab, TransitionsTab, WidgetsTab, AboutTab
- **Theme**: dark.qss

---

## Data Flow

### Startup Sequence
```
1. Parse command-line arguments
2. Initialize core systems (Threading, Resources, Events, Settings)
3. Load theme
4. Route based on argument:
   - /s -> ScreensaverEngine
   - /c -> SettingsDialog
   - /p <hwnd> -> PreviewWindow
```

### Image Display Cycle
```
1. Engine requests next image from queue
2. Source loads image (IO thread)
3. ImageProcessor scales/crops (Compute thread)
4. Engine publishes "image.ready" event
5. DisplayWidget receives event
6. Transition executes (old -> new)
7. Transition emits "finished"
8. Engine schedules timer for next image
```

### Exit Sequence
```
1. User input detected (mouse/keyboard)
2. DisplayWidget publishes "user.input"
3. Engine receives event
4. Engine publishes "exit.request"
5. Engine stops timers
6. ResourceManager.shutdown() - deterministic cleanup
7. Application quits
```

---

## Settings Schema

```python
{
    'sources': {
        'folders': [],                    # List[str] - folder paths
        'rss_feeds': [],                  # List[str] - RSS URLs
        'mode': 'folders',                # 'folders' | 'rss' | 'both'
    },
    
    'display': {
        'mode': 'fill',                   # 'fill' | 'fit' | 'shrink'
        'pan_scan_enabled': False,        # bool
        'pan_scan_speed': 1.0,            # float
        'pan_scan_zoom': 1.3,             # float (1.0 = no zoom)
    },
    
    'transitions': {
        'type': 'crossfade',              # 'crossfade' | 'slide' | 'diffuse' | 'block_puzzle'
        'duration': 1.0,                  # float (seconds)
        'block_puzzle_grid': (6, 6),      # tuple (rows, cols)
        'slide_direction': 'left',        # 'left' | 'right' | 'up' | 'down'
        'diffuse_block_size': 10,         # int (pixels)
    },
    
    'timing': {
        'image_duration': 5.0,            # float (seconds)
    },
    
    'widgets': {
        'clock_enabled': True,            # bool
        'clock_format': '24h',            # '12h' | '24h'
        'clock_timezone': 'local',        # str (timezone name)
        'clock_position': 'top-right',    # 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'
        'clock_transparency': 0.8,        # float (0.0 to 1.0)
        'clock_multiple': False,          # bool
        'clock_timezones': [],            # List[str] - for multiple clocks
        
        'weather_enabled': False,         # bool
        'weather_location': '',           # str
        'weather_position': 'top-left',   # same as clock_position
        'weather_transparency': 0.8,      # float (0.0 to 1.0)
    },
    
    'multi_monitor': {
        'mode': 'same',                   # 'same' | 'different'
    },
}
```

---

## File Structure

```
ShittyRandomPhotoScreenSaver/
├── main.py                           # Entry point
├── requirements.txt                   # Dependencies
├── screensaver.spec                  # PyInstaller spec
├── README.md
│
├── core/                              # Core framework
│   ├── threading/                    # ThreadManager
│   ├── resources/                    # ResourceManager
│   ├── events/                       # EventSystem
│   ├── settings/                     # SettingsManager
│   └── logging/                      # Logging utilities
│
├── engine/                            # Screensaver engine
│   ├── screensaver_engine.py
│   ├── display_manager.py
│   └── image_queue.py
│
├── sources/                           # Image providers
│   ├── base_provider.py
│   ├── folder_source.py
│   └── rss_source.py
│
├── rendering/                         # Display and rendering
│   ├── display_widget.py
│   ├── image_processor.py
│   ├── pan_scan_animator.py
│   └── display_modes.py
│
├── transitions/                       # Transition effects
│   ├── base_transition.py
│   ├── crossfade.py
│   ├── slide.py
│   ├── diffuse.py
│   └── block_puzzle_flip.py
│
├── widgets/                           # Overlay widgets
│   ├── clock_widget.py
│   ├── weather_widget.py
│   └── weather_provider.py
│
├── ui/                                # Configuration UI
│   ├── settings_dialog.py
│   ├── sources_tab.py
│   ├── transitions_tab.py
│   ├── widgets_tab.py
│   ├── about_tab.py
│   └── preview_window.py
│
├── utils/                             # Utilities
│   ├── monitors.py
│   └── image_cache.py
│
├── themes/                            # Stylesheets
│   └── dark.qss
│
├── tests/                             # Unit tests
│   ├── conftest.py
│   ├── test_threading.py
│   ├── test_resources.py
│   ├── test_events.py
│   ├── test_settings.py
│   ├── test_image_processor.py
│   ├── test_transitions.py
│   ├── test_sources.py
│   └── test_integration.py
│
├── logs/                              # Log files (runtime)
│
└── Docs/                              # Documentation
    ├── 00_PROJECT_OVERVIEW.md
    ├── 01_ARCHITECTURE_DESIGN.md
    ├── 02_REUSABLE_MODULES_INTEGRATION.md
    ├── 03_CORE_IMPLEMENTATION.md
    ├── 04_IMAGE_SOURCES.md
    ├── 05_DISPLAY_AND_RENDERING.md
    ├── 06_TRANSITIONS.md
    ├── 07_WIDGETS_AND_UI.md
    ├── 08_TESTING_AND_DEPLOYMENT.md
    ├── 09_IMPLEMENTATION_ORDER.md
    ├── INDEX.md
    └── SPEC.md (this file)
```

---

## Testing Requirements

### Unit Tests
- All core modules (threading, resources, events, settings)
- Image processor (all display modes)
- Transitions (all types)
- Image sources (folder, RSS)
- Image queue

### Integration Tests
- Complete startup -> slideshow -> exit workflow
- Multi-monitor scenarios
- Settings persistence
- Monitor hotplug

### Performance Tests
- Memory usage over 24 hours
- CPU usage during transitions
- Transition smoothness (60 FPS target)

### Manual Tests
- Preview mode in Windows settings
- All transition types
- Clock and weather widgets
- Configuration UI

---

## Dependencies

### Python Packages
- PySide6 >= 6.5.0 (Qt framework)
- requests >= 2.31.0 (HTTP requests for RSS/weather)
- pytz >= 2023.3 (Timezone support)
- pytest >= 7.4.0 (Testing)
- pytest-qt >= 4.2.0 (Qt testing)

### System Requirements
- Windows 11 (primary target)
- Python 3.9+
- 4GB RAM minimum
- GPU with OpenGL support (for transitions)

---

## Constraints & Limitations

### Technical Constraints
- Windows only (for now)
- Requires .scr file format
- Must handle missing images gracefully
- Must not crash on bad RSS feeds
- Must not block on weather API calls

### Design Constraints
- Dark theme only (for configuration UI)
- No video playback (future feature)
- No live photos (future feature)
- No social media integration (future feature)

### Performance Constraints
- 60 FPS transitions
- < 500MB memory
- < 2s startup
- No stuttering on 4K

---

## Error Handling Philosophy

### Root Cause Policy
**CRITICAL**: Always address root causes over mitigation or workarounds.
- Investigate and fix the underlying problem
- Avoid band-aid solutions that hide issues
- Document why root cause fix wasn't possible if mitigation is used
- Schedule root cause fix if temporary mitigation is necessary

### Fallback Policy
**Main functionality is prioritized over fallbacks.**
- Fallbacks are allowed but not prioritized
- Fallbacks MUST log with distinct styling:
  - Console: Yellow/Orange colored warnings
  - Log file: `[FALLBACK]` prefix with WARNING level
  - Include reason why fallback triggered
  - Include what main functionality failed
- Never use silent fallbacks
- Fallbacks should be temporary states, not permanent solutions

### Error Handling Implementation

#### Image Loading
- Log error with full path and detailed reason
- Skip to next image (fallback - log with `[FALLBACK]` prefix)
- Display error message if all fail
- Never crash
- **Root Cause**: Investigate why image failed to load (corrupt, permissions, format)

#### RSS Feeds
- Log error with URL, status code, and full traceback
- Fall back to cached images (log as `[FALLBACK]`)
- Continue with folder sources (log as `[FALLBACK]`)
- Retry on next scheduled update
- **Root Cause**: Fix feed parsing, network handling, or URL validation

#### Weather API
- Log error with API response details
- Display last known weather (log as `[FALLBACK]`)
- Retry on next scheduled update
- Never block screensaver start
- **Root Cause**: Fix API integration, key validation, or network handling

#### Monitor Hotplug
- Detect via Qt screen change events
- Create/destroy widgets dynamically
- Preserve settings per monitor
- Log all changes with full details
- **Root Cause**: Ensure proper Qt event handling and widget lifecycle

---

## Security Considerations

### API Keys
- No hardcoded API keys
- Use environment variables or config file
- Never commit API keys to git

### Network Requests
- Timeout all requests (10-30 seconds)
- Validate SSL certificates
- Handle network errors gracefully

### File System
- Validate folder paths
- Handle permission errors
- Never delete user files
- Clean up temp files on exit

---

## Future Enhancements

### Planned Features
- Video playback support (MP4, WebM)
- Live photo support (animated HEIC)
- Social media integration (Instagram, Flickr)
- AI-powered smart cropping
- Music visualization
- 3D effects (parallax, depth)
- Remote control via mobile app
- Cloud sync for settings

### Not Planned
- Linux/macOS support (different screensaver APIs)
- Commercial features
- Telemetry/analytics
- Auto-updates

---

## Changelog

### Version 1.0 (In Development)

#### Audit Session - Nov 6, 2025 21:00-21:30
**48 of 63 Issues Fixed - Architecture Solid**
- ✅ Fixed 20+ memory leaks across transitions, engine, rendering
- ✅ Full thread safety for ImageQueue with RLock
- ✅ ResourceManager integrated in ALL transitions + pan_and_scan + display_widget
- ✅ Fixed 10 division-by-zero bugs (image_processor, pan_and_scan)
- ✅ Lambda closure bugs fixed (3 files)
- ✅ Python 3.7+ compatibility
- ✅ Import organization (10 files cleaned)
- ✅ Code quality (unused variables, f-strings, logging)
- 🔴 **3 Transition Visual Bugs Remain**: Diffuse (black boxes), Block Puzzle (wrong sizing), Wipe (wrong size)
- ⚠️ 15 minor issues remain (non-critical edge cases, code quality)

#### Initial Development
- Initial implementation
- All core features
- Dark theme UI
- Full Windows integration

---

## Glossary

- **LRU**: Least Recently Used (cache eviction strategy)
- **RSS**: Really Simple Syndication (feed format)
- **QSS**: Qt Style Sheets (CSS-like styling)
- **Screensaver**: Windows .scr executable
- **Pan & Scan**: Animated movement across zoomed image
- **Letterboxing**: Black bars on sides of image
- **Pillarboxing**: Black bars on top/bottom of image

---

**This specification is the single source of truth for the ShittyRandomPhotoScreenSaver project. All implementation must conform to this spec.**
