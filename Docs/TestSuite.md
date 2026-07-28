# Test Suite Guide

Last updated: 2026-07-26

Testing strategy, execution commands, and minimum quality gates.

Do not read a giant inventory of every test for every task. Use the routing below.

## 1. Testing Levels

### Level A — Pure/unit

Use for:

- settings normalization;
- registries;
- pure geometry;
- cache keys;
- transition math;
- visualizer numerical helpers;
- resource accounting metadata.

### Level B — Component/integration

Use for:

- manager ownership;
- image pipeline;
- widget setup/lifecycle;
- visualizer activation and renderer transport;
- compositor scene assembly;
- GL resource-store logic with mocked/context test seams.

### Level C — Runtime-shaped

Required for:

- Settings/Edit lifecycle;
- multi-display ownership;
- first-visible behaviour;
- transition completion;
- visualizer mode/preset switching;
- frame delivery;
- stale worker rejection;
- cache/resource churn.

### Level D — Real Windows/driver

Required for:

- `QOpenGLContext` affinity;
- packaged/frozen runtime;
- fullscreen/taskbar/flash;
- real multi-display DPR/refresh;
- VRAM behaviour;
- long-run frame pacing;
- focus/media-key/hardware ingress.

### Level E — Manual visual review

Required for:

- visualizer feel;
- transition smoothness;
- cursor halo;
- overlay placement;
- flicker/first-frame;
- image quality.

Tests do not replace Level E for visual/timing-sensitive work.

## 2. Standard Commands

Full bounded suite:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900
```

Collect:

```powershell
pytest --collect-only tests -q
```

Targeted:

```powershell
pytest path/to/test_file.py -q
```

Phase 1 passive-measurement projection:

```powershell
python tools/phase1_measurement_benchmark.py
```

Use it with parser/sampler tests and an enabled/disabled runtime-shaped comparison; inspect `resource_snapshots.csv` alongside the other parser outputs. The authoritative completed Phase 1 evidence is `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.

Slow Qt target in chunks:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 180 path/to/test_file.py
```

## 3. Task Routing

| Change | Minimum validation |
|---|---|
| Settings/defaults | focused settings/default tests + import/reset runtime |
| Widget descriptor/setup | descriptor tests + setup/lifecycle runtime |
| Service widget | provider/cache tests + lifecycle/refresh runtime |
| CUSTOM layout | contract/manager tests + real multi-display Edit |
| Transition registry | registry/factory/UI tests + runtime transition sweep |
| Visualizer mode-local | mode tests + focused reactivity harness + manual review |
| Shared visualizer seam | full reactivity harness + deterministic replay + runtime |
| Image pipeline/cache | pipeline/prefetch tests + RAM plateau |
| GL resource store | resource tests + real context recreation + VRAM plateau |
| Compositor/presentation | focused compositor tests + frame-tail runtime + manual |
| Settings/Edit GL lifecycle | repeated real lifecycle loops |
| Performance instrumentation | parser/sampler tests + enabled/disabled overhead |

## 4. Recovery Test Families

The exact test filenames may evolve; use repository search and `Docs/Harness_Index.md`.

Required logical families:

- visualizer deterministic reactivity;
- visualizer activation/mode isolation;
- compositor scene/update coalescing;
- no producer-to-paint wait;
- local transition finalization;
- GL thread/context assertions;
- Settings/Edit teardown order;
- stale worker result rejection;
- exact resource byte accounting;
- CPU/GPU cache bounds;
- context-generation invalidation;
- multi-display ownership;
- image upload lifetime;
- passive telemetry overhead.

Delete or rewrite tests whose only purpose is to protect rejected architecture, including:

- paint acknowledgement release;
- adaptive timer cadence;
- distributed terminal transaction;
- partial GL reinitialization;
- compatibility mega-layer fallback.

Do not keep a test green by preserving a failed mechanism.

## 5. Visualizer Fidelity Gate

Before changing shared audio/timing/render infrastructure:

1. run focused reactivity tests;
2. run deterministic timestamped input replay;
3. compare baseline state curves;
4. run irregular presentation cadence;
5. inspect Spectrum and Bubble manually.

Measure where applicable:

- input-to-response latency;
- peak amplitude;
- attack slope;
- decay/half-life;
- overshoot;
- settling time;
- RMS/max state error;
- discontinuities;
- presentation-cadence sensitivity.

Infrastructure work does not regenerate baseline expected output.

The Phase 2 lock is owned by:

- `tests/test_visualizer_analysis_acceptance.py`;
- `tests/test_visualizer_feature_frame.py`;
- `tests/test_visualizer_replay.py`;
- `tests/fixtures/visualizer_replay/v1/`;
- `tests/goldens/visualizer_replay/v1/`.

Run `\.venv\Scripts\python.exe tools\visualizer_replay.py verify` for infrastructure work. Expected output is exact canonical JSON after seven-decimal normalization. Golden mutation requires the explicit policy documented in `Docs/Harness_Index.md` and the Phase 2 report.

## 6. Frame-Pacing Gate

Report:

- average FPS;
- p50;
- p90;
- p95;
- p99;
- maximum;
- counts above 25/33/50/100 ms;
- paint duration;
- latest-scene age;
- GUI event-loop stalls.

Higher average FPS with worse p99/max is a failure.

## 7. Lifecycle Gate

Run at minimum:

- 50 Settings cycles;
- 50 Edit cycles;
- 50 mixed cycles;
- cycles during transitions;
- cycles during Spectrum and Bubble;
- cycles with image work in flight.

Require:

- zero context-affinity error;
- zero stale callback into old runtime;
- zero old-generation GL resource;
- stable timer/worker/resource count;
- memory returns to plateau.

Phase 3 owns these concrete automated bars:

- `tests/test_phase3_runtime_lifecycle.py` — 50/50/50 ownership churn, stale delayed publication, deferred GL warmup generation, strict context/deletion failure, visualizer overlay cleanup;
- `tests/test_engine_lifecycle.py` — display cleanup precedes Settings dialog construction;
- `tests/test_s_hotkey_workflow.py` — stop means full teardown and fresh rebuild, not hide/reuse;
- `tests/test_gl_compositor_cleanup.py` — idempotent no-resource cleanup plus real Windows Qt context resource deletion;
- `tests/test_startup_shader_warmup.py` — deferred warmup behavior;
- focused `TestDisplayManagerSync` rebuild cases;
- `tests/test_image_pipeline.py`, `tests/test_image_prefetcher.py`, and `tests/test_image_worker.py` — GUI-independent QImage compute payload and async regression coverage.

The 150-cycle JSON is `Docs/phase_reports/artifacts/P03/lifecycle_churn_report.json`; see `Docs/phase_reports/P03_GL_LIFECYCLE_AND_RECONFIGURATION.md` for results and unsupported headless scenarios.

## 8. RAM/VRAM Gate

Scenarios:

- warmup;
- 30-minute image cycling;
- large/small image churn;
- transition churn;
- lifecycle loops;
- two-hour soak.

Require stable plateau and tracked byte explanation.

Count-only cache tests are insufficient.

Phase 4 owns these concrete automated bars:

- `tests/test_phase4_resource_containment.py` — exact texture-byte eviction with active-pair pinning, independent PBO bounds, Particle/Burn cancellation, and cross-display QPixmap alias deduplication;
- `tests/test_image_cache_accounting.py` — exact QImage/QPixmap logical-byte eviction and detached metadata;
- `tests/test_image_prefetcher.py` — concurrency/count/future-byte backlog bounds and worker-safe QImage results;
- `tests/test_image_pipeline.py` — exact transform sharing plus non-sharing across differing target/DPR identity;
- `tests/test_gl_texture_streaming.py` and `tests/test_memory_pooling.py` — upload/PBO reuse and cleanup regressions;
- `tools/phase4_resource_harness.py` — 45-cycle owner/allocator plateau gate with real Qt image allocations and RSS.

The authoritative artifact is `Docs/phase_reports/artifacts/P04/resource_plateau_report.json`. Driver-reported VRAM, a normal 30-minute wall-clock run, and the two-hour soak remain Phase 11 platform gates.

## 9. CPU/Task Gate

Measure:

- process CPU;
- GUI event-loop delay;
- task submissions by category;
- queue depth;
- task tail duration;
- duplicate/stale publication;
- logging overhead.

Do not claim multithreading improvement from worker count alone.

## 10. Standard Runtime Scenarios

- cold start idle;
- Spectrum steady state;
- Bubble steady state;
- transitions without visualizer;
- combined normal operation;
- Settings loop;
- Edit loop;
- CPU background load;
- disk/decode load;
- GPU load;
- mixed hostile load;
- long soak;
- display topology/DPR/refresh change.

Record environment and commit for every official run.

## 11. Completion Rule

A change is not complete because the suite is green.

Completion requires the relevant:

- focused tests;
- runtime-shaped scenario;
- tail metrics;
- visual/manual review;
- lifecycle result;
- memory result;
- production-call-chain verification.

Known user-visible failure overrides adjacent green tests.
