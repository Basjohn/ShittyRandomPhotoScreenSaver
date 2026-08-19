# Visualizer Change Checklist

Last updated: 2026-08-19

Use for visualizer settings, presets, logical analysis, activation, compositor rendering, card
geometry, fade/readiness, playback or CUSTOM work.

Also read:

- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Runtime_Efficiency.md` for shared-runtime work
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md` (**BTF**) when Bubble timing/feel can change

## 1. Identity / settings

- mode ids/labels remain registry-owned;
- grouped settings model stays symmetric;
- preset activation resolves one canonical target payload;
- genuine same-mode changes apply once;
- identical same-activation refresh is a no-op;
- valid generation 0 is never collapsed into “missing.”

## 2. Current logical runtime

Current production owner is `VisualizerLogicalRuntime`.

Check:

- exactly one runtime per enabled generation;
- no GUI recurring timer advances simulation;
- no AnimationManager listener advances simulation;
- no per-mode/fallback logical clock;
- runtime stop/join is generation-owned;
- scheduler preserves authored cadence;
- no FIFO/catch-up.

Do **not** describe a dedicated logical thread as future work.

## 3. Worker-callable ownership

`logical_tick()` and transitive worker-callable code must not:

- show/hide/update QWidget;
- mutate presentation geometry/layout;
- use QPixmap/QPainter;
- start GUI fade;
- mutate compositor/GL.

GUI-only methods should assert thread affinity in test/debug paths.

## 4. Analysis freshness

For async audio/bar analysis:

- one compute in flight;
- one newest pending source maximum;
- pending replaces old pending;
- completed valid DSP state commits before newest pending runs;
- stale generation/activation work cannot publish;
- source age is measured separately from state-to-paint.

Use delayed-compute tests, not only immediate fake executors.

## 5. Readiness

Do not use one “fresh source ready” boolean for all presentation.

At minimum:

```text
presentation_ready
reactive_source_ready
```

Paused Spectrum may reveal presentation-owned idle bars with no source generation/activation while
still waiting for fresh real data on Play.

A playing mode that requires real source authority remains gated by its current-generation source
contract.

## 6. Presentation owners

Current path:

```text
audio / analysis
    -> VisualizerLogicalRuntime
    -> latest mailbox state
    -> GUI presentation handoff
    -> CompositorVisualizerLayer
    -> display GLCompositorWidget
```

`SpotifyBarsGLOverlay` is not a presented overlay.

Do not add:

- another visualizer surface;
- visualizer swap/vsync lifecycle;
- presentation self-update loop;
- QPainter visualizer fallback.

## 7. Card / geometry

One authoritative presentation geometry feeds card texture, viewport, scissor, shader resolution,
origin, mask and border.

Compositor DPR is presentation DPR authority.

Stable card source pixels are cached by logical-size/DPR/style identity.

Real-GL tests use non-zero X/Y and non-1 DPR.

## 8. Presentation cadence

Display compositor owns physical frame opportunities.

Logical runtime owns simulation cadence.

Remove/forbid:

- pending-until-paint;
- paint/swap acknowledgement;
- producer/display divisor gates;
- render self-requeue;
- repaint rescue timer;
- second presentation timer/surface;
- second logical timer/thread.

A physical adaptive render strategy is allowed when it remains presentation-only.

## 9. Spectrum idle

Paused Spectrum gate must prove **perceptible rendered output**.

Preferred:

- actual GL/pixel readback or image comparison.

Acceptable deterministic fallback:

- real renderer/upload/geometry math yielding deliberate minimum visible pixel height.

Forbidden sole assertion:

```text
max(bars) > 0
```

Keep source identity unassigned while idle.

## 10. Playback / feedback

Pause/Play:

- preserves logical runtime/card/GL identity;
- keeps warm capture separate;
- does not reintroduce playback debounce;
- does not cold-start on ordinary warm resume.

Also inspect edge-owned GUI work.

A small feedback animation should not repaint the entire Media card dozens of times per event.

Do not solve that by merely lowering feedback FPS.

## 11. Bubble / BTF

Before accepting Bubble-affecting timing/runtime work, check the BTF alarm panel:

- logical Hz;
- deadline skip fraction;
- logical gap tails;
- source freshness;
- Bubble protected replay/goldens;
- publication/edge survival;
- state-to-paint tails;
- final visual feel.

No Bubble algorithm retune is authorized merely because Bubble exposes a shared-system problem.

## 12. Lifecycle

- logical runtime joins before retired generation is destroyed;
- stale mailbox publication is rejected;
- visualizer GL resources remain tied to compositor QRhi generation;
- borrowed context is never destroyed by SRPSS;
- hidden presentation state does not erase destruction authority;
- final GL accounting returns to baseline.

Generation tests must include `0 -> 1`.

## 13. Shared-runtime attribution

The 165 Hz display without a visualizer is a control for shared presentation cost.

If high-refresh delivery falls badly there:

- do not blame Bubble;
- do not optimize individual transitions first;
- inspect shared GUI dispatch/update/widget/lifecycle owners.

Mode/transition-specific tuning requires owner-specific evidence.

## 14. Required installed review when relevant

- Bubble long enough for BTF judgement;
- all five mode switches;
- Pause/Play quick toggles;
- paused Spectrum visible idle bars;
- Play replacing idle bars in place;
- Settings/recreate;
- CUSTOM Cancel/Save;
- 60 Hz + high refresh;
- dual-display ownership;
- clean shutdown.

Tests/average FPS never overrule a visible fidelity regression.
