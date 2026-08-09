# R-24 — 2026-05-25 — Retired Overlay-Effect Cache-Busting Path Still Driving Menu/Focus/Display Churn (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** the old shadow-corruption workaround no longer drives normal runtime menu/focus/display-change behavior. Overlay-effect refresh is now a narrow transient-opacity seam only.
- **Observed failure pattern:**
  - broad menu-time and focus-time invalidation paths were still toggling/recreating `QGraphicsOpacityEffect`
  - this churn survived the painted-shadow migration even though card/text/header shadows were no longer effect-owned
  - the stale path contributed to edit-mode/menu instability and left a large “cargo-cult fix” surface in place
- **Root cause:** the old multi-monitor shadow corruption mitigation was never fully retired after painter-owned shadows replaced `QGraphicsDropShadowEffect` on overlay cards.
- **What finally worked:**
  - reduced `rendering/widget_effects.py` to a repaint-only helper for widgets that currently own a live opacity fade effect
  - removed broad context-menu, input-handler, `focusInEvent`, `WM_DISPLAYCHANGE`, activation-refresh, and all-display-broadcast invalidation callers
  - kept the seam name/ownership centralized so runtime code did not splinter into new ad hoc refresh paths
- **Why the final solution worked:**
  - it matched the current architecture instead of the historical one
  - painter-owned shadows no longer needed cache busting
  - only transient opacity fades remained as legitimate live `QGraphicsOpacityEffect` owners
- **Supporting evidence from the rollout:**
  - `--geo` / `--life` sidecars stayed clean of the old menu/focus invalidation chatter
  - focused tests now prove popup/hide no longer force invalidation and that live opacity effects are refreshed without recreation
- **Takeaways:**
  - do not reintroduce broad menu/focus/display cache busting just because a visual issue “looks like” old Qt corruption
  - if a future opacity artifact appears, fix the live fade owner or backing-store issue directly

## Record Provenance

This standalone file preserves the complete former inline `R-24` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
