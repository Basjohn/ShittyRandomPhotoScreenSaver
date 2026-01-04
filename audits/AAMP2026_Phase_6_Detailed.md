# AAMP2026 Phase 6 Detailed Plan – Observability, Performance, Documentation (Live Checklist)

Status: Planning-only (no code). Spec.md remains current-state. Main audit references this doc for detail.

## 0) Preconditions / Policy Anchors
- [ ] Lock-free/atomic + ThreadManager policy reaffirmed; no raw Qt timers.
- [ ] Phases 1-5 plans finalized.

## 1) Scope & Goals
- [ ] Maintain telemetry, perf baselines, regression tests, docs/audits, and backups across all phases.

## 2) Perf Baselines
- [ ] Run harness per `Docs/PERFORMANCE_BASELINE.md`; capture dt_max/avg_fps/memory per transition/backend.
- [ ] Use `SRPSS_PERF_METRICS` toggles as documented; record environment.
- [ ] Compare pre/post major changes; log deltas.

## 3) Regression Tests
- [ ] Add/adjust pytest for workers, GL demotion, widget lifecycle, settings models.
- [ ] Maintain rotating pytest log per Windows guide.
- [ ] Health checks for supervisor (heartbeat/backoff) and queue backpressure.

## 4) Documentation Hygiene
- [ ] Update `Index.md`, `Spec.md`, `Docs/TestSuite.md`, and audits after each phase.
- [ ] Keep `audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md` and per-phase detailed planners in sync (no duplicates elsewhere).
- [ ] Ensure Spec.md stays current-state, not planning.

## 5) Audits & Backups
- [ ] `/bak`: snapshots for critical modules touched in each phase with short README.

## 6) Exit Criteria (Planning Only)
- [ ] Checkboxes resolved with concrete procedures documented.
- [ ] Main audit updated with any deltas; no code written.
