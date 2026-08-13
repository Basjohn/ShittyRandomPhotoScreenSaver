# Compositor Architecture

Last updated: 2026-08-13

Current target architecture for fullscreen presentation. `main` is the implementation
authority; historical candidates exist only as negative controls/reference.

## 1. Ownership

### Runtime coordinator
Owns full start/stop/recreate sequencing and generation admission. Does not own visualizer simulation or GL internals.

### Image pipeline
Owns source selection, decode/transform, bounded CPU cache and worker-safe upload-ready data. Does not own textures/QPixmap/compositor state.

### Visualizer model/controller
Owns audio/event integration, mode logical state and authoritative source/state cadence. Publishes current immutable render state.

### Display compositor
Owns one display's presentation surface/context, GL draw order, local transition animation and presentation requests. Does **not** own visualizer simulation/cadence, workers, image selection or lifecycle admission.

### GL resource owners
Own exact handles/bytes/context generation/deletion. One numeric handle has one deletion owner.

## 2. Current Phase 5 Reality

Do not start a surface merge yet. Current evidence shows:

- GUI request age dominates paint duration;
- `set_processed_image()`/`generic_pair_warm` are large GUI/context transactions;
- retained-current/next-old identity is closed at the display-owned DPR handoff and in a current live repeated-transition run;
- visualizer and shared-compositor GPU draw spans are now separated by owner;
- screen 1 is 60 Hz while visualizer overlay state/update/paint windows can approach ~100 Hz.

Fix/attribute those owners first.

The `08_13_5bf68d6b_17_00_17_04_compositor_gpu_typical` capture shows active
transition shaders are normally cheap, including roughly `3.1–3.4 ms` p95 on the
physical-4K display. Sparse steady/base draws instead repeatedly cost `36–41 ms` there
because idle presentation re-entered the full-surface QPainter pixmap path. When the
terminal destination texture is retained under exact identity, idle presentation now
draws that same texture through the existing fullscreen program; no paint-time upload or
new cadence owner is introduced.

## 3. Data Flow

```text
audio/events -> visualizer logical owner -> immutable current RenderState ------image source -> decode/transform -> GUI upload/texture owner -> base/transition --+-> display compositor -> paint
widgets/overlays -> prepared current UI state ----------------------------------/
```

There is no ordinary return arrow from paint to a producer.

## 4. Logical Cadence vs Presentation

Logical visualizer state evolves at its approved authored/source boundaries.
Presentation is a consumer opportunity.

A late/missed paint may skip intermediate immutable render snapshots after logical
integration. It may not drop events, change dt, slow source sampling, trigger catch-up
simulation or acknowledge the producer.

Phase 7 will formalize this boundary. Phase 8 may then remove a separate visualizer GL
surface/context if GPU/context evidence justifies it.

## 5. Texture Identity

Current texture retention must use a stable identity that survives terminal handoff into
the next old-image lookup under unchanged source/transform/size/context generation.
Steady transition target: old cache hit + new upload only.

Terminal steady presentation target: exact retained destination texture draw, without a
second QPainter full-surface pixmap path. Missing cache or unavailable GL may use the
existing QPainter fallback and must not upload speculatively from paint.

`DisplayWidget` is the live DPR owner. `ImagePresenter` consumes that value and must not
apply an independent stale DPR or otherwise mutate an unchanged terminal pixmap after
its texture has been retained. Focused automation covers the full presenter/manager
handoff and the old-hit/new-only-upload result.

Do not solve identity failure through larger caches or retaining historical image sets.

## 6. Transition Model

Transition owner keeps source/destination, monotonic start/duration/easing and required
temporary resources. Completion is local/exactly-once: destination becomes base; source
and temp transition ownership releases; no worker/image-pipeline terminal acknowledgement.

## 7. GPU Timing

All transition families share the same paint-timing seam. Ordinary `--perf` records CPU,
frame and delivery evidence without creating OpenGL query handles or calling query
availability/begin/end APIs. The explicitly heavier `--gpu-timing` profile implies
`--perf`, samples one in eight existing paint observations and collects available results
without waiting. It reports observed/sampled-out/poll/submission/result coverage and owns
all handles on the exact compositor context. `glFinish()` is prohibited. Correlate these
samples with process GPU busy, texture uploads and event-loop/request age, but never use
the query path as presentation or cadence control flow.

## 8. GL Ownership

All GL mutation/deletion on the owner GUI/context thread. No worker QPixmap/GL. No GL
under registry locks. Context generation is part of identity. Failed deletion retains
ownership and fails closed.

## 9. Lifecycle

Settings/Edit full stop–destroy–recreate is solved architecture and remains mandatory:
stop/reject producers, delete GL under owner context, prove zero retired ownership,
construct replacement, reveal only fresh current-generation authoritative state.

## 10. Future One-Surface Design

One compositor surface **per display** is an optional Phase 8 target only after:

- Phase 5 GUI starvation and texture reuse work;
- truthful GPU owner attribution;
- stronger visualizer temporal/paint-receipt goldens;
- Phase 7 proof that missed paints do not change logical state.

The compositor may absorb presentation surfaces/draw order, never simulation/cadence,
worker scheduling, settings lifecycle or source selection.
