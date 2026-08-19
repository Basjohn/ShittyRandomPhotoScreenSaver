# P2 Performance Evidence Ledger

Last reconstructed: 2026-08-19 20:24 SAST

This is the compact chronological index. Individual records contain the fuller evidence.

## Chronology

| Checkpoint | Source identity | Logical service | 165 Hz completed presentation | 60 Hz completed presentation | Installed conclusion |
|---|---|---|---|---|---|
| Accepted rollback/fidelity reference | `42033c84eabbdf25ccd34bb0e83f9e553f2f8f11` | historical | historical accepted reference; exact raw numbers not retained here | historical | Named rollback/fidelity baseline |
| 15:17 quantized worker | SHA not embedded | ~64 Hz effective; ~29% target deadlines skipped | median 143.6, range 143.2–149.5 FPS | median 58.0, range 57.4–58.2 | **REJECTED** worker scheduler |
| 15:29 same-day comparison | SHA not embedded | visualizer tick mostly low/mid-80 Hz; no dedicated runtime record | median 148.6, range 147.0–150.1 FPS | median 58.5, range 58.0–58.8 | Useful same-day high-refresh reference |
| 17:10 repaired worker, first installed acceptance | contemporaneous reviewed anchor `80c8ed35...`; SHA not embedded in raw log | ~89.8–89.9 Hz; 38 skips / 22636 steps; gen `-1` defect | median 131.6, range 103.8–152.2 FPS | median 57.6, range 52.7–59.6 | Scheduler fixed; product still failed |
| 19:08 second installed acceptance | contemporaneous tested anchor `ccb63542348fec5993a688142bc2e364f8149f6a`; SHA not embedded | ~89.9 Hz; valid gen `0`; very low skip rate | median 140.0, range 136.3–144.8 FPS | median 56.8, range 55.5–58.2 | Spectrum/gen0 fixed; hitch/shared delivery still failed |
| 20:02 third installed acceptance | **log self-ID** `8ac2421e2bc0a7153942fc33eb9f348b505cde9d` | ~89.9 Hz average; 43 skips; 4 slow; 1 failure | median 111.35, range 64.5–132.8 FPS | median 52.4, range 41.2–55.4 | **Worst run; shared presentation architecture now active target** |

## Important same-day direction of travel

### Logical scheduler

```text
first worker:
~64 Hz / ~29% target deadline loss
        ->
scheduler repair:
~89.9 Hz / <<2% loss
```

That fix is real and must not be forgotten merely because physical presentation later deteriorated.

### Physical 165 Hz delivery

Useful raw checkpoints:

```text
15:29 comparison       147.0–150.1 FPS
17:10 first repaired   103.8–152.2 FPS, median 131.6
19:08 second run       136.3–144.8 FPS, median 140.0
20:02 third run         64.5–132.8 FPS, median 111.35
```

The renderer is plainly capable of much better than the third-run class.

### Delivery-stage signature

Across the later runs, the repeated pattern is:

```text
adaptive deadline wake: comparatively timely
paint_pending_skips:    zero or negligible
dispatch_pending_skips: dominant
GUI dispatch/skip age:  tens to >100 ms
```

This is why current work targets GUI/presentation availability rather than shader throughput or
adaptive-timer deadline precision.

## Hypothesis ledger

| Hypothesis | Status | Evidence |
|---|---|---|
| Bubble compute is the main shared bottleneck | **REJECTED** | 17:10 Bubble publish ratio 1.000 with only 4 busy deferrals; later all-mode failures and non-visualizer display regression |
| Visualizer GPU/shaders are the main large-gap owner | **REJECTED / unsupported** | GPU remains low while both displays lose delivery; non-visualizer display also collapses |
| Python 3.11 Windows `Event.wait()` is suitable for the dedicated ~90 Hz scheduler | **REJECTED** | 15:17 raw run: ~64 Hz effective and ~29% target-deadline loss |
| High-resolution `perf_counter()` + bounded sleep repairs logical scheduler | **CONFIRMED** | 17:10, 19:08, 20:02 logical average returns ~89.9 Hz |
| Generation `0` can be truthiness-coerced to invalid sentinel | **BUG CONFIRMED / FIXED** | 17:10 starts `generation=-1`; 19:08 starts valid `generation=0` |
| Paused Spectrum only needs mathematically non-zero bars | **REJECTED** | 17:10 real renderer 0.010–0.030 was perceptually absent; 19:08 0.0738–0.4192 is visibly accepted |
| Dirty-region `update(rect)` alone makes media feedback cheap | **REJECTED** | 19:08 still has repeated real 50-call `media.paint` windows |
| Synchronous GSMTC transport wait is *the* Pause/Play hitch/shared dispatch root cause | **ROOT-CAUSE HYPOTHESIS REJECTED** | K removes GUI wait; 20:02 still hitches through mouse and physical media key, across modes |
| K fire-and-forget transport ownership is still a valid design correction | **RETAIN** | Removes real GUI wait without evidence that the async ownership itself is wrong |
| L selected-subpainter fast path proves installed feedback is cheap | **NOT ACCEPTED** | 20:02 production still shows repeated ~5–6+ ms parent paint windows |
| Adaptive timer wake precision is the dominant current owner | **CURRENTLY REJECTED** | repeated low-single-digit wake p95 with zero paint-pending skips and dominant dispatch-pending skips |
| Bubble is uniquely affected by Pause/Play hitch | **REJECTED** | direct operator report: all modes affected; mouse and physical media-key paths both reproduce |
| Steady-state worker → GUI callback-per-publication pressure is a shared owner | **ACTIVE ARCHITECTURE HYPOTHESIS** | fits current ownership and repeated GUI-dispatch starvation; not yet installed-confirmed |

## Durable conclusions

- One physical compositor surface per display remains the accepted broad presentation architecture.
- One dedicated mode-general logical clock remains accepted.
- Healthy logical cadence does not imply healthy physical presentation.
- Bubble is a temporal canary, not the presumed root cause.
- Installed perception can falsify a causal claim even when its unit test is green.
- A production-shaped test that proves a narrow mechanism does not automatically prove the full
  installed performance objective.
- When a source-owned boundary is sufficiently distinguished, a bounded architecture replacement can
  be preferable to another generic probe campaign.

## Next evidence rule

The next installed acceptance must create a new timestamped `Acceptance-*` record before further
production work. Do not overwrite the records above.
