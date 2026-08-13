# 06 — Presentation and Compositor Design

Last reconciled: 2026-08-13

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

The corrected-query `08_13_fa7e8196_16_33_16_37_gpu_queries_typical` run now
attributes the visualizer surface itself. Bubble's normal overlay GPU p50/p95 is roughly
`0.35–0.46/0.43–0.53 ms`; Spectrum is roughly `0.009–0.012/0.013 ms`. Both retain
roughly `0.9–1.25 ms` CPU paint medians, yet the run still contains `40–130 ms`
delivery gaps. Process GPU-busy peaks align more strongly with transition windows, so a
matching non-blocking timer-query ring now wraps the existing shared-compositor draw and
awaits a transition-heavy live gate.

The `08_13_5bf68d6b_17_00_17_04_compositor_gpu_typical` run closes that live gate for
seven exercised transition families. All `42` compositor windows are supported and
error/drop free. Active transition p95 is roughly `0.87–1.02 ms` on screen 0 and
`3.13–3.38 ms` on the physical-4K screen 1; whole-process GPU busy is only `4.55%`
median and `5.1%` max. The surprising owner is sparse idle/base presentation:
QPainter full-pixmap draws repeatedly measure `7–12 ms` and `36–41 ms` respectively.
The current slice therefore reuses the exact retained destination texture through the
already-compiled fullscreen program and leaves presentation cadence untouched.

The follow-up `08_13_2cb15ae4_17_17_17_20_retained_base_typical` capture validates the
replacement. Outside first-frame/recreation outliers, steady compositor GPU draw is
about `0.03–0.10 ms` on both displays; ordinary transitions retain old exactly and upload
only new, and teardown returns compositor GL ownership to zero. The remaining
transition-boundary kick is therefore not a steady-base or transition-shader cost.
GUI-owned image installation is normally `18–33 ms` and can be much longer during
recreation, so Phase 7 state/presentation decoupling cannot by itself unblock the
visualizer timer while that shared GUI transaction is running.

The next typical-load phase split shows why presentation decoupling is still not the
first correction. Ordinary physical-4K texture submission itself is about `0.482 ms`
median, while QPixmap image preparation plus source copying is about `11.689 ms` median.
The current upload slice removes the proven native-format conversion and Python bytes
clone while retaining one GUI/context-owned PBO copy. It does not add another surface,
clock, texture identity or presentation acknowledgement. Cold context/PBO staging and
pair-warm residual remain separately attributable before any Phase 7 prototype.

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

That target is not yet sufficient for Bubble. The protected temporal trace contains a
visible response that lasts one `100 Hz` logical publication; a phase-valid `60 Hz`
latest-state sample can miss it completely. Phase 7 must therefore define an
edge-preserving render-state contract, or otherwise prove equivalent authored
visibility, before enabling coalescing for Bubble. Logical-series equality by itself is
not acceptance.

Phase 7 is an option, not a required cap. The measured overlay GPU span is already
sub-millisecond, so the marginal saving must be re-measured after higher-value compositor
and delivery fixes. If a later prototype is justified, it is a display-owned consumer:
logical integration continues unchanged, producer admission never depends on paint, and
Bubble requires bounded event identity/history (or an equivalent edge-preserving state)
so a skipped snapshot cannot erase authored attack. Modes may remain uncoalesced when
that proof is absent.

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

The rejected overlay cap was not actually display scheduled. Its elapsed-time threshold
accepted a `100 Hz` producer every second tick (`~50 Hz` for a nominal `60 Hz` target),
then a pending-until-paint latch made late Qt delivery an admission gate and produced the
observed `~39–40 Hz`. `QOpenGLWidget.paintGL()` completion is neither scanout nor a
stable physical-present opportunity. Producer-timestamp gates and paint acknowledgements
are therefore prohibited as Phase 7 presentation clocks.

The overlay now has the first passive attribution seam: CPU paint/state-to-paint
windows plus a fixed non-blocking owner-context GPU query ring. It measures the Qt FBO
clear/render span and does not claim SwapBuffers, composition or physical scanout.
Unsupported, pending, dropped and discarded samples remain explicit. A current live
capture first proved the fail-closed path instead of GPU cost: PyOpenGL 3.1.10 raised a
wrapper-side `KeyError` while retrieving `GL_QUERY_RESULT`. The helper now supplies the
native uint64 output buffer explicitly and a real offscreen GL-context regression proves
submission/collection/deletion. The corrected-query typical run then collected supported
samples in all `26` overlay windows with no errors or drops and bounded pending handles;
the measured costs are recorded above. Logical cadence remains protected.

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
