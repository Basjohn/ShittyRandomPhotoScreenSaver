# Future Cleanup — Migration Deletion Ledger

Last updated: 2026-08-31

This tracks deferred/caller-proven deletion work and does not admit work ahead of `Current_Plan.md`.

## Rule

```text
caller-dead replaced pixels/helpers        -> delete when replacement contract is proven
G replacement GREEN                        -> no old CUSTOM/auxiliary pixel authority remains
H Quick production owner GREEN             -> delete remaining physical presenter/backend
I                                           -> residue only
```

A working legacy product during migration is not a retention reason.

## Current migration deletion boundary

G is closed. Do not reopen G4/G7/G8 as cleanup work.

The H authority cutover closed at `9dcb02be`: exact caller proof established the Quick destination as sole production
authority and the legacy physical-host presenter/backend source was deleted. H physical/correction acceptance remains open
in `Current_Plan.md`. Preserve Python semantic command/settings authority and neutral configuration/runtime logic; do not
restore superseded pixel/presentation ownership.

After the authority flip, I is source-driven residue only: expired aliases/adapters/tools/tests/comments that no longer own a
surviving contract.

## Unrelated focused-test debt

- Reddit helper recovery/installer/watcher tests contain stale helper-era expectations; reconcile separately from the
  retained Reddit presentation.
- Real two-display QScreen identity/topology smoke cells are **J physical acceptance evidence**, not generic cleanup debt and
  not an H deterministic gate. Keep them unless their evidence role is rehomed to an equivalent current harness.

## Settings GUI residue

- Re-audit `tools/regenerate_defaults_snapshot_artifacts.py` and `tools/regenerate_sst_defaults.py` against the final Quick/H
  settings schema before using them for migration-era defaults. Their installed-profile write hazard is fixed by `R-33`, but
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

F1–F8 family pixel retirement is closed. Do not retain or reconstruct old QWidget/QPainter family presenters for H/I.
Keep neutral provider/model/business/settings/runtime code still used by the Quick destination.

## Transition legacy

Canonical transitions are Quick-owned. Delete caller-proven old transition-only presentation as soon as safe. Preserve
canonical registry/settings, request/run lifecycle, authored math/shaders used by Quick and deterministic recovery. Only
an edge inseparable from the old physical host waits for H.

## Visualizer legacy

Preserve destination-used `VisualizerLogicalRuntime`, mode frame runtimes/authored algorithms, BeatEngine/source
ownership, immutable render state, snapshot bridge/adapters and shaders/math used by Quick. Delete caller-proven old
compositor/card/overlay pixels. The G4 viewport-edge ownership/spatial correction work is closed; do not mistake its retained contracts/tests for legacy
cleanup.

Current I residue discovered during H5c focused validation:

- `tests/test_spotify_visualizer_widget.py` still imports deleted `widgets.spotify_bars_gl_overlay` and cannot collect;
- `tests/test_visualizer_replay.py` / `tools/visualizer_replay.py` still import deleted `widgets.spotify_visualizer.replay_runtime` and cannot collect.
- `tests/test_visualizer_preset_cycling_runtime.py` still imports the deleted QWidget `InputHandler`, `WidgetManager`, and
  `SpotifyVisualizerWidget`. Its `InputHandler` cases are mouse-button routing only, not audio input. Surviving preset
  resolution/Custom round-trip contracts live in `test_visualizer_runtime_preset_cycle.py`; mode-owned `input_gain` and
  other audio settings reaching the shared BeatEngine are pinned by the Quick reactivity/config and True-F gates.

Do not restore either retired presenter/replay module to satisfy these files. Reconcile the stale harnesses against surviving
Quick/logical owners only after H admits I; maintained Bubble BTF/cadence/Quick tests remain the H gate.

## Closed Phase G

G is closed at the accepted deterministic destination boundary. Its surviving neutral/retained contracts are permanent
regressions, not deletion candidates. Any old G-era presenter code that survives after H must be classified from exact
post-cutover callers during I rather than preserved because this ledger once named a G task.

## Closed Phase H

H wired final Quick production orchestration and removed the remaining physical presentation: `DisplayWidget`,
QRhiWidget/`GLCompositorWidget`, old compositor scheduling/presentation glue, software/backend-demotion fallback,
render-backend selection used only by that fallback, obsolete `hw_accel`/fallback-overlay policy, remaining
physical-host transition/visualizer debris, temporary legacy anchors and obsolete presentation compatibility settings.

No production switch back. I must not recreate a functional old app for residue-test convenience.

## Phase I

I should be small: expired adapters, compatibility aliases, stale old-presenter utilities, obsolete tests/tools/comments
and abandoned spike code. Preserve product-neutral logic, diagnostics and resilience.

## Phase J

Archive/remove migration-only harnesses/planning material only after final compiled/installed/physical validation
evidence exists.
