# Presentation / Cadence Change Preflight

Last updated: 2026-08-19

Rejected-mechanism register for the current single-surface + dedicated-logical-runtime architecture.
It does not override `Current_Plan.md`.

For Bubble timing/feel, BTF is additionally binding:
`Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

## 1. Current architecture epoch

```text
one display
    -> one OpenGL QRhi compositor surface

visualizer logical cadence
    -> one VisualizerLogicalRuntime

visualizer presentation
    -> layer inside the display compositor
```

Old separate visualizer surfaces and GUI-timer logical cadence are previous-epoch evidence.

## 2. Rejected mechanisms

| Mechanism | Why rejected | Current status |
|---|---|---|
| producer timestamp/display-rate divisor | quantizes authored logical/source cadence | rejected |
| pending-until-paint admission | Qt delivery delay becomes backpressure | rejected |
| paint/swap acknowledgement | producer deadline depends on consumer completion | rejected |
| render callback self-update loop | independent repaint loop/UI pressure | rejected |
| repaint rescue timer | more GUI pressure without ownership correction | rejected |
| source/event decimation | lowers fidelity to improve counters | rejected |
| catch-up replay | bursts stale logical/render state after stall | rejected |
| separate visualizer presentation surface | material shared presentation cost | rejected |
| GUI recurring timer as visualizer logical owner | Qt stalls become logical holes | rejected |
| AnimationManager as visualizer logical owner | couples simulation to UI animation service | rejected |
| per-mode logical timer/thread | fragments ownership | rejected |
| timed coarse wait mechanism reproducing ~64 Hz scheduler | cannot service authored cadence | rejected |

## 3. Adaptive physical presentation clarification

The display compositor's adaptive render strategy is allowed as **physical presentation strategy**.

It may not:

- own source/simulation cadence;
- become transition-only liveness when another scene reason needs frames;
- wait for paint acknowledgement;
- pace a second visualizer surface.

Do not delete the display's physical presentation strategy because old reports rejected an adaptive
timer in a different owner/surface role.

## 4. Logical / physical boundary

```text
audio/events
    -> BeatEngine/source state
    -> VisualizerLogicalRuntime integration
    -> latest logical publication
    -> GUI presentation handoff
    -> display compositor opportunity
```

Physical presentation may sample latest current state.

It may not modify logical time/event cadence.

## 5. Readiness

Before changing reveal/fade code ask separately:

```text
is presentation drawable now?
is real reactive source authoritative now?
```

Do not require real source identity for a presentation-owned idle scene.

Do not permit reactive playback state to masquerade as current without valid source identity.

## 6. Dispatch guard

One cross-thread dispatch-pending flag is allowed only to avoid duplicate queued GUI callbacks.

It ends when the queued callback executes.

It may not remain latched until paint.

## 7. Protected edge rule

Latest-state sampling is allowed only after logical integration.

If a protected visible response can exist briefly, assert the resulting visible/positional state,
not only the trigger flag.

BTF supplies Bubble-specific requirements.

## 8. Generation identity

Check valid generation zero explicitly.

Do not use truthiness conversion where zero is meaningful.

Stale retired generation cannot enter current presentation.

## 9. Instrumentation proportionality

Use current source/evidence first.

Add a new probe only when it chooses between materially different remaining owners/designs.

A known full-card feedback repaint stream or known invalid generation conversion does not require a
new probe merely to prove it exists.

## 10. Runtime evidence

Current P2 checkpoint:

`Docs/P2_Installed_Acceptance_Findings_2026-08-19.md`

Use sidecars as needed:

- `screensaver_perf.log`
- `screensaver_spotify_vis.log`
- `screensaver_lifecycle.log`
- `screensaver.log`

Separate:

- source age;
- logical cadence/gaps;
- GUI dispatch;
- state-to-paint;
- display delivery.

## 11. Required acceptance

For cadence/presentation changes require relevant:

- authored logical/fidelity goldens green;
- scheduler actual-cadence gate;
- one-clock gate;
- source freshness does not regress;
- state-to-paint tails healthy;
- 60 Hz effectively refresh-limited;
- high-refresh display materially uses available presentation opportunity;
- no callback backlog growth;
- no new surface/clock;
- BTF if Bubble affected;
- installed visual review.
