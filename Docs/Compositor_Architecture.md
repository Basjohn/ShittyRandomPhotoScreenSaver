# Compositor Architecture

Last updated: 2026-07-26

Target architecture and recovery contract for fullscreen presentation.

This document replaces the failed donor implementation as architectural authority. It does not describe `7376bb9` as the desired system.

## 1. Evidence and Git Boundary

Behavioural/lifecycle base:

```text
main (based on baseline)
00edb57a3076b845cb8ee4b6cb7f36ea83411f0c
```

Donor/reference:

```text
donor-7376bb9
7376bb9bb380253f3bd14079e65d7bdbca062fad
```

Evidence:

```text
logs/evidence_chest/logs00edb57.zip
logs/evidence_chest/logs7376bb9.zip
```

The donor branch remains intact, reference-only/read-only, and is never merged wholesale. Phase 1 measurement evidence is archived in `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.

## 2. Runtime Conclusions

### Baseline strengths

- better perceived visualizer smoothness;
- better Spectrum/Bubble feel;
- safer Settings/Edit lifecycle in supplied evidence;
- simpler presentation topology.

### Baseline failures

- high CPU and task rate;
- excessive RAM/private commit;
- severe VRAM growth;
- degraded smoothness under heavy background load;
- weak resource-lifetime accounting.

### Donor strengths

- more explicit resource accounting;
- more bounded VRAM behaviour;
- useful GL ownership tests and diagnostics;
- proof that single-surface composition is possible.

### Donor failures

- visualizer flattening and loss of elasticity;
- microgaps and burst delivery;
- cursor/UI choppiness;
- producer dependence on compositor paint acknowledgement;
- distributed transition/lifecycle state;
- partial reconstruction and GL affinity crash;
- high CPU with low GPU use;
- implementation complexity that prevents reliable diagnosis.

## 3. Target Ownership

### Runtime coordinator

Owns complete start/stop/recreate order.

Does not own simulation or GL details.

### Image pipeline

Owns source selection, decode, transform, bounded CPU cache, and immutable upload-ready data.

Does not own textures, compositor state, or QWidget mutation.

### GPU resource store

Owns texture/FBO/PBO metadata, exact bytes, context/share generation, leases, and deletion scheduling.

Does not own image sequence, transition, visualizer, or application lifecycle.

### Visualizer controller/model

Owns audio integration, mode simulation, logical cadence, and latest immutable render state.

Does not own compositor timing or GL lifecycle.

### Transition controller

Owns source, destination, start, duration, easing, and local completion.

Does not own worker threads or image decode.

### Display compositor

Owns one display surface, GL draw order, latest scene snapshot, and local animation repaint requests.

Does not own simulation, worker scheduling, Settings/Edit lifecycle, or image selection.

## 4. Data Flow

```text
audio/input
    -> visualizer model
    -> immutable latest VisualizerState
                                  \
image source -> decode/transform -> UploadDescriptor
                                  -> GPU resource store -> TextureLease
                                                        \
transition state ----------------------------------------> SceneSnapshot
visualizer state ----------------------------------------> SceneSnapshot
overlay state -------------------------------------------> SceneSnapshot
                                                         |
                                                         v
                                                display compositor
                                                         |
                                                         v
                                                       paint
```

There is no ordinary return arrow from paint to a producer.

## 5. Scene Snapshot

A scene snapshot contains explicit immutable references:

```text
SceneSnapshot
- runtime/context generation
- display geometry and DPR
- base texture lease
- optional transition snapshot
- optional visualizer state
- overlay state
- scene generation
```

Scene generation identifies replacement of the latest scene. It is not a paint acknowledgement.

## 6. Presentation Model

When producer state changes:

1. update immutable logical/render state;
2. replace latest scene;
3. coalesce one GUI `update()` request;
4. return immediately.

At paint:

1. clear GUI-local pending-update state;
2. read latest scene;
3. draw;
4. request another GUI-local frame only if compositor-local animation remains active;
5. if state changed during paint, coalesce one additional update.

No worker waits.

No catch-up burst is emitted.

## 7. Clock Separation

Separate clocks:

- visualizer simulation;
- transition monotonic elapsed time;
- Qt presentation.

A late paint draws current state.

A late paint does not:

- pause visualizer simulation;
- alter attack/decay;
- create repeated fixed-step catch-up visible states;
- authorize a queue of repaint retries;
- require a producer acknowledgement.

## 8. Transition Model

```text
TransitionSnapshot
- source lease
- destination lease
- start monotonic timestamp
- duration
- easing
```

At completed paint:

- destination becomes base;
- source transition lease releases;
- temporary transition resources release;
- transition becomes inactive.

This state is local to the compositor/transition owner.

Remove:

- terminal transaction queue;
- post-paint completion acknowledgement;
- wrapper/compositor busy-state handshake;
- image-pipeline terminal commit handshake;
- generation-per-frame terminal machinery.

## 9. Visualizer Integration

Use a narrow renderer boundary:

```text
VisualizerModel/Controller
    -> immutable VisualizerState

VisualizerRenderer
    -> draw(state, viewport, resources)
```

Do not preserve a widget-shaped compositor layer.

Remove:

- dynamic attribute forwarding;
- compatibility local-attribute registries;
- duplicated old/new renderer state;
- compositor-owned visualizer timers;
- retry paths that silently switch surface architecture.

The visualizer state must preserve baseline feel through deterministic replay and manual review.

## 10. GL Ownership

All GL work occurs on the owner GUI/context thread.

Every native resource records:

- type/id;
- owner;
- byte size;
- context/share group;
- runtime/context generation;
- lease/reference count;
- creation and deletion reason.

Deletion is explicit and exactly once.

No GL call occurs under a resource-registry lock.

No numeric handle is trusted across context recreation.

## 11. Settings/Edit Lifecycle

Default lifecycle:

1. close admission;
2. stop producer publication;
3. stop GUI timers;
4. disconnect callbacks;
5. cancel/drain worker work;
6. reject late old-generation results;
7. make valid contexts current;
8. destroy visualizer/transition/resource-store GL objects;
9. destroy compositor surface last;
10. assert no old-generation resource;
11. create new runtime/context generation;
12. reconnect and restart.

Phase 3 implementation boundary (2026-07-28):

- `engine.engine_lifecycle.teardown_display_runtime()` is the coordinator-owned full-stop seam;
- `DisplayManager.cleanup()` retains any display whose explicit cleanup fails;
- `DisplayWidget.cleanup_runtime()` stops child producers and visualizer overlays before compositor deletion;
- `GLCompositorWidget.cleanup()` verifies GUI thread/current context and reports `DESTROYED` only after strict texture/PBO/program/buffer deletion;
- deferred GL warmups are compositor-lifecycle-generation guarded;
- engine delayed/image callbacks require runtime generation plus exact display-manager identity.

Partial reinitialization is deferred until a separately approved design proves it safe and worthwhile.

## 12. Image and Upload Path

Target one owned upload-ready representation.

Avoid:

- worker `QPixmap`;
- visible-paint conversion;
- repeated full-buffer copies;
- whole-buffer SHA-256 in normal path;
- UI waits on upload/fence completion.

Normal identity uses:

- canonical source id;
- source version/mtime/size;
- transform/crop;
- target dimensions;
- format;
- pipeline version.

## 13. Resource Budgets

All CPU and GPU caches are byte-bounded.

For the current dual-1440p environment:

- investigate application-owned GL allocations above roughly 500 MiB;
- investigate RSS above roughly 900 MiB;
- reject monotonic image-cycle or lifecycle-cycle growth.

Tracked resources must explain the expected working set.

## 14. CPU and Task Model

Do not submit a general task per display frame.

Reduce:

- tiny recurring jobs;
- callback cascades;
- duplicate per-display simulation;
- state copying;
- logging allocations;
- work while hidden/static.

Use measured vectorized/native GIL-releasing work for real numeric hotspots.

Thread count is not a success metric.

## 15. Donor Extraction

### Reconstruct selectively

- resource byte accounting;
- explicit leases;
- share-group verification;
- immutable worker/render boundaries;
- GL affinity assertions;
- stale-generation rejection;
- passive performance metrics.

### Discard

- adaptive timer;
- paint acknowledgement;
- compositor-cadence starvation state;
- terminal transactions;
- partial Settings/Edit reinit;
- compatibility mega-layer;
- broad forwarding;
- hot-path full-buffer hashing;
- scattered retry/fallback state.

## 16. Required Gates

### Visualizer

- deterministic replay;
- Spectrum shape/reactivity;
- Bubble elasticity;
- irregular-presentation equivalence;
- manual review.

### Lifecycle

- repeated Settings;
- repeated Edit;
- mixed cycles;
- active transition/visualizer cycles;
- zero GL affinity errors;
- zero old-generation resources.

### Frame pacing

- p50/p90/p95/p99/max;
- no average-only acceptance;
- cursor/overlay smoothness;
- no repeated idle 100+ ms gaps.

### CPU/task

- materially below both evidence versions;
- task categories measured;
- no one-core saturation in ordinary use;
- no task per paint.

### RAM/VRAM

- stable plateau;
- exact tracked bytes;
- no image-cycle staircase;
- no lifecycle-cycle accumulation.

## 17. Prohibited Until Recovery Completion

- partial GL recreation;
- speculative warmup architecture;
- silent legacy renderer;
- second visualizer surface as automatic fallback;
- producer-to-paint handshake;
- new presentation service with paint acknowledgements;
- another terminal transaction;
- new quality reduction;
- donor wholesale cherry-pick/merge.

## 18. Work Order

Follow `Current_Plan.md`.

Do not begin single-surface reconstruction before:

- measurement;
- visualizer fidelity lock;
- lifecycle safety;
- baseline memory containment;
- CPU/task reduction.

The architecture is accepted only when runtime evidence is better than both supplied versions.
