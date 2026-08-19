# SRPSS Guardrails

Last updated: 2026-08-19

Durable cross-cutting stop rules. `Current_Plan.md` owns active sequencing. Focused guardrails may
be stricter.

Read additionally:

- `Docs/Guardrails/Runtime_Efficiency.md` for shared-runtime/performance/change-safety work;
- `Docs/Guardrails/Visualizer_Presentation.md` for visualizer cadence/presentation ownership;
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md` (**BTF**) for Bubble feel/timing.

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

## 2. Read / scope discipline

For active architecture work read:

```text
exact main
-> Current_Plan.md
-> Docs/Contracts.md
-> Docs/Guardrails.md
-> one focused guardrail/reference
```

Do not treat old phase reports or historical incidents as current owner maps.

Changing more than one long-lived timer/thread/queue/context/generation/fallback/state machine in one
slice requires explicit architecture justification and a statement of what old mechanism disappears.

For a “small optimization”, name the work that disappears.

## 3. Immediate stop conditions

Stop/reassess when:

- Bubble/Spectrum/another mode becomes less reactive/smooth/elastic/correct;
- BTF mechanically or perceptually fails;
- source age rises while the visualizer keeps moving;
- p99/max delivery worsens despite prettier averages;
- a producer/presentation deadline waits for paint;
- a second visualizer logical clock appears;
- GUI-timer/AnimationManager simulation ownership reappears;
- a worker reaches QWidget/QPixmap/QPainter/GL mutation;
- a context/thread-affinity error appears;
- valid generation 0 is collapsed into an invalid sentinel;
- cleanup requires retries, force-clear, nested event pumping or hide-only reuse;
- resources grow monotonically or ownership cannot be explained;
- a fallback silently changes behaviour/render owner;
- tests pass while the known installed failure remains;
- a fix needs another presentation surface/clock merely to preserve old plumbing;
- a no-op settings/style/geometry replay performs expensive reconstruction;
- visible startup is made smoother only by moving expensive work into the first visible seconds;
- a tiny feedback animation repaints a large parent surface every animation frame without measured
  justification.

## 4. Documentation stability

- edit canonical files in place;
- never rename/move existing paths without explicit user instruction;
- stable contracts live in Spec/Guardrails/focused docs;
- active work lives only in `Current_Plan.md`;
- current evidence checkpoint owns current volatile measurements;
- phase reports/Historical_Bugs remain checkpoint evidence and may intentionally contain obsolete
  class names/timers/surfaces.

## 5. Ownership

One mutable concern, one owner.

Current examples:

- runtime lifecycle: engine/runtime coordinator;
- topology: engine/display-manager decision owner;
- settings: SettingsManager/store;
- visualizer audio analysis: BeatEngine/audio worker;
- visualizer logical cadence: `VisualizerLogicalRuntime`;
- visualizer GUI reveal/present commit: GUI presentation half;
- physical presentation: each display compositor;
- GL deletion: explicit context/resource owner;
- accounting: ResourceManager, never deletion fallback.

Moving work to IO/COMPUTE or a dedicated thread does not make its lifetime process-scoped.

## 6. Presentation / compositor

### Current architecture

- one accelerated OpenGL QRhi compositor surface per physical display;
- no separately presented visualizer surface;
- visualizer card + shader are compositor layers;
- one display-local presentation strategy owns physical frame opportunities;
- `VisualizerLogicalRuntime` owns visualizer simulation cadence separately.

### Admission

Allowed:

- one queued-GUI dispatch-pending guard ending when the queued callback actually executes;
- passive request/dispatch/paint timing metrics;
- Qt's own paint-event coalescing.

Forbidden:

- pending-until-paint admission;
- paint/swap acknowledgement/backpressure;
- producer timestamp/display-rate divisor gates;
- scheduler release by paint;
- render-callback self-scheduling/requeue;
- repaint rescue timer;
- catch-up bursts;
- source/event/logical cadence reduction;
- second visualizer presentation timer/surface;
- second visualizer logical timer/thread.

A display render strategy may be adaptive physical presentation. It may not become logical
visualizer cadence.

## 7. Visualizer safety

Protect:

- attack/amplitude/decay;
- smoothing;
- overshoot/elasticity/settling;
- low-energy response;
- spatial distribution;
- source freshness;
- transient/onset timing;
- mode personality.

Rules:

- every authored logical input integrates before presentation coalescing;
- logical simulation never waits for compositor paint;
- latest-state policy may not erase a protected short-lived visible edge;
- mode arrays/history/envelopes/pending work reset at real activation boundaries;
- one-in-flight analysis may retain one newest pending source frame; no FIFO/catch-up;
- source age and state-to-paint are separate metrics;
- shared runtime starvation is not a mode-specific defect without mode-owned evidence;
- current logical cadence is worker-owned and must not be moved back to Qt timing by inertia.

### Readiness

At minimum distinguish:

```text
presentation_ready
reactive_source_ready
```

A presentation-owned idle scene may reveal without fabricating reactive source identity.

Paused Spectrum is the canonical case.

### Bubble

BTF is binding for Bubble feel/timing. A healthy average does not excuse long logical gaps, stale
source, protected-edge loss or poor state-to-screen tails.

## 8. QRhi / GL lifecycle

- Qt owns QRhi and borrowed OpenGL context;
- SRPSS never destroys/doneCurrent()s it as owner;
- GL create/delete occurs on GUI/context owner;
- one numeric handle has one deletion owner;
- failed deletion retains ownership/fails closed;
- ResourceManager releases accounting only after actual deletion;
- resize is not context destruction;
- true QRhi generation replacement releases old resources before reinit;
- no `glFinish()`, `DwmFlush()`, fence polling, GUI sleep or nested event pumping as a repair;
- no SRPSS-owned swapBuffers;
- no visualizer QPainter renderer.

## 9. Settings / Edit / runtime recreation

Retire old generation before replacement can publish.

Stop producers, join the visualizer logical runtime, reject stale work, delete GL on owner context,
pass destruction barrier, then construct/register/reveal replacement.

Do not use:

- hide-only reuse as lifecycle;
- cleanup retry timers;
- force-clear numeric handles;
- garbage-collection-owned GL lifetime;
- replacement construction while retired ownership remains.

Cancel is not Save. Preview-only Cancel should restore/resume the unchanged live authority rather
than replay every persisted setting.

## 10. CPU / threading / GUI availability

Reduce duplicate work before adding mechanisms.

Do not:

- use a general compute task per presentation frame;
- busy-spin for timing;
- create worker-to-paint handshake;
- mutate QWidget/QPixmap/GL from workers;
- create an unbounded visualizer queue;
- change authored source cadence to lower task count;
- treat a widget's synchronous GUI cost as isolated from the rest of the app.

The dedicated visualizer logical runtime is current and must remain one mode-general owner.

GUI availability remains shared by presentation, widgets, input, image/card promotion, Settings/Edit,
lifecycle and legal GL commits. It no longer directly owns the visualizer simulation clock, but GUI
starvation can still make the physical result late.

## 11. Logging / diagnostics

Diagnostics are passive, sampled, bounded and lazily formatted.

They never:

- create one GUI callback per source event;
- modify task admission;
- become presentation control;
- change logical cadence.

When current source/evidence already identifies a bounded owner, fix it rather than adding another
probe family.

## 12. Resources

Byte-account CPU image representations, upload buffers, textures/PBOs and visualizer/transition
resources.

Caches are byte-bounded and count-bounded where useful.

Normal cycling and repeated lifecycle operations must plateau.

## 13. Widgets / feedback / CUSTOM

- widget metadata is descriptor-owned;
- committed CUSTOM geometry is distinct from authored/default geometry;
- live refresh cannot become a second geometry owner;
- settings hydration is not permission to start providers/workers;
- unchanged values should not rebuild caches/shadows/card pixels/runtime;
- small decorative/feedback animation should use the smallest practical paint/presentation owner;
- do not repaint a large stable card dozens of times merely to animate a small icon if equivalent
  cached/dirty-region/layer ownership is available.

## 14. Testing / evidence

Test the real installed failure shape.

A regression gate must be capable of failing when its named defect is reintroduced.

A test called “visible” that never renders pixels is not a visible-output gate.

Generation fencing must explicitly cover valid generation `0`.

Keep a named installed baseline after major architecture improvements, but do not let an old baseline
override newer installed truth.

## 15. Architecture prohibitions

Do not preserve/reintroduce:

- separate visualizer presentation surface;
- visualizer CPU/QPainter renderer;
- pending-until-paint/present acknowledgement;
- render-callback self-scheduling;
- producer/display divisor cadence gate;
- second visualizer presentation clock;
- second visualizer logical clock;
- GUI-timer or AnimationManager simulation ownership;
- source/event decimation;
- FIFO/catch-up visualizer replay;
- partial Settings/Edit GL reinit as lifecycle substitute;
- garbage-collection-owned GL lifetime;
- silent compatibility fallback to retired presentation architecture.

Historical negative controls may be studied. They are not merge targets.
