# 04 — Runtime Widgets, Retained Quick Presentation, Shadows and Full Customization

Status: Phase-E/F technical decomposition; Phase-E foundation partially landed  
Last updated: 2026-08-22

Cross-links:

- sequence/work admission: `Current_Plan.md`
- capability activation / E2 UI: `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`
- canonical widget authoring guidance: `Docs/10_WIDGET_GUIDELINES.md`
- style history: `Docs/Custom_Style_Implementation.md`
- deletion ledger: `Future_Cleanup.md`

## 1. Core rule

Do not rewrite the widget ecosystem as QML business logic.

Split:

```text
provider / model / settings / refresh / actions
                    from
runtime pixel presentation
```

Keep the first side in Python unless a separate measured reason earns a different owner.

Move runtime pixels into the display's retained Quick scene.

## 2. Current architecture seam

The old widget stack combines responsibilities that must not be recreated as one giant Python Quick
base class.

`WidgetManager` / current widget setup code still mixes some combination of:

- concrete QWidget creation;
- provider/model lifecycle;
- positioning/stacking;
- visibility/fades;
- compositor readiness;
- live settings application;
- family-specific staging and runtime assumptions.

`BaseOverlayWidget` likewise combines QWidget lifecycle, style, geometry, card/shadow painting and
other pixel-era concerns.

Phase E decomposes ownership; Phase F ports family pixels.

## 3. Landed presentation-neutral family catalog

Phase E has already landed a cheap canonical family catalog in
`rendering/widget_descriptors.py`.

`WIDGET_FAMILY_DESCRIPTORS` is the single family-membership authority mapping stable `family_id` to
member runtime widget ids. Current accessors include:

```text
get_widget_family_descriptors()
get_widget_family_descriptor()
get_family_id_for_widget()
get_active_member_widget_ids()
```

Family availability derives from active runtime descriptors/environment gates rather than maintaining
a competing gate list.

The Spotify visualizer **participates in application-level capability activation** through the neutral
family catalog (family `visualizers`, which **requires** the `media` family). Its runtime/render
ownership remains the special Phase-D visualizer subsystem — capability activation does **not** make it
an ordinary Phase-F widget-presentation family and does **not** move it under `WidgetRuntimeManager`.

The current family catalog includes legacy/dev-gated Imgur only while the old runtime surface still
exists. That does **not** authorize a Quick Imgur port; Phase F removes Imgur instead of migrating it.

## 4. Activation is not ordinary enabled state

Phase E also landed application-level family activation:

```text
widgets.family_activation.<family_id>
```

Use terms precisely:

```text
family activated/deactivated
    = may the family capability/runtime ownership resolve at all?

instance enabled/disabled
    = ordinary configuration inside an activated family
```

Do not write “disabled family owns no provider/model/etc.” when the intended state is application-level
**deactivated**. An ordinary `enabled=False` instance is not automatically equivalent to tearing down
an entire capability family.

At the currently landed runtime seam, `_create_factory_widgets` filters a deactivated family before
concrete runtime widget/model/provider creation and before per-instance enabled handling. This proves a
real runtime consequence while all default activation remains inert/all-on.

The broader E1 `WidgetRuntimeManager` provider/model/resource ownership split is still separate work
until exact source says it has landed. Do not overstate full family dormancy beyond the owners actually
migrated.

Durable destination:

- a deactivated family owns no family-exclusive model/provider/process/poll/timer/Quick component or
  family-specific render resource;
- shared infrastructure remains alive while another activated capability still requires it;
- deactivation preserves detailed saved configuration;
- a fresh process does not import/construct family-heavy implementation solely because the capability
  is catalogued.

See `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`.

## 5. Presentation-neutral widget metadata

Canonical runtime/widget metadata must not depend on constructing a QWidget factory product.

Presentation-neutral descriptors should own stable facts such as:

```text
widget_id
settings key / settings section
family_id
startup stage
default position
monitor-routing keys
CUSTOM participation
base/inheritance keys
service requirements
runtime action/refresh contracts
```

Old factory creation metadata may remain in the old path until its callers are removed. It is not the
final presentation authority.

Quick presentation maps family/runtime identity to retained Quick components through a static registry.
Do not build dynamic third-party plugin discovery, manifests, hot loading or API-version machinery.

## 6. Destination manager split

### 6.1 `WidgetRuntimeManager`

The Phase-E destination owner is presentation-neutral and owns:

- family activation admission;
- model/provider lifetime;
- per-instance enabled/visible intent;
- monitor participation;
- settings updates;
- stacking inputs;
- action routing;
- runtime generation;
- presentation-model registration.

It does **not** own QWidget instances or runtime pixels.

This broader owner is not considered landed merely because the family catalog and creation-admission
gate exist.

### 6.2 Per-display Quick widget presentation host

Owned by each `QuickSceneController`.

It creates/destroys retained Quick components for models assigned to that display and owns:

- `QQuickItem` instance;
- current resolved geometry;
- z order;
- root opacity/fade;
- edit-overlay participation;
- presentation-only resources.

The display scene must not become a per-widget `if/elif` dispatcher.

### 6.3 Static family extensibility boundary

`WidgetRuntimeManager` operates generically through descriptor/family/model contracts.

Family-specific behavior stays in isolated family implementation modules selected by stable static
registry metadata. A new optional built-in family should not require rewriting central scene/runtime
owners.

This is internal modularity, not an external plugin SDK.

## 7. Widget model contract

Each family exposes only the state required for its visual and actions.

### Clock family

Presentation state may include:

```text
formatted time/date strings
analog hand angles if applicable
timezone label
display mode
style/config
```

Keep shared ticker/timezone computation in Python.

### Weather

Presentation state may include:

```text
location label
condition
temperature
forecast rows
icon/condition identity
style/config
```

Keep weather retrieval/cache/provider ownership in Python.

### Media

Presentation state may include:

```text
title / artist / album
artwork
playback state
progress
volume / mute
control availability
provider identity
style/config
```

Keep GSMTC/provider/control command logic in Python.

### Reddit / Gmail / Steam

Expose normalized rows/cards/actions and compact state. Keep retrieval/filter/cache/ranking/service logic
out of QML/render callbacks.

## 8. Shared retained Quick visual primitives — Phase E3

Build small components rather than a base-god-object.

Candidate reusable primitives:

```text
OverlayRoot.qml
OverlayCard.qml
CardShadow.qml
ShadowedText.qml
HeaderRow.qml
Artwork.qml
Separator.qml
ProgressBar.qml
IconButton.qml
```

Use actual names from landed source; the list above describes the intended decomposition, not a required
filename manifest.

Components bind to explicit presentation model/style properties.

E3 remains unfinished until exact source/Current Plan marks it landed.

## 9. Full style state

Keep a presentation-neutral common style structure capable of representing current authored controls,
including as applicable:

```text
font family
font size
text color/alpha
show background
background color/alpha
border width
border color/alpha
corner radius
margin/padding
card shadow enable/color/opacity/blur/offset/spread
text shadow enable/color/opacity/blur/offset
header shadow if distinct
overall widget opacity/fade
global shadow direction
```

Family-specific style remains family-specific.

Do not collapse existing controls merely because one Quick property is more convenient.

## 10. Global eight-direction shadow authority — Phase E4

The abandoned 4.6.9 direction feature is restored through one canonical direction token:

```text
NW  N  NE
 W     E
SW  S  SE
```

Default: `SE`.

Preferred state shape:

```text
ShadowDirection.NW / N / NE / W / E / SW / S / SE
```

Direction controls orientation only. Each shadow class keeps its own authored magnitude/blur/spread/
opacity/color.

Conceptually:

```text
resolved_x = direction.x_sign * authored_x_magnitude
resolved_y = direction.y_sign * authored_y_magnitude
```

Axis-only directions zero the perpendicular component.

Do not retain the old ineffective `widgets.shadows.offset` as a second user-facing magnitude authority.

All shared shadow primitives must be signed-offset safe and reserve visual padding on the affected
side(s), not right/bottom only.

### 10.1 Settings UI

After runtime support exists, add the intended inset 3x3 selector to the existing General/Appearance
bucket:

- eight selectable outer cells;
- selected direction visually inset/pressed;
- center inert;
- default `SE`;
- canonical settings save/preview path;
- no new Settings backend architecture.

A direction-only change must not alter widget geometry, font sizing, content layout, blur/spread,
opacity or per-shadow magnitude.

E4 is future Phase-E work until exact source says it has landed.

## 11. Shadow history and Quick rule

Relevant historical bug evidence includes:

```text
Docs/Historical_Bugs/U-06_MC_Shadow_Cache_Corruption.md
Docs/Historical_Bugs/R-24_Retired_Overlay_Effect_Cache_Busting.md
```

Those failures involved QWidget `QGraphicsEffect`/cache/focus behavior. Qt Quick does not use that
architecture, but migration must still avoid expensive/general effect churn.

### Card shadows

Prefer a dedicated retained mathematical/shader representation for rounded rectangular cards when it
matches appearance and cost better than a general full-source blur.

Properties should cover radius, blur, spread, signed offset, color and opacity. Draw behind the card;
do not toggle effect topology during fades.

### Arbitrary-shape shadows

Use a general effect such as `MultiEffect` only when genuinely required by an arbitrary-shaped visual.
Keep source bounds tight, blur bounds explicit and hidden rendering dormant.

### Text/header shadows

Use the smallest representation that preserves current appearance: retained shadow text or a bounded
effect source where blur is actually required.

No QWidget-style global cache-busting mechanism should reappear.

## 12. Old-corruption regression gate

The Quick widget gallery/installed validation must repeatedly exercise the old stress class, including:

```text
two displays
MC/interaction mode where available
focus display A -> B -> A
context menu open/close
widget click
hide/show
Settings open/recreate
CUSTOM enter/cancel/save
monitor topology recreate
```

Inspect card/text/header shadows, opacity, clipping, stale textures, disappeared shadows and corrupted
blur.

A failure blocks the affected shared primitive/owner, not the selected Qt Quick presenter as a whole.

## 13. Opacity and fades

Distinguish:

- content/background alpha;
- border alpha;
- shadow alpha;
- whole-widget authored fade opacity.

Use retained/root opacity for the authored widget fade when appropriate.

Do not animate by repeatedly enabling/disabling shadow/effect topology.

## 14. Stacking

Keep canonical stacking policy/math outside QML when it is product-owned in Python.

Quick consumes resolved geometry/z order.

Do not make QML anchors a second stacking algorithm. CUSTOM position overrides authored stack placement
according to the existing contract.

## 15. Pixel shift

Keep pixel-shift scheduling/intent outside QML if it remains product-owned there.

Apply the resulting offset as a retained transform/property on the appropriate presentation root.

Do not rebuild widget content for a small positional shift.

## 16. Capability dormancy and lazy Settings

E2 Settings must be able to list capabilities using cheap catalog metadata without constructing family
pages/providers/runtime pixels.

Operator-facing behavior is explicit:

- `SETUP` is always present;
- only activated families expose their normal settings pill;
- deactivating a family while Settings is open removes that pill **immediately**;
- if the removed family page was selected, navigation returns to `SETUP` immediately;
- reactivating immediately restores its pill;
- detailed family pages remain lazy;
- an unbuilt/deactivated page must never overwrite persisted values during Save.

This live navigation decision is UI behavior. Runtime/provider retirement still follows the safe owner
boundary defined by exact landed E1/runtime code; do not invent unsafe immediate teardown from a UI
callback merely to match pill removal.

## 17. Family migration matrix — Phase F

### 17.1 Clock / Clock2 / Clock3

Preserve:

- digital/analog modes;
- seconds;
- timezone;
- day/date;
- calendar layout;
- analog numerals/face shadow;
- inherited secondary-clock styling;
- monitor-specific display-mode overrides.

This is the first ordinary-widget canary.

### 17.2 Weather

Preserve:

- condition icon/alignment/size;
- forecast/details;
- font/margin;
- card style/shadows.

Weather retrieval/cache remains Python-owned.

### 17.3 Media

Preserve:

- artwork/rounded artwork;
- metadata/header frame;
- controls;
- Spotify volume;
- mute;
- playback progress;
- progress shadow/glow;
- live provider updates;
- click/control actions.

### 17.4 Reddit / Reddit2

Preserve:

- header/logo;
- rows/items;
- separators;
- refresh indication;
- click/exit behavior;
- inherited second-instance style/settings.

A later post-migration QoL may add retained in-scene hover/title presentation; that is not required to
port the existing runtime pixel contract unless Current Plan explicitly admits it.

### 17.5 Gmail

Preserve current configured presentation switches, including sender/subject, envelope/three-dot/
refresh indicators, unread/header, timestamp/date mode, grouping, separators, desaturation,
background/border and current sound behavior. Sound/provider logic remains Python-owned.

### 17.6 Steam family

Preserve each supported card's artwork, selection state, accent, capsules, desaturation, metadata rows
and current dev-gate behavior.

Shared Steam services must follow activated capabilities and remaining consumers rather than being
silently duplicated per card.

### 17.7 Imgur — remove, do not port

Imgur is deprecated migration debris.

When Phase F reaches it:

- remove its descriptor/settings/runtime/provider/CUSTOM/build/test surface;
- do not create a Quick component;
- do not repair its provider merely to migrate it;
- do not build a QWidget-to-Quick compatibility presenter;
- let canonical settings cleanup/H0 strip or ignore obsolete persisted state according to the active
  plan.

A current dev-gated Imgur entry in legacy descriptors/catalogs is temporary migration source state,
**not** a supported Quick family target.

There is no later contradictory “port it if still canonical” branch in this document.

## 18. No screenshot-wrapper final implementation

A temporary development capture may be used for visual comparison.

Do not ship:

```text
old QWidget -> grab() -> texture -> Quick
```

as the final widget presentation architecture.

## 19. Tests

Per family use the relevant combination of:

- model/provider behavior;
- activation admission vs instance enabled state;
- settings-to-model mapping;
- lazy Settings hydration/save safety;
- style mapping;
- Quick component instantiation;
- geometry/DPR;
- CUSTOM;
- click/action routes;
- hide/show;
- lifecycle/recreation;
- visual capture/golden where robust;
- deactivated fresh-process dormancy after the responsible owner has migrated.

Shared primitives receive stronger regression coverage because every family depends on them.

Do not call a family migrated because legacy Python model tests still pass.

## 20. Checkpoint cadence

Follow `Current_Plan.md` rather than treating this list as parallel sequencing.

Natural bounded checkpoints include:

- presentation-neutral family/catalog work;
- E1 manager/model/provider split;
- E2 capability Settings UI/lazy navigation;
- common style/shadow primitives;
- each family port;
- shared visual-regression corrections.

Do not batch every family into one commit. High-risk owner/lifecycle boundaries should be independently
audited after push when Current Plan requires it.
