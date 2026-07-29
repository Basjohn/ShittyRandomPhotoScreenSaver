# Phase 4 — Baseline Memory and VRAM Containment

Date: 2026-07-28
Reopened: 2026-07-29
Branch: `main`
Foundation: Phase 3 checkpoint `677a317104a6507d9ecf620b54e85ee858e9ba5f`
Donor boundary: reference only; no donor merge or donor resource architecture transplant

## Outcome

Phase 4 bounds the baseline's existing CPU image cache, prefetch backlog, compositor texture cache, and upload-PBO pool by exact bytes while retaining the baseline display/compositor topology. It removes redundant active-path QImage/QPixmap copies, shares same-image backing only for exact transform matches, releases every transition family's obsolete state at terminal presentation, and extends passive resource snapshots to display-owned QPixmap backing stores.

**Status: open / whole-process plateau failed.** The deterministic cache, display, texture, PBO, and shared-memory ownership gates pass. The 52-minute `fresh_20260729_2140` platform run also validates the ImageWorker/shared-memory fix live, but main-process RSS, total application RSS, and private commit still rise after warmup. Phase 4 is not complete until those whole-application owners plateau in a post-fix comparator. CPU/task-rate reduction remains Phase 5.

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
- source-set invalidation advances a prefetch generation before clearing the cache; late raw/scaled callbacks may neither repopulate an obsolete cache nor release a newer same-key owner.
- previous-image replay now shares one processed result and GUI QPixmap only for exact source, width, height, mode, DPR, and quality identity. Scaled cache keys carry non-default DPR so the cache cannot collapse a deliberately distinct replay.

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

This closes the deterministic shared-memory ownership slice. The later full platform run below validates that result live, but does not close Phase 4 because the main process and private commit fail the whole-application plateau gate.

## Full platform comparator — `fresh_20260729_2140`

The fresh dual-display capture ran from 20:47:55 to 21:40:03 and produced 209 usage samples. The post-warmup comparison window was approximately 44m45s.

| Owner/metric | Fresh result |
|---|---:|
| ImageWorker RSS min / median / max | 92.1 / 96.5 / 115.7 MiB |
| ImageWorker post-warmup slope | about +0.12 MiB/min |
| Main-process RSS slope | about +2.42 MiB/min |
| Total application RSS slope | about +2.54 MiB/min |
| Private-commit slope | about +3.87 MiB/min |
| Shared-memory terminal counters | 80 created, 80 consumed, 0 live, 0 live bytes, 0 unlink failures |
| Tracked GL bytes after warmup | 313,039,264 bytes, flat |
| Dedicated driver VRAM after warmup | about 773.9–774.0 MiB |

The prior approximately 31.6 MiB-per-image child staircase is gone. The worker remains within a narrow warm operating band, every published segment is consumed, and shared-memory, tracked GL, and driver-VRAM owners are bounded. This validates R-52 as solved.

Phase 4 nevertheless fails as a whole: main RSS and private commit retain sustained positive slopes not explained by the bounded child, shared-memory counters, tracked GL bytes, or driver VRAM. The 256 MiB CPU cache must not be raised to conceal that gap. A post-correction comparator must synchronize cache/display/GL accounting with main, worker, total RSS, and private commit and either attribute a bounded allocator high-water pattern or identify the remaining owner.

Presentation evidence is also mixed. Bubble retained healthy loud-passage response with roughly 1.1–1.8 ms mode-owned work. Spectrum and a runtime mode switch were not exercised, so no Spectrum feel conclusion is drawn. Near the tail, screen 1 delivered 46.6 FPS with p95 56.40 ms and 25 frames above 50 ms while screen 0 delivered 108.8 FPS with p95 15.61 ms. Paint work was comparatively cheap and GUI event-loop p99 was 38.28 ms, pointing at delivery/scheduling pressure rather than a visualizer-math regression.

## Focused media/startup collision containment — 2026-07-29

The latest `phase4plus_a2f7bd89` logs showed artwork payload changes and overlay/shader startup work near visualizer frame-tail gaps, but did not prove either owner caused every gap. Bubble compute remained comparatively cheap while logical `dt` gaps persisted, and transition overlap increased warning frequency without explaining all warnings. The correction therefore stays isolated to the measured ownership seams; no Spectrum/Bubble math, visual smoothing, compositor topology, or transition presentation was retuned.

- The existing media `ThreadManager` query job now computes the bounded artwork key and decodes changed payloads once for each widget's current/pending key into worker-safe `QImage`. The GUI callback creates a single `QPixmap`, normalizes DPR, and invalidates the scaled cache only when the applied key changes. This slice deliberately adds no process-wide artwork cache or in-flight decode coordinator ahead of the separate cache audit.
- Unchanged artwork keys are text-only updates. Artwork disappearance is an explicit empty-key update. Decode failure is terminal for that key rather than becoming a repeated poll-time decode.
- While any live display is preparing or running an image transition, only the newest prepared artwork/key/generation is retained. QPixmap replacement, art-dependent margins/layout, and the artwork fade flush together only after every display is idle.
- A same-key follow-up poll now promotes the retained decoded QImage to the newest generation before metadata diff-gating. Material-event-only telemetry records `decoded`, `queued`, `replaced`, `flushing`, `discarded`, and `applied`; destroyed wrappers are removed after disposing an actual pending payload rather than producing repeated empty discard records.
- Accepted manual Next/Previous submissions rebase the existing active rotation timer. Timer expiry coalesces before queue advancement, cache lookup, worker submission, or prescale whenever image-change work is active. Previous-image decode claims that work owner before history mutation; rejected submissions release it and do not rebase.
- `FadeCoordinator` now owns named critical startup holds and real animation completion. `critical_gl_startup` releases after first-frame commitment and the existing active Spotify overlay prewarm reaches a terminal outcome; optional failure cannot strand the reveal.
- Noncritical transition shaders/resources remain compositor-owned and optional. They run one item per managed callback, pause during actual coordinated startup fades or any live display transition, and resume after real fade completion. An enabled overlay with no startup data remains `READY` without stranding warmup; any later reveal moves synchronously to `FADING` before the next slice.
- Bounded `[PERF][MEDIA_ARTWORK]` and `[STARTUP_SEQUENCE]` records separate worker decode, UI pixmap creation, transition deferral/coalescing, critical readiness, actual fade completion, and the first permitted deferred GL slice.

Focused automated evidence:

- focused media artwork/startup/fade/warmup owner suite: `119 passed`;
- protected runtime-shaped visualizer suite: `186 passed, 20 skipped`;
- current first-frame/mode-switch poison selection: `22 passed`;
- deterministic replay: all `66` goldens plus manifest verified unchanged;
- shared-memory/supervisor/accounting safety gate: `65 passed`.

This closes the deterministic ownership and scheduling slice only. The fresh full run proves the terminal shared-memory counters but predates the artwork-generation, rotation-deadline, stale-prefetch, and previous-image reuse corrections above. The next installed comparator still owns the 60 Hz/165 Hz forced Spotify-change bars, manual-change deadline collision, Spectrum/Bubble/mode-switch review, startup presentation, and whole-application plateau.

## Forced track-change collision evidence — `fresh_20260729_2233`

This short dual-display run is presentation evidence, not a replacement for the 52-minute whole-process plateau baseline. It contains three deliberate media-key track/artwork changes during active Wipe, Burn, and Block Puzzle Flip transitions.

- Every changed artwork key decoded in the existing worker job, queued while transition work was active, and applied only after both displays were idle. No pending key was replaced or discarded; `ui_pixmap_ms` was `0.00` for all three applies.
- The worst transition windows still had cheap compositor paint work but delayed delivery. Wipe reached screen-0/1 paint `dt` p95 values of 42.80/56.90 ms while paint itself remained at 3.22/6.89 ms p95. Burn reached a 96.85 ms screen-0 `dt` p99 with 3.70 ms paint p99. This rules out artwork conversion, Bubble compute, and shader paint as the primary collision.
- Each media-key command launched `start_feedback_animation` for 1.35 seconds. The corresponding windows contained 30–38 full media-card paints at roughly 3–4 ms each, versus about 2–6 paints in comparable transition windows without feedback. The shared AnimationManager summaries for those feedback fades fell to about 20–28 FPS while compositor and visualizer delivery gapped around them.
- Changed metadata also reapplied blank `QLabel` text state, fixed min/max height, and identical margins even though text is painter-owned and the card footprint had not changed. The provider header logo was smooth-scaled again on every media paint.

The owner-local correction keeps ordinary feedback animation unchanged when displays are idle, but during transition work publishes one immediate static feedback frame and clears it through one managed, token-checked callback. A process-wide 200 ms gate accepts only the first Qt/WM_KEYDOWN/WM_APPCOMMAND/raw-input route before widget lookup while leaving Windows pass-through intact; the accepted route performs the visualizer wake once. Metadata title/artist state remains immediate and requests one coalesced paint; Qt label/height/margin setters now run only when the actual state differs. The DPR-sized provider header logo is cached by source, target size, and DPR. Display-change and double-click refreshes no longer bypass the in-flight query generation, closing the observed same-owner startup double decode without retaining another prepared image. `[PERF][MEDIA_FEEDBACK]` now separates ingress suppression, static/animated mode, duration, and paint requests, while `[PERF][MEDIA_PRESENTATION]` separates layout and signal-emission cost, subscriber count, transition state, and generation.

Focused automation after this correction:

- focused media ingress/display/feedback/artwork runtime suite: `99 passed`;
- historical first-frame and mode-switch poison bars: `22 passed`;
- process-wide media-route convergence is included in the focused media suite.

Two short cold starts initially appeared to expose only a reveal-order gap. The 23:40 installed rerun proved that diagnosis incomplete: generation 1 decoded and queued the artwork, transition idle discarded that sole decoded image after generation 2 began, and generation 2 then logged an apply for the same key despite having no image or pixmap. Idle flush now retains a stale-generation pending image only while the authoritative current query remains in flight. That query then promotes the decoded image when its key matches or replaces it when the key changed. Applied telemetry now states `pixmap_ready`; startup pixmaps remain at zero opacity until card reveal completion starts their fade, with transition overlap handed to the existing all-displays-idle callback. This adds no timer, retry, eager decode, or second image representation.

The installed gate remains open. A matching 60 Hz/165 Hz run must prove the former 30–38-paint feedback burst is absent, fixed-footprint transition metadata reports zero structural mutations, artwork still flushes newest-only after final idle, cold-start artwork avoids `stale_idle_flush_generation` while its current query is in flight and reports `pixmap_ready=True` followed by one `event=fade_started` only after card reveal/transition idle, and visualizer/transition presentation tails return to the no-track-change comparator. No visualizer response, smoothing, compositor topology, or artwork-fade curve was retuned.

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
- combined Phase 4 cache/prefetch/pipeline/worker/supervisor/GL resource gate: `144 passed`;
- combined media/startup/rotation/lifecycle gate: `161 passed`;
- post-change first-frame/mode-switch poison selection: `22 passed`;
- post-change replay goldens: all `66` verified;
- follow-up deterministic 45-cycle resource harness: pass, with 4 KiB repeated-resolution drift and 8 KiB tail high-water range;
- full `fresh_20260729_2140` comparator: worker/shared-memory and GL/VRAM owners pass; main/total RSS and private commit fail to plateau;
- `fresh_20260729_2233` forced-collision comparator: artwork ownership passes; media feedback/presentation fails and is corrected in code;
- installed comparator after the newest media-feedback collision correction: pending.

## Rollback

Phase 3 checkpoint before this work: `677a317104a6507d9ecf620b54e85ee858e9ba5f` (`4.6.9 Phase 3`).

Phase 4 is committed separately as `4.6.9 Phase 4`; the Phase 3 hash remains the direct rollback point.
