# 12 — Test and Benchmark Protocol

Last reconciled: 2026-08-10

## Objective

Prove improvements against current `main` under equivalent authored scenarios without
sacrificing visualizer behaviour, first-visible response, lifecycle, image/widget
quality or resource ownership.

## Official Run Manifest

Record exact commit/dirty state, date/time/timezone, `main.py` entry point, OS/Python/
PySide, CPU/RAM/GPU/driver, display resolution/refresh/DPR/route, power profile, audio
source/mode/preset, image/cache state, transitions/widgets, background load, diagnostic
flags, evidence folder and parser version.

Diagnostic builds are attribution tools, not official performance baselines. Media
Center does not own a duplicate capture.

## Standard Scenarios

- **S1 cold/warm static** — startup and idle baseline.
- **S2 each visualizer steady state** — same authored source across Spectrum/Bubble/Sine/Oscilloscope/DevCurve.
- **S3 visualizer temporal fidelity** — source→state→publication→paint receipt, generation/activation, deliberate GUI stalls, known-bad controls.
- **S4 image transitions** — fixed source/cache set and representative transition families.
- **S5 combined normal operation** — visualizer + widgets + image transitions.
- **S6 recreation regression/stress** — Settings/Edit are solved; exercise them only as lifecycle/resource regression and release stress, not as active causal debugging.
- **S7 image/resource churn** — sizes/aspects/transitions/cache pressure.
- **S8 quiescent runtime teardown** — tracked zero plus process/driver residuals.
- **S9 CPU pressure** — mark pressure interval explicitly.
- **S10 disk/decode pressure** — controlled file/decode load.
- **S11 GPU pressure** — controlled external GPU load with driver/tool identity.
- **S12 mixed load** — explicit start/end timestamps for each pressure source.
- **S13 long soak** — post-warmup slopes/outlier timeline.
- **S14 topology/system lifecycle** — display route/DPR/resolution/sleep-wake where supported.
- **S15 texture identity A/B** — same image/transition sequence before/after current→old reuse correction.
- **S16 logging/persistence A/B** — same diagnostics/settings activity before/after queued writer ownership.

## Required Metrics

### Frame/UI

p50/p90/p95/p99/max intervals; counts >25/33/50/100 ms; request age; event-loop
lateness; callback queue age; paint duration; source/state age at paint; first-visible
latency.

### Visualizer

logical source/event integrity; authored step/submission/publication timing; source-to-
state and source-to-visible latency; state/set_state/update/paint rates; generation/
activation; user visual result.

### CPU/tasking

main/child/system CPU; submitted/started/completed/cancelled tasks by category; queue
age/depth; callback backlog; worker occupancy; GIL/native-release evidence where useful.

### Logging/persistence

caller enqueue cost; queue depth/high-water/drops; writer lag; per-family record counts;
flush duration; stale-write rejection; durable revision order.

### Memory

whole/main/child RSS, USS/private working set where available, private commit, mappings,
thread/handle counts, tracked CPU/GL/shared-memory bytes.

### GPU

- dedicated/shared GPU memory;
- process GPU-engine busy with sample timestamp/age;
- non-blocking per-transition GPU query duration + support/sample count;
- texture upload/allocation counts and durations;
- visualizer overlay update/paint rates versus display refresh.

Do not interpret “0 GPU samples” as zero GPU cost.

## Visualizer Presentation-Separation Test

Before Phase 7 acceptance, replay identical logical input while varying presentation
opportunities (fixed 60 Hz, available high-refresh, irregular opportunities, deliberate
missed paints). At the same logical/source timestamp, mode state must remain equivalent
within approved tolerance. Only intermediate immutable render snapshots may be skipped.

## Compatibility/Debris Removal Gate

For each removed façade/subsystem:

- repo-wide production call/import search;
- dynamic import/registry inspection;
- frozen-build/module discovery check where relevant;
- focused tests migrated to real owner rather than retained only to exercise dead code;
- no new fallback path;
- exact behaviour/timing goldens for visualizer-adjacent deletions.

## GPU Attribution Gate

Representative transition families must produce actual paint/GPU sample counts from the
shared compositor seam. Profiling-off overhead remains statistically negligible and
pixels/durations are unchanged. `glFinish()` invalidates the candidate.

## Checkpoint Rule

Risky slice passes focused gate → commit/checkpoint → continue. A new human stop is
required only for failed evidence, repository conflict or affected visual feel.

## Release Comparison

Routine work compares against the exact previous/current approved commit. Historical
commits are used only for a named negative-control/forensic question. Preserve failed
runs and report uncertainty.
