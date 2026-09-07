# Baseline — 42033c84 — Accepted Rollback / Fidelity Reference

## Identity

```text
4.7.2
42033c84eabbdf25ccd34bb0e83f9e553f2f8f11
```

## Evidence class

**HISTORICAL SECONDARY**

No raw log pack for this exact accepted checkpoint has been positively identified in the currently
retained conversation files.

## What is safe to preserve

- This commit is the named accepted rollback/fidelity baseline used throughout current P2 work.
- Later source comparison established that core physical presentation files such as the adaptive timer,
  compositor, and QRhi surface were byte-identical between this baseline and a later degraded
  checkpoint. Therefore the full regression cannot be simplistically attributed to a recent rewrite
  of those files.
- Historical project orientation records a low/mid-150 FPS high-refresh comparison class after the
  single-surface presentation migration.

## What must NOT be invented

Do not attach a precise FPS median, request-acceptance percentage, CPU number, or visualizer cadence
to `42033c84` unless a positively identified raw log is recovered.

Use later raw same-day checkpoints for numeric comparisons when exact numbers matter.
