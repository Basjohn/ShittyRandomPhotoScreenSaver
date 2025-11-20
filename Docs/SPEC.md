# ShittyRandomPhotoScreenSaver - Technical Specification

**Version**: 1.0  
**Last Updated**: Nov 17, 2025 23:30 - Canonical settings + GL compositor path  
**Status**: Architecture solid; GL compositor route and settings schema stabilised; GL transition visuals (Diffuse/Wipe/BlockPuzzle) still pending final tuning

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

#### 3. Transitions (CPU + GL variants)
- **FR-3.1**: Crossfade - opacity-based smooth transition (GL + CPU)
  - Centralized AnimationManager (no QPropertyAnimation)
  - Persistent CPU overlay paints old/new pixmaps with opacity
  - Easing via `core.animation.types.EasingCurve`
- **FR-3.2**: Slide - directional slide (left/right/up/down)
  - AnimationManager‑driven label movement (old out, new in)
  - Directions: LEFT, RIGHT, UP, DOWN (diag optional)
- **FR-3.3**: Wipe - progressive reveal transition
  - Mask‑based reveal on new label; full‑rect DPR alignment
- **FR-3.4**: Diffuse - random block reveal
  - CompositionMode_Clear punching holes in old label; AM timing
- **FR-3.5**: Block Puzzle Flip - grid flip 
  - Mask union on new label; DPR‑aligned grid; AM timing

GL Path: The only supported GL route uses a single `GLCompositorWidget` per display (Route 3) that executes Crossfade/Slide/Wipe/Diffuse/BlockFlip/Blinds via a compositor API. Legacy per-transition GL overlays (QOpenGLWidget + QPainter) are quarantined for reference/tests only and are not used by the current engine. Overlays/compositor expose readiness flags (e.g. `is_ready_for_display()`) to gate base paints before they present.

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
  - OpenWeatherMap/Open-Meteo integration
  - Background fetching with QThread
  - 30-minute caching
  - 4 position options
  - Error handling
- **FR-5.3**: Configurable position, transparency, and size
- **FR-5.4**: Multiple clock support for different timezones
  - Primary clock (Clock 1) plus optional Clock 2 and Clock 3
  - Each clock can target a specific monitor (ALL/1/2/3)
  - Each clock has an independent timezone, derived from either local time, UTC or explicit region (pytz/zoneinfo) with DST support

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

#### `core/logging/logger.py` 
**Purpose**: Centralized logging configuration  
**Status**: 
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

#### `core/logging/overlay_telemetry.py` 
**Purpose**: Centralized overlay diagnostics/telemetry helper for GL/software transitions  
**Status**: 
**Key Functions**:
- `record_overlay_ready(log, screen_index, overlay_name, stage, stage_counts, overlay_swap_warned, seed_age_ms, details)` - Aggregate overlay readiness events and emit structured `[DIAG]` logs.

**Features**:
- Aggregates per-overlay/per-stage readiness counts used by `DisplayWidget` and tests.  
- Emits a single detailed `[DIAG] Overlay readiness` line per `(screen, overlay, stage)` with seed age and sanitized details.  
- Logs swap-behaviour downgrades once per overlay when `gl_initialized` reports non-triple-buffered swap, using the same format across all GL overlays.

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
  - Render images (retains last frame during pauses to avoid fallback flashes)
  - Execute transitions using AnimationManager and persistent overlays
  - Host widgets (clock, weather)
  - Capture input for exit

#### 5. Transitions
- **Base**: BaseTransition (abstract) ✅ IMPLEMENTED
  - QABCMeta metaclass (QObject + ABC)
  - TransitionState enum
  - Signals: started, finished, progress, error
  - Methods: start(), stop(), cleanup()
  - Telemetry helpers `_mark_start()` / `_mark_end()` with an overridable `get_expected_duration_ms()` used to log actual vs expected wall-clock duration for each transition type (BlockPuzzleFlip variants override this to account for their two-phase timeline: `duration_ms + flip_duration_ms`).
- **Types**:
  - Crossfade (CPU + GL variants)
  - Slide (CPU + GL variants)
  - Wipe (CPU + GL variants)
  - Diffuse (CPU + GL variants)
  - BlockPuzzleFlip (CPU + GL variants)
  - Blinds (GL-only) – readiness-gated overlay with eased tail repainting
- **Interface**: start(old, new, widget), stop(), finished signal
- **Features**: Progress tracking (0.0-1.0), configurable duration, easing curves; GL overlays publish readiness flags to avoid fallback paints

#### 6. Overlay Widgets
- **Types**: ClockWidget, WeatherWidget, MediaWidget (Spotify)
- **Features**: Position, transparency, auto-update. All overlay widgets are configured exclusively via the canonical nested `widgets` map in settings (`widgets.clock`, `widgets.clock2`, `widgets.clock3`, `widgets.weather`, `widgets.media`), which is initialised and kept up to date by `SettingsManager._set_defaults()` + `_ensure_widgets_defaults()` with **no widget-specific default helpers**. The MediaWidget is a Spotify-specific overlay on Windows that shows playback state, track/artist/album text, and optional album artwork via the centralized media controller. It hides itself entirely when no Spotify GSMTC session is available or when media APIs are unavailable, and interaction is gated by Ctrl-held / hard-exit input modes. Creation of the MediaWidget at runtime is gated strictly by `widgets.media.enabled` and the configured `widgets.media.monitor` selection.

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
    'display': {
        'mode': 'fill',                    # 'fill' | 'fit' | 'shrink'
        'hw_accel': True,                  # bool - GL compositor / hardware backend enabled when True
        'refresh_sync': True,              # bool - enable vsync / refresh sync
        'prefer_triple_buffer': True,      # bool - prefer triple-buffered swap when available
        'gl_depth_bits': 24,               # int - depth buffer bits for GL context
        'gl_stencil_bits': 8,              # int - stencil buffer bits for GL context
        'render_backend_mode': 'opengl',   # 'opengl' | 'software' (fallback)
        'pan_and_scan': False,             # bool - Ken Burns effect
        'pan_auto_speed': True,            # bool - auto speed selection based on image size
        'pan_speed': 3.0,                  # float - manual speed when auto_speed is False
        'sharpen_downscale': False,        # bool - optional sharpening after downscale
        'same_image_all_monitors': False,  # bool - True = same image on all screens
        'show_on_monitors': 'ALL',         # 'ALL' or list of 1-based monitor indices (e.g. [1, 2])
    },

    'transitions': {
        'type': 'Wipe',                    # 'Crossfade' | 'Slide' | 'Wipe' | 'Diffuse' | 'Block Puzzle Flip' | 'Blinds'
        'duration_ms': 1300,               # int milliseconds
        'easing': 'Auto',                  # 'Auto' | 'Linear' | 'InQuad' | 'OutQuad' | ...
        'direction': 'Random',             # Global direction hint (Slide/Wipe); usually 'Random'
        'random_always': False,            # When True, always choose a new random direction
        'diffuse': {
            'block_size': 50,             # int pixels (UI-enforced range e.g. 4–256)
            'shape': 'Rectangle',         # 'Rectangle' | 'Circle' | 'Diamond' | 'Plus' | 'Triangle'
        },
        'block_flip': {
            'rows': 4,
            'cols': 6,
        },
        'slide': {
            'direction': 'Random',        # 'Random' | 'Left to Right' | 'Right to Left' | 'Top to Bottom' | 'Bottom to Top'
            # 'last_direction': 'Left to Right'  # persisted at runtime for non-repeating Random
        },
        'wipe': {
            'direction': 'Random',        # Same options as Slide
            # 'last_direction': 'Left to Right'  # persisted at runtime for non-repeating Random
        },
    },

    'timing': {
        'interval': 10,                    # int seconds between images
    },

    'input': {
        'hard_exit': False,                # bool - when True, only ESC/Q exit; mouse movement/clicks are ignored for exit
    },

    'widgets': {
        'clock': {
            'enabled': True,
            'monitor': 1,                  # default clock on primary monitor only
            'format': '24h',               # '12h' | '24h'
            'position': 'Top Right',       # placement label
            'show_seconds': True,
            'timezone': 'local',           # 'local' | pytz/zoneinfo name | 'UTC±HH:MM'
            'show_timezone': False,
            'font_family': 'Segoe UI',
            'font_size': 48,
            'margin': 20,
            'show_background': True,
            'bg_opacity': 0.7,
            'bg_color': [64, 64, 64, 255],
            'color': [255, 255, 255, 230],
            'border_color': [255, 255, 255, 255],
            'border_opacity': 1.0,
            # Display mode: 'digital' (existing text-based clock) or
            # 'analog' for the circular clock-face rendering.
            'display_mode': 'digital',
            # When in analogue mode, controls whether hour numerals (1–12)
            # are rendered around the clock face.
            'show_numerals': True,
        },
        'clock2': {
            'enabled': False,
            'monitor': 'ALL',              # 'ALL' | 1 | 2 | 3
            'format': '24h',
            'position': 'Bottom Right',
            'show_seconds': False,
            'timezone': 'UTC',             # Defaults to UTC; user may override
            'show_timezone': True,
            'font_family': 'Segoe UI',
            'font_size': 32,
            'margin': 20,
            'color': [255, 255, 255, 230],
            'display_mode': 'digital',
            'show_numerals': True,
        },
        'clock3': {
            'enabled': False,
            'monitor': 'ALL',              # 'ALL' | 1 | 2 | 3
            'format': '24h',
            'position': 'Bottom Left',
            'show_seconds': False,
            'timezone': 'UTC+01:00',       # Example offset-based timezone
            'show_timezone': True,
            'font_family': 'Segoe UI',
            'font_size': 32,
            'margin': 20,
            'color': [255, 255, 255, 230],
            'display_mode': 'digital',
            'show_numerals': True,
        },
        'weather': {
            'enabled': False,
            'monitor': 'ALL',              # 'ALL' | 1 | 2 | 3
            'position': 'Bottom Left',
            'location': 'London',
            'font_family': 'Segoe UI',
            'font_size': 24,
            'color': [255, 255, 255, 230],
            'show_background': True,
            'bg_opacity': 0.7,
            'bg_color': [64, 64, 64, 255],
            'border_color': [255, 255, 255, 255],
            'border_opacity': 1.0,
            'show_icons': True,
        },
        'media': {
            'enabled': False,
            'monitor': 'ALL',              # 'ALL' | 1 | 2 | 3
            'position': 'Bottom Left',
            'font_family': 'Segoe UI',
            'font_size': 20,
            'margin': 20,
            'show_background': True,
            'bg_opacity': 0.7,
            'color': [255, 255, 255, 230],
            'bg_color': [16, 16, 16, 255],
            'border_color': [255, 255, 255, 255],
            'border_opacity': 1.0,
            # Artwork and controls behaviour (Spotify widget baseline)
            'artwork_size': 200,           # int pixels, user-tunable in Widgets tab
            'show_controls': True,         # bool – when False, hide transport row
            'rounded_artwork_border': True,
            'show_header_frame': True,
        },
        # Global widget drop-shadow defaults shared by all overlay widgets.
        'shadows': {
            'enabled': True,
            'color': [0, 0, 0, 255],       # base colour, alpha scaled by opacity fields
            'offset': [4, 4],              # dx, dy in logical pixels
            'blur_radius': 18,             # blur radius in logical pixels
            'text_opacity': 0.3,           # opacity multiplier for text-only widgets
            'frame_opacity': 0.7,          # opacity multiplier for framed widgets
        },
    },
}
```

---

## Implementation Policies & Conventions

These policies are **normative**: new code, tests, and docs must follow them unless explicitly overridden.

### 1. Settings & Configuration

- **Canonical nested schema only**
  - All runtime code and UI tabs must use the nested settings structure documented above (`display`, `transitions`, `timing`, `widgets`, `input`).
  - No new flat keys such as `transitions.type`, `transitions.duration_ms`, `widgets.clock_*`, or `widgets.weather_*` may be introduced.
  - Migration logic from flat keys to nested dicts is allowed **only** in clearly marked migration helpers (e.g. widget/tab loaders) and must never be extended for new features.
- **Single source of truth**
  - A given behaviour must be configured from one canonical setting (e.g. `display.same_image_all_monitors`, `transitions.random_always`) with no duplicated flags.
  - Boolean-like values must be normalised via `SettingsManager.to_bool` / `get_bool` or an equivalent central helper.
- **Defaults come from SettingsManager**
  - All defaults are defined in `SettingsManager._set_defaults()` and mirrored in this spec. UI tabs and runtime components must not hardcode conflicting default values.

### 2. Rendering, GL Path & Flicker Policy

- **Single accelerated path (Route 3)**
  - The only supported GL path is the compositor route using `GLCompositorWidget` and the backend registry in `rendering/backends`. Per-transition GL overlays are considered legacy and must not be used for new features.
  - Software transitions are retained as a fallback when GL is unavailable or misconfigured.
- **Flicker-free requirement**
  - The display pipeline must avoid visual flicker and banding at all costs:
    - `DisplayWidget` must preserve the last rendered pixmap across transitions, errors, and restarts.
    - GL compositor readiness (`is_ready_for_display()` or equivalent) must gate base paints and avoid showing partially initialised frames.
    - Error states should prefer reusing the previous frame with overlayed messaging rather than flashing a blank or placeholder screen.
  - New transitions or rendering changes must be evaluated against this no-flicker policy.
- **Transition selection rules**
  - All transitions are created through `DisplayWidget._create_transition()` using the canonical `transitions` dict.
  - GL-only transitions (e.g. Blinds) must gracefully fall back to CPU equivalents when `display.hw_accel` is disabled or GL compositor setup fails.

### 3. Threading & Concurrency

- **Central ThreadManager**
  - `ThreadManager` is the single point of coordination for thread pools and timers.
  - New background work must use `ThreadManager` (IO/COMPUTE pools, `single_shot`, `schedule_recurring`) rather than ad-hoc `threading.Thread` instances.
- **QThread usage**
  - Direct `QThread` usage is reserved for exceptional cases (e.g. `WeatherWidget` fallback when no `ThreadManager` is available) and must be tightly scoped with explicit cleanup.
- **UI thread discipline**
  - Worker threads must never touch Qt widgets directly. All UI updates must go through `ThreadManager.run_on_ui_thread` or Qt signal/slot connections.
  - Long-lived worker components must have well-defined shutdown paths invoked from `ScreensaverEngine.cleanup()`.

### 4. Resource Management & Cleanup

- **ResourceManager integration**
  - Long-lived Qt objects (displays, overlays, widgets, timers) and external resources (temp files, image caches) must be registered with `ResourceManager` where practical.
  - `ScreensaverEngine.cleanup()` is responsible for calling `thread_manager.shutdown()` followed by `ResourceManager.shutdown()`/`cleanup_all()` to ensure deterministic teardown.
- **Ownership model**
  - `ScreensaverEngine` owns `DisplayManager`, which owns per-screen `DisplayWidget` instances. Each `DisplayWidget` owns its overlays, compositor, and widgets via Qt parent/child relationships and ResourceManager registration.
  - New components must fit into this ownership graph rather than introducing new global state.

### 5. Widgets & Configuration Patterns

- **Nested widget configuration**
  - All overlay widgets use the `widgets` nested dict for configuration (`widgets.clock`, `widgets.clock2`, `widgets.clock3`, `widgets.weather`, future widgets).
  - Each widget configuration must include at minimum: `enabled`, `monitor`, `position`, font family/size, text color, `show_background`, `bg_color`, `bg_opacity`, `border_color`, and `border_opacity` where frames are supported.
- **Single canonical defaults path for widgets**
  - Default values and migration of widget configuration **must** flow through `SettingsManager._set_defaults()` and `_ensure_widgets_defaults()` so that new widget sections (e.g. media) are added in one place without per-widget helpers.
  - No new widget-specific default/migration helpers (e.g. `_ensure_media_defaults`) may be introduced; legacy flat keys are migrated only inside UI/tab loaders where necessary.
- **Consistent theming**
  - Widget styling should follow the shared dark theme (e.g. dark grey background + white text with alpha) and prefer QSS/theme-based styling over inline palette changes, unless a specific behaviour requires programmatic styling.
  - New widgets should reuse existing patterns for background frames, opacity sliders, and color pickers in the Widgets tab.
 - **Overlay Z-order for widgets**
   - `transitions.overlay_manager.raise_overlay()` must always re-raise clock, weather, and media widgets above transition overlays (GL and software) so that overlay widgets remain visible regardless of the active renderer backend.
 - **Widget implementation checklist**
   - Settings:
     - All widget defaults (including new keys like `artwork_size`, `show_controls`, future style flags) must be added to `SettingsManager._set_defaults()` and merged via `_ensure_widgets_defaults()`.
     - UI tabs must *only* read/write the canonical nested `widgets` map; no parallel flat keys.
   - UI loading:
     - Settings tabs that mirror `widgets.*` must block signals while loading and use a `_loading` guard in their save handlers to avoid writing partial defaults back to QSettings during construction.
   - Logging:
     - Diagnostics must avoid per-frame or per-paint spam (e.g. geometry logs in `paintEvent`); prefer one-shot startup snapshots and focused state transitions instead.
     - Temporary high-volume logs added for investigations must be removed or gated once an issue is resolved.

### 6. Testing & Tooling

- **Logging-first test policy**
  - All pytest runs should follow the logging-first policy described in `Docs/TestSuite.md`, using file-based logs when terminal output is unreliable.
  - On Windows/PowerShell the preferred entrypoint is the helper script:
    - `python scripts/run_tests.py --suite {all,core,transitions,flicker}`
  - New tests must integrate with this tooling and keep output minimal by default.
- **Feature/tests coupling**
  - New features, bug fixes, or refactors must be accompanied by tests (unit or integration) that lock in the intended behaviour, especially for transitions, threading, and widget configuration.

### 7. Legacy & Compatibility Shims

- **No new shims by default**
  - Compatibility shims or legacy code paths are strongly discouraged. They may be introduced only when absolutely unavoidable and must be clearly marked as such in code and documentation.
- **Migration over permanent dual-paths**
  - When behaviour or settings change, the preferred strategy is:
    1. Migrate legacy data into the canonical schema on first load.
    2. Persist only the canonical form going forward.
    3. Avoid long-lived dual-path logic that keeps both legacy and new behaviour active.
- **Legacy modules are quarantined**
  - Legacy modules (e.g. `temp/display_widget_prev.py` and per-transition GL overlays) are retained for reference/tests only and must not be wired into the main engine or used for new development.

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
