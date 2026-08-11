# Logging Guide

Last updated: 2026-08-11

## Purpose

Keep logs readable, attributable and cheap enough that diagnostics do not become the
workload they are measuring.

## Main Contract

`screensaver.log` contains:

- high-level runtime narrative useful to an operator;
- **every WARNING, ERROR and CRITICAL from every family**;
- only routine INFO that genuinely belongs in the general sequence.

When a dedicated family sidecar is enabled, routine family INFO/DEBUG belongs in that
sidecar and should not duplicate into main. `screensaver_verbose.log` remains the broad
debug fallback, not the place agents should read first when a dedicated sidecar exists.

## Dedicated Families

Existing sidecars remain the first destinations for their domains:

- `--perf` → `screensaver_perf.log`, `perf_widgets.log`
- `--usage` → `screensaver_usage.log`
- `--viz` → `screensaver_spotify_vis.log`, `screensaver_spotify_vol.log`
- `--geo` → `screensaver_geometry.log`
- `--set` → `screensaver_settings.log`
- `--life` → `screensaver_lifecycle.log`
- `--cache` → `screensaver_cache.log`
- `--steam` → `screensaver_steam.log`

Do not create a new sidecar merely because one logger is noisy. Add a family only when a
distinct high-volume domain has a coherent correlation workflow.

## Current Cache Routing

Cache routing still relies partly on message text. It now recognizes both `[CACHE]`
and `[GL CACHE]`; focused routing automation requires routine `[GL CACHE]` INFO in
`screensaver_cache.log` and absent from main when the sidecar is active, while a
`[GL CACHE]` WARNING remains in both.

Structured family metadata remains the later replacement for token-based routing. Do
not regress this repair by lowering records to DEBUG or deleting useful cache evidence.

## Phase 5 Execution Architecture

Normal logging uses one bounded process-owned queue/writer:

```text
caller thread
   -> cheap structured LogRecord enqueue
   -> process-owned writer
      -> family routing
      -> formatting/deduplication
      -> rotation/file writes
```

Requirements:

- caller path is small and normally non-blocking;
- bounded queue with high-water/drop telemetry and explicit overload policy;
- original timestamp plus monotonic/correlation ordering metadata survives;
- one writer owns normal file rotation/writes;
- shutdown exposes a bounded flush/close contract;
- fatal/native crash breadcrumbs and faulthandler output remain direct and independent of the queue.

Current implementation details:

- the root logger exposes one producer-facing ingress; real handlers and filters are writer-owned;
- `SRPSSLogWriter` survives Settings/Edit runtime-generation retirement and is not a `ThreadManager` task;
- queue capacity is 4096 records; DEBUG/INFO may drop only on saturation/closing and are counted by level;
- WARNING+ saturation uses the serialized direct-main emergency path and is never silently dropped;
- shutdown atomically replaces queue ingress with a warning-only closing sink, preserving main visibility through writer finalization and retiring that sink on reconfiguration/atexit;
- the final `[LOG_QUEUE]` record reports enqueue/dequeue counts, high-water, drops, caller cost, writer lag, emergency/reentry fallbacks, writer errors and flush duration;
- `flush_logging()` is the bounded visibility barrier used before the exit PERF parser;
- `flush_and_close_logging()` is the supported ordinary-logging shutdown/reconfiguration API and runs before diagnostic crash-capture close;
- direct `logging.shutdown()` is not a substitute for the controller-aware drain/close contract.

## Structured Family Metadata

Human-readable tags such as `[PERF]`, `[CACHE]` and `[GL CACHE]` are useful for people
but are a fragile routing API. Prefer an explicit record family/category attribute,
e.g. `cache`, `lifecycle`, `geometry`, `visualizer`, `usage`, `perf`, while retaining the
visible tag where useful.

Late Phase 7 should migrate high-volume families systematically and simplify filters so
routing no longer depends on token quirks.

## Late Phase 7 Taxonomy Refinement

Before Phase 8 compositor work:

1. inventory routine INFO/DEBUG volume by family/logger;
2. ensure existing sidecar families receive their own routine records;
3. keep every WARNING+ visible in main regardless of sidecar;
4. add sidecars only for genuinely distinct domains;
5. remove redundant main/verbose duplication where a family sidecar is active;
6. preserve correlation identifiers/timestamps across files;
7. update parser rules/tests together with routing.

## Diagnostic Runtime

Diagnostic remains an opt-in frozen-runtime attribution product. It may enable all
families automatically and retain bounded crash/owner breadcrumbs. It is not a
performance baseline, and ordinary work must not trigger a Diagnostic rebuild unless a
specific frozen-only failure requires it.

## Correlation Workflow

1. Read `screensaver.log` for sequence and all warnings/errors.
2. Follow the owning sidecar for routine family detail.
3. Use shared timestamps/correlation ids to cross-reference perf/usage/lifecycle/cache/viz.
4. Use verbose only when the general + family sidecars are insufficient.

## Guardrails

- no per-frame routine INFO stream;
- no logging-driven repaint/cadence/control flow;
- no UI-thread normal file/rotation work; only the explicit saturated WARNING+ emergency path may write synchronously;
- no hiding WARNING+ from main;
- no “performance improvement” achieved by deleting evidence instead of moving/routing it cheaply;
- no unbounded logging queue.
