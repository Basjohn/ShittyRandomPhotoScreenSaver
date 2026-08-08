# Benchmark Report — <Commit / Scenario>

## Identity

- Working branch: `main`
- Candidate commit:
- Comparison commit:
- Scenario ID:
- Date/time/timezone:
- Run count and duration:
- Evidence folder/archive:
- Parser/version/command:
- Source hash where applicable:
- Clean/dirty state:

## Environment

- Entry point: canonical `main.py` (Media Center is not an evidence-capture variant)
- Windows:
- Python:
- PySide6:
- CPU:
- Installed RAM:
- GPU/driver:
- Displays/resolution/refresh/DPR/route:
- Power profile:
- SRPSS profile/settings:
- Image source/cache state:
- Visualizer source/mode/preset/playback authority:
- Transition/widgets:
- Background load:
- Logging/diagnostic configuration:

## Authored workload and equivalence

- Exact user actions/input sequence:
- Warmup duration/state:
- Fixed source segment/fixture:
- Material differences between candidate and comparison:
- Known confounders:

## Results

### Frame pacing and delivery

| Metric | Comparison | Candidate | Result |
|---|---:|---:|---|
| Average FPS | | | |
| p50 interval | | | |
| p90 interval | | | |
| p95 interval | | | |
| p99 interval | | | |
| Maximum interval | | | |
| >33 ms count | | | |
| >50 ms count | | | |
| >100 ms count | | | |
| Event-loop lateness p99/max | | | |
| Source-to-first-visible | | | |
| Latest-state age at paint p99/max | | | |
| Authoritative publications/sec | | | |
| Update requests/sec | | | |
| Paints/sec | | | |

### CPU, tasks, and callbacks

| Metric | Comparison | Candidate | Result |
|---|---:|---:|---|
| Whole-app CPU average/peak | | | |
| Main process CPU | | | |
| Child CPU | | | |
| Tasks/sec by dominant category | | | |
| Queue age p99/max | | | |
| Callback/GUI commit p99/max | | | |
| Handles | | | |
| Threads | | | |

### System memory

| Metric | Start | Warm | End | Peak |
|---|---:|---:|---:|---:|
| Whole-app RSS/working set | | | | |
| Main RSS | | | | |
| Child RSS by process | | | | |
| Private working set, if available | | | | |
| Whole-app private commit/private bytes | | | | |
| Main private commit | | | | |
| Child private commit | | | | |
| VMS/reserved/mapped, if available | | | | |

Do not add RSS and private commit together.

### Application resources

| Metric | Start | Warm | End | Peak |
|---|---:|---:|---:|---:|
| CPU cache logical/tracked bytes | | | | |
| QImage/QPixmap/display bytes | | | | |
| Pending future logical bytes | | | | |
| Shared-memory live bytes/mappings | | | | |
| Tracked texture/FBO/PBO/program/buffer bytes | | | | |
| Tracked/untracked gap | | | | |

### GPU memory

| Metric | Start | Warm | End | Peak |
|---|---:|---:|---:|---:|
| Dedicated VRAM | | | | |
| Shared GPU memory | | | | |
| Driver sample timestamp/age | | | | |
| Tracked GL bytes | | | | |
| Teardown idle-driver VRAM | | | | |

### Visualizer

- Modes affected:
- Input fixture/segment:
- Logical golden result:
- Production-executor temporal result:
- Known-bad negative controls:
- Source/event integrity:
- Generation/activation result:
- Manual user result separately by mode:
- Exact approval/rejection statement:

### Lifecycle

- Request/admission owner:
- Barrier arm/completion/timeout:
- QObjects/Python roots/tasks/resources at key checkpoints:
- Invalid wrapper/context warnings:
- Replacement count:
- Fresh first-frame/reveal identity:
- Graph placement/replay result:

## Interpretation

- Measured owner/cause:
- Confidence:
- What improved:
- What did not improve:
- Tracked/untracked explanation:
- Fidelity/quality consequences:

## Failures and uncertainty

## Rollback

- Exact rollback/revert commit:
- Accepted-state verification after rollback:

## Pass/fail

- [ ] Pass
- [ ] Fail
- [ ] Inconclusive; more evidence required

A candidate cannot pass solely from lower average FPS/CPU/task count/tracked bytes. User visual result, p99/max/first-visible, lifecycle ownership, and whole-process resource results are mandatory.
