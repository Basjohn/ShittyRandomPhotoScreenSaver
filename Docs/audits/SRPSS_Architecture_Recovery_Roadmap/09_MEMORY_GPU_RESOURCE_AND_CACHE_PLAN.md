# 09 — RAM, Commit, VRAM, GPU Resource, and Cache Plan

Last reconciled: 2026-08-08

## Current conclusion

The project has corrected several known monotonic leaks and can return tracked GL ownership to zero during full display teardown. That is necessary but not sufficient.

Latest active installed evidence reports approximately:

```text
whole-app resident RAM:   847–1074 MiB
whole-app private commit: 2.86–3.17 GiB
dedicated VRAM:           554–777 MiB
shared GPU memory:        84–121 MiB
```

This is too heavy for a screensaver even when the values plateau.

The project now has two independent resource gates:

1. **containment:** no monotonic growth across image/lifecycle cycles;
2. **absolute efficiency:** warm steady-state usage must fall to an evidence-backed reasonable level.

## Metric definitions

Do not combine or confuse these measurements:

- **RSS / working set:** pages currently resident in physical system RAM;
- **private working set:** resident pages not shared with other processes, where measurable;
- **private commit / private bytes:** committed private virtual memory backed by RAM and/or pagefile; it is not additional physical RAM to add on top of RSS;
- **VMS/reserved/mapped address space:** virtual mappings/reservations that may not be committed or resident;
- **child process RSS/commit:** ImageWorker or other process ownership, reported separately and in whole-app totals;
- **dedicated VRAM:** GPU-local memory attributed by the driver/tool;
- **shared GPU memory:** system RAM mapped/used by GPU work;
- **tracked logical bytes:** application ownership estimates; useful but not identical to physical/driver accounting.

Every official report must state exactly which metric a value represents.

## Current evidence interpretation

The latest Settings comparison showed:

- the old approximately linear per-cycle Settings staircase did not reproduce across two replacements;
- a one-time post-first-recreation uplift remained;
- tracked resources, handles, and threads did not add another step on the second cycle;
- dedicated VRAM fell near idle-driver levels while the display runtime was absent;
- substantial process RAM/commit remained even without active display GL ownership.

Cause of the one-time uplift and absolute residual footprint is below 90% confidence. Do not label it allocator, driver, Qt, cache, or leak without attribution evidence.

R-53 is repaired mechanically. Edit plateau conclusions remain blocked until the repaired path passes installed dual-display Save-and-Continue and alternating lifecycle validation.

## Provisional engineering targets

For the current dual-2560×1440 environment, use these as investigation/acceptance targets, not immutable laws:

### Whole-app resident RAM

- preferred warm steady state: **under 600 MiB**;
- warning/investigation: **750 MiB**;
- hard unresolved gate: **900 MiB**.

### Dedicated VRAM

- preferred warm steady state: **under 300 MiB**;
- warning/investigation: **400 MiB**;
- hard unresolved gate: **500 MiB**.

### Private commit

- no unexplained multi-GiB commitment;
- separate main and child commitment;
- identify reserved/mapped regions, thread stacks, allocator arenas, shared-memory mappings, Qt/native allocations, and driver mappings before revising the target.

Targets may be revised only through a decision record containing identical-scenario measurements, ownership explanation, fidelity result, and user-visible consequence.

## Fidelity and attribution rule

No resource target may be met by reducing:

- visualizer cadence/source sampling or mode behaviour;
- target/display texture resolution or precision;
- image scaling/crop quality;
- transition quality/duration;
- artwork, shadows, widget content, animation, or first-frame responsiveness.

Aggregate visualizer memory/CPU is presumed shared/runtime-owned until direct evidence proves a mode-specific owner. Bubble is not a default resource target.

## Required process-level attribution

For controlled equivalent scenarios, break down:

- main process RSS/private working set/private commit/VMS;
- each child process RSS/private commit/VMS;
- Python traced allocations by owner where useful;
- Qt QObject/widget/image/pixmap ownership where safely observable;
- thread count and reserved/committed stack contribution;
- mapped files/DLLs/shared-memory regions;
- CPU image cache logical and tracked bytes;
- live QImage/QPixmap/display representations;
- GL texture/FBO/PBO/program/buffer logical bytes;
- dedicated/shared GPU memory;
- process handles/GDI/USER objects;
- pending tasks/futures/callback closures;
- logging buffers and diagnostics history;
- allocator/native high-water behaviour under quiescence and pressure.

Measure with identical displays, DPR, image sources, cache warmup, transition set, widgets, duration, entry point, and visualizer input/state.

## Resource ownership record

For every application-owned representation, record where applicable:

```text
stable identity
kind
owner and owner class
runtime/context/source generation
source/transform/DPR/quality identity
dimensions/format
logical byte size
physical/allocation size where available
lease/pin/reference state
created/last-used timestamps
retirement reason
```

Count-only limits are insufficient.

## CPU representations

Audit and avoid unnecessary simultaneous retention of:

- encoded source bytes;
- decoded source image;
- orientation-corrected image;
- crop/scale variants;
- upload/staging bytes;
- QImage and QPixmap aliases/copies;
- per-display duplicates;
- thumbnails/previews/artwork;
- deferred/previous/fallback frames;
- worker/shared-memory transfer buffers.

Implicit sharing is not assumed to eliminate physical copies; verify detach/copy behaviour.

## GPU representations

Audit:

- base/source/destination textures;
- transition and visualizer FBOs;
- intermediate effect buffers;
- upload/PBO staging;
- overlay/widget textures;
- shader/program/geometry buffers;
- retained fallback/previous frames;
- per-display duplicates and driver-created backing.

A 2560×1440 RGBA8 buffer is roughly 14.06 MiB. Formula-driven expected ownership should explain most application-created live bytes even though driver accounting includes additional overhead.

## CPU cache policy

Current production CPU-cache limit remains 256 MiB unless evidence proves a different value is necessary.

Requirements:

- exact byte budget plus item cap;
- stable source/transform/DPR/quality keys;
- immutable entries;
- deterministic eviction/clear;
- no worker-created QPixmap;
- no stale generation repopulation;
- no raw source release while scaled derivatives still own it;
- pending count and future scaled bytes independently bounded.

Do not raise the cache merely to hide misses, fallback noise, or process memory.

## Prefetch policy and R-57

Prefetch must be bounded by:

- active concurrency;
- pending request count;
- future logical bytes;
- generation;
- stable key ownership.

R-57 proves that selection priority and positional deletion order were conflated. Multi-item removal must use stable identity/partitioning or explicitly descending unique numeric indices.

The repair must preserve preferred-path priority, raw-source derivative lifetime, exact pending keys/bytes, generation rejection, and no duplicate dispatch.

## GPU ownership/store policy

Current per-compositor resource owners remain valid until evidence justifies a future shared store.

Any future store must:

- be metadata-first and byte-bounded;
- use explicit leases;
- identify exact deletion owner and context/share generation;
- perform no GL calls under registry locks;
- delete on owner thread/context;
- invalidate old-context entries;
- never let two local owners delete the same numeric handle.

A shared store is not automatically a memory improvement; prove actual active-VRAM reduction and lifecycle simplicity.

## Upload/copy path

Target the fewest necessary representations without changing output.

Investigate chains such as:

1. decode;
2. copy to bytes;
3. hash whole buffer;
4. copy into payload/shared memory;
5. copy into QImage/upload buffer;
6. copy into PBO/texture.

Remove only proven redundant copies. Preserve Windows shared-memory handle lifetime and exactly-once cleanup.

## Transition and display resources

During a normal transition, only the required base/source/destination and documented temporary effect resources remain owned.

All completion/cancel/interruption/resize/Settings/Edit/topology paths release obsolete pins, textures, PBOs, FBOs, and previous frames exactly once.

After full display teardown:

- tracked display/GL ownership reaches zero before surfaces disappear;
- dedicated VRAM should approach idle-driver baseline after sampling delay;
- residual process RAM/commit is still investigated separately.

## Visualizer resources

Question and account for every visualizer:

- CPU state/buffer;
- immutable snapshot;
- per-display conversion;
- VBO/VAO/texture/FBO;
- retained/prewarm/fallback/double buffer.

Do not assume Bubble is responsible for shared visualizer resources. Do not remove a buffer or lower precision/resolution without proving identical visible output and approved behaviour.

## Lifecycle interaction

R-53/R-56 must close before final lifecycle memory slopes are trusted.

For every Settings/Edit cycle record:

- pre-stop warm state;
- zero-owner teardown checkpoint;
- dialog/edit-session checkpoint;
- replacement settled state after fixed warmup;
- exact runtime and display/visualizer mode;
- RSS/private working set/private commit/VMS;
- main/child split;
- dedicated/shared GPU memory with sample age;
- handles/threads/resources/tasks/subscriptions.

Do not compare early cold Spectrum against later warm Bubble and call the delta a leak or optimization.

## Required tests

### Controlled warm baseline

Fixed source set, displays, DPR, widgets, transition, visualizer input/mode, cache state, duration, and diagnostics.

### Plateau

Post-warmup image cycling and stable-state slopes for RSS/private commit/VRAM/tracked bytes/handles/threads.

### Churn

Alternate large/small images, aspect ratios, transitions, route changes, and cache pressure; prove old sizes release.

### Lifecycle

After R-53/R-56 repair, at least five alternating installed cycles for current Phase 5, followed by the larger release matrix.

### Pressure

Conservative cache/resource pressure without decode storms, visible quality loss, first-frame failure, or visualizer degradation.

### Quiescent teardown

No display runtime: verify tracked zero ownership, driver VRAM fall, and characterize residual main/child RSS/commit.

## Leak/footprint triage order

When whole-process usage exceeds tracked bytes:

1. verify scenario/warmup/sample age equivalence;
2. split main/children and resident/commit/mapped metrics;
3. inspect live application representations and queues;
4. inspect Python and Qt ownership;
5. inspect native/allocator regions and thread stacks;
6. inspect mappings/shared memory/DLL/driver state;
7. inspect deleted-but-pending GL/Qt objects;
8. test whether pressure reclaims pages without explicit trimming;
9. name uncertainty honestly when ownership remains below 90% confidence.

Do not increase budgets or add trimming/recycling to conceal unexplained usage.

## Phase acceptance

Memory/resource work passes only when:

- equivalent scenarios show no monotonic growth;
- absolute warm RSS/private commit/VRAM fall materially and meet or have an approved explanation against provisional gates;
- tracked/untracked gaps are documented by owner/category;
- full teardown reaches zero retiring application ownership;
- no fidelity/cadence/quality trade was used;
- normal and Media Center variants pass;
- the user reports no visual regression.
