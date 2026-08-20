# Visualizer Recovery / Migration Contract

Status: binding visualizer ownership contract during Qt Quick presentation migration
Date: 2026-08-20

## 1. Product invariant

The visualizer must remain both smooth and reactive.

Do not obtain smoothness by lowering cadence, delaying source data, averaging away transients, or
masking missing physical frames.

For Bubble, BTF is binding.

## 2. Ownership

| Concern | Logical runtime | Source/audio | Quick presentation side |
|---|---:|---:|---:|
| authored logical deadline/dt | YES | NO | NO |
| mode simulation | YES | NO | NO |
| logical envelopes/events | YES | inputs | NO |
| latest logical publication | YES | NO | consumes |
| capture/source production | consumes | YES | NO |
| runtime pixels | NO | NO | YES |
| physical presentation | NO | NO | YES |
| QWidget/QQuick/GPU mutation | NO | NO | legal owner only |

The logical worker has no GUI/Quick/GPU backdoor.

## 3. Logical runtime

`VisualizerLogicalRuntime` remains landed and authoritative.

Keep:

- high-resolution monotonic deadlines;
- bounded sleeping;
- skip genuinely missed deadlines;
- no catch-up;
- generation-owned stop/join;
- one logical clock.

The old ~64 Hz coarse-wait class remains a negative control.

## 4. Publication / presentation bridge

Logical publication is latest-state.

The migration replaces the old QRhiWidget/GUI physical consumer with a bounded Quick presentation
bridge.

Required properties:

- latest wins;
- current generation only;
- no FIFO;
- no paint acknowledgement;
- no one-callback-per-logical-tick requirement;
- no stale state after recreation;
- render-thread-safe immutable/synchronized state.

## 5. Readiness

At minimum:

```text
presentation_ready
reactive_source_ready
```

Paused Spectrum may show presentation-owned idle bars while source identity is absent.

On Play, fresh real current-generation data replaces idle state in place.

## 6. Pause / Play

Pause:

- logical runtime remains alive;
- authored idle state starts promptly;
- capture lifetime follows source owner policy.

Warm Play:

- same logical runtime continues;
- no cold-start lifecycle;
- fresh source becomes authoritative promptly.

The pixel owner may migrate to Quick without changing these semantics.

## 7. Generation / activation

`0` is valid identity.

Retired generation state cannot:

- enter the replacement state bridge;
- trigger reveal;
- mutate the current Quick scene/render state.

## 8. Error visibility

- worker thread-affinity violations fail loudly in tests/development;
- required handoffs fail loudly;
- production may fail safe, but tests must expose architecture violations.

## 9. Lifecycle

Retirement order conceptually:

```text
close logical admission
-> quiesce generation-owned producers
-> join logical runtime
-> reject stale publication
-> retire presentation/render resources
-> destroy retired runtime window/scene
```

Replacement authority starts only afterward.

## 10. Migration acceptance

Preserve:

- all five modes;
- BTF;
- source freshness;
- mode switching;
- Pause/Play;
- CUSTOM/Edit semantics;
- first-frame/reveal behaviour;
- Settings/recreate;
- topology recreation;
- compiled build;
- bounded resources.

The completed P0 benchmark selects Quick as the presentation destination. The remaining work is
migration correctness and parity, not another presenter bake-off.
