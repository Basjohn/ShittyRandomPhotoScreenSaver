# Current Plan

Last updated: 2026-07-28

Active work only.

Stable architecture belongs in `Spec.md`. Durable safety rules belong in `Docs/Guardrails.md`. Detailed compositor design belongs in `Docs/Compositor_Architecture.md`. Dated failures belong in `Docs/Historical_Bugs.md`.

## Recovery Boundary

```text
main (based on baseline 00edb57a3076b845cb8ee4b6cb7f36ea83411f0c)
donor/reference only: 7376bb9bb380253f3bd14079e65d7bdbca062fad
```

The donor is read-only reference material, never a merge target. Evidence archives remain under `logs/evidence_chest/`.
## Non-Negotiable Gates

- Visualizer feel is protected before infrastructure changes.
- Average FPS cannot hide poor p99/max frame delivery.
- Settings/Edit must not introduce GL affinity failure.
- RAM and VRAM must plateau.
- CPU/task reduction cannot lower quality or reactivity.
- Producers never wait for paint.
- Donor branch is not merged wholesale.
- Existing files and documents are not renamed or moved.

## Status Legend

- `[ ]` not started
- `[-]` active
- `[x]` complete with evidence
- `[!]` blocked/failed
- `[~]` explicitly deferred

A phase is complete only with tests, runtime evidence, visualizer result, and rollback point.

## Completed Checkpoints

- [x] **Phase 0 / Gate 0:** freeze, evidence, and ownership inventory are complete; the Phase 1 checkpoint supplies the clean committed recovery point. See `Docs/phase_reports/P00_FREEZE_INVENTORY_AND_EVIDENCE.md`, `Docs/phase_reports/P00_SOURCE_OWNERSHIP_INVENTORY.md`, and `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.
- [x] **Phase 1 / Gate 1:** bounded passive frame, event-loop, task, CPU-image, GL-resource, and lifecycle-snapshot measurement validated without behavioural change. See `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.
- [x] **Phase 2 / Gate 2:** deterministic all-mode visualizer replay, protected baseline goldens, cadence-separation tests, quantitative metrics, and Spectrum/Bubble logical review artifacts are complete. See `Docs/phase_reports/P02_VISUALIZER_FIDELITY_LOCK.md`.
- [x] **Phase 3 / Gate 3:** full stop/destroy/recreate lifecycle, generation-and-manager stale-work rejection, and strict owner-context GL deletion are complete. The post-checkpoint dual-display program-ownership defect, competing generic-registry deletion fallback, and missing two-compositor test shape were corrected and recorded in the Phase 3 report. See `Docs/phase_reports/P03_GL_LIFECYCLE_AND_RECONFIGURATION.md`.
- [x] **Phase 4 / Gate 4:** exact byte/count CPU cache and prefetch bounds, per-compositor texture/PBO budgets, complete terminal transition release, exact-transform sharing, GUI-captured QPixmap accounting, and a 45-cycle/30-virtual-minute owner/allocator plateau are complete. See `Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md` and `Docs/phase_reports/P04_RESOURCE_LIFETIME_MAP.md`.

## Phase 5 — CPU and Task Reduction

- [ ] Categorize recurring tasks.
- [ ] Remove tiny high-frequency pool jobs.
- [ ] Stop hidden/static work.
- [ ] Coalesce duplicate publications.
- [ ] Batch/vectorize measured hotspots.
- [ ] Eliminate logging/control overhead.
- [ ] Preserve visualizer fidelity and frame tails.

**Gate:** materially lower CPU and task rate.

## Phase 6 — Explicit GPU Resource Store

- [ ] Small metadata-first store.
- [ ] Exact byte accounting.
- [ ] Context/share generation.
- [ ] Explicit leases/references.
- [ ] No GL calls under registry locks.
- [ ] Deterministic owner-thread deletion.
- [ ] Byte caps and eviction for unleased resources.
- [ ] Context recreation invalidation tests.

**Gate:** bounded reuse without stale handles.

## Phase 7 — Visualizer/Presentation Decoupling

- [ ] Narrow immutable visualizer render state.
- [ ] Simulation cadence independent of paint.
- [ ] No producer paint waits.
- [ ] Latest render-state coalescing.
- [ ] Preserve input processing and mode feel.
- [ ] Test injected GUI stalls.

**Gate:** visualizer remains correct under presentation pressure.

## Phase 8 — Narrow Single-Surface Compositor

- [ ] One surface per display.
- [ ] Immutable scene snapshot.
- [ ] Explicit draw order.
- [ ] No simulation or lifecycle ownership.
- [ ] GUI-local update coalescing only.
- [ ] Replace the two adaptive presentation workers with one GUI-thread, active-animation-only update mechanism per display; preserve no worker waits or paint acknowledgement.
- [ ] No compatibility mega-layer.
- [ ] Correct multi-display overlay behaviour.
- [ ] Cursor halo and visualizer remain smooth.

**Gate:** ownership improves without coupling clocks.

## Phase 9 — Local Transition Completion

- [ ] Source/destination/start/duration/easing only.
- [ ] Finalize locally after completed paint.
- [ ] Release source/temporary resources.
- [ ] No terminal transaction or pipeline acknowledgement.
- [ ] Test interruption, resize, Settings, Edit, topology.

**Gate:** transition completion is local and leak-free.

## Phase 10 — Remove Temporary/Legacy Scaffolding

- [ ] Remove dynamic forwarding.
- [ ] Remove duplicate runtime paths.
- [ ] Remove dead retry/backoff state.
- [ ] Remove obsolete metrics.
- [ ] Remove or migrate inert `workers.fft` settings/default leaves after a compatibility audit; do not restore a separate FFT process without contrary latency and reliability evidence.
- [ ] Prove no silent fallback.
- [ ] Keep one understandable runtime path.

**Gate:** code matches target architecture and no removed compatibility path remains silently active.

## Phase 11 — Full Validation

- [ ] Normal 30-minute run.
- [ ] Two-hour soak.
- [ ] Spectrum and Bubble fidelity review.
- [ ] CPU background load.
- [ ] Disk/decode background load.
- [ ] GPU background load.
- [ ] Mixed hostile load.
- [ ] Settings/Edit during animation.
- [ ] Multi-display/topology scenarios.
- [ ] RAM/VRAM plateau.
- [ ] p99/max frame gates.

**Gate:** candidate is better than both evidence versions.

## Phase 12 — Release Preparation

- [ ] Update canonical docs to match code.
- [ ] Archive benchmark evidence.
- [ ] Record budgets and known limitations.
- [ ] Identify rollback commit.
- [ ] Tag release candidate.
- [ ] Preserve donor history and evidence.

## Current Phase

```text
Priority: P0 — Reddit Helper Recovery
Queued recovery phase: 5 — CPU and Task Reduction
Branch: main
Last evidence: Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md
```

### P0 — Reddit Helper Recovery

Keep the resolved `R-02` launch-authority model: the saver atomically queues work, the installed interactive-only scheduled task starts the ephemeral helper, the helper waits for the user shell, and saver teardown never waits for helper completion.

Ownership for this pass is explicit: `scripts/SRPSS_Installer.iss` owns the durable ProgramData tree, scoped ACLs, helper binary, and task registration; `core/windows/reddit_helper_bridge.py` owns spool capability and atomic enqueue; `core/windows/reddit_helper_runtime.py` owns heartbeat/session/launch reconciliation; `helpers/reddit_helper_worker.py` owns bounded logging and queue processing; `tools/reddit_helper_task_harness.py` plus focused tests own recovery proof.

**First implementation slice:** build disposable red fixtures for the four failure shapes, then add the shared bounded-log and spool-probe primitives. Do not mutate live ProgramData or installer ACLs until those fixtures fail for the current code.

- [ ] **P0.0 — Freeze the failure matrix and rollback boundary.**
  - [ ] Capture bounded fixtures for: an already-oversized `reddit_helper.log`/`scr_helper.log`; stale or unwritable `.bridge_ready`; pending `.json` plus abandoned `.tmp`/retry/terminal queue files; and a ProgramData tree writable by only one of SYSTEM or the scheduled-task user.
  - [ ] Assert the current bad outcomes explicitly: bridge unavailable, launch cooldown masking non-launch, helper startup before logging is available, queued work stranded, terminal debris retained, or manual ownership repair required.
  - [ ] Preserve the current task contract (`SRPSS_RedditHelper`, `InteractiveToken`, least privilege, on-demand, ephemeral) and record a direct per-file rollback list before implementation.
- [ ] **P0.1 — Bound both helper log writers before startup.**
  - [ ] Give `reddit_helper.log` and `scr_helper.log` one shared size/backup/retention policy with a hard total-byte bound.
  - [ ] Rotate or recover an oversized existing file before opening it for the next append; logging failure must remain loud but must not prevent queue reconciliation or helper startup.
  - [ ] Keep diagnostics privacy-safe and bounded; do not emit unbounded full command/URL payloads or create a new logging owner.
- [ ] **P0.2 — Replace sentinel authority with a real spool capability check.**
  - [ ] Stop treating a rewritable `.bridge_ready` file as bridge authority; use a unique same-directory atomic create/write/replace/read/delete probe so stale ownership cannot poison availability.
  - [ ] Make `.bridge_ready` optional structured diagnostics only, with schema, writer identity, timestamp, and expiry if retained.
  - [ ] Invalidate cached readiness after any real enqueue/probe failure and retry through bounded backoff; do not silently return success from stale `_SPOOL_READY` state.
- [ ] **P0.3 — Make queue recovery deterministic and bounded.**
  - [ ] Define one queue-entry schema and validate action, token, timestamps, size, retry state, and expiry before dispatch.
  - [ ] Reconcile abandoned `.tmp`, legacy `.retry`, corrupt, expired, and failed entries at helper startup; preserve recoverable queued URLs, quarantine malformed work, and age/count-cap terminal artifacts.
  - [ ] Preserve current duplicate suppression and add a durable processing/receipt rule across helper restart; prove no silent loss, bound duplicate-launch risk at the external shell-acceptance crash boundary, and make every terminal removal or quarantine reason observable.
  - [ ] Bound queue entry bytes, live entry count, terminal count, and total spool bytes so a damaged producer cannot recreate the oversized-file failure through the queue.
- [ ] **P0.4 — Move ProgramData ownership to the installer with least privilege.**
  - [ ] Pre-create only `url_queue`, `helper_signals`, and `logs` as cross-principal writable paths for SYSTEM and the installed task user, with Administrators retaining recovery authority.
  - [ ] Keep the helper executable, presets, sounds, and ProgramData root non-writable to ordinary `BUILTIN\Users`; do not solve recovery by granting write access to the whole SRPSS tree.
  - [ ] Make install/upgrade idempotently reconcile the three writable directory ACLs without deleting pending queue entries or requiring `takeown`, manual `icacls`, or administrator takeover after installation.
  - [ ] Verify fresh install, upgrade from the broad inherited ACL shape, and one-sided SYSTEM/user ownership fixtures.
- [ ] **P0.5 — Add runtime-shaped recovery automation.**
  - [ ] Extend the helper harness with a disposable ProgramData root and fault injection for all four failures; it must never write test breadcrumbs into the real production helper logs.
  - [ ] Prove helper restart, heartbeat replacement, queued-link delivery through an injected opener, terminal cleanup, bounded disk use, and no silent authority fallback; keep the clipboard safety net observable and non-authoritative.
  - [ ] Keep the existing real Windows task register/query/run/delete smoke test as a separate launch-authority bar; add a read-only installed-task/ACL audit for packaged validation.
  - [ ] Run the four failures individually and as one sequential recovery scenario, then rerun the normal helper lifecycle/unit suites.
- [ ] **P0.6 — Record closure evidence.**
  - [ ] Write `Docs/phase_reports/P0_REDDIT_HELPER_RECOVERY.md` with the owner map, before/after failure matrix, ACL contract, disk bounds, commands, packaged Windows result, known limitations, and direct rollback.
  - [ ] Update `R-02`, `Docs/Harness_Index.md`, `Docs/Contracts.md`, and `Index.md` only with the final validated contract; remove this P0 section from `Current_Plan.md` after the gate passes.

**P0 gate:** helper restart and queued-link delivery recover deterministically from all four failure shapes without silent fallback, unbounded logs, stale bridge authority, or manual ownership repair.

### Queued Phase 5 continuation

- [ ] Inventory every recurring operation and record trigger, frequency, thread, typical/p95 duration, allocations, queue delay, coalescing eligibility, hidden/static behavior, and cross-display duplication.
- [ ] Use the 2026-07-28 live run as the first Phase 5 owner baseline: 101.2 compute submissions/second, led by `visualizer.bubble_simulation` at 68.9/s and `visualizer.audio_analysis` at 32.2/s, with `uncategorized` at 0.85/s; reduce the measured owners without reducing visualizer fidelity.
- [ ] Preserve the 2026-07-28 visualizer diagnostic boundary: Bubble soft/medium/loud drift remained monotonic and all 66 replay goldens plus 17 first-frame/mode-switch poison oracles passed, while Spectrum's visible-smoothing concern correlated with 44–88 ms tick/latency gaps at image-transition boundaries. Remove the shared scheduling gaps in Phase 5 without retuning Spectrum smoothing or Bubble elasticity unless new mode-owned evidence appears.
- [ ] Establish idle, visualizer, transition, image-decode, and controlled background-load baselines for process CPU, GUI event-loop delay, task submissions, queue depth, callback tails, and duplicate/stale publication.
- [ ] Reconcile tracked CPU/GL bytes against RSS, private commit, and driver VRAM; specifically explain sustained RSS above roughly 900 MiB, multi-GiB private commit, driver VRAM above roughly 500 MiB, and ResourceManager unknown-byte entries without raising budgets.
- [ ] Remove tiny recurring pool jobs whose queue/callback overhead exceeds useful work; keep Qt/GL mutation on the GUI/context owner and coarse I/O/decode/measured computation on workers.
- [ ] Measure and attribute the two per-display adaptive presentation workers without optimizing or entrenching them; Phase 8 owns their removal in favor of GUI-local active-animation scheduling.
- [ ] Coalesce duplicate scene invalidations, visual render-state publication, geometry updates, stale image results, metadata refresh, and deletion requests without dropping audio impulses, stop/release, topology, or settings events.
- [ ] Stop recurring work when its owner is hidden or static, and require near-zero idle general-pool submissions outside justified monitoring.
- [ ] Batch/vectorize only measured Python-heavy hotspots; do not add Python threads or multiprocessing without latency, memory, and GIL evidence.
- [ ] Rerun the protected visualizer replay/runtime lock and Phase 4 resource gate after each optimization slice; require lower task/CPU cost with equivalent or better p99 frame delivery and no new synchronization.
- [ ] Record the task inventory, before/after evidence, unsupported platform measurements, and direct rollback in `Docs/phase_reports/P05_CPU_TASK_REDUCTION.md`.

## Deferred Until Recovery Passes

- new production widget families;
- partial GL reinitialization;
- speculative quality scaling;
- architectural cleanup unrelated to measured recovery;
- donor feature promotion without isolated evidence.

## Plan Hygiene

- Remove completed detail after evidence is archived.
- Do not keep benchmark narratives here.
- Do not copy stable contracts from `Spec.md`.
- Do not add provider-specific feature backlogs.
- Do not rename this file.

USER TASK BOX. ADD ITEMS BELOW INTO PLANNED STEPS AND EMPTY BOX. NEVER EVER DELETE THIS BOX AS A WHOLE OR THESE INSTRUCTIONS, ONLY PROPERLY ADOPTED IDEAS, YA GOBLIN ASS BITCH.
#######
#######
