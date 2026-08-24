# 08 — Widget Runtime Ownership, Cardinality, Threading and Async Lifetimes

Status: **cross-cutting E1/F technical decomposition; sequence owned by `Current_Plan.md`**
Last updated: 2026-08-24

Cross-links:

- active sequence/work admission: `Current_Plan.md`
- widget architecture and family migration: `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- capability activation/dormancy: `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`
- host/runtime lifecycle: `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- runtime efficiency: `Docs/Guardrails/Runtime_Efficiency.md`
- tests/retirement ledger: `Docs/TestSuite.md`

This document is **not another phase or plan**. It defines how to choose and retire ordinary-widget
runtime owners without multiplying services, threads, timers, providers or race surfaces while E1
separates non-pixel behavior from legacy QWidget presentation.

---

## 1. Core rule

The migration goal is:

```text
correct ownership
+ preserved behavior
+ fewer ambiguous lifetime authorities
```

It is **not**:

```text
one new service class per widget
one new thread per service
one provider per display because the manager is per display
maximum abstraction layers
```

Extract a runtime owner only when there is real presentation-neutral state/lifetime to own.

A smaller/cohesive module is desirable when it follows a real responsibility boundary. File-count or
line-count reduction is not a substitute for architectural improvement.

---

## 2. Choose scope before choosing a class

Classify every piece of non-pixel runtime state by the narrowest **correct semantic scope**.

### 2.1 Process/shared application owner

Use when one logical service/state genuinely serves the application regardless of display or widget
presentation.

Examples may include:

- already-neutral shared tickers;
- authenticated/shared backends;
- process-level caches;
- application-wide provider/session state.

Do not wrap an already-correct singleton/shared backend in another service merely to make it look like a
new E1 abstraction.

### 2.2 Family/shared runtime owner

Use when multiple widget instances/displays consume the same logical family data and duplication would
perform equivalent work.

A shared family owner may expose multiple presentation projections without duplicating the underlying
fetch/controller/cache.

Do **not** consolidate current per-instance behavior opportunistically if instances have distinct
settings, identities, filters, accounts, locations or refresh semantics.

### 2.3 Per-display runtime owner

Use for state that is intrinsically display-local:

- display routing/admission;
- display-local resolved geometry;
- display-local readiness/presentation registration;
- DPR/screen projection;
- interaction ownership tied to one display runtime.

One `WidgetRuntimeManager` per display is compatible with this scope.

**Important:** a per-display `WidgetRuntimeManager` does not force a provider/backend to be per-display.
The manager may own a reference/lease/projection to a broader neutral owner when the real service scope
is broader.

### 2.4 Per-widget-instance runtime owner

Use when a widget instance has genuinely independent data/configuration/lifetime.

Examples include independent:

- subreddit/feed settings;
- account slots;
- locations;
- filters;
- refresh policies;
- action state.

Slice-2 Reddit post-provider ownership is currently per-instance.

### 2.5 Presentation-only owner

Qt Quick presentation owns:

- retained visual item/component;
- local visual state;
- layout inside its assigned rect;
- presentation-only animation;
- hover/selection/edit chrome;
- visual-only image/texture resources.

Presentation ownership must not silently become provider/backend ownership.

### 2.6 Render-thread-only resources

Only custom render nodes own context-local GPU resources.

Ordinary widget service/model objects never become render-thread objects merely because final pixels are
Quick.

---

## 3. A service object is not mandatory

Before creating `FooRuntimeService`, ask:

1. Does the family own meaningful non-pixel state/lifetime today?
2. Is that state currently presentation-coupled?
3. Is there already a correct presentation-neutral owner?
4. Does a new object make ownership clearer, or merely add forwarding?
5. Can a compact model/projection over an existing owner solve the boundary instead?

Valid outcomes include:

```text
existing neutral backend + presentation model
existing shared ticker + presentation model
new per-instance runtime service
new shared family runtime owner
no service at all for a purely visual/static family
```

Do not normalize implementations merely for symmetry.

Normalize **contracts**:

- one legal owner;
- one cleanup path;
- no hidden work while deactivated;
- no duplicate cadence/provider;
- deterministic stale-result rejection;
- clean presentation boundary.

---

## 4. Preserve or reduce expensive-owner cardinality

For every E1 ownership migration, record the before/after count or semantic cardinality of expensive
owners:

```text
provider/controller instances
threads
processes
QTimers / repeating timer handles
poll loops
event subscriptions
background worker loops
network refresh authorities
cache writers
```

Default expectation:

```text
after <= before
```

unless the changed behavior genuinely requires otherwise.

A new Python service object itself is cheap. New schedulers, timers, provider instances, threads and
subscriptions are not.

Never call a migration successful merely because the new neutral owner exists while the old QWidget
owner still constructs the same expensive resource transiently or as fallback.

The first Reddit slice-2 audit blocker is the canonical failure class:

```text
QWidget constructs old provider
-> neutral owner constructs second provider
-> second provider injected later
```

That is duplicate ownership, not migration.

---

## 5. Service is not thread

Ordinary runtime services normally remain on the legal runtime/GUI owner thread and submit detached
work through existing execution infrastructure.

Preferred shape:

```text
runtime/service owner
    |
    +-- current state / generation / timers
    |
    +-- submit detached I/O/computation
            ↓
        existing ThreadManager pool
            ↓
        prepared immutable/plain result
            ↓
        commit on legal owner thread
```

Do not create a dedicated thread merely because a new service class exists.

A dedicated long-lived worker/thread requires a concrete reason such as:

- API/thread-affinity requirement;
- continuous authored/logical work that is not suitable for pooled tasks;
- measured blocking pressure;
- process/backend contract that already owns such a worker.

If a long-lived QObject has explicit thread affinity, that ownership must be singular and documented.
Do not scatter `moveToThread()` calls through presentation/setup code.

---

## 6. Worker boundary

Worker/I/O code may own detached, thread-safe data needed to perform its task.

It must not mutate:

- QWidget;
- QQuickItem/QML objects;
- `QuickSceneController`;
- render-node/GL state;
- arbitrary GUI-thread QObject state.

Prefer worker results made of:

- dataclasses/value objects;
- strings/numbers/enums;
- immutable tuples;
- dictionaries only where the schema is small and explicit;
- `QImage` or raw image bytes where image decoding is legitimately off-thread.

Do not create or mutate `QPixmap` in general worker code. `QPixmap` remains GUI/presentation-side.

Network/provider construction may happen inside a worker task when the provider is short-lived and has
no required persistent affinity. A long-lived provider/controller belongs to one explicit runtime owner
instead.

---

## 7. Timer and polling ownership

Every recurring cadence must have one authority.

For each timer/poll loop, answer:

```text
what behavior requires it?
who owns it?
what state makes it active?
what retires it?
what fences a late callback?
```

Do not leave:

```text
neutral service refresh timer
+
legacy QWidget refresh timer
```

running simultaneously.

Provider/cache refresh does not belong in QML `Timer`.

Presentation-only animation may use Quick animation/timing, but that does not become provider,
simulation or refresh authority.

Hidden/deactivated presentation must not keep a provider poll alive merely because a QML component
exists.

---

## 8. Async result fencing

A worker completing successfully does not imply its result is still legal.

Use the minimum identities required to prove the result still belongs to the current owner. Depending
on the family this may include:

```text
application/runtime generation
service/owner generation
request generation
current account/location/feed/config identity
activation identity
```

Do not add meaningless generations merely for ceremony. Do not omit the identity that actually changes
the meaning of the result.

Commit pattern:

```text
worker result arrives
-> owner still alive?
-> runtime/service generation still current?
-> request still latest/accepted?
-> config/account/location identity still matches?
-> capability/instance still admits the result where relevant?
-> commit
```

Otherwise:

```text
discard / no-op
```

A stale worker may physically finish after retirement. Correctness comes from closed admission and
identity fencing, not from assuming every task can be forcibly killed.

After E1, QWidget validity is not the primary authority deciding whether provider data is legal.

---

## 9. Runtime state vs presentation state vs events

Keep three concepts distinct.

### Runtime/business state

Examples:

- current fetched rows/data;
- provider/controller state;
- refresh timestamps;
- cache state;
- request generation;
- source identity;
- error/retry state.

Owned by the neutral runtime/backend.

### Presentation state

Only what pixels need:

- normalized text/rows;
- icon/artwork identity;
- progress/value state;
- visual flags;
- style/config;
- resolved action availability.

Published to the presentation bridge.

### One-shot business events

Examples may include:

- new-mail sound;
- notification side effect;
- externally-triggered command result.

Do not rely on a latest-only Quick presentation snapshot to deliver a business event exactly once.

If an event has business semantics, handle its exactly-once policy in Python/runtime ownership and
publish the resulting current visual state separately.

---

## 10. Standalone / compatibility construction

Some legacy widgets are directly constructed in tests/tools or compatibility paths.

A standalone convenience fallback may remain **only when there are real callers**.

Production-managed construction must explicitly opt out of that fallback whenever the neutral owner is
required.

Required shape:

```text
standalone/test caller
    -> optional convenience default

production factory/runtime path
    -> suppress default
    -> neutral owner builds/injects/attaches required service
    -> failure closes the production widget path
```

Never allow:

```text
neutral service failure
-> silently run on old QWidget-owned fallback
```

That is fail-open ownership regression.

Repeated setup/reconciliation is part of the same boundary:

```text
active presenter + valid attached service
    -> preserve the exact live edge

stale / detached / mismatched edge
    -> retire the registry entry
    -> active presenter fails closed
    -> inactive presenter may rebuild through normal activation
```

Never manufacture a fresh stopped service and install it beneath a presenter that is already active.

---

## 11. Shared services and consumer accounting

Do not add generic refcount/lease machinery pre-emptively.

First determine whether the actual service is shared.

If it is shared, define real consumer identity, for example:

```text
family instance
display projection
account slot
runtime generation
```

Then retire the shared owner only when its real consumer set is empty.

`is_family_effective()` is activation + dependency satisfaction. It is **not** a shared-service
last-consumer counter.

If an existing backend already has correct singleton/shared lifetime, preserve it rather than wrapping
it in a duplicate lease system.

---

## 12. Retirement order

A typical ordinary service retirement is:

```text
close new admission
-> advance/invalidate owner/request generation
-> stop recurring timers/polls
-> disconnect presentation consumers
-> cancel/mark outstanding work where supported
-> allow unavoidable late work to finish fenced
-> retire provider/controller/subscriptions
-> clear owned state/resources
-> release owner
```

The exact order may vary by family, but after retirement:

- no timer may restart work;
- no stale result may commit;
- no presentation callback may resurrect the service;
- no duplicate owner may remain hidden;
- cleanup is idempotent or explicitly state-guarded.

Application-wide display/runtime teardown remains governed by the host lifecycle in
`01_Runtime_Host_Lifecycle.md`.

---

## 13. Multi-display rule

Do not infer service cardinality from presentation cardinality.

Final presentation is one Quick runtime/window per physical display, but the same logical family data
may be:

```text
shared once and projected to several displays
```

or:

```text
independent per widget/display
```

depending on product semantics.

Preserve existing behavior by default. Consolidate duplicated work only when source inspection proves
the consumers are semantically equivalent and tests cover the change.

Cross-monitor presentation transfer should normally retain the same logical runtime owner/model rather
than recreating provider work merely because pixels moved.

---

## 14. Modularity / file decomposition

Prefer modules that answer one coherent question.

Useful boundaries may include:

```text
family_runtime.py
family_model.py
family_provider.py
family_cache.py
family_actions.py
```

only where the family actually has those responsibilities.

Do not create all of them by template.

A cohesive few-hundred-line module is often better than six tiny forwarding files whose behavior can
only be understood together.

Good decomposition should make it possible to inspect:

```text
provider/data lifecycle
```

without also reading:

```text
QWidget/QML painting/layout
```

and vice versa.

---

## 15. Family examples at the current migration checkpoint

These are orientation examples, not sequencing authority.

### Clock

The shared clock ticker is already presentation-neutral. Do not invent a clock runtime service merely
to match Reddit/Weather naming.

### Reddit / Reddit2

Per-instance post-provider ownership is now routed through neutral runtime service ownership. The
standalone widget default is compatibility-only; production suppresses it before neutral injection.

### Weather

Weather's provider/network/cache/refresh/retry/request-generation ownership is landed in the neutral
`WeatherRuntimeService` at `25f6ca4e`. Production suppresses the standalone convenience service before
registry injection, and detached work reuses `ThreadManager` rather than gaining a Weather thread.

### Gmail

`GmailBackend.instance()` is already the correct neutral process backend. Exact-source closure review
proved a separate real seam: every current presenter owns another cache-first startup, poll/fetch,
accepted email/error state, cache-write submission, new-mail decision and action/post-action refresh.
The active E1 slice therefore adds one runtime-generation shared Gmail owner with per-display leases;
it must not wrap, replace or shut down the existing backend singleton.

### Steam

Progress and Friend Pulse remain provider/task/timer-inert. Steam Abandonment's cache/source/rotation
owner is landed as one per-card/display `AbandonmentRuntimeService` at `86872ab9`. Achievement Pulse's
cache/source/manual-refresh/model/unscaled-artwork owner is separately landed per card/display at
`51948dc3` and adds no recurring timer. Both continue to use the existing process-scoped `core.steam`
caches, backend locks, credentials and asset helpers. Preserve those distinct cardinalities rather than
forcing the family through a Reddit-shaped or generic shared-Steam service. The bounded Abandonment
correction at `9ab4f47e` moved only logical/DPR projection back to its presenter and did not create a
second decode/fetch path.

### Media

Media's primary controller/runtime seam is landed at `4680130b`: per-display leases join one
runtime-generation owner for controller/provider target, polling/query/cache/retention, playback
generations/optimistic confirmation and source-resolution artwork decode. `MediaWidget` retains
per-display QPixmap/DPR/layout/fade/input projection. App-volume and system-mute accessories remain a
separate closure seam; do not fold them into a generic Media god service.

### Imgur

Deprecated. Remove in F0 rather than improving its runtime ownership.

---

## 16. Audit/test obligations for every ownership slice

At minimum answer with source/tests:

1. What expensive owner existed before?
2. What owns it after?
3. What old owner no longer constructs/runs it?
4. What is the before/after cardinality?
5. Does deactivated capability remain dormant?
6. Is ordinary instance-disabled behavior still distinct?
7. What fences stale async completion?
8. What stops recurring work?
9. Does cleanup happen once?
10. Does standalone compatibility, if retained, stay outside production?
11. Did thread/timer/provider/subscription count unexpectedly increase?
12. If shared, what proves remaining consumers keep the owner alive?
13. Does repeated setup preserve/revalidate the exact live presenter/service edge and reject stale
    active reuse?

Do not declare ownership migrated merely because a neutral class exists.
