# Spotify Visualizer Debug Notes

> **Last updated**: Feb 2026 (post M-4 refactor)  
> **Scope**: Audio capture, FFT pipeline, bar computation, smoothing, playback gating, volume overlay

This document captures the current, tested behaviour for the Spotify bar visualizer. It intentionally avoids Spotify-version-specific assumptions — we only consume loopback audio + GSMTC metadata.

---

## 1. Architecture (Post-Refactor)

```python
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

Tick helpers: widgets/spotify_visualizer/tick_helpers.py
 ├─ get_transition_context()  — transition metrics from parent DisplayWidget
 ├─ apply_visual_smoothing()  — per-frame EMA (rise ~55ms, decay ~145ms)
 ├─ compute_bar_geometry()    — cached bar rect calculation
 └─ update_perf_metrics()     — PERF window aggregation

GPU overlay: rendered by GLCompositorWidget via overlay paint path
CPU fallback: QPainter bar drawing in SpotifyVisualizerWidget.paintEvent()
```

### Module Map

| Module | File | Purpose |
|--------|------|---------|
| Widget | `widgets/spotify_visualizer_widget.py` | QWidget overlay, paint, tick dispatch |
| Beat Engine | `widgets/spotify_visualizer/beat_engine.py` | Singleton engine, smoothing, playback gating |
| Audio Worker | `widgets/spotify_visualizer/audio_worker.py` | Loopback capture, FFT scheduling |
| Bar Computation | `widgets/spotify_visualizer/bar_computation.py` | `_fft_to_bars()` DSP pipeline |
| Tick Helpers | `widgets/spotify_visualizer/tick_helpers.py` | Visual smoothing, geometry cache, perf metrics |
| Audio Capture | `utils/audio_capture.py` | WASAPI loopback interface |
| FFT Worker | `core/process/workers/fft_worker.py` | Out-of-process FFT computation |

### Key Design Points

1. **Audio capture** is shared via singleton `_SpotifyBeatEngine`; widgets subscribe by ref-counting.
2. **FFT → bar conversion** lives in `bar_computation.py` (`_fft_to_bars()`, `process_via_fft_worker()`).
3. **Smoothing** has two layers:
   - COMPUTE-thread smoothing in beat engine (`_smoothed_bars`, tau ~120ms, hysteresis 8%, min-change 5%).
   - Per-frame EMA in tick helpers (`_apply_visual_smoothing`, rise ~55ms, decay ~145ms).
4. **Thread safety**: No raw `QTimer`s. All recurring work through `ThreadManager`. Lock-free `TripleBuffer` for audio/bar transfer.
5. **Playback gating**: FFT halted when Spotify is not playing; 1-bar floor (0.08) for visual continuity.

---

## 2. `_fft_to_bars` Pipeline (bar_computation.py)

1. **FFT normalisation**: `log1p` + power curve. Low-resolution detection via `resolution_boost` adapts when Windows drops loopback block size.
2. **Logarithmic band edges**: Cached (`_band_edges`). RMS per band → `freq_values`.
3. **Energy buckets**: `raw_bass = mean(freq_values[:4])`, `raw_mid = mean(freq_values[4:10])`, `raw_treble = mean(freq_values[10:])`.
4. **Adaptive sensitivity**: Pins to ~0.285× multiplier. Auto-dampens on low-res, lifts on high-res. Dynamic floor with drop relief prevents bars vanishing on bass collapse.
5. **Gradient + template**: `(1 - dist)^2 * 0.82 + 0.18` base gradient. Ridge template (±3) stretched to bar_count, scaled 0.45–1.0.
6. **Low-res sculpting** (when `resolution_boost > 1.05`): Enforces target_map with drop-aware damping.
7. **Hold + drop logic**: Holds short segments during large drops. `drop_gain` boosted for low-res paths.
8. **Normalization**: `_running_peak` + `target_peak` gently compresses when peaks drift >1.18. No global peak normalization.

---

## 3. Playback Gating

- **State detection**: `_SpotifyBeatEngine.set_playback_state()` from `handle_media_update()`.
- **FFT gating**: `tick()` checks `_is_spotify_playing`; skips FFT scheduling when False.
- **1-bar floor**: Returns `[0.08, 0.0, ...]` when not playing for visual continuity.
- **CPU savings**: 100% reduction in FFT compute tasks when paused/stopped.

---

## 4. Settings & Styling

- All keys under `widgets.spotify_visualizer.*` via `SettingsManager`.
- Defaults: `bar_fill_color = [255,255,255,230]`, `bar_border_color = [255,255,255,255]`.
- Runtime hydration via `rendering/widget_manager.py`: `set_bar_style`, `set_bar_colors`, `set_ghost_config`.
- Widget follows `Docs/10_WIDGET_GUIDELINES.md` for card styling and overlay integration.

---

## 5. Logging + Diagnostics

| Log | Purpose |
|-----|---------|
| `logs/screensaver_spotify_vis.log` | Bar dumps every ~30 frames, PERF snapshots (dt_min, dt_max, avg_fps) |
| `logs/screensaver_spotify_vol.log` | Spotify volume overlay diagnostics |
| `logs/screensaver_perf.log` | Aggregated PERF metrics (set `SRPSS_PERF_METRICS=1`) |

---

## 6. Regression Harness

`tests/test_visualizer_distribution.py` encodes "known good" behaviour:

1. **REALISTIC REACTIVITY (synthetic)**: 60 FPS / 4s sinusoid with valley/micro drops. PASS criteria: centre ≥ 0.82 peak, avg drop ≥ 0.07, ridge ratios, edge range ≥ 20%, spike ratio ≤ 12%.
2. **LOG SNAPSHOT**: Replays recent frames from `screensaver_spotify_vis.log` (360 frames default).

Additional tests:
- `tests/test_visualizer_playback_gating.py` — playback state gating, CPU savings
- `tests/test_spotify_visualizer_widget.py` — unit tests for widget lifecycle

**Rule**: Do not tweak `_fft_to_bars` without running the distribution harness. If harness fails but live looks correct, adjust test thresholds, not runtime code.

---

## 7. Known Limits

1. **dt spikes**: PERF logs show `dt_max_ms` ≈70–100 ms during heavy transitions. Visual smoothing hides most; frame interpolation is a future lever.
2. **Edge pops on ultra-low resolution**: When Windows drops to 256-sample block size, drop accumulator clamps harder. Low-res `target_map` + `drop_gain` boost mitigates.
3. **Audio worker fallback**: If beat engine fails, widget falls back to inline FFT. Monitor `[SPOTIFY_VIS] compute task callback failed` for ThreadManager saturation.

---

## 8. How to Validate After Changes

1. Run `python main.py --debug` with Spotify playing for ≥10s.
2. Inspect `logs/screensaver_spotify_vis.log` — ridge should peak at bars 4/10, bars 5/9 trimmed, centre valley visible during drops.
3. Run `python -m pytest tests/test_visualizer_distribution.py tests/test_visualizer_playback_gating.py -v`.
4. Optional: `python -m pytest tests/test_spotify_visualizer_widget.py -v`.

---

*Living document. Update when bar-shaping, smoothing, module structure, or regression thresholds change.*
