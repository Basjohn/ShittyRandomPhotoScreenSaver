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
- Settings/Edit destruction remains fail-closed; no timeout extension, ignored owner, retry sleep, nested event pumping, or fake zero count.
- Runtime generation, engine generation, activation identity, first-frame authority, and owner-context GL deletion remain mandatory.
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

### Remaining lifecycle blockers

- [!] CUSTOM/Edit may still retain two `CustomLayoutManager` Python owners.
- [ ] Re-run Settings and Edit recreation now that the persistent audio lane is absent.
- [ ] Prove equivalent-state RAM, private commit, VRAM, handles, threads, resources, and owner counts plateau across repeated cycles.
- [ ] Preserve authoritative first-frame and generation/activation rejection through all recreation work.

## Required Work Order

1. Freeze `ff934616` as the current user-approved visualizer behavioural baseline.
2. Capture the mandatory stronger Bubble/Spectrum goldens described below.
3. Remove or rename no existing files while cleaning inert lane scaffolding.
4. Remove unused visualizer lane facades, diagnostics, tests, and generic scheduler integration only after repository search proves no valid production consumer remains.
5. Re-run Settings and Edit lifecycle matrices without persistent visualizer lanes.
6. Repair the independent `CustomLayoutManager` ownership/call-stack boundary if Edit still fails.
7. Complete delivery-tail, unchanged-media, cache-representation, and logging work.
8. Close Phase 5 only after installed normal and Media Center evidence passes.

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

# P5.4 — Recreation Ownership And Memory

## Visualizer lane result

- [x] Persistent visualizer lanes are absent from production behaviour.
- [ ] Confirm Settings and Edit destruction snapshots contain no `visualizer.audio_analysis` or Bubble compute-lane ownership.
- [ ] Confirm ordinary executor work cancels, completes, or generation-rejects before the barrier passes.

## CUSTOM/Edit manager ownership

- [-] Trace both surviving `CustomLayoutManager` instances if the failure still reproduces.
- [ ] Audit class-level active managers, global key filter, restack callbacks, menus, scheduled callbacks, local manager lists, shells, displays, coordinators, bound methods, closures, deferred pixmaps, and save/reload stack frames.
- [ ] Split manager-owned persist/finish/detach from engine-owned recreation.
- [ ] Stage 1 clears manager/class/display ownership and returns immutable reload intent.
- [ ] Stage 2 begins recreation only after manager-owned stacks unwind and captures no manager/display/shell/widget.
- [ ] Do not remove managers from barrier observation merely to pass it.

## First-frame invariants

For every recreation:

- retired generation reaches zero before replacement construction;
- replacement remains hidden until its own authoritative first frame;
- old callbacks, transitions, visualizer results, and cached state cannot satisfy readiness;
- Bubble and Spectrum use current engine generation and activation;
- `FadeCoordinator` remains the sole reveal coordinator;
- missing fresh data keeps presentation hidden rather than showing stale state.

## Lifecycle matrix

Run at least five alternating Edit and Settings cycles in normal and Media Center variants, including Bubble, Spectrum, Bubble → Spectrum → Bubble, playing/paused, transition-time teardown, pending image work, pending ordinary audio/Bubble executor work, dual display, and one selected display.

Every retired generation must reach zero QObjects, Python owner roots, resources, timers, animations, subscriptions, callbacks, tasks, lanes, visualizer owners, CustomLayoutManagers, registrations, pixmaps, textures, PBOs, and tracked GL bytes.

Equivalent settled RSS, private commit, dedicated VRAM, handles, threads, CPU, and GPU must stop rising approximately linearly per cycle.

# P5.5 — Cache Representations

Blocked by P5.4.

- [ ] Audit raw/scaled/display co-retention, exact-transform duplication, unused prefetch results, and eviction churn.
- [ ] Keep the 256 MiB production CPU-cache limit.
- [ ] Do not add pins or raise budgets without a proven readiness failure.

# P5.6 — Logging Hygiene

- [-] Keep detailed cache records in `screensaver_cache.log`.
- [-] Keep lifecycle ownership detail in `screensaver_lifecycle.log`.
- [ ] Add one authoritative startup record distinguishing `main` and `main_mc`.
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