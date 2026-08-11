# 08 — CPU, Threading, and Workload Plan

Last reconciled: 2026-08-11

Current `main` is the implementation authority. Historical commits are used only as negative controls or forensic references; this plan contains no historical-candidate extraction seam.

## Current evidence and correction

Historical comparison runs could consume roughly one logical core and submit around 90–100 compute jobs per second.

A later attempt to solve this through persistent shared-analysis and Bubble lanes changed temporal behaviour and was rejected. Production Bubble therefore remains on the approved ordinary general COMPUTE executor model: one lane-free authored step is submitted through the bounded executor, with the existing source/event/dt/publication semantics preserved.

The 2026-08-10 source audit and the canonical mixed-load run at
`logs/evidence_chest/08_09_ca830d7_14_59/` sharpen the problem considerably:
SRPSS already moves much of its obviously slow network/decode/simulation work away
from the GUI thread, but the GUI thread still owns avoidable synchronous I/O and
pure-data work, while several genuinely GUI/GL-affine transactions are too broad.
The active optimization target is therefore **GUI availability and ownership**, not
lower visualizer cadence or a lower raw task count.

This plan does **not** create a second optimization programme. `Current_Plan.md`
owns execution order; this document owns the threading/workload architecture and
acceptance rules. Phase 7 remains the later visualizer/presentation-boundary phase.

## 2026-08-09 mixed-load evidence checkpoint

The supplied `ca830d7` session ran from approximately 14:21 to 14:59 and included
multiple full runtime retire/rebuild cycles, Bubble, a Bubble → Spectrum → Bubble
mode sequence, active image transitions, and a later mixed host-load interval.
The sidecars contain no ERROR or CRITICAL records.

### Lifecycle remained mechanically healthy

Four Settings runtime retirements completed in approximately `172`, `187`, `172`,
and `187 ms`; one committed CUSTOM/Edit retirement completed in approximately
`265 ms`. The destruction barriers armed with only the expected two
`PixelShiftManager` Python owners and completed without timeout. Large
`settings_dialog_close elapsed_ms` values are dialog dwell/lifetime measurements:
the dialog barriers themselves armed with two QObjects, zero Python owners, and
completed in the same timestamped turn. They are not evidence of slow destruction.

This means the threading work below must preserve the solved Settings/Edit ownership
model rather than using performance work as permission to weaken lifecycle gates.

### Frame delivery is late far more often than paint is expensive

Across the 238 owner-labelled frame-gap records in the supplied performance logs:

```text
metric                 median       p95        p99        max
frame gap              44.75 ms    91.33 ms  111.10 ms  139.54 ms
request age            35.29 ms    79.58 ms  109.34 ms  138.83 ms
paint work              0.79 ms     7.88 ms    8.57 ms    8.92 ms
```

The 165 Hz display reached a `139.54 ms` gap with `138.83 ms` request age and only
`5.34 ms` paint. The 60 Hz display reached `102.02 ms` with `78.87 ms` request age
and `7.64 ms` paint. This again falsifies "paint itself is the primary bottleneck"
for the dominant tail.

The late run also carried materially higher host pressure: machine CPU samples
reached roughly `21–25%`, while SRPSS application CPU reached roughly `98–109%`.
That makes this a useful mixed-load robustness checkpoint, not a clean code-only A/B.
Future intentional pressure tests must mark load-change timestamps explicitly.

### The image-install probe found a concrete root cause

The detailed image UI instrumentation now distinguishes the major setter stages:

```text
stage                              median       p95        max
QImage -> QPixmap                   4.95 ms      9.49 ms    11.67 ms
set_processed_image               35.84 ms    117.43 ms   128.42 ms
generic_pair_warm                 26.62 ms     64.45 ms    80.41 ms
compositor_setup                   0.11 ms     46.12 ms    58.47 ms
transition_construct               5.33 ms      7.11 ms     7.18 ms
transition_controller_start        1.29 ms      1.85 ms     5.46 ms
prewarm_overlay_raise              0.42 ms      1.51 ms     1.60 ms
post_start_overlay_accounting      0.40 ms      0.60 ms     0.63 ms
transition_specific_warm           0.01 ms      0.01 ms     0.02 ms
```

`generic_pair_warm` is therefore the dominant **steady** GUI/context-bound stage.
Compositor setup is usually almost free but has cold/recreation outliers. Transition
construction, controller start and overlay/accounting are not large enough to explain
the recurrent 30–80 ms setter cost by themselves.

The exact texture-key probe also resolves the previous reuse uncertainty. On the
first transition after a fresh runtime, the old image is cache-hit and only the new
texture uploads. On repeated steady transitions the logged terminally retained key
does **not** equal the next old-image key; the old lookup is false and the generic
warm performs two allocations/uploads. Repeated examples show the retained and next
old keys moving together but remaining distinct, so this is an identity/reuse
contract failure, not merely insufficient texture capacity.

The 2026-08-11 source trace identified the exact mechanism rather than inferring it
from the numeric pattern. `DisplayWidget` owned DPR `1.5`, while `ImagePresenter` was
constructed with an independent `1.0` DPR and never synchronized. The presenter reset
the destination to `1.0` before texture warm/retention; terminal completion then wrote
`1.5` and the presenter wrote `1.0` again. Those two real pixmap mutations reproduce
the observed `retained_key + 2 == next_old_key` divergence.

`ImagePresenter` now consumes the parent display's authoritative DPR and skips no-op
mutation. A production-shaped manager/presenter regression proves the retained texture
ID is the next old ID, records one old cache hit, and uploads only the following new
image. The 45-cycle resource harness still passes with one retained terminal texture,
bounded PBO reuse, and zero owned bytes after strict resets. Context/generation,
physical size, DPR/transform change, cancellation-to-old, and a genuinely different
terminal pixmap remain explicit invalidation boundaries. Installed identical-sequence
timing/resource A/B remains active in `Current_Plan.md`.

### Cold widget rendering is still visible at rebuild time

The widget profiler shows cached Reddit paints normally around `1–3 ms`, but cold or
recreation paints still reach tens of milliseconds (`~40–61 ms` for the primary
Reddit widget in this run, with smaller but still visible Reddit2 spikes). Gmail's
stable cache regeneration is smaller, roughly `~6–10 ms`, but is still currently
allowed to occur inside the paint path.

This supports a general rule: `paintEvent()` should consume prepared/cached state,
not discover that expensive static content preparation must happen synchronously
before the frame can be delivered.

### Bubble/Spectrum evidence says to preserve cadence

Bubble worker samples remain roughly `1–2 ms`; the mode continues to use the approved
ordinary executor adapter rather than a persistent compute lane. The run nevertheless
contains visualizer tick spikes up to `99.63 ms` and bounded source-age/latency warnings
roughly `80–107 ms`, including during mixed host/transition pressure. Spectrum also
produced an elevated latency sample during its short active interval.

That combination is important: **a small Bubble worker and a late visualizer tick are
not evidence that Bubble should be rescheduled.** They are consistent with the GUI
thread/presentation owner being unavailable. Phase 5 must first remove external GUI
starvation and repeated GUI/context-bound work before changing Bubble or Spectrum
clock semantics.

## Primary goal

Reduce unnecessary work, duplication, allocations, callbacks, synchronous I/O and
large GUI-owner transactions while preserving:

- exact approved visualizer logical and temporal behaviour;
- source-to-first-visible response;
- p99/max frame pacing;
- image/transition/widget quality;
- lifecycle and ownership boundaries;
- persistence durability and crash diagnostics.

The desired runtime contract is **Prepare → Commit → Persist**:

1. **Prepare — worker-owned:** network/file I/O, JSON, parsing/filtering/sorting,
   worker-safe image transforms, finite CPU calculation, immutable result assembly.
2. **Commit — GUI/context-owned:** generation/staleness check, minimal Qt/QPixmap/GL
   mutation, geometry/visibility changes, narrow repaint request, then return.
3. **Persist — serialized I/O-owned:** ordered/coalesced durable writes with explicit
   flush points. Persistence does not hold the GUI hostage to disk latency.
4. **Paint — GUI-owned but dumb:** consume already prepared/cached state. No disk,
   network, JSON, large model construction or cold static cache build in paint.

## Work inventory

Categorize recurring work by owner, trigger, and useful result:

- audio capture and shared analysis;
- mode-owned visualizer work;
- render-state publication;
- scene/update notification;
- transition timing and terminal release;
- image source selection, decode, transform, prefetch, identity and upload preparation;
- cache accounting/eviction;
- texture/PBO/FBO/program work;
- widget/provider polling and unchanged-state handling;
- metadata/artwork layout and publication;
- service-widget cache hydration/serialization;
- settings mutation and durable persistence;
- cursor/interaction overlays;
- lifecycle/barrier callbacks;
- logging/diagnostics;
- retries/backoff/fallback paths.

For each category record:

- owner and generation;
- trigger and requested frequency;
- accepted/completed/published frequency;
- thread/process;
- p50/p95/p99/max duration and queue age;
- allocations/copies/bytes retained;
- callback/GUI-delivery cost;
- behaviour while hidden/static/unchanged;
- cross-display duplication;
- whether state/result may be safely coalesced **after** logical integration;
- fidelity/lifecycle/resource invariants.

## Thread and lane model

### GUI thread

Keep only GUI/context-affine work and small immutable-state commits:

- QObject/QWidget/QPixmap lifecycle;
- QWidget geometry/layout/visibility/stacking/input;
- GL operations and scene presentation under the current context model;
- generation/staleness validation for published worker results;
- final worker-safe `QImage` → `QPixmap` promotion where required;
- minimal GUI timers and queued lifecycle admission;
- exact-wrapper validity checks.

Remove synchronous file/network I/O, JSON serialization, broad logging, expensive
pure-data preparation, repeated static allocation and cold content-cache construction
from GUI paths where the source audit identifies them.

### General IO pool

Use existing bounded IO capacity for independent blocking operations such as:

- Reddit/Weather/Gmail network access;
- widget/service cache reads and writes that do not require ordering with other writes;
- filesystem metadata/load operations;
- media/provider work already designed around one in-flight request.

Do not serialize all background work through one miscellaneous "third thread". That
would simply create a new choke point.

### Ordered persistence lane

Settings durability is a distinct workload because **order matters**. Critical
settings should become immediately authoritative in memory and be submitted to one
process-owned ordered persistence writer/lane that:

- snapshots a monotonically ordered revision;
- coalesces superseded pending revisions only where semantics allow;
- performs JSON serialization/temp-write/atomic replace away from GUI;
- exposes explicit flush/close boundaries for Settings completion, shutdown and any
  operation that requires durable acknowledgement;
- remains visible in lifecycle/resource diagnostics.

Do not fire independent settings writes into a multi-worker pool where revision N+1
can reach disk before revision N.

### Logging writer

Ordinary logging should enqueue bounded records to one process-owned writer that owns
formatting/rotation/file writes. The caller-side path must be small and non-blocking
under normal operation.

Keep fatal/native crash breadcrumbs separate: faulthandler/emergency crash records
must not depend on a healthy logging queue or writer thread. Preserve enough ordering
metadata that cross-sidecar diagnostic correlation remains trustworthy.

Route normal records by explicit structured family/category metadata where practical rather than permanently parsing display text. The current `[GL CACHE]` versus `[CACHE]` mismatch proves that human-readable message tokens are not a reliable routing contract. Main log keeps all WARNING+ and only high-level routine narrative; enabled-family INFO/DEBUG belongs in its sidecar.

### General COMPUTE workers

Use existing bounded executors for finite thread-safe work such as:

- image processing/scaling known to be worker-safe;
- approved Bubble authored jobs through the existing ordinary executor adapter;
- other finite native-heavy or CPU transforms with measured benefit.

Do not create a worker task per paint or per tiny sub-element. Do not assume more
threads equal more CPU throughput for pure Python work.

### Presentation timing service — candidate, not immediate visualizer work

Long-lived adaptive/presentation timing loops should not permanently consume generic
finite COMPUTE workers if measurement confirms meaningful occupancy/contention. A
future extraction may use a small dedicated presentation timing service that owns
sleep/deadline waiting only.

This service is **not** a visualizer clock, may not integrate Bubble/Spectrum state,
and may not alter transition deadlines or GUI/context ownership. It is lower priority
than removing proven GUI work and the texture identity defect.

### Process workers

Use multiprocessing only for already-justified isolated heavy work where IPC/copy/
commit cost is measured and bounded. The ImageWorker is not permission to move
latency-sensitive visualizer state into another process.

## Python/GIL rule

Normal SRPSS Python builds should be treated as GIL-governed unless explicitly proven
otherwise. Threads remain valuable for:

- blocking I/O that releases the GIL while waiting;
- native Qt/Pillow/NumPy/etc. work proven to release the GIL;
- strict serialization/ordering ownership;
- isolating a blocking service from GUI ownership.

Pure Python CPU loops do not become truly parallel merely because another thread is
created. Extra pure-Python worker threads can add context switching/GIL contention and
may make latency worse. Therefore "put it on a third thread" is not an architectural
goal; owner separation and measured native/GIL behaviour are required.

Free-threaded CPython is outside this roadmap. It would change extension/native
compatibility assumptions across PySide/Nuitka and is not a shortcut for current UI
ownership problems.

## Priority work

### Priority 0 — broad root-cause removals

1. **Async ordinary logging**
   - queue normal records;
   - dedicated bounded writer owns formatting/rotation/file writes;
   - preserve direct fatal/emergency path;
   - A/B UI/request-age tails with PERF/VIZ diagnostics enabled.

2. **Ordered async settings persistence**
   - keep in-memory setting mutation synchronous/authoritative;
   - move serialization/temp-write/replace to ordered writer;
   - add revision, flush and shutdown tests;
   - prove no stale write can win.

3. **Image/transition texture identity repair — implemented; installed A/B pending**
   - the stale presenter/display DPR split and exact `+2` cache-key divergence are removed;
   - focused automation verifies one old reuse + one new upload after terminal handoff;
   - exact context/share generation, transform boundaries and byte accounting remain unchanged;
   - remeasure `generic_pair_warm`, setter and request-age tails in identical installed sequences.

These three come before visualizer scheduler changes because they attack broad GUI
starvation without altering Bubble/Spectrum time semantics.

### Priority 1 — service/widget prepare/commit/persist

**Reddit**

Move raw result conversion, filtering, numeric parsing, dedupe/sort, sparse fallback
merge, cache load and cache save/touch work off the GUI result callback. Return one
prepared immutable result. GUI owns only visible model assignment, Qt metrics/layout,
fade/visibility and update.

**Weather**

Move startup persisted/provider cache reads and post-fetch JSON persistence to IO.
Worker preparation may normalize ordinary Python values and icon identity; QLabel,
QFontMetrics, QPixmap and layout mutation remain GUI-owned.

**Gmail**

Network fetch and deferred cache writes are already largely good. Move startup cache
read/deserialization off GUI. Move stable content-cache regeneration out of
`paintEvent()` first; only consider worker-rendered `QImage` content later if the
explicit invalidation-time GUI cache build remains material and parity can be proven.

**Reddit/Gmail paint-cache contract**

Invalidation may schedule/perform content preparation, but paint should not discover
that an expensive cold static layer must be regenerated before it can deliver the
frame. Keep dynamic spinner/hit-state regions narrow and separate from static cache.

### Priority 1 — visualizer reductions with cadence frozen

#### Bubble

Bubble is the most sensitive mode and is protected.

Do **not** change:

- authored-step offer/admission cadence;
- one-in-flight/lane-free semantics;
- ordinary general COMPUTE executor ownership;
- dt calculation;
- audio/transient/event snapshot timing;
- event consume-once semantics;
- source timestamp or activation/generation ownership;
- result publication ordering;
- simulation precision, batching or process/thread model.

Allowed Phase 5 work is restricted to demonstrably cadence-neutral overhead removal.
The strongest current candidate is caching configuration data that is immutable until
settings/preset changes, instead of rebuilding and copying the same large Bubble
settings payload on every authored dispatch. The per-step energy/transient/event
snapshot remains live and is captured at exactly the existing boundary.

Any Bubble optimization must pass the stronger temporal negative controls and user
visual review. A lower task count or smoother average CPU that alters response is a
failure.

#### Spectrum

Spectrum remains on the existing authoritative UI visualizer tick. Do not create a
new timer, worker clock, paint-owned smoothing path, source decimation or scheduler
gate. Phase 5 may remove only proven repeated immutable allocation/lookup work that
does not alter source consumption, smoothing state or publication timing.

#### DevCurve

The current tick explicitly performs its field solve on the GUI thread. This is a
candidate only after measurement. Use the existing `devcurve_dispatch_ms` phase to
establish p50/p95/p99/max under representative active load. Because the solver is
stateful and substantially pure Python, moving it to a thread is not automatically a
parallel speedup and introduces temporal handoff risk. Leave actual extraction to a
separately gated change—preferably Phase 7—unless evidence proves it is a material
Phase 5 GUI owner and replay/temporal tests prove identical evolution.

#### First visualizer strategy: remove external starvation

Before changing any visualizer owner, complete the broad GUI extractions, then repeat
the same Bubble/Spectrum transition scenario on the repaired texture-identity build. If tick
and source-age tails improve while the visualizer code is unchanged, that is the
preferred solution. A transition-start visualizer stall is not proof that its clock
belongs on another thread when the final Qt/GL presentation must still wait for the
same blocked GUI owner.

### Priority 2 — pool topology

After workload classes are separated:

- measure general COMPUTE worker occupancy, queue age and native/GIL release;
- move long-lived presentation waiting loops away from finite compute if justified;
- benchmark sensible COMPUTE width rather than assuming `cpu_count - 1` is optimal;
- avoid worker proliferation that merely increases GIL/scheduler/cache contention;
- keep IO/persistence/logging ownership distinct because their blocking/ordering
  properties differ.

## Multi-display load distribution

When the same heavy, non-latency-critical worker activity exists once per display,
phase it with a small deterministic offset derived from stable display identity so
all displays do not submit/complete together. This applies to maintenance, prefetch,
diagnostics or equivalent background work only. It must not delay user input,
authoritative first frame, visualizer ticks, transition completion, lifecycle barriers
or source ordering.

For GUI commits, use a different rule: after exact texture reuse is repaired, if two
prepared display-image commits still create large back-to-back GUI transactions,
consider one bounded commit per queued GUI turn. The purpose is to return control to
Qt between unavoidable context-affine transactions, not to delay the logical image or
transition schedule. Measure first-visible and cross-display skew before accepting it.

## Rejected threading strategies

Do not introduce:

- persistent visualizer shared-analysis/Bubble lanes;
- dedicated long-lived Bubble/Spectrum loops;
- a second visualizer presentation cadence;
- more Python threads as a GIL workaround without measured native release;
- one catch-all background thread for unrelated logging/persistence/service/compute;
- worker-to-paint acknowledgement;
- worker mutation of Qt/QPixmap/GL/compositor state;
- process recycling to reclaim memory;
- thread proliferation to hide tiny-job overhead;
- queueing that permits stale generation results to outlive retirement;
- async persistence without an explicit durability/ordering contract.

## Visualizer workload contract

Preserve:

- one shared source/analysis authority;
- timestamped source/event identity;
- ordinary general-executor Bubble submission/publication semantics;
- mode-owned logical state;
- immutable/current render-state handoff where already present;
- no per-display duplicate simulation where shared state is truly identical;
- no logical event loss before simulation;
- no paint feedback;
- no scheduler change used to compensate for unrelated GUI starvation.

Potential Phase 5 visualizer-adjacent optimization is limited to measured equivalent
removal of allocations, copies, diagnostics or duplicate immutable conversions until
stronger temporal goldens exist.

## Phase 7 interpretation — decoupling without inventing a clock

Phase 7 remains the correct home for more ambitious visualizer/presentation
decoupling. Its goal is **not** "move the visualizer to another thread." Its goal is
to narrow the boundary between authoritative state evolution and presentation while
preserving the authoritative mode clocks.

For Bubble, authored integration/event semantics remain the authority. For Spectrum,
source consumption and smoothing integration remain the authority. Presentation may
consume an immutable current render state without feeding back into those authorities,
but a missed or late paint may never delete logical events, alter dt, batch authored
steps or become a new simulation clock.

Phase 7 begins only after Phase 5 removes the proven external GUI-starvation owners
and stronger temporal goldens can detect one-frame latency, missed transients,
publication-order changes and first-visible regressions.

## Safe coalescing

May coalesce after logical integration:

- duplicate scene invalidations;
- replaceable immutable render snapshots;
- identical geometry/style publications;
- stale image/provider results;
- superseded pending settings persistence revisions where durability semantics permit;
- duplicate deletion requests under one owner;
- unchanged metadata/layout commits.

May not coalesce away:

- audio/transient events before simulation;
- Bubble authored steps/events;
- lifecycle stop/reload commands;
- resource release;
- topology/settings changes in memory;
- activation/generation boundaries;
- first authoritative frame;
- required persistence flush boundaries.

## Allocation and copy control

Investigate high-frequency:

- image/QImage/QPixmap copies and cache-key identity changes;
- bytes/memoryview/shared-memory conversions;
- list/dict/DTO rebuilds;
- Bubble immutable configuration payload reconstruction;
- string/log formatting;
- full-buffer hashing;
- Qt object creation;
- shader/uniform/geometry map rebuilds;
- per-display duplicate immutable state.

Reuse is allowed only with clear single ownership or immutable handoff. Do not share
mutable buffers across threads without an explicit synchronization/lifetime contract.

## Event-loop and delivery health

Measure separately:

- scheduled versus actual GUI callback time;
- longest callbacks;
- worker completion-to-GUI commit;
- accepted-state-to-update and update-to-paint;
- paint duration;
- scene/source age at paint;
- synchronous I/O/network/lock/logging activity;
- transition and lifecycle overlap;
- image commit substage cost;
- old/new texture cache hits and uploads;
- logging/persistence queue depth and flush duration after extraction.

Cheap drawing can still be late because the GUI thread is occupied.

## Profiling method

Use sampled whole-process profiling, task-category snapshots, targeted timers,
allocation/native-memory tools and bounded stall traces.

Compare identical authored scenarios and cache state. Do not use self-reported worker
duration alone; queueing, callback delivery and retained outputs may dominate.

For each threading extraction, record the **work removed from GUI**, not merely the new
worker duration. A change that moves 5 ms to a worker but adds 8 ms of serialization,
queueing and commit cost is not a win.

## Compatibility and fallback simplification

The threading architecture should also delete temporary alternate authorities that no longer preserve a real contract. `widgets/spotify_visualizer/bubble_compute_lane.py` explicitly describes itself as a temporary compatibility façade over the ordinary general COMPUTE executor. Remove it only as an exact-semantics direct-path refactor: preserve authored cadence, one-in-flight behavior, dt, live snapshots, task category, callback/publication ordering and generation identity.

After that removal, audit `core/threading/compute_lanes.py` and ThreadManager lane APIs. Current runtime telemetry repeatedly reports zero registered lanes/worker threads. Remove the persistent-lane subsystem only after production, dynamic-import, test and frozen-build proof. This is simplification, not an invitation to alter Bubble timing.

Apply the same proof rule to other documented dead compatibility surfaces (`rendering/render_strategy.py`, `widgets/dimming_overlay.py`, `sources/rss_source.py`, and `transitions/overlay_manager.py::_raise_halo_topmost`). Preserve genuine persisted-data/external migration compatibility. One concern per reversible checkpoint.

## GPU/presentation relationship

Active-display GPU busy in `08_09_ca830d7_14_59` measured median `10.8%`, p95 `27.8%`, max `32.9%`. Screen 1 is 60 Hz while visualizer overlay windows can approach ~100 state/update/paint operations per second. Phase 5 measures/attributes this without touching logical cadence. Phase 7 may later decouple physical presentation through latest immutable render state after logical integration.

## Acceptance gates

For each optimization:

- exact owner and removed work are identified;
- before/after GUI callback/request-age impact is measured;
- queue depth and worker contention remain bounded;
- lifecycle generation rejection and teardown remain deterministic;
- persistence ordering/durability remains correct where relevant;
- crash/emergency logging remains available where relevant;
- current visualizer goldens and known-bad negative controls remain correct;
- user visual review passes when shared presentation/source paths are touched;
- source-to-first-visible and p99/max improve or remain equivalent;
- CPU falls in the named scenario or GUI availability materially improves;
- task/callback/allocation reduction is measured rather than assumed;
- whole-app RSS/private commit/VRAM do not worsen materially;
- no new unbounded lane, scheduler, timer, queue, process, retry or synchronization
  authority is added;
- canonical-main behaviour remains correct and shared package routes pass bounded
  smoke coverage without a separate Media Center capture.

A candidate that merely shifts work, reduces task count or lowers average CPU while
harming feel, ordering, durability, lifecycle or memory is rejected.
