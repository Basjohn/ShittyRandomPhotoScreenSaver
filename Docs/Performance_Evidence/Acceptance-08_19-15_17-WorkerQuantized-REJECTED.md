# Acceptance Evidence — 2026-08-19 15:15–15:17 — Quantized Dedicated Worker — REJECTED

## Provenance

**PRIMARY RAW**

Raw pack:

```text
16bef115-5a8e-40ea-87c1-63437ffc68d7.zip
SHA-256: 8d4fb94280dddacef25c8e210f913f1e735af1f839ced727cf1f8c133ac70ca0
```

The log predates `[SOURCE_HEAD]`.

**Source SHA: not embedded.**

## Logical runtime

First runtime:

```text
15:15:51 Runtime started generation=-1 interval_ms=11.11
15:16:51 Runtime stopped
steps=3883
skipped_deadlines=1581
slow_steps=0
failures=0
```

Over roughly one minute, 90 Hz would require ~5400 deadlines. The effective service is therefore
about 64–65 Hz and the missing-deadline fraction is about 29%.

Post-recreation runtime:

```text
steps=2825
skipped_deadlines=1148
```

Again the same ~64 Hz / ~29% loss class.

## Physical presentation

165 Hz display, three completed transition windows:

```text
143.2
143.6
149.5 FPS
median 143.6
```

Request acceptance:

```text
90.71% .. 92.28%
median 91.83%
```

60 Hz display:

```text
57.4 .. 58.2 FPS
median 58.0
```

## Delivery stage

Representative high-refresh window:

```text
wake lateness p95 ~1–2 ms class
dispatch_pending_skips present
paint_pending_skips=0
```

The catastrophic defect in this run is nevertheless the dedicated logical scheduler itself: it cannot
service the authored ~90 Hz cadence.

## Conclusion

**REJECT this worker scheduler implementation.**

This is the hard negative control for the later high-resolution logical-runtime repair.

Do not allow a future scheduler change to reproduce the ~64 Hz / ~29% target-deadline-loss class.
