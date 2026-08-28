# Future Cleanup — Migration Deletion Ledger

Last updated: 2026-08-29

This tracks deferred/caller-proven deletion work and does not admit work ahead of `Current_Plan.md`.

## Rule

```text
caller-dead replaced pixels/helpers        -> delete when replacement contract is proven
G replacement GREEN                        -> no old CUSTOM/auxiliary pixel authority remains
H Quick production owner GREEN             -> delete remaining physical presenter/backend
I                                           -> residue only
```

A working legacy product during migration is not a retention reason.

## Current first-order migration cleanup

Do **not** perform this instead of the active bounded G4 post-checkpoint audit corrections. After those corrections, finish
G7 caller proof and remove any remaining old QWidget/top-level context-menu, halo, dimming or pixel-shift presentation that
has no live destination-independent responsibility.

Preserve Python semantic command/settings authority and neutral configuration/runtime logic; delete only superseded
pixel/presentation ownership.

## Unrelated focused-test debt

- Reddit helper recovery/installer/watcher tests contain stale helper-era expectations; reconcile separately from the
  retained Reddit presentation.
- Three physical two-display `tests/test_qtquick_runtime.py` smoke cases can miss only the second screen's 250 ms
  crossfade-midpoint capture while transition/retirement otherwise complete. Treat as focused smoke-oracle debt, not a
  visualizer viewport blocker.

## Settings GUI residue

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
compositor/card/overlay pixels. The core G4 viewport-edge feature is landed; do not mistake the current bounded viewport
ownership/Bubble spatial corrections for legacy cleanup.

## Phase G

Before G closes:

- complete the bounded post-checkpoint G4 viewport ownership/Bubble spatial corrections while preserving the landed all-five-mode edge-resize architecture;
- close G7 auxiliary/context caller proof and retire superseded old pixels;
- complete G8 MC/focus gates;
- no old QWidget edit/grid/auxiliary presentation remains as a destination fallback.

## Phase H

H wires final Quick production orchestration and removes the remaining physical presentation: `DisplayWidget`,
QRhiWidget/`GLCompositorWidget`, old compositor scheduling/presentation glue, software/backend-demotion fallback,
render-backend selection used only by that fallback, obsolete `hw_accel`/fallback-overlay policy, remaining
physical-host transition/visualizer debris, temporary legacy anchors and obsolete presentation compatibility settings.

No production switch back. H does not preserve a functional old app for handoff aesthetics.

## Phase I

I should be small: expired adapters, compatibility aliases, stale old-presenter utilities, obsolete tests/tools/comments
and abandoned spike code. Preserve product-neutral logic, diagnostics and resilience.

## Phase J

Archive/remove migration-only harnesses/planning material only after final compiled/installed/physical validation
evidence exists.
