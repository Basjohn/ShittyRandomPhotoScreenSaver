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
