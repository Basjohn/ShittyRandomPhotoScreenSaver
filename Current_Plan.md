# Current Plan

Last updated: 2026-06-12

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

The current top-priority work is Dynamic Volume Floor assessment and oracle strengthening from the latest live runs.

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

### 1. Assess Dynamic Volume Floor from the recent live run

- [ ] Turn the recent live run into a stronger oracle before more runtime asks.
  - Capture the good Spectrum window as a positive bar:
    - strong reactivity
    - no visible jitter
    - fluid larger reactions in louder passages
  - Capture the Bubble weakness as a failure bar:
    - soft passages react well
    - some louder passages still collapse into dead/small bubbles even while the floor remains elevated
    - use the logged `14:31:54 .. 14:32:04` Bubble floor/bar windows as the initial evidence set
- [ ] Re-audit Dynamic Volume Floor for contract clarity.
  - Prefer reliable reactivity across quiet, dense, loud, bass-heavy, and vocal-forward tracks.
  - Do not lean on jitter as a substitute for responsiveness.
  - Use live-run evidence to improve the synthetic inputs/oracles instead of relying on synthetic-only tuning.
- [ ] Keep the outcome actionable:
  - identify weak seams in dynamic floor, adaptive sensitivity, and any loud-passage collapse path
  - define bars that fail when Bubble goes visually dead in loud passages or when Spectrum regresses into jitter

## Watchlist

- Non-`Custom` authored stacking stays default-off until a future re-audit proves it against real authored layouts plus `--geo`.

- If transition watchdog/compositor-complete failures reappear under `--perf`, inspect `rendering/gl_profiler.py` and `rendering/gl_compositor.py` before treating it as a generic transition regression.

## Deferred / Not Active

- Reddit fetch, cooldown, identity, and API work stays deferred until the ban/API situation changes.
- Display 0 cadence re-validation stays deferred until Dynamic Volume Floor stops dominating validation time.
- Bubble baseline, paused/idle startup, and same-track churn safety checks stay deferred behind the current Dynamic Volume Floor blocker.
- Startup update-policy observability and image-cache/prescale perf follow after the interactive geometry/audio blockers.
- Multi-display compositor/desync/startup-order validation stays deferred unless directly needed for the active Display 0 cadence regression.
- Secure-desktop long-runtime exit reliability stays deferred until the current interactive blockers stop dominating validation time.
- Future authored runtime oracles for Spectrum `Preset 1 (Organs)` and Spline Curve `Preset 1` should follow the stronger Bubble bar pattern.
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
