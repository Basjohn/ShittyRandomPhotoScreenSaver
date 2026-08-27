# SRPSS Guardrails

Last updated: 2026-08-28

## Architecture decision

```text
one selected physical display
-> one standalone QQuickWindow
-> threaded Quick scene graph
-> one composed runtime scene
```

Do not reopen broad native/C++ presenter work without new evidence the accepted architecture cannot satisfy production.
Do not use `QQuickWidget`, second accelerated runtime surfaces, or deepen QRhiWidget architecture to avoid migration
work. Remaining old QRhiWidget/DisplayWidget code is temporary scaffolding until H, not a fallback product.

## Migration continuity

A working legacy screensaver during intermediate migration slices is **not** required. Do not preserve, restore or
invent old QWidget/compositor presentation solely so the half-migrated app keeps running. Caller-dead old pixels may be
deleted once their destination contract is owned and proven. H wires final production ownership; J proves the complete
installed product.

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

Preserve unrelated user work. Do not reset/checkout/clean/stash/revert merely to manufacture checkpoint equality.
Historical evidence is not current owner map.

When current source contradicts a durable product contract, do not silently rewrite the contract to match the bug.
Promote the missing behavior into `Current_Plan.md` unless explicit product intent changed it.

## Immediate stop conditions

Stop/reassess when:

- Bubble/Spectrum/another mode loses authored fidelity/reactivity or BTF fails;
- visualizer wide/tall viewport support is replaced by final-pixel anisotropic stretch;
- Bubble is treated as exempt from required viewport reflow merely because a temporary capability flag says false;
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

## Visualizer geometry guardrail

Keep these distinct:

```text
uniform_visual_scale   # wheel/corner whole-size scaling
viewport_extent        # independent world/playroom width/height
```

All five current modes support both destination operations. Edge viewport resize is configuration, not a clock. Bubble
must receive changed spatial bounds without deforming circles or compromising BTF.

## Capability state

Ordinary ON/OFF is not family/capability activation. CUSTOM X and layout slots may change ordinary ON/OFF only.
A deactivated family remains deactivated even if a saved layout contained it.

## Lifecycle

Close admission before retirement. Fence stale generation/request state. Destroy custom GL on the legal render/context
owner. Do not repair cadence with `glFinish()`, `DwmFlush()`, GUI sleeps or nested event loops.
