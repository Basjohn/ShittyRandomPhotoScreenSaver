# Acceptance Evidence — 2026-08-20 00:15–00:20 — 82a14b31 Light Load — REFERENCE

## Provenance

**PRIMARY RAW + PRIMARY OPERATOR**

Raw pack:

```text
6ef8b47b-bc3a-4921-ac16-22449f8f08ba.zip
SHA-256:
fbaaa67d84afee4855330d7026a20dd8b4f4130be44a83469eb20f8f73f45f08
```

Log self-ID:

```text
[SOURCE_HEAD] 82a14b31d4cc71e47d0112479af0ce16596325c1
```

Architecture:

```text
dedicated logical worker + coalesced worker->GUI push + one QRhi compositor/display
```

## Operator-visible result

- Light load is substantially better than initially credited.
- Pause/Play hitches are almost completely absent.
- Visualizer spawn is reliable.
- Spectrum jumps directly to its visible resting-bar state rather than visibly falling/shrinking into it.
- Slide visibly microstutters at repeatable points despite high average FPS.

## Aggregate physical delivery

14 completed transitions.

165 Hz display:

```text
median FPS              ~150.05
range                   126.8 .. 158.4
median acceptance       ~93.26%
```

60 Hz display:

```text
median FPS              ~58.35
median acceptance       ~97.73%
```

## Logical runtime

```text
steps=22042
skipped_deadlines=8
slow_steps=0
failures=0
```

## Environment

Primed system CPU median:

```text
~8.7%
```

## Slide canary

First 165 Hz Slide:

```text
avg_fps=154.4
acceptance=95.06%
dt_p95=10.83ms
dt_p99=16.42ms
dt_max=44.73ms
>=33ms gaps=2
paint_p95=3.36ms
paint_max=6.48ms
GPU average ~0.30ms
```

Second:

```text
avg_fps=150.2
acceptance=93.90%
dt_p95=12.39ms
dt_p99=20.62ms
dt_max=43.22ms
>=33ms gaps=1
paint_p95=3.47ms
paint_max=14.05ms
```

The simultaneous 60 Hz Slides show max gaps around:

```text
65.65ms
59.72ms
```

## Conclusion

This is now the primary light-load worker+push architecture reference.

It proves:
- high average physical throughput is mostly recovered;
- dedicated logical cadence is extremely healthy;
- pull-specific spawn failure is absent;
- large perceptible tail gaps remain even in a simple linear Slide.

Future architecture work should target tail latency/load resilience without sacrificing this light-load state.
