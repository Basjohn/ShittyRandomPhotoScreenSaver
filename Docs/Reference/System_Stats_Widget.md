# System Stats Widget — Current Product Contract

Status: **CPU/MEMORY/UPTIME/NETWORK IMPLEMENTED / PUBLIC — CURRENT ARCHITECTURE REFERENCE**
Last updated: 2026-09-16
Current sequencing authority: `Current_Plan.md`
Stable widget/family id: `system_stats`

## 0. Decision

The old blanket “no system usage widget” position is retired.

A small System Stats card is acceptable **only if its own measurement cost is beneath meaningful product noise and it
remains completely dormant without an admitted card consumer**. The existing `--usage` telemetry is useful evidence and
must remain diagnostics-only; it is intentionally much broader than this product needs.

The admitted source set is intentionally small: CPU/RAM cleared the source-cost gate, while the persistent GPU/VRAM candidate did not. System uptime and aggregate network receive/transmit counters ride the **same** sampler pulse; no second cadence or hardware/provider layer exists.

### 0.1 Landed implementation state

Whole-system CPU/RAM source observations measured roughly 0.5–1.5 ms across idle and bounded CPU-contention runs. The persistent Windows GPU/VRAM candidate returned `query_error`, took about 363 ms on first setup, closed all query/counter state and is **not** in the product. No diagnostic or PID-scoped fallback was added.

System Stats is implemented as a normal product family. The family is activated by default so Setup and its pill are visible;
the member remains disabled by default. One
runtime-generation owner submits a low-priority sample only while at least one real retained-card lease is active;
additional displays share its immutable snapshot. The cadence is fixed-delay from completion with a canonical 10-second minimum/default (user-adjustable slower); one sample may be in
flight, and final release fences completion and closes/clears source ownership. Settings construction stays source-inert.

The retained card can show CPU load, RAM percentage plus used/total, system uptime and aggregate Network ↓/↑ throughput.
Each metric has a canonical default-on presentation/monitoring checkbox. Disabled metrics are skipped inside the **same
single sampler pulse** rather than spawning alternate samplers or merely hiding work. Enabled metric panels reflow through
the shared horizontal/vertical `content_extent`: extra width opens text/value lanes, extra height distributes panel
spacing, and direct-axis CUSTOM changes remain presentation state rather than Settings geometry. The metric-panel outline
uses the scale-aware 1.25 px baseline so it visually joins the authored 5 px accent block without changing that accent.

The card uses semantic Widget Theme roles, ordinary stacking/global-CUSTOM normalization and an original packaged
monochrome gear/spanner header asset. The Widgets-page family pill sizes to its actual label instead of clipping `System
Stats`. The temporary `--devstats` feature gate and parser token are retired, with one-time profile compatibility admission for the formerly
hidden family without enabling its member. Installed
soak/visual debt lives only in `Current_Plan.md`.

## 1. Product goal

Provide a quiet glanceable card for the user-selected subset of exactly these admitted public metrics:

- whole-system CPU usage;
- whole-system RAM usage;
- system uptime;
- aggregate network receive/transmit throughput.

GPU/VRAM and other hardware telemetry are not pending System Stats work. The preserved S0 GPU/VRAM probe is historical
evidence for why the product stops at the four metrics above unless the operator explicitly opens a new scope later.

This is not Task Manager and not SRPSS diagnostics.

The card should help a user answer “is the machine busy?” without becoming part of the load being measured.

## 2. Explicit non-goals

Version 1 must not collect or display:

- SRPSS process RSS/USS/private memory;
- process tree / child enumeration;
- process/thread/handle counts;
- per-process CPU/GPU tables;
- per-process or disk IO enumeration/counters;
- temperatures/fan sensors;
- per-core graphs;
- historical database/long-lived charts;
- top-process lists;
- diagnostic log parsing;
- `--usage` heavy topology refresh;
- continuous frame-rate sampling;
- arbitrary user-configurable 100 ms / 1 s monitoring cadence.

Do not turn product Settings into a telemetry-profiler surface.

## 3. Architectural principle — event-owned lifetime, sparse sampled values

Activation/dormancy should be event-owned. Usage percentages themselves are rate measurements and require observations
over time, so a tiny bounded periodic sample while a consumer exists is acceptable and more truthful than pretending
CPU/network utilization can be fully event-driven.

Design target:

```text
card admission / retirement events
        -> acquire/release one runtime-generation-shared sampler lease
        -> while lease_count > 0, sample cheap OS-maintained counters every ~10 s
        -> immutable accepted snapshot
        -> all retained cards consume same snapshot
```

No QML polling timer. No timer per monitor. No sampler when lease count is zero.

### Cadence

- **10 seconds is the canonical minimum/default interval.** Settings may make the shared sampler slower, up to one hour.
- Faster-than-10-second product sampling is forbidden; the UI enforces the same minimum.
- There is still exactly one fixed-delay owner. Changing the interval alters only its next completion-relative one-shot;
  Uptime and Network never create their own timers.
- One collection may be in flight. If a cadence edge arrives while it is still running, skip it; never queue telemetry
  samples.
- Sampling phase does not need wall-clock exactness. Low priority and bounded drift are preferable to competing with
  visual presentation.

## 4. Admitted source set

### 4.1 CPU — admitted

Prefer a whole-system OS cumulative-counter source where one cheap read gives total/idle/kernel/user time. Compute usage
from the delta between the previous accepted sample and the current sample.

Requirements:

- no process enumeration;
- no per-core enumeration unless a later feature explicitly justifies it;
- first sample is “warming / unavailable” rather than inventing a percentage;
- negative/reset/wrap anomalies reject that sample rather than displaying nonsense.

An existing cheap library helper may be used only if measurement proves it does not invoke the expensive process-tree
paths used by `--usage`.

### 4.2 RAM — admitted

Read one whole-system memory-status snapshot on the same sampling pulse:

- used/total or used percentage;
- no USS/private/process memory;
- no extra cadence.

### 4.3 Uptime — admitted

Capture boot time once when the admitted source is constructed and derive elapsed system uptime on the existing sample
pulse. No polling source, history or per-frame clock is required.

### 4.4 Network throughput — admitted

Read one aggregate OS network byte-counter snapshot on the existing pulse. The first observation warms a private baseline;
subsequent receive/transmit rates are deltas divided by actual monotonic elapsed time. This performs no network request,
per-process enumeration or adapter rediscovery and owns no second cadence.

### 4.5 GPU/VRAM — rejected candidate

The S0 Windows PDH candidate was too costly/fragile for this product and remains rejected. There is no pending GPU/VRAM
implementation phase, fallback provider or hardware-driver work in System Stats. Reconsideration requires an explicit new
operator request rather than this document acting as a dormant invitation.

## 5. Sampler owner

One small product sampler owner coordinates the admitted source set.

Recommended ownership:

```text
SystemStatsSamplerService  (one per RUN/runtime generation)
    lease_count
    generation
    current immutable snapshot
    cheap source handles/counter query
    one low-priority scheduled worker pulse while lease_count > 0
```

Do not create one sampler per display/card.

### Lease rules

- first admitted card lease starts/warms the sampler;
- additional displays reuse the same accepted snapshot;
- last lease release cancels future cadence and closes/clears the admitted System Stats source state;
- in-flight completion carries generation and is discarded after last-release/recreation;
- family deactivation forces lease release;
- ordinary card disable forces that card’s lease release;
- Settings being open does not acquire a lease;
- catalogue/descriptor import does not construct the sampler.

A future second system-stat card may justify shared infrastructure then. Do not prebuild a generic monitoring framework
now.

## 6. Dormancy contract

Implemented admission:

```text
widgets.family_activation.system_stats
AND widgets.system_stats.enabled
AND at least one admitted presentation consumer
```

Because this is presently one widget, do not invent a broad speculative `system` family with unused members merely for
future symmetry. A same-name singleton family is acceptable if that best fits current family-activation machinery.

With zero effective consumers:

- no recurring sample;
- no worker reservation;
- no open PDH/performance query;
- no retained history/baseline beyond what is needed to safely shut down;
- no QML animation/callback keeping the card alive;
- no diagnostic `--usage` service activation.

Dormancy must be tested by counters/owner cardinality, not inferred because the card is invisible.

## 7. Threading / scheduling

Sampling must not run on the GUI thread or Visualizer logical-cadence thread.

Use the existing managed worker infrastructure at low priority if it can schedule a sparse one-shot without creating a
new permanent worker/thread. The owner schedules the next sample only while it still has a lease.

Prefer:

- OS calls with bounded constant work;
- no Python loop over processes/threads/adapters each pulse;
- persistent counter handles only when they materially avoid rediscovery cost;
- close/recreate handles cleanly on runtime generation change or source failure;
- skipped sample over queue growth.

Do not add a second general scheduler framework for this card.

## 8. Accepted snapshot

The landed cross-thread payload is tiny and immutable:

```text
SystemStatsRuntimeSnapshot
    revision
    accepted_monotonic
    CpuRamSample  # historical class name retained for compatibility
        cpu_status / cpu_pct | None
        ram_status / ram_used_bytes / ram_total_bytes | None
        uptime_status / uptime_seconds | None
        network_status / network_rx_bps / network_tx_bps | None
```

Formatting (GB strings, whole-number percentages, labels) belongs in neutral preparation/presentation, not the source
collector.

Unchanged values may still advance accepted age/revision if needed for freshness, but presentation should not rebuild
its tree just because another 10-second sample arrived.

## 9. Product UI

The card is deliberately quiet and readable, with four fixed metric panels:

```text
SYSTEM STATS
CPU LOAD                         63%
Across all logical processors
MEMORY                           71%
22.7 GB of 32.0 GB used
UPTIME                           3d 14h
Since system boot
NETWORK                          ↓ 6.20 MB/s
                                 ↑ 340 KB/s
```

No cadence/rejection/architecture commentary belongs on the user-facing card.

Exact labels/layout are eyes-on work, but principles are binding:

- no scrolling graphs/history in v1;
- no twitchy decimal percentages; integer display is enough unless evidence says otherwise;
- small presentation easing between accepted samples is optional, finite and purely visual;
- displayed value changes do not change preferred geometry;
- canonical metric-selection checkboxes decide which underlying observations are sampled and which panels are rendered;
  they do not create a second sampler/cadence;
- authored geometry remains stable, while shared CUSTOM `content_extent` may redistribute enabled panels horizontally or
  vertically without mutating those settings;
- rejected GPU/VRAM is omitted; the admitted metrics do not collapse into a different card architecture when one value is warming
  or unavailable.

## 10. Icon contract

System Stats uses the landed **project-owned monochrome gear + spanner icon** through the normal resource/build/package path. Tint/opacity follows existing header/icon semantics. Do not replace it with a fetched web icon, icon-font dependency or family-local loader.

The icon is decorative identity only; it owns no animation cadence or accelerated surface.

## 11. Retained Quick / ordinary normalization

System Stats uses the same ordinary retained-card rules as the mature widgets:

- one retained Quick component inside the existing engine/window;
- stable item identity;
- descriptor uses the shared ordinary uniform outer-resize contract plus horizontal/vertical `content_extent` axes;
- side extent reflows enabled metric panels only; corners/wheel remain uniform and shared Restore Size clears extent back
  to authored geometry without changing X/Y/display;
- shared whole-card normalization/40% floor outside family side-drag policy;
- global CUSTOM disables authored stacking/adjacency globally;
- non-CUSTOM shared stacking/auto-fit;
- shared Widget Theme/Style Overrides/card border/header/glow semantics;
- shared edit-mode ownership;
- no family-specific layout manager or theme cascade.

CUSTOM child editing follows the same descriptor/session/persistence owner as the other retained widgets. System Stats
does **not** persist geometry per CPU/RAM/Uptime/Network panel. Its stable role set is:

```text
header
header_separator
metric_panels
metric_accents
metric_labels
metric_details
metric_values
metric_tracks
```

`header` and `header_separator` are singleton chrome. Every `metric_*` role is one shared geometry record projected onto
all structurally equivalent enabled panels. The panel container and its nested semantic roles may overlap by design, so
that containment pair is excluded only from selected-Edit hard peer collision; unrelated roles still use the global
Child Collision preference. The header separator keeps its truthful painted line for collision while exposing a larger
Edit hit proxy. Child geometry lives only in the ordinary CUSTOM `size_payload.child_geometry` carrier and Restore Size
returns it to the authored identity without mutating metric-selection Settings.

The sampling edge remains separate from editing: accepted runtime samples emit `sampleChanged`, while CUSTOM geometry
publishes only `customGeometryChanged`. Dragging/resizing child roles must not start/stop/wake the sampler, and a 10-second
sample must not rebuild or republish child geometry.

Do not create a custom-GL card merely because the data resembles a performance HUD. QML rectangles/text/bars are
sufficient.

## 12. Settings contract

Canonical Settings/default state is landed and limited to:

- family activation entry;
- Enabled;
- Position / Monitor;
- ordinary font family/size controls consistent with other families;
- default-on CPU, Memory, Uptime and Network metric checkboxes;
- one user-facing Update Interval in seconds, canonical default/minimum 10 and maximum one hour.

Do not expose worker priority, counter backend, diagnostic process fields, history length or rejected hardware-provider
strategy. The interval control changes the one existing shared fixed-delay owner; it does not create another timer.

Defaults live only in `core/settings/default_settings.py`; derived snapshot/SST outputs must be regenerated/audit-gated.
Any new bucket ids participate in canonical UI-state schema with closed-by-default, one-open local scope.

## 13. Failure / fallback policy

If GPU/VRAM is expensive or ambiguous:

- omit GPU/VRAM;
- keep CPU/RAM if they independently pass.

If CPU/RAM itself cannot meet the burden bar:

- shelve System Stats.

Do **not** respond by:

- sampling on the UI thread;
- hiding expensive calls behind 30–60 second pauses and calling them free;
- reducing Visualizer cadence/reactivity;
- inventing a durable stale-cache layer for sampled values instead of retaining the last accepted in-memory snapshot honestly;
- using `--usage` diagnostics as a silent fallback;
- leaving a warm sampler resident while the card is disabled.

## 14. Acceptance summary

Current implementation contract (installed validation status lives in `Current_Plan.md`):

- one shared sampler feeds every card instance;
- 10-second minimum/default cadence remains sufficient; slower user-selected intervals are allowed;
- no consumer means literally no recurring product telemetry work;
- CPU/RAM sources avoid process/thread enumeration;
- rejected GPU/VRAM hardware telemetry remains absent;
- no diagnostic `--usage` service or heavy collector is reused;
- ordinary widget normalization/theme/CUSTOM contracts are inherited;
- the header has a canonical themed glyph or project-owned gear+spanner asset without a new icon subsystem;
- contention A/B shows no meaningful Visualizer freshness/reactivity/presentation-tail regression;
- the widget remains observably cheaper than the diagnostic system it was inspired by.
