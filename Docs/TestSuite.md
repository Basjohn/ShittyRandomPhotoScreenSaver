# Test Suite Guide

Last updated: 2026-09-05

## Current authority

The production Qt Quick cutover and caller-proven I cleanup are complete. Current testing is post-cutover: P0 Visualizer delivery/hitch removal, mode dormancy/modularity, remaining J/Parity+ visual acceptance, theme/runtime correctness and resource/lifecycle hardening. `Current_Plan.md` owns sequence; the exact current source/test tree and the maintained `destination` profile own executable test membership.

Permanent destination guardrails include:

- native-QCursor Halo; no mouse-rate QML scene motion;
- transactional image admission + generation/token prefetch wake;
- R-63 non-exact-cover overscan with black=0 priority over harmless bounded mixed-DPR overshoot;
- event-driven Media observation on the explicit GSMTC affinity owner; no fast polling fallback;
- persistent serial `visualizer.audio_analysis` lane with retained DSP state and no generic Future fallback;
- R-68 CUSTOM Visualizer working-geometry presentation authority;
- R-69 golden Visualizer/Bubble scaling rule: viewport adaptation may not compress authored reactivity;
- ordinary CUSTOM absolute scale floor and whole-card uniform transform where applicable;
- startup desktop->wallpaper crossfade plus independent coordinated startup reveal;
- colour-only Widget Theme stable-ID linking/Custom ownership and the permanent runtime-card-material anti-resurrection contract.

This document is now a **testing guide plus preserved migration reconciliation ledger**, not a second hand-maintained inventory authority. The large section-10 tables are a dated 2026-09-01 migration-audit snapshot explaining why old tests were kept/re-homed/deleted. They may mention files that have since been removed or renamed. Do not restore an old owner or stale test merely because a historical row names it.

Current membership is determined from the exact tree and `tests/run_chunked.py` profile definitions. Whenever a current checkpoint adds/removes/re-homes a maintained test, update the current additions/contract notes in this document; do not try to keep the old migration snapshot pretending to be a live filesystem listing.

## 0. 2026-09-05 test-truth audit reconciliation

A whole-tree test-truth audit ran the collection preflight and re-collected every
error file **in isolation** to separate genuine per-file breakage from full-tree
import artifacts. Result: full-tree collection went from **3684 collected / 67
collection errors** to **3817 collected / 7 collection errors**. No production code
was changed; changes were test-only. The dated section-10 rows below were **not**
individually rewritten (they remain a historical snapshot per the caveat above);
this section is the authoritative current delta.

### Deleted — whole-file pre-cutover fossils (67)

Each imported an entirely-deleted pre-Quick subsystem and could never collect; the
surviving contracts are owned by the Quick/neutral successors in the `destination`
profile. Deleted via plain removal (reviewable in `git`).

- **GL compositor / RHI / GL infrastructure (26):** `test_adaptive_timer`,
  `test_compositor_metrics`, `test_compositor_presentation_liveness`,
  `test_compositor_gpu_queries`, `test_gl_compositor_cleanup`,
  `test_gl_compositor_overlays`, `test_gl_compositor_transition_lifecycle`,
  `test_gl_compositor_transitions`, `test_gl_fallback_policy`,
  `test_gl_shader_fallback_diagnostics`, `test_gl_stage_timestamps`,
  `test_gl_state_and_error_handling`, `test_gl_state_manager`,
  `test_gl_state_manager_overlay`, `test_gl_timer_queries`,
  `test_gpu_delivery_association`, `test_p4_rhi_compositor_surface`,
  `test_p4_rhi_fallback_visibility`, `test_p4_stage_integration`,
  `test_p4_stage_marker_order`, `test_phase4_resource_containment`,
  `test_rendering_backends`, `test_retained_base_texture`, `test_slide_jitter`,
  `test_frame_timing_workload`, `test_startup_shader_warmup`.
- **Legacy `transitions.*` GL transition implementations (7):**
  `test_block_puzzle_flip`, `test_diffuse_transition`, `test_slide_transition`,
  `test_transitions`, `test_transition_endframe`, `test_transition_state_manager`,
  `test_runtime_callback_ownership`.
- **Legacy QWidget display / input / widget hosts (26):** `test_display_setup`,
  `test_display_widget_target_size`, `test_double_click_navigation`,
  `test_fade_coordinator`, `test_multi_monitor_focus`, `test_startup_black_flash`,
  `test_widget_factories`, `test_widget_lifecycle`, `test_widget_positioner`,
  `test_widget_positioning_comprehensive`, `test_widget_runtime_owner_hoist`,
  `test_widget_visual_padding`, `test_pixel_shift`, `test_shadow_utils`,
  `test_overlay_startup_policy`, `test_mc_context_menu`, `test_mc_keyboard_input`,
  `test_media_provider_runtime`, `test_widget_setup`, `test_widget_manager_refresh`,
  `test_widget_manager`, `test_display_context_menu`, `test_display_image_ops`,
  `test_display_integration`, `test_custom_layout_manager`, `test_ghost_isolation`.
- **Spotify GL-overlay / old line pipeline (8):** `test_overlay_diagnostics`,
  `test_overlay_frame_shell`, `test_overlay_render_dispatch`, `test_overlay_uniforms`,
  `test_stencil_mask_alignment`, `test_p3_set_state_attribution`,
  `test_oscilloscope_display_contract`, `test_line4_6_pipeline_trace`.

Several deleted rows were still labelled `KEEP` / `KEEP — MIGRATION PERMANENT` in the
section-10 snapshot (e.g. `test_transition_registry` note aside, `test_layout_slots`,
`test_media_command_ingress`, `test_adaptive_timer`, `test_gpu_delivery_association`,
`test_frame_timing_workload`). Those `KEEP` labels were stale (pre-cutover) — the
files could no longer import. Do not restore them.

### Repaired — genuine value preserved (6)

- `test_widget_theme.py` — rewritten **colour-only** for the current schema-v3
  `WidgetThemeSpec`/`WidgetThemeState` API. The abandoned Glass/Acrylic
  `card_material` dimension (`CARD_MATERIAL_MODES`,
  `resolve_effective_card_material_mode`, `card_material_override`) is removed; the
  behavioural contracts (whole-or-reject `.srwtheme` I/O, catalogue discovery,
  Keep-Synced identity, Custom snapshot fallback, theme-owned-edit) are preserved.
  The source-grep no-material guard stays in `test_widget_theme_no_material_contract.py`.
- `test_steam_achievement_pulse.py` — dropped the deleted `rendering.input_handler`
  import and its two settings-section-priming tests; the neutral Steam achievement
  selection/cache/model coverage is preserved.
- `test_layout_slots.py` — dropped the deleted `rendering.display_widget` import and
  its three slot save/load tests; the `core.settings.layout_slots` snapshot contract
  is preserved. (The edit-session commit-once slot-reload semantics now live only in
  the Quick owner — see `test_quick_authored_layout_mode_contract.py`.)
- `test_widget_import_dormancy.py` — dropped the two probes importing the deleted
  legacy hosts (`rendering.widget_manager`, `rendering.display_widget`, and
  `WidgetManager.setup_all_widgets`); the live Quick-scene/Gmail dormancy oracles are
  retained. Deactivated-family dormancy is covered by `test_capability_activation` +
  `test_qtquick_family_binder`.
- `test_logging_routing.py` — dropped the one test importing the deleted
  `rendering.gl_programs.program_cache`.
- `test_f0_5_shadow_controls.py` — the retired-sidecar / retired-behaviour
  negative-control guards now skip source files the cutover deleted (a deleted file
  trivially cannot read the sidecar); full assertion strength is retained for every
  file that still exists.

### Test-infrastructure fixes

- `test_spectrum_viewport_temporal_scaling.py` — the module-level inert `core.settings`
  / `widgets.spotify_visualizer` stubs are now **saved and restored** around this
  module's own imports. Previously the fileless inert `core.settings` leaked into the
  shared `sys.modules` for the rest of the run, so every later
  `from core.settings import SettingsManager` failed with
  `cannot import name 'SettingsManager' from 'core.settings' (unknown location)`.
  This was the sole cause of the whole-tree collection breaking
  `test_widget_glow_settings`, `test_widgets_tab`, and
  `test_widget_capability_persist_repair` (all healthy in isolation and in the
  per-file-isolated `destination` profile).
- `tests/conftest.py` — `collect_ignore` emptied. Of the 16 previously-ignored
  modules, 13 were deleted above and 3 (`test_widget_import_dormancy`,
  `test_logging_routing`, `test_f0_5_shadow_controls`) were repaired and restored to
  normal collection.

### Remaining collection errors — 7 mixed files left for decision

These interleave live neutral logic with a deleted import and need per-file
rehome-or-delete judgement (not blind deletion):

- `test_context_menu_activation` — imports deleted `rendering.display_context_menu` /
  `widgets.context_menu`; the capability/Random-parity intent is covered by
  `test_capability_activation` + `test_transition_activation_admission`.
- `test_media_keys`, `test_media_command_ingress` — deleted QWidget media-key /
  native-event ingress path; current media is event-driven (`test_media_runtime`,
  `test_media_event_observation`).
- `test_media_widget_runtime_methods` — deleted `widgets.media_widget` anchor.
- `test_runtime_destruction` — high-value destruction-barrier coverage; imports
  deleted `rendering.custom_layout_manager` / `widget_manager` / `display_cleanup`
  alongside live `engine.runtime_destruction`. Recommend rehome to the current owner
  (compare `test_terminal_runtime_destruction`).
- `test_steam_phase3_settings_descriptors` — live `rendering.widget_descriptors` +
  deleted `rendering.widget_factories` / `widget_manager`.
- `test_transition_registry` — live `rendering.transition_registry` + deleted
  `rendering.transition_factory`; verify redundancy vs `test_transition_catalog_imports`
  + `test_transition_distribution`.

## 1. Evidence and status vocabulary

Architecture-sensitive failures are classified against the current owner before changing production code. Historical section-10 row labels retain their original meanings:

| Status | Meaning |
| --- | --- |
| `KEEP` / `KEEP — PERMANENT` | The reviewed contract remained useful at the audit point; verify current-tree existence before invoking it. |
| `I RECONCILIATION — <origin>` | Historical marker that a behavior might survive but the named old owner was already superseded. I is now closed; this label is provenance, not queued work. |
| `STALE I RESIDUE — <origin>` | Historical marker for deleted/superseded implementation-owner coverage. Never resurrect the retired owner. |
| `UPDATE REQUIRED NOW` | At the audit point, the test itself was known stale/brittle. Re-check the current tree before acting. |
| `OBSOLETE NOW` | Historical conclusion that the assertion had no current regression value. |

Current red tests use the normal rule: classify source defect vs stale/brittle test vs environment first, then repair the smallest demonstrated owner. A broad red never authorizes restoring retired QWidget/QRhi/GL-compositor presentation paths.

### Inventory count policy

Do not maintain hand-written aggregate module/status totals. Generate counts from the exact tree/profile only when a specific audit needs them.

## 2. Standard commands and evidence levels

Targeted tests are the normal per-slice gate:

```powershell
pytest path\to\test_file.py -q --tb=short
```

The accepted destination topology is protected by the canonical maintained profile:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

`run_chunked.py` performs one collection preflight before starting the maintained profile. Every selected maintained-profile target then runs in its own fresh pytest subprocess; `--chunks` groups reporting/logs only. This isolation is deliberate for QQuick/Qt lifecycle tests so queued teardown from one target cannot contaminate another.

`h-destination` is a historical compatibility alias if it still exists in the exact tree; new documentation and automation use `destination`. Remove an alias only after exact caller/search proof, never because an old phase name looks untidy.

A complete-tree run is a broad regression/reconciliation diagnostic:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

Treat the maintained `destination` profile as the current product-authority gate. A complete-tree red still requires classification because historical/optional/environment-gated modules may be present, but the retired Phase-I presenter owners are not production authority.

Do not use a red broad-suite run as the only evidence that a current slice failed. Inspect the exact failure and run the smallest focused gate that can falsify the changed contract. Never restore retired production seams to satisfy stale tests.

SRPSS does not use repository-hosted CI as the normal migration workflow. Do not add hosted CI unless the operator explicitly asks.

Validation levels:

- **A — pure/unit:** settings, catalogs, registries, geometry, numerical helpers, generation helpers.
- **B — component/integration:** logical mailbox/state bridge, widget family/activation, models, settings capability activation, presentation-state mapping, lifecycle ownership.
- **C — runtime-shaped:** real logical worker, Quick window creation, threaded scene graph, transition/visualizer state flow, Settings/recreate, activation consequences, stale-generation fencing.
- **D — real Windows/driver:** standalone `QQuickWindow`, threaded scene graph, real GL, multi-display/refresh/DPR, GPU/resource ownership, compiled/frozen build.
- **E — manual visual:** Bubble feel/BTF, transition visual parity, Spectrum idle visibility, Pause/Play hitch, startup/reveal, widget visual parity/shadows.

Use `Docs/Harness_Index.md` for recurring real-GL/physical/runtime harness commands.


### 2A. Post-cutover runtime reality smoke

A maintained pytest profile proves deterministic ownership contracts but does not replace Windows/driver/QML evidence. H's physical acceptance is preserved in `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md` rather than duplicated here.

Every physical Quick/J claim inspects both general diagnostic planes:

```text
screensaver.log
screensaver_qml.log
```

Source/developer runs and explicit debug/verbose runs add a synchronous native-fault companion:

```text
native_faults.log
```

For COM/SEH/native-fault acceptance that companion is mandatory evidence, not an optional console substitute. It lives in the same log directory so a complete log-directory bundle carries recoverable native faults even when the process continues running.

Post-cutover checkpoints execute the maintained `destination` profile in the normal Windows/PySide6/OpenGL environment when the changed contract requires it. A target failure is classified against current source before any production change. If a genuine accepted destination contract is falsified, reopen that smallest owner/incident; do not reopen migration phases wholesale.

For Visualizer performance/quality, deterministic tests may prove ownership but the operator remains the oracle for visible reactivity, Bubble temporal fidelity, large-viewport behavior, transition/black-flash behavior and real multi-DPR composition. R-69's no-reactivity-compression rule is binding even if a counter-oriented test appears easier to satisfy another way.

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

### 3A. H-closure maintained-profile reconciliation

The previous `79/85` H-profile result is historical only. Its six known stale assertion-bearing files were repaired against current authority rather than by restoring retired seams:

- `test_qtquick_auxiliary.py` — R6 native `QCursor`, event-cached semantic Ctrl/interaction, no scene pointer-position ownership;
- `test_qtquick_visualizer_bubble.py` — current viewport/layout signature and R-69 source guards;
- `test_qtquick_visualizer_devcurve.py` — current Quick normalization literal;
- `test_qtquick_visualizer_item.py` — current fail-closed mismatch telemetry plus R-68 CUSTOM presentation-authority rebase;
- `test_bubble_viewport_reflow.py` — current card-relative radius/collision-world contract instead of retired `_render_radius_in_world`;
- `test_s_hotkey_workflow.py` — current `_show_next_image(origin=...)` instrumentation/admission signature.

The full test pack exposed additional current-authority drift that is also repaired:

- `test_visualizer_compute_lanes.py` no longer asserts per-frame generic executor/Future ownership; it pins the persistent serial audio-analysis lane, retained detached DSP state, config invalidation and loud no-fallback failure;
- `test_visualizer_analysis_acceptance.py`, `test_p2_analysis_freshness.py` and `test_visualizer_playback_gating.py` use the persistent lane rather than fake generic Future submission;
- `test_qtquick_h9_uniform_resize.py` includes Gmail in the whole-card uniform-transform family;
- `test_qtquick_gmail_presentation.py` pins truthful asymmetric preferred-size semantics;
- `test_visualizer_viewport_scaling_contracts.py` pins the R-69 golden prohibition on second viewport compression of Bubble head/Ghost state;
- `test_spectrum_viewport_temporal_scaling.py` pins the live Quick owner and height-only temporal scaling without a second cadence; the removed legacy smoothing test is not profile membership;
- `test_runtime_perf_policy_contracts.py` pins the R-63 no-hardcoded-monitor rule while preserving the non-exact-cover principle.

`tests/run_chunked.py` now exposes canonical `destination` and includes the surviving permanent R4-R7/Media/audio/freshness targets that were missing from the old H list. The current 2026-09-02 profile contains **110 unique targets** in the canonical full repository. GOD overlay ZIPs intentionally carry only tests/docs added or modified in their work slice, so unchanged profile targets remain supplied by the destination repository. Do not publish an aggregate pass count until this exact profile runs in the user environment.

### 2026-09-02 J+ Widget-theme/resource contract additions

The maintained `destination` profile also includes the current J+ source contracts:

- `test_widget_theme_mirror_pack.py` — one explicit `.srwtheme` mirror per Settings theme and stable link metadata;
- `test_widget_theme_no_material_contract.py` — schema-v3 colour-only Widget Theme state, no Surface Style control/material persistence, direct healthy background/transition topology, ordinary RGBA card shells, and absence of the abandoned material Loader/layer/capture/mask/cadence ownership;
- `test_theme_completion_slice_contract.py` — Abandonment/BACKLOG accent-block inheritance with text-semantic contrast, split Reddit value/`AGO` alignment geometry (including the final 3 px left shift), timerless Context Menu submenu crossing corridor, and Theme Foundry reuse of the shared Settings->Widget counterpart authority;
- `test_theme_expansion_light_metal_contract.py` — the eight light/metal Settings themes and mirrors exist; dark-text light Settings surfaces are composited against a conservative native backdrop instead of tested as imaginary opaque RGB; light Widget mirrors establish a wallpaper-independent card floor with readable metadata/menu text; heading shadows/list selection remain readable; mirror stable IDs/semantic roles match their Settings counterparts;
- `test_media_winrt_affinity_and_native_fault_contract.py` — retained GSMTC subscribe/rebind/detach work executes on one non-caller affinity thread, manager dirty callbacks queue COM-touching rebinds back to that owner, a finishing owner transaction blocks overlapping observation ownership, source/developer or explicit debug mode opens `native_faults.log`, ordinary compiled non-debug release mode does not open the companion, false-positive activation is rejected, and the hang watchdog cannot retarget persistent faulthandler output;
- `test_widget_theme_link_and_asset_contract.py` — link/unlink identity persistence, lazy Settings-page coherence without polling, the mixed static-asset packaging contract (`assets.qrc`/`assets_rc.py` for embedded Settings UI resources, raw `images/` for runtime branded/widget imagery), and frozen theme deployment authority (`%ProgramData%\SRPSS\themes` + installer seed/clean-replace).

These source contracts can run without Qt. Runtime-card Glass/Acrylic was physically rejected after v3/v3.1 produced only modest card pixels while breaking wallpaper/transition presentation. The current gate therefore protects the rollback: no material-specific Quick layer/capture/effect/cadence owner may remain, while Widget Theme semantic selection/linking and ordinary card colours stay intact. Actual startup image/transition motion, retained theme application, link UI behavior and frozen-build asset availability remain physical acceptance work and must not be marked closed from source-only green.

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

F/G/H destination ownership and H post-cutover acceptance are closed. Their surviving tests are permanent regression coverage, not phase work.

### I — ACTIVE

I is caller-proven residue reconciliation. Its test responsibilities are:

1. run `destination` in the real PySide6/OpenGL environment;
2. classify any red against current owners;
3. delete/rehome tests that import deleted physical presenters, GL compositor transitions/backends, retired replay hosts or obsolete migration scaffolding;
4. preserve product-neutral/logical contracts through current Quick/neutral tests before deleting an old harness;
5. restore meaningful whole-tree collection without resurrecting deleted production modules.

Immediate manual deletions are intentionally conservative:

- `tests/test_settings_sync.py` — tombstone, no executable tests;
- `tests/test_phase_e_effect_corruption.py` — historical QGraphicsEffect corruption investigation;
- `tests/test_visualizer_preset_cycling_runtime.py` — deleted QWidget host/imports; surviving preset/Custom/audio-setting contracts are already current-owned.

The broader `STALE I RESIDUE` rows in the inventory are candidates, not an instruction to mass-delete by filename. Prove the surviving contract and caller graph first.

### Black-flash / image-surface source contract — accepted with bounded seam residual

Do not recreate old rejected `test_qtquick_black_flash_contract.py` experiments. Current deterministic/source protection lives in `tests/test_runtime_perf_policy_contracts.py` plus the real physical R-63 evidence. The accepted R-63 contract requires recurring black/stale flash = 0. A bounded mixed-DPR <=1px shared-edge overshoot is acceptable rather than risking exact-cover fullscreen promotion. Any optional J refinement must be generic device-space logic, not a hard-coded monitor/DPR correction.

### J — queued after I

Comprehensive **Parity+** visual/fidelity/installed acceptance, residual diagnostics/performance work and optional seam refinement. J may not weaken R-69 reactivity/freshness/cadence or R-63 black=0 to improve counters or visual neatness.

## 6. H-closure test-maintenance state

Changed/current permanent contracts in the closure patch:

| File | H-closure disposition |
| --- | --- |
| `tests/run_chunked.py` | Canonical `destination` profile; temporary `h-destination` alias; current permanent targets included. |
| `tests/test_qtquick_auxiliary.py` | R6 native cursor Halo + semantic auxiliary ownership; retired QML pointer-motion APIs forbidden. |
| `tests/test_visualizer_compute_lanes.py` | Persistent serial `visualizer.audio_analysis` lane, retained DSP state, config invalidation, stable previous-bars packet and loud no-Future fallback. |
| `tests/test_visualizer_analysis_acceptance.py` | Current persistent-lane analysis acceptance. |
| `tests/test_p2_analysis_freshness.py` | Newest-source freshness/cancellation semantics on the serial lane. |
| `tests/test_visualizer_playback_gating.py` | Playback admission uses current lane; no generic per-frame Future path. |
| `tests/test_qtquick_visualizer_item.py` | Current presentation mismatch fencing + R-68 active-CUSTOM presentation rebase. |
| `tests/test_visualizer_viewport_scaling_contracts.py` | R4/R5 viewport projection plus R-69 golden Bubble head/Ghost no-second-compression guard. |
| `tests/test_bubble_viewport_reflow.py` | Current card-relative radius / expanded collision-world invariant. |
| `tests/test_spectrum_viewport_temporal_scaling.py` | Current Spectrum height-only temporal scaling (wide canonical-height unchanged) without an independent cadence. |
| `tests/test_spectrum_viewport_temporal_scaling.py` | **R-76 live Quick contract:** canonical/wide exact temporal response, tall-only bar-field compensation, bounded physical jump growth, and viewport-invariant solid hysteresis domain. |
| `tests/test_qtquick_h9_uniform_resize.py` | Reddit/Reddit2/Media/Gmail whole-card transform and Visualizer isolation. |
| `tests/test_qtquick_gmail_presentation.py` | Gmail outer-width vs row-height+shell-inset baseline truth. |
| `tests/test_runtime_perf_policy_contracts.py` | R6/R7/R-63 source bars; no hard-coded current monitor geometry. |
| `tests/test_visualizer_doc_references.py` | Current live-doc owner/guardrail routing; historical negative-control wording is allowed where explicitly framed. |
| `tests/test_media_runtime.py` | Removed one stale deleted-`WidgetManager` production-setup case; current Quick binder + generation suites own that integration. |
| `tests/test_qtquick_visualizer_bubble.py` / `devcurve.py` | Current layout/shader source contracts. |
| `tests/test_s_hotkey_workflow.py` | Current image-change `origin=` signature. |

No changed test was weakened merely to produce green output. The closure environment cannot execute PySide-dependent collection, so runtime GREEN remains the I0 gate.

Generated `.pytest_cache`, `__pycache__` and `.pyc` files are not test authority and should not be copied into repository patches.

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
| `tests/run_chunked.py` | Collection-preflight chunk runner; owns the current `destination` profile and whole-tree reconciliation mode. |
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
| `tests/test_qtquick_artwork_fade_contract.py` | **KEEP — MIGRATION PERMANENT** | Mandatory event-driven/timerless dynamic-artwork fade-through contract for Media, Achievement Pulse and Abandonment Issues; future dynamic artwork surfaces must reuse the shared retained primitive or prove an equivalent no-flash fade owner. |
| `tests/test_custom_layout_session.py` | **KEEP — MIGRATION PERMANENT / G** | Neutral session/variants/working-state contract; separate visualizer scale + viewport extent is landed and remains permanent. |
| `tests/test_qtquick_custom_layout_overlay.py` | **KEEP — MIGRATION PERMANENT / G** | Retained CUSTOM overlay/drag/edge+corner resize/cross-display contract; extend only for current viewport-lifecycle corrections where applicable. |
| `tests/test_qtquick_h9_uniform_resize.py` | **KEEP — MIGRATION PERMANENT** | Whole-card uniform retained-presentation resize for Reddit/Reddit2/Media/Gmail, absolute-floor replay and Visualizer non-interference. |
| `tests/test_qtquick_auxiliary.py` | **KEEP — MIGRATION PERMANENT / RECONCILED** | Dimming/pixel-shift plus R6 native `QCursor` Halo/event-cached semantic state; retired QML pointer-motion APIs are forbidden. |
| `tests/test_qtquick_context_menu.py` | **KEEP — MIGRATION PERMANENT / G7** | Retained context-menu model/QML/action admission plus generation-owned global Card-shadow projection/high-plane composition contract. |
| `tests/test_qtquick_input_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current input contract, including generation closure and the presentation-neutral runtime-replacement pointer guard consumed by Quick. |
| `tests/test_qtquick_clock_presentation.py` | **KEEP — MIGRATION PERMANENT** | F1 retained Clock model/family/ticker/style/geometry/analogue-shadow destination contract, including shared 80%-alpha separator and cheap retained separator shadow; retain as permanent current coverage. |
| `tests/test_qtquick_weather_presentation.py` | **KEEP — MIGRATION PERMANENT** | F2 retained Weather runtime-consumer/model/state/icon/style/action/host contract; retain as permanent current coverage. |
| `tests/test_qtquick_ordinary_widget_host.py` | **KEEP — MIGRATION PERMANENT** | E3/E4 retained ordinary-widget host + shared shell primitives; root fade, cached directional card shadow, production display-level shadow underlay (all ordinary shadows below all ordinary cards), signed offsets and offset-only text shadow are destination architecture. |
| `tests/test_qtquick_widget_glow.py` / `tests/test_widget_glow_settings.py` | **KEEP — DESTINATION** | Theme inheritance/explicit override, 0-100% intensity roundtrip/projection, event-only held hover/last-click-target feedback, real child-action passthrough, settled animation dormancy, generation/transfer/retirement and Settings listener lifetime. |
| `tests/test_shadow_direction.py` | **KEEP — MIGRATION PERMANENT** | E4 canonical direction/settings/resolver/QML-boundary contract; retain as permanent current coverage. |
| `tests/test_qtquick_p0_presentation_benchmark.py` | **DELETE — I TOOLING AUDIT** | Coupled to deleted replay/P0 benchmark ownership; current Quick runtime/presentation tests own destination behavior. |
| `tests/test_qtquick_particle_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_phase_c_effect_smoke.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_phase_c_registry_parity.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_presentation_spike.py` | **WILL BE OBSOLETE — J** | Architecture-selection spike, not a forever product regression. |
| `tests/test_qtquick_render_node.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_ripple_transition.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_runtime.py` | **KEEP — DESTINATION / J PHYSICAL** | Deterministic/source-shaped runtime ownership, generation recreation and coordinated input-exit tests remain in the `destination` profile. The two tests explicitly requiring real physical displays (`test_threaded_runtime_uses_exact_identity_for_two_physical_displays` and `test_threaded_runtime_recreates_removed_and_added_physical_topology`) are J physical/topology evidence and are intentionally not part of the deterministic destination profile. |
| `tests/test_qtquick_scene_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_controller.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_implementations.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_slide_motion.py` | **KEEP — MIGRATION PERMANENT** | Frozen Slide motion-style resolution, dense cardinal ownership/endpoints, bounded Elastic settlement, lazy Settings persistence, and an offscreen real-GL anti-edge-smear probe. |
| `tests/test_qtquick_sphere_rendering.py` / `tests/test_sphere_mode_integration.py` | **KEEP — DESTINATION** | Disabled-by-default Sphere, owner/capture/source fencing, Settings persistence, true mesh/bump/material pixels, aspect/clip/depth and static upload proof. |
| `tests/test_qtquick_visualizer_mode_retirement.py` | **KEEP — DESTINATION** | Event-only inactive GL retirement, coalesced latest admission, failure retry and no empty-sync scheduling loop. |
| `tests/test_qtquick_transition_parameter_defaults.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_parameter_resolution.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_request_resolution.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | One Settings-authored transition spec per accepted image batch, fail-closed Random admission and frozen direction/parameter values. |
| `tests/test_qtquick_transition_state.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_state_fence.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_transition_uniform_wiring.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_all_modes.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_bubble.py` | **KEEP — MIGRATION PERMANENT / RECONCILED** | Destination Bubble ownership/BTF/layout coverage plus R-69 no-global-radius-compression guard. |
| `tests/test_qtquick_visualizer_clip_smoke.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_devcurve.py` | **KEEP — MIGRATION PERMANENT / RECONCILED** | Retained DevCurve presentation/normalization contract updated to current Quick shader semantics. |
| `tests/test_qtquick_visualizer_fade_authority.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_geometry.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_item.py` | **KEEP — MIGRATION PERMANENT / RECONCILED** | Retained-item admission/fencing plus R-68 CUSTOM working-geometry presentation authority. |
| `tests/test_qtquick_visualizer_oscilloscope.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_render_bridge.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_sine.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_visualizer_spectrum.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_qtquick_window.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_viewport_scaling_contracts.py` | **KEEP — R4/R5/R-69/BTF PERMANENT** | Viewport-domain projection plus golden prohibition on second viewport compression of Bubble head/Ghost reactivity. Listed in `destination`. |
| `tests/test_runtime_perf_policy_contracts.py` | **KEEP — R6/R7/R-63 PERMANENT** | Native cursor/no-scene-motion, runtime GC policy, R7 image/prefetch and generic no-hardcoded-monitor R-63 geometry source bars. Listed in `destination`. |

| `tests/test_qtquick_ctrl_coordinator.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | One authoritative cross-display Ctrl truth and retired-contribution cleanup. |
| `tests/test_qtquick_display_image_route.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | GUI pixmap -> immutable Quick presentation-image routing, detached image-accounting aggregation and target-size contract. |
| `tests/test_qtquick_display_presenter.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Thin per-display destination presenter; no provider/window/persistence authority. |
| `tests/test_widget_stacking_display_plan.py` | **KEEP — DESTINATION / MIGRATION PERMANENT / ORDINARY LAYOUT** | Pure display-wide authored stacking stress cases, canonical-slot spill, fixed Media+Visualizer obstacles, and explicit overfull reporting. CUSTOM is intentionally absent from the planner API. |
| `tests/test_quick_authored_layout_mode_contract.py` | **KEEP — DESTINATION / MIGRATION PERMANENT / GLOBAL CUSTOM BOUNDARY** | Source guardrails proving all three CUSTOM entry paths converge on one authored-layout switch: persisted/effective Custom at construction, live Edit Layout before capture, and number-key layout-slot reload; also protects Visualizer plain-anchor fallback and adjacency dormancy. |
| `tests/test_media_external_volume_contract.py` | **KEEP — DESTINATION / MIGRATION PERMANENT / MEDIA PRESENTATION** | External volume-rail geometry plus whole-Media/Visualizer event-wheel ownership; source bars require explicit CUSTOM edit-session gating so resize wheel remains sole owner. |
| `tests/test_qtquick_display_unit.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Per-display Quick destination-chain assembly and semantic display operations. |
| `tests/test_qtquick_family_binder.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Single-manager family admission/runtime service ownership, canonical per-instance monitor routing across logical displays, and retained host binding. |
| `tests/test_qtquick_family_size_policy.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Historical deterministic family preferred-size policies under Option-A geometry. |
| `tests/test_qtquick_geometry_resolver.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Python outer-rect/anchor/clamp authority; no QML outer-position feedback loop. |
| `tests/test_qtquick_h_cutover.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | H authority-cutover/cardinality/deletion bars, including one canonical manager-admitted visualizer owner, retained menu/double-click mode actions, H8 middle-click same-mode preset transaction, overlap rejection, delayed narrow persistence, hidden-boundary hard join, fresh-target reveal and engine-retirement lifecycle. |
| `tests/test_qtquick_overlay_preferred_size.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Size-only preferred-content signal contract used by Python geometry ownership, including terminal disconnection before retained-item retirement. |
| `tests/test_qtquick_visualizer_admission.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Exactly one admitted Quick visualizer display owner with requested/hold/fallback policy. |
| `tests/test_qtquick_visualizer_all_five_owner_chain.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Owner-shaped all-five widget-free destination chain. |
| `tests/test_qtquick_visualizer_double_click.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Retained visualizer mode-cycle semantic admission before global next-image fallback. |
| `tests/test_qtquick_visualizer_middle_click.py` | **KEEP — MIGRATION PERMANENT / H8** | Actual Quick-window middle-button preemption plus active/inside retained Visualizer preset-cycle admission with no neutral-input side effect. |
| `tests/test_qtquick_visualizer_logical_ownership.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Controller-owned authored logical state/runtime ownership without QWidget host. |
| `tests/test_qtquick_visualizer_owner_edge.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Thin display/generation visualizer ownership edge, single shared-engine acquire/release, hard retirement, and terminal callback release semantics. |
| `tests/test_qtquick_visualizer_pre_cutover_audit.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Standing source/behavior regression bars from the H pre-cutover audit. |
| `tests/test_qtquick_visualizer_reactivity_config_parity.py` | **KEEP — MIGRATION PERMANENT / DESTINATION** | Canonical Spectrum topology translation, shared BeatEngine shaping while another mode is active, exact Quick `0.55` transfer, Bubble live controls and technical zero/false semantics; maintained `destination` profile. |
| `tests/test_qtquick_visualizer_true_f_gate.py` | **KEEP — MIGRATION PERMANENT / H-ORIGIN** | Strong True-F technical-engine/logical/bar-count + exact retained-item consumption gate. |

### 10.2 Visualizer

| File | Status | Note |
| --- | --- | --- |
| `tests/test_bubble_btf_coalescing.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_bubble_viewport_config_route.py` | **KEEP — MIGRATION PERMANENT / G4** | Live/coalesced viewport configuration route into each authored Bubble step; extend for committed-vs-CUSTOM override lifecycle. |
| `tests/test_bubble_viewport_reflow.py` | **KEEP — G4/BTF PERMANENT / RECONCILED** | Current card-relative radius and expanded collision/spawn-world projection; no retired radius helper. |
| `tests/test_bubble_aspect_pixels.py` | **KEEP — DESTINATION / BTF** | Real GL head diameter/delta versus occupancy across width/height, uniform scale and fit; local specular pixel invariance across width. |
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
| `tests/test_spectrum_presentation_smoothing.py` | **REMOVED — STALE PLUMBING** | Deleted by `a3e4ec17`; stale destination-profile membership removed. Live temporal-scale proof is `test_spectrum_viewport_temporal_scaling.py`. |
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
| `tests/test_visualizer_doc_references.py` | **KEEP — RECONCILED / PERMANENT** | Current docs are checked for owner/guardrail facts rather than obsolete exact phrases or global bans on legitimate historical negative-control wording. |
| `tests/test_visualizer_failover_reclaim.py` | **KEEP — MIGRATION PERMANENT** | E2.7 canonical global-singleton/grace/reclaim/capability lifecycle suite. Must remain authoritative until successor owner inherits it. |
| `tests/test_visualizer_feature_frame.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_mode_isolation.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_modes.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_overlay_kwargs.py` | **I RECONCILIATION — OLD PHYSICAL OWNER** | Require equivalent Quick-owner coverage before deleting/re-homing stale legacy-owner assertions in I. |
| `tests/test_visualizer_playback_gating.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_presentation_contract.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_presentation_negative_controls.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_preset_cycling_runtime.py` | **STALE I RESIDUE — DO NOT RESTORE DELETED HOSTS** | Imports retired QWidget `InputHandler`/`WidgetManager`/visualizer host and cannot collect. The input handler covered mouse-button routing, not audio. Current destination resolver/Custom tests and Quick reactivity/True-F gates own the surviving preset and mode-owned `input_gain` contracts. |
| `tests/test_visualizer_preset_manifest.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_preset_transfer.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_presets.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_reactivity_quality.py` | **KEEP — MIGRATION PERMANENT** | Destination/current contract; retain as permanent current coverage. |
| `tests/test_visualizer_replay.py` | **DELETE — I TOOLING AUDIT** | Imports deleted replay host. Preserve fixture/golden data and current temporal/BTF/viewport tests, not executable legacy replay authority. |
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
| `tests/test_transition_perf_health_parser.py` | **DELETE — I TOOLING AUDIT** | Tests an overgrown generic historical parser that duplicates current instrumentation and carries retired GL/QWidget assumptions. |
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
| `tests/test_media_runtime.py` | **KEEP — PERMANENT / EVENT-DRIVEN / RECONCILED** | Shared Media owner/lease/controller/state/artwork/generation plus native-event coalescing, command convergence, slow reconcile watchdog, degraded/missed-event telemetry and stale-generation fencing. The stale deleted-`WidgetManager` production-setup test was removed because current Quick binder + generation recreation suites own that integration; the retired 1–2.5s active poll is not authority. |
| `tests/test_media_event_observation.py` | **KEEP — PERMANENT / EVENT-DRIVEN** | Controller-level GSMTC subscription/token/session-replacement contract; native callbacks remain tiny and generation-fenced, with real-WinRT round-trip environment-gated. |
| `tests/test_media_winrt_affinity_and_native_fault_contract.py` | **KEEP — PERMANENT / WINRT OWNERSHIP + LOGGING** | Proves retained manager/session subscriptions and manager-change rebinds share one affinity OS thread, plus debug native-fault companion ownership and hang-watchdog non-interference. Listed in `destination`. |
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
| `tests/test_qtquick_gmail_presentation.py` | **KEEP — MIGRATION PERMANENT** | Retained Gmail config/style, stable accepted-state row projection, static QML popup/height/visual fidelity, real manager-owned runtime/host state and action routing, and no-recreation lifecycle coverage. Includes the context-menu click-through guard (`request_open` refuses a browser-open while the shared pointer guard is armed) and the Reusable-Headers QML contract (header-aware `Math.max` width, `BrandedHeader`-owned logo desaturation and border wiring). |
| `tests/test_gmail_retiring_runtime.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_gmail_settings_roundtrip.py` | **KEEP** | Retain; no current retirement identified. |

### 10.8 Reddit

| File | Status | Note |
| --- | --- | --- |
| `tests/test_main_reddit_helper_preload.py` | **KEEP** | Retain; no current retirement identified. |
| `tests/test_qtquick_reddit_presentation.py` | **KEEP — MIGRATION PERMANENT** | Retained Reddit/Reddit2 config/style/row/state/action and no-recreation destination coverage. |
| `tests/test_reddit_exit_logic.py` | **KEEP — FOCUSED DESTINATION NODE** | Quick-era Reddit URL queue/flush logic plus the context-menu click-through regression bar (`TestContextMenuClickThroughSuppression`: a retained-menu action arms the shared pointer guard so a same-gesture phantom Reddit open is refused). Stale pre-Quick `DisplayWidget`/`cleanup`-deferral tests (removed `rendering.display_widget` module and removed `_pending_reddit_url`-at-cleanup mechanism) were removed; successor coverage lives in `TestCleanQueueFlow`. |
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
| `tests/test_worker_push_presentation_benchmark.py` | **DELETE — I TOOLING AUDIT** | Imports deleted physical Visualizer/presenter owners; no current destination contract requires the executable benchmark. |

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
| `tests/test_phase1_measurement_benchmark.py` | **DELETE — I TOOLING AUDIT** | Historical measurement experiment superseded by built-in PERF/usage instrumentation and passive external resource sampling. |
| `tests/test_phase3_runtime_lifecycle.py` | **DELETE — I TOOLING AUDIT** | Imports `tools.phase3_lifecycle_harness`; historical lifecycle evidence is already preserved and current runtime teardown/recreation tests own destination behavior. |
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
| `tests/test_main_run_lifetime.py` | **KEEP — PERMANENT** | Production shutdown ordering; R-72 requires telemetry flush/close without importing operator analysis tools. |
| `tests/test_tooling_ownership.py` | **KEEP — PERMANENT** | Production/tool boundary, canonical test-runner delegation, passive attached-PID sampling and current ImageWorker SHM harness ownership. |
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
| `tests/test_recovery_evidence_parser.py` | **DELETE — I TOOLING AUDIT** | Coupled to broken self-importing historical recovery parser; phase reports preserve the old evidence. |
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
| `tests/test_s_hotkey_workflow.py` | **KEEP — MIGRATION PERMANENT / RECONCILED** | Settings-generation retirement/replacement plus current image-change `origin=` telemetry/admission signature. |
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

### 2026-09-01 destination additions — Clock/shadow/Bubble/startup/CUSTOM

- `tests/test_shadow_direction.py` — permanent canonical direction + card-frame directional Extra Offset growth contract.
- `tests/test_bubble_lifecycle_fades.py` — permanent alpha-only runtime birth/pop fade contract; explicitly protects R-69 by asserting no viewport/domain authority is introduced.
- `tests/test_qtquick_clock_presentation.py` — current mode-neutral Clock separator + thickness + legacy-read compatibility and analogue spacing contract.
- `tests/test_qtquick_ordinary_widget_host.py` — shared retained card shadow grows selected far edges rather than translating the whole shadow; the independent startup gate cannot be bypassed by a family-authored fade.
- `tests/test_qtquick_startup_reveal.py` — cold-session-only desktop staging source -> fixed first Crossfade -> coordinated widget gate sequencing; replacement runtimes skip desktop recapture; startup staging adds no recurring timer/poller.
- `tests/test_qtquick_visualizer_fade_authority.py` — Visualizer authored `scene_fade` remains its single real fade authority while the generation startup gate multiplies root opacity independently.
- `tests/test_qtquick_custom_layout_owner.py` — uniform-transform edit admission canonicalizes a stale aspect-mismatched outer rectangle to the actual visible retained-card envelope, preventing dead letterbox geometry from becoming resize authority.

The new permanent files are included in the canonical `destination` profile. Physical J validation still owns subjective shadow coverage, analogue spacing, Bubble fade feel, Reddit edit-frame fit and the desktop/startup reveal.


### 2026-09-02 Settings-theme lifetime + bidirectional link regression

The Widget Theme catalogue/link checkpoint adds two permanent lifetime guards to the canonical `destination` profile. `tests/test_settings_theme_lifetime_contract.py` is Qt-free and verifies transaction semantics with a simulated wrapper lifetime. `tests/test_settings_theme_qobject_lifetime.py` runs only in the normal PySide6 environment and deletes a real QWidget before refreshing the root-QSS registry, proving the actual Shiboken edge that produced `Internal C++ object (SettingsDialog) already deleted`.

`tests/test_widget_theme_no_material_contract.py` and the link/asset contract protect the linked-theme UX shape: the same compact themed lock control exists on both theme pages, Widget->Settings selection uses explicit reverse link metadata, and locked catalogue selection preserves `keep_synced=True` instead of silently converting to Independent. These source contracts do **not** replace the required user-environment test: physically recreate Settings, switch themes repeatedly, verify bidirectional list movement/persistence from both pages, and confirm no deleted-C++-object warning appears.

The maintained destination profile includes `test_visualizer_line_coverage.py` for real-GL
Sine/Osc/DevCurve device-pixel coverage at DPR 1.5 and extreme extent/small authored scale.
`test_bubble_aspect_pixels.py` owns equal-area response/highlight and visible-size outline oracles;
`test_qtquick_visualizer_spectrum.py` includes curated Organs black-fill/rainbow/glow pixels.


### 2026-09-05 Checkpoint 2 — Sphere/material + slot-mode + discrete-hop contracts

This checkpoint changes current-owner tests only; it does not resurrect deleted QWidget/native-event/media owners. The
packaged ChatGPT-session test slice contains the four Checkpoint 1 Bubble/glow contracts plus these five Checkpoint 2 files.

- `tests/test_layout_slots.py` — geometry slots persist/restore the active `spotify_visualizer.mode` while deliberately
  excluding per-mode tuning/preset values. Slot load remains the fenced reconstruction boundary.
- `tests/test_sphere_mode_integration.py` — 4.5 Deformation and 3.0 Size Response clamps/UI/persistence, +0.90 logical
  size-pulse behavior, and persisted local-AA/cast-shadow controls.
- `tests/test_qtquick_sphere_rendering.py` — shared body/effect surface anchors, attached bulge/neck/pinch-off source contract,
  real Magma macro-fissure radial displacement, local AA, analytical shadow resource ownership, and extended negative-tail
  radius safety without shrinking the accepted canonical Sphere. Real GL cells remain required.
- `tests/test_qtquick_visualizer_reactivity_config_parity.py` — current immutable/config parity remains part of the Sphere
  settings seam touched by this checkpoint.
- `tests/test_qtquick_custom_layout_owner.py` — the deterministic discrete display-hop oracle now protects the floating
  geometric-centre projection that removes the pre-existing even-sized `QRect.center()` 1px drift. Pointer drag transfer is
  intentionally a separate path.

Container validation for this checkpoint is source/static only: Python AST/compile and authored JSON are clean, and Sphere
shader literals/contracts are structurally checked. This environment has no `PySide6`, so pytest collection of the focused
Qt-bearing group stops at import and is **AWAITING PySide6/OpenGL VALIDATION**, not a test failure. In the target environment
run the five files above (at minimum the named discrete-hop cell) and physically inspect attached Water/Magma liquid, Magma
fissure depth, AA, lighting-derived shadow, extreme Sphere controls and layout-slot mode restoration.
