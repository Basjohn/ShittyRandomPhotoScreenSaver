# Adding Settings to Visualizer Presets — Developer Guide

## Terminology Disambiguation

This codebase has **two separate preset systems**. Do not confuse them:

| System | Location | Controls | Keys |
|--------|----------|----------|------|
| **Global Presets** | `core/settings/presets.py` | Which widgets are visible (Purist / Essentials / Media / Full Monty / Custom) | `widgets.*.enabled` |
| **Visualizer Presets** | `core/settings/visualizer_presets.py` | How a visualizer mode looks/behaves (Preset 1 / 2 / 3 / Custom) | `widgets.spotify_visualizer.preset_{mode}` |

These are **orthogonal**. Never mix them. This guide covers **Visualizer Presets only**.

---

## What "Adding a Preset Setting" Means

A visualizer preset setting is a key→value override that gets applied when the user selects a named preset (Preset 1, 2, or 3) for a given mode. When the user is on **Custom** (index 3), the preset dict is ignored and the user's saved values are used directly.

The preset dict lives in `core/settings/visualizer_presets.py` inside `_PRESETS[mode][index].settings`.

---

## Step-by-Step: Adding a Value to a Preset

### 1. Locate the mode's preset list

Open `core/settings/visualizer_presets.py`. Find the `_PRESETS` dict entry for your mode:

```python
_PRESETS: Dict[str, List[VisualizerPreset]] = {
    mode: _default_presets() for mode in MODES
}
```

All modes currently use `_default_presets()` which returns 4 presets with empty `settings={}` dicts. To add mode-specific presets, replace the entry:

```python
_PRESETS["sine_wave"] = [
    VisualizerPreset(
        name="Preset 1",
        description="Default settings",
        settings={},          # empty = use hardcoded defaults
    ),
    VisualizerPreset(
        name="Preset 2",
        description="Snake",
        settings={
            "sine_micro_wobble": 0.7,
            "sine_width_reaction": 0.5,
            "sine_line_count": 3,
        },
    ),
    VisualizerPreset(
        name="Preset 3",
        description="Heartbeat",
        settings={
            "sine_heartbeat": 0.8,
            "sine_wave_effect": 0.4,
            "sine_wave_travel": 1,
        },
    ),
    VisualizerPreset(
        name="Custom",
        description="Your own settings (Advanced)",
        settings={},
        is_custom=True,
    ),
]
```

### 2. Use plain setting keys (no prefix)

Keys in the `settings` dict must be **plain keys** — the same keys used in `save_media_settings()` and the `spotify_vis_config` dict. Do **not** use dotted prefix keys like `widgets.spotify_visualizer.sine_micro_wobble`.

**Correct:** `"sine_micro_wobble": 0.7`  
**Wrong:** `"widgets.spotify_visualizer.sine_micro_wobble": 0.7`

### 3. How the overlay is applied

`apply_preset_to_config(mode, index, raw_dict)` in `visualizer_presets.py` merges the preset's `settings` dict over the raw config dict. This is called inside `SpotifyVisualizerSettings.from_mapping()` before any model fields are read.

- **Custom (index 3):** `raw_dict` is returned unchanged.
- **Named preset with empty `settings={}`:** `raw_dict` is returned unchanged (no-op — uses saved/default values).
- **Named preset with non-empty `settings`:** Preset values override the corresponding keys in `raw_dict`.

### 4. Verify the key exists in the 8-layer pipeline

Before adding a key to a preset dict, confirm it is already wired through all 8 layers (model, from_settings, from_mapping, to_dict, creator, widget, tick, GL overlay). If it isn't, adding it to a preset dict will silently do nothing. See the **8-Layer Checklist** in `Docs/Visualizer_Debug.md`.

### 5. Test backward compatibility

- Users with no `preset_{mode}` key in their settings default to index 0 (Preset 1).
- Preset 1 should always have `settings={}` (empty) so existing users see no change.
- Never put `rainbow_enabled` or `rainbow_speed` in a preset — these are global overlays.

---

## What NOT to Put in Preset Settings

| Key | Reason |
|-----|--------|
| `rainbow_enabled` / `rainbow_speed` | Global overlay, independent of mode |
| `ghosting_enabled` / `ghost_alpha` / `ghost_decay` | Global to all modes |
| `sensitivity` / `adaptive_sensitivity` | Global audio settings |
| `preset_{mode}` | Never self-reference |
| `enabled` / `monitor` | Widget-level, not mode-level |

---

## UI Behaviour Summary

- **Preset slider position** is saved as `preset_{mode}` (integer 0–3) in `spotify_vis_config`.
- **Advanced container** (all sliders) is shown only when preset index == 3 (Custom).
- **Auto-switch to Custom**: If the user modifies a setting while the advanced container is visible and the preset is NOT already Custom, `_auto_switch_preset_to_custom()` in `widgets_tab.py` switches to Custom automatically. This only fires when the Qt `sender()` is a descendant of the mode's `_<mode>_advanced` container.
- **Preset slider itself** sets `_preset_slider_changing = True` on the tab before emitting `preset_changed`, preventing the auto-switch from re-triggering.

---

## Key Files Reference

| File | Role |
|------|------|
| `core/settings/visualizer_presets.py` | Preset registry, `apply_preset_to_config()` |
| `core/settings/models.py` | `SpotifyVisualizerSettings.from_mapping()` — applies overlay |
| `ui/tabs/media/preset_slider.py` | `VisualizerPresetSlider` widget |
| `ui/tabs/widgets_tab.py` | `_auto_switch_preset_to_custom()` |
| `ui/tabs/widgets_tab_media.py` | Save/load preset index |
| `ui/tabs/media/*_builder.py` | Per-mode UI builders with `_<mode>_advanced` containers |
