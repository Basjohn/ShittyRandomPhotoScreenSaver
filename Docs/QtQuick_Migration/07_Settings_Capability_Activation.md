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

Landed transition selection seams now include one canonical state-normalization authority:

```text
normalize_transition_capability_state(...)
```

It repairs malformed persisted capability state explicitly rather than letting renderer/factory code
silently substitute another effect:

- if every transition is deactivated, it reactivates the deterministic recovery transition
  (`Crossfade`) **in canonical settings state** and reports that the repaired state must be persisted;
- if Random is on while `activated ∩ saved pool membership` is empty, it turns Random off, persists a
  deterministic activated manual replacement selection, and preserves the saved pool preferences;
- effective Random pool filtering, C-key/cycle selection, and ordinary manual selection all honor
  activation at their current seams.

This recovery is a state repair, not permission to execute a deactivated Crossfade.

**Final transition admission is now closed (E2 audit correction).** The factory revalidates an
already-resolved `transitions.random_choice` against activation + hardware at admission
(`TransitionFactory._is_admissible_random_choice`) and re-resolves if stale; `_pick_random_transition`
fails closed (no blanket `'Crossfade'` return); and the engine, factory, and C-key empty-candidate paths
never run a *deactivated* Crossfade — they pick a deterministic activated hw-available transition or
perform the explicit persisted recovery repair (`ensure_recovery_transition_activated`). `random_always`
is the single live Random authority: the factory `_get_random_mode` and engine
`_prepare_random_transition_if_needed` no longer treat `type="Random"` as a live trigger (E2.6).

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
replacement selection. Do not silently reactivate the transition the user disabled except through the
explicit zero-activated-state normalization rule below, where Crossfade reactivation is the canonical
persisted state repair for an otherwise invalid all-false transition set.

### 5.5 Live transition navigation

The same live-nav rule applies:

- deactivate transition -> its settings pill disappears immediately;
- if selected, navigate to `SETUP` immediately;
- reactivate -> pill immediately returns;
- builder remains lazy until selected.

### 5.6 Zero-activated / empty-effective-pool invariant

Do not confuse two different invalid states:

```text
zero activated transitions
```

and

```text
activated transitions exist, but none are Random-pool members
```

The landed canonical normalization policy is explicit:

```text
zero activated transitions
    -> set Crossfade activation=True in canonical settings state
    -> persist the repaired state

Random on + empty effective pool
    -> random_always=False
    -> persist deterministic activated manual selection
    -> preserve saved pool membership unchanged
```

This is deliberate **state normalization**, not a renderer/factory bypass. Once normalization has run,
any selected/run transition must still pass activation admission normally.

Hardware availability is a separate rendering-side filter. If hardware filtering leaves no valid
activated candidate, do not silently execute a deactivated Crossfade or broaden into an unrelated
Random pool. Fail closed or perform an explicit canonical state repair whose result is then admitted
normally.

The final factory/engine/C-key admission paths described in §2.3 are now fenced and regressed (E2 audit
correction). This normalization also runs at the E2 SETUP mutation boundary and in the context-menu
selection handler, so an invalid capability state is repaired and reflected live rather than persisted
and deferred.

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

Transition-specific pages are built lazily: each page is constructed only when its pill is first
selected, a deactivated transition's page is never built, deactivation retires a built page, and
reactivation rebuilds + hydrates from preserved settings on next selection. The authoritative
edited/manual selection is a plain state value, not the hidden legacy dropdown (which survives, if at
all, only as a non-authoritative mirror until Phase I).

## 7A. E2 presentation rules (durable, not a pixel-spec)

Widgets SETUP and Transitions SETUP are sibling visual/interaction surfaces and share one grammar:

- **Responsive pill navigation.** The top pill row wraps onto additional rows via the shared
  `ui/flow_layout.py` (`FlowContainer`/`FlowLayout`) instead of clipping; canonical pill order is
  preserved; pills never become horizontally unreachable; labels are not crushed to avoid wrapping.
  Use consistent `SETUP` labelling across both tabs.
- **Responsive module grids.** Activation lists (Widget Modules, Transition Modules) and the Transitions
  Random Pool are responsive grids that fit at least two modules per row at ordinary Settings widths and
  gain columns when width allows, collapsing toward one column only when genuinely too narrow. Column
  count derives from available width / item min width / spacing, not a hardcoded breakpoint.
- **Reachable action rows.** Enable All / Disable All reflow (wrap) so both stay visible/reachable while
  the frame's right border remains visible; horizontal scrolling is never the workaround.
- **Horizontal containment.** No page/frame/nav layout may force the scroll content wider than its
  viewport; the styled frame's right border stays visible at every supported width; layout recomputes on
  resize while Settings is open.
- **Shared styling.** Module frames use the canonical styled `QGroupBox` (`style_group_box`) and
  circle-checkbox language (`circleIndicator` + `CIRCLE_CHECKBOX_STYLE`); do not invent per-surface
  checkbox styles. Mature Widget subsections keep their existing internal design and only gain outer
  containment; specialized builders (e.g. the Visualizer) keep their internal UI but must fit inside the
  same responsive shell.

`random_always` is the single Random authority shared by Transitions SETUP, the runtime, and the
screensaver context menu. Legacy `type="Random"` is migration input only; no UI writes it.

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

The normalization invariants are now directly pinned: `tests/test_capability_activation.py` covers the
all-false Crossfade state repair, the legacy `type="Random"` migration, the deactivated-manual-type
replacement, and the Random-empty-pool normalization; `tests/test_transitions_tab_setup.py` and
`tests/test_context_menu_activation.py` prove these repairs are reflected live in both operator surfaces.

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
- manual replacement selection after deactivation is deterministic and activated;
- all-false activation explicitly reactivates/persists Crossfade through the canonical normalization
  authority rather than a renderer bypass;
- Random-on + empty effective pool explicitly disables Random, persists an activated manual selection,
  and preserves saved pool membership;
- a stale pre-resolved `transitions.random_choice` is rejected/re-resolved if it becomes deactivated or
  hardware-invalid before factory admission;
- hardware filtering / empty candidate sets never reach a deactivated Crossfade last-resort;
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
