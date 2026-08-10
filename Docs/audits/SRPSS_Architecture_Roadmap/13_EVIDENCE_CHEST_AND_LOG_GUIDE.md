# 13 — Evidence Chest and Log Guide

Last reconciled: 2026-08-10

## Purpose

The evidence chest preserves raw runtime evidence, parser output, manifests and rejected
candidate comparisons. Current-main evidence is primary; older archives are historical.

## Current Canonical Evidence

```text
logs/evidence_chest/08_09_ca830d7_14_59/
```

Strong current conclusions already extracted from this run should not be rediscovered
from raw logs by every later agent unless a new hypothesis needs the source lines:

- request age dominates paint in owner-labelled frame gaps;
- `generic_pair_warm` dominates steady `set_processed_image()` cost;
- retained current texture identity does not cache-hit next old texture;
- active-display process GPU busy reaches median `10.8%`, p95 `27.8%`, max `32.9%`;
- visualizer screen 1 is 60 Hz while overlay state/update/paint windows can approach ~100 Hz;
- captured lifecycle barriers are mechanically healthy; solved Settings/Edit ownership is historical, not active.

## Historical Evidence

Old baseline/candidate ZIPs remain immutable forensic sources. Their filenames/tooling
may retain historical names. They are not current implementation authority.

## Sidecar Contract

Expected families include main, verbose, perf/widget perf, usage, cache, geometry,
lifecycle, settings, visualizer/volume and Steam sidecars.

**Main log contract:** high-level runtime narrative plus every WARNING/ERROR/CRITICAL.
When a dedicated family is active, routine family INFO/DEBUG belongs in its sidecar and
should not duplicate into main.

Current known defect: the mixed-load run contains **132 `[GL CACHE]` INFO records in
`screensaver.log` and zero in `screensaver_cache.log`** because current cache routing
looks for `[CACHE]`/selected prefixes. This is a routing bug, not desired policy.

## Logging Architecture Evidence

Phase 5 queued logging must preserve:

- original record timestamp and monotonic/correlation metadata;
- severity/logger/family identity;
- bounded queue depth/high-water/drop telemetry;
- one writer's file/rotation ownership;
- flush/close semantics;
- direct emergency/faulthandler path independent of the queue.

Late Phase 7 taxonomy refinement should prefer structured family metadata over message
string parsing. New sidecars are justified by a genuinely distinct high-volume domain,
not by every logger name.

## GPU Evidence Rules

Record together:

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
flags, actions and expected termination. Do not store credentials, API keys, sensitive
titles/URLs or copyrighted audio.

## Epistemic Rules

- distinguish direct log fact, source fact, inference and user visual verdict;
- state confidence below 90%;
- one mixed-load run can identify owner correlations but is not a clean code-only A/B;
- a driver GPU busy metric is not theoretical GPU utilization;
- logs diagnose visualizer timing but cannot certify feel;
- solved historical incidents remain useful anti-regression evidence without staying active tasks.
