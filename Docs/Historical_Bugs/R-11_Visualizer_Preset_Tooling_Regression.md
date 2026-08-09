# R-11 — 2026-03-14 — Visualizer Preset Tooling Regression (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Running `visualizer_preset_repair.py` on new Spectrum presets (e.g., `preset_2_cake.json`) shrank the JSON but silently reset `spectrum_shape_nodes` and all shaping sliders back to defaults. The GUI then loaded "Preset 2" with the default curve, ignoring the user-authored shape entirely.
- Switching from any curated preset back to Custom instantly overwrote the Custom slot (even without hitting Save). Toggling presets was enough to nuke hand-tuned slider values because the parser reapplied the curated dict into the Custom slot while the UI reloaded.

**Root Causes**
1. `_collect_visualizer_sections` appended `snapshot.custom_preset_backup` *after* the `snapshot.widgets.spotify_visualizer` block. Because the parser merges sections in order, the backup dict (which still held default values) overwrote the curated entries the moment the preset was reapplied.
2. The repair tool only inferred `preset_index`, leaving `name` blank whenever the snapshot lacked metadata. The UI therefore showed the placeholder "Preset 2" even for curated files like `preset_2_cake`. Combined with #1, it looked as if presets were not sticking.

**Fixes**
- Parser now feeds `custom_preset_backup` first and then the main `widgets.spotify_visualizer` block, so curated settings remain authoritative and the Custom slot stops being overwritten when presets reload. @core/settings/visualizer_presets.py#223-247
- `tools/visualizer_preset_repair.py` now derives friendly names from the filename when missing metadata (e.g., `preset_2_cake.json` → "Preset 2 (Cake)"). We also re-ran the tool to confirm Spectrum retains custom shape nodes and that backups are emitted (`.bak1`).

**Status**
- ✅ Resolved — Spectrum `preset_2_cake.json` retains custom shaping data and displays the friendly name. Switching between presets and Custom no longer wipes the Custom slot. Cross-mode audit pending to ensure every curated file behaves the same way.

**Takeaways**
- Always merge snapshot backup sections *before* the primary widget payload so curated presets remain authoritative.
- Repair-tool outputs must include human-friendly names; otherwise it’s impossible to tell curated presets apart in the UI.

## Record Provenance

This standalone file preserves the complete former inline `R-11` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
