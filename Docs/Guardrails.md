# SRPSS Guardrails

Last updated: 2026-09-01

## Architecture decision

```text
one selected physical display
-> one standalone QQuickWindow
-> threaded Quick scene graph
-> one composed runtime scene
```

Do not reopen broad native/C++ presenter work without new evidence the accepted architecture cannot satisfy production.
Do not use `QQuickWidget`, second accelerated runtime surfaces, or restore/deepen the deleted QRhiWidget/DisplayWidget architecture. H is closed; the old physical presenter is not a fallback product or test convenience.

## Migration continuity

A working legacy screensaver during intermediate migration slices is **not** required. Do not preserve, restore or
invent old QWidget/compositor presentation solely so the half-migrated app keeps running. Caller-dead old pixels may be
deleted once their destination contract is owned and proven. H already established final production ownership; I removes caller-dead residue and J proves final visual/compiled/installed/physical quality.

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

Performance-specific admission, telemetry semantics, load-class evidence and reference envelopes live in `Docs/Guardrails/Performance_Optimization_Contract.md`. Use that checklist before changing cadence, GC policy, scheduling, caching, resource lifetime or presentation for performance.

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
- Bubble is re-gated/exempted from viewport reflow to avoid fixing a viewport ownership or spatial-domain defect;
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
must receive changed spatial bounds without deforming circles or compromising BTF. Ordinary committed viewport extent
remains truth outside CUSTOM; a working CUSTOM extent is a temporary override only. Leaving CUSTOM must not reset a saved
non-baseline layout to canonical by confusing "no override" with "baseline".

**R-69 golden rule:** viewport adaptation must not globally compress Bubble head/radius response, already-normalized Ghost/history displacement, or another Visualizer mode's authored musical response/freshness. Never add a second `baseline/current` or `1 / viewport_extent` compensation to state that is already projected into renderer content coordinates. If an extreme visual tail is too large, fix only that proven tail.

## Capability state

Ordinary ON/OFF is not family/capability activation. CUSTOM X and layout slots may change ordinary ON/OFF only.
A deactivated family remains deactivated even if a saved layout contained it.

## Lifecycle

Close admission before retirement. Fence stale generation/request state. Destroy custom GL on the legal render/context
owner. Do not repair cadence with `glFinish()`, `DwmFlush()`, GUI sleeps or nested event loops.

The operator-authorized 2026-09-05 Bubble equal-area response correction is documented in
`Docs/Future_Work/Visualizer_Visual_Regression_Recovery.md` and `Docs/Visualizer_Reference.md`.
It supersedes height-only product mapping; it does not authorize viewport-dependent performance caps,
DSP attenuation, temporal smoothing changes or compression of already projected Ghost/history.
