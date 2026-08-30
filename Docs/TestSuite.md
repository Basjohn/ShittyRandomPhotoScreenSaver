# Test Suite Guide

Last updated: 2026-08-30

Reviewed authority:

```text
G: independently audited and accepted; no active G implementation gate.
H pre-cutover visualizer destination edge: CLOSED, including the stronger True-F technical/retained-consumer proof.
CURRENT H: caller-proven legacy physical-host source deletion audit; maintained destination profile 60/60 GREEN after deletion.
Settings GUI/theme: large 2026 overhaul reconciled against current ui/ source in this test-maintenance pass.
```

This document is the SRPSS testing strategy and **live test-file inventory/retirement ledger**. It is not a phase changelog.
`Current_Plan.md` owns the current implementation sequence and exact checkpoint. Exact source outranks this inventory when
later work has landed.

The whole top-level test tree is **not currently one homogeneous H gate**. Until H/I remove the legacy `DisplayWidget`,
GLCompositor, old QWidget edit-shell and related presenter tests, a whole-tree run intentionally mixes destination Quick
contracts with tests whose implementation owners are scheduled for deletion. Whole-tree results remain valuable for debt
reconciliation, but an unrelated legacy red does not reopen a previously proven H destination gate by itself.

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
| `MIGRATION-CRITICAL — <phase>` | The contract survives, but the harness/owner will move. Rehome/update it in the named phase before deleting old assertions. |
| `WILL BE OBSOLETE — <phase>` | Still legitimate for the current production/transition state, but its implementation owner is intentionally removed in the named phase. Do not let it become destination authority. |
| `UPDATE REQUIRED NOW` | The test itself is already stale/brittle/known-red against current authority. Classify source-vs-test first, then fix deliberately. |
| `OBSOLETE NOW` | No longer meaningful current regression coverage. Delete rather than skip or preserve as fake authority. |

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

The **current H destination gate** is the maintained profile:

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
a single production-authority gate. The post-deletion collection diagnostic currently reaches 2,846 tests and reports 58
legacy-owner collection errors before one old visualizer module aborts collection; those failures are admitted I inventory,
not a reason to restore H production modules. After I retires/re-homes them, the complete tree should regain normal broad-gate
authority.

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
- interruption/exactly-once completion;
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

E, F and complete G are closed at their accepted boundaries. Their surviving neutral/destination tests remain permanent
regressions, but they are not active implementation gates and should not be rewritten back into QWidget presentation tests.

The H pre-cutover visualizer correction gate is also closed. The standing destination evidence includes:

- all-five logical configuration ownership;
- one GUI/Quick presentation synchronization edge;
- single-display visualizer admission;
- semantic visualizer double-click mode cycling;
- hard authored-runtime join/retirement barrier;
- neutral presentation configuration;
- **True-F** canonical technical cache -> shared BeatEngine/logical state -> bar-count coherence -> exact retained Quick item
  consumption without `SpotifyVisualizerWidget`.

### H — CURRENT: physical-host deletion audit

The coordinated `DisplayManager` + engine authority cutover onto Quick display units is complete at the production source
boundary, and the caller-proven old physical host is deleted in the current checkpoint. "Coordinated/atomic" describes the
**finished authority topology**, not one uninterrupted coding session or one giant commit. The final H audit must not restore
a second legitimate production presenter or a fake `DisplayWidget` compatibility facade to satisfy obsolete tests.

Use the `h-destination` runner profile as the bounded regression bar while this conversion proceeds. It contains the current
Quick display/unit/family/geometry/input/CUSTOM owners, all retained family presentations, the corrected visualizer edge and
authored fidelity bars, plus destination transition contracts. Extend the profile only for a surviving H contract; do not
add old physical-host tests merely to make the profile look broad.

H runtime-shaped proof must ultimately cover one/multiple selected displays, image/transition routing, ordinary families,
the one admitted visualizer, generation/topology replacement, clean retirement and caller-proven old-host deletion.

### I

Residue-only source **and test** reconciliation after the authority flip. Delete/rehome legacy `DisplayWidget`, GLCompositor,
QWidget edit-shell/auxiliary and old visualizer-presenter tests only after caller/source proof establishes that their owner is
gone and the surviving product contract is covered by destination tests. At the end of I, restore the whole-tree suite as a
normal broad regression authority rather than carrying permanent ignore lists.

### J

Comprehensive compiled/installed 1/2/N-display, mixed-refresh/DPR/topology/off-wake, full eyes-on parity, physical tail
metrics and clean-exit validation. Architecture-selection spike tests may retire only after final evidence exists.

## 6. Immediate test-maintenance state

The Settings-overhaul drift found during the pre-cutover caution run is reconciled in this pass:

| File | Status | Disposition |
| --- | --- | --- |
| `tests/test_settings_no_sources_popup.py` | **RECONCILED** | Tests current central `StyledPopup` construction/result routing and current curated-source actions; no retired `NoSourcesPopup` import. |
| `tests/test_sine_line4_ui_simulation.py` | **RECONCILED** | Tests the central `ColorSwatchButton` + `bind_color_button` contract, including programmatic-load no-save behavior. |
| `tests/test_sine_line4_builder_integration.py` | **RECONCILED** | Uses the real lazy `WidgetsTab` visualizer hydration/save owner and round-trips Line 4 colour/glow/shift. |
| `tests/test_sine_line4_persistence.py` | **RECONCILED** | Removes retired `_sine_line4_horizontal_shift` assumptions; locks current normalized `sine_line4_shift` binder semantics. |
| `tests/test_visualizer_settings_plumbing.py` | **PARTIALLY RECONCILED / H-I MIXED** | Known unknown-mode assertion now follows the canonical registry fallback. Surviving settings contracts remain; legacy presenter/overlay portions retire or rehome with their owners in H/I. |
| `tests/test_settings_theme_system.py` | **ADDED — PERMANENT** | Locks the centralized Settings ThemeSpec runtime transaction, catalog/default-mirror rules, persisted fallback semantics and temporary path-resolution precedence. |
| `tests/run_chunked.py` | **RECONCILED** | Adds one collection preflight and a maintained, **target-isolated** `h-destination` profile so QQuick teardown cannot poison unrelated targets; whole-tree mode remains available for reconciliation. |
| `tests/test_qtquick_custom_layout_owner.py` | **ADDED — H DESTINATION** | Proves one manager-generation CUSTOM owner, same-item Cancel, exact committed geometry/size/enabled Save, routed ordinary same-item A-to-B transfer/Cancel/Save without a target duplicate, retained menu/Enter/Escape routes, and visualizer transfer retargeting without duplicate logical/presentation ownership. |

Remaining non-blocking ledger debt belongs to the owner named by each row, not to the current H admission decision:

- `tests/test_settings_sync.py` is a tombstone-only file and can be deleted in residue cleanup;
- `tests/test_phase_e_effect_corruption.py` remains obsolete historical investigation scaffolding;
- `tests/test_visualizer_doc_references.py` still deserves a later brittle-prose-token cleanup;
- whole-tree legacy physical-host reds are classified in the inventory/retirement register and are not silently skipped.

## 7. Legacy-retirement register

High-value groups that must **not** become destination authority:

- **F0 (done):** the three Imgur test modules were deleted with the Imgur removal.
- **F0.5 (done):** deleted `test_shadow_tuning_paths.py` and `test_base_overlay_shadow_cache.py`; trimmed the tuning-payload assertion from `test_shadow_utils.py`.
- **E4/F remaining:** QWidget opacity/effect implementations such as `test_widget_effects.py`; remaining `ShadowFadeProfile` coverage retires with its presentation owners.
- **H/I:** legacy renderer backend/software fallback (`test_rendering_backends.py`, `test_gl_fallback_policy.py`), GLCompositor retained-base/fallback/presenter tests, `test_block_puzzle_flip.py`, QRhiWidget P4 surface tests, old SpotifyBarsGLOverlay presentation tests.
- **H/I mixed CUSTOM:** retain neutral session/geometry/persistence assertions from `test_custom_layout_manager.py`, but direct `EditShellWidget` guide/button/pixel assertions retire or rehome to the retained Quick CUSTOM overlay when the old shell is deleted.
- **J:** architecture-selection/spike benchmark suites where no ongoing product regression remains.

A `WILL BE OBSOLETE` test remains legitimate until the named owner is retired. Do not delete it early simply to reduce test count.

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
| `tests/test_qtquick_blinds_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_bootstrap.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_build_packaging.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_burn_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_crumble_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_diffuse_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_frame_pacer.py` | **KEEP — MIGRATION PERMANENT** | Single display-local presentation pacer, including callback-required visualizer GUI synchronization before each retained update opportunity. |
| `tests/test_qtquick_image_boundary.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_image_textures.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_custom_layout_session.py` | **KEEP — MIGRATION PERMANENT / G** | Neutral session/variants/working-state contract; separate visualizer scale + viewport extent is landed and remains permanent. |
| `tests/test_qtquick_custom_layout_overlay.py` | **KEEP — MIGRATION PERMANENT / G** | Retained CUSTOM overlay/drag/edge+corner resize/cross-display contract; extend only for current viewport-lifecycle corrections where applicable. |
| `tests/test_qtquick_auxiliary.py` | **KEEP — MIGRATION PERMANENT / G7** | Same-scene dimming/pixel-shift/halo generation and lifecycle contract. |
| `tests/test_qtquick_context_menu.py` | **KEEP — MIGRATION PERMANENT / G7** | Retained context-menu model/QML/action admission contract. |
| `tests/test_qtquick_input_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current input contract, including generation closure and the presentation-neutral runtime-replacement pointer guard consumed by Quick. |
| `tests/test_qtquick_clock_presentation.py` | **KEEP — MIGRATION PERMANENT** | F1 retained Clock model/family/ticker/style/geometry/analogue-shadow destination contract; retain through cutover. |
| `tests/test_qtquick_weather_presentation.py` | **KEEP — MIGRATION PERMANENT** | F2 retained Weather runtime-consumer/model/state/icon/style/action/host contract; retain through cutover. |
| `tests/test_qtquick_ordinary_widget_host.py` | **KEEP — MIGRATION PERMANENT** | E3/E4 retained ordinary-widget host + shared shell primitives; root fade, cached card shadow, signed offsets and offset-only text shadow are destination architecture. |
| `tests/test_shadow_direction.py` | **KEEP — MIGRATION PERMANENT** | E4 canonical direction/settings/resolver/QML-boundary contract; retain through cutover. |
| `tests/test_qtquick_p0_presentation_benchmark.py` | **WILL BE OBSOLETE — J** | Architecture-selection benchmark, not a forever product regression. |
| `tests/test_qtquick_particle_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_phase_c_effect_smoke.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_phase_c_registry_parity.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_presentation_spike.py` | **WILL BE OBSOLETE — J** | Architecture-selection spike, not a forever product regression. |
| `tests/test_qtquick_render_node.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_ripple_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_runtime.py` | **KEEP — MIXED H/J** | Deterministic/source-shaped runtime ownership, generation recreation and coordinated input-exit tests remain in the H destination profile. The two tests explicitly requiring real physical displays (`test_threaded_runtime_uses_exact_identity_for_two_physical_displays` and `test_threaded_runtime_recreates_removed_and_added_physical_topology`) are J physical/topology evidence and are intentionally not part of the per-commit H profile. |
| `tests/test_qtquick_scene_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_transition_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_transition_implementations.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_transition_parameter_defaults.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_transition_parameter_resolution.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_transition_request_resolution.py` | **KEEP — MIGRATION PERMANENT / H** | One Settings-authored transition spec per accepted image batch, fail-closed Random admission and frozen direction/parameter values. |
| `tests/test_qtquick_transition_state.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_transition_state_fence.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_transition_uniform_wiring.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_visualizer_all_modes.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_visualizer_bubble.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_visualizer_clip_smoke.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_visualizer_devcurve.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_visualizer_fade_authority.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_visualizer_geometry.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_visualizer_item.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_visualizer_oscilloscope.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_visualizer_render_bridge.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_visualizer_sine.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_visualizer_spectrum.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_window.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |

| `tests/test_qtquick_ctrl_coordinator.py` | **KEEP — MIGRATION PERMANENT / H** | One authoritative cross-display Ctrl truth and retired-contribution cleanup. |
| `tests/test_qtquick_display_image_route.py` | **KEEP — MIGRATION PERMANENT / H** | GUI pixmap -> immutable Quick presentation-image routing, detached image-accounting aggregation and target-size contract. |
| `tests/test_qtquick_display_presenter.py` | **KEEP — MIGRATION PERMANENT / H** | Thin per-display destination presenter; no provider/window/persistence authority. |
| `tests/test_qtquick_display_unit.py` | **KEEP — MIGRATION PERMANENT / H** | Per-display Quick destination-chain assembly and semantic display operations. |
| `tests/test_qtquick_family_binder.py` | **KEEP — MIGRATION PERMANENT / H** | Single-manager family admission/runtime service ownership, canonical per-instance monitor routing across logical displays, and retained host binding. |
| `tests/test_qtquick_family_size_policy.py` | **KEEP — MIGRATION PERMANENT / H** | Historical deterministic family preferred-size policies under Option-A geometry. |
| `tests/test_qtquick_geometry_resolver.py` | **KEEP — MIGRATION PERMANENT / H** | Python outer-rect/anchor/clamp authority; no QML outer-position feedback loop. |
| `tests/test_qtquick_h_cutover.py` | **KEEP — MIGRATION PERMANENT / H** | H authority-cutover/cardinality/deletion bars, including Quick-only DisplayManager and engine caller source surfaces with no legacy presenter/CUSTOM compatibility branch, one canonical manager-admitted visualizer owner, retained menu/double-click mode actions, hidden-boundary hard join, exact-once engine activation transaction, fresh-target reveal and engine-retirement lifecycle. |
| `tests/test_qtquick_overlay_preferred_size.py` | **KEEP — MIGRATION PERMANENT / H** | Size-only preferred-content signal contract used by Python geometry ownership, including terminal disconnection before retained-item retirement. |
| `tests/test_qtquick_visualizer_admission.py` | **KEEP — MIGRATION PERMANENT / H** | Exactly one admitted Quick visualizer display owner with requested/hold/fallback policy. |
| `tests/test_qtquick_visualizer_all_five_owner_chain.py` | **KEEP — MIGRATION PERMANENT / H** | Owner-shaped all-five widget-free destination chain. |
| `tests/test_qtquick_visualizer_double_click.py` | **KEEP — MIGRATION PERMANENT / H** | Retained visualizer mode-cycle semantic admission before global next-image fallback. |
| `tests/test_qtquick_visualizer_logical_ownership.py` | **KEEP — MIGRATION PERMANENT / H** | Controller-owned authored logical state/runtime ownership without QWidget host. |
| `tests/test_qtquick_visualizer_owner_edge.py` | **KEEP — MIGRATION PERMANENT / H** | Thin display/generation visualizer ownership edge, single shared-engine acquire/release, hard retirement, and terminal callback release semantics. |
| `tests/test_qtquick_visualizer_pre_cutover_audit.py` | **KEEP — MIGRATION PERMANENT / H** | Standing source/behavior regression bars from the H pre-cutover audit. |
| `tests/test_qtquick_visualizer_true_f_gate.py` | **KEEP — MIGRATION PERMANENT / H** | Strong True-F technical-engine/logical/bar-count + exact retained-item consumption gate. |

### 10.2 Visualizer

| File | Status | Note |
| --- | --- | --- |
| `tests/test_bubble_btf_coalescing.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_bubble_viewport_config_route.py` | **KEEP — MIGRATION PERMANENT / G4** | Live/coalesced viewport configuration route into each authored Bubble step; extend for committed-vs-CUSTOM override lifecycle. |
| `tests/test_bubble_viewport_reflow.py` | **KEEP — MIGRATION PERMANENT / G4** | Baseline exact no-op plus wide/tall/shrink domain projection, authored-count invariance and no geometry-created tick. |
| `tests/test_bubble_cadence.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_bubble_reactivity.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_bubble_renderer_transport.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_bubble_shader_compile.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_devcurve_builder_contract.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_devcurve_runtime.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_devcurve_settings_binding.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_devcurve_shader_contract.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_devcurve_shape_editor.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_input_gain.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_osc_sine_glow_contract.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_oscilloscope_display_contract.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_remote_visualizer_capability_admission.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_sine_line4_builder_integration.py` | **KEEP — MIGRATION PERMANENT** | Current lazy `WidgetsTab` builder + real save/round-trip coverage for Line 4 colour/glow/shift. |
| `tests/test_sine_line4_persistence.py` | **KEEP — MIGRATION PERMANENT** | Current binder colour/glow + normalized `sine_line4_shift` collect/load contract. |
| `tests/test_sine_line4_ui_simulation.py` | **KEEP — MIGRATION PERMANENT** | Central `ColorSwatchButton` + builder binding contract; programmatic load is non-saving, user signal updates/saves. |
| `tests/test_sine_wave_gl_fix.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_spectrum_presentation_smoothing.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_spectrum_shaping.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_spotify_overlay_repaint_contract.py` | **MIGRATION-CRITICAL — H/I** | Scheduling contract survives; SpotifyBarsGLOverlay/display-compositor owner does not. |
| `tests/test_spotify_visualizer_integration.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_spotify_visualizer_mode_transition.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_spotify_visualizer_widget.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_transient_bus.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_transient_per_mode_integration.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_transient_preset_preservation.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_alignment.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_visualizer_analysis_acceptance.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_architecture_split.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_capability_admission.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_card_geometry.py` | **WILL BE OBSOLETE — H/I** | Tests pre-Quick mode growth/relative card geometry that destination explicitly retires; Quick geometry tests are the destination authority. |
| `tests/test_visualizer_compute_lanes.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_doc_references.py` | **UPDATE REQUIRED NOW** | Known stale brittle assertion: do not ban a token globally when legitimate historical/contrast wording may mention it. |
| `tests/test_visualizer_failover_reclaim.py` | **KEEP — MIGRATION PERMANENT** | E2.7 canonical global-singleton/grace/reclaim/capability lifecycle suite. Must remain authoritative until successor owner inherits it. |
| `tests/test_visualizer_feature_frame.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_mode_isolation.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_modes.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_overlay_kwargs.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_visualizer_playback_gating.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_presentation_contract.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_presentation_negative_controls.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_preset_cycling_runtime.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_preset_manifest.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_preset_transfer.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_presets.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_reactivity_quality.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_replay.py` | **RETIRE/REHOME — I** | Imports the removed QWidget replay host; the maintained H profile now uses runtime-shaped Settings replacement and controller-owned cadence/bridge tests instead. Preserve only authored-fidelity assertions that still falsify a destination contract. |
| `tests/test_visualizer_retired_modes.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_runtime_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination runtime-controller contract, including presentation-neutral viewport configuration ownership; retain through cutover. |
| `tests/test_visualizer_settings_plumbing.py` | **MIGRATION-CRITICAL — H/I (MIXED)** | Registry/settings/shader contracts survive; known mode fallback is current. Retire/rehome old presenter/overlay assertions with their source owner. |
| `tests/test_visualizer_smart_positioning.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_visualizer_startup_contract.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |

### 10.3 Transitions

| File | Status | Note |
| --- | --- | --- |
| `tests/test_block_puzzle_flip.py` | **WILL BE OBSOLETE — H/I** | Legacy `GLCompositorBlockFlipTransition` implementation/API coverage; Quick registry/transition implementation tests own the destination contract. |
| `tests/test_diffuse_transition.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_gl_compositor_transition_lifecycle.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_gl_compositor_transitions.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_micro_wobble_math.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_slide_jitter.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_slide_transition.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_transition_activation_admission.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_transition_catalog_imports.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_transition_distribution.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_transition_endframe.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_transition_perf_health_parser.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_transition_registry.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_transition_state_manager.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_transitions.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_transitions_tab.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_transitions_tab_setup.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |

### 10.4 Widget/display presentation & CUSTOM

| File | Status | Note |
| --- | --- | --- |
| `tests/test_custom_layout_contract.py` | **KEEP — retained CUSTOM contract** | Retain neutral CUSTOM geometry/persistence proof; the durable contract now owns the exact persisted screen-signature algorithm without the retired multi-monitor coordinator. |
| `tests/test_custom_layout_manager.py` | **MIGRATION-CRITICAL — H/I (MIXED)** | Neutral CUSTOM session/geometry/persistence survives; direct `EditShellWidget` guide/button/pixel assertions retire/rehome with the legacy shell. |
| `tests/test_dimming_and_interaction_fixes.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_display_context_menu.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_display_integration.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_display_setup.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_display_tab.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_display_widget_target_size.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_fade_coordinator.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_flicker_fix_integration.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_ghost_isolation.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_gl_compositor_overlays.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_gl_state_manager_overlay.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_layout_slots.py` | **KEEP — MIGRATION PERMANENT / G** | Ordinary visible-layout snapshot semantics; protect ON/OFF vs capability activation and separate visualizer scale/viewport extent replay. |
| `tests/test_multi_monitor_focus.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_multidisplay_sync.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_no_legacy_widget_position_strings.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_overlay_diagnostics.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_overlay_frame_shell.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_overlay_render_dispatch.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_overlay_startup_policy.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_overlay_uniforms.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_pixel_shift.py` | **MIGRATION-CRITICAL — H/I (MIXED)** | Legacy QWidget manager/statistical movement coverage is not the retained Quick auxiliary authority; preserve only surviving burn-in semantics when old owner retires. |
| `tests/test_service_widget_runtime.py` | **MIGRATION-CRITICAL — F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_f0_5_shadow_controls.py` | **KEEP — MIGRATION PERMANENT** | F0.5 canonical shadow cleanup + Widgets → General controls: sidecar retirement, model/default parity, retired-`offset` drop, 3×3 direction picker, and the save-preservation merge. |
| `tests/test_shadow_utils.py` | **MIGRATION-CRITICAL — F** | Mixed legacy file. F0.5 removed the tuning-payload assertion; remaining `ShadowFadeProfile`/QGraphicsOpacityEffect assertions survive only until their legacy presentation owners are removed. Do not preserve sidecar semantics or port staged effect-carrier fades. |
| `tests/test_startup_black_flash.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_weather_runtime.py` | **KEEP — MIGRATION PERMANENT** | Neutral Weather cache/cadence/retry/persistence/stale-generation owner coverage retained after F2 pixel retirement. |
| `tests/test_widget_capability_persist_repair.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_widget_descriptors.py` | **MIGRATION-CRITICAL — F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_effects.py` | **WILL BE OBSOLETE — E4/F** | Keep only until owning QWidget effect/shadow path is replaced. |
| `tests/test_widget_factories.py` | **MIGRATION-CRITICAL — F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_family_catalog.py` | **MIGRATION-CRITICAL — F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_lifecycle.py` | **MIGRATION-CRITICAL — F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_manager.py` | **MIGRATION-CRITICAL — F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_manager_refresh.py` | **MIGRATION-CRITICAL — F** | Current E2/E2.7 lifecycle/admission regression owner; six stale tests were corrected at 5b3cbaef. Update with E1/F ownership. |
| `tests/test_widget_import_dormancy.py` | **KEEP — MIGRATION PERMANENT** | Fresh-process legacy/common-Quick host/package and deactivated-family implementation/runtime/backend loading oracle; preserve after cutover. |
| `tests/test_widget_runtime_manager.py` | **KEEP — MIGRATION PERMANENT** | Neutral owner admission/service/fail-closed/reuse/lifecycle contract; source proof rejects dormant old widget-setup/coordinator bridges. |
| `tests/test_widget_runtime_owner_hoist.py` | **MIGRATION-CRITICAL — H/I** | Current `DisplayWidget -> WidgetRuntimeManager <- WidgetManager` identity/order proof; rehome host identity to `QuickDisplayRuntime` at cutover while preserving one-owner/cleanup-order semantics. |
| `tests/test_widget_performance.py` | **MIGRATION-CRITICAL — F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_positioner.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_widget_positioning_comprehensive.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_widget_setup.py` | **MIGRATION-CRITICAL — F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_stack_predictor.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_widget_visual_padding.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_widgets_tab.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_widgets_tab_general.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_widgets_tab_setup.py` | **KEEP** | Retain; no migration-specific retirement identified. |

### 10.5 Settings / capability / persistence

| File | Status | Note |
| --- | --- | --- |
| `tests/test_capability_activation.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_capability_activation_neutrality.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_default_settings_editor.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_regenerate_sst_defaults.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_binding.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_defaults_parity.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_dialog.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_dialog_cache.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_manager.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_no_sources_popup.py` | **KEEP — PERMANENT** | Current shared `StyledPopup` no-source recovery routing + curated RSS action contract. |
| `tests/test_settings_persistence.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_profile_separation.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_schema.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_shared_styles.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_sync.py` | **OBSOLETE NOW** | Tombstone only; contains no executable tests. |
| `tests/test_settings_theme_system.py` | **KEEP — PERMANENT** | Central ThemeSpec runtime transaction, catalogue/default mirror, persisted fallback and path-resolution ownership. |
| `tests/test_theme_foundry_model.py` | **KEEP — PERMANENT** | Pure schema-v5 Theme Foundry model coverage, including exact-RGBA bulk replacement and most-used-colour ranking/alpha separation. |

### 10.6 Media / audio

| File | Status | Note |
| --- | --- | --- |
| `tests/test_audio_capture_block_size.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_media_command_ingress.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_media_keys.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_media_provider_registry.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_media_provider_runtime.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_qtquick_media_presentation.py` | **KEEP — MIGRATION PERMANENT** | Retained Media core plus transport/progress/app-volume/system-mute/input admission, separate neutral-owner injection, real runtime-owner/host lifecycle and no-recreation destination coverage; retain through cutover. |
| `tests/test_media_runtime_artwork.py` | **KEEP — PERMANENT** | Presentation-neutral artwork decode, stable key and unchanged-payload deduplication contract. |
| `tests/test_media_runtime_state.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_media_runtime.py` | **KEEP — PERMANENT** | Shared Media owner/lease/controller/poll/state/artwork/generation contract; presentation-neutral after F4. |
| `tests/test_media_volume_runtime.py` | **KEEP — PERMANENT** | Shared app-volume owner/lease/read-write generation/coalescing plus neutral Media-anchor injection contract. |
| `tests/test_system_mute_runtime.py` | **KEEP — PERMANENT** | Shared system-audio endpoint/poll/action/lease plus neutral Media-anchor injection contract. |
| `tests/test_media_widget_runtime_methods.py` | **MIGRATION-CRITICAL — H** | Temporary non-painting accepted-state/runtime/Visualizer anchor, geometry and neutral auxiliary-action lifecycle; retire/rehome with physical host cutover. |
| `tests/test_spotify_volume.py` | **KEEP — PERMANENT** | Presentation-neutral app-volume controller/backend contract. |

### 10.7 Gmail

| File | Status | Note |
| --- | --- | --- |
| `tests/test_gmail_assets.py` | **KEEP — PERMANENT** | Retained Quick asset identity plus packaging/notification-sound coverage. |
| `tests/test_gmail_backend_bootstrap.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_backend_smoke.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_client.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_runtime.py` | **KEEP — PERMANENT** | Shared Gmail owner/lease/bootstrap/cache/fetch/action/generation contract after presenter-edge retirement. |
| `tests/test_gmail_components.py` | **KEEP — PERMANENT** | Presentation-neutral sender/subject/date/grouping preparation used by the retained model. |
| `tests/test_gmail_deeplinks.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_imap_actions.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_oauth.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_preparation.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_qtquick_gmail_presentation.py` | **KEEP — MIGRATION PERMANENT** | Retained Gmail config/style, stable accepted-state row projection, static QML popup/height/visual fidelity, real manager-owned runtime/host state and action routing, and no-recreation lifecycle coverage. |
| `tests/test_gmail_retiring_runtime.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_settings_roundtrip.py` | **KEEP** | Retain; no migration-specific retirement identified. |

### 10.8 Reddit

| File | Status | Note |
| --- | --- | --- |
| `tests/test_main_reddit_helper_preload.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_qtquick_reddit_presentation.py` | **KEEP — MIGRATION PERMANENT** | Retained Reddit/Reddit2 config/style/row/state/action and no-recreation destination coverage. |
| `tests/test_reddit_exit_logic.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_helper_recovery.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_helper_runtime.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_helper_task_harness.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_helper_watcher.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_post_provider.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_preparation.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_provider_settings.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_rate_limiter.py` | **KEEP** | Retain; no migration-specific retirement identified. |
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
| `tests/test_steam_backend.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_steam_cache.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_steam_credentials.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_steam_openid.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_steam_phase3_settings_descriptors.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_steam_profile_assets_events.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_steam_request_policy.py` | **KEEP** | Retain; no migration-specific retirement identified. |

### 10.10 Imgur — removed in F0

Deprecated Imgur has been removed from current product authority. Its three dedicated test modules
(`test_imgur_cache.py`, `test_imgur_scraper.py`, `test_imgur_widget.py`) were deleted. Mixed surviving
modules were de-Imgured in place rather than weakened. Historical references may remain as evidence but
no current test inventory row or product gate should restore the family.

### 10.11 Image/source/cache/providers

| File | Status | Note |
| --- | --- | --- |
| `tests/test_cache_maintenance.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_display_image_ops.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_image_cache_accounting.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_image_pipeline.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_image_prefetcher.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_image_processor.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_image_queue.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_image_worker.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_image_worker_shared_memory.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_lanczos_scaling.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_open_meteo_provider.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_resource_manager.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_resource_metrics.py` | **KEEP — H semantic ownership** | Retain detached accounting plus lifecycle ownership proof; display facts come only from the bounded Quick `DisplayManager` snapshot and fail loud/unavailable when that contract is absent. |
| `tests/test_rss_behavior.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_rss_startup_budget.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_source_head.py` | **KEEP** | Retain; no migration-specific retirement identified. |

### 10.12 Legacy/current rendering & performance

| File | Status | Note |
| --- | --- | --- |
| `tests/test_compositor_gpu_queries.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_compositor_metrics.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_compositor_presentation_liveness.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_frame_budget.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_frame_interpolator.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_frame_timing_workload.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gl_compositor_cleanup.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_gl_fallback_policy.py` | **WILL BE OBSOLETE — H/I** | Legacy FULL_SHADERS→COMPOSITOR_ONLY→SOFTWARE_ONLY demotion ladder; destination contract forbids this as final runtime policy. |
| `tests/test_gl_profiler.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_gl_shader_fallback_diagnostics.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_gl_stage_timestamps.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_gl_state_and_error_handling.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_gl_state_manager.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_gl_texture_streaming.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_gl_timer_queries.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_gpu_delivery_association.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_presentation_benchmark_core.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_rendering_backends.py` | **WILL BE OBSOLETE — H/I** | Legacy OpenGL→Software backend selection/fallback; destination explicitly has no supported software presenter fallback. |
| `tests/test_retained_base_texture.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_startup_shader_warmup.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_stencil_mask_alignment.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_worker_push_presentation_benchmark.py` | **WILL BE OBSOLETE — J** | Migration comparison harness; archive after final cutover validation. |

### 10.13 Historical phase / migration regression

| File | Status | Note |
| --- | --- | --- |
| `tests/test_p2_165_delivery.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_p2_activation_final.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_analysis_freshness.py` | **KEEP — PERMANENT** | Presentation-neutral latest-source analysis freshness; keep. |
| `tests/test_p2_audio_capture_callback.py` | **KEEP — PERMANENT** | Presentation-neutral permanent regression. |
| `tests/test_p2_custom_cancel_media_state.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_p2_custom_cancel_resume.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_p2_custom_edit.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_p2_gate1_spectrum_idle_pixels.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_gate1_spectrum_paused_visible.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_gate2_mode_switch_presents.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_gate6_gate9_ownership.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_gate7_pause_play_identity.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_idle_mode_switch_edge.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_live_source_to_reveal.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_logical_present_delivery.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_logical_runtime.py` | **KEEP — PERMANENT** | Despite P2 name, permanent: Qt-free logical runtime, latest-only mailbox, generation fencing, clean join, real ~90 Hz cadence bar. |
| `tests/test_p2_mode_activation_production.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_mode_activation_transaction.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_nested_gpu_timing.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_p2_perf_unchanged_scene.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_p2_playback_epoch.py` | **KEEP — PERMANENT** | Presentation-neutral permanent regression. |
| `tests/test_p2_playback_state_ownership.py` | **KEEP — PERMANENT** | Presentation-neutral permanent regression. |
| `tests/test_p2_pre_reveal_gl_warmup.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_ready_fade.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_single_surface.py` | **MIGRATION-CRITICAL — H/I** | Important one-surface intent, but harness imports legacy GLCompositor/SpotifyBarsGLOverlay. Quick successor must inherit intent before deletion. |
| `tests/test_p2_single_surface_gl_render.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_slicek_nonblocking_transport.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_p2_slow_tick_diagnostic.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_p2_spectrum_idle_presentation.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_spectrum_idle_reachability.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_visualizer_warmup.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_warm_pause_resume.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p3_set_state_attribution.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p4_native_presentation.py` | **MIGRATION-CRITICAL — H/I** | Mixed: DWM physical-delivery probe can remain useful; legacy compositor HUD/presenter pieces should be split out. |
| `tests/test_p4_rhi_compositor_surface.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_p4_rhi_fallback_visibility.py` | **WILL BE OBSOLETE — H/I** | Legacy retained-base/QPainter fallback diagnostics tied to GLCompositor paint path. |
| `tests/test_p4_stage_integration.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p4_stage_marker_order.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_phase1_measurement_benchmark.py` | **WILL BE OBSOLETE — J** | Historical architecture/performance evidence; archive after J. |
| `tests/test_phase3_runtime_lifecycle.py` | **MIGRATION-CRITICAL — H/I** | Mixed: durable generation/stale-callback lifecycle plus legacy GL/overlay teardown. Split as H/I advances. |
| `tests/test_phase4_resource_containment.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_phase_e_effect_corruption.py` | **OBSOLETE NOW** | Historical QGraphicsEffect investigation; many pass/documentation bodies and trivial checks. Real focus/native-event coverage exists elsewhere. |

### 10.14 Core runtime / tooling / platform

| File | Status | Note |
| --- | --- | --- |
| `tests/test_adaptive_timer.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_animation.py` | **MIGRATION-CRITICAL — E3/F** | Generic manager may survive, but runtime QWidget/QGraphicsOpacityEffect cases are not destination presentation. |
| `tests/test_browser_window_routing.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_build_layout.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_build_runner.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_decorators.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_diagnostic_build.py` | **KEEP** | Retain diagnostic build/entrypoint/crash-capture proof; the entrypoint source gate rejects retired `DisplayWidget` patching. |
| `tests/test_event_loop_recorder.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_event_scheduler.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_events.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_flow_layout.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_fresh_start_logging.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_logging_config.py` | **KEEP — PERMANENT** | Logging bootstrap/family routing and exact rotating-handler policy; Diagnostic uses 2 MiB chunks with deliberately deeper bounded main/usage/lifecycle retention. |
| `tests/test_logging_console_encoding.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_logging_routing.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_main_run_lifetime.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_mc_context_menu.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_mc_entrypoint_contract.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_mc_keyboard_input.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_mc_window_flags.py` | **WILL BE OBSOLETE — H/I** | Old MC physical-window flag implementation; retained Quick window-role/policy tests own the destination contract. |
| `tests/test_memory_pooling.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_notification_sound_paths.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_ownership_trace.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_process_supervisor.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_qt_timer_threading.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_queued_logging.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_recovery_evidence_parser.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_runtime_callback_ownership.py` | **MIGRATION-CRITICAL — F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_runtime_destruction.py` | **MIGRATION-CRITICAL — F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_save_debounce.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_secure_url_launcher.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_storage_paths.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_thread_manager.py` | **KEEP** | Retain generic thread/timer ownership diagnostics; old compositor cadence/transition scraping and classifiers retired in H. |
| `tests/test_usage_sampler.py` | **KEEP** | Retain; no migration-specific retirement identified. |

### 10.15 Other / integration

| File | Status | Note |
| --- | --- | --- |
| `tests/test_context_menu_activation.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_double_click_navigation.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_engine_lifecycle.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_integration_full_workflow.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_line4_6_pipeline_trace.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_log_throttling.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_prewarm_no_deadlock.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_s_hotkey_workflow.py` | **KEEP — MIGRATION PERMANENT / H** | Real Quick settings-generation retirement/replacement with valid image input; no QWidget visibility assumption or retained old-generation owner. |
| `tests/test_worker_latency_tuning.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/unit/test_policy_compliance.py` | **KEEP** | Retain; no migration-specific retirement identified. |

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
