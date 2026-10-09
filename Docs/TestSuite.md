# Test Suite Guide

This file is the **current test/acceptance authority** for SRPSS. It describes what deserves trust now, how to classify evidence, and which architecture contracts must stay guarded. It is not a checkpoint diary or migration changelog; source control and `Docs/Historical_Bugs/` preserve chronology.

`Current_Plan.md` owns execution order. The exact source tree plus `tests/run_chunked.py` own executable inventory. `Docs/Reference/Harness_Index.md` owns operator-tool/harness lookup.

`tools/run_matrix.py` is the maintained bounded RUN coordinator. Its JSON case contract, source/argument allowlists, per-run log
snapshots, output schema and physical-acceptance limits are documented in `Docs/Reference/Harness_Index.md` → Bounded
self-terminating RUN sessions. It is operator tooling, not a test-runner facade or product runtime owner.

**Execution owner:** Frozen-product builds, installer compilation and lengthy whole-suite Windows acceptance are operator-run only, with logs delivered to the agent. A source/documentation agent must **never attempt a build**, and should return only affected focused tests unless asked to request or run a full suite.

## 1. Current authority and inventory

The maintained product profile is `destination` in `tests/run_chunked.py`.

The live `test_*.py` inventory and maintained destination targets are resolved from the actual source tree and `tests/run_chunked.py`. Do not copy a previous checkpoint’s count into this reference.

The destination profile is **target-isolated**: each selected target runs in its own fresh pytest subprocess so queued Qt/QQuick teardown from one target cannot poison another target's result.

Do not record a transient focused-run status or checkpoint-era target count in this guide. Re-evaluate the maintained profile from `tests/run_chunked.py` and report PASS/RED only from an actual run on the tree being discussed. Historical performance landmarks belong in `Docs/Historical_Bugs/` and the relevant Guardrails, not in current suite inventory prose.

**Evidence rule:** Targeted Windows Qt tests and operator-observed behavior are distinct claims. Unrelated families need not be rerun merely to document another family. A focused green selection establishes only the submitted tests on that exact tree, not full-suite completion, a live-network benchmark or universal physical visual acceptance. For subsequent code changes, execute the affected tests against that changed tree.

The maintained `destination` profile's status must come from its actual current run, not from piecing together passing focused counts from other checkpoints.

The current agent/container may lack PySide6/OpenGL. In that environment, a collection failure caused by missing runtime dependencies is **ENVIRONMENT BLOCKED**, not a product RED and not a PASS.

## 1.1 Test durability and authority hygiene

Tests are strict about product contracts, not accidental copies of today's authored data. Mutable defaults, extensible registry membership/cardinality and curated preset payloads remain owned by their canonical source. Authored Markdown explains contracts and is never a proxy runtime oracle. Behavior tests derive expectations from the owning source or use self-owned fixtures; exact literal pins remain appropriate when the literal itself is a protocol, compatibility, golden, geometry, ownership or negative-control invariant. The blocking audit follows canonical-default aliases transitively so an intermediate `widgets = defaults[...]` assignment cannot hide a copied authored value.

Runtime-shaped worker fixtures must preserve production callback topology. A fake may execute work synchronously, but when production completion is asynchronous it should queue that completion and let the test drain it explicitly; do not invoke completion re-entrantly from inside ``submit_*``. For shared FEEDS/NEWS owners this is required so cache admission, serialized remote work and family settlement are tested without sleeps/polling or impossible nested callbacks.

The maintained blocking bar is:

```powershell
python tools/test_durability_audit.py
python -m pytest tests/test_test_suite_durability.py tests/test_default_pin_scan.py tests/test_test_oracle_review.py -q
```

`tools/default_pin_scan.py` is deliberately review-only. It filters literal dict values explicitly authored by the same test, but computed/control-driven fixture values and legitimate exact contracts may still appear and require review. `tools/test_oracle_review.py` is also review-only: it separates source-string implementation oracles, exact UI-copy oracles and potentially intrusive window operations for classification. Neither review queue changes test selection or acceptance: do not skip, xfail, deselect, stop a run or request operator action solely because a candidate exists. Never mass-edit either queue. Full policy, examples, source/UI-copy markers and non-intrusive-window guidance live in `Docs/Guides/Test_Durability.md`.

## 1.2 Qt delivery and painted-geometry evidence

`tests/test_qt611_display_identity_migration.py` crosses runtime identity, committed hydration, Clock face selection,
Arrange and explicit save: changing a manufacturer label must preserve saved geometry, merge independent variants,
avoid another monitor's data, and retire old keys without repeated migration. `tests/test_qt611_presentation_messages.py`
parses every canonical QML component and captures warnings during real construction of every ordinary family
(both Clock faces), exercises onboarding paint
with pixel and point fonts, and reproduces the native Windows 11 combo font warning in a fresh process before
proving identical text metrics and zero font warnings with the corrected shared style.
`tests/test_qtquick_blinds_transition.py` compiles/links the authored band shaders in a real OpenGL context;
the existing Blinds smoke checks source/midpoint/destination patterns and retirement per direction.
`tests/test_qt611_shader_admission.py` compiles the registered transition/Visualizer implementations, including
optional scene3d motion/trail/AA/post variants, proves resource retirement, and renders the actual Spectrum preview
with the production OpenGL floor. These are bounded admission checks, not aesthetic or long-duration acceptance.

`tests/test_qtquick_bootstrap.py` verifies the strict 4.6 Core / GLSL 460 floor, actual-context admission/retirement,
and fresh-process startup parity for production, the Settings flicker diagnostic and both ordinary-widget capture
tools. The capture cases render real retained cards and reject Qt warnings. Its shader-source gate covers runtime
and maintained diagnostics; shared scene3d GPU mirrors, grid, environment, target, trails and uniform fixtures also
compile GLSL 460 while retaining their independent pixel, packing, state-restoration and retirement oracles.

Immutable resource ownership is covered by `tests/test_qt_resource_assets.py` (Qt lookup and lazy Guided Setup
registration), `tests/test_widget_theme_link_and_asset_contract.py` (immutable resources versus editable themes),
and the retained widget/About tests. `tests/test_qrc_regeneration.py` protects selected-toolchain regeneration,
staleness, failure and Foundry sequencing; `tests/test_build_runner_cancellation.py` protects the shared process-tree
owner. These are source/resource proofs; fresh frozen size and installed rendering remain operator-build evidence.
`tests/test_clock_timezone_resolution.py` exercises the actual Clock resolver for local/UTC/explicit offsets,
named DST and non-DST zones, persisted aliases, and the Troll/Casablanca cases that require the retained database.

A green geometry owner/source suite does not verify which MouseArea receives a click or whether a short post headline makes a timestamp rail float. `tests/test_qtquick_edit_pointer_delivery.py` sends real press/release events into a QQuickWindow and verifies top-strip selection, header-gap selection, and that the flip target calls the existing flip authority instead of selecting/moving the parent. `tests/test_qtquick_reddit_presentation.py` asserts retained Reddit/Reddit2 title/age/AGO paint-item rectangles and common timestamp alignment across short and long titles, parent resize and semantic flips. Both are Windows/PySide6 a required native regression gate when their actual input or geometry paths change. Only screen-pixel appearance/hardware-specific DPI, OS mouse routing, and real GPU dual-display behavior require a bounded physical check when affected; never carry an old checkpoint-specific red/green assertion into another tree.

## Shared paint/Edit parity acceptance

The selected Edit mapper must project actual QML paint through inherited item/QML Scale/Translate/Rotation, ancestor clipping and inherited visibility without adding a normal-runtime geometry observer. Read ordinary bindable ancestor geometry directly; QQuickItem.transform is a non-bindable list and must never be enumerated by an active QML binding. QML transform owners declare the **applied properties** of their named Scale/Translate objects through `customEditMappingDependency`, rather than early-notifying source/model inputs; the mapper reads those markers on retained ancestors and uses `mapToItem()` for exact paint geometry. Guard both the absence of transform-list binding warnings and stable Edit delegate identity under repeated transform changes. Semantic role identity is stable while paint availability toggles, including Pulse artwork, Weather location text and Media optional bands; Clock mode-specific roles remain intentional. Transparent structural Edit targets may represent actually painted child content and must not be discarded solely for opacity. Family QML remains responsible for normal X/Y reflow; CUSTOM owner remains responsible for edit/persistence/Undo. Clock's four digital targets and analogue face/three footer targets publish their own applied Scale/Translate signature, with the analogue face's scale origin explicitly included; mode-specific roles and the transparent centred face carrier remain intentional. No source-input-only signature is sufficient when QML applies the transform asynchronously. Clock markers are lightweight property bindings updated at actual geometry-change edges, not a second clock tick, timer, scene scan, or persistence owner.

`tests/test_qtquick_child_mapped_geometry.py::test_selected_mapper_tracks_nested_qml_scale_translate_clips_and_role_readiness` verifies dynamic and direct applied-object QML transforms, ancestor clipping, retained role identity and both geometries with **different independent oracles**. The Qt test performs direct QML transform writes via a QML-owned function and `QQmlExpression`; do not fetch `QQuickTranslate*` with Python `QObject.property()` because PySide6 has no converter for that pointer. On PySide6 builds where `QQmlExpression.evaluate()` returns `(value, isUndefined)`, unwrap the primitive and assert `isUndefined` is false before checking the requested applied transform value; do not compare the tuple to a scalar. While a clip is active the exact visible intersection in the fixture's axis-aligned clipping-parent coordinates is projected into the Edit frame, and only after clip-off are all four uncut target corners compared. A full-target bounding box must never be substituted for the clipped visible paint inside the 24-update stress phase. `tests/test_qtquick_other_family_owner_save_reopen.py::test_other_family_real_owner_save_live_promotion_fresh_generation_and_reedit` checks exact painted target object and its actual exposed rectangle on the third generation, plus Cancel/no-write preservation. `tests/test_qtquick_media_presentation.py::test_media_volume_opposite_axis_reflow_updates_live_edit_proxy` finds the live visual delegate, varies supported normalized volume-bar X/Y offsets and moves the parent across the display centre to exercise automatic accessory-side relocation. It compares the proxy to the actual painted track without ever asserting an artificial direct `slider.x/y` move against `anchors.fill`. The nested-transform Qt gate captures and rejects selected-mapper non-bindable-property and binding-loop warnings across repeated retained-transform edits. The source gates reject reading `node.transform` or `ancestor.transform` inside the selected Edit mapper. These Qt cases require **Windows/PySide6 execution** when affected behavior changes; syntax/source checks alone cannot certify real-time drag responsiveness.

**Live-normalization / role-lifetime gate:** `tests/test_live_normalization_role_lifetime_contract.py` protects stable semantic arrays in Media, Reddit/Reddit2, Gmail, Weather, System Stats, Friend Pulse, Achievement Pulse and Abandonment Issues, including the external-volume distinction, the whole metric-stack role and named `baseAuthoredWidth/Height` on dense families. `tests/test_qtquick_child_mapped_geometry.py::test_selected_roles_retain_identity_when_live_normalization_baselines_change` uses a native retained QML object to change the card's independent X/Y, Media-like accessory X and dense family's named authored X/Y baselines twenty times while checking all three original delegate identities, bindable baseline values, actual painted target/blue rectangle agreement, role hide/reveal and full Edit teardown without Qt warning cascades. Pair these with existing real-family Media opposite-side volume, Reddit/Gmail header/refresh and shared owner tests; source-only passes are not native proof, and whole-list column rails must not be reinterpreted as individually editable row positions. Clock's separate changing preferred text dimensions continue through the same selected-only normalization path. This gate adds no normal-runtime observation.

**Selected child snap-guide churn gate:** `tests/test_custom_layout_guides_contract.py::test_child_snap_guide_chrome_is_retained_and_idempotent_during_selected_edit` protects two Edit-only retained guide items, no per-sample guide arrays or Repeaters and no extra scheduler/persistence path. `tests/test_qtquick_child_mapped_geometry.py::test_child_snap_guides_retain_one_item_per_axis_during_repeated_pointer_samples` uses the actual selected retained QML scene to verify unchanged guide QQuickItem and role-delegate identities through 24 repeated samples per position, both axes, two semantic styles, hide/reveal and teardown. The Edit-only guide-publisher test does not by itself prove end-to-end physical drag latency or wider outer peer-guide performance; require a physical check only when the changed seam can affect those properties.

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

**Repeated-list semantic rail swap gate:** `tests/test_column_rails_contract.py` validates all permutations, no-op and invalid input. `tests/test_qtquick_custom_layout_owner.py::test_column_rail_swap_is_one_bounded_owner_undo_action_and_restores_authored_order` checks one whole-list discrete Undo transaction without Settings I/O. `tests/test_qtquick_reddit_presentation.py::test_three_semantic_column_rails_reorder_every_retained_post_and_rehydrate` and `tests/test_qtquick_gmail_presentation.py::test_gmail_semantic_column_rails_reorder_all_retained_message_rows` check actual retained painted positions in all rows, order reversal, header-flip independence, Y/width reflow and retained delegate identity. Retain the native Qt suite as regression coverage; repeat physical rail checks only when paint/input behavior can change. The canonical CUSTOM payload is `column_rails`, never per-row `x_offset`; no normal-runtime rail observer, and a dedicated column-order notification
so child-geometry changes do not churn the list columns. See `Docs/Guides/Custom_Child_Placement_And_Headers.md`.

**Normal-runtime cross-family churn gate:** `tests/test_qtquick_normal_runtime_publication_churn.py` protects unchanged versus independent effective QQuickItem property writes, QML-side divergence and repeated retained menu-model binding. Pair it with the real ordinary-host/context-menu Qt suites when that path changes; static/recording-target passes do not establish measured pointer latency or repaint cost. Do not rerun unrelated families solely to refresh a count.

## 2. Status vocabulary

Use these labels consistently:

- **PASS** — executed against the stated tree/environment and passed.
- **NEEDS RUN** — current coverage is structurally valid but still requires the intended Windows/PySide/OpenGL or installed environment before it can be acceptance evidence.
- **ENVIRONMENT BLOCKED** — collection/execution cannot begin because a required platform/runtime dependency is absent. This is not a product failure.
- **RED** — a current test executed in an appropriate environment and failed a current contract.
- **OBSOLETE** — the test targets a retired owner/architecture and no longer expresses a current contract. Delete it or preserve its lesson in Historical Bugs.
- **REHOME** — only part of a mixed old test still has value. Move that assertion to the current owner/suite and retire the dead shell.

A green static/source test is never a substitute for a required Qt/QML, real-GL or installed physical gate.

**Cross-family Edit and repeated-role gate:** The retained QML geometry checks cover Clock digital/analogue mapped child targets, System Stats' single retained metric-stack Edit role against the union of all enabled painted cards (both header orientations, compact/expanded X/Y and shared block offsets), with no per-metric ghost Edit handles, and Friend Pulse's row/grid first painted frame, avatar and username against its grouped targets under live resize. System Stats' import-free role/rail guard in `tests/test_system_stats_reflow_contract.py` rejects overlapping metric child editors; the real selected-Edit Qt gate checks the three retained roles, exact mapped group bounds, all painted panels and absence of role-delegate reconstruction during repeated flip/move updates. A family is not sent through an unrelated physical gate solely because a test-only fixture changed. The 0.02px tolerance applies to exact painted target/proxy bounds; the Clock's non-painted Column layout-box containment alone permits 1.0 logical px for fractional text metrics. The selected Edit lifetime test also covers 20 independent card, accessory and dense authored-baseline updates, three retained delegate identities, exact paint and warning absence. Native Qt is required for retained scene truth and no-warning evidence; source-only validation cannot establish drag latency or formal performance neutrality.

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
python tools/check_defaults_authority.py
```

Run this whenever canonical defaults, Settings normalization or Defaults-Foundry-facing keys change. Nothing is generated from the defaults: readers use the canonical source (or an in-memory projection).

### 3.4 Focused tests first

Prefer the smallest set capable of falsifying the current change:

```powershell
pytest path\to\test_file.py -q --tb=short
```

Then widen to the maintained profile and installed/physical gates only when the change actually requires them.

### 3.5 Test-authority hygiene

```powershell
python tools/test_durability_audit.py
python tools/default_pin_scan.py --summary
python tools/test_oracle_review.py
```

`test_durability_audit.py` is blocking and intentionally high-confidence. The other two commands are review queues and always remain advisory. A review queue never changes suite selection, creates a skip/xfail, stops execution or becomes a request for operator action.

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
- Settings warms only hidden Display/Transitions; dormant tabs construct on first visit. Only SettingsManager repairs the OpenGL-only backend and hardware acceleration, without DisplayTab load/save writes; retain `test_settings_dialog.py`, `test_display_tab.py`, and `test_settings_manager.py` as targeted acceptance;
- descriptor/load/save/default keys remain mutually complete;
- compatibility normalization happens at explicit input boundaries and retired aliases do not become current output;
- read-oriented defaults/manifest validation and runtime preset catalogue loading must not rewrite shipped Visualizer preset artifacts; explicit regeneration is the source-tree write authority and no-op manifest writes must remain byte-stable across host newline conventions;
- Theme Foundry and Defaults tooling consume canonical schema rather than inventing parallel fields;
- collapsible-bucket identities stay canonical while persisted state remains sparse/local-scope;
- every descriptor with Technical controls has canonical outer/leaf UI-state identities, and every statically authored Visualizer builder bucket is represented in the canonical bucket map; lazy page construction must never discover schema identity by crashing at first selection;
- solid Spectrum bar tops retain at least one logical pixel of horizontal-cap coverage throughout fractional height motion; tests must inspect rendered endpoint pixels, not infer correctness from source strings or bar geometry alone;
- Windows PyAudio capture accepts a valid float32 payload according to the payload's actual channel-divisible length rather than treating callback `frame_count` as byte-shape authority; malformed channel framing still fails loud and bounded;
- the former Spectrum-borrowing Extruded profile is frozen under mode-owned keys with the historical Organs-effective 35-bar/128-sample response, schema-10 generated 33/512 bundles receive a narrow field-preserving schema-11 repair, and the owned Kick Lane Mix reaches the technical cache;
- the current 3D modes cross the full Settings-to-runtime ownership seam: resolved Custom/preset state configures the retained Quick owner, source/BeatEngine projection and Technical destination from each mode's own namespace, and Visualizer Reset returns those namespaces to canonical defaults without erasing the separate user-authored Custom preset cache;
- current 3D lazy Settings pages round-trip mode-owned/Technical values across reopen and through the real curated-preset ↔ Custom transaction without cross-mode leakage;
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

**Audio analysis is not visual shaping.** The active mode descriptor/capability projection owns admission to the Spectrum visual shaper: Spectrum, Extruded Spectrum and Shockwave Grid currently use it; Bubble, Sphere, Sine, Oscilloscope and Dev Curve do **not**. Those unshaped modes still consume shared FFT, pre-AGC bands, waveform/transient or onset data as appropriate; the shared worker legitimately returns zero Spectrum-shaped bars for them. Dev Curve has its own independent curve-layer shaping, which is not the Spectrum bar shaper. Do not force `_spectrum_shaping_enabled=True` in a nonshaper fixture, infer missing acoustic analysis from zero bars, or restore a retired cross-mode dependency to satisfy an old test. `tests/test_audio_analysis_only_isolation.py`, `tests/test_visualizer_spectrum_shaper_ownership.py` and `tests/test_visualizer_compute_lanes.py` guard the current boundary. An explicitly test-owned Spectrum DSP fixture **must** configure Spectrum's own source/shaper when the test is intended to measure shaped Spectrum bars; it must not borrow a curated preset.

**2D and Extruded Spectrum ghosts have different mode-owned configuration paths.** `tests/test_spectrum_rainbow_ghost_contract.py` checks the production source-routing seam (ordinary 2D ghost enablement must survive normalization, and Rainbow Ghost must not be confused with bar or border rainbows); `tests/test_qtquick_visualizer_spectrum.py`, `tests/test_qtquick_extruded_spectrum.py` and `tests/test_visualizer_settings_plumbing.py` cover the relevant retained render/settings ownership. Test a synthetic source with ordinary ghosting on/off and rainbow on/off, but do not pin the operator's Organ preset or make Extruded's already accepted ghost implementation inherit 2D settings. The presence, hue and motion of a painted trail require the appropriate native GL and eyes-on evidence when affected; green configuration tests alone do not establish visibility.

**Bubble is the strongest protected canary.** Idle traces are insufficient for any production change that touches Bubble cadence, simulation, payload/coalescing, reactive uniforms, event admission, attack/settle, elasticity/breathing, loud-passage expansion, ghost/tail motion or presentation timing. Such a change requires an explicit active-music installed lane plus operator feel. Never retune Bubble merely to satisfy a benchmark or stale golden.

**Preserve the operator's real-music reactivity corpus and its test route.** The canonical operator-authored schema-2 recordings live **only on the local Windows checkout** at `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\logs\visualizer_recordings` (repository-relative `logs/visualizer_recordings/`): `balanced.jsonl`, `heavy1.jsonl`, `quiet_intro.jsonl`, and `quiet_intro2.jsonl`. This local path and these recordings are a standing part of reactivity evaluation; do **not** delete their mention when updating this guide, silently replace them with synthetic clips, or expect normal Godzips to contain them. `tools.visualizer_replay.record.recorded_clips()` selects the active takes and deliberately ignores archived/derived `*_vN` and `*_noevents` takes. Do not alter, re-record, delete or reseed operator recordings as a byproduct of tests.

**Local-agent replay route (run from the operator's Windows checkout, not this archive):**

```powershell
$root = 'F:\Programming\Apps\ShittyRandomPhotoScreenSaver'
Set-Location $root
& '.\.venv\Scripts\python.exe' -m tools.visualizer_replay.mode_audit
& '.\.venv\Scripts\python.exe' -m tools.visualizer_replay.sphere_ramp
& '.\.venv\Scripts\python.exe' -m tools.visualizer_replay.bubble_judder --px-per-unit 300 --compare-release
```

`mode_audit` reads the local recorded-music corpus and measures Spectrum, Oscilloscope, Sine, Dev Curve and Shockwave Grid; `sphere_ramp` exercises Voxel Sphere's real-scale response; `bubble_judder` measures Bubble's observed radius and movement in the same recordings, including the release-envelope comparison. Agents must report the actual recorded clip names, mode, measured quiet/usual/loud response or event coverage, and any replay limitations. These offline results are **logical/observation evidence, not native GPU pixels, physical musical feel, or measured end-to-end latency**. Recordings complement rather than replace committed synthetic fixtures/frozen-settings regression floors; `python -m tools.visualizer_replay` and `tests/test_visualizer_replay.py` run that **different synthetic suite**, not the operator's recordings. Do not automatically recalibrate a golden from local music, nor force Spectrum shaping into modes that lack the Spectrum shaper.

`test_bubble_render_judder.py` protects the accepted release-envelope negative control and exact authored small-radius
snapshot targets. `test_bubble_fidelity_report.py` protects identity-preserving observation, truthful frame indices,
delay/pixel-bound/representation/simulation-change detection and unchanged production logical/Quick output while observing.
The replay report uses supplied projection pixels; first radius movement in a moving musical window is not causal latency.

Voxel Sphere is a standard selectable Visualizer while retaining lazy mode-owned behavior on the shared low-level Scene3D substrate. Its behavioural/state contract remains private and golden-protected; standard product admission does not make its reaction/material schema a shared family. `Docs/Reference/Sphere_Visualizer.md` owns the current contract; current Voxel Sphere tests supersede the retired smooth/material Sphere family.

User-authored Visualizer preset counts/numbers may be arbitrary or sparse. Runtime compacts selectable positions without renaming/deleting authored files or treating shipped manifests as catalogue authority.

3D Visualizers (Extruded Spectrum, Shockwave Grid) and the shared 3D Detail tiers:

- `tests/test_qtquick_extruded_spectrum.py`, `tests/test_qtquick_shockwave_grid.py` — renders through the production
  host on an offscreen context: projections against their GPU mirrors, Smooth Edges, polished Mirror Faces reflecting the
  displayed wallpaper (uploaded once per photograph) with the old procedural brushed/hash grain barred from returning,
  translucent painter's order, onset events taken once by serial, reactivity (quiet gating, big vs. medium hits, echo, idle
  swell), glow that only adds light;
- `tests/test_visualizer_prepared_reveal.py` — first use prepares on hidden frames, the reveal waits (with a deadline);
- `tests/test_visualizer_view_orbit.py`, `tests/test_visualizer_direct_gestures.py` — W/A/S/D and Alt + left orbit;
  Alt + right move and Alt + wheel resize outside Edit through Edit's own session, one commit at the gesture's end;
- `tests/test_visualizer_geometry_profiles.py`, `tests/test_visualizer_custom_geometry_profiles.py` — independent descriptor
  geometry-kind/layout-profile metadata, N-profile CUSTOM persistence, one-way legacy claim, hidden 2D↔3D and 3D↔3D hot-swap,
  profile-local Save/Cancel plus Arrange/slot/transfer, and proof that turn/tilt/camera state is not layout geometry;
- `tests/test_visualizer_edit_native_input.py`, `tests/test_visualizer_edit_footprint.py`,
  `tests/test_visualizer_edit_content_envelope.py`, `tests/test_visualizer_edit_orbit_publication.py`,
  `tests/test_qtquick_visualizer_render_bridge.py` — native QQuickWindow/QML wheel/move/orbit delivery, actual GPU footprint,
  projected eight-vertex 3D cage + north marker, stable gesture targets, bounded existing-wake framing with closed/deselected
  dormancy, and explicit profile-switch/Edit-Save snapshot discard/rebase without false geometry mismatch counts. Test stages lie
  inside their bound native window; hidden window pixels or supplied event coordinates alone cannot certify physical feel;
- `tests/test_scene3d_quality_settings.py` — the 3D Settings tab, the tier resolver (General / family / entry, Auto by
  GPU), the `transitions.detail_3d` bridge, each tier's levers in the renderers;
- `tests/test_visualizer_profile_lender_presets.py`, `tests/test_3d_curated_preset_ownership.py` — descriptor-declared
  borrowing, one-time ownership promotion and complete preset isolation through persisted startup and production callers;
- `tests/test_sphere_authoring_contract.py`, `tests/test_sphere_analysis_consumers.py`,
  `tests/test_sphere_render_authoring.py` — consumed technical ownership, RAW startup/Custom/SST promotion, real PCM analysis
  and GL proof for direct alpha plus Rainbow speed/extent;
- `tests/test_gl_error_policy.py` — per-call PyOpenGL error checking off at every entry, one check per node frame.

Cost: `tools/visualizer_cost_probe.py` (offscreen, production host; median/p90 CPU submit and GPU, GL-call counts).

### 6.5 Visualizer performance/trace authority

The frame-trace sidecar remains current diagnostic authority for Visualizer performance/freshness attribution. Historical R-87/CHK26 measurements and their comparison baseline live in `Docs/Historical_Bugs/` and `Docs/Guardrails/Performance_Optimization_Contract.md`; do not duplicate checkpoint status here.

High-value permanent guards include:

- `tests/test_visualizer_logical_hook_dormancy.py` — active-only Sine queries, activation-resolved hooks, registry-derived
  repeated switching, lazy import, malformed-descriptor rejection and synthetic registry growth without common-tick work;
- `tests/test_p2_audio_capture_lane.py` — backend create/open/restart/release are serial on the dedicated capture
  owner; blocked opens leave the GUI free, newest-state admission stays bounded, callback conversion cannot publish
  after stop, and rejected/failed native operations release exactly once or retain explicit ownership debt;
- `tests/test_affinity_lane_resource_ownership.py` — native ownership remains visible after task drain and worker join,
  while successful owner-thread release clears the existing lifecycle observation;
- `tests/test_qtquick_runtime_purity_source.py` — forbids retired Python pacing/live-state ghosts and other source-level regressions;
- `tests/test_frame_trace.py` — binary trace format, bounded rolling retention, optional phase/clip/Bubble attribution and backward-compatible reporting;
- `tests/test_lifecycle_window.py` — startup/teardown are not stall points: every display teardown opens the lifecycle window before anything is torn down and the current generation's coordinated reveal closes it; inside it the event-loop recorder, Visualizer latency and slow-tick warnings stay silent and count again after; the trace report keeps lifecycle frames out of steady-state spacing and flags late frames in the 2 s after a reveal;
- `tests/test_visualizer_switch_abc_harness.py` — causal switch/lifecycle scoring and freshness gates;
- real-GL visualizer clip/render tests where driver/context behavior matters.

The following are **not** valid “fixes” absent contradictory evidence: Python display-refresh pacing, `frameSwapped -> requestUpdate()` feedback, lower Bubble cadence/reactivity, global GIL switch-interval tuning, high-rate render text logging, or removal of inherited clip/stencil restoration fences. Detailed falsifiers live in R-87.

### 6.6 Transitions

Burn: `test_qtquick_burn_transition.py` also renders Flames and Ember Veins: flames only from the burning band upward (flames on both sides fail), veins only inside the char, both continuous at the ends. Expansion gates: `test_transition_direction_labels.py` (every direction label of every directional transition, resolved by production and rendered: the new picture shows first on the side the label starts from, and Block Spins turns its start side toward the viewer; the pre-fix labels fail 16 cases), `test_qtquick_glass_shatter.py` (fracture coverage, bounded topology, depth scissor and failed cleanup), `test_qtquick_instanced_transition_effects.py` and `test_qtquick_tile_departure.py` (closed cube topology, impulse launch not ease-in, shock-front timing, blast light, epicentre, the blast opening the picture at detonation, and weak-force departure), `test_qtquick_glass_layers.py` (Glass depth layers: at least 65% fewer on-screen shard intersections than none, crash partners share a layer, split pieces keep their parent's), `test_qtquick_block_spins_edge_glass.py` (3D Block Spins Edge Glass: only the side faces change, nothing gets darker so the sheen and gloss stay, the glass visibly shows the picture edge-on, exact endpoints on every axis, resolver repairs unknown values; negative controls drop the sheen and leak the glass onto a photo face), `test_scene3d_trails.py` (motion trails: ghosts a fixed real time apart, oldest and faintest first; the ghost transform needs a motion-writing fragment and draws only pieces that moved; on every transition that exposes Motion Trails, trails are light lines where pieces moved, nothing on nearly still ones, dropped at park; each ghost program variant is prepared once per pass), `test_transition_warmup.py` (S11/S10 gradual warm-up: after warming, the first frames of every registry-covered shared-3D transition compile nothing and allocate no scene textures or stream rings (and compile no graphics or compute programs) across anti-aliasing, motion blur, trails, bloom and Edge Glass setups, and park still releases every texture; a step compiles one program or allocates one texture unit, plainly, with no driver compile threads; without a render size it only compiles; the size estimate before any render is never smaller than the window; the background node's own program is a step; steps run only on spaced rendered frames and stop when done or cancelled, and a starting run cancels them; the next Random pick is reserved when the displays go idle and taken by the next rotation, replaced if it left the pool, and busy displays get nothing; the next batch meets the warmed spec and prepared geometry unless Settings changed; completion and the startup reveal trigger it), `test_scene3d_environment.py` (photo reflections: once per run, mipmapped, the lent photographs untouched; roughness blurs; Block Spins edge reflections alike in both halves of every spin, including diagonals; the Exploding Tiles wall exact until release; Glass reflection-free at sheen zero; copies dropped at park), `test_scene3d_grid.py` (the bendable grid: one winding, exact closed coverage, density by tier and aspect, a flat grid draws the photograph, normals face the viewer and follow a bend), `test_scene3d_camera.py` (the shared camera: overscan is the least zoom that covers the view, a moving camera never exposes frame edges, shake is deterministic and bounded), `test_scene3d_uniforms.py` (per-frame uniform blocks: driver-reported std140 offsets equal the Python layout, values arrive, the previous binding is handed back; partial named updates reach only their owned block even when the generic UBO binding changes, and draws before an update keep their values), `test_qtquick_beam.py` (Beam: the path starts and ends a reach off the picture at a steady pace, the brightness only gains, the last cure and spark finish before the run ends; both pictures exact beyond the beam's reach and the new one once cured for straight and diagonal directions (an unwindowed glow fails 6, a cure that never finishes fails 5), near-end continuity, scorch only behind the beam and darker there, the colour tints only the beam and its light, sparks only mid-run and gone at the end even on a one-second run (uncapped spark life fails), warm-up compiles and allocates nothing per run, resolver repairs), `test_qtquick_cube_turn.py` (Cube Turn: the turn and dolly mirror end square on with the camera home, exact and continuous ends for every direction and tier, the new picture arrives from the side the box turns away from (a swapped turn fails), gloss touches nothing at rest, warm-up builds the box, park/release, resolver), `test_qtquick_volumetric_dissolve.py` (Volumetric Dissolve: everything finishes by 0.93 with releases inside their window, the front starts where the sweep starts, a bounded grid, exact ends and near-ends for three directions on every tier, unreached cells exactly the old picture, Center Out reveals the centre first, mist only behind the front and never at the ends with texture unit 3 handed back, a warm-up that allocates the population and leaves the first frames nothing to compile or allocate, park drops copies and population, resolver directions and repairs), `test_release_media_transition_loop.py` (the transition showcase loop through the production host: there and back with both ends and the rest exact), `test_qtquick_jigsaw.py` (Jigsaw Piece Flip: knobs differ in shape across a layout, the pieces cover the picture exactly with counter-clockwise simple ear-clipped faces at three aspects and piece counts, neighbours hold bit-identical cut points including corners (per-edge corner arithmetic fails), vertices lead with the flat front faces and stay on the picture, a corner order starts at its corner and turns pieces away from it, random-start and unordered orders are seeded permutations, every piece lands and every cut line is gone by the end and the flip pose ends turned with its outline mirrored, exact and continuous ends on every tier, the order's corner turns to the new picture first, a warm-up from COMPUTE-prepared pieces leaves the first frames nothing to compile or allocate and park drops the pieces, resolver orders and repairs), `test_qtquick_relief_rise.py` (Relief Rise: the phase ends exactly everywhere, its GLSL equals the CPU mirror on the GPU (a drifted front fails), ahead of the wave and behind it the photographs are exact for three directions and every tier, the lifted relief differs, the wave travels the way its label says, gloss touches only the lifted relief, texture unit 3 is handed back (its removal fails), warm-up builds the grid, park/release, resolver), `test_qtquick_accordion_fold.py` (Accordion Fold: pleats keep their width through folding, flipping and unfolding and never pass through the picture, the phases meet, the fold's GLSL equals its CPU mirror on the GPU, every crease lands on a grid vertex row for every tier, aspect, pleat count and axis, exact ends, the front folds away as the old picture and the back unfolds as the new one toward every edge on every tier (old pictures on the back fail), a still backdrop beyond the stack, near-end continuity (a wrong mirror axis fails), gloss only on the folded sheet, warm-up builds both axes' grids, park/release, resolver), `test_qtquick_disintegrate.py` (Disintegrate: the schedule keeps both ends exact and the grid bounded, frames before the first release and after the last death are the photographs exactly through the population path, a frame renders identically twice, the GPU's live grains equal the CPU mirror's in id order, the wind blows the way its label says on both axes, a warm-up that leaves the first frames nothing to compile or allocate including the population, park/release, resolver repairs), `test_scene3d_population.py` (S16/S18 compacted population: exact live ids/slots/states/indirect count against a CPU reference up to 300,000 members with a broken-scan negative control, order kept through membership changes, the indirect draw draws exactly the live members, barriers, capacity, restored bindings, dormancy, release/rebuild), `test_qtquick_page_curl.py` (Page Curl: the roll bends without stretching and leaves the page level, its radius grows by its pitch per turn, the line starts at the page, keeps an even pace through the middle and ends with the roll gone and no shade, the roll's GLSL equals its CPU mirror on the GPU (a drifted roll angle fails), exact ends on every tier, the flat page and the uncovered new picture exact (shade as the mirror predicts) away from the roll for corner and edge origins, near-end continuity, every origin peels from its own side, gloss only on the peeled sheet, a warm-up that leaves the first frames nothing to compile or allocate including the tier's grid, park/release, resolver origins and repairs), `test_qtquick_blinds_slats.py` (Blinds 3D Slats: exact ends, slats at rest are the photographs exactly and the wave runs first to last on both axes and every tier, judged through the schedule's CPU mirror (a drifted GLSL schedule fails), turning slats differ from both photographs, gloss changes only turning slats, near-end continuity, a dormant Flat style, a warm-up that leaves the first frames nothing to compile or allocate, park/release, resolver axis choice and repairs), `test_scene3d_compute.py` (S15 compute seam and motion-blur tile max: exact column-then-row reference with ties and partial tiles, dispatch-owned texture-fetch barrier before the gather, image units handed back, no compute without Motion Blur for every covered transition consumer, fixed loud tile capacity, release/rebuild and failed compile/link cleanup), `test_scene3d_stream.py` (S14 stream ring and std430 layouts: driver offsets/strides and values, restored indexed ranges with untouched generic bindings, fence-waited slot reuse across unsynchronised frames, fixed loud capacity, GL-free dormancy, release/retry/rebuild and failed-mapping cleanup), `test_scene3d_target.py` (the shared scene target for any item rect: equals a direct draw, honours an inherited scissor, reuses its allocation, hands state back after a failure, resolves in shaders and never through a blit, with or without bloom; motion blur leaves a still scene exact and smears a moving surface along its motion only, both axes, 1 and 4 samples; an overlay leaves undrawn pixels exact, matches a direct draw where drawn, mixes by its opacity, blends smoothed edges without a dark fringe (a premultiplied composite fails) and refuses bloom and motion blur), `test_scene3d_glsl_mirrors.py` (every shared 3D library GLSL function against its CPU mirror on the GPU, with a drifted-mirror negative control; the motion shader transforms keep the shader, add its motion and refuse shaders they cannot handle), `test_scene3d_foundation.py` (bloom glows emitted light only and follows each transition's setting over the tier, and a single-sample bloom target draws like a direct draw; motion blur blurs only moving tiles, follows each transition's setting over the tier and is dropped at park; every other 3D transition blurs its motion and is exact when a shutter moves nothing; each 3D transition's anti-aliasing choice decides its scene target; the shared 3D library's departure solver, projection, shadows, 3D Detail tiers, exact endpoints and framebuffer restoration per tier, High multisampling and `park()` dropping only the scene target), `test_qtquick_crumble_volume.py` (closed fracture solids, parent-bound chip debris and release weighting), `test_qtquick_melt_surface.py` (bounded implicit liquid surface), `test_qtquick_organic_surfaces.py` (bounded raised Ink topology), `test_qtquick_transition_material_settings.py` (canonical material ranges), and `test_qtquick_future_transition_gl.py` (actual endpoint/near-endpoint pixels, seed/option/direction sensitivity and retirement). `test_qtquick_organic_transition_renderers.py` no longer owns actual-driver compilation. Registry/request/default/Settings tests remain the integration authority. `test_tendril_retirement.py` permanently guards the rejected Tendril capability against registry/default/runtime/source resurrection and verifies stale persisted state is pruned.

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

**System-audio / OSD gate:** the read-only native callback registration module runs directly on Windows with `python -m pytest tests/test_core_audio_callback_native_probe.py -q --tb=short`; no environment-variable gate is used. Shared system-audio source and Media lease integration are covered by `tests/test_audio_shared_source.py`, `tests/test_audio_event_qt_bridge.py`, `tests/test_audio_event_session.py`, `tests/test_system_mute_runtime.py` and `tests/test_media_generation_recreation.py`. Native registration alone cannot prove external event arrival; require bounded hardware evidence when the callback/device-lifecycle seam changes.

Current injection/admission belongs to `rendering/widget_runtime_services.py`, retained Quick family binders/models and the actual runtime-service implementations. Preserve event-driven media ownership, bounded reconciliation/watchdogs, generation fencing and clean family dormancy/retirement.

Shared scene3d resource regression routes are in `Docs/Reference/Scene3D_Resources.md`: real DSA mesh drawing and
binding isolation, linked-program sampler lifetime, immutable reflection/scene/post allocation, partial-failure
retirement, and real reflection/multisample state restoration on failures. `test_scene3d_environment.py` protects
the reflection copy; `test_scene3d_dsa_targets.py` checks named target construction and allocation failure cleanup.

### 6.8 Caches, prefetch and long-lived workers


Cache tests protect useful bounded caches, ownership and reclamation, not arbitrary low memory numbers. Do not “fix” a cache test by destroying hot-cache value or turning event-driven work into polling.

Historical Bugs R-82/R-83 and related worker/lifetime records own the mechanisms that justified permanent regressions. `test_network_tls_context.py` protects the one verified direct-socket TLS context (R-98). Memory-owner bars (R-99):
- `test_image_pipeline.py`: consumed derivatives leave the cache.
- `test_qtquick_native_texture_handoff.py::test_parked_transition_node_pins_neither_frame`
- `test_native_thread_pools.py`: one OpenBLAS thread in the app and its spawned workers.
- `test_settings_manager.py::test_settings_reads_leave_no_reference_cycles` The test suite should encode their surviving invariants rather than repeat the incident diary here.

`test_image_prefetcher.py` protects bounded source batching, cooldown, cancellation and stale-cache fencing.
`test_image_prefetch_transport.py` crosses the production construction/packed-response seam, including a spawned worker's near-aspect FILL request, detached QImage lifetime and malformed/cancelled shared-memory retirement. Manifest rejection retains expected/actual geometry and complete spaced paths in console diagnostics.
`test_image_worker_prefetch_batch.py` spawns the image worker, proves Qt byte parity for ordinary Smooth and exact
foreground/batch parity for every canonical resample filter with/without sharpening, and rejects repeated source decodes,
mixed-quality inputs and over-budget batches. Transport fixtures reject mismatched filter/sharpen manifests as well
as geometry, and pipeline fixtures isolate every canonical filter/sharpen quality cache identity.
`test_image_quality.py` guards bounded visible-region FILL work, sharpening halo, severe-reduction detail and opaque
source ownership; `test_resample_filter_settings.py` and `test_display_tab.py` preserve old Lanczos selections and
round-trip the new enum without retaining a second setting. The mechanism and measured scope are in
`Docs/Reference/Image_Quality.md`.
`test_async_image_processor_current.py` checks exact FILL coverage at near-matching source/target aspect ratios, with no black edge padding for RGB or RGBA, and pixel-exact odd-width Qt/Pillow row-stride conversion.
`test_frame_trace.py` protects explicit parent-handoff attribution and interval-overlap counting; these automated bars do not close two-display performance acceptance.

### 6.9 Build/package evidence

`tests/test_build_layout.py` protects canonical publication, QRC regeneration/inclusion and the current-build evidence
contract. Standard, Diagnostic and Media Center workers must request a Nuitka XML report and write one compact
footprint JSON after publication. The JSON records artifact/published bytes, file count, top-level buckets, largest
files and QRC source-vs-generated-binary-pack sizes; the `.rcc` bytes are the deployed Qt resource representation and
generated Python resource modules are explicitly excluded from product workers. The report files live directly under `logs/`, so ordinary LOGZIP capture includes
them without a second collector or scheduler. Package exclusions require evidence from the **current** build report for the actual import/plugin owner or dead
payload, not source-directory-name suspicion. `test_build_layout.py` also pins the authored QML import allowlist
and the shared dead-family exclusion surface so a new QML namespace cannot silently ship against a stale prune.
`test_installer_contract.py` protects the two self-contained Inno 6.7.2+ dark installer contracts, Build Foundry
Inno 7/6 discovery, pre-compile stale-output retirement, transparent-ICO Setup/Uninstall branding, retired-BMP boundary,
QRC-owned-image boundary, ICO-first solid-compression ordering and MC single-payload-copy rule. These are static packaging bars; successful Inno 7.1 compilation and eyes-on
installed wizard/DPI behavior remain physical/operator evidence when that seam changes.

`tests/test_godzip_foundry_core.py` owns the GODZIP transfer-safety contract: manifest/hash/debris semantics, reversible apply,
repository-local Foundry state, hidden internal Git child processes, embedded `.godzip/workflow.md`, and the hard exclusion of
`ui/assets/` from normal handoff payloads even when a caller attempts to force-select it. The embedded workflow is explicitly an
archive-handoff contract; it must not redirect Codex, Claude or another application already working directly in the local repo.
GODZIP CLEAN age classification must
reuse the core hidden Git path; a cleanup scan may inspect many archives and must never spawn a visible console per relation query.
These tests do not authorize deletion: cleanup likelihood remains advisory and only explicit debris/recycle actions mutate files.

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

**Distinguish the retired physical-host replay executable from the current deterministic offline replay.** The old physical host is retired and must not be restored. `tests/test_visualizer_replay.py`, `tools/visualizer_replay/driver.py`, `tools/visualizer_replay/floors.py` and `python -m tools.visualizer_replay` are **active**, test-owned post-DSP replay authorities. The maintained `destination` profile includes the replay test. Its offline logical/Quick-snapshot result is not real GPU pixels, live capture or scheduler evidence. Current temporal/BTF/viewport tests provide complementary coverage; Bubble's specific protection follows `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

The deterministic replay uses committed synthetic feature clips under `tests/fixtures/visualizer_replay/v1/`, **independent frozen settings** under `tests/fixtures/visualizer_frozen_settings/` and the reviewed reference at `tests/goldens/visualizer_replay/reactivity_floor.json`. Test input and reference provenance must be checked together. An old reference description such as *current authored preset zero* does not override the current test's explicit `frozen_visualizer_settings` injection or license resetting an operator-editable curated preset. Normal Godzips may omit the fixture/golden payloads; missing artifacts prevent independent recalibration from that handoff, not the operator's installed-tree test run.

When a current Windows replay test is RED, report the exact measured mode output, floor and case, then inspect the actual fixture, frozen input, reference provenance and current mode-owned consumer before classifying it as a stale floor or behavioral regression. For unshaped modes, zero **Spectrum bars** can be correct while the independent mode output remains active; Dev Curve `output_flux` measures its curve output, not the unused Spectrum bar shaper. Do not silently lower/reseed floors, update historic artistic snapshots or restore phantom Spectrum shaping to make the gate pass. A reviewed recalibration must demonstrate the intended behavior with test-owned inputs and retain meaningful negative controls.

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

## 9. Physical evidence routing

This guide does not maintain a list of historically accepted checkpoints or completed visual reviews. Closed evidence belongs in `Docs/Historical_Bugs/` or the owning Guardrail/Reference document. Current tests should state **when** a physical gate is required, not preserve a diary of when one once passed.

Rerun a physical gate only when the changed seam can affect what that gate observes: pixels, authored reaction/timing, native focus/input, DWM/taskbar behavior, real driver/context behavior, multi-monitor ownership, or installed lifecycle. Do not rerun unrelated families merely to refresh a suite count or checkpoint label.

When a native Qt/GL test needs a genuinely shown/exposed window for scene-graph/context creation, keep it invisible to the operator with `tests._invisible_windows.keep_off_screen()` (or the established equivalent) unless visibility/focus itself is the contract. Offscreen-QPA/software rendering is appropriate only when it preserves the evidence level being claimed.

## 10. Maintenance and completion rule

When changing tests or this guide:

1. count current `test_*.py` modules from source instead of copying an old inventory;
2. validate every maintained-profile target exists;
3. run focused tests first, then the maintained profile when appropriate;
4. classify dependency blockers separately from product REDs;
5. delete obsolete whole-file tests once surviving assertions are rehomed;
6. mark **NEEDS RUN** only for current tests that genuinely require another environment;
7. remove NEEDS RUN only after an actual intended-environment execution;
8. update this file in the same slice whenever test authority, maintained routing, evidence level, durability policy or operator-containment policy changes materially; do not append per-run diary entries;
9. put failure archaeology in Historical Bugs, not numbered checkpoint sections here;
10. keep routine tests non-intrusive without changing selection: pure/model tests create no top-level window; compatible Qt tests use offscreen QPA; a real native/GL window that must be shown/exposed uses `tests._invisible_windows.keep_off_screen` or `WA_DontShowOnScreen`; only an explicitly physical focus/input/DWM contract may intentionally become visible or steal focus, and such a test still runs rather than being skipped merely for operator convenience;
11. never pin what the operator or user can edit (defaults, presets, copy): derive it from its owner or assert
    structure, and mark a genuinely fixed literal `EXACT-VALUE INVARIANT:` (`Docs/Guardrails.md`).

A test-affecting slice is complete only when:

- production behavior and test expectation agree on the current owner/contract;
- directly runnable focused tests are green;
- environment-blocked current coverage is described honestly;
- obsolete tests are deleted/re-homed rather than converted into permanent skips;
- `tools/check_defaults_authority.py` passes when defaults changed;
- maintained-profile membership is valid;
- installed/Qt/GL evidence is requested where static/headless proof cannot close the claim.

Git and `Docs/Historical_Bugs/` preserve history. `Docs/TestSuite.md` should remain small enough to answer one question quickly: **what deserves trust now?**

### Feeds family regression routing

`tests/test_feed_core.py` protects feed normalization, image-optional validity, URL/magnet normalization, bounded conditional transport, last-good cache durability/backoff and endpoint-isolated CUSTOM identity. `tests/test_feed_projection.py` protects List/Grid/Compact projection and sparse per-story artwork. `tests/test_feed_runtime.py` protects generation-shared source ownership, same-endpoint deduplication, active-lease cadence recomputation, cache-first scheduling, manual refresh and retirement/callback detachment. `tests/test_feed_news.py` protects the NEWS categories discovered from the canonical feed catalog, stable provider identity, newest-first merge, publisher attribution, failure isolation, one lease per selected publisher and Settings round-trip. `tests/test_feed_custom_slots.py`, `tests/test_feed_artwork_multisource.py` and the live-artwork tests protect simultaneous CUSTOM/NEWS sources, cancellation/pruning, artwork eviction fencing and bounded warming.
Synchronous FEEDS fixtures must still model the production cadence contract: accepted runtime results carry a current success timestamp, failures carry a retry/backoff floor, and any test-only collapse of the inter-source stagger may remove elapsed waiting but must not bypass serialization or create a second scheduler. Do not add sleeps to make serialized NEWS tests pass.

`tests/test_feed_f2_contract.py` is the family admission contract for **every registered FEEDS card**: every runtime descriptor is identical apart from identity, every card supports the same independent X/Y `content_extent`, the Settings section is descriptor-owned/lazy, QML owns no network/timer/remote image source, and foreground actions are HTTP/S pages or validated magnets only. `tests/test_qtquick_feed_component_load.py` is the mandatory native `QQmlComponent` compile/retained-visual gate and exercises sparse local Grid art, X/Y extent, stable child roles, real-artwork Edit proxy, authored-surface containment and widget-wide semantic flip. `tests/test_feed_custom_reflow_contract.py`, `tests/test_feed_header_parity_contract.py` and `tests/test_click_affordance_parity.py` protect freeform artwork reflow, shared header/monogram semantics and hover language. Source-string checks do not replace the native component gate.

No deterministic FEEDS test should require live publisher access. `tools/feed_probe.py --catalog` is the separate native endpoint probe. Remaining operator-only lifecycle/visual checks are the live checklist in `Docs/Reference/Feeds.md`; there is no per-card promotion gate for already-admitted FEEDS identities; family membership is owned by the canonical FEEDS registry/configuration, not by a copied card count.

### Steam inline imagery and disk-budget gate

`tests/test_steam_followed_inline_news_artwork.py` covers complete Steam Clan image-macro removal from preview prose, up to three validated local article thumbnails, offline restart, invalid reference rejection, failed lookup negative caching, independent game/inline cache pruning, and recovery of pre-thumbnail ranked/per-game cached article rows whose preview contained image paths without image-reference fields. Assert cache-first visual metadata and full text sanitation before the affected game's next rolling-news batch, with a second offline source lifetime; fresh-news fixtures alone do not protect existing user caches. `tests/test_steam_profile_assets_events.py` additionally guards the shared Steam asset writer/pruner. Source and cache fixtures retain game news and hub click eligibility when old records have no source URL or contain a rejected article target; Qt staging verifies no extra public row publication is required for a private link revision, portable QUrl file-path identity, a responsive thumbnail rail and preview text based on the actual displayed thumbnail count. `tests/test_qtquick_games_you_follow_staging.py::test_followed_inline_article_thumbnails_keep_local_sources_and_retained_slots` is the *native* QML role/border/geometry/source-release gate; a green Python source fixture cannot certify appearance. Disk caps are per-profile/per-cache-family, not proof of an aggregate installation-wide budget.

**Retained refresh and inner-shadow gate:** The native `tests/test_qtquick_games_you_follow_staging.py` exercise must distinguish locally cached third-image availability from the image source of a third *painted* frame, including a narrower two-image tile and a broad tall single-column three-image tile on the same retained model. It also checks that artwork and thumbnail contacts exist while the tile's cached frame shadow stays separate. `tests/test_qtquick_reddit_presentation.py` (both Reddit identities), `tests/test_qtquick_gmail_presentation.py` and `tests/test_qtquick_feed_component_load.py` cover real retained refresh controls and QML readiness; hover treatment and cursor require native interaction/physical evidence when that seam changes, not source-string assertions; automated source tests alone never certify the painted interaction. `tests/test_qtquick_friend_pulse_presentation.py` covers row/grid frame and avatar contact targets with unchanged authored dimensions. Preserve stable child-role identity, no new image shaders, retained shadow-direction projection and safe normal/Edit hitbox gating. The source-only Steam news tests do not establish Qt painted-state or shadow acceptance.

### Games You Follow | current regression routing

`tests/test_steam_games_followed_source.py`, `tests/test_steam_games_followed_projection.py`, `tests/test_steam_games_followed_g0.py`, `tests/test_steam_games_followed_news_g0.py`, `tests/test_steam_followed_shared_runtime.py` and `tests/test_games_followed_live_admission_contract.py` cover followed-set provenance, bounded newest-first source selection, durable private cache and incremental maintenance, generation/shared-owner retirement, projection and admitted runtime behavior. `tests/test_steam_games_followed_g2_staging_contract.py` protects the staging/presentation contracts although the family is now live; the filename is not a claim that the product remains unadmitted. `tests/test_steam_followed_metadata_and_artwork.py` covers durable AppID name hydration/restart/negative retry, correct attribution without title text, mixed/corrupt artwork and stale snapshots without live network. `tests/test_qtquick_games_you_follow_staging.py` exercises actual Qt/QML retained slot identity, paint-capacity equivalence, reflow, game-name projection and mixed-image rail/placeholder admission on Windows. A green automated gate still does not prove real provider language accuracy, Steam's personalized What's New parity, hardware/network cost or every live article route. Automated coverage does not certify a real provider article route. When link-routing/provider ingestion changes, use a newly refreshed syndicated story that actually carries its validated original article URL; legacy cached rows without one correctly fall back to the app news hub.

### Sphere drag momentum / wallpaper ban ownership (R129)

`tests/test_visualizer_view_orbit.py` protects Sphere presentation-clock inertia, finite settle/cancel and pose persistence boundaries, including preset rebase without held keys. `tests/test_image_bans.py` protects zero-ban no-lookup admission, hashed sentinel restart/clear, local-vs-remote canonical identity, queue skipping, preview/peek and all-banned termination, plus context-menu routing. Both require the operator's Windows Qt runtime before reporting a green gate; pure local source/execution probes are not real Quick/GL acceptance. The R128 focused result (140 pass) predates these modifications.
