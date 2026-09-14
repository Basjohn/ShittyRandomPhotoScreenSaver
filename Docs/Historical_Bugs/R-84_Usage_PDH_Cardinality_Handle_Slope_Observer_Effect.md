# R-84 — Main-Process Handle Growth Survived PDH Cardinality Attribution

Date: 2026-09-14  
Status: PARTIAL — steady-generation leak hypothesis rejected; replacement-generation retention requires one final bounded churn proof

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [ ] AWAITING VALIDATION
- [ ] SOLVED

## Original Failure

Earlier lifetime evidence showed main-process Windows handles appearing to climb at roughly **+19 handles/hour** while RSS,
USS/private memory, thread count, shared-memory ownership, and worker resource counts remained broadly stable. The first
attribution hypothesis was that `--usage`'s 300-second PDH GPU query rebuilds and changing counter cardinality could explain
the apparent slope.

A preferred **58-minute Windows soak on 2026-09-14** disproved that as a complete explanation. It produced twelve PDH
generations and every generation carried the same cardinality: **15 GPU Engine + 1 dedicated-memory + 1 shared-memory = 17
counters**. A straight-line fit across the final long runtime generation still looked like roughly **+16 handles/hour**.
That was enough to keep R-84 open, but the series was noisy and did not identify an owner.

## Handle-Type Attribution Changed The Diagnosis

The follow-up ~56.5-minute Windows soak ran the new out-of-process handle classifier for the whole session:

- **226/226 `--usage` samples** completed;
- **57** independent `screensaver_handles.log` snapshots were captured;
- the classifier PID remained excluded from app aggregates;
- the long settled generation-0 interval (~18:13–18:40) was effectively flat.

Across that settled interval, five-sample `handles_main` medians moved only about **1812 -> 1814**. Persistent object classes
were likewise flat: `type_56` ~236/237, `Key` 66, `Section` 390, `File` 419, and `Semaphore` roughly 259–263. Therefore the
old “continuous +handles/hour leak” interpretation **did not reproduce when object-class history was available**.

At the explicit Settings/runtime replacement around 18:42, however, the newly settled generation-1 baseline stepped upward
by a persistent bundle of approximately:

- `type_56`: **+10**;
- `Semaphore`: **+10**;
- `Key`: **+6**;
- `Section`: **+3**;
- `File`: **+2**.

Subsequent ordinary visualizer/mode/transition activity did **not** staircase those persistent classes again. The remaining
question is now narrow: is that bundle a one-time native/lazy initialization cost of the first replacement generation, or does
**each complete runtime replacement** retain another bundle?

Do not regress this bug back into a generic “+handles/hour” hunt. The stable runtime is not currently exhibiting that failure
shape.

## `--usage` Observer Effect — Repaired And Validated

The first soak also exposed a separate diagnostic-performance defect. The old two-minute Windows topology/thread refresh used
psutil recursive-child discovery plus per-process `num_threads()`, backed by a GIL-held system snapshot. Heavy samples were
roughly **80–144 ms** and repeatedly coincided with large frame/visualizer tails.

Windows now uses one Toolhelp process snapshot for recursive topology and thread counts, retaining psutil only as fallback.
The follow-up soak validated the change:

- after startup, Toolhelp topology refreshes were roughly **26–59 ms** (median ~47 ms);
- all intended 15-second samples completed;
- the old regular two-minute visualizer/frame hitch signature disappeared;
- GPU/VRAM telemetry and 300-second PDH rediscovery remained intact.

The Toolhelp observer-effect repair is therefore closed. Do not restore the GIL-held Windows recursive `children()` /
per-process `num_threads()` path.

## Handle-Type Attribution Path

Windows `--usage` starts a low-cadence helper that writes `screensaver_handles.log` every **60 seconds**. The helper:

- takes `SystemExtendedHandleInformation` snapshots in its own process;
- filters to the SRPSS main PID;
- groups handles by kernel object type;
- duplicates only representative target handles **into the helper** to resolve object type names;
- never performs per-handle type/name queries inside SRPSS;
- is excluded from app process/thread/memory/handle aggregates;
- flushes each JSON record immediately and records explicit session/controller boundaries.

This path has already answered the broad attribution question. **Do not add another probe or another hour-long discovery soak.**

## Normal-Runtime Performance Findings From The Same Follow-up Soak

The several-hundred-ms stalls surrounding Settings are not accepted as normal steady-state behavior. Code ownership shows that
Settings explicitly stops the engine and begins full Quick runtime retirement before dialog/replacement construction. The
roughly 300–500 ms work therefore occurs inside an intentional full replacement boundary used by Settings, committed CUSTOM
edit reload, monitor-topology replacement, startup, and teardown. Ordinary visualizer mode/preset changes use the retained
runtime owner and do not take this path.

That classification is narrow: **any comparable stall outside those explicit replacement boundaries is a first-class runtime
performance defect.**

The soak did expose two such normal-runtime owners:

1. **Image rotation:** ordinary 3840x2160 rotations spent roughly **28–53 ms** in GUI-thread image publication. The async
   compute task already owned a processed `QImage`, but UI publication converted it to `QPixmap`, then Quick capture converted
   it back to `QImage`/RGBA and materialized ~33 MiB of Python bytes. The authored repair now captures detached
   `PresentationImage` state in the compute task and publishes that value directly, removing the GUI QPixmap round-trip.
   The current immutable presentation contract still materializes a Python `bytes` RGBA payload, so the final acceptance must
   also check that image changes no longer cause meaningful Python/Visualizer cadence spikes. If a residual spike survives
   while UI publication is cheap, the next repair is a Qt-native detached image/buffer contract through texture upload — not
   another probe and not visualizer retuning.

2. **Context Menu:** repeated 75–94 ms periods aligned with normal right-click/open/hide. The retained menu model incorrectly
   used one notify signal for immutable entries, visibility, and anchor coordinates; opening/hiding could therefore invalidate
   the QML Repeater model even though entries were unchanged. The authored repair gives entries, anchor, and visibility distinct
   notify signals so ordinary open/close does not rebuild the retained row/submenu model.

Both repairs require the same final Windows acceptance below; no separate performance soak is requested.

## Final Exit Gate — One Bounded Churn Run Only

This is the **last R-84 handle-discovery run**. Keep one visualizer mode/preset stable and perform **3–5 explicit Settings
open/close cycles**, allowing roughly **60–90 seconds** of settled runtime after each. Exercise a few ordinary image rotations
and Context Menu open/dismiss actions between or after cycles.

Use only:

`--debug --fresh --usage --perf --life`

Do not add `--verbose` or `--gpu-timing`.

Decision is binary:

1. **Persistent handle classes staircase by roughly another 20–30 handles per replacement:** this is a real
   generation-retirement/lifetime defect. Repair the existing retirement/constructor owners directly using the type evidence;
   do **not** ask for another broad diagnostic soak.
2. **Only the first replacement steps and later cycles plateau:** classify the step as one-time lazy/native initialization and
   close R-84.

The same run must also prove:

- normal rotations no longer have the GUI-thread QPixmap publication stage;
- detached publication is cheap and does not merely shift a large hitch into Python/Visualizer cadence;
- Context Menu open/dismiss no longer produces the prior 50+ ms event-loop tails;
- Toolhelp remains the active Windows topology source.

## Guardrail

Observer attribution must be proven, but probes are not substitutes for code ownership analysis. Once evidence narrows a
failure to a lifecycle or presentation seam, inspect and repair that seam directly. Preserve GPU/VRAM statistical fidelity,
transition source/destination truth, image accounting, stale-generation rejection, and visualizer reactivity while doing so.
