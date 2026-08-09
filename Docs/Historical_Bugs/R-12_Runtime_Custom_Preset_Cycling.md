# R-12 — 2026-04-09 — Runtime Custom Slot Replaced While Cycling Presets (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- In live runtime, cycling away from `Custom` and eventually back to `Custom` could replace the user's hand-tuned settings with a different preset payload instead of restoring the real Custom state.
- In the reported Spectrum case, the replaced payload appeared to match the most recently viewed curated preset before returning to `Custom`.
- The overwrite did not require `Move To Custom`; simple runtime preset stepping was enough to corrupt what `Custom` represented for that mode.

**Root Cause**
1. The settings-dialog path already had a `leave Custom -> snapshot live payload -> return to Custom -> restore cached payload` rule.
2. The runtime path (`WidgetManager.cycle_visualizer_preset`) did not honor that same rule. It advanced preset indices and applied curated payloads, but it did not snapshot the outgoing `Custom` payload or restore the cached one on re-entry.
3. Because runtime cycling is settings-backed and non-UI, the active `spotify_visualizer` config could end up carrying the last curated payload when the preset index wrapped back to `Custom`.

**Fixes**
- Shared Custom snapshot helpers now live in `core/settings/visualizer_presets.py` so the contract is not duplicated differently in separate callers.
- `ui/tabs/widgets_tab.py` and `rendering/widget_manager.py` now both use that shared snapshot/restore path, which keeps the settings UI and runtime manager aligned.
- Runtime regression coverage was added in `tests/test_visualizer_preset_cycling_runtime.py` for the exact `Custom -> curated -> Custom` round-trip through `WidgetManager`.

**Status**
- Resolved in code and covered by focused runtime regression tests.
- Keep an eye on live reports across all modes, because the symptom had been remembered as intermittent and cross-mode rather than Spectrum-only.

**Takeaways**
- `Custom` is not just another preset index; it is a live user-owned snapshot that must be preserved consistently across UI and runtime code paths.
- If the same workflow exists in settings UI and runtime interaction, both paths need to share the same helper/contract instead of re-implementing it separately.

## Record Provenance

This standalone file preserves the complete former inline `R-12` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
