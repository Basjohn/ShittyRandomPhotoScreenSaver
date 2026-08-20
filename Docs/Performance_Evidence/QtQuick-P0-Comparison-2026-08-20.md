# Qt Quick P0 common-workload comparison — 2026-08-20

## Status

**Architecture decision: ACCEPT Qt Quick as the runtime presentation destination.**

This report preserves the P0 evidence. It is not an active task list.

## Scope

The Quick candidate used the same deterministic 15-second Slide + Bubble workload as the preserved
worker+push/QRhiWidget reference.

The Quick arm used standalone top-level `QQuickWindow` instances, forced threaded scene-graph
rendering, OpenGL, and render-thread identities distinct from the GUI thread.

No worker heavy reference rerun is required.

## Load classification

The retained Quick evidence contains three lower-load runs and two externally heavy runs. Passive
CPU samples support the operator's corrected labels.

The heavy Quick runs were approximately mid-60s to high-70s percent system CPU at their sampled
median/p95 range.

## Whole-capture PresentMon summary

The raw whole-capture table remains useful for broad comparison, but maximum `DisplayedTime` values
must be phase-correlated before being described as active-animation holes.

| Candidate / load | Display path | p95 | p99 | raw max |
|---|---|---:|---:|---:|
| worker light | 165 Hz / GDI | 25.55 ms | 124.46 ms | 1358.86 ms |
| Quick light | 165 Hz / GDI | 9.47–9.97 ms | 17.45–23.30 ms | 236.59–236.60 ms |
| worker heavy | 165 Hz / GDI | 58.31 ms | 253.76 ms | 2280.88 ms |
| Quick heavy | 165 Hz / GDI | 12.15–12.16 ms | 41.38–53.46 ms | 418.57–451.44 ms |
| worker light | 60 Hz / legacy flip | 19.21 ms | 27.76 ms | 55.73 ms |
| Quick light | 60 Hz / legacy flip | 17.62–17.69 ms | 18.25–19.72 ms | 26.17–33.82 ms |
| worker heavy | 60 Hz / legacy flip | 21.67 ms | 58.87 ms | 69.50 ms |
| Quick heavy | 60 Hz / legacy flip | 19.38–19.72 ms | 20.95–21.68 ms | 61.59–62.87 ms |

## Important phase-correlation correction

The extreme raw 165 Hz maxima are **not valid descriptions of active Slide/Bubble cadence**.

The largest Quick GDI `DisplayedTime` values occur before the benchmark's first intentional visible
frame, while PresentMon capture is already active.

Representative correlation:

```text
Quick Light:
    ~236.6 ms rows occur ~0.48 s before first intentional presentation

Quick Heavy:
    ~419–451 ms rows occur before first intentional presentation
```

The worker reference raw maxima are contaminated by the same capture/startup region.

Therefore do not write:

> Quick has 237 ms light and 451 ms heavy active-animation stalls.

That is not what the phase-correlated evidence shows.

## Active-motion comparison

When evaluation is restricted to the active Slide/Bubble interval before the intentional synthetic
pause, the 165 Hz result is approximately:

```text
worker light:
    p95  ~13.9 ms
    p99  ~33.5 ms
    max  ~89.9 ms
    >=25 ms holes: 5

Quick light:
    p95  ~8.7–9.9 ms
    p99  ~12.0–12.2 ms
    max  ~16.6–23.3 ms
    >=25 ms holes: 0

worker heavy:
    p95  ~37.3 ms
    p99  ~76.5 ms
    max  ~253.8 ms
    >=25 ms holes: 19

Quick heavy:
    p95  ~12.1–12.2 ms
    p99  ~36.0–47.3 ms
    max  ~70.9–80.3 ms
    >=25 ms holes: 8–10
```

This is the central architecture result.

Under heavy external CPU load, Quick remains approximately in the same presentation class as the old
architecture under light load, and is better on several tail measures.

The 60 Hz path also remains healthy; heavy Quick stays near refresh-limited delivery and materially
improves the old heavy p99 behaviour.

## 165 Hz GDI row-count caution

Do not naively calculate continuous "physical FPS" as:

```text
non-NA DisplayedTime rows / capture seconds
```

for the 165 Hz GDI path when those rows do not represent continuous display occupancy over the phase.

For that path, phase-correlated `DisplayedTime` tails/severe-gap distribution is the safer
discriminator.

## Conclusion

The experiment answered its architecture question.

Standalone threaded `QQuickWindow` materially improves physical presentation cadence and resilience
for the representative workload while still using Python/PySide and representative existing
rendering work.

Therefore:

- proceed with one Qt Quick runtime-presentation migration;
- do not continue broad QRhiWidget optimization as an alternative architecture programme;
- do not schedule a second native/C++ presenter migration;
- retain C++ only as a possible localized renderer optimization if future profiling earns it;
- preserve the raw P0 evidence as the architecture-selection record.
