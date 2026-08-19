# Current Plan

Last updated: 2026-08-18
Branch: `main`
Current source anchor: `0adb1a56` (P2-CUSTOM-CANCEL, Gmail ownership, PERF-A, PERF-B landed)
Architecture epoch: **OpenGL QRhi, one accelerated presentation surface per physical display**

This file owns unfinished active work and execution order. Current source and installed evidence
override old completion claims. Phase reports and Historical_Bugs remain evidence, not current
ownership maps. `Future_Cleanup.md` is deferred debt only and must not absorb active correctness
or performance work.

`versioning.py` remains user-owned unless a version change is explicitly requested.

---

## 1. Binding architecture and product contract

### 1.1 One accelerated presentation surface per physical display

Each display has one `GLCompositorWidget` / `ExternalOpenGLRhiWidget` using Qt's OpenGL QRhi
backend. SRPSS borrows Qt's QRhi/OpenGL context; it does not own the top-level context,
`swapBuffers()`, or context destruction.

The Spotify visualizer is not another surface.

`SpotifyBarsGLOverlay` is a plain, non-presented QWidget used for logical visualizer state,
CUSTOM/geometry anchoring, shader/uniform state and visualizer GL-resource ownership where
applicable. `CompositorVisualizerLayer` presents the card and visualizer pixels inside the display
compositor.

Do not reintroduce:
- a second QOpenGLWidget/QRhiWidget visualizer surface;
- CPU/QPainter substitute visualizer rendering;
- `hw_accel=off` compatibility rendering;
- application-owned top-level swaps or Qt context destruction.

### 1.2 Logical cadence and physical presentation are separate

The visualizer owns:
- audio/source sampling;
- logical tick/simulation;
- dt/events/transients;
- smoothing and authored state evolution;
- latest immutable render-state publication.

The display compositor owns physical presentation opportunities.

No producer waits for paint. No paint acknowledgement/backpressure, pending-until-paint admission,
source/display divisor gate, catch-up replay, second visualizer clock or paint-local visualizer
simulation.

A queued GUI-dispatch guard may prevent duplicate Python callbacks only while the previous callback
has not yet reached `QWidget.update()`. Paint completion is not an admission authority.

### 1.3 Visualizer feel is a first-class contract

The visualizer lock protects user-visible behaviour, not historical implementation accidents.

Required feel:
- lowest practical reaction latency;
- authored reactions should almost never be missed;
- smoothing, when enabled, should look continuous rather than stepped;
- mode/preset/generation changes must not poison later state;
- Bubble, Spectrum, Sine, Oscilloscope and DevCurve retain their authored personality and fidelity.

Do not improve counters by lowering source cadence, logical cadence, target refresh, event rate,
visual fidelity or responsiveness.

### 1.4 Efficiency means removing waste

SRPSS should be cheap enough that ordinary accelerated hardware is plausible even though current
development evidence comes from high-end hardware.

Optimize:
- duplicate computation;
- redundant paint/presentation of an unchanged scene;
- unnecessary GUI callbacks;
- cache/raster rebuilds whose revision has not changed;
- repeated setup/warmup;
- allocation/Future/task churn where an already-approved lower-churn mechanism exists;
- unnecessary synchronization/copies.

Do not add “energy efficiency” throttles or deliberately reduce useful cadence. A discrete GPU being
awake is not itself a defect. High sustained CPU/GPU utilization caused by unnecessary work is.

---

## 2. What the 2026-08-18 acceptance DID establish

The previous P2 regressions are repaired in the installed runtime and remain retained:

- the real audio callback is live; the `time.time()` callback failure is gone;
- Bubble becomes live/reactive;
- mode changes work through the context menu and Settings;
- all five modes come back correctly;
- mode fades now look good;
- the pre-fade flash is fixed;
- cross-mode generation poisoning/dead-mode behaviour is not reproduced;
- Bubble latency feels materially better / at least decent enough that cadence is now the dominant
  perceptual problem.

Do not reopen P2-R1/R2/R3, the card-region fix, the card-texture lifetime fix, the one-fade authority,
or single-surface architecture without new contradictory evidence.

CUSTOM/Edit is also mostly successful:
- compositor-owned edit preview works;
- move/resize works;
- Save generally works;
- cross-display visualizer movement generally works.

P2 is **not closed** because the same acceptance exposed:
1. a reproducible Cancel restore failure;
2. one real fail-closed application exit during cross-display CUSTOM Save;
3. visibly poor/stuttery visualizer cadence;
4. highly variable transition delivery;
5. post-migration CPU/GPU usage still needing a clean final acceptance.

---

## 3. P2-CUSTOM-CANCEL — PROVEN mid-runtime resume ownership bug

### Installed evidence

The short `--geo` run proves the Cancel failure is **not geometry loss**.

Before edit, the visualizer is:

```text
local=(672,948,721,481)
global=(3232,948,721,481)
```

At Cancel, CUSTOM replay restores exactly that rectangle through:

```text
replay_start
replay_after_payload
replay_after_update_position
replay_final
```

The audio worker is stopped on edit entry.

On Cancel the current restore path calls the visualizer's ordinary `start()`. The log then records:

```text
Seeded playback state from anchor (start ... state=playing)
Deferred hot start to Spotify secondary stage
```

and no later `Audio worker started` appears before the run exits.

### Source cause

`CustomLayoutManager._pause_visualizer_for_edit_mode()` currently uses the ordinary visualizer
`stop()` path and `_restore_special_widgets()` uses the ordinary visualizer `start()` path.

`startup_staging.start_legacy()` is a startup lifecycle entry point. When the visualizer has already
completed its process/runtime secondary stage, a mid-runtime Cancel can re-enter `start_legacy()`,
see `_startup_secondary_stage_pending`, defer to the Spotify secondary-stage event, and then wait for
an event that is one-shot and has already happened.

The existing CUSTOM test only stubs `vis.start()` and proves that the stub was called once. It does
not exercise a real visualizer after its normal startup secondary stage has already completed.

### Required correction

Edit mode needs an explicit **edit suspend/resume** contract. It must not pretend a mid-runtime edit
session is cold startup.

Entering edit:
- capture compositor-owned preview once;
- suspend/hide compositor visualizer presentation;
- pause the logical visualizer/audio work required by edit mode;
- retain current runtime generation, committed mode/config and GL resources;
- do not reset mode state or re-enter startup staging.

Cancel:
- restore the original authoritative CUSTOM geometry;
- resume the existing visualizer runtime directly;
- restart/reacquire audio capture exactly once if edit suspension stopped it;
- resume the normal logical tick;
- restore compositor visualizer presentation through the current fade/readiness owner;
- no startup-secondary event is required;
- no engine generation change merely because edit mode was cancelled;
- no duplicate card texture/program creation.

Save still owns the existing full runtime replacement boundary where required.

### Production-shaped bar

The owning test must perform:

```text
normal visualizer startup
-> secondary stage actually completes
-> playing/live visualizer
-> enter CUSTOM
-> edit suspend
-> Cancel
-> no second secondary-stage callback
-> audio/tick/presentation live again
```

Use real startup/edit state-machine owners with only external services faked. A `SimpleNamespace`
whose `start()` merely increments a counter is not sufficient.

---

### Landed

`startup_staging` gained an explicit edit seam. `suspend_for_edit()` stops logical admission,
the tick and the engine reference while keeping the runtime generation, staged-startup
bookkeeping, committed mode/config, engine identity and GL resources. `resume_after_edit()`
resumes that same runtime: re-seeds playback state, re-acquires the engine without resetting it,
restarts capture exactly once, restarts the logical tick, and arms only the reveal gate so
presentation returns through the current fade/readiness owner. No secondary-stage event is
required and no engine generation changes.

`CustomLayoutManager` prefers the seam and falls back to `stop()`/`start()` for a visualizer
without it. The stub-only Cancel bars are retired; the replacement drives the real startup/edit
state machine with the real audio worker over a fake capture device.

## 4. CUSTOM cross-display “crash” — PROVEN fail-closed lifecycle timeout

The one apparently non-reproducible crash was real, but it was **not a native visualizer crash**.

At 22:47:32 the visualizer Save moved from monitor 2:

```text
global=(3232,948,721,481)
```

to monitor 1:

```text
global=(936,408,721,481)
```

CUSTOM runtime generation 5 retired normally and the destruction barrier armed.

Exactly at the barrier deadline it reported:

```text
[LIFECYCLE_BARRIER] timeout reason=custom_edit retiring_generation=5
thread_work=[
  {
    category: gmail_fetch,
    pool: io,
    owner_class: GmailWidget,
    runtime_generation: 5
  }
]
```

The application then exited code 1 under the existing fail-closed lifecycle policy.

This explains why repeating the same visualizer transfer did not necessarily reproduce it: the
failure requires an old-runtime Gmail network fetch to be in flight during the replacement window.

### Source cause

`GmailWidget._fetch_emails_async(generation)` checks cancellation/generation before entering
`self._gmail_client.list_messages(...)`.

Cleanup correctly sets `_cancelled=True` and advances widget fetch generations, but an already-running
REST request does not observe that state until the blocking network call returns.

`GmailClient` currently permits a request to remain in network I/O well beyond the runtime
destruction barrier (`requests` connect/read timeout plus retries, followed by per-message metadata
requests).

The destruction barrier is doing its job: it sees retiring-generation work still alive and refuses
to construct a replacement.

### Required correction

Do **not**:
- extend the 8-second destruction timeout;
- ignore `gmail_fetch` in barrier accounting;
- call the replacement continuation while old runtime work still executes;
- convert this to a warning;
- weaken fail-closed teardown.

Correct the ownership/cancellation boundary.

Preferred outcomes, in order:

1. A runtime-owned Gmail fetch becomes cooperatively cancellable and returns promptly when its
   runtime generation retires, including while traversing list/metadata requests; or
2. if Gmail network retrieval is intentionally process-scoped and allowed to survive display
   replacement, move the network operation to a genuinely process-scoped data-service owner and
   make the retiring widget only a generation-fenced consumer.

Do not merely relabel widget-owned work as global.

Use bounded request chunks/timeouts/cancellation checks as appropriate. Preserve existing Gmail
semantics and cached-data behaviour.

### Production-shaped lifecycle bar

Hold a controllable Gmail request in flight across:

```text
CUSTOM Save
-> runtime generation invalidation
-> display/widget cleanup
-> destruction barrier
```

Then prove:
- retiring-generation widget work is cancelled/settled;
- barrier completes rather than timing out;
- replacement runtime may start;
- stale fetch result cannot apply to the new runtime;
- terminal fail-closed behaviour remains intact for a genuinely unretired owner.

---

### Landed

The cancellation boundary is corrected at the producer, not the barrier.
`GmailClient.list_messages()`/`_get_message_metadata()`/`_make_request()` and the IMAP client
accept a cancellation predicate and check it before the list request, before every metadata
request and before each retry, raising `GmailFetchCancelled`. `GmailWidget` passes a
generation-fenced predicate and treats cancellation as quiet abandonment: no error, no UI
callback for a retired generation, fetch guard still released.

The barrier, its 8-second budget and its `gmail_fetch` accounting are untouched, and tests pin
all three. A client without the seam still works through an explicit fallback.

## 5. P2-PERF — current bottleneck is delivery/cadence, not visualizer rendering

### 5.1 Renderer/GPU are substantially exonerated

The short valid Bubble run reports approximately:

```text
Bubble worker                  ~1.44–1.50 ms
Bubble tick body               ~0.97–1.12 ms
Bubble submitted/published     596 / 596
Bubble busy deferrals          0
Bubble stale results           0

visualizer paint CPU p50       ~0.56 ms
visualizer paint CPU p95       ~0.90 ms
visualizer GPU p50             ~0.95 ms
visualizer GPU p95             ~1.17 ms
state -> paint p50             ~5.14 ms
state -> paint p95             ~11.12 ms
```

The visualizer shader/card renderer is not large enough to explain recurring 40–90 ms visible
motion gaps.

Do not tune shaders, reduce Bubble complexity or lower visual fidelity to fix this.

### 5.2 The logical visualizer clock is being serviced late

The logical tick is still a GUI-thread `QTimer` created by `ThreadManager.schedule_recurring()`.
Live playback targets approximately 90–100 logical Hz.

Installed windows instead show broad variation. The short Bubble run reaches only roughly:

```text
65.3–69.7 logical FPS
dt_max ~87.8 ms
```

with repeated ordinary-playback tick gaps around 42–80 ms.

Longer acceptance windows can reach the high-70s/80s and occasionally near the intended band, but
the recurring long gaps make motion visibly chug even when average FPS looks less alarming.

This is the primary visualizer-feel problem now.

### 5.3 Physical compositor delivery shows the same GUI-service pressure

The old paint-acknowledged admission bug is gone:

```text
paint_pending_skips=0
```

throughout current evidence.

The remaining loss is queued-GUI-dispatch delay. Examples include:

```text
165 Hz, no transition:
    target=165
    accepted=4159/4769 = 87.21%
    dispatch_pending_skips=610
    dispatch skip p95 age ~43 ms
    max ~102 ms

60 Hz after recreation:
    acceptance ~75%
    dispatch skip p95 age ~50 ms
    max ~105 ms
```

A queued callback sitting for tens of milliseconds and a GUI-owned visualizer timer firing tens of
milliseconds late are two manifestations of GUI/event-loop service pressure.

This does not yet prove one single callback family owns every gap. It does prove the missing time is
not primarily inside visualizer GL paint.

### 5.4 Transition delivery is genuinely variable

The acceptance contains 165-Hz BlockSpin windows ranging roughly through:

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

while the 60-Hz side is generally in the high-50s/near-60 but with large dt tails.

Some good windows prove the QRhi compositor can still deliver materially better than the worst
windows. Treat this as scheduling/workload variability, not a new hard GPU ceiling.

### 5.5 Existing evidence already names concrete GUI work worth removing

Do not begin with another instrumentation campaign.

Current `perf_widgets`/frame-gap evidence already contains synchronous GUI work such as:
- Reddit cache regeneration reaching tens of milliseconds and much larger startup/recreation spikes;
- painted frame-shadow regeneration commonly around 8–20+ ms across several widgets;
- transition/recreation setup callbacks in the ~10–20 ms class;
- shader/program warmup clustered around reconstruction/startup.

These do not individually explain every steady visualizer gap, so do not claim one of them as the
sole owner. They are nevertheless real avoidable GUI pressure and valid optimization targets where
the same pixels/result can be retained.

### 5.6 Important negative finding — visualizer publication is already separated from presentation

Do not “fix” a mechanism that is no longer present.

`SpotifyBarsGLOverlay._request_frame_update()` has a legacy-sounding name and increments the
`update_requests` perf counter, but current source only publishes latest visualizer state to
`GLCompositorWidget.publish_visualizer_state()`.

It does **not** issue one QWidget paint request per logical publication.

The compositor render strategy remains the sole physical presentation requester.

Keep that architecture.

### 5.7 Important historical guardrail — do NOT reactivate the rejected persistent Bubble lane

Current production `BubbleComputeLane` is intentionally a compatibility facade over the approved
general COMPUTE executor path. Its source explicitly says the persistent Bubble scheduler was
rejected and production returned to the approved pre-lane semantics.

Current evidence therefore legitimately reports:

```text
lane_registrations=0
executor_tasks=<one per accepted Bubble step>
```

That per-step allocation/task churn is real, but **do not reactivate `create_compute_lane()` or the
rejected persistent scheduler as an optimization shortcut**.

If task/Future churn later proves to own meaningful CPU/GIL pressure, design a new bounded mechanism
from the accepted semantics and test it against the full Bubble trajectory/event contract. That is
not the first move in this slice.

---

## 6. P2-PERF-A — stop physically presenting an unchanged visualizer scene

There is one safe architectural waste target already exposed by the single-surface design.

When the visualizer was on the 165-Hz display, a representative 10-second window showed roughly:

```text
logical/state publications     ~86.6 / sec
physical paints                ~140.7 / sec
display refresh                ~164.8 Hz
state -> paint p50             ~5 ms
```

A large fraction of visualizer-only physical paints therefore present the exact same latest scene
again.

P1 forbids paint-local visualizer simulation, so an unchanged published render state has no new
authored visualizer state to reveal.

### Required mechanism

Keep the compositor timer as the sole physical presentation authority.

Add/retain a monotonically changing **scene revision** (or equivalent existing generation/revision)
on compositor visualizer publication.

When an image transition is active:
- render every admitted physical display deadline exactly as today.

When no image transition is active and visualizer presentation is the only liveness reason:
- at a compositor deadline, request a physical paint only if the visualizer/card/fade scene revision
  has advanced since the last requested/presented visualizer scene;
- if the scene is unchanged, do not queue a redundant GUI update;
- the compositor timer may still wake at the display rate; a cheap revision comparison is enough.

This is **not**:
- a logical cadence cap;
- a display-refresh divisor;
- producer-owned paint scheduling;
- a second clock;
- source/event decimation.

On a 60-Hz display with ~90–100 Hz logical state, almost every physical deadline should still have a
new state and presentation remains refresh-limited.

On a 165-Hz display, visualizer-only physical work naturally follows useful authored scene revisions
rather than redrawing the same state ~165 times/sec.

During compositor-owned fade/preparation, every fade/card change must advance the useful scene
revision or temporarily bypass unchanged-scene suppression. Do not freeze the fade.

Before landing, prove no visualizer mode evolves from paint-local wall-clock state. If any does, move
that evolution back to the logical authority rather than preserving duplicate physical paints as a
hidden simulation clock.

Extend the existing cadence summary with one bounded `unchanged_scene_skips` (or equivalent) counter
so intentional no-change suppression is not misreported as dispatch failure. Do not create a new
diagnostic family.

### Landed

`CompositorVisualizerLayer` owns a monotonic `scene_revision`, advanced by every publication,
by `clear()` and by explicit invalidation. `GLCompositorWidget.presentation_scene_revision()`
reports it only when the visualizer is the sole liveness reason with no active transition, and
`None` otherwise. The adaptive timer declines to queue a GUI paint for a revision it already
requested; `request_frame()` is always eligible.

Suppression is reported as `unchanged_scene_skips` inside the existing cadence record and is
excluded from the acceptance denominator. `u_time` was confirmed to come from
`_accumulated_time`, advanced in `set_state()` and never in `paint_layer()`, so no mode was
using duplicate physical paints as a hidden simulation clock.

### Tests

- no transition + unchanged revision -> no GUI update request;
- no transition + new revision -> one update opportunity;
- 90–100 Hz publication / 60-Hz display -> no useful state loss;
- 90–100 Hz publication / 165-Hz display -> no duplicate unchanged presentation requirement;
- active transition -> every display deadline remains eligible regardless of visualizer revision;
- fade progress change -> remains eligible;
- no paint-local mode evolution.

---

## 7. P2-PERF-B — bounded GUI-thread waste/churn reduction

After the correctness fixes and unchanged-scene suppression, use **existing** perf evidence to remove
the highest-cost synchronous GUI work that is duplicative or can be prepared outside the live turn.

Rules:
- one mechanism/owner per commit;
- preserve pixels and cache identities;
- no cadence/fidelity cuts;
- QPixmap/QWidget/GL mutation stays on its legal GUI/context owner;
- worker preparation may use QImage/plain data only;
- no global cache that violates runtime-generation or borrowed-GL ownership;
- no broad “optimize everything” refactor.

Priority candidates:
1. duplicate/needless card/frame-shadow/cache regeneration across unchanged style/geometry revisions;
2. reconstruction warmup that can be completed before reveal rather than during live cadence;
3. pure raster/cache preparation that can be prepared as QImage/plain data off GUI and committed once
   on GUI;
4. repeated transition setup work whose immutable result is already valid for the current QRhi
   generation.

Do not simply move work to a worker if it still requires GUI synchronization on every frame.

Do not touch Bubble authored complexity or smoothing to improve transition FPS.

If the existing evidence cannot justify a concrete source change for a candidate, skip that candidate
rather than inventing a speculative rewrite.

---

### Landed

`BaseOverlayWidget.set_show_background()`, `set_background_color()`,
`set_background_opacity()` and `set_background_corner_radius()` rebuilt the painted frame
shadow unconditionally. Their siblings `set_background_border()`/`_apply_border_width()`
already returned early on an unchanged value; these four now do too, so a repeated identical
style apply during setup, settings refresh or reconstruction no longer invalidates the shared
frame and rebuilds the pixmap synchronously. Pixels and cache identity are unchanged.

Candidates 2-4 were not landed: existing evidence does not yet name a specific reconstruction
warmup, raster preparation or transition-setup owner concretely enough to change source without
speculating. They stay listed above rather than being invented.

## 8. Do not jump straight to a timer-rate “fix”

Increasing the visualizer QTimer target above 90–100 Hz will not repair a timer that already suffers
40–90 ms service gaps.

Likewise:
- do not cap it lower;
- do not evolve visualizer state in compositor paint;
- do not interpolate away missed logical reactions;
- do not borrow transition AnimationManager ticks;
- do not make compositor refresh the visualizer simulation clock.

If, after Sections 3/4/6/7, steady ordinary playback still has recurring >33 ms logical-tick holes,
the next architecture correction is **logical cadence isolation from GUI delivery**.

That would require first extracting a Qt-free logical step/state owner and a latest immutable
publication bridge. Do not move the current QWidget-touching `_on_tick()` wholesale onto a worker
thread.

That larger step should only begin from fresh post-waste-removal evidence.

---

## 9. One installed acceptance after the current slices

Do not ask the operator for an intermediate run after each commit.

After:
- P2-CUSTOM-CANCEL;
- Gmail retiring-runtime ownership/cancellation;
- P2-PERF-A unchanged-scene suppression;
- any P2-PERF-B source changes actually justified by existing evidence;

request one:

```text
python main.py --perf --gpu-timing --geo
```

### Functional/CUSTOM gate

Prove:
- startup Bubble live;
- mode switches remain good;
- all five modes still render;
- fades remain good;
- enter CUSTOM -> Cancel restores a live visualizer without another secondary-stage event;
- edit move/resize still works;
- Save still reconstructs correctly;
- cross-display visualizer Save does not exit;
- no destruction-barrier timeout;
- no stale old-generation fetch/result applies.

### Visualizer feel/cadence gate

Steady ordinary playback should approach its configured ~90–100 Hz logical target with low jitter.

The critical criterion is **not merely average FPS**. The current visible failure is recurring
40–90 ms holes. Those should disappear from ordinary steady playback except for rare external/system
events.

Retain:
- low source/reaction latency;
- no missed authored reactions;
- current smoothing;
- exact Bubble/event trajectory semantics;
- all five mode personalities.

State->paint should remain in the healthy current class (~5 ms p50, ~10–12 ms p95 rather than becoming
the new bottleneck).

### Physical presentation gate

For transition-active windows:
- 60-Hz display remains effectively refresh-limited;
- 165-Hz display should return toward the best current 150s/low-160s class with much less window-to-
  window collapse;
- `paint_pending_skips` remains zero;
- queued GUI dispatch ages/skips materially improve if GUI pressure was removed.

For **visualizer-only** 165-Hz windows after unchanged-scene suppression:
- do not demand 165 identical physical paints/sec;
- useful physical paints should track available new authored scene revisions;
- intentional `unchanged_scene_skips` are healthy, not delivery failures.

### Usage/efficiency gate

Re-establish post-migration same-machine usage.

Current evidence often has low GPU utilization while app/main CPU occupies roughly one logical-core
class or more. The desired movement is:
- lower CPU/GUI churn;
- low GPU utilization retained;
- no new callback/task backlog;
- no RAM/VRAM slope;
- tracked GL ownership returns to zero on teardown.

No throttling/fidelity sacrifice is accepted as an efficiency win.

---

## 10. P5 — MONITOR TOPOLOGY / PHYSICAL SLEEP-WAKE HARDENING — MANDATORY NEXT

P5 remains mandatory after P2 presentation/cadence closure.

Observed failure class:
- both physical displays off while saver remains active;
- long idle;
- wake can leave one SRPSS display frozen and the other black;
- clock/input/Escape/context menu can become dead;
- Ctrl+Alt+Delete can be required to disturb Windows enough to recover.

The Gmail/CUSTOM destruction failure in Section 4 strengthens this requirement: replacement must not
proceed while a retired generation still owns work. Fix the producer ownership; do not weaken the
barrier.

### P5-A — one topology decision authority

One engine/DisplayManager-level owner decides:
- no-op;
- local re-anchor/update;
- full runtime replacement.

Native Windows, Qt screen and per-window notifications are invalidation/report inputs, not competing
mutation owners.

### P5-B — true trailing-edge settlement + immutable snapshot

Every relevant topology event restarts the quiet-period timer. A bounded maximum settlement deadline
prevents endless postponement.

Freeze one accepted topology generation/snapshot before destructive work, including:
- screen count/order/identity;
- geometry/work area as required;
- DPR;
- configured visualizer display;
- topology generation.

A later topology event queues the next transaction; it does not mutate the frozen transaction.

### P5-C — transactional replacement/readiness

```text
Notify -> Settle -> Snapshot -> Retire -> Rebuild -> Reveal
```

- stop old-runtime topology mutation;
- invalidate old generation;
- retire once;
- quiesce/cancel all retiring-generation producer work;
- strict borrowed-context/owned-resource GL cleanup;
- destruction barrier proves old ownership is gone;
- construct/register complete replacement from frozen snapshot;
- replay committed CUSTOM state;
- reveal only current-generation ready displays.

Do not weaken fail-closed teardown, extend timeouts, add GL retry loops, hide/reuse old runtime or
pump nested events.

### P5-D — generic CUSTOM replay

Reapply committed display-local CUSTOM geometry generically after reconstruction. Do not hard-code
the historical Media/visualizer endpoint merely because that was the last visible breadcrumb.

Prove stale pre-rebuild widget geometry cannot overwrite committed CUSTOM state.

### P5-E — sticky configured visualizer monitor

Temporary asleep/rebuilding/non-participating display is not absence.

If the configured monitor remains in settled topology:
- keep ownership sticky;
- park/hide/defer presentation until ready;
- do not eagerly fallback.

Only genuine settled absence may arm one coarse generation-owned ~60-second confirmation. If still
absent at that single check, fallback may occur once.

Return-home is event-driven from later topology/readiness, not polling.

### P5-F — recovery-specific desktop capture boundary

Keep `screen.grabWindow(0)` for normal stable desktop -> screensaver cold-start anti-flash.

Do not make synchronous waking-desktop capture a prerequisite of topology recovery. Reuse retained
SRPSS image/replay state or wait for the first real frame.

### P5-G — physical acceptance

Exercise:
- both displays off -> long idle -> wake;
- simultaneous wake;
- D0 then D1;
- D1 then D0;
- temporary one-display topology before sibling stabilizes;
- genuine configured-monitor absence > grace;
- return before grace;
- return after legitimate fallback;
- overnight-equivalent idle.

Pass:
- both displays recover;
- normal input recovers;
- no Ctrl+Alt+Delete required;
- no eager visualizer migration;
- no stale old-generation owners/resources/tasks;
- no monitor polling architecture.

---

## 11. After P5

Only after P5:
- long-run RAM/private-commit/VRAM slopes;
- broader resource/cache efficiency with quality unchanged;
- cleanup/diagnostic retirement from `Future_Cleanup.md`;
- harness/test-flake cleanup;
- obsolete non-accelerated toggle/path retirement;
- unrelated provider/media work in separate causal slices.

`Future_Cleanup.md` does **not** need modification for this round. The Cancel restore fault, retiring
Gmail task, visualizer cadence problem and transition delivery variability are active correctness/
performance work.
