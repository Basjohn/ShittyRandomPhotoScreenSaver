# Current Plan

Last updated: 2026-08-11  
Branch: `main`  
Active phase: Phase 5 — workload, delivery, GPU attribution, and resource efficiency

This file contains **unfinished active work only**. Detailed architecture belongs in
`Docs/audits/SRPSS_Architecture_Roadmap/`; completed measurements belong in phase or
benchmark reports; solved failures belong in `Docs/Historical_Bugs/`.

Settings/Edit lifecycle ownership, the Diagnostic-build ownership investigation, and
clock-shadow work are closed. They remain regression contracts and historical evidence,
not active Phase 5 tasks. Do not rebuild Diagnostic or reopen those incidents unless a
new frozen-only failure provides direct evidence that requires it.

## Current Authority And Evidence

- [x] Work directly on current `main`; historical baseline/candidate commits are negative controls or forensic references only.
- [x] Preserve `ff93461685476bd0657aa88312fc2e35e9037880` as the current user-approved Bubble/Spectrum behavioural reference until a later exact commit receives explicit visual approval.
- [x] Preserve the solved Settings/Edit compiled-bound-method ownership lesson under R-59; lifetime-critical Qt→plain-Python callbacks use explicit stable weak ownership and exact disconnect callables.
- [x] Preserve `logs/evidence_chest/08_09_ca830d7_14_59/` as the current mixed-load/root-cause evidence checkpoint. Its source-level conclusions are already documented; reread raw logs only for a new hypothesis or a direct before/after comparison.
- [x] Treat `main.py` as the sole performance, soak, hostile-load, golden, and evidence-capture authority. Diagnostic is a frozen-runtime attribution product, not a performance target; Media Center receives bounded shared route/build smoke coverage only.
- [ ] Promote a later visualizer behavioural reference only after stronger temporal evidence and separate installed approval for affected modes.

## Checkpoint Policy

A checkpoint is a rollback anchor, **not a pause for permission**.

- Make a clean, narrow commit after an independently risky architectural slice.
- Run the owning focused tests and the smallest useful runtime/evidence gate.
- If the gate passes, keep the checkpoint and continue to the next planned slice without stopping merely because a commit was created.
- Stop only when evidence fails, the causal model is contradicted, repository state is unexpectedly dirty/conflicted, or an affected visual change genuinely requires operator judgement.
- Never carry a failed experiment forward through compensating flags, fallbacks, retries, or hidden alternate paths.

## Non-Negotiable Guardrails

- Keep `versioning.py` user-owned unless a version change is explicitly requested.
- Preserve Bubble's authored-step cadence, dt, source/event sampling, one-in-flight semantics, simulation behaviour, and ordinary general COMPUTE executor ownership during Phase 5.
- Preserve Spectrum's authoritative source/state evolution on the existing visualizer tick. No second clock, paint-local state mutation, source decimation, or cadence cap.
- Distinguish **logical/state-evolution cadence** from **presentation opportunity**. A future presentation layer may skip stale immutable render snapshots after logical integration; it may never skip authored logical work or become a new simulation clock.
- Attack work starving the GUI owner before moving Bubble/Spectrum timing. The mixed-load evidence shows late delivery with cheap paint and ~1–2 ms Bubble worker samples.
- Do not create one catch-all “third thread.” Blocking I/O, ordered persistence, logging, finite compute, and GUI/GL commits have different ownership and ordering requirements.
- Qt/QWidget/QPixmap/GL mutation stays on the correct GUI/context owner. Move only preparation, I/O, serialization, and thread-safe compute away from it.
- Strict GL teardown remains fail-closed and byte-accounted. Do not weaken lifecycle/resource gates to improve a graph.
- Keep the production CPU image-cache cap at 256 MiB until measured hit/fallback evidence justifies a deliberate change.
- Do not add sleeps, nested event pumping, production `gc.collect()`, working-set trimming, process recycling, timeout extensions, ignored owners, hidden fallback runtime paths, or cadence hacks.

# Phase 5 — Active Work

## P5.0 Media Provider Runtime Validation

The provider/failover plumbing reaches the shared GSMTC controller. The unresolved
Browser path is below settings/failover policy. Current controller selection can discard
a matching current session when `get_sessions()` is empty/nonmatching.

- [x] Preserve exact registry-owned provider identities and one bounded GSMTC query/failover pass.
- [ ] Make `WindowsGlobalMediaController._select_media_session_for_providers()` test `get_current_session()` for the requested provider before requiring a match in `get_sessions()`.
- [ ] Add bounded diagnostics for current-session source id separately from enumerated session ids.
- [ ] Add regressions for `get_sessions()==[]` with matching current Firefox/Chromium source ids.
- [ ] Validate Spotify Browser in ordinary `main.py` against Firefox first and at least one Chromium browser. If both current and enumerated sessions are absent, classify Windows/browser exposure separately from SRPSS selection.
- [ ] Repair the real `MediaWidget` missing-session hide contract: production currently lacks `_complete_hide_sequence()` while the test double supplies it. Make the test shape match production rather than allowing a fake to invent lifecycle API.
- [ ] Confirm browser providers expose no application-volume control and desktop providers restore the preserved volume preference.

## P5.1 Visualizer Fidelity And Stronger Goldens

- [x] Keep `ff93461685476bd0657aa88312fc2e35e9037880` as the current Bubble/Spectrum behavioural authority.
- [x] Preserve the rejected persistent-lane `666624d4` and paint-local Spectrum `ebfec397` shapes as negative controls.
- [ ] Capture approved numerical source features/playback offsets and source-to-state/source-to-visible timing for Bubble and Spectrum.
- [ ] Add installed Spectrum state-publication → overlay-state → paint receipt with bounded distributions and display refresh identity.
- [ ] Exercise attack, drop, rapid alternation, pause/resume, transition overlap, mode switches, and deliberate GUI stalls without changing authored cadence.
- [ ] Visually validate Sine Waves, Oscilloscope, and Dev Curve against the current shared source.
- [ ] Complete scheduler-ownership negative controls before any Phase 7 presentation decoupling.

### Protected Phase 5 visualizer work

Phase 5 may remove repeated immutable allocation/configuration work only when the
existing temporal boundary is unchanged. In particular:

- Bubble configuration that changes only with settings/preset changes may be cached instead of rebuilt/copied on every authored dispatch; live energy/transient/event snapshots remain captured at the exact existing step boundary.
- Spectrum may cache immutable lookups only; source consumption, smoothing state, logical publication and existing timer remain unchanged.
- DevCurve is measured first. Its stateful pure-Python field solve is not moved merely because another thread exists.

## P5.2 UI Delivery And Transition Root Causes

Current mixed-load evidence shows the dominant tail is **GUI availability**, not paint
cost. Across 238 owner-labelled gaps, gap median/max was `44.75/139.54 ms`, request-age
median/max `35.29/138.83 ms`, while paint median/max was only `0.79/8.92 ms`.

The image-install probe found a concrete steady-state defect:

```text
QImage -> QPixmap                  median 4.95 ms   p95 9.49 ms   max 11.67 ms
set_processed_image               median 35.84 ms  p95 117.43 ms max 128.42 ms
generic_pair_warm                 median 26.62 ms  p95 64.45 ms  max 80.41 ms
```

The source-level identity defect is repaired. `ImagePresenter` previously retained an
independent `1.0` DPR while the display-owned DPR was `1.5`; its pre-terminal and
post-terminal writes changed the destination pixmap cache identity, including the exact
`retained_key + 2 == next_old_key` pattern in the canonical run. The presenter now
consumes the display-owned DPR and skips no-op mutation. Focused automation proves the
retained destination is the next old cache hit and only the following destination
uploads under unchanged context/generation/size/transform identity.

The current live typical-load run at
`logs/evidence_chest/08_11_51ff1e03_03_14_03_21_typical/` closes the runtime identity
bar: all `20/20` steady transitions report `old_key == retained_key`, an old cache hit,
one allocation and one upload. All 26 terminal samples retain exactly one texture and
one idle PBO. Steady `generic_pair_warm` fell from the historical reference median/p95
`23.48/39.80 ms` to `13.64/20.98 ms`; setter median/p95 fell from `33.40/52.59 ms` to
`25.66/34.72 ms`. Request-age and visualizer-tick tails did not improve, so the broad
GUI-availability problem remains active and is not a texture-identity problem.

- [x] Validate retained-current → next-old reuse in a live repeated-transition run without increasing terminal texture/PBO ownership.
- [ ] Re-run the same typical scenario after queued logging and ordered settings persistence. Require lower request-age/visualizer-tick tails, clean bounded logging/settings-writer terminal metrics, and preservation of the closed texture/resource bars.
- [ ] Change multi-display commit scheduling only if post-extraction steady evidence shows back-to-back prepared commits are a remaining owner. The current run's three large stagger delays occurred only during cold runtime starts and do not justify a scheduling change.
- [ ] Keep transition names and one terminal GL metric bracket per real transition; no repaint retry or scheduler/cadence compensation.

## P5.2A UI-Thread Workload Extraction

Target contract: **Prepare → Commit → Persist**.

### Priority 1 — service/widget preparation

- [ ] Weather: move startup cache reads and post-fetch persistence to IO ownership; keep Qt text/layout/QPixmap commits on GUI.
- [ ] Gmail: move startup cache read/deserialization off GUI and move stable content-cache regeneration out of `paintEvent()`; paint consumes prepared/cache state.
- [ ] Reddit/Gmail: cold static rendering must not be discovered inside `paintEvent()`. Prefer invalidation-time preparation before worker-rendered text unless measurement justifies the extra complexity.
- [ ] Audit other widget/provider callbacks for JSON/filesystem/filter/sort work and apply the same owner rule only where source inspection proves it.

### Priority 2 — worker topology after extraction

- [ ] Measure general COMPUTE occupancy/queue age/native GIL release after unrelated I/O/persistence/logging ownership has been removed from GUI contention.
- [ ] Audit long-lived presentation/deadline waiters that consume finite COMPUTE workers while mostly sleeping; move waiting ownership only when measured contention exists.
- [ ] Benchmark worker width instead of assuming `cpu_count - 1` remains ideal after workload classes are separated.

## P5.2B GPU Work Attribution And Efficiency

The `08_09_ca830d7_14_59` active-display samples make GPU work an active problem, not
a distant cleanup item. Process GPU-engine busy with tracked GL active measured:

```text
median  10.8%
p90     24.0%
p95     27.8%
max     32.9%
```

On the visualizer display, runtime geometry identifies screen 1 as 60 Hz, yet captured
10-second overlay windows reach roughly `1000 set_state / 1000 update requests / 1000
paintGL` calls. Current visualizer timing starts from a 16 ms UI timer and can target
roughly 90–100 Hz. This is a **presentation-rate mismatch to explain**, not permission
to cap Bubble/Spectrum logical cadence to display refresh.

- [ ] Promote truthful per-transition GPU timing to active work: route paint timing through the shared compositor seam and use non-blocking GL timer queries with delayed result collection for every exercised transition family where supported.
- [ ] Never use `glFinish()` in ordinary profiling. It changes the workload and invalidates the measurement.
- [ ] Log support/sample counts so a zero GPU duration means measured zero only when samples exist.
- [ ] Split GPU attribution among image texture upload/warm, transition shader/render work, visualizer overlay/context work, overdraw/composition, and driver/context overhead.
- [ ] Record per-display refresh, logical visualizer state publication rate, update-request rate and paint rate together. Do not infer waste solely from one counter.
- [x] Measure GPU busy after texture identity reuse: the typical run records process GPU busy median/max `9.1/32.7%` while the steady texture path uploads new only. Remaining GPU work still needs owner attribution.
- [ ] Feed the result into Phase 7: if logical integration remains correct while physical presentation is above useful display opportunities, decouple presentation through latest immutable render state rather than reducing simulation/source cadence.
- [ ] Do not begin Phase 8 one-surface compositor work until Phase 7 proves missed paints cannot alter logical state and GPU/context evidence shows the merge is worth its lifecycle risk.

## P5.2C Compatibility, Fallback, And Debris Leverage

Compatibility code that preserves a real persisted-data or external-interface contract
may remain. A runtime shim that only preserves a rejected architecture shape is debt.
Delete one proven authority at a time; do not combine cleanup with behaviour changes.

- [ ] **Bubble façade first:** remove `widgets/spotify_visualizer/bubble_compute_lane.py` as a sterile direct-path cleanup. It is explicitly documented as a temporary compatibility adapter over the ordinary general COMPUTE executor; `tick_pipeline.py` already contains the direct submission path. Preserve exact authored-step cadence, dt, live snapshots, one-in-flight behaviour, task category, callback/publication ordering and generation identity. Rename/preserve useful metrics without “persistent lane” fiction.
- [ ] After the façade is gone, audit `core/threading/compute_lanes.py` and ThreadManager lane APIs. Runtime evidence repeatedly reports `registered_lanes=0 worker_threads=0`; remove the subsystem only after production, dynamic-import, test and frozen-build call-graph proof.
- [ ] Audit/remove `rendering/render_strategy.py` if it remains production-dead; it retains an obsolete scheduling/update design.
- [ ] Audit/remove `widgets/dimming_overlay.py` if it remains test-only after compositor replacement.
- [ ] Audit/remove `sources/rss_source.py` if it remains a compatibility façade with no production caller; migrate tests/docs to the real owner first.
- [ ] Remove `transitions/overlay_manager.py::_raise_halo_topmost` if it remains a called compatibility no-op.
- [ ] Keep each debris deletion in its own reversible checkpoint with focused tests; passing checkpoints continue automatically.

## P5.3 Absolute Memory, Commit, VRAM, And Cache Efficiency

- [ ] Capture cold, warm, active-transition, steady-image, quiescent-runtime and post-churn snapshots under one controlled authored scenario.
- [ ] Reconcile whole/main/child RSS, private commit, USS, worker mappings, thread stacks, Qt/native heaps, driver mappings and tracked application bytes.
- [ ] Separate one-time high-water retention from live ownership and true repeated-cycle growth.
- [ ] Audit exact-transform per-display image duplication without collapsing different DPR/transform outputs.
- [ ] Audit raw/scaled/display co-retention, unused prefetch results, future-byte pressure and eviction churn using actual cache hit/miss/worker-fallback cost.
- [ ] Treat GPU **memory** and GPU **busy** as separate metrics; neither substitutes for the other.
- [ ] If tracked ownership reaches expected zero/plateau while process memory still rises, open an evidence-led retention incident before changing cache budgets or lifecycle policy.

## P5.4 Logging And Evidence Quality

P5 changes the logging execution architecture; late Phase 7 performs the full taxonomy
refinement before Phase 8.

- [x] Preserve parser rotation/time-range semantics, exact texture-key image-install evidence, startup identity, bounded action telemetry and all warning/error visibility.
- [x] Fix the known `[GL CACHE]` routing defect: routine INFO now follows the cache sidecar and WARNING+ remains visible in main and cache.
- [x] Main log contract: readable high-level runtime narrative plus every `WARNING`/`ERROR`/`CRITICAL`; routine enabled-family INFO/DEBUG belongs in its sidecar and should not duplicate into main.
- [ ] Late Phase 7 logging refinement: inventory high-volume families, move routine records to existing sidecars, add a new sidecar only for a genuinely distinct domain, replace token-guess routing with structured family metadata, and preserve cross-sidecar ordering/correlation fields.
- [ ] Keep diagnostic/perf instrumentation passive and bounded; never improve a performance run by simply deleting the evidence required to understand it.

## P5.5 Verification

- [ ] Run focused owning-subsystem tests after every change; do not default to monolithic `pytest -q`.
- [ ] For risky changes, checkpoint after the focused gate and continue if it passes.
- [ ] Use `tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log` only when a broader release gate is useful; classify existing unrelated failures rather than weakening current contracts.
- [ ] Repeat the same canonical mixed-load scenario after the texture reuse and broad UI-thread extractions, with deliberate host-load timestamps and identical visualizer/image/cache conditions.
- [ ] Require unchanged visualizer temporal goldens and negative controls for any visualizer-adjacent cleanup, including Bubble façade removal.

## Phase 5 Exit Gate

- [ ] Bubble and Spectrum are separately approved equal or better than `ff934616`; other supported modes retain current behaviour.
- [x] The proven texture old/current identity miss is corrected and steady transitions reuse old + upload only new under unchanged identity.
- [ ] Routine logging/persistence and proven service/cache preparation no longer perform avoidable synchronous GUI I/O/data work.
- [ ] Host-pressure request-age/tick tails materially improve or remaining owners are named without cadence hacks.
- [ ] GPU busy is attributed by owner enough to distinguish transition/upload/visualizer/presentation cost and guide Phase 7/8 rationally.
- [ ] Absolute RAM/private-commit/VRAM excess is materially reduced or explicitly attributed in an approved decision record.
- [ ] Compatibility/fallback debris promoted into Phase 5 is removed or explicitly retained with a real current contract.
- [ ] Stronger visualizer temporal/negative-control evidence is complete enough to begin Phase 7 safely.

# Accepted And Rejected Methods

## Keep Using

- Current `main` as implementation authority; historical commits only as precise negative controls or forensic comparison.
- Ordinary general COMPUTE executor semantics for Bubble with generation/activation rejection.
- One authoritative visualizer **state-evolution** clock per current design; presentation consumes current immutable state and may later coalesce only after logical integration.
- Prepare → Commit → Persist ownership with explicit ordered persistence and narrow GUI/GL commits.
- Stable weak forwarding callbacks at Qt→plain-Python lifetime seams where ownership requires them.
- Exact current texture retention plus bounded PBO reuse; identity must make retained current actually reusable as next old.
- Passive request-age, task, resource, GPU and source-age telemetry with exact timestamps and named owners.
- Narrow, reversible commits as checkpoint/rollback anchors without artificial approval stops.

## Blacklisted

- Persistent shared-analysis/Bubble lanes and `666624d4` scheduling semantics.
- Bubble terminal batching, source/publication decimation, cadence caps or display-refresh-driven authored work.
- Paint-local Spectrum smoothing, `paintGL()` state mutation, self-requested visualizer loops or any second logical clock.
- A catch-all background thread or unbounded queue for unrelated work.
- Worker mutation of QWidget/QPixmap/GL/context-owned state.
- `glFinish()` as routine profiler synchronization.
- Repaint retries, scheduler gates or visual smoothing used to hide GUI starvation.
- Hidden runtime fallback architecture, compatibility shells with no current contract, or parallel authorities kept “just in case.”
- Working-set trimming, process recycling, forced GC, timeout extension, ignored owners, fake zero accounting, or fidelity cuts.
- Reopening solved Settings/Edit/Diagnostic/clock work without new direct evidence.

# Later Phases

- **Phase 6:** explicit GPU resource store only if current owner/resource evidence proves a shared store is beneficial and simpler than per-compositor ownership.
- **Phase 7:** immutable visualizer state/presentation boundary while preserving exact logical/source clocks. Also complete the full logging taxonomy/routing refinement late in Phase 7 so Phase 8 evidence is readable.
- **Phase 8:** one compositor surface per display only after Phase 7 proves missed paints never alter logical state and measured GPU/context evidence justifies the merge.
- **Phase 9:** local transition completion and deterministic temporary-resource release simplification where any remaining scaffolding exists.
- **Phase 10:** remaining low-risk temporary/deprecated scaffolding removal not already promoted for Phase 5 leverage.
- **Phase 11:** full normal/soak/all-mode/hostile-load/topology validation.
- **Phase 12:** release preparation and final documentation freeze.
