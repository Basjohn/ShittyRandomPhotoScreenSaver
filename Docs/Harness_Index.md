# Harness Index

Last updated: 2026-07-28

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

### Deterministic replay and protected goldens

Use the repository `.venv` on Windows:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe tools\visualizer_replay.py verify
.\.venv\Scripts\python.exe tools\visualizer_replay.py metrics
.\.venv\Scripts\python.exe tools\visualizer_replay.py artifacts
```

`verify` is the normal infrastructure gate and is read-only. `bootstrap-goldens` is only for an empty baseline directory. `update-goldens` requires an acknowledged intentional behaviour change and an approved visualizer change declaration. Review the Spectrum/Bubble artifacts under `Docs/phase_reports/artifacts/P02/` and the Phase 2 evidence in `Docs/phase_reports/P02_VISUALIZER_FIDELITY_LOCK.md`.

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

Run the deterministic ownership gate:

```powershell
.\.venv\Scripts\python.exe tools\phase3_lifecycle_harness.py --cycles 50 --output Docs\phase_reports\artifacts\P03\lifecycle_churn_report.json
.\.venv\Scripts\python.exe -m pytest tests\test_phase3_runtime_lifecycle.py -q
```

This exercises the production engine/display teardown seams with exact context/resource/timer/worker/callback accounting and stale decode publication. It must report 150 cycles, 150 rejected stale callbacks, zero stopped ownership, and no errors. It complements, rather than replaces, real Windows Qt context cleanup (`tests/test_gl_compositor_cleanup.py`), whose required shape includes two live per-display compositors with distinct program owners destroyed in sequence, runtime-shaped Settings/CUSTOM tests, Phase 4 driver/RSS/VRAM plateau work, and Phase 11 sleep/wake validation.

Authoritative Phase 3 evidence: `Docs/phase_reports/P03_GL_LIFECYCLE_AND_RECONFIGURATION.md`.

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

Run the deterministic Phase 4 owner/allocator gate:

```powershell
.\.venv\Scripts\python.exe tools\phase4_resource_harness.py --cycles 45 --output Docs\phase_reports\artifacts\P04\resource_plateau_report.json
.\.venv\Scripts\python.exe -m pytest tests\test_phase4_resource_containment.py tests\test_image_cache_accounting.py tests\test_image_prefetcher.py tests\test_image_pipeline.py tests\test_gl_texture_streaming.py tests\test_memory_pooling.py -q
```

The 45 rotations represent 30 virtual minutes at the shipped 40-second interval and exercise alternating resolutions/aspects, active transitions, exact-transform two-display sharing, pressure budgets, and full owner resets. It uses production cache/accounting/transition/texture/PBO seams with real QImage/QPixmap allocations and RSS, but a fake GL deletion ledger; it does not claim driver VRAM or replace the Phase 11 real-platform soak.

Authoritative Phase 4 evidence: `Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md` and `Docs/phase_reports/P04_RESOURCE_LIFETIME_MAP.md`.

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
