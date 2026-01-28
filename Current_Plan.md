# Current Plan

## 1. Control Halo (Reduce Size by ~40%) — **Status: Completed**
- **Result:** Halo footprint now uses the `48 * 0.8` geometry with a 3px ring stroke in this repo, matching the 2.6 visual balance (no misaligned center dots). Before/after verification pending screenshot capture for the audit doc.

## 2. Display Settings Defaults (Sync ON, Adaptive OFF) — **Status: Blocked until re-port**
- **Scope / Risk:** `core/settings/defaults.py` currently ships `display.refresh_adaptive=True`, so first-run, reset-to-defaults, and presets all power up with adaptive caps enabled—even though docs/spec require Sync=ON / Adaptive=OFF. Any preset export/import (SST) or `SettingsManager.reset_to_defaults()` call reverts to the wrong combo and the UI dutifully reflects it, so QA keeps seeing adaptive ladders even after manually fixing them.
- **Likely causes:**
  - Default map never updated in this repo after the legacy-port (audit log shows changes only in the retired folder).
  - Preset templates and SST snapshots still reference the stale adaptive flag, so presets reapply the bad state even if defaults flip.
  - DisplayTab loads via `SettingsManager.get_bool()` and therefore mirrors whatever is stored—so parity hinges entirely on the canonical defaults being correct.
- **Proposed execution:**
  1. Update `core/settings/defaults.py` so `refresh_sync=True`, `refresh_adaptive=False`, and regenerate the flattened defaults to ensure `get_flat_defaults()` mirrors the new values.
  2. Add regression coverage in `tests/test_settings_models.py::TestDisplaySettings` (and, if needed, `tests/test_display_tab.py::test_display_tab_default_values`) to pin Sync=ON / Adaptive=OFF.
  3. Rebuild preset templates (`core/settings/presets.py`, tools/regenerate scripts, SST snapshots) so they ingest the updated defaults. Document the runbook in `Docs/PARITY_PLAN.md` if tooling changes.
  4. Verify reset workflow: `SettingsManager.reset_to_defaults()`, first-launch, and preset cycling (Standard, Minimal, MC) must all leave Sync=ON / Adaptive=OFF unless a preset explicitly overrides it. Capture logs/screenshots for the audit bundle.
  5. Update `Spec.md`/Index if any wording changed during the audit.

## 3. Settings GUI Regression (Toggling Resets FPS Cap) — **Status: Investigation to restart here**
- **Observed:** First-toggle works (Sync OFF uncaps, Adaptive toggles react). After leaving/re-entering the Display tab and toggling again, both screens snap back to the capped ladder and `_target_fps` returns to the adaptive tiers even though the UI shows Sync OFF. Logs confirm the setting is saved, but no runtime component reapplies it.
- **Root causes identified so far:**
  - `DisplayWidget` only hooks `SettingsManager.settings_changed` for the `"transitions"` key, so runtime refresh toggles never trigger `_configure_refresh_rate_sync()` or `_ensure_gl_compositor()` unless the window is rebuilt. Any UI toggle therefore persists to QSettings but the running display keeps its original FPS target until restart.
  - There is zero structured logging around `display_tab._save_settings()` or refresh handlers, so diagnosing round-trip failures requires spelunking raw QSettings dumps.
  - Adaptive checkbox state is stored even when disabled; combined with the stale defaults from Item 2, reopening the tab frequently re-enables adaptive caps without any visual indication.
- **Proposed execution:**
  1. Instrument `DisplayTab` (verbose-only) to log refresh-sync/adaptive saves and the resulting values read back from `SettingsManager`, so we can prove round-trip behavior before/after fixes.
  2. Extend `DisplayWidget` to subscribe to `display.refresh_sync`, `display.refresh_adaptive`, and `display.hw_accel` (either via targeted `register_change_handler` or by listening to `settings_changed` and filtering). Handlers must immediately call `_configure_refresh_rate_sync()` and, when hw accel toggles, `_ensure_gl_compositor()`.
  3. Add a regression harness (likely in `tests/test_display_tab.py` or a new `tests/test_display_refresh_sync.py`) that toggles Sync/Adaptive twice and asserts `_target_fps` follows the expected ladder (full-rate when sync off, adaptive tiers only when both toggles demand it). Guard with `pytest.mark.qt`.
  4. Audit `SettingsManager.to_bool`/cache to confirm no stale values remain post-toggle; if caching interferes, add targeted cache invalidation or disable caching for display.* keys.
  5. Once instrumentation verifies runtime reconfiguration, remove verbose logs or keep them behind `is_verbose_logging()` per logging policy.

## 4. Media Card Controls (2.6 Visual Reference & Repro) — **Status: Needs parity pass**
- **Look & Layout:**
  - Card anchored Bottom Left by default (`OverlayPosition.BOTTOM_LEFT`).
  - Artwork frame (200px logical, rounded corners 8px) on the left, Spotify header with glyph on top row, title/artist text stacked with adaptive shrinking.
  - Transport controls row sits along the card’s lower margin: matte black glass bar with 6px rounded corners, thin vertical dividers at 1/3 intervals, white glyphs (Prev ←, Play ▶ / Pause ||, Next →). SINGLE Click/Media Key feedback adds bright rounded highlight scaling ~10%.
- **Reproduction Steps (upcoming QA pass):**
  1. Launch 2.6 baseline build with `SRPSS_PERF_METRICS=1` to enable hover logs.
  2. Press `Ctrl` to enter interaction mode (confirms halo) and click the media card bottom row to trigger control feedback and log entries (`[MEDIA] play_pause` etc.).
  3. Use media keys (Play/Pause, Next, Previous) to observe synchronized feedback (QTimer-driven) and verify `_controls_feedback` paints the highlight rectangles.
  4. Document with screenshots (Idle state + button press) for design parity.

## 5. Spotify Visualizer Start Reliability — **Status: Pending implementation**
- **Issue:** On first run the visualizer often stays idle until multiple polls complete. Need deterministic wake-up when the user presses transport controls or media keys without resorting to high-frequency polling.
- **Immediate next steps:**
  1. Register to the existing `EventSystem` topic `MEDIA_CONTROL_TRIGGERED` (already used by MediaWidget for feedback). When an event fires, force a one-shot refresh on the visualizer pipeline (FFT worker and widget) if it’s currently idle.
  2. Add a `request_refresh(reason: str)` hook on `SpotifyVisualizerWidget` that checks resources (FFT worker instantiated, last spectrum timestamp older than threshold) and triggers an immediate poll, then resumes normal cadence.
  3. Gate new logging behind `is_perf_metrics_enabled()` to avoid log spam.
  4. Manual QA: press media keys and confirm the visualizer animates within one polling interval (<1 s) even without prior track detection.
  5. Ensure no additional timers are created—reuse the existing overlay timer handle and poke the worker via `ThreadManager.single_shot`.

---
**Next Steps (Keep this doc current; rewrite when ≥50% becomes historical):**
1. Deliver the control halo change and capture 2.6 parity screenshots.
2. Re-port display defaults, update preset/load paths, and regression-test the Display tab toggles.
3. Document media card visuals (screenshots) and maintain Spotify visualizer wake-up guarantees.
4. After each batch, run the standard perf/iterative cycling loop to confirm FPS, widget fades, and media interactions remain stable. Remove or rewrite sections promptly as deliverables land to keep this plan ≥50% forward-looking.
