# 12 — Test and Benchmark Protocol

## Objective

Prove the reconstructed architecture is better than both `00edb57` and `7376bb9` without sacrificing the core experience.

## Environment manifest

Record for every official run:

- commit;
- branch;
- dirty/clean state;
- date/time;
- Windows version;
- Python version;
- PySide6 version;
- GPU and driver;
- CPU;
- RAM;
- display count/resolution/refresh rate;
- power profile;
- Spotify/audio source;
- SRPSS settings;
- image source/cache state;
- background applications;
- log level and diagnostics enabled.

## Standard scenarios

### S1 — Cold start idle

- launch;
- visualizer hidden or inactive as normal;
- no transitions after initial stabilization;
- 10 minutes.

Measures idle work and memory warmup.

### S2 — Visualizer steady state

- fixed mode;
- fixed deterministic input or repeatable live input;
- no image transition during measurement window;
- 10 minutes.

Run Spectrum and Bubble separately.

### S3 — Image transitions

- visualizer disabled;
- regular image changes;
- representative transition set;
- 15 minutes.

### S4 — Combined normal operation

- visualizer active;
- image cycling;
- overlays active;
- 30 minutes.

### S5 — Settings lifecycle loop

- 50 open/apply/close cycles;
- include no-op and changed settings;
- visualizer and transitions active where possible.

### S6 — Edit lifecycle loop

- 50 enter/exit cycles;
- mixed with Settings cycles.

### S7 — Background CPU load

- controlled CPU stress leaving system responsive;
- combined normal operation;
- 10 minutes.

### S8 — Background disk/decode load

- controlled file activity;
- combined normal operation;
- 10 minutes.

### S9 — Background GPU load

- controlled 3D or compute load;
- combined normal operation;
- 10 minutes.

### S10 — Mixed hostile load

- CPU + disk + GPU background activity;
- combined operation;
- 10 minutes.

### S11 — Long soak

- 2 hours;
- image cycling;
- visualizer modes rotate or fixed representative mode;
- periodic Settings/Edit if automated safely.

### S12 — Display topology

Where supported:

- primary display changes;
- display disconnect/reconnect;
- resolution/scale change;
- sleep/wake.

## Metrics

### Frame pacing

- frame count;
- average FPS;
- p50/p90/p95/p99/max frame interval;
- count over 25 ms;
- count over 33 ms;
- count over 50 ms;
- count over 100 ms;
- latest-scene age at paint;
- paint duration;
- update coalescing rate.

### Visualizer

- input-to-state latency;
- state publication rate;
- logical simulation step;
- dropped/coalesced render states;
- golden-output errors;
- manual review result.

### CPU/threading

- process CPU;
- main-thread/event-loop delay;
- worker CPU if available;
- task submissions by category;
- queue depth;
- longest tasks;
- callback backlog.

### Memory

- RSS;
- private commit;
- Python heap where available;
- CPU cache tracked bytes;
- GL tracked bytes;
- driver dedicated VRAM;
- resource count by type;
- live resources by generation.

### Lifecycle

- context generation;
- cross-thread errors;
- stale publication count;
- remaining timers/workers;
- old-generation resource count;
- reentry success.

## Initial pass gates

These gates may be tightened after Phase 1 measurement.

### Visualizer

- all golden tests within mode-specific tolerance;
- no manual loss of reactivity, Spectrum shape, Bubble elasticity, or smoothness;
- no presentation-cadence dependency.

### Frame pacing

At idle/normal load:

- p95 near one display interval or documented equivalent;
- p99 materially better than donor;
- no repeated 100+ ms gaps without external system cause;
- maximum outliers investigated;
- average FPS cannot compensate for failed tail metrics.

### Lifecycle

- zero `QOpenGLContext` cross-thread errors;
- 50 Settings + 50 Edit + 50 mixed cycles pass;
- no old-generation resource survives.

### Memory

For dual 1440p target environment:

- no monotonic growth;
- preferred VRAM under 300 MiB, investigate above 400 MiB, fail pending explanation above 500 MiB;
- preferred RSS under 600 MiB, investigate above 750 MiB, fail pending explanation above 900 MiB;
- tracked resources explain expected live memory.

### CPU

- materially below both evidence versions in comparable scenarios;
- no one-core saturation under normal idle/visualizer operation;
- no general compute task per frame;
- task submission rate reduced and categorized.

## Comparison method

Use the same scenario and environment for:

1. `00edb57`;
2. `7376bb9`, if needed for reference;
3. current recovery commit.

Do not compare a short idle run with a long active run.

Use median of at least three runs for important release metrics when practical.

## Regression rule

A phase is rejected when it improves its target metric but causes:

- visualizer fidelity failure;
- worse p99/max pacing;
- lifecycle warning;
- memory growth;
- unexplained task-rate increase;
- overlay/display regression.

## Artifact retention

Store:

```text
logs/evidence_chest/
logs/benchmarks/<commit>/<scenario>/
docs/phase_reports/
docs/benchmark_reports/
```

Include:

- raw logs;
- parsed CSV/JSON;
- environment manifest;
- summary report;
- screenshots/video references where used;
- exact command or script.

## Benchmark integrity

- warm up consistently;
- note cache state;
- avoid changing log verbosity between candidates;
- do not omit failed runs;
- separate application CPU from whole-system CPU;
- state external background load precisely;
- report uncertainty and scenario differences.
