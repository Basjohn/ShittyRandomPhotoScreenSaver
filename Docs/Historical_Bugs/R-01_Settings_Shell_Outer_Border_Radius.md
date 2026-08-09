# R-01 — 2026-04-09 — Settings Shell Outer Border Radius / Corner Bleed (Resolved With Caveats)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** the settings shell now uses a forged rounded outer-border paint compromise rather than true window rounding. Live validation got the bleed down to a near-imperceptible level while preserving acrylic, the custom title bar, and the existing inner styling contract.
- **What finally worked:** a paint-only border treatment in `ui/settings_dialog.py`.
  - the real acrylic top-level window remains structurally unchanged
  - the white outer border is still custom-painted in `paintEvent`
  - a darker backing stroke and a forged corner-cover path are painted under that border
  - the accepted outer-corner radius ended up as a very conservative compromise (`6.5`) rather than a visually stronger curve
- **Why the final solution worked:** it solved the correct seam.
  - it did not ask Qt/Windows to genuinely round, clip, or mask the top-level acrylic HWND
  - it did not expose any acrylic margin outside the visible shell
  - it did not touch the custom title-bar composition again
  - it kept all risk localized to a small paint-only edge treatment
- **Important caveats:**
  - this is an accepted compromise, not a mathematically perfect true rounded window edge
  - a trace amount of corner fringe may still exist on some machines/themes/compositor paths
  - pushing the radius stronger than the accepted range quickly re-enters regression territory
  - the fix is intentionally conservative to stay mixed-machine friendly and avoid reopening the much worse failures below
- **Key failed methods worth preserving:**
  - true outer-window rounding: live runtime bled all four corners and broke the top/title-bar segment
  - inset inner-shell/card illusion: exposed a sharp black acrylic strip outside the border
  - hidden-render/offscreen validation as sign-off: produced false confidence and did not match live compositor behavior
  - mask/polygon clipping and dialog-shadow paths from the older styling history: incompatible with this acrylic/translucent frameless shell family
- **Validation rule to preserve:** for this bug family, hidden render is only a paint sanity check. Live runtime on the real Windows shell is the only valid sign-off path.
- **Takeaways:**
  - keep acrylic untouched unless a future rewrite explicitly budgets for it
  - prefer forged-corner paint over true outer-window rounding for this dialog family
  - treat “almost invisible bleed with no collateral regressions” as the practical success bar here, not a quest for perfect geometry at any cost

## Record Provenance

This standalone file preserves the complete former inline `R-01` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
