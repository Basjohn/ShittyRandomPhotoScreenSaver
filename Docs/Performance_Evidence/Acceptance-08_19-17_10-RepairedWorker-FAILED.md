# Acceptance Evidence — 2026-08-19 17:05–17:10 — Repaired Dedicated Worker — FIRST INSTALLED FAILURE

## Provenance

**PRIMARY RAW + CONTEMPORANEOUS REVIEW + PRIMARY OPERATOR**

Raw pack:

```text
41f6cf08-f731-4967-8e20-a1a987add126.zip
SHA-256: 54469e6d8a305e2fa335fa5ac372a86cdca42f4f312274001713146920cd957c
```

The raw log predates `[SOURCE_HEAD]`.

Contemporaneous findings recorded reviewed source anchor:

```text
80c8ed35f2f027522b00dcbe9795eb95b42076f4
```

Treat this as the reviewed/associated source anchor, not a SHA embedded by the run itself.

## Operator-visible result

```text
Pause/Play hitch remains essentially unchanged.
Paused Spectrum card appears, but no idle bars are perceptibly visible.
Overall performance remains unimpressive.
```

Acceptance: **FAILED**.

## Logical runtime — scheduler repair succeeds

Long runtime:

```text
17:05:47 Runtime started generation=-1 interval_ms=11.11
17:09:59 Runtime stopped
steps=22636
skipped_deadlines=38
slow_steps=4
failures=0
```

This is approximately 89.8–89.9 Hz with ~0.17% target deadline loss.

Post-Settings:

```text
generation=1
steps=1621
skipped_deadlines=1
slow_steps=0
failures=0
```

Conclusion:

**The high-resolution worker scheduler repair is real. Do not broadly revert the worker.**

## Remaining BTF tails

Recorded logical spikes include:

```text
49.83 ms
42.27 ms
```

Bubble state-to-paint across 13 measured windows:

```text
median p95 9.737 ms
worst p95  11.727 ms
worst max  71.797 ms
```

## Bubble compute admission

Final cadence snapshot:

```text
offered=11328
submitted_tasks=11324
publish_ratio=1.000
worker_busy_deferrals=4
result_waiting_deferrals=0
submission_failures=0
stale_results=0
```

This strongly weakens Bubble-compute-as-shared-bottleneck theories.

## Spectrum idle failure

Real renderer:

```text
count=35
min=0.0100
max=0.0300
```

The operator sees no resting bars.

Conclusion: mathematically non-zero values were not a valid visible-pixel acceptance oracle.

## Generation identity defect

Initial worker runs as:

```text
generation=-1
```

despite generation zero being valid.

This later becomes a confirmed fixed defect.

## Physical presentation

165 Hz completed windows:

```text
median 131.6 FPS
range 103.8 .. 152.2 FPS
```

Request acceptance:

```text
median 85.28%
range 74.98% .. 94.58%
```

60 Hz:

```text
median 57.6 FPS
range 52.7 .. 59.6 FPS
```

## Conclusion

Accepted:
- dedicated logical runtime concept;
- repaired scheduler mechanism.

Rejected / still open:
- P2 product acceptance;
- Pause/Play perceptual behavior;
- Spectrum idle visibility;
- generation-zero fencing;
- physical high-refresh delivery;
- BTF tails.
