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

Result 2 refines the mechanism: because Qt already paints 96.7% of requests, a
pending-until-painted coalescer would recover only the ~3.3% Qt collapses by itself. The
follow-up mixed run reproduces the same 1.0000 ratio under Spectrum, so this is a
system-wide presentation-ownership defect.
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
