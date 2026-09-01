# Current Plan — Qt Quick Production Migration

Last updated: 2026-09-01

## Current checkpoint

**PHASE H CLOSED. PHASE I ACTIVE.**

The production Qt Quick authority cutover, post-cutover functional/runtime correction work, and heavy-load H performance acceptance are complete at the current source checkpoint. The detailed H acceptance record is preserved in:

- `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md`
- `Docs/Historical_Bugs/README.md`
- `Docs/QtQuick_Migration/Post_Cutover_Operator_Observation_Ledger_2026-08-30.md`
- `Docs/Guardrails/Performance_Optimization_Contract.md` — canonical post-H performance admission/acceptance rules and modest/heavy reference envelopes.
- `Docs/Tooling_Audit_2026-09-01.md` — current I keep/delete/migrate authority for operator tools; production/tool boundary is protected by R-72.
- the superseded H5c/R6/R7 checkpoint documents retained for provenance.

Do **not** repopulate the active work queue with hundreds of stale completed H sub-items. Preserve H as a compact **completed checklist** here and keep the detailed evidence in its closure/historical records. If later evidence falsifies an accepted H contract, reopen the smallest demonstrated owner/incident and repair it; do not revive H wholesale.

**Checklist discipline is mandatory:** every phase in this plan has an explicit checkbox list. Completed phases keep a compact checked closure list; the active phase owns detailed actionable checkboxes; queued phases keep enough unchecked acceptance/work items that the next agent can enter them without reconstructing intent.

### Test-run qualification at H closure

The complete test tree was reconciled against current production/source authority. The closure environment has `pytest` and NumPy but does **not** have PySide6 or PyOpenGL, and `tests/conftest.py` imports PySide6 unconditionally. Therefore no new Qt aggregate pass count is claimed here.

The canonical maintained destination profile is now:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

`h-destination` remains a temporary compatibility alias only. The **first Phase-I gate** is to run `destination` in the normal project environment with PySide6/OpenGL available. A red is evidence to classify; it is never permission to restore a deleted QWidget/GL owner or a retired fallback.

## Non-Blocking Auxiliary Work — live session queue

This is the high-visibility owner for bounded parity/polish issues being worked alongside I/J. These items do **not** block unrelated architecture work, but they must not disappear into chat history. Status discipline is strict: `[ ]` open, `[~]` implemented/analysed but **AWAITING VALIDATION**, `[x]` only after operator validation or a purely non-visual evidence task is conclusively closed. Do not promote `[~]` to `[x]` merely because source/tests look plausible.

- [x] **Bubble lifecycle fades — keep them.** Operator likes the fades visually, and paired logs show the recurring hitch class predates the fade slice: every sampled Gen2 collection aligned with a Bubble wall-clock gap while Bubble compute/FPS/cadence counters stayed healthy. The fades are scalar opacity/lifecycle state only and are not an evidence-backed removal target.
- [ ] **Bubble hitch root cause — J performance debt.** Attribute both GC-correlated and remaining non-GC stalls without lowering authored cadence/reactivity. New evidence: sampled Gen2 pauses around ~41–68 ms align with Bubble wall-clock gaps, newer/lighter-run Gen2 events can collect zero objects, and rolling/internal Bubble counters can miss the stop-the-world interval. Preserve this evidence in the performance guardrails and instrument pause/wall-clock attribution before changing collector policy.
- [x] **Card Shadow Extra Offset opposite-edge invariant.** Operator physically confirmed the third R-73 geometry mechanism no longer steals shadow coverage from the opposite edge when Extra Offset grows in the selected direction.
- [x] **Card shadows must never overpaint sibling widget content.** Operator physically validated the display-level ordinary-shadow underlay: close/overlapping widgets no longer allow a later sibling shadow to paint over earlier card content. R-74 owns the mechanism.
- [~] **Visualizer global card-shadow projection — AWAITING VALIDATION.** Retained Visualizer receives global shadow enabled/color/opacity/blur/direction/Extra Offset without per-tick settings polling; verify its physical card shadow and directional growth independently of the ordinary-card underlay slice.
- [~] **Clock separator parity — AWAITING VALIDATION.** Shared analogue/digital separator now targets 80% of text alpha, keeps the mode-neutral 1–8 px thickness contract, and has its own cheap retained hard shadow driven by the global text-shadow color/direction/offset (no MultiEffect/layer capture). Also validate analogue placement remains ~20% closer to the face without footer overlap.
- [ ] **Text-shadow extension option.** Keep the current cheap duplicate-glyph shadow as default. If a continuous/extruded directional text shadow is desired, implement a bounded duplicate-glyph trail rather than MultiEffect; do not add soft blur/offscreen capture casually.
- [~] **Startup widget flash-proof gate — Visualizer skip FIXED + PHYSICALLY VALIDATED; ordinary-family flash not reproduced (watch).** Instrumented single-display `main_mc` runs proved the orchestration was correct (ordinary roots created before prime, riding `fadeOpacity * startupRevealOpacity`) and isolated the only "skip" to the Visualizer: its GL bars are a custom `QSGRenderNode` that ignored the QML root's inherited opacity (so `startupRevealOpacity` faded only the card shell while the bars popped), and its authored scene fade was never wired into the Quick presentation. Fixes (Qt Quick-native, no legacy QWidget/`ShadowFadeProfile`/`push_spotify_visualizer_frame`): (1) `node.py` folds `inheritedOpacity()` into `content_fade` at the single render seam, only while fading; (2) `quick_display_visualizer_owner.py` eases `scene_fade` 0→1 once per activation via the pacer-driven `sync_present` + clock (no new timer). Operator confirmed the Visualizer now fades in cleanly with the cohort. Regression bars in `tests/test_qtquick_visualizer_fade_authority.py`. See `Docs/QtQuick_Migration/J_Reveal_Startup_Composition_Decomposition_2026-08-31.md` Area 1.
- [x] **Desktop -> first wallpaper -> synchronized widget reveal — PHYSICALLY VALIDATED.** The earlier "no crossfade at all" was a prior build; current source crossfades correctly. Cold runtime only (`runtime_generation == 0`): each selected `QScreen` is captured once before any Quick window is shown and published only as retained staging state (into `scene_controller.presentation_image`, so the first wallpaper resolves the crossfade branch, not direct-publish). Fixed 1300 ms retained Crossfade; only all-display finalization starts the shared reveal. R-63 non-exact-cover/1 px overscan preserved; no recurring timer/cover window/second surface. Operator + `[STARTUP_DESKTOP]` logs confirm the desktop→wallpaper crossfade. Watch multi-display cold starts for consistency.
- [~] **Edit-mode X / close-button contract — AWAITING VALIDATION.** Surviving source/tests implement session-local behavior: duplicate -> remove only that duplicate; singleton ordinary/casual widget -> working OFF only; Save commits; Cancel restores; no immediate provider destruction/persistence. Physically revalidate before closure.
- [ ] **Media parity recovery.** Re-audit the landed Media alignment/thickness/seek-bar alignment/seek-length changes from surviving source/history before modifying them. The exact vanished-chat values/intent are not to be guessed. Preserve event-owned Media runtime architecture while correcting presentation.
- [~] **Reddit edit chrome / stale-envelope geometry seam — AWAITING VALIDATION.** Audit found a real H9 geometry seam rather than oversized handle primitives: uniform-transform Reddit/Reddit2 could render a correctly centred card inside an old aspect-mismatched committed outer rect while CUSTOM outlined/resized the invisible letterbox envelope. Admission now canonicalizes the session/edit rectangle to the actual visible retained-card bounds at the same centre/scale; Save retires only dead geometry and Cancel leaves visible pixels unchanged. The unused `custom_layout_runtime_vertical_content_resize` descriptor flag was removed because it falsely advertised a retired runtime geometry contract. Validate Reddit + Reddit2 handles and corner/wheel scale; if bars remain tall, capture the frame/card mismatch rather than changing handle primitives blindly.
- [ ] **Reddit ordinary/non-CUSTOM content contract.** Ordinary adjustment/resize interaction must preserve Reddit's newest-message cycling/content behavior rather than accidentally mutating geometry; audit Reddit and Reddit2 together.

## H closure summary

### H completed checklist

- [x] One selected physical display -> one standalone `QQuickWindow` -> one threaded Quick scene graph/runtime scene.
- [x] Old `DisplayWidget` / QRhiWidget / `GLCompositorWidget` physical presentation authority remains deleted.
- [x] H1a/H1b lifecycle/recreation/terminal retirement accepted.
- [x] H2/H3/H3b/H4 family/product runtime semantics accepted.
- [x] H5a/H5b visualizer routing/topology accepted physically.
- [x] H5c visualizer reactivity/performance accepted at the heavy-load H boundary; residual optimization debt moved to J.
- [x] H6 Media CUSTOM Settings lock semantics accepted.
- [x] H7 visible Exit response accepted.
- [x] H8 middle-click same-mode preset cycling/Custom round-trip accepted physically.
- [x] H9 ordinary-family uniform resize accepted, including absolute persisted 40% floor and Gmail whole-card scaling.
- [x] R6 native-`QCursor` Halo architecture accepted and protected.
- [x] R7 transactional image admission/prefetch wake accepted; timer/manual transitions are the same performance class.
- [x] R-63 black-flash prevention accepted with `black=0`; bounded mixed-DPR shared-edge pixel overshoot tolerated rather than risking exact-cover fullscreen promotion.
- [x] Media fast polling retired in favor of event ownership plus slow reconciliation/watchdog.
- [x] Final heavy-load Visualizer audio lane/state work materially reduced GC frequency without sacrificing logical cadence/reactivity.
- [x] H closure docs/tests reconciled enough to hand authority to the phase-neutral `destination` profile and Phase I cleanup.

The final heavy-load performance evidence is intentionally **not** an invitation to chase counters further inside H. Representative accepted evidence:

```text
Visualizer logical publication: ~89-90 Hz when active
Typical snapshot age:           ~18-22 ms
Audio analysis mean compute:    ~1.86 ms
Audio callback work:            ~0.067 ms
Generic per-frame Future path:  0
Final heavy-load gen-0 rate:    ~9.8 collections/s
Final heavy-load gen-2 rate:    ~0.39/min
Residual deep gen-2 pauses:     ~130-146 ms in that run
```

Those residual deep pauses are real J/end-performance debt. They are **not** permission to reduce authored work, cadence, freshness, response amplitude, motion, viewport scaling, newest-state semantics, or visible fidelity.

## Golden guardrails carried into I/J

Performance work in I/J must also follow `Docs/Guardrails/Performance_Optimization_Contract.md`. That document owns the permanent rule that **freshness/reactivity and latency-tail quality outrank prettier aggregate counters**, plus the 2026-09-01 heavy/modest reference envelopes.

### 1. Visualizer reactivity/freshness is sacred

Priority order remains binding: authored fidelity/reactivity outranks lifecycle counters, frame-pacing averages, task-count elegance and FPS cosmetics.

Never “fix” performance or extreme geometry by:

- lowering the authored/logical Visualizer cadence;
- adding a debounce/catch-up FIFO/backlog between current source and newest-state presentation;
- allowing stale source/snapshot age to rise while pixels continue;
- globally compressing Bubble head radius, pulse amplitude, motion, Ghost/history displacement or another mode's authored reaction as viewport extent grows;
- applying a second `baseline/current` or `1 / viewport_extent` compensation to state already normalized into renderer-content coordinates;
- retuning DSP/gain/cold-play response to hide a presentation/geometry defect;
- restoring per-frame generic `Future`/task submission for audio analysis;
- removing the stable previous-bars packet snapshot merely to improve allocation counters without a replacement correctness proof.

**R-69 is the golden Bubble scaling lesson.** Canonical, wide and tall CUSTOM geometry must preserve the same authored response character. Bubble's renderer-facing head radius stays the authored fraction of actual card height. Ghost consumes already-normalized history exactly once. The accepted compact ripple-wake projection is a separate effect and must not be generalized to head/Ghost state. If an extreme full-expansion head is visually too large, fix only a proven upper visual tail without flattening the full response curve.

Apply the same reasoning to Spectrum/Oscilloscope/Sine/DevCurve: geometry adaptation may reframe/reflow/smooth presentation, but may not quietly weaken musical response.

### 2. Visualizer audio compute ownership

Current accepted path:

```text
one shared BeatEngine
-> one persistent serial visualizer.audio_analysis compute lane
-> one in flight + newest pending source replacement
-> retained detached DSP state across ordinary frames
-> rebuild only at real config/activation/reset epoch boundaries
-> immutable newest logical/render publication
```

No generic Future fallback. Lane creation failure must be loud. Config/reset crossing an in-flight computation fences the stale result. Keep the small stable previous-bars tuple because the live silence path may mutate the backing list in place.

Further GC work belongs near the end of J and must start from allocation/lifetime evidence. Do not tune collector thresholds simply to make counters prettier, and do not trade response latency/reactivity for fewer collections. 2026-09-01 operator-log comparison now supplies a concrete symptom seam: every observed generation-2 collection in both sampled runs coincided with a Bubble wall-clock tick spike (~41-68 ms GC pauses / ~46-64 ms Bubble dt spikes), including newer-run Gen2 scans that collected zero objects. The two log builds contain no Bubble runtime change between them, so this is evidence of a pre-existing stop-the-world hitch class, not evidence that the later lifecycle fades caused it. Investigate retained allocation/lifetime roots and visibility of pause telemetry; do not remove the scalar-only fades or relocate forced collections without a mechanism.

Historical performance record: `Docs/Historical_Bugs/R-71_Visualizer_Audio_Per_Frame_Task_And_DSP_State_Allocation.md`.

### 3. R-63 seam / black-flash priority

The no-black-flash contract outranks exact shared-edge pixel perfection.

Current native evidence on the operator's mixed-DPR pair showed Display 0's intended exterior/top overscan rounding to a `2561`-device-pixel window over a `2560`-pixel monitor, overlapping Display 1 by one device pixel. That explains the intermittent seam pixel.

A **bounded 1px overshoot is acceptable** while `black=0` remains true. Any later refinement must derive device-space coverage from actual monitor rectangles/DPR and remain valid across different resolutions, coordinates, monitor ordering and DPR combinations (including 1.0/1.25/1.5/1.75/2.0 and mixed-DPR). Never hard-code the current monitor pair, force exact cover, or remove R-63 overscan generically.

### 4. CUSTOM resize authority

Ordinary CUSTOM scale is absolute against stable authored/preferred size, persisted across sessions, with shared **40% floor**. A new session must not treat an already-scaled committed rectangle as a fresh 100% baseline.

Reddit/Reddit2, Media and Gmail use whole-card retained `uniformScaleTransform`; fixed chrome/text/rows/spacing scale with the card. Gmail's model width is already outer width; only row-derived preferred height receives the shell inset. Visualizer remains on its independent `uniform_visual_scale` + `viewport_extent` contract.

### 5. Media event ownership

Do not restore fast Media polling or process-probe fallback. Native GSMTC event/session observation is primary. The slow reconciliation/watchdog is deliberate safety coverage and degraded observation must be conspicuous in logs.

### 6. Native Cursor Halo

Passive pointer motion must not become QML scene invalidation again. Halo position/visibility is native cursor presentation through `QuickCursorController`/`QCursor`; QML retains only semantic interaction/Ctrl state where needed. The orphan `rendering/quick/qml/CursorHalo.qml` is I deletion residue, not a dormant fallback.

## Phase I — ACTIVE: caller-proven residue reconciliation

I is intentionally source-driven cleanup. It must make the tree tell the truth about the already-accepted destination; it must not redesign production behavior.

### I0 — deterministic destination gate

- [x] Apply the H-closure test/doc patch. (Present in current tree.)
- [x] Manually delete the **Immediate manual deletions** tombstone tests — already removed (not tracked in git).
- [x] Ran the destination gate in the real PySide6/OpenGL environment (2026-09-01):

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

- [~] **Destination gate 2026-09-01: 98 targets, 77 pass / 21 fail. Collection preflight clean.** Every red was classified; none are current-source defects and none are caused by the visualizer-fade slice. Reconciliation is stale-test-vs-current-API work:
  - **Ctrl/interaction API drift (~14 failures across `test_qtquick_ctrl_coordinator`, `test_qtquick_input_controller`, `test_qtquick_display_unit`, `test_qtquick_context_menu`(+`_single_owner`), `test_qtquick_clock_presentation`, `test_qtquick_runtime`(+`_reality`), `test_qtquick_auxiliary`, `test_runtime_perf_policy_contracts`, `test_qtquick_retained_model_lifetime`, `test_qtquick_custom_layout_owner`):** tests inject the deleted `interaction_mode_provider`/`global_ctrl_held_provider` constructor wiring or read `SharedCtrlCoordinator.held_provider`. Current `QuickInputController` deliberately owns interaction/Ctrl as event-updated generation-scoped `QuickInputState` facts and passes `None` to the base owner (R6/§4.5: passive pointer motion must never query Settings/cross-display state). **Update the tests to the event-driven model; do not restore provider injection.**
  - **Visualizer engine stub drift (~7 failures in `test_qtquick_h_cutover`, `test_qtquick_visualizer_true_f_gate`, `test_qtquick_visualizer_reactivity_config_parity`):** the fake `_ManagerVisualizerEngine`/technical-config stub lacks `set_transient_lane_config`, which the real `BeatEngine`/`audio_worker` provide and `quick_technical_config`/`config_applier` require. **Add the method to the test stub.**
  - **Environment/brittle:** `QCoreApplication has no attribute 'screenAdded'` (headless QCoreApplication vs QGuiApplication); `NameError: Path not defined` in `test_qtquick_visualizer_geometry`; assess `test_qtquick_window` R-63 overscan, `test_qtquick_startup_reveal` (seed crossfade / no-recapture) and `test_visualizer_playback_gating` individually.
- [~] Resolve/rehome the classified `destination` reds so the gate returns GREEN. No retired owner may be restored. **Progress 2026-09-01:**
  - [x] Visualizer engine-stub cluster (`set_transient_lane_config`) — GREEN.
  - [x] Ctrl/interaction provider-injection cluster (7 files) rewired to the event-driven `SharedCtrlCoordinator` publish/subscribe + `interaction_mode_enabled` model — GREEN.
  - [ ] **Behavioral transition-admission cluster** (real contract change, needs test-intent rewrite, not a kwarg swap): `test_qtquick_h_cutover::…routes_descriptors_and_images_by_screen_identity` and `test_qtquick_runtime_reality::…active_transition_replacement_cancels_to_destination_then_starts_new` and `test_runtime_perf_policy_contracts::…never_snaps_active_transition` encode the pre-R7 "cancel/snap active transition, or settings-free direct-publish of a second image" behavior; current source rejects a newer image mid-transition and requires a resolvable transition once a source exists (no-flash, R-63/R7). Rewrite the tests to the transactional contract.
  - [ ] **Stub/attr lag:** `test_visualizer_custom_route_contract` `_Owner` missing `card_shadow_kwargs`; `test_visualizer_playback_gating` `_SpotifyBeatEngine` missing `_test_thread_manager`.
  - [ ] **Trivial test bugs:** `test_qtquick_visualizer_geometry` missing `Path`/`_card_policy` names.
  - [ ] **Source-text/behavioral assertions to reconcile:** `test_qtquick_runtime::…narrow_qobject_owner` (retirement close-call list), `test_qtquick_context_menu::…no_settings_or_qwidget_authority` (QML 'QWidget' substring), `test_qtquick_window::…overscans_without_losing_coverage` (R-63), `test_qtquick_custom_layout_owner::…save_commits…` (committed-size dict shape), `test_p2_analysis_freshness::…superseded_result…` (slot fencing).
  - [ ] **Headless env:** `test_qtquick_retained_model_lifetime` (3) hit `OverlayWidget.qml rejected startupRevealOpacity` — confirm QML-load-in-headless vs real defect in isolation before touching the host.
  Note: multi-file `pytest` runs cross-contaminate Qt teardown; classify each red with the per-target-isolated `destination` runner, never a shared-process batch.

### Immediate manual deletions

These are already caller/contract-proven enough that preserving them adds fake authority:

- [x] Delete `tests/test_settings_sync.py` — already removed (not tracked in git).
- [x] Delete `tests/test_phase_e_effect_corruption.py` — already removed.
- [x] Delete `tests/test_visualizer_preset_cycling_runtime.py` — already removed.

Generated test cache (`tests/.pytest_cache/`, `tests/**/__pycache__/`, `*.pyc`) is never source authority and can be removed locally at any time.

### I1 — exact stale-owner test/tool reconciliation

Use `Docs/TestSuite.md` as the live inventory. Highest-confidence residue already identified:

- [ ] Reconcile old GL/compositor transition and rendering tests.
- [ ] Reconcile old compositor metrics/GPU-query/fallback tests.
- [ ] Reconcile old visualizer physical-host/card geometry tests.
- [ ] Reconcile `tests/test_spotify_visualizer_widget.py` importing deleted overlay/host code.
- [x] Tooling audit proved `tests/test_visualizer_replay.py` + `tools/visualizer_replay.py` have no current executable owner; delete them while preserving current fixtures/goldens/temporal/BTF contracts.
- [ ] Reconcile old MC physical-window implementation tests where current Quick role/policy tests own the surviving contract.
- [ ] For every candidate deletion/rehome: identify the exact surviving product-neutral contract and prove its current owner/test first.
- [ ] Do not mass-delete by filename/phase prefix; record each resolved owner/removal in `Docs/TestSuite.md` / cleanup ledger.


### I1A — tooling authority cleanup

- [x] Audit every `tools/` executable against current post-H owners rather than filename/phase age.
- [x] Remove the dead in-process PERF parser hook from `main.py`; production now only emits/flushes evidence (`R-72`).
- [x] Make `tools/run_tests.py` delegate to canonical `tests/run_chunked.py` instead of owning a second suite manifest.
- [x] Re-home the still-useful ImageWorker SHM proof as `tools/image_worker_shm_lifecycle_harness.py`.
- [x] Re-audit defaults regeneration tooling against the current schema/atomic-write safety contract.
- [x] Reject `bubble_parity_harness.py` as R-69 authority: it has no viewport/domain/DPR/presentation-scaling oracle.
- [x] Reject the generic `transition_perf_health_parser.py`/synthetic Visualizer distribution harness as permanent authority; current instrumentation + focused tests own those contracts.
- [x] Apply the manual tool/test deletions in `Docs/Tooling_Audit_2026-09-01.md` — verified: all 20 tools and all 7 tool-coupled tests are already removed from the tree.
- [x] Run `test_tooling_ownership.py` in the real project environment as part of `destination` — passed in the 2026-09-01 gate (not among the 21 reds).
- [x] Confirm no production Python imports `tools`/`scripts` analysis modules after the deletion batch — enforced GREEN by `test_tooling_ownership.py`.
- [ ] Carry only `presentation_benchmark_core.py` + `qtquick_presentation_spike.py` as explicitly non-authoritative architecture-selection evidence until J physical acceptance, then delete them.

### I2 — source/tool residue

After exact caller search:

- [x] Delete orphan `rendering/quick/qml/CursorHalo.qml` — removed 2026-09-01 after proving no `.py`/`.qml`/`.qrc`/`qmldir` reference (only docs/history mention it).
- [x] Remove caller-dead Media process-probe helpers retired by event ownership — none remain; `psutil` survives only in the two KEEP out-of-process sampler tools.
- [ ] Remove old physical-presenter/compositor aliases/adapters/comments/spikes that no longer have a production caller.
- [x] Reconcile regeneration/default tools against current Settings/Quick schema; audit completed 2026-09-01 and current atomic/schema-derived pipeline is protected.
- [ ] Preserve neutral transition registry/settings/math/shaders and neutral visualizer DSP/logical algorithms used by Quick.
- [ ] Re-run exact caller/import searches after each residue batch so deletion does not create hidden compatibility fallback pressure.

`Future_Cleanup.md` owns the detailed deletion ledger.

### I3 — whole-tree truth restoration

After bounded residue batches:

- [ ] Run the maintained destination authority:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

- [ ] Run the broad whole-tree gate:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

- [ ] Confirm the first command remains GREEN production authority.
- [ ] Drive the second away from deleted-owner/museum failures until it is a useful broad gate again.
- [ ] Sweep current docs/test inventory after the final residue batch so source, tests and authority documents agree before I closes.

### I exit checklist

- [ ] Canonical `destination` profile GREEN in the real project environment.
- [ ] No current tests import deleted physical owners merely to preserve migration history.
- [ ] Whole-tree collection has no caller-dead-owner import failures.
- [ ] Source/tool residue has exact caller proof before deletion.
- [ ] No compatibility alias/fallback can silently recreate a second presenter/analysis/polling authority.
- [ ] `Docs/TestSuite.md`, `Future_Cleanup.md`, migration docs and source agree on owner map.
- [ ] No change violates the golden Visualizer/R-63/Media/CUSTOM guardrails above.
- [ ] Historical-bug records exist for any newly resolved or instructively failed I incidents before the phase is closed.
- [ ] `Current_Plan.md` is compactly rolled forward to J with the completed I checklist retained as closure evidence.

## Phase J — queued after I

J is final visual/fidelity/installed/physical acceptance and intentional polish. The detailed matrix lives in `Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md`.

Front-load the mandatory image-oracle parity work (`images/migration/Ideal (PreMigration)/` vs `Current (PostMigration)/`) when vision-capable tooling is available.

### J queued checklist

- [ ] Perform family visual-parity pass against the pre/post migration image oracle.
- [ ] Restore/verify alignment and snap guides.
- [ ] Verify/fix context-menu and theme correctness.
- [ ] Complete remaining Visualizer presentation polish, including any proven extreme Bubble full-expansion tail, **without weakening R-69 reactivity**.
- [ ] Consider device-space R-63 seam refinement only if it preserves `black=0` generically across DPR/resolution combinations; bounded overshoot remains preferable to black flash risk.
- [ ] Fix latency/telemetry accounting so recreation boundaries cannot report stale pre-recreation timestamps as multi-second live latency.
- [ ] Run late-J performance work under `Docs/Guardrails/Performance_Optimization_Contract.md`: target rare active latency tails and proven useless allocation/lifetime work before average counters.
- [ ] Work the live bounded parity/polish queue in **Non-Blocking Auxiliary Work** above without duplicating its checkbox authority here; unresolved auxiliary items may carry forward explicitly, but must not disappear.
- [ ] Verify resource plateau across recreation/soak (RSS/USS, VRAM, threads, handles, workers/caches) without destroying useful bounded caches merely to reduce Task Manager numbers.
- [ ] Recheck both modest-load quality and representative-heavy graceful degradation after any performance change.
- [ ] Complete compiled/frozen/installed 1/2/N-display/DPR/topology acceptance.
- [ ] Complete final family-specific parity/polish acceptance from `Remaining_J_Final_Installed_Acceptance_Decomposition.md`.
- [ ] Reconcile remaining historical-bug records, including failed methods worth preserving.
- [ ] Remove migration-only harness/planning debris only after acceptance evidence exists.
- [ ] Run final maintained destination + broad suite gates and reconcile docs before J closes.

### Committed J+ card-material checklist — non-blocking for J close

- [ ] Implement the committed, non-blocking ordinary-widget **Normal / Glass / Acrylic** card-material slice after mandatory parity is under control, using the shared/lazy Qt Quick design at the bottom of `Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md` and `Future_Work.md` section 10. This item must remain tracked until implemented/accepted or explicitly superseded; J may close before it. Default remains Normal/off-cost; do not create per-card capture/blur owners or weaken performance/reactivity contracts.

## Authority order

For current work:

```text
exact source / exact test tree
-> Current_Plan.md
-> Spec.md
-> Docs/Contracts.md
-> Docs/Guardrails.md + focused subsystem references
-> Docs/TestSuite.md / Future_Cleanup.md
-> physical/log evidence
-> historical records for mechanism/failed-method lessons
```

Historical documents preserve what happened; they do not override current owner maps. Conversely, current source must not erase a binding historical lesson merely because a tempting shortcut looks locally cleaner.
