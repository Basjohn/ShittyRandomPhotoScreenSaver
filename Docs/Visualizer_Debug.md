# Visualizer Debug Reference

The Spotify Beat Visualizer consists of a shared pipeline (audio capture → FFT → smoothing → GPU push) and seven GLSL modes (Spectrum, Oscilloscope, Sine Wave, Blob, Bubble, Starfield, Helix). This document is the authoritative guide for debugging, default settings, and what each control does.

**Architecture (Mar 2026 split):** The monolithic widget/overlay have been decomposed:
- **Per-mode renderers** in `widgets/spotify_visualizer/renderers/` — each exports `get_uniform_names()` + `upload_uniforms()`. Only the active mode's uniforms are pushed.
- **Tick pipeline** in `widgets/spotify_visualizer/tick_pipeline.py` — extracted `_on_tick()` (~415 lines).
- **Mode transition** in `widgets/spotify_visualizer/mode_transition.py` — mode cycling, fade, teardown (~300 lines).
- **Config applier** in `widgets/spotify_visualizer/config_applier.py` — settings JSON → widget attributes.
- **Bubble sim** in `widgets/spotify_visualizer/bubble_simulation.py` — CPU-side particle sim.

---

## 1. Shared Pipeline

| Stage | Module | Notes |
|-------|--------|-------|
| Audio capture | `widgets/spotify_visualizer/audio_worker.py` | Pulls PCM from Windows GSMTC, resamples to 44.1 kHz float32 buffers, double buffers results |
| FFT + energy bands | `widgets/spotify_visualizer/bar_computation.py`, `widgets/spotify_visualizer/energy_bands.py` | Computes 64-bar spectrum + bass/mid/high envelopes. Curved profile template is applied here before smoothing. |
| Smoothing & growth | `widgets/spotify_visualizer/tick_helpers.py` | Applies exponential smoothing, card height growth (mode-specific), and GPU fade factors. |
| Config apply | `widgets/spotify_visualizer/config_applier.py` | Maps settings JSON → widget attributes → `_reset_visualizer_state()` cold-start parity + `_mode_transition_resume_ts` |
| GPU render | `widgets/spotify_bars_gl_overlay.py` + per-mode renderers in `widgets/spotify_visualizer/renderers/` + shaders in `widgets/spotify_visualizer/shaders/*.frag` | Loads all fragment shaders at `initializeGL()` and switches per mode at `paintGL()`. Per-mode uniform upload is dispatched via `upload_mode_uniforms(mode, gl, u, state)` from the renderer registry — only the active mode's uniforms are pushed, preventing cross-mode bleed. The overlay always clears its framebuffer (even when disabled) and `cleanup_gl()` drives deletions while the GL context is current. |

Global settings (defaults from `core/settings/defaults.py`):

- `adaptive_sensitivity=True`, `sensitivity=1.0` (UI label: **Suggest Sensitivity**. When checked we hide the manual slider and use the curated auto multiplier; uncheck to expose the slider and honor `sensitivity`.)
- `dynamic_floor=True`, `manual_floor=2.1`, `ghosting_enabled=True`, `ghost_alpha=0.34`, `ghost_decay=0.35`
- Per-mode technical slots now own `bar_count`, `<mode>_audio_block_size` (0 = Auto), `<mode>_manual_floor`, etc. There is **no** legacy global `audio_block_size` anymore; presets/repairs must reference the per-mode keys only. The visualizer now always renders through the GPU overlay — the legacy `software_visualizer_enabled` flag and QWidget fallback have been removed entirely.

When debugging, always verify these steps in order:
1. **Media state** – ensure `_spotify_playing` true and `_target_bars` are moving (check `[SPOTIFY_VIS][FLOOR]` logs).
2. **Fade gating** – `_get_gpu_fade_factor()` should rise from 0→1 after the card fade finishes.
3. **Mode uniforms** – confirm `_renderer_config` pushes the expected per-mode values (see sections below).
4. **State reset parity** – double-click mode switches call `_reset_visualizer_state()`, so stale bars/geometry should never leak between modes. If they do, log `_cached_vis_kwargs` / `_last_applied_model` for corruption.
5. **Shader output** – enable `[PERF] [GL COMPOSITOR]` metrics and screensaver_perf.log to catch dt spikes.

---

## 2. Per-Mode Defaults & Controls

### 2.1 Spectrum (default view)
- Shader: `widgets/spotify_visualizer/shaders/spectrum.frag`
- Defaults: `spectrum_bar_profile="curved"`, `spectrum_single_piece=True`, `spectrum_border_radius=3.0`, `bar_fill_color=[255,255,255,230]`, `bar_border_color=[255,255,255,220]`
- Uniforms: `u_bars[64]`, `u_peaks[64]`, `u_bar_count`, `u_segments`, `u_single_piece`, `u_fill_color`, `u_border_color`, `u_ghost_alpha`, `u_fade`, `u_time`, `u_resolution`
- Behaviour: geometry cache builds mirrored pillars; ghost peaks follow decaying envelope; segment count = `clamp(inner_height//5, 8, 64)`.
- Debug tip: If curved profile looks flat, confirm multiplication `profile_shape[i] * zone_energy` still occurs before smoothing.
- **Median+hysteresis gate (Mar 12 2026):** `_apply_bar_gate()` now runs before `_apply_reactive_smoothing()` to kill <~1.5 % jitter. Gate tracks the last two frames per bar, takes a 3-sample median, and only updates when the delta exceeds a dynamic threshold (rises require ≈8 % of prior value, drops ≈5 %). When debugging “stuck” bars, log `_bar_gate_prev*` on the worker; if they never seed, ensure the worker saw at least three frames after mode switch.
- Validation: run `tests/test_visualizer_bar_gate.py` once it lands, or temporarily enable `[SPOTIFY_VIS][TIMER]` to confirm gate isn’t starving when block size = 128.

### 2.2 Oscilloscope
- Shader: `widgets/spotify_visualizer/shaders/oscilloscope.frag`
- Defaults: `osc_glow_enabled=True`, `osc_glow_intensity=0.3`, `osc_line_color=[255,255,255,255]`, `osc_line_count=3`, `osc_line_dim=True`, `osc_line_amplitude=4.5` *(legacy key `osc_sensitivity` still accepted on load)*, `osc_smoothing=0.8`, `osc_speed=0.4`, `osc_line_offset_bias=0.5`, `osc_vertical_shift=35`
- Uniforms: `u_waveform[256]`, `u_line_color`, `u_glow_color`, `u_glow_enabled`, `u_reactive_glow`, `u_line_amplitude`, `u_line_count`, `u_line_dim`, `u_bass/mid/high/overall_energy`
- Waveform pipeline: sample → Gaussian smooth → Catmull-Rom interpolation → tanh soft-sat. Multi-line mode assigns bass/mid/high per line.
- Debug tip: `_update_osc_multi_line_visibility()` must run after config load; wave stuck? check `_osc_smoothing` not at 1.0. Oscilloscope line 2/3 colour + glow swatches are now bound via `ColorBinding`, so Taste The Rainbow reaches all glow lines without manual rehydrate/sync code.

-### 2.3 Sine Wave (pure sine successor to oscilloscope sine mode)
- Shader: `widgets/spotify_visualizer/shaders/sine_wave.frag`
- Defaults: `sine_wave_growth=3.99`, `sine_wave_travel=2`, `sine_wave_effect=0.7`, `sine_micro_wobble=0.0`, `sine_vertical_shift=35`, `sine_card_adaptation=0.2`, `sine_glow_enabled=True`, `sine_glow_intensity=0.6`, `sine_glow_color=[5,155,255,255]`, `sine_line_color=[255,255,255,255]`, `sine_reactive_glow=True`, `sine_sensitivity=0.1`, `sine_speed=1.0`, `sine_line_count=3`, `sine_line_offset_bias=0.7`, `sine_line_dim=False`, `sine_line{1,2,3}_shift=0.0`
- Uniforms reuse oscilloscope names for compatibility (`u_osc_speed`, `u_osc_sine_travel`, etc.) but values come from `_sine_*` attrs.
- **Density (Feb 2026):** `sine_density` is remapped onto a perceptual curve spanning ≈0.65–8.5 full cycles. Low settings keep broad arcs; high settings reach tighter combs without collapsing into a single hump.
- **Displacement (retired Feb 28 2026):** Slider/UI are locked at 0% and only exist to show the feature is disabled. The shader still exposes `u_sine_displacement` for backward compatibility but clamps all values to zero so random jitter can’t reappear from old presets.
- **UI alignment:** Density, displacement, and horizontal shift sliders live in the Sine Advanced bucket and must be created with `_aligned_row()` so the 120 px label gutter stays consistent with the rest of the visualizer builders.
- **Line Offset Bias behaviour:** slider is dual-purpose. At 0%, all three lines share the same vertical center and energy mix (pure bass). As bias rises toward 100%, the shader (a) increases their vertical separation (Line 2 gains +70% of the requested spacing, Line 3 gains +100%, Line 1 stays anchored) and (b) tints their energy weighting toward mid/high bands. This keeps low biases visually aligned while high biases emphasise vocals/treble on lines 2/3. Documented here because users kept expecting it to be "horizontal offset only".
- **Per-line horizontal shifts (Feb 2026):** new sliders (`sine_line{1,2,3}_shift`, exposed as "Horizontal Shift") phase each line independently in full cycles (-1.0..1.0). Defaults are zero so all lines align when Line Offset Bias = 0. This replaces the ad-hoc practice of nudging `sine_line_offset_bias` just to desync lines.
- **Normalization TODO:** after documenting the controls we will evaluate whether lines 2/3 should auto-normalize back toward line 1 when both Line Offset Bias and Horizontal Shifts are zero. Track that work under Current Plan §4.
- **Uniform gating regression (Feb 2026):** ensure `u_sine_line{1,2,3}_shift` uploads stay inside the `mode == 'sine_wave'` branch. Pushing them globally caused stale uniforms when other modes were active, so any future per-mode uniforms must stay inside their respective branch.
- **Heartbeat neutralization:** The heartbeat slider row is now labelled “Disabled,” and `heartbeat_amp_params()` always returns `(1.0, 0.48)`. If a preset contains non-zero heartbeat values, they have no effect until the feature is redesigned.
- Debug tip: Glow blowing out? clamp `sine_glow_intensity<=0.6`; reactive glow already adds +10%.

### 2.4 Blob (default visualizer card)
- Shader: `widgets/spotify_visualizer/shaders/blob.frag`
- Defaults: `blob_color=[0,105,243,230]`, `blob_edge_color=[89,175,255,255]`, `blob_glow_color=[3,104,255,180]`, `blob_glow_intensity=0.5`, `blob_size=0.7`, `blob_width=0.9`, `blob_growth=4.0`, `blob_reactive_deformation=0.5`, `blob_constant_wobble=0.25`, `blob_reactive_wobble=1.0`, `blob_pulse=1.75`, `blob_stretch_tendency=0.12`
- Uniforms: `u_blob_color`, `u_blob_edge_color`, `u_blob_outline_color`, `u_blob_glow_color`, `u_blob_glow_intensity`, `u_blob_reactive_glow`, `u_blob_size`, `u_blob_width`, `u_blob_pulse`, `u_blob_smoothed_energy`
- Deformation layers: bass pulse, constant wobble (time), reactive wobble (energy), vocal wobble, stretch tendency, reactive deformation scale.
- **Ghosting V5 (Mar 2026):** Peak tracking uses 150ms hold before decay, decays toward smoothed energy (not raw), and enforces a minimum offset (`max(0.06, smoothed_e * 0.12)`) so the ghost shape is always visible during playback. Shader smoothstep zones widened for broader ghost fill region. Peak state: `_blob_peak_{energy,bass,mid,high,overall}` + `_blob_peak_hold_remaining` in `spotify_bars_gl_overlay.py`.
- Debug tip: "Tearing" occurs when `blob_growth>5` without card height increase.

### 2.5 Starfield (dev-gated by `SRPSS_ENABLE_DEV=1`) [GATED FOR BEING SHIT]
- Shader: `widgets/spotify_visualizer/shaders/starfield.frag`
- Defaults: `star_density=1.0`, `star_travel_speed=0.93`, `star_reactivity=1.95`, `starfield_growth=3.01`, `nebula_tint1=[27,116,194,255]`, `nebula_tint2=[80,20,100,255]`, `nebula_cycle_speed=0.59`
- Uniforms: `u_star_density`, `u_travel_speed`, `u_star_reactivity`, `u_travel_time`, `u_nebula_tint1/2`, `u_nebula_cycle_speed`, `u_bass/mid/overall_energy`
- Debug tip: `star_density>1.2` drastically reduces stars due to gate. Travel stops when `overall_energy` zero.
- Better approach needs to be found or completely different angle.
-### Bubble Stream Speed & Card Border

`bubble_stream_speed` used to be a single slider controlling the entire travel velocity budget. With reactivity enabled, bursts could never exceed that slider's ceiling, which made the stream feel sluggish on high-energy tracks when the baseline needed to stay low for idle drift.

**Card border syncing (Feb 2026):** The overlay now receives the global card border width every frame and forwards it to `bubble.frag` via `u_border_width`. Combined with widget setup seeding `BaseOverlayWidget.set_global_border_width()`, the very first bubble render uses the correct frame thickness instead of waiting for a mode cycle.

**New controls (Feb 2026, updated Feb 2026 PF-12)**

- `bubble_stream_constant_speed`: Baseline drift multiplier. Clamped to 0.05–cap inside the sim. Default `0.5`.
- `bubble_stream_speed_cap`: Absolute ceiling when reactivity + energy fully engage. Slider now spans `0.5–4.0×` so high-energy tracks can take advantage of faster flows, but the simulation applies a steeper gate curve so you need meaningful energy (and/or high reactivity) to graze the new limit. Default `2.0`.
- `bubble_stream_reactivity`: How aggressively the stream chases energy spikes. Default `0.5`.

**PF-12 (Bubble Speed Cap Scaling) behaviour:** The `BubbleSimulation` energy curve now raises the cap only when smoothed energy exceeds a reactivity-weighted gate (`speed_energy ** gate_exp`). This keeps idle drift anchored to the constant slider while still allowing the reactivity slider to unlock the 3–4× ceiling on loud passages. The UI slider and config clamp were both extended to 400%/4.0 to match the new sim headroom.

The simulation blends the baseline toward the cap as energy climbs and scales by a smoothed mid/high envelope:

```
vocal_speed = smooth_mid * 0.7 + smooth_high * 0.3
speed_energy = clamp(smooth(vocal_speed), 0, 1)
baseline = clamp(constant_speed, 0.1, cap)
cap_mix = baseline + (cap - baseline) * (reactivity * speed_energy)
speed_scale = baseline * (1 - reactivity) + cap_mix * reactivity
energy_scale = 0.15 + 0.85 * speed_energy
effective_speed = speed_scale * energy_scale
```

This keeps quiet sections floating at the baseline while letting peaks approach the cap.
(this should be rare and must be slowly gotten out of) ship will move up to 15px higher on Y axis, this is only when travelling at highest speed/highest bass/maximum trails.

**Swirl drift directions (Feb 2026):** `bubble_drift_direction` now understands `swirl_cw`/`swirl_ccw`. The simulation derives a tangential vector from the bubble’s center offset, pushes motion clockwise or counter-clockwise, and applies a mild radial correction so orbits stay inside the card. Use these when art direction calls for choreographed spiral flows instead of axis-locked swish wobble.

### 2.6 Bubble (particle sim + GLSL shader)
- Shader: `widgets/spotify_visualizer/shaders/bubble.frag`; CPU simulation lives in `widgets/spotify_visualizer/bubble_simulation.py` (COMPUTE pool, 110 bubble slots, 3-step motion trails).
- Defaults overview (see `Docs/Defaults_Guide.md` for full table):
  - Stream controls: `bubble_stream_constant_speed=0.5`, `bubble_stream_speed_cap=2.0`, `bubble_stream_reactivity=0.5`. Constant sets idle drift; reactivity raises the effective cap toward `speed_cap` on high energy; cap slider now spans 0.5×–4.0× and clamps in both UI + sim.
  - Drift: Swish (axis-locked wobble) and Swirl (clockwise/counter-clockwise orbital) live under `bubble_drift_direction`.
  - Counts/sizing: 8 big / 25 small bubbles, `bubble_big_size_max=0.038`, `bubble_small_size_max=0.018`, shared `bubble_growth=3.0` multiplier.
- Gradient vs specular directions are **decoupled**:
  - `bubble_gradient_direction` (Normal bucket) tilts the background gradient. Presets + SST exports carry this key; Always-Apply rule means the gradient keeps its heading even when Advanced is collapsed.
  - `bubble_specular_direction` (Advanced bucket) controls highlight wobble. UI exposes both comboboxes; shader uniforms `u_gradient_light/dark` and `u_specular_dir` are updated in `build_gpu_push_extra_kwargs()` + overlay `set_state()`.
- Preset slider behavior: curated bubble presets store the new gradient key, and switching presets toggles the Advanced container off/on (via `VisualizerPresetSlider`). Editing Advanced controls while on a curated slot auto-switches to Custom, guaranteeing curated payloads remain immutable.
- Diagnostics: `BubbleSimulation` logs `[SPOTIFY_VIS][BUBBLE][OVERDRIVE]` whenever reactivity pushes stream speed above 1.0× (cap gate) and `[SPOTIFY_VIS][BUBBLE][SWIRL]` entries when swirl drift is active. Use `SRPSS_VIZ_DIAGNOSTICS=1` to capture stream gate values when tuning.
- Shader uniforms: `u_bubble_count`, `u_bubbles_pos[110]`, `u_bubbles_extra[110]`, `u_bubbles_trail[330]`, `u_trail_strength`, `u_specular_dir`, `u_outline_color`, `u_specular_color`, `u_gradient_light`, `u_gradient_dark`, `u_pop_color`. Remember to update `tests/test_visualizer_settings_plumbing.py` + overlay kwarg tests when adding new keys to this mode.

### 2.7 Helix [RETIRED FOR BEING SHIT]
- Shader: `widgets/spotify_visualizer/shaders/helix.frag`
- Defaults: `helix_turns=6`, `helix_double=True`, `helix_speed=1.0`, `helix_glow_enabled=True`, `helix_glow_intensity=0.5`, `helix_glow_color=[0,200,255,180]`, `helix_reactive_glow=False`, `helix_growth=2.5`
- Uniforms: `u_helix_turns`, `u_helix_double`, `u_helix_speed`, `u_helix_glow*`, `u_helix_reactive_glow`, `u_fill_color`, `u_border_color`, `u_bass/mid/high/overall_energy`
- Audio reactivity: bass drives rotation (`speed*1.2 + bass*1.5`), mid widens tube radius, high widens rung width.

### 2.8 Preset repair workflow (updated Mar 12 2026)
- Tool: `tools/visualizer_preset_repair.py`
- Purpose: sanitize curated preset JSON/SST payloads by dropping foreign keys, enforcing per-mode defaults, and rewriting the payload in the new lean format (only `snapshot.widgets.spotify_visualizer` plus non-visualizer widgets when present).
- Key behaviour changes:
  - `_build_clean_payload()` now emits a single `spotify_visualizer` block; `snapshot.custom_preset_backup` + top-level `widgets.spotify_visualizer` are stripped.
  - Mandatory technical suffixes drive optional backfill logic; at present we only prune junk and preserve provided values (no auto backfill unless explicitly enabled).
  - `--repair-all` CLI flag + GUI “Repair All Presets” button batch-process every JSON under `presets/visualizer_modes/**`. Each file gets a `.bakN` backup before rewrite.
- Usage:
  1. Launch `python tools/visualizer_preset_repair.py` (GUI) or run `python tools/visualizer_preset_repair.py --repair-all` for CLI batch.
  2. Pick the mode/preset. Inspect the stats log (added/removed/changed keys). GUI keeps an undo stack per session.
  3. Validate repaired JSONs manually (`git diff` or `jq`) to ensure only the target keys remain.
- When to run it:
  - After adding/removing visualizer settings so curated presets stay in sync with runtime filters.
  - When QA hands you SST snapshots full of entire widget trees.
  - Before checking in curated preset edits, to guarantee they only contain allowed keys.
  - As part of doc refreshes so editors see only one copy of each control.

---

## 3. `_fft_to_bars` Pipeline (bar_computation.py)

1. **Window + FFT** – Hann window on 4096-sample block → real FFT → magnitude² → `log1p` floor shaping.
2. **Resolution boost** – When Windows drops loopback block size (<2048), apply `resolution_boost = block_size / 4096` to keep energy consistent.
3. **Log-spaced bands** – `_band_edges = logspace(0, Nyquist, bar_count+1)` cached per `bar_count`.
4. **Energy buckets** –
   ```python
   raw_bass = mean(freq_values[0:4])
   raw_mid = mean(freq_values[4:10])
   raw_treble = mean(freq_values[10:])
   ```
5. **Adaptive sensitivity** – target peak ≈0.285 via `multiplier = clamp(target/max(actual,1e-3), 0.05, 4.0) * resolution_boost`.
6. **Gradient + ridge template** – `(1 - dist)**2 * 0.82 + 0.18` blended with ridge template (legacy/curved).
7. **Hold + drop** – `hold_frames=2`, `drop_rate=0.08` prevents instant collapse.
8. **Running peak normalisation** – targets update toward current peak (`lerp(.., 0.02)`); bars clamped ≤1.0.

---

## 4. Playback Gating & Card Behaviour
- `_SpotifyBeatEngine.set_playback_state()` toggles FFT scheduling. When paused, FFT tasks halt and UI receives `[0.08, 0.0, ...]` floor.
- CPU savings: 100 % reduction in FFT compute work while idle.
- Card height growth configured via `widgets/spotify_visualizer/card_height.py` per mode (blob +2.5×, starfield +2×, etc.).

---

## 5. Settings, Styling, and UI
- All keys live under `widgets.spotify_visualizer.*` (see `Docs/Defaults_Guide.md`).
- **Visualizers Subtab + Toggle (Mar 2026):** Widgets tab now exposes a dedicated *Visualizers* subtab next to Media. The master toggle writes `widgets.spotify_visualizer.visualizers_enabled` and gates every Beat Visualizer control. Runtime still requires the Media widget to be enabled/visible, so the visualizer inherits the Media monitor/position after the toggle is on. `visualizers_enabled` + `enabled` persist independently, and both flags (plus Media enabled) must be true for the overlay to spawn.
- Widget styling follows `Docs/10_WIDGET_GUIDELINES.md` (shadow fade, overlay stacking, fade sync).
- Settings UI only surfaces controls for the active mode; use `rendering/widget_manager.py` for hydration (`set_bar_style`, `set_bar_colors`, `set_ghost_config`).
- Visualizer diagnostics obey environment gates: `SRPSS_PERF_METRICS=1` enables `[SPOTIFY_VIS][FLOOR]/[LATENCY]`, while `SRPSS_VIZ_DIAGNOSTICS=true` additionally enables `[SPOTIFY_VIS][TECHNICAL]` (mode, bar count, floors, sensitivity, block size, dynamic range, energy boost) whenever `_apply_technical_config_for_mode()` runs.

---

## 6. Logging & Telemetry
- `logs/screensaver_spotify_vis.log` – `[SPOTIFY_VIS][FLOOR]`, `[SPOTIFY_VIS][LATENCY]`, and (NEW) `[SPOTIFY_VIS][TIMER]` entries. Enable via `SRPSS_PERF_METRICS=1` + `--viz-diagnostics`. Expect to see (and use these to validate ripple fixes):
  - `Mode cycle requested: <from> -> <to>` when double-click starts.
  - `mode_phase=<N>` in latency lines so we can correlate phase 1→3→2.
  - Future work: `[SPOTIFY_VIS][TIMER] pause/resume` once instrumentation lands per Current Plan §3.
- `[PERF] [GL COMPOSITOR]` metrics are required when validating the ripple shader change—capture ripple transitions with 2+ waves enabled and confirm the final frame brightness matches the destination image (no additive spike at T=1.0).
- `logs/screensaver_perf.log` – Widget perf metrics (`SRPSS_PERF_METRICS=1`). Use to confirm `_on_tick` dt stays <50 ms even while the teardown gate holds bars.
- `logs/screensaver_spotify_vol.log` – Spotify volume overlay diagnostics.
- `[PERF] [GL COMPOSITOR]` – Transition timing; ensure visualizer tick loop not starved.

---

## 7. Mode-Cycle Teardown Lifecycle (Feb 2026)

Double-clicking the visualizer now performs a full teardown/restart to eliminate dynamic-floor drift and stale smoothing data. Use this reference while debugging:

| Phase | `_mode_transition_phase` | Visual | Engine/overlay action | Logging cues |
|-------|--------------------------|--------|----------------------|--------------|
| Idle | 0 | Bars active | Engine ticking normally | `[SPOTIFY_VIS][LATENCY] ... mode_phase=0` |
| Fade-out | 1 | ShadowFadeProfile fades card to 0 | `_on_mode_cycle_requested` kicks off fade and freezes card height | `Mode cycle requested` + fade latched to 0 |
| Waiting | 3 | Bars hidden (GPU fade set to 0) | `_mode_teardown_block_until_ready=True`; cancels FFT tasks via `_compute_gate_token`, calls `reset_smoothing_state()` + `reset_floor_state()`, restarts engine and records new `generation_id`; `_destroy_parent_overlay()` blanks the GL framebuffer, destroys the overlay (with `cleanup_gl()`), unregisters from PixelShift, and marks `_waiting_for_fresh_frame=True` so no shadows reattach early | Look for `[SPOTIFY_VIS][LATENCY] ... mode_phase=3` while audio worker reinitializes |
| Fade-in | 2 | Bars fade back in once fresh frame arrives | `_begin_mode_fade_in()` clears block + restarts ShadowFadeProfile fade-in; the first successful GPU push calls `_on_first_frame_after_cold_start()` to reapply shadows | Latency lines drop back toward 0 once phase=2 completes; when testing ripple brightness fixes, confirm the compositor logs for this phase show ring highlights tapering off before the final frame |

### Timing guarantees
- The widget now records `_pending_engine_generation` whenever `_reset_engine_state()` fires and blocks GPU pushes while `_waiting_for_fresh_engine_frame` is True. `_on_tick()` polls `get_latest_generation_with_frame()` every tick and only resumes Blob/bubble/osc updates once the engine publishes a frame for the new generation (or 750 ms elapse to guard silence).
- Bubble sim tasks are skipped whenever `_mode_teardown_block_until_ready` is true.
- `_mode_transition_ready` stays `False` until we enter fade-in, preventing GPU from pushing partially reset bars.

#### Blob “Crossover Persistence” instrumentation (Feb 2026)
- `_reset_engine_state()` now cancels compute tasks, zeroes `_display_bars/_target_bars`, and seeds `_waiting_for_fresh_engine_frame` so Blob can never reuse the previous smoothing envelope when re-entering mid-song.
- `SpotifyBarsGLOverlay` continues to log `[BLOB][DIAG] reset_reason=<reason> reset_age=<seconds>`; correlate any muted stage progress with missing fresh-engine frames.
- Regression test `test_blob_crossover_waits_for_fresh_engine_frame` enforces that `_waiting_for_fresh_engine_frame` gates GPU pushes until the beat engine reports the new generation.

### Debug checklist
1. Trigger double-click and confirm log shows `mode_phase` sequence `1 -> 3 -> 2 -> 0`.
2. Verify `[SPOTIFY_VIS][LATENCY]` never exceeds 60 ms once phase 3 completes.
3. Watch for `[PERF] FFT task submitted` spam after cycling; if you see old callbacks touching state, `_compute_gate_token` isn’t incrementing (bug).
4. When diagnosing “stuck bars,” confirm `_mode_teardown_block_until_ready` eventually clears; if not, either audio never produced a new frame or the timeout is not firing.
5. If residual overlays/shadows appear, inspect logs for `[SPOTIFY_VIS] Destroying SpotifyBarsGLOverlay` followed by `GL handles cleaned up` and ensure `_waiting_for_fresh_frame` is flipping back to `False` via `_on_first_frame_after_cold_start()`.

---

## 7. Regression Harness & Validation Checklist
1. `$env:SRPSS_PERF_METRICS='1'; python main.py --debug --viz` (≥15 s of playback).
2. Inspect `screensaver_spotify_vis.log` for healthy `[FLOOR]` entries and tick perf block.
3. Run `python -m pytest tests/test_visualizer_distribution.py tests/test_visualizer_playback_gating.py tests/test_visualizer_modes.py -v` after DSP or shader changes.
4. Overlay kwarg guard (Feb 2026): add/maintain a small regression test that instantiates `SpotifyBarsGLOverlay`, reflects `set_state` and asserts every key produced by `build_gpu_push_extra_kwargs()` is accepted. This would have caught the `sine_line1_shift` break immediately—keep it green whenever new settings are plumbed.
5. Uniform gating audit: whenever a new per-mode uniform is added, confirm the upload happens only inside that mode's section (see Current Plan §8). Add a quick GL overlay unit test if needed.
6. For blob/helix/starfield tweaks, visually confirm fades/shadows obey `Docs/10_WIDGET_GUIDELINES.md`.
7. When modifying `_fft_to_bars`, also update regression plots + docs.

---

### Quick reference links
- Beat engine / worker map: `widgets/spotify_visualizer/beat_engine.py`, `audio_worker.py`
- DSP + profiles: `widgets/spotify_visualizer/bar_computation.py`
- Mode shaders: `widgets/spotify_visualizer/shaders/*.frag`
- GL overlay: `widgets/spotify_bars_gl_overlay.py`
- Settings defaults: `core/settings/defaults.py`
