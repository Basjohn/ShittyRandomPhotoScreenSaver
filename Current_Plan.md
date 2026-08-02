# Current Plan

Last updated: 2026-08-02

Active unfinished work only.

Stable architecture belongs in `Spec.md`. Durable safety rules belong in `Docs/Guardrails.md`. Detailed evidence belongs in the existing phase reports. Dated failures and rejected fixes belong in `Docs/Historical_Bugs.md`. Completed narratives should leave this file once their evidence is accepted and archived.

## Recovery Boundary

```text
branch: main
recovery baseline: 00edb57a3076b845cb8ee4b6cb7f36ea83411f0c
donor/reference only: 7376bb9bb380253f3bd14079e65d7bdbca062fad
pre-persistent-lane behavioral checkpoint: 6f188adadabb77b1a9d47a0fe1685c86ad39fb77
current failed-evidence application checkpoint: 666624d421b08f978c5f610571a078570150a1e7
current evidence: logs/evidence_chest/08_01_666624d4_22_05/
owning report: Docs/phase_reports/P05_CPU_TASK_REDUCTION.md
```

The donor is read-only reference material, never a merge target. Phase 4 remains closed. Current failures are repaired under Phase 5 rather than reopening or discarding completed work.

`6f188ad` is the immediate checkpoint before the persistent shared-audio and Bubble compute-lane migration. It already contains the restored lane-free Bubble path that received operator confirmation. It is therefore the authoritative behavioral recovery point for this visualizer regression investigation.

## Status Legend

- `[ ]` not started
- `[-]` active
- `[x]` complete with accepted evidence
- `[!]` failed or blocking
- `[~]` explicitly deferred

A code slice is not complete merely because unit tests pass. Acceptance requires the relevant deterministic checks, installed runtime evidence, operator visual review where presentation is involved, and a rollback point.

## Non-Negotiable Gates

- Visualizer feel, reactivity, latency, smoothness, mode personality, and first-frame correctness outrank task-count reduction.
- Spectrum and Bubble are independently protected. A change helping one may not silently alter the other.
- Operator-observed Bubble or Spectrum regression overrides green task counters and incomplete deterministic proxies.
- Average FPS, mean worker duration, total accepted steps, and zero rejected submissions cannot hide p99/max source gaps, lost impulses, stale energy, or visible stepping.
- Full Settings/Edit stop/destroy/recreate remains authoritative. Do not weaken it to make recreation pass.
- The destruction barrier fails closed. Do not ignore an idle-but-registered owner, extend timeouts, add retries, or continue after a critical timeout.
- The destruction barrier and authoritative-first-frame barrier are separate and must both pass before reveal.
- The existing `FadeCoordinator` remains the sole reveal coordinator.
- Runtime generation, manager identity, engine generation, and activation identity rejection remain mandatory.
- GL resources are deleted in their owning context before Qt roots and contexts are destroyed.
- RAM, private commit, handles, threads, tracked ownership, and dedicated VRAM must plateau across repeated equivalent recreation cycles.
- Producers never wait for paint. Simulation and analysis cadence are never derived from paint acknowledgement.
- Do not add arbitrary sleeps, nested `processEvents()`, periodic `gc.collect()`, working-set trimming, process/worker recycling, cache enlargement, retired-tree reuse, or warm-standby runtimes.
- Existing files and documents are not renamed or moved.
- Do not discard or overwrite unrelated in-progress Phase 5 work. Finish an atomic slice safely before changing visualizer execution paths.
- Do not update or regenerate visualizer goldens to bless the current lane behavior.
- Do not tune Bubble or Spectrum while restoring the pre-lane execution path.

## Completed Checkpoints

- [x] **Phase 0 / Gate 0:** freeze, evidence, and ownership inventory.
- [x] **Phase 1 / Gate 1:** passive measurement foundation.
- [x] **Phase 2 / Gate 2:** deterministic all-mode logical replay and protected goldens.
- [x] **Phase 3 / Gate 3:** full lifecycle, stale-work rejection, and owner-context GL deletion.
- [x] **Phase 4 / Gate 4:** bounded image/GL ownership, whole-application plateau evidence, startup artwork, and media-next transition collision repair.

Phase 2 goldens remain valuable but are not a complete scheduler/presentation oracle. Phase 4 is not reopened by later lifecycle regressions.

# Phase 5 — CPU, Task, Delivery, and Recreation Recovery

## Current blocking state

The application checkpoint and evidence above are failed runtime evidence.

- [!] CUSTOM/Edit Save-and-Continue tears down but does not recreate.
- [!] Settings stop/open/return tears down but does not complete its intended flow.
- [!] Both paths can fail on an unreleased retiring-generation `visualizer.audio_analysis` compute lane.
- [!] CUSTOM/Edit additionally retains two `CustomLayoutManager` Python owners.
- [!] Spectrum is visibly less smooth and less reliable than at the pre-lane checkpoint.
- [!] Bubble is operator-reported as regressed after previously being restored and approved at `6f188ad`.
- [!] The persistent visualizer lanes are not accepted production architecture while either visualizer fidelity or lifecycle ownership is failing.
- [!] No run containing `CRITICAL [LIFECYCLE_BARRIER] timeout` may be described as accepted or successful.
- [!] P5.4 blocks P5.5 and Phase 5 closure.

## Required work order

1. Inspect and preserve the current working tree and retained Codex context.
2. Finish the currently atomic in-progress task safely; do not leave unused shells.
3. Keep active docs truthful and remove stale lifecycle or visualizer pass claims.
4. Restore the exact pre-persistent-lane visualizer execution semantics from `6f188ad` for both shared audio analysis and Bubble simulation, preserving only passive newer telemetry and lifecycle identity tags that do not alter execution.
5. Produce an installed recovery build before tuning, smoothing changes, scheduler changes, or new golden work.
6. Obtain operator A/B confirmation for Bubble and Spectrum against `6f188ad` behavior.
7. After confirmation, remove the now-unused visualizer lane facades and generic scheduler integration unless another proven production owner exists.
8. Repair the remaining `CustomLayoutManager` ownership and Edit-save-to-reload call-stack boundary.
9. Prove Settings and Edit recreation in normal and Media Center variants.
10. Rerun first-frame and mode-switch poison protection.
11. Recover and document the two adversarial lane findings previously reported by Codex.
12. Resume remaining Phase 5 work in order.
13. Close Phase 5 only after the complete installed matrix passes.

# Investigation Ledger

Concrete source-level findings belong here as they are established. Suspicions remain labelled as hypotheses until runtime evidence distinguishes them.

## CF-01 — Persistent visualizer lane migration crossed a protected behavioral boundary

**Status:** concrete commit-boundary finding and rejected current production state. Exact internal timing mechanism remains useful diagnostic evidence, but behavioral recovery no longer waits for a speculative lane repair.

### Commit isolation

The persistent lane migration is isolated to the change from:

```text
6f188adadabb77b1a9d47a0fe1685c86ad39fb77
→
666624d421b08f978c5f610571a078570150a1e7
```

`6f188ad` already contained:

- the rollback of the failed 60 Hz/max-two Bubble batching design;
- one authored Bubble simulation step for every lane-free opportunity;
- operator-confirmed restored Bubble reaction and elasticity;
- the ordinary general COMPUTE executor path for shared audio analysis;
- the ordinary general COMPUTE executor path for Bubble simulation.

`666624d` introduced two distinct behavioral migrations:

1. shared `visualizer.audio_analysis` moved from repeated general COMPUTE submissions to one persistent managed lane;
2. Bubble simulation moved from the restored general COMPUTE submission path to a persistent Bubble lane.

The current regression report therefore has two plausible direct causes rather than requiring one shared speculative explanation:

- Spectrum can regress through the shared audio-analysis lane;
- Bubble can regress through both the shared source lane and its own simulation-lane migration.

### Current decision

The persistent visualizer lane design is not accepted in its current form.

It achieved lower Task/Future/accounting churn, but it now has both:

- a hard lifecycle failure: the retired shared audio lane remains registered and blocks Settings/Edit recreation;
- an operator-reported fidelity failure: Spectrum and Bubble no longer match the accepted pre-lane behavior.

A task-reduction design that fails lifecycle or authored visualizer feel is a failed optimization regardless of average handoff, worker duration, publication count, or rejected-submission count.

Do not ask Codex to tune the lane until it looks right. Restore the exact known behavior first.

### Is the lane idea intrinsically invalid?

No general claim is made that persistent compute lanes can never be useful.

The narrower conclusion is authoritative:

- this visualizer adoption was not sufficiently validated;
- the generic lane scheduler has no proven non-visualizer production consumer at this checkpoint;
- the shared analysis and Bubble paths are too behavior-sensitive to retain an unapproved scheduler substitution;
- future reconsideration belongs after recovery, with a scheduler-shaped oracle and operator-approved evidence.

No separate Spectrum lane is proposed.

### Why current counters do not clear the design

The latest installed evidence reports:

- no busy or stopped submission rejection during long sampled sections;
- cheap mean handoff and callbacks;
- high accepted/completed/published totals;
- occasional substantially larger execution and handoff maxima than the means.

These counters prove throughput and bounded ownership during normal operation. They do not prove equivalence of:

- inter-publication timing;
- exact source sequence;
- transient-to-first-visible timing;
- Bubble event consumption timing;
- Bubble expansion and contraction trajectory;
- Spectrum hold duration and per-frame step size;
- source freshness during a continuously moving simulation.

This is the same class of validation failure that allowed the earlier Bubble batching regression to pass proxy tests.

### Exact old versus new shared-analysis semantics

At `6f188ad`, each accepted audio frame:

- created one ordinary COMPUTE task;
- captured the smoothing state for that task;
- ran FFT and smoothing through the general executor;
- cleared `_compute_task_active` at callback entry before committing the result;
- committed through `_commit_analysis_frame()` after token and activation checks.

At `666624d`, the same logical work:

- enters one persistent scheduler lane;
- shares a small process-owned lane worker set with other managed visualizer lanes;
- remains lane-owned through result publication;
- clears `_compute_task_active` only after callback completion;
- gains persistent lane registration and lifecycle state.

The new sequence may be safer in some interleavings, but it is not behaviorally identical. The old semantics are the recovery authority.

### Exact old versus new Bubble semantics

At `6f188ad`, every lane-free authored Bubble step:

- freezes current energy/settings/pulse payloads;
- submits the existing Bubble worker directly to the general COMPUTE executor;
- publishes through the existing token-checked callback;
- uses no persistent Bubble facade or scheduler lane.

At `666624d`, that step:

- is wrapped in `BubbleStepPacket`;
- is submitted through `BubbleComputeLane` and the shared persistent scheduler;
- publishes through an additional facade callback layer;
- competes under the generic managed-lane worker pool;
- gains another lifetime owner and stop contract.

Even when every step is accepted, this changes scheduling and publication timing. Operator evidence says the replacement is not equivalent.

### Why the Phase 2 goldens did not stop this

The Phase 2 goldens protect deterministic logical equations and mode-owned output after a frame has been accepted.

The replay path:

- injects timestamped feature frames through `accept_analysis_frame()`;
- uses an immediate deterministic compute test double;
- executes worker and callback synchronously;
- does not advertise or run the production persistent compute-lane scheduler;
- does not reproduce handoff, shared-worker contention, publication jitter, real callback timing, or lifetime ownership.

The persistent-lane unit tests similarly establish local packet execution and stop behavior, not live visual equivalence.

Exact goldens can therefore remain green while live scheduling feel regresses.

### Can Git reconstruct the true golden?

Git can reconstruct the exact code and deterministic logical output of `6f188ad`.

Git cannot independently reconstruct the complete subjective live golden because visual feel also depends on:

- real audio capture timing;
- song dynamics;
- Windows scheduling;
- display refresh and Qt delivery;
- the exact installed settings/preset;
- operator perception of reaction, elasticity, and smoothness.

Therefore:

- do not ask Codex to infer the desired Bubble feel from current code;
- do not ask Codex to create new expected outputs from the broken checkpoint;
- use `6f188ad` as an executable behavioral oracle;
- restore its execution path mechanically into the current lifecycle branch;
- require operator confirmation;
- only after confirmation capture stronger reference traces from that approved behavior.

### Behavioral recovery implementation

#### Recovery commit A — disable visualizer lane adoption

Make the smallest behavior-restoring patch first.

1. `widgets/spotify_visualizer/beat_engine.py`
   - restore `_schedule_compute_bars_task()` from `6f188ad` as the active production path;
   - use ordinary `ThreadManager.submit_compute_task()`;
   - preserve the old smoothing snapshot, callback ordering, token check, activation check, and `_commit_analysis_frame()` seam;
   - retain current runtime-generation annotations only when they are passive ownership metadata and do not change callback order;
   - stop creating or consulting `_analysis_compute_lane`;
   - do not add replacement cadence, priority, smoothing, queue, or retry logic.

2. `widgets/spotify_visualizer/tick_pipeline.py`
   - restore the `6f188ad` Bubble submission path exactly;
   - submit `_bubble_compute_worker` directly through the general COMPUTE executor;
   - preserve one authored step per lane-free opportunity;
   - preserve token-checked publication and existing event/energy payload semantics;
   - passive `source_ts`/`authored_ts` observation may remain only if it does not alter worker arguments, callback order, admission, or publication.

3. `widgets/spotify_visualizer_widget.py`
   - stop constructing, starting, stopping, or diagnosing `BubbleComputeLane`;
   - restore the `6f188ad` Bubble worker/result ownership fields and cleanup behavior;
   - preserve current generation and first-frame rejection guards.

4. Shared engine lifecycle
   - stop creating the persistent audio-analysis lane;
   - ensure no lane registration can remain after visualizer cleanup because no production visualizer lane is acquired;
   - continue to cancel or generation-reject ordinary executor work during teardown.

5. Tests
   - add a structural test that production shared analysis does not call `create_compute_lane()`;
   - add a structural test that production Bubble dispatch does not call `BubbleComputeLane` or `create_compute_lane()`;
   - keep Phase 2 goldens read-only;
   - keep the Bubble source/discrete-edge oracle;
   - do not replace operator acceptance with these tests.

#### Temporary retention rule

For the first installed recovery build, the generic `ComputeLaneScheduler` and facades may remain present but must be unreachable from production visualizer execution. This keeps the behavioral patch narrow and makes causality easy to confirm.

They may remain inert for only this A/B step.

#### Recovery commit B — remove rejected scaffolding

After operator confirmation that Bubble and Spectrum are restored:

- delete `widgets/spotify_visualizer/bubble_compute_lane.py`;
- delete visualizer lane tests that only authorize the rejected path;
- remove visualizer-specific lane diagnostics and lifecycle accounting;
- remove `ComputeLaneScheduler` and ThreadManager integration if repository search still shows no proven production consumer;
- otherwise retain the generic scheduler only for the independently proven consumer and remove all visualizer coupling;
- update Phase 5 and Historical Bugs with the exact rejection and rollback.

Do not leave dead lane shells indefinitely.

### Installed behavioral comparison

Produce two comparable builds or runs:

```text
reference: 6f188ad
recovery: current branch with Recovery commit A
```

Use the same:

- settings and selected visualizer preset;
- display route and refresh conditions;
- audio device;
- song and playback position where practical;
- Bubble and Spectrum mode-switch sequence;
- normal/MC variant where applicable.

Required operator review:

- Bubble on quiet, sustained-bass, sharp-kick, and dense/loud material;
- Spectrum attack, decay, between-frame smoothness, and reliability;
- Bubble → Spectrum → Bubble;
- transition overlap;
- pause/resume;
- Settings/Edit recreation after the lane is absent.

The operator's result decides whether behavior is restored. Codex may report measurements but may not overrule the visual result.

### Stronger golden only after recovery

Once the restored current build is operator-approved:

1. Record a deterministic PCM or post-capture source sequence with authoritative timestamps.
2. Run it through the approved general-executor analysis path.
3. Capture:
   - source sequence and timestamps;
   - accepted analysis frames;
   - inter-publication intervals;
   - Bubble input snapshots and simulation results;
   - Spectrum displayed bars;
   - source-to-first-visible timing;
   - mode-owned overlay state.
4. Freeze those traces as an additional scheduler-shaped reference.
5. Never update them automatically.

This supplements the Phase 2 logical goldens. It does not replace operator runtime review.

### Acceptance

Recovery commit A passes only when:

- production audio analysis uses the `6f188ad` general COMPUTE path;
- production Bubble simulation uses the `6f188ad` general COMPUTE path;
- no production visualizer compute lane is registered;
- the Settings/Edit barrier no longer sees `visualizer.audio_analysis` or Bubble lane ownership;
- Phase 2 goldens remain unchanged;
- existing first-frame and generation guards remain passing;
- Bubble is operator-confirmed equal to the approved pre-lane behavior;
- Spectrum is operator-confirmed equal to or better than the pre-lane behavior;
- no new task reduction is attempted during recovery.

If behavior remains wrong after the exact execution-path restoration, continue diffing `6f188ad → current` outside the lane subsystem. Do not tune blindly.

# P5.0 — Visualizer cadence and fidelity

- [!] Reject the current persistent shared-analysis and Bubble-lane production adoption.
- [-] Implement CF-01 Recovery commit A from `6f188ad` without tuning.
- [ ] Produce the installed `6f188ad` versus recovery comparison.
- [ ] Obtain explicit operator Bubble and Spectrum acceptance.
- [ ] Remove rejected lane scaffolding in Recovery commit B after acceptance.
- [x] Reject the failed Bubble 60 Hz/max-two terminal-batching design.
- [x] Restore one authored Bubble step for every lane-free opportunity at `6f188ad`.
- [x] Add a source/discrete-edge-to-first-visible Bubble oracle for the rejected batching failure.
- [ ] Capture stronger scheduler-shaped references from the operator-approved restored path.
- [ ] Validate Sine, Oscilloscope, and Dev Curve after the shared source is restored.
- [ ] Require installed operator review before marking P5.0 complete.

# P5.1 — Delivery tails

- [-] Correlate owner-labelled transition gaps with event-loop lateness, queue/callback tails, update-request age, and per-display request-to-paint delay.
- [x] Preserve compositor transition names in owner telemetry.
- [ ] Attribute the remaining transition-time p99/max gaps before changing shader or visualizer cadence.
- [ ] Reject repaint retries and transition-derived visualizer clocks.

# P5.2 — Latency truthfulness

- [x] Remove impossible uptime-linear visualizer ERROR values.
- [x] Separate Bubble source, simulation, render-state, and request-to-paint ages.
- [ ] Preserve passive source/visible timing telemetry through the executor restoration.
- [ ] Validate separated ages in installed transition evidence.
- [ ] Do not reinterpret current lane metrics as fidelity proof.

# P5.3 — Unchanged media work

- [-] Prove unchanged polls perform no metadata publication, structural layout mutation, artwork work, or repaint.
- [ ] Preserve changed-track responsiveness and the fixed transition-time static feedback path.
- [ ] Preserve startup artwork generation and reveal ordering.

# P5.4 — Recreation ownership and memory

## Hard failures

CUSTOM/Edit currently times out with:

```text
python_owners={'CustomLayoutManager': 2}
thread_work=[visualizer.audio_analysis lane for retiring generation]
```

Settings can reach zero QObjects and Python owners yet still time out on the same idle-but-unreleased audio-analysis lane.

The barrier is correctly failing closed.

## Visualizer lane blocker

CF-01 Recovery commit A is the first repair for the shared lane blocker.

After the visualizer no longer registers persistent compute lanes:

- the destruction barrier must contain no `visualizer.audio_analysis` lane;
- Settings must proceed to its dialog/recreation flow;
- Edit must either proceed or fail only on independently retained owners;
- ordinary executor tasks remain generation-visible and must cancel, complete, or reject publication before the barrier passes.

Do not build a complex engine-lease system solely to preserve a rejected visualizer lane.

If an engine, audio worker, ordinary executor task, or widget owner still survives after lane removal, then add the narrow exact ownership lease needed for that remaining owner. Do not pre-emptively retain the lane architecture.

## CUSTOM/Edit manager ownership

- [-] Trace both surviving `CustomLayoutManager` instances.
- [ ] Audit class-level active managers, global key filter, restack callbacks, menu state, scheduled single shots, local manager lists, shell callbacks, display/coordinator references, bound methods, closures, deferred pixmaps, and save/reload stack frames.
- [ ] Split Edit commit from engine-owned recreation where the current manager-owned stack retains the managers.
- [ ] Stage 1 persists data, finishes sessions, destroys shells/overlay, clears class state, detaches managers, and returns an immutable reload intent.
- [ ] Stage 2 starts the existing engine recreation only after the manager-owned call stack has unwound.
- [ ] Stage 2 captures no manager, display, shell, or widget.
- [ ] Clear `display._custom_layout_manager` during retirement after cleanup.
- [ ] Do not remove managers from barrier observation merely to pass it.

## First-frame poison invariants

For every recreation:

- retired generation reaches zero before replacement construction;
- replacement remains hidden until its own authoritative first frame;
- old callbacks, frames, transitions, visualizer results, and cached presentation cannot satisfy readiness;
- Spectrum waits for current engine generation and activation;
- Bubble uses new generation-owned simulation state;
- mode-specific waveform rules remain intact;
- `FadeCoordinator` reveals only after critical-resource and first-frame barriers;
- a missing fresh frame keeps presentation hidden rather than showing a placeholder or stale frame.

## Lifecycle matrix

Run at least five alternating Edit and Settings cycles in both normal and Media Center variants, including:

- Bubble;
- Spectrum;
- Bubble → Spectrum → Bubble;
- Spotify playing and paused;
- active image transition near teardown;
- pending image work;
- pending ordinary audio-analysis work;
- pending ordinary Bubble simulation;
- dual display;
- one selected display.

Every retiring generation must reach zero:

- QObjects;
- Python owner roots;
- ResourceManager generation entries;
- timers;
- animations;
- subscriptions;
- queued/delayed callbacks;
- executor tasks;
- compute lanes;
- visualizer engine owners;
- CustomLayoutManagers;
- display/coordinator registrations;
- display pixmaps;
- textures;
- PBOs;
- tracked GL bytes.

Every replacement generation must construct, produce exactly one authoritative first-frame-ready event, reveal through `FadeCoordinator`, and resume normal images, media, Bubble, and Spectrum.

Equivalent settled RSS, private commit, dedicated VRAM, handles, threads, CPU, and GPU must stop rising approximately linearly per cycle.

# P5.5 — Cache representations

Blocked by P5.4.

- [ ] Audit raw/scaled/display co-retention, exact-transform duplication, unused prefetch results, and eviction churn.
- [ ] Keep the 256 MiB production CPU-cache limit.
- [ ] Do not add pins or raise budgets without a proven readiness failure.

# P5.6 — Logging hygiene

- [-] Keep detailed cache records in `screensaver_cache.log`.
- [-] Keep lifecycle ownership detail in `screensaver_lifecycle.log`.
- [ ] Add one authoritative startup record distinguishing `main` and `main_mc`.
- [ ] Keep high-volume diagnostics bounded and passive.
- [ ] All warnings and errors remain visible in `screensaver.log`.
- [ ] A critical lifecycle timeout always marks the evidence run failed.

# Undocumented adversarial lane findings

Codex previously reported two major adversarial-lane issues that are not present in the visible active documents.

- [!] Recover the exact two findings from retained context.
- [ ] For each, record the interleaving, owner, failure, missing test, reproduction, repair, rollback, deterministic acceptance, and installed evidence.
- [ ] Current correctness, lifecycle, latency, memory, or fidelity issues remain in Phase 5 and Historical Bugs.
- [ ] If the exact findings are no longer recoverable, state that plainly and rerun the adversarial audit. Do not invent them.
- [ ] If the generic scheduler has no production consumer after CF-01 Recovery commit B, document the findings before deleting it; do not preserve rejected production architecture merely to justify the audit.

# Phase 5 gate

Phase 5 passes only when:

- CPU/task cost is materially lower without lane-induced visualizer regression;
- p99/max delivery is equal or better;
- Settings and Edit recreation pass repeatedly;
- memory/VRAM/handle/thread ownership plateaus;
- no retired generation survives;
- no first-frame poison returns;
- Spectrum and Bubble are equal or better by deterministic evidence and installed manual review;
- all five visualizer modes pass shared-source validation;
- no diagnostic system creates meaningful work;
- normal and Media Center variants both pass;
- the two adversarial findings are documented and resolved or explicitly active.

# Later Phases

## Phase 6 — Explicit GPU Resource Store

- metadata-first store;
- exact byte accounting;
- context/share generation;
- explicit leases;
- no GL calls under registry locks;
- owner-thread deletion;
- byte caps and unleased eviction.

## Phase 7 — Visualizer/Presentation Decoupling

- narrow immutable render state;
- simulation independent of paint;
- newest render-state coalescing after logical integration;
- injected GUI-stall tests;
- no producer paint waits.

Any future persistent-lane reconsideration belongs here or in a separately approved Phase 5 experiment after the restored executor path is frozen. It must use the stronger scheduler-shaped reference and operator approval.

## Phase 8 — Narrow Single-Surface Compositor

- one surface per display;
- immutable scene snapshot;
- explicit draw order;
- GUI-local update coalescing;
- no simulation or lifecycle ownership.

## Phase 9 — Local Transition Completion

- source/destination/start/duration/easing;
- local completion after completed paint;
- deterministic temporary-resource release;
- interruption, resize, Settings, Edit, and topology tests.

## Phase 10 — Remove Temporary and Legacy Scaffolding

- remove dynamic forwarding;
- remove duplicate runtime paths;
- remove dead retries/backoff;
- remove obsolete metrics and inert settings after compatibility audit;
- prove no silent fallback.

## Phase 11 — Full Validation

- normal 30-minute run;
- two-hour soak;
- all-mode fidelity review;
- CPU, disk/decode, GPU, and mixed hostile load;
- Settings/Edit during activity;
- multi-display/topology;
- RAM/VRAM plateau;
- p99/max gates.

## Phase 12 — Release Preparation

- canonical docs match code;
- benchmark evidence archived;
- budgets and limitations recorded;
- rollback commit identified;
- release candidate tagged;
- donor history and evidence preserved.

## Deferred Until Recovery Passes

- new production widget families;
- partial GL reinitialization;
- speculative quality scaling;
- unrelated architectural cleanup;
- donor feature promotion without isolated evidence.

## Plan Hygiene

- Keep active failures and concrete findings here.
- Move dated resolved narratives to Historical Bugs and phase reports.
- Do not claim closure from deterministic tests alone.
- Do not rename this file.
- Do not delete the user task box.

USER TASK BOX. ADD ITEMS BELOW INTO PLANNED STEPS AND EMPTY BOX. NEVER EVER DELETE THIS BOX AS A WHOLE OR THESE INSTRUCTIONS, ONLY PROPERLY ADOPTED IDEAS, YA GOBLIN ASS BITCH.
#######
#######