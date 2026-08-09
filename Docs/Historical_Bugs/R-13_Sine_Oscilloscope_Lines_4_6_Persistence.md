# R-13 — 2026-04-13 — Visualizer Sine/Oscilloscope Lines 4-6 Settings Never Persisted (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

Cross-mode settings loss had been ongoing since lines 4-6 were added. User-visible symptoms: editing Line 4 color/glow/shift → entering runtime → returning to settings → all Line 4-6 changes reverted to defaults. Affected both Sine and Oscilloscope modes identically.

**What finally worked:** Two layered bugs needed to be fixed together.

**BUG #6 — Cross-mode save wipe (fixed 2026-07-25):**
`_save_settings_now()` in `ui/tabs/widgets_tab.py` replaced the entire `widgets.spotify_visualizer` dict with freshly-collected data that only contained shared + active-mode keys. Every save wiped all inactive-mode settings. Fixed to read existing config first, merge fresh current-mode data via `.update()`, then normalize the merged result.
- **File:** `ui/tabs/widgets_tab.py`

**BUG #7 — Model serialization gap for lines 4-6 (fixed 2026-04-13, the true root cause):**
`SpotifyVisualizerSettings.from_mapping()`, `from_settings()`, and `to_dict()` in `core/settings/models.py` all read/wrote line 1-3 settings but completely omitted lines 4-6 for both Sine and Oscilloscope. The normalization pass (`normalize_visualizer_section_mapping`) round-trips through these methods, so it silently dropped all line 4-6 keys even when `collect_sine_wave_mode_settings()` correctly collected them from the UI.

Pipeline trace:
1. User edits Line 4 color → `collect_sine_wave_mode_settings()` reads it correctly ✓
2. `_save_settings_now()` merges it into existing config correctly ✓ (after BUG #6 fix)
3. `normalize_visualizer_section_mapping()` round-trips through model → line 4-6 keys silently dropped ✗
4. Normalized result written to JSON without line 4-6 → settings lost

**Secondary fix — Wiring alignment (2026-07-25):**
All 10 sine multi-line color button lambdas in `ui/tabs/media/sine_wave_builder.py` were converted from direct `color_changed.connect(lambda ...)` to `bind_color_button()` for consistency with line 1. This was not the root cause but is the canonical wiring pattern.

**Keys added to all three model methods:**
- Sine: `sine_line4/5/6_color`, `sine_line4/5/6_glow_color`, `sine_travel_line4/5/6`, `sine_line4/5/6_shift`, `sine_ghost_line4/5/6_enabled`
- Osc: `osc_line4/5/6_color`, `osc_line4/5/6_glow_color`, `osc_ghost_line4/5/6_enabled`

**Key failed methods (BUGs #1-#5 in Current_Plan.md Historical Reference):**
- BUG #1: `apply_preset_to_config()` merge overlay → correct partial fix but not root cause
- BUG #2: `save_media_settings()` collected all modes → correct fix but not root cause
- BUG #3: `.update()` left stale keys → correct fix but not root cause
- BUG #4: Technical keys lost when switching presets → correct fix but not root cause
- BUG #5: Technical keys from ALL modes leaked → correct fix but not root cause

**BUG #8 — Runtime config bridge missing lines 4-6 kwargs (fixed 2026-04-13):**
`apply_spotify_vis_model_config()` in `rendering/spotify_widget_creators.py` built the kwargs dict that feeds the runtime visualizer widget via `apply_vis_mode_config()`. It explicitly listed lines 2-3 but completely omitted lines 4-6 for both sine and osc (colors, glow colors, travel, shifts, ghost enabled). Also missing: `sine_smoothing`, `sine_glow_reactivity`, `osc_glow_reactivity`. The fallback path in `rendering/widget_manager.py` had the same gap.

This is why the GUI retained correct values (save path worked after BUGs #6+#7) but runtime showed defaults — the model→widget bridge simply never forwarded them.

**BUG #9 — Shift updaters wrote wrong attribute name + shift rows always visible (fixed 2026-04-13):**
Lines 4-6 shift `bind_setting_signal` updaters in `ui/tabs/media/sine_wave_builder.py` wrote to `_sine_lineN_horizontal_shift` instead of `_sine_lineN_shift`. Harmless for saving (collect reads slider `.value()` directly) but incorrect. All shift rows (lines 2-6) used `_aligned_row()` (untracked) instead of `_aligned_row_widget()`, so the visibility function couldn't hide them — they always displayed regardless of line count.

**BUG #10 — Overlay set_state silently dropped lines 4-6 shift and travel (fixed 2026-04-13):**
`SpotifyBarsGLOverlay.set_state()` accepted `sine_line4/5/6_shift` and `sine_travel_line4/5/6` as named parameters but the method body never assigned them to `self._sine_line4_shift` etc. The overlay attributes stayed at their `__init__` defaults (0.0 / 0) even when the entire upstream pipeline (model → widget → config_applier → tick_pipeline → extras → overlay) was passing correct values. The shader's `upload_uniforms` reads from `self._sine_line4_shift`, so lines 4-6 always rendered at shift=0 and travel=0.
- **File:** `widgets/spotify_bars_gl_overlay.py`

**Why prior fixes failed:** They addressed real secondary issues in the save/load pipeline, but none addressed the full 5-layer chain: (a) save path replacing instead of merging, (b) settings model discarding lines 4-6 during normalization, (c) the runtime config bridge never forwarding lines 4-6 to the widget, (d) the UI builder using wrong attribute names and untracked rows, and (e) the overlay `set_state` accepting parameters but never storing them.

**Takeaways:**
- When adding new per-line settings, all three serialization methods (`from_settings`, `from_mapping`, `to_dict`) must be updated in the same commit. The dataclass fields + `__post_init__` defaults are necessary but not sufficient.
- The runtime config bridge (`apply_spotify_vis_model_config`) must also be updated — it is a separate explicit kwargs list that does not auto-discover model fields.
- `SpotifyBarsGLOverlay.set_state()` accepts parameters explicitly and assigns them to `self` manually — adding a parameter to the signature does **not** mean it is stored. Every new parameter needs a corresponding `self._xxx = ...` line in the method body.
- Normalization passes that round-trip through a model will silently drop any field the model doesn't know how to serialize — this failure mode produces no errors or warnings.
- When debugging settings persistence, always test the normalization round-trip directly: feed test data into `normalize_visualizer_section_mapping` and verify the output contains all expected keys.
- UI row widgets that should conditionally hide must use `_aligned_row_widget()` (tracked) instead of `_aligned_row()` (fire-and-forget).

**Closure update (2026-04-16):**
- The issue was pruned from `current_plan.md` after user-reported runtime confirmation that the settings round-trip now appears solved in practice, not just in code/tests.
- Keep this entry because the bug was unusually sneaky: the user-facing symptom looked like one cross-mode persistence failure, but the real failure chain spanned save merge semantics, model normalization, runtime config bridging, UI builder wiring, and overlay state storage.
- Future regressions that look like "custom settings randomly reverted" should be checked against this entire chain before assuming a single save-path bug.

## Record Provenance

This standalone file preserves the complete former inline `R-13` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
