# R-07 — 2026-03-28 — Startup Fade / Visualizer Secondary-Stage Ownership Split (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Primary overlays could sit behind a compositor-only dead gap and then appear too abruptly instead of following a coordinated fade wave.
- The Spotify visualizer could enter later than before but still in a bad state: jittery first frames, fallback-timer reveal, and occasional startup-side audio restart noise.
- Cold start, mode-cycle recovery, and settings-return recovery could behave differently, which pointed to orchestration drift rather than one isolated renderer bug.

**Root Cause**
- `WidgetManager` / `FadeCoordinator` were the real owners of primary fade state, but Spotify secondary-stage timing still depended on display-local fade/runtime fields.
- That split let coordinator logs look healthy while the live visualizer still followed a different runtime schedule.
- Shared fade behavior also had helper-level leaks: some widgets waited for the first animation tick to become visible, and several callers carried timing literals that were not actually authoritative.

**Fixes**
- Moved Spotify secondary-stage scheduling back under manager-owned control, with display-local fields treated as mirrored readable state rather than a second source of truth.
- Removed the old primary startup dead-gap and fixed the shared fade helper so widgets can become visible immediately at opacity `0.0`.
- Centralized startup contracts into:
  - `rendering/overlay_startup_policy.py` for display-side startup timing
  - `widgets/spotify_visualizer/startup_contract.py` for visualizer staged-startup state
- Delayed visualizer hot-start/reveal behind the centralized Spotify secondary stage, seeded from anchor/media state, and prewarmed shader/overlay work while hidden.
- Blocked the delayed-play startup branch from revealing via fallback before real playback becomes live.
- Restored proper duration-override forwarding so shared fade timing is real policy, not decorative literals.

**Validation**
- Latest user-validated runs covered all three comparison paths:
  - cold start with music already playing
  - full mode cycle back to Spectrum
  - settings open/close and return
- In those runs:
  - primary fade begins at compositor-ready
  - the visualizer reveals through `fresh_frame_ready_delay`, not `fallback_timer`
  - `Audio capture unhealthy, restarting...` no longer appears during startup
  - startup behavior now matches the healthier recovery paths closely enough to close the bug

**Takeaways**
- Keep shared fade ownership centralized. Do not reintroduce display-local scheduling logic that can diverge from manager/coordinator state.
- Prefer narrow mirrored runtime-readable state over duplicate decision-making state.
- If startup needs more polish later, tune it from the shared fade/startup contracts instead of adding visualizer-specific timing hacks.
- Occasional future fade-softness polish is a separate UX tuning topic, not a reason to reopen this resolved startup bug unless the old parity failure returns.

## Record Provenance

This standalone file preserves the complete former inline `R-07` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
