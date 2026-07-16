# Logging Guide

Last updated: 2026-07-16

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
| `--usage` | `screensaver_usage.log` | Low-cadence whole-process plus child CPU, memory, thread/handle/IO, ThreadManager throughput, ResourceManager/GL registration, GPU, VRAM, and sampler-cost telemetry. Collection is non-overlapping and worker-owned. |
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
  - `--viz --perf --usage`
- Startup/teardown/recreation regressions:
  - `--life --geo`
- Cache/prefetch/prescale investigations:
  - `--perf --cache --usage`
- Steam widget family investigations:
  - `--steam --cache --set`
  - Add `--devsteam` only when investigating Steam Journey, Friend Pulse, or Abandonment Issues prototypes.

## Perf Semantics
- Transition-scoped perf warnings should describe active-cadence problems, not intentional idle time.
- Recurring-timer `Large gap` warnings are meant for unexpected steady-runtime cadence loss; if a widget intentionally hands cadence to a different owner during transitions, the resumed dedicated timer should not be treated as a catastrophic gap by itself.
- Compositor `Paint gap` warnings are transition-paint diagnostics. Once a transition has completed and the compositor is intentionally idle/paused, later base-frame paints should not inherit the old transition label.
- Visualizer latency is playback-authority-aware. Runtime source logging suppresses paused/non-playing latency, including forced transition probes. When parsing older logs, `Paused forced-probe latency diagnostics` are retained as historical diagnostics but excluded from significant/severe live-audio failures; a matching playing probe remains severe.
- Spotify visualizer `[MICROGAP]` records are `--perf`-only ten-second summaries. They use preallocated fixed buckets to report paint-gap p95/max and oldest accepted-update-to-paint p95/max by owning screen and `transition_active`, `just_ended`, `mode_handoff`, or `steady_idle` context. `pending_wait_ms` means the oldest accepted `update()` request had still not reached `paintGL()` when the summary was emitted; the probe does not request another paint or query GL.
- Slow GL upload records may include `direct=True/False`. `direct=True` means the mapped-PBO stage consumed the exact converted `QImage` buffer without a second Python full-frame copy. It does not mean UI-side `QPixmap.toImage()/convertToFormat()` has been removed.
- Cache fallback context includes `streamed_raw`. A positive value means an oversized raw decode is intentionally retained only by planned scaled consumers; it is a valid producer state, not an LRU entry or missing-producer fallback.
- Transition correctness counters are fail-loud health signals. `Transition start refusals`, `Transition instant commits`, `Transition request drops`, and `GL program lifecycle errors` should all remain zero; an abrupt destination commit is not an acceptable fallback for a transition that could not start.
- Canonical merged health command:
  - `python tools/transition_perf_health_parser.py --log logs/screensaver_perf.log --usage-log logs/screensaver_usage.log --extra-log logs/screensaver_cache.log --extra-log logs/screensaver_spotify_vis.log --timeline`

## Guardrails
- Do not reintroduce environment-variable activation for diagnostic families.
- Do not let sidecar filters hide warnings/errors from the general logs.
- If a new high-volume family is added, give it:
  - one explicit CLI flag,
  - one dedicated log file,
  - one documented correlation rule,
  - and one suppression path from general INFO/DEBUG only when active.
