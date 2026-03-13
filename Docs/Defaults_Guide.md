# Defaults Guide

> Canonical reference for all default settings, storage locations, SettingsManager behaviour, and safe procedures for changing defaults.

---

## 1. Default Settings by Section

All canonical defaults live in **`core/settings/defaults.py`** → `get_default_settings()`.

### Display
| Key | Default | Notes |
|-----|---------|-------|
| `display.gl_depth_bits` | `24` | OpenGL depth buffer |
| `display.gl_stencil_bits` | `8` | OpenGL stencil buffer |
| `display.hw_accel` | `True` | Hardware acceleration |
| `display.mode` | `"fill"` | Fill / Fit / Shrink |
| `display.prefer_triple_buffer` | `True` | GL triple buffering |
| `display.render_backend_mode` | `"opengl"` | Render backend |
| `display.same_image_all_monitors` | `False` | Different images per display |
| `display.sharpen_downscale` | `False` | Sharpen after downscale |
| `display.show_on_monitors` | `"ALL"` | Which monitors to cover |
| `display.use_lanczos` | `False` | Lanczos scaling (slower) |

### Input
| Key | Default | Notes |
|-----|---------|-------|
| `input.hard_exit` | `False` | When true, mouse/clicks do not exit |

### Queue
| Key | Default | Notes |
|-----|---------|-------|
| `queue.shuffle` | `True` | Shuffle image order |

### Sources
| Key | Default | Notes |
|-----|---------|-------|
| `sources.mode` | `"folders"` | folders / rss / both |
| `sources.rss_background_cap` | `30` | Max background RSS images |
| `sources.rss_refresh_minutes` | `10` | RSS poll interval |
| `sources.rss_save_directory` | `""` | RSS save path |
| `sources.rss_save_to_disk` | `False` | Persist RSS images |
| `sources.rss_stale_minutes` | `30` | RSS cache staleness |
| `sources.local_ratio` | `95` | % local vs RSS images |
| `sources.rss_rotating_cache_size` | `20` | RSS rotating cache |

### Timing
| Key | Default | Notes |
|-----|---------|-------|
| `timing.interval` | `45` | Seconds between rotations |

### Accessibility
| Key | Default |
|-----|---------|
| `accessibility.dimming.enabled` | `False` |
| `accessibility.dimming.opacity` | `50` |
| `accessibility.pixel_shift.enabled` | `False` |
| `accessibility.pixel_shift.rate` | `4` |

### Transitions
| Key | Default | Notes |
|-----|---------|-------|
| `transitions.type` | `"Random"` | Active transition type |
| `transitions.duration_ms` | `4000` | Default duration |
| `transitions.easing` | `"Auto"` | Easing function |
| `transitions.direction` | `"Random"` | Global direction |
| `transitions.random_always` | `False` | Force random every rotation |

Per-transition durations, pool membership, and sub-settings (block_flip, blinds, crumble, diffuse, particle, ripple, slide, wipe) are all defined in `defaults.py` under the `transitions` section.

### Widgets — Clock
| Key | Default |
|-----|---------|
| `widgets.clock.enabled` | `True` |
| `widgets.clock.display_mode` | `"analog"` |
| `widgets.clock.position` | `"Top Right"` |
| `widgets.clock.monitor` | `"ALL"` |
| `widgets.clock.format` | `"24h"` |
| `widgets.clock.font_family` | `"Segoe UI"` |
| `widgets.clock.font_size` | `78` |
| `widgets.clock.margin` | `30` |
| `widgets.clock.show_seconds` | `True` |
| `widgets.clock.show_timezone` | `True` |
| `widgets.clock.show_numerals` | `True` |
| `widgets.clock.show_background` | `False` |
| `widgets.clock.bg_opacity` | `0.6` |
| `widgets.clock.analog_face_shadow` | `True` |
| `widgets.clock.analog_shadow_intense` | `True` |
| `widgets.clock.digital_shadow_intense` | `False` |

Clock2 and Clock3 follow the same schema but default to `enabled: False`.

### Widgets — Media
| Key | Default | Notes |
|-----|---------|-------|
| `widgets.media.enabled` | `True` | |
| `widgets.media.provider` | `"spotify"` | `"spotify"` or `"musicbee"` — selects GSMTC session filter + branding |
| `widgets.media.position` | `"Bottom Left"` | |
| `widgets.media.monitor` | `2` | |
| `widgets.media.artwork_size` | `225` | |
| `widgets.media.show_controls` | `True` | |
| `widgets.media.show_header_frame` | `True` | |
| `widgets.media.rounded_artwork_border` | `True` | |
| `widgets.media.intense_shadow` | `True` | |
| `widgets.media.spotify_volume_enabled` | `True` | |
| `widgets.media.spotify_volume_fill_color` | `[66, 66, 66, 255]` (`#424242FF`) | |
| `widgets.media.mute_button_enabled` | `True` | |

### Widgets — Weather
| Key | Default |
|-----|---------|
| `widgets.weather.enabled` | `True` |
| `widgets.weather.position` | `"Top Left"` |
| `widgets.weather.monitor` | `"ALL"` |
| `widgets.weather.font_size` | `28` |
| `widgets.weather.show_forecast` | `True` |
| `widgets.weather.show_details_row` | `True` |
| `widgets.weather.show_condition_icon` | `True` |
| `widgets.weather.icon_alignment` | `"RIGHT"` |
| `widgets.weather.icon_size` | `96` |

### Widgets — Reddit
| Key | Default |
|-----|---------|
| `widgets.reddit.enabled` | `True` |
| `widgets.reddit.position` | `"Bottom Center"` |
| `widgets.reddit.monitor` | `2` |
| `widgets.reddit.subreddit` | `"SubredditDrama"` |
| `widgets.reddit.limit` | `20` |
| `widgets.reddit.exit_on_click` | `True` |

Reddit2 defaults to `enabled: True`, `position: "Bottom Right"`, `subreddit: "Games"`.

### Widgets — Imgur
| Key | Default |
|-----|---------|
| `widgets.imgur.enabled` | `False` |
| `widgets.imgur.tag` | `"most_viral"` |
| `widgets.imgur.layout_mode` | `"hybrid"` |
| `widgets.imgur.grid_rows` | `2` |
| `widgets.imgur.grid_columns` | `4` |

### Widgets — Spotify Visualizer
| Key | Default | Notes |
|-----|---------|-------|
| `widgets.spotify_visualizer.visualizers_enabled` | `True` | Master toggle exposed on the Visualizers subtab. Gates all Beat Visualizer controls; runtime still requires Media widget enabled to spawn the overlay. |
| `widgets.spotify_visualizer.enabled` | `True` | Per-mode Beat Visualizer enable (within the subtab). |
| `widgets.spotify_visualizer.mode` | `"blob"` | bars/blob/helix/nebula/oscilloscope/sine_wave/spectrum/starfield |
| `widgets.spotify_visualizer.monitor` | `"ALL"` | |
| `widgets.spotify_visualizer.bar_count` | `21` | Legacy placeholder; runtime bar counts now resolved per-mode via `SpotifyVisualizerSettings`. |
| `widgets.spotify_visualizer.sine_line_offset_bias` | `0.7` | Controls both vertical line spread and per-line energy tint (0 = all lines share bass mix, 1 = spreads lines apart and leans lines 2/3 toward mid/high energy). |
| `widgets.spotify_visualizer.blob_stage_bias` | `0.0` | Bias applied to stage thresholds (−0.30→+0.30) |
| `widgets.spotify_visualizer.blob_stage2_release_ms` | `900` | Stage 2 release duration (ms) |
| `widgets.spotify_visualizer.blob_stage3_release_ms` | `1200` | Stage 3 release duration (ms) |
| `widgets.spotify_visualizer.sine_line1_shift` | `0.0` | Horizontal phase shift (cycles) for line 1 (negative=lead, positive=lag). `_reset_visualizer_state()` re-applies the cached value so double-click mode switches stay in sync. |
| `widgets.spotify_visualizer.sine_line2_shift` | `0.0` | Same as above for line 2 (visible when multi-line enabled). |
| `widgets.spotify_visualizer.sine_line3_shift` | `0.0` | Same as above for line 3. |
| `widgets.spotify_visualizer.adaptive_sensitivity` | `True` | Stored as a bool but exposed in the UI as **Suggest Sensitivity** — when enabled the manual slider stays hidden and we apply the curated auto multiplier; uncheck to reveal the slider and use the manual `sensitivity` value |
| `widgets.spotify_visualizer.preset_<mode>` | `0` | One key per mode (e.g. `preset_spectrum`, `preset_bubble`). Stores the curated slot index used by `VisualizerPresetSlider`; values clamp between 0 and the Custom slot. Preset overlays are applied at model-build time, but **Custom** always reflects the user’s raw settings. |
| `widgets.spotify_visualizer.dynamic_floor` | `True` | Global legacy fallback. Actual floor/toggle defaults live per-mode (see below). |
| `widgets.spotify_visualizer.manual_floor` | `2.1` | Global legacy fallback. |
| `widgets.spotify_visualizer.ghosting_enabled` | `True` | |

**Per-mode technical schema (Mar 2026):** Every mode owns an explicit set of technical keys (`<mode>_bar_count`, `<mode>_dynamic_floor`, `<mode>_manual_floor`, `<mode>_adaptive_sensitivity`, `<mode>_sensitivity`, `<mode>_audio_block_size`, `<mode>_dynamic_range_enabled`). Defaults for Spectrum/Bubble/Blob/Sine/Osc/Starfield/Helix are defined in `defaults.py` under `widgets.spotify_visualizer`. UI helpers (`build_per_mode_technical_group`) and the widget cache read/write ONLY per-mode keys; the global `bar_count`/`dynamic_floor` fallbacks remain for legacy SST snapshots but should not be edited going forward.

**Preset hygiene:** Use `tools/visualizer_preset_repair.py` to refresh curated preset JSON/SST payloads whenever defaults change. The tool reads `DEFAULT_SETTINGS`, applies `_migrate_preset_settings()` + `_filter_settings_for_mode()`, fills missing keys, writes `.bak` backups, and keeps an in-session undo stack.

#### Spotify Visualizer — Bubble Mode
| Key | Default | Notes |
|-----|---------|-------|
| `bubble_big_bass_pulse` | `0.5` | Bass response strength for large bubbles |
| `bubble_small_freq_pulse` | `0.5` | Treble response strength for small bubbles |
| `bubble_stream_direction` | `"up"` | up/down/random |
| `bubble_stream_constant_speed` | `0.5` | Baseline travel speed multiplier (idle drift) |
| `bubble_stream_speed_cap` | `2.0` | Maximum travel speed multiplier (reactive ceiling). UI slider now spans `0.5–4.0×` and config clamps at `4.0` (PF-12) |
| `bubble_stream_reactivity` | `0.5` | How quickly stream speed reacts to audio |
| `bubble_rotation_amount` | `0.5` | Adds swirl motion |
| `bubble_drift_amount` | `0.5` | Horizontal drift distance |
| `bubble_drift_speed` | `0.5` | Drift rate |
| `bubble_drift_frequency` | `0.5` | Drift oscillation |
| `bubble_drift_direction` | `"random"` | `none`, `left`, `right`, `diagonal`, **Swish (Horizontal)**, **Swish (Vertical)**, **Swirl (Clockwise)**, **Swirl (Counter-Clockwise)**, `random` — Swish modes lock wobble to an axis, Swirl modes orbit around the card center clockwise/counter-clockwise |
| `bubble_big_count` | `8` | Big bubble count |
| `bubble_small_count` | `25` | Small bubble count |
| `bubble_surface_reach` | `0.6` | How close bubbles travel toward the card top |
| `bubble_outline_color` | `[255, 255, 255, 230]` | Rim highlight |
| `bubble_specular_color` | `[255, 255, 255, 255]` | Specular sparkles |
| `bubble_gradient_light` | `[210, 170, 120, 255]` | Gradient top color |
| `bubble_gradient_dark` | `[80, 60, 50, 255]` | Gradient bottom color |
| `bubble_pop_color` | `[255, 255, 255, 180]` | Burst sparkle |
| `bubble_specular_direction` | `"top_left"` | Lighting direction (`top`, `bottom`, `left`, `right`, diagonals) for the highlight offset (Advanced bucket). Applies even when Advanced is collapsed (Always-Apply rule). |
| `bubble_gradient_direction` | `"top"` | Independent gradient tilt vector (Normal bucket). Preset rebuilds and SST exports carry this key so curated/default visuals stay in sync. |
| `bubble_big_size_max` | `0.038` | Max radius for big bubbles |
| `bubble_small_size_max` | `0.018` | Max radius for small bubbles |
| `bubble_growth` | `3.0` | Size multiplier |
| `bubble_trail_strength` | `0.0` | *Temporarily disabled.* Slider is greyed out until gradient-taper trails are rebuilt |

### Workers
| Key | Default |
|-----|---------|
| `workers.max_workers` | `"auto"` |
| `workers.image.enabled` | `True` |
| `workers.rss.enabled` | `True` |
| `workers.fft.enabled` | `False` |
| `workers.transition.enabled` | `True` |

### Shadows (shared card styling)
| Key | Default |
|-----|---------|
| `widgets.shadows.enabled` | `True` |
| `widgets.shadows.blur_radius` | `18` |
| `widgets.shadows.frame_opacity` | `0.77` |
| `widgets.shadows.text_opacity` | `0.33` |
| `widgets.shadows.offset` | `[4, 4]` |

---

## 2. Build Variants & Presets

### Standard Screensaver (.scr)
- Profile name: `Screensaver`
- JSON path: `%APPDATA%/SRPSS/settings_v2.json`
- `input.hard_exit` defaults to `True` (any key exits)
- Runs on Winlogon desktop when installed as .scr

### MC (Media Center) Build
- Profile name: `Screensaver_MC`
- JSON path: `%APPDATA%/SRPSS_MC/settings_v2.json`
- Detected by exe name containing `srpss_mc`, `srpss media center`, or `main_mc.py`
- Forces `input.hard_exit = True` at runtime
- Separate settings file — MC and standard builds do NOT share settings

### Script / Debug Build
- Same profile as Standard (`Screensaver`)
- Shares the same `settings_v2.json`
- Console output enabled for debugging

---

## 3. Settings Storage Architecture

### File Locations

| Build | JSON Path |
|-------|-----------|
| Standard | `%APPDATA%/SRPSS/settings_v2.json` |
| MC | `%APPDATA%/SRPSS_MC/settings_v2.json` |
| Test/Custom | `%APPDATA%/SRPSS_profiles/<name>/settings_v2.json` |

Determined by `core/settings/json_store.py` → `determine_storage_path()`.

### Code Locations

| File | Purpose |
|------|---------|
| `core/settings/defaults.py` | **Canonical defaults** — single source of truth |
| `core/settings/models.py` | Dataclass models with typed fields (e.g., `SpotifyVisualizerSettings`) |
| `core/settings/settings_manager.py` | Runtime get/set, caching, change notifications, migration |
| `core/settings/json_store.py` | JSON file I/O, locking, snapshot versioning |

### How Settings Flow

```
defaults.py (canonical defaults)
    ↓
SettingsManager.__init__()
    ↓ _set_defaults() merges missing keys
    ↓ _ensure_widgets_defaults() deep-merges widget sections
    ↓ _ensure_transitions_defaults() deep-merges transition sections
    ↓
JsonSettingsStore (settings_v2.json on disk)
    ↓
SettingsManager.get(key, fallback)
    ↓ checks in-memory cache
    ↓ checks structured roots (widgets, transitions)
    ↓ falls back to json_store.value()
    ↓ returns fallback param if key missing everywhere
```

### Preserved Keys (never reset)
These keys are excluded from "Reset to Defaults":
- `sources.folders`
- `sources.rss_feeds`
- `widgets.weather.location`
- `widgets.weather.latitude`
- `widgets.weather.longitude`

Defined in `defaults.py` → `PRESERVE_ON_RESET`.

---

## 4. SettingsManager Considerations

### Key API Methods
- **`get(key, default)`** — Returns stored value or `default`. The `default` param is a **runtime fallback**, not the canonical default. Always pass the value from `defaults.py`.
- **`set(key, value)`** — Stores value, emits `settings_changed` signal, invalidates cache.
- **`get_bool(key, default)`** — Convenience wrapper with string normalization.
- **`to_bool(value, default)`** — Static method for bool coercion from strings/ints.
- **`get_widget_defaults(section)`** — Returns fresh canonical defaults for a widget section without touching storage.
- **`reset_to_defaults()`** — Resets all settings except `PRESERVE_ON_RESET` keys.

### Caching
- In-memory cache (`_cache`) is enabled by default for frequently accessed keys.
- Cache is keyed by `f"{key}:{id(default)}"`.
- `set()` invalidates the cache entry for the changed key.
- Bulk operations (import/reset) clear the entire cache.

### Thread Safety
- All reads/writes are protected by `threading.RLock`.
- `settings_changed` signal is emitted on the calling thread — UI consumers should ensure they handle it on the UI thread.

### Structured Roots
The keys `widgets`, `transitions`, `ui`, and `custom_preset_backup` are stored as nested dicts (not flattened). Accessing sub-keys like `widgets.clock.enabled` goes through `_get_structured_value_locked()` which navigates the nested dict.

### Legacy Migration
On first run, if no `settings_v2.json` exists but legacy QSettings data is found, `_run_initial_migration()` imports the data and writes a backup to `%APPDATA%/SRPSS/backups/`.

---

## 5. Steps to Change a Default Safely

### Adding a New Setting

1. **`core/settings/defaults.py`** — Add the key+value in the appropriate section of `get_default_settings()`.
2. **`core/settings/models.py`** — If the setting belongs to a dataclass model (e.g., `SpotifyVisualizerSettings`), add the field with type annotation and default.
3. **Model loaders** — Update `from_settings()`, `from_mapping()`, and `to_dict()` in the model.
4. **UI** — If UI-exposed, add the widget in the appropriate tab and wire up save/load.
5. **Consumer code** — Use `settings_manager.get('section.key', <default_from_defaults.py>)`.
6. **Test** — Delete `settings_v2.json` and verify the new default appears. Also test with an existing file to verify merge.
7. **Documentation** — Update this guide and `Index.md`.

### Changing an Existing Default

1. **`core/settings/defaults.py`** — Change the value.
2. **`core/settings/models.py`** — Update the dataclass field default if applicable.
3. **Verify all `get()` call sites** — Search for the key and ensure the fallback parameter matches the new default. This is critical because `get(key, old_default)` will return `old_default` for users who never explicitly set the key.
4. **Test both paths**:
   - Fresh install (no JSON) → should use new default
   - Existing install → user's stored value should be preserved
5. **Update documentation**.

### Renaming a Setting Key

1. Add the new key to `defaults.py`.
2. In model `from_settings()` and `from_mapping()`, add fallback reads for the old key name.
3. In UI load paths, check old key as fallback.
4. Add old key to `_OBSOLETE_KEYS` in `settings_manager.py` for cleanup.
5. Test migration from old → new key.

### Visualizer Settings (8-Layer Rule)

Every new visualizer setting must be added to **all 8 layers** or it silently uses defaults:

1. Model dataclass field (`core/settings/models.py`)
2. `from_settings()` loader
3. `from_mapping()` loader
4. `to_dict()` serializer
5. Creator kwargs (`rendering/spotify_widget_creators.py`)
6. Widget `apply_vis_mode_config()` (`widgets/spotify_visualizer_widget.py`)
7. Widget `_on_tick` extra dict (now in `tick_pipeline.py`)
8. GL overlay `set_state()` (`widgets/spotify_bars_gl_overlay.py`) — per-mode uniform upload via `renderers/<mode>.py`

Plus UI creation, UI save, and shader uniform if applicable.

### Widget Factory Default Drift (Mar 2026 Audit)

The Settings Persistence Audit (`Audits/settings_persistence_audit.md`) found that `ClockWidgetFactory` and `WeatherWidgetFactory` in `rendering/widget_factories.py` had hardcoded defaults that drifted from `defaults.py`. Both now use `canonical = get_default_settings().get('widgets', {}).get(section, {})` as fallback. If you add or change a widget default, verify the factory reads from canonical — never hardcode a fallback value directly.

---

## 6. Common Pitfalls

- **`get(key, 0)` with bool check** — `0` is falsy, so `value or default` patterns fail. Use explicit `is None` checks.
- **String booleans** — QSettings legacy data may store `"true"/"false"` strings. Always use `get_bool()` or `to_bool()`.
- **Cache staleness** — If you modify settings outside `SettingsManager.set()`, the cache won't update. Always go through the manager.
- **MC vs Standard confusion** — They use separate JSON files. A setting changed in MC mode won't appear in standard mode and vice versa.
- **`PRESERVE_ON_RESET`** — If you add a user-specific key (like API keys or geo data), add it to this set.
