# Current Plan

Last updated: 2026-08-02

Active unfinished work only. Stable architecture belongs in `Spec.md`; durable rules belong in `Docs/Guardrails.md` and focused guardrails; dated failures belong in historical documentation; completed narratives leave this file once accepted and archived.

## Recovery And Approval Boundary

```text
branch: main
recovery baseline: 00edb57a3076b845cb8ee4b6cb7f36ea83411f0c
pre-persistent-lane behaviour: 6f188adadabb77b1a9d47a0fe1685c86ad39fb77
failed persistent-lane checkpoint: 666624d421b08f978c5f610571a078570150a1e7
restored executor behaviour: 4bde89e8e39177dc4dd7b5e64b9ac99256ab9486
rejected Spectrum smoothing: ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9
current approved behaviour: ff93461685476bd0657aa88312fc2e35e9037880
failed smoothing evidence supplied: logsspectsmoo.zip
lifecycle evidence: logs/evidence_chest/08_01_666624d4_22_05/
owning report: Docs/phase_reports/P05_CPU_TASK_REDUCTION.md
focused presentation guardrail: Docs/Guardrails/Visualizer_Presentation.md
smoothing incident: Docs/Historical_Bugs/R-55_Spectrum_Presentation_Smoothing.md
```

`ff934616` is code-equivalent to `4bde89e` and preserves the accepted restored Bubble/Spectrum behaviour while recording the rejected smoothing experiment and exact revert in history.

## Status Legend

- `[ ]` not started
- `[-]` active
- `[x]` complete with accepted evidence
- `[!]` failed or blocking
- `[~]` explicitly deferred

## Non-Negotiable Gates

- User-observed visualizer feel outranks task counts, mean timings, paint counts, and green logical tests.
- Bubble and Spectrum are independently protected.
- No visualizer optimization begins before the stronger approved goldens in this plan exist.
- No future optimization silently changes cadence, scheduler, source sampling, attack, decay, elasticity, or presentation authority.
- No second visualizer cadence, self-requested Spectrum repaint loop, paint-derived clock, or `paintGL()` mutation authority.
- Settings/Edit destruction remains fail-closed; no timeout extension, ignored owner, retry sleep, nested event pumping, forced garbage collection, or fake zero count.
- Full runtime teardown may not begin from inside a retiring widget/session owner call stack. Persist and retire the local graph first; engine-owned recreation admission runs on a later GUI turn.
- Runtime generation, exact `DisplayManager` identity, engine generation, activation identity, first-frame authority, and owner-context GL deletion remain mandatory.
- Do not rename or move existing files.
- Do not regenerate expected outputs merely to make a change pass.

# Phase 5 — CPU, Task, Delivery, And Recreation Recovery

## Current State

### Visualizer recovery

- [x] Shared audio analysis restored from persistent lane to the approved general COMPUTE executor semantics.
- [x] Bubble simulation restored from persistent lane scheduling to the approved general COMPUTE executor semantics.
- [x] Production visualizer paths no longer register persistent audio-analysis or Bubble compute lanes.
- [x] Operator confirmed Spectrum became significantly better after restoration.
- [x] Operator now describes Bubble and Spectrum as well behaving at `ff934616`.
- [x] Spectrum paint-local decay smoothing was attempted, made Spectrum significantly less smooth, and was exactly reverted.
- [x] Failed smoothing logs identified a second presentation cadence: roughly 977–1000 authoritative state updates versus 1417–1544 paints per 10 seconds.
- [!] Stronger goldens are still missing. Accepted behaviour exists, but automated hazard lights remain incomplete.

### Lifecycle investigation result

- [x] The old Settings timeout had zero surviving Python owners and only the rejected idle `visualizer.audio_analysis` persistent lane. That known blocker has been removed from production. Confidence that the identified blocker is gone: **98%**. Confidence that Settings now passes installed recreation: **below 90% until rerun**.
- [x] The old CUSTOM/Edit timeout reached zero watched QObjects, zero tracked resources, zero global subscriptions, and retained exactly two `CustomLayoutManager` Python owners—one per display—plus the same rejected audio lane.
- [x] Source tracing proves the CUSTOM save path synchronously enters full engine teardown from the retiring edit graph: `EditShell/key event → CustomLayoutManager.save_session() → DisplayWidget signal → DisplayManager relay → engine.stop()`.
- [x] During that direct call, `commit_session_without_reload()` still owns `self`, a copied `active_managers` list, grouped manager/state collections, loop locals, and its `finally` block. Every `EditShellWidget` also stores two lambdas closing over its manager and connects manager-bound slots without an explicit release contract.
- [!] Cause boundary confidence: **95%** that CUSTOM recreation is admitted too early from inside the retiring manager/session graph and therefore relies on incidental Python/PySide release timing.
- [!] Exact final strong-reference edge confidence: **85%**. The most likely persistent edge is the deleted shell wrapper retaining manager-closing resolver/applier lambdas and/or bound signal callback records; the active save/key-filter frames unquestionably contribute during admission but should unwind quickly. A live referrer capture was not present in the evidence.
- [x] Existing tests do not exercise this failure. Their reload stub only increments a counter, so no synchronous engine teardown occurs, and they do not assert manager/shell weakref death before replacement admission.
- [ ] Replacement initialization currently has no demonstrated separate cause defect: `_initialize_display()` rejects construction while a barrier is pending, display creation is generation/manager guarded, and reveal remains authoritative-first-frame gated. Treat initialization as a validation target, not a redesign target, unless fresh evidence contradicts this.
- [ ] Equivalent-state RAM/private-commit/VRAM growth has no cause above 90% until clean repeated Settings/Edit recreation exists. Do not change caches, allocators, budgets, or process lifetime to guess at it.

## Required Work Order

1. Freeze `ff934616` as the current user-approved visualizer behavioural baseline.
2. Capture the mandatory stronger Bubble/Spectrum approval manifest and temporal hazard lights described below before visualizer optimization or lane-scaffolding deletion.
3. Run one fresh Settings recreation on current main. If it passes, record that the removed persistent lane was the complete observed Settings blocker; if it fails, investigate the new owner list without changing initialization architecture speculatively.
4. Repair the proven CUSTOM/Edit admission and callback-retention boundary described in P5.4.
5. Run the focused two-display weakref/barrier tests and one installed Edit Save-and-Continue cycle before any memory conclusions.
6. Remove unused visualizer lane facades, diagnostics, tests, and generic scheduler integration only after repository search proves no valid production consumer remains.
7. Run the full alternating Settings/Edit lifecycle and memory plateau matrix.
8. Complete delivery-tail, unchanged-media, cache-representation, and logging work.
9. Close Phase 5 only after installed normal and Media Center evidence passes.

# P5.0 — Visualizer Fidelity And Mandatory Goldens

## Accepted baseline

The approved comparison point is:

```text
ff93461685476bd0657aa88312fc2e35e9037880
```

No later build replaces it as the visualizer golden authority until the user explicitly approves the exact new commit after installed testing.

## Mandatory stronger golden package

The existing Phase 2 JSON replay goldens remain valid logical-equation protection. They are insufficient for scheduling, publication timing, first-visible response, or perceived continuity.

Create one additional versioned golden package from `ff934616` while Bubble and Spectrum are explicitly user-confirmed as correct.

### A. Immutable approval manifest

Record:

- exact commit SHA;
- date and explicit user approval statement;
- Windows version;
- Python and PySide versions;
- GPU and driver;
- display count, resolution, refresh rate, DPR, and selected display route;
- audio capture device and sample configuration;
- normal or Media Center entry point;
- exact Bubble and Spectrum presets/settings;
- bar count, timer target, playing/paused state, and transition state;
- source fixture identifiers and playback offsets.

Do not store copyrighted commercial audio in the repository. Prefer deterministic synthetic PCM plus captured numerical post-capture/source-feature sequences from approved real-song runs.

### B. Exact logical golden

For deterministic fixtures, capture exact or tolerance-bounded:

- raw bars;
- engine-smoothed bars;
- energy and transient bands;
- event edges and consume-once identity;
- Bubble authored inputs and output arrays;
- Spectrum authoritative display bars;
- mode-owned state after each accepted logical frame;
- generation and activation identity.

Continue using the existing replay framework and versioned golden directory. Do not create a competing replay architecture.

### C. Production-executor temporal golden

Run the approved production-style general executor path rather than `ImmediateComputeThreadManager`.

Capture, per sequence or bounded sample window:

- source sequence number and source timestamp;
- capture → submit time;
- worker start/end;
- callback/commit time;
- inter-publication interval;
- source age at visualizer tick;
- source age at Bubble authored step;
- Bubble submit, completion, consumption, and first-visible publication;
- Spectrum authoritative `set_state` publication and paint receipt;
- skipped/rejected/cancelled sequence identity;
- runtime, engine-generation, and activation identity;
- transition and GUI-stall markers.

Use exact ordering/integrity assertions and bounded timing distributions rather than exact wall-clock timestamps.

### D. Installed visual scenario record

Run and record:

- Bubble quiet passage;
- Bubble sustained bass;
- Bubble sharp kick/transient passage;
- Bubble dense/loud passage;
- Spectrum attack, decay, and rapid alternating rise/fall passage;
- Bubble → Spectrum → Bubble;
- pause/resume;
- mode transition overlap;
- normal presentation;
- controlled GUI stall;
- Settings recreation;
- Edit Save-and-Continue recreation;
- 60 Hz and available high-refresh display conditions.

Record user acceptance separately for Bubble and Spectrum. Logs may prove timing hazards but cannot overrule the visual verdict.

### E. Negative controls

The stronger suite must detect known rejected behaviour:

- persistent lane scheduling checkpoint `666624d` must differ in the scheduler/ownership temporal layer;
- rejected Spectrum smoothing `ebfec397` must fail the single-cadence/presentation-publication checks;
- Bubble terminal batching/cadence-gate fixtures must fail first-visible discrete-edge checks.

A golden package that also accepts these known-bad shapes is not strong enough.

### F. Mutation policy

- Never auto-regenerate approved visualizer goldens.
- A golden change requires a named candidate commit, reason, before/after evidence, and explicit user approval.
- Preserve old golden versions and their approved commit identities.
- A performance optimization should normally pass unchanged goldens.
- If visual behaviour intentionally changes, capture a new version only after installed approval; never overwrite the previous approved baseline.

## P5.0 tasks

- [x] Reject persistent shared-analysis and Bubble scheduling lanes.
- [x] Restore exact pre-lane production execution behaviour.
- [x] Obtain user approval of restored Bubble and Spectrum behaviour.
- [x] Reject and revert paint-local Spectrum smoothing.
- [ ] Create the immutable approval/environment manifest.
- [ ] Add deterministic source fixtures and captured approved source-feature sequences.
- [ ] Add production-executor temporal replay/capture.
- [ ] Add source-to-first-visible Bubble and Spectrum assertions.
- [ ] Add known-bad `666624d`, batching, and `ebfec397` negative controls.
- [ ] Archive installed visual scenario evidence and separate Bubble/Spectrum approval.
- [ ] Validate Sine, Oscilloscope, and Dev Curve against the restored shared source.
- [ ] Remove inert visualizer lane scaffolding after golden capture and repository-use audit.

# Deferred Visualizer Optimizations

These are **not current priority work**. None may begin until all P5.0 stronger-golden tasks are complete and the user explicitly authorizes the individual experiment.

Potentially acceptable later experiments:

1. Remove bookkeeping, diagnostics, allocations, or copies while preserving the exact approved executor, authored-step, publication, and paint cadence.
2. Reuse bounded immutable buffers where values, ordering, ownership, and publication remain identical.
3. Coalesce render snapshots only after every logical input and discrete event has already been integrated.
4. Explore Spectrum smoothing only as an isolated presentation experiment on the existing authoritative visualizer tick.

Any future Spectrum smoothing must:

- add no timer, scheduler, queue, self-requested paint loop, or paint-derived clock;
- never mutate authoritative bars inside `paintGL()` or a render callback;
- preserve immediate attack unless explicitly approved otherwise;
- preserve source, generation, activation, and first-frame authority;
- reset presentation state at mode/activation/generation/teardown boundaries;
- leave Bubble and shared-source scheduling untouched;
- compare publication and paint cadence against `ff934616`;
- revert immediately if the user reports worse behaviour.

Explicitly rejected unless separately re-proposed after new evidence:

- persistent visualizer compute lanes;
- source decimation;
- Bubble cadence caps or terminal batching;
- paint acknowledgement as producer control;
- simultaneous shared-source and mode-owned scheduler migration;
- “more paints” as a smoothing strategy.

# P5.1 — Delivery Tails

- [-] Correlate owner-labelled transition gaps with event-loop lateness, callback tails, update-request age, and per-display request-to-paint delay.
- [x] Preserve compositor transition names in owner telemetry.
- [ ] Attribute remaining p99/max transition gaps before changing visualizer cadence or shader behaviour.
- [ ] Reject repaint retries and transition-derived visualizer clocks.

# P5.2 — Latency Truthfulness

- [x] Remove impossible uptime-linear visualizer ERROR values.
- [x] Separate Bubble source, simulation, render-state, and request-to-paint ages.
- [ ] Preserve passive timing telemetry through lane-scaffolding cleanup.
- [ ] Add bounded inter-publication and source-sequence summaries required by the stronger golden package.
- [ ] Do not treat average latency or task throughput as fidelity proof.

# P5.3 — Unchanged Media Work

- [-] Prove unchanged polls perform no metadata publication, structural layout mutation, artwork work, or repaint.
- [ ] Preserve changed-track responsiveness and transition-time static feedback.
- [ ] Preserve startup artwork generation and reveal ordering.

# P5.4 — Recreation Ownership, Initialization, And Memory

## Evidence and confidence

### Settings

- The prior Settings barrier armed with one `PixelShiftManager`; that owner released normally.
- At timeout, QObjects, Python owners, resources, and global subscriptions were already zero. The only blocker was an idle persistent `visualizer.audio_analysis` lane.
- That production lane no longer exists after the approved executor restoration.
- **98% confidence:** the complete previously observed Settings blocker was removed.
- **Below 90% confidence that Settings now passes:** no installed post-restoration Settings recreation has yet proved the full current path.

### CUSTOM/Edit

- The prior two-display Edit barrier armed with two `CustomLayoutManager` and two `PixelShiftManager` owners.
- Both PixelShift owners and every watched QObject released. At timeout, exactly two `CustomLayoutManager` owners remained, plus the now-removed idle audio lane.
- `CustomLayoutManager.commit_session_without_reload()` calls the runtime reload synchronously before its manager-bearing locals and `finally` block have returned.
- The signal route remains direct on the GUI thread through DisplayWidget, DisplayManager, and the engine handler.
- Each `EditShellWidget` stores manager-closing `live_geometry_resolver` and `live_geometry_applier` lambdas. Shell signals are connected to manager bound methods. No explicit shell callback/signal release method exists before `deleteLater()`.
- **95% confidence:** the lifecycle defect is admission of teardown from inside the retiring edit-session graph, combined with reliance on incidental PySide/Python callback release.
- **85% confidence:** the exact final eight-second strong edge is a shell Python wrapper/callback registry retaining its manager. The evidence lacks a live `gc.get_referrers` or equivalent referrer snapshot, so do not claim a more exact edge as fact.

### Replacement initialization

- `_initialize_display()` already rejects replacement construction while the retiring barrier is incomplete.
- The current display path creates the complete participating display set before staggered show, tags delayed shows with runtime generation, checks exact manager/display membership, and gates reveal on current authoritative first frames.
- No evidence currently shows replacement construction beginning too early or stale first-frame state satisfying readiness after the barrier.
- Do not redesign initialization unless a fresh run shows a separate failure. Preserve and test the existing boundaries.

## Required CUSTOM/Edit implementation

### 1. Separate persistence from recreation admission

Refactor the save/reset/slot-commit paths into two explicit stages:

1. **Persist and retire edit session:** calculate and save the CUSTOM scene, then completely detach edit-session UI and manager-owned callbacks.
2. **Engine-owned reload admission:** on a later GUI event-loop turn, validate an immutable request and begin `engine.stop(exit_app=False, reason="custom_edit")`.

The synchronous signal handler may accept the request, set a duplicate-admission guard, and queue the later engine callback. It may not call `stop()` directly.

### 2. Immutable reload intent

Create a narrow immutable intent containing only primitive identity needed to reject stale requests, for example:

- request kind (`save`, `reset`, `slot_load`, or `slot_save`);
- expected runtime generation;
- expected `DisplayManager` identity;
- settings revision or committed scene identity if available.

The queued callback may retain the process-lifetime engine and the immutable intent. It must not retain a `CustomLayoutManager`, `DisplayWidget`, `DisplayManager`, `EditShellWidget`, edited widget, shell state, deferred pixmap, bound manager method, or closure over any of those objects.

The callback must reject stale generation/manager identity and coalesce duplicate CUSTOM admissions.

### 3. Deterministic shell callback release

Add one explicit EditShell retirement contract and call it before `hide()`, `deleteLater()`, or display teardown:

- cancel mouse/pointer interaction and release grabs;
- disconnect every shell signal connected to manager bound methods;
- clear `_live_geometry_resolver` and `_live_geometry_applier`;
- remove installed button event filters if needed for clean wrapper release;
- clear snapshot and guide payloads that are not needed after retirement;
- make repeated retirement harmless.

Do not rely on QObject destruction, automatic PySide signal cleanup, Python cyclic GC, or the barrier timeout to release these callbacks.

### 4. Finish managers before queuing teardown

The persist stage must, before requesting engine work:

- retire every active manager and shell;
- empty `CustomLayoutManager._active_managers`;
- uninstall and clear the global key filter;
- cancel or neutralize pending restack/menu callbacks and class flags;
- clear manager shell/state collections and manager-bound deferred state;
- clear each display's edit-active and reload-pending flags;
- remove display → manager ownership only during normal display cleanup, not prematurely while persistence still needs it;
- return from all manager-owned save/reset/key-filter frames before engine teardown starts.

Do not keep a manager-bearing `active_managers`, `grouped_states`, `survivors`, or equivalent collection alive across the queued admission boundary.

### 5. Deferred image rule

A deferred processed image captured during Edit belongs to the retiring runtime:

- **Cancel without runtime replacement:** it may be flushed back to the still-current display after session state is restored.
- **Save/reset/slot action followed by full runtime reload:** discard it; do not publish it immediately before generation invalidation and teardown.

### 6. Preserve the fail-closed barrier

- Keep `CustomLayoutManager` in `collect_runtime_roots()` and barrier observation.
- Do not weaken the timeout, ignore manager owners, remove weakref watches, or invoke production `gc.collect()`.
- Barrier completion remains the permission for replacement construction, not the mechanism used to force owner release.

## Required focused tests

Add tests that fail on the current implementation:

1. Two-display Save-and-Continue uses the real signal relay shape and proves engine teardown is not called until a later GUI turn after `save_session()` and the key-filter/event frame return.
2. Weakrefs to both retired managers and all edit shells clear without `gc.collect()` before the runtime barrier continuation runs.
3. Shell retirement clears resolver/applier callbacks and disconnects manager-bound signals idempotently.
4. The queued engine callback closure contains no manager/display/shell/widget owner and carries only engine plus immutable intent.
5. Duplicate requests coalesce; stale runtime generation or `DisplayManager` identity is rejected.
6. Save/reset/slot reload discards deferred processed image; cancel restores it.
7. Two-display barrier integration reaches zero `CustomLayoutManager` Python owners and then constructs exactly one replacement runtime.
8. Settings recreation reaches zero ownership with no persistent visualizer lane and does not use the CUSTOM admission path.

The existing counter-only `_request_custom_layout_runtime_reload()` stub tests remain useful for persistence, but they are not lifecycle evidence.

## First-frame and initialization invariants

For every recreation:

- retired generation reaches zero before replacement construction;
- `_initialize_display()` fails closed if any destruction barrier remains pending;
- all requested displays are registered before the first staggered show;
- delayed show callbacks are rejected by runtime generation, exact manager, and display membership;
- replacement remains hidden until its own authoritative first frame;
- old callbacks, transitions, visualizer results, cached state, construction, GL initialization, or timer ticks cannot satisfy readiness;
- Bubble and Spectrum use current engine generation and activation;
- `FadeCoordinator` remains the sole reveal coordinator;
- missing fresh data keeps presentation hidden rather than showing stale state.

## Runtime validation order

### Pass A — current Settings path

Run Settings once on current main before CUSTOM code changes. Require:

- no persistent visualizer lane ownership;
- barrier completion;
- Settings dialog construction only after completion;
- dialog destruction barrier completion;
- exactly one replacement runtime;
- correct authoritative first-frame reveal.

If it fails, use the new owner/resource/task list as evidence. Do not apply the CUSTOM fix to an unrelated Settings owner.

### Pass B — repaired CUSTOM path

Run dual-display Edit Save-and-Continue and require:

- persist stage completes and returns before teardown begins;
- no manager/shell/display object appears in the queued request closure;
- zero retiring `CustomLayoutManager` owners;
- zero QObjects/resources/tasks/subscriptions before replacement;
- exactly one replacement runtime;
- saved layout replays correctly;
- no stale deferred image or old visualizer frame appears.

### Pass C — alternating lifecycle and plateau matrix

Run at least five alternating Edit and Settings cycles in normal and Media Center variants, including Bubble, Spectrum, Bubble → Spectrum → Bubble, playing/paused, transition-time teardown, pending image work, pending ordinary audio/Bubble executor work, dual display, and one selected display.

Every retired generation must reach zero QObjects, Python owner roots, resources, timers, animations, subscriptions, callbacks, tasks, lanes, visualizer owners, CustomLayoutManagers, registrations, pixmaps, textures, PBOs, and tracked GL bytes.

Equivalent settled RSS, private commit, dedicated VRAM, handles, threads, CPU, and GPU must stop rising approximately linearly per cycle.

If ownership reaches zero but memory still rises, begin a new evidence-led retention investigation. Current confidence in any remaining allocator/cache/driver cause is below 90%; do not alter cache budgets, add trimming, recycle processes, or weaken teardown without that evidence.

# P5.5 — Cache Representations

Blocked by P5.4.

- [ ] Audit raw/scaled/display co-retention, exact-transform duplication, unused prefetch results, and eviction churn only after clean lifecycle cycles exist.
- [ ] Keep the 256 MiB production CPU-cache limit.
- [ ] Do not add pins or raise budgets without a proven readiness failure.

# P5.6 — Logging Hygiene

- [-] Keep detailed cache records in `screensaver_cache.log`.
- [-] Keep lifecycle ownership detail in `screensaver_lifecycle.log`.
- [ ] Add one authoritative startup record distinguishing `main` and `main_mc`.
- [ ] Add bounded CUSTOM admission diagnostics: request identity, queued turn, persist-complete timestamp, teardown-start timestamp, stale/duplicate rejection, and manager/shell weakref counts.
- [ ] Keep high-volume diagnostics bounded and passive.
- [ ] All warnings and errors remain visible in `screensaver.log`.
- [ ] A critical lifecycle timeout always marks the run failed.

# Undocumented Adversarial Findings

- [!] Recover the exact two adversarial-lane findings previously reported by Codex.
- [ ] Record interleaving, owner, failure, missing test, reproduction, repair, rollback, deterministic acceptance, and installed evidence.
- [ ] If no production consumer remains for the generic scheduler, document these findings before deleting it.
- [ ] If the exact findings are unrecoverable, state that and rerun the adversarial audit rather than inventing them.

# Phase 5 Gate

Phase 5 passes only when:

- the stronger user-approved visualizer golden package exists;
- Bubble and Spectrum remain equal or better than `ff934616`;
- all five visualizer modes pass restored shared-source validation;
- Settings and Edit recreation pass repeatedly;
- CUSTOM teardown begins only after the retiring edit graph is explicitly retired and its manager-owned call stacks return;
- no retired generation survives;
- memory, VRAM, handles, threads, and ownership plateau;
- first-frame poison does not return;
- p99/max delivery is equal or better;
- diagnostics create no meaningful work;
- normal and Media Center variants pass;
- adversarial findings are documented and resolved or explicitly active.

# Later Phases

## Phase 6 — Explicit GPU Resource Store

Metadata-first storage, exact bytes, context/share generation, explicit leases, no GL under registry locks, owner-thread deletion, byte caps, and unleased eviction.

## Phase 7 — Visualizer/Presentation Decoupling

Narrow immutable render state, simulation independent of paint, coalescing only after logical integration, injected GUI-stall tests, and no producer paint waits. Any future presentation smoothing belongs here only after the P5.0 golden gate.

## Phase 8 — Narrow Single-Surface Compositor

One surface per display, immutable scene snapshots, explicit draw order, GUI-local update coalescing, and no simulation/lifecycle ownership.

## Phase 9 — Local Transition Completion

Source/destination/start/duration/easing, local completion after paint, deterministic temporary-resource release, and interruption/resize/Settings/Edit/topology tests.

## Phase 10 — Remove Temporary And Legacy Scaffolding

Remove forwarding, duplicate runtime paths, dead retries/backoff, obsolete metrics, and inert settings after compatibility audit; prove no silent fallback.

## Phase 11 — Full Validation

Normal run, two-hour soak, all-mode review, CPU/disk/GPU/mixed hostile load, Settings/Edit during activity, multi-display/topology, memory plateau, and p99/max gates.

## Phase 12 — Release Preparation

Canonical docs match code, benchmark evidence archived, budgets/limitations recorded, rollback commit identified, release candidate tagged, and donor history/evidence preserved.

## Deferred Until Recovery Passes

- new production widget families;
- partial GL reinitialization;
- speculative quality scaling;
- unrelated architectural cleanup;
- donor feature promotion without isolated evidence.

## Plan Hygiene

- Keep only active work and current acceptance boundaries here.
- Move resolved dated narratives to historical records and phase reports.
- Do not claim closure from deterministic tests alone.
- Do not rename this file.
- Do not delete the user task box.

USER TASK BOX. ADD ITEMS BELOW INTO PLANNED STEPS AND EMPTY BOX. NEVER EVER DELETE THIS BOX AS A WHOLE OR THESE INSTRUCTIONS, ONLY PROPERLY ADOPTED IDEAS, YA GOBLIN ASS BITCH.
#######
#######