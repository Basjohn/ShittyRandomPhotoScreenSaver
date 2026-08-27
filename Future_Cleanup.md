# Future Cleanup — Migration Deletion Ledger

Last updated: 2026-08-27

This tracks deferred/caller-proven deletion work and does not admit work ahead of `Current_Plan.md`.

## Rule

```text
family replacement GREEN + caller proof -> family pixel deletion
G replacement GREEN                     -> old CUSTOM/edit pixel deletion
H cutover GREEN                         -> old physical presenter/backend deletion
I                                       -> residue only
```

Family GREEN follows current audit policy; an external reviewer is not mechanically required for every
ordinary family checkpoint. Real product resilience is not migration debris.

## Unrelated focused-test debt

- `tests/test_logging_config.py::test_diagnostic_build_enables_every_family_beside_frozen_executable`
  reproduces independently of active widget migration because at least one diagnostic
  `RotatingFileHandler` does not match the test's blanket 1 MiB expectation. Resolve handler policy vs
  stale assertion in a dedicated logging checkpoint.
- Reddit helper recovery/installer/watcher tests contain stale helper-era expectations (`_SPOOL_LAST_PROBE`,
  installer markers and singleton-state assumptions). Reconcile helper tests against current helper/
  installer contract separately from retained Reddit feed migration.
- The three physical two-display `tests/test_qtquick_runtime.py` smoke cases can miss only the second
  screen's 250 ms crossfade-midpoint capture while still completing transition and retirement. In the
  2026-08-27 Phase-F boundary run, the input-exit case passed on immediate rerun while identity/topology
  cases repeated the same capture miss. Reconcile the real-GL smoke capture deadline/oracle separately;
  no F8 Steam source participates in that path.

## Settings GUI residue

- `ui/tabs/presets_tab.py` is the disconnected legacy top-level Settings **Presets** tab. Current
  `SettingsDialog` has no Presets tab/import/constructor path. Delete it after final caller proof, together
  with stale comments such as the lazy Presets-tab signal-wiring note in `ui/settings_dialog.py`.
- This is **not** the active visualizer preset system. Preserve the live visualizer preset UI, transfer/
  import/export paths, preset data and runtime behavior.
- `ui/settings_theme_paths.py` contains temporary `THEMES_DIRECTORY_BUILD_REPLACE_BLANK` packaging wiring
  plus a repository-local `themes/` fallback so source/dev builds can exercise `.srtheme` loading now.
  Before release, build/startup authority must wire the real packaged themes directory (replace the blank
  or pass an explicit path), then remove the temporary stub/dev fallback once that resource-path contract
  is durable. Preserve compiled `DEFAULT_DARK_SETTINGS_THEME` as the unconditional no-file fallback.

## Phase-F family retirement

After each substantive F1–F8 family is GREEN and caller-proofed:

- delete old QWidget/QPainter family pixels;
- delete/rehome presentation-only tests/helpers;
- retain presentation-neutral provider/model/business/settings/runtime code still used;
- retain shared old helpers only while a live destination/unported owner genuinely needs them.

Git becomes historical pixel reference after deletion.

## Transition legacy

All canonical transition implementations are Quick-owned. Old transition-only presentation
(`TransitionFactory` pixel construction, `gl_compositor_*_transition.py`, old presentation tests/helpers)
may retire before H as soon as exact caller proof permits.

Preserve canonical registry/settings, activation/admission, request/run lifecycle, authored math/shaders used
by Quick and deterministic recovery. A seam inseparable from old physical host may wait for H; do not invent
compatibility architecture.

## Visualizer legacy

Do not delete by path/name alone. Preserve destination-used `VisualizerLogicalRuntime`, mode frame runtimes/
authored algorithms, BeatEngine/source ownership, immutable render state, snapshot bridge/adapters and
shaders/math used by Quick.

Delete caller-proven old compositor-only/card/overlay pixel owners as soon as safe. Physical-host pieces may
wait for H.

## Phase G

After Quick CUSTOM/input/edit presentation GREEN, delete old QWidget edit/grid/pixel owners, preserve
committed geometry/session semantics under destination owners, and preserve real non-pixel Settings controls.

## Phase H

H removes old physical presentation in the same audited cutover boundary: `DisplayWidget`, QRhiWidget /
`GLCompositorWidget`, old compositor scheduling/presentation glue, software/backend-demotion fallback,
render-backend selection used only by that fallback, obsolete `hw_accel`/fallback-overlay policy, remaining
physical-host transition/visualizer debris, temporary legacy anchors after destination ownership, and obsolete
presentation compatibility settings.

No production switch back.

## Phase I

I should be small: expired adapters, compatibility aliases, stale old-presenter utilities, obsolete tests/
tools/comments and abandoned spike code. Preserve product-neutral logic, diagnostics and resilience.

## Phase J

Archive/remove migration-only harnesses/planning material only after final validation evidence exists.
