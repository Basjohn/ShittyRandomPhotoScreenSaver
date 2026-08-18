# Phase 5 — CPU / Task / GUI Availability Evidence

Status: **reconciled evidence record; not an alternate active plan**  
Last reconciled: 2026-08-18  
Execution owner: `Current_Plan.md`

This report preserves the useful CPU/workload findings from the pre-QRhi and migration work without
keeping obsolete Phase 7/8 sequencing alive.

---

## 1. Durable conclusions

The recurring performance problem has repeatedly been **late GUI delivery / broad GUI-owner work**,
not a visualizer shader taking tens of milliseconds.

Historical and current evidence repeatedly showed:
- request age much larger than paint duration;
- Bubble worker work commonly around 1–2 ms;
- drained general IO/COMPUTE queues during many bad delivery windows;
- process CPU often near one logical-core class even when GPU work was small;
- cold/recreation widget/cache work capable of consuming tens of milliseconds synchronously.

The correct target is **remove unnecessary work and narrow GUI-owned commits**, not reduce authored
visualizer cadence.

---

## 2. Accepted image/texture reuse correction

A major historical steady transition cost was traced to DPR identity drift between `DisplayWidget`
and `ImagePresenter`.

That mismatch prevented the terminally retained texture from becoming the next transition's old
texture and forced unnecessary old+new uploads.

The correction made the parent display DPR authoritative and eliminated no-op mutation.

Accepted result:
- retained terminal texture becomes next-old cache hit;
- steady transitions upload only the next new image;
- retained texture/PBO ownership remains bounded;
- strict reset returns owned GL bytes to zero.

Do not reopen this identity fix casually.

---

## 3. GUI preparation rule

Cold widget/content generation must not surprise `paintEvent()`.

Durable rule:

```text
Prepare -> Commit -> Paint
```

Prepare:
- detached data/QImage/plain-state work where thread-safe.

Commit:
- narrow GUI generation/staleness check;
- QPixmap/QWidget/GL mutation on the legal owner;
- cache revision publication.

Paint:
- consume prepared/cached state;
- no network, disk, JSON, broad model construction or cold static-cache build.

Current evidence still shows Reddit/frame-shadow/reconstruction preparation capable of consuming
large GUI turns. Remove duplicate preparation where source proves the revision is unchanged.

---

## 4. Visualizer CPU conclusions

Historical and current Bubble worker durations are small relative to visible 40–100 ms logical
holes.

Current accepted ordinary-executor semantics remain:
- one authored Bubble step admitted when lane-free;
- one in-flight;
- no backlog/catch-up;
- event/dt semantics preserved;
- generation fencing preserved.

The prior persistent Bubble scheduler/lane was rejected because it altered temporal behaviour.

Do not reactivate it.

If executor/Future churn later proves material, design a **new bounded mechanism** from the accepted
semantics rather than restoring the rejected lane.

---

## 5. Current visualizer cadence problem

The newest installed evidence shows visualizer rendering itself is inexpensive while the logical
QTimer can be serviced only ~65–70 Hz with repeated 40–80+ ms holes.

Therefore:
- do not tune shaders for this;
- do not lower Bubble complexity;
- do not reduce source/event cadence;
- do not increase the timer target to compensate for late service;
- do not move the current QWidget-touching tick wholesale to a worker.

First remove known GUI waste and redundant unchanged presentation.

If large ordinary-playback logical gaps survive, a Qt-free logical runtime/cadence owner becomes a
valid architecture target.

That future extraction must preserve all mode fidelity and publish immutable latest state to GUI.

---

## 6. Current physical-presentation waste

Single-surface high-refresh evidence can physically paint more often than authored visualizer state
changes.

Redrawing the same immutable visualizer scene is valid waste to remove.

This is different from throttling logical cadence:
- logical source/simulation remains unchanged;
- transition-active presentation remains display-rate eligible;
- visualizer-only unchanged scene may skip redundant GUI paint;
- fade/geometry/card/state revision remains presentable.

---

## 7. Thread/service ownership

### GUI/context owner
Keep:
- QWidget/QObject/QPixmap mutation;
- GL create/delete/render on borrowed current context;
- minimal current-generation result commit;
- geometry/visibility/input;
- final QImage->QPixmap promotion where needed.

Remove where source permits:
- synchronous file/network I/O;
- duplicate cache construction;
- repeated immutable layout/raster work;
- broad serialization/log formatting;
- unnecessary per-frame allocations.

### IO
Use bounded IO for blocking provider/file work, but runtime-owned work must cooperate with runtime
retirement.

The current Gmail CUSTOM failure proves that “off GUI” is not enough: a generation-owned blocking IO
task can still block destruction.

### COMPUTE
Use bounded compute for finite worker-safe work.

Do not:
- create a compute job per paint;
- use a worker-to-paint handshake;
- assume more threads improve pure-Python throughput;
- create unbounded queues.

### Process-scoped services
Process-scoped ownership is valid only when the work genuinely survives runtime generations and its
consumers are generation-fenced.

Do not relabel widget/runtime work as global merely to make lifecycle barriers pass.

---

## 8. Logging/settings accepted architecture

Settings persistence and logging already have process-scoped serialized writer ownership where order
and durability require it.

Retain:
- ordered/coalesced complete settings snapshots;
- explicit durability/flush boundaries;
- bounded logging queue/writer;
- fatal/native breadcrumbs independent from the routine logging writer.

Do not turn these back into GUI-thread disk work.

---

## 9. Evidence proportionality / refactor rule

The project has already spent excessive engineering time on probes that only restated known
structural problems.

Preferred order:

1. inspect exact source;
2. use existing passive evidence;
3. if one owner/mechanism is already distinguished, fix or replace it;
4. add a new probe only when it will choose between two plausible designs;
5. define the decision threshold before collecting the data.

Large structural replacement is acceptable when it **deletes** a bad owner boundary and can be
protected by fidelity/lifecycle tests. Small instrumentation is not inherently safer than a bounded
refactor.

---

## 10. Product efficiency target

Same-machine CPU/GPU usage remains the available proxy for weaker hardware.

A good optimization:
- removes redundant work/churn;
- lowers CPU/GUI pressure or leaves it flat while improving delivery;
- keeps GPU work low;
- preserves fidelity and reaction timing.

A bad optimization:
- caps refresh;
- lowers logical/source cadence;
- reduces transition/image quality;
- smooths over missed reactions;
- shifts cost into another queue/thread/memory pool.

Final post-migration acceptance must re-establish CPU, GPU, memory and task behaviour after the
current P2/P5 architecture settles.
