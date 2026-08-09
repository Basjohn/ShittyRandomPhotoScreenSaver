# U-08 — 2026-06-06 / 2026-06-12 — CUSTOM Runtime Replay Shrink Failure / Minimum-Constraint Reassertion Drift (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** CUSTOM geometry now closes cleanly across the edited widget family. Edit-mode shells and runtime replay agree on the committed rect, repeated visualizer save/re-enter churn keeps the intended aspect ratio instead of slowly squaring off, and the changed widgets in the latest `--geo` run replay back onto their saved rects.
- **Observed failure pattern:**
  - shrinking `reddit`, `reddit2`, `gmail`, `weather`, `media`, and sometimes `spotify_visualizer` from their default sizes makes post-save runtime replay far more likely to widen, overlap, or otherwise ignore the previewed shell
  - enlarging tends to survive more often, which made several geometry theories look plausible even while the real runtime contract was still broken
  - disabling authored stacking did not remove the failures, proving the overlap family was larger than stack planning alone
- **Root cause family currently identified:**
  1. Several overlays are constructed with large authored/default minimum sizes before `_custom_layout_local_rect` is attached at runtime replay.
  2. Later CUSTOM replay tried to `setGeometry(...)` to a smaller saved rect, but Qt still honored those earlier minimum constraints, so the widget could not actually shrink to the saved outer size.
  3. Earlier tests missed this because they mostly used plain QWidget doubles without real BaseOverlayWidget minimum-size behavior, so replay looked correct in tests while the real widgets stayed too large.
  4. Stacking noise obscured this by creating extra overlaps, but it was not the only or main cause once the user disabled stacking and the failures remained.
- **Failed investigation patterns worth preserving:**
  - treating post-save overlap as primarily a stacking planner issue
  - fixing only widget-local geometry mutators while leaving pre-existing minimum constraints alive
  - relying on polite test doubles that never start with large authored minimum widths/heights
  - assuming "reassert the saved rect after payload apply" was sufficient even when Qt was still enforcing bigger minimum sizes created earlier in startup
- **What changed once the real seam was identified:**
  - CUSTOM replay now explicitly locks BaseOverlayWidget min/max width/height to the committed saved rect once `_custom_layout_local_rect` becomes active
  - clearing CUSTOM replay restores the prior authored min/max constraints
  - focused regression tests now include hostile shrink cases where a widget starts with larger authored minimums and must still land on the smaller committed CUSTOM rect
  - full CUSTOM runtime reload now refreshes the in-memory settings snapshot before display recreation, and geometry-critical runtime seams were moved onto `get_widgets_map()` instead of ad hoc `get('widgets', ...)` calls so stale widget-route snapshots cannot keep reintroducing authored geometry after the saved file is already correct
  - visualizer CUSTOM resize/save stopped persisting a moving mode/media-relative scale payload and now persists absolute committed `width` / `height`, so repeated save/re-enter churn cannot silently rebase onto the current authored envelope and drift toward a square card
- **Closure evidence worth preserving:**
  - the latest visualizer resize chain held near-constant aspect ratio through heavy churn: `390x260`, `195x130`, `565x377`, `763x509`, `496x331`, `422x281`, `274x183`, `397x265`
  - those sizes stayed clustered around a `1.5` ratio instead of drifting toward the old square failure shape
  - the same run also replayed the changed widgets back to their saved rects in `replay_final`, including `spotify_visualizer (397x265)`, `media (390x187)`, `gmail (480x198)`, `weather (600x249)`, `reddit (600x679)`, `reddit2 (600x619)`, and `spotify_volume (32x279)`
- **Remaining lesson / guardrail:**
  - whenever a CUSTOM geometry bug is "much worse when shrinking than enlarging", audit pre-existing minimum/maximum size constraints before blaming stacking, normalized rect math, or edit-shell preview
  - if logs prove the saved settings file is correct while runtime still behaves as if widgets are authored/default-sized, treat stale in-memory widget snapshots as a first-class suspect and re-audit any geometry ownership checks that still gate on route/config state instead of an active committed custom rect
  - if visualizer replay stays green but saved `HxW` slowly drifts over many edit/save cycles, the next suspect is resize-baseline rebasing rather than ordinary replay parity

## Record Provenance

This standalone file preserves the complete former inline `U-08` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
