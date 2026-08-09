# A-04 — 2026-03-22 — MC Keyboard Focus / Ctrl Halo Interaction Regressions (Historical Partial Fixes Archived; superseded by [U-05](U-05_MC_Keyboard_Focus_Ctrl_Halo.md))

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [ ] AWAITING VALIDATION
- [ ] SOLVED

**Archive scope note**
- This entry records March 2026 partial improvements only.
- Current runtime truth is tracked in [U-05](U-05_MC_Keyboard_Focus_Ctrl_Halo.md); do not treat this section alone as current behavior status.

**Symptoms**
- MC hotkeys and media keys could stop working after interaction clicks.
- Ctrl-held suppression could drift across local/global/handler state.
- Cursor Halo behavior regressed around compositor interaction: it could fail to return after slight coordinate drift, and Interaction Mode clicks could make it vanish immediately.

**Failed / insufficient attempts**
1. Relying on only one Ctrl-held source was too fragile; focus/ownership drift could leave different subsystems disagreeing about whether interaction mode was active.
2. Halo behavior tied too closely to raw move events was vulnerable to compositor coordinate drift and click-driven focus churn.
3. A later "simplify it" experiment that made the top-level Halo window `WA_TransparentForMouseEvents` was a regression: clicks could escape the compositor/widget tree instead of being forwarded through the real display interaction path, which in turn worsened click swallowing and shadow-side fallout. Do not reintroduce that top-level transparent Halo path as a casual cleanup.

**Final fix**
- `display_input._ctrl_interaction_active()` now resolves Ctrl-held state across local widget state, coordinator state, deprecated global state, and handler state.
- `InputHandler.handle_ctrl_press()` explicitly marks handler-held state, so downstream guards agree even after interaction/focus churn.
- MC interaction clicks now perform a best-effort focus reclaim via `display_input._restore_mc_input_focus()`, which keeps keyboard/media support alive after clicking overlays.
- `display_input.show_ctrl_cursor_hint()` clamps small compositor drift back inside the display instead of treating it as a real out-of-bounds exit.
- `display_input.handle_mousePressEvent()` now refreshes halo visibility/activity after interactive clicks in Interaction Mode, so clicking compositor elements no longer makes the halo disappear immediately.
- `CursorHaloWidget._forward_mouse_event()` now routes button events back through the fullscreen display root so the existing interaction router, preset cycling, focus reclaim, and halo keepalive logic all run on forwarded clicks.
- Later Mar 22 follow-up: the blanket click-triggered halo keepalive / focus-reclaim calls in `display_input.handle_mousePressEvent()` were backed back out. They were well-intended, but in live use they worsened Halo visibility and click behavior instead of restoring last-commit behavior. The valuable retained parts are the multi-source Ctrl gate, display-root forwarding, and drift clamp.

**Regression coverage & validation**
- `tests/test_mc_keyboard_input.py` guards the focus reclaim path and hotkey behavior.
- `tests/test_dimming_and_interaction_fixes.py` now guards the multi-source Ctrl gate, halo drift clamp, removal of the bad generic click-keepalive path, and display-root halo forwarding contract.
- User confirmed that keys are now working again in script mode.
- Follow-up note (later Mar 22 user validation): keyboard/focus improvements held, but Cursor Halo click passthrough/hide behavior was still not fully correct. Keep treating Halo click behavior as an active issue even though the underlying keyboard-focus repair remains valuable and should not be reverted casually.

**Takeaways**
- Interaction reliability depends on focus reclaim and state agreement together; fixing only one side is not enough.
- Halo lifetime should be treated as its own interaction contract, not just a side effect of mouse-move traffic.
- Halo passthrough must preserve the real display interaction pipeline; bypassing the display root silently breaks preset cycling / keepalive behavior even when focus handling looks correct.
- Top-level transparent Halo windows are not equivalent to real compositor passthrough in this project; preserving forwarded ownership is safer than assuming Qt click-through will land on the right target.
- When a bug family only partly resolves, keep the resolved sub-contracts documented separately so later work does not accidentally unwind them while chasing the remaining visual issue.

## Record Provenance

This standalone file preserves the complete former inline `A-04` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
