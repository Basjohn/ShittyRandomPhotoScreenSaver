# R-25 — 2026-06-13 — Spectrum Solid-Bar Boundary Flicker / Robotic Snap Follow-Up (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** Solid-bar Spectrum no longer falls into the earlier 1-segment jitter/judder pattern, and the follow-up display seam now avoids the robotic frozen-block look that appeared in the first hysteresis pass. The latest runtime logs stayed clean of reset poison or first-frame churn specific to this work, and live feedback moved the issue from active bug to minor watchlist-level blockiness on one later song.
- **Observed failure pattern:**
  - before the fix, solid bars could visibly chatter by one segment up and down in rapid succession even while the underlying continuous Spectrum signal looked healthy
  - the first anti-flicker pass solved the chatter but made the body look too snapped and robotic because each accepted segment was rendered as one frozen display height
- **Root cause family:**
  1. The actual bug was visual boundary chatter in the solid-bar display contract, not a shared audio/FFT/floor problem.
  2. A hard segment-lock output solved the chatter but over-quantized the rendered body, removing too much intra-segment motion and making the result feel artificial.
- **What finally worked:**
  - moved the fix into a dedicated display-only helper at `widgets/spotify_visualizer/spectrum_solid_hysteresis.py`
  - kept asymmetric segment acceptance rules for solid Spectrum only:
    - `+2` segments required to rise immediately
    - `-2` segments fall immediately
    - persistent `-1` segment drops release after a short visual dwell
  - changed the visible output from "snap to one accepted segment value" into "clamp the continuous bar inside the currently accepted segment band" so the bar can still breathe without crossing back and forth over the boundary every frame
  - reset the state cleanly on mode/reset/segment-count changes through the overlay state seam
- **Why the final solution worked:**
  - it addressed the real seam: post-audio display quantization for `spectrum` + `single_piece`
  - it preserved audio/reactivity behavior while only changing how the body is visually admitted across segment boundaries
  - it avoided reopening shared beat-engine or dynamic-floor logic for a problem the logs did not support
- **Closure evidence worth preserving:**
  - focused bars now cover:
    - 1-step boundary chatter hold
    - true `+2` rise acceptance
    - true `-2` fall acceptance
    - `-1` dwell release
    - reset/segment-count hygiene
    - preserved intra-band motion inside an accepted segment
  - the latest `--viz` runtime log stayed free of repeated `MODE_RESET_ASSERT` / `FIRST_FRAME_GUARD` churn during the solid Spectrum pass
  - the only remaining note from runtime was a small amount of second-song blockiness, treated as acceptable watchlist material rather than an active blocker
- **Takeaways:**
  - if solid Spectrum flicker returns, investigate the display quantization seam first, not shared audio smoothing
  - suppressing segment chatter by freezing the body to one snapped value is too coarse; preserve continuous motion inside the accepted segment band
  - keep future fixes scoped to `single_piece` unless logs prove segmented Spectrum shares the same visible failure shape
- **2026-07-14 rare-dropout follow-up:** around 09:46 the solid Spectrum input/support coherently fell to zero and recovered, while around 10:41 the overlay continued near 99 FPS through isolated 47-76 ms tick gaps. There was no mode reset, smoothing bypass, paint starvation, or shared-audio tuning change. The display-only helper now holds only brief coherent-zero frames and caps one-frame smoothing catch-up after a stall; focused solid-Spectrum tests and the 17-test current-good visualizer lock pass. Runtime confirmation remains in `Current_Plan.md`; do not use this narrow follow-up to justify the deferred shared wall-time-to-monotonic migration.

## Record Provenance

This standalone file preserves the complete former inline `R-25` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
