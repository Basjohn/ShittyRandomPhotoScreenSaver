# Current Plan

Last updated: 2026-06-12

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

The current top-priority work is Bubble mode consistency: tighten the runtime-shaped oracle around the real loud-passage failure and investigate Bubble-owned seams without destabilizing the now-good Spectrum path.

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

### 1. Rebuild Bubble investigation around mode-specific seams, not another shared-floor rewrite

- [ ] Treat Spectrum as the protected good path for this pass.
  - Keep the current Spectrum reactivity baseline as a regression guard:
    - strong reactivity
    - no visible jitter
    - fluid larger reactions in louder passages
  - Do not broaden Bubble fixes back into the shared floor contract unless Bubble-owned seams are ruled out by evidence.
- [ ] Turn the recent live runs into a harsher Bubble oracle before more runtime asks.
  - Preserve the known failure shape from the older hot windows:
    - soft passages can look more expressive than louder passages
    - small bubbles can die while the hero lane survives, flatlines, or clamps
    - support/floor can stay elevated while visible Bubble output still underreacts
  - Capture the newest soft-track caveat explicitly:
    - the latest log is not a closure signal because the whole song stayed generally soft
    - Bubble looking healthy on this run must not weaken the loud-passage oracle
  - Record the newest late-run hot evidence in the same structure as the older windows:
    - `22:30:11 .. 22:30:56` shows the same low-reaction family even with `raw_bass` repeatedly near or above `1.0`
    - this window is especially important because it is a manual-floor run (`gate=manual=0.200`, `support=0.000`)
    - treat that as evidence against blaming the remaining failure only on shared dynamic-floor/support-pressure behavior
  - Use the existing hot evidence sets as primary anchors:
    - `14:31:54 .. 14:32:04`
    - `15:52:06 .. 15:52:31`
    - `22:30:11 .. 22:30:56`
    - the runtime-loud replay/profile bars already in the suite
- [ ] Investigate Bubble-owned runtime seams in this order.
  - Bubble continuous feed / dispatch:
    - check whether `get_bubble_energy_bands()` still compresses loud variance too early even when support pressure is healthy
    - confirm Bubble-specific feed behavior is evaluated separately from Spectrum/shared control lanes
  - Bubble simulation and visible sizing:
    - inspect hero-lane size/clamp behavior, small-lane survival, and any state that makes loud passages converge toward one visible shape
    - verify whether pulse/size/clamp paths help one lane while starving the other
  - Bubble oracle realism:
    - tighten bars against the exact user-visible failure shape rather than helper/proxy success
    - prefer runtime-shaped replay/profile checks over friendly synthetic-only phrases
- [ ] Keep the output actionable.
  - identify whether the inconsistency is primarily:
    - Bubble feed compression
    - Bubble simulation/render sizing/clamp behavior
    - oracle weakness
  - only after that should a Bubble code change be proposed

## Watchlist

- Non-`Custom` authored stacking stays default-off until a future re-audit proves it against real authored layouts plus `--geo`.
- Bubble work must preserve mode isolation:
  - shared floor/support behavior may remain the neutral baseline
  - Bubble-specific rescue logic belongs to Bubble-owned seams if Spectrum is already healthy

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
