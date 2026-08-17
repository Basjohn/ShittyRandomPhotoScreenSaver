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

`render_requests == frames` on both sampled transitions. Stated conservatively: this proves only
that **at the observed request rate of ~54–56 Hz there was no obvious loss at the paint layer**.
It does **not** prove the compositor will cleanly deliver ~90 Hz once the visualizer begins
driving `compositor.update()`. Paint duration of 0.32–11.02 ms is consistent with headroom above
56 Hz but does not establish delivery at triple that request rate, under a different request
pattern, with visualizer draw work added to each paint.

The R-62 failure mode was Bubble **waiting for** the compositor's opportunity. In a shared-surface
design Bubble would **drive** the surface: each publication requests the compositor to repaint, as
it requests the overlay today. The compositor appears under-requested rather than paint-bound at
the observed rate, so adding visualizer requests plausibly raises its frame rate rather than
lowering Bubble's — but that is an inference from a ~56 Hz observation, not a measurement at
~90 Hz. Delivery at the higher rate remains **unproven** and would have to be measured.

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


## 2026-08-17 — Legacy compositor visualizer seam: dependency/debris audit

Narrow audit requested to prevent the historical compositor visualizer path being mistaken for
evidence that modern modes can move into the compositor cheaply. Read-only.

### Scope of the seam

```text
rendering/gl_compositor.py:280-287             _spotify_vis_{enabled,rect,bars,bar_count,
                                                segments,fill_color,border_color,fade}
rendering/gl_compositor.py:724-738             set_spotify_visualizer_state()  -> delegation
rendering/gl_compositor.py:2205-2208           _paint_spotify_visualizer(painter)
rendering/gl_compositor.py:2246-2248           _paint_spotify_visualizer_gl()
gl_compositor_pkg/transition_lifecycle.py:176  set_spotify_visualizer_state() implementation
gl_compositor_pkg/overlays.py:106-175          paint_spotify_visualizer() — QPainter bars
gl_compositor_pkg/shader_dispatch.py:419-453   paint_spotify_visualizer_gl() + 2 call sites
gl_compositor_pkg/paint.py:24, 411             import + call of paint_spotify_visualizer
```

### Q1 — is any current production visualizer mode calling or depending on it?

**No.** `set_spotify_visualizer_state()` has **no production caller**. The only occurrences are
its definition on `GLCompositorWidget` and that method's delegation to the
`transition_lifecycle` implementation. Nothing in the runtime invokes it.

`widget._spotify_vis_enabled = True` occurs in exactly two places: inside that unreachable
implementation, and in `tests/test_gl_compositor_overlays.py:154`, which sets it directly.

Consequently `_spotify_vis_enabled` remains `False` from construction in production, and every
consumer — `paint_spotify_visualizer`, `paint_spotify_visualizer_gl`, and the `paint.py:411`
call site — early-returns on its first guard. **The seam is unreachable in production and is kept
alive only by one test that sets the flag by hand.**

### Q2 — is any lifecycle/geometry/state ownership reused by modern code?

**No.** Other `_spotify_vis*` matches in the repository are unrelated code sharing a name prefix:

- `rendering/spotify_widget_creators.py::apply_spotify_vis_model_config` — modern settings
  application to the visualizer **widget**, used by `activation_runtime` and `replay_runtime`;
- `rendering/widget_descriptors.py:2212-2213` and `ui/tabs/*` — `_spotify_vis_fill_color` /
  `_spotify_vis_border_color` on the **settings tab** object;
- `ui/widget_stack_predictor.py::estimate_spotify_vis_size` — layout estimation.

None of these read or write the compositor's `_spotify_vis_*` attributes. There is no shared
lifecycle, geometry or state ownership between the legacy seam and the modern overlay.

### Q3 — is it dead compatibility debris?

**Yes.** It is the original Spectrum-only implementation, and it is `QPainter` bar drawing:
`setBrush`/`setPen`, a segment loop over `bar_x`/`seg_y`, alpha-scaled fill and border. It has
**zero** references to `vis_mode`, `bubble`, `oscilloscope`, `sine_wave` or `devcurve`.

It therefore cannot render any modern mode, has no stencil/card masking, no CUSTOM geometry
handling, and no GL renderer integration. It belongs in cleanup, not in the P2 decision.

### Q4 — does it constrain or confuse the shared-surface design?

It confuses it, in one specific and dangerous way: its existence makes the compositor **look** as
though it already knows how to draw the visualizer, which would suggest the shared-surface lane is
cheap. It is not. What exists is a single-mode QPainter bar routine from the pre-GL era.

**It is therefore excluded from the P2 architectural decision.** It must not be revived or
extended merely because it is already there, and its presence is not evidence for Option A. The
real architecture P2 would have to replace or absorb remains the modern `SpotifyBarsGLOverlay`:
five GL mode renderers (`bubble`, `spectrum`, `oscilloscope`, `sine_wave`, `devcurve`), the
rounded-rect stencil/card masking, CUSTOM geometry/DPR handling, fade/visibility and GL lifecycle.

The Step 2c Q6/Q9 blockers stand unchanged — the legacy seam does nothing to reduce them.

### Disposition

Cleanup candidate, not P2 work. It should be removed with the usual production-caller and
frozen-build proof, and its one test either retired or repointed, at a time that does not
interleave with the active delivery lane. Recorded in `Future_Cleanup.md`.


## 2026-08-17 — P2 scope decision: Option B (deferred, explicitly not closed)

Bad Smell 1 is recorded as a **measured unresolved presentation defect** that is not safely
correctable on the current separate-surface architecture with any presently identified
request-layer mechanism. It is **not** solved, abandoned, impossible or permanently closed.

The A/B evidence and all P2 acceptance bars are preserved unchanged. **P3/P4 success must not be
represented as fixing P2** — they are separate measured owners (Bad Smell 1b, Bad Smell 2).

Order of work: P3, then P4, then re-measure the equivalent 165 Hz + 60 Hz scenario and reassess
the remaining deficit; only then decide whether the residual P2 cost justifies a Phase-8-class
shared-surface/card change. P3/P4 are taken first because they are independently measured owners
with substantially smaller architectural risk.

The shared-surface/card design is described as **the only currently identified direct architecture
for removing the independent presentation owner** — not the only conceivable one.

The proposed ~90 Hz compositor-driving measurement is **deliberately not run now**: it would
characterize a hypothetical architecture against a baseline P3/P4 are about to change.

### Regression clue retained

Substantially better 165 Hz behaviour existed historically. If P3/P4 do not recover enough
delivery headroom, historical architecture comparison is a legitimate next investigation before
concluding that the modern multi-mode GL visualizer fundamentally cannot reach the target. The
current deficit must not be treated as an inherent property of the modern architecture until that
comparison is made or explicitly rejected with evidence.

### Standing confound for P3

Because P2 was deferred rather than corrected, the auxiliary one-publication → one-`update()`
stream remains live during all P3 measurement. It is a known confound, must be stated in P3
attribution rather than assumed away, and its cost must not be silently reassigned to
preparation/commit.


## 2026-08-17 — P3 work classification of `SpotifyBarsGLOverlay.set_state()` (source only)

Read-only classification into the four required categories, ahead of any measurement. No
production change. `set_state()` spans lines 586-1391 (805 lines).

**Standing confound:** P2 was deferred, not corrected, so the auxiliary one-publication →
one-`update()` stream is live throughout. Category 4 consequences are kept strictly separate
below and must not be attributed to categories 1-3.

### Category 1 — authoritative temporal/logical state evolution (NOT a P3 extraction candidate)

Preserve cadence, order and owner. Not movable merely for containing no Qt calls.

- `now_ts = time.time()`, `dt` sanity clamp, `self._accumulated_time += dt` — wall-clock read and
  authored time accumulation, with the deliberate Spectrum no-paused-drift exception;
- `_line_smoothed_bass/_mid/_high` — dt-dependent asymmetric exponential smoothing
  (`dt/0.06` rising, `dt/0.12` falling);
- `_sine_peak_bass/_mid/_high` and `_sine_peak_hold_remaining` — peak-tracked band envelopes;
- waveform temporal smoothing via `line_speed`, `_prev_waveform`, `_ghost_waveform_ring`,
  `_ghost_ring_idx` — history rings;
- `_line_kick_event_envelope` / `_line_snare_event_envelope` and their `_strength` outputs —
  discrete event envelopes, including the pause/resume boundary reset;
- `_transient_energy` per-frame snapshot;
- Spectrum `_peaks` / `_last_peak_ts` and solid-bar hysteresis;
- Bubble temporal payload handling;
- `apply_state_handoff()` — activation/generation identity and `reset_mode_state()` clears.

### Category 2 — pure immutable render-state preparation (the only extraction candidate)

Derived from already-evolved state; no Qt types, no temporal ownership.

- bar clamping to `clamped` → `_bars`, `_bar_count`;
- numeric coercion/clamping of mode configuration — 97 `float()`/`int()` sites;
- list copies of devcurve curves and bubble positional/extra/trail payload.

### Category 3 — Qt-owned commit / geometry / visibility

Stays on the GUI/context owner by contract.

- **28 `QColor(...)` constructions** — glow, line1-6 and their glow colours, spectrum glow,
  bubble outline/specular/gradient-light/gradient-dark/pop, four devcurve layer colours;
- `self.geometry()` / `self.setGeometry(rect)` and the `geometry_changed` flag;
- `self.isVisible()` / `self.show()` and `became_visible`;
- painted-frame shadow sync.

### Category 4 — presentation request (kept separate; P2 territory)

- `_request_frame_update()` → `QWidget.update()`.

Its downstream cost belongs to Bad Smell 1 and must not be attributed to categories 1-3.

### Primary P3 hypothesis (unmeasured)

The dominant per-publication cost in categories 2 and 3 may not be *preparation* at all, but
**re-derivation of unchanged configuration**.

The 28 `QColor` constructions and 97 numeric coercions are guarded only by `is not None` — there
is no change detection. At ~90 Hz publication that is roughly **2,500 QColor constructions and
8,700 coercions per second**, re-deriving values that change only on a settings/preset/activation
change.

If confirmed, the correction is **not** moving work off the GUI thread. It is applying
configuration on change rather than per publication — revision- or identity-gated commit. That:

- touches no category 1 state, so no cadence, smoothing, envelope or event ownership moves;
- requires no worker, thread or immutable-snapshot boundary, so it avoids the P3 test debt that
  worker extraction would incur;
- leaves category 4 untouched, so it cannot be mistaken for a P2 fix.

This is a hypothesis from source inspection only. It must be measured before any change.

### Required measurement design

- Use **in-callback self-time boundaries** inside `set_state()`, not overall FPS or end-to-end
  callback latency, and not paint duration.
- Emit four separate accumulations — category 1, 2, 3, 4 — so no category can absorb another's
  cost.
- Sample rather than timestamp every publication, consistent with existing PERF practice, so the
  probe does not become the load it measures.
- Record with visualizer mode as a covariate, never as an explanation.
- Do not add a queued hop, timer or event interception; observational only.

### Explicitly not concluded

- That category 2 should move off GUI. That requires a measured owner, and current evidence names
  none.
- That the no-visualizer control's improvement is owned by preparation. It proves another
  visualizer-family cost exists; it does not locate it.
- Anything about P2. The request stream remains live and unattributed here.


## 2026-08-17 — P3 corrected semantic attribution of `set_state()` (accepted run)

Steady-state, weighted, microseconds per accepted publication. Probe: explicitly bracketed
known-homogeneous blocks; mixed source deliberately untimed; residual derived as
`total - sum(measured)`.

```text
mode           total   temporal   static   dynamic   residual
Bubble           329         88       19        28        175
DevCurve         327         98       19        12        178
Spectrum         404        211      156         3         21
Sine             383        154      103         3        106
Oscilloscope     923        616      162         3        121
```

### What this establishes

**Static configuration is a real target for Spectrum, Sine and Oscilloscope, and not a general
P3 explanation.** Static is 39% of Spectrum, 27% of Sine and 18% of Oscilloscope, but only ~6%
of Bubble and DevCurve. Revision-gated configuration would therefore be a genuine but
**mode-skewed** optimization. It cannot be presented as closing P3.

**Residual dominates Bubble and DevCurve** — 53% and 54% respectively, the largest single
category for both. That is unattributed by design, not an error: the probe leaves mixed and
ambiguous source untimed. For those two modes the honest statement is that the majority of
`set_state()` self-time is **not yet located**.

**Temporal is authoritative work and is not a removal target.** It dominates Oscilloscope (616
of 923) and Spectrum (211 of 404). Cadence, smoothing, envelopes and event ownership stay where
they are.

**Dynamic payload is negligible everywhere** — 3 us for Spectrum, Sine and Oscilloscope, 12-28 us
for DevCurve and Bubble. **Worker extraction is not pursued**: there is no measured owner to
extract, and the P3 test debt it would incur is unjustified by these figures.

### What this does not establish

P3 self-time does not explain the delivery defect. In the same run 165 Hz transition acceptance
varied ~69-90% while callback cost did not track that variation. Total `set_state()` self-time of
0.33-0.92 ms per publication is real work, but it is not the mechanism behind the acceptance
swing. P2 and P4 remain separate live owners.

### Next step before any implementation

Revision-gated static configuration is **not yet authorized**. First define the authoritative
config-change boundary and the invalidation contract:

- a newly created overlay must begin with config state invalid/uncommitted, never assuming its
  initial revision is already applied;
- the first accepted activation/frame must perform a complete configuration commit;
- mode activation, engine/runtime generation replacement, Settings recreation and any reset
  boundary that can invalidate config must invalidate the cached revision;
- gating must wrap only genuinely static assignments, never Cat-1 timing/state evolution;
- Python object identity must not be the sole invalidation contract; the boundary must be an
  authoritative revision or value comparison.

### Warning telemetry — retained for P4, not acted on

The run contains ~119 `FRAME_GAP_OWNER` warnings with ~33-144 ms gaps plus frequent visualizer
tick-dt spikes. This is **diagnostic evidence for P4 attribution, not a runtime failure**.

- Do not infer that the `last_ui` field is causal merely because a callback name appears in it.
- Do not rate-limit or remove this telemetry during active attribution. Logging is already
  writer-thread queued, so warning volume is not currently the leading stall hypothesis.
- Revisit aggregation/rate limiting only for final acceptance runs.

## 2026-08-17 — P3 Step 3: config-change boundary inspection (read-only)

Prerequisite analysis before any revision-gated configuration. Source only, no change.

### Where the static configuration actually lives

The values re-derived per publication do **not** originate on the overlay. They are attributes of
`SpotifyVisualizerWidget`, passed as kwargs each tick:

```text
SpotifyVisualizerSettings / activation payload
    -> config_applier.apply_vis_mode_kwargs(widget, kwargs)   [writes widget._* config]
    -> tick_pipeline: parent.push_spotify_visualizer_frame(fill_color=widget._bar_fill_color,
           segments=widget._dynamic_bar_segments(), border_radius=widget._spectrum_border_radius,
           **build_gpu_push_extra_kwargs(widget))
    -> display_image_ops assembles overlay_kwargs
    -> SpotifyBarsGLOverlay.set_state(**overlay_kwargs)       [re-derives, coerces, QColors]
```

So a gate belongs at the overlay's *commit* of these values, keyed to a revision owned upstream
by the widget.

### Blocker: the config-change boundary is not currently single-writer

`config_applier.apply_vis_mode_kwargs()` is the main writer and is reached from
`mode_transition.py`, `spotify_visualizer_widget.py` (two sites), and
`spotify_widget_creators.py`. But it is **not the only writer**:

- `widgets/spotify_visualizer_widget.py:107` — constructor default for `_bar_fill_color`;
- `widgets/spotify_visualizer_widget.py:1551` — `set_bar_colors()`, a public API that writes
  `_bar_fill_color` / `_bar_border_color` directly and calls `update()`.

A revision bumped only inside `apply_vis_mode_kwargs()` would therefore miss `set_bar_colors()`
and silently present stale colours. **Establishing the authoritative boundary is real work, not a
counter.** It requires either routing every config write through one applier, or defining the
revision at a level that provably covers all writers.

This is exactly the failure mode the invalidation contract warns about, and it is why Python
object identity cannot be the invalidation contract — `QColor` instances are replaced wholesale
by both writers, so identity would appear to change on every publication while value-equality
would not.

### Contract that any implementation must satisfy

- new overlay starts **invalid/uncommitted**; it never assumes its initial revision is applied;
- first accepted activation/frame performs a **complete** configuration commit;
- mode activation, engine/runtime generation replacement, Settings recreation and every reset
  boundary invalidate the cached revision;
- gating wraps only genuinely static assignments — never Cat-1 timing/state evolution, and never
  the protected first-frame dt/initialization behaviour;
- the boundary is an authoritative revision or value comparison, never object identity.

### Recommendation

The measured prize is real but bounded and mode-skewed: ~156 us/publication Spectrum, ~103 us
Sine, ~162 us Oscilloscope; ~19 us Bubble/DevCurve. Against totals of 329-923 us, and against a
delivery defect that P3 self-time demonstrably does not explain, this does not justify
restructuring config ownership as an urgent step.

Sequencing suggestion, for decision: locate the Bubble/DevCurve residual first (53%/54% of their
callback, currently unattributed), since it is larger than the static-config prize and may reveal
a cost shared across modes. Then decide whether config gating is worth its ownership work.

## 2026-08-17 — P3 Step 4: bounded residual audit (three added brackets)

Source inspection of the untimed regions found ~542 of 890 `set_state()` body lines untimed,
concentrated in four blocks. Inspection named three candidate owners, all previously untimed and
all shared across modes rather than mode-specific:

1. **`apply_state_handoff()`** — activation/generation identity and mode-reset bookkeeping, run on
   every publication. Now bracketed as `handoff`.
2. **DevCurve layer colour commit** — a further ~10 `QColor` constructions with `setAlpha` calls,
   beyond the previously measured static block. Now bracketed as `static_config`.
3. **Bar sequence build, resize/pad and per-bar clamp loop** — `list(bars)`, length reconciliation
   and an interpreted per-bar loop appending to `clamped`. Shared by every mode and the strongest
   candidate for a cost that appears in all residuals. Now bracketed as `dynamic_payload`.

Three brackets added, deliberately bounded. This is not open-ended decomposition: if the next run
shows the residual fragmenting across small legitimate work rather than concentrating in one of
these, **P3 is recorded as secondary and work proceeds to P4**. A ~0.175 ms/publication residual
does not warrant further archaeology while the runtime shows 33-144 ms frame gaps.

Config gating stays a valid later optimization; its split-writer ownership cost currently
outweighs its measured mode-skewed benefit, and it is not being implemented now.


## 2026-08-17 — P3 CLOSED as measured secondary cost

Final steady attribution after the bounded residual audit:

```text
Bubble        ~285 us total; dynamic bar build/clamp ~27, handoff ~11, residual ~117
DevCurve      ~277 us total; added static colour commit explains part of the old residual
Spectrum      residual effectively exhausted
Sine / Osc    remain mostly authoritative temporal + static work
```

**No newly named P3 owner is large enough to justify further decomposition or worker
extraction.** The bar build/clamp loop, suspected as a shared owner, measures ~27 us on Bubble —
real but not material against a 285 us callback, and negligible against 33-144 ms frame gaps.

Recorded status: **P3 is a measured secondary cost with no safe, high-value production
correction currently justified.** Specifically:

- worker extraction is rejected — no measured owner, and unjustified test debt;
- static-config gating is **deferred, not rejected**: a real but mode-skewed prize
  (~156 us Spectrum, ~103 us Sine, ~162 us Oscilloscope; ~19 us Bubble/DevCurve) whose
  split-writer ownership cost currently outweighs the benefit. Preserved as a later optimization
  with its invalidation contract already documented;
- the attribution probe is retained as evidence.

P3 does not explain the delivery defect and was never claimed to. P2 remains an open measured
presentation defect. **P4 is now the active lane.**

## 2026-08-17 — P4 first attribution pass over FRAME_GAP_OWNER (125 records)

Analysis of the existing telemetry. No production change, no new instrumentation.

```text
gap_ms            p50 46.0   max 77.0
paint_ms          p50  0.74  max  9.31
request_age_ms    p50 33.3   max 71.3
```

### What is ruled out by this evidence

**`last_ui` is not causal — confirmed with evidence, not assumed.** Median `last_ui_age_ms` is
**698 ms** (max 2433 ms). The most recent UI callback completed roughly seven-tenths of a second
*before* the gap. `MediaWidget._refresh_async` appears in 80 of 125 records purely because it is
the most recent named UI callback identity, not because it was running. Its own duration
(`last_ui_ms`) has a median of 0.38 ms and correlates with the gap at only **+0.110**.

**Not a queued-callback backlog.** `ui_queue` is 0 in every record (p50 and max), `ui_active` 0,
`ui_failed` 0, `ui_callbacks` p50 0 / max 2. There is no UI work waiting or running.

**Not garbage collection.** `gc_enabled=0` in every record — GC is disabled in this runtime.

**Not worker queue contention, on this evidence.** `io_queue` and `compute_queue` are 0;
`io_queue_wait_ms` p50 0.00; `compute_queue_wait_ms` p50 1.00. Worker *execution* is nonzero
(`io_exec_ms` p50 12.07, max 38.01; `compute_active` p50 2), but correlation with the gap is
**+0.055 / +0.039** — effectively none. GIL contention from workers is therefore not supported as
the primary owner, though it is not positively excluded by correlation alone.

**Not paint cost.** `paint_ms` p50 0.74 ms against a 46 ms gap; correlation +0.186.

### What the evidence points to

```text
corr(gap_ms, request_age_ms)   = +0.880
corr(gap_ms, skipped_requests) = +0.649
gap minus every named GUI-thread cost: p50 40.9 ms (min 27.9)
  -> ~89% of the median gap is unexplained by any recorded GUI-thread callback
```

The gap is almost entirely **request-to-paint latency on an otherwise idle GUI thread**. Roughly
89% of it is not accounted for by any callback, queue, paint or worker cost the telemetry records.

**Every one of the 125 records has `transition_active=1`.** Not a majority — all of them.

### Candidate owners now, in order

1. **Presentation/compositing serialization while two GL surfaces are live during a transition.**
   Fits the total transition correlation, sub-millisecond paint, empty UI queue, and time
   disappearing between request and paint. Note the overlap with P2: the second surface is
   Bad Smell 1 territory, and the two lanes may share one mechanism.
2. **Blocking outside Python** — swap/vblank serialization, driver or compositor stall. Consistent
   with an idle GUI thread and unexplained wall time, and not currently instrumented.
3. **GIL contention from worker execution.** Weakly supported: execution time exists but does not
   correlate. Retained but ranked below the first two.

### Explicitly not concluded

That `MediaWidget` is the owner. It is the last-entered/not-returned identity, ~700 ms stale, and
this analysis actively contradicts a causal reading.

### Next step

Distinguishing candidates 1 and 2 requires a timestamp between the accepted request and paint
entry — where the wall time actually goes. That is new instrumentation and must be designed
against the same observational constraints as the P3 probe: no queued hop, no timer, no event
interception, PERF-gated, sampled.

## 2026-08-17 — P4: single-display control, and what `request_age_ms` actually spans

### Single-display control (main_mc.py) — multi-monitor excluded

One active SRPSS display (`show_on_monitors=[2]`, screen 0 skipped, screen 1 active at 60 Hz)
reproduces the same pathology:

```text
48 qualifying gaps
gap_ms p50 ~48.2  max ~94.4      paint_ms p50 ~0.96
request_age_ms p50 ~33.4
corr(gap_ms, request_age_ms)   ~+0.858
corr(gap_ms, skipped_requests) ~+0.844
ui_queue = 0 and ui_active = 0 in all 48
transition_active = 1 in all 48
```

`record_paint_metrics()` emits FRAME_GAP_OWNER whenever `gap_ms > 33`, independently of
transition state — `active_transition_window` is recorded but does not gate emission. So
48/48 here and 125/125 on dual-display is **genuine transition specificity, not telemetry
selection**.

**Active multi-monitor rendering / mixed-refresh interaction is excluded as root cause.**

This does not disprove the two-surface hypothesis: the single active display still owns both the
GL compositor surface and the `SpotifyBarsGLOverlay` `QOpenGLWidget`. The surviving candidate is
therefore **intra-display cross-surface presentation/compositing serialization during
transitions**, not multi-monitor serialization.

### What `request_age_ms` spans (documented before adding any timestamp)

```text
adaptive_timer._signal_frame()            [TIMER WORKER THREAD]
  -> _queue_safe_widget_update(compositor)
  -> _record_render_timer_tick()
       -> metrics.record_render_request()  <-- _pending_request_ts = perf_counter()
  ... cross-thread marshalling, GUI callback runs, widget.update() called ...
  ... Qt schedules and delivers the paint event ...
paintGL -> _record_paint_start_metrics(_paint_start)
       -> metrics.record_paint_start()     <-- request_age_ms = paint_start - request_ts
```

So `request_age_ms` is measured **from the timer worker thread**, and conflates two very
different intervals: the cross-thread queued-dispatch hop, and Qt's internal update→paint
delivery. On its own it cannot separate them.

### The P0 delivery-stage seam already splits exactly this boundary

No new compositor-side timestamp is required. The instrumentation retained in P0 already reports
both halves, and this run contains it:

```text
window 7: dispatch p50 0.542  p95 4.142  max 45.188 | paint_pending p50 0.291 p95 2.476 max 18.284
window 8: dispatch p50 0.370  p95 4.344  max 44.798 | paint_pending p50 0.265 p95 3.192 max 77.636
```

- `dispatch_ms` = worker queued the update → GUI callback ran `widget.update()`
- `paint_pending_ms` = `update()` returned → `paintGL` entry

**Tens-of-millisecond outliers appear in both stages** (dispatch max ~45 ms, paint_pending max
~77.6 ms) while both medians are sub-millisecond. A ~45 ms dispatch max means the GUI event loop
did not run an already-queued callback for 45 ms — with `ui_queue = 0`, no Python callback was
waiting to run and none was executing.

### Interpretation against the stated bar

Neither GL surface is inside Python paint for tens of milliseconds: compositor `paint_ms` p50
0.74-0.96 ms, overlay `paint_cpu` p95 ~1.7 ms. The stall is therefore **below both paint
callbacks**, in Qt/native/driver/composition — the second stated candidate.

Crucially this does **not** eliminate the first candidate; it locates its mechanism. If the
auxiliary overlay's buffer swap or composition blocks the GUI thread, it would delay the
compositor's queued dispatch *and* its paint event, while the compositor's own `paint_ms` stayed
small — which is precisely the observed shape. Intra-display cross-surface serialization and
below-Python blocking are then the same finding at two levels of description, not competing
explanations.

**P2/P4 shared-owner hypothesis is strengthened, not by correlation of counters, but because the
only structure that explains blocking with an empty UI queue and sub-millisecond paints is
presentation-level serialization between the two surfaces this display owns.**

### Consequence for the planned probe

The compositor-side half of the proposed probe is redundant — P0's seam already provides it. What
is genuinely missing is the **visualizer side**: the overlay records `set_state`, update requests,
paints and `state_to_paint`, but its samples cannot currently be aligned in time with a specific
compositor gap.

Before building that, note the cheaper discriminator: if the overlay is disabled, the P0 seam
alone will show whether `dispatch_max` / `paint_pending_max` outliers persist. That is the
existing no-visualizer control, needs no new code, and would separate the two candidates
directly.

## 2026-08-17 — P4: no-visualizer single-display control, and GPU-identity audit

### Control result — the overlay is not necessary for the severe stall

Single active 60 Hz display, visualizer disabled entirely. Absence confirmed:
`screensaver_spotify_vis.log` empty, and FRAME_GAP_OWNER records carry
`overlay_set=0 overlay_repaints=0 overlay_paints=0`.

The severe transition-stall signature nonetheless survives:

```text
26 FRAME_GAP_OWNER events over ~55.1 s of measured transition windows
gap_ms p50 ~56.2  max ~79.7      17/26 gaps > 50 ms
transition_active = 1 in all 26
dispatch_max still ~69 ms        paint_pending_max still ~42 ms
transition compositor dt_max ~61-73 ms across Blockspin/Burn/Diffuse/BlockFlip
```

**The auxiliary `SpotifyBarsGLOverlay` / second GL surface is not necessary for the P4 severe
transition stalls and is not their primary root cause.** The intra-display cross-surface
serialization hypothesis is therefore rejected as the owner of P4.

**P2 and P4 must not be merged into one overlay-owned defect.** My previous note suggesting they
might be one owner is withdrawn — this control contradicts it.

### P2 remains a real amplifier, separately

Against the preceding single-display visualizer-enabled control:

```text
mean delivery acceptance     ~97.6%  ->  ~98.5%
median per-window dispatch p95      ~4.17 ms  ->  ~0.85 ms
median per-window paint-pending p95 ~3.14 ms  ->  ~0.79 ms
>33 ms gap frequency         ~0.67/s ->  ~0.47/s
```

So P2 adds presentation pressure and worsens ordinary and tail delivery, while P4's severe
transition stall exists independently of it. Both stay open, separately owned.

### Shape: tail stall, not sustained workload

With no visualizer, dispatch and paint-pending medians and p95s are excellent while isolated
tens-of-ms maxima persist. This is a tail-stall mechanism, not sustained Python/GUI workload.

### Compositor GPU clue (not yet causal)

Sampled transition GPU maxima in the same no-visualizer run:

```text
Blockspin  ~44.6 ms, ~36.6 ms      Burn      ~32.5-39.3 ms
Diffuse    ~46.7 ms                BlockFlip ~38.4 ms
GPU p95 generally only ~3-4.5 ms
```

Tens-of-ms GPU outliers now exist in the compositor **with the overlay absent**. This is not yet
a causal claim: timer-query GPU duration and CPU/event-loop blocking are different quantities.

### Audit: GPU samples do NOT retain alignable identity

`rendering/gl_timer_queries.py::_QuerySlot` carries only `handle`, `resource_id`, `label` and
`pending`. On completion `poll()` appends `elapsed_ns/1e6` into `_window_samples_ms[label]` — a
plain per-label list — and clears the slot. `consume_window()` then aggregates over the window.

**No frame index, request identity or timestamp is retained.** A GPU outlier therefore cannot
currently be aligned with a specific FRAME_GAP_OWNER or P0 delivery-stage outlier. The identity
does not exist and must be added to answer the question.

### Minimum association to add (design only; not implemented)

Answer required: *when a 40-80 ms transition delivery gap occurs, was that frame — or an
immediately preceding compositor transition frame — also a tens-of-ms GPU sample?*

Minimum sufficient design:

- `metrics` already maintains `presented_frame_index` / `_active_presented_frame_index`. Capture
  that value into `_QuerySlot` at `begin_sampled()` — one integer, no new call.
- On completion in `poll()`, if `elapsed_ms` exceeds a threshold, push
  `(frame_index, elapsed_ms)` into a small bounded ring (e.g. 8 entries).
- FRAME_GAP_OWNER already runs at gap emission: report whether the ring holds an outlier within
  the last K frames of the gap frame, plus its elapsed value and frame delta.

Constraints unchanged: PERF-gated, sampled, no new timer, queued hop, event interception,
admission gate, paint acknowledgement or scheduling change. GPU diagnostics must never become
presentation control flow.

### Alternative kept alive

Blocking may occur in Qt/native/DWM/driver presentation **independently of measured shader GPU
execution**. A negative correlation from the association above would support that, not refute the
stall.

### Active target

Multi-monitor contention and the visualizer overlay are both excluded as necessary conditions.
The active P4 target is the **compositor transition / Qt-native-GL presentation path itself**.
P2 stays open separately as a measured amplifier, not P4's owner.
