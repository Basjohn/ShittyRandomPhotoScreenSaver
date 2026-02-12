# Spotify Visualizer Debug Notes

> **Last updated**: Feb 2026  
> **Scope**: All 6 visualizer modes, audio capture, FFT pipeline, bar computation, smoothing, playback gating, volume overlay

This document captures the current, tested behaviour for the Spotify visualizer system. We only consume loopback audio + GSMTC metadata — no Spotify-version-specific assumptions.

---

## 1. Architecture

```
SpotifyVisualizerWidget (widgets/spotify_visualizer_widget.py)
 └─ Shared _SpotifyBeatEngine (singleton per process)
     │  Location: widgets/spotify_visualizer/beat_engine.py
     │  Factory:  get_shared_spotify_beat_engine()
     │
     ├─ SpotifyVisualizerAudioWorker (widgets/spotify_visualizer/audio_worker.py)
     │   ├─ Loopback audio capture (WASAPI via utils/audio_capture.py)
     │   ├─ FFT computation (inline or via FFTWorker process)
     │   └─ _fft_to_bars() DSP pipeline (widgets/spotify_visualizer/bar_computation.py)
     │
     ├─ TripleBuffer<_AudioFrame>   — lock-free audio sample transfer
     ├─ TripleBuffer<List[float]]>  — lock-free bar magnitudes transfer
     ├─ ThreadManager (COMPUTE pool) for FFT + smoothing scheduling
     └─ Anti-flicker: segment hysteresis + min-change thresholds

Shared data from BeatEngine:
 ├─ get_smoothed_bars()   → List[float]      (pre-smoothed for UI)
 ├─ get_waveform()        → List[float] (256) (raw samples for oscilloscope)
 └─ get_energy_bands()    → EnergyBands       (bass/mid/high/overall for all modes)

Tick helpers: widgets/spotify_visualizer/tick_helpers.py
 ├─ get_transition_context()  — transition metrics from parent DisplayWidget
 ├─ apply_visual_smoothing()  — per-frame EMA (rise ~55ms, decay ~145ms)
 ├─ rebuild_geometry_cache()  — cached bar rect calculation (dynamic segments)
 └─ log_perf_snapshot()       — PERF window aggregation

GPU overlay: SpotifyBarsGLOverlay renders via per-mode GLSL shaders
CPU fallback: QPainter bar drawing in SpotifyVisualizerWidget.paintEvent()
```

### Module Map

| Module | File | Purpose |
|--------|------|---------|
| Widget | `widgets/spotify_visualizer_widget.py` | QWidget overlay, paint, tick dispatch |
| Beat Engine | `widgets/spotify_visualizer/beat_engine.py` | Singleton engine, smoothing, playback gating |
| Audio Worker | `widgets/spotify_visualizer/audio_worker.py` | Loopback capture, FFT scheduling |
| Bar Computation | `widgets/spotify_visualizer/bar_computation.py` | `_fft_to_bars()` DSP pipeline |
| Energy Bands | `widgets/spotify_visualizer/energy_bands.py` | Bass/mid/high/overall extraction from FFT bars |
| Card Height | `widgets/spotify_visualizer/card_height.py` | Per-mode card height expansion (growth factors) |
| Tick Helpers | `widgets/spotify_visualizer/tick_helpers.py` | Visual smoothing, geometry cache, perf metrics |
| Shader Loader | `widgets/spotify_visualizer/shaders/__init__.py` | GLSL source loading for multi-shader architecture |
| GL Overlay | `widgets/spotify_bars_gl_overlay.py` | QOpenGLWidget, shader compilation, uniform dispatch |
| Audio Capture | `utils/audio_capture.py` | WASAPI loopback interface |
| FFT Worker | `core/process/workers/fft_worker.py` | Out-of-process FFT computation |

### Key Design Points

1. **Audio capture** is shared via singleton `_SpotifyBeatEngine`; widgets subscribe by ref-counting.
2. **FFT → bar conversion** lives in `bar_computation.py` (`_fft_to_bars()`, `process_via_fft_worker()`).
3. **Smoothing** has two layers:
   - COMPUTE-thread smoothing in beat engine (`_smoothed_bars`, tau ~120ms, hysteresis 8%, min-change 5%).
   - Per-frame EMA in tick helpers (`apply_visual_smoothing`, rise ~55ms, decay ~145ms).
4. **Thread safety**: No raw `QTimer`s. All recurring work through `ThreadManager`. Lock-free `TripleBuffer` for audio/bar transfer.
5. **Playback gating**: FFT halted when Spotify is not playing; 1-bar floor (0.08) for visual continuity.
6. **Multi-shader**: All 6 GLSL programs compiled at `initializeGL()`; `paintGL()` dispatches to active mode.
7. **Dynamic segments**: Spectrum segment count adapts to card height (~4px/segment + 1px gap, 8–64 range).

---

## 2. Visualizer Modes

### 2.1 Spectrum

**Shader**: `widgets/spotify_visualizer/shaders/spectrum.frag`

Classic segmented bar analyzer with per-bar ghost peak trails.

**Key uniforms (GPU or CPU fallback):**

| Uniform | Type | Source | Notes |
|---------|------|--------|-------|
| `u_bars[64]` | float array | `SpotifyBarsGLOverlay._bars` | Values pre-scaled ×0.55 to match Spotify 55% mixer reference |
| `u_peaks[64]` | float array | `_peaks` | Same ×0.55 scaling, drives ghost envelope |
| `u_bar_count` | int | widget | Clamped ≤64 |
| `u_segments` | int | widget | Dynamic: `max(8, min(64, floor(inner_height / 5)))` |
| `u_bar_height_scale` | float | widget | `max(1.0, card_height / 80px)` |
| `u_single_piece` | bool | widget/settings | **Default = 1 (v2.75)** |
| `u_fill_color`, `u_border_color` | vec4 | settings | SRGB → linear handled by Qt |
| `u_playing` | bool | beat engine | 1 = audio active |
| `u_ghost_alpha` | float | settings | Zeroed when ghosting disabled |

**GPU-only extras:** `u_resolution`, `u_dpr`, `u_fade`, `u_time` for overlay management.

**Behaviour:**
- Bars are boosted ×1.2 before segment mapping; always at least 1 active segment
- Ghost segments drawn above active height using decaying peak envelope with vertical alpha falloff
- Segment count dynamically scales with card height: `inner_h // 5` (4px segment + 1px gap), clamped 8–64
- CPU fallback uses QPainter with cached geometry (same layout math)
- **Curved Profile** (optional toggle): Dual-curve mirrored layout with bass peak at outer edges,
  dip, vocal peak mid-way, calm center. Template: `[1.0, 0.82, 0.70, 0.61, 0.55, 0.85, 0.72, 0.35, ...]`
  (mirrored). Energy adjustments are profile-aware: outer bars bass-reactive, mid bars vocal-reactive,
  center balanced. Legacy profile retains original behavior.

### 2.2 Oscilloscope

**Shader**: `widgets/spotify_visualizer/shaders/oscilloscope.frag`

Catmull-Rom spline waveform with per-band energy-reactive glow and up to 3 lines.
Oscilloscope has its own independent settings (`_osc_*` attributes in widget).

**Key uniforms:**
- `u_waveform[256]`, `u_waveform_count` — raw waveform buffer (temporally smoothed CPU-side)
- `u_line_color`, `u_glow_color` — primary line appearance
- `u_glow_enabled`, `u_glow_intensity`, `u_reactive_glow` — glow control
- `u_sensitivity` (default 3.0), `u_smoothing` (0–1) — waveform processing
- `u_line_count` (1–3), `u_line{2,3}_color`, `u_line{2,3}_glow_color` — multi-line
- `u_osc_line_dim` — optional half-strength dimming on lines 2/3
- `u_bass_energy`, `u_mid_energy`, `u_high_energy`, `u_overall_energy` — per-band energy

**Waveform pipeline:**
1. `get_waveform_sample(idx)` — modular wrap for circular buffer safety
2. `smoothed_sample(center)` — Gaussian kernel (half-width 1–12 taps based on `u_smoothing`)
3. `catmull_rom()` — sub-sample interpolation between smoothed taps
4. `sample_waveform(nx, offset)` — full pipeline with manual tanh soft-saturation

**Multi-line per-band energy:**
- Single-line mode: line 1 uses `u_overall_energy`
- Multi-line mode: line 1 = bass, line 2 = mid (vocals), line 3 = high (cymbals)
- Each line's amplitude and glow reactive to its own band energy
- CPU-side smoothed bands (`_osc_smoothed_bass/mid/high`) prevent glow flicker

### 2.3 Blob

**Shader**: `widgets/spotify_visualizer/shaders/blob.frag`

2D SDF organic metaball with audio-reactive deformation and configurable glow.

**Key uniforms:**
- `u_bass_energy`, `u_mid_energy`, `u_high_energy`, `u_overall_energy` — energy bands
- `u_blob_color`, `u_blob_glow_color`, `u_blob_edge_color`, `u_blob_outline_color` — colours
- `u_blob_pulse` (0–2) — bass pulse intensity multiplier
- `u_blob_size` (0.3–2.0) — relative blob scale
- `u_blob_glow_intensity` (0–1) — glow size/strength
- `u_blob_reactive_glow` (0/1) — static vs energy-reactive glow
- `u_blob_smoothed_energy` — CPU-smoothed overall energy (prevents glow flicker)

| Parameter | Default | Range | Sourced from |
|-----------|---------|-------|--------------|
| `u_blob_pulse` | 1.75 | 0.0–2.0 | settings (`blob_pulse`) |
| `u_blob_width` | 0.9 | 0.1–1.0 | settings |
| `u_blob_size` | 0.5 | 0.3–2.0 | settings |
| `u_blob_glow_intensity` | 0.6 | 0.0–1.0 | settings |
| `u_blob_reactive_glow` | 1 | bool | settings |
| `u_blob_smoothed_energy` | dynamic | 0–1 | overlay CPU smoothing |

**SDF deformation layers (constant and reactive cleanly separated):**
1. **Bass pulse**: `r += bass * 0.077 * pulse` with dip contraction
2. **Constant wobble** (time-driven, gated by `cw`): 4 sine layers at angular freq 3/5/7/1. Zero when `cw=0`.
3. **Reactive wobble** (energy-driven, gated by `rw`): 4 sine layers at angular freq 3/5/7/11 driven by mid/high energy. Zero when silent.
4. **Vocal-reactive wobble**: 2 smooth low-freq layers driven by `u_mid_energy * rw`
5. **Stretch tendency**: quadratic peak-energy tendrils at angular freq 2/3/5/7/1
6. **Reactive deformation scale**: `rd` range 0–3.0 (was 0–2.0), quadratic above 1.0

**CPU-side smoothing** (in `spotify_bars_gl_overlay.py`):
- `_blob_smoothed_energy`: fast rise (~50ms tau), slow decay (~300ms tau)
- Prevents glow flickering and ensures shrink contraction is smooth

**Card height**: Default growth factor 2.5× (configurable via `card_height.py`)

### 2.6 Sine Wave

**Shader**: `widgets/spotify_visualizer/shaders/sine_wave.frag`

Dedicated sine wave visualizer with audio-reactive amplitude, independent settings from Oscilloscope.

**Settings pipeline**: Sine wave has its own `_sine_*` attributes in the widget, separate from `_osc_*`.
The `_on_tick` method is mode-aware: when `mode_str == 'sine_wave'`, it sends sine-specific values
for glow, color, speed, sensitivity, line count, and line offset bias to the GL overlay.

**Key uniforms** (same names as oscilloscope but fed from sine-specific widget attributes):
- `u_line_color`, `u_glow_color` — sine line/glow appearance (from `_sine_line_color`, `_sine_glow_color`)
- `u_glow_enabled`, `u_glow_intensity`, `u_reactive_glow` — glow control (from `_sine_glow_*`)
- `u_sensitivity` — amplitude scaling (from `_sine_sensitivity`, default 1.0)
- `u_osc_speed` — wave animation speed (from `_sine_speed`, default 1.0)
- `u_osc_sine_travel` — travel direction: 0=none, 1=left, 2=right (from `_sine_wave_travel`)
- `u_line_count` (1–3) — multi-line (from `_sine_line_count`)
- `u_osc_line_offset_bias` — vertical spread (from `_sine_line_offset_bias`)
- `u_bass_energy`, `u_mid_energy`, `u_high_energy`, `u_overall_energy` — per-band energy

**Card height**: Default growth factor 1.0× (configurable up to 4.0×)

### 2.4 Starfield (dev-gated: `SRPSS_ENABLE_DEV=true`)

**Shader**: `widgets/spotify_visualizer/shaders/starfield.frag`

Point-star starfield with nebula background and audio-reactive travel/glow.

**Key uniforms:**
- `u_star_density` — grid density multiplier
- `u_travel_speed` — base forward-travel speed
- `u_star_reactivity` — energy-to-glow multiplier
- `u_travel_time` — CPU-accumulated monotonic travel (never reverses)
- `u_nebula_tint1`, `u_nebula_tint2` — nebula background colours
- `u_nebula_cycle_speed` — tint crossfade rate
- `u_bass_energy`, `u_mid_energy`, `u_overall_energy`

**Key features:**
- 5 depth layers with perspective scaling and fade
- ~10% of stars are "big" with diffraction spikes
- Nebula background uses 5-octave FBM value noise
- Travel gated on `overall_energy` so stars stop when music is silent
- Bass energy boosts travel speed via `bass * reactivity * 0.4`

**Card height**: Default growth factor 2.0×

### 2.5 Helix

**Shader**: `widgets/spotify_visualizer/shaders/helix.frag`

Parametric 3D DNA double-helix with Blinn-Phong tube shading.

**Key uniforms:**
- `u_helix_turns` (min 2) — number of helix turns across card
- `u_helix_double` (0/1) — single or double helix with rungs
- `u_helix_speed` — base rotation speed
- `u_helix_glow_enabled`, `u_helix_glow_intensity`, `u_helix_glow_color` — glow
- `u_helix_reactive_glow` (0/1) — energy-reactive glow sigma
- `u_fill_color`, `u_border_color` — strand colours (strand A / strand B)
- `u_bass_energy`, `u_mid_energy`, `u_high_energy`, `u_overall_energy`

**Audio reactivity:**
- Bass drives rotation speed (`speed * 1.2 + bass * 1.5`) and coil amplitude
- Mid energy widens tube radius
- High energy widens rung half-width
- Overall energy boosts brightness

**Rendering layers (depth-sorted):**
1. Back strand (double-helix only) — Blinn-Phong shaded tube
2. Rungs/base pairs (double-helix only) — two-tone, depth-shaded
3. Front strand — always drawn on top
4. Glow halo — Gaussian falloff around closest strand when nothing else hit

**Card height**: Default growth factor 2.0×

---

## 3. `_fft_to_bars` Pipeline (bar_computation.py)

1. **Window + FFT**
   - Capture block = 4096 samples @ 48 kHz (loopback). Windowed with Hann.
   - Real FFT → magnitude² → `log1p` to reduce floor spread.
2. **Resolution boost**
   - When Windows downshifts loopback buffer (<2048 samples), apply `resolution_boost = block_size / 4096` to preserve energy.
3. **Log-spaced bands**
   - `_band_edges = logspace(0, Nyquist, bar_count + 1)` cached per bar_count.
   - Energy per band = RMS of FFT bins within edges.
4. **Energy buckets (for shaders)**
   ```python
   raw_bass = mean(freq_values[0:4])
   raw_mid = mean(freq_values[4:10])
   raw_treble = mean(freq_values[10:])
   ```
5. **Adaptive sensitivity (`_resolve_sensitivity`)**
   ```python
   target = 0.285
   actual = max(freq_values)
   multiplier = clamp(target / max(actual, 1e-3), 0.05, 4.0)
   multiplier *= resolution_boost
   ```
6. **Gradient + ridge template**
   ```python
   base = (1 - dist)**2 * 0.82 + 0.18  # dist = normalized distance from left edge
   shaped = base * ridge_template[i]
   ```
   - Ridge template derived from Spotify desktop capture; stretched via cubic interpolation to current bar_count.
7. **Hold + drop**
   - `hold_frames = 2`, `drop_rate = 0.08` to prevent instant collapses.
8. **Running peak normalization**
   ```python
   if peak > target_peak * 1.18:
       target_peak = peak
   else:
       target_peak = lerp(target_peak, peak, 0.02)
   bars = [min(1.0, val / target_peak) for val in shaped]
   ```

---

## 4. Playback Gating

- **State detection**: `_SpotifyBeatEngine.set_playback_state()` from `handle_media_update()`.
- **FFT gating**: `tick()` checks `_is_spotify_playing`; skips FFT scheduling when False.
- **1-bar floor**: Returns `[0.08, 0.0, ...]` when not playing for visual continuity.
- **CPU savings**: 100% reduction in FFT compute tasks when paused/stopped.

---

## 5. Settings & Styling

- All keys under `widgets.spotify_visualizer.*` via `SettingsManager`.
- Runtime hydration via `rendering/widget_manager.py`: `set_bar_style`, `set_bar_colors`, `set_ghost_config`.
- Widget follows `Docs/10_WIDGET_GUIDELINES.md` for card styling and overlay integration.
- Settings UI shows only the active mode's controls (conditional visibility).

---

## 6. Logging + Diagnostics

| Log | Purpose |
|-----|---------|
| `logs/screensaver_spotify_vis.log` | Bar dumps, PERF snapshots (dt_min, dt_max, avg_fps) |
| `logs/screensaver_spotify_vol.log` | Spotify volume overlay diagnostics |
| `logs/screensaver_perf.log` | Aggregated PERF metrics (set `SRPSS_PERF_METRICS=1`) |

---

## 7. Regression Harness

`tests/test_visualizer_distribution.py` encodes "known good" behaviour:

1. **REALISTIC REACTIVITY (synthetic)**: 60 FPS / 4s sinusoid with valley/micro drops.
2. **LOG SNAPSHOT**: Replays recent frames from `screensaver_spotify_vis.log`.

Additional tests:
- `tests/test_visualizer_playback_gating.py` — playback state gating, CPU savings
- `tests/test_spotify_visualizer_widget.py` — unit tests for widget lifecycle
- `tests/test_visualizer_modes.py` — per-mode basics (creation, attributes, segments)

**Rule**: Do not tweak `_fft_to_bars` without running the distribution harness. If harness fails but live looks correct, adjust test thresholds, not runtime code.

---

## 8. Known Limits

1. **dt spikes**: PERF logs show `dt_max_ms` ≈70–100 ms during heavy transitions. Visual smoothing hides most.
2. **Edge pops on ultra-low resolution**: When Windows drops to 256-sample block size, low-res mitigations apply.
3. **Audio worker fallback**: If beat engine fails, widget falls back to inline FFT. Monitor `[SPOTIFY_VIS] compute task callback failed`.
4. **Starfield dev-gated**: Visual quality and performance still being tuned.

---

## 9. How to Validate After Changes

1. Run `$env:SRPSS_PERF_METRICS='1'; python main.py --debug` with Spotify playing for ≥10s.
2. Inspect `logs/screensaver_spotify_vis.log` — check bar distribution and PERF snapshots.
3. Run `python -m pytest tests/test_visualizer_distribution.py tests/test_visualizer_playback_gating.py tests/test_visualizer_modes.py -v`.
4. For blob/helix/starfield: visually confirm smooth reactivity, no flicker, correct card expansion.

---

*Living document. Update when bar-shaping, smoothing, shader uniforms, module structure, or regression thresholds change.*
