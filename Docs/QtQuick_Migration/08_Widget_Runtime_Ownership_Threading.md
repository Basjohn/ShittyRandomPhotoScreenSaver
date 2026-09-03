# 08 — Widget Runtime Ownership, Cardinality, Threading and Async Lifetimes

Status: **landed permanent post-cutover runtime ownership/cardinality/threading contract**  
Last updated: 2026-08-28

This is a durable owner/cardinality/threading contract, not an unfinished phase plan.

## Core rule

```text
correct ownership + preserved behavior + explicit cardinality + deterministic retirement/stale rejection
```

It is not “one new service per widget” or “one provider per display because manager is per display.”

## Semantic scope

Process/shared: one logical app service/backend/cache/ticker regardless of presentation count.
Runtime-generation/family shared: several displays consume one logical family owner; current Media/Gmail.
Per-display: display routing/geometry/readiness/input/projection; one WidgetRuntimeManager per display can lease
broader shared owners. Per-instance/member: genuinely distinct feed/location/filter/account; current Reddit
members. Presentation-only: visual/layout/hover/menu state only. Render-thread-only: custom render resources.

## Service object is optional

Valid outcomes:

```text
existing shared ticker + presentation model       # Clock
neutral runtime service + model                    # Weather
shared owner + display lease + model               # Media/Gmail
per-member runtime service + model                 # Reddit
neutral model/card path without invented service   # when appropriate
```

Normalize contracts, not class names.

## Current cardinality examples

Clock: `GlobalClockTicker` already neutral/shared; no Clock service.
Weather: provider/network/cache/cadence/retry/request-generation under `WeatherRuntimeService` injected into
retained model.
Media: one runtime-generation shared Media owner serves display leases; app volume and system mute are
separate narrow shared owners/leases; one lease retirement must not kill survivors.
Gmail: `GmailBackend.instance()` process backend/auth; one runtime-generation shared Gmail owner owns cache/
cadence/request generations/actions/notifications/sound with display `GmailRuntimeService` leases.
Reddit/Reddit2: independent configured member runtime service/provider identity, shared family rate-limit/
policy infrastructure.
Steam: preserve existing neutral models/runtime/cache/provenance; do not force every card through a Reddit-
shaped service.

## Cardinality audit

Account before/after providers/controllers, threads/processes, repeating timers/polls, subscriptions, network
refresh authorities and cache writers. Default after <= before unless product semantics require otherwise.
Neutral class beside old expensive owner is duplicate ownership, not migration.

## Service is not thread

Ordinary services normally stay on legal owner thread and submit detached work through ThreadManager:

```text
service owner -> submit I/O/computation -> immutable/plain result -> legal-owner commit after fencing
```

Dedicated long-lived worker/thread requires concrete affinity/continuous-work/performance reason. Do not
scatter `moveToThread()` through setup/presentation.

## Worker boundary

Worker/I/O code does not mutate QWidget, QQuickItem/QML, QuickSceneController or GPU state. Prefer value
objects/immutable tuples and `QImage`/raw bytes where image decode legitimately happens off-thread. Do not
create/mutate QPixmap in general worker code.

## Timer / polling ownership

Every recurring cadence has one authority: why, owner, activation, retirement, stale callback fence. Never
run service refresh timer + legacy presenter refresh timer simultaneously. Provider/cache refresh does not
belong in QML Timer.

## Async fencing

Commit only if relevant identities match: runtime/owner/request generation and account/location/feed/provider/
activation identity where meaning changes. Stale work may finish physically; closed admission makes no-op.

## State / presentation / one-shot events

Runtime owns provider/controller/cache/request/error/current data. Presentation gets normalized text/rows,
stable image identity, progress/value, visual flags/style/action availability. One-shot business events such
as notification sound remain runtime-owned; do not rely on latest-only presentation snapshot for exactly-once
business semantics.

## Standalone compatibility / leases

Standalone/test convenience owner exists only for real callers. Production-managed construction suppresses
it and injects neutral owner; never fail open from neutral-owner failure into old QWidget-owned fallback.

Add lease/refcount only where genuinely shared; define real consumer identity and retire shared owner only
when real consumer set empty. Capability effectiveness is not last-consumer counter.

## Import dormancy

Owner dormancy begins before construction: common catalog/Quick-host imports must not eagerly import inactive
family business/runtime/backend trees. Package convenience exports are not reason to violate boundary.

## Retirement

```text
close admission
-> invalidate owner/request generation
-> stop recurring timers/polls
-> disconnect presentation consumers
-> cancel/mark outstanding work where supported
-> unavoidable late work finishes fenced
-> retire provider/controller/subscriptions as ownership permits
-> clear state / release owner
```

After retirement no timer restarts work, stale result commits, presentation callback resurrects owner or
hidden duplicate remains.

## Multi-display

Do not infer service cardinality from presentation cardinality. One Quick window/display may project shared
logical owner or independent per-instance owners according to semantics. Cross-monitor presentation transfer
normally retains logical runtime/model unless product semantics require recreation.

## Audit obligations

For each ownership slice prove: expensive owner before/after; old owner no longer constructs/runs it;
cardinality; capability dormancy including common import; ordinary enabled distinction; stale async fencing;
recurring work stop; cleanup once/idempotent; standalone compatibility excluded from production; no unexpected
thread/timer/provider/subscription increase; shared owner survives while consumers remain.
