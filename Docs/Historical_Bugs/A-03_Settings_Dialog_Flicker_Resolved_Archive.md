# A-03 — 2026-03-22 — Settings Dialog Flicker / Placeholder Regression (Resolved) - USER NOTE: UNRESOLVED BUT LOW PRIORITY NOW. SEE DUPLICATION OF THIS ISSUE IN THIS VERY DOCUMENT.

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Opening Settings from the screensaver/MC flow could produce a bad Windows placeholder/flicker moment while the dialog came up.
- The regression was especially visible in mixed monitor setups and became tied to the settings invocation path rather than image rendering itself.

**Failed / insufficient attempts**
1. Shield overlays and masking experiments did not solve the root problem and could add their own flicker.
2. Pure teardown-order tweaks were not enough on their own because the settings path still had visible timing gaps.
3. Early placeholder-tab work and caching helped, but were not originally considered sufficient in isolation.

**Final working state**
- The screensaver/settings handoff now uses the full lifecycle path guarded by `tests/test_s_hotkey_workflow.py`: opening Settings quiesces producers, deletes display/GL resources, and detaches the old manager before constructing the dialog.
- `SettingsDialog` builds the initial tab immediately and hydrates remaining tabs asynchronously, reducing visible construction pressure during first paint.
- Flicker-regression coverage also lives in `tests/test_flicker_fix_integration.py`, including guards around immediate fullscreen presentation and avoiding `processEvents()`-style races in transition code.

**Validation / guardrail**
- User later confirmed the settings flicker is resolved in live use.
- Keep `tests/test_s_hotkey_workflow.py` and `tests/test_flicker_fix_integration.py` as the minimum regression bar before reworking settings launch flow again.

**Takeaways**
- Do not reintroduce shield-style masking as a first response.
- Keep the settings launch path explicit and test-guarded: fully tear down the display runtime before constructing Settings, paint Settings quickly, and avoid event-loop race hacks.

## Record Provenance

This standalone file preserves the complete former inline `A-03` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
