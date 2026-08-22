# Phase 5 — Presentation / Delivery Attribution

Status: **current reconciled evidence record; execution remains owned by `Current_Plan.md`**  
Last reconciled: 2026-08-18  
Architecture epoch: **one QRhi/OpenGL presentation surface per physical display**

This report records what the presentation/delivery evidence has established. It is not an alternate
task list. Exact current `main` and `Current_Plan.md` own implementation order.

Historical experiments remain useful where they establish a mechanism or negative control, but old
class names and old two-surface diagrams are not current architecture.

---

## 1. Current architecture boundary

Each physical display owns one accelerated `GLCompositorWidget` /
`ExternalOpenGLRhiWidget` using Qt's OpenGL QRhi backend.

The Spotify visualizer is a layer inside that compositor. `SpotifyBarsGLOverlay` remains a logical
state/geometry/visualizer-GL owner but is not a presented surface.

Current separation:

```text
audio / events
    -> authored logical visualizer integration
    -> latest current-generation visualizer scene state
    -> one display-local compositor presentation strategy
    -> Qt / QRhi / DWM physical delivery
```

Logical cadence and physical presentation are independent.

---

## 2. Durable historical causal result — old second-surface presentation was harmful

The accepted same-process A→B→C→A experiment on the old separate visualizer surface established:

| State | 165 Hz FPS | 165 Hz acceptance | 60 Hz FPS | 60 Hz acceptance |
|---|---:|---:|---:|---:|
| A — normal visualizer | 143.4 | 87.12% | 57.9 | 96.55% |
| B — suppress auxiliary visualizer `update()` | 150.2 | 91.39% | 58.9 | 98.37% |
| C — B + hide still-live visualizer surface | 151.6 | 92.11% | 58.75 | 98.01% |
| A — restored | 141.2 | 85.85% | 57.6 | 96.36% |
| no visualizer from startup | 156.5 | 95.11% | 59.35 | 99.09% |

Durable conclusion:

> independently dirtied visualizer presentation materially amplified shared-GUI delivery loss.

That experiment does **not** describe current source. The second visualizer surface is gone.

---

## 3. QRhi compositor migration result

The main compositor migration from `QOpenGLWidget` to OpenGL `QRhiWidget` materially improved the
no-visualizer transition path.

Accepted 60-Hz no-visualizer control after migration:

```text
gaps >33 ms       9
gaps >50 ms       0
median gap        ~39.9 ms
worst gap         ~42.1 ms
transition FPS    ~59.8–59.9
```

The old corresponding severe class had roughly:

```text
gaps >50 ms       28
median severe     ~58.5 ms
max               ~80.7 ms
```

This remains an accepted architecture checkpoint.

---

## 4. Rejected sibling-QRhi visualizer experiment

Migrating the visualizer to a second QRhi-backed surface did not solve the problem and worsened the
relevant delivery distribution despite inexpensive shader work.

Durable conclusion:

> shared QRhi does not make a second independently dirtied presentation surface free.

The single-surface compositor-layer design remains retained.

---

## 5. Single-surface visualizer result

The visualizer/card were moved into the display compositor while preserving logical source/state
cadence.

Retained architecture:
- one compositor surface per display;
- one latest visualizer state;
- one compositor physical presentation owner;
- no visualizer paint-acknowledgement loop;
- no second visualizer presentation timer.

The migration exposed and subsequently repaired:
- framebuffer/card-local coordinate authority;
- card texture viewport/scissor ordering;
- card texture lifetime after hidden/cleared state;
- renderer/card readiness before visible fade;
- mode activation/final-generation ownership;
- real audio callback publication;
- compositor-owned CUSTOM snapshot.

These were implementation defects in the new architecture, not evidence to restore the old surface.

---

## 6. Current installed functional state

The 2026-08-18 installed acceptance establishes:

- startup Bubble appears without the old pre-fade flash;
- real live audio publication works;
- Bubble becomes live/reactive;
- context-menu mode switching works;
- Settings/reinit mode switching works;
- all five current modes return correctly;
- returning to Bubble does not poison the runtime;
- current mode fades are visually good;
- reaction latency is materially improved relative to the prior broken path.

Still open:
- one CUSTOM Cancel resume defect;
- one fail-closed runtime exit caused by retiring Gmail IO work;
- visualizer logical cadence/jitter;
- variable high-refresh transition delivery;
- final post-migration CPU/GPU efficiency acceptance.

---

## 7. CUSTOM Cancel evidence — geometry is not the owner

The short `--geo` reproduction restores the exact original visualizer rect through the CUSTOM replay
chain.

The failure occurs after replay:
- edit entry stops the visualizer/audio runtime;
- Cancel calls the ordinary visualizer `start()` path;
- `start_legacy()` defers hot start to the Spotify secondary startup stage;
- that one-shot startup stage has already happened;
- the audio worker never restarts before exit.

Therefore the current defect is **mid-runtime edit resume ownership**, not CUSTOM geometry.

Required architecture:
- edit suspend/resume is distinct from cold startup;
- Cancel resumes the existing runtime directly;
- no second startup-secondary dependency;
- no generation churn merely for Cancel;
- Save may still use the established runtime-replacement path.

---

## 8. Cross-display CUSTOM exit evidence — fail-closed barrier worked correctly

The apparently intermittent cross-display visualizer crash is explained by lifecycle evidence.

The visualizer geometry/monitor Save completed. During retiring runtime generation teardown the
destruction barrier still found a generation-owned `gmail_fetch` IO task alive. At the barrier
deadline, SRPSS exited code 1 under the fail-closed lifecycle policy.

This was not a native GL crash and not proof that cross-display visualizer ownership itself failed.

Durable conclusion:

> the retiring Gmail producer must quiesce/cancel or become genuinely process-scoped; the barrier
> must not be weakened.

The failure is intermittent because it requires overlap with an in-flight Gmail network operation.

---

## 9. Current visualizer performance attribution

The short valid Bubble run is the strongest current discriminator.

Representative values:

```text
Bubble worker                  ~1.44–1.50 ms
Bubble tick body               ~0.97–1.12 ms
Bubble submissions/published   596 / 596
busy deferrals                 0
stale results                  0

visualizer paint CPU p50       ~0.56 ms
visualizer paint CPU p95       ~0.90 ms
visualizer GPU p50             ~0.95 ms
visualizer GPU p95             ~1.17 ms
state -> paint p50             ~5.1 ms
state -> paint p95             ~11.1 ms
```

Yet the same run showed:

```text
logical Bubble rate            ~65–70 Hz
logical dt_max                 ~87.8 ms
ordinary-play gaps             repeatedly ~42–80 ms
```

The shader/render duration is far too small to explain those visible holes.

Current attribution:

> the authored logical visualizer clock is being serviced late; renderer cost is secondary.

The logical tick remains GUI-timer serviced in current source. If the same holes remain after known
GUI waste is removed, cadence isolation becomes a legitimate architecture target.

---

## 10. Current compositor delivery attribution

The old paint-acknowledged admission latch is gone:

```text
paint_pending_skips = 0
```

in current evidence.

Remaining loss is dominated by queued GUI-dispatch age under pressure. Representative high-refresh
windows have dispatch-pending ages in the tens of milliseconds with tails around 100 ms.

Transition delivery is variable rather than hard-capped. The same current architecture has produced
165-Hz BlockSpin windows approximately spanning:

```text
151.5
156.3
156.4
144.4
148.3
134.2
137.3
142.7 FPS
```

The high windows disprove a demonstrated fixed ~134-FPS GPU ceiling.

Transition/mode names are load covariates, not causal explanations.

---

## 11. Safe waste target — unchanged visualizer scene presentation

Current single-surface evidence can physically paint substantially faster than new authored
visualizer scene states arrive.

A representative high-refresh visualizer window had roughly:

```text
new logical/state publications     ~87 / sec
physical paints                    ~141 / sec
display refresh                    ~165 Hz
```

Because authoritative visualizer state does not evolve in compositor paint, some physical paints
redraw the same visualizer scene revision.

Safe direction:
- keep the compositor strategy as sole physical presentation owner;
- preserve every logical/source/event integration;
- while a transition is active, every display deadline remains eligible;
- while visualizer-only, an unchanged scene revision need not queue another GUI paint;
- fade/card/geometry/state changes advance eligibility;
- no producer paint request, cadence cap, display divisor or second clock.

Intentional unchanged-scene suppression needs a bounded counter so it is not mistaken for delivery
failure.

---

## 12. Bubble compute negative control

The persistent Bubble scheduler/lane experiment was rejected because it changed temporal behaviour.

At the P05 checkpoint, production `BubbleComputeLane` was intentionally a compatibility facade over
the approved general COMPUTE executor semantics.

Therefore:

```text
lane_registrations = 0
executor task per accepted Bubble step = expected P05 behaviour
```

Phase D later removed that facade and its executor submission entirely: Bubble now integrates every
admitted step directly on the sole authored visualizer logical runtime. This report remains the
historical evidence for rejecting the persistent-lane experiment.

Do not reactivate the rejected persistent lane to reduce Future/task churn.

If per-step executor churn later proves material, a replacement mechanism must preserve:
- one lane-free authored step at a time;
- identical dt/event consumption;
- no queue/backlog/batching;
- identical trajectory digest;
- current-generation/stale-result fencing.

That would be a **new design**, not restoration of the rejected lane.

---

## 13. Evidence proportionality

Do not add another probe merely to restate an already distinguished mechanism.

Add instrumentation only when:
- two materially different architecture choices remain plausible;
- existing source/evidence cannot distinguish them;
- the measurement has a predetermined decision boundary.

When a structural owner is already proven, correcting or replacing that owner is preferred to a
probe treadmill.

Architecture replacement is not disfavoured merely because it is larger. It is appropriate when:
- the current owner boundary itself causes the defect;
- the replacement deletes competing timers/queues/state machines;
- fidelity/lifecycle contracts can be locked before the change;
- rollback is bounded and the success criterion is explicit.

---

## 14. Next architectural escape hatch if GUI starvation remains

Do not implement this merely because it is interesting.

If, after known GUI waste/remnant presentation work is removed, ordinary steady playback still
contains recurring >33 ms logical visualizer holes, the likely next architecture is:

```text
Qt-free logical visualizer runtime
    -> dedicated cadence authority
    -> immutable latest frame state
    -> GUI/compositor consumer
```

Requirements:
- one authoritative logical clock;
- all source/event/transient integration before publication;
- no QWidget/QPixmap/GL mutation off GUI/context owner;
- no paint-driven simulation;
- no FIFO/catch-up queue;
- generation-owned shutdown;
- exact Bubble/Spectrum/Sine/Oscilloscope/DevCurve fidelity bars.

Do not move the current QWidget-touching `_on_tick()` wholesale onto a worker. Extract the logical
owner from presentation concerns first.

---

## 15. Acceptance

Current presentation/delivery closure requires:
- CUSTOM Cancel restores a live visualizer;
- retiring runtime work cannot hold the destruction barrier accidentally;
- all five modes retain approved feel/fidelity;
- ordinary visualizer logical cadence no longer has recurring visible 40–90 ms holes;
- high-refresh transition delivery stops collapsing unpredictably under ordinary load;
- 60 Hz remains effectively refresh-limited;
- state-to-paint remains healthy;
- no callback/task backlog grows;
- CPU/GPU utilization is re-established after migration;
- strict GL/lifecycle ownership returns to zero at teardown.

P5 physical monitor topology/off-wake hardening remains mandatory after this closure.

---

## P2 Cancel / Gmail / Cadence Round

Evidence and corrections from the 2026-08-18 `--geo` acceptance. That run was
functionally much better than the previous one - live audio, working mode
switches, good fades, no pre-fade flash - so the findings below are the residue,
not a regression class.

### Cancel was a lifecycle-ownership fault, not geometry loss

CUSTOM replay restored the exact pre-edit rect through `replay_start` ..
`replay_final`. The failure was that edit entry/exit used the STARTUP entry
points. Mid-runtime, `start_legacy()` re-arms staged startup, sees
`_startup_secondary_stage_pending` and defers to the Spotify secondary stage - a
one-shot event that already fired for the process:

```text
Seeded playback state from anchor (start ... state=playing)
Deferred hot start to Spotify secondary stage
```

with no later `Audio worker started`.

Corrected with an explicit `suspend_for_edit()`/`resume_after_edit()` seam. An
edit session is not a lifecycle boundary: the runtime generation, staged-startup
bookkeeping, committed mode/config, engine identity and GL resources all survive,
and resume re-acquires the engine without resetting it.

The previous bar could not see this because it stubbed `vis.start()` with a
counter. The replacement drives the real state machine through
startup -> secondary stage completes -> live -> suspend -> Cancel.

### The cross-display "crash" was the barrier working correctly

```text
[LIFECYCLE_BARRIER] timeout reason=custom_edit retiring_generation=5
thread_work=[{category: gmail_fetch, pool: io,
              owner_class: GmailWidget, runtime_generation: 5}]
```

`GmailWidget` cleanup set `_cancelled` and advanced `_fetch_generation`, but
`GmailClient.list_messages()` never consulted that state again once inside its
traversal - one list request plus one metadata request per message, each with its
own timeout and retry budget. The fetch held an IO worker for the whole 8-second
window, so the replacement runtime could not be built.

Corrected at the producer: the client and the IMAP client accept a cancellation
predicate checked before the list request, before every metadata request and
before each retry. The barrier, its budget and its accounting are unchanged, and
tests pin that they were not weakened.

This is a direct input to P5: replacement must never proceed while a retired
generation still owns work, so the producer ownership is what has to be fixed.

### Presentation waste: unchanged scenes were being painted again

Visualizer on the 165-Hz display, representative 10-second window:

```text
logical/state publications     ~86.6 / sec
physical paints                ~140.7 / sec
display refresh                ~164.8 Hz
state -> paint p50             ~5 ms
```

Roughly 54 paints/sec presented an identical scene. P1 forbids paint-local
visualizer simulation, and `u_time` was confirmed to come from
`_accumulated_time` advanced in `set_state()` - never in `paint_layer()` - so
those paints revealed no new authored state.

The compositor timer remains the sole physical presentation authority and still
wakes at the display rate. It now declines to queue a GUI paint for a scene
revision it already requested, and only when the visualizer is the sole liveness
reason with no active transition. Transitions keep every admitted deadline.

Intentional suppression is reported as `unchanged_scene_skips` in the existing
cadence record and excluded from the acceptance denominator, so it cannot be
misread as a dispatch failure.

### GUI waste: an unchanged style rebuilt the painted frame shadow

Frame-shadow regeneration was measured at 8-20+ ms of synchronous GUI work.
`set_background_border()`/`_apply_border_width()` already returned early on an
unchanged value; `set_show_background()`, `set_background_color()`,
`set_background_opacity()` and `set_background_corner_radius()` did not, so every
repeated identical style apply during setup, settings refresh or reconstruction
rebuilt the frame for pixels that could not differ.

The remaining P2-PERF-B candidates - reconstruction warmup, off-GUI raster
preparation, repeated transition setup - were deliberately not landed: current
evidence does not name a specific owner concretely enough to change source
without speculating.

### Still open

The dominant visualizer-feel problem remains the logical tick being serviced
late: ~65-70 logical FPS against a ~90-100 Hz target, with recurring 42-80 ms
gaps in ordinary playback, alongside queued-GUI-dispatch ages in the same class.
Whether removing the above waste moves it is the question the next acceptance
answers.
