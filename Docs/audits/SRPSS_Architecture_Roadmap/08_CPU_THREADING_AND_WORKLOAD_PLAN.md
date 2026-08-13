# 08 — CPU, Threading, and Workload Plan

Last reconciled: 2026-08-13

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
That makes this a useful mixed-load robustness checkpoint, not a controlled
implementation comparison.
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
terminal pixmap remain explicit invalidation boundaries.

The current live typical-load run at
`logs/evidence_chest/08_11_51ff1e03_03_14_03_21_typical/` closes the runtime handoff
bar. All `20/20` retained steady transitions have exact retained/next-old key equality,
an old cache hit, one allocation and one upload. Every one of the 26 terminal records
retains one texture and one idle PBO. Against the historical causal reference, steady
`generic_pair_warm` median/p95 falls from `23.48/39.80 ms` to `13.64/20.98 ms`, and
setter median/p95 from `33.40/52.59 ms` to `25.66/34.72 ms`. Request-age and
visualizer-tick tails remain high, which isolates the remaining work to broader GUI
availability rather than texture identity.

### Cold widget rendering is still visible at rebuild time

The source run showed cached Reddit paints normally around `1–3 ms`, but cold or
recreation paints reached tens of milliseconds (`~40–61 ms` for the primary Reddit
widget, with smaller but still visible Reddit2 spikes). Gmail's stable regeneration
was smaller at roughly `~6–10 ms`. Both widget-owned static layers and the inherited
shared frame-shadow layer now prepare before paint.

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

The current typical-load `08_13_1be7f01a_15_38_15_46_typical` capture gives a stronger
downstream observation: on the recorded 60 Hz visualizer display, Bubble's 24 windows
reach `89.75` median state/update and `87.05` median `paintGL()` calls per second, while
Spectrum reaches `92.7` and `91.15`. No geometry churn accompanies those windows.
They are Qt FBO paint attempts rather than physical-present counts. The first passive
owner-context CPU/GPU timing slice is now installed to attribute their cost; logical
cadence, source capture, integration and publication remain frozen.

The corrected-query `08_13_fa7e8196_16_33_16_37_gpu_queries_typical` run shows the
overlay is not the duration source of the worst stalls: normal Bubble GPU p50/p95 is
roughly `0.35–0.46/0.43–0.53 ms`, Spectrum roughly `0.009–0.012/0.013 ms`, and CPU
paint medians remain near `0.9–1.25 ms` while request/delivery gaps still reach
`40–130 ms`. General COMPUTE and IO queues remain drained. Process CPU remains high at
roughly `94%` median, with Bubble logical work around `85–93/s` and audio work around
`64–68/s`, but that is not evidence to move or reduce Bubble cadence.

The subsequent shared-compositor run keeps the same CPU conclusion while narrowing GPU
ownership. Process CPU remains about `96.75%` median, COMPUTE/IO snapshots remain
drained, and frame gaps remain about `51.46/125.64 ms` median/max. Active transition GPU
draw is normally only `0.05–0.48 ms` p50 depending on display; the concrete avoidable
GUI/GL boundary is the terminal steady QPainter pixmap draw, not visualizer logical work.

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

Settings durability is a distinct workload because **order matters**. It is now owned
by one lazy process-scoped `SRPSSSettingsWriter`, deliberately outside runtime
`ThreadManager` generations. `SettingsManager` mutation is immediately authoritative
in memory and submits a complete revisioned snapshot to that writer. The contract is:

- one live `JsonSettingsStore` authority per normalized profile path;
- monotonic store revisions admitted under the store lock so an older snapshot cannot
  be submitted after a newer one;
- coalescing only for superseded, complete, same-owner pending snapshots; an in-flight
  snapshot is never replaced;
- JSON serialization, temp write, file flush/fsync and durable atomic replacement on
  the writer thread;
- explicit bounded durability acknowledgement at startup repair/migration completion,
  Settings close, reload boundaries and process shutdown;
- failed writes remain dirty and retryable rather than being reported as durable;
- queue depth/high-water, revision, coalescing, writer lag/write/flush/close duration,
  failure and timeout state in passive diagnostics and terminal logging.

Do not fire independent settings writes into a multi-worker pool where revision N+1
can reach disk before revision N. SST import/export remains explicit user transport;
it is not a competing routine settings writer.

### Logging writer

Ordinary logging now snapshots/enqueues bounded records to one process-owned
`SRPSSLogWriter` that owns filtering/formatting/deduplication/rotation/file writes. The
caller-side path is normally non-blocking; only a saturated WARNING+ uses the
serialized direct-main emergency path. The final queue record exposes caller cost,
high-water, drops, writer lag, emergency/reentry fallbacks, writer errors and bounded
flush duration. The writer is process-scoped and deliberately outside runtime
`ThreadManager` generations.

Keep fatal/native crash breadcrumbs separate: faulthandler/emergency crash records
must not depend on a healthy logging queue or writer thread. Preserve enough ordering
metadata that cross-sidecar diagnostic correlation remains trustworthy.

Records may now declare the immutable `srpss_log_families` tuple. Valid explicit
metadata is authoritative, supports intentional multi-family delivery such as
`perf + cache`, and survives queued detachment. Unclassified or unknown third-party
records retain the established name/tag fallback. The real GL program-cache producer
is explicitly `cache`-owned, closing the `[GL CACHE]` versus `[CACHE]` token accident
without changing its human-readable text. Main log keeps all WARNING+ and only
high-level routine narrative; enabled-family INFO/DEBUG belongs in its sidecar.
Migrate other high-volume families systematically during the late taxonomy pass.

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

The `08_13_ab429163_16_08_16_18_typical_teardown_churn` capture observes exactly two
per-display `presentation.adaptive_timer` tasks continuously active, with drained IO and
COMPUTE queues, COMPUTE queue wait about `1/2/3.02 ms` median/p95/max, and observed
execution about `2.51/4.89/9.3 ms`. This proves long-lived waiter ownership but does not
prove contention. Keep the current service in place unless later runtime evidence shows
finite work delayed behind it; do not create a new pool merely to lower active-task
counts.

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
   - implemented with a bounded process-owned writer and producer-facing ingress;
   - normal filtering/formatting/deduplication/rotation/file writes are writer-owned;
   - immutable multi-family metadata is authoritative when declared, while legacy and third-party records retain compatible name/tag fallback;
   - direct fatal capture remains independent and saturated WARNING+ remains main-visible;
   - focused gates cover bounded close, shutdown handoff, reentry, drops/lag/high-water/flush telemetry and sidecar routing;
   - repeat the same typical scenario and compare UI/request-age tails with PERF/VIZ diagnostics enabled.

2. **Ordered async settings persistence — complete**
   - in-memory mutation, peer-manager cache invalidation and notifications are synchronous;
   - one process writer owns serialization/temp-write/fsync/durable replace for every profile;
   - one shared store authority per path plus lock-ordered revisions prevents stale-write wins;
   - explicit startup, Settings-close, reload and process-close durability boundaries are bounded and observable;
   - focused tests cover asynchronous caller return, coalescing, failure/retry, flush timeout,
     two-thread revision races, same-path peer managers/cache invalidation, reload races,
     multi-profile ordering, shutdown rejection and writer-thread ownership.

3. **Image/transition texture identity repair — complete**
   - the stale presenter/display DPR split and exact `+2` cache-key divergence are removed;
   - focused automation verifies one old reuse + one new upload after terminal handoff;
   - exact context/share generation, transform boundaries and byte accounting remain unchanged;
   - current live evidence verifies `20/20` steady old hits, one new upload and bounded terminal resources;
   - request-age/tick tails remain workload-extraction targets, not identity-validation debt.

These three come before visualizer scheduler changes because they attack broad GUI
starvation without altering Bubble/Spectrum time semantics.

### Priority 1 — service/widget prepare/commit/persist

**Reddit fetch-result preparation — complete**

Normal fetches now capture detached inputs and use the shared IO task for provider work,
raw result conversion, filtering, numeric parsing, dedupe/sort, sparse fallback merge
and post-cache JSON persistence. The worker publishes one frozen
`PreparedRedditFeed`; transition deferral retains that object and the GUI commit owns
only visible model assignment, Qt metrics/layout, fade/visibility and update. Same-path
cache transactions are process-serialized and replace the JSON file atomically. The
former missing-worker synchronous network fallback is removed.

Startup control-plane extraction is also complete. Activation loads the post cache and
persisted blocked gate as one immutable `RedditStartupSnapshot` on shared IO, commits
cached content first, then evaluates freshness/cooldown from that snapshot. Runtime
cadence checks read a process-shared in-memory timestamp registry updated by worker
cache writes and gate touches, so they do not `stat`, create or touch files on GUI.
Late snapshots are rejected after deactivation or receipt of any newer authoritative
live result. The unused legacy startup-attempt marker had no production caller and was
removed rather than promoted into a persistence contract.

**Weather prepare/commit/persist — complete**

Weather construction and lifecycle initialization are now filesystem-inert. Activation
submits one shared-IO startup task which performs legacy migration, widget-cache JSON
read/validation and provider-cache fallback selection, then publishes one frozen
`PreparedWeatherStartup`. The GUI accepts it only for the current request, lifecycle
generation and normalized location before assigning visible state, measuring text,
loading QPixmaps, updating layout and joining the coordinated fade.

Provider/network work remains on shared IO and now returns a frozen
`PreparedWeatherSample`. Worker callbacks retain only a weak widget reference; current
request/location tokens reject out-of-order results after a newer request, location
change, deactivation or cleanup. An accepted GUI commit queues detached JSON
persistence back to shared IO. Only an accepted fresh network sample is merged into
the shared provider fallback, so a rejected/out-of-order fetch cannot become durable;
the locked atomic merge preserves other cached cities. Widget-cache persistence uses
the same atomic/newest-wins rule, and legacy migration participates in that path lock
rather than racing a current write.
Neither startup nor ordinary refresh has a synchronous network/filesystem fallback,
and the exported legacy fetch helper now defers provider construction/cache loading to
its worker-owned `fetch()` call.

**Gmail startup cache prepare/commit/persist — complete**

Activation now submits one shared-IO startup task which performs the cache stat/read,
freshness classification and metadata-only JSON reconstruction, then publishes one
frozen `PreparedGmailStartup`. The GUI accepts it only for the current startup request
and unchanged content revision before rebuilding rows, measuring card geometry and
joining the coordinated fade. A newer accepted live fetch, deactivation or cleanup
invalidates the snapshot. The startup refresh decision consumes the prepared timestamp,
so activation no longer repeats filesystem inspection on GUI.

Accepted cache writes remain ordered after GUI commit and now use a per-path reserved
newest-wins identity plus locked unique-temp atomic replacement on shared IO. A late
older task cannot overwrite newer accepted mail. Missing-worker or rejected-dispatch
paths skip durability/service work instead of reading, writing or fetching synchronously on GUI.
Malformed cache roots fail open to the ordinary background refresh path while valid
metadata rows preserve stored order and invalid individual rows remain filtered.

**Gmail backend bootstrap preparation — complete**

`GmailBackend` and `GmailOAuthManager` remain GUI-affine singleton QObjects, but their
constructors are now filesystem-inert. The first widget/settings consumer joins one
process-coalesced shared-IO bootstrap which resolves/creates storage, reads and parses
backend/OAuth configuration, DPAPI-decrypts IMAP and OAuth credentials, and performs
legacy OAuth migration with atomic encrypted replacement. It publishes a frozen,
non-repr secret-bearing snapshot; the GUI commit installs the existing backend/OAuth
authority and creates only memory-local clients.

Widget activation may load visible mail cache independently, but live fetch waits for
backend readiness. Widget callbacks are weak/lifecycle-request gated, multiple displays
and Settings share the single in-flight preparation, and Settings keeps backend actions
disabled while loading. Missing-worker/dispatch failure does not fall back to GUI disk
or DPAPI work. User-triggered config/credential mutations and token refresh/revoke are
separate callback/persistence audit items, not part of this closed construction slice.

**Gmail static paint-cache preparation — complete**

The stable Gmail layer remains a GUI-owned `QPixmap`, but content/data commits now
prepare it immediately before reveal and ordinary visual invalidations coalesce into one
managed zero-delay GUI preparation. The exact cache identity is logical size, DPR and
static revision. Resize/screen-DPR events and every cached visual input—including the
previously missed text colour, font family, header border/corner and shadow settings—
invalidate through that owner.

`paintEvent()` no longer allocates the Gmail static pixmap or performs header/row font,
layout, elision, shadow or hit-geometry work. It accepts only an exact-current prepared
cache and then paints the narrow dynamic refresh spinner separately. During a queued
invalidation window neither stale pixels nor mismatched hit targets are exposed. Worker
rendering remains unnecessary; consider detached `QImage` preparation only if installed
measurement proves this bounded GUI commit remains material and visual/interaction
parity can be preserved.

**Reddit static paint-cache preparation — complete**

Reddit data commits now prepare its GUI-owned static `QPixmap` after content geometry
settles and before first reveal. Ordinary visual, resize and screen-DPR invalidations
coalesce into one GUI callback with an exact logical-size/DPR/static-revision identity.
Paint only accepts that exact-current snapshot, blits it, then paints the refresh spiral
as a narrow dynamic region. Static pixels, row/header hit geometry and the header's
subreddit routing identity are committed and withheld together, so a queued invalidation
or pending subreddit fetch cannot expose mismatched pixels and click targets.

If an invalidation lands while image transition work is pending/running, Reddit retains
the invalid state but performs no static rebuild. The existing terminal transition
notification schedules exactly one deferred preparation after the compositor becomes
idle; there is no retry timer or additional cadence. Relative-age labels retain their
established snapshot policy and change only when data/style/size invalidates the cache.
Worker text rendering remains unjustified without new installed evidence and parity bars.

**Shared overlay frame-shadow preparation — complete**

`BaseOverlayWidget` now owns an exact logical-size/DPR/style/revision identity for its
GUI-owned painted-frame `QPixmap`. Visible style and geometry commits synchronously
publish the exact replacement before requesting paint; hidden construction accumulates
invalidations and prewarms once at show. Known multi-setting application paths and Clock
mode changes use an explicit GUI commit batch, so they publish only the final identity
without relying on timer ordering. Resize, screen/DPR changes and fade completion obey
the same boundary.

Base paint now performs lookup/validation and blit only; a stale or absent identity is
never rebuilt or drawn from paint. Worker preparation is rejected and cleanup clears
pending/cache ownership. Clock Analogue and Imgur explicitly opt out because their
custom painters own different shapes; Clock Digital, Gmail, Reddit, Weather, Media and
Steam retain the shared rectangular frame path. Specialized Spotify volume/visualizer
shadows remain separate owners and were not silently folded into this contract.

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

The `08_13_2cb15ae4_17_17_17_20_retained_base_typical` run makes that distinction
concrete. Parser 1.15 classifies visualizer tick spikes by transition boundary: sampled
transition-start spikes are `53.06/72.25/73.99 ms` min/median/max and transition-end
spikes `75.36/78.24/93.23 ms`, while Bubble worker work stays about `1.4–1.5 ms` and
overlay GPU p50/p95 about `0.36/0.43 ms`. Image installation immediately around the
boundary remains a GUI/context transaction, normally `18–33 ms` and occasionally much
larger during cold/recreation work. Continue attribution at that GUI/GL boundary; do not
reinterpret Phase 7 as a way to run Qt presentation through a blocked GUI thread.

The follow-up parser-1.15 capture
`08_13_e40eee8b_17_42_17_47_upload_phases_typical` closes the first upload-attribution
gate. Across `30` PBO uploads, image preparation plus source-bit copying consumes
`283.391/434.594 ms` (`65.2%`) of measured upload CPU time. Ordinary physical-4K medians
are `6.260 ms` image preparation, `5.429 ms` bits copy and only `0.482 ms` texture
submission. Initial PBO staging spikes (`15.061/27.162 ms`) and roughly `206.449 ms` of
cold pair-warm residual are distinct follow-ups rather than evidence for moving GL.

The narrow copy-control slice keeps QPixmap and GL on their current owner. Native Qt
`RGB32/ARGB32` storage already matches the BGRA upload contract, so it bypasses the old
full-frame ARGB32 conversion; a Shiboken address for the read-only `constBits()` view
then feeds the existing mapped-PBO copy without creating a Python `bytes` clone. Other
formats still convert explicitly. Parser 1.16 distinguishes native/converted formats and
direct/copy-fallback buffer paths; a real-context texture readback verifies exact RGB and
alpha bytes. Installed timing and teardown validation remains open.

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

The corrected-query typical run now proves owner-local GPU collection: all `26` overlay
windows are supported, collect samples, have no query errors/drops and retain only the
bounded pending ring state. Bubble's normal GPU span is sub-millisecond and Spectrum's
is negligible; similar CPU-side QOpenGLWidget paint cost remains measurable in both.
Logical cadence remains unchanged. Process GPU-busy peaks align more strongly with
Crumble/Particle/Burn windows, so shared-compositor transition attribution is the next
runtime gate.

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
