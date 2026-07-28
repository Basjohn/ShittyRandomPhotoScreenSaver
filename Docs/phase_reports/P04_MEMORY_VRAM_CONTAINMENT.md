# Phase 4 — Baseline Memory and VRAM Containment

Date: 2026-07-28
Branch: `main`
Foundation: Phase 3 checkpoint `677a317104a6507d9ecf620b54e85ee858e9ba5f`
Donor boundary: reference only; no donor merge or donor resource architecture transplant

## Outcome

Phase 4 bounds the baseline's existing CPU image cache, prefetch backlog, compositor texture cache, and upload-PBO pool by exact bytes while retaining the baseline display/compositor topology. It removes redundant active-path QImage/QPixmap copies, shares same-image backing only for exact transform matches, releases every transition family's obsolete state at terminal presentation, and extends passive resource snapshots to display-owned QPixmap backing stores.

The deterministic owner/plateau gate passed. A driver VRAM soak is not fabricated by the offscreen harness and remains part of Phase 11 platform validation.

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

## Live log follow-up — 2026-07-28

The latest dual-display run provides encouraging but preliminary platform evidence. It lasted about 5.75 minutes and ended at the Phase 3 program-ownership fault, so it does not replace the 30-minute or two-hour Phase 11 gates.

Compared with the frozen baseline peaks:

| Metric | Frozen peak | Latest peak | Preliminary change |
|---|---:|---:|---:|
| RSS | 1770.5 MiB | 1228.7 MiB | -30.6% |
| Private commit | 5141.9 MiB | 3172.0 MiB | -38.3% |
| Dedicated driver VRAM | 1872.8 MiB | 773.8 MiB | -58.7% |

The live Phase 4 owners stayed inside their configured envelopes: the CPU image cache remained within 256 MiB, combined two-compositor texture accounting remained within 256 MiB, and upload-PBO accounting peaked at about 45.7 MiB. This supports the containment direction but is not yet plateau proof because the scenario was short and teardown failed.

The same run identifies work that must remain open:

- process CPU averaged about 55.1% and compute submission rate was 101.2/s, so no CPU/task reduction is claimed;
- `visualizer.bubble_simulation` accounted for about 68.9 submissions/s and `visualizer.audio_analysis` about 32.2/s, making them the first measured Phase 5 owners;
- two long-lived per-display adaptive presentation workers remain and must be replaced by the Phase 8 GUI-local active-animation mechanism rather than optimized as a competing scheduler;
- RSS above roughly 900 MiB, multi-GiB private commit, driver VRAM above roughly 500 MiB, and the gap between tracked bytes and OS/driver totals still require explanation;
- usage telemetry now emits the already-collected display-QPixmap count/bytes explicitly, and the recovery parser preserves those fields for the next evidence capture.

## Verification

```powershell
.\.venv\Scripts\python.exe tools\phase4_resource_harness.py --cycles 45 --output Docs\phase_reports\artifacts\P04\resource_plateau_report.json
.\.venv\Scripts\python.exe -m pytest tests\test_phase3_runtime_lifecycle.py tests\test_engine_lifecycle.py tests\test_s_hotkey_workflow.py tests\test_gl_compositor_cleanup.py tests\test_gl_compositor_transitions.py tests\test_gl_compositor_transition_lifecycle.py tests\test_gl_texture_streaming.py tests\test_memory_pooling.py tests\test_image_cache_accounting.py tests\test_image_prefetcher.py tests\test_image_pipeline.py tests\test_image_worker.py tests\test_resource_metrics.py tests\test_phase4_resource_containment.py tests\test_settings_defaults_parity.py tests\test_regenerate_sst_defaults.py -q
```

Final closure evidence:

- combined Phase 3/4 lifecycle, resource, image, settings, and display gate: `194 passed, 13 skipped` (the skips are environment-gated GL cases);
- protected runtime-shaped visualizer file: `186 passed, 20` documented Bubble skips;
- deterministic visualizer replay: all `66` goldens plus manifest verified unchanged;
- visualizer documentation references: `6 passed`;
- real Windows Qt GL cleanup: `3 passed` without skip, including the corrected two-compositor ownership sequence;
- deterministic 45-cycle / 30-virtual-minute resource plateau artifact: pass.

## Rollback

Phase 3 checkpoint before this work: `677a317104a6507d9ecf620b54e85ee858e9ba5f` (`4.6.9 Phase 3`).

Phase 4 is committed separately as `4.6.9 Phase 4`; the Phase 3 hash remains the direct rollback point.