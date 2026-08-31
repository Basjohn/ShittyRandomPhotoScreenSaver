# Test Suite Guide

Last updated: 2026-09-01

Reviewed authority:

```text
G: independently audited and accepted.
H production Quick authority / old physical-host deletion: structurally accepted.
H1a reconstruction hang: CLOSED; repeated dual-display Settings/CUSTOM physical gate passed.
H1b terminal retirement / retained model lifetime / Settings event-filter teardown: CLOSED; later dual-display exits are clean.
H2 Media artwork provider identity: CLOSED; exact engine-registered provider is injected and artwork is physically visible.
H3 Reddit production opener: CLOSED; operator validated product opening behavior physically.
H3b Clock runtime mode-toggle persistence + CUSTOM geometry recreation: CLOSED; operator validated physically.
H4 Media Play/Pause/seek provider-result semantics: CLOSED; operator validated physically.
H5a/H5b/H5c/H6/H8/H9/H7: exact remaining validation belongs to Current_Plan.md; do not copy volatile sub-status here.
R6 native-QCursor Halo: pointer-motion performance physically accepted; visible custom Halo parity remains J.
H9 uniform ordinary resize: deterministic 8/8 falsifiers + broad affected surface GREEN; operator reports major physical improvement; final Save/recreation containment still required.
R7 image/surface integrity: transactional image-change, generation/token prefetch resume and exterior-edge R-63 refinement implemented; source-only R4-R7 contract files GREEN (`test_visualizer_viewport_scaling_contracts.py` + `test_runtime_perf_policy_contracts.py`); physical/log validation pending.
Media event migration: event-driven GSMTC observation implemented at `2e7a9242`; short installed smoke established observation on each recreation with real events, stale=0/missed=0/degraded=False and clean exit; broader provider-switch/frozen validation remains open.
Qt/QML observability: permanent always-on direct `screensaver_qml.log`; physical Quick gates inspect it alongside the Python log.
I residue reconciliation: BLOCKED until H re-closes.
```

This document is the SRPSS testing strategy and **live test-file inventory/retirement ledger**. It is not a phase changelog.
`Current_Plan.md` owns the current implementation sequence and exact checkpoint. Exact source outranks this inventory when
later work has landed. **At this checkpoint the inventory combines current `main` with the explicitly named R6/R7 local checkpoint additions that are being folded into the next cohesive worktree; do not assume a file is absent merely because an intermediate ZIP was sparse.**

The whole top-level test tree is **not currently one homogeneous current-owner gate**. H has deleted the legacy physical
`DisplayWidget`/GLCompositor presenter, while the tree still contains tests/tools whose implementation owners are already
gone or are awaiting I re-home/deletion. A whole-tree run therefore mixes destination Quick contracts with admitted residue.
Whole-tree results remain valuable for debt reconciliation, but an unrelated legacy red does not reopen a proven destination
contract by itself.

This reconciliation also accounts for the Settings GUI overhaul that did not travel through the usual migration-agent doc
loop: stale direct imports of the retired `NoSourcesPopup`, retired `ui.widgets.color_swatch`, and the old
`build_sine_wave_tab` builder entry point are replaced with tests against the current centralized Settings owners.

## 1. Audit method and status vocabulary

This ledger was built from the complete Git tree at the reviewed checkpoint, then classified against the current migration contracts. Architecture-sensitive groups were checked with direct source reads and repository-wide searches for legacy owners such as `QRhiWidget`, `GLCompositorWidget`, software-render fallback and `QGraphicsEffect`.

This is deliberately **not** a claim that every assertion in every top-level test module was manually
read line-by-line or executed during this review. The row-level inventory is the useful current authority; semantic inspection was
concentrated where migration status could change whether a test remains authority.

### Status vocabulary

| Status | Meaning |
| --- | --- |
| `KEEP` | Current useful coverage; no migration-specific retirement identified. |
| `KEEP — PERMANENT` / `KEEP — MIGRATION PERMANENT` | Protects a presentation-neutral or destination-architecture contract and should survive cutover. |
| `I RECONCILIATION — <origin>` | The durable contract may survive, but the named old migration/physical harness is already superseded. Rehome/update/delete the stale assertion during I against the current Quick/neutral owner; never restore the retired owner. |
| `STALE I RESIDUE — <origin>` | The implementation owner named by the old phase has already been removed/superseded. The test is no longer production authority; delete or rehome only the surviving behavior contract during I. |
| `UPDATE REQUIRED NOW` | The test itself is already stale/brittle/known-red against current authority. Classify source-vs-test first, then fix deliberately. |
| `OBSOLETE NOW` | No longer meaningful current regression coverage. Delete rather than skip or preserve as fake authority. |

**Completed migration phases must not remain written as future test work.** F/G/H-origin rows now use `I RECONCILIATION` / `STALE I RESIDUE`: the old owner is already ported or deleted, and the only remaining question is whether a surviving behavior contract needs a current-owner test.

**Do not use filename age or phase prefixes as the decision rule.** `test_p2_logical_runtime.py`, for example, is permanent logical-runtime coverage, while some newer-looking files encode presenter paths intentionally scheduled for deletion.

### Inventory count policy

Do not maintain hand-written aggregate module/status totals in this live document. During migration they become stale as
soon as a test is added, removed or reclassified and can contradict the row-level inventory in the same file. The tables
under section 10 are the authority for current test ownership. Generate counts from the current tree only when a specific
audit actually needs them.

## 2. Standard commands and evidence levels

Targeted tests are the normal per-slice gate:

```powershell
pytest path\to\test_file.py -q --tb=short
```

The closed H destination topology remains protected by the maintained profile:

```powershell
python tests/run_chunked.py --profile h-destination --chunks 4 --timeout-seconds 900 --log
```

`run_chunked.py` performs one collection preflight before starting the maintained profile. A stale import therefore fails
once and stops. **Maintained profiles are then isolated by target:** every selected file or nodeid runs in its own fresh pytest process,
while `--chunks` only partitions those subprocesses into a small number of reporting/log groups. This is deliberate for
QQuick/Qt lifecycle tests: a queued callback or scene-graph teardown defect in one target must not contaminate unrelated tests
in another target. Whole-tree/explicit-target mode still uses pytest-chunk test-level partitioning because it is a reconciliation
diagnostic during H/I rather than the current destination authority.

A complete-tree run remains available as a **broad reconciliation diagnostic** during H/I:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

Until the I residue pass reconciles tests/tools for the now-deleted physical host, do not interpret that whole-tree command as
a single production-authority gate. Do **not** preserve old aggregate collection/failure counts in this living guide; regenerate them from the exact current tree when doing a broad reconciliation. Legacy-owner collection failures are admitted I inventory, not a reason to restore H production modules. After I retires/re-homes them, the complete tree should regain normal broad-gate authority.

Do not use a red broad-suite run as the only evidence that the active slice failed. Inspect the exact failure/timeout and run
the smallest focused gate that can falsify the changed contract.

SRPSS does not use repository-hosted CI as the normal migration workflow. Do not add GitHub Actions or another hosted
workflow unless the operator explicitly asks for it.

Validation levels:

- **A — pure/unit:** settings, catalogs, registries, geometry, numerical helpers, generation helpers.
- **B — component/integration:** logical mailbox/state bridge, widget family/activation, models, settings capability activation, presentation-state mapping, lifecycle ownership.
- **C — runtime-shaped:** real logical worker, Quick window creation, threaded scene graph, transition/visualizer state flow, Settings/recreate, activation consequences, stale-generation fencing.
- **D — real Windows/driver:** standalone `QQuickWindow`, threaded scene graph, real GL, multi-display/refresh/DPR, GPU/resource ownership, compiled/frozen build.
- **E — manual visual:** Bubble feel/BTF, transition visual parity, Spectrum idle visibility, Pause/Play hitch, startup/reveal, widget visual parity/shadows.

Use `Docs/Harness_Index.md` for recurring real-GL/physical/runtime harness commands.


### 2A. H -> I source-mode runtime reality smoke

A maintained pytest profile proves deterministic ownership contracts but does not replace Windows/driver/QML evidence.

Closed physical gates now include:

```text
H1a: 3 Settings + 5 CUSTOM dual-display recreations, no watchdog dump
H1b: terminal destruction barrier completes before final process/Qt shutdown; clean natural exit
H2: real Media artwork resolves through the engine-registered provider
H3: Reddit production opener physically validated
H3b: Clock mode-toggle/CUSTOM recreation physically validated
H4: Media Play/Pause/seek provider-result semantics physically validated
```

The Qt Quick runtime has a second diagnostic plane. Every physical H/J Quick claim must inspect:

```text
screensaver.log
screensaver_qml.log
```

A successful Qt/QML capture eagerly creates `screensaver_qml.log` even when Qt emits zero messages. The file therefore doubles as capture-health evidence. See `Docs/Qt_QML_Observability.md`.

Permanent/focused regression coverage should preserve:

```text
tests/test_qtquick_family_binder_two_phase.py
tests/test_settings_eventfilter_teardown_guards.py
tests/test_terminal_runtime_destruction.py
tests/test_qtquick_retained_model_lifetime.py
tests/test_qt_message_capture_contract.py
tests/test_qt_message_capture_qml_runtime.py
```

Reddit URL opening, Clock runtime mode persistence/CUSTOM recreation and Media Play/Pause/seek are physically closed. Current H work is the narrower set named by `Current_Plan.md`: remaining Visualizer routing/reactivity/settings/resize gates, R7 transition/prefetch/seam validation, GC/perf classification and exit classification. Do not reopen closed H3/H3b/H4 from stale test prose.

Spectrum has two H-level evidence streams: repeated live bar payload saturation before shader presentation **and** the wrong basic Organ/Spectrum topology. A test that proves only shader load/draw count is insufficient.

The short operator smoke remains mandatory for black/test-frame flashes, Bubble visible response, clipping, cursor duplication, layout composition and other J Parity+ facts.

## 3. Failure triage and stale-test rule

A test failing on the previous checkpoint is **not automatically out of scope** and is **not automatically stale**.

For every directly relevant red test:

1. identify the contract it is supposed to protect;
2. compare that contract with current `Current_Plan.md`, focused migration docs, current source, and the actual production path;
3. if the source violates the surviving contract, fix source;
4. if the harness/API expectation is obsolete but the contract survives, update/rehome the test without weakening the assertion;
5. if the entire implementation owner is intentionally retired, mark/delete it according to this ledger only when the replacement owner is in place;
6. never convert a real failure into a skip merely because the environment or migration changed.

The E2.7 `test_widget_manager_refresh.py` stale-test incident is the model: six tests had old capability/grace/coordinator API assumptions. They were updated to exercise the same intended behavior through the current API rather than deferred as “pre-existing red.”

### 3A. Current maintained-profile drift that must be reconciled

The last completed maintained-profile run **before the newest R6/R7 source-contract and full Media-runtime wiring** was 79/85. Treat that as historical evidence only; do not quote it as the count/result of the reconciled profile. The six red **files are not obsolete wholesale**; specific assertions inside them are obsolete against current owners. Do not make product code imitate these retired seams:

| File | Current stale assertion | Correct disposition |
| --- | --- | --- |
| `tests/test_qtquick_auxiliary.py` | names `update_halo_pointer`, `halo_visible`, `pointer_position_changed` / retained-QML pointer motion | **UPDATE REQUIRED NOW.** Keep dimming/pixel-shift/semantic auxiliary coverage; replace Halo assertions with R6 native-`QCursor`, event-cached interaction/Ctrl and no scene-position binding. |
| `tests/test_qtquick_visualizer_bubble.py` | checkpoint-specific Bubble telemetry literals that drifted after accepted reactivity/wake repairs | **UPDATE REQUIRED NOW.** Keep behavior/ownership/BTF assertions; compare expected telemetry to current diagnostic schema rather than restoring removed fields. |
| `tests/test_qtquick_visualizer_devcurve.py` | checkpoint-specific visualizer telemetry/presentation literals | **UPDATE REQUIRED NOW.** Preserve visible/renderer contract; update removed diagnostic-token expectations only. |
| `tests/test_qtquick_visualizer_item.py` | checkpoint-specific visualizer telemetry/presentation literals | **UPDATE REQUIRED NOW.** Preserve retained-item consumption/fencing; update removed diagnostic-token expectations only. |
| `tests/test_bubble_viewport_reflow.py` | references retired `_render_radius_in_world` helper | **UPDATE REQUIRED NOW.** File remains permanent G4/BTF coverage; assert the current authored-pixel/radial/ring-spacing projection contract through public/current helpers. |
| `tests/test_s_hotkey_workflow.py` | monkeypatched `_show_next_image()` fake does not accept current `origin=` keyword | **UPDATE REQUIRED NOW.** Production `origin=` is current instrumentation/admission truth; update the fake signature, do not remove the production keyword. |

New/current tests that must be represented in the maintained test story:

| File | Status |
| --- | --- |
| `tests/test_qtquick_h9_uniform_resize.py` | **KEEP — H9 PERMANENT.** Uniform retained-presentation scale, geometry-only Reddit/Media CUSTOM payload and Visualizer non-interference. Already in `h-destination` on current `main`. |
| `tests/test_visualizer_viewport_scaling_contracts.py` | **KEEP — R4/R5/BTF PERMANENT.** Source/presentation-neutral viewport projection contracts for Bubble wake/spatial scaling and related nonbaseline invariants. Present in the R7 worktree but not yet wired into current-main `h-destination`. |
| `tests/test_runtime_perf_policy_contracts.py` | **KEEP — R6/R7 CHECKPOINT CONTRACTS.** Native cursor hot-path, runtime GC policy guard, transactional image change, generation/token prefetch wake and exterior-edge R-63 geometry. Present in the R7 worktree but not yet wired into current-main `h-destination`. |
| `tests/test_media_event_observation.py` | **KEEP — MEDIA EVENT PERMANENT.** GSMTC token/session replacement/threading observation contract. Added to `h-destination` by `2e7a9242`. |
| `tests/test_media_runtime.py` | **KEEP — MEDIA EVENT PERMANENT / OWNER INTEGRATION.** Shared owner coalescing, command/event convergence, degraded/watchdog/missed-event behavior and stale-generation fencing were rewritten for the event-driven architecture. **Important runner gap:** current-main `h-destination` does not list this file yet. |

`tests/test_qtquick_black_flash_contract.py` and `tests/test_qt_message_capture.py` are **not current files on `main`**; older docs that named them as executable gates were stale. Black-flash source contracts now live in `test_runtime_perf_policy_contracts.py`; Qt/QML capture is owned by `test_qt_message_capture_contract.py` + `test_qt_message_capture_qml_runtime.py`.

**Maintained-profile reconciliation before the next aggregate claim:** keep the six stale-bearing files in the profile while their assertions are repaired; add `test_visualizer_viewport_scaling_contracts.py`, `test_runtime_perf_policy_contracts.py`, and `test_media_runtime.py`. `test_media_event_observation.py` and `test_qtquick_h9_uniform_resize.py` are already listed by current-main `run_chunked.py`. Do not remove a red file merely to obtain a green count, and do not assign a new pass/target total until that exact profile has run.

**Runner state at repo checkpoint `2e43a0cb`:** `tests/run_chunked.py` still lacks exactly those three additions. This document is therefore accurate about the desired maintained inventory even though the runner is not yet reconciled. Update the runner from the exact cohesive worktree, then run collection preflight before changing any pass-count prose here.

## 4. Permanent architecture gates

### 4.1 Transitions

Preserve:

- canonical registry ↔ Quick implementation parity;
- dormant/lazy implementation resolution;
- capability activation admission;
- Random effective pool = activated ∩ saved pool membership ∩ runnable/hardware;
- Settings/default/random parameter resolution before render admission;
- immutable transition request/run state;
- exact endpoints and authored direction/mode variants;
- effect-discriminative midpoint oracles;
- parameter sensitivity and request→uniform wiring;
- exactly-once completion; competing image-change requests are rejected/deferred before queue/image truth moves; no active transition may be cancelled/snapped merely to admit a replacement;
- generation fencing;
- GL-state restoration including exception path;
- resource teardown.

A zero-activated-transition stored state is handled by the canonical deterministic repair policy. A deactivated Crossfade is never silently executed as a fallback.

### 4.2 Visualizer

Preserve:

- exactly one `VisualizerLogicalRuntime`;
- authored scheduler cadence (Bubble canary ~90 Hz / >=88 Hz service bar);
- every authored logical step integrated before presentation coalescing;
- latest-only mailbox semantics, no FIFO/catch-up;
- worker cannot mutate GUI/Quick/GPU state;
- valid generation `0`;
- all five modes;
- source freshness separate from presentation;
- protected Bubble renderer-visible consequences and BTF;
- continuous visual-only hero-radius rate selection plus stable bounded same-bubble B6-B8 evidence;
- consume-once Bubble transient motion carried by the existing envelope, with same-body event/no-event displacement and
  exact pulse/radius-isolation oracles;
- Pause/Play identity;
- clean worker join;
- one authored fade authority;
- default 1.5 aspect with 420×280 internal reference only;
- baseline/wide/tall geometry without anisotropic finished-pixel stretching;
- render-node-local clip/state restoration.

Do not regenerate visualizer behavioral goldens merely because presentation architecture changes.

### 4.3 Quick presentation

Preserve:

- one standalone top-level `QQuickWindow` per selected physical display;
- threaded render loop and expected GUI/render-thread ownership;
- inline custom GL through `QSGRenderNode`;
- no `QQuickWidget`;
- no second accelerated runtime surface;
- no QRhiWidget/software presenter fallback;
- bounded latest-state synchronization;
- stale generation rejection;
- intentional first frame;
- Settings/recreate and topology recreation;
- clean shutdown/resource retirement.

### 4.4 Phase-E capability foundation

**Current authority:** Visualizers **is** an application-level widget-family capability, and it requires Media. The older TestSuite wording that said Visualizers was excluded from widget-family activation is retired.

Preserve:

- canonical family catalog/membership and environment gating;
- missing activation keys resolve compatibly;
- activation distinct from ordinary `enabled`;
- Media OFF forces Visualizers OFF; Media reactivation does not silently reactivate Visualizers;
- deactivated family filtered before runtime/model/provider creation where that owner has migrated;
- Widgets/Transitions `SETUP` lazy navigation and live pill behavior;
- hidden/unhydrated pages never overwrite persisted detail settings;
- transition activation/pool/manual/Random authorities;
- E2.7 global-singleton Visualizer CUSTOM failover/reclaim lifecycle:
  - unavailable configured target → **full 30 s one-shot grace**;
  - return during grace → no fallback;
  - still unavailable at deadline → at most one temporary fallback;
  - return later → retire/fence fallback before configured owner;
  - new outage after reclaim → fresh full 30 s grace/global generation;
  - capability OFF retires pending failover state and only discards live-fallback state after confirmed retirement.

E2/E2.7, E1, E3 and E4 are closed and Phase E is structurally **CLOSED**. F0 deprecated Imgur deletion is source-audited GREEN from `19460a7`, with its stale scraping dependency pins removed by the closure reconciliation. Phase F is also **CLOSED** through F8 caller-proof retirement; Phase G owns the next active test migration. Do not write “after E/F lands” tests as future work.

## 5. Active migration gates

### Closed foundations

E, F and complete G are closed at their accepted boundaries. The H production authority flip/deletion is structurally accepted; the deleted old physical presenter is not a legitimate test target merely because I residue still references it.

### H — OPEN: post-cutover runtime reality

`Current_Plan.md` owns exact sequence. Current state:

```text
H1a/H1b/H2/H3/H3b/H4: CLOSED; preserve their permanent regressions.
H5a/H5b/H5c/H6/H8/H9/H7: OPEN only as named by Current_Plan.md; do not duplicate volatile sub-status here.
R6 native cursor: performance physically GREEN; visible Halo parity is J.
R7 image-change/prefetch/seam: deterministic/source contracts implemented; physical/log validation pending.
Media event observation: implemented; short installed recreation smoke clean; broader frozen/provider-switch validation pending.
Maintained profile: last completed pre-R6/R7 wiring run was 79/85 because six stale assertions listed in §3A need test-source reconciliation. The reconciled profile also needs the three currently omitted permanent targets named in §3A; do not assign a new aggregate count until run.
```

Use `h-destination` as the maintained deterministic bar and extend it only for surviving destination contracts. H re-closes only after every H ledger row is reconciled, both Python + Qt/QML logs are clean/understood, and the final dual-display source smoke remains physically GREEN.

### I — BLOCKED

Residue-only source/test/tool reconciliation after H. Do not use I to absorb current runtime failures or restore deleted presenter owners to satisfy stale tests.

### Black-flash / image-surface source contract — current

The old documentation referenced `tests/test_qtquick_black_flash_contract.py`, but that file is not current test-tree authority and its deferred-show/background-refresh experiment was physically rejected and removed. Do not recreate it to satisfy old prose. Current deterministic/source checks live in `tests/test_runtime_perf_policy_contracts.py` and protect the accepted R-63 principle plus the R7 exterior-edge refinement. Physical acceptance still requires **both** recurring black/stale flash = 0 and shared-edge seam pixel = 0.

### J — pending H re-close

Comprehensive **Parity+** physical visual/fidelity/installed acceptance. Use the J decomposition, J addendum, `J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md`, mandatory operator ledger and `Docs/Qt_QML_Observability.md`. Historical screenshots/code establish user-visible floor/behavior only; current Quick architecture remains implementation authority.

## 6. Immediate test-maintenance state

Current post-cutover focused additions:

| File | Status | Disposition |
| --- | --- | --- |
| `tests/test_qt_message_capture_contract.py` | **ADDED — PERMANENT OBSERVABILITY** | Eager sidecar creation/session markers, structured Qt context, prior-handler delegation/restoration, sink relocation and metrics. |
| `tests/test_qt_message_capture_qml_runtime.py` | **ADDED — PERMANENT REAL-QML OBSERVABILITY** | Real `QQmlEngine`/`console.warn` probe must reach the direct sidecar and session markers; requires PySide runtime, so awaiting execution in the real environment. |
| `tests/test_qtquick_family_product_actions.py` | **ADDED — H3/H3b + PERMANENT PRODUCT SEMANTICS** | Pins Reddit saver-vs-interactive consequences and per-display Clock mode override persistence. Pure subset GREEN in handoff environment; production PySide composition still needs physical/runtime validation. |
| `tests/test_settings_eventfilter_teardown_guards.py` | **CLOSED H1b / KEEP** | Late Settings helper events cannot dereference retired targets. |
| `tests/test_visualizer_custom_route_contract.py` | **ADDED — PERMANENT H5a ROUTING/BINDING PIN** | Real manager admission over two live unit shells proves CUSTOM Visualizer owns its intentionally different monitor, non-CUSTOM follows Media, one bounded generation trace reports the exact route/outcome, and the sole owner can bind playback from the existing Media model on the other display without creating a Media copy. |
| `tests/test_qtquick_visualizer_middle_click.py` + `tests/test_visualizer_runtime_preset_cycle.py` + affected H/Settings suites | **ADDED — PERMANENT H8 CONTRACT / DETERMINISTIC GREEN** | Pins middle-click preemption, one-step/wraparound, unchanged mode, Custom round-trip, curated replace semantics, atomic narrow persistence with no Media mutation, schema-v5 removal of leaked route/admission fields, live monitor/position preservation, one same-mode activation, overlap/stale-owner rejection, structured restart persistence and all-five-mode coverage. Physical interaction/recreation acceptance remains open. |
| `tests/test_qtquick_h9_uniform_resize.py` | **ADDED — H9 PERMANENT / DETERMINISTIC GREEN** | Pins whole-card uniform scale for Reddit/Media, geometry-only payload replay, stale pre-H9 payload rejection, opt-out family inertness and Visualizer contract isolation. |
| `tests/test_visualizer_viewport_scaling_contracts.py` | **ADDED — R4/R5/BTF SOURCE CONTRACT / DETERMINISTIC GREEN** | Pins viewport/domain projection invariants, including accepted Bubble wake/spatial behavior across nonbaseline aspect/extent. **Not yet listed by current-main `tests/run_chunked.py`.** |
| `tests/test_runtime_perf_policy_contracts.py` | **ADDED — R6/R7 SOURCE CONTRACT / DETERMINISTIC GREEN** | Source-only guard for native cursor ownership/no scene motion, runtime GC policy, generation/token prefetch wake, transactional image-change fail-closed behavior and exterior-edge R-63 geometry. **Not yet listed by current-main `tests/run_chunked.py`.** |
| `tests/test_media_event_observation.py` | **ADDED — MEDIA EVENT PERMANENT / DETERMINISTIC GREEN** | Pins GSMTC manager/session add-remove token lifetime, transactional session replacement and stale callback fencing; real-WinRT round-trip remains environment-gated. Already listed by current-main `h-destination`. |
| `tests/test_media_runtime.py` | **UPDATED — MEDIA EVENT PERMANENT / DETERMINISTIC OWNER CONTRACT** | Event-driven shared-owner/coalescing/command-convergence/reconcile/degraded/missed-event/stale-generation falsifiers. **Current-main runner omission: add the whole file to `h-destination`; controller-token tests alone are insufficient.** |
| Media app-volume child presentation tests (to add with J implementation) | **PENDING J PARITY+ CONTRACT** | Pin separate retained child/item as the existing and unspecified default, integrated only by explicit option, Media-effective/provider-capability dependency, shared Media display route/lifecycle, own CUSTOM rect/size in Media's display bucket, and the existing Media presentation model plus one `MediaVolumeRuntimeService` lease/action seam across both variants. |
| `tests/test_widget_descriptors.py` + `tests/test_widgets_tab.py` | **PERMANENT SETTINGS PIN / H6** | Media CUSTOM lock metadata and real Settings state: only font/artwork lock; progress/glow/volume/mute retain normal dependency truth. |

Qt/QML capture tests are not a substitute for real QML runtime evidence; physical gates must inspect `screensaver_qml.log`.


The Settings-overhaul drift found during the pre-cutover caution run is reconciled in this pass:

| File | Status | Disposition |
| --- | --- | --- |
| `tests/test_settings_no_sources_popup.py` | **RECONCILED** | Tests current central `StyledPopup` construction/result routing and current curated-source actions; no retired `NoSourcesPopup` import. |
| `tests/test_sine_line4_ui_simulation.py` | **RECONCILED** | Tests the central `ColorSwatchButton` + `bind_color_button` contract, including programmatic-load no-save behavior. |
| `tests/test_sine_line4_builder_integration.py` | **RECONCILED** | Uses the real lazy `WidgetsTab` visualizer hydration/save owner and round-trips Line 4 colour/glow/shift. |
| `tests/test_sine_line4_persistence.py` | **RECONCILED** | Removes retired `_sine_line4_horizontal_shift` assumptions; locks current normalized `sine_line4_shift` binder semantics. |
| `tests/test_visualizer_settings_plumbing.py` | **PARTIALLY RECONCILED / I MIXED** | Known unknown-mode assertion now follows the canonical registry fallback. Surviving settings contracts remain; legacy presenter/overlay portions retire or rehome with their owners in I. |
| `tests/test_settings_theme_system.py` | **ADDED — PERMANENT** | Locks the centralized Settings ThemeSpec runtime transaction, catalog/default-mirror rules, persisted fallback semantics and temporary path-resolution precedence. |
| `tests/run_chunked.py` | **RECONCILED, PROFILE LIST NEEDS ONE FINAL UPDATE** | Collection preflight + target-isolated `h-destination` are correct. Before the next aggregate H claim, add `test_visualizer_viewport_scaling_contracts.py`, `test_runtime_perf_policy_contracts.py`, and `test_media_runtime.py`; keep the six stale-bearing files until their assertions are repaired. Whole-tree mode remains reconciliation evidence. |
| `tests/test_qtquick_custom_layout_owner.py` | **ADDED — H DESTINATION** | Proves one manager-generation CUSTOM owner, same-item Cancel, exact committed geometry/size/enabled Save, routed ordinary same-item A-to-B transfer/Cancel/Save without a target duplicate, retained menu/Enter/Escape routes, and visualizer transfer retargeting without duplicate logical/presentation ownership. |

Current I ledger debt belongs to the owner named by each row:

- **OBSOLETE WHOLE FILE:** `tests/test_settings_sync.py` is tombstone-only and can be deleted in residue cleanup;
- **OBSOLETE WHOLE FILE:** `tests/test_phase_e_effect_corruption.py` is historical corruption-investigation scaffolding with no current production owner;
- **OBSOLETE/NONEXISTENT OLD NAMES:** `tests/test_qtquick_black_flash_contract.py` and `tests/test_qt_message_capture.py` must not be recreated; their surviving contracts moved to the current files named above;
- **STALE HARNESS, NOT CURRENT AUTHORITY:** `tests/test_spotify_visualizer_widget.py`, `tests/test_visualizer_replay.py`, and `tests/test_visualizer_preset_cycling_runtime.py` still depend on deleted presenter/replay/input owners. Preserve surviving logical/product contracts only through current Quick/neutral tests during I; never restore deleted modules so these collect;
- `tests/test_visualizer_doc_references.py` still deserves a later brittle-prose-token cleanup;
- the six §3A maintained-profile files are **not obsolete whole files**. Repair only the stale assertions;
- whole-tree legacy physical-host reds are classified in the inventory/retirement register and are not silently skipped.

## 7. Legacy-retirement register

High-value groups that must **not** become destination authority:

- **F0 (done):** the three Imgur test modules were deleted with the Imgur removal.
- **F0.5 (done):** deleted `test_shadow_tuning_paths.py` and `test_base_overlay_shadow_cache.py`; trimmed the tuning-payload assertion from `test_shadow_utils.py`.
- **I residue from E4/F:** QWidget opacity/effect implementations such as `test_widget_effects.py` no longer own production presentation; keep only any still-valid neutral fade/style semantics and delete stale physical-owner assertions in I.
- **I residue from the completed H cutover:** legacy renderer backend/software fallback (`test_rendering_backends.py`, `test_gl_fallback_policy.py`), GLCompositor retained-base/fallback/presenter tests, `test_block_puzzle_flip.py`, QRhiWidget P4 surface tests, old SpotifyBarsGLOverlay presentation tests. These are not current runtime gates.
- **H/I mixed CUSTOM:** retain neutral session/geometry/persistence assertions from `test_custom_layout_manager.py`, but direct `EditShellWidget` guide/button/pixel assertions retire or rehome to the retained Quick CUSTOM overlay because the old shell is already deleted; rehome only surviving guide/interaction semantics to Quick.
- **J:** architecture-selection/spike benchmark suites where no ongoing product regression remains.

Completed F/G/H owners must not still be labeled `WILL BE OBSOLETE`: use `STALE I RESIDUE` or `I RECONCILIATION` and name the surviving contract. Future `WILL BE OBSOLETE` wording is reserved only for an owner that actually still exists in production.

## 8. Fixtures and goldens

`tests/fixtures/` is active support data, including:

- audio cadence/reactivity WAVs;
- Steam JSON snapshots;
- visualizer replay v1 inputs (silence, impulse, ramps, broadband, BPM cases, irregular cadence, mode switch, representative music);
- visualizer temporal fixtures (`bubble_discrete_edge.json`, `spectrum_authoritative_smoothing.json`).

`tests/goldens/visualizer_replay/` and `tests/goldens/visualizer_temporal/` are authored-fidelity evidence. **Do not regenerate them merely to make a presentation migration pass.** Regeneration requires a deliberate authored-behavior change with separate review.

## 9. Test infrastructure

These are support infrastructure rather than inventory test cases:

| Path | Role |
| --- | --- |
| `tests/conftest.py` | Shared pytest/Qt fixtures and suite setup. |
| `tests/_gl_test_utils.py` | Shared GL test helpers. |
| `tests/pytest.ini` | Test configuration. |
| `tests/pytest.py` | Repository-local test support module. |
| `tests/run_chunked.py` | Collection-preflight chunk runner; owns the current `h-destination` profile and whole-tree reconciliation mode. |
| `tests/__init__.py` | Package marker/support. |
| `tests/fixtures/` | Deterministic external/sample inputs. |
| `tests/goldens/` | Visualizer authored replay/temporal expected data. |

## 10. Complete test-file inventory

The inventory below accounts for every executable `test_*.py` file present after this reconciliation. Status describes migration ownership, **not pass/fail state**.


### 10.1 Qt Quick runtime / transitions / visualizer

| File | Status | Note |
| --- | --- | --- |
| `tests/test_qtquick_blinds_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_bootstrap.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_build_packaging.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_burn_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_crumble_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_diffuse_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_frame_pacer.py` | **KEEP — MIGRATION PERMANENT** | Single display-local presentation pacer, including callback-required visualizer GUI synchronization before each retained update opportunity. |
| `tests/test_qtquick_image_boundary.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_image_textures.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_custom_layout_session.py` | **KEEP — MIGRATION PERMANENT / G** | Neutral session/variants/working-state contract; separate visualizer scale + viewport extent is landed and remains permanent. |
| `tests/test_qtquick_custom_layout_overlay.py` | **KEEP — MIGRATION PERMANENT / G** | Retained CUSTOM overlay/drag/edge+corner resize/cross-display contract; extend only for current viewport-lifecycle corrections where applicable. |
| `tests/test_qtquick_h9_uniform_resize.py` | **KEEP — H9 PERMANENT** | Whole-card uniform retained-presentation resize for Reddit/Media, geometry-only payload replay and Visualizer non-interference. |
| `tests/test_qtquick_auxiliary.py` | **UPDATE REQUIRED NOW / KEEP FILE** | Dimming/pixel-shift/semantic auxiliary coverage survives. Retired QML Halo coordinate/visibility assertions are obsolete after R6 native `QCursor`; update those assertions rather than restoring the old seams. |
| `tests/test_qtquick_context_menu.py` | **KEEP — MIGRATION PERMANENT / G7** | Retained context-menu model/QML/action admission contract. |
| `tests/test_qtquick_input_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current input contract, including generation closure and the presentation-neutral runtime-replacement pointer guard consumed by Quick. |
| `tests/test_qtquick_clock_presentation.py` | **KEEP — MIGRATION PERMANENT** | F1 retained Clock model/family/ticker/style/geometry/analogue-shadow destination contract; retain as permanent current coverage. |
| `tests/test_qtquick_weather_presentation.py` | **KEEP — MIGRATION PERMANENT** | F2 retained Weather runtime-consumer/model/state/icon/style/action/host contract; retain as permanent current coverage. |
| `tests/test_qtquick_ordinary_widget_host.py` | **KEEP — MIGRATION PERMANENT** | E3/E4 retained ordinary-widget host + shared shell primitives; root fade, cached card shadow, signed offsets and offset-only text shadow are destination architecture. |
| `tests/test_shadow_direction.py` | **KEEP — MIGRATION PERMANENT** | E4 canonical direction/settings/resolver/QML-boundary contract; retain as permanent current coverage. |
| `tests/test_qtquick_p0_presentation_benchmark.py` | **WILL BE OBSOLETE — J** | Architecture-selection benchmark, not a forever product regression. |
| `tests/test_qtquick_particle_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_phase_c_effect_smoke.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_phase_c_registry_parity.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_presentation_spike.py` | **WILL BE OBSOLETE — J** | Architecture-selection spike, not a forever product regression. |
| `tests/test_qtquick_render_node.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_ripple_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_runtime.py` | **KEEP — MIXED H/J** | Deterministic/source-shaped runtime ownership, generation recreation and coordinated input-exit tests remain in the H destination profile. The two tests explicitly requiring real physical displays (`test_threaded_runtime_uses_exact_identity_for_two_physical_displays` and `test_threaded_runtime_recreates_removed_and_added_physical_topology`) are J physical/topology evidence and are intentionally not part of the per-commit H profile. |
| `tests/test_qtquick_scene_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_implementations.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_parameter_defaults.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_parameter_resolution.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_request_resolution.py` | **KEEP — MIGRATION PERMANENT / H** | One Settings-authored transition spec per accepted image batch, fail-closed Random admission and frozen direction/parameter values. |
| `tests/test_qtquick_transition_state.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_state_fence.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_uniform_wiring.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_all_modes.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_bubble.py` | **UPDATE REQUIRED NOW / KEEP FILE** | Destination Bubble ownership/BTF coverage survives; reconcile stale checkpoint-specific telemetry literals with the current diagnostic schema. |
| `tests/test_qtquick_visualizer_clip_smoke.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_devcurve.py` | **UPDATE REQUIRED NOW / KEEP FILE** | Retained DevCurve contract survives; reconcile stale diagnostic/presentation-token expectations only. |
| `tests/test_qtquick_visualizer_fade_authority.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_geometry.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_item.py` | **UPDATE REQUIRED NOW / KEEP FILE** | Retained-item consumption/fencing survives; reconcile stale diagnostic-token expectations only. |
| `tests/test_qtquick_visualizer_oscilloscope.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_render_bridge.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_sine.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_spectrum.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_window.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_viewport_scaling_contracts.py` | **KEEP — R4/R5/BTF SOURCE CONTRACT** | Permanent source/presentation-neutral viewport-domain projection bars, including accepted Bubble wake/spatial nonbaseline invariants. Wire into maintained profile on exact-runner reconciliation. |
| `tests/test_runtime_perf_policy_contracts.py` | **KEEP — R6/R7 SOURCE CONTRACT** | Native cursor/no-scene-motion, runtime GC policy, R7 image-change/prefetch and R-63 exterior-edge geometry source bars. Wire into maintained profile on exact-runner reconciliation. |

| `tests/test_qtquick_ctrl_coordinator.py` | **KEEP — MIGRATION PERMANENT / H** | One authoritative cross-display Ctrl truth and retired-contribution cleanup. |
| `tests/test_qtquick_display_image_route.py` | **KEEP — MIGRATION PERMANENT / H** | GUI pixmap -> immutable Quick presentation-image routing, detached image-accounting aggregation and target-size contract. |
| `tests/test_qtquick_display_presenter.py` | **KEEP — MIGRATION PERMANENT / H** | Thin per-display destination presenter; no provider/window/persistence authority. |
| `tests/test_qtquick_display_unit.py` | **KEEP — MIGRATION PERMANENT / H** | Per-display Quick destination-chain assembly and semantic display operations. |
| `tests/test_qtquick_family_binder.py` | **KEEP — MIGRATION PERMANENT / H** | Single-manager family admission/runtime service ownership, canonical per-instance monitor routing across logical displays, and retained host binding. |
| `tests/test_qtquick_family_size_policy.py` | **KEEP — MIGRATION PERMANENT / H** | Historical deterministic family preferred-size policies under Option-A geometry. |
| `tests/test_qtquick_geometry_resolver.py` | **KEEP — MIGRATION PERMANENT / H** | Python outer-rect/anchor/clamp authority; no QML outer-position feedback loop. |
| `tests/test_qtquick_h_cutover.py` | **KEEP — MIGRATION PERMANENT / H** | H authority-cutover/cardinality/deletion bars, including one canonical manager-admitted visualizer owner, retained menu/double-click mode actions, H8 middle-click same-mode preset transaction, overlap rejection, delayed narrow persistence, hidden-boundary hard join, fresh-target reveal and engine-retirement lifecycle. |
| `tests/test_qtquick_overlay_preferred_size.py` | **KEEP — MIGRATION PERMANENT / H** | Size-only preferred-content signal contract used by Python geometry ownership, including terminal disconnection before retained-item retirement. |
| `tests/test_qtquick_visualizer_admission.py` | **KEEP — MIGRATION PERMANENT / H** | Exactly one admitted Quick visualizer display owner with requested/hold/fallback policy. |
| `tests/test_qtquick_visualizer_all_five_owner_chain.py` | **KEEP — MIGRATION PERMANENT / H** | Owner-shaped all-five widget-free destination chain. |
| `tests/test_qtquick_visualizer_double_click.py` | **KEEP — MIGRATION PERMANENT / H** | Retained visualizer mode-cycle semantic admission before global next-image fallback. |
| `tests/test_qtquick_visualizer_middle_click.py` | **KEEP — MIGRATION PERMANENT / H8** | Actual Quick-window middle-button preemption plus active/inside retained Visualizer preset-cycle admission with no neutral-input side effect. |
| `tests/test_qtquick_visualizer_logical_ownership.py` | **KEEP — MIGRATION PERMANENT / H** | Controller-owned authored logical state/runtime ownership without QWidget host. |
| `tests/test_qtquick_visualizer_owner_edge.py` | **KEEP — MIGRATION PERMANENT / H** | Thin display/generation visualizer ownership edge, single shared-engine acquire/release, hard retirement, and terminal callback release semantics. |
| `tests/test_qtquick_visualizer_pre_cutover_audit.py` | **KEEP — MIGRATION PERMANENT / H** | Standing source/behavior regression bars from the H pre-cutover audit. |
| `tests/test_qtquick_visualizer_reactivity_config_parity.py` | **KEEP — MIGRATION PERMANENT / H5b-H5c** | Canonical Spectrum topology translation, shared BeatEngine shaping while another mode is active, exact Quick `0.55` transfer, Bubble live controls and technical zero/false semantics; maintained H profile. |
| `tests/test_qtquick_visualizer_true_f_gate.py` | **KEEP — MIGRATION PERMANENT / H** | Strong True-F technical-engine/logical/bar-count + exact retained-item consumption gate. |

### 10.2 Visualizer

| File | Status | Note |
| --- | --- | --- |
| `tests/test_bubble_btf_coalescing.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_bubble_viewport_config_route.py` | **KEEP — MIGRATION PERMANENT / G4** | Live/coalesced viewport configuration route into each authored Bubble step; extend for committed-vs-CUSTOM override lifecycle. |
| `tests/test_bubble_viewport_reflow.py` | **UPDATE REQUIRED NOW / KEEP — G4/BTF PERMANENT** | Core viewport/BTF contract survives; the `_render_radius_in_world` helper reference is obsolete. Re-express that assertion through the current authored-pixel radial/ring-spacing projection contract. |
| `tests/test_bubble_cadence.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_runtime_preset_cycle.py` | **KEEP — MIGRATION PERMANENT / H8** | All-five same-mode wrap, curated replace semantics, lossless Custom round-trip, first-use snapshot seeding and flat-cache migration. |
| `tests/test_bubble_reactivity.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract, including same-body consume-once transient stream/drift displacement with exact pulse/radius isolation; retain as permanent current coverage. |
| `tests/test_bubble_renderer_transport.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_bubble_shader_compile.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_devcurve_builder_contract.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_devcurve_runtime.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_devcurve_settings_binding.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_devcurve_shader_contract.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_devcurve_shape_editor.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_input_gain.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_osc_sine_glow_contract.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_oscilloscope_display_contract.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_remote_visualizer_capability_admission.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_sine_line4_builder_integration.py` | **KEEP — MIGRATION PERMANENT** | Current lazy `WidgetsTab` builder + real save/round-trip coverage for Line 4 colour/glow/shift. |
| `tests/test_sine_line4_persistence.py` | **KEEP — MIGRATION PERMANENT** | Current binder colour/glow + normalized `sine_line4_shift` collect/load contract. |
| `tests/test_sine_line4_ui_simulation.py` | **KEEP — MIGRATION PERMANENT** | Central `ColorSwatchButton` + builder binding contract; programmatic load is non-saving, user signal updates/saves. |
| `tests/test_sine_wave_gl_fix.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_spectrum_presentation_smoothing.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_spectrum_shaping.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_spotify_overlay_repaint_contract.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Scheduling contract survives; SpotifyBarsGLOverlay/display-compositor owner does not. |
| `tests/test_spotify_visualizer_integration.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_spotify_visualizer_mode_transition.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_spotify_visualizer_widget.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_transient_bus.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_transient_per_mode_integration.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_transient_preset_preservation.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_alignment.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_visualizer_analysis_acceptance.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_architecture_split.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_capability_admission.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_card_geometry.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Tests pre-Quick mode growth/relative card geometry that destination explicitly retires; Quick geometry tests are the destination authority. |
| `tests/test_visualizer_compute_lanes.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_doc_references.py` | **UPDATE REQUIRED NOW** | Known stale brittle assertion: do not ban a token globally when legitimate historical/contrast wording may mention it. |
| `tests/test_visualizer_failover_reclaim.py` | **KEEP — MIGRATION PERMANENT** | E2.7 canonical global-singleton/grace/reclaim/capability lifecycle suite. Must remain authoritative until successor owner inherits it. |
| `tests/test_visualizer_feature_frame.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_mode_isolation.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_modes.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_overlay_kwargs.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_visualizer_playback_gating.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_presentation_contract.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_presentation_negative_controls.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_preset_cycling_runtime.py` | **STALE I RESIDUE — DO NOT RESTORE DELETED HOSTS** | Imports retired QWidget `InputHandler`/`WidgetManager`/visualizer host and cannot collect. The input handler covered mouse-button routing, not audio. Current H8 resolver/Custom tests and Quick reactivity/True-F gates own the surviving preset and mode-owned `input_gain` contracts. |
| `tests/test_visualizer_preset_manifest.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_preset_transfer.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_presets.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_reactivity_quality.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_replay.py` | **RETIRE/REHOME — I** | Imports the removed QWidget replay host; the maintained H profile now uses runtime-shaped Settings replacement and controller-owned cadence/bridge tests instead. Preserve only authored-fidelity assertions that still falsify a destination contract. |
| `tests/test_visualizer_retired_modes.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_runtime_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination runtime-controller contract, including presentation-neutral viewport configuration ownership; retain as permanent current coverage. |
| `tests/test_visualizer_settings_plumbing.py` | **I RECONCILIATION — OLD PHYSICAL OWNER (MIXED)** | Registry/settings/shader contracts survive; known mode fallback is current. Retire/rehome old presenter/overlay assertions with their source owner. |
| `tests/test_visualizer_smart_positioning.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_visualizer_startup_contract.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |

### 10.3 Transitions

| File | Status | Note |
| --- | --- | --- |
| `tests/test_block_puzzle_flip.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Legacy `GLCompositorBlockFlipTransition` implementation/API coverage; Quick registry/transition implementation tests own the destination contract. |
| `tests/test_diffuse_transition.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_gl_compositor_transition_lifecycle.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_gl_compositor_transitions.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_micro_wobble_math.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_slide_jitter.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_slide_transition.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_transition_activation_admission.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_transition_catalog_imports.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_transition_distribution.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_transition_endframe.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_transition_perf_health_parser.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_transition_registry.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_transition_state_manager.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_transitions.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_transitions_tab.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_transitions_tab_setup.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |

### 10.4 Widget/display presentation & CUSTOM

| File | Status | Note |
| --- | --- | --- |
| `tests/test_custom_layout_contract.py` | **KEEP — retained CUSTOM contract** | Retain neutral CUSTOM geometry/persistence proof; the durable contract now owns the exact persisted screen-signature algorithm without the retired multi-monitor coordinator. |
| `tests/test_custom_layout_manager.py` | **I RECONCILIATION — OLD PHYSICAL OWNER (MIXED)** | Neutral CUSTOM session/geometry/persistence survives; direct `EditShellWidget` guide/button/pixel assertions retire/rehome with the legacy shell. |
| `tests/test_dimming_and_interaction_fixes.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_display_context_menu.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_display_integration.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_display_setup.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_display_tab.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_display_widget_target_size.py` | **I RECONCILIATION — G OWNER ALREADY PORTED** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_fade_coordinator.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_flicker_fix_integration.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_ghost_isolation.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_gl_compositor_overlays.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_gl_state_manager_overlay.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_layout_slots.py` | **KEEP — MIGRATION PERMANENT / G** | Ordinary visible-layout snapshot semantics; protect ON/OFF vs capability activation and separate visualizer scale/viewport extent replay. |
| `tests/test_multi_monitor_focus.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_multidisplay_sync.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_no_legacy_widget_position_strings.py` | **I RECONCILIATION — G OWNER ALREADY PORTED** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_overlay_diagnostics.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_overlay_frame_shell.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_overlay_render_dispatch.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_overlay_startup_policy.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_overlay_uniforms.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_pixel_shift.py` | **I RECONCILIATION — OLD PHYSICAL OWNER (MIXED)** | Legacy QWidget manager/statistical movement coverage is not the retained Quick auxiliary authority; preserve only surviving burn-in semantics because the old owner is already retired; rehome only surviving semantics in I. |
| `tests/test_service_widget_runtime.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_f0_5_shadow_controls.py` | **KEEP — MIGRATION PERMANENT** | F0.5 canonical shadow cleanup + Widgets → General controls: sidecar retirement, model/default parity, retired-`offset` drop, 3×3 direction picker, and the save-preservation merge. |
| `tests/test_shadow_utils.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Mixed legacy file. F0.5 removed the tuning-payload assertion; remaining `ShadowFadeProfile`/QGraphicsOpacityEffect assertions survive only until their legacy presentation owners are removed. Do not preserve sidecar semantics or port staged effect-carrier fades. |
| `tests/test_startup_black_flash.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_weather_runtime.py` | **KEEP — MIGRATION PERMANENT** | Neutral Weather cache/cadence/retry/persistence/stale-generation owner coverage retained after F2 pixel retirement. |
| `tests/test_widget_capability_persist_repair.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_widget_descriptors.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_effects.py` | **STALE I RESIDUE — OLD FAMILY PIXEL OWNER** | Keep only until owning QWidget effect/shadow path is replaced. |
| `tests/test_widget_factories.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_family_catalog.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_lifecycle.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_manager.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_manager_refresh.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Current E2/E2.7 lifecycle/admission regression owner; six stale tests were corrected at 5b3cbaef. Update with E1/F ownership. |
| `tests/test_widget_import_dormancy.py` | **KEEP — MIGRATION PERMANENT** | Fresh-process legacy/common-Quick host/package and deactivated-family implementation/runtime/backend loading oracle; preserve after cutover. |
| `tests/test_widget_runtime_manager.py` | **KEEP — MIGRATION PERMANENT** | Neutral owner admission/service/fail-closed/reuse/lifecycle contract; source proof rejects dormant old widget-setup/coordinator bridges. |
| `tests/test_widget_runtime_owner_hoist.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Legacy `DisplayWidget -> WidgetRuntimeManager <- WidgetManager` identity/order proof. The physical host is already deleted; in I retain only the one-owner/cleanup-order semantics through `QuickDisplayRuntime` and remove stale host assertions. |
| `tests/test_widget_performance.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_positioner.py` | **I RECONCILIATION — G OWNER ALREADY PORTED** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_widget_positioning_comprehensive.py` | **I RECONCILIATION — G OWNER ALREADY PORTED** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_widget_setup.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_stack_predictor.py` | **I RECONCILIATION — G OWNER ALREADY PORTED** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_widget_visual_padding.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_widgets_tab.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_widgets_tab_general.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_widgets_tab_setup.py` | **KEEP** | Retain; no current retirement identified. |

### 10.5 Settings / capability / persistence

| File | Status | Note |
| --- | --- | --- |
| `tests/test_capability_activation.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_capability_activation_neutrality.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_default_settings_editor.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_regenerate_sst_defaults.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_settings_binding.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_settings_defaults_parity.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_settings_dialog.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_settings_dialog_cache.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_settings_manager.py` | **KEEP — PERMANENT SETTINGS / H8** | Core Settings behavior plus H8 schema-v4 flat-to-nested Custom-cache migration and atomic visualizer-child/cache persistence that survives disk reload without mutating Media siblings. |
| `tests/test_settings_no_sources_popup.py` | **KEEP — PERMANENT** | Current shared `StyledPopup` no-source recovery routing + curated RSS action contract. |
| `tests/test_settings_persistence.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_settings_profile_separation.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_settings_schema.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_settings_shared_styles.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_settings_sync.py` | **OBSOLETE NOW** | Tombstone only; contains no executable tests. |
| `tests/test_settings_theme_system.py` | **KEEP — PERMANENT** | Central ThemeSpec runtime transaction, catalogue/default mirror, persisted fallback and path-resolution ownership. |
| `tests/test_theme_foundry_model.py` | **KEEP — PERMANENT** | Pure schema-v5 Theme Foundry model coverage, including exact-RGBA bulk replacement and most-used-colour ranking/alpha separation. |

### 10.6 Media / audio

| File | Status | Note |
| --- | --- | --- |
| `tests/test_audio_capture_block_size.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_media_command_ingress.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_media_keys.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_media_provider_registry.py` | **KEEP — PERMANENT** | Provider identities plus canonical GSMTC Play/Pause/Toggle capability projection, exact command selection and absolute seek-tick contract. |
| `tests/test_media_provider_runtime.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_qtquick_media_presentation.py` | **KEEP — MIGRATION PERMANENT** | Retained Media core plus enabled-glyph/transport/progress/app-volume/system-mute/input admission, separate neutral-owner injection, real runtime-owner/host lifecycle and no-recreation destination coverage; retain as permanent current coverage. |
| `tests/test_media_runtime_artwork.py` | **KEEP — PERMANENT** | Presentation-neutral artwork decode, stable key and unchanged-payload deduplication contract. |
| `tests/test_media_runtime_state.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_media_runtime.py` | **KEEP — PERMANENT / EVENT-DRIVEN** | Shared Media owner/lease/controller/state/artwork/generation plus native-event coalescing, command convergence, slow reconcile watchdog, degraded/missed-event telemetry and stale-generation fencing; the retired 1–2.5s active poll is not authority. |
| `tests/test_media_event_observation.py` | **KEEP — PERMANENT / EVENT-DRIVEN** | Controller-level GSMTC subscription/token/session-replacement contract; native callbacks remain tiny and generation-fenced, with real-WinRT round-trip environment-gated. |
| `tests/test_media_volume_runtime.py` | **KEEP — PERMANENT** | Shared app-volume owner/lease/read-write generation/coalescing plus neutral Media-anchor injection contract. |
| `tests/test_system_mute_runtime.py` | **KEEP — PERMANENT** | Shared system-audio endpoint/poll/action/lease plus neutral Media-anchor injection contract. |
| `tests/test_media_widget_runtime_methods.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Temporary non-painting accepted-state/runtime/Visualizer anchor, geometry and neutral auxiliary-action lifecycle; physical host is already deleted; rehome only surviving accepted-state/Visualizer semantics in I and delete stale anchor/geometry assertions. |
| `tests/test_spotify_volume.py` | **KEEP — PERMANENT** | Presentation-neutral app-volume controller/backend contract. |

### 10.7 Gmail

| File | Status | Note |
| --- | --- | --- |
| `tests/test_gmail_assets.py` | **KEEP — PERMANENT** | Retained Quick asset identity plus packaging/notification-sound coverage. |
| `tests/test_gmail_backend_bootstrap.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_gmail_backend_smoke.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_gmail_client.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_gmail_runtime.py` | **KEEP — PERMANENT** | Shared Gmail owner/lease/bootstrap/cache/fetch/action/generation contract after presenter-edge retirement. |
| `tests/test_gmail_components.py` | **KEEP — PERMANENT** | Presentation-neutral sender/subject/date/grouping preparation used by the retained model. |
| `tests/test_gmail_deeplinks.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_gmail_imap_actions.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_gmail_oauth.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_gmail_preparation.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_qtquick_gmail_presentation.py` | **KEEP — MIGRATION PERMANENT** | Retained Gmail config/style, stable accepted-state row projection, static QML popup/height/visual fidelity, real manager-owned runtime/host state and action routing, and no-recreation lifecycle coverage. |
| `tests/test_gmail_retiring_runtime.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_gmail_settings_roundtrip.py` | **KEEP** | Retain; no current retirement identified. |

### 10.8 Reddit

| File | Status | Note |
| --- | --- | --- |
| `tests/test_main_reddit_helper_preload.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_qtquick_reddit_presentation.py` | **KEEP — MIGRATION PERMANENT** | Retained Reddit/Reddit2 config/style/row/state/action and no-recreation destination coverage. |
| `tests/test_reddit_exit_logic.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_reddit_helper_recovery.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_reddit_helper_runtime.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_reddit_helper_task_harness.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_reddit_helper_watcher.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_reddit_post_provider.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_reddit_preparation.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_reddit_provider_settings.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_reddit_rate_limiter.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_reddit_runtime.py` | **KEEP — MIGRATION PERMANENT** | Neutral startup/cache/cadence/manual-refresh/accepted-state/generation/retirement coverage. |

### 10.9 Steam

| File | Status | Note |
| --- | --- | --- |
| `tests/test_steam_abandonment_issues.py` | **KEEP** | Neutral Abandonment provider/cache/selection/preparation/model/rotation behavior; QWidget presentation assertions retired in F8. |
| `tests/test_steam_abandonment_runtime.py` | **KEEP — MIGRATION PERMANENT** | Neutral Abandonment owner/generation/cardinality/timer/lifecycle plus retired-caller proof. |
| `tests/test_qtquick_abandonment_issues_presentation.py` | **KEEP — MIGRATION PERMANENT** | Retained Abandonment config/style/model/image/runtime-action/transition lifecycle and stable shared Steam field-model coverage. |
| `tests/test_steam_achievement_pulse.py` | **KEEP** | Neutral Achievement selection/cache/provider/model behavior; QWidget presentation assertions retired in F7. |
| `tests/test_steam_achievement_runtime.py` | **KEEP — MIGRATION PERMANENT** | Neutral Achievement owner/generation/cardinality/reuse/dormancy/artwork lifecycle plus retired-caller proof. |
| `tests/test_qtquick_achievement_pulse_presentation.py` | **KEEP — MIGRATION PERMANENT** | Retained Achievement Pulse config/style/model/image/runtime-action lifecycle and stable identity destination coverage. |
| `tests/test_steam_backend.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_steam_cache.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_steam_credentials.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_steam_openid.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_steam_phase3_settings_descriptors.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_steam_profile_assets_events.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_steam_request_policy.py` | **KEEP** | Retain; no current retirement identified. |

### 10.10 Imgur — removed in F0

Deprecated Imgur has been removed from current product authority. Its three dedicated test modules
(`test_imgur_cache.py`, `test_imgur_scraper.py`, `test_imgur_widget.py`) were deleted. Mixed surviving
modules were de-Imgured in place rather than weakened. Historical references may remain as evidence but
no current test inventory row or product gate should restore the family.

### 10.11 Image/source/cache/providers

| File | Status | Note |
| --- | --- | --- |
| `tests/test_cache_maintenance.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_display_image_ops.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_image_cache_accounting.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_image_pipeline.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_image_prefetcher.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_image_processor.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_image_queue.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_image_worker.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_image_worker_shared_memory.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_lanczos_scaling.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_open_meteo_provider.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_resource_manager.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_resource_metrics.py` | **KEEP — H semantic ownership** | Retain detached accounting plus lifecycle ownership proof; display facts come only from the bounded Quick `DisplayManager` snapshot and fail loud/unavailable when that contract is absent. |
| `tests/test_rss_behavior.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_rss_startup_budget.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_source_head.py` | **KEEP** | Retain; no current retirement identified. |

### 10.12 Legacy/current rendering & performance

| File | Status | Note |
| --- | --- | --- |
| `tests/test_compositor_gpu_queries.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_compositor_metrics.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_compositor_presentation_liveness.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_frame_budget.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_frame_interpolator.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_frame_timing_workload.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_gl_compositor_cleanup.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_gl_fallback_policy.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Legacy FULL_SHADERS→COMPOSITOR_ONLY→SOFTWARE_ONLY demotion ladder; destination contract forbids this as final runtime policy. |
| `tests/test_gl_profiler.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_gl_shader_fallback_diagnostics.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_gl_stage_timestamps.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_gl_state_and_error_handling.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_gl_state_manager.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_gl_texture_streaming.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_gl_timer_queries.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_gpu_delivery_association.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_presentation_benchmark_core.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_rendering_backends.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Legacy OpenGL→Software backend selection/fallback; destination explicitly has no supported software presenter fallback. |
| `tests/test_retained_base_texture.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_startup_shader_warmup.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_stencil_mask_alignment.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_worker_push_presentation_benchmark.py` | **WILL BE OBSOLETE — J** | Migration comparison harness; archive after final cutover validation. |

### 10.13 Historical phase / migration regression

| File | Status | Note |
| --- | --- | --- |
| `tests/test_p2_165_delivery.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_p2_activation_final.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_analysis_freshness.py` | **KEEP — PERMANENT** | Presentation-neutral latest-source analysis freshness; keep. |
| `tests/test_p2_audio_capture_callback.py` | **KEEP — PERMANENT** | Presentation-neutral permanent regression. |
| `tests/test_p2_custom_cancel_media_state.py` | **I RECONCILIATION — G OWNER ALREADY PORTED** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_p2_custom_cancel_resume.py` | **I RECONCILIATION — G OWNER ALREADY PORTED** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_p2_custom_edit.py` | **I RECONCILIATION — G OWNER ALREADY PORTED** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_p2_gate1_spectrum_idle_pixels.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_gate1_spectrum_paused_visible.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_gate2_mode_switch_presents.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_gate6_gate9_ownership.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_gate7_pause_play_identity.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_idle_mode_switch_edge.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_live_source_to_reveal.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_logical_present_delivery.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_logical_runtime.py` | **KEEP — PERMANENT** | Despite P2 name, permanent: Qt-free logical runtime, latest-only mailbox, generation fencing, clean join, real ~90 Hz cadence bar. |
| `tests/test_p2_mode_activation_production.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_mode_activation_transaction.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_nested_gpu_timing.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_p2_perf_unchanged_scene.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_p2_playback_epoch.py` | **KEEP — PERMANENT** | Presentation-neutral permanent regression. |
| `tests/test_p2_playback_state_ownership.py` | **KEEP — PERMANENT** | Presentation-neutral permanent regression. |
| `tests/test_p2_pre_reveal_gl_warmup.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_ready_fade.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_single_surface.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Important one-surface intent, but harness imports legacy GLCompositor/SpotifyBarsGLOverlay. Quick successor must inherit intent before deletion. |
| `tests/test_p2_single_surface_gl_render.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_slicek_nonblocking_transport.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_p2_slow_tick_diagnostic.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_p2_spectrum_idle_presentation.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_spectrum_idle_reachability.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_visualizer_warmup.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p2_warm_pause_resume.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p3_set_state_attribution.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p4_native_presentation.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Mixed: DWM physical-delivery probe can remain useful; legacy compositor HUD/presenter pieces should be split out. |
| `tests/test_p4_rhi_compositor_surface.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Delete with legacy presenter during I after equivalent current-owner coverage is confirmed. |
| `tests/test_p4_rhi_fallback_visibility.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Legacy retained-base/QPainter fallback diagnostics tied to GLCompositor paint path. |
| `tests/test_p4_stage_integration.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_p4_stage_marker_order.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_phase1_measurement_benchmark.py` | **WILL BE OBSOLETE — J** | Historical architecture/performance evidence; archive after J. |
| `tests/test_phase3_runtime_lifecycle.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Mixed: durable generation/stale-callback lifecycle plus legacy GL/overlay teardown. Split as H/I advances. |
| `tests/test_phase4_resource_containment.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_phase_e_effect_corruption.py` | **OBSOLETE NOW** | Historical QGraphicsEffect investigation; many pass/documentation bodies and trivial checks. Real focus/native-event coverage exists elsewhere. |

### 10.14 Core runtime / tooling / platform

| File | Status | Note |
| --- | --- | --- |
| `tests/test_adaptive_timer.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_animation.py` | **I RECONCILIATION — OLD EFFECT/FAMILY PIXEL OWNER** | Generic manager may survive, but runtime QWidget/QGraphicsOpacityEffect cases are not destination presentation. |
| `tests/test_browser_window_routing.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_build_layout.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_build_runner.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_decorators.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_diagnostic_build.py` | **KEEP** | Retain diagnostic build/entrypoint/crash-capture proof; the entrypoint source gate rejects retired `DisplayWidget` patching. |
| `tests/test_event_loop_recorder.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_event_scheduler.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_events.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_flow_layout.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_fresh_start_logging.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_logging_config.py` | **KEEP — PERMANENT** | Logging bootstrap/family routing and exact rotating-handler policy; Diagnostic uses 2 MiB chunks with deliberately deeper bounded main/usage/lifecycle retention. |
| `tests/test_qt_message_capture_contract.py` | **KEEP — PERMANENT** | Process-scoped Qt/QML capture health: eager file/session markers, structured context, prior-handler preservation and passive metrics; complements real PySide/QML tests. |
| `tests/test_qt_message_capture_qml_runtime.py` | **KEEP — PERMANENT** | Real Qt/QML message-handler smoke; proves actual QML warnings reach the sidecar. |
| `tests/test_qtquick_family_product_actions.py` | **KEEP — PERMANENT** | Presentation-neutral product consequences for retained Reddit URL actions and per-display Clock runtime mode persistence. |
| `tests/test_logging_console_encoding.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_logging_routing.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_main_run_lifetime.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_mc_context_menu.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_mc_entrypoint_contract.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_mc_keyboard_input.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_mc_window_flags.py` | **STALE I RESIDUE — OLD PHYSICAL OWNER** | Old MC physical-window flag implementation; retained Quick window-role/policy tests own the destination contract. |
| `tests/test_memory_pooling.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_notification_sound_paths.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_ownership_trace.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_process_supervisor.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_qt_timer_threading.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_queued_logging.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_recovery_evidence_parser.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_runtime_callback_ownership.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_runtime_destruction.py` | **I RECONCILIATION — F OWNER ALREADY PORTED** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_save_debounce.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_secure_url_launcher.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_storage_paths.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_thread_manager.py` | **KEEP** | Retain generic thread/timer ownership diagnostics; old compositor cadence/transition scraping and classifiers retired in H. |
| `tests/test_usage_sampler.py` | **KEEP** | Retain; no current retirement identified. |

### 10.15 Other / integration

| File | Status | Note |
| --- | --- | --- |
| `tests/test_context_menu_activation.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_double_click_navigation.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_engine_lifecycle.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_integration_full_workflow.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_line4_6_pipeline_trace.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_log_throttling.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_prewarm_no_deadlock.py` | **I RECONCILIATION — QUICK SUCCESSOR EXISTS** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_s_hotkey_workflow.py` | **UPDATE REQUIRED NOW / KEEP — H PERMANENT** | Settings-generation retirement/replacement contract survives. Update the `_show_next_image` test double to accept current `origin=`; do not remove production image-change origin telemetry/admission. |
| `tests/test_worker_latency_tuning.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/unit/test_policy_compliance.py` | **KEEP** | Retain; no current retirement identified. |

## 11. Physical and acceptance evidence

Final J execution/sign-off follows `Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md`. This
section remains the test-ledger rule for distinguishing deterministic status from physical evidence.

Physical display/refresh/DPR/GPU/subjective claims remain separate from deterministic test status.

`tests/test_qtquick_runtime.py` contains two useful physical-source smoke cells that are retained for J rather than used as
the H per-commit gate:

- `test_threaded_runtime_uses_exact_identity_for_two_physical_displays`
- `test_threaded_runtime_recreates_removed_and_added_physical_topology`

They consume the operator's actual `QScreen` identities/topology and therefore remain valuable acceptance evidence, but a
timing/hardware red in those cells does not block the H authority cutover before the production Quick chain exists to validate.

Report per display as relevant:

- physical p50/p90/p95/p99/max;
- severe-gap counts;
- request/synchronization age where meaningful;
- visualizer logical cadence and source age;
- CPU/GPU context.

Internal `frameSwapped`/render callbacks are proxies, not proof of actual panel delivery. Bubble feel/BTF, transition visual parity, startup/reveal and widget visual/shadow parity still require operator eyes-on evidence where the requirement is subjective.

## 12. Lifecycle gate

Exercise as relevant:

- startup/shutdown;
- Settings/recreate;
- Edit/CUSTOM;
- visualizer active;
- transitions active;
- capability activation/deactivation/reactivation;
- monitor topology changes;
- display off/wake.

Require:

- logical runtime joins;
- stale state rejected;
- generation zero preserved;
- retired scene cannot reveal;
- render resources return to expected baseline;
- no old-generation callback survives destruction;
- no background owner prevents process/test shutdown.

A pytest summary followed by a process that never exits is lifecycle evidence to diagnose, not a reason to raise timeout blindly.

## 13. Inventory maintenance rule

This ledger must not rot back into strategy-only prose.

Whenever a checkpoint:

- adds a test file;
- renames/moves a test file;
- deletes a test file;
- intentionally retires a production owner;
- rehomes a surviving contract from legacy presenter to Quick;
- discovers a baseline-red stale test;

update the relevant inventory row in `Docs/TestSuite.md` **in the same checkpoint**.

Do not add hand-maintained aggregate counts as a second authority over the row inventory. If a count is useful for an
audit, generate it from that exact tree and keep it in the audit/evidence rather than letting it become stale living prose.

When a `WILL BE OBSOLETE` source owner is actually deleted, do one of three explicit things:

1. delete the test because the behavior itself was implementation-only;
2. move the surviving assertion into the named Quick/current-owner suite and then delete the old test;
3. retain the file only if it has been rewritten so completely that its name/status no longer misrepresents ownership.

Do not leave zero-test tombstones behind merely to record history; Git and historical docs already provide history.

When a whole caller-dead feature island has no surviving neutral caller/contract, retire the implementation and its
implementation-only regression together instead of keeping one solely to justify the other. This is the rule applied to
the retired global/general Presets island; visualizer presets are a separate live system.

## 14. Completion rule

Green focused tests are necessary but not sufficient.

Implementation closure and acceptance closure are distinct. An acceptance/sign-off ledger stays open until assigned gates actually run against the relevant commit/environment.

Do not turn an unchecked gate into a pass because:

- source review looks good;
- an agent says it should pass;
- another environment cannot execute it;
- later implementation has already begun.

A later failure reopens the smallest demonstrated defect.
