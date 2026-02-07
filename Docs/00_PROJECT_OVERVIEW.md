# Project Overview: ShittyRandomPhotoScreenSaver

## Project Name
**ShittyRandomPhotoScreenSaver** (SRPSS)

## Objective
A modern, feature-rich Windows screensaver application using PySide6 that displays photos from multiple sources with GPU-accelerated transitions, multi-monitor support, and rich overlay widgets including a Spotify audio visualizer.

## Key Features

### 1. Multi-Source Image Support
- **Local Folders**: Recursive scanning of designated directories with extension filtering
- **RSS/JSON Feeds**: Parse RSS/Atom feeds and Reddit JSON listings for images
  - High-resolution filter for Reddit (prefers posts ≥2560px width)
  - On-disk caching with rotating cache (keeps at least 20 images before cleanup)
  - Optional save-to-disk mirroring for permanent storage
- **Usage Ratio Control**: Configurable split between local and RSS sources (default 70/30)
  - Probabilistic selection based on ratio with automatic fallback when the selected pool is empty
  - UI slider control in Sources tab (disabled when only one source type is configured)

### 2. Display Modes
- **Fill Mode** (Primary): Crop and scale to fill screen without distortion/letterboxing
- **Fit Mode**: Scale to fit within screen bounds with letterboxing
- **Shrink Mode**: Scale down only if larger than screen
- DPR-aware scaling for high-DPI displays

### 3. Transition Effects (12 Types)
Transitions run on the GL compositor when hardware acceleration is available. Some transition types are GL-only and do not have CPU fallbacks.
- **Crossfade**: Smooth opacity transition
- **Slide**: Directional slide (cardinal directions)
- **Wipe**: Directional wipe (includes diagonals)
- **Diffuse**: Block-based dissolve (Rectangle/Membrane shapes)
- **Block Puzzle Flip**: 3D tile flip effect
- **Blinds**: GL-only venetian blinds effect
- **Peel**: GL-only strip-based peel
- **3D Block Spins**: GL-only full-frame 3D slab rotation
- **Ripple/Rain Drops**: GL-only radial ripple effect
- **Warp Dissolve**: GL-only vortex-style dissolve
- **Crumble**: GL-only Voronoi crack pattern with falling pieces
- **Particle**: GL-only particle stacking transition (Directional/Swirl/Converge)

### 4. Multi-Monitor Support
- **Same Image Mode**: Synchronized display across all monitors
- **Different Image Mode**: Independent images per monitor with deduplication
- **Per-Monitor Widget Config**: Each widget can target ALL, Monitor 1, 2, or 3
- Automatic monitor hotplug detection

### 5. Widget Overlays
- **Clock Widget** (up to 3 instances):
  - Digital or analog display with cached face pixmaps for low paint cost
  - 12h/24h format, optional seconds, timezone per instance
  - Per-monitor placement plus centralized visual padding helpers for alignment
- **Weather Widget**:
  - Current temperature/conditions via Open-Meteo with 30-minute caching
  - Optional forecast row and location autocomplete
  - ThreadManager-driven refresh timers (no raw QThreads)
- **Media Widget**:
  - Spotify/system media integration via Windows GSMTC with guarded WinRT polling and adaptive idle detection
  - Album artwork, track info, transport controls, optional Spotify volume slider
  - Smart polling intervals (1000 ms → 2500 ms active, 5000 ms idle)
- **Reddit Widget** (up to 2 instances):
  - Top posts from configured subreddits with 4-, 10-, or 20-item layouts
  - Click-through behavior gated by interaction mode (Ctrl/Hard Exit)
  - Shared styling via widget factories
- **Spotify Visualizer** (5 modes):
  - **Spectrum**: Segmented bar analyzer with ghost peak trails, dynamic segment count scaling with card height
  - **Oscilloscope**: Catmull-Rom spline waveform, up to 3 frequency-band-reactive lines with glow
  - **Blob**: 2D SDF organic metaball with drum-reactive pulse, vocal wobble, energy-reactive glow
  - **Starfield**: Point-star field with nebula background, audio-reactive travel (dev-gated)
  - **Helix**: 3D DNA double-helix with Blinn-Phong tube shading and energy-reactive rotation
  - All modes: WASAPI loopback audio, GL rendering + software fallback, synchronized fade-in
  - Volume slider control and pixel-shift aware positioning

### 6. Configuration GUI
- Dark-themed settings dialog (dark.qss)
- Six tabs: Sources, Display, Transitions, Widgets, Accessibility, About
- Instant save and apply
- Settings import/export (JSON snapshots)
- Context menu (right-click) for quick access

### 7. Windows Screensaver Integration
- Command-line arguments: `/s` (run), `/c` (config), `/p` (preview)
- .scr file format deployment
- Manual Controller (MC) variant for non-screensaver use
  - Separate QSettings application name (`Screensaver_MC`) with executable stem detection
  - Hard-exit mode forced on at startup so mouse movement never exits unless the user changes the setting
  - Idle suppression now relies on standard OS power settings (legacy `SetThreadExecutionState` call removed)
  - MC window uses `Qt.Tool` flags to stay off Alt+Tab/taskbar and ships primarily as a Nuitka onedir bundle

### 8. Accessibility Features
- **Background Dimming**: Adjustable compositor-based dimming (rendered after the base image/transition but before overlay widgets)
- **Pixel Shift**: Periodic 1px widget movement for burn-in prevention
- **Hard Exit / Ctrl Gating**: Prevents accidental exit from mouse movement; holding Ctrl temporarily enables widget interaction even when hard-exit is off

## Technology Stack
- **Framework**: PySide6 (Qt 6.x)
- **Language**: Python 3.11
- **Graphics**: OpenGL 4.1+ via PyOpenGL (GLSL shaders)
- **Audio**: WASAPI loopback via pyaudiowpatch/sounddevice
- **Architecture**: Event-driven with centralized resource/resource + settings managers (see `Spec.md`)
- **Threading**: ThreadManager with IO/Compute pools, lock-free SPSC queues
- **Platform**: Windows 11 (Windows 10 supported but not primary test target)

## Core Architecture

### Centralized Managers
- **ThreadManager** (`core/threading/manager.py`): All async operations, IO/Compute thread pools
- **ResourceManager** (`core/resources/manager.py`): Qt object lifecycle tracking
- **EventSystem** (`core/events/event_system.py`): Pub/sub inter-module communication
- **SettingsManager** (`core/settings/settings_manager.py`): Persistent configuration with change notifications
- **AnimationManager** (`core/animation/animator.py`): Centralized animation timing and easing

### Rendering Pipeline
1. **Image Queue** selects next `ImageMetadata` (ratio-based for local/RSS)
2. **Prefetcher** decodes images to `QImage` on IO threads, stores in `ImageCache`
3. **Engine** loads via cache (QPixmap if cached, else QImage→QPixmap conversion)
4. **ImageProcessor** scales to screen size (DPR-aware)
5. **Transition** (GL compositor or CPU) presents old→new
6. **Prefetch** scheduled for next images

### GL Compositor
- Single `GLCompositorWidget` per display
- Hosts all GL-backed transitions via GLSL shaders
- Fallback to QPainter compositor or CPU transitions on GL failure
- Session-scoped fallback: shader failure disables shaders for entire session

### Transition Groups
- **Group A**: Shader-backed GLSL transitions (primary path)
- **Group B**: QPainter compositor transitions (fallback)
- **Group C**: Pure software/CPU transitions (final fallback)

## Performance Targets
- 60 FPS transitions on 1080p displays
- < 500MB memory usage typical
- < 2 second startup time (local images)
- Smooth operation on dual 4K monitors
- No memory leaks during extended runs

## Quality Assurance
- Unit tests for core modules (see `Docs/TestSuite.md`)
- Logging-first policy with rotating log files
- Debug mode with comprehensive logging
- PERF metrics for GL compositor timing

## Deployment
- **SRPSS.scr** / **SRPSS.exe**: Main screensaver build
- **SRPSS_MC.exe**: Manual Controller variant
- **Inno Setup installer**: `scripts/SRPSS_Installer.iss`
- Build scripts: PyInstaller and Nuitka options

## Key Settings
| Setting | Description | Default |
|---------|-------------|---------|
| `sources.local_ratio` | Local vs RSS image ratio (%) | 70 |
| `display.same_image_all_monitors` | Same image on all displays | false |
| `display.hw_accel` | Hardware acceleration | true |
| `transitions.type` | Active transition type | Ripple |
| `transitions.duration_ms` | Transition duration (ms) | 7200 |
| `timing.interval` | Image rotation interval (s) | 45 |

## Related Documentation
- `Index.md` - Canonical module map and class index
- `Spec.md` - Architecture decisions, policies, and settings schema
- `Docs/10_WIDGET_GUIDELINES.md` - Widget implementation standards and compositor rules
- `Docs/TestSuite.md` - Test documentation and execution patterns
- `audits/` - Architecture audits and optimization notes
