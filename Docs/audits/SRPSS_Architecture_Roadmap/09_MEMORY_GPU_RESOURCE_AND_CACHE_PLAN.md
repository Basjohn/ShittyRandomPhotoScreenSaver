# 09 — RAM, Commit, VRAM, GPU, Resource, and Cache Plan

Last reconciled: 2026-08-13

## Current Conclusion

Containment and absolute efficiency are separate gates. Current code can return tracked
GL ownership to zero, yet the application remains heavy in RSS/private commit/VRAM and
now shows material GPU-engine busy under active displays.

Current mixed-load evidence (`08_09_ca830d7_14_59`) adds a fourth top-level resource
metric:

```text
active-display process GPU busy
median 10.8%   p90 24.0%   p95 27.8%   max 32.9%
```

GPU **busy** is not GPU **memory** and is not “percent of theoretical RTX 4090 FLOPS.”
It is still too material to leave unattributed.

## Independent Gates

1. **Containment:** equivalent cycles do not grow monotonically.
2. **Absolute memory efficiency:** warm RSS/private commit/VRAM reach reasonable levels or have approved owner-level explanation.
3. **GPU work efficiency:** process GPU busy is attributable by owner and avoidable redundant work is removed without cadence/quality cuts.

## Metric Discipline

Report separately:

- whole/main/child RSS and USS/private working set where available;
- private commit/private bytes (do not add to RSS);
- VMS/mappings/thread stacks;
- tracked CPU image/cache/shared-memory bytes;
- tracked GL texture/FBO/PBO/program/buffer bytes;
- dedicated and shared GPU memory;
- process GPU-engine busy and sample timestamp/age;
- transition GL timer-query duration/support/sample count;
- visualizer state/update/paint rates per display/refresh.

## Texture Reuse Result

The exact current-texture identity defect was the stale DPR split between display and
presenter ownership. `DisplayWidget` used the live `1.5` DPR while `ImagePresenter`
retained its construction default `1.0`; terminal completion toggled the pixmap twice
after texture retention and reproduced the canonical `retained_key + 2` next-old miss.

The presenter now reads the display-owned DPR and skips no-op mutation. Focused
automation proves old cache hit + only new upload on a steady transition, and the
45-cycle resource harness retains one terminal texture without larger budgets,
historical texture staircases or weaker teardown. The current live typical-load run
then verifies exact retained/next-old equality and old cache hits on all `20/20` steady
handoffs, with one allocation/upload and one terminal texture/idle PBO. Process GPU
busy remains material (median/max `9.1/32.7%`) but can no longer be attributed to
duplicate steady old-texture upload; owner-level GPU attribution remains active.

## GPU Attribution Program

Promoted from Future Cleanup into active Phase 5:

- route transition paint timing through a shared compositor seam so every exercised family has real paint samples;
- use non-blocking GL timer queries with delayed result collection where supported;
- never use `glFinish()` in ordinary profiling;
- log support and sample counts so zero is not confused with “not measured”;
- correlate per-transition GPU time with process GPU busy, texture uploads, update/paint rates and event-loop/request age;
- separate visualizer overlay/context work from image transition/compositor work;
- repeat on the texture-identity-fixed build before attributing remaining cost to persistent rendering.

The first attribution slice now wraps only the already-occurring visualizer overlay
clear/render span in a fixed owner-context `GL_TIME_ELAPSED` query ring. It polls
`GL_QUERY_RESULT_AVAILABLE`, never waits or flushes, drops a sample when the ring is
full, and reports supported/submitted/collected/pending/dropped/discarded/error counts
beside CPU paint and state-to-paint summaries. Query handles are ResourceManager-tracked
and deleted on the exact overlay context. Its first live run submitted a query on every
new overlay context but collected none because PyOpenGL 3.1.10 raised `KeyError` from
the two-argument `GL_QUERY_RESULT` wrapper. Retrieval now supplies the native one-value
uint64 output buffer explicitly, error counts are parsed, and a real offscreen
OpenGL-context regression proves submission, collection and strict deletion. The
corrected-query `08_13_fa7e8196_16_33_16_37_gpu_queries_typical` run then collected
supported samples in all `26` overlay windows with zero errors/drops and bounded pending
state. Normal Bubble GPU p50/p95 is roughly `0.35–0.46/0.43–0.53 ms`; Spectrum is
roughly `0.009–0.012/0.013 ms`. Process GPU peaks instead align more strongly with
Crumble/Particle/Burn windows, so the same non-blocking ring was installed at the shared
compositor for the transition-heavy runtime capture below.

That capture is now preserved as
`08_13_5bf68d6b_17_00_17_04_compositor_gpu_typical`. All `42` compositor windows are
supported and error/drop free. Active transition p95 is roughly `0.87–1.02 ms` on
screen 0 and `3.13–3.38 ms` on the physical-4K screen, while sparse steady QPainter
base draws repeatedly cost `7–12 ms` and `36–41 ms`. Because terminal ownership already
retains exactly one destination texture, steady presentation now consumes that exact
cached texture through the existing fullscreen program rather than creating a second
full-pixmap presentation route. It does not expand texture/PBO budgets or upload in paint.

## Visualizer Presentation Efficiency

Captured screen 1 is 60 Hz while the current typical-load run records Bubble medians of
`89.75` state/update and `87.05` `paintGL()` calls per second, and Spectrum medians of
`92.7` and `91.15`. Phase 5 does not change Bubble/Spectrum logical/source cadence.
Phase 7 may test whether immutable render snapshots can be coalesced to useful
presentation opportunities **after** logical integration and only after owner cost is
measured.

The historical elapsed-time cap is a negative control, not a Phase 7 prototype. A
`100 Hz` producer tested against `0.92 * 1/60 s` can request only every second tick
(`50 Hz`), and holding the gate until paint adds variable Qt-delivery backpressure. A
generic latest-state sampler is also unsafe for Bubble because its protected temporal
trace includes a one-logical-tick visible edge that valid `60 Hz` phase alignment can
miss. Future coalescing requires an edge-preserving render-state contract and real
source-to-visible evidence, not cleaner update counters.

Measure before/after:

- logical state publications;
- overlay state commits;
- update requests;
- paints;
- display refresh;
- source/state age at paint;
- GPU timer/busy;
- visible response.

A lower paint rate is not a win if logical latency or feel worsens.

## Teardown-Churn Containment Result

The `08_13_ab429163_16_08_16_18_typical_teardown_churn` run intentionally exercises
two CUSTOM rebuilds, one Settings runtime rebuild, the Settings-dialog lifetime, and
final exit. Every runtime teardown reaches `0` tracked GL bytes/resources/unknowns;
each replacement settles at the same `25` GL resources and `14` unknown resources.
Cleanup callbacks retaining an owner and invalid QObjects remain zero. Threads and
handles fluctuate without a generation-sized staircase, and dedicated VRAM drops to
`8 MiB` during the zero-GL Settings interval before rebuilding to roughly
`539–608 MiB`. This is positive containment evidence, not an absolute-efficiency pass:
final RSS/private are about `936 MiB/3.00 GiB`, peaks reach about
`1.04 GiB/3.08 GiB`, and warm VRAM remains above the provisional target. Tracked CPU
cache growth follows legitimate fill under its `256 MiB` cap rather than a teardown
owner leak.

## Memory/Representation Audit

Audit simultaneous retention of encoded bytes, decoded/raw images, transform variants,
QImage/QPixmap/display representations, shared-memory payloads, upload staging, textures,
previous/fallback frames and per-display duplicates. Different DPR/transform outputs are
not duplicates merely because source identity matches.

## CPU Cache And Prefetch

Keep the 256 MiB production CPU-cache cap unless hit/fallback measurements justify a
deliberate change. Preserve bounded concurrency, pending count/future bytes, generation
rejection, stable transform identity and derivative/source lifetime. Do not raise budgets
to hide misses.

## GPU Ownership

Current per-compositor ownership remains authoritative until Phase 6 proves a shared
store would reduce real duplication and complexity. Any future store requires exact
byte caps, leases, context/share generation, one deletion owner and no GL under locks.

## Provisional Targets

For the current dual-1440p environment retain investigation targets from prior work:

- preferred whole-app warm RSS under ~600 MiB; investigate >750 MiB; unresolved >900 MiB blocks release;
- preferred dedicated VRAM under ~300 MiB; investigate >400 MiB; unresolved >500 MiB blocks release;
- no unexplained multi-GiB private commit;
- no unexplained sustained/high GPU busy after owner attribution.

GPU busy needs scenario-specific targets only after transition/visualizer/upload owners
are separately measurable; do not invent a magic percentage first.

## Prohibited Resource Fixes

No quality/cadence/source-resolution reduction, working-set trimming, production GC,
process recycling, cache inflation, fake zero accounting, unbounded retention, or
scheduler change used to disguise a resource owner.

## Phase Acceptance

- no monotonic equivalent-state growth;
- absolute RSS/commit/VRAM materially lower or explicitly explained;
- current-texture reuse is correct;
- GPU busy has owner-level attribution and avoidable redundant presentation/upload work is removed;
- strict teardown reaches zero application GL ownership;
- visualizer and image/transition quality remain approved.
