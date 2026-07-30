# Phase 5 — CPU and Task Reduction

Date: 2026-07-30
Branch: `main`
Foundation: closed Phase 4 (`Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md`)

## Outcome

Phase 5 reduces measured CPU, task, publication, and diagnostic work without changing authored visualizer feel, coupling simulation to paint, or enlarging the 256 MiB CPU-cache budget. It is **in progress**. The implemented slices below are not runtime closure.

Phase 4 is closed by `logs/evidence_chest/07_30_dc8d1741_00_26/`, including startup artwork and media-next during transitions. Older captures that reported a whole-process slope or media/startup collision remain useful historical failed-run evidence, but are superseded as Phase 4 gate evidence. Their CPU/frame-delivery and accounting questions transfer here.

## Current implementation state

- Latency authority/lifecycle resets and WARNING rate limiting are implemented; their runtime diagnostic truthfulness and tail effect remain to be measured.
- Bubble submits authored cadence at 60 submissions/s with bounded maximum-two batching. Spectrum retains its existing shared newest-only path for now.
- Unchanged media polling is a no-op for repaint work.
- Frame-delivery ownership telemetry, cache representation churn work, and memory/driver accounting reconciliation remain underway.

## P5.0 — Visualizer authored cadence

- [-] Validate Bubble's 60 submissions/s cadence and maximum-two batching with deterministic replay, synthetic audio, irregular paint, GUI-stall, transition, and mode-switch scenarios.
- [ ] Demonstrate preserved Bubble loud-passage elasticity and first-frame behaviour; compare cadence, input-to-visible latency, p99/max delivery, and CPU/task cost before/after.
- [ ] Exercise Spectrum on its unchanged shared newest-only path and Bubble → Spectrum → Bubble; do not retune Spectrum smoothing or Bubble authored behaviour without mode-owned failure evidence.
- [ ] Reject any optimization that turns paint delivery, feedback animation, or a retry timer into the visualizer clock.

## P5.1 — Frame-delivery owner telemetry

- [-] Add/passively consume owner-labelled render, submission, GUI callback, update-request, and paint timestamps without creating UI work or a new timer/queue.
- [ ] Correlate logical scene age, event-loop lateness, task queue/callback tails, and per-display render/paint gaps for idle, visualizer, transition, decode, and controlled-load runs.
- [ ] Attribute delayed delivery to its actual owner before changing cadence mechanics; a healthy render clock with delayed paint is event-loop delivery starvation, not permission to add repaint retries.

## P5.2 — False visualizer-latency diagnostics

- [-] Verify lifecycle resets make latency authority explicit and WARNING output is rate-limited without suppressing distinct failures.
- [ ] Separate logical audio/simulation age from render-state age and Qt paint delay in sampled diagnostics.
- [ ] Prove diagnostic warnings neither claim a mode regression from presentation delay nor hide a real first-frame, mode-switch, or audio-input failure.

## P5.3 — Unchanged media repaint churn

- [-] Preserve the unchanged-media poll no-op through idle, transition, startup, and media-next scenarios.
- [ ] Measure media-card paint/update requests and layout mutations for unchanged key/metadata; require no recurring repaint, Qt structural mutation, artwork decode, or pixmap replacement.
- [ ] Keep changed artwork/title and transition-time feedback contracts from Phase 4 intact; validate current-key updates remain responsive without reviving the historical 30–38-paint burst.

## P5.4 — Memory/driver accounting and repeated edit/rebuild cycles

- [ ] Reconcile exact application-owned CPU/display/GL bytes with main/worker/total RSS, private commit, ResourceManager unknown-byte entries, and driver VRAM without raising budgets to conceal uncertainty.
- [ ] Repeat Settings/Edit/CUSTOM rebuild cycles with image work and visualizer activity; record generations, owner cleanup, task/worker counts, accounting deltas, p99/max delivery, and warnings.
- [ ] Distinguish bounded allocator/driver high-water behaviour from a live owner leak using synchronized snapshots and repeated-cycle slopes.

## P5.5 — Cache representation churn

- [ ] Profile raw/scaled/GUI backing co-retention, prefetch future bytes, transformations, and cache hit usefulness under representative cycling.
- [ ] Remove only measured redundant representation/copy churn while retaining exact source/transform/size/mode/DPR identity and existing newest-only/stale-generation ownership.
- [ ] Keep the CPU image cache at its 256 MiB production ceiling; do not add pins, enlarge budgets, or use trimming/GC as a substitute for owner evidence.

## P5.6 — Logging hygiene

- [-] Keep latency diagnostics and warnings bounded, sampled, passively collected, and rate-limited.
- [ ] Verify `--perf`/`--viz` output has owner labels and correlation fields sufficient to diagnose delivery without per-frame INFO logs, whole-state dumps, or new diagnostic work queues.
- [ ] Confirm warnings/errors remain visible in `screensaver.log`; rate limiting may coalesce repeats but must retain count/window/owner context and never change runtime control flow.

## Runtime gate

- [ ] Capture before/after evidence for idle, Bubble, Spectrum, mode switch, active transition, image decode, Settings/Edit/CUSTOM rebuild, and controlled background load.
- [ ] Require materially lower task/CPU cost, equal-or-better p99/max frame delivery, preserved visualizer runtime review, bounded memory/driver accounting, and no new synchronization or UI-pressure workaround.
- [ ] Record environment, commit, parser version, excluded intervals, rollback, and unsupported platform measurements before marking Phase 5 complete.

## Non-goals

Do not remove the Phase 8 presentation-worker architecture here, add threads/processes without latency/GIL/memory evidence, change the compositor topology, turn diagnostics into control flow, or modify visualizer creative settings solely to improve a metric.
