# Phase 4 — Baseline Memory and VRAM Containment

Date: 2026-07-28
Reopened: 2026-07-29
Branch: `main`
Foundation: Phase 3 checkpoint `677a317104a6507d9ecf620b54e85ee858e9ba5f`
Donor boundary: reference only; no donor merge or donor resource architecture transplant

## Outcome

Phase 4 bounds the baseline's existing CPU image cache, prefetch backlog, compositor texture cache, and upload-PBO pool by exact bytes while retaining the baseline display/compositor topology. It removes redundant active-path QImage/QPixmap copies, shares same-image backing only for exact transform matches, releases every transition family's obsolete state at terminal presentation, and extends passive resource snapshots to display-owned QPixmap backing stores.

**Status: open / platform gate blocked.** The deterministic cache, display, texture, and PBO owner/allocator gate passed and remains valid. The later real run exposed a separate ImageWorker shared-memory retention path that the deterministic harness did not model. Phase 4 is not complete until labelled worker RSS and shared-memory accounting plateau in the full Phase4plus scenario. CPU/task-rate reduction remains Phase 5.

## Baseline growth mechanisms corrected

1. `ImageCache` kept exact QImage/QPixmap byte metadata but evicted using a separate `width × height × 4` approximation. Its missing-setting fallback was 1 GiB.
2. raw and scaled prefetch concurrency was bounded, but pending backlogs and future decoded bytes were not.
3. scaled prefetch created `QPixmap` in a compute worker.
4. the active async display path deep-copied raw/scaled QImages repeatedly and materialized an unused original QPixmap for every display.
5. same-image monitors independently processed identical transforms and independently materialized identical GUI pixmaps.
6. compositor textures were limited only to 12 entries, allowing hundreds of MiB per display at large resolutions.
7. the PBO pool could retain multiple historical sizes and a reused PBO could be reallocated smaller behind stale capacity accounting.
8. normal transition completion released pair references only for selected transition types; Particle/Burn cancellation did not clear their state or snap to their destination.
9. Phase 1 accounting omitted current/previous/seed/pending/compositor QPixmap backing stores because a background sampler may not inspect live Qt objects.
10. each large ImageWorker response appended its creator `SharedMemory` mapping to `_shared_memories`, retaining every RGBA segment until process exit; the parent copied the entire mapping into `bytes`, closed without unlinking, then deep-copied it again into a detached `QImage`.

## Implemented containment

### CPU image ownership

- `ImageCache` now evicts on `QImage.sizeInBytes()` / QPixmap depth-derived exact logical bytes.
- missing defaults are 16 entries / 256 MiB; legacy persisted values clamp to 2–32 entries, 64–256 MiB, and 1–4 concurrent prefetch requests.
- raw/scaled prefetch queues are bounded by outstanding count; scaled future footprints are also bounded by target RGBA8 bytes.
- scaled prefetch returns QImage only.
- immutable compute DTOs alias cache-owned QImages rather than deep-copying them.
- one GUI QPixmap serves both processed/original compatibility parameters because the original parameter is not a distinct runtime owner.
- same-image monitors reuse compute and GUI backing only when width, height, mode, and DPR match exactly.

### Display accounting

`rendering/image_resource_accounting.py` captures QPixmap metadata on the GUI thread and deduplicates backing stores by cache key across:

- DisplayWidget current, previous, and seed roles;
- ImagePresenter aliases;
- pending transition and CUSTOM deferred payloads;
- compositor base and every supported transition old/new role;
- multiple displays sharing one exact-transform backing store.

`collect_resource_accounting()` reads only that detached sidecar and now reports `cpu_display_resources` / `cpu_display_bytes` alongside CPU cache and GL registry bytes.

### GL containment

- each compositor texture cache has a 128 MiB plus 12-entry LRU cap;
- active old/new pair IDs are pinned only until terminal presentation;
- completion and cancellation always release pair pins, making obsolete sources immediately evictable on the current context;
- failed texture deletion retains accounting/ownership;
- the idle PBO pool retains at most one entry under 64 MiB;
- reused PBO uploads preserve the tracked allocation capacity rather than silently shrinking it;
- full Phase 3 teardown still requires exact zero and owner-context deletion.

The Phase 6 shared resource store is intentionally not pulled forward. Phase 4 remains per-compositor and metadata/accounting-first.

### ImageWorker shared-memory containment

- Each large worker result now has one versioned, per-transfer mapping and no process-lifetime mapping list.
- Windows destroys a named mapping when its last handle closes, so the worker publishes the descriptor and waits only for a one-byte attachment acknowledgement. Once the parent has opened its own mapping, the worker closes its creator handle immediately. A failed publication or unacknowledged handoff is reclaimed by the worker.
- The parent constructs one temporary non-owning `QImage` over the mapped RGBA view and performs exactly one `QImage.copy()` into Qt-owned memory. It releases the temporary QImage and memoryviews, then closes/unlinks in `finally`; no intermediate full-image `bytes` copy remains.
- The supervisor tombstones timeouts/cancellations, disposes stale-generation and rejected payloads, bounds and resource-disposes buffer overflow, drains response resources on worker stop, and disposes every buffered response before shutdown/cleanup.
- Parent-visible accounting records `segments_created`, `segments_live`, `live_bytes`, `segments_consumed`, `segments_reclaimed_late`, and `unlink_failures`. Usage telemetry also emits labelled ImageWorker PID/RSS/VMS separately from main, child-total, and application RSS.
- Shared-memory lifetime remains owned by ImageWorker transport and `ProcessSupervisor`; it is not attached to compositor teardown.

## Resource lifetime map

See `Docs/phase_reports/P04_RESOURCE_LIFETIME_MAP.md` for representation, owner, identity, release event, accounting, and budget.

## Plateau evidence

Artifact: `Docs/phase_reports/artifacts/P04/resource_plateau_report.json`

The harness uses production `ImageCache`, display accounting, `collect_resource_accounting()`, transition state, and `GLTextureManager` eviction/cleanup seams with real QImage/QPixmap allocations and process RSS. It runs 45 rotations, equivalent to 30 virtual minutes at the shipped 40-second interval, across 720p, 1080p, 1440p, 4K, portrait, and ultrawide frames.

Coverage and result:

- alternating large/small images and aspect ratios;
- active transition on every cycle;
- two displays sharing exact-transform backing;
- tighter pressure budgets: 96 MiB CPU cache, 96 MiB texture cache, 40 MiB PBO;
- all cache/texture/PBO samples within terminal budgets;
- terminal display accounting retained one unique frame, not alias-counted copies;
- modeled full-owner resets at cycles 15, 30, and 45 reached zero CPU-cache, display, texture, and PBO bytes; normal Settings/Edit retains only the independently bounded CPU cache and rebuilds display/GL owners;
- repeated-resolution RSS drift: 4 KiB;
- final three complete-cycle RSS high-water range: 12 KiB;
- all pass criteria true.

This is deterministic owner/allocator evidence, not a claim of real driver VRAM. Phase 11 retains the normal run, two-hour soak, multi-display topology, and driver-reported VRAM gates.

## Reopening evidence — `phase4plus_a2f7bd89`

The newest pre-fix dual-display capture ran for about 13m45s and exited cleanly. It supersedes the report's earlier 5.75-minute sample. The sole child was the ImageWorker. Across 55 usage samples its inferred RSS (`rss_app_mb - rss_main_mb`) rose from 92.2 MiB to 770.3 MiB while main RSS remained broadly bounded. From the post-warmup sample onward, the child commonly climbed by about 31–32 MiB per 40-second `3840×2158` prescale; one RGBA8 frame at that size is 31.611 MiB. This is a real-run shared-memory containment failure, not a failure of the separately bounded cache/texture/PBO owners.

Compared with the frozen baseline peaks:

| Metric | Frozen peak | `phase4plus_a2f7bd89` peak | Change |
|---|---:|---:|---:|
| RSS | 1770.5 MiB | 1578.7 MiB | -10.8% |
| Private commit | 5141.9 MiB | 3216.2 MiB | -37.5% |
| Dedicated driver VRAM | 1872.8 MiB | 773.9 MiB | -58.7% |

The previously instrumented owners remained bounded: CPU image cache peaked at about 254.7 MiB, combined two-compositor texture accounting at 252.8 MiB, and upload-PBO accounting at about 45.7 MiB. Those facts preserve the deterministic Phase 4 result, but the application as a whole did not plateau because worker mappings were outside that accounting.

The same run preserves separate later-phase work:

- process CPU median was about 59.4% and median compute submission rate was 163.8/s across changing mode/transition intervals, so no CPU/task reduction is claimed;
- two long-lived per-display adaptive presentation workers remain and must be replaced by the Phase 8 GUI-local active-animation mechanism rather than optimized as a competing scheduler;
- after shared-memory containment is proven live, remaining gaps between tracked owners, total RSS/private commit, and driver VRAM still require explanation without raising the 256 MiB CPU cache.

## Focused shared-memory result — 2026-07-29

`tools/phase4_image_worker_shm_harness.py` ran the real spawned ImageWorker for 50 sequential `3840×2160` prescales. Each payload was 33,177,600 bytes. It then submitted one additional image and stopped the worker while that transfer was in flight.

- 50 mappings consumed normally; one shutdown transfer reclaimed;
- zero live segments and zero live bytes after each normal consumption and at completion;
- zero unlink failures;
- no captured `srpss_img_*` name remained attachable after the forced worker stop or after final supervisor shutdown;
- worker RSS stayed between 89.2 MiB and 90.1 MiB;
- post-warmup RSS slope was effectively zero (-0.00009 MiB/cycle), versus the broken path's approximately 31.6 MiB/image staircase;
- final-window high-water growth was -0.13 MiB.

This closes the deterministic shared-memory ownership slice. It does not close Phase 4: the full Phase4plus platform comparator must still prove total RSS/private commit, worker RSS, tracked GL bytes, driver VRAM, and presentation together.

## Verification

```powershell
.\.venv\Scripts\python.exe tools\phase4_resource_harness.py --cycles 45 --output Docs\phase_reports\artifacts\P04\resource_plateau_report.json
.\.venv\Scripts\python.exe tools\phase4_image_worker_shm_harness.py --cycles 50 --width 3840 --height 2160
.\.venv\Scripts\python.exe -m pytest tests\test_image_worker_shared_memory.py tests\test_image_worker.py tests\test_process_supervisor.py tests\test_usage_sampler.py tests\test_recovery_evidence_parser.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_phase3_runtime_lifecycle.py tests\test_engine_lifecycle.py tests\test_s_hotkey_workflow.py tests\test_gl_compositor_cleanup.py tests\test_gl_compositor_transitions.py tests\test_gl_compositor_transition_lifecycle.py tests\test_gl_texture_streaming.py tests\test_memory_pooling.py tests\test_image_cache_accounting.py tests\test_image_prefetcher.py tests\test_image_pipeline.py tests\test_image_worker.py tests\test_resource_metrics.py tests\test_phase4_resource_containment.py tests\test_settings_defaults_parity.py tests\test_regenerate_sst_defaults.py -q
```

Evidence that remains valid:

- combined Phase 3/4 lifecycle, resource, image, settings, and display gate: `194 passed, 13 skipped` (the skips are environment-gated GL cases);
- protected runtime-shaped visualizer file: `186 passed, 20` documented Bubble skips;
- deterministic visualizer replay: all `66` goldens plus manifest verified unchanged;
- visualizer documentation references: `6 passed`;
- real Windows Qt GL cleanup: `3 passed` without skip, including the corrected two-compositor ownership sequence;
- deterministic 45-cycle / 30-virtual-minute resource plateau artifact: pass.

Current reopened-gate evidence:

- shared-memory ownership regressions: `15 passed`, including malformed-descriptor reclamation and bounded accounting history;
- 50×4K spawned-worker shared-memory plateau: pass;
- post-change first-frame/mode-switch poison selection: `19 passed, 1` existing environment skip;
- post-change replay goldens: all `66` verified;
- full Phase4plus platform comparator: pending.

## Rollback

Phase 3 checkpoint before this work: `677a317104a6507d9ecf620b54e85ee858e9ba5f` (`4.6.9 Phase 3`).

Phase 4 is committed separately as `4.6.9 Phase 4`; the Phase 3 hash remains the direct rollback point.
