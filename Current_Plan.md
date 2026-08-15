# Current Plan

Last updated: 2026-08-15
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
- the ordinary-PERF control did **not** recover the remaining delivery regression.

### Active next gate

- [ ] Attribute **adaptive-render wakeup lateness**, **queued GUI dispatch waiting**, and **already-dispatched paint-pending waiting** as separate stages.
- [ ] Preserve existing request/paint ownership and transition labels while adding only passive timing needed for that split.
- [ ] Use the stage split to explain lost/delayed requests before changing coalescing, admission or scheduling.
- [ ] Correlate large stalls against native/context/swap/event ownership or long Python GUI callbacks only after the stage boundary is known.
- [ ] Change multi-display commit scheduling only if steady post-extraction evidence proves back-to-back prepared commits are a remaining owner.
- [ ] No repaint retry, scheduler gate, display-FPS cap or visualizer cadence compensation.

## P5.2A Remaining GUI Workload Extraction

Target contract: **Prepare → Commit → Persist**.

- [ ] Audit remaining provider/widget callbacks for filesystem/JSON/filter/sort/credential work only where source inspection proves it.
- [ ] Keep Gmail user-triggered backend-mode write, IMAP credential save/delete, OAuth local-token deletion/revoke and expired-token refresh as explicit candidates rather than reopening closed cold-construction work.
- [ ] Revisit worker width or a dedicated presentation timing service only if later evidence shows queue/execution contention. Current evidence does not justify widening pools or moving visualizer scheduling.

## P5.2B GPU / Presentation Attribution

- [ ] Record per-display refresh, logical publication rate, update-request rate and paint rate together.
- [ ] Treat the 60 Hz display receiving ~90–100 update/paint requests as a presentation-pressure question, not permission to lower authored logical cadence.
- [ ] Re-measure residual overlay/presentation cost after delivery attribution.
- [ ] Feed a future Phase 7 prototype only after an edge-preserving immutable render-state contract proves Bubble's protected discrete response cannot disappear.
- [ ] Phase 7 presentation coalescing remains conditional, not inevitable.
- [ ] Do not begin Phase 8 one-surface-per-display work until Phase 7 and GPU/context evidence justify the lifecycle risk.

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
