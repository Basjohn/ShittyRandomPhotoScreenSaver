# Future Cleanup — Active Deletion / Compatibility Ledger

Last updated: 2026-09-12

This file contains only **surviving cleanup/deletion debt**. Completed migration history belongs in
`Docs/Fossils/`, historical bug records and source-control history (the Qt Quick migration is closed and its
`Docs/QtQuick_Migration/` decomposition tree was deleted); it must not remain here as a pseudo-task that a
later agent can accidentally reopen. `Current_Plan.md` always outranks this file.

## Rules

```text
READY / caller-proven residue     -> remove in one bounded cleanup slice
DELETE AFTER HORIZON              -> temporary compatibility read/migration bridge only
```

- Never restore deleted QWidget/GL/overlay/polling/fallback owners to satisfy an old test/tool.
- Rehome a still-valid behavioural assertion to the current Quick/logical owner, then delete the fossil.
- Exact caller/import search precedes each deletion batch. Historical-document references are evidence,
  not production callers.
- Cleanup is not performance tuning. Do not alter Visualizer cadence/freshness/reactivity or GC policy
  merely because a compatibility symbol is being removed.

## READY — broad-suite stale-owner reconciliation

The old manual-delete tool/test set from the 2026-09-01 tooling audit is already absent from the current
tree; do **not** keep re-listing or recreating it. The remaining broad-suite debt is now the larger set of
stale tests that still import/assert against deleted presentation owners such as `DisplayWidget`,
`GLCompositorWidget`, `spotify_bars_gl_overlay` and `SpotifyVisualizerWidget`.

- [ ] Reconcile these by current behaviour/owner, using `Docs/TestSuite.md` as the detailed ledger.
- [ ] Delete assertions that only prove dead compositor/QWidget implementation details.
- [ ] Rehome surviving layout/input/Media-Center/transition/visualizer behaviour to current Quick or
      presentation-neutral owners before deletion.
- [ ] Reconcile Reddit helper recovery/installer/watcher tests separately from retained Reddit presentation.
- [ ] Restore the broad whole-tree suite to useful signal without weakening the canonical `destination`
      profile or resurrecting museum architecture.

## DONE — caller-dead visualizer-renderer + image-processor islands

Exact production-import search was reconfirmed on 2026-09-11 and both caller-dead islands are retired. The
pre-Quick `widgets/spotify_visualizer/renderers/` package and synchronous `rendering/image_processor.py` no
longer exist. Live mixed coverage was rehomed to current owners before the old test modules were staged as
debris: Quick Spectrum layout, presentation-neutral Sine reactivity, Quick DevCurve shader/uniform source,
and QImage-first `AsyncImageProcessor`. `test_retired_runtime_islands_contract.py` now guards both removals
without requiring museum owners to import. Never restore either island to satisfy historical tests.


## DONE — bucket reachability / stale bucket-test residue

The 2026-09-11 single-open bucket change was followed by an explicit reachability/duplication audit. Outer Visualizer
`Advanced`/`Technical` disclosures remain independent parents; Technical `AGC`/`Transient` are current leaf buckets.
Seven duplicated Widget bucket-finalization helpers were collapsed into the shared owner. Three mixed tests retained
current coverage but asserted retired bucket semantics, so their surviving coverage was rehomed to
`test_widgets_tab_current.py`, `test_widgets_tab_general_current.py`, and
`test_visualizer_settings_lazy_bodies_current.py`; the old modules are debris. Do not restore simultaneous sibling-open,
fresh-profile default-open, or checkbox-style Technical visibility semantics to make old tests pass.

## READY — retained broad-suite evidence reconciliation

The later Sphere/geometry destination run completed all 117 targets (105 passed, 12 failed). The same nine
unrelated targets below remain red. Its additional CUSTOM-owner failure occurred while that implementation was
being edited and is covered by the live-commit slice's focused rerun; the input-exit smoke failure was an
intermittent missing midpoint capture, with retirement complete. Its bounded fixture now allows three phase
intervals for the existing render-node oracle; three input-exit reruns and one recreation rerun passed without
new timers, polling or frame requests.

- [ ] **Awaiting Logs — S-hotkey native fault:** the later destination run recorded one access violation
  (`3221225477`) in `test_s_hotkey_workflow.py`; an isolated rerun passed all 12 tests. Preserve
  `logs/evidence_chest/fw_missing_line_glow_2026_09_05/pytest_destination_group_1.log` and obtain a repeatable
  stack/reproduction before changing lifecycle. Do not attribute it to Sphere or declare it fixed without evidence.

The 2026-09-05 115-target destination run exposed these surviving unrelated reds after Glow/Slide/Sphere-related
fixtures and the new retirement native fault were corrected. Evidence: `logs/pytest_destination_group_{1,2,3,4}.log`.
The initial native runtime-reality and hotkey failures passed after replacing Qt-owned runnable cleanup with render
events; the later non-reproduced hotkey fault is tracked separately above. The missing legacy Spectrum smoothing target was already deleted
by `a3e4ec17`; its stale profile entry was removed rather than restoring retired plumbing.

- [ ] Reconcile `test_qtquick_media_presentation.py` against current border/volume colour/artwork aspect/title/mask
  contracts, and `test_media_external_volume_contract.py` against current Settings bucket names.
- [ ] Reconcile current weather/achievement border, layout and theme expectations in
  `test_qtquick_weather_presentation.py` and `test_qtquick_achievement_pulse_presentation.py`.
- [ ] Resolve Widget Theme catalogue/assets counts and layout markers in `test_widget_theme_no_material_contract.py`,
  `test_theme_completion_slice_contract.py` and `test_theme_expansion_light_metal_contract.py`; do not synthesize
  missing theme assets solely to bless a count.
- [ ] Update obsolete phase prose assertions in `test_visualizer_doc_references.py` against the current destination.
- [ ] Resolve caller-proven quarantine/debris listed by `test_tooling_ownership.py` without restoring removed tools.


## READY AFTER PROFILE PROOF — Visualizer `enabled_modes` migration bridge

`widgets.spotify_visualizer.mode_activation.<stable_mode_id>` is the sole current persisted/runtime authority. The old
`enabled_modes` list survives only as a pre-default forward-migration signature for supported older profiles.

- [ ] Remove `migrate_legacy_enabled_modes_to_activation`, its SettingsManager pre-default hook and warning path only
      after automated persisted-profile/import fixtures prove supported profiles no longer require the bridge.
- [ ] Current defaults/model/UI/runtime must never write or consume `enabled_modes` as product state while the bridge
      exists. Do not retain it as a second dormancy representation.

## AUDIT — GPU timing CLI versus Quick ownership

- [ ] Reconcile `main.py`/logging's advertised `--gpu-timing` owner-context query capability with current
  Quick production: exact search finds no Quick GL timer-query consumer. Preserve useful PERF logging;
  remove stale claims or deliberately implement measured, bounded owner-context diagnostics when a real
  attribution task needs them. Do not restore the retired compositor to make this switch truthful.

## READY — temporary `h-destination` profile alias

Current repo search shows `h-destination` has no live automation/script caller outside its own
`tests/run_chunked.py` compatibility declaration; remaining occurrences are historical/migration prose.

- [ ] Remove the alias and its current TestSuite wording in one bounded cleanup after a final exact caller
      search. Historical documents may retain the old name as history. `destination` remains canonical.

## READY — pre-Quick `GCController` compatibility facade

`core/performance/frame_budget.py` still defines/exports `GCController` and `get_gc_controller()`, but
current non-document caller search finds only the facade/export itself. `RuntimeGCPolicy` is the RUN-lifetime
GC owner.

- [ ] Remove the dead facade/global/export after one final import/caller proof.
- [ ] Do **not** combine this deletion with collector retuning. The accepted `gc.freeze()` policy and any
      measured late-J GC work remain separate.

## READY — Media idle process-probe residue

Event-driven GSMTC ownership retired the old idle process-running probe. Current source search finds no
production caller of the old `is_app_process_running()` interface/Windows override. Its Toolhelp helpers are
used only by that probe.

- [ ] Remove `BaseMediaController.is_app_process_running()`, the Windows override, `_win_process_exists()` and
      `_win_any_process_exists()` after stale tests/fakes are rehomed or deleted.
- **KEEP `get_provider_process_exe_names()`.** It now has durable value in exact Core Audio/app-volume target
  resolution (`spotify_volume.py` and source-identity mapping). Do not delete it under the old polling cleanup
  rationale; update its stale idle-poll-oriented docstring when that cleanup lands.
- Never restore process polling or a fast Media fallback.

## DELETE AFTER HORIZON — Clock separator compatibility key

Current ownership is `widgets.clock.show_separator` + `widgets.clock.separator_thickness`.
`widgets.clock.show_digital_separator` survives only as a read compatibility input for older saved configs.
Current UI/default saves must not revive it as a supported second key.

- [ ] After the compatibility horizon and exact persisted-config/caller proof, remove the legacy fallback
      from Clock presentation/settings loading and update its compatibility tests.

## DELETE AFTER HORIZON — ordinary Widget family colour bridge

Branded-header family colour controls are retired in favour of Widget Theme `header.*` semantics plus
`Widgets -> General -> Style Overrides -> Header Fill`. `Reset All Colours to Theme` is deliberately
**user-invoked**, never a startup migration. It normalizes ordinary family colour/alpha values to canonical
implicit-Inherit values and excludes Visualizer-authored colours.

Temporarily retained compatibility is now limited to old per-family colour persistence/value reads needed
for old profiles/imports. Retired header-button loader/signal/finalize bookkeeping has been removed rather
than preserved as phantom GUI authority. This is migration plumbing, not a supported hidden palette.

- [ ] After the supported old-profile/SST-import horizon and exact caller proof, remove retired header-colour
      persistence/value fields that no surviving import contract needs.
- [ ] Audit the remaining non-header family colour fields individually: keep only those with genuine durable
      family-level customization value; otherwise retire them rather than preserving invisible precedence.
- If `Reset All Colours to Theme` has become a useful permanent user action by then, keep the action and
  delete only obsolete compatibility plumbing.

## Settings GUI residue

### `themes/dark.qss` retirement

`themes/dark.qss` remains legacy base-stylesheet geometry/debris, not Settings Theme palette authority. This row is
cleanup bookkeeping; active sequencing is `Current_Plan.md` section 3. Execution authority is
`Docs/Future_Work/Settings_Dark_QSS_Retirement.md`. Do not simply delete it, copy literals into
Python, or disturb native AccentPolicy/frameless/forged-edge behaviour. Final retirement requires the
physical Default Dark + Acrylic + Glass + dialogs/controls/tray matrix with the file genuinely absent, then
production loaders and file removed in the same bounded slice.

The old `ui/settings_theme_paths.py` "temporary packaging/dev fallback" task is **closed**: current source
already resolves explicit injection -> ProgramData for frozen/installed -> repo source for dev, without
silently merging another root. Do not reopen it unless a new packaging defect is observed.

## READY — retire migration-era architecture-selection evidence

The Qt Quick migration is closed and operator-accepted. These bounded architecture-selection artifacts are no longer
protected by a final-acceptance horizon; they are ordinary caller-proven cleanup candidates:

- `tools/presentation_benchmark_core.py` + `tests/test_presentation_benchmark_core.py`;
- `tools/qtquick_presentation_spike.py` + `tests/test_qtquick_presentation_spike.py`.

They are bounded architecture-selection evidence, not current product-performance authority. Do not expand them.
Perform one final exact caller/import search, rehome any still-useful behavioural assertion to a current owner, then
delete each tool with its spike-only tests. If future performance work is reopened from a genuine traceable issue, use retained built-in/opt-in evidence instead of keeping these migration spikes alive.

## Permanent cleanup guardrails

- `R-72`: production never imports operator analysis tools.
- R-69/R-76 Visualizer response/freshness contracts are not cleanup targets.
- Stable RSS/VRAM/thread/handle/cache counts are not deletion targets merely because they are large.
- Runtime card Glass/Acrylic experiments are rejected historical material; never resurrect their Loader/
  capture/mask/cadence owners as "cleanup compatibility".
- Product-neutral provider/model/settings/runtime logic stays unless exact current callers prove it dead.
