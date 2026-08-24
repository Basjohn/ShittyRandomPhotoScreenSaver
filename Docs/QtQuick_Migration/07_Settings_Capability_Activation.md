# 07 — Settings Capability Activation and Lazy Navigation

Status: **E2 + E2.7 implementation CLOSED / independently audited GREEN; E1 ownership CLOSED; E3 active**  
Last updated: 2026-08-23

Cross-links:

- sequence/work admission: `Current_Plan.md`
- widget runtime/model ownership: `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- transition rendering: `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- defaults: `Docs/Defaults_Guide.md`
- tests and retirement ledger: `Docs/TestSuite.md`
- harness routing: `Docs/Harness_Index.md`

This document is now a **landed capability/Settings contract**, not an unfinished E2 implementation
plan. E1 has now closed its runtime/model/provider ownership work. E3/F must preserve this capability
contract and must not reopen the E2 UI/state model without contradictory evidence.

## 1. Durable capability model

SRPSS has one application-level capability authority above ordinary feature configuration:

```text
capability installed / catalogued
        ↓
capability ACTIVATED / LOADABLE?
        ↓ yes
implementation/runtime ownership may resolve
        ↓
ordinary enabled / selected / pool configuration
        ↓
runtime work / presentation
```

Use terminology precisely:

```text
activated / deactivated
    = application-level capability authority

enabled / disabled
    = ordinary feature or widget-instance state inside an activated capability

transition pool membership
    = saved Random preference, independent of activation

manual transition selection
    = ordinary concrete transition choice when Random is off
```

Do not use `disabled family` when the state is application-level deactivation.

Settings remains QWidget-based. Capability metadata must remain cheap and presentation-neutral.

## 2. Canonical widget-family authority

`core/settings/widget_family_catalog.py` is the canonical presentation-neutral authority for:

- stable family ids;
- member runtime widget ids;
- family labels/cheap metadata;
- family-level dependencies such as `visualizers requires media`.

`rendering/widget_descriptors.py` may consume/re-export this information for the current runtime, but
it is **not** a competing membership authority.

Catalog construction must not import heavy family presenters/providers merely to list capabilities.
Availability may still derive from the ordinary descriptor/environment gates where applicable.

### 2.1 Visualizers is a real capability family

Canonical family:

```text
family_id = "visualizers"
member_widget_ids = ("spotify_visualizer",)
required_family_ids = ("media",)
```

Visualizers therefore participates in application-level family activation.

That does **not** make the Visualizer an ordinary Phase-F widget presentation family and does not move
its special `VisualizerLogicalRuntime` / Quick-render-node ownership under `WidgetRuntimeManager`.
Capability membership and presentation/runtime architecture are separate concerns.

Dependency normalization is canonical:

```text
media = false
    -> visualizers = false
```

Reactivating Media never silently reactivates Visualizers. The user must explicitly reactivate it.

## 3. Canonical persisted activation schema

Canonical settings include:

```text
widgets.family_activation.<family_id>
transitions.activation.<canonical transition setting name>
```

`core/settings/capability_activation.py` is the read/write/normalization/query authority.

Missing activation state resolves compatibly to activated so pre-Quick/current installations do not
silently lose features merely because the schema was introduced.

Current compatibility defaults remain all activated. **E2 UI is already landed. H0, not E2, owns the
final Quick-era default activation/reset epoch.**

Deactivation is not reset. Preserve detailed configuration, including:

- ordinary widget `enabled` state;
- detailed family settings;
- CUSTOM geometry;
- transition saved pool membership;
- transition/manual configuration.

An unbuilt/deactivated page must never write default control values over persisted configuration that
it never hydrated.

## 4. Widgets `SETUP` — LANDED E2 contract

Widgets has an always-present first pill:

```text
SETUP
```

The Setup page is cheap and driven from canonical family metadata.

### 4.1 Family rows

Show one activation row per available family/capability rather than one row per runtime instance.

Representative families include:

```text
Clocks
Weather
Media
Visualizers
Reddit
Gmail
Steam
```

Imgur may remain visible only while the legacy/dev-gated source still exists. It is
**CURRENT-LEGACY — WILL BE REMOVED in Phase F0**, not a Quick family target.

Visualizers remains visible while Media is off, but is disabled/unchecked with the dependency
explained. Canonical state must already be normalized to `visualizers=False` in that condition.

### 4.2 Enable All / Disable All

These controls modify **family activation only**.

They do not rewrite ordinary instance settings such as:

```text
widgets.clock.enabled
widgets.weather.enabled
```

Enable All must respect dependency ordering; Disable All leaves detailed configuration intact.

### 4.3 Live navigation

Navigation changes immediately while Settings is open:

```text
deactivate family
    -> SETUP remains
    -> family row remains in SETUP
    -> family detail pill disappears immediately
    -> built detail page is retired
    -> if selected, navigate immediately to SETUP

reactivate family
    -> pill returns immediately
    -> detail page remains lazy
    -> selecting later rebuilds/hydrates preserved state
```

A hidden/non-admitted page must not stay addressable through stale programmatic navigation.

### 4.4 Lazy hydration / save safety

Forbidden failure:

```text
family deactivated
-> page not built/hydrated
-> unrelated Save
-> absent controls overwrite preserved family settings
```

Setup activation state must save independently of hidden detailed pages.

## 5. Transitions `SETUP` — LANDED E2 contract

Transitions uses the same always-present `SETUP` + activated-detail-pill model.

A deactivated transition:

- has no ordinary detail pill;
- is excluded from manual/cycle/effective Random resolution;
- does not gain implementation/shader/GPU ownership solely because code exists;
- keeps detailed settings and saved pool membership.

### 5.1 Random authority

The one live Random authority is:

```text
transitions.random_always = bool
```

Legacy:

```text
transitions.type = "Random"
```

is migration input only. It must not become a second live Random switch.

Saved pool membership remains separate from activation:

```text
effective saved pool = activated ids ∩ saved pool-member ids
```

Runtime may additionally filter for runnable/hardware eligibility:

```text
effective runtime candidates
    = activated ∩ saved pool ∩ runnable/hardware
```

Do not broaden an empty effective pool into an unrelated transition and call that Random behavior.

### 5.2 Manual selection while Random is on

When Random is off, selecting a transition detail pill updates the manual selection.

When Random is on, selecting a detail pill changes editing focus and may remember the manual selection
for later; it does **not** silently disable Random.

The screensaver context menu is intentionally different: choosing a concrete transition there disables
Random and selects that concrete transition.

### 5.3 Canonical invalid-state repair

Two invalid states are distinct:

```text
zero activated transitions
```

and:

```text
Random on + empty activated saved pool
```

Landed normalization is:

```text
zero activated transitions
    -> activate Crossfade in canonical settings state
    -> persist repair

Random on + empty effective saved pool
    -> random_always = false
    -> persist deterministic activated manual transition
    -> preserve saved pool membership
```

This is state repair, not a renderer/factory bypass. No renderer may simply execute a deactivated
Crossfade.

Final runtime admission revalidates stale pre-resolved Random choices against current activation and
hardware/runnability. Empty-candidate branches do not use a hidden literal Crossfade substitution.

## 6. E2.7 Visualizer CUSTOM failover/reclaim — LANDED / GREEN

The configured CUSTOM monitor remains the canonical owner. A fallback host is temporary runtime state
only and never persists monitor/position/size/viewport authority.

### 6.1 Thirty-second grace

If the configured target is unavailable — whether absent or runtime-known/non-participating — use one
human-scale grace:

```text
30 seconds
```

If the target becomes usable inside the grace, use/reclaim it and create no fallback.

If still unavailable at the deadline, at most one temporary fallback may be created on a participating
display. If no participating fallback exists, fail closed.

### 6.2 One global outage generation

Visualizer ownership is global, so failover generation/deadline authority is global too.

Required properties:

- one effective grace per outage;
- reconcile from another DisplayWidget does not restart/extend it;
- every delayed callback validates the coordinator/global generation;
- target return/reclaim invalidates the whole old generation;
- a later genuinely new outage receives a fresh strictly-new generation and full 30-second grace;
- stale scheduled callbacks may physically fire but are fenced no-ops.

### 6.3 Event-driven late reclaim

After fallback creation, return is event-driven rather than polling-timer-driven.

If the configured target returns seconds, minutes or hours later:

```text
display/topology event
    -> re-read current settings/capability
    -> retire/fence temporary owner
    -> only after confirmed retirement create/restore configured owner
    -> restore configured target's saved CUSTOM geometry
```

Repeated return events are idempotent.

`screenAdded -> full topology rebuild` remains the authority for a physically absent display appearing.
Runtime-known return/re-anchor paths perform the targeted reclaim where appropriate.

### 6.4 Capability deactivation retires failover lifecycle

If Media or Visualizers becomes ineffective:

- pending grace/global generation is invalidated;
- stale callbacks cannot create fallback;
- a live temporary fallback is retired;
- its record is discarded only after retirement is confirmed;
- failed retirement retains recoverable live-owner state;
- later explicit reactivation with the target still absent starts a **fresh full 30-second grace**.

A stale Media/Visualizer QWidget/runtime object grants no permission after canonical capability state is
off.

## 7. E1 boundary — ACTIVE next

E2 proved the activation and Settings/navigation authority. E1 must now move provider/model/runtime
ownership to the presentation-neutral owner without changing the E2 state model.

A deactivated family ultimately owns no family-exclusive:

- model/provider;
- helper process;
- timer/poll/refresh callback;
- worker;
- presentation component;
- family-specific render resource.

Shared infrastructure remains until its last activated consumer retires.

Fresh-process deactivation means heavy family implementation is not imported/resolved merely because
cheap catalog metadata exists. Literal `sys.modules` unloading after prior use is not required; live
ownership is what matters.

Ordinary `enabled=False` remains distinct from family deactivation.

The Visualizer remains special: its capability admission is governed here, while its logical/render
ownership remains the dedicated visualizer subsystem.

## 8. H0 defaults/settings epoch

H0 later chooses the final Quick-era defaults/reset policy for:

- family activation;
- transition activation;
- Random mode/pool;
- explicitly retired presentation-era state.

Do not use E1/E3/E4/F work to silently pre-empt H0 choices.

Pre-Quick per-mode visualizer growth/card-height settings and other presentation state explicitly
retired by the migration are **CURRENT-LEGACY — WILL BE OBSOLETE at H0/I caller cleanup**.

## 9. Permanent test obligations

Preserve direct proof for:

- canonical family membership/environment gating/dependencies;
- Visualizers **included** as capability family and requiring Media;
- missing activation keys resolve compatibly;
- Media-off forces Visualizers-off; Media-on does not silently reactivate it;
- activation read/write/normalization helpers;
- family activation distinct from ordinary instance enabled state;
- Widgets/Transitions `SETUP` first-pill/live-navigation/lazy hydration behavior;
- built-page retirement and later rehydration;
- Enable All/Disable All activation-only semantics;
- transition activation/pool/manual/Random separation;
- `random_always` as sole live Random authority;
- zero-activated Crossfade canonical repair;
- Random-empty-pool repair preserving saved membership;
- stale pre-resolved Random choice final-admission recheck;
- no deactivated Crossfade last-resort;
- E2.7 one global outage generation, 30-second grace, event reclaim, retirement-failure retention,
  capability-off retirement, stale-callback fencing and fresh-grace reactivation;
- E1 owner dormancy/retirement as each real provider/model/process owner migrates.

`Docs/TestSuite.md` is the canonical file inventory/retirement ledger. Do not revive a stale E2-era test
expectation merely because its filename sounds authoritative.

## 10. E2 closure / do-not-reopen rule

E2 and E2.7 implementation are closed by independent audit. Remaining E2-related operator acceptance
(such as responsive Settings eyes-on or physical dual-display wake/late-return for R-26) is acceptance
debt, not unfinished E2 implementation.

A failing future test/installed run reopens only the smallest demonstrated owner. Do not send an agent
back to “finish E2” from old planning prose.
