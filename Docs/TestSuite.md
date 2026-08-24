# Test Suite Guide

Last updated: 2026-08-24

Reviewed source basis:

```text
origin/main = 86872ab92a6b0960f2a3746d43dc6056cb013d47
tests/ tree = 0d93fb81fd219eb7f4c1aab4e9f2955887589e2f
```

Focused E1 Abandonment ownership and the two E1 test modules added since the prior inventory were
refreshed against `86872ab9`; unchanged classifications were not semantically recounted.

This document is both the SRPSS testing strategy and the **current test-file inventory/retirement ledger** for the Qt Quick migration.

At the reviewed checkpoint the repository contains:

- **354 test-module files**: 353 top-level `tests/test_*.py` files plus `tests/unit/test_policy_compliance.py`;
- shared test infrastructure (`conftest.py`, `_gl_test_utils.py`, `pytest.ini`, `pytest.py`, `run_chunked.py`);
- authored visualizer/audio/Steam fixtures under `tests/fixtures/`;
- visualizer replay/temporal goldens under `tests/goldens/`.

Inventory status is **not an execution result**. `KEEP` does not mean a test was run in this review, and `UPDATE REQUIRED NOW` does not by itself prove production source is wrong. Red tests must still be classified against the current contract and actual production path.

## 1. Audit method and status vocabulary

This ledger was built from the complete Git tree at the reviewed checkpoint, then classified against the current migration contracts. Architecture-sensitive groups were checked with direct source reads and repository-wide searches for legacy owners such as `QRhiWidget`, `GLCompositorWidget`, software-render fallback and `QGraphicsEffect`.

This is deliberately **not** a claim that every assertion in all 354 modules was manually read line-by-line or executed during this review. The inventory is complete; semantic inspection was concentrated where migration status could change whether a test remains authority.

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

### Inventory status counts

| Status | Files |
| --- | ---: |
| `KEEP` | 116 |
| `KEEP — MIGRATION PERMANENT` | 83 |
| `MIGRATION-CRITICAL — H/I` | 47 |
| `WILL BE OBSOLETE — H/I` | 23 |
| `MIGRATION-CRITICAL — F` | 18 |
| `MIGRATION-CRITICAL — G/H` | 16 |
| `MIGRATION-CRITICAL — G` | 12 |
| `MIGRATION-CRITICAL — E1/F` | 15 |
| `MIGRATION-CRITICAL — E1` | 1 |
| `KEEP — PERMANENT` | 5 |
| `WILL BE OBSOLETE — J` | 4 |
| `UPDATE REQUIRED NOW` | 3 |
| `WILL BE OBSOLETE — E4/F` | 3 |
| `WILL BE OBSOLETE — F0` | 3 |
| `MIGRATION-CRITICAL — E4` | 2 |
| `OBSOLETE NOW` | 2 |
| `MIGRATION-CRITICAL — E3/F` | 1 |
| **Total** | **354** |

## 2. Standard commands and evidence levels

Targeted tests are the normal per-slice gate:

```powershell
pytest path\to\test_file.py -q --tb=short
```

The bounded broad diagnostic is:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

Do not use a red broad-suite run as the only evidence that the active slice failed. Inspect the exact failure/timeout and run the smallest focused gate that can falsify the changed contract.

SRPSS does not use repository-hosted CI as the normal migration workflow. Do not add GitHub Actions or another hosted workflow unless the operator explicitly asks for it.

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

E2/E2.7 implementation is closed; E1 is the next ownership slice. Do not write “after E2 lands” tests as future work.

## 5. Active migration gates by next phase

### E1 — presentation-neutral runtime/model/provider ownership

Test the **real owner** for family provider/model lifetime, timers/polls, exclusive workers/processes, shared-service references, generation registration, deactivation teardown, reactivation, and fresh-process deactivated import/construction dormancy.

### E3/E4 — retained primitives and shadow authority

Retain semantic/style/configuration coverage while replacing QWidget-painted frame caches, `QGraphicsOpacityEffect`, `QGraphicsDropShadowEffect`, and QPainter-only shadow helpers with retained Quick equivalents. E4 must cover one global 8-direction shadow direction authority without reintroducing QWidget graphics effects.

### F — widget family ports

For each family, preserve provider/model/behavior/settings tests. Rehome direct QWidget painting/geometry/presentation assertions to retained Quick items. F0 deletes Imgur and its tests instead of porting them.

### G — CUSTOM/input/auxiliary pixels

Preserve geometry/routing/session semantics, but move shell/top-level QWidget assumptions to Quick-scene input/edit ownership. Edge resize reflows the viewport; it does not anisotropically stretch finished visualizer pixels.

### H/I — production cutover and legacy deletion

Before deleting an old presenter test, prove its **surviving contract** is covered by Quick tests. Then delete QRhiWidget/GLCompositor/software-fallback/old-overlay tests together with the source they own. Do not keep them as a compatibility layer.

### J — final validation/docs closure

Archive/remove architecture-selection spike/benchmark tests that are no longer useful product regressions after final evidence is recorded.

## 6. Immediate test-maintenance queue

| File | Status | Required action |
| --- | --- | --- |
| `tests/test_settings_sync.py` | **OBSOLETE NOW** | Delete. It is only a tombstone docstring and contains no tests. |
| `tests/test_phase_e_effect_corruption.py` | **OBSOLETE NOW** | Delete historical QGraphicsEffect investigation scaffolding; many bodies are `pass`/trivial constants. |
| `tests/test_visualizer_doc_references.py` | **UPDATE REQUIRED NOW** | Keep routing/contract checks but narrow brittle global prose-token bans, especially legitimate historical/contrast `QSGClipNode` wording. |
| `tests/test_visualizer_settings_plumbing.py` | **UPDATE REQUIRED NOW** | Split surviving settings/shader plumbing from retired pre-Quick growth/old-overlay assumptions; resolve known stale unknown-mode fallback test. |
| `tests/test_sine_line4_builder_integration.py` | **UPDATE REQUIRED NOW** | Reconcile known-red direct-builder save fixture with current descriptor/lazy save ownership; merge/delete duplicate debug-heavy coverage if `test_sine_line4_persistence.py` / `test_sine_line4_ui_simulation.py` already prove it. |

These statuses describe test maintenance. They are not permission to change production behavior merely to satisfy an old assertion.

## 7. Legacy-retirement register

High-value groups that must **not** become destination authority:

- **F0:** `test_imgur_cache.py`, `test_imgur_scraper.py`, `test_imgur_widget.py`.
- **E4/F:** QWidget painted-frame/effect implementations such as `test_base_overlay_shadow_cache.py`, `test_widget_effects.py`, `test_widget_effects_contract.py`; split `test_shadow_utils.py`.
- **H/I:** legacy renderer backend/software fallback (`test_rendering_backends.py`, `test_gl_fallback_policy.py`), GLCompositor retained-base/fallback/presenter tests, QRhiWidget P4 surface tests, old SpotifyBarsGLOverlay presentation tests.
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
| `tests/run_chunked.py` | Bounded broad-suite diagnostic wrapper. |
| `tests/__init__.py` | Package marker/support. |
| `tests/fixtures/` | Deterministic external/sample inputs. |
| `tests/goldens/` | Visualizer authored replay/temporal expected data. |

## 10. Complete test-file inventory

The inventory below accounts for every executable test file present at the reviewed tree. Status describes migration ownership, **not pass/fail state**.


### 10.1 Qt Quick runtime / transitions / visualizer

| File | Status | Note |
| --- | --- | --- |
| `tests/test_qtquick_blinds_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_bootstrap.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_build_packaging.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_burn_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_crumble_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_diffuse_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_frame_pacer.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_image_boundary.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_image_textures.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_input_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_p0_presentation_benchmark.py` | **WILL BE OBSOLETE — J** | Architecture-selection benchmark, not a forever product regression. |
| `tests/test_qtquick_particle_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_phase_c_effect_smoke.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_phase_c_registry_parity.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_presentation_spike.py` | **WILL BE OBSOLETE — J** | Architecture-selection spike, not a forever product regression. |
| `tests/test_qtquick_render_node.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_ripple_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_runtime.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_scene_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_transition_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_transition_implementations.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_transition_parameter_defaults.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_qtquick_transition_parameter_resolution.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
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

### 10.2 Visualizer

| File | Status | Note |
| --- | --- | --- |
| `tests/test_bubble_btf_coalescing.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
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
| `tests/test_sine_line4_builder_integration.py` | **UPDATE REQUIRED NOW** | Known broad-suite watch item; reconcile direct builder fixture with current descriptor/lazy save path or merge unique coverage into line4 persistence/UI tests. |
| `tests/test_sine_line4_persistence.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_sine_line4_ui_simulation.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
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
| `tests/test_visualizer_replay.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_retired_modes.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_runtime_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_visualizer_settings_plumbing.py` | **UPDATE REQUIRED NOW** | Mixed file: current settings/shader contracts plus retired pre-Quick card-growth/old-overlay assumptions; known broad-suite watch item. |
| `tests/test_visualizer_smart_positioning.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_visualizer_startup_contract.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |

### 10.3 Transitions

| File | Status | Note |
| --- | --- | --- |
| `tests/test_block_puzzle_flip.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain through cutover. |
| `tests/test_diffuse_transition.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_gl_compositor_transition_lifecycle.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_gl_compositor_transitions.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_media_transition_deferral.py` | **KEEP** | Retain; no migration-specific retirement identified. |
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
| `tests/test_clock_widget.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_custom_layout_contract.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_custom_layout_manager.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
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
| `tests/test_layout_slots.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_multi_monitor_focus.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_multidisplay_sync.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_no_legacy_widget_position_strings.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_overlay_diagnostics.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_overlay_frame_shell.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_overlay_render_dispatch.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_overlay_startup_policy.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_overlay_uniforms.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_pixel_shift.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_service_widget_runtime.py` | **MIGRATION-CRITICAL — E1/F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_shadow_tuning_paths.py` | **MIGRATION-CRITICAL — E4** | Mostly persistence/schema/profile path; likely survives E4 with direction/default updates. |
| `tests/test_shadow_utils.py` | **MIGRATION-CRITICAL — E4** | Mixed: useful tuning/fade semantics plus QPainter/QGraphicsOpacityEffect implementation. |
| `tests/test_startup_black_flash.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_weather_widget.py` | **MIGRATION-CRITICAL — E1/F** | Weather runtime-service ownership/cache/cadence/stale-result coverage is separated from the temporary QWidget presentation assertions; preserve and rehome the latter as the family ports. |
| `tests/test_widget_capability_persist_repair.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_widget_descriptors.py` | **MIGRATION-CRITICAL — E1/F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_effects.py` | **WILL BE OBSOLETE — E4/F** | Keep only until owning QWidget effect/shadow path is replaced. |
| `tests/test_widget_effects_contract.py` | **WILL BE OBSOLETE — E4/F** | Keep only until owning QWidget effect/shadow path is replaced. |
| `tests/test_widget_factories.py` | **MIGRATION-CRITICAL — E1/F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_family_catalog.py` | **MIGRATION-CRITICAL — E1/F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_lifecycle.py` | **MIGRATION-CRITICAL — E1/F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_manager.py` | **MIGRATION-CRITICAL — E1/F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_manager_refresh.py` | **MIGRATION-CRITICAL — E1/F** | Current capability admission plus production factory/service-injection seam coverage, including Reddit, Weather and Abandonment ownership/reuse validation; continue updating with later E1/F slices. |
| `tests/test_widget_performance.py` | **MIGRATION-CRITICAL — E1/F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_widget_runtime_manager.py` | **MIGRATION-CRITICAL — E1** | E1 owner regression bar (`WidgetRuntimeManager` admission, service build/inject/fail-closed/retire, deactivation dispatch, reuse validation and lifecycle routing). Extend as each E1 slice migrates real ownership. |
| `tests/test_widget_positioner.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_widget_positioning_comprehensive.py` | **MIGRATION-CRITICAL — G** | Rehome CUSTOM/input/topology geometry contract to Quick ownership. |
| `tests/test_widget_setup.py` | **MIGRATION-CRITICAL — E1/F** | Update with provider/model/runtime ownership split; preserve contract. |
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
| `tests/test_general_preset_gate_isolation.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_presets.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_regenerate_sst_defaults.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_binding.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_defaults_parity.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_dialog.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_dialog_cache.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_manager.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_no_sources_popup.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_persistence.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_profile_separation.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_schema.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_shared_styles.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_settings_sync.py` | **OBSOLETE NOW** | Tombstone only; contains no executable tests. |

### 10.6 Media / audio

| File | Status | Note |
| --- | --- | --- |
| `tests/test_audio_capture_block_size.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_media_artwork_layout.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_media_command_ingress.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_media_dependent_visibility.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_media_display_update.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_media_keys.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_media_provider_registry.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_media_provider_runtime.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_media_runtime_state.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_media_widget_runtime_methods.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_mute_button_widget.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_spotify_volume.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_spotify_volume_widget.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |

### 10.7 Gmail

| File | Status | Note |
| --- | --- | --- |
| `tests/test_gmail_assets.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_backend_bootstrap.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_backend_smoke.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_client.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_components.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_gmail_deeplinks.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_imap_actions.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_oauth.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_preparation.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_retiring_runtime.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_settings_roundtrip.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_gmail_widget.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |

### 10.8 Reddit

| File | Status | Note |
| --- | --- | --- |
| `tests/test_main_reddit_helper_preload.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_exit_logic.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_helper_recovery.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_helper_runtime.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_helper_task_harness.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_helper_watcher.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_paint_caching.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_reddit_post_provider.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_preparation.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_progressive_loading.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_reddit_provider_settings.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_rate_limiter.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_reddit_widget.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |

### 10.9 Steam

| File | Status | Note |
| --- | --- | --- |
| `tests/test_steam_abandonment_issues.py` | **MIGRATION-CRITICAL — E1/F** | Source/cadence/preparation ownership is separated from the temporary QWidget pixels; preserve behavior and rehome presenter assertions in F. |
| `tests/test_steam_abandonment_runtime.py` | **MIGRATION-CRITICAL — E1/F** | Destination-owner/generation/cardinality/repeated-setup/real-ThreadManager-timer/lifecycle bar; preserve the neutral contract and rehome only its QWidget integration edge in F. |
| `tests/test_steam_achievement_pulse.py` | **MIGRATION-CRITICAL — E1/F** | Residual cache/refresh/artwork ownership still requires E1 extraction; rehome temporary presenter assertions in F. |
| `tests/test_steam_backend.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_steam_cache.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_steam_credentials.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_steam_openid.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_steam_phase3_settings_descriptors.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_steam_phase4_mock_visuals.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_steam_profile_assets_events.py` | **MIGRATION-CRITICAL — F** | Rehome presentation assertions as family ports; preserve provider/model/behavior. |
| `tests/test_steam_request_policy.py` | **KEEP** | Retain; no migration-specific retirement identified. |

### 10.10 Imgur

| File | Status | Note |
| --- | --- | --- |
| `tests/test_imgur_cache.py` | **WILL BE OBSOLETE — F0** | Delete with Imgur removal. |
| `tests/test_imgur_scraper.py` | **WILL BE OBSOLETE — F0** | Delete with Imgur removal. |
| `tests/test_imgur_widget.py` | **WILL BE OBSOLETE — F0** | Delete with Imgur removal. |

### 10.11 Image/source/cache/providers

| File | Status | Note |
| --- | --- | --- |
| `tests/test_base_overlay_shadow_cache.py` | **WILL BE OBSOLETE — E4/F** | QWidget painted-frame shadow cache/prewarm implementation; Quick retained primitives replace this owner. |
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
| `tests/test_resource_metrics.py` | **KEEP** | Retain; no migration-specific retirement identified. |
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
| `tests/test_p2_gate7b_feedback_repaint_cost.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
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
| `tests/test_p2_pre_reveal_frame_preparation.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_pre_reveal_gl_warmup.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_ready_fade.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_single_surface.py` | **MIGRATION-CRITICAL — H/I** | Important one-surface intent, but harness imports legacy GLCompositor/SpotifyBarsGLOverlay. Quick successor must inherit intent before deletion. |
| `tests/test_p2_single_surface_gl_render.py` | **MIGRATION-CRITICAL — H/I** | Require equivalent Quick-owner coverage before deleting legacy-owner assertions. |
| `tests/test_p2_slicek_nonblocking_transport.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
| `tests/test_p2_slicel_feedback_paint_ownership.py` | **WILL BE OBSOLETE — H/I** | Delete with legacy presenter after Quick cutover/parity confirmation. |
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
| `tests/test_diagnostic_build.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_event_loop_recorder.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_event_scheduler.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_events.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_flow_layout.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_fresh_start_logging.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_logging_config.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_logging_console_encoding.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_logging_routing.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_main_run_lifetime.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_mc_context_menu.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_mc_entrypoint_contract.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_mc_keyboard_input.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_mc_window_flags.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_memory_pooling.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_notification_sound_paths.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_ownership_trace.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_process_supervisor.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_qt_timer_threading.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_queued_logging.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_recovery_evidence_parser.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_runtime_callback_ownership.py` | **MIGRATION-CRITICAL — E1/F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_runtime_destruction.py` | **MIGRATION-CRITICAL — E1/F** | Update with provider/model/runtime ownership split; preserve contract. |
| `tests/test_save_debounce.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_secure_url_launcher.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_storage_paths.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/test_thread_manager.py` | **KEEP** | Retain; no migration-specific retirement identified. |
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
| `tests/test_s_hotkey_workflow.py` | **MIGRATION-CRITICAL — G/H** | Rehome display/input/topology behavior to Quick runtime. |
| `tests/test_worker_latency_tuning.py` | **KEEP** | Retain; no migration-specific retirement identified. |
| `tests/unit/test_policy_compliance.py` | **KEEP** | Retain; no migration-specific retirement identified. |

## 11. Physical and acceptance evidence

Physical display/refresh/DPR/GPU/subjective claims remain separate from deterministic test status.

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

When a `WILL BE OBSOLETE` source owner is actually deleted, do one of three explicit things:

1. delete the test because the behavior itself was implementation-only;
2. move the surviving assertion into the named Quick/current-owner suite and then delete the old test;
3. retain the file only if it has been rewritten so completely that its name/status no longer misrepresents ownership.

Do not leave zero-test tombstones behind merely to record history; Git and historical docs already provide history.

## 14. Completion rule

Green focused tests are necessary but not sufficient.

Implementation closure and acceptance closure are distinct. An acceptance/sign-off ledger stays open until assigned gates actually run against the relevant commit/environment.

Do not turn an unchecked gate into a pass because:

- source review looks good;
- an agent says it should pass;
- another environment cannot execute it;
- later implementation has already begun.

A later failure reopens the smallest demonstrated defect.
