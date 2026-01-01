# AAMP2026 Phase 2 Detailed Plan – Image & Audio Pipeline Offload (Live Checklist)

Status: Planning-only (no code). Spec.md remains current-state. Main audit references this doc for detail.

## 0) Preconditions / Policy Anchors
- [ ] Lock-free/atomic + ThreadManager policy reaffirmed; no raw Qt timers.
- [ ] Phase 1 process isolation RFC finalized (schemas, supervisor model).

## 1) Scope & Goals
- [ ] Offload heavy pipelines to workers: image decode/prescale, RSS fetch/parse/mirror, FFT/beat smoothing, transition precompute.
- [ ] Preserve cache/promote semantics and UI non-blocking behavior.

## 2) Image Worker
- [ ] Inputs: `{path, target_size, profile, cache_key, ratio_policy}`.
- [ ] Outputs: shared-memory RGBA + metadata `{width, height, stride, format, generation, ts}`.
- [ ] Cache strategy: `path|scaled:WxH` key parity with ImageCache; shared-memory generation tied to cache entry.
- [ ] Ratio policy enforcement: local vs RSS request mix preserved (no inline decode in UI).

## 3) RSS Worker
- [ ] Inputs: `{feeds, max_items, ttl_hint, priority_policy}`.
- [ ] Disk mirror: path, rotation rules, TTL.
- [ ] Outputs: validated `ImageMetadata` list with `{url,title,ts,priority,ttl}`; cache path optional.
- [ ] Error handling: drop/skip with logged reason; no UI blocking.

## 4) FFT/Beat Worker
- [ ] Inputs: `{window, smoothing, ghosting_cfg, floor_config}`.
- [ ] Outputs: bins handle + ghost envelopes; generation/ts metadata.
- [ ] Must satisfy visualizer triple-buffer expectations and dt_max independence (non-blocking UI poll).
- [ ] Synthetic test baseline (from Phase 0 guardrail) rerun after workerization.
- [ ] Preserve dynamic floor pipeline (floor_mid_weight, dynamic_floor_ratio, headroom/hardness, silence thresholds) plus sensitivity/decay tuning knobs (`set_sensitivity_config`, `_apply_smoothing` tau/alpha choices) so workerized path matches current resilience to app audio changes.
- [ ] Preserve current FFT math + smoothing semantics (Spotify visualizer) before migrating. Reference snapshot:

```python
# widgets/spotify_visualizer_widget.py:_fft_to_bars (excerpt)
np.log1p(mag, out=mag)
np.power(mag, 1.2, out=mag)
if n > 4:
    if self._smooth_kernel is None:
        self._smooth_kernel = np.array([0.25, 0.5, 0.25], dtype="float32")
    mag = np.convolve(mag, self._smooth_kernel, mode="same")
...
if use_recommended:
    auto = float(getattr(self, "_recommended_sensitivity_multiplier", 0.285))
    auto = max(0.25, min(2.5, auto))
    if resolution_boost > 1.0:
        damp = min(0.4, (resolution_boost - 1.0) * 0.55)
        auto = max(0.25, auto * (1.0 - damp))
    else:
        boost = min(0.25, (1.0 - resolution_boost) * 0.4)
        auto = min(2.5, auto * (1.0 + boost))
    base_noise_floor = max(self._min_floor, min(self._max_floor, noise_floor_base / auto))
    expansion = expansion_base * max(0.55, auto ** 0.35)
else:
    base_noise_floor = max(self._min_floor, min(self._max_floor, noise_floor_base / user_sens))
...
profile_template = np.array(
    [0.10, 0.15, 0.25, 0.50, 1.0, 0.45, 0.25, 0.08,
     0.25, 0.45, 1.0, 0.50, 0.25, 0.15, 0.10],
    dtype="float32",
)
for i in range(bands):
    offset = abs(i - center)
    base = profile_shape[i] * overall_energy
    if offset == 3:
        base = base * 1.15 + bass_energy * 0.35
    elif offset == 4:
        base = base * 0.82
    if offset == 0:
        vocal_drive = mid_energy * 4.0
        base = vocal_drive * 0.90 + base * 0.10
    ...
```

```python
# widgets/spotify_visualizer_widget.py:_SpotifyBeatEngine._apply_smoothing (excerpt)
dt = max(0.0, now_ts - last_ts) if last_ts >= 0.0 else 0.0
if dt > 2.0 or dt <= 0.0:
    self._smoothed_bars = list(target_bars)
    return self._smoothed_bars

base_tau = self._smoothing_tau
tau_rise = base_tau * 0.35  # Fast attack
tau_decay = base_tau * 3.0  # Slow decay
alpha_rise = 1.0 - math.exp(-dt / tau_rise)
alpha_decay = 1.0 - math.exp(-dt / tau_decay)

for i in range(bar_count):
    cur = smoothed[i] if i < len(smoothed) else 0.0
    tgt = target_bars[i] if i < len(target_bars) else 0.0
    alpha = alpha_rise if tgt >= cur else alpha_decay
    smoothed[i] = cur + (tgt - cur) * alpha
```

This code must be preserved (or reimplemented deterministically) inside the FFT worker to avoid fidelity loss; capture a `/bak/widgets/spotify_visualizer_widget.py` snapshot before moving logic.

## 5) Transition Precompute Worker
- [ ] Inputs: `{transition_type, params, duration, direction_history, seed}`.
- [ ] Outputs: pre-baked payloads (lookup tables, block sequences) + generation.
- [ ] Preserve settings overrides (duration, direction history) from SettingsManager models.

## 6) Shared Memory & Messaging (Reuse Phase 1 Schemas)
- [ ] Use Phase 1 common fields and shared-memory headers (RGBA/FFT). Size caps enforced per channel.
- [ ] Ownership/freshness: generation + seq guard; drop stale.

## 7) Queue & Backpressure
- [ ] Per-channel caps (image/rss/fft/precompute); drop-old policy; queue length metrics.
- [ ] Non-blocking UI poll wrappers; overflow logs throttled.

## 8) Supervisor Integration
- [ ] Workers registered with supervisor API; heartbeat/health monitoring per Phase 1 rules.
- [ ] Restart/backoff policies apply equally to all new workers.

## 9) Testing Strategy (Design)
- [ ] Extend `tests/helpers/worker_sim.py` for image/rss/fft/precompute payloads with latency/failure injection.
- [ ] End-to-end latency tests: worker delay still keeps dt_max bounded.
- [ ] Cache parity tests: shared-memory promotion matches existing ImageCache behavior.
- [ ] Visualizer synthetic test rerun after FFT worker integration.

## 10) Documentation & Backups Plan
- [ ] Keep audit Phase 2 checklist in sync with this doc.
- [ ] Spec.md stays current-state (no planning).
- [ ] Index.md: add worker modules when implemented.
- [ ] `/bak`: snapshots pre/post for modules touched in Phase 2.

## 11) Exit Criteria (Planning Only)
- [ ] All checkboxes resolved with concrete decisions documented.
- [ ] Main audit updated with any deltas; no code written.
