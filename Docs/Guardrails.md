# SRPSS Guardrails

Last updated: 2026-08-18

Durable cross-cutting stop rules. `Current_Plan.md` owns active sequencing. Focused guardrails
may be stricter for their domain.

## 1. Priority

1. visualizer fidelity/reactivity;
2. lifecycle/GL safety;
3. frame pacing/perceived smoothness;
4. multi-display correctness;
5. bounded RAM/VRAM;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

Never improve a counter by silently lowering visualizer/source cadence, transition/image quality,
overlay behaviour or display support.

## 2. Read / Scope Discipline

For active architecture work read exact `main`, `Current_Plan.md`, the current owner in
`Docs/Contracts.md`, this guardrail and one focused guardrail. Do not treat old phase reports or
historical incidents as current owner maps.

Changing more than one long-lived timer/thread/queue/context/generation/fallback/state machine in
a slice requires explicit architecture justification and a statement of what existing mechanism
is removed.

## 3. Immediate Stop Conditions

Stop/reassess when:

- Bubble/Spectrum/another visualizer becomes less reactive/smooth/elastic/correct;
- source age rises while the visualizer keeps moving;
- p99/max delivery worsens despite prettier averages;
- a producer/presentation deadline waits for paint;
- a context/thread-affinity error appears;
- cleanup requires retries, force-clear, nested event pumping or hide-only reuse;
- resources grow monotonically or ownership cannot be explained;
- a fallback silently changes behaviour/render owner;
- tests pass while the known installed failure remains;
- a fix needs another presentation surface/clock merely to preserve old plumbing.

## 4. Repository / Documentation Stability

- edit existing canonical paths in place;
- never rename/move existing paths without explicit user instruction;
- stable contracts live in Spec/Guardrails/focused docs;
- active work lives only in `Current_Plan.md`;
- volatile benchmark detail lives in phase reports;
- historical incidents/old phase reports are evidence scoped to their named date/commit and may
  contain intentionally obsolete class names/architecture.

## 5. Ownership

One mutable concern, one owner. Current examples:

- runtime lifecycle: engine/runtime coordinator;
- topology: one engine/display-manager decision owner;
- settings: SettingsManager/store owners;
- visualizer logical state: visualizer subsystem;
- physical presentation: each display compositor;
- transition state: compositor/transition owner;
- GL deletion: explicit context/resource owner;
- accounting: ResourceManager, never deletion fallback.

Do not create shadow settings/task/transition/descriptor/lifecycle/render frameworks.

## 6. Presentation / Compositor

### Current architecture

- one accelerated `QRhiWidget.Api.OpenGL` compositor surface per physical display;
- no separate presented Spotify visualizer surface;
- visualizer card + shader are layers inside the display compositor;
- visualizer logical/source cadence remains independent from physical presentation;
- one display-local presentation strategy owns physical frame opportunities for all reasons that
  keep that scene live.

### Adaptive render strategy

`AdaptiveRenderStrategyManager` / its timer is permitted as the **display's physical
presentation strategy**. It may not become visualizer simulation/source cadence.

R-61/R-62 prohibit reusing a transition-scoped timer to pace a separate visualizer presentation
surface/deferral path. They do not require a second visualizer clock after presentation has been
merged into the display compositor.

### Admission

Allowed:

- one cross-thread dispatch-pending guard that prevents duplicate queued GUI callbacks until the
  queued callback actually executes and calls `QWidget.update()`;
- passive request/dispatch/paint timing metrics.

Forbidden:

- pending-until-paint admission;
- paint/swap acknowledgement/backpressure;
- producer timestamp/display-rate divisor gate;
- scheduler release by paint;
- render-callback self-scheduling/requeue loop;
- repaint rescue timer;
- catch-up bursts;
- source/event/logical cadence reduction;
- second visualizer presentation timer/surface.

Qt may coalesce repeated `QWidget.update()` calls after GUI dispatch. Paint is a consumer, not an
admission token.

Render callbacks may draw, compute local transition progress and record passive metrics. They do
not own visualizer simulation, source analysis, lifecycle teardown or their own recurring
presentation loop.

## 7. Visualizer Safety

Protect attack, amplitude, decay, smoothing, overshoot, elasticity, settling, low-energy response,
spatial distribution, source freshness, transient/onset timing and mode personality.

Rules:

- every authored logical input integrates before presentation coalescing;
- logical simulation never waits for compositor paint;
- no latest-state policy may erase a protected short-lived authored/visible edge;
- mode arrays/history/envelopes/pending work reset at real activation boundaries;
- scheduler/compute substitutions are behavioural changes and need runtime-shaped temporal tests;
- average FPS/task count/final-state equality cannot overrule an installed fidelity regression;
- one-in-flight compute may retain one latest pending source frame; no backlog/catch-up FIFO;
- compositor state-to-paint and upstream source age are separate metrics; do not tune the shader
  for an upstream freshness problem.

See `Docs/Guardrails/Visualizer_Presentation.md`.

## 8. QRhi / GL Lifecycle

- Qt owns QRhi and the borrowed OpenGL context;
- SRPSS never destroys borrowed Qt context and never `doneCurrent()`s it as owner;
- GL create/delete occurs on GUI owner with correct borrowed context current;
- one numeric handle has one deletion owner;
- failed deletion retains ownership/fails closed;
- ResourceManager releases accounting only after actual deletion;
- resize is not context destruction;
- true QRhi generation replacement releases old resources before reinit;
- no `glFinish()`, `DwmFlush()`, polling fence, GUI sleep or nested event pumping as a repair;
- no SRPSS-owned swapBuffers;
- no fake visualizer QPainter renderer;
- base-image QPainter fallback is allowed only as its explicit compositor capability/failure path
  and unexpected established-path fallback is state-loud/bounded.

## 9. Settings / Edit / Runtime Recreation

Retire old runtime generation before replacement can publish. Stop producers, reject stale queued
work, delete GL on owner context, pass destruction barrier, then construct/register/reveal the new
generation.

Do not use hide-only reuse, cleanup retry timers, force-clear numeric handles, garbage collection,
`deleteLater()` alone, or replacement construction while retired ownership remains.

CUSTOM edit preview must not resurrect retired presentation surfaces. Preview may be a snapshot;
mouse-drag preview does not require live GPU geometry mutation on every event.

## 10. CPU / Threading

Reduce/remove duplicate work before adding threads.

Do not:

- use a general compute task per presentation frame;
- busy-spin for timing;
- create a worker-to-paint handshake;
- mutate QWidget/QPixmap/GL from workers;
- create an unbounded visualizer frame queue;
- change authored source cadence merely to lower task count.

Workers may prepare detached immutable data and bounded measured compute.

## 11. Logging / Diagnostics

Diagnostics are passive, sampled, bounded, non-overlapping and lazily formatted. They never create
one GUI callback per event, modify task admission or become presentation control flow.

No per-frame INFO logging. Heavy GL timing stays opt-in and non-blocking; never wait for a query.

## 12. Memory / Resources

Byte-account CPU image representations, upload buffers, textures/PBOs and visualizer/transition
resources. Caches are byte-bounded plus count-bounded where useful. Context-local GL objects remain
context-local unless explicit leases/share ownership exist.

Normal cycling and repeated lifecycle operations must plateau.

## 13. Settings / Widgets / CUSTOM

- one settings normalization/persistence authority;
- widget metadata descriptor-owned;
- visualizer mode/preset identity registry/model-owned;
- committed CUSTOM geometry is a distinct authority from authored/default geometry;
- live refresh cannot silently become a second outer-geometry owner;
- intentional cross-display edit transfer is not sleep/wake fallback.

## 14. Testing / Evidence

Test the real installed failure shape. High-risk work needs focused automation and runtime/manual
review where relevant.

Do not use a fake engine/context whose lifecycle counters cannot reproduce the production boundary
being asserted. A regression test must fail when the real defect is reintroduced.

## 15. Architecture Prohibitions

Do not preserve/reintroduce:

- separate visualizer QOpenGLWidget/QRhiWidget presentation surface;
- visualizer CPU/QPainter renderer;
- pending-until-paint/present acknowledgement;
- render-callback self-scheduling;
- producer/display divisor cadence gate;
- second visualizer presentation clock;
- source/event decimation;
- partial Settings/Edit GL reinit as a substitute for ordered teardown;
- broad widget impersonation/dynamic forwarding;
- garbage-collection-owned GL lifetime;
- silent compatibility fallback to retired presentation architecture.

Historical negative controls may be studied; they are not merge targets.
