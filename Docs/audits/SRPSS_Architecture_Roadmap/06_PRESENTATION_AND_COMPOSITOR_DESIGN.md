# 06 — Presentation and Compositor Design

Last reconciled: 2026-08-11

## Design Objective

Provide predictable display-local presentation while keeping simulation/source cadence,
lifecycle, worker scheduling and resource policy in their correct owners.

Phase 5 is still reducing proven GUI starvation and texture/GPU waste. Phase 7 owns the
state/presentation boundary. Phase 8 may then consider one compositor surface per
display if measured GPU/context benefit justifies it.

## Current Readiness Evidence

Do **not** begin the Phase 8 surface merge yet.

Current evidence says:

- request age, not paint cost, dominates frame gaps;
- `set_processed_image()` and `generic_pair_warm` are large GUI/context transactions;
- the retained-current/next-old DPR identity defect is closed in automation and a current live repeated-transition run (`20/20` steady old hits with one new upload);
- process GPU busy is material but not yet split by owner;
- visualizer screen 1 is 60 Hz while the current typical-load run measures Bubble
  state/update/paint medians of `89.75/89.75/87.05` per second and Spectrum medians of
  `92.7/92.7/91.15` per second, without geometry changes.

The last point motivates Phase 7 presentation separation, not a logical cadence cap.

## Absolute Rules

- producers do not wait for `paintGL()`, `update()` or a presentation acknowledgement;
- paint is not a simulation/smoothing clock;
- compositor does not own Bubble/Spectrum source/tick cadence;
- no catch-up replay of missed immutable render snapshots;
- no self-requested visualizer repaint loop;
- no worker GL/QPixmap mutation;
- local transition continuation may request frames only for animation the compositor actually owns;
- no hidden alternate presentation path or compatibility mega-layer.

## Phase 7 State / Presentation Boundary

Target shape:

```text
audio/events/source
        |
        v
visualizer logical/model owner  -- current authoritative cadence --> immutable RenderState
                                                               |
                                                               v
                                                   latest valid state slot
                                                               |
                                                Qt/display opportunity
                                                               v
                                                         paint latest
```

If ten presentation opportunities are missed, logical state must evolve exactly as it
would have otherwise. The next paint consumes the latest valid generation/activation
state; it does not replay ten intermediate snapshots or ask the producer to catch up.

## Presentation-Rate Attribution

For each display record together:

- detected refresh/route/DPR;
- logical visualizer state publication rate;
- overlay `set_state` rate;
- `update()` request rate;
- `paintGL()` rate and intervals;
- source/state age at paint;
- GPU timer-query samples and process GPU busy;
- transition state and image-upload activity.

A rate above physical refresh is evidence to investigate, not proof that the logical
producer should be slowed.

The overlay now has the first passive attribution seam: CPU paint/state-to-paint
windows plus a fixed non-blocking owner-context GPU query ring. It measures the Qt FBO
clear/render span and does not claim SwapBuffers, composition or physical scanout.
Unsupported, pending, dropped and discarded samples remain explicit. A current live
capture first proved the fail-closed path instead of GPU cost: PyOpenGL 3.1.10 raised a
wrapper-side `KeyError` while retrieving `GL_QUERY_RESULT`. The helper now supplies the
native uint64 output buffer explicitly and a real offscreen GL-context regression proves
submission/collection/deletion. Runtime owner windows must still validate GPU samples
and teardown before Phase 7 policy work. The same capture measures Bubble/Spectrum
CPU-paint p95 window medians around `1.52/1.41 ms`; logical cadence remains protected.

## GUI-Local Update Coalescing

A GUI/display owner may keep a single pending-update boolean/generation only for request
deduplication. It cannot acknowledge logical frames or backpressure producers.

## Scene Ownership

Each display eventually owns:

- one presentation surface/context if Phase 8 is accepted;
- viewport/DPR/display identity;
- current base/transition resources;
- latest immutable visualizer render state;
- overlays/widgets in explicit draw/stack order;
- GUI-local update-coalescing state.

Global controllers may publish shared logical state, not display-local geometry or
presentation ownership.

## Transition Model

Transition state is local and monotonic-time based. Completion is exactly once:
destination becomes base, obsolete source/temp resources release, transition becomes
inactive. No image-worker/pipeline terminal acknowledgement is required.

## GPU Profiling Boundary

Before Phase 8, every transition family needs truthful paint/GPU timing from a shared
compositor seam. Use non-blocking timer queries and delayed result collection. Never use
`glFinish()` in ordinary profiling. Zero GPU time is meaningful only with support/sample
counts proving it was measured.

## Phase 8 Acceptance Prerequisites

- Phase 5 external GUI starvation materially reduced;
- texture identity/reuse corrected;
- stronger Bubble/Spectrum temporal/paint-receipt goldens pass;
- Phase 7 proves logical state is independent of paint opportunity;
- GPU/context evidence shows the second visualizer surface/context is a material owner;
- one-surface-per-display design does not absorb simulation, scheduling, lifecycle or source selection.
