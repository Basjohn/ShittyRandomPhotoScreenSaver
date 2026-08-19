# Project Overview

Last updated: 2026-08-19

## What SRPSS is

SRPSS is a Windows screensaver/media runtime with multi-display image presentation, accelerated
transitions, a high-fidelity multi-mode Spotify visualizer, configurable overlay widgets, durable
settings/profiles and Normal/Media Center runtime variants.

## Read order

Do **not** read the whole documentation tree.

For active work:

1. user instruction + exact current `main`;
2. `Current_Plan.md`;
3. `Index.md` / `Docs/Contracts.md`;
4. `Docs/Guardrails.md` + one focused guardrail;
5. `Spec.md` / focused architecture reference;
6. current installed evidence when the task needs measurements;
7. older phase/Historical_Bug evidence only for a named mechanism.

Historical owner maps do not become current architecture because they are detailed.

## Current presentation architecture

- one accelerated OpenGL QRhi compositor surface per physical display;
- visualizer card + shader are layers inside that compositor;
- no separate presented visualizer QOpenGLWidget/QRhiWidget;
- physical display presentation is owned by the display compositor;
- no producer-to-paint acknowledgement/backpressure.

## Current visualizer cadence architecture

- `VisualizerLogicalRuntime` is the one mode-general logical visualizer clock;
- it is a standard Python thread, independent from Qt event-loop timing;
- logical code publishes latest plain-data state;
- GUI presentation code consumes that state and owns reveal/layout/card/GL work;
- the former GUI visualizer timer does not advance simulation;
- `AnimationManager` does not advance visualizer simulation.

This worker architecture is **landed**, not a future proposal.

## Current readiness rule

Presentation permission and reactive source authority are different.

Paused Spectrum may reveal its presentation-owned idle scene while still waiting for real
current-generation source data for reactive playback.

## Bubble / BTF

For “Bubble feel”, Bubble stutter/flicker/latency/elasticity or shared timing changes that affect
Bubble, read:

`Docs/Guardrails/Bubble_Temporal_Fidelity.md`

BTF protects both authored Bubble behaviour and temporal delivery.

## Current P2 truth

The dedicated logical scheduler fixed the old ~64 Hz cadence collapse, but P2 remains open because:

- Pause/Play still visibly hitches;
- paused Spectrum's card reveals but its current idle bars are effectively invisible;
- valid runtime generation 0 is mishandled in part of the logical/presentation fence;
- shared GUI/compositor delivery remains weak even on the 165 Hz display without a visualizer;
- Bubble still sees unacceptable long-tail logical/presentation gaps.

Use `Current_Plan.md` for exact active order and
`Docs/P2_Installed_Acceptance_Findings_2026-08-19.md` for the current evidence checkpoint.

## Core engineering priorities

1. visualizer fidelity/reactivity;
2. lifecycle/GL safety;
3. frame pacing/perceived smoothness;
4. multi-display correctness;
5. bounded RAM/VRAM;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

Efficiency means removing technical waste, not reducing authored content.

## Repository/document stability

Current `main` is implementation authority.

Existing canonical documents are updated in place. Do not rename/move paths without explicit user
instruction.

Old phase reports and Historical_Bugs remain evidence-scoped and may intentionally describe retired
architectures.
