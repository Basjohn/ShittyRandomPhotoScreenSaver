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
- **Usage Ratio Control**: Configurable split between local and RSS sources (default 60/40)
  - Probabilistic selection based on ratio
  - Automatic fallback when selected pool is empty
  - UI slider control in Sources tab

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
  - Digital or analog display
  - 12h/24h format with optional seconds
  - Independent timezone per instance
  - Per-monitor selection
- **Weather Widget**:
  - Current temperature and conditions via Open-Meteo API
  - Tomorrow's forecast (min/max temp)
  - Location autocomplete
- **Media Widget**:
  - Spotify/system media integration via Windows GSMTC
  - Album artwork, track info, transport controls
  - Per-monitor selection
- **Reddit Widget** (up to 2 instances):
  - Top posts from configured subreddits
  - 4-item and 10-item layouts
  - Click-through to browser (deferred in hard-exit mode)
- **Spotify Visualizer**:
  - Real-time audio visualization via WASAPI loopback
  - 15-bar GL-rendered frequency display with ghosting
  - Center-out gradient (bass center, treble edges)
  - Spotify-style card with album art and track info
  - Volume slider control

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
  - Separate settings profile
  - System idle suppression
  - Hard-exit mode by default

### 8. Accessibility Features
- **Background Dimming**: Adjustable opacity overlay for widget readability
- **Pixel Shift**: Periodic 1px widget movement for burn-in prevention
- **Hard Exit Mode**: Prevents accidental exit from mouse movement

## Technology Stack
- **Framework**: PySide6 (Qt 6.x)
- **Language**: Python 3.9+
- **Graphics**: OpenGL 4.1+ via PyOpenGL (GLSL shaders)
- **Audio**: WASAPI loopback via pyaudiowpatch/sounddevice
- **Architecture**: Event-driven with centralized resource management
- **Threading**: ThreadManager with IO/Compute pools, lock-free SPSC queues
- **Platform**: Windows 10/11

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
| `sources.local_ratio` | Local vs RSS image ratio (%) | 60 |
| `display.same_image_all_monitors` | Same image on all displays | true |
| `display.hw_accel` | Hardware acceleration | true |
| `transitions.type` | Active transition type | Crossfade |
| `transitions.duration_ms` | Transition duration (ms) | 3000 |
| `timing.interval` | Image rotation interval (s) | 60 |

## Related Documentation
- `Index.md` - Module map and class index
- `Spec.md` - Architecture decisions and implementation details
- `Docs/10_WIDGET_GUIDELINES.md` - Widget implementation standards
- `Docs/TestSuite.md` - Test documentation
- `audits/` - Architecture audits and optimization notes
