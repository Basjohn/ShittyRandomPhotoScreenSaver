# Logging Guide

Last updated: 2026-08-08

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
- Fallbacks should stay loud at `WARNING` or higher and, when possible, carry the owning family tag too:
  - `"[CACHE] [FALLBACK] ..."`
  - `"[LIFECYCLE][FALLBACK] ..."`
  - `"[REFRESH_DIAG][FALLBACK] ..."`
  - `"[CUSTOM_LAYOUT][FALLBACK] ..."`
  - `"[SPOTIFY_VIS][FALLBACK] ..."`
- Cache worker/compute fallback paths are diagnostic events, not routine cache hits; keep them `WARNING` plus `[FALLBACK]` while leaving normal cache hit/miss telemetry at INFO in `--cache`.

## Specific Sidecar Logs

| CLI flag | File(s) | Purpose |
|---|---|---|
| `--perf` | `screensaver_perf.log`, `perf_widgets.log` | Performance telemetry, GC/perf probes, widget timing summaries. |
| `--usage` | `screensaver_usage.log` | Low-cadence whole-application CPU, main/child/total RSS, private commit, handles/threads, driver GPU/VRAM, shared-memory, task, and aggregate owner bytes. |
| `--viz` | `screensaver_spotify_vis.log`, `screensaver_spotify_vol.log` | Visualizer and volume diagnostics. `--viz` also enables visualizer diagnostics. |
| `--geo` | `screensaver_geometry.log` | Geometry, z-order, CUSTOM layout, and display-stack diagnostics. |
| `--set` | `screensaver_settings.log` | Settings mutations, imports, schema normalization, and settings-binding traces. |
| `--life` | `screensaver_lifecycle.log` | Widget, worker, and engine lifecycle/setup/teardown diagnostics. |
| `--cache` | `screensaver_cache.log` | Image-cache authority, prefetch targeting, scaled warmup, and worker-fallback classification traces. |
| `--steam` | `screensaver_steam.log` | Steam provider/cache/widget diagnostics for public Achievement Pulse and the unfinished card prototypes. |

Legacy compatibility:
- `--viz-diagnostics` and `--viz-diag` remain accepted aliases for extra visualizer diagnostics, but `--viz` is the preferred operator flag.

## CLI Rules
- Use CLI flags, not environment variables, to activate diagnostic families.
- Diagnostic family flags are intentionally composable. Example:
  - `python main.py --debug --geo --life`
  - `python main.py --perf --viz`
  - `python main.py --perf --cache`
  - `python main.py --steam --cache`
- `--fresh` means a genuinely clean slate for the resolved runtime log directory:
  all existing log files there are deleted before the new launch starts logging.
- Startup logs should advertise both:
  - the available specific logs
  - the specific logs active for the current run
- Each launch emits one bounded `[STARTUP]` identity record with
  `entrypoint=main|main_mc`, parsed mode, frozen/script state, and executable
  basename. Use it instead of inferring Media Center from later window flags.
- Move To Custom emits one bounded `[VIS_PRESETS]` INFO record with mode,
  source preset index/name, and destination Custom index. It deliberately does
  not serialize the complete settings payload.

## Installable Diagnostic Runtime

Normal standard and Media Center packaged launches remain logging-off. The
separate `SRPSS_Diagnostic.exe` product automatically activates every
registered logging family and writes by default to:

```text
<directory containing SRPSS_Diagnostic.exe>\logs
```

If that directory is not writable, every runtime log, sidecar, crash trace,
fresh-log operation, and profiling artefact uses
`%LOCALAPPDATA%\SRPSS\Diagnostic\logs`, then
`%TEMP%\SRPSS\Diagnostic\logs`. Build logs remain in the Foundry build-log
directory and never mix with runtime evidence.

The main and sidecar handlers rotate at 1 MiB with at most five backups per
file; the verbose stream retains three backups. `diagnostic_crash.log` rotates
live breadcrumbs/Python tracebacks at the same bound and records eagerly
flushed Settings/native-window stages. A terminal faulthandler write captures
only the failing thread; if that final raw write crosses the active-file bound,
the next diagnostic launch trims it before retaining the bounded backup. It
contains no settings payloads.

The diagnostic installer is per-user, has a distinct AppId and install tree,
does not replace/register `SRPSS.scr`, and does not alter the Media Center
payload. It also uses direct interactive URL routing and never writes helper
tickets/queue entries or starts the shared secure-desktop helper. Diagnostic
runs are attribution sessions, not performance baselines. `main.py` remains
the sole performance/evidence-capture authority and Media Center never
receives an independent capture.

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
- Cache/prefetch/prescale investigations:
  - `--perf --cache`
- Settings/Edit memory/VRAM recreation investigations:
  - `--usage --life --perf --cache`
- Steam widget family investigations:
  - `--steam --cache --set`
  - Add `--devsteam` only when investigating Steam Journey, Friend Pulse, or Abandonment Issues prototypes.

## Perf Semantics
- Transition-scoped perf warnings should describe active-cadence problems, not intentional idle time.
- Recurring-timer `Large gap` warnings are meant for unexpected steady-runtime cadence loss; if a widget intentionally hands cadence to a different owner during transitions, the resumed dedicated timer should not be treated as a catastrophic gap by itself.
- Compositor `Paint gap` warnings are transition-paint diagnostics. Once a transition has completed and the compositor is intentionally idle/paused, later base-frame paints should not inherit the old transition label.
- Per-entry image-cache hit/miss/put/remove/eviction records belong to `screensaver_cache.log` when `--cache` is active. `screensaver_perf.log` retains only bounded `[PERF] [CACHE]` summaries needed for lifecycle correlation.
- Bounded ResourceManager generation/owner/creation-site records belong to `screensaver_lifecycle.log` as `[LIFECYCLE] [RESOURCE_DETAIL]`. The ordinary `[PERF] [RESOURCE]` record contains aggregate counts/bytes only and does not duplicate the resource list.
- Lifecycle snapshots reuse the latest background `--usage` totals for whole-app RSS/private commit/VRAM and state their sample age. They do not run a new driver query or inspect live Qt pixmaps, QObjects, or Qt-wrapper validity from the usage worker.
- `[SPOTIFY_VIS][BUBBLE_CADENCE]` distinguishes lane-free submissions from `worker_busy_deferrals` and `result_waiting_deferrals`. It is passive accounting, not a task-rate controller; a low publish ratio must be explained by an existing owner, never an artificial cadence token.
- `[PERF] [IMAGE_UI_DELAY]` identifies delayed image-pipeline UI work by reason,
  display, nested callable, scheduled delay, due lateness, runtime-identity
  guard duration, actual callback duration, monotonic start/end bounds, total
  age, generation, and outcome. Stale callbacks report zero callback cost.
  `[PERF] [IMAGE_UI_SEGMENT]` separately times GUI `QImage→QPixmap` conversion
  and display image application. These records are attribution only; they do
  not alter the existing display stagger.

## Guardrails
- Do not reintroduce environment-variable activation for diagnostic families.
- Do not let sidecar filters hide warnings/errors from the general logs.
- Do not activate the diagnostic build profile from the standard or Media
  Center entry points, installers, or workers.
- If a new high-volume family is added, give it:
  - one explicit CLI flag,
  - one dedicated log file,
  - one documented correlation rule,
  - and one suppression path from general INFO/DEBUG only when active.
