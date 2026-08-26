# SRPSS Guardrails

Last updated: 2026-08-26

## Architecture decision

```text
one selected physical display
-> one standalone QQuickWindow
-> threaded Quick scene graph
-> one composed runtime scene
```

Do not reopen broad native/C++ presenter work without new evidence accepted architecture cannot satisfy
production. Do not use `QQuickWidget`, second accelerated runtime surfaces, or deepen QRhiWidget architecture
to avoid migration work. Old QRhiWidget path is current-legacy until H.

## Priority

1. visualizer fidelity/reactivity;
2. lifecycle/resource safety;
3. frame pacing/perceived smoothness;
4. multi-display correctness;
5. bounded resources;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

Never improve counters by silently reducing authored work/fidelity.

## Read / scope discipline

```text
exact source
-> Current_Plan.md
-> Spec.md
-> Docs/Contracts.md
-> relevant focused contract/guardrail
-> tests/evidence
```

Preserve unrelated user work. Do not reset/checkout/clean/stash/revert merely to manufacture checkpoint
equality. Historical evidence is not current owner map.

## Immediate stop conditions

Stop/reassess when:

- Bubble/Spectrum/another mode loses authored fidelity/reactivity or BTF fails;
- source age rises while visuals continue;
- physical p99/max worsens despite prettier averages;
- producer waits for paint/present or second visualizer logical clock appears;
- logical worker mutates GUI/Quick/GPU state;
- valid generation 0 is lost or stale generation/request can publish/reveal;
- resource ownership cannot be explained;
- fallback silently changes presenter/renderer/capability/authored behavior;
- second accelerated surface appears or `QQuickWidget` claims migration progress;
- common Quick imports eagerly resolve inactive family backend/runtime trees;
- family port duplicates provider/controller/timer/cache/action authority;
- migration casually redesigns working family interaction/visual behavior without product intent.

## Resilience vs fallback

Do not silently substitute alternate architecture/authored behavior when selected path fails. Fail closed or
repair selected owner. Provider/cache/network recovery and deterministic resolution inside same feature
contract remain valid product resilience.

Legacy GL demotion (`FULL_SHADERS -> COMPOSITOR_ONLY -> SOFTWARE_ONLY`) retires with old physical presenter.

## One owner per concern

Topology: DisplayManager/topology owner. Physical presentation: one destination QQuickWindow per display.
Ordinary retained items: QuickSceneController/OrdinaryWidgetPresentationHost. Ordinary runtime cardinality:
WidgetRuntimeManager plus real neutral owner scope. Visualizer source: Beat/audio owner. Visualizer logical
cadence: VisualizerLogicalRuntime. GPU deletion: legal render/context owner. ResourceManager accounts only.

A per-display manager does not imply every provider/backend is per-display.

## Capability / import dormancy

Family deactivation and ordinary instance disabled are distinct. Deactivated family ultimately owns no
family-exclusive provider/model/helper/timer/poll/worker/presentation/render resource.

Cheap catalog/common Quick imports must not eagerly import heavy inactive family implementation trees. Do
not use package `__init__` convenience exports to defeat dormancy.

## Presentation admission

Allowed: bounded latest-state sync, passive metrics, coalescing that prevents duplicate queued work without
waiting for paint.

Forbidden: pending-until-paint, paint/swap acknowledgement, producer timestamp/display-rate divisor,
scheduler release by paint, catch-up replay, source/event/logical cadence reduction, independent visualizer
presentation loops.

## Visualizer safety

Preserve attack/amplitude/decay, smoothing, overshoot/elasticity/settling, low-energy response, spatial
distribution, source freshness, transients and mode personality. Every authored input integrates before
presentation coalescing. Logical time never derives from physical paint cadence. Bubble BTF is binding.

## Quick/render resource safety

One resource has one deletion owner; create/use/destroy under legal render-thread/context contract; old
resources retire before replacement authority; failed deletion retains ownership/fails closed; accounting
follows real ownership release. No `glFinish()`, `DwmFlush()`, GUI sleeps, nested event pumping or fence
polling as cadence repair. Do not copy QRhiWidget borrowed-context rules into Quick without proof.

## Lifecycle

Close old admission -> stop generation-owned producers -> join logical runtimes where required -> reject
stale state -> retire legal render resources -> destruction barrier -> construct replacement -> prepare
intentional first content -> reveal. No hide-only lifecycle or force-cleared handles.

## Runtime overlays / widgets

Do not rewrite provider/model/business logic because pixels migrate. QML owns presentation/semantic input
only. Preserve proven family behavior; remove obsolete QWidget mechanics rather than using migration as an
unrelated redesign opportunity. Settings may remain QWidget.

## Native/C++

Native code is contingency/local optimization only. Name measured cost, exact renderer, why current Quick
primitive is insufficient, and how code remains inside same QQuickWindow. No second presentation architecture.

## Diagnostics

Passive, sampled, bounded, never cadence/admission control. Physical-display claims require physical/OS
boundary evidence when internal callbacks are ambiguous.

## Documentation

Edit canonical docs in place. Current Plan stays lean and owns current sequence/work/debt. Independent
audit/closure narrative belongs under `Docs/audits/` or historical evidence. When owner/type/retirement
policy changes, reconcile current owner docs in same sweep. Do not preserve obsolete planning docs that
compete with accepted architecture.
