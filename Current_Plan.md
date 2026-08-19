# Current Plan — P2 Shared Presentation Recovery After Third Installed Acceptance Failure

Last updated: 2026-08-19 20:19 SAST  
Branch: `main`  
Installed behavioral checkpoint from the log itself:

```text
[SOURCE_HEAD] 8ac2421e2bc0a7153942fc33eb9f348b505cde9d
```

Named accepted rollback/fidelity baseline:

```text
4.7.2
42033c84eabbdf25ccd34bb0e83f9e553f2f8f11
```

Architecture epoch:

```text
one QRhi/OpenGL physical compositor surface per display
+
one dedicated mode-general visualizer logical runtime
+
latest-state publication
```

This file owns unfinished P2 work.

A later documentation-only commit does not supersede the installed behavioral checkpoint above. Do not reinterpret the tested code epoch merely because these Markdown files are committed afterward.

---

# 0. Executive truth

## 0.1 P2 is substantially failing

The third installed acceptance is the worst observed presentation run in this recovery sequence.

Operator report:

- general performance is terrible;
- transitions are universally poor;
- Pause/Play hitching remains and feels worse;
- the hitch occurs through both mouse transport controls and physical media-key input;
- the hitch affects all visualizer modes, not only Bubble;
- the visualizer as a whole is performing worse than in prior installed runs.

The logs agree with the broad failure.

This is no longer a reasonable point for another sequence of tiny edge patches.

## 0.2 The problem is shared/system-level

Retain the existing doctrine:

> Bubble is a temporal canary, not the presumed owner.

All visualizer modes share the degraded presentation environment.

The 165 Hz display that does not own the visualizer also collapses during ordinary transition work.

The dominant installed signature remains:

```text
logical/source/compute work continues
        ->
latest logical state exists
        ->
GUI delivery/presentation is not serviced promptly
        ->
queued GUI dispatch remains pending
        ->
later physical presentation opportunities are skipped
        ->
visualizer modes hitch
AND
other-display transitions lose cadence
```

The next active work therefore moves to the shared logical-to-GUI-to-physical-presentation ownership boundary.

---

# 1. What the latest run actually established

## 1.1 Source identity diagnostic works

The log contains:

```text
[SOURCE_HEAD] 8ac2421e2bc0a7153942fc33eb9f348b505cde9d
```

Keep this diagnostic.

It is:
- script/debug only;
- local Git metadata only;
- one lookup per process;
- absent from compiled builds;
- not a GitHub/network dependency.

## 1.2 Slice K implementation is real; its causal claim failed

Slice K removed the GUI wait from ordinary GSMTC transport command submission.

Retain the non-blocking command ownership unless exact command-correctness evidence disproves it.

However the installed product falsifies the claim that the old synchronous wait was the owner of:
- the visible Pause/Play hitch;
- the broad `dispatch_pending_skips`;
- the visualizer cadence collapse.

Why:

- mouse Pause/Play still hitches;
- physical media-key Pause/Play also hitches;
- all visualizer modes exhibit the edge problem;
- broad transition/presentation performance is worse even though the transport command wait is gone.

K fixed a real latency-sensitive design flaw. It did not fix the product failure.

Do not spend another slice proving K is asynchronous. That property is already established.

## 1.3 Slice L is not accepted as a production performance fix

Slice L introduced a feedback-only `MediaWidget` paint branch.

Its deterministic test proves that, for an artificially clean controls-row-only real Qt repaint event, five named expensive subpainters can be skipped.

The installed application still shows frame-count-scale `media.paint` activity with high cost.

Representative current windows include approximately:

```text
50 calls @ 5.11 ms average
50 calls @ 4.95 ms average
50 calls @ 5.22 ms average
50 calls @ 5.90 ms average
45 calls @ 6.39 ms average
```

Therefore the production objective:

```text
animated feedback is genuinely lightweight
```

is NOT established.

Possible reasons include:
- real Qt damage coalescing widens the event and bypasses the containment fast path;
- `BaseOverlayWidget.paintEvent()` still executes on the feedback branch;
- another parent/card paint path overlaps the animation;
- parent paint cost itself remains too large.

Do not call Gate 7C green from the existing unit test.

Do not make this the only next task. It is now one contributor inside a larger GUI-availability problem.

## 1.4 A stale slow-tick diagnostic can throw inside the logical runtime

The installed run contains:

```text
NameError: name 'is_transition_active' is not defined
```

from the slow-tick diagnostic path in `widgets/spotify_visualizer/tick_pipeline.py`.

The logical runtime catches the failure and continues, which turns the defect into a timing hole instead of a process crash.

This stale diagnostic reference already existed before K/L and therefore does not explain the whole regression.

Required:
- fix it immediately while touching this area;
- add a regression gate that the slow-tick diagnostics themselves cannot throw;
- do not elevate this into the supposed sole root cause.

---

# 2. How much the third installed run regressed

Compared with the previous installed acceptance, approximate observed classes:

| Metric | Previous run | Third run |
|---|---:|---:|
| 165 Hz completed transition median | ~140.2 FPS | ~111.5 FPS |
| 165 Hz worst completed window | ~136.4 FPS | ~64.7 FPS |
| 165 Hz request acceptance median | ~90.1% | ~75.6% |
| 60 Hz transition median | ~56.9 FPS | ~52.5 FPS |
| 60 Hz worst completed window | ~55.6 FPS | ~41.3 FPS |
| late-run event-loop p95 | ~12.9 ms | ~27.7 ms |
| frame-gap event rate | ~0.68/s | ~2.78/s |
| media.paint average | ~3.16 ms | ~5.37 ms |
| media.paint CPU/sec | ~14.2 ms | ~20.3 ms |
| logical skipped deadlines | ~0.09% | ~0.32% |

Representative 165 Hz completed windows in the third run include:

```text
108.7
64.7
96.1
114.2
133.0
119.7 FPS
```

One delivery window fell to roughly:

```text
54.47% request acceptance
673 dispatch_pending_skips
dispatch-skip age p95 ~143.7 ms
```

This is a system-level presentation failure, not a marginal tuning miss.

---

# 3. Important environment qualification

The third run also carried higher machine CPU load than the previous run.

Approximate observed class:

```text
previous system CPU: low/mid-20%
third-run system CPU: ~41–44%

previous SRPSS CPU median: ~88%
third-run SRPSS CPU median: ~104%
```

GPU remains low, approximately the few-percent class.

Therefore:

- do not falsely claim K or L alone caused the entire numeric regression;
- do not dismiss the regression as “external CPU” either.

SRPSS itself consumed more CPU and its GUI/presentation system became dramatically more fragile under contention.

A screensaver on this hardware must not collapse into 65–110 FPS high-refresh delivery because total CPU load is in the ~40% class.

The architecture must tolerate ordinary contention without losing the GUI for 50–150 ms at a time.

---

# 4. Adaptive timer status

The latest run again does NOT name adaptive deadline wake precision as the dominant owner.

Observed class:

```text
wake lateness p95: generally a few ms
paint_pending_skips: 0
dispatch_pending_skips: dominant
GUI dispatch / skip age: tens to >100 ms
```

Do not:
- lower target display Hz;
- retune timer precision;
- restore vsync;
- replace the adaptive timer merely because presentation is poor.

The timer is usually waking and attempting delivery.

The GUI is frequently not available to service that delivery.

---

# 5. Active architecture correction — remove steady-state worker -> GUI callback pressure

## 5.1 Current seam

The dedicated logical runtime publishes immutable latest state to `_logical_mailbox`.

Current `_publish_logical_state()` then calls:

```python
request_logical_present(widget)
```

whenever the dedicated logical runtime exists.

This means the ~90 Hz logical producer continuously marshals GUI presentation work merely because a fresher logical state exists.

Meanwhile physical display presentation is already independently paced at the display/compositor layer.

On the current 60 Hz visualizer display this can create up to ~90 logical freshness notifications for at most ~60 physical presentation opportunities.

Those GUI callbacks also share one GUI thread with the 165 Hz display's transition delivery and ordinary widgets.

This is now an active architecture target.

## 5.2 Required replacement shape

Retain:

```text
VisualizerLogicalRuntime @ authored cadence
        ->
thread-safe latest-state mailbox/revision
```

Change steady-state delivery toward:

```text
physical display presentation opportunity
        ->
GUI/compositor samples freshest current-generation logical state
        ->
apply current presentation state
        ->
render
```

The logical producer must not need to enqueue one GUI callback for every ordinary published logical revision.

The exact current-source implementation can choose the narrowest safe seam, but the required ownership is:

### Logical worker owns
- authored logical time;
- source/event/smoothing/simulation evolution;
- immutable latest-state publication;
- mailbox revision/current-generation state.

### GUI/presentation owner owns
- QWidget geometry;
- card/background pixels;
- reveal/fade side effects;
- compositor layer state;
- GL/QRhi interaction;
- physical presentation.

### Physical presentation opportunity owns
- sampling the freshest available logical revision;
- deciding whether a new visualizer revision must be applied before that display frame.

No FIFO.
No catch-up.
No replay of intermediate logical states.

At 60 Hz, presentation naturally samples the freshest ~60 of the ~90 logical states.

At 165 Hz, transition/compositor presentation remains free to run at display cadence while visualizer logical state changes only at its authored cadence.

## 5.3 Freshness without callback-per-state

Do not solve this by introducing another 90 Hz GUI timer.

Use a thread-safe mailbox revision / dirty revision / equivalent existing primitive that the presentation owner can observe at its normal display opportunity.

If the adaptive/compositor scheduler currently suppresses presentation when scene revision is unchanged, integrate logical-mailbox freshness into the scheduler's existing notion of pending scene work without posting a full GUI presentation callback for every logical tick.

The worker may publish plain thread-safe state/revision.

It may not call QWidget, QPixmap, QPainter, GL or QRhi APIs.

## 5.4 Edge events remain explicit

Not every logical publication is equivalent to a steady-state frame.

Explicit edge/lifecycle operations may still require one bounded GUI marshal, including:
- mode reveal;
- card reveal/hide;
- geometry changes;
- activation/generation changes;
- teardown/recreation;
- other GUI-owned state changes.

Do not eliminate required edge handoffs merely to reduce callback count.

The goal is:

```text
remove continuous steady-state callback pressure
while
preserving explicit edge/lifecycle ownership
```

---

# 6. Required production-shaped regression gates for the architecture replacement

Do not create an A/B installed experiment.

Build deterministic bars around the intended ownership.

## Gate A — steady logical publication does not enqueue GUI work per revision

Drive the dedicated logical runtime through many ordinary logical steps.

Prove:
- mailbox revision/state advances at authored cadence;
- ordinary steady-state publications do not call/enqueue `present_logical_frame` once per logical step;
- there is no hidden replacement 90 Hz GUI timer;
- no FIFO/backlog forms.

Negative control:
the old callback-per-publication seam must fail the callback-count bound.

## Gate B — physical presentation samples newest state

Publish logical revisions faster than a simulated/controlled presentation consumer.

On each physical presentation opportunity:
- consume/apply the newest current-generation revision;
- intermediate stale revisions are not replayed;
- state age remains bounded by logical + display cadence;
- generation/activation fences remain enforced.

## Gate C — all visualizer modes retain semantics

Exercise all five modes.

Prove:
- logical reactions still advance at authored cadence;
- presentation sees current mode state;
- mode switching reveals correctly;
- paused Spectrum idle remains visible;
- no Bubble trajectory/cadence retuning;
- no source smoothing/decimation;
- no CPU/QPainter visualizer fallback.

## Gate D — two-display independence

With a controlled 60 Hz visualizer consumer and 165 Hz transition/display consumer:

- 60 Hz visualizer sampling must not require ~90 GUI callbacks/s from the logical producer;
- 165 Hz display opportunities must remain independently serviceable;
- no global lock/queue couples the two display rates;
- visualizer state publication on one display must not create a callback backlog that starves the other.

This is a deterministic ownership/scheduling test, not an installed FPS benchmark.

## Gate E — edge GUI handoffs still work

Pause/Play, mode switch, Settings/recreate and reveal/hide edges must:
- execute required GUI-owned mutations exactly once/bounded;
- preserve generation fences;
- preserve warm visualizer ownership;
- not restore playback debounce;
- not create a second logical clock.

## Gate F — slow-tick diagnostics cannot throw

Force the slow-tick diagnostic path.

No exception may escape or increment logical-runtime failure count.

---

# 7. Pause/Play after K — trace the common edge, not the transport mechanism

The latest operator report distinguishes two input paths:

```text
mouse transport click
physical media key
```

Both still produce the visualizer hitch.

Therefore do not return to “the WinRT command blocks the GUI.”

The common owner must be downstream of the point where those input paths converge, for example:
- accepted playback-state propagation;
- visualizer playback-edge wake/state application;
- shared feedback/state notification;
- GUI invalidation caused by playback state;
- logical/presentation edge handoff.

While implementing the shared presentation correction, trace the exact common playback-state edge in current source.

If a synchronous/repeated GUI operation is plainly present there, correct it in the same architecture slice and lock it with a deterministic gate.

Do not add a new telemetry campaign merely to rediscover that both input methods visibly hitch.

Acceptance is all-mode:
- Bubble;
- Spectrum;
- Devcurve;
- remaining visualizer modes.

---

# 8. Media feedback remains open but secondary

Keep Slice L's selective paint work only if it is visually correct and does not create broader invalidation problems.

Do not claim it solved the production cost.

During the architecture work:
- inspect why installed events still produce high `media.paint` cost;
- if the fast path is routinely defeated by coalesced damage, repair the ownership rather than adding another containment special-case;
- a dedicated lightweight child/overlay remains acceptable if that is cleaner than forcing parent-paint region inference.

Do not lower feedback animation cadence as the fix.

Do not let feedback work derail the shared presentation correction into another week of local paint micro-optimization.

---

# 9. Explicit prohibitions

No:
- another generic probe/instrumentation phase;
- A/B production architecture branch;
- lowering visualizer logical cadence;
- lowering display target Hz;
- Bubble retuning;
- source/audio smoothing;
- source/event decimation;
- playback debounce;
- FIFO/catch-up;
- paint acknowledgement/backpressure;
- second visualizer surface;
- second logical clock;
- per-transition fidelity cuts;
- broad “move everything to workers” rewrite;
- vsync restoration as a diagnostic experiment.

The next change should remove an ownership/callback mechanism, not layer another scheduler on top of it.

---

# 10. What may be rewritten

The project is no longer constrained to baby-step patches if the current owner boundary is the defect.

A bounded architecture replacement is allowed when:
- existing behavioural contracts are retained;
- one source-owned boundary is replaced;
- old callback/timer/state machinery is deleted rather than duplicated;
- lifecycle/generation ownership remains explicit;
- deterministic negative controls prove the removed bad shape;
- rollback remains coherent.

Architecture elegance is not the goal.

Removing shared GUI starvation while preserving authored behavior is.

---

# 11. Installed acceptance after the architecture slice

After the shared presentation correction and focused gates pass, request ONE installed script/debug acceptance run.

Use the normal comprehensive diagnostic command.

The log must identify itself via:

```text
[SOURCE_HEAD] <sha>
```

Exercise:
1. startup both displays;
2. each visualizer mode;
3. ordinary and rapid mouse Pause/Play;
4. physical media-key Pause/Play;
5. long Bubble observation;
6. ordinary 165 Hz transitions while visualizer remains active on the other display;
7. paused Spectrum idle;
8. mode switching;
9. Settings/recreate;
10. clean shutdown.

Hard fail:
- Pause/Play hitches in any visualizer mode;
- visible all-mode cadence holes;
- recurring ordinary >33 ms BTF holes;
- 165 Hz display remains in the current ~65–130 FPS collapse class;
- request acceptance remains in the current ~55–80% collapse class;
- 60 Hz visualizer presentation visibly steps;
- logical-runtime failures/exceptions;
- generation/lifecycle regression.

The installed product decides closure.

---

# 12. P2 is not allowed to close merely because this architecture slice lands

The third installed run proves that the broader problem is still substantial.

Even if the steady-state callback replacement is correct, P2 remains open until:
- all-mode visualizer hitching is gone;
- Pause/Play is perceptually clean through mouse and media-key paths;
- high-refresh transition delivery returns toward the accepted class;
- BTF tails are controlled;
- lifecycle remains correct.

If the next installed run still fails, continue from the new source/log evidence.

Do not convert “no probe treadmill” into “stop after one architecture commit.”
