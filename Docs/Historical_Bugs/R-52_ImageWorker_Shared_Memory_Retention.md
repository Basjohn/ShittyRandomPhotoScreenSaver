# R-52 — ImageWorker Retained Every Shared-Memory Frame Until Process Exit

Date: 2026-07-29  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

The 13m45s `phase4plus_a2f7bd89` capture exited cleanly but the sole child grew from about 92.2 MiB to 770.3 MiB while main RSS remained broadly bounded. Post-warmup child RSS commonly rose by roughly 31–32 MiB at each 40-second `3840×2158` prescale, matching one 31.611 MiB RGBA8 frame. The deterministic Phase 4 cache/display/texture/PBO harness still passed because it did not spawn the long-lived ImageWorker.

## Root Cause

Each large worker result appended its creator `SharedMemory` mapping to a process-lifetime list and released the list only at worker exit. The parent copied the full mapping into `bytes`, closed without unlinking, then deep-copied it again into `QImage`. Timeout, late response, cancellation, buffered shutdown, and queue cleanup had no payload-specific disposal.

## Fix

Shared images now use one versioned per-transfer mapping. A one-byte attachment handshake preserves the required Windows handle lifetime only until the parent opens the mapping; the worker then closes immediately. The parent builds a temporary QImage directly over the mapped view, copies once into Qt-owned memory, and releases/closes/unlinks in `finally`. Supervisor tombstones and payload-aware disposal cover late/cancelled/stale/buffered/stopping paths, with exact shared-memory counters and separate ImageWorker RSS telemetry.

## Focused Bars

Ownership regressions pass (`15 passed`), including malformed-descriptor reclamation and bounded accounting history; the real spawned-worker harness consumed 50 sequential 4K frames and reclaimed one forced shutdown transfer with zero live bytes, zero unlink failures, no captured orphan names, worker RSS 89.2–90.1 MiB, and effectively zero (-0.00009 MiB/cycle) post-warmup slope. The post-change visualizer gate verified all 66 replay goldens and passed 22 first-frame/mode-switch poison tests.

## Live Validation

The 52-minute `fresh_20260729_2140` run created and consumed 80 segments with zero terminal live bytes and unlink failures. ImageWorker RSS stayed within 92.1–115.7 MiB and its post-warmup slope was about +0.12 MiB/min; the former approximately 31.6 MiB/image staircase did not recur.

## Boundary

This comparator kept Phase 4 open at the time. Phase 4 subsequently closed after the installed normal-run presentation/containment comparator. The later repeated Edit/Settings recreation staircase belongs to P5.4 and does not reopen R-52 or Phase 4.

## Guardrail

Never retain creator mappings as a worker-lifetime cache, clear response buffers without payload disposal, attach transfer lifetime to compositor teardown, recycle workers to reclaim memory, or hide unexplained total memory with a larger CPU cache, repeated GC, or memory trimming.

## Evidence

- `Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md`
- `Docs/phase_reports/P04_RESOURCE_LIFETIME_MAP.md`
- `tests/test_image_worker_shared_memory.py`
- `tools/phase4_image_worker_shm_harness.py`

## Migration Record

This file is the standalone detailed record copied from the original `R-52` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
