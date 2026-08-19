# Test Suite Guide

Last updated: 2026-08-19

Testing strategy and routing for current architecture.

Tests are necessary but not sufficient for visual/timing/lifecycle work.

## 1. Standard commands

Full bounded suite:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900
```

Do not use one monolithic long-lived `pytest -q` process for the full repository.

Targeted:

```powershell
pytest path\to\test_file.py -q --tb=short
```

Discover current tests by owner/defect rather than trusting an old filename inventory:

```powershell
rg -n "VisualizerLogicalRuntime|logical runtime|generation 0|Spectrum|Bubble|mode switch|pause|feedback|compositor" tests
```

## 2. Validation levels

### A — pure/unit

Use for:

- settings normalization;
- registries;
- pure geometry;
- cache keys;
- visualizer numerical helpers;
- generation identity helpers.

### B — component/integration

Use for:

- visualizer activation;
- logical mailbox handoff;
- GUI reveal/presentation handoff;
- renderer transport;
- widget lifecycle;
- compositor scene assembly.

### C — runtime-shaped

Required for:

- real worker-thread logical execution;
- scheduler actual cadence;
- mode switching;
- Pause/Play;
- Settings/Edit lifecycle;
- stale generation fencing;
- high-refresh/60 Hz delivery;
- feedback paint ownership.

### D — real Windows/driver

Required for:

- real QRhi/OpenGL context;
- fullscreen/multi-display;
- actual refresh/DPR;
- installed scheduler timing;
- frame pacing;
- VRAM/native resource behaviour.

### E — manual visual

Required for:

- BTF/Bubble feel;
- Spectrum idle visibility;
- Pause/Play hitch;
- transition smoothness;
- first-frame/flicker;
- image quality.

## 3. Current P2 gate router

Binding contract:

`Docs/P2_Behavioral_Gates.md`

Current required families include:

1. real paused-Spectrum visible pixels/height;
2. all-five-mode actual reveal;
3. scheduler cadence;
4. worker cannot mutate GUI/GL;
5. required handoff fail-loud;
6. one logical clock;
7A. Pause/Play identity;
7B. Pause/Play feedback does not full-card repaint every animation frame;
8. BTF;
9. valid generation-0 fencing;
10. known-bad validation;
11. high-refresh shared presentation;
12. 60 Hz visualizer presentation tails;
13. Pause/Play no-hitch perceptual end condition;
14. stale source/activation cannot gain visible authority;
15. lifecycle/recreation join/fencing.

A green suite that never renders a pixel cannot certify visible Spectrum output.

A generation test that begins at `1` cannot certify generation-zero fencing.

## 4. Visualizer deterministic fidelity

Before shared audio/timing/render changes:

```powershell
.\.venv\Scripts\python.exe tools\visualizer_replay.py verify
```

Protect existing replay/goldens.

Infrastructure work does not regenerate expected behaviour merely because architecture changed.

For Bubble timing/feel also apply:

`Docs/Guardrails/Bubble_Temporal_Fidelity.md`

BTF requires logical cadence/gap, source freshness, edge survival and state-to-screen evidence in
addition to deterministic behavioural goldens.

## 5. Logical scheduler gate

The old “callbacks happened eventually” test class is insufficient.

At approximately 11.11 ms authored interval over a meaningful scheduler-only window require:

```text
achieved cadence            >= 88 Hz
skipped deadlines           <= 2%
recurring >33 ms gaps       none
catch-up                    none
step failures               0
join                        succeeds
```

The gate must reject independently:

- coarse deadline clock;
- coarse timed wait reproducing the old ~64 Hz class.

Do not reintroduce timed `Event.wait()` as a scheduler fix without proving it does not recreate the
known platform failure.

## 6. Visualizer ownership gate

Production worker path must prove:

```text
logical_tick() on worker
    -> no QWidget/QPixmap/QPainter/GL mutation
    -> latest publication
    -> GUI present handoff
```

GUI-only methods should assert thread affinity in test/debug.

One-clock tests must prove no GUI recurring visualizer timer or AnimationManager logical listener is
active.

## 7. Spectrum visible-output gate

Preferred: real renderer/compositor GL output readback/image comparison.

If deterministic geometry is used instead, include real upload scale and shader/bar-height contract.

`max(bars) > 0` alone is invalid.

Test:

- normal + expanded card;
- representative DPRs;
- relevant segmented/single-piece paths;
- paused source identity absent;
- Play transfers authority only after fresh real source arrives.

## 8. Pause/Play gate

Split into:

### Identity

- same logical runtime;
- no cold card/GL recreation;
- no visualizer playback debounce;
- warm capture remains engine policy.

### Delivery

- no full MediaWidget repaint stream per feedback animation frame;
- logical gap tails remain healthy;
- state-to-paint/GUI dispatch remain healthy;
- installed visualizer does not visibly hitch.

Identity alone is not a product pass.

## 9. Frame-pacing gate

Report separately:

- physical display completed-paint FPS;
- p50/p90/p95/p99/max gaps;
- request acceptance;
- GUI dispatch/request age;
- state-to-paint;
- logical cadence;
- source age.

Higher average FPS with worse tails is a failure.

Use the 165 Hz display without a visualizer as a shared-presentation control.

Do not write per-transition fixes merely because one transition exposes the shared problem more.

## 10. Lifecycle gate

Run repeated:

- Settings;
- Edit;
- mixed lifecycle;
- visualizer active;
- transitions active;
- cleanup/shutdown.

Require:

- logical runtime joins;
- stale mailbox publication rejected;
- valid generation 0 preserved before first recreation;
- retired generation cannot reveal/publish;
- GL ownership/accounting returns to baseline;
- no old-generation callback survives destruction.

P5 will extend this to monitor topology/wake.

## 11. Performance observer discipline

`--perf` is ordinary CPU/frame/delivery evidence.

`--gpu-timing` is heavier sampled GPU timing.

`--viz` is visualizer diagnostics.

Do not compare observer profiles as if identical.

Current installed P2 evidence is recorded in:

`Docs/P2_Installed_Acceptance_Findings_2026-08-19.md`

## 12. Completion rule

A change is not complete because tests are green.

Completion requires the relevant combination of:

- focused tests;
- runtime-shaped scenario;
- tail metrics;
- real-driver validation where needed;
- manual visual review;
- lifecycle result;
- source/owner-chain verification.

Known user-visible failure overrides adjacent green tests.
