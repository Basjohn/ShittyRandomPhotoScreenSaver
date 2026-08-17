# Current Plan

Last updated: 2026-08-17
Branch: `main`  
Active phase: Phase 5 — workload, delivery, GPU attribution, resource efficiency

This file contains **unfinished active work only**. Stable architecture belongs in
`Spec.md`; detailed design/evidence belongs in the roadmap/phase reports; solved failures
belong in `Docs/Historical_Bugs/`.

Settings/Edit compiled ownership, Diagnostic ownership attribution, retained-current
texture identity, steady retained-base draw, direct upload-copy removal, and clock-shadow
work are closed. Preserve them as regression contracts; do not reopen them without new
contradictory evidence.

## Current Authority And Evidence

- Work directly on current `main`.
- Historical commits are negative controls/forensic references only.
- Preserve `ff93461685476bd0657aa88312fc2e35e9037880` as the user-approved Bubble/Spectrum behavioural reference until a later exact commit receives explicit approval.
- `main.py` is the ordinary performance/hostile/soak/evidence authority.
- Diagnostic is a frozen-runtime/lifecycle attribution product, not a performance baseline.
- Media Center receives bounded shared route/build coverage.
- `Current_Plan.md` owns active execution order.
- `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` owns the accepted 2026-08-16 delivery/presentation evidence and the exact A/B/C/D interpretation.
- `Future_Cleanup.md` owns temporary diagnostic removal and test debt; it is not an alternate active plan.
- Do not freeze raw log/ZIP paths into `Index.md` or roadmap navigation.

## Checkpoint Policy

A checkpoint is a rollback anchor, not a pause for permission.

- Make a clean narrow commit after an independently risky architectural slice.
- Run the owning focused tests and smallest useful runtime/evidence gate.
- If the gate passes, keep the checkpoint and continue.
- Stop on failed evidence, contradicted causal model, dirty/conflicted repository state, or an affected visual result requiring operator judgement.
- Never carry a failed experiment forward through compensating flags, retries or hidden alternate paths.

## Non-Negotiable Guardrails

- Keep `versioning.py` user-owned unless a version change is explicitly requested.
- Preserve Bubble authored-step cadence, dt, source/event sampling, one-in-flight semantics, simulation and ordinary COMPUTE ownership.
- Preserve Spectrum authoritative source/state evolution on the existing visualizer tick.
- No second visualizer clock, paint-local state mutation, source decimation or cadence cap.
- Logical/state-evolution cadence is distinct from presentation opportunity.
- Attack GUI/request delivery starvation before moving Bubble/Spectrum timing.
- Do not create one catch-all "third thread".
- Qt/QWidget/QPixmap/GL mutation stays on the correct GUI/context owner.
- Strict GL teardown remains fail-closed and byte-accounted.
- Keep the production CPU image-cache cap at 256 MiB until measured evidence justifies a deliberate change.
- No sleeps, nested event pumping, production `gc.collect()`, working-set trimming, process recycling, timeout extension, ignored owners, hidden runtime fallback paths or cadence hacks.
- Configured visualizer display ownership is sticky across transient sleep/wake/non-participation. Preserve the hard-won same-display geometry/aspect-ratio correction path; do not migrate ownership to another display merely because the configured display is temporarily not ready. Cross-display fallback requires authoritative settled-topology absence plus one intentionally coarse ~60-second confirmation opportunity. This is ownership grace, not a frame clock: no polling, dedicated thread, raw periodic timer or exact-deadline requirement. Return to the configured display is event-driven from later authoritative topology plus normal display-runtime readiness.
- Preserve ordinary stable cold-start anti-flash behaviour. `screen.grabWindow(0)` may remain on the normal desktop→screensaver startup path; any removal/bypass is recovery/reinitialization-specific unless separately approved.

# Phase 5 — Active Work

## Immediate Priority Queue

This queue is the **Phase 5 execution authority**. P1 is closed; P2→P4 remain the immediate performance/delivery
sequence. P5 is the next mandatory monitor-topology/sleep-wake hardening lane and must complete
before returning to lower-leverage Phase 5 work in P6. Detailed delivery evidence belongs in
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`; cleanup details belong in
`Future_Cleanup.md`.

P0 diagnostic-scaffolding removal is closed: the temporary A/B/C presentation probe, its
`--viz-present-abc` gate, `Shift+/` hotkey and event-loop-recorder install hook are gone, and the
passive delivery-stage seam in `rendering/adaptive_timer.py` is retained under
`tests/test_adaptive_timer.py::TestDeliveryStageInvariants`. Preserve that as a regression
contract; do not reintroduce runtime class patching as a presentation solution.

### P1 — production presentation/fidelity contract (locked; audit corrections complete)

P1's original landing is closed and made **no production runtime changes**: it added tests and
documentation only. The logical/publication bars remain useful. A post-P1 audit found several
test-semantics problems that could mislead P2; those test-semantics corrections are now complete
and production remains byte-identical to the approved pre-P2 anchor `30e66e08`.

Current useful bars:

- `tests/test_visualizer_presentation_contract.py` — publication/presentation separation on the
  real `SpotifyBarsGLOverlay` with an injected deterministic clock: every accepted publication
  integrates exactly once, presentation requests may be fewer but never more than publications,
  and withholding presentation at both the paint seam and the request seam leaves the covered
  logical state unchanged.
- `tests/test_visualizer_presentation_negative_controls.py` — rejected admission designs
  (target-FPS gate, pending-until-paint latch, latest-at-60 Hz edge loss).
- `tests/test_bubble_cadence.py` — authored step/dt, one-in-flight semantics, discrete-edge
  first-visible timing, and the temporal golden that rejects terminal batching/persistent lanes.
- `tests/test_spectrum_presentation_smoothing.py` — authoritative tick trace against the
  versioned golden; no independent cadence.
- `tests/test_visualizer_replay.py` — all supported modes on the real tick/overlay path, and
  `test_presentation_schedule_does_not_change_logical_series` across presentation rates/stalls.
- `tests/test_phase3_runtime_lifecycle.py`, `tests/test_runtime_destruction.py`,
  `tests/test_gl_compositor_cleanup.py`, `tests/test_spotify_visualizer_mode_transition.py` —
  generation/activation rejection, Settings/recreate, display reassignment, strict GL teardown.

#### P1 audit follow-up — complete (test semantics only)

All five audit items are done:

- Stale R-61 eligibility contract removed. `TestPresentationSourceLiveness` now disqualifies
  `AdaptiveTimerStrategy` in **any** scope, asserts no visualizer presentation is wired to it,
  and prescribes no publication/request ratio.
- `TestMixedRefreshDeliveryPolicyModel` is explicitly a `HAZARD_LIGHT_ONLY` closed-form model;
  it does not execute Qt's real dispatch/composition path and may not be cited as runtime
  acceptance.
- `_logical_digest()` now includes Bubble positional/extra/trail payload, kick/snare strengths and
  envelopes, transient energy, smoothed band state and devcurve payload. The suppression oracle
  is trajectory-based rather than endpoint-only, so a transient Bubble divergence cannot hide by
  returning to the same terminal state.
- `test_stored_overlay_state_is_the_latest_publication_not_a_backlog` now says what it actually
  proves: latest stored state only. `update()` is stubbed, so it does **not** prove paint receipt.
- `presentation_requests <= accepted_publications` is documented as an anti-amplification guard
  only, never as sufficient evidence of fidelity.

The P1 mixed-refresh model remains useful as a **hazard light**, not a live dual-monitor
regression oracle. No P1 unit test may close P2 or overrule installed visual review.

### P2 — fix bad smell 1: publication-coupled visualizer presentation

**Architecture review only. No further production wiring is authorized until Step 2b/2c below is
resolved and the matching Step 3 bars are written against the selected architecture.**

Two production attempts and one source-analysis candidate are closed negative controls. The
premise remains measured: the auxiliary visualizer one-publication → one-`QOpenGLWidget.update()`
stream is a shared-GUI amplifier. The failures were in attempted admission/pacing mechanisms,
not in that causal premise.

See `Docs/Historical_Bugs/R-61_*`, `R-62_*`,
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`, and the preserved R-62 evidence.

#### What the failed attempts established

```text
R-61  sole dependence on AdaptiveTimerStrategy   -> visualizer froze after first transition
R-62  same source, while-active only             -> Bubble worse; state->paint p95 roughly doubled
P2-3  pre-GUI dispatch-window coalescing         -> killed before implementation; no such layer exists
```

R-62 was a **valid active negative result**, not an inert run:

```text
                    u/ss            Bubble state->paint p95
immediate           0.971 - 1.000   4.90 ms median
light deferral      0.949           7.04 ms
heavy deferral      0.699 - 0.755   13.2 - 15.4 ms (peaks 52.7 - 56.5 ms)
```

The windows show a strong dose-response association between more deferral and older Bubble state
at paint. Treat that as strong mechanistic evidence, not as an independently randomized dose:
the borrowed opportunity's own sickness can simultaneously increase deferral and latency.
Bubble logical publication remained ~99.7-100%, strongly localizing the installed regression to
presentation/delivery rather than simulation.

The borrowed compositor opportunity delivered only **~54-56 accepted, irregular Hz under
transition load** (`511/545`, `493/543`). Pacing a ~90 Hz visualizer from that degraded stream
was therefore rejected.

#### Constraints now binding on every P2 candidate

- `AdaptiveTimerStrategy` / `AdaptiveRenderStrategyManager` is disqualified as a visualizer
  presentation source in **any** scope, sole or while-active-only.
- **A pacing source that degrades under the load it is meant to relieve is disqualified.**
- **State-to-paint latency is an acceptance metric, not a diagnostic.** A lower request ratio
  cannot compensate for materially older Bubble state at paint.
- Edge protection must be asserted against the real Bubble **positional-payload** edge in the v1
  golden, on the tick where it becomes visible, not the tick where the event is authored.
- Every logical input is integrated before any presentation coalescing (R-54).
- No producer timestamp gate, display-rate divisor, paint acknowledgement, pending-until-paint
  admission, second visualizer clock, source/event decimation, catch-up replay or repaint requeue
  (R-27/R-54).
- `u/ss < 1.0` proves only that request coupling changed. It is **not** success by itself.
- A narrower candidate cannot silently close P2. Any scope change must be justified in writing
  against the accepted A/B evidence.

#### Step 1 — COMPLETE: dispatch-layer characterization (source analysis, no runtime change)

The current production path is synchronous on the GUI thread end to end:

```text
schedule_recurring(16, _on_tick) -> GUI-thread QTimer/direct callback
    -> _on_tick -> tick_pipeline.push_gpu_frame
    -> display_image_ops.push_gpu_frame -> _push_spotify_bars_overlay_state
    -> SpotifyBarsGLOverlay.set_state() -> _request_frame_update() -> QWidget.update()
```

`rendering/display_image_ops.py` and `widgets/spotify_bars_gl_overlay.py` do not contain an
existing `run_on_ui_thread`, queued `invokeMethod`, `QueuedConnection`, `singleShot` or worker
handoff in this presentation path.

**There is no existing pre-GUI queued-dispatch window to coalesce.** The compositor's
`_srpss_timer_update_dispatch_pending` covers a different layer: a cross-thread callback queued
*before* `widget.update()`. Copying that concept onto the overlay would either manufacture a new
queue or rename post-`update()`/paint-pending state, both barred.

Evidence limits remain explicit:

- existing overlay windows cannot reliably stratify within one transition because they carry no
  transition label and use variable aggregation windows;
- existing fields cannot separate wait-for-opportunity from opportunity inter-arrival jitter.

Those remain unknown; do not add behavioural machinery merely to force an answer.

#### Step 2 — KILLED: request admission / dispatch-window coalescing

Do not revive this family under different names.

- No new queued GUI hop may be inserted merely to create something to coalesce.
- No `QTimer.singleShot`, `run_on_ui_thread`, queued `invokeMethod`, worker, thread, queue or lane
  may be introduced solely as visualizer request admission.
- Qt post-`update()` pending state may not be used as an admission latch; if it clears at
  `paintEvent()`/`paintGL()`, it is pending-until-paint regardless of variable name.
- Do not intercept/suppress `UpdateRequest`, paint, or other Qt events to manufacture admission
  without a separately approved architecture proving no acknowledgement/backpressure semantics.

#### Step 2b — DECISION: do not merge P2 into P3; audit shared-surface presentation feasibility

Claude's four-lane review correctly identified that request-admission mechanisms are exhausted,
but **"reduce per-publication GUI cost" is not a P2 solution**. The accepted A/B intervention
kept logical publication and the overlay `set_state()` handoff alive while suppressing only the
auxiliary `update()` request. The large A→B improvement therefore isolates consequences of the
independent presentation-request stream. Optimizing state preparation may help Bad Smell 1b/P3,
but it cannot by itself close Bad Smell 1.

Likewise, do **not** conclude that P2 is impossible merely because the current separate overlay
has no safe request-admission seam. That proves admission control is the wrong mechanism, not that
the independent presentation owner must exist forever.

The next P2 action is a **read-only/source-level feasibility audit** of a bounded shared-surface
visualizer presentation design:

```text
existing authored visualizer tick
        -> integrate every logical input exactly as today
        -> publish immutable visualizer render state / protected edge identity
        -> one existing per-display GL compositor surface owns drawing
        -> no separate SpotifyBarsGLOverlay presentation surface/request stream
```

This is a narrow Phase-8-prerequisite audit, **not authorization to implement full Phase 8** and
not authorization to merge all QWidget overlays into the compositor.

Why this lane is now eligible for analysis despite the old C-vs-B result:

- B proved suppressing the auxiliary overlay request stream was the dominant measured win.
- C added only ~1.4 FPS by hiding the already request-suppressed surface, proving that mere
  second-surface existence is secondary.
- C did **not** test whether drawing the visualizer on the already-owned display compositor can
  retain visual output while eliminating the independent auxiliary request owner. Therefore
  C-vs-B does not disqualify this architecture question.

`Current_Plan.md` temporarily supersedes any roadmap wording that requires P2 to be already
closed before a **read-only** shared-surface feasibility audit. It does not authorize Phase 8
production work.

#### Step 2c — required shared-surface feasibility questions; no wiring until answered

- [ ] Map the exact compositor draw/lifecycle path in steady-image and active-transition states.
      Determine whether the compositor surface exists and can safely draw a visualizer layer for
      the full visualizer lifetime without becoming transition-owned.
- [ ] Determine the smallest render-state boundary that lets the existing visualizer tick publish
      immutable Bubble/Spectrum/etc. state without moving simulation, smoothing, event identity,
      source sampling or authored dt into paint/compositor code.
- [ ] Determine whether ordinary visualizer publications can target the **same compositor
      `QOpenGLWidget`** without creating another timer/clock. Outside transitions, publication may
      request that existing surface to repaint; during transitions, duplicate requests to the
      same widget may be left to Qt's normal same-widget update merging. Do **not** add a manual
      pending latch to force this result.
- [ ] Prove that the design does not depend on `AdaptiveTimerStrategy` for visualizer liveness.
      The visualizer must continue presenting after transitions stop.
- [ ] Analyze the transition-active cadence risk explicitly. If sharing the compositor would make
      Bubble inherit the same ~54-56 Hz irregular opportunity that failed R-62, the design is
      rejected before implementation unless the architecture itself removes that under-delivery.
- [ ] Map Z-order/card/stencil implications. The current GL visualizer sits above/within a normal
      visualizer card while other widgets remain QWidget-owned; shared-surface rendering must not
      disappear behind the card, bleed outside CUSTOM geometry, or require merging unrelated
      widgets.
- [ ] Preserve CUSTOM geometry/aspect correction, configured-display ownership, fade/visibility,
      startup/recreation generation fencing, and strict GL teardown.
- [ ] Reuse or explicitly transfer shader/program/geometry ownership without duplicate GL deletion
      or hidden shared-context lifetime.
- [ ] Estimate code/lifecycle blast radius before implementation. If this requires a broad Phase 8
      rewrite rather than a bounded visualizer layer, stop and return to an explicit scope
      decision; do not let a P2 fix silently become a compositor rewrite.
- [ ] Record whether the expected benefit is removal of the **independent auxiliary presentation
      owner**, not "the second surface is expensive." Keep those causal claims separate.

If this audit fails, P2 must be explicitly re-scoped or recorded as not safely achievable on the
current separate-surface architecture. Do not return to pacing/admission experiments. P3 may then
proceed as its own Bad Smell 1b lane, but P3 success must not be used to pretend the A/B request
amplifier was fixed.

#### Step 2c — COMPLETE: shared-surface feasibility audit (read-only)

Full findings in `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`.

**Not rejected on cadence (Q5).** The compositor surface is *not* transition-scoped — only its
render-strategy timer is — and it already has a steady-state retained-base draw path. Preserved
evidence shows `render_requests == frames` (511/511, 493/493) with `dur_min=0.32 ms`,
`dur_max=11.02 ms`, so its ~54–56 Hz is a **request rate, not a paint capacity limit**. R-62
failed because Bubble *waited for* that opportunity; a shared surface has Bubble *drive* it from
the existing GUI-thread tick via `compositor.update()`. No new timer, thread or clock, and Qt
merges same-widget updates without a manual latch. Liveness no longer depends on
`AdaptiveTimerStrategy` (Q3/Q4).

**Blocked on scene composition (Q6, Q9).** The overlay is a *sibling* of the compositor, stacked
above the visualizer card, and owns a rounded-rect stencil-mask program for card-corner clipping.
The compositor is the bottom-most child of `DisplayWidget`, beneath every QWidget overlay
including the card. Drawing the visualizer inside compositor paint would render it *behind* its
own card unless the card composition also changes. With ~2.2k lines each side plus mode
renderers, stencil, CUSTOM geometry/DPR and fade, this is a **compositor scene-composition
change, not a bounded visualizer layer** — the stop-and-report case in Step 2b.

Q2/Q7/Q8 (render-state boundary, lifecycle/teardown, shader ownership) are deferred: they are
only answerable after the Q6 Z-order decision and would otherwise be speculation.

**Legacy compositor seam excluded (audited 2026-08-17).** The existing compositor
`_spotify_vis_*` / `set_spotify_visualizer_state()` / `paint_spotify_visualizer()` path is dead
debris from the original Spectrum-only implementation: no production caller, `_spotify_vis_enabled`
set `True` only inside the unreachable implementation and one test, every paint consumer
early-returns, and the routine is `QPainter` bars with zero mode awareness, no stencil/card masking
and no CUSTOM geometry. No modern lifecycle/geometry/state ownership reuses it. It is **not**
evidence that modern modes can move into the compositor cheaply, is excluded from this decision,
and must not be revived or extended. Logged in `Future_Cleanup.md`. The Q6/Q9 blockers stand
unchanged.

**Q5 wording, conservative.** `render_requests == frames` proves only that there was no obvious
loss **at the observed ~54-56 Hz request rate**. It does not prove the compositor will cleanly
deliver ~90 Hz once the visualizer drives `compositor.update()`, under a different request pattern
and with visualizer draw work added to each paint. That remains unproven and would need
measurement.

#### Step 2d — DECIDED 2026-08-17: Option B (deferred, not closed)

**P2 is not solved, not abandoned, not impossible and not permanently closed.**

Recorded status of Bad Smell 1: a **measured unresolved presentation defect** that is **not
safely correctable on the current separate-surface architecture with any presently identified
request-layer mechanism**. The causal premise stands and the evidence is retained.

What remains in force and must not be weakened:

- the accepted A→B→C→A result — suppressing only the auxiliary `update()` request stream improved
  both compositors, restoring it degraded them again in the same process;
- the measured coupling `update_requests / set_state == 1.0000` across both modes, with the
  overlay painting ~31% above what the 60 Hz display can present at ~1.7 ms CPU p95 per paint;
- every P2 acceptance bar in Step 3 below, for any future candidate.

**P3 and P4 success must never be represented as fixing P2.** They are separate measured owners
(Bad Smell 1b and Bad Smell 2). Closing them does not close Bad Smell 1.

Sequence now in force:

1. **P3** — attribute the remaining visualizer-family GUI handoff/preparation cost.
2. **P4** — name and fix the residual non-visualizer queued-GUI-dispatch owner.
3. **Re-measure** the equivalent 165 Hz + 60 Hz scenario on ordinary `main.py` with `--perf` and
   `--gpu-timing`; reassess the remaining delivery deficit against the accepted report.
4. **Only then** decide whether the residual P2 cost justifies promoting shared-surface/card work
   into a deliberate Phase-8-class architecture change.

P3 and P4 are taken first because they are independently measured owners carrying substantially
smaller architectural risk than compositor/card scene composition.

Deferred deliberately, not forgotten:

- The shared-surface/card design remains **the only currently identified direct architecture for
  removing the independent presentation owner.** It is not claimed to be the only conceivable one.
- **Do not run the ~90 Hz compositor-driving measurement now.** It would characterize a
  hypothetical architecture against a baseline P3/P4 are about to change. Revisit after P3/P4 if
  the shared-surface question is reopened, or earlier only if an independent question requires it.
- The dead legacy compositor Spectrum seam stays excluded from P2 and queued for cleanup only.

**Regression clue to preserve.** Substantially better 165 Hz behaviour existed historically. That
is retained as evidence: if P3/P4 do not recover enough delivery headroom, a historical
architecture comparison is a legitimate next investigation **before** concluding that the modern
multi-mode GL visualizer fundamentally cannot reach the target. Do not treat the current deficit
as an inherent property of the modern architecture until that comparison has been made or
explicitly rejected with evidence.

#### Step 3 — test bars required before any selected P2 production implementation

- [ ] Bubble **visible positional-payload edge** from the v1 golden survives actual presentation
      receipt on the tick where it becomes visible.
- [ ] Add a phase-offset/GUI-stall matrix so the protected edge survives whether publication lands
      just before, during or just after the selected presentation path's natural coalescing.
- [ ] State-to-paint p50/p95/max does not materially worsen versus an equivalent approved 1:1
      baseline at equal publication/load. Better FPS/request counters cannot compensate for older
      state.
- [ ] First-visible Bubble attack/edge latency does not worsen; Spectrum authoritative smoothing
      and tick trace remain unchanged.
- [ ] Logical/mode-owned state evolution remains equivalent with and without presentation
      suppression using the strengthened P1 trajectory oracle plus the existing versioned goldens.
- [ ] If shared-surface is selected, test steady-state visualizer liveness with no transition,
      active-transition liveness, transition start/finish, resize/CUSTOM geometry, display
      reassignment, Settings recreation and strict GL teardown.
- [ ] If shared-surface is selected, prove it introduces **no new visualizer timer, worker,
      display-rate gate, paint acknowledgement or manual pending-until-paint latch**.
- [ ] Teardown/recreation/generation invalidation rejects stale visualizer state and leaves no
      duplicate shader/program/context ownership.
- [ ] Both overpaint and under-delivery remain detectable; R-27's
      `set_state≈90-100` / `paint-update≈39-40` stutter signature is absent.
- [ ] The synthetic P1 mixed-refresh model remains green only as a hazard light; it cannot be
      cited as runtime acceptance.

#### Step 4 — runtime gate

- [ ] Confirm the selected candidate is active in the owning sidecar before interpreting results.
- [ ] Use an equivalent ordinary `main.py` dual-display run with `--perf` and `--gpu-timing`;
      compare against the accepted A/B/C/D baseline and approved behavioural reference.
- [ ] Record logical publication, state handoff, presentation requests per target surface, paints,
      state-to-paint p50/p95/max, protected-edge receipt, 165/60 delivery acceptance, and
      transition/non-transition windows together.
- [ ] Installed Bubble and Spectrum visual review is the acceptance authority. If either is worse
      in any relevant way, revert the isolated candidate immediately; do not tune it in place.
- [ ] A candidate may close P2 only if it materially addresses the measured **independent
      auxiliary presentation-request amplifier** without changing authored logical behaviour,
      increasing temporal age, or moving the same pressure into another independent queue/surface.

### P3 — attribute the remaining visualizer-family GUI handoff/preparation cost

P3 remains a distinct defect lane. **Do not merge P2 into P3 merely because both execute on the
GUI thread.** B/C kept logical publication and state handoff alive while suppressing presentation;
the separate no-visualizer control improved again, proving another visualizer-family cost exists.

- [ ] After the P2 architecture decision (or an explicit recorded inability to close P2 on the
      separate-surface architecture), measure producer/state-build → pure-data preparation →
      Qt-owned overlay/render-state commit separately from presentation request and paint.
- [ ] **Standing confound:** P2 was deferred rather than corrected (Step 2d, Option B), so the
      auxiliary one-publication → one-`update()` stream is live during every P3 measurement.
      State it explicitly in attribution. Do not subtract it by assumption, and do not let its
      cost be silently reassigned to preparation/commit.
- [ ] The no-visualizer control proves another visualizer-family GUI cost exists, but does **not**
      prove `SpotifyBarsGLOverlay.set_state()` alone owns it.
- [ ] If pure-data render-state preparation is a measured owner, move only thread-safe immutable
      preparation off GUI; QWidget/QColor/QPixmap/GL mutation stays on the GUI/context owner.
- [ ] Do not turn logical state into paint-driven state and do not create another visualizer
      scheduler.

#### P3 Step 1 — COMPLETE: source classification of `set_state()`

Full map in `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`. `set_state()` is
805 lines (586-1391), classified into the four required categories:

- **Cat 1 (not movable):** accumulated time/dt, `_line_smoothed_*` asymmetric smoothing, sine peak
  envelopes, waveform smoothing and ghost rings, kick/snare event envelopes, transient snapshot,
  Spectrum peaks/hysteresis, Bubble temporal payload, `apply_state_handoff()` activation identity.
- **Cat 2 (only extraction candidate):** bar clamping, 97 numeric coercions, payload list copies.
- **Cat 3 (GUI-owned):** 28 `QColor` constructions, geometry read/set, visibility/show, shadow sync.
- **Cat 4 (P2, kept separate):** `_request_frame_update()` → `update()`.

**Primary hypothesis, unmeasured:** the dominant cat-2/cat-3 per-publication cost may be
**re-derivation of unchanged configuration**, not preparation. The 28 `QColor` constructions and
97 coercions are guarded only by `is not None` with no change detection — roughly 2,500 QColor
constructions and 8,700 coercions per second at ~90 Hz, for values that change only on
settings/preset/activation change. If confirmed, the correction is revision/identity-gated
configuration commit, **not** worker extraction: it touches no cat-1 state, needs no thread
boundary, and cannot be mistaken for a P2 fix.

#### P3 Step 2 — measurement design (no production change yet)

- [ ] Add sampled **in-callback self-time** accumulation for categories 1-4 separately inside
      `set_state()`. Not FPS, not end-to-end callback latency, not paint duration.
- [ ] Keep category 4 strictly separate; its downstream cost is Bad Smell 1 and must not be
      attributed to categories 1-3.
- [ ] Record visualizer mode as a covariate, never as an explanation.
- [ ] Observational only — no queued hop, timer, or event interception.
- [ ] Confirm or reject the unchanged-configuration hypothesis before proposing any change.

### P4 — fix/name bad smell 2: residual queued-GUI-dispatch loss without visualizers

- [ ] After P2/P3, repeat a visualizer-disabled control with Media still enabled.
- [ ] Attribute the remaining 165 Hz dispatch-pending bursts to concrete GUI callbacks/owners.
- [ ] Close the owner by extraction/narrowing only when direct evidence names it; do not tune the adaptive timer, and do not hide the owner by changing how compositor update requests are coalesced. (This constrains the **compositor's** request ownership only. It is not a requirement that the visualizer keep one auxiliary `update()` per publication — P2 exists to remove exactly that.)
- [ ] Do not claim Phase 5 delivery closure while a no-visualizer run still loses roughly five percent of 165 Hz deadlines for an unnamed reason.

### P5 — harden authoritative monitor topology and physical sleep/wake recovery

This is **not deferred cleanup**. It follows P2→P4 because the installed non-diagnostic runtime
has a repeatable high-severity physical-monitor recovery failure: when both displays are off while
the screensaver runtime is active, waking them can leave one display visible but frozen, the other
blank, all Qt input dead, and recovery possible only after Ctrl+Alt+Delete disturbs the Windows
desktop/display state.

A 2026-08-17 Diagnostic failure finally captured enough wake/rebuild breadcrumbs to **reorder and
strengthen the existing targets without deleting any of them**. It did not produce a Python
traceback or a clean orderly-exit record, so the exact terminal native operation remains unproven.
Do not claim more than the evidence shows.

#### New accepted diagnostic checkpoint — target priority, not root-cause declaration

The failing wake sequence showed:

```text
~19:58:51  WM_DISPLAYCHANGE / Qt topology churn
            MSI G321Q appears; LG TV disappears
            monitor reconcile is already pending and is not re-armed
            transient topology is accepted as one MSI display
            full runtime teardown/rebuild begins

~19:58:55  LG TV appears again
            second topology change is accepted as MSI + LG
            second full teardown/rebuild begins only seconds after the first
```

Additional evidence from the same run:

- `[SCREEN] Ignoring screen change for deleted display widget` occurred during churn. The guard
  rejected the stale target, but the event proves old per-window/native mutation can overlap an
  engine-level replacement generation.
- The temporary one-display reconstruction logged a Spotify visualizer CUSTOM fallback to the
  participating display while the configured display was only temporarily missing. P5-D is now
  directly evidenced by the failing wake trace, not only by historical R-26.
- Both observed destruction barriers completed promptly (about **94 ms** and **172 ms**) and the
  run progressed through GL cleanup/reconstruction far beyond the earlier `makeCurrent()`
  suspicion. Therefore GL teardown/context acquisition remains instrumented but is **lower
  priority for this incident**, not removed as a target.
- The second two-display rebuild completed D0 and progressed deep into D1 construction. The last
  narrow replay sequence was:

  ```text
  clock replay_start
  clock replay_after_payload
  clock replay_after_update_position
  clock replay_final

  media replay_start
  media replay_after_payload
  [SPOTIFY_VOL] Positioned volume widget ...
  <logging ends before media replay_after_update_position>
  ```

  A later successful Diagnostic launch with the same layout crossed
  `media replay_after_update_position` and continued to both displays ready. This does **not**
  prove `MediaWidget` is the root cause; it identifies a much narrower last-entered/not-returned
  boundary inside D1 CUSTOM-layout replay during a poisoned double-rebuild topology sequence.
- The replacement generation can be reported/started as RUNNING while staged display readiness is
  still incomplete. The exact safety of that boundary is now an explicit audit target.

#### P5 evidence-prioritized execution order

Keep **all** previously listed suspects/breadcrumb targets. Reorder work as follows:

```text
1. P5-A + P5-B  stop overlapping topology authorities and transient-snapshot rebuilds
2. P5-C1        make replacement one transaction with an explicit all-display readiness boundary
3. P5-C2        instrument/narrow D1 per-widget CUSTOM replay, especially Media update_position
4. P5-D         stop eager visualizer ownership migration during transient participation
5. P5-E         remove grabWindow(0) only from recovery-critical reinit; preserve cold-start polish
6. P5-F         installed physical-off/wake acceptance and residual native-boundary attribution
```

The older GL cleanup/context, surface creation, show/reveal and `grabWindow(0)` suspects remain in
the breadcrumb set because a different wake failure may stop there. This run **demotes** them as
the terminal boundary for this incident; it does not exonerate them globally.

#### P5-A — one authoritative monitor-topology owner

- [ ] Make `DisplayManager` (or one equivalently explicit engine-level owner) the sole authority
      that decides whether a display event is a no-op, re-anchor or full runtime replacement.
- [ ] Reduce `WM_DISPLAYCHANGE`, Qt `screenAdded`/`screenRemoved`, and related per-window callbacks
      to topology-invalidated notifications plus strictly local bookkeeping. A `DisplayWidget`
      must not walk/reconfigure all displays while the manager can retire the same runtime.
- [ ] Preserve per-display DPR/geometry/surface ownership, but issue mutations from one accepted
      topology decision against one identified runtime generation.
- [ ] Treat the observed "screen change for deleted display widget" as regression evidence:
      duplicate native+Qt event storms must produce one authority/decision, not stale-widget
      re-anchor attempts racing a replacement.
- [ ] Add focused tests proving duplicate native+Qt event storms produce one authoritative
      decision/rebuild rather than overlapping re-anchor and teardown/recreate paths.

#### P5-B — true trailing-edge topology settling

The captured failure directly exercises this defect: the first event armed reconciliation and
later churn encountered an already-pending reconcile rather than extending the quiet period,
allowing a temporary one-display topology to be accepted and rebuilt before the second display
returned.

- [ ] Replace first-event-style settling with a **true trailing-edge quiet-period debounce**:
      every relevant topology event restarts the quiet timer.
- [ ] Add a bounded maximum settle deadline so pathological driver/event storms cannot postpone
      reconciliation forever. Reaching the bound yields one explicit best-known snapshot/decision,
      not retries or nested event pumping.
- [ ] Freeze accepted screen count/order/identity/geometry/DPR into one topology snapshot/generation
      before destructive replacement. Do not rebuild from a temporary D0-only/MSI-only view merely
      because the sibling display has not returned yet.
- [ ] A topology snapshot accepted for replacement must remain immutable for that transaction; a
      newer topology generation invalidates/queues a later transaction rather than mutating the
      one already retiring/rebuilding.
- [ ] Record low-rate breadcrumbs for event receipt, debounce restart, maximum-settle arm/hit,
      accepted snapshot/generation and decision.
- [ ] Add a deterministic reproduction of the captured pattern: add/remove churn inside the quiet
      window must extend settlement and collapse to one final two-display decision rather than
      two full rebuilds seconds apart.

#### P5-C1 — transactional replacement and explicit readiness commit

- [ ] Make monitor replacement an explicit transaction:

  ```text
  settle topology
      -> freeze snapshot/generation
      -> stop further old-runtime topology mutation
      -> retire old runtime exactly once
      -> pass existing destruction barrier
      -> construct/register complete replacement against frozen snapshot
      -> stage per-display reveal/widget readiness
      -> commit replacement only at the defined all-display-ready boundary
  ```

- [ ] Preserve the existing all-displays-registered-before-staggered-show principle. The current
      reveal staggering may remain unless evidence proves it harmful.
- [ ] Audit the current `RUNNING` transition/readiness relationship. A topology replacement must
      **not be treated as fully committed merely because DisplayWidget objects exist**. Either:
      - delay normal RUNNING/replay/provider activity until every display in the frozen snapshot
        reaches the authoritative ready boundary; or
      - prove, owner by owner, that every activity permitted before `ready=N/N` cannot touch or
        publish into an incomplete display generation.
      Prefer one explicit commit boundary over a collection of exceptions.
- [ ] Generation-fence every delayed D0/D1 reveal/readiness callback so a newer topology event or
      terminal shutdown cannot complete the wrong transaction.
- [ ] Do not weaken Phase 3/R-49 strict GL teardown, restore hide/reuse, ignore failed deletion,
      extend destruction timeouts or move GL teardown to a worker as a recovery shortcut.

#### P5-C2 — new narrow failure target: per-widget CUSTOM replay during D1 rebuild

This is **additional**, not a replacement for topology fixes. The double-rebuild/topology poison
must be fixed first; then this seam becomes the next last-entered/not-returned boundary if the
failure survives.

- [ ] Add low-frequency, flush-safe before/after breadcrumbs around
      `CustomLayoutManager._apply_entry_to_widget()` for each widget during monitor recovery,
      including widget id, screen index, topology generation and runtime generation.
- [ ] Split the existing replay stages so a future hang can distinguish:
      - replay entry/begin;
      - size-payload apply begin/end;
      - stack-offset reset begin/end;
      - widget `update_position()` begin/end;
      - committed `setGeometry()` reassert begin/end;
      - replay final/end.
- [ ] Start with `media` because the captured run ended after `media replay_after_payload` and
      before `media replay_after_update_position`; do **not** hard-code a "MediaWidget caused it"
      conclusion. Instrument the generic owner so another widget can implicate itself.
- [ ] Trace synchronous side effects of `MediaWidget`/`BaseOverlayWidget.update_position()` under
      CUSTOM geometry: stacking, geometry change callbacks, visualizer/volume neighbour positioning,
      resize/layout invalidation, QWidget native geometry work and any cross-widget manager calls.
- [ ] Record the exact screen/runtime identity used by every geometry calculation so D1 cannot
      accidentally consult stale D0/retired-generation state during replay.
- [ ] Do not add retries, sleeps, event pumping or timeout-based recovery around
      `update_position()`/`setGeometry()`. First pass is attribution only.
- [ ] Add deterministic replay/recreation tests for two displays where D1 replays Media + Spotify
      volume/visualizer CUSTOM layout after a topology generation replacement.

#### P5-C3 — retain older native/GL blocking targets, but investigate after C2 for this signature

Do **not** delete any of the earlier breadcrumbs. Keep before/after attribution around:

- native `WM_DISPLAYCHANGE` enter/exit per display;
- monitor reconcile begin/accepted snapshot/emit;
- engine monitor-change stop/rebuild boundaries;
- display cleanup begin/end;
- GL compositor cleanup and `makeCurrent()` begin/end;
- strict GL cleanup sub-sections where needed;
- offscreen warmup surface/context `makeCurrent()`/`doneCurrent()`/destroy;
- destruction barrier arm/complete;
- rebuild begin/end;
- D0/D1 show callback begin/end;
- recovery `grabWindow(0)` call/skip begin/end;
- widget `show()` begin/end;
- `_handle_screen_change()` begin/end;
- `_ensure_gl_compositor()` begin/end.

The captured run crossed enough of these boundaries that they are **not the leading terminal
owner for this incident**, but retaining them is cheap and protects against a different physical
wake ordering failing earlier.

#### P5-D — sticky visualizer display ownership; conservative fallback and nearly-free return-home

The diagnostic run directly observed eager CUSTOM visualizer fallback during a temporary
one-display wake topology. That is now a real failure signature, not merely an architectural
preference.

- [ ] Preserve the existing same-display visualizer geometry/aspect-ratio stabilization and
      correction work. Geometry correction is **not** permission to change ownership.
- [ ] Treat a configured visualizer monitor that still exists in authoritative settled topology
      but is asleep, rebuilding, lacks a ready `WidgetManager`, or is temporarily non-participating
      as **temporarily unavailable, not absent**. Hold/park/hide/defer on the configured target.
      **Do not start an absence timer for mere non-participation.**
- [ ] Retire the current ~1500 ms remote CUSTOM participation fallback as cross-display authority.
      Same-display readiness/geometry rechecks may remain only if independently required.
- [ ] Begin cross-display fallback consideration only after P5-B accepts an authoritative settled
      topology snapshot in which the configured monitor is genuinely absent. Record one absence
      candidate tied to topology/runtime generation.
- [ ] Confirm sustained absence with **one intentionally coarse lifecycle-owned recheck at
      approximately 60 seconds**. No polling loop, periodic timer, dedicated thread, worker wait,
      sleep or repeated retry chain.
- [ ] Any newer authoritative topology generation invalidates the old absence candidate. Return
      before the coarse recheck makes the stale callback a generation/token-owned no-op.
- [ ] If the single coarse recheck still finds genuine absence, one fallback transfer is allowed.
- [ ] Return-home is **event-driven and timer-free**: later settled topology contains the configured
      display -> normal display-runtime readiness -> retire fallback owner once -> restore configured
      owner once. No reverse polling timer.
- [ ] Preserve saved CUSTOM geometry/aspect authority across fallback and return-home.
- [ ] Test D0-before-D1, D1-before-D0, temporary zero/partial participation, >60 s true absence,
      physical removal, return before grace, return after fallback, Settings/recreation while armed,
      and stale-generation callback rejection.

#### P5-E — keep `grabWindow(0)` startup polish; remove it from recovery-critical reinit only

This target remains. The captured run progressed beyond the earlier screenshot/show/context
suspects, so it is lower-priority for this specific signature, **not cancelled**.

- [ ] Preserve `screen.grabWindow(0)` on ordinary stable desktop→screensaver cold startup because
      it avoids desktop/wallpaper→black→first-photo flash.
- [ ] On monitor-topology replacement / physical wake recovery, do **not** synchronously require a
      waking-desktop screenshot before reconstructing the display. Prefer retained SRPSS image/
      replay state; if none is safe, keep updates blocked until the first real SRPSS image.
- [ ] Keep ordinary startup appearance unchanged. Test normal cold start separately from recovery.

#### P5-F — installed physical-off/wake and ownership-recovery gate

- [ ] Add deterministic coverage for topology-event coalescing, true trailing-edge settling,
      bounded maximum settle, frozen snapshots, one replacement transaction, explicit all-display
      readiness commit, stale-generation rejection, generic per-widget CUSTOM replay boundaries,
      sticky visualizer ownership, one coarse ~60 s absence candidate, event-driven return-home,
      and recovery-specific desktop-capture bypass.
- [ ] Prove monitor fallback introduces no periodic polling, dedicated worker/thread, per-frame
      check or exact-deadline dependency.
- [ ] Run repeated installed **ordinary non-diagnostic** cycles where both displays are physically
      off before/during screensaver activation, remain off for a meaningful/overnight-equivalent
      period where practical, then wake together and in opposite sequential orders.
- [ ] Include the exact captured churn class: one monitor temporarily returns/disappears before
      the sibling stabilizes. One wake episode must not cause serial full-runtime rebuilds from
      transient snapshots.
- [ ] Include visualizer ownership cases: target returns before grace; target remains truly absent
      beyond grace and falls back once; target later returns and restores home once.
- [ ] Pass only when both displays recover/reveal, clocks advance, Escape/context menu/input remain
      responsive, topology replacement commits once per settled generation, visualizer ownership
      does not migrate on transient participation, genuine absence fallback/return works, normal
      cold-start remains flash-free, and Ctrl+Alt+Delete is never required.
- [ ] If a freeze remains, use the **last entered/not-returned breadcrumb** to reprioritize the
      retained target list. Do not compensate with sleeps, retries, forced paints, timeout
      extensions, relaxed GL ownership or additional monitor-polling machinery.

### P6 — resume lower-leverage Phase 5 work

- [ ] Return to absolute memory/commit/VRAM attribution, remaining proven GUI service/cache work, parser/logging debt and compatibility cleanup only after P1–P5 reach their gates.


## P5.0 Media Provider Runtime Validation

- [ ] Validate Spotify Browser in ordinary `main.py` against Firefox first and at least one Chromium browser.
- [ ] Confirm metadata/control selection, desktop-Spotify-first volume and exact selected-browser whole-session fallback.
- [ ] Repair the real `MediaWidget` missing-session hide contract; tests may not invent production lifecycle API.

## P5.0A Immediate Installed Validation

- [ ] Validate compact day/date grouping and Digital → Analogue → Digital authored scale in Normal and MC builds, including Settings apply/restart and CUSTOM persistence.
- [ ] Validate the optional media progress pill with playing, paused, seek and unknown-duration sessions; confirm no independent polling/cadence and bounded repaint/layout work.

## P5.1 Visualizer Fidelity And Stronger Goldens

- [ ] Capture approved numerical source features/playback offsets and source-to-state/source-to-visible timing for Bubble and Spectrum.
- [ ] Use current Preset 1 as a capture anchor across every supported mode while retaining per-mode acceptance.
- [ ] Add installed Spectrum state-publication → overlay-state → paint receipt with bounded distributions and display refresh identity.
- [ ] Exercise attack, drop, rapid alternation, pause/resume, transition overlap, mode switches and deliberate GUI stalls without changing authored cadence.
- [ ] Visually validate Sine Waves, Oscilloscope and Dev Curve against the current shared source.
- [ ] Complete scheduler-ownership negative controls before any Phase 7 presentation decoupling.

Protected Phase 5 visualizer work is cadence-neutral only: cache immutable configuration
or lookup data where safe, but keep live source consumption, simulation, event identity,
publication order and existing clocks unchanged.

## P5.2 UI Delivery And Transition Root Cause

Detailed accepted evidence:
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`.

### Accepted attribution checkpoint

- adaptive-render deadline wakeup is no longer the dominant suspect; failing runs retain near-target wake opportunity while later GUI/presentation stages reject deadlines;
- retained-current texture identity, steady retained-base draw and redundant ordinary upload copies are closed owners;
- the 2026-08-16 same-process A→B→C→A test proves the auxiliary visualizer one-publication → one-`QOpenGLWidget.update()` stream is a **material shared-GUI amplifier**;
- hiding the still-live visualizer GL surface adds only a smaller benefit beyond suppressing its update-request stream, so Phase 8 surface consolidation is not justified by this evidence;
- visualizer shader GPU execution remains tiny; the proven loss is Qt/GUI delivery pressure rather than shader cost;
- the separate no-visualizer-from-start control improves again while Media/GSMTC remains active, proving another visualizer-family GUI owner remains to be measured;
- even with visualizers absent, the 165 Hz display still loses a smaller but repeatable fraction of deadlines, now dominated by queued-GUI-dispatch skips. This is a second independent bad smell and remains open.

### Active gate

For the delivery/performance thread, P1 is closed and execution continues through **Immediate Priority Queue P2→P4** above.
P5 monitor-topology/sleep-wake hardening follows immediately after those gates and before P6 lower-leverage work.

- P2 owns the proven visualizer presentation-request correction.
- P3 owns the still-unproven visualizer handoff/preparation attribution.
- P4 owns the residual non-visualizer queued-GUI-dispatch owner.
- P5 must preserve the P1–P4 presentation/fidelity contracts while centralizing topology and recovery ownership.
- No repaint retry, scheduler gate, display-FPS cap, visualizer cadence compensation, paint acknowledgement or source/event decimation is permitted.

## P5.2A Remaining GUI Workload Extraction

Target contract: **Prepare → Commit → Persist**.

- [ ] Audit remaining provider/widget callbacks for filesystem/JSON/filter/sort/credential work only where source inspection proves it.
- [ ] Keep Gmail user-triggered backend-mode write, IMAP credential save/delete, OAuth local-token deletion/revoke and expired-token refresh as explicit candidates rather than reopening closed cold-construction work.
- [ ] Revisit worker width or a dedicated presentation timing service only if later evidence shows queue/execution contention. Current evidence does not justify widening pools or moving visualizer scheduling.

## P5.2B GPU / Presentation Attribution

- [x] Record refresh, logical publication, overlay-state, update-request and paint rates per display.
- [x] Prove by same-process A/B/A that suppressing only auxiliary visualizer update requests materially improves compositor delivery on both displays while logical visualizer state continues publishing.
- [x] Prove hiding the still-live visualizer GL surface is a secondary effect in the accepted Spectrum run.
- [x] Prove sampled visualizer shader GPU cost is far too small to explain the delivery loss.
- [ ] P2: complete the shared-surface visualizer feasibility audit and either select a bounded architecture that removes the independent auxiliary presentation owner or explicitly record why P2 cannot be safely closed on the current surface model.
- [ ] P3: split and measure logical render-state preparation / overlay commit cost from presentation request and paint; P3 may not be used as a substitute for the isolated A/B request-stream defect.
- [ ] Preserve Bubble edge/event visibility and all supported-mode logical goldens under whatever presentation architecture is selected.
- [ ] Do not begin broad Phase 8 production work from C-vs-B. A read-only/bounded shared-surface feasibility audit is allowed because request-admission mechanisms are exhausted; C-vs-B only showed that mere second-surface existence is secondary.

## P5.2C Compatibility, Fallback And Debris

Delete one proven authority at a time; do not combine cleanup with behaviour changes.

- [ ] Remove the temporary Bubble compatibility façade only after direct-path/call-graph proof, preserving exact cadence, snapshots, one-in-flight semantics, task category, callback ordering and generation identity.
- [ ] Audit `core/threading/compute_lanes.py` and lane APIs after façade removal; remove only after production/dynamic/test/frozen-use proof.
- [ ] Audit `rendering/render_strategy.py`, `widgets/dimming_overlay.py`, `sources/rss_source.py`, and `transitions/overlay_manager.py::_raise_halo_topmost` for proven dead compatibility use.
- [ ] Keep each deletion reversible and independently tested.

## P5.3 Absolute Memory, Commit, VRAM And Cache Efficiency

Containment/lifecycle plateaus are healthy; absolute process cost remains open.

- [ ] Capture cold, warm, active-transition, steady-image, quiescent-runtime and post-churn snapshots under one controlled scenario.
- [ ] Reconcile whole/main/child RSS, private commit, USS, worker mappings, thread stacks, Qt/native heaps, driver mappings and tracked application bytes.
- [ ] Separate one-time high-water retention from live ownership and repeated-cycle growth.
- [ ] Audit exact-transform per-display image duplication without collapsing different DPR/transform outputs.
- [ ] Audit raw/scaled/display co-retention, unused prefetch results, future-byte pressure and eviction churn using actual hit/miss/fallback cost.
- [ ] Treat GPU memory and GPU busy as separate metrics.
- [ ] If tracked ownership reaches expected zero/plateau while process memory still rises, open an evidence-led retention incident before changing budgets/lifecycle policy.

## P5.4 Logging And Evidence Quality

Current logging architecture is intentionally retained:

- bounded process-owned writer;
- persistent main/sidecars before optional fancy console;
- canonical machine sidecars;
- human-readable main/WARNING+ fan-in;
- 2 MiB rotations with longer bounded Diagnostic main/usage/lifecycle retention;
- queue, file-commit and console timing in final `[LOG_QUEUE]`;
- direct independent Diagnostic crash breadcrumbs.

- [ ] **Repair the canonical evidence parser before treating parser 1.21 as authoritative.** Commit `264ac5a` replaced `tools/recovery_evidence_parser.py` with the 1.21 compatibility front-end while that front-end imports `recovery_evidence_parser` as its `_base`. In the canonical filename this resolves back to itself/circularly and no longer contains the 1.20 parsing engine it claims to wrap. Restore a real base implementation or fold 1.21 compatibility into the canonical parser, then run focused parser tests.
- [ ] Update parser/harness wording to 1.21 only after the canonical tool passes old-format, fancy-main, sidecar, rotation and exact-source tests.
- [ ] Update logging configuration tests for the intentional 2 MiB and Diagnostic retention profiles; do not weaken all handlers to one generic ceiling.
- [ ] Late Phase 7: inventory high-volume families, move routine records to existing sidecars, and simplify token fallback only after structured family metadata coverage is complete.
- [ ] Never "improve" performance by deleting evidence needed to understand it.

## P5.5 Verification

- [ ] Treat `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` as the accepted pre-fix delivery baseline for P2–P4.
- [ ] Run focused owning-subsystem tests after every change; do not default to monolithic `pytest -q`.
- [ ] Use `tests/run_chunked.py` only when a broader release gate is useful.
- [ ] Preserve visualizer temporal goldens/negative controls for visualizer-adjacent cleanup.
- [ ] Official performance comparisons use ordinary `main.py`; name `--gpu-timing` observer differences explicitly.
- [ ] Long soak/lifecycle captures preserve enough main + relevant sidecar rotations to cover the claimed interval.
- [ ] P5 physical-monitor recovery validation uses ordinary installed `main.py`/screensaver behaviour as the acceptance authority; deterministic tests do not substitute for real display-off/wake cycles.

## Low-Priority Presentation Follow-Ups

Keep behind active delivery/resource work and do not introduce polling/repaint loops.

- [ ] Media progress click-to-seek through the accepted GSMTC session/controller authority.
- [ ] Replace progress outline-like glow with a cached/style-invalidated soft halo.
- [ ] Extend clock separator configuration to Analogue while preserving cadence, geometry and settings round-trip.

## Phase 5 Exit Gate

- [ ] Bubble and Spectrum are separately approved equal or better than `ff934616`; other modes retain current behaviour.
- [x] Retained-current texture identity and steady old/new upload ownership are corrected.
- [x] Routine logging and ordered settings persistence no longer perform ordinary file work on the GUI caller.
- [ ] Proven remaining service/cache preparation no longer performs avoidable synchronous GUI work.
- [ ] Host-pressure request-age/tick tails materially improve or remaining stage/owners are named without cadence hacks.
- [ ] GPU busy is attributed enough to distinguish upload/transition/visualizer/presentation cost.
- [ ] Absolute RAM/private-commit/VRAM excess is reduced or explicitly attributed in an approved decision record.
- [ ] Promoted compatibility/fallback debris is removed or retained with a real current contract.
- [ ] Stronger visualizer temporal/paint-receipt evidence is complete.
- [ ] Canonical evidence parser and logging tests match the current logging format/retention contract.
- [ ] Physical monitor-off→screensaver→wake recovery passes repeated dual-display installed cycles without frozen UI/blank sibling display, without eager visualizer ownership migration, and without weakening strict GL teardown or normal cold-start anti-flash behaviour.
