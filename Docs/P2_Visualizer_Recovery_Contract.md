# P2 Visualizer Recovery Contract

Status: **binding current P2 ownership contract after the logical-runtime landing**  
Date: 2026-08-19

This document defines the architecture that must be preserved while the remaining P2 delivery
failures are closed.

`Current_Plan.md` owns active slice order.

## 1. Product invariant

The visualizer must be smooth **and** reactive.

Smooth:

- continuous authored motion;
- no visible freeze/jump/flicker from timing holes.

Reactive:

- low source-to-visible latency;
- preserved transient/attack strength.

Do not obtain smoothness by delaying/averaging source data.

For Bubble, BTF is binding.

## 2. Current ownership table

| Concern | Logical runtime | Audio/analysis | GUI/compositor |
|---|---:|---:|---:|
| authored logical deadline/dt | YES | NO | NO |
| mode simulation | YES | NO | NO |
| logical envelopes/events | YES | publishes inputs | NO |
| idle logical evolution | YES | NO | NO |
| latest logical publication | YES | NO | consumes |
| source/capture production | consumes snapshot | YES | NO |
| capture keepalive | NO | YES | NO |
| QWidget visibility/update | NO | NO | YES |
| QPixmap/QPainter | NO | NO | YES |
| layout/geometry mutation | NO | NO | YES |
| reveal/fade execution | decision only | NO | YES |
| GL/QRhi mutation | NO | NO | YES |
| physical presentation cadence | NO | NO | YES |

The logical worker must have no GUI/GL backdoor.

## 3. Current logical runtime

`VisualizerLogicalRuntime` is landed and is the sole logical cadence owner.

The old GUI recurring visualizer timer no longer advances simulation.

AnimationManager no longer advances simulation.

Scheduler current contract:

- high-resolution monotonic deadline clock;
- bounded real sleeping, not busy spin;
- no coarse timed-wait regression;
- skip genuinely missed deadlines;
- no catch-up replay;
- stop/join with runtime generation.

The old ~64 Hz / ~29% skipped coarse-wait class is now a negative control, not current architecture.

## 4. Plain-data handoff

Logical runtime publishes one latest state/intention through the mailbox.

Conceptually:

```text
logical timestamp
runtime generation
mode activation
mode
changed/revision state
mode-reveal intent
source identity/freshness
```

Exact packing is implementation-owned.

Required GUI handoffs are explicit and fail loudly in tests/development when missing.

## 5. Readiness distinction

At minimum:

```text
presentation_ready
reactive_source_ready
```

Do not overload source freshness into presentation permission.

Mode capability matrix:

| Mode | Idle reveal | Idle self-animation | Presentation-owned idle scene | Fresh real source for reactive playback |
|---|---:|---:|---:|---:|
| Bubble | yes | yes | no | no |
| Spectrum | yes | no | yes | yes |
| Sine | yes | yes | no | no |
| Oscilloscope | yes | yes | no | no |
| DevCurve | yes | yes | no | no |

Paused Spectrum may reveal its presentation-owned idle scene while source identity remains absent.

On Play, real current-generation/current-activation Spectrum data replaces idle bars in place.

## 6. One-clock contract

Exactly one visualizer logical clock:

```text
VisualizerLogicalRuntime = yes
GUI recurring visualizer timer = no logical ownership
AnimationManager = no logical ownership
per-mode timer/thread = none
physical compositor timer = presentation only
```

Physical display refresh is independent from logical simulation cadence.

## 7. Latest-state contract

One slot, latest wins.

No:

- FIFO;
- backlog;
- catch-up;
- one GUI callback per logical tick;
- paint backpressure.

Every authored event integrates before its state may be replaced.

## 8. Generation / activation fencing

Generation/activation are real ownership boundaries.

Valid generation `0` must remain `0`.

None/missing may map to invalid sentinel.

Never use `value or -1` for identity where zero is valid.

Retired generation state cannot:

- enter replacement mailbox;
- trigger reveal;
- mutate current GUI/GL presentation.

## 9. Pause / Play

Playback state and capture lifetime are separate.

Pause:

- logical runtime remains alive;
- card/GL/mode identity remains;
- authored idle state begins promptly;
- capture may remain warm.

Warm Play:

- same logical runtime continues;
- same card/GL owner continues;
- no cold startup;
- fresh source becomes authoritative promptly.

Do not reintroduce visualizer pause debounce.

Identity continuity is a narrow gate only. It does not prove no-hitch physical delivery.

## 10. Current remaining P2 failures

Current installed evidence owns volatile measurements, but the durable failure classes are:

1. Pause/Play still visibly hitches despite identity continuity.
2. Spectrum idle scene is reachable but current bar magnitude is effectively invisible.
3. valid generation 0 is mishandled by part of the fence.
4. shared GUI/compositor delivery remains weak even on a non-visualizer high-refresh display.
5. Bubble logical/presentation long tails remain BTF alarms despite healthy average cadence.

Do not fix these by reverting the logical-runtime architecture.

## 11. Pause/Play feedback ownership

A small control-feedback animation must not use a large stable MediaWidget as its full-card
per-animation-frame paint owner when a smaller equivalent owner can preserve the visual effect.

The current plan treats this as the first bounded edge-specific target before speculative
wake/source-handoff changes.

## 12. Error visibility

- GUI-only methods assert thread affinity in tests/debug.
- required handoffs fail loudly.
- worker ownership violations cannot disappear into broad exception handlers and a green suite.
- production may fail safe, but tests must expose architecture violation.

## 13. Lifecycle

Retirement order includes:

```text
close logical admission
-> quiesce source producers as required
-> join logical runtime
-> clear/reject stale publication
-> retire GUI/GL generation
```

Settings/Edit/shutdown/P5 topology rebuild use the same ownership model.

## 14. Validation

Binding behavioral gates:

`Docs/P2_Behavioral_Gates.md`

Current installed checkpoint:

`Docs/P2_Installed_Acceptance_Findings_2026-08-19.md`

Do not call P2 complete from unit counts.
