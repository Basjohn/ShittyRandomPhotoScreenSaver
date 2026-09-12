# System Stats S0 Source Admission

Measured: 2026-09-12, source-mode Python 3.11 on the local Windows host.

This is a non-product source experiment. It created no Settings state, retained
card, runtime owner, QML component, or recurring scheduler.

## Method

`tools/system_stats_s0_probe.py` directly sampled the new neutral source at a
10-second interval. CPU is computed from the source-owned delta of
`psutil.cpu_times()`; RAM comes from one `psutil.virtual_memory()` snapshot.
The first CPU observation is intentionally `warming`.

The bounded CPU-contention run used two temporary worker processes owned by the
probe for the duration of the experiment. They were joined before the probe
exited. The GPU run attempted the persistent PDH adapter candidate once; a
terminal source failure is retained rather than rediscovering it every pulse.

## Results

| Condition | Samples | p50 | p95 | max | Source result |
| --- | ---: | ---: | ---: | ---: | --- |
| CPU/RAM idle, 10 s | 3 | 0.661 ms | 0.790 ms | 0.790 ms | RAM `ok`; CPU warming then `ok` |
| CPU/RAM, two CPU burners, 10 s | 3 | 1.177 ms | 1.464 ms | 1.464 ms | RAM `ok`; CPU warming then `ok` |
| CPU/RAM idle, 0.1 s diagnostic density | 15 | 0.523 ms | 0.773 ms | 0.785 ms | RAM `ok`; CPU warming then `ok` |
| CPU/RAM, two CPU burners, 0.1 s diagnostic density | 15 | 0.540 ms | 0.651 ms | 0.676 ms | RAM `ok`; CPU warming then `ok` |
| CPU/RAM plus local PDH GPU candidate | 3 | 1.073 ms | 363.273 ms | 363.273 ms | GPU `query_error`, zero open queries/counters after every observation |

The GPU timing includes its one failed setup attempt. Subsequent observations
were terminal `query_error` with zero query, engine-counter, memory-counter and
adapter-identity cardinality; they did not retry PDH discovery.

## Decision

CPU/RAM passes **source-cost admission**: the measured source remains in the
low-single-digit-millisecond range under this bounded contention shape and has
the required whole-system semantics without process/thread enumeration.

GPU/VRAM is **not admitted on this host**. PDH could not establish the required
adapter aggregate, and its failed setup alone is far above the CPU/RAM source
cost. Do not substitute the diagnostic PID-scoped GPU collector.

CPU/RAM is not yet a product-green result. A later runtime-generation shared
owner must still prove lease dormancy/cardinality and off-vs-on Visualizer and
event-loop tail behavior before a card is enabled. GPU/VRAM remains omitted
unless a later source probe succeeds with stable adapter identity, truthful
counter semantics and comparable cost.

## Reproduction

```powershell
python tools\system_stats_s0_probe.py --condition cpu-ram --samples 3 --interval-seconds 10
python tools\system_stats_s0_probe.py --condition cpu-ram --samples 3 --interval-seconds 10 --contention-workers 2
python tools\system_stats_s0_probe.py --condition gpu --samples 3 --interval-seconds 0.1
```
