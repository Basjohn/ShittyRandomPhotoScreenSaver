# Bubble Slice 9: group-cohesion, particle light, and SINE soft-retirement

## Status and scope

Working-tree successor to `GODZIP_cc4c390a9e_BubbleAmbient_Slice8_SpiralDriftGlow_2026-11-03.zip`. No change to `Current_Plan.md`, `Future_Work.md`, existing Bubble presets, ordinary Bubble stream/breathing/collision, previous ambient occlusion, or viewport/stencil geometry. GPU and Qt visual acceptance **not yet run**.

### 1. Group Drift is 30% less cohesive, not 30% less reactive

The accepted Group Drift carrier, its timing, musical amplitude and speed remain intact. Only the per-bubble transport *direction* changes when Group Drift is active and not in a spiral mode:

- 70% of each bubble's already-authored group-drift displacement;
- 30% independently phased displacement at the same group's reactive magnitude, with the heading derived from that bubble's existing phase/bias.

Stream, collisions, quiet drift controls, ordinary ungrouped drift, and spiral drift are untouched. No new RNG, clocks, settings, UI, or per-bubble state. A controlled source-equivalent old/new run with identical seeds and inputs showed **exactly identical ungrouped positions** after 45 ticks. Group mode changed, as expected, with no new transport owner. Visual spread and long-run performance remain acceptance checks.

### 2. Particle glow repaired at the emission/coverage contract

This corrects the *cause* of the solid-orb regression, rather than increasing brightness again:

1. The ambient fragment's earlier glow raised halo alpha, causing a filled translucent body, while its large emissive gain clipped in the 8-bit framebuffer.
2. The final Bubble shader only sampled the decorative layer if alpha was nontrivial; RGB emission with near-zero alpha could be ignored.
3. Particles now have **coverage from fixed-size core only**. Outer radiance has a curved, bounded inner/outer falloff, tone-shaped by the existing inherited small-bubble breathing signal.
4. The Bubble final composite now admits emitted RGB even when coverage alpha is nearly zero. A partially transparent gradient also preserves the contribution of visible emission.

No new bloom pass or texture format; no changed particle core size or per-sprite population; ambient remains underneath hero bubbles and subject to the previously accepted occlusion. The bounded 8-bit RGB radiance profile prevents the prior flat white plateau. The exact glow still requires native GPU assessment at idle, moderate and sustained-loud intensity, particularly at custom particle colours and extreme viewport sizes.

### 3. SINE disabled, visibly and reversibly

SINE is **not deleted**. All renderer/runtime source, preset definitions, stored setting keys and older authored snapshots remain. The central mode gate denies product admission, cycling, selection and runtime logical activation; an old SINE-only saved configuration falls back to an available live mode. Settings mode navigation and its enable list show grey disabled `Sine Waves (Retiring)` controls. Guided Setup shows the same disabled unchecked option, not a silently missing entry. There is no checkbox path to enable it.

This is a soft retirement and a future removal candidate. Do not refactor/delete dormant SINE components without a separate explicit task.

## Verification performed

- Python compilation (source `compile`, no `.pyc`) of modified Python modules.
- Five focused PySide6-independent tests: SINE registration/gating, old-config fallback and visual-light emission/coverage shape.
- Controlled Bubble old/new source comparison with identical input/seed: 45-tick ungrouped path byte-for-byte identical; grouped path deviates as authored.
- Analytic halo samples: at maximum inherited glow strength, strongest radiance remains **below 1.0** per individual sprite; glow falls steeply outside the unchanged core and reaches zero at sprite edge.
- Archive payload SHA-256, sizes, CRC, manifest-to-inventory equality; no `__pycache__`, `.pyc`, `.pytest_cache` or undeclared payloads.

## Native acceptance still required

- Qt Settings: SINE greyed in navigation and Setup; Guided Setup grey and cannot be checked; selecting a stored SINE config never launches it. Confirm standard modes remain selectable and presets untouched.
- Bubble: compare unchanged ordinary drift side-by-side with Slice 8; confirm grouped movement fills gaps more naturally without losing loud-passage power, and no new movement jumps/odd convergence during transitions.
- Particle glow: evaluate 150% intensity / 300% reactivity, idle vs sustained loud, extreme viewport and rotation. It must read as *light radiating past a fixed core*, not larger white circles, and remain below normal Bubble heroes.
- Observe FPS and frame-time under concurrent GPU use. This environment has no PySide6/OpenGL for native execution.
