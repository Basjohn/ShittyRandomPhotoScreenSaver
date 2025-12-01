# Project Overview: ShittyRandomPhotoScreenSaver

## Project Name
**ShittyRandomPhotoScreenSaver**

## Objective
Build a modern, feature-rich Windows screensaver application using PySide6 that displays photos from multiple sources with advanced transitions, multi-monitor support, and overlay widgets.

## Key Features

### 1. Multi-Source Image Support
- **Local Folders**: Recursive scanning of designated directories
- **RSS Feeds**: Parse RSS/Atom feeds for image enclosures
- **Multiple Sources**: Use folders, RSS, or both simultaneously

### 2. Display Modes
- **Fill Mode** (Primary): Crop and scale to fill screen without distortion/letterboxing
- **Fit Mode**: Scale to fit within screen bounds with letterboxing
- **Shrink Mode**: Scale down only if larger than screen
- **Pan & Scan**: Animated movement across zoomed images

### 3. Transition Effects
- **Crossfade**: Smooth opacity transition
- **Slide**: Directional slide (left/right/up/down)
- **Diffuse**: Random pixel/block reveal
- **Block Puzzle Flip**: 3D flip effect with configurable grid (primary feature)

### 4. Multi-Monitor Support
- **Same Image Mode**: Synchronized display across all monitors
- **Different Image Mode**: Independent image queues per monitor
- **Per-Monitor Config**: Different settings per display

### 5. Widget Overlays
- **Clock Widget**: 
  - Digital or analog
  - 12h/24h format
  - Timezone support
  - Multiple clocks for different timezones
- **Weather Widget**:
  - Current temperature and conditions
  - Location with autocomplete
  - Periodic updates

### 6. Configuration GUI
- Dark-themed settings dialog using dark.qss
- Side-tab navigation design
- Four tabs: Sources, Transitions, Widgets, About
- Instant save and apply
- 16:9 aspect ratio (1080x720 minimum)

### 7. Windows Screensaver Integration
- Command-line arguments: `/s` (run), `/c` (config), `/p` (preview)
- .scr file format
- Preview mode support
- System integration

## Technology Stack
- **Framework**: PySide6 (Qt 6.x)
- **Language**: Python 3.9+
- **Architecture**: Event-driven with centralized resource management
- **Threading**: Lock-free concurrent architecture
- **Platform**: Windows 11

## Rendering Architecture & Performance

- **Single GL Compositor per display**
  - Each display hosts one `GLCompositorWidget` that renders the base image and all GL-backed transitions (Slide, Wipe, Peel, Block Puzzle Flip, Ripple/Raindrops, Warp Dissolve, Shuffle, GL Crossfade).
  - Legacy per-transition GL overlay widgets are being retired in favour of this single compositor surface.

- **CPU fallbacks remain authoritative**
  - CPU Crossfade/Slide/Wipe/Diffuse remain the safe fallback paths when GL or the compositor is unavailable for a session.
  - If a shader-backed transition fails, only the shader path is disabled for that run; composited QPainter transitions continue to render.

- **Claw Marks / Shooting Stars status**
  - The GLSL Shooting Stars / Claw Marks transition has been evaluated and removed from the active transition pool.
  - Its shader path is hard-disabled in the compositor; any legacy requests for this transition are routed through a safe Crossfade.

- **Shuffle shader regression handling**
  - The experimental GLSL Shuffle path is currently disabled due to visual/regression issues.
  - Shuffle continues to run via the compositor-backed diffuse/QRegion implementation while the shader is refactored or formally retired.

- **PERF metrics and on-screen overlay**
  - GL and animation timing are tracked via `[PERF] [GL COMPOSITOR]` and `[PERF] [ANIM]` log lines (duration, frames, avg_fps, dt_min/max, size).
  - A small optional on-screen FPS/debug overlay is available in the compositor to visualise real frame pacing during development.
  - All PERF logging and the overlay are gated by the global performance toggle so production builds can disable this instrumentation entirely.

## Quality Assurance
- Unit tests for all core modules
- Logging-first policy (terminal output unreliable)
- Debug mode with comprehensive logging
- No fallbacks without explicit errors

## Success Criteria
- 60 FPS transitions on 1080p displays
- < 500MB memory usage
- < 2 second startup time
- Smooth operation on dual 4K monitors
- No memory leaks during extended runs
- Graceful error handling
- Professional UI with dark theme

## Development Timeline
Approximately 6 weeks with phased rollout:
- **Week 1**: Foundation + single monitor support
- **Week 2**: Transitions + multi-monitor
- **Week 3-4**: Pan & scan + block puzzle flip
- **Week 4**: RSS + weather widgets
- **Week 5**: Configuration UI
- **Week 6**: Testing + deployment

## Constraints
- Windows 11 only (for now)
- PySide6 required (Qt licensing)
- Must work as .scr file
- Must handle monitor hotplug
- Must handle missing images gracefully
- All settings must persist
- No silent fallbacks

## Out of Scope (Future)
- Video playback support
- Live photo/animated formats
- Social media integration
- AI features
- Music visualization
- Remote control
- Cloud sync

---

**Next Document**: `01_ARCHITECTURE_DESIGN.md` - Detailed architecture and module structure
