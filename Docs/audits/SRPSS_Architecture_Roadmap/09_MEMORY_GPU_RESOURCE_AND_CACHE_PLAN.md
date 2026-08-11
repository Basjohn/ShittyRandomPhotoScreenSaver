# 09 — RAM, Commit, VRAM, GPU, Resource, and Cache Plan

Last reconciled: 2026-08-11

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
historical texture staircases or weaker teardown. Installed identical-sequence timing,
GPU and retained-count comparison remains active Phase 5 validation.

## GPU Attribution Program

Promoted from Future Cleanup into active Phase 5:

- route transition paint timing through a shared compositor seam so every exercised family has real paint samples;
- use non-blocking GL timer queries with delayed result collection where supported;
- never use `glFinish()` in ordinary profiling;
- log support and sample counts so zero is not confused with “not measured”;
- correlate per-transition GPU time with process GPU busy, texture uploads, update/paint rates and event-loop/request age;
- separate visualizer overlay/context work from image transition/compositor work;
- repeat on the texture-identity-fixed build before attributing remaining cost to persistent rendering.

## Visualizer Presentation Efficiency

Captured screen 1 is 60 Hz while overlay windows can approach ~1000 state/update/paint
operations per 10 seconds. Phase 5 does not change Bubble/Spectrum logical/source
cadence. Phase 7 may test whether immutable render snapshots can be coalesced to useful
presentation opportunities **after** logical integration.

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
