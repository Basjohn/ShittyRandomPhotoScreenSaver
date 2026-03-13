---
description: Cross-mode Spotify visualizer reset contract
---
# Visualizer Reset Matrix

This document defines the canonical reset sequence for every component that participates in the Spotify visualizer pipeline. The goal is to make mode switches, GL fallbacks, and cold starts deterministic so that no mode inherits stale state (bars, waveform buffers, blob staging, bubble trails, etc.) from any other mode.

## Scope

Applies to the following code paths:

1. Cold start or wake-from-sleep initialization.
2. User-triggered visualization mode changes (including preset-driven changes).
3. Settings-dialog Apply/OK flows that reconfigure Spotify visualizer parameters while music is playing.
4. GL failures or driver resets that require overlay teardown/recreation.
5. Process restarts driven by watchdogs or manual developer actions.

## Components

| Component | File | Reset Responsibilities |
|-----------|------|------------------------|
| **SpotifyVisualizerWidget** | `widgets/spotify_visualizer_widget.py` | Owns UI-level state, cached GPU kwargs, preset slider state, and parent overlay orchestration. `_reset_visualizer_state()` / `_reset_engine_state()` zero bars/energy, tear down cached geometry, replay the last settings snapshot, and keep `VisualizerPresetSlider`/Advanced collapse cache in sync so Custom always reflects current user values. |
| **SpotifyBarsGLOverlay** | `widgets/spotify_bars_gl_overlay.py` | Handles GLSL program compilation and per-mode GPU accumulators. `request_mode_reset()` queues mode-specific cold starts; `_reset_mode_state()` clears waveform ghosts, blob stage buffers, starfield travel time, bubble particle + trail buffers, and pushes new uniforms such as `bubble_gradient_direction` / `bubble_specular_direction` before the first post-reset draw. |
| **Beat Engine / SpotifyVisualizerAudioWorker** | `widgets/spotify_visualizer/beat_engine.py` | Supplies FFT data. Needs `cancel_pending_compute_tasks()`, `reset_smoothing_state()`, `reset_floor_state()`, and `set_smoothing()` after every cutover so generation IDs increment and consumers wait for fresh frames. |
| **DisplayWidget / Overlay Manager** | `widgets/spotify_visualizer_widget.py`, `widgets/spotify_bars_gl_overlay.py` | Ensures GL overlay is hidden during resets, re-raised only after fresh bars arrive, and that `ShadowFadeProfile` and fade gating stay in sync. |
| **Diagnostics & Logging** | `screensaver_spotify_vis.log`, `[SPOTIFY_VIS]` logs | Capture reset reasons, mode names, and timestamps (`[RESET] mode=... reason=...`) to make regressions traceable. |
| **Preset infrastructure** | `ui/tabs/media/preset_slider.py`, `core/settings/visualizer_presets.py` | Preset indices (`widgets.spotify_visualizer.preset_<mode>`) and curated payloads are reapplied immediately after resets so curated slots (incl. bubble gradient/specular overrides) stay authoritative. Custom preset state survives resets via `custom_preset_backup` in SST snapshots. |

## Reset Triggers and Contract

| Trigger | SpotifyVisualizerWidget | GL Overlay | Beat Engine | Other Notes |
|---------|------------------------|------------|-------------|-------------|
| **Cold start / wake** | Call `_reset_visualizer_state(clear_overlay=True, replay_cached=True)` before first `set_state`. Block UI until `_waiting_for_fresh_engine_frame` clears. | `_init_gl_pipeline()` compiles programs, `request_mode_reset()` for current mode, GL context is held until first frame. | `ensure_started()`, then `reset_smoothing_state()` and `reset_floor_state()` so first FFT frame is fresh. | Reattach shadows only after `_on_first_frame_after_cold_start()` per doc. |
| **Mode switch (user or preset)** | Invoke `_reset_visualizer_state(clear_overlay=False, replay_cached=True)` followed by `_request_overlay_mode_reset(target_mode)`. | `_pending_mode_resets` receives new mode; `_reset_mode_state()` clears accumulators on next frame. | `cancel_pending_compute_tasks()`; `reset_smoothing_state()` increments generation so stale FFTs are ignored. | Settings dialog should mark `Waiting Validation` until user confirms behavior. |
| **Settings Apply while playing** | If any Spotify slider changed, call `_reset_visualizer_state(replay_cached=True)` to guarantee new uniforms land together. Remember Advanced sliders (e.g., `bubble_specular_direction`) remain active even when collapsed, so resets must replay those values. | Optional mode reset only if mode changed; otherwise keep current program but flush per-mode buffers. | `set_smoothing(self._smoothing)` to reapply user tau after reset. | Prevents displacement/heartbeat ghosts after disabling sliders and confirms decoupled gradient/specular headings stick after Apply. |
| **GL failure / driver reset** | `_reset_visualizer_state(clear_overlay=True)` to drop old programs and request recompile when overlay returns. | `_gl_state` transitions to ERROR, `reset_GL_overlay()` tears down programs, then `_init_gl_pipeline()` runs again when context recovers. | Engine reset required so GPU uniforms don't reference stale bar buffers. | GLErrorHandler should record demotion Group A→B. |
| **Process watchdog / manual restart** | Treat as cold start; ensure cached kwargs and presets reload before enabling overlay. | Recompile shaders, confirm all uniforms are declared to avoid fallback to spectrum. | Start engine with defaults, then replay stored settings once stable. | Run diagnostics if recovery took multiple attempts. |

## Recommended Sequence (Mode Switch)

1. **UI gating** – Disable mode-selection controls until reset completes to prevent double-presses.
2. **Widget reset** – `_reset_visualizer_state(replay_cached=True)`
   - Zero bars/energy caches.
   - Clear heartbeat/bubble state.
   - Request overlay mode reset with `reason="widget_reset_state"`.
3. **Beat engine reset** – `_reset_engine_state(reason="mode_switch")`
   - Cancel outstanding FFT tasks (`cancel_pending_compute_tasks`).
   - Reset smoothing/floor state.
   - Reapply smoothing tau / config.
4. **Overlay cold start** – In `SpotifyBarsGLOverlay.paintGL`, detect `_pending_mode_resets` and call `_reset_mode_state(mode, reason)` before uploading new uniforms.
5. **Replay settings** – After reset completes and cached kwargs exist, call `apply_vis_mode_kwargs()` with the stored snapshot so user sliders take effect. This replays preset overlays (if `preset_<mode>` != Custom) then restores any Custom overrides.
6. **Resume rendering** – Wait for `_waiting_for_fresh_engine_frame` to clear before showing overlay; propagate fade gating so the card does not pop.

## Diagnostics Expectations

- Every reset must log `[SPOTIFY_VIS] Engine state reset reason=...` and `[SPOTIFY_VIS][OVERLAY][RESET] mode=... reason=...`.
- When a GL context failure occurs, GLErrorHandler must record `record_shader_failure()` with the shader program name, demoting capability level as needed.
- Validation clips/logs should be archived under `logs/visualizer/YYYY-MM-DD/` whenever Crawl or other sensitive sliders are retuned so QA can compare post-reset behavior.

## Open Items / Follow-ups

1. **Automation** – Tests should assert that calling `SpotifyVisualizerWidget.set_visualization_mode()` triggers `_pending_mode_resets` and increments beat engine generation IDs, and that `bubble_gradient_direction` / `bubble_specular_direction` values survive the reset.
2. **Shared transitions** – Need clarity on whether compositor transitions require their own entry in this matrix (currently scoped to Spotify visualizer only).
3. **Bubble mode tooling** – Future Bubble-specific reset work (e.g., swirl drift) should extend the “Other Notes” column once the simulation exposes higher-level hooks.
