# Acceptance Evidence — 2026-08-19 19:59–20:02 — Third Installed Run — HARD FAILURE

## Provenance

**PRIMARY RAW + PRIMARY OPERATOR**

Raw pack:

```text
13490052-c96e-4501-b4cf-a29ba3370aca.zip
SHA-256: 16f532c43154de207d9ede734b01946a262285de21c12d6b8c88a3fbfb18890c
```

The log self-identifies:

```text
[SOURCE_HEAD] 8ac2421e2bc0a7153942fc33eb9f348b505cde9d
```

This source identity is exact.

## Operator-visible result

- Worst visualizer performance observed so far.
- Transitions universally poor.
- Pause/Play hitch remains and feels worse.
- Mouse and physical media-key Pause/Play both reproduce the hitch.
- All visualizer modes are affected.
- Bubble is not the unique owner.

Acceptance: **HARD FAILED**.

## Logical runtime

```text
generation=0
steps=13264
skipped_deadlines=43
slow_steps=4
failures=1
joined=True
```

Average cadence remains near the ~90 Hz class, but skip/tail quality is worse than the prior run and
one logical-runtime failure occurs.

## Diagnostic exception

The run hits:

```text
NameError: name 'is_transition_active' is not defined
```

inside the slow-tick diagnostic path.

This stale reference predates K/L, so it is a correctness defect but not the global regression root
cause.

## Physical 165 Hz presentation

Six completed windows:

```text
median 111.35 FPS
range 64.5 .. 132.8 FPS
```

Request acceptance:

```text
median 75.575%
range 54.47% .. 86.80%
```

Worst delivery window:

```text
54.47% acceptance
673 dispatch_pending_skips
dispatch-skip age p95 143.676 ms
dispatch-skip age max 236.364 ms
wake lateness p95 3.740 ms
paint_pending_skips=0
```

## Physical 60 Hz presentation

```text
median 52.4 FPS
range 41.2 .. 55.4 FPS
```

Request acceptance:

```text
median 91.045%
range 78.43% .. 96.17%
```

## Media paint after Slice L

Repeated production windows still include:

```text
50 calls avg 5.11 ms
50 calls avg 4.95 ms
50 calls avg 5.22 ms
50 calls avg 5.90 ms
45 calls avg 6.39 ms
```

Across parsed media-paint windows, the mean of the reported window-average costs is ~5.68 ms.

Conclusion: the narrow selected-subpainter unit gate did not establish installed feedback/card paint
efficiency.

## K causal hypothesis — falsified

Slice K removed GUI waiting from transport command execution.

The visible hitch persists through:

```text
mouse command path
physical media-key path
```

and across all visualizer modes.

Therefore:

```text
"the synchronous GSMTC transport wait is the Pause/Play/shared hitch owner"
```

is **REJECTED** as a root-cause claim.

K's non-blocking transport design may remain.

## Shared delivery conclusion

The repeated installed signature is now too strong to treat as an edge-only problem:

```text
logical/source work continues
-> GUI presentation dispatch remains pending
-> later deadlines are skipped
-> all visualizer modes hitch
-> non-visualizer 165 Hz transitions also collapse
```

This run is the evidence checkpoint that promotes the shared logical→GUI→physical-presentation
ownership boundary into active architecture work.
