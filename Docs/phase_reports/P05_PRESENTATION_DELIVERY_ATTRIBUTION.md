# Phase 5 — Presentation / Delivery Attribution

Status: **accepted causal checkpoint; active implementation input**  
Date reconciled: 2026-08-17  
Execution owner: `Current_Plan.md`  
Cleanup/test-debt owner: `Future_Cleanup.md`

## Purpose

This report is the durable evidence record for the Phase 5 presentation/delivery work.
It keeps benchmark numbers and causal interpretation out of `Current_Plan.md`, which owns
unfinished work only.

Raw conversation ZIP names are intentionally not canonical repository evidence paths.
If the raw captures are copied into `logs/evidence_chest/`, add that path here later;
do not rewrite the interpretation merely because the storage path changes.

## Experiment Shape

The accepted comparison consists of:

1. one uninterrupted **dual-display same-process A→B→C→A run** with a 165 Hz display
   and a 60 Hz display, Spectrum active, ordinary PERF delivery-stage attribution and
   sampled `--gpu-timing`;
2. one separate **no-visualizer-from-start control** with Media/GSMTC still active and
   the visualizer disabled in Settings from runtime creation onward.

The A/B/C probe changed presentation only:

- **A_NORMAL** — production visualizer behaviour;
- **B_SUPPRESS_REQUESTS** — logical visualizer state continued publishing while the
  auxiliary `SpotifyBarsGLOverlay.update()` request was withheld;
- **C_HIDDEN_SURFACE** — B plus the still-live auxiliary GL widget hidden;
- return to **A_NORMAL** — presentation restored in the same process.

The no-visualizer control is not a same-process D state. It removes the visualizer family
at construction time and therefore supplies a strong negative control but not same-process
method-level proof.

## Accepted Results

| State | 165 Hz FPS | 165 Hz acceptance | 60 Hz FPS | 60 Hz acceptance |
|---|---:|---:|---:|---:|
| A — normal visualizer | 143.4 | 87.12% | 57.9 | 96.55% |
| B — suppress auxiliary update requests | 150.2 | 91.39% | 58.9 | 98.37% |
| C — B + hide still-live visualizer GL surface | 151.6 | 92.11% | 58.75 | 98.01% |
| A — presentation restored | 141.2 | 85.85% | 57.6 | 96.36% |
| no visualizer from startup | 156.5 | 95.11% | 59.35 | 99.09% |

The same-process reversal is the primary causal result: removing only the auxiliary
visualizer repaint-request stream improves both compositors, and restoring it degrades
them again without restarting the process.

## Stage Attribution

The adaptive render timer is not the primary owner in these failures. Target-rate wake
opportunities remain available; loss occurs after wakeup when queued GUI delivery or
already-dispatched paint delivery remains pending long enough that later deadlines are
rejected.

The hidden-live C state still carries more post-wakeup latency than the no-visualizer
control. On the 165 Hz display, representative p95 values moved approximately:

```text
                         C hidden-live      no visualizer
queued GUI dispatch         3.06 ms            1.89 ms
paint-pending wait           2.16 ms            0.52 ms
```

Even with the visualizer absent, the 165 Hz display remains around 155–159 FPS rather
than 165. Complete no-visualizer windows retain roughly 51 dispatch-pending skips versus
17 paint-pending skips at the median. Therefore a smaller non-visualizer GUI-dispatch
owner remains.

## GPU Result

The visualizer surface is not expensive because of shader execution. In the accepted
Spectrum run, sampled overlay GPU duration was roughly:

```text
p50 ≈ 0.02 ms
p95 ≈ 0.025 ms
```

The important cost is Qt/GUI presentation pressure and downstream delivery, not
visualizer shader time.

## Source-Level Seam

Current `SpotifyBarsGLOverlay.set_state()` performs the logical-to-overlay handoff and
finishes by requesting a frame. `_request_frame_update()` increments its counters and
calls `self.update()`; its `force` argument is currently discarded.

That means accepted logical state publication and auxiliary Qt repaint request are
effectively coupled one-for-one in the normal path. The A/B result proves that coupling
is a material shared-GUI amplifier.

The no-visualizer control improves further than C while the live B/C run still performs
roughly 88–90 overlay state handoffs per second. This proves another visualizer-family
GUI cost exists, but it does **not** prove that the whole `set_state()` method, or any one
sub-block inside it, is the owner. P3 must measure producer/state-build, pure-data overlay
preparation, Qt state commit and repaint request separately before moving work.

## Two Bad Smells

### Bad smell 1 — publication-coupled visualizer presentation

**Proven.**

A logical visualizer publication currently implies an auxiliary `QOpenGLWidget.update()`
request even when logical publication outruns useful display presentation opportunity.
The request stream materially delays both displays on the shared GUI owner.

Required production direction:

- logical/source cadence remains authoritative and unchanged;
- presentation becomes a consumer of already-integrated immutable render state;
- stale render snapshots may be coalesced at presentation ownership only;
- protected Bubble event/edge visibility must survive skipped presentation snapshots;
- paint completion is not producer acknowledgement;
- no pending-until-paint admission latch, display-FPS cap, source decimation, elapsed
  producer timestamp gate or second visualizer clock.

### Bad smell 1b — remaining visualizer-family GUI handoff/preparation

**Proven to exist; owner not yet named.**

The no-visualizer control improves beyond hidden-live C. Because it is a separate process
and removes the whole visualizer family, the only safe conclusion is that additional
visualizer-family GUI work remains.

P3 must time the logical-to-overlay handoff in bounded substages. Only proven pure-data
preparation may move off GUI; QWidget/QColor/QPixmap/GL mutation remains on its
GUI/context owner.

### Bad smell 2 — residual queued GUI dispatch without visualizers

**Proven to exist; owner not yet named.**

With the visualizer absent, the 165 Hz display still loses a smaller repeatable fraction
of deadlines, predominantly as queued-dispatch pending skips rather than paint-pending
skips.

P4 must name the concrete GUI callback/owner after the visualizer correction. Adaptive
timer cadence changes are not justified by this evidence.

## What This Evidence Rejects

- **Bubble-specific blame.** The same delivery disease appears across modes and the
  proven A/B owner is shared presentation architecture.
- **Shader/GPU-cost blame.** Measured Spectrum GPU execution is tiny.
- **Window activation as the general root cause.** Earlier activation correlation was
  useful as a clue but is not necessary for failure in the dual-display evidence.
- **Immediate Phase 8 surface merge.** C is only modestly better than B; visible surface
  existence is secondary to the repaint-request stream in this checkpoint.
- **Timer-frequency/cadence fixes.** Wake opportunity remains healthy enough that the
  main loss is downstream.

## Required Execution Order

`Current_Plan.md` is authoritative:

1. **P0** remove completed A/B/C diagnostic scaffolding while retaining passive stage metrics;
2. **P1** lock fidelity/presentation regression bars;
3. **P2** implement the real visualizer presentation-opportunity owner;
4. **P3** measure and, only if proven, extract remaining visualizer handoff/preparation work;
5. **P4** rerun the no-visualizer control and name/fix the residual queued-GUI-dispatch owner.

`Future_Cleanup.md` owns exact temporary files and test debt. The roadmap documents
describe architecture/dependencies and must not become competing task lists.

## Exit Conditions For This Attribution Thread

This thread is not complete merely because visualizer-on performance improves.

- the temporary A/B/C code is removed;
- P2 production code passes fidelity and mixed-refresh regression bars;
- the visualizer-on 165 Hz result approaches the visualizer-disabled control without
  changing authored logical behaviour;
- P3 either names/removes a remaining visualizer handoff owner or closes it with evidence;
- P4 names the residual no-visualizer queued-dispatch owner, or demonstrates with accepted
  evidence that the remaining delta is external/irreducible;
- lifecycle/GL teardown remains strict and tracked resources return to their expected zero/plateau.

## 2026-08-17 Installed Bubble Run — Supplementary Evidence

This is a **supplementary** observation, not a replacement for the accepted 2026-08-16
A/B/C/D interpretation above. It is not a like-for-like baseline: the accepted run used
Spectrum, this run used **Bubble**, so the two are not directly comparable on FPS or
acceptance. Do not restate one as a regression of the other.

Source: ordinary `main.py`, dual display (2560x1439 @ 60 Hz configured visualizer display,
1707x959 logical @ 165 Hz), `blockspin` transition, PERF delivery-stage attribution and
sampled GPU timing active.

### Direct confirmation of the P2 coupling

Aggregated across 18 overlay windows / 13,978 accepted publications:

```text
update_requests / set_state = 1.0000
paints          / set_state = 0.9669
publication rate            = 81.1 Hz
overlay paint rate          = 78.4 Hz
configured display refresh  = 60 Hz
overlay paint_cpu p95       = 1.695 ms
sampled overlay GPU (Bubble) = 0.381 ms p50 / 0.421 ms p95
```

Two results follow.

1. The one-publication → one-`update()` contract is confirmed in production at exactly
   1.0000, over a large sample. P2's premise is measured, not inferred.
2. The overlay paints roughly **31% more often than the 60 Hz display can present**, costing
   about **133 ms/s of GUI thread** in overlay paint alone before any GPU cost. The waste is
   paint work, not only dispatch demand.

Result 2 refines the mechanism: the waste is paint work, not only dispatch demand. The
follow-up mixed run reproduces the same `1.0000` ratio under Spectrum, so this is a system-wide
presentation-ownership defect.

**Withdrawn inference (2026-08-17).** An earlier revision argued that because Qt paints 96.7% of
requests, only ~3.3% of the request stream could usefully be removed. That is invalid and is no
longer accepted: `paint / update_request` is not a measure of useful physical presentation.
R-27 recorded ~275 paints/s against a 60 Hz owner, and R-55 recorded ~142–154 paints/s against
~100 Hz `set_state` while the visualizer was *worse*. The measurements above stand; only that
inference is withdrawn.
Presentation must be bounded by the owning display's presentation opportunity. See the
corrected P2 implementation decision in
`Docs/audits/SRPSS_Architecture_Roadmap/06_PRESENTATION_AND_COMPOSITOR_DESIGN.md`.

### Skip-profile difference — NOT mode-owned

An earlier reading of this run attributed a delivery skip-profile inversion to "Bubble's
heavier paint". **That attribution was wrong and is withdrawn.** A follow-up mixed
Bubble + Spectrum + teardown run on 2026-08-17 measured, per mode:

```text
              windows  set_state  update_requests  u/ss     publish   paint    paint_cpu p95
Bubble          10       6159         6159        1.0000    62.2 Hz   58.2 Hz     ~1.7 ms
Spectrum        10       8238         8238        1.0000    86.4 Hz   83.7 Hz     ~1.5 ms
```

The coupling is exactly 1.0000 in **both** modes, and Spectrum carries the *heavier*
presentation load — it publishes and paints faster than Bubble at comparable paint CPU. The
publication-coupled presentation owner is therefore system-wide, not a property of any mode.

Standing rule for this project, repeatedly confirmed in `Docs/Historical_Bugs/`: do not
attribute a performance result to a visualizer mode or a transition type. Blockspin is used
in these captures precisely because it is reasonably heavy; it is a load condition, not a
cause. Modes and transitions expose system-level owners at different rates. Bubble is the
most sensitive seam and therefore the best detector of a bad change — which is not the same
as being its cause.

P3/P4 attribution should still record the active mode, as a covariate for interpreting
rates, never as an explanation.

### Not yet established

- No same-process A/B comparison was performed in this run; the retired probe is gone and P2
  is the production correction.
- Bubble was not visually reviewed against `ff934616` as part of this capture.
- `paint_fps=0.0` in the `[GL COMPOSITOR]` blockspin records is unexplained and should be
  confirmed as an instrumentation gap rather than a real zero before being cited.

### Open lead — Spectrum hotswap versus Spectrum from init

Operator observation, 2026-08-17: Spectrum behaves worse when hot-swapped to at runtime than
when active from initialization. Supporting signal in the same capture is elevated
state-to-paint latency in mode-change windows (`mode_change` Spectrum window
`state_to_paint_p95 = 7.073 ms` against `2.337–3.979 ms` in steady windows; the Bubble
`mode_change` window shows the same shape at `9.201 ms`).

This is not yet attributed. Candidate owners to check **after** P2, since P2 changes the
presentation path this symptom is measured through:

- activation not consuming one fully resolved mode/preset payload (`Spec.md` §5);
- mode-owned arrays/history surviving activation where `reset_mode_state()` is expected to
  clear them;
- first-frame/reveal staging differing between cold init and runtime hotswap.

Do not tune Spectrum smoothing or cadence in response to this. The symptom is an activation
seam, not authored behaviour.

## 2026-08-17 Second Pre-Fix Baseline (P2 present but inert)

This run was captured after the P2 implementation landed but **before** it was active. The
overlay is constructed lazily on the first visualizer push, which precedes render-strategy
construction, so registration found no strategy and the overlay kept the unowned fallback —
deliberately the previous request-per-publication contract. Treat these numbers as a second
pre-fix baseline, not as a P2 result.

Activation evidence absent: no `Overlay presentation owned` record, and
`update_requests / set_state` remained exactly `1.0000` in both modes.

```text
              set_state  update_requests  u/ss     publish   paint
Bubble          15965        15965       1.0000    83.1 Hz   80.2 Hz
Spectrum         7950         7950       1.0000    89.3 Hz   87.0 Hz

              windows  acceptance mean   min      dispatch_skips  paint_skips
165 Hz           9         74.91%      66.05%         1041           2376
 60 Hz           9         94.17%      90.38%          154            135
```

Operator observations for this run: Spectrum behaved very well, Bubble as usual, and
transition-onset visualizer stutter felt perhaps 40% less prominent. **That improvement
cannot be attributed to P2**, which was not running. It is unattributed and should not be
counted as evidence for the presentation change.

Method consequence, now recorded in `Docs/Guardrails.md` §3: a fallback that preserves
previous behaviour can make a change completely inert while tests stay green and the runtime
looks healthy. Runtime acceptance must confirm a change is *active* before interpreting its
effect, and a null result is "not proven active" rather than "did not help".


## 2026-08-17 — P2 Attempt 2 Rejected (transition-scoped deferral)

A second P2 candidate (`8eb381fb`) deferred auxiliary presentation only while the transition
render strategy was running. Installed manual review rejected it: **Bubble worse in every
relevant way**. Reverted in `b6e3e051`; production restored to the approved anchor `30e66e08`.

Failed-experiment logs preserved at
`logs/evidence_chest/08_17_8eb381fb_p2_transition_deferral_REJECTED/`. Full analysis in
`Docs/Historical_Bugs/R-62_Transition_Scoped_Presentation_Deferral_Bubble_Regression.md`.

Measured (valid negative result; P2 was confirmed active):

```text
                    u/ss            Bubble state->paint p95
immediate windows   0.971 - 1.000   4.90 ms median
light deferral      0.949           7.04 ms
heavy deferral      0.699 - 0.755   13.2 - 15.4 ms (peaks 52.7 - 56.5 ms)

Bubble logical publication      ~99.7 - 100%  (simulation path exonerated)
borrowed 60 Hz opportunity      ~54 - 56 accepted/sec in late transitions
165 Hz sibling acceptance       ~84.9% mean vs A ~87.1%, B ~91.4% (not like-for-like)
```

Consequences for this report:

- `AdaptiveTimerStrategy` is disqualified as a presentation source in **any** scope, not merely
  as a sole source.
- The A/B/C evidence above remains valid. It shows the auxiliary request stream is a material
  amplifier; it does **not** name an eligible mechanism for removing it. Two attempts have now
  failed at the mechanism, not at the premise.
- Any future candidate must assert against the real Bubble positional-payload edge from the v1
  golden — on the tick where it becomes visible, not the tick where the event is authored.
- **A presentation opportunity that is itself degraded under load is not a valid pacing source.**
  The compositor opportunity delivers ~54–56 irregular Hz exactly when GUI delivery is sick, so
  pacing a ~90 Hz visualizer from it guarantees late, uneven arrival. Any candidate must show
  that its pacing source is healthy *under the load it is meant to relieve*.
- **State→paint latency is now a required acceptance metric**, not a diagnostic. The
  dose-response above makes it the sharpest available proxy for the fidelity loss operators
  report.


## 2026-08-17 — P2 Step 1: dispatch-layer characterization (source analysis)

Static source analysis, no production change and no added instrumentation.

### The visualizer presentation path is synchronous on the GUI thread

```text
ThreadManager.schedule_recurring(16, widget._on_tick)
    -> QTimer(parent) on the GUI thread, timeout.connect(_invoke), direct connection
    -> SpotifyVisualizerWidget._on_tick()                        [GUI thread]
    -> tick_pipeline ... push_gpu_frame()                        [GUI thread]
    -> display_image_ops.push_gpu_frame()                        [GUI thread]
    -> display_image_ops._push_spotify_bars_overlay_state()      [GUI thread]
    -> SpotifyBarsGLOverlay.set_state()                          [GUI thread]
    -> _request_frame_update()                                   [GUI thread]
    -> QWidget.update()                                          [GUI thread]
```

`core/threading/manager.py::schedule_recurring` documents "Schedule a recurring task on the UI
thread" and implements it as `QTimer(timer_parent)` + `timeout.connect(_invoke)` + `start()` — a
plain GUI-thread timer with a direct connection.

`rendering/display_image_ops.py` and `widgets/spotify_bars_gl_overlay.py` contain **zero**
occurrences of `run_on_ui_thread`, `QMetaObject.invokeMethod`, `QueuedConnection`,
`QTimer.singleShot` or `submit_task`. Nothing on this path crosses a thread or enters a queue.

### Consequence: there is no pre-GUI dispatch window on this path

The three layers the plan requires to be kept distinct resolve as:

| Layer | Compositor | Visualizer overlay |
|---|---|---|
| 1. pre-GUI runnable pending (queued callback not yet executed) | **exists** — timer worker thread → `run_on_ui_thread` → `_apply_update()` | **does not exist** — no queued hop |
| 2. Qt update pending (after `update()` returns) | Qt-internal | Qt-internal |
| 3. paint pending / in progress | at `paintGL()` | at `paintGL()` |

`_srpss_timer_update_dispatch_pending` brackets layer 1 **for the compositor only**. It is set
when the cross-thread callback is queued and cleared by `_mark_widget_update_dispatched` once
that callback reaches the GUI thread and calls `update()`. The overlay has no equivalent
boundary, because `set_state()` already runs on the GUI thread and calls `update()` directly.

### Candidate killed: dispatch-window coalescing

The attempt-3 hypothesis required an existing observable pre-GUI queued-dispatch window in which
a newer publication supersedes a queued callback. **That window does not exist on the visualizer
path.**

Implementing it would require either:

- copying `_srpss_timer_update_dispatch_pending` onto the overlay, where it would necessarily
  bracket the post-`update()` Qt state instead — the barred pending-until-paint family under a
  different variable name; or
- inserting a new queued GUI hop purely to create something to coalesce — explicitly prohibited.

Both are barred. The candidate is dead on source inspection, before any implementation, which is
the outcome Step 1 exists to produce. My earlier claim that it would be "latency-neutral by
construction" was also unfounded and is withdrawn.

### What the preserved R-62 evidence cannot answer

- **Within-transition stratification is not possible.** Overlay records carry
  `set_state`/`update_requests`/`paint`/`state_to_paint`/`mode`/`screen` but **no transition
  label**, and arrive as variable 1–10 s windows. They cannot be aligned to individual
  transitions from the `[DELIVERY_STAGE]` records without new instrumentation. Recorded as a
  limitation rather than forced.
- **Waiting-for-opportunity cannot be separated from opportunity inter-arrival jitter.** No
  inter-arrival, gap or jitter field exists in the overlay records. This remains **unknown**, and
  per the plan no behavioural instrumentation was added to manufacture the answer.

Both limits are properties of the existing evidence, not of the candidate.

### What this leaves for P2

The measured defect is unchanged: `update_requests / set_state == 1.0000` across both modes, the
overlay painting ~31% above what a 60 Hz display can present, ~1.7 ms CPU p95 per overlay paint,
and the accepted A/B/C result that suppressing only the auxiliary request stream materially
improves both compositors.

What is now eliminated is every mechanism that tries to reduce that stream **at the request
layer**:

- external pacing sources — degraded under the load they must relieve (R-62);
- transition-scoped sources — ineligible in any scope (R-61, R-62);
- pre-GUI dispatch coalescing — the layer does not exist here (this analysis);
- paint-derived admission, producer gates, divisors, second clocks (R-27, R-54).

Since `set_state()` and `update()` are the same synchronous GUI-thread call, the auxiliary
request stream is not a schedulable queue that can be thinned; it is a direct function-call
stream. That points the remaining design space away from admission control and toward either
reducing per-publication GUI cost (P3's preparation/commit split) or removing the second surface
entirely (Phase 8) — the latter still not justified by C-vs-B evidence.

**Next action per `Current_Plan.md`: explicit P2 architecture review. Not another timer, latch,
wrapper, retry, Phase-8 jump, or silent move to P3.**


## 2026-08-17 — P2 Step 2c: shared-surface feasibility audit (read-only)

Source analysis plus preserved R-62 evidence. No production change, no instrumentation added.
This audit answers the Step 2c questions; it does not authorize wiring.

### Q1 — compositor surface lifetime and steady-state draw

`GLCompositorWidget(QOpenGLWidget)` is created as a single child of `DisplayWidget` covering the
full client area, and lives for the whole display runtime. It is destroyed only in
`display_cleanup.cleanup_runtime()`.

Critically, **the surface is not transition-scoped — only its render-strategy timer is.** In the
no-transition branch `paintGL_impl` draws `_paint_retained_base_texture()`, with a QPainter
fallback. So a steady-state draw path already exists and the surface can host a layer for the
full visualizer lifetime.

This distinguishes the shared-surface lane from R-61/R-62, which failed by borrowing the
transition-scoped *timer*, not the surface.

### Q5 — cadence inheritance: the reject condition does NOT clearly apply

This was the question most likely to kill the lane. The preserved evidence says otherwise:

```text
screen 1 (60 Hz, the visualizer's display), Blockspin:
  frames=511  render_requests=511  avg_fps=56.2  slow_frames=0
  dur_min=0.32 ms   dur_max=11.02 ms      <- paint COST is cheap
  dt_min=4.41 ms    dt_max=79.63 ms       <- paint INTERVAL is irregular
```

`render_requests == frames` on both sampled transitions: the compositor drops nothing at the
paint layer. Its ~54–56 Hz is therefore a **request rate, not a paint capacity limit**. Paint
duration (0.32–11.02 ms) can support well above 56 Hz on a 60 Hz panel.

The R-62 failure mode was Bubble **waiting for** the compositor's opportunity. In a shared-surface
design Bubble would **drive** the surface: each publication requests the compositor to repaint, as
it requests the overlay today. Since the compositor is currently under-requested rather than
paint-bound, adding visualizer requests should raise its frame rate rather than lower Bubble's.

**Therefore the Step 2c reject condition is not met on current evidence.** Two caveats, held
deliberately:

1. `dt_max ≈ 79.6 ms` shows real event-loop stalls. Those are shared-GUI stalls that would affect
   Bubble on either surface; the shared design neither causes nor fixes them.
2. Compositor paint is heavier per frame than the overlay's (~1.7 ms CPU p95). Driving it at
   ~90 Hz on a 60 Hz panel replaces overlay overpaint with compositor overpaint. The expected win
   is removing one independent *request owner* and one surface's dispatch demand, not cheaper
   paint. That claim must not be conflated — see Q10.

This is a *not-rejected* verdict, not a proof of benefit. It rests on `render_requests == frames`
across two transitions; it is not an independently randomized test.

### Q3/Q4 — presentation ownership and liveness

The visualizer would call `compositor.update()` from its existing GUI-thread tick, exactly where
it calls `overlay.update()` today. That requires **no new timer, thread, lane or clock**, and
`QWidget.update()` on the same widget is merged by Qt without a manual latch.

Liveness does not depend on `AdaptiveTimerStrategy`: `update()` schedules a paint whether or not
the strategy is running, so the visualizer keeps presenting after transitions stop. This is the
R-61 defect structurally removed rather than worked around.

### Q6 — Z-order, card and stencil: the hard blocker

The overlay is a **sibling** of the compositor (both children of `DisplayWidget`), deliberately
stacked above the visualizer card. It owns a rounded-rect **stencil-mask program** for
painted-card corner clipping (`_begin_painted_card_stencil_clip`,
`_draw_painted_card_stencil_mask`, `_end_painted_card_stencil_clip`, plus
`widgets/spotify_visualizer/overlay_mask.py`).

Moving the draw into the compositor inverts the stacking: the compositor is the **bottom-most**
child of `DisplayWidget`, beneath every QWidget overlay including the visualizer card itself. The
visualizer would render *behind* its own card unless the card is also moved into the compositor
scene or made transparent in a coordinated way.

That is the crux of the blast radius, and it is not a visualizer-local change.

### Q9 — blast radius

```text
widgets/spotify_bars_gl_overlay.py   2196 lines   (5 mode renderers, stencil, geometry, fade)
rendering/gl_compositor.py           2265 lines
```

A bounded "draw the visualizer layer inside compositor paint" change would still need: mode
renderer relocation or shared invocation, stencil/mask integration into compositor paint state,
CUSTOM geometry/DPR translation into compositor coordinates, fade/visibility, and Z-order
resolution against the card (Q6).

**Assessment: this is not a bounded visualizer layer. It is a compositor scene-composition
change** — precisely the "compositor rewrite" case Step 2b says to stop and report rather than
implement.

### Q2, Q7, Q8 — deferred, not answered

The render-state boundary (Q2), lifecycle/generation/teardown preservation (Q7) and shader/program
ownership transfer (Q8) are all answerable only *after* the Q6 Z-order decision, because that
decision determines whether the visualizer draws inside the compositor scene or the card
composition changes. Answering them now would be speculation.

### Q10 — causal claim, kept separate

The expected benefit is **removal of the independent auxiliary presentation-request owner** —
one widget requesting and dispatching instead of two. It is explicitly **not** "the second surface
is expensive": C-vs-B added only ~1.4 FPS from hiding the already request-suppressed surface, so
surface existence is secondary. Any future measurement must attribute to request-owner removal,
not surface count.

### Verdict

- The shared-surface lane is **not rejected** by the transition-cadence condition (Q5), and it
  structurally removes the R-61 liveness defect and the R-62 pacing dependency (Q3/Q4).
- It **is blocked** by Z-order/card composition (Q6) and blast radius (Q9): delivering it requires
  changing how the display composes its scene, not adding a visualizer layer.

Per Step 2b/2c this is a **stop-and-report**, not an implementation. The next decision is a scope
question for the operator: whether P2 may become a bounded compositor scene-composition change
(with the card), or whether P2 is recorded as not safely achievable on the current
separate-surface architecture with the measured defect carried into the Phase 8 decision.

No pacing or admission experiments may resume either way.
