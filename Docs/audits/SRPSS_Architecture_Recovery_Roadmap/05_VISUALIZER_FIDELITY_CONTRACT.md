# 05 — Visualizer Fidelity Contract

Last reconciled: 2026-08-02

## Why this contract exists

Infrastructure changes have repeatedly passed logical or structural checks while visibly damaging:

- reactivity;
- Spectrum height/shape and smoothness;
- Bubble responsiveness and elasticity;
- motion continuity;
- beat alignment;
- first-visible response;
- mode personality.

Visualizer behaviour is therefore a protected product contract. The user is the final authority for perceived quality.

## Current approved authority

```text
approved visual behaviour:   ff93461685476bd0657aa88312fc2e35e9037880
code-equivalent restoration: 4bde89e8e39177dc4dd7b5e64b9ac99256ab9486
pre-lane reference:           6f188adadabb77b1a9d47a0fe1685c86ad39fb77
```

The original `00edb57` artifacts remain historical fidelity evidence, but they no longer automatically override the current user-approved runtime.

No later commit becomes the behavioural authority merely because tests pass. The exact candidate must receive installed user approval.

## Protected family and attribution rule

All supported modes are protected:

- Spectrum;
- Bubble;
- Sine Waves;
- Oscilloscope;
- Dev Curve.

Aggregate application or visualizer CPU, task, RAM, private-commit, or VRAM load is presumed to arise from shared/runtime ownership until direct evidence isolates a mode-specific owner.

Bubble is not a default optimization target. Do not change Bubble physics, cadence, authored-step scheduling, batching, or publication to solve general workload or memory concerns unless the user explicitly authorizes a Bubble-specific change after owner-level evidence.

Mode comparisons may diagnose shared versus mode-owned cost. They are not permission to degrade the more expensive-looking mode.

## Approved execution and cadence

Current production authority uses the ordinary general COMPUTE executor semantics restored at `4bde89e`.

Rejected scheduling/presentation shapes include:

- persistent shared-analysis lanes;
- persistent Bubble compute lanes;
- dedicated long-lived visualizer worker loops;
- cadence caps and source decimation;
- terminal batching that hides impulses until the end of a window;
- producer waits for paint;
- paint acknowledgement/backpressure;
- self-requested Spectrum repaint loops;
- paint-derived clocks;
- authoritative state mutation inside `paintGL()`.

A scheduler change is a fidelity change even when equations are unchanged.

## Protected qualities

Every supported mode must preserve, as applicable:

- response to quiet, medium, and strong input;
- low-energy movement where the approved runtime moves;
- attack speed;
- time to peak and peak magnitude;
- decay speed and curve;
- overshoot/rebound;
- settling time;
- inter-frame continuity;
- spatial/frequency distribution;
- timestamp/event ordering;
- first-visible response;
- behaviour under irregular presentation opportunities;
- behaviour after Settings/Edit and mode switches;
- mode-specific personality.

## Spectrum-specific protections

- Bars must not collapse into a visually flat band under ordinary music.
- Attack must remain tied to the beat.
- Decay must remain smooth without creating a second cadence.
- Frequency mapping, normalization, and bar authority must not silently change.
- Paint may consume current state but may not advance smoothing or request an independent continuation loop.
- A skipped paint may omit an intermediate visual snapshot; it may not alter logical response or hold/filter state on a separate clock.

The rejected `ebfec397` experiment is a mandatory negative control: roughly 977–1000 authoritative state publications versus 1417–1544 paints per ten seconds exposed a second cadence and the user reported significantly worse smoothness.

## Bubble-specific protections

- Elasticity, rebound, overshoot, and settling remain equal or better than the approved runtime.
- Beat/transient impulses remain visible and consume once.
- Position/velocity integration preserves approved elapsed-time semantics.
- Authored steps are not cadence-capped, terminal-batched, or moved to a persistent lane.
- A presentation stall does not create a burst of repeated fixed steps, frozen state followed by teleport, or paint-driven simulation.
- Stale tests or retired presets may not be used as justification to retune working Bubble behaviour.

## Stronger golden package

The existing Phase 2 logical replay package remains useful but was insufficient to detect real scheduling/publication hazards.

The current package must add:

### A. Immutable approval/environment manifest

Record:

- exact approved commit;
- explicit user approval statement and date;
- Windows, Python, PySide, GPU/driver;
- displays, refresh rates, DPR, and routes;
- audio source/capture configuration;
- entry point;
- exact mode/preset/settings;
- playing/paused and transition state;
- source fixture identity and playback offset.

Do not store copyrighted commercial audio. Store deterministic synthetic PCM and/or numerical feature sequences.

### B. Exact logical state

Capture mode-relevant state, source/event identity, generations, and activation boundaries with exact or documented tolerance assertions.

### C. Production-executor temporal state

Use the real ordinary executor shape and capture:

- source sequence/timestamp;
- submit/start/end/callback/commit;
- inter-publication interval;
- source age at logical tick;
- mode-owned submit/completion/consumption;
- first-visible publication/paint receipt;
- skipped/rejected/cancelled identity;
- runtime/engine/activation identity;
- GUI-stall/transition markers.

Assert ordering/integrity and bounded distributions, not exact wall-clock timestamps.

### D. Installed scenario record

Review separately by mode under:

- quiet, sustained, transient, dense/noisy input;
- attack/decay and rapid alternation;
- mode switches;
- pause/resume;
- transition overlap;
- Settings recreation;
- Edit recreation;
- 60 Hz and available high-refresh presentation;
- controlled GUI pressure.

Logs diagnose timing. They cannot overrule the user's visual verdict.

### E. Known-bad negative controls

The suite must reject:

- persistent-lane checkpoint `666624d` in scheduler/ownership temporal checks;
- Bubble terminal batching/cadence-gate fixtures in first-visible discrete-event checks;
- Spectrum paint-local smoothing `ebfec397` in single-cadence/presentation checks.

A suite that accepts the rejected shapes is incomplete.

## Quantitative fidelity metrics

Record where applicable:

- source-to-state and source-to-first-visible latency;
- publication intervals and source age;
- time to peak and peak magnitude;
- attack slope;
- decay/half-life;
- overshoot ratio;
- settling time;
- integrated response energy;
- cross-correlation lag;
- RMS/max state error;
- discontinuity/derivative spikes;
- dropped logical events versus skipped render snapshots;
- mode/activation reset correctness.

Numerical equality is not always appropriate. Tolerances must be mode-specific and tied to an approved reference.

## Presentation-separation test

Run identical logical input with presentation opportunities at representative fixed and irregular cadences plus deliberate stalls.

The logical state at the same source/simulation timestamp must remain equivalent within tolerance. Presentation must not create another simulation or smoothing authority.

## Coalescing contract

Coalescing may replace intermediate immutable **render snapshots** after all logical inputs/events have been integrated.

It may not:

- discard beat/transient events before simulation;
- change scheduler/cadence semantics;
- skip mode-owned authored work;
- let paint acknowledgement control production;
- merge activation/generation boundaries;
- create a paint-local smoothing stream.

## Manual review and approval

Any architecture phase touching shared source, scheduling, publication, presentation, renderer, first-frame, lifecycle, or resource representations requires installed review of affected modes.

Manual rejection overrides:

- averages;
- green logical tests;
- lower task counts;
- lower CPU/memory;
- higher FPS.

## Change declaration

Intentional behaviour change requires `templates/VISUALIZER_CHANGE_DECLARATION.md` and must identify:

- exact requested scope and user approval;
- modes affected;
- equations/parameters/data-flow/scheduler changes;
- before/after deterministic and temporal evidence;
- installed comparison;
- golden version policy;
- rollback commit.

Infrastructure work may not use this form to retroactively justify an accidental regression.

## Prohibited shortcuts

Do not:

- lower update/publication rate merely to reduce CPU or tasks;
- clamp amplitudes or increase damping to hide gaps;
- average more samples to conceal scheduling jitter;
- tie logical work to paint completion;
- replace elapsed-time semantics with frame-count assumptions;
- perform uncontrolled catch-up bursts;
- target Bubble because shared visualizer load is high;
- regenerate approved goldens automatically;
- claim feel from logs alone.

## Fidelity gate

A candidate fails if:

- the user reports worse feel;
- Spectrum is flatter, stepped, delayed, or less smooth;
- Bubble is less reactive/elastic or its impulses are less visible;
- another supported mode loses current behaviour;
- source-to-first-visible latency grows beyond the approved bound;
- logical state depends on paint cadence;
- Settings/Edit/mode switch reveals stale or poisoned state;
- a known-bad negative control passes;
- a resource optimization lowers perceivable quality.

Rollback first. Diagnose the architecture rather than compensating with visualizer parameters.