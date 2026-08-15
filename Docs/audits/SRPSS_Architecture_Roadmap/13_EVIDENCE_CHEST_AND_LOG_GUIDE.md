# 13 — Evidence Chest and Log Guide

Last reconciled: 2026-08-15

## Purpose

The evidence chest preserves raw runtime evidence, parser output, manifests and rejected
candidate comparisons. Current-main evidence is primary; older archives are historical.

## Evidence Authority

`Current_Plan.md` owns the exact active evidence pointer and next comparison gate.

Do not keep a rapidly changing "current canonical run" duplicated in this guide.

The historical mixed-load causal checkpoint remains:

```text
logs/evidence_chest/08_09_ca830d7_14_59/
```

Later 08-13 evidence closed several formerly active hypotheses, including retained
texture identity, the expensive steady full-pixmap base draw, ordinary texture-upload
copy overhead and unsampled/heavy GPU-query ambiguity.

## Current Strong Conclusions

Do not rediscover these from raw logs unless a new hypothesis needs the source lines:

- repeated delivery stalls are dominated by request age rather than paint duration;
- retained-current → next-old texture identity is repaired and steady old reuse is healthy;
- steady compositor presentation can reuse the exact retained destination texture and avoid the old expensive full-pixmap QPainter base draw;
- ordinary RGB32/ARGB32 texture upload no longer needs the previous redundant conversion plus Python `bytes` copy;
- Bubble worker/overlay GPU and ordinary transition draw duration are too small to explain the largest 40–130+ ms stalls;
- heavy owner-context timer queries are isolated behind sampled `--gpu-timing`;
- ordinary `--perf` does not issue GL query-driver calls, and the ordinary control did not recover the remaining delivery regression;
- the next delivery question is where time is lost between adaptive wake, queued GUI dispatch and paint receipt;
- captured lifecycle/resource teardown remains bounded in the validated paths;
- Settings/Edit compiled ownership and clock-shadow incidents are historical regression contracts, not active causal investigations.

## Sidecar Contract

Expected families include:

- main;
- verbose;
- perf/widget perf;
- usage;
- cache;
- geometry;
- lifecycle;
- settings;
- visualizer/volume;
- Steam.

**Main log contract:** high-level runtime narrative plus every WARNING/ERROR/CRITICAL.

When a dedicated family is active, routine family INFO/DEBUG belongs in its sidecar and
should not duplicate into main.

The main log may use human-readable aligned columns and framed severity cards. Sidecars
remain compact canonical machine evidence.

The old GL-cache routing defect is closed: routine `[GL CACHE]` INFO follows the cache
sidecar and WARNING+ remains main-visible.

## Logging Execution Evidence

Normal logging uses one process-owned bounded queue/writer.

For each dequeued record:

1. persistent main/relevant sidecar handlers are serviced;
2. optional human console formatting/output follows.

The final `[LOG_QUEUE]` record should expose at least:

- enqueued/dequeued;
- drop counters;
- high-water/capacity;
- caller enqueue average/max;
- writer queue-lag average/max;
- file-commit lag average/max;
- console emit average/max;
- emergency/reentry fallbacks;
- writer/snapshot errors;
- flush duration.

Use those fields to distinguish queue availability from file-service cost and human
terminal cost. Do not infer that a pretty console is expensive merely because queue lag
exists.

WARNING+ saturation retains the serialized direct-main emergency path. Diagnostic fatal
and native crash breadcrumbs remain direct and independent of the queue.

## Rotation and Long Capture Rules

Runtime rotations use 2 MiB chunks.

Current retention is intentionally asymmetric:

- ordinary main: about 16 MiB;
- ordinary high-volume sidecars: commonly about 12 MiB;
- ordinary verbose: about 8 MiB;
- Diagnostic main: about 24 MiB;
- Diagnostic usage: about 24 MiB;
- Diagnostic lifecycle: about 24 MiB.

The asymmetry is deliberate. Main provides chronology/WARNING+ correlation; sidecars
provide the domain detail. Diagnostic receives longer main/usage/lifecycle history because
it is used for long frozen-runtime/lifecycle reconstruction.

If a capture exceeds a family's rolling window, preserve/copy the overlapping rotations
before continuing. Prefer more backups for the specific affected family over universally
larger chunks.

## Evidence Parser Contract

The canonical evidence parser is read-only.

It must:

- read active logs and copied evidence folders without modifying them;
- join rotations oldest-first then active file;
- preserve exact selected-source byte/time-range semantics;
- parse canonical sidecars by family to avoid duplicate counting;
- retain old canonical main-log compatibility;
- normalize framed main-log WARNING/ERROR/CRITICAL cards back into logical records;
- ignore presentation-only borders/rules in unknown-line output;
- never treat missing GPU samples as zero work;
- never schedule, repaint, fence, sleep or otherwise alter the runtime being measured.

Focused parser tests are mandatory after presentation/parser changes.

## Correlation Workflow

1. Read `screensaver.log` for runtime sequence and all WARNING+/errors.
2. Follow the owning sidecar for routine detailed evidence.
3. Cross-reference by timestamp, display, generation, transition, activation, install id or other existing correlation identity.
4. Use verbose only when main + family sidecars are insufficient.
5. For long captures, verify that the main and relevant sidecar rotation windows overlap the claimed interval.
6. Record parser version/tool state in the run manifest.

Main and sidecars are complementary, not redundant.

## GPU Evidence Rules

Record together where relevant:

- process GPU busy and sample time/age;
- display refresh/DPR/route;
- transition family;
- GL timer-query support/sample count/duration;
- texture upload/allocation telemetry;
- visualizer logical/set_state/update/paint rates;
- request/event-loop/paint timing.

Never infer zero GPU cost from absent timer samples. Never use `glFinish()` to make
profiling synchronous.

## Manifest Requirements

Every official current run records exact commit/dirty state, entry point, environment,
displays, source/cache/visualizer settings, transitions/widgets, load intervals, logging
flags, actions and expected termination.

Do not store credentials, API keys, sensitive titles/URLs or copyrighted audio.

## Epistemic Rules

- distinguish direct log fact, source fact, inference and user visual verdict;
- state confidence below 90%;
- one mixed-load run can identify owner correlations but is not a controlled implementation comparison;
- a driver GPU busy metric is not theoretical GPU utilization;
- logs diagnose visualizer timing but cannot certify feel;
- solved historical incidents remain useful anti-regression evidence without staying active tasks.
