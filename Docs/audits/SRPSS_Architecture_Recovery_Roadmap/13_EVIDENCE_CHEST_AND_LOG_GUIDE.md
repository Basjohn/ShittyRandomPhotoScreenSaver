# 13 — Evidence Chest and Log Guide

## Required files

Repository-relative expected location:

```text
logs/evidence_chest/logs7376bb9.zip
logs/evidence_chest/logs00edb57.zip
```

Expected contents of each archive include:

```text
perf_widgets.log
screensaver.log
screensaver_cache.log
screensaver_geometry.log
screensaver_lifecycle.log
screensaver_perf.log
screensaver_settings.log
screensaver_spotify_vis.log
screensaver_spotify_vol.log
screensaver_usage.log
screensaver_verbose.log
```

## Evidence identity

- `logs7376bb9.zip`: donor/head `7376bb9`, generated around 2026-07-22.
- `logs00edb57.zip`: baseline `00edb57`, generated around 2026-07-23.

Recorded SHA-256 hashes:

```text
logs7376bb9.zip  2E0E125BF4D8877D55EFFAFEEE82CC3367EB9B4A319669122F372801878B0D74
logs00edb57.zip  90AF3A54058FEBD54E961CA56FFFBDDD26D8AB4204EC605C1E8C4C4305E5DAEB
```

Do not rename or modify either archive without updating this document and the Phase 0 report.

## Extraction

Cross-platform Python:

```bash
python -m zipfile -e logs/evidence_chest/logs7376bb9.zip logs/evidence_chest/head_7376bb9
python -m zipfile -e logs/evidence_chest/logs00edb57.zip logs/evidence_chest/baseline_00edb57
```

Keep extracted directories ignored if they are large/noisy. Preserve ZIPs.

## Questions Codex must answer from logs

### Presentation

- How often are visualizer microgaps reported?
- What are p95/p99/max intervals?
- Does starvation occur while transitions are inactive?
- Are paint requests pending for long periods?
- Are state generations diverging?
- Are frames delivered in bursts?

### CPU/tasking

- What is process CPU during active rendering?
- What is main-thread/event-loop delay?
- How many compute tasks are submitted per second?
- Which task categories dominate?
- Is GPU busy low while CPU remains high?

### Memory

- Does RSS plateau?
- Does private commit plateau?
- Does dedicated VRAM plateau?
- Does usage rise after each image, transition, Settings, or Edit cycle?
- Which tracked cache/resource counters correlate with growth?

### Lifecycle

- What happens immediately before Settings/Edit?
- Which workers/timers stop?
- Which generations change?
- Are old callbacks or resources retained?
- Is a context-current error present in the archive?
- If absent, does the log end before crash output is flushed?

### Visualizer

- What logical update rate is reported?
- What presentation gaps occur?
- Does mode state continue while compositor is paused?
- Does publication wait for presentation?
- Are amplitude/smoothing values changed by infrastructure?

## Known evidence conclusions

These conclusions are already supported strongly enough to guide architecture:

1. The donor visualizer suffers compositor cadence starvation even without an active transition.
2. Average FPS and improved `DT_Max` do not reflect perceived smoothness.
3. The donor path has extensive microgaps, paint waits, and tail latency.
4. The donor runtime is CPU-heavy while GPU busy can remain low.
5. The baseline looks and feels better but has severe RAM/VRAM growth and high CPU/task rate.
6. The donor's resource work appears to improve VRAM bounds relative to baseline.
7. The donor Settings/Edit lifecycle introduces or retains a cross-thread GL context failure not reproduced in the supplied baseline run.
8. Neither version is an acceptable final performance architecture.

## Important epistemic limit

The supplied donor ZIP does not necessarily contain the literal final `QOpenGLContext` error line. Do not falsely claim the archive captures it if it does not.

The user observed the crash and prior architecture evidence records the same error class. Treat it as a reproducible external observation requiring a new controlled lifecycle test.

## Recovery evidence parser

The repeatable read-only parser is `tools/recovery_evidence_parser.py`.

```powershell
python tools/recovery_evidence_parser.py `
  --archive logs/evidence_chest/logs00edb57.zip `
  --output-dir logs/evidence_chest/derived/baseline_00edb57

python tools/recovery_evidence_parser.py `
  --archive logs/evidence_chest/logs7376bb9.zip `
  --output-dir logs/evidence_chest/derived/head_7376bb9
```

It produces:

```text
summary.json
frame_intervals.csv
task_rates.csv
memory_usage.csv
gpu_usage.csv
lifecycle_events.csv
visualizer_gaps.csv
errors_and_warnings.txt
unknown_lines.txt
```

The parser:

- preserves timestamps and source line numbers;
- parses canonical sidecars by category to avoid double-counting verbose-log duplicates;
- records parser version, source archive hash, assumptions, and file sizes;
- retains every unclassified non-empty line for later inspection;
- treats frame records as aggregate windows because the archives do not contain every raw interval.

## Evidence protection

Do not modify original logs.

Derived data must state:

- parser version;
- source archive hash;
- commit;
- assumptions;
- excluded intervals;
- why intervals were excluded.

The evidence chest is a forensic input, not a convenient source of cherry-picked numbers.
