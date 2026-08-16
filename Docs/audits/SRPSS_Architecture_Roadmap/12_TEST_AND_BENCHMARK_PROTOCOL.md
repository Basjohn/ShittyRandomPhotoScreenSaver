# 12 — Test and Benchmark Protocol

Last reconciled: 2026-08-16

## Objective

Prove improvements against current `main` under equivalent authored scenarios without
sacrificing visualizer behaviour, first-visible response, lifecycle, image/widget quality
or resource ownership.

Accepted current delivery baseline:
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`.

## Official Run Manifest

Record exact commit/dirty state, entry point, date/time/timezone, OS/Python/PySide,
CPU/RAM/GPU/driver, display resolution/refresh/DPR/route, power profile, audio
source/mode/preset, image/cache state, transitions/widgets, background load, diagnostic
flags, evidence location and parser version.

Canonical `main.py` is the ordinary performance authority. Diagnostic is for frozen
runtime/lifecycle attribution, not baseline performance.

## Standard Scenarios

- **S1 cold/warm static** — startup and idle baseline.
- **S2 each visualizer steady state** — same authored source across supported modes.
- **S3 visualizer temporal fidelity** — source→logical state→presentation state→paint receipt, generation/activation, deliberate missed presentation opportunities.
- **S4 image transitions** — fixed source/cache set and representative transition families.
- **S5 combined normal operation** — visualizer + widgets + transitions.
- **S6 recreation regression/stress** — Settings/Edit lifecycle/resource stress.
- **S7 image/resource churn** — sizes/aspects/transitions/cache pressure.
- **S8 quiescent runtime teardown** — tracked zero plus process/driver residuals.
- **S9–S12 host pressure** — CPU, disk/decode, GPU and mixed load with explicit timestamps.
- **S13 long soak** — post-warmup slopes/outlier timeline.
- **S14 topology/system lifecycle** — display route/DPR/resolution/sleep-wake where supported.
- **S15 texture identity comparison** — retained current→old contract.
- **S16 logging/persistence comparison** — same diagnostics/settings scenario across writer ownership.
- **S17 mixed-refresh presentation ownership** — 165 Hz + 60 Hz, visualizer on one display, fixed authored source and transitions; compare logical publication, overlay handoff, update request, paint and compositor delivery stages.
- **S18 visualizer-disabled residual dispatch control** — Media remains enabled; visualizer disabled from runtime creation; identify remaining queued-GUI-dispatch owner.

## Required Metrics

### Frame/UI

- frame interval p50/p90/p95/p99/max and >25/33/50/100 ms counts;
- adaptive wake lateness;
- queued GUI dispatch wait and dispatch-pending skip count;
- paint-pending wait and paint-pending skip count;
- request age and paint duration;
- event-loop lateness;
- first-visible latency.

### Visualizer

- logical source/event integrity;
- authored step/submission/publication timing;
- logical publication rate;
- overlay handoff/commit rate;
- auxiliary update-request rate;
- paint rate;
- source/state age at paint;
- generation/activation;
- protected edge/event identity/history;
- user visual result.

### CPU/tasking

Main/child/system CPU, task queue age/depth, callback backlog, worker occupancy and
measured substage durations where ownership is under investigation.

### GPU

Process GPU busy/sample age; sampled visualizer/compositor GPU query durations;
texture upload/allocation counts. Zero samples are never interpreted as zero cost.

### Memory/lifecycle

RSS/private commit, tracked CPU/GL/shared bytes, handles/threads, generation barriers and
strict teardown zero/plateau.

## P1 Fidelity Gate Before Presentation Correction

Before P2 is accepted:

- Bubble authored step/dt/source/event identity remains unchanged;
- one-in-flight Bubble simulation semantics remain unchanged;
- protected short-lived edges/events remain visible when intermediate render snapshots are skipped;
- Spectrum source/state evolution remains on its authoritative logical tick;
- supported-mode replay/state digests remain unchanged or explicitly approved;
- generation/activation stale state is rejected;
- presentation opportunity cannot feed back into logical admission.

## P2 Mixed-Refresh Production Gate

The production candidate is tested without the temporary A/B/C monkeypatch.

Required observations:

- logical publication rate remains equivalent to the approved pre-fix workload;
- auxiliary update-request rate is no longer mechanically one-for-one with logical publication when useful presentation opportunity is lower;
- 165 Hz compositor request acceptance/FPS materially approaches the accepted no-visualizer control;
- the 60 Hz sibling remains at/near its healthy baseline;
- queued dispatch and paint-pending distributions improve rather than merely shifting loss;
- no new divisor pattern (~half/third target rate) appears;
- no source/event/cadence reduction explains the gain;
- teardown/resource ownership remains healthy.

Do not encode one exact FPS as a unit-test oracle. Runtime acceptance compares equivalent
runs and stage distributions.

## P3 Handoff Attribution Gate

Instrument bounded substages without adding per-frame log spam:

```text
producer/state build
pure-data render preparation
Qt overlay commit
presentation request
paint
```

If moving preparation off GUI:

- worker output is immutable and Qt/GL-free;
- GUI commit validates generation/activation;
- logical replay/state is unchanged;
- PERF-off scheduling path is unchanged;
- no new worker wait/backpressure is introduced.

## P4 Residual Dispatch Gate

Run S18 after P2/P3. Correlate dispatch-pending bursts with concrete GUI callbacks using
existing low-rate/event-owner instrumentation.

Acceptance requires naming the owner/call path or explicitly classifying the residual as
external/irreducible with evidence. “Still about 156 FPS” is not an owner.

## Compatibility / Diagnostic Removal Gate

For temporary A/B/C scaffolding:

- remove helper module, CLI gate, hotkey and event-loop install hook together;
- ordinary startup remains unchanged;
- passive delivery-stage metrics remain available;
- no tests depend on the monkeypatch as production architecture.

## GPU Attribution Gate

Profiling remains non-blocking and sampled. `glFinish()` invalidates the candidate.
Shader cost may not be inferred from process GPU busy alone.

## Checkpoint Rule

Risky slice passes focused gate → clean checkpoint → continue. Stop only on failed
evidence, repository conflict or affected visual judgement.

## Release Comparison

Routine work compares current approved commits under equivalent authored workload.
Historical commits are only named negative controls/forensic references. Preserve failed
runs and report uncertainty.
