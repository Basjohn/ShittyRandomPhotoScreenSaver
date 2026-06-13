# Current Plan

Last updated: 2026-06-13

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

There are no active visualizer blockers at the moment. Keep this file minimal until the next concrete runtime issue or priority is chosen.

## Guardrails

- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. This is not a changelog.
- Keep harnesses/probes that materially improve diagnosis quality.
- Use relevant CLI families for new logging. Geometry logging belongs behind `--geo`.
- Prefer automation bars over repeated runtime-verification asks.
- Do not close visual/runtime bugs from polite unit doubles alone.
- Treat `presets/visualizer_modes/` as authored content; validate schema/index/repair behavior without forcing creative payload values.
- CUSTOM widgets are outside authored stacking for that runtime/layout pass.
- Gmail/Reddit may adjust height for visible count/cache/dead-space QoL, but no widget gets width authority from that path.

## Active Tasks

- No active tasks currently remain.

## Watchlist

- Spectrum solid-bar visual hysteresis is close enough to close for now:
  - the new display-only seam removed the earlier flicker/judder without reintroducing obvious stale behavior in the latest run
  - a small amount of second-song blockiness remains watchlist material, not active work
  - if Spectrum complaints return, keep the fix scoped to the solid-bar display seam rather than reopening shared audio/floor logic first
- Non-`Custom` authored stacking stays default-off until a future re-audit proves it against real authored layouts plus `--geo`.
- Bubble work is closed for now, but future changes should still preserve mode isolation:
  - shared floor/support behavior may remain the neutral baseline
  - Bubble-specific rescue logic belongs to Bubble-owned seams if Spectrum is already healthy
- Bubble transition spikes are currently treated as non-sticky perf watch items, not active blockers:
  - the `23:39:57` spike / latency burst completed cleanly and did not leave `waiting_engine`, `waiting_frame`, or transition-running drift behind in the following windows
  - keep a regression eye on long-lived staleness, not one-off transition spikes by themselves

- If transition watchdog/compositor-complete failures reappear under `--perf`, inspect `rendering/gl_profiler.py` and `rendering/gl_compositor.py` before treating it as a generic transition regression.

## Deferred / Not Active

- Reddit fetch, cooldown, identity, and API work stays deferred until the ban/API situation changes.
- Display 0 cadence re-validation stays deferred until it becomes a real runtime priority again.
- Bubble baseline, paused/idle startup, and same-track churn safety checks stay deferred unless a fresh Bubble complaint reopens them.
- Startup update-policy observability and image-cache/prescale perf follow after the interactive geometry/audio blockers.
- Multi-display compositor/desync/startup-order validation stays deferred unless directly needed for the active Display 0 cadence regression.
- Secure-desktop long-runtime exit reliability stays deferred until the current interactive blockers stop dominating validation time.
- Future authored runtime oracles for Spline Curve `Preset 1` should follow the stronger Bubble bar pattern.
- Rain Drops / Blinds cleanup stays deferred unless current runtime evidence shows active user harm.

## Documentation Rule

- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
No unintegrated user tasks currently remain in this box.
----
######
