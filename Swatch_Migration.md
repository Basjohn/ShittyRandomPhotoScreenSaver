# Swatch Migration Plan

Central reference for replacing legacy `QPushButton("Choose Color...")` pickers with the new `ColorSwatchButton`.

## Migration guidelines

1. **Preserve labels/layouts** – keep the existing `QLabel` descriptions (or add stacked labels where missing). Do not embed text in the swatch itself.
2. **Signal wiring** – prefer connecting `ColorSwatchButton.color_changed` directly to a lambda/slot that assigns the backing `QColor` attribute *and* calls `_save_settings()`. Use `auto_picker=True` so the button opens `StyledColorPicker` automatically. Only fall back to existing `_choose_*` handlers if the color logic is complex and you set `auto_picker=False`.
3. **Persistence** – whenever a tab-level attribute like `_media_color` is updated via the swatch, ensure the corresponding `load_*_settings` function sets that attribute *and* calls `_apply_color_to_button("btn_attr", "_attr")` (as done in `widgets_tab_media.py`). For tabs without that helper yet, add one before migrating the UI.
4. **Default/state init** – verify the underlying `_attr` is initialised in the tab’s `__init__`/loader and included in `save_*_settings()`. Swatches must reflect the loaded value when the dialog opens.
5. **Tooltips/accessibility** – keep any existing tooltips. If the old button relied on text for context (e.g. multi-line controls), add tooltips describing the colour.
6. **Testing checklist** – after each migration: (a) colour shows immediately on load; (b) clicking opens the picker; (c) selecting a new colour updates the swatch; (d) applying settings + reopening restores the chosen colour; (e) Taste The Rainbow / dependent features still read the stored RGBA values.

---

## Widget tabs

### Clock (`ui/tabs/widgets_tab_clock.py`)
- [ ] Text Color – `tab.clock_color_btn` (`_clock_color`, `_choose_clock_color`). Add `_apply_color_to_button` helper in `load_clock_settings` similar to media tab.
- [ ] Background Color – `tab.clock_bg_color_btn` (`_clock_bg_color`). Same helper usage.
- [ ] Border Color – `tab.clock_border_color_btn` (`_clock_border_color`). Ensure save/load pipe remains intact.

### Weather (`ui/tabs/widgets_tab_weather.py`)
- [x] Text Color – `tab.weather_color_btn` (`_weather_color`). Swatch uses `ColorSwatchButton` and `_sync_weather_swatch` helper.
- [x] Background Color – `tab.weather_bg_color_btn` (`_weather_bg_color`). Swatch in `_weather_bg_container`.
- [x] Border Color – `tab.weather_border_color_btn` (`_weather_border_color`). Synced via `_sync_weather_swatch`.

### Media widget (`ui/tabs/widgets_tab_media.py` – media section)
- [x] Text Color – `tab.media_color_btn` (`_media_color`). Uses `ColorSwatchButton` with `_apply_color_to_button` sync.
- [x] Background Color – `tab.media_bg_color_btn` (`_media_bg_color`). Swatch in `_media_bg_container`.
- [x] Border Color – `tab.media_border_color_btn` (`_media_border_color`). Synced via `_apply_color_to_button`.
- [x] Volume Fill Color – `tab.media_volume_fill_color_btn` (`_media_volume_fill_color`). Initializes from saved fill colour or `_media_color` fallback.

### Reddit widget (`ui/tabs/widgets_tab_reddit.py`)
- [x] Text Color – `tab.reddit_color_btn` (`_reddit_color`). Uses `ColorSwatchButton` and `_apply_color_to_button` sync helper.
- [x] Background Color – `tab.reddit_bg_color_btn` (`_reddit_bg_color`). Swatch gated by `reddit_show_background` visibility.
- [x] Border Color – `tab.reddit_border_color_btn` (`_reddit_border_color`). Synced via helper for load reliability.

### Imgur widget (`ui/tabs/widgets_tab_imgur.py`)
- [x] Text Color – `tab.imgur_color_btn` (`_imgur_color`). Uses `ColorSwatchButton` via `_apply_color_to_button` helper in loader.
- [x] Background Color – `tab.imgur_bg_color_btn` (`_imgur_bg_color`).
- [x] Border Color – `tab.imgur_border_color_btn` (`_imgur_border_color`).

### Additional widgets (if re-enabled later)
- Gmail/archive sections still contain `_choose_*` helpers; if resurrected, follow this playbook. Document any legacy paths in `archive/` before migrating.

---

## Spotify Visualizer build tabs

### Spectrum (`ui/tabs/media/spectrum_builder.py`)
- [x] Bar Fill Color – `tab.spotify_vis_fill_color_btn` (`_spotify_vis_fill_color`). Swatch sits inline with label and syncs via existing loader.
- [x] Bar Border Color – `tab.spotify_vis_border_color_btn` (`_spotify_vis_border_color`).

### Starfield (`ui/tabs/media/starfield_builder.py`)
- [x] Nebula Tint 1 – `tab.nebula_tint1_btn` (`_nebula_tint1`). Two swatches share one row; labels “Tint 1 / Tint 2”.
- [x] Nebula Tint 2 – `tab.nebula_tint2_btn` (`_nebula_tint2`). Loader now reuses `_apply_color_to_button` helper.

### Blob (`ui/tabs/media/blob_builder.py`)
- [ ] Glow Color – `tab.blob_glow_color_btn` (`_blob_glow_color`). Located inside `_blob_glow_sub_container` that is gated by `blob_reactive_glow`.
- [ ] Fill Color – `tab.blob_fill_color_btn` (`_blob_color`).
- [ ] Edge Color – `tab.blob_edge_color_btn` (`_blob_edge_color`).
- [ ] Outline Color – `tab.blob_outline_color_btn` (`_blob_outline_color`).

### Helix (`ui/tabs/media/helix_builder.py`)
- [x] Glow Color – `tab.helix_glow_color_btn` (`_helix_glow_color`). Loader syncs via `_apply_color_to_button`.

### Other modes
- Bubble & sine/osc multi-line already migrated. Re-check `bubble_builder` later; if new color controls are added, follow same rules.

---

## Transitions tab

### Burn transition (`ui/tabs/transitions_tab.py`)
- [x] Glow Colour – `self.burn_glow_color_btn` (custom sized button). Uses `ColorSwatchButton(auto_picker=False)` but keeps `_pick_burn_glow_color` dialog for consistency.

---

## Tracking & verification

- When a swatch migration is completed, tick the corresponding checkbox above and append a brief note (date + summary) below the section.
- **2026-02-21:** Weather widget swatches migrated (text/bg/border) with `_sync_weather_swatch` helper for load-time sync.
- **2026-02-21:** Media widget swatches migrated (text/bg/border/volume fill) using `ColorSwatchButton` + `_apply_color_to_button` loader sync.
- **2026-02-21:** Reddit widget swatches migrated (text/bg/border) using `ColorSwatchButton` + `_apply_color_to_button` loader sync.
- **2026-02-21:** Imgur widget swatches migrated (text/bg/border) with `ColorSwatchButton` + `_apply_color_to_button` helper gated behind dev flag.
- **2026-02-21:** Spectrum visualizer swatches migrated (bar fill/border) using `ColorSwatchButton`; `widgets_tab_media.load_media_settings` already syncs `_spotify_vis_*` colors.
- **2026-02-21:** Starfield nebula tint swatches migrated with `ColorSwatchButton` + `_apply_color_to_button` loader sync (shared row maintained).
- **2026-02-21:** Helix glow swatch migrated with `ColorSwatchButton`; loader now syncs `_helix_glow_color` into the swatch.
- **2026-02-21:** Burn transition glow swatch migrated using `ColorSwatchButton(auto_picker=False)` while retaining `_pick_burn_glow_color` for the styled dialog.
- If a migration requires new helpers (e.g., `_apply_color_to_button` in other tabs), document the helper name and file/line references in this doc for future maintainers.
- Regression risks to watch:
  - Missing `_apply_color_to_button` call → swatch loads with default colour each time.
  - Failing to remove the old `_choose_*` button leads to dead code; clean up once swatch uses direct lambdas.
  - Settings dict mismatches (e.g., `widgets` vs `SettingsManager`) – use the fixed pattern already applied in `load_media_settings`.
