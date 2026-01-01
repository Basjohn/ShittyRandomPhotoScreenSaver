# AAMP2026 Phase 1 Detailed Plan – Process Isolation Foundations (Live Checklist)

Status: Planning-only (no code). Spec.md remains current-state. Main audit references this doc for detail.

## 0) Preconditions / Policy Anchors
- [ ] Re-affirm lock-free/atomic policy: ThreadManager for all business logic; no raw Qt timers; lock only if unavoidable and documented.
- [ ] Confirm fallback groups (A→B→C) and `[PERF]` tagging conventions in audit/Spec/Index.
- [ ] Ensure visualizer synthetic baseline saved/double-verified before FFT worker changes (prereq for later phases).

## 1) Worker Roles & Responsibilities
- [ ] ImageWorker: decode/prescale; enforce cache key `path|scaled:WxH`; ratio policy (local vs RSS); returns shared-memory RGBA + metadata; clamps outputs to configured max size; honors sharpen flag when applicable.
- [ ] RSSWorker: fetch/parse RSS/JSON; disk mirror; emits validated `ImageMetadata` list with TTL/priorities; filters invalid/oversized payloads; redacts PII-equivalent fields from logs.
- [ ] FFTWorker: loopback ingest + FFT + smoothing; outputs bins + ghost envelopes; non-blocking to UI; handles device-missing gracefully; exposes smoothing/floor config metadata.
- [ ] TransitionPrepWorker: CPU precompute (lookup tables/block sequences) keyed by settings (duration/direction/history); deterministic seeds; per-type payload size caps.

## 2) Message Schemas (Requests/Responses)
- [ ] Common fields: `seq_no`, `correlation_id`, `ts_req`, `ts_res`, `worker_type`, `payload_size`, `version`; immutable payloads only.
- [ ] ImageWorker req/resp: `{path, target_size, profile, cache_key, ratio_policy}` → `{success, error?, shm_handle?, width, height, stride, format, generation, ts, diagnostic?}`.
- [ ] RSSWorker req/resp: `{feeds, max_items, ttl_hint, priority_policy}` → `{success, error?, items:[{url,title,ts,priority,ttl}], cache_path?, diagnostic?}`.
- [ ] FFTWorker req/resp: `{window, smoothing, ghosting_cfg, floor_cfg}` → `{success, error?, bins_handle, bins_len, generation, smoothing_meta, ts}`.
- [ ] TransitionPrep req/resp: `{transition_type, params, seed, history}` → `{success, error?, payload_handle|data, generation, ts}`.
- [ ] Serialization rules: forbid QImage/QPixmap; compression flag only if bounded size; strict size caps per channel with reject + log.

## 3) Shared Memory Schema
- [ ] RGBA header: `{handle, size_bytes, width, height, stride, format='RGBA8', producer_pid, generation, ts, checksum?}`; optional checksum for debugging only.
- [ ] FFT header: `{handle, size_bytes, bins_len, window, smoothing_meta, producer_pid, generation, ts}`.
- [ ] Ownership/freshness: producer writes generation; consumer checks generation + seq; drop stale generations; metrics for stale drops.
- [ ] Lifetime: supervisor owns cleanup on worker restart; UI drops on missing/invalid handle; document cleanup order.

## 4) Supervisor (`core/process/`) – API & Health Model
- [ ] API surface: `start`, `stop`, `restart`, `heartbeat`, capability flags (`supports_shared_mem`, `supports_gpu`); enumerate worker types.
- [ ] Health: heartbeat interval, missed-heartbeat threshold, exponential backoff restart, max restarts/window; metrics counters; structured `[PERF]` + `[HEALTH]` logs.
- [ ] Settings gates: per-worker enable/disable; graceful shutdown integrated with ResourceManager; propagate shutdown to children.
- [ ] Logging format: worker_type, pid, seq_no, generation, latency buckets, restart reason; throttle duplicate errors.

## 5) Queue & Backpressure
- [ ] UI wrappers: non-blocking poll, drop-old policy, per-channel caps (image/rss/fft/precompute), queue length metrics; last-good frame reuse documented.
- [ ] Backpressure thresholds per channel; overflow handling = drop oldest + once-per-interval log + metric increment.
- [ ] Serialization constraints reiterated (no Qt objects; bounded payloads); define max payload sizes and rejection paths.

## 6) Testing Strategy (Design)
- [ ] `tests/helpers/worker_sim.py`: deterministic simulators per worker type; latency + failure injection knobs; controllable generation counters.
- [ ] Schema fixtures: validate req/resp/shared-memory headers and size caps; reject oversize payloads in tests.
- [ ] Health tests: heartbeat miss → restart/backoff; metrics increments; logging format conformance; restart cap respected.
- [ ] Integration shims: stub supervisor for UI tests (no process spawn); verify UI drop-old semantics under delay.

## 7) Documentation & Backups Plan
- [ ] Keep audit Phase 1 checklist in sync with this doc; note any deviations.
- [ ] Spec.md stays current-state (no planning).
- [ ] Index.md: add `core/process/*` entries when implemented.
- [ ] `/bak`: snapshots for new/modified modules pre/post when Phase 1 code lands.

## 8) Exit Criteria (Planning Only)
- [ ] All checkboxes above resolved with concrete decisions documented (values, limits, thresholds).
- [ ] Main audit updated with any deltas; no code written.
