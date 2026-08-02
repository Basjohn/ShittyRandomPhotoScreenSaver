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
- No visualizer optimization begins until the user explicitly approves a named restored build and the stronger baseline in this plan is frozen.

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
6. Obtain explicit operator A/B confirmation for Bubble and Spectrum against `6f188ad` behavior.
7. Immediately freeze the mandatory approved baseline and stronger goldens described below.
8. After baseline capture, remove the now-unused visualizer lane facades and generic scheduler integration unless another proven production owner exists.
9. Repair the remaining `CustomLayoutManager` ownership and Edit-save-to-reload call-stack boundary.
10. Prove Settings and Edit recreation in normal and Media Center variants.
11. Rerun first-frame and mode-switch poison protection.
12. Recover and document the two adversarial lane findings previously reported by Codex.
13. Resume only the explicitly allowed Phase 5 visualizer optimizations described below.
14. Resume remaining Phase 5 work in order.
15. Close Phase 5 only after the complete installed matrix passes.

# Investigation Ledger

## CF-01 — Persistent visualizer lane migration crossed a protected behavioral boundary

**Status:** concrete commit-boundary finding and rejected current production state. Behavioral recovery no longer waits for a speculative lane repair.

### Commit isolation

The persistent lane migration is isolated to:

```text
6f188adadabb77b1a9d47a0fe1685c86ad39fb77
→
666624d421b08f978c5f610571a078570150a1e7
```

`6f188ad` already contained:

- rollback of the failed 60 Hz/max-two Bubble batching design;
- one authored Bubble simulation step for every lane-free opportunity;
- operator-confirmed restored Bubble reaction and elasticity;
- ordinary general COMPUTE executor submission for shared audio analysis;
- ordinary general COMPUTE executor submission for Bubble simulation.

`666624d` introduced two distinct behavioral migrations:

1. shared `visualizer.audio_analysis` moved to one persistent managed lane;
2. Bubble simulation moved to a persistent Bubble lane.

Spectrum can regress through the shared audio lane. Bubble can regress through both the shared source lane and its own simulation-lane migration.

### Current decision

The persistent visualizer lane design is rejected in its current production form.

It achieved lower Task/Future/accounting churn, but it also produced:

- a hard lifecycle failure: a retired shared audio lane remains registered and blocks Settings/Edit recreation;
- operator-reported Spectrum and Bubble fidelity regressions.

Task reduction that fails lifecycle or authored visualizer feel is a failed optimization regardless of average handoff, worker duration, publication count, or rejection count.

Do not tune the lane until it looks right. Restore the exact known behavior first.

### Why counters and existing goldens did not clear it

The current evidence can show high throughput, cheap means, and zero rejected submissions while missing:

- irregular inter-publication gaps;
- source age at a visual tick;
- transient-to-first-visible timing;
- Bubble event-consumption timing;
- Bubble expansion/contraction trajectory;
- Spectrum visible holds and step size;
- lifecycle ownership after the lane is idle.

The Phase 2 replay uses `ImmediateComputeThreadManager`; worker and callback execute synchronously. It protects equations and mode-owned state after accepted input, not the production scheduler boundary.

### Behavioral recovery implementation

#### Recovery commit A — restore visualizer execution semantics

1. `widgets/spotify_visualizer/beat_engine.py`
   - restore `_schedule_compute_bars_task()` from `6f188ad` as the active production path;
   - use ordinary `ThreadManager.submit_compute_task()`;
   - preserve the old smoothing snapshot, callback ordering, token check, activation check, and `_commit_analysis_frame()` seam;
   - retain current runtime-generation annotations only when they are passive metadata and do not change callback order;
   - stop creating or consulting `_analysis_compute_lane`;
   - add no replacement cadence, priority, smoothing, queue, or retry logic.

2. `widgets/spotify_visualizer/tick_pipeline.py`
   - restore direct Bubble submission from `6f188ad`;
   - submit `_bubble_compute_worker` through the ordinary COMPUTE executor;
   - preserve one authored step per lane-free opportunity;
   - preserve token-checked publication and current event/energy payload semantics;
   - passive source/authored timestamps may remain only when they do not alter admission, worker arguments, or callback order.

3. `widgets/spotify_visualizer_widget.py`
   - stop constructing, starting, stopping, or diagnosing `BubbleComputeLane`;
   - restore the pre-lane worker/result ownership fields and cleanup behavior;
   - preserve current generation, activation, and first-frame rejection guards.

4. Tests
   - production shared analysis must not call `create_compute_lane()`;
   - production Bubble dispatch must not call `BubbleComputeLane` or `create_compute_lane()`;
   - Phase 2 goldens remain read-only;
   - the Bubble discrete-edge oracle remains active;
   - tests do not replace operator acceptance.

The generic scheduler may remain present but unreachable for the first installed A/B build so causality remains narrow.

#### Recovery commit B — remove rejected scaffolding

Only after operator confirmation and stronger-baseline capture:

- delete `widgets/spotify_visualizer/bubble_compute_lane.py`;
- remove visualizer lane tests and diagnostics that authorize only the rejected path;
- remove visualizer lane lifecycle accounting;
- remove `ComputeLaneScheduler` and ThreadManager integration if repository search shows no independently proven production consumer;
- otherwise retain it only for that proven consumer and remove every visualizer dependency;
- document the rejection and rollback in Phase 5 and Historical Bugs.

Do not leave inert lane shells indefinitely.

### Installed recovery comparison

Compare:

```text
reference: 6f188ad
recovery: current branch with Recovery commit A
```

Use the same settings, preset, audio device, display route, song/position where practical, and mode-switch sequence.

Required operator review:

- Bubble on quiet, sustained-bass, sharp-kick/transient-heavy, and dense/loud material;
- Spectrum attack, decay, between-source smoothness, and reliability;
- Bubble → Spectrum → Bubble;
- pause/resume;
- transition overlap;
- Settings/Edit after lane removal.

The operator decides whether behavior is restored. Measurements support that decision and cannot overrule it.

# Mandatory approved visualizer baseline and stronger goldens

**Status:** blocked until the user explicitly states that Bubble and Spectrum are correct, ideal, restored, or otherwise approved on a named recovery build.

Stronger goldens are mandatory after that approval even if no further visualizer optimization is considered safe. Their minimum value is to act as better hazard lights.

## Approval trigger

The baseline may be created only after an explicit user statement approving both Bubble and Spectrum on an identified commit/build.

Record verbatim or faithfully quote:

```text
approval date
approved commit SHA
version/build identity
operator acceptance statement
```

Do not infer approval from silence, absence of complaint, green tests, or a short run.

## Baseline identity manifest

Create one immutable baseline id, for example:

```text
visualizer-approved-YYYYMMDD-<short-sha>
```

Freeze:

- commit SHA and version;
- normal or Media Center runtime variant;
- Windows version;
- Python, PySide/Qt, GPU, driver, CPU, and audio device identity;
- audio sample rate, block size, and relevant capture configuration;
- complete normalized visualizer settings payload;
- active preset files and SHA-256 hashes;
- display routes, resolutions, refresh rates, DPR, and visualizer owner display;
- selected scenario ids;
- fixture and output hashes;
- approval statement.

The approved commit remains a permanent comparison point after later baselines exist.

## Extend the existing Phase 2 framework

Use and extend:

- `tools/visualizer_replay.py`;
- `widgets/spotify_visualizer/replay_runtime.py`;
- `tests/fixtures/visualizer_replay/`;
- `tests/goldens/visualizer_replay/`;
- `tests/test_visualizer_replay.py`.

Do not build a second visualizer implementation or unrelated golden framework.

Keep the current `v1` logical goldens unchanged. Add a separately versioned approved-live/scheduler layer rather than overwriting Phase 2 history.

## Golden Layer A — exact logical state

Retain the existing deterministic feature fixtures and exact canonical JSON comparison.

Add approved-baseline captures for at least:

- raw and smoothed analysis bars;
- continuous energy bands;
- pre-AGC and Bubble-specific energy feeds;
- transient/onset state and consume-once edges;
- Spectrum target/displayed bar state;
- Bubble dispatch energy, pulse, settings, task token, and dt;
- Bubble logical simulation result and render-state payload;
- mode activation/reset state;
- runtime, engine-generation, and activation identity.

Use exact normalized comparison where clocks, random state, fixture input, and execution order are deterministic. Use narrowly documented numeric tolerances only where exact equality is impossible.

Layer A protects equations and state transitions. It does not authorize scheduler changes.

## Golden Layer B — production-scheduler temporal behavior

Add a scheduler-shaped mode to the existing replay/harness that uses the approved production admission and callback path rather than `ImmediateComputeThreadManager`.

It must preserve the actual approved executor semantics while allowing controlled timing injection around the real seams.

Inputs must include:

- existing Phase 2 feature fixtures;
- deterministic PCM or captured post-audio-worker fixtures for silence, isolated impulse, periodic beats, sustained bass, sustained treble, broadband/dense material, gradual ramp, sudden volume step, and irregular source cadence;
- Bubble-focused sharp transient, sustained-body, and dense/loud sequences;
- Spectrum-focused attack/decay and rapidly changing contour sequences.

Operator-selected real music segments may be retained as local evidence fixtures with hashes and scenario metadata. Do not commit copyrighted audio unless ownership and repository use are explicitly approved; derived feature/PCM fixtures and local evidence references are acceptable.

Exercise:

- ordinary approved executor load;
- controlled worker handoff jitter;
- controlled long-tail worker delay;
- GUI stalls;
- image transitions;
- 60 Hz and high-refresh presentation;
- dual-display and one-display routes;
- Bubble → Spectrum → Bubble;
- pause/resume;
- cold start, Settings recreation, and Edit recreation;
- normal and Media Center variants.

Capture per source sequence:

```text
source_sequence
source_timestamp
capture_to_submit_ms
submit_to_worker_start_ms
analysis_execution_ms
worker_complete_to_commit_ms
inter_publication_ms
source_age_at_visual_tick_ms
source_age_at_gpu_push_ms
source_sequences_skipped
first_visible_response_ms
maximum_visible_hold_ms
maximum_per_tick_visual_step
attack_rise_time_ms
decay_and_settling_time_ms
Bubble_discrete_edge_to_first_visible_ms
Bubble_expansion_contraction_trajectory
Spectrum_target_and_display_trajectory
runtime_generation
engine_generation
activation_id
```

Report distributions and bounded worst cases:

- p50;
- p90;
- p95;
- p99;
- maximum;
- over-threshold counts;
- skipped/lost sequence counts;
- duplicate event-consumption counts.

Averages alone are forbidden.

Temporal acceptance envelopes are derived from repeated runs of the approved build and must document their rationale. They may not be widened merely to let a proposed optimization pass.

## Golden Layer C — installed operator visual manifest

Create a manifest of the exact approved manual scenarios:

- Bubble quiet/low-energy response;
- Bubble sustained bass/body;
- Bubble sharp kicks and transient-heavy material;
- Bubble dense/loud expansion, elasticity, contraction, and settling;
- Spectrum attack speed;
- Spectrum decay and smoothing;
- Spectrum reliability through rapidly changing contours;
- Bubble → Spectrum → Bubble;
- pause/resume;
- transition overlap;
- Settings/Edit recreation;
- normal/Media Center variants where relevant.

For each scenario record:

```text
scenario id
input/track reference and hash where available
playback segment or fixture interval
settings/preset hash
display/refresh route
runtime log folder
optional frame-timestamped screen recording
operator result and notes
```

The visual manifest preserves what was actually approved. It does not claim to numerically replace perception.

## Negative-control requirement

The strengthened gate must be tested against known failed designs:

- the rejected 60 Hz/max-two Bubble batching implementation;
- the `666624d` persistent shared-analysis/Bubble-lane checkpoint when reproducible.

The new gate must either fail those designs or produce an explicit hazard signal that clearly distinguishes them from the approved baseline.

If it cannot distinguish a known bad build, it is not yet strong enough.

## Golden mutation rules

- Never regenerate automatically.
- Never update expected output in the same behavioral change being tested.
- Never generate from a build the operator has reported as regressed.
- Keep every prior approved baseline immutable.
- A new baseline requires an explicit user-approved intentional behavior change.
- Golden-update tooling remains locked behind explicit acknowledgement flags and a declaration containing `approved: true` and `goldens: true`.
- Infrastructure and optimization branches verify only.

## Baseline completion gate

The stronger baseline is complete only when:

- all three layers exist;
- manifests and fixture/output hashes are frozen;
- the approved build passes all layers;
- known failed designs trip the new hazard checks;
- the user confirms that the captured scenarios represent the approved Bubble and Spectrum behavior;
- rollback commit and baseline id are documented in `Current_Plan.md`, the Phase 5 report, and `Docs/Visualizer_Reference.md`.

# Future visualizer optimization envelope

No visualizer optimization is authorized before the approved stronger baseline above is complete.

The following are the only currently plausible optimization families. They are candidates, not commitments.

## Candidate A — reduce bookkeeping while preserving exact executor semantics

Potentially reduce per-task registry/UI-stat/Future allocation overhead around the existing approved general COMPUTE submission path without changing:

- admission timing;
- one-authored-step behavior;
- worker-pool selection;
- callback order;
- source sampling time;
- event consumption;
- publication timing;
- stop/generation semantics.

Examples may include sampled accounting, lighter internal task records, or avoiding diagnostics allocation when diagnostics are disabled.

This is the preferred first optimization candidate because it attacks overhead rather than visual behavior.

## Candidate B — remove duplicate or inactive work

Prove and remove only work with no visual contribution:

- inactive modes computing after deactivation;
- hidden or absent visualizers continuing mode-owned work;
- duplicate shared analysis per display;
- repeated unchanged config rebuilding;
- duplicate payload conversion/copying;
- diagnostics executing when disabled.

No source or logical edge may be dropped from the active mode.

## Candidate C — allocation and copy reduction inside an unchanged logical step

Consider bounded reuse of plain Python/native buffers, immutable packet structures, or vectorized/native math only when:

- numerical output remains within the approved exact/tolerance contract;
- object reuse cannot leak mode/generation state;
- callback order and timing remain within the approved temporal envelope;
- memory ownership remains explicit.

Do not trade retained high-water memory for fewer allocations without measurement.

## Candidate D — post-integration render-state coalescing

Later Phase 7 may coalesce newest render state only after every logical input has been integrated.

It may not:

- reduce source analysis cadence;
- skip Bubble authored simulation steps;
- consume discrete events without visible publication;
- derive cadence from paint;
- change mode equations.

## Candidate E — Spectrum presentation change

A Spectrum-only presentation bridge or interpolation layer is not presently authorized as a performance optimization.

It may be considered only as an intentional visual behavior change when:

- the approved baseline exists;
- source timing is already healthy;
- the user explicitly requests or approves the changed look;
- attack latency remains equal or better;
- a new approved baseline is created afterward.

## Explicitly not planned for production

Until separately proposed and explicitly user-approved after the stronger baseline:

- persistent visualizer lane substitution;
- dedicated Spectrum source lane;
- Bubble persistent scheduler lane;
- token buckets or cadence caps;
- source decimation;
- terminal-state batching;
- smoothing retuning disguised as optimization;
- paint-driven or transition-driven visualizer cadence;
- worker-to-paint acknowledgement;
- simultaneous shared-source and mode-simulation scheduler migration.

A future scheduler experiment, if ever attempted, must:

- live on an isolated branch or explicit development flag;
- change one causal boundary only;
- compare directly against the approved commit;
- pass all stronger goldens and negative controls;
- receive explicit operator approval before production adoption;
- have a one-commit rollback.

# P5.0 — Visualizer cadence and fidelity

- [!] Reject the current persistent shared-analysis and Bubble-lane production adoption.
- [-] Implement CF-01 Recovery commit A from `6f188ad` without tuning.
- [ ] Produce the installed `6f188ad` versus recovery comparison.
- [ ] Obtain explicit operator Bubble and Spectrum acceptance.
- [ ] Capture all mandatory approved-baseline layers immediately after acceptance.
- [ ] Prove the stronger gate detects known bad designs.
- [ ] Remove rejected lane scaffolding in Recovery commit B after acceptance and capture.
- [x] Reject the failed Bubble 60 Hz/max-two terminal-batching design.
- [x] Restore one authored Bubble step for every lane-free opportunity at `6f188ad`.
- [x] Add a source/discrete-edge-to-first-visible Bubble oracle for the rejected batching failure.
- [ ] Validate Sine, Oscilloscope, and Dev Curve after the shared source is restored.
- [ ] Attempt no optimization outside the approved envelope above.
- [ ] Require installed operator review before marking P5.0 complete.

# P5.1 — Delivery tails

- [-] Correlate owner-labelled transition gaps with event-loop lateness, queue/callback tails, update-request age, and per-display request-to-paint delay.
- [x] Preserve compositor transition names in owner telemetry.
- [ ] Attribute remaining transition-time p99/max gaps before changing shader or visualizer cadence.
- [ ] Reject repaint retries and transition-derived visualizer clocks.

# P5.2 — Latency truthfulness

- [x] Remove impossible uptime-linear visualizer ERROR values.
- [x] Separate Bubble source, simulation, render-state, and request-to-paint ages.
- [ ] Preserve passive source/visible timing telemetry through executor restoration.
- [ ] Validate separated ages in installed transition evidence.
- [ ] Feed truthful source/visible timings into Golden Layer B.
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

- the destruction barrier contains no `visualizer.audio_analysis` or Bubble lane;
- Settings proceeds to its dialog/recreation flow;
- Edit either proceeds or fails only on independently retained owners;
- ordinary executor tasks remain generation-visible and must cancel, complete, or reject publication before the barrier passes.

Do not build a complex engine-lease system solely to preserve a rejected visualizer lane.

If an engine, audio worker, ordinary executor task, or widget owner still survives after lane removal, add only the narrow ownership fix needed for that remaining owner.

## CUSTOM/Edit manager ownership

- [-] Trace both surviving `CustomLayoutManager` instances.
- [ ] Audit class-level active managers, global key filter, restack callbacks, menu state, scheduled single shots, local manager lists, shell callbacks, display/coordinator references, bound methods, closures, deferred pixmaps, and save/reload stack frames.
- [ ] Split Edit commit from engine-owned recreation where the current manager-owned stack retains managers.
- [ ] Stage 1 persists data, finishes sessions, destroys shells/overlay, clears class state, detaches managers, and returns an immutable reload intent.
- [ ] Stage 2 starts existing engine recreation only after the manager-owned call stack has unwound.
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
- a missing fresh frame keeps presentation hidden rather than showing stale or placeholder output.

## Lifecycle matrix

Run at least five alternating Edit and Settings cycles in normal and Media Center variants, including:

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
- [ ] For each, record interleaving, owner, failure, missing test, reproduction, repair, rollback, deterministic acceptance, and installed evidence.
- [ ] Current correctness, lifecycle, latency, memory, or fidelity issues remain in Phase 5 and Historical Bugs.
- [ ] If the exact findings are no longer recoverable, state that plainly and rerun the adversarial audit. Do not invent them.
- [ ] If the generic scheduler has no production consumer after Recovery commit B, document the findings before deleting it; do not preserve rejected architecture merely to justify the audit.

# Phase 5 gate

Phase 5 passes only when:

- CPU/task cost is materially lower without visualizer regression;
- p99/max delivery is equal or better;
- Settings and Edit recreation pass repeatedly;
- memory/VRAM/handle/thread ownership plateaus;
- no retired generation survives;
- no first-frame poison returns;
- Spectrum and Bubble are equal or better by deterministic evidence and installed manual review;
- the approved stronger baseline exists and catches known failed designs;
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
- newest render-state coalescing only after logical integration;
- injected GUI-stall tests;
- no producer paint waits;
- all work constrained by the approved stronger baseline.

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