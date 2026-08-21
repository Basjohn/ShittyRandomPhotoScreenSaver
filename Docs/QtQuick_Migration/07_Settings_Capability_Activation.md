# 07 — Settings Capability Activation and Lazy Navigation

Status: Phase-E technical decomposition; not active until `Current_Plan.md` admits E2  
Last updated: 2026-08-21

Cross-links:

- sequence/permission: `Current_Plan.md`
- transition catalog/rendering: `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- widget descriptor/runtime split: `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- settings tests: `Docs/TestSuite.md`
- final defaults/tooling: `Docs/Defaults_Guide.md`
- H0/J0 sequencing: `Current_Plan.md`

## 1. Purpose

The internal plugin-shaped architecture needs a user-facing application-level activation authority.

The final Settings UX must distinguish:

```text
capability installed/catalogued
        ↓
capability ACTIVATED / LOADABLE
        ↓
implementation may resolve
        ↓
ordinary feature enabled/selected state
        ↓
runtime presentation/work
```

"Activated" is not the same thing as a widget's existing `enabled` checkbox or a transition's random
pool membership.

The Settings GUI remains QWidget. This work does not migrate Settings itself to QML.

## 2. Why this belongs in Phase E

Transitions already have a lightweight canonical catalog and lazy Quick implementation registry.

Widgets are about to gain the final presentation-neutral descriptor/family/runtime contract in E1.

E2 is therefore the earliest clean point to expose the same application-level activation concept to
both domains before widget-family ports rely on it.

Do not implement this during Phase D unless the operator explicitly changes sequencing.

## 3. Durable activation semantics

For every capability, keep cheap catalog metadata available so Settings can list it without importing
heavy implementation code.

Persist one explicit application-level activation state per transition or widget family.

Conceptually:

```text
CapabilityState
    capability_id
    activated
```

The exact schema belongs to canonical Settings/defaults; do not hard-code a second state store in the
Settings UI.

### Deactivated before first use

On a fresh process:

- no implementation import solely for runtime use;
- no provider/model/service/process solely for that capability;
- no polling/timer/refresh callback;
- no Quick component;
- no renderer/shader/GPU resources;
- no heavy Settings page builder import merely because the Settings tab exists.

### Deactivated after use

If the capability was already resolved in the current process:

- retire runtime/model/provider ownership cleanly;
- release family/effect-specific resources;
- remove its Settings navigation/page ownership as appropriate;
- do not use it again while deactivated.

Python may retain imported bytecode in `sys.modules`. Literal Python module unloading is not the
contract.

On the next clean process, the deactivated capability should never need to import.

## 4. Persisted configuration is retained

Application-level deactivation is not "reset this feature."

Do not erase a capability's detailed settings when it is deactivated.

Reactivation restores its previous detailed configuration and ordinary enabled/pool state.

Exceptions:

- explicit user reset/default action;
- H0 one-time Qt Quick settings epoch;
- a deliberate future schema migration.

This is critical for lazy Settings pages: an unbuilt/deactivated page must not save default control
values over the persisted configuration it never hydrated.

## 5. Widgets SETUP subtab

`WidgetsTab` already has pill/button navigation and descriptor-driven lazy section builders. Extend
that architecture rather than replacing it.

Add an always-present first pill:

```text
SETUP
```

The Setup page must be cheap and driven by presentation-neutral family catalog metadata.

### 5.1 Activation rows

Show one circle-checkbox row per canonical **widget family/capability**, not blindly one row per
runtime instance.

Examples depend on final E1 family ownership:

```text
Clocks
Weather
Media
Reddit
Gmail
Steam
...
```

A family may own several runtime instances:

```text
Clocks -> clock / clock2 / clock3
Reddit -> reddit / reddit2
Steam  -> Steam family cards/services
```

Do not automatically classify the visualizer as a widget-family capability merely because its current
settings live in WidgetsTab. Phase D/final descriptor ownership decides that boundary.

### 5.2 Enable All / Disable All

Bottom-right:

```text
Enable All
Disable All
```

These operate only on **family activation**.

They must not rewrite internal settings such as:

```text
widgets.clock.enabled
widgets.weather.enabled
...
```

After `Disable All`, detailed per-family `enabled` values remain stored. Re-enabling a family restores
those values.

### 5.3 Navigation

Only activated families expose their normal settings pill/button.

Deactivated family:

```text
SETUP remains visible
family row remains visible in SETUP
family settings pill absent
family page unbuilt/destroyed
```

Activated family:

```text
family settings pill present
page builder imported/built only when selected
```

If the currently selected family is deactivated, navigation returns to `SETUP` rather than leaving a
dead page selected.

### 5.4 Runtime consequence

On Settings apply/recreate, a deactivated family must not be resolved by `WidgetRuntimeManager`.

If it was live, retire its exclusive provider/model/Quick resources safely.

Shared services are capability/reference-owned: disabling one family may not stop a service another
activated family still requires.

### 5.5 Lazy hydration guard

The current WidgetsTab already protects lazy unhydrated sections from being saved over stored values.

Preserve and extend that guard.

Required failure to prevent:

```text
family deactivated
-> page never built/hydrated
-> user saves unrelated Settings
-> missing controls write canonical defaults over the family's stored configuration
```

Setup activation state must be saveable without requiring hydration of the hidden family page.

## 6. Transitions SETUP subtab

The current Transitions tab still uses a transition dropdown and eagerly constructs many
transition-specific groups.

Replace that with the same pill/subtab model.

Always-present first pill:

```text
SETUP
```

One pill per **activated** transition.

Do not import Quick renderer implementations to build Settings pages.

## 7. Transition activation vs runtime selection

Keep four concepts separate:

### 7.1 Activation

```text
activated = capability may exist/load/run
```

A deactivated transition:

- has no normal transition settings pill;
- is excluded from explicit runtime selection;
- is excluded from effective Random/Switch pool;
- does not resolve/import its Quick implementation solely for runtime use;
- keeps its detailed saved settings.

### 7.2 Random-pool membership

Saved per transition, independent of activation.

Effective runtime pool:

```text
effective_pool = activated_ids ∩ pool_member_ids
```

Preserving pool preference while inactive means reactivating the transition restores the user's old
pool choice.

### 7.3 Use Random Transitions

Put one circle checkbox near the Setup random-pool list:

```text
Use Random Transitions
```

This replaces the need for a separate random-pool dialog/button and removes the old
per-transition "Include in Switch/Random Pool" checkbox from each transition page.

Random mode may not remain active with an empty effective pool. Prevent or explicitly resolve that
state in the UI/runtime contract; do not hide it behind a renderer fallback.

### 7.4 Manual transition

When Random is off, the selected transition pill is the manual runtime selection, matching the useful
behavior of the old dropdown without retaining the dropdown.

When Random is on:

- selecting a transition pill changes the settings page/edit focus;
- it does not implicitly turn Random off;
- the selected pill may update/remember the manual transition that would be used if Random is later
  disabled.

If the selected manual transition is deactivated, resolve and persist a deterministic activated
fallback.

## 8. Transition Settings page decomposition

Do not replace one monolithic dropdown with one monolithic page that still constructs every
transition's controls.

Introduce lightweight Settings descriptors, conceptually:

```text
TransitionSettingsSectionDescriptor
    transition_id
    label
    builder_module
    builder_factory
    persisted_keys
    optional shared controls
```

Builder module paths remain strings/callables resolved on demand.

Shared UI helpers may construct repeated controls such as duration, direction selectors, sliders,
swatches, and labeled rows.

Renderer implementations remain separate. Settings builder modules must not import renderer classes
merely to discover their controls.

## 9. Suggested Widgets/Transitions UI layout

### Widgets

```text
[ SETUP ] [ Clocks ] [ Weather ] [ Media ] [ Reddit ] ...
```

Setup:

```text
Widget Modules

○ Clocks
○ Weather
○ Media
○ Reddit
○ Gmail
○ Steam
...

                               [ Enable All ] [ Disable All ]
```

Only activated rows produce pills.

### Transitions

```text
[ SETUP ] [ Crossfade ] [ Slide ] [ Wipe ] [ Burn ] ...
```

Setup:

```text
Transition Modules
○ Crossfade
○ Slide
○ Wipe
○ Burn
...

○ Use Random Transitions

Random Pool
[✓ Crossfade]
[✓ Slide]
[  Wipe]
[✓ Burn]
...
```

The pool list only shows activated transitions.

## 10. Defaults / H0

New activation state, random-mode state and pool state must be owned by canonical defaults.

Do not derive default activation from whether Python files happen to be importable.

H0 resets old presentation-era state to final canonical Quick defaults, including:

- transition activation;
- transition random-mode/pool;
- widget-family activation.

Detailed credentials/source data remain subject to H0's explicit durable whitelist.

## 11. Defaults Foundry

J0 must teach Defaults Foundry about the final activation/default schema without importing heavy
runtime modules.

The Foundry remains a standalone QWidget tool unless another tooling decision changes it.

## 12. Tests

### Catalog-only Settings construction

Prove opening Settings and selecting `SETUP`:

- imports cheap descriptor/catalog modules;
- does not import deactivated family builders/providers/renderers;
- does not import deactivated transition renderers.

### Widgets

Prove:

- first pill is `SETUP`;
- only activated family pills exist;
- family page builds once/on demand;
- disabling current family returns to Setup;
- Enable All/Disable All change activation only;
- per-widget enabled/detail values survive activation toggle;
- lazy/unhydrated sections never overwrite stored settings;
- deactivated family owns no exclusive runtime resources;
- shared services follow remaining activated capabilities.

### Transitions

Prove:

- first pill is `SETUP`;
- only activated transition pills exist;
- implementation registry stays dormant until runtime needs an activated effect;
- random effective pool equals activated ∩ pool membership;
- inactive pool preference can be preserved without affecting effective pool;
- Random cannot silently operate with an empty effective pool;
- selected manual transition fallback is deterministic after deactivation;
- Random-on pill browsing does not disable Random;
- old dropdown/pool-checkbox paths have no remaining authority once E2 lands.

### Recreate/lifecycle

Prove activation changes survive Settings save/recreate and do not leave stale providers, models,
callbacks, Quick items, or render resources alive.

## 13. Exit

E2 exits when:

- both Settings tabs expose the new Setup/navigation contract;
- activation is canonical/persisted;
- disabled capability runtime dormancy is real;
- lazy Settings pages cannot corrupt hidden configuration;
- transition random/manual selection semantics are deterministic;
- widget family activation and per-instance enabled state remain separate;
- no old transition dropdown/random-pool authority remains;
- Phase F can port families against the final activation contract.
