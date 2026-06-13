# Current Plan

Last updated: 2026-06-13

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

The current top-priority work is Bubble mode consistency: keep the now-stronger loud-path oracle honest against real songs and only continue tuning Bubble-owned seams when fresh evidence shows a failure the current bars do not yet model.

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

### 1. Keep Bubble loud-path work evidence-first and Bubble-owned

- [ ] Keep Spectrum protected while Bubble continues moving.
  - Preserve the current Spectrum regression guards:
    - strong reactivity
    - no visible jitter
    - fluid larger reactions in louder passages
  - Do not reopen shared floor semantics unless a new failure clearly escapes Bubble-owned seams.
- [ ] Keep the Bubble oracle harsher than runtime complaints, not friendlier.
  - Preserve the existing loud-path families:
    - soft passages must not look more expressive overall than louder passages
    - the small lane must stay alive in loud holds
    - the hero lane must not flatline, clamp-pin, or collapse into one narrow shape
  - Preserve the newer crest-vs-bed rule:
    - kick/crest moments inside an already-hot section must still step up above the surrounding loud bed
    - the hero lane may step up more than the small lane, but not by killing the small lane
  - Keep the loud-hold contract perceptual:
    - a loud bed must stay clearly alive
    - it does not need to counterfeit the exact same size/pulse shape as a sharper crest hit
- [ ] Use fresh runtime logs to decide whether another Bubble tuning pass is warranted.
  - If a new song still shows missed loud beats or another inconsistent hot-window family, add that exact failure to the replay/fixture bar set before more tuning.
  - Prefer Bubble-owned seams in this order:
    - continuous feed / dispatch ranking inside hot sections
    - BubbleSimulation pulse/size conversion
    - only then additional oracle expansion if runtime still escapes the suite

## Watchlist

- Non-`Custom` authored stacking stays default-off until a future re-audit proves it against real authored layouts plus `--geo`.
- Bubble work must preserve mode isolation:
  - shared floor/support behavior may remain the neutral baseline
  - Bubble-specific rescue logic belongs to Bubble-owned seams if Spectrum is already healthy
- Bubble transition spikes are currently treated as non-sticky perf watch items, not active Bubble blockers:
  - the `23:39:57` spike / latency burst completed cleanly and did not leave `waiting_engine`, `waiting_frame`, or transition-running drift behind in the following Bubble windows
  - keep a regression eye on long-lived staleness, not one-off transition spikes by themselves

- If transition watchdog/compositor-complete failures reappear under `--perf`, inspect `rendering/gl_profiler.py` and `rendering/gl_compositor.py` before treating it as a generic transition regression.

## Deferred / Not Active

- Reddit fetch, cooldown, identity, and API work stays deferred until the ban/API situation changes.
- Display 0 cadence re-validation stays deferred until Bubble loud-path investigation stops dominating validation time.
- Bubble baseline, paused/idle startup, and same-track churn safety checks stay deferred behind the current loud-path/oracle blocker.
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
