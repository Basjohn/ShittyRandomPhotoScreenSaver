# Current Plan (Forward-Looking)

## 1. Timer-Only Rendering Rollout — **Status: Completed**
- **Outcome:** Refresh-sync/adaptive toggles, settings keys, and tests have been removed. `DisplayWidget` now always derives `_target_fps` from detected Hz, and all GL surface descriptors request `swapInterval=0`.
- **Verification:**
  - `rendering/display_widget.py` hard-caps FPS via `_resolve_display_target_fps()` (adaptive ladder disabled).
  - `rendering/gl_format.py` and backend descriptors never re-enable driver VSync.
  - UI/tests/specs updated to remove references to the deprecated settings.
- **Next Steps:** Monitor logs for any regressions; if future telemetry demands expose VSync again, design a new strategy from scratch rather than resurrecting the legacy flags.

## 2. Comprehensive Settings Hygiene & Audit — **Status: Planned**
- **Goal:** Establish a single, authoritative settings pipeline (defaults → SettingsManager → dataclasses → UI → presets/tests/docs) and eliminate drift. The recent test failures (cache max_items, Reddit position) show multiple layers fall out of sync when defaults change.
- **Audit scope & actions:**
  1. **Canonical defaults alignment:**
     - Enumerate every key in `core/settings/defaults.py` and emit a structured dump (JSON) sorted alphabetically.
     - Cross-compare with dataclass defaults in `core/settings/models.py`; raise warnings for mismatches (type, value, or missing fields).
     - Verify `SettingsManager._set_defaults()` writes the same values to QSettings (include nested dict flattening) and that `reset_to_defaults()` truly wipes overrides.
  2. **Flats & caching:**
     - Inspect `SettingsManager.get_flat_defaults()` and any cached dictionaries used by presets/import/export. Ensure nested keys (e.g., `display.refresh_sync`) are preserved verbatim and not duplicated under legacy aliases.
     - Add unit tests exercising `get_flat_defaults()` vs dataclasses to guard against regressions.
  3. **UI bindings:**
     - Audit all tabs (Display, Widgets, Sources, etc.) for direct key references. Document which controls rely on `SettingsManager.get_bool` vs manual parsing, and ensure they handle missing keys gracefully.
     - Confirm each UI save path updates both canonical keys and any legacy mirrors (if required), then emits `settings_changed` events.
  4. **Presets & SST artifacts:**
     - Review `core/settings/presets.py`, sample SST bundles, and any onboarding JSON to ensure they either (a) explicitly override keys or (b) intentionally inherit canonical defaults. Remove stale overrides that fight the defaults.
     - Provide a regeneration script to re-export presets after defaults change.
  5. **Testing strategy:**
     - Expand `tests/test_settings_models.py` to cover every dataclass default, plus a round-trip test that instantiates a `SettingsManager`, calls `reset_to_defaults()`, and compares the resulting flat map to the dataclasses.
     - Add snapshot-style tests for presets/SST to ensure they stay aligned with defaults (fail if canonical values drift).
  6. **Documentation:**
     - Update `Spec.md` and `Index.md` with the canonical defaults plus notes on derived/legacy keys.
     - Outline the governance process: whenever a default changes, required steps include updating defaults map, dataclasses, UI help text, tests, docs, and preset regeneration.
- **Success criteria:**
  - Single source of truth documented and enforced by automated tests.
  - No failing tests due to drift when defaults change.
  - Clear runbook for future settings modifications (who updates what, in what order).

## 3. Media Card Controls (2.6 Parity) — **Status: Needs parity pass**
- **Why it matters:** The Spotify/Media card in current builds still drifts from the 2.6 reference (layout, control feedback, positioning). QA relies on the card for interaction cues, so we need pixel + behavior parity before pushing any refreshed UI.
- **Reference capture:**
  - Pull historical assets from the Git history (tag/branch `v2_6` in `Basjohn/ShittyRandomPhotoScreenSaver`) for `widgets/media_widget.py`, relevant QML/QSS, and transitional overlays. Document the canonical geometry, colors, and interaction timing.
  - When visual capture is impractical, rely on code diffs (layout constants, gradients, animations) to drive parity decisions.
- **Work items:**
  1. **Layout + styling**
     - [ ] Anchor the card Bottom Left (`OverlayPosition.BOTTOM_LEFT`) using the exact paddings and rounded-rectangle metrics from 2.6.
     - [ ] Reapply the matte glass gradient + divider treatment, matching font families/sizes/weights.
     - [ ] Verify background color/opacity constants match the reference implementation.
  2. **Control feedback**
     - [ ] Re-implement the bright rounded highlight and ~10 % scale pulse used in 2.6.
     - [ ] Ensure both mouse clicks and media-key events trigger the feedback path.
     - [ ] Cross-check `_controls_feedback` timing constants against the 2.6 commit history.
  3. **Positioning rules**
     - [ ] Audit monitor selection logic; preserve 2.6 cross-monitor behavior (affinity + context-menu overrides).
     - [ ] Add regression tests that instantiate the widget for every `WidgetPosition` and assert geometry calculations.
  4. **QA checklist:**
     - Compare current vs 2.6 behavior by diffing code-derived layout metrics and logging control events (no screenshots required).
     - Exercise control clicks + media keys while logging `[MEDIA] play_pause` outputs to confirm event propagation.
     - Validate theming across light/dark backgrounds and with both GL/software backends.
- **Deliverables:** Updated widget code/stylesheets and a short write-up summarizing differences vs 2.6 and how they were resolved (include git commit references for traceability).

## 4. Spotify Visualizer Responsiveness — **Status: Pending implementation**
- **Issue:** On cold start the visualizer often stays idle until multiple polls complete. Users expect an immediate response when pressing transport controls or media keys; we need deterministic wake-up without resorting to high-frequency polling.
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