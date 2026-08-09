# R-06 — 2026-04-11 — Visualizer Preset Override Bug (MERGE Semantics + Cross-Mode Pollution + Call-Site MERGE) (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** All three MERGE/pollution bugs in preset loading/saving were fixed. Preset application uses CLEAR-then-APPLY at every layer, and saving only collects current-mode settings.
- **What finally worked:** Three distinct fixes across two sessions:
  1. **Loading path fix (2026-04-11):** Changed `apply_preset_to_config()` in `core/settings/visualizer_presets.py` to use CLEAR-then-APPLY pattern. Clears all mode-specific keys not present in the preset before applying the preset's settings.
  2. **Saving path fix (2026-04-11):** Modified `save_media_settings()` in `ui/tabs/widgets_tab_media.py` to only collect settings for the current visualizer mode instead of collecting from all modes.
  3. **Call-site fix (2026-04-12):** Both callers of `apply_preset_to_config` (`_on_visualizer_preset_changed` in `widgets_tab.py` and `cycle_visualizer_preset` in `widget_manager.py`) used `.update()` to merge the clean result back into the live config dict. `.update()` only adds/overwrites — it never removes stale mode-specific keys that `apply_preset_to_config` had cleared. Replaced with `restore_visualizer_snapshot()` which does proper in-place CLEAR-then-APPLY.
- **Why the final solution worked:** It addressed all three root causes:
  1. MERGE semantic inside `apply_preset_to_config`: The old `merged.update(preset_settings)` only overwrote keys present in the preset.
  2. Cross-mode pollution in saving: The old save path collected settings from ALL modes.
  3. Call-site MERGE: Even after fix #1, the callers used `.update()` to merge the returned clean dict back into the live dict, re-introducing the exact same stale-key problem at the call site.
- **Symptoms before fix:**
  - Custom settings (shaper, others) were overriding preset application
  - User got "stuck" on shaped blob even after explicitly choosing unshaped presets
  - Reset did not clear the stuck state
  - Selecting "The Mighty Blob" in settings showed selected but rendered Preset 3 behavior
  - Custom slot may not have been surviving hotswapping
  - When user saved a custom preset (e.g., Bubble Preset 4 → Custom → Save As Preset 9), the saved preset contained incorrect reactions and behavior due to pollution from other modes' default values
- **Root causes:**
  1. **BUG #1 - MERGE Semantic:** `apply_preset_to_config()` used `merged.update(preset_settings)` which only overwrote keys present in preset. Keys not in preset (e.g., `blob_shaper_enabled`) persisted from previous config.
  2. **BUG #2 - Cross-Mode Pollution:** `save_media_settings()` collected settings from ALL modes (`collect_spectrum_mode_settings()`, `collect_bubble_mode_settings()`, etc.). Inactive modes returned fallback defaults that polluted saved presets.
  3. **BUG #3 - Call-Site MERGE:** `_on_visualizer_preset_changed` and `cycle_visualizer_preset` used `vis_config.update(applied)` to merge the clean result of `apply_preset_to_config` back into the live dict. Since `.update()` only adds/overwrites, stale mode-specific keys (like `blob_shaper_enabled: true` from Custom) survived into curated presets that never declared them.
- **Affected modes:** ALL visualizer modes (Blob, Spectrum, Bubble, Sine Wave, Oscilloscope) were affected by the MERGE bugs. The pollution bug affected any user who saved custom presets.

- **Verification:** 11 cycling tests pass (including 2 new regression tests for Bug #3), 295 broader tests pass. Manual verification confirms no cross-mode pollution.
- **Defense in depth:** All three layers are now fixed:
  1. Loading: `apply_preset_to_config` clears mode-specific keys before applying presets
  2. Call sites: Use `restore_visualizer_snapshot()` instead of `.update()` for proper CLEAR-then-APPLY
  3. Saving: Only collects current mode settings (prevents cross-mode pollution)
  4. Export: `extract_visualizer_snapshot()` filters to only mode-specific keys
- **Takeaways:**
  - Preset application must use REPLACE semantics at EVERY layer, not just inside the config builder — callers that merge the result back must also purge stale keys
  - `.update()` is never safe for applying preset results because it only adds; it cannot remove
  - Preset saving should be mode-scoped, not mode-agnostic
  - The normalization layer is defense-in-depth but should not be relied on as the primary guard
  - Users who saved custom presets during the buggy period may need to re-save them to remove pollution
- **Documentation:** Full investigation retained in `Docs/Visualizer_Preset_Override_Bug_Investigation.md`

## Record Provenance

This standalone file preserves the complete former inline `R-06` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
