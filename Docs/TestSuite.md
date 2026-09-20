# Test Suite Guide

Last updated: 2026-09-20

This file is the **current test/acceptance authority** for SRPSS. It describes what deserves trust now, how to classify evidence, and which architecture contracts must stay guarded. It is not a checkpoint diary or migration changelog; source control and `Docs/Historical_Bugs/` preserve chronology.

`Current_Plan.md` owns execution order. The exact source tree plus `tests/run_chunked.py` own executable inventory. `Docs/Reference/Harness_Index.md` owns operator-tool/harness lookup.

## 1. Current authority and inventory

The maintained product profile is `destination` in `tests/run_chunked.py`.

Current-tree inventory at this checkpoint (module count enumerated from this tree; destination target count is the last separately recorded profile snapshot):

```text
393 test_*.py modules
136 maintained destination targets
0 missing destination target files
```

The destination profile is **target-isolated**: each selected target runs in its own fresh pytest subprocess so queued Qt/QQuick teardown from one target cannot poison another target's result.

The previously recorded maintained destination profile ran **132/132 GREEN on Windows + PySide6 + OpenGL on 2026-09-17**, before the later ordinary-widget CUSTOM/Visualizer changes. The current maintained profile lists 136 targets and remains **NEEDS RUN** on the present tree. The separate accepted R-87/CHK26 performance landmark is documented in `Docs/Historical_Bugs/R-87_QtQuick_HighRefresh_Freshness_And_Scheduler_Regression.md` and `Docs/Guardrails/Performance_Optimization_Contract.md`.

**Most recent operator evidence, 2026-09-20:** the expanded three-action undo/third-generation owner gate passed **6/6 on Windows**; the focused Reddit Restore/spacing and offline Achievement Pulse/Weather owner gate passed **7/7 on Windows**; the operator also accepted the rendered Reddit Restore and title/age clearance. The earlier Reddit/Reddit2 owner Save/fresh-generation/second Edit gate passed 2/2. The revised owner lifecycle gate includes Achievement Pulse/Weather second Save and third fresh generation, accepted in the six-case run. The bounded three-action Edit undo is accepted in that run; real user keyboard and physical end-to-end acceptance remain distinct. Media's separate absent-Edit-delegate regression remains unverified beyond its known failing setup, not a reason to replace working automatic side placement.

**Open acceptance gates:** the real retained Media saved-offset/compact-Y test returned **2 PASS / 2 RED** on Windows. The previous right-edge assertion measured absolute root X despite legitimate uniform card recentering; the revised test measures painted-card-relative metadata alignment and essential row containment. Its test parameter named reset/reprojection does **not** execute owner Save/reopen; physical Reset -> Flip -> Save -> Edit remains unaccepted until rechecked. The third-generation Pulse/Weather selected Edit-proxy/actual paint comparisons are newly added and not yet run. Repeated-column drag swapping is proposed and is not an implemented or accepted test contract.

The current agent/container may lack PySide6/OpenGL. In that environment, a collection failure caused by missing runtime dependencies is **ENVIRONMENT BLOCKED**, not a product RED and not a PASS.

## 1.1 Qt delivery and painted-geometry evidence (2026-09-19)

A green geometry owner/source suite does not verify which MouseArea receives a click or whether a short post headline makes a timestamp rail float. `tests/test_qtquick_edit_pointer_delivery.py` sends real press/release events into a QQuickWindow and verifies top-strip selection, header-gap selection, and that the flip target calls the existing flip authority instead of selecting/moving the parent. `tests/test_qtquick_reddit_presentation.py` asserts retained Reddit/Reddit2 title/age/AGO paint-item rectangles and common timestamp alignment across short and long titles, parent resize and semantic flips. Both are Windows/PySide6 **NEEDS RUN** for the new checkpoint. Only screen-pixel appearance/hardware-specific DPI, OS mouse routing, and real GPU dual-display behaviour require subsequent bounded physical sampling if these tests pass. The previous all-green suite predates these tests and does not retroactively pass them.

## Current child-geometry and owner lifecycle gates

The inventory below describes the live contracts and their evidence state. New or
modified tests must be entered here in the same checkpoint as their source changes.
These focused gates supplement rather than replace the maintained destination profile.

| Contract | Executable gate | Current evidence |
| --- | --- | --- |
| Nine-family normalized child persistence, physical-floor and resize no-churn | `tests/test_qtquick_child_persist_floor_regression.py` | PASS: operator, 68 cases (2026-09-19) |
| Shared parent/Visualizer Edit no-op publication and gesture release | `tests/test_qtquick_edit_noop_publication.py` | PASS: operator, 8 cases (2026-09-19) |
| Mapped child/proxy geometry, cancelling axes | `tests/test_qtquick_child_mapped_geometry.py` | PASS: operator, focused mapped gate (2026-09-19) |
| Reddit/Reddit2 committed painted child reopen and full owner Save/live promotion/fresh display/second Edit | `tests/test_qtquick_reddit_child_committed_reopen_scene.py` | PASS: operator, owner 2 cases (2026-09-20); direct committed 2 cases previously passed |
| Achievement Pulse header/list semantic flip and actual text/badge paint | `tests/test_qtquick_achievement_pulse_presentation.py` | PASS: operator, recent 2 header cases; physical header flip accepted. Outer leading-gutter trim/reverse/Save still needs physical acceptance |
| Achievement Pulse and Weather owner Save/live promotion/fresh generation/second Edit with offline cached provider | `tests/test_qtquick_other_family_owner_save_reopen.py` | PASS: operator, 2 cases in 7-case focused gate and extended second Save/third generation in six-case focused gate (2026-09-20). This is not a binder phase-2 activation acceptance test. |
| Reddit/Reddit2 AGO/title clearance at ordinary and scaled CUSTOM sizes, both alignments | `tests/test_qtquick_reddit_presentation.py`, `tests/test_reddit_spacing_contract.py` | PASS: operator, affected seven-case gate plus physical check on 2026-09-20; retain internal 01HR/AGO spacing and actual post-title clearance. |
| Bounded three-action Edit undo across widgets, no-op gesture exclusion, active-gesture block and Edit retirement | `tests/test_qtquick_custom_layout_owner.py::test_three_level_undo_retains_only_three_completed_edit_actions`, `tests/test_qtquick_custom_layout_owner.py::test_three_action_undo_is_global_across_items_and_clears_on_retirement`, `tests/test_qtquick_input_controller.py::test_edit_only_undo_and_lock_hotkeys_preserve_plain_z_and_ignore_repeats` | PASS: operator, two new owner cases in six-case focused Windows gate (2026-09-20); keyboard routing unchanged. No pointer-sample snapshot, redo, polling or Settings write. |
| Media compact-height active-track rows, saved-offset independent-axis flow and flipped right-rail text scaling | `tests/test_qtquick_media_presentation.py::test_compact_media_essential_rows_survive_flip_and_transient_capability_loss`, `tests/test_qtquick_media_presentation.py::test_media_child_axis_edits_keep_live_band_flow_at_compact_y`, `tests/test_media_content_extent_contract.py::test_media_nested_seek_and_transport_keep_axis_independent_band_reflow` | Operator reran the revised saved-offset Media four-case gate on Windows: **4 PASS**, including reset/reprojection flipped. The gate is model reprojection and does not on its own certify an actual Media owner Save/reopen or the original physical sequence; it checks real card bounds and right-edge metadata alignment. The source-only and pristine-child cases do not accept the original physical Reset -> Flip -> Save -> Edit defect; this parametrized case is model reprojection, not a real owner Save/reopen. |
| Outer-only child containment across families and dense requirement retirement | `tests/test_custom_layout_guides_contract.py`, `tests/test_qml_reflow_loop_contract.py`, `tests/test_qtquick_child_edit_off_dependency_contract.py`, `tests/test_quick_child_paint_containment_contract.py`, `tests/test_qtquick_child_persist_floor_regression.py`, `tests/test_qtquick_custom_layout_owner.py` | Source-only guards updated and executed locally; dynamic Qt child/parent move/resize, collision OFF, no Settings writes and unchanged live pointer feel NEED WINDOWS RUN. Old parent-growth tests no longer certify this changed policy. |
| Achievement Pulse/Weather full owner Save, second Save, third fresh generation **and selected painted-child/Edit-proxy mapping** | `tests/test_qtquick_other_family_owner_save_reopen.py::test_other_family_real_owner_save_live_promotion_fresh_generation_and_reedit` | Operator accepted the earlier two-family owner/third-generation 6-case gate. The additional third-generation selected Edit-proxy assertions were RUN on Windows and are **2 RED**: Achievement Pulse lacks the selected artwork proxy; Weather creates a location-text proxy whose rectangle does not match the target mapped by the test. Do not discard these checks or classify the result as a Save/reopen pass. Investigate actual role declaration, Qt delegate creation/lifetime and mapped-paint target selection. Cancel must leave paint and Settings unchanged. |
| Media external volume Edit-proxy geometry | `tests/test_qtquick_media_presentation.py::test_media_volume_opposite_axis_reflow_updates_live_edit_proxy` | RED at absent Qt Edit delegate before the mapping assertions; automatic side placement is physically working and is not under redesign |
| Reddit Restore Size loading/ready invariant and child retention | `tests/test_qtquick_reddit_presentation.py::test_reddit_loading_and_ready_state_use_the_same_authored_height`, `tests/test_qtquick_custom_layout_owner.py::test_flip_wheel_restore_repeatedly_returns_authored_shape_and_clears_stale_extent` | PASS: operator focused seven-case Qt gate and subsequent physical Restore check (2026-09-20). Existing saved compact rectangles remain valid CUSTOM geometry. |

The offline Achievement Pulse/Weather Save/reopen fixture explicitly activates the
real retained-family ports and injects synchronous cached data. It must not be used
to certify binder phase-2 activation or external-service readiness. A future
binder-activation regression requires a separate test with a real activation
service seam and should inspect the event-edge activation warning rather than
mistaking an inactive family for a persistence failure.

Reddit's authored preferred height must be stable while row data is absent or
loading. The CUSTOM content extent is a separate user-authored resize override;
do not fix Restore by deleting saved extents, changing the post limit, or
introducing an extra geometry/size owner. After the focused QML gate passes,
physically check loading -> populated -> Restore Size and live reversed Edit;
a render-level source assertion alone cannot accept the previous reported snap.

For Reddit post rows, check the actual painted geometry after the shared retained
presentation scale. A QML source literal or unscaled logical-gap assertion is
insufficient: both alignments and all rows must retain visible separation between
AGO and the title, without changing the 01HR/AGO internal gap.

**Repeated-list semantic rail swap (candidate, Qt/physical acceptance pending):** `tests/test_column_rails_contract.py` validates all permutations, no-op and invalid input. `tests/test_qtquick_custom_layout_owner.py::test_column_rail_swap_is_one_bounded_owner_undo_action_and_restores_authored_order` checks one whole-list discrete Undo transaction without Settings I/O. `tests/test_qtquick_reddit_presentation.py::test_three_semantic_column_rails_reorder_every_retained_post_and_rehydrate` and `tests/test_qtquick_gmail_presentation.py::test_gmail_semantic_column_rails_reorder_all_retained_message_rows` check actual retained painted positions in all rows, order reversal, header-flip independence, Y/width reflow and retained delegate identity. Windows execution and physical grip drag/Undo/Cancel/Save/slot/fresh-generation are still required. The canonical CUSTOM payload is `column_rails`, never per-row `x_offset`; no normal-runtime rail observer, and a dedicated column-order notification
so child-geometry changes do not churn the list columns. See `Docs/Future_Work/Custom_Child_Placement_And_Headers.md`.

## 2. Status vocabulary

Use these labels consistently:

- **PASS** — executed against the stated tree/environment and passed.
- **NEEDS RUN** — current coverage is structurally valid but still requires the intended Windows/PySide/OpenGL or installed environment before it can be acceptance evidence.
- **ENVIRONMENT BLOCKED** — collection/execution cannot begin because a required platform/runtime dependency is absent. This is not a product failure.
- **RED** — a current test executed in an appropriate environment and failed a current contract.
- **OBSOLETE** — the test targets a retired owner/architecture and no longer expresses a current contract. Delete it or preserve its lesson in Historical Bugs.
- **REHOME** — only part of a mixed old test still has value. Move that assertion to the current owner/suite and retire the dead shell.

A green static/source test is never a substitute for a required Qt/QML, real-GL or installed physical gate.

## 3. Standard commands

### 3.1 Maintained product gate

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

### 3.2 Broad reconciliation diagnostic

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

A whole-tree run is useful for discovering stale tests, optional-dependency gaps and hidden regressions. It is **not** permission to resurrect retired production architecture merely to make an old test green.

### 3.3 Defaults authority

```powershell
python -m core.settings.defaults_snapshot_builder --check-all
```

Run this whenever canonical defaults, generated snapshots/SSTs, Settings normalization or Defaults-Foundry-facing keys change. Regeneration is owned by `--write-all`; checked-in generated artifacts must remain exact projections of canonical source.

### 3.4 Focused tests first

Prefer the smallest set capable of falsifying the current change:

```powershell
pytest path\to\test_file.py -q --tb=short
```

Then widen to the maintained profile and installed/physical gates only when the change actually requires them.

## 4. Evidence levels

Use the minimum relevant combination, but never claim a higher level from a lower one:

1. **Static/schema contract** — ownership, imports, canonical defaults, descriptors, manifests, forbidden paths.
2. **Deterministic behavioural test** — equations, normalization, response, persistence, compatibility normalization, lifecycle state.
3. **Qt/QML runtime-shaped test** — real objects/signals/bindings/layout/teardown/retained presentation.
4. **Real GL/platform test** — shader/resource/context/driver behavior where fakes are insufficient.
5. **Installed physical review** — final visual/timing/input/multi-monitor/lifecycle acceptance on the target machine.

Do not collapse levels 3–5 into “unit tests passed.”

## 5. Stale-test and retirement rule

When a test fails because an import or owner no longer exists:

1. establish whether the production owner was deliberately retired;
2. identify the surviving behavioural contract, if any;
3. rehome a surviving contract onto the current owner/path;
4. delete the test if the contract itself retired;
5. preserve important failure mechanisms in `Docs/Historical_Bugs/`, not fake compatibility architecture.

For every migration/compatibility retirement slice, search the test tree for the retired symbol, owner, import path and fixture shape **before checkpointing**. Classify each hit in the same change: update/rehome tests that protect a surviving current contract, delete tests whose contract/owner retired, and record environment-blocked current coverage honestly. Intentional automatic reds are not an acceptable migration artifact.

Diagnostic CLI retirement follows the same rule: when an operator-retired spelling has no current workflow, remove the parser/filter token, tool aliases/descriptions and tests that keep it callable. Do not preserve a narrower hidden diagnostic mode merely because old tests can exercise it; current diagnostic authority must be proven through the surviving canonical flag.

Do not:

- create forwarding modules solely for tests;
- restore QWidget/old compositor presenters to satisfy stale imports;
- keep whole-file skips as permanent tombstones;
- weaken a current assertion merely because an old test encoded obsolete topology;
- treat an old phase/checkpoint name as current authority;
- “fix” a test by changing protected product behavior without first establishing that the product contract changed.

Fixtures must follow current architecture. A fixture that manufactures a retired owner can give convincing green results for a product path that no longer exists.

### 5.1 Stale-oracle discipline (gate closed 2026-09-17)

The former test-first gate is closed: the broad-suite reds were reconciled (all test-side drift against current architecture; production correct throughout) and the maintained destination profile is 132/132 GREEN. A whole-tree sweep on 2026-09-17 ran every one of the 373 collectable test files in per-file subprocess isolation (245 unprofiled "gap" files + the profile + `tests/unit/test_policy_compliance.py`): all GREEN, no hangs. The only two reds were stale test-side drift — the family-colour doc-content assertion (repointed after the `Future_Cleanup.md` retirement) and the threading-policy exclusion list missing the opt-in `--frame-trace` writer; production was correct in both. Compatibility-bridge retirement is no longer globally frozen — it is governed per-item by `Docs/Architecture/Persisted_Input_Compatibility.md` (horizon-gated, one bridge at a time, whole test cascade updated in the same commit). The discipline below is permanent, not a one-time audit.

Current retained-Quick Visualizer contract modules are `test_qtquick_visualizer_owner_contract.py`, `test_qtquick_visualizer_technical_sync_contract.py`, and `test_qtquick_product_wiring_contract.py`. Phase/checkpoint-named predecessor files are retired; do not restore them to satisfy an external stale test list.

A test that mentions a retired owner is not automatically obsolete. **Negative absence/import guards are current contracts.** Conversely, a test with no meaningful oracle, a tautological assertion, a permanently skipped empty shell, or a loop over a schema root that no longer exists is not useful evidence merely because it is green.

## 6. Permanent architecture gates

### 6.1 Qt Quick presentation and lifecycle

Protect:

- one retained accelerated `QQuickWindow` per admitted display;
- no `QQuickWidget`, second accelerated widget surface or generic fallback presenter;
- current family binders and retained models;
- generation/activation fencing;
- destruction on legal owners and clean replacement-generation retirement;
- QML emits semantic actions rather than owning provider/business side effects;
- ordinary family presentation remains normalized from authored size plus one resolved runtime geometry authority;
- event-driven monitor/sleep/wake reconciliation rather than polling.

High-value suites include `test_qtquick_runtime.py`, `test_qtquick_window.py`, `test_qtquick_scene_controller.py`, `test_qtquick_monitor_wake_reconcile.py`, `test_qtquick_family_binder*.py`, `test_qtquick_ordinary_widget_host.py`, lifecycle/terminal-destruction suites and family-specific Quick presentation tests.

`test_qtquick_monitor_wake_reconcile.py` permanently protects the event-driven topology contract. Installed dual-display wake/topology validation is already recorded in the relevant Historical Bug; do not reintroduce a debounce/poller merely because a future test fixture is easier that way.

### 6.2 Widget normalization and CUSTOM

Tests must distinguish:

```text
authored/natural size
resolved runtime size
uniform scale
content extent when admitted
CUSTOM working geometry
committed geometry
serialized stale payload
```

Required properties:

- stale stored dimensions normalize once, not repeatedly;
- reconstruction does not compound scaling;
- Save commits exactly the working geometry;
- Cancel restores pre-edit committed geometry;
- layout-slot replay does not mutate authored baseline;
- dynamic content does not redefine natural size unless the product contract explicitly says it does;
- fitted text remains presentation inside resolved geometry, not another widget-scale authority;
- global CUSTOM suppresses ordinary stacking/adjacency authority as specified.

Primary suites include `test_qtquick_resize_normalization.py`, `test_widget_auto_shrink.py`, `test_qtquick_family_size_policy.py`, `test_qtquick_geometry_resolver.py`, `test_qtquick_custom_layout_owner.py`, `test_qtquick_custom_layout_overlay.py` and capture/geometry tests.

**Current Edit acceptance:** `test_qtquick_custom_layout_owner.py` exercises three completed-action undo, flips, wheel then reset; `test_qtquick_input_controller.py` exercises keyboard admission only in Edit without stealing non-Edit plain `Z`; `test_qtquick_child_lock_scene.py` checks keyboard and glyph signals against one retained lock frame. `test_qtquick_reddit_presentation.py` checks flipped title → age value → AGO order and compact live spacing; `test_qtquick_friend_pulse_presentation.py` checks separator growth/reset and edited width-scale preservation. Confirm these in the intended Windows Qt environment plus actual pointer/Save/Cancel/Restore interactions. Source tests cannot prove QML signal delivery, pointer grabs, render alignment or full paint/geometry parity.

Clock face state is independent from its digital/analogue geometry variants. `test_layout_slots.py`, the real DisplayManager slot path, and Clock Settings preservation coverage must keep those authorities separate.

### 6.3 Settings, defaults and themes

Protect:

- `core/settings/default_settings.py` as defaults SSOT;
- generated snapshot/SST parity;
- no second fallback/default authority;
- lazy Settings hydration cannot masquerade as user edits;
- descriptor/load/save/default keys remain mutually complete;
- compatibility normalization happens at explicit input boundaries and retired aliases do not become current output;
- read-oriented defaults/manifest validation and runtime preset catalogue loading must not rewrite shipped Visualizer preset artifacts; explicit regeneration is the source-tree write authority and no-op manifest writes must remain byte-stable across host newline conventions;
- Theme Foundry and Defaults tooling consume canonical schema rather than inventing parallel fields;
- collapsible-bucket identities stay canonical while persisted state remains sparse/local-scope;
- `themes/dark.qss` stays physically absent; narrow structural renderers plus `SettingsThemeSpec` own Settings styling and no fallback monolithic QSS may return;
- Widget Theme semantics stay separate from Settings HWND material/backdrop ownership; while old material-bearing Widget Theme profile/SST/QSettings state remains supported, only `core.settings.widget_theme_input_compat` may name that retired runtime-card material schema, and current Widget Theme selection/runtime/file I/O remain colour-only v3.
- Settings Theme authoring/runtime remains schema v6; supported schema-v5 `.srtheme` files may be named only by the explicit file-input compatibility owner, and tests must keep Foundry/current export assertions separate from historical v5 migration assertions. A v5 fixture must remain distinguishing and incomplete old themes must still fail whole rather than default-merge.
- Canonical storage-path tests target current `core.settings.storage_paths` and engine startup only. The retired `%TEMP%` storage importer and Weather home-cache bridge have no surviving compatibility-test owners: tests must not reintroduce their historical filenames, startup probes, generic migration helpers or compatibility-only facades. Current cache/runtime tests own only canonical behavior.
- Reddit helper runtime/install tests own only the current session-scoped helper plus canonical root `SRPSS_RedditHelper` scheduled task. Retired HKCU Run startup, historical task-name fallback and runtime `persistent=True` bootstrap have no surviving test owners and must not be reintroduced to satisfy stale tests.

Primary coverage includes `test_defaults_schema_authority.py`, `test_storage_paths.py`, `test_settings_theme_input_compat.py`, `test_widget_theme_input_compat.py`, `test_widget_theme_no_material_contract.py`, Settings manager/persistence/binding/default parity, descriptor suites, Theme Foundry, default-settings-editor, bucket-state and Settings-theme lifetime tests.

### 6.4 Visualizers

Read these before changing visualizer behavior:

- `Docs/Guides/Visualizer_Change_Checklist.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Guides/Visualizer_Reactivity_Authoring.md`
- `Docs/Guardrails/Performance_Optimization_Contract.md`

Permanent shared-mode work must preserve source freshness, authored logical cadence, latest-state delivery, mode hotswap and viewport/normalization contracts.

**Bubble is the strongest protected canary.** Idle traces are insufficient for any production change that touches Bubble cadence, simulation, payload/coalescing, reactive uniforms, event admission, attack/settle, elasticity/breathing, loud-passage expansion, ghost/tail motion or presentation timing. Such a change requires an explicit active-music installed lane plus operator feel. Never retune Bubble merely to satisfy a benchmark or stale golden.

Voxel Sphere is accepted experimental architecture and remains isolated until explicit operator promotion. Its current contract lives in `Docs/Reference/Sphere_Visualizer.md`; current Voxel Sphere tests supersede the retired smooth/material Sphere family.

User-authored Visualizer preset counts/numbers may be arbitrary or sparse. Runtime compacts selectable positions without renaming/deleting authored files or treating shipped manifests as catalogue authority.

### 6.5 Visualizer performance/trace authority

R-87 is closed and **CHK26 / `a0bf70932c` is the accepted performance/freshness GOLDEN**. The frame-trace sidecar remains useful diagnostic authority and must not be removed merely because the investigation closed.

High-value permanent guards include:

- `tests/test_qtquick_runtime_purity_source.py` — forbids retired Python pacing/live-state ghosts and other source-level regressions;
- `tests/test_frame_trace.py` — binary trace format, bounded rolling retention, optional phase/clip/Bubble attribution and backward-compatible reporting;
- `tests/test_visualizer_switch_abc_harness.py` — causal switch/lifecycle scoring and freshness gates;
- real-GL visualizer clip/render tests where driver/context behavior matters.

The following are **not** valid “fixes” absent contradictory evidence: Python display-refresh pacing, `frameSwapped -> requestUpdate()` feedback, lower Bubble cadence/reactivity, global GIL switch-interval tuning, high-rate render text logging, or removal of inherited clip/stencil restoration fences. Detailed falsifiers live in R-87.

### 6.6 Transitions

Quick transition ownership is current. Do not restore old compositor transition presenters to satisfy stale tests.

Protect:

- canonical registry/settings/activation parity;
- authored shader/math and exact endpoints;
- request/run generation fencing;
- lazy implementation/resource ownership;
- transition completion/lifecycle;
- no transition-driven background scheduler feedback loop.

Real-GL/capture oracles supplement source/uniform tests when visual effect semantics cannot be proved statically. `Docs/Guides/Transition_Change_Checklist.md` owns the change procedure.

### 6.7 Media and runtime services

Shared service tests target current service ownership directly. Old `MediaWidget`/deleted manager anchor setup is not integration authority.

Current injection/admission belongs to `rendering/widget_runtime_services.py`, retained Quick family binders/models and the actual runtime-service implementations. Preserve event-driven media ownership, bounded reconciliation/watchdogs, generation fencing and clean family dormancy/retirement.

### 6.8 Caches, prefetch and long-lived workers

Cache tests protect useful bounded caches, ownership and reclamation, not arbitrary low memory numbers. Do not “fix” a cache test by destroying hot-cache value or turning event-driven work into polling.

Historical Bugs R-82/R-83 and related worker/lifetime records own the mechanisms that justified permanent regressions. The test suite should encode their surviving invariants rather than repeat the incident diary here.

## 7. Test infrastructure rules

### Destination profile

- every profile target must resolve to an existing file/node id;
- each target runs in a fresh subprocess;
- do not add obsolete coverage merely because it once represented a migration gate;
- add durable regressions for current behavior likely to recur;
- keep environment-specific coverage visible rather than silently dropping it.

### Goldens and replays

Do not regenerate goldens merely because architecture changed. If an approved product decision changes protected behavior, state the behavioral change explicitly and update the golden deliberately.

The retired Visualizer replay executable must not be resurrected. Current temporal/BTF/viewport tests plus retained fixtures/goldens preserve authored evidence; Bubble follows `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

### Static source assertions

Static tests are appropriate for:

- forbidden imports/owners;
- canonical defaults/manifest/reference paths;
- no timer/poller/thread additions;
- isolation/dormancy boundaries;
- exact shader/source contract fragments when runtime execution is unavailable.

They are insufficient for proving:

- QML layout actually fits;
- signal/lifetime ordering under Qt;
- OpenGL output;
- visual smoothness/reactivity;
- physical focus/input;
- installed multi-monitor lifecycle.

### Qt/QML sidecar

Runtime-shaped Quick/QML evidence must inspect both `logs/screensaver.log` and `logs/screensaver_qml.log`. A missing QML sidecar means the Qt/QML evidence plane was unavailable; it cannot prove “zero QML errors.” See `Docs/Guides/Qt_QML_Observability.md`.

## 8. Installed and physical acceptance

Installed eyes-on validation is mandatory when a change can materially affect pixels, timing, reaction, focus/input, multi-monitor ownership or GPU behavior.

Examples:

- visualizer cadence/freshness work requires logs **and** eyes-on response;
- Bubble-touching work requires active music, not idle-only traces;
- Voxel Sphere reaction/particle changes require music, silence, loud passages and geometry review;
- real-GL shader/resource changes require the intended driver/context environment;
- Settings theme/backdrop changes require contrasting themes, live switching and the relevant native Glass/Acrylic path;
- widget normalization changes need normal/CUSTOM reconstruction and Save/Cancel/slot replay where applicable;
- multi-display ownership changes require a physical topology/hop lane when the seam is actually display-sensitive.

A unit/static green never overrules a reproducible installed visual or interaction regression.

## 9. Current accepted physical landmarks

These are useful current acceptance landmarks, not instructions to rerun unrelated work:

- **Qt Quick runtime cutover:** accepted; no fallback presenter is supported.
- **Settings base stylesheet retirement:** accepted with `themes/dark.qss` physically absent; no replacement monolith/fallback loader.
- **Clock face-state + geometry slots:** accepted across live face switching and saved slot replay.
- **Settings bucket single-open/reachability:** accepted; sparse state and lazy page/mode reconstruction remain guarded.
- **R-82/R-83 soak repairs:** accepted; orphaned derivative budget and Reddit zero-delay re-entry are closed.
- **R-87 performance/freshness:** CHK26 / `a0bf70932c` accepted GOLDEN; CHK27-29 mapped the apparent residuals and closed further generic fishing. Sidecar instrumentation remains retained.

Detailed dates, metrics and failed methods belong in Historical Bugs rather than being duplicated here.

## 10. Maintenance and completion rule

When changing tests or this guide:

1. count current `test_*.py` modules from source instead of copying an old inventory;
2. validate every maintained-profile target exists;
3. run focused tests first, then the maintained profile when appropriate;
4. classify dependency blockers separately from product REDs;
5. delete obsolete whole-file tests once surviving assertions are rehomed;
6. mark **NEEDS RUN** only for current tests that genuinely require another environment;
7. remove NEEDS RUN only after an actual intended-environment execution;
8. update this file when test authority/architecture changes materially, not for every small assertion edit;
9. put failure archaeology in Historical Bugs, not numbered checkpoint sections here.

A test-affecting slice is complete only when:

- production behavior and test expectation agree on the current owner/contract;
- directly runnable focused tests are green;
- environment-blocked current coverage is described honestly;
- obsolete tests are deleted/re-homed rather than converted into permanent skips;
- defaults/generated artifacts are checked when Settings changed;
- maintained-profile membership is valid;
- installed/Qt/GL evidence is requested where static/headless proof cannot close the claim.

Git and `Docs/Historical_Bugs/` preserve history. `Docs/TestSuite.md` should remain small enough to answer one question quickly: **what deserves trust now?**
