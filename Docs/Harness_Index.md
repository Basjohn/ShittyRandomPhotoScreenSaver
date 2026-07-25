# Harness Index

Last updated: 2026-07-26

Compact routing for recurring investigation commands.

Read only the relevant section. Harness success is evidence, not final sign-off for visual, timing, focus, GL, or multi-display issues.

## 1. Full and Targeted Tests

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900
pytest --collect-only tests -q
pytest path/to/test_file.py -q
```

Use `Docs/TestSuite.md` to select the required validation level.

## 2. Defaults and Settings

### Defaults editor

```powershell
python tools/default_settings_editor.py
```

Headless/focused:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python tools/default_settings_editor.py --smoke-test
python -m pytest `
  tests/test_default_settings_editor.py `
  tests/test_regenerate_sst_defaults.py `
  tests/test_settings_profile_separation.py `
  tests/test_settings_dialog_cache.py `
  tests/test_settings_defaults_parity.py `
  -q
```

### Settings flicker/window probes

```powershell
python tools/flicker_test.py
python tools/winprobe_observer.py
```

Use for constructor flicker, ghost windows, and transient HWND investigation.

## 3. Visualizer Fidelity

### Focused reactivity lock

Run before and after any shared visualizer/audio/timing/render/performance change.

Use the current repository test names matching:

- first-visible Spectrum;
- mode-switch parity;
- all-mode cycle;
- Sine transient response;
- Bubble reactivity/elasticity;
- Dev Curve active/idle and stale-result rejection;
- Oscilloscope display contract;
- activation/mode isolation.

Example repository search:

```powershell
rg -n "first_visible|reactivity|bubble|devcurve|oscilloscope|mode_switch|activation" tests
```

Then run the focused set:

```powershell
python -m pytest <focused visualizer tests> -q --tb=short
```

Required accompanying runtime work:

- deterministic timestamped input replay;
- Spectrum manual review;
- Bubble manual review;
- irregular paint cadence;
- injected GUI stall;
- live Settings/Edit restart.

Do not treat stale expected output as permission to change feel.

## 4. Compositor Recovery

Use when touching compositor, GL lifecycle, visualizer integration, image upload, transition completion, or resource sharing.

Find current focused tests:

```powershell
rg -n "compositor|paintGL|gl_|texture|framebuffer|transition|display_cleanup|image_upload" tests
```

The recovery test set must cover:

- one surface per display;
- GUI-local update coalescing;
- no producer paint wait;
- immutable scene state;
- local transition completion;
- GL owner/context assertions;
- full Settings/Edit recreation;
- resource byte accounting;
- context-generation invalidation;
- correct display routing;
- visualizer fidelity.

Tests that protect adaptive timer acknowledgement, terminal transactions, or partial reconstruction must be replaced rather than treated as release gates.

## 5. Performance and Log Analysis

Runtime flags remain CLI-first. Use only the families needed for the scenario:

```text
--perf
--usage
--viz
--geo
--set
--life
--cache
```

Evidence location:

```text
logs/evidence_chest/
```

Recovery archive parser:

```powershell
python tools/recovery_evidence_parser.py --archive logs/evidence_chest/logs00edb57.zip --output-dir logs/evidence_chest/derived/baseline_00edb57
python tools/recovery_evidence_parser.py --archive logs/evidence_chest/logs7376bb9.zip --output-dir logs/evidence_chest/derived/head_7376bb9
```

Phase 1 measurement benchmark:

```powershell
python tools/phase1_measurement_benchmark.py
```

Use this bounded paired-method projection when changing Phase 1 collectors. It is not a substitute for a Qt/GL runtime comparison; pair it with the relevant enabled/disabled runtime-shaped test and retain the resulting Phase 1 report.
For official comparisons, preserve:

- raw logs;
- commit/branch;
- environment;
- parser version;
- excluded intervals and reason;
- frame-tail summary;
- CPU/task summary;
- RAM/VRAM summary;
- lifecycle errors.

Required parsed outputs should include:

```text
frame_intervals
event_loop_stalls
task_rates
memory_usage
resource_snapshots
gpu_usage
lifecycle_events
visualizer_gaps
errors_and_warnings
```

Do not double-count duplicated records across verbose and sidecar logs.

## 6. Lifecycle Loop Harness

Create or use a harness that repeatedly:

- opens/applies/closes Settings;
- enters/exits Edit;
- alternates Settings/Edit;
- runs during transition;
- runs during Spectrum;
- runs during Bubble;
- runs with image work in flight.

Minimum official gate:

```text
50 Settings
50 Edit
50 mixed
```

Capture per cycle:

- runtime/context generation;
- live GL bytes/resources;
- worker/timer count;
- stale result count;
- RSS/VRAM;
- warnings/errors.

## 7. RAM/VRAM Plateau Harness

Required scenarios:

- normal warmup;
- 30-minute image cycling;
- large/small/aspect-ratio churn;
- transition churn;
- Settings/Edit loops;
- two-hour soak.

Output:

- tracked CPU cache bytes;
- tracked GL bytes by type;
- RSS/private commit;
- driver VRAM;
- resource create/delete events;
- plateau slope after warmup.

Monotonic growth fails the run.

## 8. Background-Load Matrix

Run combined normal operation under controlled:

- CPU load;
- disk/decode load;
- GPU load;
- mixed load.

Compare:

- visualizer feel;
- cursor halo;
- p99/max;
- task queue;
- event-loop stalls;
- CPU;
- GPU;
- RAM/VRAM.

External saturation is resilience evidence, not the ordinary baseline.

## 9. Media-Key and Focus Harnesses

Existing tools:

```powershell
python tools/media_key_matrix_harness.py --launch mc --profile-mode mirrored --focus-policy realistic --scenarios focused_idle,focused_clicked
python tools/media_key_reality_harness.py --profile-mode mirrored --scenario focus_transition --manual-focus-seconds 8 --observe-seconds 12
python tools/hardware_ingress_validator.py
```

Use physical ingress validation when synthetic results disagree with hardware.

## 10. Secure-Desktop/Helper Harness

Existing Reddit helper smoke test:

```powershell
python tools/reddit_helper_task_harness.py --action smoke-test --task-name SRPSS_TaskHarness_Test
```

## 11. Provider/Widget Harnesses

Use focused provider documents and repository search.

General rule:

- tests use fixtures/injected openers;
- no live credentials;
- no real account data in repository artifacts;
- provider/cache tests do not replace runtime widget lifecycle tests.

## 12. Harness Maintenance

Add an entry only for a recurring investigation with a stable command or procedure.

Do not copy every test description into this file.

When a harness changes:

- update its command;
- update the owning focused document;
- remove obsolete architecture tests;
- preserve historical evidence separately.
