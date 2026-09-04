# Future Cleanup — Active Deletion / Compatibility Ledger

Last updated: 2026-09-03

This file contains only **surviving cleanup/deletion debt**. Completed migration history belongs in
`Docs/QtQuick_Migration/`, historical bug records and source-control history; it must not remain here as
a pseudo-task that a later agent can accidentally reopen. `Current_Plan.md` always outranks this file.

## Rules

```text
READY / caller-proven residue     -> remove in one bounded cleanup slice
DELETE AFTER HORIZON              -> temporary compatibility read/migration bridge only
J EXIT                            -> retain until final compiled/installed/physical evidence exists
```

- Never restore deleted QWidget/GL/overlay/polling/fallback owners to satisfy an old test/tool.
- Rehome a still-valid behavioural assertion to the current Quick/logical owner, then delete the fossil.
- Exact caller/import search precedes each deletion batch. Historical-document references are evidence,
  not production callers.
- Cleanup is not performance tuning. Do not alter Visualizer cadence/freshness/reactivity or GC policy
  merely because a compatibility symbol is being removed.

## READY — stale destination tests and dead-owner expectations

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

## READY — Future Work destination gate reconciliation

The 2026-09-05 115-target destination run exposed these surviving unrelated reds after Glow/Slide/Sphere-related
fixtures and the new retirement native fault were corrected. Evidence: `logs/pytest_destination_group_{1,2,3,4}.log`.
The native runtime-reality and hotkey targets now pass after replacing Qt-owned runnable cleanup with render events;
do not leave those as unresolved native failures. The missing legacy Spectrum smoothing target was already deleted
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

`themes/dark.qss` remains legacy base-stylesheet geometry/debris, not Settings Theme palette authority.
Execution authority is `Docs/Settings_Dark_QSS_Retirement.md`. Do not simply delete it, copy literals into
Python, or disturb native AccentPolicy/frameless/forged-edge behaviour. Final retirement requires the
physical Default Dark + Acrylic + Glass + dialogs/controls/tray matrix with the file genuinely absent, then
production loaders and file removed in the same bounded slice.

The old `ui/settings_theme_paths.py` "temporary packaging/dev fallback" task is **closed**: current source
already resolves explicit injection -> ProgramData for frozen/installed -> repo source for dev, without
silently merging another root. Do not reopen it unless a new packaging defect is observed.

## J EXIT — temporary architecture-selection evidence

Keep only until final compiled/installed/physical acceptance no longer needs them:

- `tools/presentation_benchmark_core.py` + `tests/test_presentation_benchmark_core.py`;
- `tools/qtquick_presentation_spike.py` + `tests/test_qtquick_presentation_spike.py`.

They are bounded architecture-selection evidence, not current product-performance authority. Do not expand
them. Delete them together with their spike-only tests at J exit.

## Permanent cleanup guardrails

- `R-72`: production never imports operator analysis tools.
- R-69/R-76 Visualizer response/freshness contracts are not cleanup targets.
- Stable RSS/VRAM/thread/handle/cache counts are not deletion targets merely because they are large.
- Runtime card Glass/Acrylic experiments are rejected historical material; never resurrect their Loader/
  capture/mask/cadence owners as "cleanup compatibility".
- Product-neutral provider/model/settings/runtime logic stays unless exact current callers prove it dead.
