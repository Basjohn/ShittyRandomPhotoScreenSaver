# 05 — Visualizer Fidelity Contract

Last reconciled: 2026-08-10

## Authority

```text
approved Bubble/Spectrum behaviour: ff93461685476bd0657aa88312fc2e35e9037880
rejected persistent-lane control:    666624d421b08f978c5f610571a078570150a1e7
rejected Spectrum second clock:      ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9
```

All supported modes are protected: Spectrum, Bubble, Sine Waves, Oscilloscope and Dev
Curve. User-observed behaviour remains the final authority for perceived quality.

## Critical Terminology

There is one authoritative **logical/state-evolution cadence** for the current
visualizer design. That is not the same thing as physical presentation rate.

- Logical/source work integrates audio/events, mode state, dt and authored steps.
- An immutable/current render state is the output of that integration.
- Presentation consumes that state when a valid Qt/display opportunity exists.
- A skipped paint may skip an intermediate render snapshot **after integration**.
- A skipped paint may not discard events, change dt, alter smoothing/state, or control the producer.

This distinction is mandatory for Phase 7.

## Current Evidence

The mixed-load capture strengthens protection against “fixing the visualizer” for a
shared UI problem:

- Bubble worker samples remain roughly 1–2 ms while visualizer tick/source-age spikes approach ~100 ms under transition/host pressure.
- Screen 1 is a 60 Hz display in the captured runtime.
- Captured overlay windows can approach ~1000 state/update/paint operations per 10 seconds.
- The visualizer timer starts at 16 ms and current max-FPS logic can target roughly 90–100 Hz.

This establishes a future presentation-efficiency question. It **does not** establish
that Bubble/Spectrum logical/source cadence should be capped to 60 Hz.

## Bubble Protection

During Phase 5 do not change:

- authored-step offer/admission cadence;
- one-in-flight/lane-free semantics;
- ordinary general COMPUTE executor ownership;
- dt calculation/clamp;
- source/energy/transient/event snapshot timing;
- consume-once event semantics;
- physics/equations/precision;
- callback/publication ordering;
- generation/activation identity.

Allowed cadence-neutral work includes caching configuration values that change only
with settings/preset changes instead of reconstructing/copying them every step.

### Bubble temporary façade

`widgets/spotify_visualizer/bubble_compute_lane.py` is explicitly a temporary
compatibility adapter over the approved ordinary executor, not a real persistent lane.
Removing it is allowed only as a sterile equivalence refactor: make the already-present
direct executor path authoritative and preserve every timing/ownership invariant above.
Useful metrics may remain under neutral names; misleading “persistent lane” terminology
must not survive merely for compatibility.

## Spectrum Protection

- source consumption and presentation-filter state stay on the existing authoritative visualizer tick;
- no paint-local decay/smoothing or self-requested repaint loop;
- no second timer/cadence;
- no display-refresh-driven source decimation;
- reset/snap behaviour across mode/generation/pause/stall boundaries remains explicit;
- optional current presentation smoothing remains subject to installed visual approval.

`ebfec397` remains a negative control because paint became a second state
clock and visible smoothness worsened despite plausible metrics.

## DevCurve

Measure `devcurve_dispatch_ms` first. Its field solve is stateful and largely pure
Python; moving it to another Python thread is not automatically parallel under the GIL
and creates temporal handoff risk. Extraction belongs in a separately gated Phase 7
change unless measurements prove it a material Phase 5 GUI owner.

## Stronger Golden Package

Must protect:

- source/event sequence and timestamp identity;
- submit/start/end/callback/commit order;
- publication intervals/source age;
- first-visible publication and paint receipt;
- activation/generation reset;
- deliberate GUI stalls and irregular presentation opportunities;
- negative controls `666624d4`, terminal batching and `ebfec397`.

A future Phase 7 test must run identical logical input with different presentation
opportunities and prove logical state is equivalent at the same authored/source time.

## Fidelity Gate

Reject/rollback when:

- Bubble becomes less reactive/elastic or misses impulses;
- Spectrum becomes flatter, stepped, delayed or less smooth;
- another mode loses its current personality;
- source-to-first-visible latency materially worsens;
- logical state depends on paint opportunity;
- a known-bad negative control passes;
- a CPU/GPU/memory improvement is purchased through cadence or quality reduction.
