# Current Plan

Last updated: 2026-08-16
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
- `Current_Plan.md` owns the active evidence pointer; do not freeze a dated current-run path into `Index.md` or roadmap navigation.

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

# Phase 5 — Active Work

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

### Closed evidence

- retained-current → next-old texture reuse is repaired and validated;
- steady terminal presentation reuses the retained texture instead of the previous expensive full-pixmap QPainter path;
- redundant ordinary RGB32/ARGB32 conversion/source-buffer copies are removed;
- Bubble worker/overlay GPU and ordinary transition draw durations are too small to explain the largest stalls;
- heavy owner-context GL queries are isolated behind sampled `--gpu-timing`;
- ordinary `--perf` performs no GL query-driver calls;
- the ordinary-PERF control did **not** recover the remaining delivery regression;
- passive delivery-stage attribution now separates deadline wake lateness, queued GUI dispatch and already-dispatched paint-pending wait. In the failing mixed-refresh runs the render timer continues waking near target; rejected deadlines are downstream pending-state losses rather than a timer cadence collapse;
- the 2026-08-16 same-process dual-display Spectrum A/B/C run proves the auxiliary visualizer presentation-request stream is a material shared-GUI amplifier. On the 165 Hz display, complete BlockSpin windows moved from median **143.4 FPS / 87.12% acceptance** in `A_NORMAL` to **150.2 / 91.39%** when only `SpotifyBarsGLOverlay.update()` requests were suppressed. Restoring normal presentation in the same process dropped the next complete window back to **141.2 / 85.85%**. The 60 Hz display moved from median **57.9 / 96.55%** to **58.9 / 98.37%** under the same suppression;
- hiding the still-live auxiliary GL widget after suppressing requests produced only a smaller additional gain in that run: the 165 Hz display median was **151.6 FPS / 92.11% acceptance**. Therefore visible-surface participation is secondary to the request stream in this evidence; do not jump directly to one-surface-per-display surgery;
- while normal Spectrum presentation was active, sampled visualizer shader GPU time was only about **0.02 ms p50 / 0.025 ms p95**. The proven cost is Qt/GUI presentation pressure, not expensive visualizer shader execution;
- a separate no-visualizer-from-start control retained the Media widget/GSMTC controller but created no visualizer/overlay stream. It reached median **156.5 FPS / 95.11% acceptance** on the 165 Hz display and **59.35 / 99.09%** on the 60 Hz display. Relative to the hidden-live C state, queued-dispatch p95 fell from about **3.06 ms → 1.89 ms** and paint-pending p95 from about **2.16 ms → 0.52 ms** on the 165 Hz display;
- the no-visualizer control is a separate process and removes the whole visualizer pipeline, so its additional improvement is evidence for **another visualizer-family GUI owner**, not proof that `SpotifyBarsGLOverlay.set_state()` alone owns it. The live hidden/suppressed run still executed roughly **88–90 `set_state()` handoffs/sec**, so that handoff/state-preparation path is the next bounded attribution target;
- even with visualizers disabled, the 165 Hz display remains at roughly **155–159 FPS**, not 165. Residual rejected deadlines are now mostly queued-GUI-dispatch bursts (median about **51 dispatch-pending skips** versus **17 paint-pending skips** per complete no-visualizer window), so a non-visualizer GUI-dispatch owner remains after the visualizer work is corrected.

### Active next gate

- [x] Attribute **adaptive-render wakeup lateness**, **queued GUI dispatch waiting**, and **already-dispatched paint-pending waiting** as separate stages.
- [x] Preserve existing request/paint ownership and transition labels while adding only passive timing needed for that split.
- [x] Use the stage split to explain the major lost-request mechanism: target-rate wakeups continue, while pending GUI/paint delivery rejects later deadlines.
- [ ] **Promoted fixable owner:** replace the one-visualizer-state-publication → one auxiliary `QOpenGLWidget.update()` contract with an owned presentation-opportunity contract. Logical source/state cadence must remain unchanged; presentation may consume the latest immutable render state without scheduling one Qt repaint per publication.
- [ ] Before implementing that production change, add/retain fidelity bars that prove Bubble discrete event identity/edges, one-in-flight simulation semantics, Spectrum state evolution and all supported-mode logical snapshots remain unchanged when presentation consumes fewer opportunities than logical publication produces.
- [ ] **Next attribution inside the visualizer family:** measure the GUI cost of the high-cadence logical-to-overlay handoff separately from repaint/paint. Split producer/state-build work from `SpotifyBarsGLOverlay.set_state()` preparation/commit and quantify it in the live mixed-refresh run. The no-visualizer control justifies this measurement but does not yet justify moving all `set_state()` logic off-thread.
- [ ] If the handoff is a proven GUI owner, move only immutable/preparable render-state work off the GUI owner and leave QWidget/GL mutation on the GUI/context owner. Do not create a second visualizer clock and do not make logical state paint-driven.
- [ ] After the visualizer presentation/handoff correction, rerun the no-visualizer-equivalent control and attribute the residual 165 Hz queued-dispatch bursts against concrete GUI callbacks/owners. Do not let the visualizer fix claim closure while the 165 Hz display still loses ~5% of deadlines with visualizers absent.
- [ ] Change multi-display commit scheduling only if steady post-extraction evidence proves back-to-back prepared commits are a remaining owner.
- [ ] No repaint retry, scheduler gate, display-FPS cap or visualizer cadence compensation.

## P5.2A Remaining GUI Workload Extraction

Target contract: **Prepare → Commit → Persist**.

- [ ] Audit remaining provider/widget callbacks for filesystem/JSON/filter/sort/credential work only where source inspection proves it.
- [ ] Keep Gmail user-triggered backend-mode write, IMAP credential save/delete, OAuth local-token deletion/revoke and expired-token refresh as explicit candidates rather than reopening closed cold-construction work.
- [ ] Revisit worker width or a dedicated presentation timing service only if later evidence shows queue/execution contention. Current evidence does not justify widening pools or moving visualizer scheduling.

## P5.2B GPU / Presentation Attribution

- [x] Record per-display refresh, logical publication rate, update-request rate and paint rate together.
- [x] Prove that the 60 Hz visualizer surface receiving roughly 85–95 logical publications/update requests per second creates shared-GUI presentation pressure without requiring a Bubble-specific failure.
- [x] Prove by same-process A/B/A that suppressing only auxiliary visualizer `update()` requests materially improves compositor acceptance/FPS on both displays while logical visualizer state continues publishing.
- [x] Prove that hiding the still-live auxiliary GL widget adds only a smaller benefit than suppressing its repaint-request stream in the current Spectrum run; visible surface existence is not the primary owner established by this experiment.
- [x] Re-measure overlay GPU execution with `--gpu-timing`: Spectrum overlay shader cost remains tiny (~0.02 ms p50 / ~0.025 ms p95) and does not explain the GUI-delivery loss.
- [ ] Instrument and attribute high-cadence logical-to-overlay GUI handoff/state preparation while presentation is suppressed/hidden. Compare against the no-visualizer control without conflating a separate-process control with same-process proof.
- [ ] Design the production presentation-opportunity contract around an immutable/latest render snapshot plus edge/event preservation. It may coalesce **presentation states**, never source/event sampling or authored logical cadence.
- [ ] Add a mixed-refresh regression bar proving one display's visualizer cannot starve another display's compositor dispatch/paint delivery.
- [ ] Remove the temporary `--viz-present-abc`/Shift+/ monkeypatch experiment after its evidence is captured and before treating a production fix as complete.
- [ ] Do not begin Phase 8 one-surface-per-display work: current A/B/C evidence does not justify that lifecycle risk because C was only modestly better than B.

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

- [ ] Run focused owning-subsystem tests after every change; do not default to monolithic `pytest -q`.
- [ ] Use `tests/run_chunked.py` only when a broader release gate is useful.
- [ ] Preserve visualizer temporal goldens/negative controls for visualizer-adjacent cleanup.
- [ ] Official performance comparisons use ordinary `main.py`; name `--gpu-timing` observer differences explicitly.
- [ ] Long soak/lifecycle captures preserve enough main + relevant sidecar rotations to cover the claimed interval.

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
