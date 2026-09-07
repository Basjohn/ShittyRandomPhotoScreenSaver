# Acceptance Evidence — 2026-08-20 00:03–00:05 — 82a14b31 Heavy Load — REFERENCE FAILURE CLASS

## Provenance

**PRIMARY RAW**

Raw pack:

```text
8f897d84-bd04-4685-8093-611e9815ffef.zip
SHA-256:
c09a04cda8431a3704217df6f8b40bd93595946e17db57c751340f4da1d3cadb
```

Log self-ID:

```text
[SOURCE_HEAD] 82a14b31d4cc71e47d0112479af0ce16596325c1
```

Architecture:

```text
dedicated logical worker + coalesced worker->GUI push + one QRhi compositor/display
```

## Environment

Primed system CPU median:

```text
~42.9%
```

No artificial benchmark CPU burner was used by the SRPSS code.

## Physical delivery

Six completed high-load Blockspin windows.

165 Hz display:

```text
median FPS              ~105.8
range                   97.3 .. 130.0
median acceptance       ~72.38%
```

60 Hz display:

```text
median FPS              ~52.8
```

## Logical runtime

```text
steps=14119
skipped_deadlines=36
slow_steps=4
failures=0
```

Logical cadence remains fundamentally healthy while physical delivery degrades.

## Frame-gap class

Canonical `screensaver_perf.log`:

```text
events                  ~270
median                  ~52.3ms
p95                     ~129.2ms
>=100ms                 30
max                     ~191.4ms
```

## Spawn/liveness

No pull-style interval was found where the active logical visualizer remained physically stranded at `paint=0`.

## Conclusion

The restored worker+push state is still load-sensitive in the same broad class as previous worker+push evidence.

The surviving problem is physical presentation under contention, not the visualizer logical clock.

Use this as the heavy-load reference for the Quick architecture benchmark.
