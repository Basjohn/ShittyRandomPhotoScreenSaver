# R-82 — Scaled Prefetch Derivatives Could Permanently Occupy Budget After Raw Parent Eviction

Date: 2026-09-14  
Status: SOLVED — Installed 58-Minute Soak Closed The Liveness Gate

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

A roughly ten-hour overnight soak showed that scaled-prefetch warmup effectively stopped near the start of the run while raw preview prefetch continued for hours. Final flow counters showed **4,675 scaled-prefetch intents**, only **11 scaled completions**, **2,600 completed raw-prefetch IO tasks**, and only **9 scaled-cache hits** against **962 misses**.

The bounded derivative queue did not grow without limit. Instead it became permanently poisoned: six undispatchable derivative requests retained **125,337,600 bytes** of logical pending budget, about **93.4% of the 128 MiB cap**, leaving only about **8.47 MiB** for useful future work.

## Root Cause

Scaled derivative ownership was admitted while its raw parent was resident or still had a raw producer. That was correct. The lifetime contract broke later:

1. raw decode completed;
2. `ImageCache.put(raw_path, image)` returned successfully;
3. the hard LRU budget could immediately evict that same large raw image;
4. the prefetch completion path treated successful `put()` as proof of residency;
5. the raw producer ownership was retired;
6. `_pump_scaled_prefetch()` correctly refused to dispatch a derivative whose raw parent was no longer resident;
7. no path reclaimed the now-impossible derivative's pending key and logical byte charge.

A derivative could therefore become permanently undispatchable while still owning bounded-queue budget. The memory bounds prevented an actual memory leak, but they converted the queue into a long-lived dead-work reservation.

The soak's stable poisoned budget was exact, not approximate noise:

```text
2 × 3840 × 2160 × 4 bytes
+ 4 × 2560 × 1440 × 4 bytes
= 125,337,600 bytes
```

## Fix

`ImagePrefetcher` now uses actual ownership facts:

- after raw `ImageCache.put()`, actual cache residency is checked instead of assuming the call retained the image;
- pending derivatives are reclaimed when their raw parent is neither cache-resident nor owned by a queued/inflight raw producer;
- reclamation retires both the pending cache key and exact logical-byte charge;
- producer-owned derivatives remain valid even while the raw parent is not yet resident;
- cleanup runs independently of post-transition compute cooldown, so a dead derivative cannot pin budget merely because dispatch is temporarily paused;
- no cache size, scaled-pending budget, concurrency, transition pacing, rendering path, or Visualizer reactivity contract was changed.

This is intentionally reclamation/ownership repair, **not** a larger-cache workaround.

## Regression Coverage

`tests/test_image_prefetcher.py` now covers the production-shaped failure rather than only queue shape:

- successful raw `put()` followed by immediate self-eviction;
- exact derivative key/byte reclamation;
- repeated cycles returning pending state to zero instead of accumulating;
- protection of derivatives while a queued/inflight raw producer still owns the parent;
- replacement work becoming admissible after reclaimed budget is returned.

The exact state machine was A/B checked against pre-fix and repaired source: old behavior retained **1 pending derivative / 16 MiB** in the reduced fixture; repaired behavior returned **0 / 0**.

`--cache` is the permanent diagnostic owner for this family. Existing cache-sidecar records now expose orphan reclamation count/bytes and bounded-backlog skips; no additional recurring probe or `--perf` instrumentation is justified.

## Installed Validation — 2026-09-14

The preferred roughly one-hour Windows diagnostic soak closed the remaining liveness gate:

- **93** scaled-prefetch requests and **91** completions occurred during the run;
- **85** scaled-cache evictions occurred while scaled warmup continued;
- deferred resume was scheduled **45** times and ran **45** times;
- raw-prefetch sources were released after the final derivative **91** times;
- cumulative scaled-cache eviction reached roughly **2.642 GiB** while the live cache finished bounded at about **189.8 MiB / 6 items**;
- one startup bounded-backlog refusal near the 128 MiB derivative cap recovered normally instead of poisoning admission;
- presentation recorded **45 scaled hits, zero scaled misses, zero worker requests/fallbacks**, with reuse continuing after eviction pressure.

The historical failure signature — derivative budget remaining pinned near 128 MiB after raw-parent eviction while scaled completions effectively stop — did not recur. R-82 is therefore closed. Do not churn this repair merely because later performance work touches adjacent diagnostics.

## Guardrail

A successful cache insertion call is not a lifetime guarantee. Derivative work may own a nonresident parent only while some explicit producer still owns that parent. Once neither residency nor producer ownership exists, every derivative key and byte reservation must be retired promptly.
