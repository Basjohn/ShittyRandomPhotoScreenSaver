# SRPSS Guardrails

Last updated: 2026-08-20

Durable cross-cutting stop rules.

## 1. Architecture decision

Qt Quick is the accepted runtime presentation destination:

```text
one physical display -> one standalone QQuickWindow -> threaded Quick scene graph
```

Do not reopen a broad C++/native presenter route without new evidence that the accepted architecture
cannot satisfy production requirements.

Do not use `QQuickWidget`.

Do not add second accelerated runtime surfaces.

During migration, the existing QRhiWidget path is a reference/rollback implementation only.

## 2. Priority

1. visualizer fidelity/reactivity;
2. lifecycle/resource safety;
3. frame pacing/perceived smoothness;
4. multi-display correctness;
5. bounded resources;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

Never improve a counter by silently reducing authored work or fidelity.

## 3. Read/scope discipline

For architecture work read:

```text
current source
-> Current_Plan.md
-> Spec.md
-> Docs/Compositor_Architecture.md
-> Docs/Contracts.md
-> relevant focused guardrail
```

Preserve unrelated user work.

Do not reset/checkout/clean/stash/revert merely to manufacture checkpoint equality.

Historical evidence is not a current owner map.

## 4. Immediate stop conditions

Stop/reassess when:

- Bubble/Spectrum/another mode loses fidelity/reactivity;
- BTF fails;
- source age rises while visuals keep moving;
- physical p99/max worsens despite prettier averages;
- a producer waits for paint/present;
- a second visualizer logical clock appears;
- GUI/AnimationManager simulation ownership reappears;
- logical worker mutates GUI/Quick/GPU state;
- valid generation `0` is lost;
- stale generation can reveal/publish;
- resource ownership cannot be explained;
- a fallback silently changes presentation architecture;
- a second accelerated window/surface is introduced;
- `QQuickWidget` is used to claim migration progress;
- a change deepens the old QRhiWidget presenter without explicit migration need;
- a local renderer concern is used to reopen a whole native-presenter migration.

## 5. One owner per concern

Examples:

- runtime lifecycle: engine/display lifecycle owner;
- topology: DisplayManager/topology owner;
- visualizer source: BeatEngine/audio owner;
- visualizer logical cadence: `VisualizerLogicalRuntime`;
- physical runtime presentation: destination `QQuickWindow` per display;
- GPU resource deletion: explicit legal render/context owner;
- accounting: ResourceManager, never deletion fallback.

## 6. Presentation admission

Allowed:

- bounded latest-state synchronization;
- passive timing metrics;
- coalescing that prevents duplicate queued work without waiting for paint.

Forbidden:

- pending-until-paint;
- paint/swap acknowledgement;
- producer timestamp/display-rate divisor;
- scheduler release by paint;
- catch-up replay;
- source/event/logical cadence reduction;
- independent visualizer presentation loops.

## 7. Visualizer safety

Preserve:

- attack/amplitude/decay;
- smoothing;
- overshoot/elasticity/settling;
- low-energy response;
- spatial distribution;
- source freshness;
- transients;
- mode personality.

Every authored input integrates before presentation coalescing.

Logical time never derives from physical paint cadence.

For Bubble, BTF is binding.

## 8. Quick/render resource safety

The selected Quick primitive defines the legal render/context owner.

Rules:

- one resource has one deletion owner;
- creation/use/destruction obey the render-thread/context contract;
- old-generation resources retire before replacement authority;
- failed deletion retains ownership/fails closed;
- accounting follows real ownership release;
- no `glFinish()`, `DwmFlush()`, GUI sleeps, nested event pumping, or fence polling as cadence repair.

Do not copy old QRhiWidget borrowed-context rules forward without verifying they apply.

## 9. Lifecycle

For recreation/cutover:

1. close old admission;
2. stop generation-owned producers;
3. join logical runtime;
4. reject stale state;
5. retire legal render resources;
6. pass destruction barrier;
7. construct replacement;
8. prepare intentional first content;
9. reveal current generation.

No hide-only lifecycle, cleanup retry timers, force-cleared GPU handles, or garbage-collection-owned
resource lifetime.

## 10. Runtime overlays

Do not rewrite provider/model/business logic merely because runtime pixels migrate.

Separate data authority from pixel authority.

The destination Quick scene owns runtime pixels that coexist over the screensaver.

Settings may remain QWidget.

## 11. Native/C++ rule

Native code is contingency/local optimization only.

Before introducing it, name:

- the measured Python/render callback cost;
- the exact renderer to move;
- why existing Quick primitives are insufficient;
- how the change remains inside the same `QQuickWindow`.

No second presentation architecture.

## 12. Diagnostics

Diagnostics are passive, sampled, bounded, and never cadence/admission control.

Use existing evidence before creating another probe family.

Physical-display claims require OS/display-boundary evidence when internal callbacks are ambiguous.

## 13. Documentation

- edit canonical docs in place;
- `Current_Plan.md` is active work only;
- evidence reports keep measurements;
- historical reports remain historical;
- when a migration changes owner/type, reconcile current owner docs in the same docs sweep.

Do not preserve obsolete planning documents that can compete with the accepted architecture.
