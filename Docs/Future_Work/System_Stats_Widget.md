# System Stats Widget — Low-Burden Product Decomposition

Status: **CPU/RAM IMPLEMENTED / DEV-GATED / AWAITING S7 SOAK**
Last updated: 2026-09-13
Current sequencing authority: `Current_Plan.md`
Stable widget/family id: `system_stats`

## 0. Decision

The old blanket “no system usage widget” position is retired.

A small System Stats card is acceptable **only if its own measurement cost is beneath meaningful product noise and it
remains completely dormant without an admitted card consumer**. The existing `--usage` telemetry is useful evidence and
must remain diagnostics-only; it is intentionally much broader than this product needs.

This decomposition began with a sampler admission experiment. CPU/RAM cleared the source-cost gate; optional GPU/VRAM
did not. Later metrics remain shelved rather than weakening Visualizer cadence/reactivity or disguising expensive
collection behind a slower UI.

### 0.1 Landed implementation state

S0 admitted only whole-system CPU/RAM: direct source observations measured roughly 0.5–1.5 ms across idle and bounded
CPU-contention runs. The persistent Windows GPU/VRAM candidate returned `query_error`, took about 363 ms on first setup,
closed all query/counter state and is **not** in the product. No diagnostic or PID-scoped fallback was added.

S1-S6 are implemented behind `--devstats` and the family remains deactivated/member-disabled by default. One
runtime-generation owner submits a low-priority sample only while at least one real retained-card lease is active;
additional displays share its immutable snapshot. The cadence is a fixed completion+10 seconds, one sample may be in
flight, and final release fences completion and closes/clears source ownership. Settings construction stays source-inert.

The retained card shows CPU load and RAM percentage plus used/total in two fixed panels. It uses semantic Widget Theme
roles, ordinary stacking/global-CUSTOM/40% normalization, finite width easing and an original packaged monochrome gear
and spanner header asset. Focused automated source/runtime/dormancy/multi-display/Settings/QML/binder/build checks and
real Quick standard/busy/40%-floor captures are GREEN. S7 remains open for installed off-vs-on Visualizer contention,
long-run, repeated retirement/recreation and two-display resource/cardinality validation; `--devstats` remains until then.

## 1. Product goal

Provide a quiet glanceable card for:

- whole-system CPU usage;
- whole-system RAM usage;
- optional system/adapter GPU usage **only if an honest low-cost aggregate can be proven**;
- optional VRAM used/total **only if an honest low-cost adapter/system value can be proven**.

This is not Task Manager and not SRPSS diagnostics.

The card should help a user answer “is the machine busy?” without becoming part of the load being measured.

## 2. Explicit non-goals

Version 1 must not collect or display:

- SRPSS process RSS/USS/private memory;
- process tree / child enumeration;
- process/thread/handle counts;
- per-process CPU/GPU tables;
- IO counters;
- temperatures/fan sensors;
- per-core graphs;
- historical database/long-lived charts;
- top-process lists;
- diagnostic log parsing;
- `--usage` heavy topology refresh;
- continuous frame-rate sampling;
- arbitrary user-configurable 100 ms / 1 s monitoring cadence.

Do not turn product Settings into a telemetry-profiler surface.

## 3. Evidence from the preserved diagnostic run

Durable evidence: `logs/evidence_chest/logsb11575b976.zip`.

The 2026-09-12 `--usage` run demonstrates two things:

1. low-frequency off-thread diagnostics can coexist with the application;
2. `UsageTelemetryService` / `ProcessUsageCollector` is far too broad to reuse as a 5–10 second live product sampler.

Observed audit summary from that run:

- ordinary/light collections roughly ~24.5 ms median / ~33.9 ms p95;
- heavy samples roughly ~67 ms median / ~107 ms p95;
- at least one contention outlier above one second;
- the diagnostic collector intentionally reads process memory/USS/handles/IO and periodically performs GIL-held
  process/thread topology work that the product card does not need.

Therefore **do not instantiate, wrap, subclass or silently enable `UsageTelemetryService` for System Stats**.

## 4. Architectural principle — event-owned lifetime, sparse sampled values

Activation/dormancy should be event-owned. Usage percentages themselves are rate measurements and require observations
over time, so a tiny bounded periodic sample while a consumer exists is acceptable and more truthful than pretending
CPU/GPU utilization can be fully event-driven.

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

- **Start at 10 seconds fixed cadence.**
- 5 seconds is the only planned faster candidate if eyes-on validation proves 10 s feels unacceptably stale and A/B
  performance still shows no meaningful burden.
- Do not expose a cadence knob initially. A user-facing slider invites pathological high-frequency monitoring and adds
  product complexity without clear value.
- One collection may be in flight. If a cadence edge arrives while it is still running, skip it; never queue telemetry
  samples.
- Sampling phase does not need wall-clock exactness. Low priority and bounded drift are preferable to competing with
  visual presentation.

## 5. Cheap source candidates

### 5.1 CPU — preferred

Prefer a whole-system OS cumulative-counter source where one cheap read gives total/idle/kernel/user time. Compute usage
from the delta between the previous accepted sample and the current sample.

Requirements:

- no process enumeration;
- no per-core enumeration unless a later feature explicitly justifies it;
- first sample is “warming / unavailable” rather than inventing a percentage;
- negative/reset/wrap anomalies reject that sample rather than displaying nonsense.

An existing cheap library helper may be used only if measurement proves it does not invoke the expensive process-tree
paths used by `--usage`.

### 5.2 RAM — preferred

Read one whole-system memory-status snapshot on the same sampling pulse:

- used/total or used percentage;
- no USS/private/process memory;
- no extra cadence.

### 5.3 GPU utilization — optional admission

GPU is not allowed to make the whole widget expensive or semantically dishonest.

Probe the current Windows counter infrastructure / PDH adapter-engine facilities and determine whether SRPSS can obtain
a stable, understandable system/adapter utilization value without:

- process enumeration;
- rebuilding wildcard counter sets every sample;
- summing unrelated engines into impossible >100% values;
- silently picking an arbitrary adapter on multi-GPU systems;
- long synchronous query refresh on the GUI or Visualizer logical thread.

If the only easy number is ambiguous, omit GPU utilization from v1 and ship honest CPU/RAM first.

### 5.4 VRAM — optional admission

If an adapter-level dedicated-memory used/total figure can be read cheaply and mapped coherently to the same GPU
identity used for utilization, expose it. Otherwise omit it. Do not substitute SRPSS-process VRAM from `--usage` and
label it as system VRAM.

## 6. Sampler owner

Introduce one small product sampler owner only after S0 proves the source cost.

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
- last lease release cancels future cadence and closes/clears the admitted CPU/RAM source state;
- in-flight completion carries generation and is discarded after last-release/recreation;
- family deactivation forces lease release;
- ordinary card disable forces that card’s lease release;
- Settings being open does not acquire a lease;
- catalogue/descriptor import does not construct the sampler.

A future second system-stat card may justify shared infrastructure then. Do not prebuild a generic monitoring framework
now.

## 7. Dormancy contract

Proposed admission:

```text
widgets.family_activation.system_stats
AND widgets.system_stats.enabled
AND temporary dev/member gate while experimental
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

## 8. Threading / scheduling

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

## 9. Accepted snapshot

The landed cross-thread payload is tiny and immutable:

```text
SystemStatsRuntimeSnapshot
    revision
    accepted_monotonic
    CpuRamSample
        cpu_status / cpu_pct | None
        ram_status / ram_used_bytes / ram_total_bytes | None
```

Formatting (GB strings, whole-number percentages, labels) belongs in neutral preparation/presentation, not the source
collector.

Unchanged values may still advance accepted age/revision if needed for freshness, but presentation should not rebuild
its tree just because another 10-second sample arrived.

## 10. Product UI

The initial card is deliberately quiet and readable:

```text
SYSTEM STATS                      WHOLE SYSTEM • 10 SEC
CPU LOAD                         63%
Across all logical processors    [bounded bar]
MEMORY                           71%
22.7 GB of 32.0 GB used          [bounded bar]
```

Exact labels/layout are eyes-on work, but principles are binding:

- no scrolling graphs/history in v1;
- no twitchy decimal percentages; integer display is enough unless evidence says otherwise;
- small presentation easing between accepted samples is optional, finite and purely visual;
- displayed value changes do not change preferred geometry;
- configured metric capacity owns preferred height;
- rejected GPU/VRAM is omitted; CPU/RAM does not collapse into a different card architecture when one value is warming
  or unavailable.

## 11. Icon contract

No suitable gear/spanner image asset currently exists in the tree; the only SVG assets are Settings-control glyphs.

Implementation order:

1. inspect the current branded-header/semantic glyph path and reuse a suitable project/system tools/settings glyph if it
   can be themed and packaged consistently;
2. if no suitable canonical glyph exists, create a **small original project-owned monochrome gear + spanner icon** for
   System Stats;
3. add it through the normal resource/build/package path and tint/opacity it through existing header/icon semantics;
4. do not fetch a random web icon, add an icon-font dependency, or create a family-local icon loader.

The icon is decorative identity only; it must not require a new accelerated surface or animation cadence.

## 12. Retained Quick / ordinary normalization

System Stats uses the same ordinary retained-card rules as the mature widgets:

- one retained Quick component inside the existing engine/window;
- stable item identity;
- descriptor uses current ordinary uniform-resize contract;
- shared 40% whole-card CUSTOM floor;
- global CUSTOM disables authored stacking/adjacency globally;
- non-CUSTOM shared stacking/auto-fit;
- shared Widget Theme/Style Overrides/card border/header/glow semantics;
- shared edit-mode ownership;
- no family-specific layout manager or theme cascade.

Do not create a custom-GL card merely because the data resembles a performance HUD. QML rectangles/text/bars are
sufficient.

## 13. Settings contract

Only add canonical Settings/default state after sampler S0 admission passes.

Landed settings:

- family activation entry;
- Enabled;
- Position / Monitor;
- ordinary font family/size controls consistent with other families.

Do not initially expose:

- cadence;
- worker priority;
- counter backend;
- diagnostic process fields;
- history length;
- GPU query strategy.

Defaults live only in `core/settings/default_settings.py`; derived snapshot/SST outputs must be regenerated/audit-gated.
Any new bucket ids participate in canonical UI-state schema with closed-by-default, one-open local scope.

## 14. S0 admission experiment — mandatory before UI

Build a tiny non-product probe against the current tree before adding card code.

Compare:

```text
A: feature absent / no sampler
B: CPU + RAM sampler at 10 s
C: CPU + RAM + candidate GPU/VRAM sampler at 10 s
D: only if needed, admitted set at 5 s
```

Test under:

- idle desktop;
- normal SRPSS widgets/visualizer;
- the deliberate contention shape used in the preserved 2026-09-12 evidence (heavy external CPU/build/game load where
  practical);
- multi-display presentation.

Capture:

- source collection p50/p95/max;
- worker execution duration;
- skipped cadence edges;
- event-loop p95/p99/max;
- Visualizer logical revision Hz / snapshot age / tick-dt tail;
- sampler owner/thread/task/handle cardinality;
- process CPU delta if discernible.

Admission is based on *no meaningful regression in latency/freshness*, not on a pretty average collection number.

Target expectation for CPU/RAM is low-single-digit milliseconds or better. If a supposedly cheap source routinely takes
tens of milliseconds, investigate/reject it rather than normalizing that cost because the cadence is only 10 seconds.

## 15. Implementation phases

### S0 — sampler feasibility — CPU/RAM admitted, GPU/VRAM rejected

- prove cheap whole-system CPU/RAM source;
- probe honest GPU/VRAM candidate separately;
- A/B at 10 s; optionally 5 s only after 10 s passes;
- no product Settings/UI yet.

### S1 — canonical owner + leases — implemented

- add the minimum sampler service;
- generation fencing;
- low-priority managed work;
- first/last lease start/stop;
- explicit source handle close.

### S2 — dormancy tests — implemented

- family activated but card disabled -> zero sampler work;
- card enabled on one display -> one sampler;
- same card on multiple displays -> still one sampler;
- last presentation removed -> sampler stops;
- runtime recreation -> old completion rejected, old handles closed;
- Settings open/close -> zero runtime sampler side effects.

### S3 — canonical Settings/default descriptor — implemented

Only after S0–S2 are green:

- add family/widget descriptor and defaults;
- regenerate derived settings artifacts;
- add lazy Settings builder/body;
- maintain activation vs ordinary enabled distinction.

### S4 — retained card — implemented

- CPU/RAM card first;
- stable geometry/model identity;
- unavailable/warming/error states;
- no graphs.

### S5 — optional GPU/VRAM — probed and rejected

Only metrics that passed S0:

- one coherent adapter/system identity;
- stable counter ownership;
- no >100% aggregate nonsense;
- graceful unsupported state.

### S6 — icon / presentation polish — implemented

- reuse canonical glyph if viable;
- otherwise add original gear+spanner resource;
- Widget Theme/Style Overrides/glow/stacking/CUSTOM acceptance;
- finite sample-to-sample visual easing only if it helps readability.

### S7 — soak / ungate — automated gate GREEN, installed/long-run cells pending

- off-vs-on contention comparison;
- 10-second long run;
- optional 5-second comparison if genuinely needed;
- repeated enable/disable;
- display/runtime recreation;
- multi-monitor/card cardinality;
- installed build resource/icon validation;
- ungate only if the widget cannot be identified as a meaningful burden on the rest of SRPSS.

## 16. Failure / fallback policy

If GPU/VRAM is expensive or ambiguous:

- omit GPU/VRAM;
- keep CPU/RAM if they independently pass.

If CPU/RAM itself cannot meet the burden bar:

- shelve System Stats.

Do **not** respond by:

- sampling on the UI thread;
- hiding expensive calls behind 30–60 second pauses and calling them free;
- reducing Visualizer cadence/reactivity;
- caching stale data indefinitely without freshness labeling;
- using `--usage` diagnostics as a silent fallback;
- leaving a warm sampler resident while the card is disabled.

## 17. Acceptance summary

System Stats is GREEN only when:

- one shared sampler feeds every card instance;
- 10-second default cadence is sufficient, with 5 seconds admitted only by evidence;
- no consumer means literally no recurring product telemetry work;
- CPU/RAM sources avoid process/thread enumeration;
- GPU/VRAM is shown only if cheap and semantically honest;
- no diagnostic `--usage` service or heavy collector is reused;
- ordinary widget normalization/theme/CUSTOM contracts are inherited;
- the header has a canonical themed glyph or project-owned gear+spanner asset without a new icon subsystem;
- contention A/B shows no meaningful Visualizer freshness/reactivity/presentation-tail regression;
- the widget remains observably cheaper than the diagnostic system it was inspired by.
