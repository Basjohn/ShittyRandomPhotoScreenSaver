# Current Plan

Last updated: 2026-08-02

Active unfinished work only.

Stable architecture belongs in `Spec.md`. Durable safety rules belong in `Docs/Guardrails.md`. Detailed evidence belongs in the existing phase reports. Dated failures and rejected fixes belong in `Docs/Historical_Bugs.md`. Completed narratives should leave this file once their evidence is accepted and archived.

## Recovery Boundary

```text
branch: main
recovery baseline: 00edb57a3076b845cb8ee4b6cb7f36ea83411f0c
donor/reference only: 7376bb9bb380253f3bd14079e65d7bdbca062fad
current failed-evidence application checkpoint: 666624d421b08f978c5f610571a078570150a1e7
current evidence: logs/evidence_chest/08_01_666624d4_22_05/
owning report: Docs/phase_reports/P05_CPU_TASK_REDUCTION.md
```

The donor is read-only reference material, never a merge target. Phase 4 remains closed. Current failures are repaired under Phase 5 rather than reopening or discarding completed work.

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
- Average FPS and mean worker duration cannot hide p99/max delivery gaps, source holds, lost impulses, or visible stepping.
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
- Do not discard or overwrite unrelated in-progress Phase 5 work. Finish an atomic slice safely before changing lanes.

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
- [!] Spectrum is visibly less smooth and less reliable than before the latest Phase 5 work.
- [!] No run containing `CRITICAL [LIFECYCLE_BARRIER] timeout` may be described as accepted or successful.
- [!] P5.4 blocks P5.5 and Phase 5 closure.

## Required work order

1. Inspect and preserve the current working tree and retained Codex context.
2. Finish the currently atomic in-progress task safely; do not leave unused shells.
3. Keep active docs truthful and remove stale lifecycle pass claims.
4. Repair exact engine/lane ownership and prove the retiring audio-analysis lane is released.
5. Repair `CustomLayoutManager` ownership and the Edit-save-to-reload call-stack boundary.
6. Prove Settings and Edit recreation in normal and Media Center variants.
7. Rerun first-frame and mode-switch poison protection.
8. Resolve the shared analysis-lane fidelity risk and Spectrum regression without degrading Bubble or other modes.
9. Recover and document the two adversarial lane findings previously reported by Codex.
10. Resume remaining Phase 5 work in order.
11. Close Phase 5 only after the complete installed matrix passes.

# Investigation Ledger

Concrete source-level findings belong here as they are established. Suspicions remain labelled as hypotheses until runtime evidence distinguishes them.

## CF-01 — Persistent audio-analysis lane is a cross-mode fidelity boundary

**Status:** concrete architectural finding; exact contribution to the operator-observed Spectrum regression still requires installed comparison.

### What changed

Phase 5 moved the shared beat engine's `visualizer.audio_analysis` work from repeated general COMPUTE submissions to one persistent managed analysis lane. That lane computes and commits:

- raw bar output;
- engine-smoothed bars;
- continuous energy bands;
- audio-worker processing state;
- authoritative frame timestamp;
- engine generation and activation ownership.

This is not a Spectrum-only lane. It is the common live analysis source used by several modes.

No new or separate Spectrum lane is proposed here.

### Mode impact

- **Spectrum — high exposure**
  - Reads engine-smoothed bars from the shared analysis result.
  - Copies accepted bars directly to the displayed bar array.
  - Publishes a new Spectrum GPU state only when bars or another explicit presentation property change.
  - Irregular analysis publication can therefore appear as hold-then-step motion.

- **Bubble — high but visually masked exposure**
  - Its particle simulation has a separate authored simulation lane.
  - Its continuous energy, transients, onset/event state, and audio-worker control state still originate from the shared analysis pipeline.
  - Bubble may continue moving while its source energy is stale or uneven, making regressions strongly song-dependent and harder to diagnose by eye.
  - A healthy Bubble simulation-step counter does not prove healthy audio-source cadence.

- **Dev Curve — meaningful exposure**
  - Its solver consumes shared continuous energy and transient state each presentation tick.
  - Uneven source publication can change layer drive and transient response while geometric motion continues.

- **Sine Wave and Oscilloscope — partial exposure**
  - Raw waveform authority is updated directly from the consumed audio frame and is less dependent on the analysis lane for primary line motion.
  - Reactive glow, energy, transient width, onset envelopes, and related effects consume shared analysis state and can still regress.

- **Paused synthetic idle paths**
  - Do not establish live-lane fidelity because they use generated idle state rather than live audio analysis.

### Correction to the earlier hypothesis

`_target_bars`, `_visual_bars`, `_visual_smoothing_tau`, and `_apply_visual_smoothing()` still exist, but the recovery baseline and Phase 4 code already copied engine-smoothed bars directly into `_display_bars`.

Therefore:

- the unused visual interpolation helper is real technical debt and may be useful in the repair;
- its disconnection is not proven to be a recent Phase 5 regression;
- restoring it blindly is not a valid historical revert;
- the first comparison must be old executor publication versus current persistent-lane publication.

### Why the Phase 2 goldens did not stop this

The Phase 2 goldens protect deterministic logical equations and mode-owned output after a frame has been accepted.

The replay path:

- injects timestamped feature frames through `accept_analysis_frame()`;
- uses an immediate deterministic compute test double;
- executes worker and callback synchronously;
- does not advertise or run the production persistent compute-lane scheduler;
- does not reproduce lane handoff, shared-worker contention, publication jitter, long worker tails, newest-only source loss, or real callback timing.

The current persistent-lane unit test proves one packet can execute, commit, and disappear after stop. It does not prove:

- continuous publication cadence;
- source-to-visible latency;
- behaviour under irregular worker delay;
- two-display or multi-lane contention;
- Spectrum visible smoothness;
- Bubble input freshness;
- other-mode reactive extras.

Exact goldens can therefore remain green while live scheduling feel regresses.

### Important live-evidence interpretation

The latest installed logs show healthy average audio-lane throughput and cheap typical callbacks during long sections. That does not clear the lane:

- average publication rate cannot expose irregular inter-publication gaps;
- cumulative maxima show occasional much longer analysis execution than the mean;
- Spectrum directly exposes a long source gap;
- Bubble can conceal a source gap by continuing its own simulation against old energy;
- the logs currently lack per-publication interval and source-sequence evidence needed to assign the visible complaint conclusively.

### Required diagnosis before architecture changes

Add passive, bounded analysis-source telemetry:

```text
source_sequence
source_timestamp
runtime_generation
engine_generation
activation_id
capture_to_submit_ms
lane_handoff_ms
analysis_execution_ms
commit_ms
inter_publication_ms
source_age_at_visual_tick_ms
source_age_at_gpu_push_ms
source_sequences_skipped
lane_busy_rejections
scheduler_worker_occupancy
competing_lane_category
```

Report p50/p95/p99/max and bounded worst samples by mode. Do not emit per-frame INFO logs.

Compare at minimum:

1. recovery/Phase 4 general-executor path;
2. current persistent-lane path;
3. Spectrum alone;
4. Bubble alone;
5. shared audio lane plus Bubble lane;
6. dual-display ownership;
7. 60 Hz and high-refresh presentation;
8. controlled worker delays and GUI stalls;
9. normal and Media Center runtime.

### Best repair sequence

1. **Preserve one authoritative shared audio source.**
   - Do not create a separate Spectrum analysis authority merely because Spectrum exposes the fault.
   - Do not return to one Future/task per frame without evidence.
   - Do not allow old and new analysis commits to overlap unsafely.

2. **Fix source cadence or scheduler fairness where evidence points.**
   - If inter-publication gaps originate in lane scheduling, repair bounded fairness/priority or ownership in the existing scheduler.
   - Audio analysis must not be starved by Bubble or another high-rate lane.
   - Do not solve starvation by dropping authored Bubble edges or batching terminal state.

3. **Add presentation bridging for Spectrum only if source timing remains inherently irregular.**
   - Treat each authoritative analysis result as a newest target.
   - Interpolate visual bars on the existing visualizer presentation tick using real elapsed time.
   - Preserve fast attack and `spectrum_drop_speed` decay semantics.
   - Continue publishing while visual state is converging even without a new source packet.
   - Carry source generation and activation through target, visual, and displayed state.
   - Do not add a timer, worker, scheduler, retry, paint acknowledgement, or second source authority.
   - This is a targeted presentation improvement, not a blind restoration of dead code.

4. **Protect Bubble separately.**
   - Do not apply Spectrum visual interpolation to Bubble.
   - Measure audio-source age at every Bubble authored step.
   - Preserve every discrete scheduler edge and immediate first-visible attack.
   - Require Bubble manual comparison across quiet, bass-heavy, sustained, and transient-heavy tracks.

5. **Audit other modes.**
   - Sine/Oscilloscope: separate waveform age from energy/transient age.
   - Dev Curve: measure energy/transient source age and first visible response.
   - No shared-source change is accepted from Spectrum-only evidence.

### Required new validation layer

Keep the exact Phase 2 goldens. Add a scheduler-shaped fidelity gate using the real `ComputeLaneScheduler`:

- deterministic source frames;
- controlled handoff and execution jitter;
- real persistent analysis lane;
- shared audio plus Bubble-lane contention;
- 60/90/120/165 Hz presentation ticks;
- injected GUI stalls;
- transitions;
- source sequence tracking;
- first-visible response;
- maximum visible hold;
- maximum visual step;
- attack and decay timing;
- discrete-edge accounting;
- mode-switch and first-frame identity.

The scheduler-shaped gate supplements the goldens; it does not replace or rewrite them.

### Acceptance

- Shared-source inter-publication p99/max is bounded and explained.
- No unexplained long source holds under normal load.
- Spectrum has equal-or-better first-visible reaction and visibly smoother motion/decay.
- Bubble retains operator-confirmed reactivity, expansion, elasticity, and discrete-edge response.
- Sine/Oscilloscope waveform and reactive extras remain correct.
- Dev Curve energy/transient response remains correct.
- Phase 2 exact goldens remain unchanged unless an intentional, user-approved behaviour change is declared.
- Installed manual review is mandatory.

# P5.0 — Visualizer cadence and fidelity

- [-] Complete CF-01 source-cadence instrumentation and old/new comparison.
- [x] Reject the failed Bubble 60 Hz/max-two terminal-batching design.
- [x] Restore one authored Bubble step for every lane-free opportunity.
- [x] Add a source/discrete-edge-to-first-visible Bubble oracle for the rejected batching failure.
- [ ] Extend the oracle to shared audio-source age and persistent-lane contention.
- [ ] Add the scheduler-shaped all-mode gate described in CF-01.
- [ ] Resolve Spectrum reliability/smoothness with equal-or-better reaction latency.
- [ ] Validate Bubble with multiple song dynamics rather than one favourable track.
- [ ] Validate Sine, Oscilloscope, and Dev Curve reactive lanes.
- [ ] Require installed operator review before marking P5.0 complete.

# P5.1 — Delivery tails

- [-] Correlate owner-labelled transition gaps with event-loop lateness, queue/callback tails, update-request age, and per-display request-to-paint delay.
- [x] Preserve compositor transition names in owner telemetry.
- [ ] Attribute the remaining transition-time p99/max gaps before changing shader or visualizer cadence.
- [ ] Reject repaint retries and transition-derived visualizer clocks.

# P5.2 — Latency truthfulness

- [x] Remove impossible uptime-linear visualizer ERROR values.
- [x] Separate Bubble source, simulation, render-state, and request-to-paint ages.
- [ ] Validate the separated ages in installed transition evidence.
- [ ] Add CF-01 source-sequence and inter-publication truthfulness.
- [ ] Keep source-frame age diagnostic unless presentation is proven stale.

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

## Engine/lane ownership repair

- [-] Replace implicit shared-engine refcount authority with an exact per-widget lease or equivalent explicit ownership token.
- [ ] Record exact engine instance, owner widget, runtime generation, acquisition token, release state, lane identity, and activation.
- [ ] Acquire once and release once through one idempotent seam.
- [ ] Release independently of `_enabled`, visibility, or prior deactivation.
- [ ] Cleanup releases the exact acquired engine before clearing the reference.
- [ ] Never call `get_shared_spotify_beat_engine()` merely to release an engine the widget may not have acquired.
- [ ] Final lease release stops/cancels the audio-analysis lane and removes it from lifecycle ownership.
- [ ] One display cleanup may not stop another valid display's lease.
- [ ] A lane may not change runtime generation in place while an old lease exists.
- [ ] Duplicate stop/cleanup is harmless and cannot decrement another owner.

## Compute-lane terminal contract

Test:

- idle stop;
- pending stop;
- active stop;
- callback concurrent with stop;
- callback attempting resubmission;
- owner disappearance;
- generation invalidation during compute;
- duplicate lane ID;
- weak worker/callback release;
- worker exception;
- callback exception;
- duplicate stop;
- scheduler shutdown with live lanes;
- final engine lease release during publication;
- no lane resurrection after stop.

A stopped idle lane must disappear synchronously from lifecycle ownership. An active lane becomes terminal immediately and disappears after worker return without publication.

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
- pending audio analysis;
- pending Bubble simulation;
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
- visualizer engine leases;
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

# Phase 5 gate

Phase 5 passes only when:

- CPU/task cost is materially lower;
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

CF-01 may introduce a narrow Spectrum presentation bridge in Phase 5 only when required to repair the measured current regression. It must not pre-empt the broader Phase 7 architecture.

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
