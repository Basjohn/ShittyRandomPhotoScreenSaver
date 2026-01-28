# Current Plan (Forward-Looking)

## 1. Verify Sync vs Uncapped Rendering End-to-End — **Status: In Progress**
- **Observed Behavior (latest run @ `2026-01-28 20:59`):**
  1. Instrumentation shows `_configure_refresh_rate_sync()` picking 165 Hz for Display 0 when sync is OFF, yet the compositor only retimes once the next transition starts. Until a transition spins up, `_restart_render_strategy()` bails because no timer is running, which matches the "needs one more transition" complaint.
  2. Even when timers restart at 6 ms (`target=165Hz`), both screens still present at ~60 Hz. The GL surface swap interval never changes after creation, so toggling sync just twiddles timers while `QSurfaceFormat.setSwapInterval` stays at the original value. This violates the requirement that sync OFF must give uncapped FPS on *all* screens simultaneously.
  3. Display 2 occasionally drifts to ~40 Hz even though we log a 60 Hz target. Likely causes: shared GPU queue starvation when Display 0 requests 6 ms timers, or the second compositor inheriting the wrong swap interval / render-thread pacing.
  4. All three instrumentation tasks are DONE (`log_refresh_decision`, render strategy reason logging, GL compositor fallback rationale). Focus now shifts to plumbing fixes that keep the experience seamless (tear-downs or swaps must be invisible to the user).

- **Immediate tasks:**
  1. **Swap interval + surface lifecycle (user-invisible)**
     - [ ] Reapply `setSwapInterval(0|1)` whenever `display.refresh_sync` flips. If Qt refuses to change it live, tear down and recreate the GL surface (via `_destroy_render_surface()` + `_ensure_gl_compositor()`) in a double-buffered/hidden phase so the user never sees a flicker.
     - [ ] Add a one-time log dumping the effective swap interval from `QOpenGLContext.format()` so future runs prove we actually flipped vsync, and assert per-screen values so mixed-Hz rigs stay respected.

  2. **Idle-phase retiming**
     - [ ] When `_restart_render_strategy()` runs while idle, store the desired FPS and immediately poke the compositor to rebuild timers before the next transition (e.g., schedule a lightweight `render_strategy_manager.configure` + `start/stop` cycle or keep a background timer alive for static scenes) so uncapped mode snaps to unlimited FPS without waiting for motion.
     - [ ] Extend logging so we know whether the restart was skipped because no strategy was active; emit a warning in that case to make the "needs another transition" bug obvious in logs and guarantee all screens honor the latest command simultaneously.

  3. **Second display pacing audit**
     - [ ] Capture per-display frame durations straight from `GLCompositor._record_render_timer_tick()` (include `screen_index`, `dt_ms`, `target_fps`) to verify the 40 Hz observation and see whether we're starving that compositor.
     - [ ] Check whether both compositors share a single `QOpenGLContext`/thread that serializes swapbuffers; if so, evaluate isolating contexts or staggering timers so Display 2 is not waiting on Display 0 and still achieves true uncapped throughput when sync is OFF.
  - Remove the extra instrumentation guards once the above proof exists and bake the CLI helper into the QA checklist.

## 2. Comprehensive Settings Hygiene & Audit — **Status: Planned**
- **Goal:** Establish a single, authoritative settings pipeline (defaults → SettingsManager → dataclasses → UI → presets/tests/docs) and eliminate drift. The recent test failures (cache max_items, Reddit position) show multiple layers fall out of sync when defaults change.
- **Actionable subtasks:**
  1. **Canonical defaults alignment:**
     - [ ] Build a script (`tools/dump_defaults.py`) that emits JSON of `core/settings/defaults.py` (sorted) and dataclass defaults side-by-side.
     (Developer question, why do this instead of just migrating settings to a json file instead? Why keep this complexity?)
     - [ ] Add CI check comparing the JSON dump against dataclass definitions; fail if any key diverges (value or type).
     - [ ] Exercise `SettingsManager.reset_to_defaults()` on a throwaway profile and diff the resulting `QSettings` store vs the canonical dump to ensure no missing keys.
  2. **Flats & caching:**
     - [ ] Review `SettingsManager.get_flat_defaults()` for order/deduping; document its contract inside `Spec.md`.
     - [ ] Add targeted unit tests verifying nested keys (e.g., `display.refresh_sync`) remain intact and no legacy alias overwrites them.
  3. **UI bindings audit:**
     - [ ] Inventory every settings UI component (DisplayTab, WidgetsTab, etc.) noting the keys they load/save.
     - [ ] For each component, ensure we call `SettingsManager.set(...)` with canonical keys only; if legacy keys are needed, document why and add TODO to sunset them.
     - [ ] Add smoke tests that simulate load/save cycles for the most volatile tabs (Display, Widgets, Particle Transition - I find it resets to directional very often without permission) verifying round-trip data matches defaults.
  4. **Presets & SST artifacts:**
     - [ ] Enumerate preset definitions and sample SST JSON; flag overrides that duplicate current defaults.
     - [ ] Create a regeneration helper (`tools/regenerate_presets.py`) to rebuild presets whenever defaults change.
     - [ ] Store golden preset snapshots under `tests/data/presets/` and add snapshot tests catching drift.
  5. **Testing strategy expansion:**
     - [ ] Extend `tests/test_settings_models.py` to cover remaining dataclasses, ensuring each field has a default assertion.
     - [ ] Add a “round-trip” test: instantiate `SettingsManager`, call `reset_to_defaults()`, and assert the flat dict equals dataclass defaults (after type normalization).
  6. **Documentation & governance:**
     - [ ] Update `Spec.md` and `Index.md` with canonical defaults list + description of the governance workflow.
     - [ ] Draft a short SOP (under `/docs/process/settings_change.md`) describing the steps required when modifying settings (update defaults, dataclasses, UI, presets, tests, docs).
- **Success criteria:**
  - Single source of truth documented and enforced by automated tests.
  - No failing tests due to drift when defaults change.
  - Clear runbook for future settings modifications (who updates what, in what order).

## 3. Media Card Controls (2.6 Parity) — **Status: Needs parity pass**
- **Why it matters:** The Spotify/Media card in current builds still drifts from the 2.6 reference (layout, control feedback, positioning). QA relies on the card for interaction cues, so we need pixel + behavior parity before pushing any refreshed UI.
- **Reference capture:**
  - Pull historical assets from the Git history (tag/branch `v2_6` in `Basjohn/ShittyRandomPhotoScreenSaver`) for `widgets/media_widget.py`, relevant QML/QSS, and transitional overlays. Document the canonical geometry, colors, and interaction timing.
- **Actionable subtasks:**
  1. **Layout + styling:**
     - [ ] Ensure the card anchors Bottom Left (OverlayPosition.BOTTOM_LEFT) with the exact paddings and rounded rectangle metrics from 2.6.
     - [ ] Reapply the matte glass gradient + divider treatment, matching font sizes/weights.
     - [ ] Verify the card’s background color and opacity match the reference.
  2. **Control feedback:**
     - [ ] Re-implement the button feedback (bright rounded highlight, ~10 % scale pulse) and ensure both mouse clicks and media-key events trigger the effect.
     - [ ] Reference 2.6 commit diffs for `_controls_feedback` timing constants.
  3. **Positioning rules:**
     - [ ] Audit how the current widget selects monitor/position. Preserve cross-monitor behavior from 2.6 (respect monitor affinity, context menu overrides).
     - [ ] Add regression tests that instantiate the widget with each `WidgetPosition` and verify geometry calculations.
- **Work items:**
  1. **Layout + styling:** Ensure the card anchors Bottom Left (OverlayPosition.BOTTOM_LEFT) with the exact paddings and rounded rectangle metrics from 2.6. Reapply the matte glass gradient + divider treatment, matching font sizes/weights.
  2. **Control feedback:** Re-implement the button feedback (bright rounded highlight, ~10 % scale pulse) and ensure both mouse clicks and media-key events trigger the effect. Reference 2.6 commit diffs for `_controls_feedback` timing constants.
  3. **Positioning rules:** Audit how the current widget selects monitor/position. Preserve cross-monitor behavior from 2.6 (respect monitor affinity, context menu overrides). Add regression tests that instantiate the widget with each `WidgetPosition` and verify geometry calculations.
  4. **QA checklist:**
     - Compare current vs 2.6 screenshot overlays.
     - Exercise control clicks + media keys while logging `[MEDIA] play_pause` outputs to confirm event propagation.
     - Validate theming across light/dark backgrounds and with both GL/software backends.
- **Deliverables:** Updated widget code/stylesheets and a short write-up summarizing differences vs 2.6 and how they were resolved (include git commit references for traceability).

## 4. Spotify Visualizer Responsiveness — **Status: Pending implementation**
- **Issue:** On cold start the visualizer often stays idle until multiple polls complete. Users expect an immediate response when pressing transport controls or media keys; we need deterministic wake-up without resorting to high-frequency polling. This also needs to function if music is ALREADY playing.
- **Planned improvements:**
  1. **Event-driven refresh:** Subscribe `SpotifyVisualizerWidget` (or a helper manager) to `EventSystem` topics such as `MEDIA_CONTROL_TRIGGERED` and `MEDIA_TRACK_CHANGED`. When events fire and the visualizer is idle, trigger a one-shot refresh path.
  2. **Widget API:** Add `request_refresh(reason: str)` that checks whether FFT worker state, spectra, and textures are ready. If stale, kick the FFT worker via `ThreadManager.single_shot` and repaint overlays once data arrives. Keep calls idempotent.
  3. **Resource readiness:** Ensure FFT worker initialization is awaited before we declare the widget live. If the worker is still spinning up, buffer the event and replay once ready.
  4. **Telemetry & logging:** Log refresh requests under `widgets.spotify_visualizer` (gated behind `is_perf_metrics_enabled()` to avoid spam) noting reason, latency, and success, so QA can confirm responsiveness from logs.
  5. **QA checklist:** Press play/pause/next via keyboard/mouse immediately after launch and confirm the visualizer animates within one polling interval (<1 s). Test both GL and software backends, plus MC builds.
- **Deliverables:** Updated widget/worker code, log samples demonstrating <1 s wake-up, and regression tests (where feasible) that simulate `request_refresh` to ensure no-ops when already active.

---
**Execution Notes:** Revise this plan whenever ≥50 % of items are delivered so it always reflects current priorities. Attach instrumentation/scripts created for Item 1 to the audit repo once validated, then prune temporary logs to keep production builds lean.
ONLY remove completed items from this plan!