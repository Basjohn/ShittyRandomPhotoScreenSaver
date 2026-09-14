# R-84 — Main-Process Handle Growth Survived PDH Cardinality Attribution

Date: 2026-09-14  
Status: COMPLETELY FUCKED — Residual Handle Class Attribution Required

## Classification

- [x] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure

Earlier lifetime evidence showed main-process Windows handles climbing at roughly **+19 handles/hour** while RSS, USS/private memory, thread count, shared-memory ownership, and worker resource counts remained broadly stable. The first attribution hypothesis was that `--usage`'s 300-second PDH GPU query rebuilds and changing counter cardinality could explain the apparent slope.

The preferred **58-minute Windows soak on 2026-09-14 disproved that as a complete explanation**. It produced twelve PDH generations and every generation carried the same cardinality: **15 GPU Engine + 1 dedicated-memory + 1 shared-memory = 17 counters**. After the final Settings reconstruction there was roughly **39 minutes of stable runtime generation**, yet `handles_main` still had an estimated residual slope of about **+16.0 handles/hour**. Five-sample medians moved roughly **1874 -> 1887** over that interval.

The 300-second PDH boundaries themselves were not sufficient to explain it. Across generations 4->12, immediate boundary changes were approximately `+4, -4, +1, -1, +6, +4, -31, +24`, for only **+3 net handles**. Because counter cardinality stayed fixed at 17, there is no growing PDH denominator available to absorb the remaining trend.

This still does **not** prove a specific product leak: the series is noisy rather than monotonically increasing inside every generation. It does prove the previous closure criterion failed. R-84 therefore remains **COMPLETELY FUCKED** until handle-class evidence identifies or clears the residual owner.

## Observer Effect Found During The Same Soak

The run also exposed a separate diagnostic-performance defect. The old two-minute Windows topology/thread refresh used psutil recursive-child discovery plus per-process `num_threads()`. Those calls route through a GIL-held system snapshot. Heavy `--usage` samples in this run were about **80-144 ms** and repeatedly coincided with roughly **70-156 ms frame maxima**, while ordinary usage samples were around **24 ms**.

This is observer contamination, not an excuse to discard the lifetime evidence. It is being repaired without weakening the resource statistics:

- the 15-second RSS/USS/CPU/handles/IO cadence remains unchanged;
- the two-minute topology freshness contract remains unchanged;
- Windows topology + thread counts now come from one Toolhelp process snapshot through ctypes, whose native calls release the GIL;
- non-Windows and Toolhelp-failure paths retain the old psutil fallback;
- each usage line records `topology_refresh` and `topology_source` so the next Windows run can prove the new path is actually active.

The soak also used first-time `--verbose` alongside the broad diagnostic family. The async logger itself stayed healthy (**44,870 records, zero drops, caller average about 0.052 ms**), so verbose output added work but was not a logger-collapse explanation. Routine performance closure runs should omit `--verbose`; `--debug` already produces `screensaver_verbose.log`.

## Handle-Type Attribution Added

The next diagnostic must identify **what kind of kernel object is growing**, not guess at owners from total handle count. Windows `--usage` therefore starts a low-cadence out-of-process helper that writes `screensaver_handles.log` every **60 seconds**.

The helper:

- takes a system extended-handle snapshot in its own process;
- filters the snapshot to the SRPSS main PID;
- groups handles by object type index;
- duplicates only representative handles **into the helper** to resolve type names;
- never performs per-handle type/name queries inside SRPSS;
- is excluded from `--usage` app process/thread/memory/handle aggregates;
- leaves only the small stable parent ownership cost of running the helper in `handles_main`;
- flushes each JSON record immediately and records explicit session/controller boundaries.

This intentionally belongs to `--usage`, not `--perf`. LOGZIP already captures direct loose files under `/logs`, so the sidecar evidence requires no separate archive workflow.

## Existing PDH Lifecycle Guardrail Still Applies

Do **not** reduce GPU/VRAM fidelity or lengthen/drop the 300-second rediscovery merely to make the handle graph flatter. `WindowsGpuUsageCollector` still closes each old query before replacement, replaces rather than appends counter lists, and exposes:

- `gpu_query_generation`;
- `gpu_engine_counters`;
- `gpu_dedicated_counters`;
- `gpu_shared_counters`;
- `gpu_pdh_counters_total`.

Those fields remain necessary context even though cardinality did not explain this run's residual slope.

## Regression Coverage

`tests/test_usage_sampler.py` covers:

- dynamic PDH rebuild/cardinality replacement and final close ownership;
- the injected topology-provider path avoiding psutil child/thread enumeration;
- sidecar PID exclusion from process aggregates;
- sidecar exclusion from Toolhelp thread totals;
- pure handle-type grouping for resolved and unresolved object types;
- usage log exposure of topology source/refresh and PDH denominator.

The native Toolhelp and NT handle-query paths still require the intended Windows/PySide/Nuitka environment for execution proof.

## Exit Condition From COMPLETELY FUCKED

Run **30 minutes minimum / about 60 minutes preferred** on Windows, single-display is sufficient. Use `--usage` and only the other diagnostic families actually needed for the question; **omit `--verbose`** for performance judgement.

Require all of the following:

1. heavy samples report `topology_source=toolhelp` rather than silently falling back to psutil;
2. two-minute heavy-sample collection/frame spikes collapse toward ordinary usage samples;
3. GPU/VRAM statistics and 300-second PDH query replacement remain intact;
4. correlate `screensaver_handles.log` type-count deltas against `handles_main` and PDH generation boundaries;
5. if one class (`Event`, `Thread`, `File`, `Key`, `Section`, etc.) rises, trace that owner next rather than mass-editing unrelated lifetime code;
6. if type counts and `handles_main` plateau after warmup with no meaningful independent slope, R-84 can move out of **COMPLETELY FUCKED**.

Instrumentation is not a fix. Until that evidence exists, R-84 stays open.

## Guardrail

Diagnostic observers consume resources too, but observer attribution must be proven rather than assumed. Preserve statistical fidelity, separate observer cost from product lifetime ownership, and identify the growing handle class before changing runtime owners.
