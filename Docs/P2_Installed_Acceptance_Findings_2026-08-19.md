# P2 Installed Acceptance Findings — Third Run — 2026-08-19

Installed source identity from the log:

```text
[SOURCE_HEAD] 8ac2421e2bc0a7153942fc33eb9f348b505cde9d
```

This is the authoritative behavioral checkpoint for this run even if documentation commits are added afterward.

---

# Operator result

The third installed acceptance is a hard failure.

Reported:
- worst visualizer performance so far;
- transitions universally poor;
- Pause/Play hitching remains and feels worse;
- mouse controls and physical media keys both trigger the hitch;
- all visualizer modes are affected;
- Bubble is not the unique failure owner.

---

# Source-ID diagnostic

The new debug/script-only diagnostic worked:

```text
[SOURCE_HEAD] 8ac2421e2bc0a7153942fc33eb9f348b505cde9d
```

Retain it.

---

# Slice K

K genuinely changed GSMTC transport ownership from:

```text
submit IO work
-> GUI waits for completion
```

to:

```text
submit IO command
-> GUI returns immediately
```

This is a legitimate correction.

Installed reality falsifies the stronger causal claim that the old wait owned the Pause/Play hitch or broad dispatch starvation.

Both:
- mouse Pause/Play;
- physical media-key Pause/Play

still hitch.

Therefore K should be retained as a design improvement, but the causal investigation moves downstream to the shared playback-state/presentation edge.

---

# Slice L

L's unit gate proves selected expensive media subpainters are skipped for a clean controls-row-only repaint.

Installed production still shows expensive repeated parent paint activity.

Representative windows:

```text
50 calls avg 5.11 ms
50 calls avg 4.95 ms
50 calls avg 5.22 ms
50 calls avg 5.90 ms
45 calls avg 6.39 ms
```

Therefore production Gate 7C remains RED.

Potential reasons:
- real damage coalescing bypasses the fast path;
- BaseOverlayWidget parent paint remains costly;
- overlapping invalidation forces wider parent events;
- feedback is not the only owner of those paint windows.

Do not count the existing focused unit test as product acceptance.

---

# Logical-runtime diagnostic exception

The run contains:

```text
NameError: name 'is_transition_active' is not defined
```

from the slow-tick diagnostic path.

This stale reference existed before K/L and cannot explain the broad regression.

It must still be removed and locked with a failure-path test.

---

# Performance regression

Approximate comparison with the previous installed run:

| Metric | Previous | Third |
|---|---:|---:|
| 165 Hz transition median | ~140.2 FPS | ~111.5 FPS |
| 165 Hz worst | ~136.4 FPS | ~64.7 FPS |
| 165 Hz acceptance median | ~90.1% | ~75.6% |
| 60 Hz transition median | ~56.9 FPS | ~52.5 FPS |
| 60 Hz worst | ~55.6 FPS | ~41.3 FPS |
| event-loop p95 late-run | ~12.9 ms | ~27.7 ms |
| frame-gap rate | ~0.68/s | ~2.78/s |
| media.paint average | ~3.16 ms | ~5.37 ms |
| media.paint CPU/sec | ~14.2 ms | ~20.3 ms |
| logical skipped deadline rate | ~0.09% | ~0.32% |

Representative 165 Hz windows:

```text
108.7
64.7
96.1
114.2
133.0
119.7 FPS
```

One delivery window reached roughly:

```text
54.47% request acceptance
673 dispatch_pending_skips
dispatch-skip age p95 ~143.7 ms
```

This is not a small miss.

---

# Current delivery owner signature

The adaptive timer still generally wakes near its requested deadline.

Observed shape:

```text
wake lateness: low single-digit ms p95 class
paint_pending_skips: 0
dispatch_pending_skips: dominant
GUI dispatch/skip age: tens to >100 ms
```

Interpretation:

```text
deadline source wakes
-> requests GUI delivery
-> GUI has not serviced prior delivery
-> next display opportunity is skipped
```

GPU remains low.

This is a shared GUI-availability/presentation problem.

---

# All-mode visualizer evidence

The operator explicitly reports the Pause/Play hitch across visualizer modes.

The logs likewise show degraded visualizer handoff/presentation outside Bubble.

Bubble remains the strongest motion canary, not the unique owner.

Do not tune Bubble equations or cadence.

---

# Environment qualification

The third run also had higher total CPU load.

Approximate class:

```text
system CPU: ~41–44%
SRPSS CPU: ~104% median-class
GPU: low few-percent class
```

This prevents a clean claim that K or L alone numerically caused the whole regression.

It does not excuse SRPSS:
- SRPSS CPU increased;
- GUI dispatch deteriorated;
- physical presentation collapsed;
- a screensaver on this hardware should not become unusable under this level of CPU contention.

Robustness under ordinary contention is part of the architecture problem.

---

# New active architecture target

The dedicated logical runtime remains correct.

The active suspect is its steady-state notification/delivery mechanism:

```text
logical worker publishes latest state
-> request_logical_present()
-> GUI callback
```

for ordinary ~90 Hz publications, while physical display presentation is already independently paced.

The next correction should remove callback-per-logical-revision steady-state pressure and let the physical GUI/compositor presentation opportunity sample the latest current-generation logical mailbox state.

Explicit edge/lifecycle GUI mutations remain marshaled.

No FIFO.
No catch-up.
No second logical clock.
No new 90 Hz GUI timer.

This is a production architecture correction, not an A/B experiment.
