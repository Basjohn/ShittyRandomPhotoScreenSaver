# P00 Source Ownership Inventory

Date: 2026-07-25

Refs inspected:

- baseline/recovery: `00edb57a3076b845cb8ee4b6cb7f36ea83411f0c`
- donor: `7376bb9bb380253f3bd14079e65d7bdbca062fad`

This is a static Phase 0 inventory, not a claim that every matched path is active in every scenario. Runtime activity is confirmed only where the supplied logs show it.

Status update: Phase 1 completed on main, based on baseline 0edb57a3076b845cb8ee4b6cb7f36ea83411f0c; donor 7376bb9bb380253f3bd14079e65d7bdbca062fad remains reference-only/read-only. The completed measurement result is Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md.

## Reproduction searches

```powershell
rg -n -g '*.py' -g '!tests/**' -g '!tools/**' `
  'makeCurrent|doneCurrent|QOpenGLContext|glGenTextures|glDeleteTextures|glGenFramebuffers|glDeleteFramebuffers|glGenBuffers|glDeleteBuffers|glCreateShader|glDeleteShader|glCreateProgram|glDeleteProgram' `
  core engine rendering transitions widgets

rg -n -g '*.py' -g '!tests/**' `
  'QTimer\(|startTimer\(|threading\.Timer\(' `
  core engine rendering widgets main.py

rg -n -g '*.py' -g '!tests/**' -g '!tools/**' `
  'submit_task\(|submit_io_task\(|submit_compute_task\(|ThreadPoolExecutor\(|QThreadPool|QThread\(' `
  core engine rendering sources transitions widgets ui main.py

rg -n -g '*.py' -g '!tests/**' `
  'self\.update\(|\.update\(\)|request_update|request_frame|schedule_update' `
  rendering widgets core
```

The equivalent donor inventory was produced with `git grep -n -E <pattern> 7376bb9 -- '*.py'`.

## Mutable-owner map

| Concern | Current owner(s) | Phase 0 finding |
|---|---|---|
| Runtime sequencing | `ScreensaverEngine`, `engine_lifecycle`, `DisplayManager` | Settings pause and terminal shutdown share much of the stop path but diverge in cleanup depth |
| Display surface | per-display `GLCompositor` | One compositor per display for image transitions; not yet the final all-layer surface |
| Visualizer surface | `SpotifyBarsGLOverlay` | Separate GL surface and separate direct context lifecycle |
| Transition state | display/compositor plus transition wrappers/controller | Completion and notification span several objects |
| Image decode/scale/prefetch | `engine.image_pipeline`, `ImagePrefetcher` | Compute and I/O work publish GUI-ready representations; cache is count plus estimated-memory bounded |
| Generic tasks | app-shared `ThreadManager` | Owns IO/COMPUTE executors and task registry |
| Presentation cadence | `AdaptiveTimer` / render strategy per display | Phase 1 now records passive render/paint timing; Phase 5 owns reduction decisions. |
| Visualizer simulation | shared BeatEngine plus mode helpers | Audio capture and compute jobs are separate from the overlay, but overlay tick/publication adds another cadence path |
| Generic resource tracking | `ResourceManager` | Tracks cleanup callbacks; does not itself establish GL currentness |
| GL object lifetime | compositor/overlay context owners and GL helper modules | Deletion responsibility is distributed and not byte-accounted exactly |

## GL context and surface sites

| Site | Creates/current/destroys | Ownership risk to measure |
|---|---|---|
| `rendering/gl_compositor.py` | `QOpenGLWidget` lifecycle; direct `makeCurrent()` / `doneCurrent()` during cleanup/reconfiguration | Direct context operations occur outside one narrow lifecycle function |
| `rendering/gl_compositor_pkg/gl_lifecycle.py` | auxiliary `QOpenGLContext` + `QOffscreenSurface`, widget currentness, warmup, program/buffer deletion | Multiple warmup and cleanup paths; context validity must be proven per call |
| `widgets/spotify_bars_gl_overlay.py` | separate visualizer `QOpenGLWidget`; shader/VBO creation and direct currentness for warmup/cleanup | Second GL owner with independent lifetime and update cadence |
| `transitions/overlay_manager.py` | calls `overlay.makeCurrent()` | Transition/overlay coordinator reaches into GL currentness |
| `core/resources/manager.py` | stores generic cleanup lambdas for buffers, programs, textures | Registry cleanup can execute only if caller already owns a valid current context |

## GL resource sites

| Resource | Creation/deletion owners |
|---|---|
| Image textures and upload PBOs | `rendering/gl_programs/texture_manager.py` |
| Quad/box VBOs | `rendering/gl_programs/geometry_manager.py` |
| Transition/compositor programs | `rendering/gl_programs/base_program.py`, `program_cache.py`, `gl_compositor_pkg/shader_dispatch.py`, `gl_lifecycle.py` |
| Visualizer programs/VBO | `widgets/spotify_bars_gl_overlay.py`, `widgets/spotify_visualizer/overlay_render_dispatch.py` |
| FBO/renderbuffer use | compositor lifecycle/paint paths and visualizer overlay rendering; exact byte accounting is absent |
| Transition-specific geometry/program state | GL transition modules under `transitions/` and compositor program cache |

Phase 1 adds bounded resource snapshots with owner, generation, dimensions, format, tracked bytes, and `lease_count=None` pending Phase 6 leases. Known GL allocations are exact where tracked; programs/VAOs and Qt-owned default FBOs remain explicitly untracked rather than estimated.

## Donor-only or donor-expanded GL seams

The donor adds or expands GL ownership in:

- `rendering/gl_programs/context_identity.py`;
- `rendering/gl_compositor_pkg/spotify_visualizer_layer.py`;
- `rendering/image_upload_payload.py`;
- `engine/display_manager.py`;
- `rendering/display_widget.py`.

These are donor inspection targets, not promotion candidates. Context identity assertions and immutable upload payload ideas may be reconstructed later; donor lifecycle and compositor orchestration are not accepted.

## Timers active or potentially active in normal runtime

| Category | Sites | Purpose |
|---|---|---|
| Image rotation | `ScreensaverEngine._rotation_timer` | source/image cadence |
| Presentation | `rendering/adaptive_timer.py`, `rendering/render_strategy.py` | per-display frame request loop |
| Shared animation | `core/animation/animator.py` | registered Qt animations |
| Shared recurring helper | `ThreadManager.schedule_recurring()` | app-shared QTimer construction and instrumentation |
| Worker process health | `core/process/supervisor.py` | `threading.Timer` heartbeat/restart checks |
| Input | `rendering/display_input.py` | bounded input timeout/debounce |
| Transition | `rendering/transition_controller.py` | timeout/watchdog path |
| Widget stacking/reveal | `rendering/widget_manager.py` | delayed raise/reveal |
| Overlay cadence | clock ticker, pixel shift, media, weather, Gmail, Reddit, service-widget runtime | provider refresh, UI feedback, burn-in movement |
| Visualizer/media | `spotify_visualizer/media_bridge.py`, visualizer tick helpers, `spotify_volume_widget.py` | media polling, visualizer tick, volume flush |
| GL warmup | `spotify_bars_gl_overlay.py` | deferred shader warmup |
| Diagnostics | cursor-halo perf timer, usage sampler scheduling | sampled diagnostics |

Settings-tab and dialog timers were inventoried but are not normal screensaver cadence owners.

## Worker and task submissions

### High-frequency candidates

- `rendering/adaptive_timer.py`: submits a COMPUTE task for the presentation loop.
- `rendering/render_strategy.py`: alternate/manager presentation task path.
- `widgets/spotify_visualizer/beat_engine.py`: submits compute jobs for audio/bar processing.
- `widgets/spotify_visualizer/tick_pipeline.py`: submits mode-specific compute work.

These sites were leading candidates in the Phase 0 archive. Phase 1 now records bounded passive category totals (with an `other` overflow bucket); Phase 5 owns any reduction decision.

### Image and prefetch work

- `engine/image_pipeline.py`: two compute submission paths for image load/process variants.
- `rendering/image_processor_async.py`: compute processing helper.
- `utils/image_prefetcher.py`: raw I/O and scaled compute prefetch queues.

### Low-frequency/service work

- usage sampler;
- RSS coordinator;
- media query;
- weather, Gmail, Reddit, Imgur, Steam, geocode, and OAuth tasks;
- Spotify volume read/write.

These still require category labels because aggregate ThreadManager counters cannot distinguish them today.

### Non-ThreadManager concurrency

- `ProcessSupervisor` owns child processes and heartbeat timers.
- Spotify audio capture owns its capture thread through the audio worker/backend.
- `ThreadManager` owns the application IO and COMPUTE `ThreadPoolExecutor` instances.

## Presentation `update()` publishers

### Cadence/control publishers

- `rendering/adaptive_timer.py`: safe queued widget update.
- `rendering/render_strategy.py`: safe queued update and `request_frame()` routing.
- `rendering/gl_compositor.py`: state change, transition, resize, cleanup/warmup, and paint-continuation update sites.
- `rendering/gl_compositor_pkg/transition_lifecycle.py`: transition continuation.
- `widgets/spotify_bars_gl_overlay.py`: `_request_frame_update()`, state publication, geometry, and cleanup paths.
- `widgets/spotify_visualizer/tick_pipeline.py`: direct visualizer widget update.
- `widgets/spotify_visualizer/media_bridge.py`: overlay update on media/playback changes.

### State-change publishers

- `rendering/display_image_ops.py`, `display_overlays.py`, and `display_setup.py`;
- ordinary overlay widgets (clock, cursor halo, media, weather, Gmail, Reddit, Steam, Imgur, edit overlays, dimming, volume, mute);
- shared effects/shadow helpers.

Ordinary widget state-change updates are not automatically defects. Phase 1 must distinguish justified updates from recurring cadence, duplicate fan-out, and paint-starvation patterns.

## Lifecycle order observed in baseline

1. Engine stops admission and recurring sources.
2. RSS and rotation timers stop.
3. DisplayManager quiesces/clears displays.
4. Display render pipelines and adaptive timers stop.
5. Widgets/visualizer overlays clean up.
6. Settings pause hides/reuses higher-level engine objects; terminal exit additionally cleans DisplayManager, ThreadManager, ProcessSupervisor, AnimationManager, ResourceManager, and global shader programs.
7. Recreation initializes displays and GL contexts again.

The supplied run shows cleanup/recreation, but not enough repetitions to prove exactly-once deletion or absence of old callbacks.

## Phase 1 measurement closure

- [x] Category labels and bounded passive totals are recorded at authoritative `ThreadManager` task accounting without changing scheduling.
- [x] Passive compositor render-request, paint-start, and paint-end timestamps are recorded.
- [x] One app-owned opt-in bounded low-rate event-loop lateness sampler records diagnostics independently of render timers.
- [x] Exact logical CPU-image bytes and known GL allocation bytes are recorded at their owners; unknown/Qt-owned values remain explicit.
- [x] Resource snapshots bracket lifecycle boundaries and are emitted as `resource_snapshots.csv` by parser v1.2.

No measurement becomes an acknowledgement or control dependency. See `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.
