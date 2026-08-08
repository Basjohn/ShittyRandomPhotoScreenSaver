# 13 — Evidence Chest and Log Guide

Last reconciled: 2026-08-02

## Purpose

The evidence chest preserves raw installed-runtime evidence, parser output, environment manifests, and rejected-candidate comparisons. It is forensic input, not a source of cherry-picked numbers.

## Evidence classes

### A. Original baseline/donor archives

Canonical historical archives:

```text
logs/evidence_chest/logs7376bb9.zip
logs/evidence_chest/logs00edb57.zip
```

Identity:

- `logs7376bb9.zip`: donor/reference `7376bb9`, generated around 2026-07-22;
- `logs00edb57.zip`: original baseline `00edb57`, generated around 2026-07-23.

Recorded SHA-256:

```text
logs7376bb9.zip  2E0E125BF4D8877D55EFFAFEEE82CC3367EB9B4A319669122F372801878B0D74
logs00edb57.zip  90AF3A54058FEBD54E961CA56FFFBDDD26D8AB4204EC605C1E8C4C4305E5DAEB
```

Do not rename/modify those files without updating the Phase 0 record and hashes.

### B. Current installed evidence folders

Use one folder per authored run or coherent comparison:

```text
logs/evidence_chest/MM_DD_<short-commit>_HH_MM/
```

Current temporary evidence identity:

```text
logs/evidence_chest/08_02_3877b2c7_20_27/
```

It contains the latest Settings/Edit/lifecycle/memory/prefetch evidence used by R-53, R-56, R-57, and `Current_Plan.md`.

A folder name is a convenient temporary identity, not a durable substitute for an environment manifest and exact commit.

### C. Rejected candidate archives/folders

Keep failed experiment evidence when it teaches a durable lesson, for example the rejected Spectrum smoothing logs originally supplied as `logsspectsmoo.zip`.

Record:

- candidate commit;
- accepted comparison commit;
- exact user verdict;
- scenario/environment;
- parser/analysis;
- revert commit.

## Expected log sidecars

A run may include:

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

Not every run must contain every sidecar. The manifest must state which diagnostic flags were enabled and whether missing files are expected.

## Evidence manifest requirements

Every current official folder/archive includes or is paired with:

- exact branch/commit and clean/dirty state;
- date/time/timezone and duration;
- normal or Media Center entry point;
- OS/Python/PySide/CPU/RAM/GPU/driver;
- displays/resolution/refresh/DPR/route;
- power profile;
- exact SRPSS settings/profile;
- image source/cache/warmup state;
- audio source/capture/mode/preset/playback authority;
- transition/widget activity;
- logging/diagnostic flags;
- user actions in order;
- expected versus unexpected termination;
- source archive hash where applicable.

Do not store credentials, API keys, personal titles/URLs, or copyrighted commercial audio.

## Raw evidence protection

- never edit raw logs in place;
- preserve source timestamps and file identity;
- derived/sanitized files live separately;
- document redactions and excluded intervals;
- do not omit failed runs;
- do not merge logs from different scenarios into one apparent timeline without explicit boundaries.

## Extraction

Cross-platform Python:

```bash
python -m zipfile -e logs/evidence_chest/logs7376bb9.zip logs/evidence_chest/derived/head_7376bb9
python -m zipfile -e logs/evidence_chest/logs00edb57.zip logs/evidence_chest/derived/baseline_00edb57
```

Large extracted directories may remain ignored while the source archive and derived summary are preserved.

## Recovery evidence parser

Use read-only parser:

```powershell
python tools/recovery_evidence_parser.py `
  --archive logs/evidence_chest/logs00edb57.zip `
  --output-dir logs/evidence_chest/derived/baseline_00edb57

python tools/recovery_evidence_parser.py `
  --archive logs/evidence_chest/logs7376bb9.zip `
  --output-dir logs/evidence_chest/derived/head_7376bb9
```

For plain current folders, use the parser's supported folder/input mode and preserve the exact command in the report.

Typical outputs:

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

Derived data records parser version, source hash/path, assumptions, file sizes, timestamps/line numbers, excluded intervals, and unknown/unclassified lines.

## Questions to answer from current evidence

### Visualizer and presentation

- Which mode/source/preset/activation was authoritative?
- What were source/publication/paint rates and ages?
- Was there one presentation cadence?
- Did logical events integrate before render coalescing?
- What was source-to-first-visible latency?
- Did Settings/Edit/mode switch reveal stale state?
- What did the user report separately by affected mode?

Logs can diagnose cadence and timing. They cannot certify feel.

### CPU/tasking

- Which categories dominate submitted, queueing, callback, and GUI-commit cost?
- What work occurs while hidden/static/unchanged?
- Is work duplicated by display or representation?
- Did a lower task rate change first-visible response or fidelity?
- Are diagnostics contributing meaningful load?

### System memory

Report separately:

- whole-app/main/child RSS;
- private working set where available;
- private commit/private bytes;
- VMS/reserved/mapped regions;
- thread/handle counts;
- tracked images/caches/resources;
- dedicated/shared GPU memory with sample age.

Do not add RSS and private commit. Do not treat stale asynchronous GPU samples as exact same-instant values.

### Resource ownership

- Did tracked application resources reach expected zero/plateau?
- Which logical representations remain live?
- How large is the tracked/untracked gap?
- Did full teardown reduce driver VRAM?
- Are pending tasks/mappings/callbacks retaining outputs?

### Lifecycle

- What exact event admitted stop/reload?
- Was teardown called from inside a retiring owner frame?
- Which QObjects/Python roots/tasks/timers/resources survived at arm, completion, or timeout?
- Did a modal wrapper's C++ object die before later code touched it?
- Was replacement constructed exactly once and only after zero ownership?
- Which fresh state authorized reveal?

### Cache/prefetch

- Were pending keys/bytes/count internally consistent?
- Did preferred/general selection overlap?
- Were multiple indices removed safely?
- Did stale callbacks repopulate or release current ownership?
- Did callback failure increase fallback/miss churn?

## Current strongly supported conclusions

1. Donor presentation orchestration damaged visual smoothness despite selected average improvements.
2. Original baseline behaviour was better but resource/task architecture was not acceptable.
3. Persistent shared-analysis/Bubble lanes changed approved timing and were rejected.
4. Paint-local Spectrum decay created a second cadence and was visually worse.
5. The preserved 08-02 Settings evidence succeeds but contains the R-56 invalid-wrapper failure; the later mechanical repair still needs installed confirmation.
6. The preserved 08-02 Edit evidence admits teardown from inside the retiring manager graph and proves the R-53 cause boundary above 99% confidence; the later mechanical repair still needs installed confirmation.
7. The preserved evidence proves the R-57 selected-index deletion defect; the later deterministic repair still needs installed image/transition confirmation.
8. The old linear Settings memory staircase did not reproduce in the latest two cycles.
9. Current absolute active RSS/private commit/VRAM remains excessive and not fully attributed.
10. Tracked-zero GL teardown and low teardown VRAM do not alone explain residual process memory.

## Epistemic rules

- distinguish direct log fact, source fact, inference, user visual verdict, and unresolved hypothesis;
- state confidence below 90% explicitly;
- do not claim a literal error line exists when only external observation/source architecture supports it;
- do not claim a leak from one non-equivalent snapshot;
- do not claim resource success from logical counters alone;
- do not use logs to overrule user-observed visual behaviour.

## Derived evidence retention

Derived outputs state:

- source path/archive hash;
- parser/version/command;
- exact commit/environment;
- assumptions and sanitization;
- exclusions and reasons;
- confidence and unresolved gaps.

The evidence chest preserves both successful and failed runs so later work cannot rewrite history.
