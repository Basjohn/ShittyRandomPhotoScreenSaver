# Test Suite Guide

### System-audio owner / OSD source gate

The read-only native callback registration module runs directly on Windows with `python -m pytest tests/test_core_audio_callback_native_probe.py -q --tb=short`; no environment-variable gate is used. The current shared system-audio source and Media lease integration are covered by `tests/test_audio_shared_source.py`, `tests/test_audio_event_qt_bridge.py`, `tests/test_audio_event_session.py`, `tests/test_system_mute_runtime.py` and `tests/test_media_generation_recreation.py`. Native registration alone cannot prove external event arrival. The implemented event-driven Media/OSD source is operator-accepted; repeat hardware checks only when its actual callback or device-lifecycle behavior changes.


This file is the **current test/acceptance authority** for SRPSS. It describes what deserves trust now, how to classify evidence, and which architecture contracts must stay guarded. It is not a checkpoint diary or migration changelog; source control and `Docs/Historical_Bugs/` preserve chronology.

`Current_Plan.md` owns execution order. The exact source tree plus `tests/run_chunked.py` own executable inventory. `Docs/Reference/Harness_Index.md` owns operator-tool/harness lookup.

## 1. Current authority and inventory

The maintained product profile is `destination` in `tests/run_chunked.py`.

The live `test_*.py` inventory and maintained destination targets are resolved from the actual source tree and `tests/run_chunked.py`. Do not copy a previous checkpoint’s count into this reference.

The destination profile is **target-isolated**: each selected target runs in its own fresh pytest subprocess so queued Qt/QQuick teardown from one target cannot poison another target's result.

The maintained `destination` profile has not been established by the current FEEDS-focused Windows gate. Re-evaluate its actual target count from `tests/run_chunked.py` and report that profile only from a real current-tree run. The separate accepted R-87/CHK26 performance landmark is documented in `Docs/Historical_Bugs/R-87_QtQuick_HighRefresh_Freshness_And_Scheduler_Regression.md` and `Docs/Guardrails/Performance_Optimization_Contract.md`.

**Evidence rule:** Targeted Windows Qt tests and operator-observed behavior are distinct claims. Previously accepted unrelated families need not be rerun merely to document another family. A focused green selection establishes only the submitted tests on that exact tree, not full-suite completion, a live-network benchmark or universal physical visual acceptance. For subsequent code changes, execute the affected tests against that changed tree.

The maintained `destination` profile's status must come from its actual current run, not from piecing together passing focused counts from other checkpoints.

The current agent/container may lack PySide6/OpenGL. In that environment, a collection failure caused by missing runtime dependencies is **ENVIRONMENT BLOCKED**, not a product RED and not a PASS.

## 1.1 Qt delivery and painted-geometry evidence

A green geometry owner/source suite does not verify which MouseArea receives a click or whether a short post headline makes a timestamp rail float. `tests/test_qtquick_edit_pointer_delivery.py` sends real press/release events into a QQuickWindow and verifies top-strip selection, header-gap selection, and that the flip target calls the existing flip authority instead of selecting/moving the parent. `tests/test_qtquick_reddit_presentation.py` asserts retained Reddit/Reddit2 title/age/AGO paint-item rectangles and common timestamp alignment across short and long titles, parent resize and semantic flips. Both are Windows/PySide6 a required native regression gate when their actual input or geometry paths change. Only screen-pixel appearance/hardware-specific DPI, OS mouse routing, and real GPU dual-display behavior require a bounded physical check when affected; never carry an old checkpoint-specific red/green assertion into another tree.

## Shared paint/Edit parity acceptance

The selected Edit mapper must project actual QML paint through inherited item/QML Scale/Translate/Rotation, ancestor clipping and inherited visibility without adding a normal-runtime geometry observer. Read ordinary bindable ancestor geometry directly; QQuickItem.transform is a non-bindable list and must never be enumerated by an active QML binding. QML transform owners declare the **applied properties** of their named Scale/Translate objects through `customEditMappingDependency`, rather than early-notifying source/model inputs; the mapper reads those markers on retained ancestors and uses `mapToItem()` for exact paint geometry. Guard both the absence of transform-list binding warnings and stable Edit delegate identity under repeated transform changes. Semantic role identity is stable while paint availability toggles, including Pulse artwork, Weather location text and Media optional bands; Clock mode-specific roles remain intentional. Transparent structural Edit targets may represent actually painted child content and must not be discarded solely for opacity. Family QML remains responsible for normal X/Y reflow; CUSTOM owner remains responsible for edit/persistence/Undo. Clock's four digital targets and analogue face/three footer targets publish their own applied Scale/Translate signature, with the analogue face's scale origin explicitly included; mode-specific roles and the transparent centred face carrier remain intentional. No source-input-only signature is sufficient when QML applies the transform asynchronously. Clock markers are lightweight property bindings updated at actual geometry-change edges, not a second clock tick, timer, scene scan, or persistence owner.

`tests/test_qtquick_child_mapped_geometry.py::test_selected_mapper_tracks_nested_qml_scale_translate_clips_and_role_readiness` verifies dynamic and direct applied-object QML transforms, ancestor clipping, retained role identity and both geometries with **different independent oracles**. The Qt test performs direct QML transform writes via a QML-owned function and `QQmlExpression`; do not fetch `QQuickTranslate*` with Python `QObject.property()` because PySide6 has no converter for that pointer. On PySide6 builds where `QQmlExpression.evaluate()` returns `(value, isUndefined)`, unwrap the primitive and assert `isUndefined` is false before checking the requested applied transform value; do not compare the tuple to a scalar. While a clip is active the exact visible intersection in the fixture's axis-aligned clipping-parent coordinates is projected into the Edit frame, and only after clip-off are all four uncut target corners compared. A full-target bounding box must never be substituted for the clipped visible paint inside the 24-update stress phase. `tests/test_qtquick_other_family_owner_save_reopen.py::test_other_family_real_owner_save_live_promotion_fresh_generation_and_reedit` checks exact painted target object and its actual exposed rectangle on the third generation, plus Cancel/no-write preservation. `tests/test_qtquick_media_presentation.py::test_media_volume_opposite_axis_reflow_updates_live_edit_proxy` finds the live visual delegate, varies supported normalized volume-bar X/Y offsets and moves the parent across the display centre to exercise automatic accessory-side relocation. It compares the proxy to the actual painted track without ever asserting an artificial direct `slider.x/y` move against `anchors.fill`. The nested-transform Qt gate captures and rejects selected-mapper non-bindable-property and binding-loop warnings across repeated retained-transform edits. The source gates reject reading `node.transform` or `ancestor.transform` inside the selected Edit mapper. These Qt cases require **Windows/PySide6 execution** when affected behavior changes; syntax/source checks alone cannot certify real-time drag responsiveness.

**Live-normalization / role-lifetime gate:** `tests/test_live_normalization_role_lifetime_contract.py` protects stable semantic arrays in Media, Reddit/Reddit2, Gmail, Weather, System Stats, Friend Pulse, Achievement Pulse and Abandonment Issues, including the external-volume distinction, the whole metric-stack role and named `baseAuthoredWidth/Height` on dense families. `tests/test_qtquick_child_mapped_geometry.py::test_selected_roles_retain_identity_when_live_normalization_baselines_change` uses a native retained QML object to change the card's independent X/Y, Media-like accessory X and dense family's named authored X/Y baselines twenty times while checking all three original delegate identities, bindable baseline values, actual painted target/blue rectangle agreement, role hide/reveal and full Edit teardown without Qt warning cascades. Pair these with existing real-family Media opposite-side volume, Reddit/Gmail header/refresh and shared owner tests; source-only passes are not native proof, and the accepted whole-list column rails must not be reinterpreted as individually editable row positions. Clock's separate changing preferred text dimensions continue through the same selected-only normalization path. This gate adds no normal-runtime observation.

**Selected child snap-guide churn gate:** `tests/test_custom_layout_guides_contract.py::test_child_snap_guide_chrome_is_retained_and_idempotent_during_selected_edit` protects two Edit-only retained guide items, no per-sample guide arrays or Repeaters and no extra scheduler/persistence path. `tests/test_qtquick_child_mapped_geometry.py::test_child_snap_guides_retain_one_item_per_axis_during_repeated_pointer_samples` uses the actual selected retained QML scene to verify unchanged guide QQuickItem and role-delegate identities through 24 repeated samples per position, both axes, two semantic styles, hide/reveal and teardown. The Edit-only guide-publisher test does not by itself prove end-to-end physical drag latency or wider outer peer-guide performance; no repeat physical checks for already accepted families are required solely because this guide chrome changed.

## Current child-geometry and owner lifecycle gates

The inventory below describes the live contracts and their evidence state. New or
modified tests must be entered here in the same change as their source changes.
These focused gates supplement rather than replace the maintained destination profile.

| Contract | Executable gate | What the gate establishes |
| --- | --- | --- |
| Normalized child persistence, physical floor and resize no-churn | `tests/test_qtquick_child_persist_floor_regression.py` | Stable persisted geometry and no republish floor churn across enrolled families. |
| Shared parent/Visualizer Edit no-op publication and gesture release | `tests/test_qtquick_edit_noop_publication.py` | No-op gestures do not manufacture state/publication and release retires transient work. |
| Mapped child/proxy geometry and cancelling axes | `tests/test_qtquick_child_mapped_geometry.py` | Selected Edit proxies follow real painted geometry through transforms/clips while axis cancellation remains coherent. |
| Reddit/Reddit2 committed painted child reopen | `tests/test_qtquick_reddit_child_committed_reopen_scene.py` | Save/live promotion/fresh display/re-Edit uses committed painted geometry rather than stale delegates. |
| Achievement Pulse semantic header/list flip and paint | `tests/test_qtquick_achievement_pulse_presentation.py` | Header/list semantics, text/badge paint and family reflow remain coupled to one orientation intent. |
| Achievement Pulse/Weather owner save and fresh generation | `tests/test_qtquick_other_family_owner_save_reopen.py` | Real owner Save/live promotion/fresh generation/re-Edit with injected cached provider data. It does not establish external-service activation. |
| Reddit/Reddit2 title/time clearance | `tests/test_qtquick_reddit_presentation.py`, `tests/test_reddit_spacing_contract.py` | AGE/AGO/title rails remain legible across ordinary/scaled CUSTOM geometry and both alignments. |
| Bounded three-action Edit undo | `tests/test_qtquick_custom_layout_owner.py::test_three_level_undo_retains_only_three_completed_edit_actions`, `tests/test_qtquick_custom_layout_owner.py::test_three_action_undo_is_global_across_items_and_clears_on_retirement`, `tests/test_qtquick_input_controller.py::test_edit_only_undo_and_lock_hotkeys_preserve_plain_z_and_ignore_repeats` | Only completed state-changing Edit actions enter the global three-action history; no pointer-sample snapshots, redo, polling or Settings writes. |
| Media compact-height and independent-axis reflow | `tests/test_qtquick_media_presentation.py::test_compact_media_essential_rows_survive_flip_and_transient_capability_loss`, `tests/test_qtquick_media_presentation.py::test_media_child_axis_edits_keep_live_band_flow_at_compact_y`, `tests/test_media_content_extent_contract.py::test_media_nested_seek_and_transport_keep_axis_independent_band_reflow` | Compact active tracks, saved offsets and flipped right-rail metadata reproject coherently. Model/source gates do not substitute for a changed real-owner physical sequence. |
| Outer-only child containment and dense requirement retirement | `tests/test_custom_layout_guides_contract.py`, `tests/test_qml_reflow_loop_contract.py`, `tests/test_qtquick_child_edit_off_dependency_contract.py`, `tests/test_quick_child_paint_containment_contract.py`, `tests/test_qtquick_child_persist_floor_regression.py`, `tests/test_qtquick_custom_layout_owner.py` | Children remain inside their legal parent/accessory surface and cannot resurrect the retired child-driven parent-growth owner. Dynamic Qt/pointer feel still requires native evidence when this path changes. |
| Clock paint/Edit alignment and compact intrinsic fit | `tests/test_qtquick_clock_presentation.py::test_clock_selected_edit_proxies_follow_actual_applied_transforms_in_both_faces`, `tests/test_clock_applied_edit_transform_contract.py` | Digital/analogue targets follow applied transforms; compact digital paint fits without adding a second cadence/observer. |
| Media external-volume proxy and automatic side relocation | `tests/test_qtquick_media_presentation.py::test_media_volume_opposite_axis_reflow_updates_live_edit_proxy` | The Edit proxy follows the actual painted external-volume track while family logic remains free to choose left/right placement. |
| Reddit Restore Size loading/ready invariant | `tests/test_qtquick_reddit_presentation.py::test_reddit_loading_and_ready_state_use_the_same_authored_height`, `tests/test_qtquick_custom_layout_owner.py::test_flip_wheel_restore_repeatedly_returns_authored_shape_and_clears_stale_extent` | Authored preferred height remains stable across loading/ready and Restore clears stale extent without deleting valid CUSTOM placement. |

**Dense-family reflow and test lifetime:** Achievement Pulse's Header-flip and Abandonment Issues' BACKLOG/semantic-flip Qt tests check painted rails and unchanged committed parent `content_extent` across repeated event-loop settlement. `customEditableChildRequirementTarget` is deliberately null in both families; tests must not resurrect or inspect the retired `customChildRequirement` object. The live-normalization stress fixture detaches its test-owned probe before retiring its presentation host, preventing test teardown from accessing a destroyed C++ `QQuickItem`; this is distinct from the asserted retained selected-Edit delegate identity during the test. Full/native Qt execution is required after fixture or oracle edits: import-free source checks cannot certify lifetime or rendering.

The offline Achievement Pulse/Weather Save/reopen fixture explicitly activates the
real retained-family ports and injects synchronous cached data. It must not be used
to certify full service activation or external-service readiness. A future
activation regression requires a separate test with a real activation
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

**Repeated-list semantic rail swap (Qt/physical acceptance complete):** `tests/test_column_rails_contract.py` validates all permutations, no-op and invalid input. `tests/test_qtquick_custom_layout_owner.py::test_column_rail_swap_is_one_bounded_owner_undo_action_and_restores_authored_order` checks one whole-list discrete Undo transaction without Settings I/O. `tests/test_qtquick_reddit_presentation.py::test_three_semantic_column_rails_reorder_every_retained_post_and_rehydrate` and `tests/test_qtquick_gmail_presentation.py::test_gmail_semantic_column_rails_reorder_all_retained_message_rows` check actual retained painted positions in all rows, order reversal, header-flip independence, Y/width reflow and retained delegate identity. The operator accepted the Windows and physical rail checks; retain this suite as regression coverage. The canonical CUSTOM payload is `column_rails`, never per-row `x_offset`; no normal-runtime rail observer, and a dedicated column-order notification
so child-geometry changes do not churn the list columns. See `Docs/Guides/Custom_Child_Placement_And_Headers.md`.

**Normal-runtime cross-family churn gate:** `tests/test_qtquick_normal_runtime_publication_churn.py` protects unchanged versus independent effective QQuickItem property writes, QML-side divergence and repeated retained menu-model binding. Pair it with the real ordinary-host/context-menu Qt suites when that path changes; static/recording-target passes do not establish measured pointer latency or repaint cost. Do not rerun unrelated accepted families solely to refresh a count.

## 2. Status vocabulary

Use these labels consistently:

- **PASS** — executed against the stated tree/environment and passed.
- **NEEDS RUN** — current coverage is structurally valid but still requires the intended Windows/PySide/OpenGL or installed environment before it can be acceptance evidence.
- **ENVIRONMENT BLOCKED** — collection/execution cannot begin because a required platform/runtime dependency is absent. This is not a product failure.
- **RED** — a current test executed in an appropriate environment and failed a current contract.
- **OBSOLETE** — the test targets a retired owner/architecture and no longer expresses a current contract. Delete it or preserve its lesson in Historical Bugs.
- **REHOME** — only part of a mixed old test still has value. Move that assertion to the current owner/suite and retire the dead shell.

A green static/source test is never a substitute for a required Qt/QML, real-GL or installed physical gate.

**Cross-family Edit and repeated-role gate:** The retained QML geometry checks cover Clock digital/analogue mapped child targets, System Stats' single retained metric-stack Edit role against the union of all enabled painted cards (both header orientations, compact/expanded X/Y and shared block offsets), with no per-metric ghost Edit handles, and Friend Pulse's row/grid first painted frame, avatar and username against its grouped targets under live resize. System Stats' import-free role/rail guard in `tests/test_system_stats_reflow_contract.py` rejects overlapping metric child editors; the real selected-Edit Qt gate checks the three retained roles, exact mapped group bounds, all painted panels and absence of role-delegate reconstruction during repeated flip/move updates. A physically accepted family is not retested solely because a test-only fixture changed. The 0.02px tolerance applies to exact painted target/proxy bounds; the Clock's non-painted Column layout-box containment alone permits 1.0 logical px for fractional text metrics. The selected Edit lifetime test also covers 20 independent card, accessory and dense authored-baseline updates, three retained delegate identities, exact paint and warning absence. Native Qt is required for retained scene truth and no-warning evidence; source-only validation cannot establish drag latency or formal performance neutrality.

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

### 5.1 Stale-oracle discipline

A red test is evidence to classify, not permission to resurrect retired architecture or weaken a current product contract. Reconcile each failure against the exact current owner first. Persisted-input compatibility retirement is governed per item by `Docs/Architecture/Persisted_Input_Compatibility.md`; update the complete affected test cascade in the same change. Keep checkpoint-specific suite counts and closed audit narratives out of this living reference.

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

**Runtime replacement / Settings admission:** `tests/test_qtquick_transition_controller.py` guards silent transition terminalization and forbids live `clear_all()` / `unit.clear()` from the full destruction path; `tests/test_visualizer_failover_adapter_retirement.py` guards manager + display-unit Visualizer owner detachment after confirmed retirement; `tests/test_audio_event_mailbox.py` guards bounded callback delivery and callback-cycle severing at retirement; and `tests/test_settings_dialog.py` guards semantic tab/section/builder restoration with top-of-section scroll anchoring. These are current lifecycle contracts. Qt/Windows execution is required for replacement-generation, retained-scene and native COM acceptance; pure source/default/mailbox gates alone do not close those physical checks.

**Replacement first image, hang window, reveal ownership and quit (R-96):**
- `test_monitor_replay_admission.py`: one first-image admission per replacement.
- `test_replacement_hang_window.py`: one shared construction path and a hang window from construction to reveal.
- `test_startup_reveal_stalled_display.py`: failed and stalled siblings; the two-monitor late-recovery bar reads each display's gate at the real 1,800 ms.
- `test_quit_request_render_thread_gil.py`: a subprocess with a real threaded-GL window running the production node; the queued quit must exit, and `MODE=synchronous` reproduces the wedge.
- `test_qtquick_native_texture_wrapper_retention.py`: uploads leave no Python `QSGTexture` wrappers (R-97).

These bars run real engine/manager code on the real Qt loop. Native Windows wake and topology acceptance stays physical.

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

Expansion gates: `test_qtquick_glass_shatter.py` (fracture coverage, bounded topology, depth scissor and failed cleanup), `test_qtquick_instanced_transition_effects.py` and `test_qtquick_tile_departure.py` (closed cube topology, ray-exit departure and material controls), `test_qtquick_crumble_volume.py` (closed fracture solids, parent-bound chip debris and release weighting), `test_qtquick_melt_surface.py` (bounded implicit liquid surface), `test_qtquick_organic_surfaces.py` (bounded raised Ink topology), `test_qtquick_transition_material_settings.py` (canonical material ranges), and `test_qtquick_future_transition_gl.py` (actual endpoint/near-endpoint pixels, seed/option/direction sensitivity and retirement). `test_qtquick_organic_transition_renderers.py` no longer owns actual-driver compilation. Registry/request/default/Settings tests remain the integration authority. `test_tendril_retirement.py` permanently guards the rejected Tendril capability against registry/default/runtime/source resurrection and verifies stale persisted state is pruned.

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

Historical Bugs R-82/R-83 and related worker/lifetime records own the mechanisms that justified permanent regressions. `test_network_tls_context.py` protects the one verified direct-socket TLS context (R-98). Memory-owner bars (R-99):
- `test_image_pipeline.py`: consumed derivatives leave the cache.
- `test_qtquick_native_texture_handoff.py::test_parked_transition_node_pins_neither_frame`
- `test_native_thread_pools.py`: one OpenBLAS thread in the app and its spawned workers.
- `test_settings_manager.py::test_settings_reads_leave_no_reference_cycles` The test suite should encode their surviving invariants rather than repeat the incident diary here.

## 7. Test infrastructure rules

### Destination profile

- every profile target must resolve to an existing file/node id;
- each target runs in a fresh subprocess;
- do not add obsolete coverage merely because it once represented a migration gate;
- add durable regressions for current behavior likely to recur;
- keep environment-specific coverage visible rather than silently dropping it.
- never wait with `QTest.qWait` around a threaded-render `QQuickWindow`: it keeps the GIL while processing events, and the first expose then deadlocks against the render thread's GIL acquisition. Use `qtbot.wait` or `QEventLoop.exec()`, which release the GIL (R-96).

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

### Feeds | Custom 1 regression routing

`tests/test_feed_core.py` protects RSS/Atom normalization, image-optional validity, relative URL resolution, magnet action/title fallback, bounded conditional transport, durable cache corruption handling, last-good retention, persisted backoff, CUSTOM endpoint cache isolation, built-in endpoint migration fencing and cache-write failure tolerance. `tests/test_feed_projection.py` protects List/Grid/Compact projection and sparse per-story Grid imagery: one image-less story cannot globally veto unrelated accepted local artwork. `tests/test_presentation_image_coherence.py` protects the pure generation-coherence primitive retained for consumers with an all-or-none image policy; Steam Games You Follow instead supports mixed image-optional stories. `tests/test_storage_paths.py` and `tests/test_cache_maintenance.py` protect canonical Feeds cache placement and the clear-cache allowlist. The cache inventory tests also check the six resolved family targets, Steam followed-news/name/inline-image deletion, preservation of Friend Pulse pins and credentials, and zero-file reporting as a disk-only result; `tests/test_widgets_tab_general_current.py` covers the real target tooltip and warns about retained live data instead of claiming visible caches are empty. `tests/test_feed_runtime.py` protects generation-shared source ownership, same-endpoint deduplication, active-lease cadence recomputation, cache-first scheduling, manual refresh and retirement/callback detachment. `tests/test_qtquick_feed_component_load.py` is the mandatory native `QQmlComponent` compile/retained-visual check: it catches unsupported custom `ShadowedText` properties capable of blocking screensaver startup, traverses the actual QQuick visual-child tree for Repeater delegates, exercises sparse local Grid art, independent X/Y extent, the five stable child roles including the real-artwork edit proxy, scale-below-1 authored-surface containment, and widget-wide semantic header flip without row-model recreation. Source-string checks cannot substitute for this gate. `tests/test_feed_custom_reflow_contract.py` additionally guards four-direction Grid text reflow around freeform artwork and the no-geometry-to-Python boundary. `tests/test_feed_header_parity_contract.py` protects the shared semantic-colour `BrandedHeader`, separate below-pill subtitle, widget-wide semantic flip and cached QPainter vector-segment monogram, including the negative prohibition on a FEEDS-local monogram/header renderer, image-pixel mirroring or runtime font-glyph dependency. `tests/test_click_affordance_parity.py` protects the current interaction language: semantic colour at rest; bright-white active borders/separators/emphasized text where admitted; neutral-white borderless wash for dense FEEDS/Reddit/Gmail rows; white Friend Pulse action cues; white Achievement/Abandonment artwork outlines; and border-free Media seek/transport hover. `tests/test_qtquick_gmail_presentation.py` also verifies saver-side Gmail authorization remains interaction-admission gated before the injected Settings action can run. `tests/test_feed_f2_contract.py` protects the admitted Custom 1 family/registry/Settings/QML/action boundaries, including explicit TEST FEED, no QML network/timers/remote images, geometry-bounded complete-row/cell presentation and secure HTTP/S action routing. `tests/test_rss_bounded_feed_transport.py` uses AST inspection of actual `feedparser.parse(...)` call arguments; comments/documentation are not valid failure oracles. No deterministic test in this set should require live publisher access; `tools/feed_probe.py` is the separate native probation path for current external reachability.

A container lacking the installed `feedparser` dependency or repository PySide harness cannot replace native Windows evidence by syntax/source inspection alone. The current requested Custom 1 regression selection is green on Windows, and physical artwork reflow plus click-highlight/link behavior has current-tree acceptance. Before enabling Custom 2–4, close only the remaining physical lifecycle gates in `Current_Plan.md`: full Edit save/reopen/flip/undo/lock, subtitle setting round-trip, fresh offline last-good restart, and clean source/artwork retirement. Multi-CUSTOM admission additionally requires simultaneous endpoint cancellation/pruning and artwork-eviction fencing. NEWS provider promotion requires repeated native `feed_probe.py` evidence and cannot be inferred from deterministic unit tests.

### Steam inline imagery and disk-budget gate

`tests/test_steam_followed_inline_news_artwork.py` covers complete Steam Clan image-macro removal from preview prose, up to three validated local article thumbnails, offline restart, invalid reference rejection, failed lookup negative caching, independent game/inline cache pruning, and recovery of pre-thumbnail ranked/per-game cached article rows whose preview contained image paths without image-reference fields. Assert cache-first visual metadata and full text sanitation before the affected game's next rolling-news batch, with a second offline source lifetime; fresh-news fixtures alone do not protect existing user caches. `tests/test_steam_profile_assets_events.py` additionally guards the shared Steam asset writer/pruner. Source and cache fixtures retain game news and hub click eligibility when old records have no source URL or contain a rejected article target; Qt staging verifies no extra public row publication is required for a private link revision, portable QUrl file-path identity, a responsive thumbnail rail and preview text based on the actual displayed thumbnail count. `tests/test_qtquick_games_you_follow_staging.py::test_followed_inline_article_thumbnails_keep_local_sources_and_retained_slots` is the *native* QML role/border/geometry/source-release gate; a green Python source fixture cannot certify appearance. Disk caps are per-profile/per-cache-family, not proof of an aggregate installation-wide budget.

**Retained refresh and inner-shadow gate:** The native `tests/test_qtquick_games_you_follow_staging.py` exercise must distinguish locally cached third-image availability from the image source of a third *painted* frame, including a narrower two-image tile and a broad tall single-column three-image tile on the same retained model. It also checks that artwork and thumbnail contacts exist while the tile's cached frame shadow stays separate. `tests/test_qtquick_reddit_presentation.py` (both Reddit identities), `tests/test_qtquick_gmail_presentation.py` and `tests/test_qtquick_feed_component_load.py` cover real retained refresh controls and QML readiness; hover treatment and cursor require native interaction/physical acceptance, not source-string assertions; the current shared highlight behavior has operator acceptance, so future changes must preserve or deliberately re-open that evidence. `tests/test_qtquick_friend_pulse_presentation.py` covers row/grid frame and avatar contact targets with unchanged authored dimensions. Preserve stable child-role identity, no new image shaders, retained shadow-direction projection and safe normal/Edit hitbox gating. The source-only Steam news tests do not establish Qt painted-state or shadow acceptance.

### Games You Follow | current regression routing

`tests/test_steam_games_followed_source.py`, `tests/test_steam_games_followed_projection.py`, `tests/test_steam_games_followed_g0.py`, `tests/test_steam_games_followed_news_g0.py`, `tests/test_steam_followed_shared_runtime.py` and `tests/test_games_followed_live_admission_contract.py` cover followed-set provenance, bounded newest-first source selection, durable private cache and incremental maintenance, generation/shared-owner retirement, projection and admitted runtime behavior. `tests/test_steam_games_followed_g2_staging_contract.py` protects the staging/presentation contracts although the family is now live; the filename is not a claim that the product remains unadmitted. `tests/test_steam_followed_metadata_and_artwork.py` covers durable AppID name hydration/restart/negative retry, correct attribution without title text, mixed/corrupt artwork and stale snapshots without live network. `tests/test_qtquick_games_you_follow_staging.py` exercises actual Qt/QML retained slot identity, paint-capacity equivalence, reflow, game-name projection and mixed-image rail/placeholder admission on Windows. A green automated gate still does not prove real provider language accuracy, Steam's personalized What's New parity, hardware/network cost or every live article route. The current display/name/thumbnail/hover behavior is accepted; the remaining independent live check is a newly refreshed syndicated story that actually carries its validated original article URL, because legacy cached rows without one correctly fall back to the app news hub.
