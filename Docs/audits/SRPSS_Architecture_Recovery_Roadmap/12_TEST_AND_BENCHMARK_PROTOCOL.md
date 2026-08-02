# 12 — Test and Benchmark Protocol

Last reconciled: 2026-08-02

## Objective

Prove that a candidate improves the current approved runtime without sacrificing visualizer feel, first-visible response, frame pacing, lifecycle safety, image/widget quality, or resource ownership.

Historical comparisons against `00edb57` and `7376bb9` remain useful when answering a specific regression question. Routine Phase 5 acceptance compares against the exact current approved/previous commit under an identical authored scenario.

## Official environment manifest

Record for every official run:

- exact commit and working branch (`main` unless explicitly changed);
- clean/dirty state;
- date/time and run duration;
- normal or Media Center entry point;
- Windows, Python, PySide6;
- CPU, installed RAM, GPU/driver;
- display count, resolution, refresh, DPR, primary/route;
- power profile;
- audio capture device/source and playback authority;
- exact visualizer mode/preset/settings;
- SRPSS widget/transition/settings profile;
- image source set and source-size distribution;
- cache cold/warm/pressure state;
- background applications/load;
- logging/diagnostic flags;
- evidence folder/archive identity and parser version.

For visual approval, record the exact user-approved commit and statement separately by mode.

## Scenario equivalence

A comparison is invalid when it changes material conditions such as:

- cold versus warm runtime;
- Spectrum versus Bubble without declaring mode as a variable;
- different tracks/input segments;
- different image/cache state;
- different transition families;
- different display route/refresh/DPR;
- different logging verbosity;
- different run duration or sample age.

Mode comparison may diagnose owner differences but cannot by itself authorize mode-specific degradation.

# Standard scenarios

## S1 — Cold start and warm static

- record cold startup;
- settle for a fixed period;
- record warm static state;
- no image transitions during the measurement window unless startup requires one.

Purpose: startup cost, warm baseline, idle work, one-time allocation.

## S2 — Supported visualizer steady state

Run each supported mode separately with the same repeatable source fixture/segment and no image transition during the measurement window:

- Spectrum;
- Bubble;
- Sine Waves;
- Oscilloscope;
- Dev Curve.

Purpose: shared versus mode-owned CPU/task/allocation differences and fidelity. Do not infer Bubble is the optimization target merely because its logical state is larger.

## S3 — Visualizer temporal fidelity

For approved fixtures and the real ordinary executor path:

- capture source sequence/timestamp;
- submit/start/end/callback/commit;
- publication intervals/source age;
- mode-owned authored work;
- first-visible publication/paint;
- generation/activation identity;
- irregular GUI opportunity and controlled stall markers.

Run known-bad controls `666624d`, terminal batching fixtures, and `ebfec397`; they must fail the appropriate checks.

## S4 — Image transitions

- visualizer inactive only when isolation is required;
- regular image changes;
- representative transition set;
- fixed source/cache state;
- sufficient duration for warm plateau and size churn.

## S5 — Combined normal operation

- current user-approved visualizer behaviour;
- image cycling/transitions;
- ordinary widgets/overlays;
- fixed duration and source inputs.

## S6 — Settings lifecycle

For Phase 5 focused validation:

- one installed cycle after R-56 repair;
- then at least five alternating lifecycle cycles;
- larger 50-cycle release matrix later.

Include no-op and changed settings, current visualizer/transition/image activity, and the real modal `WA_DeleteOnClose` path.

## S7 — CUSTOM/Edit lifecycle

- dual-display Save-and-Continue through the real relay shape;
- graph save/replay and shell retirement;
- queued later-turn engine admission;
- focused one-cycle installed proof;
- alternating Phase 5 matrix;
- larger release matrix later.

## S8 — Image/resource churn

- alternate large/small images and aspect ratios;
- vary transition families;
- exercise prefetch queue and cache pressure;
- verify old size/representation release.

## S9 — Quiescent teardown

With display runtime absent:

- tracked QObject/Python/resource/task/subscription/GL ownership reaches zero;
- record main/child RSS, private working set, private commit, VMS/mapped regions, handles, threads;
- record dedicated/shared GPU memory with sample age.

Purpose: distinguish active display resources from process/runtime/allocator/driver residuals.

## S10 — Background CPU load

Controlled CPU pressure while preserving system responsiveness.

## S11 — Background disk/decode load

Controlled file activity and decode contention.

## S12 — Background GPU load

Controlled GPU pressure with driver/tool state recorded.

## S13 — Mixed hostile load

Combined CPU/disk/GPU plus ordinary operation.

## S14 — Long soak

- at least two hours for release validation;
- image cycling;
- representative supported visualizer mode(s) with fixed authored source periods;
- periodic lifecycle operations only when safely automated;
- post-warmup slopes and outlier timeline.

## S15 — Display topology/system lifecycle

Where supported:

- primary route changes;
- display disconnect/reconnect;
- resolution/DPR changes;
- sleep/wake;
- selected-display and all-display routes.

# Metrics

## Frame and delivery

- average FPS for context only;
- p50/p90/p95/p99/max intervals;
- counts over 25/33/50/100 ms;
- event-loop lateness;
- paint duration;
- accepted-state-to-update and update-to-paint;
- latest scene/source age at paint;
- source-to-first-visible latency;
- update request/paint/publication rates;
- skipped immutable render snapshots versus lost logical events.

## Visualizer

- logical source/event sequence integrity;
- source-to-state and source-to-first-visible latency;
- publication interval/source age;
- attack/peak/decay/overshoot/settling where applicable;
- mode activation/generation reset correctness;
- deterministic golden result;
- known-bad negative-control result;
- manual user review result separately by affected mode.

## CPU/tasking

- whole-app and main/child CPU;
- event-loop/main-thread delay;
- task submitted/started/completed/cancelled/failed by category;
- queue age/depth and callback backlog;
- longest callbacks/tasks;
- unchanged/hidden work;
- sampler overhead.

## System memory

Report separately:

- whole-app RSS/working set;
- main and each child RSS;
- private working set where available;
- whole-app/main/child private commit/private bytes;
- VMS/reserved/mapped regions where available;
- Python/Qt/native allocation attribution where measured;
- thread count/stack estimate;
- handles/GDI/USER objects.

Do not add RSS and private commit together.

## Application resources

- CPU cache exact logical/tracked bytes and entries by kind;
- QImage/QPixmap/display representation bytes;
- pending/inflight future bytes;
- shared-memory mappings/transfers;
- GL textures/FBOs/PBOs/programs/buffers by owner/generation;
- tracked/untracked gap.

## GPU memory

- dedicated VRAM;
- shared GPU memory;
- sample timestamp/age;
- tracked application GL bytes;
- teardown idle-driver baseline;
- process GPU-engine busy where available.

## Lifecycle

- runtime/context/engine/activation identities;
- barrier arm/zero/completion times;
- watched QObject and Python roots;
- tasks/timers/animations/subscriptions/resources;
- stale/duplicate admission rejection;
- invalid-wrapper/context warnings;
- replacement count and authoritative reveal identity.

# Current pass gates

## Visualizer

- current approved goldens unchanged unless explicitly approved;
- stronger production-executor temporal package passes;
- known-bad controls fail;
- no user-reported loss of feel;
- no second cadence or paint-local authority;
- all supported modes pass shared-source validation.

## Frame pacing

- p95/p99/max and first-visible response are equal or better in the named scenario;
- no repeated unexplained 100+ ms gaps;
- average FPS cannot compensate for worse tails/feel.

## Lifecycle

Focused Phase 5:

- R-56 no invalid dialog-wrapper touch;
- R-53 teardown starts after Edit owner frames return;
- zero retiring ownership before exactly one replacement;
- graph layout/replay and fresh reveal correct.

Release:

- 50 Settings, 50 Edit, and 50 mixed hostile cycles or a later explicitly approved equivalent matrix;
- zero cross-thread/context/invalid-wrapper/stale-publication failures;
- no old-generation owner/resource survives.

## Memory/resource

For the current dual-1440p environment:

- no monotonic post-warmup growth;
- preferred whole-app warm RSS under 600 MiB; investigate at 750 MiB; unresolved failure above 900 MiB;
- preferred dedicated VRAM under 300 MiB; investigate at 400 MiB; unresolved failure above 500 MiB;
- no unexplained multi-GiB private commit;
- tracked/untracked gaps named by owner/category;
- no fidelity/quality/cadence reduction used to meet targets.

## CPU/tasking

- materially lower measured work in the named owner/scenario;
- no arbitrary visualizer cadence/task-rate cut;
- no persistent lane/dedicated visualizer loop;
- no task per paint/bar/bubble/group;
- p99/first-visible/resource results do not worsen.

# Comparison method

Use identical authored workloads and at least three comparable runs for important release metrics when practical.

Compare against:

1. the exact previous/current approved commit for ordinary work;
2. `00edb57` or `7376bb9` only when historical comparison answers a specific question;
3. known-bad commits/fixtures as negative controls.

Do not omit failed runs or change metrics/logging between candidates.

# Artifact retention

Use repository-relative paths with canonical capitalization:

```text
logs/evidence_chest/<date_commit_time>/
logs/benchmarks/<commit>/<scenario>/
Docs/phase_reports/
Docs/benchmark_reports/
```

Store raw logs, parser output, manifest, commands, summary, failed-run notes, and screenshot/video references. Do not store copyrighted audio or sensitive titles/URLs/credentials.

# Regression rule

Reject a candidate that improves its target but causes:

- user-observed visualizer loss;
- known-bad control acceptance;
- worse p99/max/first-visible response;
- invalid wrapper/context/lifecycle owner;
- memory growth or excessive unexplained footprint;
- task/callback increase without benefit;
- display/graph/reveal regression;
- hidden fallback or new scheduler authority.

# Benchmark integrity

- fixed warmup and cache state;
- exact scenario and source segment;
- same diagnostic configuration;
- separate app versus system load;
- sample timestamps/ages for asynchronous GPU data;
- report uncertainty and confidence;
- no selective interval removal without documented reason;
- user visual result reported honestly.