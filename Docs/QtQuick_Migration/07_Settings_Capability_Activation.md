# 07 — Settings Capability Activation and Lazy Navigation

Status: **Phase-E activation foundation landed; E2 operator-facing Settings UI remains active work**  
Last updated: 2026-08-22

Cross-links:

- sequence/permission: `Current_Plan.md`
- transition catalog/rendering: `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- widget descriptor/runtime split: `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- settings tests: `Docs/TestSuite.md`
- defaults: `Docs/Defaults_Guide.md`
- H0/J0 sequencing: `Current_Plan.md`

## 1. Purpose

SRPSS now has an application-level capability activation authority above ordinary feature settings.

The durable model is:

```text
capability installed/catalogued
        ↓
capability ACTIVATED / LOADABLE?
        ↓
implementation/runtime ownership may resolve
        ↓
ordinary feature enabled/selected/pool state
        ↓
runtime presentation/work
```

Use terms precisely:

```text
activated / deactivated
    = application-level capability authority

enabled / disabled
    = ordinary widget/feature state inside an activated capability

pool membership
    = saved Random preference

manual transition selection
    = ordinary transition choice when Random is off
```

The Settings GUI remains QWidget-based. This work does not migrate Settings to QML.

## 2. What has already landed

At the current Phase-E foundation boundary, the following are real source/runtime mechanisms rather
than future design prose.

### 2.1 Presentation-neutral widget family catalog

`rendering/widget_descriptors.py` owns `WIDGET_FAMILY_DESCRIPTORS` and cheap family lookup helpers.

The catalog maps stable family ids to member runtime widget ids and derives availability from active
runtime descriptors/environment gates. It does not import family Quick presenters/providers merely to
list the catalog.

The visualizer is deliberately excluded from widget-family activation.

### 2.2 Canonical persisted activation schema

Canonical settings currently include:

```text
widgets.family_activation.<family_id>
transitions.activation.<canonical transition setting name>
```

`core/settings/capability_activation.py` is the presentation-neutral read/write/query authority.

Missing activation state resolves to `True` so existing/pre-Quick settings preserve current behavior.
Current canonical activation defaults are all `True`; H0 owns the final Quick-era default selection.

### 2.3 Transition runtime consequence

Landed transition selection seams honor application activation:

- effective Random pool filters by activation;
- C-key/cycle skips deactivated transitions;
- manual selection of a deactivated transition resolves through deterministic fallback logic;
- transition factory/random selection does not deliberately choose a deactivated transition while a
  valid activated alternative exists.

These mechanisms are inert while all activation defaults are on.

### 2.4 Widget runtime creation consequence

Current factory-backed widget creation filters a deactivated family before concrete runtime
widget/model/provider creation and before ordinary per-instance `enabled` handling.

This is a real runtime consequence, but it is **not** equivalent to the full E1
`WidgetRuntimeManager` ownership split. Provider/model/shared-service retirement semantics must follow
the owners that have actually migrated.

## 3. Persisted configuration survives deactivation

Application-level deactivation is not “reset this feature.”

Do not erase detailed capability settings when it is deactivated.

Reactivation restores previous detailed configuration and ordinary enabled/pool/manual state unless:

- the user explicitly resets/defaults it;
- H0 intentionally establishes the new Quick settings epoch;
- a deliberate later schema migration says otherwise.

This is critical for lazy Settings pages: an unbuilt/deactivated page must not save default control
values over persisted configuration it never hydrated.

Python may retain already imported bytecode in `sys.modules`; literal module unloading is not the
contract. Runtime/resource dormancy is immediate at the legal owner boundary, and a clean process must
not import heavy implementation solely for a deactivated capability.

## 4. Widgets `SETUP` subtab — E2

`WidgetsTab` already has descriptor-driven/lazy section infrastructure. Extend it rather than replacing
Settings architecture.

Add an always-present first pill:

```text
SETUP
```

The Setup page is cheap and driven by presentation-neutral family catalog metadata.

### 4.1 Family activation rows

Show one activation row per canonical available **family/capability**, not blindly one row per runtime
instance.

Current family ownership is source-owned. Examples include:

```text
Clocks -> clock / clock2 / clock3
Weather -> weather
Media -> media + media-owned controls
Reddit -> reddit / reddit2
Gmail -> gmail
Steam -> supported Steam family cards/services
```

Imgur may remain temporarily visible only under its current legacy/dev environment gate before Phase F
removes it; it is not a Quick family target.

The visualizer is not a widget-family activation row.

### 4.2 Enable All / Disable All

Widget Setup includes:

```text
Enable All
Disable All
```

These change **family activation only**.

They do not rewrite ordinary settings such as:

```text
widgets.clock.enabled
widgets.weather.enabled
...
```

After family deactivation, internal enabled/detail values remain stored. Reactivation restores them.

### 4.3 Live navigation — operator decision

Navigation rebuilds **live while Settings is open**.

Deactivating a family:

```text
SETUP remains visible
family row remains visible in SETUP
family normal settings pill disappears immediately
family page is no longer a live navigation target
```

If the removed family page is currently selected, navigate immediately to `SETUP`.

Reactivating the family immediately restores its normal settings pill.

This is not a grey-out/deferred-close design.

Detailed page construction remains lazy; re-adding a pill does not require eagerly constructing the
family page.

### 4.4 Runtime consequence

On the safe runtime/settings application boundary, a deactivated family must not be resolved by the
current/final runtime owner.

If it was live, retire its exclusive runtime ownership according to the owner that actually controls
that resource. Shared services remain alive while another activated consumer still requires them.

Do not perform unsafe provider/process teardown directly from a navigation-button callback merely to
match immediate pill removal.

### 4.5 Lazy hydration guard

Required failure to prevent:

```text
family deactivated
-> page never built/hydrated
-> user saves unrelated Settings
-> absent controls write canonical defaults over stored family config
```

Setup activation state must be saveable without hydrating hidden family pages.

## 5. Transitions `SETUP` subtab — E2

Replace the old transition dropdown/eager transition-specific group ownership with the same
`SETUP` + activated-transition pill model.

Always-present first pill:

```text
SETUP
```

Only activated transitions expose normal settings pills.

Do not import Quick renderer implementations to build Settings pages.

### 5.1 Activation

```text
activated = capability may exist/load/run
```

A deactivated transition:

- has no normal transition settings pill;
- is excluded from explicit effective runtime selection;
- is excluded from the effective Random pool;
- does not resolve/import its Quick renderer solely for runtime use;
- keeps its detailed saved settings and saved pool preference.

### 5.2 Random pool membership

Pool membership is saved independently of activation.

Effective runtime pool:

```text
effective_pool = activated_ids ∩ saved_pool_member_ids
```

A deactivated transition may keep `pool_member=True` in storage so reactivation restores the user's
preference; it contributes nothing to the effective pool while inactive.

### 5.3 `Use Random Transitions`

The Setup page owns one ordinary control:

```text
Use Random Transitions
```

Random mode uses the effective pool and is separate from application activation.

The old per-transition `Include in Switch/Random Pool` control and separate pool dialog/button should
lose authority once E2 is complete.

### 5.4 Manual transition

When Random is off, the selected transition pill represents/updates the manual transition selection.

When Random is on:

- selecting a transition pill changes editing focus;
- it does not implicitly turn Random off;
- it may remember the manual selection that would be used later when Random is disabled.

If the selected manual transition is deactivated, resolve and persist a deterministic **activated**
fallback. Do not silently reactivate the transition the user disabled.

### 5.5 Live transition navigation

The same live-nav rule applies:

- deactivate transition -> its settings pill disappears immediately;
- if selected, navigate to `SETUP` immediately;
- reactivate -> pill immediately returns;
- builder remains lazy until selected.

### 5.6 Zero-activated / empty-effective-pool invariant

Do not confuse two different failure states:

```text
zero activated transitions
```

and

```text
activated transitions exist, but none are Random-pool members
```

The second state can be resolved by explicit Random-mode UX/runtime policy without violating
activation.

The first state has **no valid “activated fallback” by definition**. A helper returning the string
`Crossfade` is not sufficient if Crossfade itself is deactivated.

At the repository checkpoint this documentation pack was based on, the Phase-E foundation does not
establish an explicit legal all-deactivated transition runtime state. E2 must therefore either prevent
that state or pair it with a deliberately implemented source/runtime contract before exposing it.

Do **not** silently run a deactivated Crossfade, silently reactivate a transition, or claim an
“activated fallback” exists when the activated set is empty.

If source lands a different explicit policy after this checkpoint, update this section to the tested
source contract rather than preserving this warning as stale prose.

## 6. Settings implementation shape

Keep cheap Settings descriptors separate from renderer implementations.

Conceptually:

```text
Capability / Settings descriptor
    stable id
    label
    activation key
    builder module/factory
    persisted-key ownership
    family/group identity
```

Builder modules resolve only when their page is selected.

For transitions, do not replace one monolithic dropdown with a monolithic page that still constructs
every transition's controls.

For widgets, extend the existing descriptor/lazy-section system.

`SETUP` itself is never capability-gated.

## 7. Transition Settings page decomposition

Transition-specific Settings builders may use lightweight metadata such as:

```text
TransitionSettingsSectionDescriptor
    transition id
    label
    builder module/factory
    persisted keys
    shared-control metadata
```

Keep renderer implementation imports out of Settings builders unless an exact measured/technical
reason requires otherwise.

Shared UI helpers may construct repeated controls such as duration rows, direction selectors, sliders,
swatches and labels without making them runtime renderer authority.

## 8. Defaults / H0

Activation state is canonical settings/default state. Do not derive default activation from whether a
Python file happens to import.

Current compatibility defaults are all activated so the foundation is inert.

H0 later selects final canonical Quick-era defaults for:

- transition activation;
- transition Random mode/pool;
- widget-family activation;
- other explicitly reset presentation-era state.

Do not pre-empt H0 values in E2 docs/code unless Current Plan explicitly selects them.

Deactivation preserves detailed configuration; H0's deliberate settings epoch is a separate event.

## 9. Defaults Foundry

J0/final tooling must understand the final activation schema without importing heavy runtime modules.

The Foundry remains a standalone QWidget tool unless another explicit tooling decision changes it.

Generated defaults/SST artifacts derive from canonical defaults rather than becoming a second
activation authority.

## 10. Tests

### 10.1 Landed foundation tests

Preserve proof for:

- family catalog membership/environment gating;
- visualizer excluded from widget-family activation;
- missing activation keys resolve compatibly;
- family and transition activation read/write helpers;
- effective Random pool = activated ∩ saved pool membership;
- transition selection/cycle/random seams exclude deactivated transitions when a valid activated choice
  exists;
- runtime factory widget creation filters deactivated family before per-instance enabled handling.

### 10.2 E1 ownership tests

As E1 lands, prove the owner actually responsible for each family resource retires exclusive:

- models/providers;
- timers/polls/refresh callbacks;
- processes/workers;
- Quick components/resources;

while shared services remain until their last activated consumer retires.

Do not claim a resource is dormant merely because factory widget creation was skipped if another old
owner still starts it.

### 10.3 Widgets E2 tests

Prove:

- first pill is `SETUP`;
- only activated family pills exist;
- live deactivation removes pill immediately;
- deactivating current page navigates to Setup;
- reactivation restores pill immediately;
- family page builds only on demand;
- Enable All/Disable All change activation only;
- per-instance enabled/detail values survive family activation toggles;
- lazy/unhydrated sections never overwrite stored settings.

### 10.4 Transitions E2 tests

Prove:

- first pill is `SETUP`;
- only activated transition pills exist;
- live pill removal/re-addition works;
- implementation registry remains dormant until runtime needs an activated effect;
- effective Random pool is exactly activated ∩ saved membership;
- inactive pool preference survives;
- Random-on pill browsing does not disable Random;
- manual fallback after deactivation is deterministic and activated;
- zero-activated-transition policy is explicitly tested rather than reaching a deactivated renderer
  through fallback;
- old dropdown/pool-checkbox authority is gone once E2 cuts over.

### 10.5 Recreate/lifecycle

Prove activation changes survive Settings save/recreate and do not leave stale providers, models,
callbacks, Quick items or render resources alive according to the owners that have landed.

## 11. E2 exit

E2 exits when:

- Widgets and Transitions expose the new `SETUP`/pill contract;
- activation is canonical/persisted;
- live navigation removal/re-addition is deterministic;
- hidden/unbuilt settings cannot corrupt persisted configuration;
- transition Random/manual/activation semantics are deterministic and tested;
- zero-activated-transition behavior is explicitly legal or prevented;
- widget family activation remains separate from per-instance enabled state;
- no old transition dropdown/random-pool authority remains;
- Phase F can rely on the final application-level activation contract.

`Current_Plan.md` owns the actual promotion decision.
