# Harness Index

Last updated: 2026-08-11

Compact routing for recurring investigation commands.

Read only the relevant section. Harness success is evidence, not final sign-off for visual, timing, focus, GL, or multi-display issues.

## 1. Full and Targeted Tests

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900
pytest --collect-only tests -q
pytest path/to/test_file.py -q
```

Do not run the complete repository as one `pytest -q` process. On 2026-08-08 that
monolithic invocation remained CPU-active rather than deadlocked, but accumulated
about 2.54 GiB working set, 3.28 GiB private memory, 133 threads, and no incremental
result visibility before it was stopped. Full-suite validation must use
`tests/run_chunked.py` so each Qt/GL singleton graph and worker population is
released between bounded subprocesses and a slow chunk is identifiable.

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

Replay schema v1 predates the optional Spectrum presentation filter. Its model builder
therefore explicitly disables that candidate and excludes only the two later dotted
presentation fields from the frozen authored-preset hash. Do not enable the candidate
or rewrite v1 outputs; its expected behaviour belongs in the temporal package below.

### Affected-path temporal hazard lights

Run the Bubble/Spectrum temporal checks without regenerating their versioned artifacts:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest tests\test_bubble_cadence.py tests\test_spectrum_presentation_smoothing.py -q
```

The Bubble trace uses the ordinary production-shaped `ThreadManager` COMPUTE executor
and requires a discrete event exactly once on the first lane-free visible publication.
The Spectrum trace records authoritative source and presentation publications on the
existing UI visualizer tick and rejects independent timers, paint-local mutation, and
overlay self-updates. The manifest under `tests/goldens/visualizer_temporal/v1/` is
hand-reviewed evidence: do not auto-regenerate it. These checks do not replace the
installed source/paint-receipt/operator gate.

## 4. Compositor Architecture Regression

Use when touching compositor, GL lifecycle, visualizer integration, image upload, transition completion, or resource sharing.

Find current focused tests:

```powershell
rg -n "compositor|paintGL|gl_|texture|framebuffer|transition|display_cleanup|image_upload" tests
```

The compositor/architecture regression set must cover:

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

Evidence location and format:

```text
logs/evidence_chest/<run_name>/
```

Parse the current live root directly when the active sidecars are still in place:

```powershell
python tools/recovery_evidence_parser.py --source logs --output-dir logs/_analysis_live
```

Parser 1.11 treats a directory named `logs` as the live sidecar root: it reads only
immediate `.log` files and their rotations, ignoring `evidence_chest`, derived-analysis,
and other descendant trees. Each selected file is read once; its recorded size and the
source hash cover the exact byte prefix consumed even if a live sidecar continues growing
during analysis.

Phase 5 output also promotes each 10-second
`[PERF][SPOTIFY_VIS][OVERLAY]` window into structured per-mode state-publication,
update-request, `paintGL`, CPU paint-duration, and state-to-paint rates. Parser 1.11
separately parses `[PERF][SPOTIFY_VIS][OVERLAY_GPU]` windows emitted by the
non-blocking owner-context timer-query ring. A GPU duration is measured only when
`gpu_supported=True` and `gpu_samples` is non-zero; unsupported, pending, dropped,
and discarded query counts remain explicit, so a missing or zero sample set is never
interpreted as zero GPU work. Correlate those records with the display refresh rate;
they measure Qt FBO presentation pressure, not physical scanout/present count, and do
not authorize a logical Bubble/Spectrum cadence change.

New captures are plain disposable subfolders. Parse an explicitly selected capture
directly; do not create a ZIP merely for analysis:

```powershell
python tools/recovery_evidence_parser.py --source logs/evidence_chest/phase4plus_a2f7bd89 --output-dir logs/evidence_chest/derived/phase4plus_a2f7bd89
```

The parser filename is historical and remains stable; its name does not make any historical branch or candidate an implementation authority.

Explicit evidence-run folders retain recursive discovery for copied/extracted layouts;
select one run rather than the whole `evidence_chest` parent. Parser 1.11 joins copied
sidecar rotations oldest-first and then reads the active
`.log`, so a session that crosses `screensaver_verbose.log.1` or
`screensaver_lifecycle.log.1` remains continuous. Copy only the rotations needed
to cover the authoritative live session. The generated `summary.json` describes
the complete copied time range; when system load or multiple runs share the
folder, record the accepted timestamp interval in a `MANIFEST.md` and calculate
that interval's frame, event-loop, visualizer, and usage result separately.

For UI-delivery attribution, correlate `[PERF] [FRAME_GAP_OWNER]` with the new
`[PERF] [IMAGE_UI_DELAY]` and `[PERF] [IMAGE_UI_SEGMENT]` records. The former
identifies delayed-work reason/display/due lateness, runtime-identity guard cost,
actual payload duration, monotonic interval bounds, total age, and outcome. The
latter separates `QImage→QPixmap` conversion from display
setter/transition-start cost. Do not change display staggering from a
last-callback correlation alone.

`--archive` remains a legacy ZIP alias for frozen historical comparisons only.

Historical/frozen Settings/Edit owner-attribution regression:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest tests/test_ownership_trace.py tests/test_runtime_destruction.py -q
```

These retained-wrapper cases preserve the solved R-59 ownership oracle. Do not
rebuild the Diagnostic product for routine work or to re-prove the solved
Settings/Edit issue. Use the frozen Diagnostic product and its bounded
`[PYTHON_OWNER_REFS]` attribution only if a new failure reproduces exclusively
in a frozen build and ordinary source/runtime-shaped evidence cannot name the
retaining edge.

Phase 1 measurement benchmark:

```powershell
python tools/phase1_measurement_benchmark.py
```

Use this bounded paired-method projection when changing Phase 1 collectors. It is not a substitute for a Qt/GL runtime comparison; pair it with the relevant enabled/disabled runtime-shaped test and retain the resulting Phase 1 report.

Phase 5 scheduler-accounting and passive frame-owner projections:

```powershell
python tools/phase5_thread_manager_benchmark.py --duration-seconds 5 --tasks-per-second 165
python tools/phase5_frame_owner_benchmark.py --invocations 50000 --repeats 7
```

The first runs the production general COMPUTE executor and reports process CPU plus
queued/delivered UI callbacks. The second measures the exact perf-gated passive
frame-owner snapshot and projects it at the 165 Hz + 60 Hz dual-display ceiling.
Both are headless attribution aids; neither replaces ordinary `main.py` or
`main_mc.py` visual, delivery, RSS/private-commit, or driver-VRAM evidence.
Frozen executables are required only for failures or packaging contracts that
cannot be exercised faithfully from those live entry points.
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
.\.venv\Scripts\python.exe tools\phase4_image_worker_shm_harness.py --cycles 50 --width 3840 --height 2160
.\.venv\Scripts\python.exe -m pytest tests\test_phase4_resource_containment.py tests\test_image_cache_accounting.py tests\test_image_prefetcher.py tests\test_image_pipeline.py tests\test_image_worker.py tests\test_image_worker_shared_memory.py tests\test_process_supervisor.py tests\test_usage_sampler.py tests\test_gl_texture_streaming.py tests\test_memory_pooling.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_media_command_ingress.py tests\test_media_artwork_layout.py tests\test_media_display_update.py tests\test_media_transition_deferral.py tests\test_startup_shader_warmup.py tests\test_fade_coordinator.py tests\test_widget_manager.py tests\test_transition_distribution.py tests\test_engine_lifecycle.py -q
```

The 45 rotations represent 30 virtual minutes at the shipped 40-second interval and exercise alternating resolutions/aspects, active transitions, exact-transform two-display sharing, pressure budgets, and full owner resets. It uses production cache/accounting/transition/texture seams plus the production PBO acquire/release/trim lifecycle with real QImage/QPixmap allocations and RSS, but fake GL name generation/deletion. The terminal bar requires exactly the current texture, reuse of that retained texture ID as the next transition source, one sufficient idle PBO under the byte cap, later reuse of the same retained PBO ID, larger-size replacement through pool trimming, and zero texture/PBO bytes after each strict owner reset. The focused Phase 4 regression additionally drives the real `ImagePresenter` DPR handoff and requires the retained key/texture ID to survive as next old with one cache hit and only the following destination upload.

The focused regressions also cover source-generation cancellation of late prefetch callbacks, exact previous-image sharing without cross-DPR cache collapse, pre-diff artwork-generation promotion, retention of the sole decoded startup image across a same-key in-flight generation, card-before-artwork cold-start reveal ownership with transition-idle resumption, accepted/rejected manual rotation ownership, and timer-expiry coalescing before acquisition.

The shared-memory harness uses the real spawned ImageWorker and production parent QImage consumption for 50 sequential 4K transfers plus an in-flight worker stop. It requires labelled worker RSS plateau, zero terminal shared-memory bytes, zero unlink failures, and no captured orphan name. `fresh_20260729_2140` validates that worker slice live, but neither deterministic harness claims driver VRAM or whole-process containment.

The next installed comparator must synchronize main/worker/total RSS, private commit, CPU cache/display/GL accounting, and driver VRAM. Force artwork/title changes with media Next/Previous during transitions and manual slideshow Next/Previous near the old timer deadline. Require one accepted process-wide media ingress plus any immediate duplicates marked suppressed; `[PERF][MEDIA_FEEDBACK] mode=static` with two paint requests and no feedback-animation label; bounded artwork lifecycle events; no stale idle-flush discard; `[PERF][MEDIA_PRESENTATION] ... layout_mutations=0` for an unchanged fixed-card footprint; no 30–38-paint media-feedback burst; and slideshow coalescing before queue/cache/worker/prescale acquisition. On a cold start with artwork, require one decode, no `stale_idle_flush_generation` while the current query is in flight, one apply with `pixmap_ready=True`, and the media-card fade to complete before exactly one `[PERF][MEDIA_ARTWORK] event=fade_started reason=widget_reveal_complete`; if a transition overlaps reveal completion, require the one start at `reason=all_displays_idle`. Also prove normal idle media feedback still reports `mode=animated`. Deliberately exercise Spectrum, Bubble loud passages, and a mode switch because the long memory baseline did not activate Spectrum.

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

## 12. Build Foundry

Use the single standard-library GUI owner for both build environments:

```powershell
python tools/build_runner.py
python tools/build_runner.py --mode normal
python tools/build_runner.py --mode venv
```

The selected environment changes the standard, Media Center, and helper
PowerShell workers. Normal mode uses `scripts/*.ps1`; repo-venv mode uses
`scripts/venv/*.ps1`. The opt-in Diagnostic Runtime always uses its dedicated
repo-venv worker for reproducibility. All modes compile the canonical installer
definitions in `scripts/`. The runner reports Reddit
helper input drift inline, persists the auto-close preference under local app
data, exposes per-job log/output links, and shows stage progress while each
long-running compiler owns the pipeline.

Selecting an installer without its product build intentionally packages the
existing canonical release payload. Keep the corresponding product steps
selected when fresh binaries are required.

Build workers stage compiler products under the ignored
`build/<environment>/<product>/` tree.
Successful products publish into one release tree:

```text
release/
  screensaver/
  media_center/
  diagnostic/
  reddit_helper/
  installers/
```

`Diagnostic Runtime` and `Diagnostic Installer` are deliberately unselected by
default. Together they publish/install `SRPSS_Diagnostic.exe` without changing
the standard screensaver registration or Media Center installation. Runtime
logs live beside the executable under `logs`, falling back to
`%LOCALAPPDATA%\SRPSS\Diagnostic\logs` and then `%TEMP%`; use the diagnostic
product for frozen-crash attribution, never as a performance baseline or as a
Media Center capture substitute. The diagnostic product is interactive and
does not provision, queue to, start, or keep alive the standard SCR Reddit
helper.

Shader validation derives its expected files from the current
`widgets/spotify_visualizer/shaders/*.frag` sources. Onefile builds validate the
embedded Nuitka data declarations; onedir builds validate the published shader
files. Never restore retired names such as `blob.frag` to satisfy a stale
hard-coded validator.

Validate routing and helper-fingerprint status without opening the GUI or
starting a build:

```powershell
python tools/build_runner.py --smoke-test --mode normal
python tools/build_runner.py --smoke-test --mode venv
```

Do not run the test suite concurrently with a Nuitka/PyInstaller build from the
same checkout.

## 13. Harness Maintenance

Add an entry only for a recurring investigation with a stable command or procedure.

Do not copy every test description into this file.

When a harness changes:

- update its command;
- update the owning focused document;
- remove obsolete architecture tests;
- preserve historical evidence separately.
