# Harness Index

Last updated: 2026-06-22

Compact reference for recurring SRPSS investigation harnesses and probes.

## Usage Rule
- Prefer targeted harnesses for diagnosis and regression confirmation.
- Keep these commands narrow; they are meant to support real bug families, not replace full runtime testing.
- For visual, timing-sensitive, or focus-sensitive bugs, harness success is evidence, not final sign-off.

## Settings / Windowing

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

## Secure-Desktop / Link Handoff

### Reddit helper scheduled-task smoke test
- Purpose: verify the helper registration/run path used for secure-desktop or saver-side URL handoff.
- Tool: `tools/reddit_helper_task_harness.py`
- Typical command:
```powershell
python tools/reddit_helper_task_harness.py --action smoke-test --task-name SRPSS_TaskHarness_Test
```
- See also: `Docs/Historical_Bugs.md` entry `R-02`.

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
- Purpose: protect the currently accepted behavior of `Spectrum`, `Sine Waves`, `Bubble`, and `Dev Curve` before touching shared visualizer/audio/activation/render/transition seams.
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
  -q --tb=short
```
- Notes:
  - Bubble oracle failures that only reflect stale expected values are re-baseline work, not permission to change Bubble feel.
  - `Oscilloscope` remains a watchlist mode; do not block unrelated health work on Osc behavior unless the task explicitly targets it.
  - Harness success is still not final sign-off for visual bugs, but this lock is the required pre/post guard for shared seams.

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
- Purpose: guard the transition-adjacent image prewarm path so scaled warmups cannot orphan work, skip later preview images only because active IO slots are full, or hide fallback state from `--cache` logs.
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
  - cache fallback warnings need producer-state classification
- Transition/cache health commands:
```powershell
python tools/transition_perf_health_parser.py --log logs\screensaver_perf.log --max-samples 8
python tools/transition_perf_health_parser.py --log logs\screensaver_cache.log --max-samples 8
```
- Add `--fail-on-anomaly` when using it as a CI/local bar. It flags high-refresh transition windows stuck near 60fps, 60Hz transition/render windows far under target, AnimationManager windows far under target, zero-producer cache worker fallbacks, and loud shader fallbacks.

## Maintenance
- If a harness becomes part of a real recurring workflow, add it here and link the relevant bug/history doc.
- If a harness is retired, remove it here in the same change that retires the tool.
