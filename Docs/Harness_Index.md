# Harness Index

Last updated: 2026-08-19

Compact routing for recurring investigation commands.

Harness success is evidence, not final visual/timing/lifecycle sign-off.

## 1. Full / targeted tests

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900
pytest --collect-only tests -q
pytest path\to\test_file.py -q --tb=short
```

Use `Docs/TestSuite.md` for validation level and current P2 gate routing.

## 2. Visualizer authored-fidelity replay

Use the repository `.venv` on Windows:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe tools\visualizer_replay.py verify
.\.venv\Scripts\python.exe tools\visualizer_replay.py metrics
```

Normal infrastructure work uses `verify` read-only.

Do not regenerate goldens to accommodate scheduler/presentation changes.

Phase-2 behavioural evidence remains in:

`Docs/phase_reports/P02_VISUALIZER_FIDELITY_LOCK.md`

For Bubble timing/feel additionally read BTF:

`Docs/Guardrails/Bubble_Temporal_Fidelity.md`

## 3. Current logical-runtime / P2 gates

Find current tests by contract rather than assuming a frozen filename list:

```powershell
rg -n "VisualizerLogicalRuntime|generation 0|mode switch|Spectrum|Pause|feedback|BTF|single clock|thread affinity" tests
```

Run the focused current P2 set.

Required coverage is defined by:

`Docs/P2_Behavioral_Gates.md`

Important current rules:

- scheduler must prove actual ~90-Hz-class service;
- worker logical code cannot mutate GUI/GL;
- exactly one logical clock;
- generation 0 is valid;
- paused Spectrum visibility means rendered pixels/height, not non-zero floats;
- Pause/Play identity and Pause/Play no-hitch are separate;
- BTF is multi-layer, not average FPS.

## 4. Bubble temporal checks

Existing Bubble cadence/replay tests remain useful for:

- discrete event survival;
- lane-free publication;
- trajectory/elasticity;
- no stale event replay.

But current worker architecture means no harness should describe the production logical cadence as
the “existing UI visualizer tick.”

BTF requires combining behavioural goldens with:

- logical achieved Hz/gaps;
- source freshness;
- publication progression;
- state-to-paint;
- installed perception.

## 5. Spectrum checks

Paused Spectrum contract:

```text
presentation-owned idle scene
source identity absent
fresh-source wait retained
visible resting bars
Play -> fresh real source replaces in place
```

A test double that merely records frame kwargs cannot certify visual output.

Use real GL/pixel or renderer-aware pixel-height evidence.

## 6. Current runtime flags

Use only relevant families:

```text
--perf
--gpu-timing
--usage
--viz
--geo
--set
--life
--cache
```

`--gpu-timing` is heavier and should not be compared directly with a plain `--perf` run without
naming observer difference.

## 7. Evidence locations

Live sidecars:

```text
logs/
```

Preserved evidence:

```text
logs/evidence_chest/<run_name>/
```

Current parser:

```powershell
python tools/recovery_evidence_parser.py --source logs --output-dir logs/_analysis_live
```

Use its current output to separate:

- logical tick gaps;
- source age where emitted;
- visualizer state-to-paint;
- compositor request/paint tails;
- transition windows;
- lifecycle events.

Parser name is historical and does not confer implementation authority on an old branch.

## 8. Shared high-refresh control

When investigating visualizer/system performance, include the 165 Hz display without a visualizer.

If it degrades badly too, treat that as shared GUI/compositor delivery evidence.

Do not optimize Bubble or individual transitions first unless their own cost is named.

## 9. Pause/Play feedback check

Current investigation target:

- MediaWidget control-feedback event;
- number of full parent-card update/paint requests;
- animation duration/fps/gap tails;
- visualizer logical gaps;
- display request/state-to-paint tails.

The fix must preserve feedback meaning while removing large-parent per-frame repaint waste.

Do not “optimize” by simply lowering feedback FPS.

## 10. Lifecycle

Use focused Settings/Edit/shutdown tests plus repeated real runtime loops.

Check:

- logical runtime stops/joins;
- generation 0 remains valid;
- stale mailbox state is fenced;
- GL/accounting returns to baseline;
- no retired callback publishes.

## 11. Historical evidence use

Historical bug records remain useful negative controls.

Do not copy old:

- QOpenGLWidget visualizer surface;
- GUI-QTimer visualizer clock;
- transition-scoped visualizer presentation;
- paint-ack admission;

back into current code because an old harness describes them in detail.
