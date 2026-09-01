# Future Cleanup — Migration Deletion Ledger

Last updated: 2026-09-01

This tracks deferred/caller-proven deletion work and does not admit work ahead of `Current_Plan.md`.

## Rule

```text
caller-dead replaced pixels/helpers        -> delete when replacement contract is proven
G replacement GREEN                        -> no old CUSTOM/auxiliary pixel authority remains
H Quick production owner + acceptance GREEN -> H closed; never restore physical presenter/backend
I ACTIVE                                    -> caller-proven residue only
```

A working legacy product during migration is not a retention reason.

## Current migration deletion boundary

G is closed. Do not reopen G4/G7/G8 as cleanup work.

The H authority cutover closed at `9dcb02be`: exact caller proof established the Quick destination as sole production
authority and the legacy physical-host presenter/backend source was deleted. H post-cutover physical/correction/performance
acceptance is now also closed; durable evidence lives in `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md`. Preserve
Python semantic command/settings authority and neutral configuration/runtime logic; do not restore superseded
pixel/presentation ownership.

After the authority flip, I is source-driven residue only: expired aliases/adapters/tools/tests/comments that no longer own a
surviving contract.

## Unrelated focused-test debt

- Reddit helper recovery/installer/watcher tests contain stale helper-era expectations; reconcile separately from the
  retained Reddit presentation.
- Real two-display QScreen identity/topology smoke cells are **J physical acceptance evidence**, not generic cleanup debt and
  not an H deterministic gate. Keep them unless their evidence role is rehomed to an equivalent current harness.

## Settings GUI residue

- Re-audit `tools/regenerate_defaults_snapshot_artifacts.py` and `tools/regenerate_sst_defaults.py` against the final Quick
  destination settings schema before using them for migration-era defaults. Their installed-profile write hazard is fixed by `R-33`, but
  that safety proof does not establish that every generated field still follows current mode/layout ownership.
- `ui/settings_theme_paths.py` contains temporary theme-directory packaging/dev-fallback wiring. Before release, wire the
  real packaged themes directory and remove temporary fallback once that resource-path contract is durable. Preserve
  compiled Default Dark as unconditional no-file fallback.
- `themes/dark.qss` is legacy base-stylesheet debris, not Settings theme authority. Its removal is a dedicated zero-intended-
  pixel-change cleanup. **Execution authority: `Docs/Settings_Dark_QSS_Retirement.md`.** Do not simply delete the file,
  copy its visual literals into Python, or alter native AccentPolicy/frameless/forged-edge behavior while retiring it.
  The final gate is a physical Default Dark + Acrylic + Glass + dialogs/controls/tray matrix with the file genuinely absent,
  followed by removal of both production loaders and the file in the same bounded cleanup boundary.
  Permanent backdrop/theme authority remains `Docs/Settings_Theme_Architecture.md`.

## Closed Phase-F family retirement

F1–F8 family pixel retirement is closed. Do not retain or reconstruct old QWidget/QPainter family presenters during I/J.
Keep neutral provider/model/business/settings/runtime code still used by the Quick destination.

## Media post-event-migration residue

After `2e7a9242`, the retired idle-poll process-probe path is no longer production-owned: `WindowsGlobalMediaController.is_app_process_running`, `_win_*_process_exists`, and `get_provider_process_exe_names` were used by the old idle polling stages and are now cleanup candidates. Remove only in I/a bounded cleanup after exact caller proof. **Do not reinterpret their existence as permission to restore process polling or a fast Media fallback.**

## Transition legacy

Canonical transitions are Quick-owned. The old physical-host edge left with the accepted H cutover. Preserve canonical
registry/settings, request/run lifecycle, authored math/shaders used by Quick and deterministic recovery. Any surviving
old transition-only source/test/tool reference is I residue; never restore the deleted host to satisfy it.

## Visualizer legacy

Preserve destination-used `VisualizerLogicalRuntime`, mode frame runtimes/authored algorithms, BeatEngine/source
ownership, immutable render state, snapshot bridge/adapters and shaders/math used by Quick. Delete caller-proven old
compositor/card/overlay pixels. The G4 viewport-edge ownership/spatial correction work is closed; do not mistake its retained contracts/tests for legacy
cleanup.

Current I residue discovered during H closure/test reconciliation:

- `tests/test_spotify_visualizer_widget.py` still imports deleted `widgets.spotify_bars_gl_overlay` and cannot collect;
- `tests/test_visualizer_replay.py` / `tools/visualizer_replay.py` still import deleted `widgets.spotify_visualizer.replay_runtime` and cannot collect.
- `tests/test_visualizer_preset_cycling_runtime.py` still imports the deleted QWidget `InputHandler`, `WidgetManager`, and
  `SpotifyVisualizerWidget`. Its `InputHandler` cases are mouse-button routing only, not audio input. Surviving preset
  resolution/Custom round-trip contracts live in `test_visualizer_runtime_preset_cycle.py`; mode-owned `input_gain` and
  other audio settings reaching the shared BeatEngine are pinned by the Quick reactivity/config and True-F gates.

Do not restore either retired presenter/replay module to satisfy these files. Reconcile the stale harnesses against surviving
Quick/logical owners during I; maintained Bubble BTF/cadence/Quick tests remain permanent destination guards.

## Closed Phase G

G is closed at the accepted deterministic destination boundary. Its surviving neutral/retained contracts are permanent
regressions, not deletion candidates. Any old G-era presenter code that still survives is post-cutover I residue and must be classified from exact current
callers rather than preserved because this ledger once named a G task.

## Closed Phase H production + post-cutover acceptance

The H production-authority cutover wired final Quick orchestration and removed the remaining physical presentation:
`DisplayWidget`, QRhiWidget/`GLCompositorWidget`, old compositor scheduling/presentation glue,
software/backend-demotion fallback, render-backend selection used only by that fallback, obsolete
`hw_accel`/fallback-overlay policy, remaining physical-host transition/visualizer debris, temporary legacy anchors and
obsolete presentation compatibility settings. **The cutover and its named post-cutover functional/runtime/performance gates are accepted; H is closed.**
See `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md`.

No production switch back. I is active and must not recreate a functional old app for residue-test convenience.

## Phase I

I should be small: expired adapters, compatibility aliases, stale old-presenter utilities, obsolete tests/tools/comments
and abandoned spike code. Preserve product-neutral logic, diagnostics and resilience.

Immediate caller/contract-proven manual test deletions from the H-closure audit:

- `tests/test_settings_sync.py` — tombstone only;
- `tests/test_phase_e_effect_corruption.py` — historical QGraphicsEffect investigation;
- `tests/test_visualizer_preset_cycling_runtime.py` — deleted QWidget host; surviving same-mode preset/Custom/audio-setting contracts have current owners.

Other stale-owner rows in `Docs/TestSuite.md` are **candidates**, not a bulk-delete list. Prove the surviving contract/current owner before deleting each one.

Additional high-confidence source/tool residue to prove then remove in bounded I slices:

- orphan `rendering/quick/qml/CursorHalo.qml` if exact caller search remains empty; native `QCursor` is the permanent Halo pixel owner;
- Media process-probe helpers retired by event ownership (`is_app_process_running`, `_win_*_process_exists`, provider-process-name helpers) if exact caller search confirms no non-polling consumer;
- old GL/compositor/visualizer presenter aliases/adapters/comments/spikes whose production callers disappeared with H;
- temporary `h-destination` runner alias after exact script/doc caller proof shows all automation has moved to `destination`.

Do not classify rare deep GC pauses as deletion cleanup. R-71 carries that evidence to late J performance work, and any future optimization must preserve Visualizer reactivity/freshness/cadence.

## Phase J

Archive/remove migration-only harnesses/planning material only after final compiled/installed/physical validation
evidence exists.
