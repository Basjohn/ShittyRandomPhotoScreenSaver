# Test Suite Guide

Last updated: 2026-09-14

## 0.18 2026-09-14 Fossil-test hygiene + broad-tree reconciliation

Evidence-driven audit of the full `tests/` tree (per-file isolated run) on
Windows/PySide6. `collect_ignore` is confirmed **empty** (no fossil graveyard),
broad collection has **0 collection errors**, and the maintained `destination`
profile remains **132/132 GREEN**. Test-module count **368 → 364**. Broad-tree
per-file failures **58 → 32 files**. No production behaviour/default/schema was
changed to make any test pass.

**Whole-file fossils deleted (retired owners, no surviving current invariant):**
`test_presentation_benchmark_core.py` + `test_qtquick_presentation_spike.py`
(migration-era Qt Quick presentation spike tooling — caller-proven, deleted with
the tools); `test_spotify_overlay_repaint_contract.py` (scraped the retired
`widgets/spotify_bars_gl_overlay.py`); `test_r77_cleanup_quarantine_gui.py`
(imported the deleted one-off `SRPSS_R77_Cleanup_Quarantine_GUI.py`).

**Fossil cells trimmed / rehomed (kept the current invariant, dropped the dead
shell):** `test_p4_native_presentation.py` (dropped 8 `gl_compositor_pkg`
perf-HUD/present-context cells, kept DWM timing); `test_visualizer_mode_isolation.py`
(rehomed onto `rendering/quick/visualizer/implementations/`);
`test_osc_sine_glow_contract.py` (dropped redundant renderer-scrape + the
fully-retired `glow_size` migration); `test_engine_lifecycle.py` (removed retired
`multi_monitor_coordinator` scaffolding; settings-dialog-active rehomed onto
`engine._settings_dialog_active`); `test_media_volume_runtime.py` /
`test_system_mute_runtime.py` (removed retired `widget_setup_all` + WidgetManager
+ MediaWidget QWidget-anchor cells); `test_multidisplay_sync.py` (removed the
pre-Quick `set_image` display-contract cell); `test_steam_achievement_runtime.py`
(removed the WidgetManager fresh-process fossil; retired-path guard tolerates
absent files); `test_process_supervisor.py` (removed retired
`WorkerType.TRANSITION` / `MessageType.TRANSITION_PRECOMPUTE` assertions + the
TransitionPrepWorker contract fossil).

**Stale current-owner tests reconciled** (API/signature/default drift, not
fossils): jedi SSOT scrape, theme-defaults SSOT scrapes, reddit fixed-sort
policy, bubble settings/collision signatures (62→1), devcurve runtime/shape-editor/
settings-binding, sine line4 fields, cache-family list (`settings` family retired),
qt logger rename, transitions activation-gated nav, SpectrumShapeConfig field,
image-pipeline `perf_trace`, `_FakeSettingsManager.get_bool`, audio-worker
block-size guard, and several settings-binding test doubles gaining the current
canonical-default helpers.

**Remaining broad-tree reds (32 files) are NOT fossils** — they are current-owner
value/behaviour drift requiring operator judgment or deeper fixture work, and are
deliberately left rather than force-fixed (test count is not the metric):

- *Bubble reactivity golden (BTF-binding):* one `test_bubble_reactivity`
  grouped-drift signed-lag-spread oracle — do not retune Bubble to satisfy it.
- *Value-drift goldens (confirm each is intended before blessing):*
  `test_custom_layout_contract`, `test_f0_5_shadow_controls`, `test_input_gain`,
  `test_transient_per_mode_current`, `test_settings_dialog`,
  `test_default_settings_editor`, `test_display_tab`, `test_transitions_tab_setup`,
  `test_steam_abandonment_runtime`, `test_steam_credentials`,
  `test_build_closeout_contract`, `test_installer_v5_reset_policy`,
  `test_visualizer_settings_lazy_bodies_current`, `test_visualizer_settings_plumbing`,
  `test_widgets_tab_current` (non-profile cells), `test_widgets_tab_general_current`,
  `test_worker_latency_tuning`, `tests/unit/test_policy_compliance`.
- *Deeper behavioural/integration (fixture reconciliation needed):*
  `test_image_pipeline` (prefetch state shape), `test_image_worker`,
  `test_image_worker_shared_memory`, `test_save_debounce`,
  `test_spotify_visualizer_integration` + `test_visualizer_reactivity_quality`
  (need full resolved technical config to produce FFT output),
  `test_visualizer_preset_transfer` (fail-closed all-mode-presets contract),
  `test_reddit_helper_recovery`, `test_reddit_helper_task_harness`,
  `test_transition_distribution` + `test_visualizer_alignment` (semantic/real-Qt).
- *Real-GL:* `test_qtquick_render_node`, `test_qtquick_visualizer_clip_smoke`
  (need real-GL/driver acceptance).

## 0.17 2026-09-14 Windows/PySide6 destination profile — ALL GREEN (132/132)

The full maintained `destination` profile was executed on the intended
**Windows + PySide6 6.9.1 + OpenGL** environment
(`python tests/run_chunked.py --profile destination --chunks 4`):
**132 targets run, 132 passed, 0 failed.** The surviving current reds recorded
in §0.10 were reconciled at the test boundary and are now green; obsolete Sphere
coverage was retired separately (see the wording note below) rather than counted
among those passes. This also discharges the destination-target NEEDS RUN labels
in §0.15 (Clock slot: `test_layout_slots.py`, `test_qtquick_h_cutover.py`,
`test_widgets_tab_current.py::test_clock_settings_save_preserves_runtime_display_mode_overrides`)
and §0.16 (`test_settings_dark_qss_retirement_contract.py`,
`test_settings_theme_lifetime_contract.py`).

**Wording correction for the §0.10 "nine remaining reds":** that list was never
nine files that later all "passed". `test_sphere_mode_integration.py` was
deliberately deleted as a retired smooth/material-Sphere fossil (current Voxel
Sphere contracts supersede it — see §4.1); the remaining current-owner reds
(`test_qtquick_h_cutover`, `test_qtquick_custom_layout_overlay`,
`test_visualizer_viewport_scaling_contracts`, `test_visualizer_glow_footprint`,
`test_visualizer_line_coverage`, `test_bubble_aspect_pixels`,
`test_qtquick_achievement_pulse_presentation`, `test_sphere_voxel_audio_contract`)
were reconciled/repaired against current owners. Do not read §0.10 as "all nine
passed unchanged."

Every fix was a test-side reconciliation to current production; no production
owner/default/fallback was changed:

- `test_qtquick_h_cutover.py` no longer hangs. Settings stub gained
  `get_application_name()`; the minimal-config context-menu test explicitly
  disables the visualizer family (visualizers now default-on, so the menu
  legitimately gains Change Visualizer / Edit Widget Layout otherwise); the
  transient-lane stub gained the third `transient_clamp` arg; `_committed`
  supplies the neutral card/shadow kwargs the resolver now requires.
- `test_qtquick_input_controller.py`: `FriendPulsePresentation.qml` added to the
  double-click fallback-admission owner set.
- `test_qtquick_custom_layout_owner.py`: wheel-guide case reseated so the uniform
  enlarge grows toward the peer (880->895) publishing `(900,"peer")` without
  snapping; presenter stub gained `authored_geometry_for`.
- `test_qtquick_custom_layout_overlay.py`: cross-display transfer now asserts the
  deliberate retained-idle-shell design (the source item stays alive to avoid
  Shiboken wrapper invalidation on a return hop); admission departure is proven
  by the cleared `render_identity` in both directions.
- `test_visualizer_viewport_scaling_contracts.py`: collision helper passes the new
  `bounce_same_only`/`collision_pop_mode` kwargs; impulse-invariance settings
  dict gained the keys `BubbleSimulation.tick` now requires; devcurve
  projected-offset bar rehomed onto `value *= layout.normalized_y_scale`; the
  retired `widgets/.../renderers/spectrum.py` scrape was dropped (Quick
  implementation is the sole spectrum height-scale owner).
- `test_qtquick_achievement_pulse_presentation.py`: goldens reconciled to the
  established Progress-Pulse/Shelf design — `double_capsules` defaults on,
  `square_artwork_size` defaults to 160 (portrait 160x224), real `QFontMetricsF`
  capsule sizing; card-height bars now track `model.authoredHeight`.

**Operator-accepted 2026-09-14 (physical acceptance COMPLETE — no longer NEEDS RUN):**

- Achievement Pulse §8 physical visual acceptance (Progress-Pulse/Shelf at
  0% / one- and two-digit / 100%, with and without Shelf Style) — **ACCEPTED**.
- Clock analogue/digital slot + face + geometry installed acceptance
  (per-display double-click face state, slot save/load replay, mixed ALL routing,
  restart persistence) — **ACCEPTED**.
- `themes/dark.qss` file-absent visual/lifecycle acceptance across Default Dark,
  contrasting light/metal themes, live switching, tray, colour picker,
  tooltips/group boxes/check boxes, first-start, and native Glass/Acrylic —
  **ACCEPTED**, and `themes/dark.qss` has been **physically deleted** from the
  repository. Architectural rule retained: no replacement monolithic QSS file
  and no fallback stylesheet loader may be reintroduced; `SettingsThemeSpec`
  owns semantic palette/backdrop/shadow and narrow permanent renderers own
  structure.

**Still owed:** the broad full-tree `pytest tests/` reconciliation diagnostic
(the maintained profile is the primary product gate and is green; broad-tree work
is a fossil-reconciliation audit, not a mandate to resurrect retired architecture).

## 0.10 2026-09-12 Windows/PySide validation run — supersedes prior NEEDS RUN

The maintained `destination` profile was executed on the intended **Windows +
PySide6 6.9.1 + OpenGL** environment (unlike the earlier Linux audit that could
not import PySide6). This is the actual run the prior "NEEDS RUN"
labels were waiting for — treat those labels below as discharged for every
target that now passes.

- Broad collection: **4010 tests, 0 collection errors** — the earlier "206 files
  errored" was 100% environmental (missing PySide/OpenGL/feedparser).
- Destination profile before this migration pass: **77/130 pass, 53 fail**. The
  53 were stale tests predating the Sep-2026 visualizer **card/border/shadow**
  feature and the **Viz Schema Migration** (per-mode `*_growth` retired,
  full-materialized custom-cache normalization), plus intentional default
  changes — **not** architecture breakage. Production was internally coherent at
  every boundary checked.
- After this pass: **121/130 pass, 9 fail.** Reusable migration scaffolding lives
  in `tests/_visualizer_presentation.py` (neutral card resolver wrapper,
  `make_visualizer_owner`, canonical Bubble settings/pulse builders, model +
  technical-cache factory).

**One real production bug found and fixed** (not a stale test): Clock `12h`
format was unreachable via `ClockPresentationConfig.from_mapping`
(`rendering/quick/widgets/clock.py`) once the canonical default became `24h`;
`12 Hour` is user-selectable, so this was a functionality defect. Fixed to honour
either canonical token, falling back to the default only on invalid input.

**s_hotkey native crash fixed**: a cross-test QQuickWindow teardown race (pending
`deleteLater` destruction corrupting the next test's window teardown under
pytest-qt's event pump). Fixed by draining `DeferredDelete` in the fixture; not a
product defect (per-file subprocess isolation normally hides it).

**9 remaining reds (deferred, deeper work):** `test_qtquick_h_cutover` (hangs
creating real multi-display Quick windows — display-connectivity dependent, needs
a real installed session); `test_sphere_voxel_audio_contract` +
`test_sphere_mode_integration` (golden-value pins on operator-authored sphere
presets that drifted through the voxel work / smooth-sphere fossil — need a
deliberate golden refresh, not piecemeal guessing); `test_visualizer_glow_footprint`,
`test_visualizer_line_coverage`, one `test_bubble_aspect_pixels` real-GL assertion
(hand-built 27-param immutable frames drifted — need rehoming onto the production
frame-capture path rather than hand-maintained param dicts);
`test_qtquick_achievement_pulse_presentation` (Progress-Pulse/Shelf layout
redesign — eyes-on acceptance per §8); one `test_qtquick_custom_layout_overlay`
cross-display-transfer lifecycle assertion; `test_visualizer_viewport_scaling_contracts`
(Qt-avoiding module loader + many inline Bubble dicts + stale `renderers/spectrum.py`
path + DevCurve source scrapes).

---

## 0.11 2026-09-12 Visualizer ABC event-loop oracle correction

The original P4 `swap_sensitive` classifier result is **invalid causal evidence** because the event-loop recorder's 2,048-sample rolling percentile retained about 102.4 seconds of pre-window history while the ABC driver excluded only 15 seconds before marking a "steady" window. R-80 owns the failure/history.

Current test/oracle contract:

- `tests/test_event_loop_recorder.py` protects independent `period_*` report slices and scored-window history reset without restarting the timer/deadline chain;
- `tests/test_visualizer_switch_abc_driver.py` protects one event-loop scoring reset at each named `steady_A`, `steady_B`, `steady_C_pre` and `steady_C_post` boundary;
- `tests/test_visualizer_switch_abc_harness.py` proves causal scoring uses only matching window-local period summaries, rejects old rolling-only logs, preserves named C windows/freshness gates, applies persistence to represented non-overlapping periods, and preserves native Windows `--run-cmd` executable paths (including quoted paths with spaces).

Validation:

- corrected live A/B oracle on Windows: **VALID / persistent post-switch regression NOT REPRODUCED** (A p99 5.87 ms; B p99 6.80 ms; delta +0.93 ms/+15.8%; 3 >25 ms events each; ~89.9 Hz revision and 1.000 Bubble integration both);
- pure harness scorer/classifier/path-parser + experiment-flag tests executed directly in this Linux workspace: **37/37 PASS**;
- changed Python source compilation: **PASS**;
- real PySide recorder/driver pytest collection remains **NOT RUN HERE** because this workspace lacks PySide6. Do not convert that environment limitation into PASS.
- closed-investigation `core/diagnostics/visualizer_attribution.py` and its dedicated test were removed; retained coverage is the opt-in boundary lifecycle telemetry, repeated-switch retirement tests, corrected event-loop oracle, ABC driver/scorer and Windows command parsing.

The performance investigation is closed: the corrected A/B result rejects the synthetic persistent 25-switch poison claim, and the original long-run observation is not currently reproduced/actionable. Reopen only from future persistent/traceable evidence; do not schedule another probe campaign from this record alone.

---

## 0.12 2026-09-13 Friend Pulse and System Stats implementation verification

The F0-F6 Friend Pulse and S0-S6 CPU/RAM System Stats implementation verification is GREEN on Windows/PySide6:

- **281/281 PASS** across Friend source/privacy/cache/request/avatar runtime, System Stats source/shared sampler, both
  retained QML models/components, Steam/System Settings, binder/runtime-manager/family catalog, defaults authority,
  one-open buckets, ordinary uniform resize, display stacking/prediction, build assets and focused semantic theme
  inheritance. The expanded verification also covers private-cache ID confinement, identity-match validation, row-index-only
  Friend actions, Steam/profile/Store target validation, interactive client fallback, normal secure-helper fail-closed
  routing, exactly-once saver exit, and Achievement/Abandonment artwork actions;
- **14/14 PASS** across widget import dormancy, capability-catalog neutrality and Widgets SETUP activation routing;
- **258/258 PASS** for the public-admission follow-up across ungated Friend/System descriptors, Setup/pill visibility,
  retained binder admission, one-time existing-profile activation migration, later user-deactivation preservation,
  member-off dormancy, Steam actions, CLI compatibility, generated defaults and build assets;
- **160/160 PASS** for the final Friend roster correction across full online-first/offline-fill projection, zero-AppID
  rejection, visible-only avatar hydration, semantic actions, event-owned glow, virtualized Grid/Rows and stable model
  attachment;
- generated default snapshot plus both SST documents: **CURRENT** via `defaults_snapshot_builder --check-all`;
- production-Quick threaded-OpenGL visual smoke at DPR 1.5: eight-slot and twelve-friend Grid, Activity Rows, retained
  action menu, finite change glow, rounded avatar/tile corners, Strict, System Stats and both shared 40% floor captures
  rendered with **zero QML warnings**;
- source asset contract: Friend/System QML and the original System Stats gear-and-spanner SVG are required build payloads.

This is not the installed acceptance claim. Friend Pulse still needs connected-account privacy/readability,
installed Steam/chat/profile/Store routing, and two-display retirement/cardinality validation. System Stats still needs
the installed 10-second off-vs-on Visualizer contention/long-run and two-display resource/cardinality cells. Both are
public and member-disabled by default; `--devsteam` remains only for unfinished Games You Follow and `--devstats` is retired.
The parser tolerates the old `--devstats` token as an inert no-op so an existing shortcut cannot change launch mode.


## 0.13 2026-09-13 System Stats expansion + frameless interaction-glow gate

- System Stats now keeps one generation-shared, lease-gated fixed-delay sampler and adds **UPTIME** plus aggregate
  **NETWORK ↓/↑** to the same immutable snapshot; no new cadence owner exists. Canonical sample interval is user-adjustable
  only upward from a hard/default 10-second floor.
- The card has four fixed metrics (CPU LOAD, MEMORY, UPTIME, NETWORK), capacity 4 / authored height 430. User-facing
  implementation/rejection filler text is removed.
- Widget interaction glow/Jedi admission now requires the live `cardShellEnabled` truth for ordinary widgets and the
  Visualizer. Frameless presentations cannot load glow pixels, become click targets, retain click selection, or emit Jedi
  Mode through the glow path. The old shell-less Digital Clock intrinsic-bounds exception is retired.
- Local workspace lacks PySide6, so real Settings/QML pytest execution remains **NOT RUN HERE**. Local executable gates
  for this checkpoint are **8/8 PASS** pure System Stats source contracts, **11/11 PASS** shared-sampler state-machine
  cases under a Qt-free ThreadManager stub, generated-default authority **GREEN**, **15/15 PASS** changed-Python compile,
  plus static QML/card-shell policy checks.

---

## Current authority

The exact current source tree and the maintained `destination` profile in `tests/run_chunked.py` own executable test truth. `Current_Plan.md` owns execution order. Historical bug records and old migration reports are evidence, not permission to keep tests for retired owners alive indefinitely.

The current product is post-Qt-Quick cutover. The five established visualizer modes remain permanent shared modes; Voxel Sphere is an **accepted experimental, architecturally isolated** sixth mode. Tests must preserve that distinction rather than forcing Sphere into permanent-mode assumptions or treating experimental isolation as exemption from shared persistence/normalization contracts.

## 0.14 2026-09-13 geometry-guide + widget visual polish

Focused acceptance owns: wheel resize publishes alignment guides without snapping; authored guides are +1 px while the generic grid stays 1 px; Media artwork consumes non-overlapping right-column vertical space and insets under its frame; all shared dynamic artwork buffers are hard-contained; Friend Pulse local linework is +0.5 px, roster names are title-cased/two-line shrink-to-fit/bold, and BrandedHeader scale-up stroke delta receives the extra 25% boost. Real PySide/QML execution remains user-environment validation when unavailable to the agent.

This file is a maintained routing/status guide. It deliberately does **not** carry a giant hand-maintained inventory of every `test_*.py` file. That became stale faster than the code and obscured obsolete tests. Source discovery plus the maintained profile are the inventory authorities.

## 0.15 2026-09-14 Clock slot face-state persistence

The Clock slot repair has dedicated current-owner regression coverage. Clock analogue/digital face state is independent persisted state and must round-trip separately from the two CUSTOM geometry variants. **All automated coverage is GREEN and installed acceptance is COMPLETE (operator-accepted 2026-09-14; see §0.17).**

- `tests/test_layout_slots.py` protects v2 capture of `display_mode` + `display_mode_overrides`, exact replay including an explicitly empty override map, and v1 fallback that clears newer stale overrides and uses the legacy slot baseline. **GREEN** (2026-09-14 destination run).
- `tests/test_qtquick_h_cutover.py` carries the state through the real `DisplayManager` fenced save/load boundary. **GREEN** (destination target).
- `tests/test_widgets_tab_current.py::test_clock_settings_save_preserves_runtime_display_mode_overrides` proves a normal Clock Settings save cannot erase double-click/runtime per-display state. **GREEN** (destination target).
- Installed acceptance (save a slot with one display Digital and another Analogue, switch live, load the slot, verify the saved face + its own geometry per display, both directions and with an empty override map) — **ACCEPTED 2026-09-14**.

These tests must never collapse face state into geometry authority: `custom_layout` owns the `digital`/`analog` rectangles; the Clock section owns `display_mode` and per-display overrides.

## 0.16 2026-09-14 legacy Settings base-stylesheet retirement — COMPLETE

The production dependency on `themes/dark.qss` is severed with no monolith copied into another owner, and the retirement is now fully accepted: the Windows/PySide file-absent visual/lifecycle matrix passed and **`themes/dark.qss` has been physically deleted from the repository** (operator-accepted 2026-09-14; see §0.17).

- `tests/test_settings_dark_qss_retirement_contract.py`: **GREEN** (destination target). It proves live Settings/tray source has no legacy path reference/loader, the permanent structural base contains no palette literals, the complete Default Dark root renderer resolves with no placeholders/legacy file, generic disabled labels use `text.disabled`, tray `QMenu` geometry is rendered from existing semantic context-menu roles, the color-picker wrapper explicitly owns its old subsettings chrome, and installer/build tooling has no filename-specific dependency on the obsolete stylesheet.
- `tests/test_settings_theme_lifetime_contract.py` is reconciled to the complete-root renderer (`_build_settings_root_stylesheet`) rather than the retired base-file concatenation seam. **GREEN** (destination target).
- `tests/test_settings_theme_qobject_lifetime.py`, Settings dialog/theme switching, Theme Foundry, tray, picker, native Glass/Acrylic and first-start behaviour were validated in the file-absent installed matrix — **ACCEPTED 2026-09-14**.
- Physical removal of `themes/dark.qss` — **DONE**. The application is accepted running without the asset.

Retirement acceptance is zero intended visual/interaction change: semantic `SettingsThemeSpec` remains palette authority; structural QSS belongs to narrow permanent renderers. **Binding architectural rule (retained):** no replacement monolithic QSS file and no fallback stylesheet loader may be reintroduced, even when the asset is absent.

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

That was a Settings-hydration normalization/lifecycle hole, not a runtime geometry-normalization rewrite. Functional work is closed; the Qt resize-normalization oracle remains part of the outstanding Windows/PySide test inventory rather than a separate visual-acceptance blocker.

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

## 0.5 2026-09-11 small polish contracts

Three new Qt-free/source-level tests cover the narrow Achievement/CUSTOM/Particle slice without editing pre-existing test modules:

```text
tests/test_achievement_pulse_polish_contract.py
tests/test_custom_layout_peer_margin_snag_contract.py
tests/test_particle_transition_swirl_seam_contract.py
```

Direct execution in the current Linux workspace: **6/6 assertions PASS**. The geometry test executes the actual `_snap_axis_position()` function body in an isolated Qt-free namespace and verifies both the narrow/external-only 30 px peer-gap attraction and the small semantic alignment preference over a nearby grid target; a farther screen-edge approach still resolves to the ordinary grid, guarding against sticky snapping. The Particle contract protects the periodic Center Outward angle term and exact UI-to-shader label ordering. Achievement Pulse coverage protects the 10% text reduction, unchanged 108x108 pulse geometry, 4 px rail raise, and Shelf-only `UNKNOWN`/`UNAVAILABLE` presentation parity.

These focused gates do not replace the outstanding broad Windows/PySide/OpenGL test inventory.

## 0.6 2026-09-11 first-run source-onboarding launch contract

One new Qt-free/source-level test covers the launch-intent seam without editing a pre-existing test module:

```text
tests/test_startup_source_onboarding_resume.py
```

Direct execution in the current Linux workspace: **4/4 assertions PASS**. The contract protects normal RUN resumption after missing-source onboarding, preserves `/c`, `-c`, `-s` and `--s` as CONFIG-only invocations, verifies the same Settings manager is reused and `quitOnLastWindowClosed` is restored, and requires startup-dependent Interaction Mode resolution to occur after onboarding. Operator-installed launch validation is accepted as of 2026-09-11; only automated test execution debt remains.

## 0.7 2026-09-11 Visualizer dormancy schema + Weather Settings target

Two new Qt-free/current-owner contract modules cover this misc slice without editing a pre-existing test module:

```text
tests/test_visualizer_mode_activation_schema_current.py
tests/test_weather_settings_target_contract.py
```

Direct execution in the Linux workspace: **8/8 assertions PASS**. Visualizer coverage requires the canonical per-mode dormancy authority to be the explicit `mode_activation` boolean map, treats mapping insertion order as irrelevant while protecting registry-order resolution/the last-mode recovery invariant, verifies the typed model serializes no retired `enabled_modes` key, and proves the one temporary legacy reader converts/removes the old list while emitting warning feedback when relied upon. Weather coverage protects the semantic `weather_location` target, retained family callback injection, generation-checked DisplayManager/engine Settings lifecycle route, Widgets -> Weather lazy navigation and synchronous Location focus without a target-specific timer.

Defaults regeneration and authority checking are required for this schema change. Operator-installed validation is accepted as of 2026-09-11 for real Visualizer enable/disable persistence and the retained Weather missing-location SETTINGS click -> modal Settings -> runtime restart path; only automated test execution debt remains.

## 0.8 2026-09-11 Achievement Pulse post-fit percentage scale

One new Qt-free/source-level contract covers the installed visual follow-up without editing a pre-existing test module:

```text
tests/test_achievement_pulse_progress_text_visual_scale_contract.py
```

Direct execution in the Linux workspace: **2/2 assertions PASS**. The contract requires the 0.90 reduction to occur as a final presentation transform after `Text.HorizontalFit`, where it cannot be masked by the fitter's existing point-size choice. It separately protects the existing 108x108 pulse geometry and 4 px lift and verifies that the Total parsing/model and authored-size normalization remain in their existing Python owners. Operator-installed visual confirmation is accepted as of 2026-09-11; only automated test execution debt remains.

## 0.9 2026-09-11 Widget Glow Use Theme button style

One new Qt-free/source-level contract covers the tiny style correction without editing a pre-existing test module:

```text
tests/test_widget_glow_use_theme_button_style.py
```

Direct execution in the Linux workspace: **2/2 assertions PASS**. The Display -> Widget Glow `Use Theme` action now consumes the canonical `COMPACT_ACTION_BUTTON_STYLE`/`control.button.*` ThemeSpec semantics instead of the special ghost-action style. Its existing 30 px height, click behavior and `None` = Use Theme settings semantics are unchanged.

---

## 1. Status vocabulary

Use these labels consistently:

- **PASS** — executed against the stated current tree/environment and passed.
- **NEEDS RUN** — current/recent coverage judged valuable and structurally reconciled, but it could not execute in this environment. Run it on the intended Windows/PySide/OpenGL environment before using it as acceptance evidence. This is the canonical replacement for older `NEEDS RUN VALIDATION` wording.
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
- **NEEDS RUN** after this rehome because `ThreadManager` imports PySide6 in this environment.

`tests/test_system_mute_runtime.py`

- retained: shared owner/backend semantics, generation fencing, coalescing and UI-owner-thread behavior;
- removed: old `MediaWidget` + deleted `WidgetManager` anchor integration cells;
- current Quick injection is covered by current service/family-binder/media-presentation suites;
- **NEEDS RUN** after this rehome because `ThreadManager` imports PySide6 here.

`tests/test_qtquick_crumble_transition.py`

- received the useful Crumble shader assertions formerly embedded in the deleted mixed dimming/interaction file;
- **NEEDS RUN** because the retained transition package imports PySide6 here.

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

### NEEDS RUN

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
Operator-installed Settings bucket interaction is accepted as of 2026-09-11, including Spectrum Custom Bar Appearance/Rainbow rendering, no-flash sibling closure, lazy page/mode restoration, parent-disclosure reachability, and mode-switch/body-reconstruction reachability. Automated PySide coverage for the same paths remains outstanding where listed above.

Do not change environment-blocked automated entries to PASS until they have actually run on the intended environment.

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

High-value suites include `test_qtquick_runtime.py`, `test_qtquick_window.py`, `test_qtquick_monitor_wake_reconcile.py`, `test_qtquick_scene_controller.py`, `test_qtquick_family_binder*.py`, `test_qtquick_ordinary_widget_host.py`, lifecycle/terminal-destruction suites and family-specific Quick presentation tests. `test_qtquick_monitor_wake_reconcile.py` permanently pins the event-driven sleep/wake contract: same-count QScreen metric changes reach DisplayManager topology authority, only `ApplicationActive` admits resume repair, metric-first/resume-second bursts preserve that repair intent, unchanged final signatures reapply bound Quick geometry once, primary-screen changes are signature-visible, and retirement disconnects every topology edge. Installed physical dual-display wake validation passed on 2026-09-12 through real `2 -> 1 -> 2 -> 1 -> 2` topology churn; R-79 is closed while the nondeterministic same-signature resume branch remains automation-owned.

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
- production Settings/tray styling must not load `themes/dark.qss`; the root renderer and narrow component renderers own structure while `SettingsThemeSpec` owns semantic palette/backdrop/shadow values;
- `themes/dark.qss` is physically deleted (retirement operator-accepted 2026-09-14); its absence is never permission to reintroduce a fallback loader or a replacement monolithic Settings QSS;
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
- legacy Settings stylesheet retirement must be checked with the file physically absent across Default Dark, contrasting light/metal themes, live theme switching, tray menu, color picker, tooltips/group boxes/check boxes, first-start, and native Glass/Acrylic;
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
5. add **NEEDS RUN** immediately for newly added/recent tests that cannot execute in the current environment;
6. remove that label only after an actual appropriate-environment run;
7. update this file when architecture/test authority changes materially, not for every small assertion edit.

Current 2026-09-14 inventory after this pass:

```text
367 test_*.py modules
132 unique maintained destination targets
0 missing destination target files
```

The 2026-09-14 additions place the Clock slot file, the Clock Settings preservation node and the legacy-Settings-stylesheet retirement contract in the maintained destination profile. Environment-gated entries remain **NEEDS RUN** until an intended Windows/PySide execution records their result.

Git and `Docs/Historical_Bugs/` preserve migration history. `Docs/TestSuite.md` should stay current enough to tell an agent **what deserves trust now**.

---

## 10. Completion rule

A test-affecting slice is complete only when:

- production behavior and test expectation agree on the current owner/contract;
- directly runnable focused tests are green;
- environment-blocked current tests are explicitly marked **NEEDS RUN** where appropriate;
- obsolete tests have been deleted/re-homed rather than converted into permanent skips;
- defaults/generated artifacts are checked when settings changed;
- maintained-profile membership is valid;
- installed/Qt/GL evidence is requested where static/headless proof cannot close the claim.
