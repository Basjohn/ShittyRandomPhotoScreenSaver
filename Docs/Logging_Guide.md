# Logging Guide

Last updated: 2026-05-24

Operator-facing logging guide for SRPSS.

## Purpose
- Keep runtime diagnostics CLI-first.
- Keep noisy families in dedicated sidecar logs instead of flooding the main log.
- Make it obvious where to look first during regressions without needing repo history.

## Main Logs

| File | Purpose |
|---|---|
| `logs/screensaver.log` | General runtime log. Keeps `WARNING`/`ERROR`/`CRITICAL` from every family. |
| `logs/screensaver_verbose.log` | Full DEBUG/INFO stream for broad debugging when `--debug` or `--verbose` is active. |

Notes:
- Dedicated sidecar families suppress their routine INFO/DEBUG from the general logs only when that sidecar is active.
- Dedicated sidecars never suppress `WARNING`/`ERROR`/`CRITICAL` from the general logs.

## Specific Sidecar Logs

| CLI flag | File(s) | Purpose |
|---|---|---|
| `--perf` | `screensaver_perf.log`, `perf_widgets.log` | Performance telemetry, GC/perf probes, widget timing summaries. |
| `--viz` | `screensaver_spotify_vis.log`, `screensaver_spotify_vol.log` | Visualizer and volume diagnostics. `--viz` also enables visualizer diagnostics. |
| `--geo` | `screensaver_geometry.log` | Geometry, z-order, CUSTOM layout, and display-stack diagnostics. |
| `--set` | `screensaver_settings.log` | Settings mutations, imports, schema normalization, and settings-binding traces. |
| `--life` | `screensaver_lifecycle.log` | Widget, worker, and engine lifecycle/setup/teardown diagnostics. |

Legacy compatibility:
- `--viz-diagnostics` and `--viz-diag` remain accepted aliases for extra visualizer diagnostics, but `--viz` is the preferred operator flag.

## CLI Rules
- Use CLI flags, not environment variables, to activate diagnostic families.
- Diagnostic family flags are intentionally composable. Example:
  - `python main.py --debug --geo --life`
  - `python main.py --perf --viz`
- Startup logs should advertise both:
  - the available specific logs
  - the specific logs active for the current run

## Correlation Workflow
1. Start with `screensaver.log` for the high-level sequence and all warnings/errors.
2. If startup says a sidecar is active, go there before diving into `screensaver_verbose.log`.
3. Use timestamps to correlate across files; all runtime logs use the same wall-clock timestamp format.
4. Use `screensaver_verbose.log` only when the family sidecars and main log are still not enough.

## Recommended Pairings
- Edit-mode / CUSTOM / stacking bugs:
  - `--geo --life`
- Settings drift, restore, import, or schema issues:
  - `--set --life`
- Visualizer mode/preset/runtime issues:
  - `--viz --perf`
- Startup/teardown/recreation regressions:
  - `--life --geo`

## Guardrails
- Do not reintroduce environment-variable activation for diagnostic families.
- Do not let sidecar filters hide warnings/errors from the general logs.
- If a new high-volume family is added, give it:
  - one explicit CLI flag,
  - one dedicated log file,
  - one documented correlation rule,
  - and one suppression path from general INFO/DEBUG only when active.
