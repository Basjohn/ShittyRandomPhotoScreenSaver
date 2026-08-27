# 07 — Settings Capability Activation and Lazy Navigation

Status: **landed capability/Settings contract — preserved through closed Phase F and current G/H**  
Last updated: 2026-08-28

## Durable capability model

```text
capability installed/catalogued
-> application family ACTIVATED?
-> implementation/runtime ownership may resolve
-> ordinary enabled/configuration
-> runtime work / presentation
```

`activated/deactivated` = application-level capability. `enabled/disabled` = ordinary feature/widget
instance state inside activated capability. Do not use as synonyms.

## Canonical family authority

`core/settings/widget_family_catalog.py` owns stable family IDs/member IDs/cheap metadata/dependencies.
`rendering/widget_descriptors.py` may consume/re-export runtime info but is not second membership authority.
Catalog/common metadata construction does not import heavy family provider/presenter/runtime trees.

Current capability families include Clocks, Weather, Media, Visualizers, Reddit, Gmail and Steam. Deprecated
Imgur was removed in F0 and is no longer current capability/default surface.

Visualizers is application capability and requires Media: `media=false -> visualizers=false`. Reactivating
Media does not silently reactivate Visualizers. Capability membership does not move special Visualizer
logical/render ownership under ordinary WidgetRuntimeManager presentation.

## Persisted schema

```text
widgets.family_activation.<family_id>
transitions.activation.<canonical transition setting name>
```

`core/settings/capability_activation.py` is canonical authority. Missing state resolves compatibly activated.
Deactivation preserves detailed configuration, ordinary enabled values, CUSTOM geometry and transition pool/
detail state. H settings epoch owns final Quick-era default/reset choices.

## Widgets SETUP

Always-present SETUP page uses cheap canonical metadata. Deactivate: family row remains, detail pill disappears,
built page retires, selected detail redirects SETUP, persisted detail remains. Reactivate returns pill; page
stays lazy until selected and hydrates preserved state.

Enable All/Disable All change activation only, not ordinary instance enabled. Hidden/unbuilt page never saves
default control values over detail it never hydrated.

## Transition SETUP

Deactivated transition has no detail pill, excluded from manual/cycle/effective Random, owns no implementation/
shader/GPU solely because code exists, and keeps saved detail/pool membership.

Live Random authority: `transitions.random_always`; legacy `transitions.type="Random"` is migration input.
Effective Random = activated ∩ saved pool ∩ runnable/hardware.

Canonical repair: zero activated -> canonical Crossfade activation repair; Random + empty effective saved pool
-> Random off + deterministic activated manual selection while preserving saved membership; final admission
revalidates stale selections. Context-menu concrete transition intentionally disables Random; editing detail
while Random on does not.

## Visualizer CUSTOM failover/reclaim

Configured CUSTOM monitor remains canonical. Temporary fallback is runtime-only and never persists geometry.
Unavailable target -> one global outage generation -> one 30s grace -> no fallback if target returns -> at most
one temporary fallback if still absent. Late return is event-driven; retire/fence temporary before configured
owner. Repeated events idempotent; new outage gets fresh generation/grace.

Capability deactivation invalidates pending grace and retires live temporary fallback; failed retirement
retains recoverable live-owner state.

## Runtime ownership / dormancy

E1 ownership is closed. Deactivated family owns no family-exclusive provider/model/backend wrapper/helper/
timer/poll/worker/presentation/render resource. Shared infrastructure remains while real activated consumers
need it.

Fresh-process dormancy includes destination Quick import path: common Quick scene/host imports must not
eagerly resolve inactive family business/runtime/backend trees. Literal sys.modules unloading after prior use
is not required.

## Edit-mode X relationship

G edit X on singleton maps ordinary enabled=False, not family deactivation. Duplicate removal likewise does
not mutate family capability. Save commits; Cancel restores.

## Permanent tests

Preserve family membership/dependencies/environment gating, Visualizers+Media dependency, compatibility of
missing keys, activation vs enabled, lazy SETUP behavior, activation-only Enable/Disable All, transition
activation/pool/manual/Random repair, E2.7 global generation/grace/reclaim/retirement behavior, owner dormancy/
retirement, and fresh-process Quick-host import dormancy.

## Do-not-reopen

E2/E2.7/E1 foundations are closed. Future failure reopens smallest demonstrated owner; do not send an agent
back to “finish E2/E1” because historical prose says next.
