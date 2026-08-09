# R-23 — 2026-05-24 / 2026-05-25 — CUSTOM Edit Mode Global Shell/Grid/Z-Order/Geometry Regression Family (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** CUSTOM edit mode now behaves as a stable global child-surface session across displays: no shell loss, no grid stacking/flicker, reliable context menus, smooth drag, working corner/scroll resize, and clean bounded save/revert behavior.
- **Observed failure pattern:**
  - shell widgets could disappear after cross-display moves when clicking or right-clicking a destination/source display
  - grid could flash, stack repeatedly, or appear above widgets/menu
  - right-click could be swallowed or fight the menu stack
  - drag movement felt sticky, laggy, or stalled behind the cursor, especially across display boundaries
  - some CUSTOM geometry replays and minimum-size paths leaked content outside widget/display bounds
- **Root cause family:**
  - edit mode was still behaving unlike stable normal runtime by using separate top-level tool windows plus repeated `raise_()`-style correction
  - geometry ownership was split between local child geometry and global display geometry after the shell/grid ownership shift
  - live drag was doing too much correction/snap work per move frame
- **What finally worked:**
  - moved edit shells/grid to display-owned child surfaces with explicit cross-display reparenting
  - made `EditShellWidget` speak global geometry outward and left global↔local translation solely to `CustomLayoutManager`
  - kept drag live-clamped/guide-driven and deferred hard snap-to-grid/peer snap until release
  - preserved resize through one shared widget-logical resize authority for scroll and corner drag
  - cached the static grid and no-op'd unchanged guides/transfer-state updates to improve drag smoothness
  - fixed Gmail small-height content clipping so constrained CUSTOM cards truncate instead of leaking below the card
- **Why the final solution worked:**
  - the fix aligned edit mode with the normal display-owned runtime model instead of layering more top-level z-order tricks
  - geometry and display ownership became single-authority again
  - hot-path repaint/update work was reduced enough for drag to feel fluid
- **Useful diagnostics from this rollout:**
  - `--geo` and `--life` sidecars plus targeted `[ZORDER]` traces were materially better than the old mixed verbose-only approach
  - runtime validation remained essential; several intermediate “theory fixes” passed tests but failed the actual edit session feel
- **Takeaways:**
  - edit-mode surfaces should follow normal runtime ownership where possible
  - do not let shell widgets emit local-parent geometry into a global layout contract
  - drag feel is part of correctness for this feature family, not polish

## Record Provenance

This standalone file preserves the complete former inline `R-23` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
