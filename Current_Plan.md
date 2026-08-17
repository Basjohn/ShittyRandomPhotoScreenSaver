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

This queue is the **Phase 5 execution authority**. P1→P4 remain the immediate performance/delivery
sequence. P5 is the next mandatory monitor-topology/sleep-wake hardening lane and must complete
before returning to lower-leverage Phase 5 work in P6. Detailed delivery evidence belongs in
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`; cleanup details belong in
`Future_Cleanup.md`.

P0 diagnostic-scaffolding removal is closed: the temporary A/B/C presentation probe, its
`--viz-present-abc` gate, `Shift+/` hotkey and event-loop-recorder install hook are gone, and the
passive delivery-stage seam in `rendering/adaptive_timer.py` is retained under
`tests/test_adaptive_timer.py::TestDeliveryStageInvariants`. Preserve that as a regression
contract; do not reintroduce runtime class patching as a presentation solution.

### P1 — production presentation/fidelity contract (locked; regression bar for P2)

P1 is closed. These are now the acceptance bars P2 must keep green; do not weaken one to make
a presentation change pass.

- `tests/test_visualizer_presentation_contract.py` — publication/presentation separation on the
  real `SpotifyBarsGLOverlay` with an injected deterministic clock: every accepted publication
  integrates exactly once, presentation requests may be fewer but never more than publications,
  and withholding presentation at both the paint seam and the request seam leaves logical state
  bit-identical. Also owns the mixed-refresh delivery bar and per-display independence.
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

The mixed-refresh bar is a deterministic policy property, not a live dual-monitor measurement.
Installed dual-display acceptance remains P5-F.

### P2 — fix bad smell 1: publication-coupled visualizer presentation

**Design only. Do not implement until step 1 below is complete and reviewed.**

Two implementations have been rejected. The premise is unchanged and still measured; both
failures were in the **mechanism**. See `Docs/Historical_Bugs/R-61_*` and `R-62_*`, and the
preserved evidence at `logs/evidence_chest/08_17_8eb381fb_p2_transition_deferral_REJECTED/`.

#### What the two failures established

```text
R-61  sole dependence on AdaptiveTimerStrategy   -> visualizer froze after first transition
R-62  same source, while-active only             -> Bubble worse; state->paint p95 doubled
```

R-62 is a **valid negative result**, not an inert run: registration is logged at 16:18:40,
16:20:22 and 16:23:14, and `u/ss` fell from `1.000` to `0.699-0.755` while deferral was active.
The mechanism worked. Working is what broke Bubble.

```text
                    u/ss            Bubble state->paint p95
immediate           0.971 - 1.000   4.90 ms median
light deferral      0.949           7.04 ms
heavy deferral      0.699 - 0.755   13.2 - 15.4 ms (peaks 52.7 - 56.5 ms)
```

Latency scaled with the amount of deferral, a dose-response relationship across 31 windows.
Bubble logical publication held at ~99.7-100%, so the **simulation path is exonerated**; the
damage was entirely in when integrated state reached the screen.

Root cause: the borrowed compositor opportunity delivers only **~54-56 accepted, irregular Hz
under transition load** (`511/545`, `493/543`). Pacing a ~90 Hz visualizer from a stream that is
sick exactly when it is needed guarantees late, uneven arrival.

#### Constraints now binding on any candidate

- `AdaptiveTimerStrategy` / `AdaptiveRenderStrategyManager` is disqualified as a presentation
  source in **any** scope, sole or while-active-only.
- **A pacing source that degrades under the load it is meant to relieve is disqualified.** A
  candidate must show its source stays healthy under that load, or use no external source.
- **State-to-paint latency is an acceptance metric, not a diagnostic.** A candidate that reduces
  `u/ss` while raising Bubble state-to-paint p95 is rejected regardless of delivery counters.
- Edge protection must be asserted against the real Bubble **positional-payload** edge in the v1
  golden, on the tick where it becomes visible, not the tick where the event is authored, and
  not merely that a bypass fired.
- Every logical input is integrated before any coalescing (R-54). No producer gate, paint
  acknowledgement, pending-until-paint admission, display-rate divisor, second clock, or requeue
  (R-27).
- A candidate narrower than the stated goal cannot close P2 without evidence justifying the
  narrowing.

#### Step 1 - measurement before design (no production change)

- [ ] From the preserved R-62 logs, plot Bubble state-to-paint distribution against `u/ss` per
      window and confirm the dose-response relationship holds within single transitions, not
      only across them.
- [ ] Establish whether the latency rise is dominated by *waiting for the next opportunity* or by
      *opportunity irregularity* (inter-arrival jitter). These imply different fixes and the
      distinction is currently unproven.
- [ ] Quantify, from `logs/screensaver_perf.log`, how much of the auxiliary request stream is
      **genuinely redundant**: a request issued while a previous request for the same surface is
      still queued and undispatched, so Qt would have painted the newer state anyway. This is the
      only reduction that costs zero latency by construction.
- [ ] Record the result in the phase report. If redundant traffic is negligible, say so and
      escalate the scope question rather than building anyway.

#### Step 2 - candidate design: dispatch-window coalescing (demand-driven, no external clock)

Leading candidate, subject to step 1. Coalesce a presentation request **only while a previously
issued request for the same surface is queued and not yet dispatched by Qt**. Once dispatched,
the next publication requests normally.

```text
publication -> integrate (always)
            -> is a prior request still queued and undispatched?
                 yes -> drop this request; the queued one will paint the newer state
                 no  -> request presentation immediately
```

Why this differs from both failures:

- **No external pacing source.** Nothing is borrowed; the mechanism is driven by Qt's own
  dispatch backlog, so it cannot inherit a sick clock's irregularity (R-62's root cause).
- **Cannot delay any state.** `paintGL()` reads current state, so an already-queued request
  paints the *latest* integrated state when it runs. A dropped duplicate would have painted the
  same or older state. State-to-paint latency can only stay equal or improve, which is the exact
  metric R-62 regressed.
- **Not paint-based admission.** It keys on *dispatch*, not paint completion. R-27 explicitly
  separated queued-dispatch coalescing from paint-pending state and preserved the former; the
  barred design keyed on paint.
- **Self-regulating.** Under congestion the dispatch backlog grows and more redundancy is removed
  exactly where the GUI is sick. When healthy, dispatch is immediate and `u/ss` stays ~1.0.
- Symmetric with the compositor, which already uses `_srpss_timer_update_dispatch_pending` for
  precisely this distinction.

Open risk to resolve in step 1: if Qt dispatches the overlay's updates promptly even under load,
the redundant fraction is small and this candidate is not worth the seam. That is a legitimate
outcome and must be reported rather than engineered around.

#### Step 3 - test bars, written before any wiring

- [ ] Bubble **visible positional-payload edge** from the v1 golden survives presentation, on the
      tick it becomes visible.
- [ ] State-to-paint p95 does not rise versus the 1:1 baseline at equal publication rate. This is
      the explicit R-62 regression bar.
- [ ] `u/ss` stays ~1.0 when dispatch is prompt; falls only when a request is genuinely
      superseded before dispatch.
- [ ] Logical state bit-identical with and without coalescing.
- [ ] Worker-thread caller and paused/idle lifecycle states modelled, not direct invocation.
- [ ] Teardown/recreation clean: no `None`-overlay attribute writes (the R-62 lifecycle defect).
- [ ] Both overpaint and under-delivery detectable; R-27 stutter signature absent.

#### Step 4 - runtime gate

- [ ] Confirm activation in `logs/screensaver_spotify_vis.log` before interpreting anything.
- [ ] Compare Bubble state-to-paint p95 and `u/ss` against the preserved R-62 windows and the
      approved-anchor windows.
- [ ] Installed Bubble and Spectrum visual review is the acceptance authority. If Bubble is worse
      in any relevant way, revert whole; do not retune in place.

#### Remaining original P2 requirements

- [ ] Logical/source cadence remains unchanged; presentation may consume the latest valid immutable render state only after logical integration.
- [ ] Preserve protected short-lived Bubble edges/events through bounded event identity/history or another approved equivalent; latest-state sampling alone is insufficient.
- [ ] Do **not** use paint completion, a pending-until-paint latch, elapsed producer timestamps, a display-FPS cap, source/event decimation or a second visualizer clock as admission.
- [ ] Re-run the mixed-refresh production scenario with `--perf` and `--gpu-timing`; compare against the accepted report rather than the temporary monkeypatch.

### P3 — attribute the remaining visualizer-family GUI handoff cost

- [ ] With the P2 presentation-request owner corrected, measure producer/state-build → overlay preparation/commit separately from repaint/paint.
- [ ] The no-visualizer control proves another visualizer-family GUI cost exists, but does **not** prove `SpotifyBarsGLOverlay.set_state()` alone owns it.
- [ ] If pure-data render-state preparation is a measured owner, move only thread-safe immutable preparation off GUI; QWidget/QColor/QPixmap/GL mutation stays on the GUI/context owner.
- [ ] Do not turn logical state into paint-driven state and do not create another visualizer scheduler.

### P4 — fix/name bad smell 2: residual queued-GUI-dispatch loss without visualizers

- [ ] After P2/P3, repeat a visualizer-disabled control with Media still enabled.
- [ ] Attribute the remaining 165 Hz dispatch-pending bursts to concrete GUI callbacks/owners.
- [ ] Close the owner by extraction/narrowing only when direct evidence names it; do not tune the adaptive timer, and do not hide the owner by changing how compositor update requests are coalesced. (This constrains the **compositor's** request ownership only. It is not a requirement that the visualizer keep one auxiliary `update()` per publication — P2 exists to remove exactly that.)
- [ ] Do not claim Phase 5 delivery closure while a no-visualizer run still loses roughly five percent of 165 Hz deadlines for an unnamed reason.

### P5 — harden authoritative monitor topology and physical sleep/wake recovery

This is **not deferred cleanup**. It follows the immediate P1→P4 performance sequence because the
installed non-diagnostic runtime now has a repeatable high-severity physical-monitor recovery failure:
when both displays are off while the screensaver runtime is active, waking them can leave one display
visible but frozen, the other blank, all Qt input dead, and recovery possible only after
Ctrl+Alt+Delete disturbs the Windows desktop/display state. Do not claim a root cause until evidence
names the blocking owner. Historical R-26 remains a useful warning that D0 can reappear before D1 and
that temporary participation is not authoritative topology; Phase 3 lifecycle evidence did not cover
this physical-off→wake platform scenario.

#### P5-A — one authoritative monitor-topology owner

- [ ] Make `DisplayManager` (or one equivalently explicit engine-level owner) the sole authority that decides whether a display event is a no-op, re-anchor, or full runtime replacement.
- [ ] Reduce `WM_DISPLAYCHANGE`, Qt `screenAdded`/`screenRemoved`, and related per-window callbacks to topology-invalidated notifications plus local bookkeeping. A `DisplayWidget` must not independently walk/reconfigure all displays while the manager can concurrently decide to retire the same runtime.
- [ ] Preserve per-display DPR/geometry/surface ownership, but issue mutations from one authoritative topology decision against one identified runtime generation.
- [ ] Add focused tests proving duplicate native+Qt event storms produce one authoritative decision/rebuild rather than overlapping re-anchor and teardown/recreate paths.

#### P5-B — true trailing-edge topology settling

- [ ] Replace the current first-event-style settle behaviour with a trailing-edge quiet-period debounce: every relevant topology event restarts the quiet timer so reconciliation occurs only after a real period of silence.
- [ ] Add a bounded maximum settle deadline so a pathological driver/event storm cannot postpone reconciliation forever. Reaching the bound must produce one explicit best-known snapshot/decision, not retries or nested event pumping.
- [ ] Freeze the accepted screen count/order/geometry/DPR identity into one topology snapshot/generation before any destructive replacement begins. Do not rebuild from a transient D0-only sample merely because D1 has not reappeared yet.
- [ ] Record low-rate lifecycle breadcrumbs for topology-event receipt, debounce restart, accepted snapshot, and decision so an overnight failure can be reconstructed without per-frame logging.

#### P5-C — transactional topology replacement

- [ ] Make monitor replacement an explicit transaction: settle topology → freeze snapshot → stop further old-runtime topology mutation → retire the old runtime exactly once → pass the existing destruction barrier → construct/register the complete replacement against the frozen snapshot → reveal displays through the existing staged startup/readiness path.
- [ ] Do not weaken Phase 3/R-49 strict GL teardown, restore hide/reuse, ignore failed deletion, extend destruction timeouts, or move GL teardown to a worker as a recovery shortcut.
- [ ] Add before/after breadcrumbs around the small set of potentially blocking native boundaries used by monitor recovery/rebuild (including compositor cleanup/context acquisition, surface/compositor creation, display show/reveal, and the staggered D0/D1 callbacks). Breadcrumbs are observational only; no retry loop or behavioural timeout is introduced.
- [ ] Preserve the existing all-displays-registered-before-staggered-show principle. The 100 ms-style reveal staggering may remain unless evidence proves it harmful; it is useful for avoiding simultaneous heavy GL startup.

#### P5-D — sticky visualizer display ownership; conservative fallback and nearly-free return-home

- [ ] Preserve the existing same-display visualizer geometry/aspect-ratio stabilization and correction work. Correcting a visualizer that spawned with bad geometry on its configured display is **not** permission to change which display owns it.
- [ ] Treat a configured visualizer monitor that still exists in the authoritative settled topology but is temporarily asleep, rebuilding, missing a ready `WidgetManager`, or otherwise non-participating as **temporarily unavailable, not absent**. Hold/park/hide/defer that visualizer on its configured ownership target rather than moving it to another display. **Do not start an absence timer for mere non-participation.**
- [ ] Retire the current ~1500 ms remote CUSTOM participation fallback as cross-display authority. Participation rechecks may still be used for same-display readiness/geometry work if independently required, but a fixed participation delay must never establish that the configured monitor disappeared.
- [ ] Begin cross-display fallback consideration only after P5-B has accepted an authoritative settled topology snapshot in which the configured monitor is genuinely absent. At that point record one absence candidate tied to the topology/runtime generation.
- [ ] Confirm sustained absence with **one intentionally coarse lifecycle-owned recheck at approximately 60 seconds** after the accepted absence candidate. It need not run at exactly 60.000 seconds and must not receive frame-level/raw-timer treatment. Reuse an existing owned one-shot/lifecycle scheduling seam; add **no polling loop, periodic timer, dedicated thread, worker wait, sleep, or repeated retry chain** merely to watch the monitor.
- [ ] Any newer authoritative topology generation invalidates the old absence candidate. If the configured monitor returns before the coarse recheck, normal topology reconciliation makes the candidate stale and ownership remains with the configured target; the stale delayed callback must become a no-op through generation/token ownership.
- [ ] If the single coarse recheck finds the configured monitor still absent from the current authoritative settled topology, one fallback ownership transfer to a participating display is permitted. This is a last-resort availability action, not normal wake recovery.
- [ ] Make return-home **event-driven and timer-free**: when normal topology notifications later settle to a snapshot containing the configured monitor, wait only for the existing display-runtime readiness boundary needed to safely host the visualizer, then retire the fallback owner and transfer ownership back **once** to the configured display. Do not add a reverse polling timer or periodic “is D1 back?” task.
- [ ] Preserve saved CUSTOM geometry/aspect authority across both fallback and return-home. A fallback display may need a temporary valid presentation geometry, but the configured display's saved layout remains the source of truth when ownership returns.
- [ ] Add tests for D0-before-D1 wake order, D1-before-D0 wake order, temporary zero/partial participation, long (>60 s) real absence, actual cable/display removal, return before the grace check, return after fallback, Settings/recreation during an armed absence candidate, and stale-generation callback rejection. Temporary wake churn must never move visualizer ownership; genuine sustained absence may; stable return restores configured ownership once.

#### P5-E — keep `grabWindow(0)` startup polish, remove it from recovery-critical reinit

- [ ] Preserve `screen.grabWindow(0)` on the ordinary stable desktop→screensaver cold-start path because its user-visible purpose is to avoid a desktop/wallpaper→black→first-photo flash while the first SRPSS frame is prepared.
- [ ] On monitor-topology replacement / physical wake recovery, do **not** synchronously capture the waking Windows desktop as a prerequisite to reconstructing a display. Prefer the already-retained SRPSS image/replay state as the recovery seed; if no safe retained seed exists, keep updates blocked until the first real SRPSS image is ready rather than making desktop capture recovery-critical.
- [ ] Keep normal startup visual appearance unchanged. Add separate tests for ordinary cold startup (no new black flash) and monitor recovery (no synchronous desktop-capture dependency).

#### P5-F — installed physical-off/wake and ownership-recovery gate

- [ ] Add deterministic unit/integration coverage for event coalescing, trailing-edge settling, bounded maximum settle, frozen topology snapshots, one replacement transaction, stale-generation rejection, sticky visualizer ownership, the single coarse ~60-second absence candidate, event-driven return-home, and recovery-specific desktop-capture bypass.
- [ ] Prove the fallback implementation introduces no periodic monitor polling, dedicated worker/thread, per-frame check or exact-deadline timing dependency. One owned delayed absence-confirmation callback may exist only while a genuine settled-topology absence candidate is armed.
- [ ] Run repeated installed **ordinary non-diagnostic** cycles where both displays are turned off before/during screensaver activation, remain off long enough for the runtime to continue normally, then wake together and in opposite sequential orders. Include long-idle/overnight-equivalent duration where practical.
- [ ] Include visualizer ownership cases where the configured display returns before the ~60-second grace check, remains genuinely absent beyond it so fallback occurs once, and later returns after fallback. Return-home must happen from normal topology/readiness events without polling and must restore the configured CUSTOM geometry once.
- [ ] Pass only when both displays recover/reveal, clocks continue advancing, Escape/context-menu/input remain responsive, visualizer ownership does not migrate on transient participation, genuine sustained absence can recover to one fallback owner, stable return restores the configured owner once, normal desktop→screensaver startup remains flash-free, and no Ctrl+Alt+Delete escape is required.
- [ ] If a freeze still occurs, use the last entered/not-returned native-boundary breadcrumb to narrow the next investigation. Do not compensate with sleeps, retries, forced paints, timeout extensions, relaxed GL ownership, or additional monitor-polling machinery.

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

For the delivery/performance thread, execution order remains **Immediate Priority Queue P1→P4** above.
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
- [ ] P2: implement the real presentation-opportunity owner without retaining the diagnostic monkeypatch.
- [ ] P3: split and measure logical render-state preparation / overlay commit cost from repaint and paint.
- [ ] Preserve Bubble edge/event visibility and all supported-mode logical goldens while presentation coalesces stale render snapshots.
- [ ] Do not begin Phase 8 one-surface-per-display work from this evidence; C was only modestly better than B.

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
