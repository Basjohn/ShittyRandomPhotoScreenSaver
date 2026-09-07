# Performance Reference — 2026-08-19 15:27–15:29 — Pre-Dedicated-Runtime Comparison

## Provenance

**PRIMARY RAW**

Raw pack:

```text
21c18ab4-6738-4d89-8b39-d87136f014fb.zip
SHA-256: 751cc4c10b5caf983fa75f682acd2713ed7efa0b0e95d54c48277dbe5025947a
```

The log predates `[SOURCE_HEAD]`.

**Source SHA: not embedded.**

## Architecture identification

The logs contain ordinary `[SPOTIFY_VIS] Tick metrics` and do not contain
`[SPOTIFY_VIS][LOGICAL] Runtime started/stopped` records.

Therefore this is retained as a **pre-dedicated-runtime / GUI-serviced tick comparison**, not assigned
a guessed commit SHA.

## Visualizer tick service

During the main run the accumulated tick metric commonly sits in the low/mid-80 Hz class, with
examples:

```text
82.7
85.1
85.9
86.0
87.0
87.4 Hz
```

There are dt maxima in the ~36–54 ms class, so this is not a temporal-fidelity gold standard.

## Physical 165 Hz presentation

Three completed windows:

```text
Crumble 147.0 FPS
Warp    148.6 FPS
Diffuse 150.1 FPS
```

Median:

```text
148.6 FPS
```

Request acceptance:

```text
93.25%
93.98%
94.76%
median 93.98%
```

## Physical 60 Hz presentation

```text
58.0
58.8
58.5 FPS
median 58.5
```

## Why this record matters

This raw run is useful evidence that, on the same development machine and same day, the physical
presentation system could live around ~147–150 FPS on the 165 Hz display.

It does NOT prove the old logical architecture should be restored. Its logical timing still contains
large holes and later worker extraction fixed a real simulation-cadence problem.

Use it as a physical-delivery reference, not as a rollback recommendation.
