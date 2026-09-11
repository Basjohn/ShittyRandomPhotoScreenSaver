# Test Suite Guide

Last updated: 2026-09-11

## Current authority

The exact current source tree and the maintained `destination` profile in `tests/run_chunked.py` own executable test truth. `Current_Plan.md` owns execution order. Historical bug records and old migration reports are evidence, not permission to keep tests for retired owners alive indefinitely.

The current product is post-Qt-Quick cutover. The five established visualizer modes remain permanent shared modes; Voxel Sphere is an **accepted experimental, architecturally isolated** sixth mode. Tests must preserve that distinction rather than forcing Sphere into permanent-mode assumptions or treating experimental isolation as exemption from shared persistence/normalization contracts.

This file is a maintained routing/status guide. It deliberately does **not** carry a giant hand-maintained inventory of every `test_*.py` file. That became stale faster than the code and obscured obsolete tests. Source discovery plus the maintained profile are the inventory authorities.

---

## 0. 2026-09-11 test-truth / normalization audit

Audit baseline: `GODZIP_AchievementPulse_ProgressPulse_ThemeAccentFix_2026-09-11.zip`.

### 0.1 Achievement Pulse normalization verdict

The new `Progress Pulse` and `Shelf Style` presentation options use the existing widget settings/normalization system rather than a second widget-size or state authority:

- canonical defaults own `widgets.achievement_pulse.progress_pulse = true` and `shelf_style = false`;
- generated defaults snapshot and both SST defaults remain derived from canonical defaults;
- the Steam Settings builder loads/saves the same canonical keys;
- the retained Quick Achievement Pulse presentation config consumes those keys;
- `Progress Pulse` presents the existing Total/percentage truth rather than creating another progress calculation;
- the authored Achievement Pulse canvas/natural-size contract remains the same outer normalization authority;
- percentage text uses fitted presentation inside the pulse and does not resize the widget baseline when the string becomes `100%`.

**Real defect found and corrected during this audit:** the two new Settings controls were initially missing from the Steam section descriptor's `signal_block_attrs`. Lazy Settings hydration could therefore programmatically alter them without the same signal-block protection as peer Steam controls. Both attributes are now part of the canonical hydration block list, and `test_defaults_schema_authority.py` plus `test_steam_phase3_settings_descriptors.py` guard that contract.

That was a Settings-hydration normalization/lifecycle hole, not a runtime geometry-normalization rewrite. The Qt resize-normalization oracle still requires a Windows/PySide run before the new Achievement Pulse state can be called physically validated.

### 0.2 Headless validation completed here

The following current suites run without PySide/OpenGL/feedparser in this Linux environment and passed after reconciliation:

```text
131 passed
  tests/test_defaults_schema_authority.py
  tests/test_about_art_theme.py
  tests/test_visualizer_doc_references.py
  tests/test_sphere_voxel_audio_contract.py
  tests/test_visualizer_settings_body_transaction_contract.py
  tests/test_visualizer_user_authored_preset_catalog.py
  tests/test_visualizer_technical_profile_contract.py
  tests/test_sphere_voxel_geometry.py

13 passed
  tests/test_p4_native_presentation.py   # retained DWM-only portion

4 passed
  tests/test_spotify_volume.py

TOTAL DIRECTLY EXECUTED HERE: 148 passed
```

Also passed:

```powershell
python -m core.settings.defaults_snapshot_builder --check-all
```

Result:

```text
defaults snapshot OK
SST defaults documents OK
```

### 0.3 Environment-limited collection

A full-tree collection attempt after stale-test cleanup produced:

```text
1218 tests collected
206 files errored during collection
```

The errors are environment dependencies in this container, dominated by:

```text
PySide6    196 missing-module signatures
OpenGL       9 missing-module signatures
feedparser   2 missing-module signatures
```

Do **not** call those product reds. Equally, do not call the affected tests green. They require the intended Windows/PySide/OpenGL environment.

### 0.4 Maintained destination profile

After this audit:

```text
130 unique destination targets
0 missing target files
```

The destination profile remains target-isolated: each profile target runs in its own fresh pytest process so queued QQuick/QObject teardown cannot contaminate unrelated files.

---

## 1. Status vocabulary

Use these labels consistently:

- **PASS** — executed against the stated current tree/environment and passed.
- **NEEDS RUN VALIDATION** — current/recent coverage judged valuable and structurally reconciled, but it could not execute in this environment. Run it on the intended Windows/PySide/OpenGL environment before using it as acceptance evidence.
- **ENVIRONMENT BLOCKED** — collection/execution cannot begin because a required external runtime package/platform is missing. This is not a product failure.
- **OBSOLETE** — test targets a retired owner/architecture and no longer expresses a current contract. Delete it or preserve the lesson in Historical Bugs; do not keep it red forever.
- **REHOME** — only part of a mixed legacy test still has current value. Move that assertion into the current owner/suite and retire the dead integration shell.
- **RED** — current test executed in an appropriate environment and failed a current contract.

A green static/source test is not a substitute for a required Qt/QML/real-GL/installed gate.

---

## 2. Standard commands and evidence levels

### 2.1 Fast maintained product gate

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

This is the canonical maintained profile. The old `h-destination` spelling is compatibility only.

### 2.2 Broad reconciliation diagnostic

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

A complete-tree run is useful for discovering stale tests, optional dependency gaps and hidden regressions. It is not permission to resurrect a retired production owner merely to make an old test green.

### 2.3 Defaults authority

```powershell
python -m core.settings.defaults_snapshot_builder --check-all
```

Required whenever canonical defaults, generated snapshots/SSTs, Settings normalization or Defaults Foundry-facing keys change.

### 2.4 Evidence levels

Use the minimum relevant combination:

1. **Static/schema contract** — ownership, source wiring, canonical defaults, descriptor membership, manifest/reference integrity.
2. **Deterministic behavioural test** — equations, normalization, response, persistence, migration, lifecycle state.
3. **Qt/QML runtime-shaped test** — actual objects/signals/bindings/layout, teardown, retained presentation.
4. **Real GL/platform test** — shader/resource/context/driver behavior where fakes are insufficient.
5. **Installed physical review** — final visual/timing/interaction acceptance on the real machine.

Do not collapse levels 3–5 into “unit tests passed.”

---

## 3. Stale-test rule

When a test fails because an import/owner no longer exists:

1. establish whether the production owner was deliberately retired;
2. identify the behavioural contract the old test was trying to protect;
3. if that contract still exists, rehome it onto the current owner/path;
4. if the contract itself retired, delete the test;
5. preserve important failure lessons in Historical Bugs rather than maintaining fake compatibility architecture.

Do not:

- create forwarding modules solely for tests;
- restore QWidget/old compositor presenters to satisfy stale imports;
- keep whole-file skips as permanent tombstones;
- weaken a current assertion merely because an old test encoded obsolete topology;
- assume an old phase name means the behaviour is obsolete; inspect the actual assertion first.

---

## 4. Obsolete/rehome decisions made in this audit

### 4.1 Whole-file fossils removed

The following 11 files targeted retired owners or were tombstones whose surviving lessons are covered elsewhere:

```text
test_dimming_and_interaction_fixes.py
test_flicker_fix_integration.py
test_gl_profiler.py
test_gl_texture_streaming.py
test_integration_full_workflow.py
test_mc_window_flags.py
test_prewarm_no_deadlock.py
test_qtquick_sphere_rendering.py
test_settings_schema.py
test_widget_effects.py
test_widget_performance.py
```

Important classifications:

- `test_qtquick_sphere_rendering.py` described the retired smooth/material Sphere architecture and imported the nonexistent old Sphere renderer. Current Voxel Sphere authority is covered by the Voxel Sphere audio/geometry/mode-integration/current renderer suites; do not resurrect the old smooth Sphere to satisfy this file.
- `test_prewarm_no_deadlock.py` and `test_settings_schema.py` were module-level skip tombstones for deleted owners.
- old QWidget widget-effect/performance and pre-Quick display/compositor integration tests no longer own destination pixels.

### 4.2 Mixed files repaired instead of deleted

`tests/test_p4_native_presentation.py`

- retained: current non-blocking `rendering.dwm_timing` structure/association behavior;
- removed: retired `rendering.gl_compositor_pkg` present-context and perf-HUD probes;
- current headless result: **13 PASS**.

`tests/test_media_volume_runtime.py`

- retained: shared volume-owner leases, provider retargeting, generation fencing, optimistic/debounced writes;
- removed: old `MediaWidget` + deleted `WidgetManager` anchor integration cells;
- current Quick service injection is covered by current runtime-service/family-binder/media-presentation suites;
- **NEEDS RUN VALIDATION** after this rehome because `ThreadManager` imports PySide6 in this environment.

`tests/test_system_mute_runtime.py`

- retained: shared owner/backend semantics, generation fencing, coalescing and UI-owner-thread behavior;
- removed: old `MediaWidget` + deleted `WidgetManager` anchor integration cells;
- current Quick injection is covered by current service/family-binder/media-presentation suites;
- **NEEDS RUN VALIDATION** after this rehome because `ThreadManager` imports PySide6 here.

`tests/test_qtquick_crumble_transition.py`

- received the useful Crumble shader assertions formerly embedded in the deleted mixed dimming/interaction file;
- **NEEDS RUN VALIDATION** because the retained transition package imports PySide6 here.

### 4.3 Stale assertions corrected in maintained tests

The audit also repaired assertions that still encoded superseded contracts:

- old Sphere Rainbow setting names -> current Sphere-local Taste The Rainbow keys;
- hard-coded Sphere preset count/contiguous-slot assumptions -> user-authored arbitrary/sparse preset contract;
- old technical-cache direct indexing -> current resolver call shape;
- stale Custom-cache normalization expectations -> current import/replace/merge semantics;
- accepted Sphere A/B tests no longer claim those two files are the only legal user presets.

These are test-truth corrections, not permission to change the production contracts they protect.

---

## 5. Recent work validation matrix — 2026-09-09 through 2026-09-11

### PASS in this environment

- `test_defaults_schema_authority.py` — canonical defaults, generated-authority/static routes, recent Achievement Pulse hydration contract.
- `test_about_art_theme.py` — About liquid masks/theme semantic behavior.
- `test_visualizer_doc_references.py` — current visualizer documentation paths/contracts.
- `test_sphere_voxel_audio_contract.py` — accepted-experimental Sphere audio/particle/settings contract.
- `test_sphere_voxel_geometry.py` — current Voxel Sphere geometry contract.
- `test_visualizer_settings_body_transaction_contract.py` — lazy body build/hydration all-or-nothing contract.
- `test_visualizer_user_authored_preset_catalog.py` — arbitrary/sparse user preset catalogue semantics.
- `test_visualizer_technical_profile_contract.py` — technical-profile/isolation contract.
- `test_p4_native_presentation.py` — retained DWM timing utility only.
- `test_spotify_volume.py` — exact Spotify/browser volume-session matching.
- `test_settings_bucket_single_open_contract.py` — 13/13 direct Qt-free assertions passed: all-closed canonical baseline, sparse structured-root merge (including Visualizer Technical leaves), legacy normalization, local-scope replacement, Spectrum accessory bucket schema, synchronous no-timer peer closure, deferred-body finalization ownership, explicit Setup/About/Accessibility exclusions, and parent-disclosure reachability. Normal pytest collection is still globally blocked here by missing PySide6 in `tests/conftest.py`.
- `test_devcurve_shader_contract_current.py` and `test_retired_runtime_islands_contract.py` are new Qt-free/static replacements for retired-owner assertions; source compilation passed, with normal pytest collection subject to the same global PySide6 blocker.
- Bucket reachability audit rehomed three mixed tests whose surviving coverage was current but whose bucket expectations were obsolete: `test_widgets_tab.py` -> `test_widgets_tab_current.py`, `test_widgets_tab_general.py` -> `test_widgets_tab_general_current.py`, and `test_visualizer_settings_lazy_bodies.py` -> `test_visualizer_settings_lazy_bodies_current.py`. The old modules are debris; production code is not weakened to retain multi-open/default-open/legacy Technical assertions.

### NEEDS RUN VALIDATION

The following are current/recent and could not collect here because PySide6 is unavailable:

- `test_qtquick_achievement_pulse_presentation.py`
  - Progress Pulse layout;
  - numeric-change-only pulse signal;
  - fitted percentage text including wider values such as `100%`;
  - Shelf Style/presentation behavior;
  - QML/runtime lifecycle.
- `test_qtquick_resize_normalization.py`
  - Achievement Pulse/Abandonment/Weather stale-payload replay;
  - repeated reconstruction;
  - CUSTOM Save/Cancel/slot replay without baseline compounding.
- `test_steam_phase3_settings_descriptors.py`
  - Steam section hydration/saver/descriptor integration;
  - now explicitly checks the two Achievement Pulse signal-block attributes.
- `test_theme_foundry_model.py`
  - Settings theme schema-v6/About liquid semantic through Theme Foundry model.
- `test_default_settings_editor.py`
  - Defaults Foundry/editor Qt interaction and canonical schema behavior.
- `test_qtquick_crumble_transition.py`
  - includes newly rehomed current shader/fall/shadow assertions.
- `test_media_volume_runtime.py`
  - retained shared service behavior after obsolete QWidget anchor cells were removed.
- `test_system_mute_runtime.py`
  - retained shared service behavior after obsolete QWidget anchor cells were removed.
- `test_spectrum_shaping_current.py` and `test_transient_per_mode_current.py`
  - live Spectrum/transient assertions rehomed away from the retired pre-Quick renderer island;
  - Sine scheduler assist now targets presentation-neutral `sine_reactivity`; Spectrum layout now targets the retained Quick implementation.
- `test_async_image_processor_current.py`
  - current QImage-first FILL/FIT/SHRINK/Lanczos/null-image mechanics after retirement of synchronous `ImageProcessor`;
  - requires the intended PySide environment.
- `test_widgets_tab_current.py`, `test_widgets_tab_general_current.py`, and `test_visualizer_settings_lazy_bodies_current.py`
  - current replacements for mixed modules whose surviving assertions were useful but whose bucket expectations were obsolete;
  - require the intended PySide environment for actual Widget/Visualizer construction and reload behavior.
- Settings bucket physical interaction
  - Spectrum Custom Bar Appearance/Rainbow must render as normal collapsible buckets;
  - opening a peer must close the prior bucket without flash/artifacting;
  - lazy page/mode changes must restore only the remembered local open bucket and never collapse a required parent card;
  - Visualizer Technical must keep its outer parent open while AGC/Transient behave as one-open per-mode child buckets;
  - Advanced must likewise remain an independent parent while an Advanced child bucket is open;
  - Spectrum Bar Appearance/Rainbow must remain reachable after mode switches/body retirement/reconstruction.

Do not change these entries to PASS until they have actually run on the intended environment.

---

## 6. Permanent architecture gates

### 6.1 Qt Quick presentation

Protect:

- one retained accelerated `QQuickWindow` per admitted display;
- no `QQuickWidget`/second accelerated widget surface/fallback presenter;
- current family binders and retained models;
- generation/activation fencing;
- resource destruction on legal owners;
- QML emits semantic actions rather than owning provider/business side effects;
- ordinary family presentation remains normalized from authored size + one resolved runtime geometry authority.

High-value suites include `test_qtquick_runtime.py`, `test_qtquick_window.py`, `test_qtquick_scene_controller.py`, `test_qtquick_family_binder*.py`, `test_qtquick_ordinary_widget_host.py`, lifecycle/terminal-destruction suites and family-specific Quick presentation tests.

### 6.2 Widget normalization / CUSTOM

Normalization changes require tests that distinguish:

```text
authored/natural size
resolved runtime size
uniform scale
CUSTOM working geometry
committed geometry
serialized stale payload
```

Required properties:

- stale stored dimensions normalize once, not repeatedly;
- reconstruction does not compound scaling;
- Save commits exactly the working geometry;
- Cancel restores pre-edit committed geometry;
- slot replay does not mutate authored baseline;
- dynamic content changes do not redefine natural size unless the product contract explicitly says they do;
- fitted text is presentation behavior inside the resolved geometry, not another widget-scale authority.

Primary suites: `test_qtquick_resize_normalization.py`, `test_widget_auto_shrink.py`, `test_qtquick_family_size_policy.py`, `test_qtquick_geometry_resolver.py`, `test_qtquick_custom_layout_owner.py`, `test_qtquick_custom_layout_overlay.py`, capture/geometry tests.

### 6.3 Settings/defaults/theme authority

Protect:

- `core/settings/default_settings.py` as defaults SSOT;
- generated snapshot/SST parity;
- no second fallback default authority;
- lazy Settings hydration blocks programmatic control changes from masquerading as user edits;
- descriptor/load/save/default keys remain mutually complete;
- schema migrations normalize legacy input once and remove retired aliases;
- Theme Foundry and Defaults Foundry consume canonical schema rather than inventing parallel fields.
- collapsible bucket persistence remains sparse and page/local-scope accordion behavior stays centralized; canonical defaults enumerate identities but `SettingsManager` must not materialize absent false members.

Primary suites include `test_defaults_schema_authority.py`, settings manager/persistence/binding/default parity, descriptor suites, Theme Foundry and default-settings-editor tests.

### 6.4 Visualizers

Read `Docs/Guides/Visualizer_Change_Checklist.md`, `Docs/Guardrails/Visualizer_Presentation.md`, `Docs/Guardrails/Bubble_Temporal_Fidelity.md`, and `Docs/Guides/Visualizer_Reactivity_Authoring.md` as relevant.

Permanent shared-mode work must protect Bubble/BTF, Spectrum temporal scaling, source freshness, logical cadence and latest-state delivery. Experimental Sphere remains isolated until explicit operator migration approval.

For Sphere specifically:

- accepted-experimental does not mean permanent/shared promotion;
- user presets are arbitrary/sparse user-owned state;
- Settings bodies are transactional;
- persisted collapsible bucket state is sparse while canonical bucket identities remain schema;
- current Voxel Sphere tests supersede the retired smooth/material Sphere test family;
- reactivity/particle changes require the accepted A/B and current signal-contract tests, not a recreated old renderer.

### 6.5 Transitions

Quick transition ownership remains current. Do not restore old compositor transition presenters to satisfy stale tests. Preserve transition request/state fencing, authored shader/math, lifecycle and current Quick implementations. Crumble's rehomed shader assertions now belong in the current Quick Crumble suite.

### 6.6 Media/runtime services

Shared service tests should target current service ownership directly. Old `MediaWidget`/`WidgetManager` anchor setup is not a destination integration authority. Current injection/admission belongs to `rendering/widget_runtime_services.py`, Quick family binders and current Media presentation/runtime suites.

---

## 7. Test infrastructure rules

### Destination profile

- profile entries must resolve to existing files/node ids;
- each target runs in its own fresh subprocess;
- do not add an obsolete test merely because it once represented a migration gate;
- add new durable regression tests when the behavior is current and likely to regress;
- mark environment-specific tests rather than silently dropping them from documentation.

### Fixtures

Keep fixtures aligned with current architecture. A fixture that manufactures a retired owner can produce convincing green results for a product path that no longer exists.

### Goldens/replays

Do not regenerate goldens merely because architecture changed. If a deliberate product decision changes protected behavior, state the behavioural change explicitly and update goldens deliberately after approval.

### Static source assertions

Static tests are appropriate for:

- forbidden imports/owners;
- canonical defaults/manifest/reference paths;
- no timer/poller/thread additions;
- isolation boundaries;
- exact shader/source contract fragments where runtime execution is unavailable.

They are insufficient for proving:

- QML layout actually fits;
- signal/lifetime ordering under Qt;
- OpenGL output;
- visual smoothness;
- physical input/focus behavior;
- installed multi-monitor lifecycle.

---

## 8. Physical/installed acceptance

Installed eyes-on validation remains mandatory when a change can materially affect pixels, timing, focus/input, multi-monitor ownership or GPU behavior.

Examples:

- Achievement Pulse Progress Pulse must be viewed at `0%`, one/two-digit values and `100%`, with and without Shelf Style, at normal and CUSTOM sizes;
- About recolouring must be checked across materially different themes and after live theme switching;
- Voxel Sphere changes require real music, silence, loud-passage and geometry review;
- visualizer cadence/freshness work requires logs plus eyes-on response, not FPS alone;
- real-GL shader/resource changes need the intended driver/context environment.

A unit/static green does not overrule a reproducible installed visual regression.

---

## 9. Maintenance rule

When changing tests or this guide:

1. count current `test_*.py` modules from source instead of copying an old inventory;
2. validate every maintained-profile target exists;
3. run the broad collection diagnostic when practical and classify dependency blockers separately from product reds;
4. delete whole-file fossils once their remaining current assertions are rehomed or no longer applicable;
5. add **NEEDS RUN VALIDATION** immediately for newly added/recent tests that cannot execute in the current environment;
6. remove that label only after an actual appropriate-environment run;
7. update this file when architecture/test authority changes materially, not for every small assertion edit.

Current 2026-09-11 inventory after this audit:

```text
338 test_*.py modules (nine caller-dead/mixed-owner modules retired, nine current replacement/contract modules added)
130 unique maintained destination targets
0 missing destination target files
```

Git and `Docs/Historical_Bugs/` preserve migration history. `Docs/TestSuite.md` should stay current enough to tell an agent **what deserves trust now**.

---

## 10. Completion rule

A test-affecting slice is complete only when:

- production behavior and test expectation agree on the current owner/contract;
- directly runnable focused tests are green;
- environment-blocked current tests are explicitly marked **NEEDS RUN VALIDATION** where appropriate;
- obsolete tests have been deleted/re-homed rather than converted into permanent skips;
- defaults/generated artifacts are checked when settings changed;
- maintained-profile membership is valid;
- installed/Qt/GL evidence is requested where static/headless proof cannot close the claim.
