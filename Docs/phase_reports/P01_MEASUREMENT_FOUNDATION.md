# Phase Report — P01: Measurement Foundation

## Metadata

- Branch: `main`
- Baseline ancestor: `00edb57a3076b845cb8ee4b6cb7f36ea83411f0c`
- Checkpoint: commit `4.6.9 Phase 1`
- Date: 2026-07-25
- Runtime flags: measurement is inert unless the relevant `--perf` / `--usage` family is enabled
- Related decisions: recovery roadmap Phase 1 and ADR-A through ADR-J

## Phase objective

Make frame delivery, event-loop delay, task volume, CPU image bytes, GL bytes, and lifecycle resource state observable without importing donor orchestration or changing product behaviour.

## Baseline shape preserved

- No donor code was copied, merged, or used as a runtime dependency.
- No visualizer equation, preset, audio transform, simulation cadence, paint request, transition duration, or image-selection rule changed.
- No producer waits for paint.
- No metric participates in scheduling, quality, retry, cache eviction, or lifecycle decisions.
- Settings and CUSTOM Edit retain the baseline full `stop -> display cleanup -> recreate -> start` path.

## Measurement implementation

### Frame delivery

- The existing compositor paint seam owns one `--perf`-gated 512-sample deque.
- Each retained sample records:
  - accepted render-request time;
  - paint start and end;
  - paint duration;
  - start-to-start frame interval;
  - request-to-paint age;
  - presented frame index;
  - existing transition/scene generation.
- Final aggregate records include p50/p90/p95/p99/max, counts above 25/33/50/100 ms, accepted/skipped request counts, and acceptance percentage.
- No per-frame INFO record is emitted.

### Event-loop delay

- One app-owned `--perf` recorder samples main-thread timer lateness at 20 Hz.
- Retention is bounded to 2,048 values.
- Aggregates emit every 15 seconds and at shutdown.
- A delayed delivery resets the next expectation from observed time so one stall is not counted repeatedly as catch-up.
- The recorder remains owned by `run_screensaver()` across Settings/Edit engine recreation.

### Task categories

- `ThreadManager` records synchronous passive category totals at its authoritative active-task registry.
- Counts include submitted, active, completed, failed, cancelled, and rejected.
- Category labels are length-bounded and cardinality-bounded to 64 entries with an `other` overflow bucket.
- High-rate image, presentation, visualizer, and usage-sampler submission sites provide stable categories.
- The existing 15-second usage sample emits a compact category snapshot; no new task or UI callback is created for category accounting.

### CPU and GL bytes

- `ImageCache` keeps its pre-existing approximate eviction budget unchanged.
- A separate exact logical-byte sidecar uses `QImage.sizeInBytes()` and `QPixmap` dimensions/depth.
- Qt-derived metadata is captured on `put()`; background snapshots never inspect live `QImage`/`QPixmap` objects.
- Known GL allocations record exact requested bytes for RGBA8 texture base levels, PBO storage, and known VBO data.
- Programs and VAOs remain explicitly unknown rather than estimated.
- The baseline contains no application-owned FBO allocation seam, so application-owned FBO count/bytes are exactly zero. `QOpenGLWidget`'s default FBO is reported as `qt_owned_untracked`.
- Every resource snapshot carries owner, generation, dimensions, format, tracked bytes, and `lease_count=None` until real leases are introduced in Phase 6.
- Owner deletion releases tracking only after successful deletion. Resource-manager cleanup callbacks execute outside registry locks.

### Lifecycle snapshots and artifacts

- Settings and CUSTOM Edit emit snapshots at:
  - `before_stop`;
  - `after_stop`;
  - `after_display_cleanup`;
  - `after_restart`.
- The usage sidecar emits periodic aggregate resource fields.
- Parser version 1.2 adds:
  - `event_loop_stalls.csv`;
  - extended `frame_intervals.csv`;
  - category deltas/rates in `task_rates.csv`;
  - exact byte fields in `memory_usage.csv`;
  - `resource_snapshots.csv` with retained per-resource JSON.

## Overhead and pacing evidence

### Conservative composite budget

Command:

```powershell
python tools/phase1_measurement_benchmark.py
```

The benchmark uses seven alternating paired runs and upper-quartile added cost. It projects the exact Phase 1 collector methods at the frozen target rates: 165 Hz + 60 Hz paint delivery, 20 Hz event-loop sampling, 171 task submissions/s, and one aggregate resource snapshot per 15 seconds.

| Result | Value | Gate |
|---|---:|---:|
| Projected CPU overhead vs paired workload | 0.6583% | < 2% |
| Projected CPU use of one logical core | 0.0535% | informational |
| Paired p99 work-duration delta | -0.2553 ms | <= +0.25 ms |
| Verdict | pass | pass |

This is a conservative direct-method projection, not a substitute for a real Qt/GL run. Its retained resource fixture contains 24 cache entries and 64 registry resources. It excludes Qt event dispatch, actual draw/GPU cost, executor/callback work, real live-resource distribution, and lifecycle-detail JSON serialization.

### Real GL runtime-shaped comparison

`tests/test_frame_timing_workload.py` passed both with ordinary diagnostics disabled and with production PERF logging enabled.

| Run | Steady transition `dt_max` | Sustained degradation |
|---|---:|---:|
| PERF disabled | 20.79 ms | -4.69 ms |
| PERF enabled | 20.67 ms | -6.57 ms |

The enabled compositor sidecar contained the new fields. After cold/warmup windows, sustained 165 Hz paint p99 was generally 6.47–8.60 ms; the first sustained window recorded 26.98 ms p99 and a 36.49 ms maximum, then recovered. No repeated 50/100 ms steady gaps were recorded.

## Visualizer fidelity evidence

- Full runtime-shaped visualizer file: `186 passed, 20 skipped`.
- The skips are environment/optional-path skips already encoded by the suite.
- Spectrum first-visible, mode-switch, synthetic-audio, Bubble reactivity/elasticity, activation isolation, stale-compute rejection, and runtime dispatch oracles passed.
- One earlier full run had a 0.78 ms Bubble snapshot average against a 0.75 ms wall-clock threshold; the isolated rerun passed, and the final full run passed cleanly.
- No manual Spectrum/Bubble review or deterministic golden capture was created in Phase 1; those are Phase 2 deliverables.

## Automated validation

- Final combined Phase 1 owning-suite gate after legacy test-double compatibility repair: `260 passed, 1 warning`.
- Full visualizer regression: `186 passed, 20 skipped`.
- Scheduler/image owning suites: `85 passed`.
- Real GL frame workload, PERF disabled: `2 passed`.
- Real GL frame workload, PERF enabled: `2 passed`.
- Phase 1 benchmark tests: `6 passed`.
- Baseline evidence archive reparsed successfully with unchanged SHA-256:
  `90AF3A54058FEBD54E961CA56FFFBDDD26D8AB4204EC605C1E8C4C4305E5DAEB`.
- Python compilation passed for all changed runtime, parser, benchmark, and focused test modules.
- The repository-wide four-chunk sweep also ran to expose unrelated baseline debt. It did not pass: chunks 1–3 retained 32 failures plus one setup error across pre-existing Bubble, display/default, Sine, transition, Steam, and stale-test surfaces, while chunk 4 exited with Windows status `3221226505`. The Phase 1 `category=` compatibility issue found in legacy test doubles was repaired; the affected visualizer scheduling suites then passed. The remaining slide wall-clock oracle still includes the baseline randomized deferred-start interval and recorded an approximately 813 ms gap, so it is not used as a Phase 1 pacing gate.

## Gate criteria

| Criterion | Result |
|---|---|
| Less than 2% CPU overhead in target scenario | Pass: 0.6583% conservative paired projection; real GL comparison showed no material tail change |
| No visualizer fidelity change | Pass: all supported runtime-shaped visualizer oracles green; no visualizer behaviour changed |
| No material p99 regression | Pass: paired p99 delta -0.2553 ms and enabled real-GL steady windows remained healthy |
| Metrics survive Settings/Edit | Pass for ownership/call-order automation: app recorder persists and snapshots bracket both baseline full-reload paths |

The 50/50/50 real lifecycle loop, manual visualizer review, long-run memory plateau, and driver-level VRAM validation are intentionally not claimed here. They remain owned by Phases 2–4 and 11.

## Unexpected findings and rejected approaches

- `tools/perf_integration_harness.py --help` is not a CLI help path; it starts the full approximately 85-second interactive GUI sequence. The accidentally launched process was terminated and the harness debt was recorded in `Future_Cleanup.md`.
- The Windows workspace patch helper failed intermittently. Exact workspace-validated marker replacements were used where necessary.
- Measuring the pre-existing render-timer collector would not measure the new paint-delivery recorder; the benchmark was corrected to exercise `_PaintMetrics.record_render_request`, `record_paint_start`, and `record`.
- A synthetic registry fixture must retain its weakly registered objects. The benchmark fixture was corrected to retain all 64 resources and include the actual app-owned cache-plus-registry aggregate helper.

## Rollback

Revert checkpoint `4.6.9 Phase 1` as one unit. Do not selectively leave producer call sites passing `category=` to an older `ThreadManager`, and do not leave lifecycle snapshot calls without the passive resource helper.

## Gate decision

- [x] Pass
- [ ] Fail
- [ ] Pass with explicit deferred issue

Gate 1 is complete. The checkpoint also supplies the clean committed recovery point that closes Gate 0.
