# Harness Index

Last updated: 2026-07-12

Compact reference for recurring SRPSS investigation harnesses and probes.

## Usage Rule
- Prefer targeted harnesses for diagnosis and regression confirmation.
- Keep these commands narrow; they are meant to support real bug families, not replace full runtime testing.
- For visual, timing-sensitive, or focus-sensitive bugs, harness success is evidence, not final sign-off.

## Settings / Windowing

### Canonical defaults editor and regeneration
- Purpose: inspect or change every discovered Normal/MC fresh-install/reset default without hand-editing the large base mapping or drifting generated artifacts.
- Tool: `tools/default_settings_editor.py`
- GUI command:
```powershell
python tools/default_settings_editor.py
```
- Headless construction/discovery bar:
```powershell
$env:QT_QPA_PLATFORM='offscreen'
python tools/default_settings_editor.py --smoke-test
python -m pytest tests/test_default_settings_editor.py tests/test_regenerate_sst_defaults.py tests/test_settings_profile_separation.py tests/test_settings_dialog_cache.py tests/test_settings_defaults_parity.py -q
```
- Notes:
  - Normal writes the authoritative `default_settings.py` base; MC stores only differences from resolved Normal defaults.
  - Alpha colour swatches and font-family leaves use application controls; all other leaves remain type-aware and recursively discovered.
  - **Import SST / JSON Into Selected Profile** merges an exported application snapshot into the selected model while stripping credentials, reset-preserved source/weather state, machine-local absolute paths, active CUSTOM geometry, and layout slots. It remains unsaved until Save and Regenerate.
  - Every string leaf tooltip identifies registered finite choices or its accepted free-text domain.
  - Save regenerates `core/settings/defaults_snapshot.json` plus both canonical SST files in fresh processes, with SST managers rooted in a temporary directory rather than either installed profile.
  - Failed save/undo regeneration restores the prior canonical base, MC source, prior undo state, and regenerated artifacts when rollback generation remains available; a second rollback failure is reported explicitly.
  - Undo state is local under `%LOCALAPPDATA%/SRPSS/DefaultSettingsEditor`, never in the repository.
  - The editor changes fresh/reset defaults, not the current user's saved settings.

### WidgetsTab lazy-section and settings-lifetime slice
- Purpose: protect descriptor-owned WidgetsTab section routing, lazy hydration, hydrated-only normal save collection, the still-loud direct unhydrated-save guard, visualizer-section persistence, dev-gated Blob UI construction, and stale settings-slider QObject lifetime handling.
- Use when:
  - editing `ui/tabs/widgets_tab.py`
  - editing `ui/tabs/widgets_tab_media.py`
  - changing WidgetsTab descriptor load/save/build routing
  - changing settings slider/highlight helpers in `ui/tabs/shared_styles.py`
- Typical command:
```powershell
python -m pytest `
  tests/test_widgets_tab.py `
  tests/test_settings_dialog.py::test_settings_dialog_widgets_tab_accessor_keeps_visualizers_restore_hydrated `
  tests/test_settings_dialog.py::test_settings_dialog_builds_widgets_tab_in_lazy_mode `
  tests/test_settings_dialog.py::test_settings_dialog_exposes_widgets_tab_via_lazy_accessor `
  tests/test_settings_shared_styles.py `
  -q
```

### Settings dialog flicker / transient ghost windows
- Purpose: reproduce and isolate constructor-time flicker, ghost HWNDs, and transient helper windows.
- Tools:
  - `tools/flicker_test.py`
  - `tools/winprobe_observer.py`
- Typical commands:
```powershell
python tools/flicker_test.py
python tools/winprobe_observer.py
```
- See also: `Docs/Historical_Bugs.md` entry `R-18`.

## Steam Widgets

### Production Steam source / cache / visual lock
- Purpose: protect Achievement Pulse and Abandonment Issues source provenance, successful-only cache authority, cross-card/display request reuse, cache-before-fade lifecycle, worker-prepared assets, sparse content transitions, settings/default parity, and deterministic authored geometry.
- Use when editing `core/steam/`, either production Steam widget, Steam descriptors/factories/settings, shared Steam painting, or Steam refresh/transition policy.
- Typical command:
```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest `
  tests/test_steam_backend.py `
  tests/test_steam_cache.py `
  tests/test_steam_request_policy.py `
  tests/test_steam_profile_assets_events.py `
  tests/test_steam_achievement_pulse.py `
  tests/test_steam_abandonment_issues.py `
  tests/test_steam_phase3_settings_descriptors.py `
  tests/test_steam_phase4_mock_visuals.py `
  -q
```
- Notes:
  - Tests use synthetic fixtures and injected openers only; no test may contact Steam or contain real account data.
  - Offscreen raster bars require bundled font registration for representative typography. They prove geometry and paint safety, not final frozen-build/multi-display appearance.
  - Runtime validation should use `--steam --perf --cache --set --geo --life`; add `--devsteam` only when intentionally testing Journey/Friend prototypes.

## Secure-Desktop / Link Handoff

### Reddit helper scheduled-task smoke test
- Purpose: verify the helper registration/run path used for secure-desktop or saver-side URL handoff.
- Tool: `tools/reddit_helper_task_harness.py`
- Typical command:
```powershell
python tools/reddit_helper_task_harness.py --action smoke-test --task-name SRPSS_TaskHarness_Test
```
- See also: `Docs/Historical_Bugs.md` entry `R-02`.

### Reddit widget automatic refresh cadence and provider fallback
- Purpose: protect Reddit widget cache/update cadence so settings/runtime rebuilds cannot keep resetting the first periodic refresh into the future, paired stale startup caches use the `30s` stagger instead of suppression, manual refresh uses its shorter sparse gate, provider fallback follows the bounded session/configured -> old -> www source chain, and the retired cache-growth reveal does not return.
- Use when:
  - editing `widgets/reddit_widget.py`
  - editing shared service-widget timer/startup refresh policy
  - investigating stale Reddit cache timestamps or missing `[CACHE][REDDIT] Periodic refresh fired` logs
  - investigating manual refresh spiral lockouts or candidate-window/display-count behavior
  - editing Reddit provider selection, RSS/Public JSON/PullPush behavior, or the designed old/www Reddit HTML fallback
- Typical command:
```powershell
python -m pytest `
  tests/test_reddit_progressive_loading.py `
  tests/test_reddit_post_provider.py `
  tests/test_reddit_provider_settings.py `
  tests/test_reddit_widget.py::test_reddit_periodic_refresh_due_fires_stale_primary_without_recurring_reset `
  tests/test_reddit_widget.py::test_reddit2_periodic_refresh_staggers_stale_due_not_repeat_cadence `
  tests/test_reddit_widget.py::test_reddit_periodic_due_survives_widget_rebuild `
  tests/test_reddit_widget.py::test_reddit_startup_refresh_skips_when_cache_is_fresh `
  tests/test_reddit_widget.py::test_reddit2_startup_refresh_paces_second_stale_cache_behind_reddit1 `
  tests/test_reddit_widget.py::test_reddit_manual_fetch_bypasses_automatic_blocked_cooldown_after_manual_window `
  tests/test_reddit_widget.py::test_reddit_empty_provider_result_does_not_freshen_cache_timestamp `
  tests/test_reddit_widget.py::test_reddit_fetch_caches_candidate_window_but_displays_configured_count `
  -q
```
- See also: `Docs/Historical_Bugs.md` entry `R-29`.

## Media Keys / MC Focus

### Media-key scenario matrix
- Purpose: compare focused/unfocused/manual-click scenarios across launch/profile modes.
- Tool: `tools/media_key_matrix_harness.py`
- Example command:
```powershell
python tools/media_key_matrix_harness.py --launch mc --profile-mode mirrored --focus-policy realistic --scenarios focused_idle,focused_clicked
```

### Reality harness
- Purpose: capture longer-running focus transitions and manual-focus behavior in a more realistic MC path.
- Tool: `tools/media_key_reality_harness.py`
- Example command:
```powershell
python tools/media_key_reality_harness.py --profile-mode mirrored --scenario focus_transition --manual-focus-seconds 8 --observe-seconds 12
```

### Hardware ingress validator
- Purpose: correlate real physical key ingress with SRPSS logging when synthetic probes are not enough.
- Tool: `tools/hardware_ingress_validator.py`
- When to use:
  - focused-click MC failures
  - “keys are eaten” reports
  - disagreements between synthetic harnesses and real hardware behavior
- See also: `Docs/MEDIAKEYDEBUG.md`, `Docs/Historical_Bugs.md` entry `U-05`.

## Visualizer / Distribution / Presets

### Current-good visualizer reactivity lock
- Purpose: protect the currently accepted behavior of `Spectrum`, `Sine Waves`, `Bubble`, `Dev Curve`, and `Oscilloscope` before touching shared visualizer/audio/activation/render/transition seams.
- Use when:
  - editing visualizer tick/render/audio feed plumbing
  - changing mode activation/reset/first-frame behavior
  - changing overlay payloads or transition handoff
  - changing shared perf paths that could alter visualizer timing
- Typical command:
```powershell
python -m pytest `
  tests/test_spotify_visualizer_widget.py::test_spectrum_organs_first_visible_frame_is_nontrivial_under_authored_phrase `
  tests/test_spotify_visualizer_widget.py::test_mode_switch_organs_first_visible_frame_matches_fresh_activation_oracle `
  tests/test_spotify_visualizer_widget.py::test_mode_switch_deep_sea_first_visible_frame_matches_fresh_activation_oracle `
  tests/test_spotify_visualizer_widget.py::test_runtime_cycle_all_modes_and_settle_devcurve_matches_settings_refresh `
  tests/test_transient_per_mode_integration.py::TestSineOscTransientWidthMix::test_sine_width_reaction_modulated `
  tests/test_devcurve_runtime.py::test_devcurve_active_amplitude_exceeds_idle_amplitude `
  tests/test_oscilloscope_display_contract.py `
  -q --tb=short
```
- Notes:
  - Bubble oracle failures that only reflect stale expected values are re-baseline work, not permission to change Bubble feel.
  - `Oscilloscope` is now part of the accepted lock after its mode-owned waveform/ghost/glow pass; keep future changes mode-owned unless a shared seam is proven.
  - A lone `[FIRST_FRAME_PRIMER]` is expected remediation when the overlay still owns an old generation/activation before the first authoritative push. Escalate only when current source authority does not replace it, or when `FIRST_FRAME_GUARD`, `PARITY`, technical replay, fallback, or stale-commit evidence also fails.
  - Cached `[PERF][SPOTIFY_VIS][BUBBLE]` summaries can outlive Bubble mode. They are telemetry-only unless Bubble simulation/drift/dispatch lines also continue after the switch.
  - Harness success is still not final sign-off for visual bugs, but this lock is the required pre/post guard for shared seams.

### Blob Mighty / Shaped architecture lock

- Purpose: protect the preset-owned Blob subtype contract, canonical migration, isolated UI/runtime/shader ownership, subtype-boundary resets, Mighty organic behavior, Shaped authored-contour behavior, and shared reactive body paint.
- Use when:
  - changing `blob_type`, Blob defaults/model/snapshot/preset repair, or Blob curated payloads
  - editing Blob Settings builders/binding
  - editing Blob runtime config, overlay state, renderer dispatch, contour solvers, or shader programs
  - investigating stale Shaped/Mighty state after startup, settings refresh, preset apply, or hot cycling
- Focused command:
```powershell
python -m pytest `
  tests/test_visualizer_blob_contract.py `
  tests/test_blob_type_runtime.py `
  tests/test_blob_unshaped_geometry.py `
  tests/test_blob_shaper_plumbing.py `
  tests/test_blob_pockets.py `
  tests/test_blob_intensity_reserve.py `
  tests/test_blob_inward_liquid.py `
  tests/test_blob_shader_compile.py `
  tests/test_visualizer_reactivity_quality.py `
  tests/test_visualizer_overlay_kwargs.py `
  tests/test_overlay_render_dispatch.py `
  tests/test_startup_shader_warmup.py `
  tests/test_visualizer_presets.py `
  tests/test_visualizer_preset_cycling_runtime.py `
  -q --tb=short
```
- Focused Blob UI/settings command:
```powershell
python -m pytest tests/test_settings_manager.py tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "blob" -q --tb=short
```
- Schema/artifact checks:
```powershell
python tools/regenerate_defaults_snapshot_artifacts.py
python tools/regenerate_visualizer_shipped_presets.py
python tools/visualizer_preset_repair.py --audit-curated
```
- Notes:
  - Run the current-good visualizer reactivity lock before and after any change that crosses shared audio/activation/render seams.
  - The strong Mighty oracle uses 128 samples and a synthetic fixed-phase quiet/hot vector. It must measure non-circular idle shape, pixel-scale contour/Stretch movement, at least `95%` target-to-settled audio-delta transfer, bounded attack/release, and zero-shift-dominant temporal motion. A large static spread or helper-only variation is not closure.
  - The strong Shaped oracle uses synthetic authored base/reaction nodes rather than a copied temporary preset. It must measure mutation beyond the authored no-motion goal, temporal/fixed-angle motion, representative pixel reach, bounded neighbor steps, clean release, and zero-shift-dominant growth/relaxation.
  - Do not turn temporary showcase presets into exact artistic regression snapshots. Preset bars own schema, subtype payload isolation, slot/manifest integrity, and runtime application; synthetic contour cases own the measurable creative behavior.
  - Green automation proves the contract, not the final look. Under `-devblob`, validate Mighty and Shaped at startup and through curated/Custom hot switches; confirm `[SPOTIFY_VIS][BLOB][TYPE_RESET]` occurs only at real subtype boundaries, no fallback appears, both body fills visibly react, Mighty stays organic/bounded with no circular center, and Shaped mutates around then returns cleanly to its authored contour.
  - In Blob logs, `[BLOB_PROFILE]` is final-runtime evidence. Compare it with incoming bands/transients and, for code closure, with target-profile synthetic bars; profile spread alone can be the static authored shape. Interpret `[FIRST_FRAME_PRIMER]` under the same authority rule as the current-good lock above.

### Visualizer distribution harness
- Purpose: inspect transition-random distribution or mode-selection skew over longer sessions.
- Tool: `tools/visualizer_distribution_harness.py`

### Bubble historical parity harness
- Purpose: compare current Bubble curated preset behavior against historical-good revisions when present-day runtime bars are no longer trustworthy.
- Tool: `tools/bubble_parity_harness.py`
- Typical commands:
```powershell
python tools/bubble_parity_harness.py --preset preset_1_deep_sea.json
python tools/bubble_parity_harness.py --preset preset_9_deap_sea_experimental.json
```
- Notes:
  - compares current BubbleSimulation against `9d4925e` and `510520e`
  - includes the harsher `runtime_loud_phrase` comparison lane for sustained-loud audits
  - use alongside authored widget-path tests, not instead of them

### Preset repair tool
- Purpose: audit, repair, and reindex visualizer preset payloads without hand-edit drift.
- Tool: `tools/visualizer_preset_repair.py`
- Use when:
  - preset schema changes
  - slot/index normalization changes
  - curated preset loading behavior drifts

## Performance / Metrics

### Image cache / prewarm producer contract
- Purpose: guard the transition-adjacent image prewarm path so scaled warmups cannot orphan work, skip later preview images only because active IO slots are full, hide fallback state from `--cache` logs, or reintroduce raw `QTimer.singleShot` delayed work outside the ThreadManager seam.
- Use when:
  - editing `utils/image_prefetcher.py`
  - editing `engine/image_pipeline.py` cache/prefetch scheduling
  - investigating `[CACHE] [FALLBACK] Worker fallback reason=scaled_miss raw_state=raw_missing`
- Typical command:
```powershell
python -m pytest tests/test_image_prefetcher.py tests/test_image_pipeline.py -q --tb=short
```

### Widget and integration perf probes
- Tools:
  - `tools/perf_integration_harness.py`
  - `tools/perf_measure.py`
  - `tools/overlay_log_parser.py`
  - `tools/spotify_vis_metrics_parser.py`
  - `tools/slide_metrics_parser.py`
  - `tools/transition_perf_health_parser.py`
- Use when:
  - widget repaint churn is suspected
  - transition contention is suspected
  - visualizer perf logs need aggregation
  - mixed-refresh transition windows need a fail-fast health check
  - Spotify visualizer overlay paint/update cadence needs to be checked for both overpaint and under-delivery against the owning display target
  - cache fallback warnings need producer-state classification
  - pending paint/update delivery needs to be distinguished from render timer cadence and queued-dispatch coalescing
- Transition/cache health commands:
```powershell
python tools/transition_perf_health_parser.py --log logs\screensaver_perf.log --max-samples 8
python tools/transition_perf_health_parser.py --log logs\screensaver_perf.log --max-samples 8 --timeline
python tools/transition_perf_health_parser.py --log logs\screensaver_perf.log --extra-log logs\screensaver_spotify_vis.log --extra-log logs\screensaver.log --max-samples 8
python tools/transition_perf_health_parser.py --log logs\screensaver_cache.log --max-samples 8
```
- Add `--fail-on-anomaly` when using it as a CI/local bar. It flags paired paint-delivery starvation where same-screen `GL RENDER` remains healthy but `GL PAINT` under-delivers, high-refresh visual paint/render windows stuck near 60fps, high-refresh animation/control callback cadence collapsed near 60fps, stable divisor-like cadence (`target/2` or `target/3`), Spotify visualizer overlay overpaint beyond the owning display target, Spotify visualizer overlay under-delivery where the feed is healthy but paint/update cadence is visibly choppy, render timer wakeups skipped because an update dispatch was still queued or paint pending had gone stale (`pending_skips`), 60Hz transition/render/paint windows far under target, AnimationManager progress-sample windows far under target, MediaWidget timer gaps, Spotify visualizer timing warnings, settings UI stalls above 1s, pending-paint requeue rescues, passive pending-paint stalls with `no_requeue=True`, zero-producer cache worker fallbacks, slow GL texture uploads, and loud shader fallbacks.
- Use `--extra-log logs\screensaver_spotify_vis.log --extra-log logs\screensaver.log` when investigating Spotify/media/visualizer topology; the perf sidecar owns render/paint cadence, the viz sidecar owns visualizer creation/display ownership, and the main log carries media/fallback context.
- Add `--timeline` when root-causing collapse. It prints settings stalls, edit saves, display lifecycle churn, frame-budget spikes, visualizer tick spikes, slow uploads, fallback use, and pending-paint rescues so paint starvation can be correlated before touching runtime cadence.
- For current shader-authoritative compositor transitions, `GL PAINT` / `GL RENDER` are the primary visible cadence signals. `GL ANIM` transition-progress windows should not be required for those paths after the paint-time `FrameState` handoff; if they reappear during shader transitions, treat that as a regression toward UI-timer-owned progress.

## Maintenance
- If a harness becomes part of a real recurring workflow, add it here and link the relevant bug/history doc.
- If a harness is retired, remove it here in the same change that retires the tool.
