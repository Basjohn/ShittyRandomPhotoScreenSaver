# Acceptance Evidence — 2026-08-20 04:46–13:03 — Diagnostic Long Soak — LIFECYCLE PASS / PRESENTATION DIRECTION REINFORCED

## Provenance

Evidence confidence:

```text
PRIMARY RAW
+
PRIMARY OPERATOR for visible post-wake behavior
+
INFERENCE where explicitly labelled
```

Raw ZIP:

```text
dc49978b-ed1b-454a-9ec3-eea14544fbaf.zip
```

SHA-256:

```text
7bf1c99aedce5f484f41e80729ae7940b411f439328561491ce93651b49afe22
```

Runtime product:

```text
SRPSS_Diagnostic.exe
entrypoint=main_diagnostic
build_flavour=diagnostic
frozen=True
```

### Source identity caveat

The compiled diagnostic log does **not** embed `[SOURCE_HEAD]`.

Therefore the raw evidence does not itself prove an exact source SHA.

Contemporaneous repository `main` reviewed during analysis was:

```text
7d1befce2eab44c379a2919aca0e84b05fedc5a7
4.7.2 - Push Pre-Benchmark Baseline. Good Light, Terrible At Even Modest Load
```

Treat that as a contemporaneous source anchor only, not as a SHA embedded by the raw run.

## Archive session separation

The ZIP contains multiple diagnostic sessions.

Observed starts include:

```text
2026-08-19 22:42:16  run
2026-08-20 02:04:06  preview
2026-08-20 04:46:04  run  <- long soak analysed here
```

Do not merge the earlier short sessions into the soak.

The relevant uninterrupted run is:

```text
start: 2026-08-20 04:46:04
stop:  2026-08-20 13:03:36
elapsed: 8 h 17 m 32 s
```

Usage telemetry is continuous for this run:

```text
sequence=1 at 04:46:05
sequence=1991 at 13:03:35
session_stop sequence=1991
```

---

# 1. Dark-residency / display topology

At soak start Windows exposed one display:

```text
screen=0 detected_hz=60 target_fps=60
```

The physical displays remained off for most of the run.

At approximately `12:55:56`, display topology began changing as the real displays returned.

The runtime then survived three monitor-topology generation changes in rapid succession:

```text
12:55:57  generation=1 reason=monitor_topology
12:56:11  generation=2 reason=monitor_topology
12:56:14  generation=3 reason=monitor_topology
```

Observed refresh/topology reports during settling include:

```text
12:55:59  screen 0 detected_hz=165 target_fps=165
12:55:59  screen 1 detected_hz=60  target_fps=60
```

There was additional transient detection churn before the final generation settled.

By `12:56:16–12:56:18` both final displays had:
- render surfaces;
- intentional first frames;
- compositor readiness;
- coordinated fade completion.

Final steady render timers reported:

```text
screen 0 display=164Hz target=165Hz interval=6.06ms
screen 1 display=60Hz  target=60Hz  interval=16.67ms
```

The runtime then continued through real image transitions and Bubble visualizer work until normal exit.

Application exit:

```text
13:03:36 generation=4 reason=application_exit
```

Final shared-memory accounting:

```text
segments_created=80
segments_live=0
live_bytes=0
segments_consumed=80
segments_reclaimed_late=0
unlink_failures=0
```

## Operator-visible result

After display wake the product was visibly alive and continued through transitions rather than remaining frozen/dead.

## Conclusion

**SUPPORTED:** current monitor-off/wake and topology-recreation architecture is healthy enough to leave the active repair lane.

Keep it as a permanent migration/release regression gate.

This run does not prove every possible display topology sequence, but it is a strong real-world lifecycle pass after long residency and unusually aggressive topology churn.

---

# 2. Long residency did not progressively degrade 60 Hz presentation

The retained PERF rotation window begins at approximately:

```text
06:39:30
```

and reaches wake at approximately:

```text
12:55:30
```

Within that retained pre-wake period there are:

```text
565 completed screen-0 60 Hz Slide paint windows
```

Hourly Slide medians:

| Hour | n | completed FPS | request acceptance | dt p95 | median run max | paint p95 |
|---|---:|---:|---:|---:|---:|---:|
| 06 | 31 | 59.8 | 99.67% | 16.78 ms | 36.16 ms | 5.67 ms |
| 07 | 90 | 59.75 | 99.67% | 16.78 ms | 36.23 ms | 5.70 ms |
| 08 | 90 | 59.8 | 99.67% | 16.78 ms | 35.77 ms | 5.70 ms |
| 09 | 90 | 59.8 | 99.67% | 16.78 ms | 35.37 ms | 5.69 ms |
| 10 | 90 | 59.7 | 99.67% | 16.78 ms | 35.84 ms | 5.69 ms |
| 11 | 90 | 59.7 | 99.67% | 16.78 ms | 35.49 ms | 5.71 ms |
| 12 | 84 | 59.7 | 99.67% | 16.78 ms | 36.26 ms | 5.71 ms |

Simple linear trend over the retained Slide population is effectively flat:

```text
avg_fps slope                  ~-0.005 FPS/hour
request acceptance slope       ~+0.009 percentage points/hour
dt p95 slope                   ~+0.001 ms/hour
dt max slope                   ~-0.083 ms/hour
paint p95 slope                ~+0.009 ms/hour
```

## Conclusion

**WEAKENED/REJECTED as primary explanation:** the current cadence problem is not a progressive hours-alive degradation mechanism.

The long-running dark 60 Hz topology remains stable while process memory/handles rise separately.

---

# 3. Post-wake logical/compute health

A short generation-1 visualizer runtime began at `12:56:01` and retired cleanly during topology churn:

```text
generation=1
steps=983
skipped_deadlines=1
slow_steps=0
failures=0
joined=True
```

The final generation-3 logical runtime began at `12:56:17` and stopped normally at application exit:

```text
generation=3
steps=39502
skipped_deadlines=26
slow_steps=0
failures=0
joined=True
```

Final Bubble compute cadence:

```text
offered=39502
submitted_tasks=39495
publish_ratio=1.000
worker_busy_deferrals=7
result_waiting_deferrals=0
submission_failures=0
stale_results=0
```

At the last usage sample:

```text
compute submitted=66808
compute completed=66806
compute queue_depth=0
IO submitted=3849
IO completed=3847
IO queue_depth=0
```

The remaining deltas are active work at sample time, not an accumulated queue.

## Conclusion

**STRONGLY SUPPORTED:** retain the dedicated logical runtime and bounded current compute model.

This run gives no evidence for reverting to GUI-driven logical cadence or resurrecting the historical dedicated FFT process.

---

# 4. Post-wake physical presentation still exhibits the target failure class

After the final mixed-refresh generation settled, retained completed paint windows include:

```text
screen 0 / 165 Hz: 9 Slide, 3 Blockspin
screen 1 / 60 Hz:  9 Slide, 3 Blockspin
```

## 4.1 165 Hz screen

Slide medians:

```text
completed FPS           155.1
request acceptance      94.96%
dt p95                  10.79 ms
median run max          40.40 ms
worst observed max      101.30 ms
paint p95               2.85 ms
```

Blockspin medians:

```text
completed FPS           156.0
request acceptance      95.56%
dt p95                  10.81 ms
worst observed max      57.45 ms
paint p95               3.00 ms
```

## 4.2 60 Hz screen with Bubble

Slide medians:

```text
completed FPS           58.8
request acceptance      98.71%
dt p95                  18.97 ms
median run max          66.23 ms
worst observed max      102.37 ms
paint p95               8.30 ms
```

Blockspin medians:

```text
completed FPS           59.4
request acceptance      99.45%
dt p95                  18.17 ms
worst observed max      73.53 ms
paint p95               9.01 ms
```

## 4.3 Severe-gap population

Post-settle `FRAME_GAP_OWNER` records:

```text
screen 0 / 165 Hz:
    n=63
    median=51.90 ms
    p95=93.34 ms
    max=101.30 ms
    >=50 ms=34
    >=100 ms=2
    median local paint=0.96 ms

screen 1 / 60 Hz:
    n=64
    median=55.94 ms
    p95=86.79 ms
    max=102.37 ms
    >=50 ms=41
    >=100 ms=1
    median local paint=1.585 ms
```

Gap records cover Slide and Blockspin. The failure is therefore not unique to one transition.

## 4.4 Bubble overlay cost

Representative 10 s Bubble overlay GPU windows after wake are generally around:

```text
GPU p50 ~0.64 .. 0.99 ms
GPU p95 ~0.70 .. 1.12 ms
```

while physical gap tails remain tens of milliseconds.

## Conclusion

**STRONGLY SUPPORTED:** the next architecture experiment should challenge physical presentation ownership rather than optimize individual transition/visualizer algorithms.

Slide is useful as the first architecture discriminator because it is simple and its continuous linear motion exposes missing physical opportunities. It is not identified as the root cause.

Blockspin remains a secondary stress/regression case.

---

# 5. Long-run memory/handle retention signal

Usage telemetry is continuous across the full soak.

To reduce startup/warmup distortion, a simple linear fit was taken from approximately:

```text
05:01:05 -> 12:55:50
```

while the runtime remained in the dark single-display topology.

Approximate slopes:

```text
main USS               +29.216 MB/hour
main private commit    +89.960 MB/hour
main RSS               +28.175 MB/hour
app handles            +15.077/hour
```

In the same interval:

```text
app threads            slope ~+0.04/hour; median 78; range 77..79
GL resources           median 10; range 10..11
RM resources           median 31; range 29..33
dedicated VRAM         no comparable monotonic rise
```

Hourly main USS/private-commit medians make the trend visible:

| Hour | USS MB | private MB | handles | threads | dedicated VRAM MB | RM | GL |
|---|---:|---:|---:|---:|---:|---:|---:|
| 05 | 644.8 | 1780.7 | 1843 | 78 | 312.5 | 29 | 10 |
| 06 | 659.6 | 1861.4 | 1860 | 78 | 312.5 | 31 | 10 |
| 07 | 686.8 | 1951.3 | 1875 | 79 | 312.5 | 31 | 10 |
| 08 | 712.8 | 2040.3 | 1890 | 79 | 312.5 | 31 | 10 |
| 09 | 754.8 | 2135.6 | 1907 | 79 | 312.5 | 31 | 10 |
| 10 | 783.5 | 2218.0 | 1921 | 78 | 312.5 | 31 | 10 |
| 11 | 828.5 | 2330.3 | 1935 | 78 | 312.5 | 31 | 10 |
| 12 | 856.5 | 2418.4 | 1948 | 78 | 312.5 | 31 | 10 |

### Caveat

This is a **Full Telemetry Diagnostic** runtime emitting very high logging/telemetry volume.

The evidence establishes a retention slope in this diagnostic shape. It does **not** establish:
- a production leak;
- Python cyclic GC as the owner;
- GL/resource-manager ownership as the owner;
- cache growth as the owner;
- telemetry/logging as the owner.

Current source does not globally disable Python GC merely because `FRAME_GAP_OWNER` records contain `gc_enabled=0`; PERF installs a GC timing callback rather than calling `gc.disable()`.

## Conclusion

**NEW PARALLEL RESOURCE QUESTION, NOT P2 PRESENTATION OWNER.**

Required future test:

```text
ordinary/light-telemetry long soak
vs
Full Telemetry Diagnostic long soak
```

Do not make this a prerequisite for the physical-presentation benchmark.

---

# 6. Diagnostic Winlogon URL result

During this session the diagnostic build's Reddit/browser link escape did not behave like the normal installed SCR path.

Current source intentionally treats the diagnostic product as an interactive/direct URL launcher and skips the ordinary secure helper contract.

Therefore this run does not establish a production `.scr` Winlogon regression.

## Conclusion

**OUT OF ACTIVE LANE.**

Only reopen if the ordinary installed screensaver reproduces the failure through its real secure-helper/Task-Scheduler handoff.

---

# 7. Engineering conclusions changed by this run

## Promoted / strengthened

1. Keep `VisualizerLogicalRuntime`.
2. Keep latest-state + one-pending push reference.
3. Keep current bounded FFT/audio compute architecture; no dedicated FFT process resurrection.
4. Challenge physical presentation ownership with a real standalone threaded `QQuickWindow` benchmark.
5. Tail latency / missing physical opportunities remain the acceptance target; average FPS is insufficient.
6. Keep monitor topology/wake as a later parity/regression gate for any winning presenter.

## Demoted / separated

1. Monitor wake is no longer an active repair priority.
2. Diagnostic direct-browser Winlogon behavior is not a production blocker.
3. Long-run memory/handle retention is a separate resource investigation and does not explain the stable pre-wake 60 Hz cadence.
4. Per-transition/Bubble optimization is not justified by this evidence.

## Benchmark consequence

Add a runtime-presentation-population axis to reference characterization:

```text
P0 minimal common architecture workload
P1 production-shaped enabled widget/card population
```

The user's separate installed A/B showed widget population materially changes Bubble-active GPU load. Treat that as shared presentation/composition coupling to measure, not as proof that an individual widget is the cadence owner.

Stage-1 Quick still proves the minimal common P0 scheduling/presentation hypothesis before migrating all widgets.
