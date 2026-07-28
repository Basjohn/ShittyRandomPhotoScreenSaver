# Phase 4 Resource Lifetime Map

Date: 2026-07-28
Branch: `main`
Scope: baseline image rotation, transition, compositor upload, display replay, and full lifecycle rebuild

## Ownership map

| Representation | Creation seam | Single owner / retained roles | Release event | Accounting / bound |
|---|---|---|---|---|
| Encoded source file | source/RSS acquisition | filesystem/cache file, not retained as an in-process byte buffer by the display cache | source cache policy or file deletion | disk-only; outside RSS/VRAM |
| Image-worker shared-memory RGBA payload | `load_image_via_worker()` response | temporary `SharedMemory` view copied once into detached `QImage` | view closes immediately; worker owns unlink | transient response size from worker metadata |
| Raw decoded `QImage` | raw prefetch/load | `ImageCache[path]` | exact-byte/count LRU eviction, source reset, or engine-cache replacement | `QImage.sizeInBytes()`; runtime cache hard-clamped to 256 MiB / 32 entries |
| Scaled/cropped `QImage` | async processor or image worker | `ImageCache[transform_key]` | exact-byte/count LRU eviction, source reset, or engine-cache replacement | same CPU cache budget; key includes path, size, mode, quality flags |
| Compute publication DTO | `_ProcessedDisplayImage` | immutable alias of the selected scaled cache `QImage` | task result/callback release | no deep image copy and no GUI object in worker |
| GUI display `QPixmap` | guarded UI callback | one object per unique path/size/mode/DPR transform; exact same-image transforms share it | next image, transition terminal state, display clear, or full teardown | GUI-captured sidecar deduplicates `cacheKey()` backing stores and all retaining roles |
| Display current/previous/seed aliases | `DisplayWidget`, `ImagePresenter` | aliases of GUI `QPixmap`, not independent copies | transition completion clears previous; clear/cleanup clears all | roles recorded without double-counting bytes |
| Pending/deferred transition image | display finish closure / CUSTOM defer | alias of GUI `QPixmap` | callback completion, flush, cancellation, clear, or generation rejection | included in display sidecar roles |
| Compositor base and transition old/new | `GLCompositorWidget` state | aliases of GUI `QPixmap` | terminal presentation/cancellation clears state; base advances to destination | included in display sidecar roles |
| Upload `QImage` and Python bytes | `GLTextureManager.upload_pixmap()` | call-local conversion and contiguous upload bytes | function return | transient; no cache owner |
| Image GL texture | per-display `GLTextureManager` | compositor texture cache plus active old/new pair pins | owner-context LRU eviction, completion/cancel release, or strict compositor cleanup | exact RGBA8 bytes; 128 MiB and 12-entry per-compositor cap; failed delete retains ownership |
| Pixel-unpack buffer | per-display `GLTextureManager` | at most one idle pooled PBO; active upload owns temporary pin | upload release trims pool; strict compositor cleanup deletes remainder | exact allocated capacity; 64 MiB per-compositor idle cap |
| Application FBO/renderbuffer | none in baseline image compositor | none | n/a | exact zero |
| Qt default `QOpenGLWidget` FBO | Qt | Qt/context-owned | surface/context destruction | explicitly `qt_owned_untracked`, never guessed into app bytes |
| Programs, VAOs, VBOs | compositor/geometry/program owners | per compositor/context generation | strict owner-context cleanup | `ResourceManager`; known VBO bytes exact, handle-only objects explicitly unknown |
| CUSTOM/editor snapshots | `CustomLayoutManager` / edit shell | bounded current edit session | edit exit, rebuild, or full teardown | not part of normal image rotation; display deferred payload is included above |
| Widget-local painted caches | widget instance | one current size/style variant per widget | invalidation, resize replacement, or widget cleanup | bounded by widget instance and current geometry; no rotation-indexed accumulation |

## Identity and sharing rules

CPU cache identity is source plus transform: canonical path, target dimensions, display mode, Lanczos/sharpen flags, and pipeline version encoded by the existing key builder. Same-image display processing reuses a result only when target width, target height, display mode, and DPR are all equal. Different transforms remain independent.

Display accounting uses `QPixmap.cacheKey()` to collapse current/previous/seed/presenter/compositor/pending aliases and to collapse the same shared backing across displays. The sampler reads a detached mapping captured on the GUI thread and never touches live Qt image objects.

GL texture identity remains the owning compositor's `QPixmap.cacheKey()` for Phase 4. There is no cross-context/shared texture registry in this phase; Phase 6 owns that work. Active transition pair IDs are protected from eviction until terminal presentation, after which both pins release and the obsolete source becomes immediately evictable.

## Budget policy

- Production CPU cache: configured legacy values are clamped to 64–256 MiB, 2–32 entries, and 1–4 concurrent prefetch requests; missing defaults are 256 MiB / 16 entries / 2 requests.
- Per-compositor texture cache: 128 MiB / 12 entries.
- Per-compositor idle PBO pool: one entry, at most 64 MiB.
- The Phase 4 pressure harness deliberately uses tighter 96 MiB CPU, 96 MiB texture, and 40 MiB PBO budgets.
- A resource may exceed a cache cap only while it is an active transition pin or when one formula-adjusted frame itself exceeds the provisional cap. It must become evictable at terminal presentation and must return to zero at full teardown.

No cache budget may be raised to conceal unexplained RSS/VRAM. Driver-reported VRAM remains a platform measurement; exact application-owned GL bytes are the deterministic gate here.